from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

from analytics import (
    build_daily_summary,
    compute_metrics,
    display_table,
    ema,
    ema_alpha_from_days,
    prepare_metric_series,
    sma,
    weekly_summary,
)
from config import load_config
from db import (
    get_activity_records_df,
    get_activity_detail_raw,
    get_activity_raw,
    get_daily_summary_df,
    get_last_sync,
    get_latest_activity_time,
    get_runs_df,
    get_sleep_df,
    get_table_counts,
    get_wellness_df,
    init_db,
    log_sync,
    upsert_activities,
    upsert_activity_details,
    upsert_activity_records,
    upsert_activity_trimp,
    upsert_daily_summary,
    upsert_sleep_daily,
    upsert_wellness_daily,
)
from garmin_client import (
    dump_extract_to_json,
    fetch_garmin_comprehensive,
    fetch_garmin_runs,
    import_runs_from_folder,
)
from synthetic_data import generate_synthetic_runs


st.set_page_config(page_title="Temperance", layout="wide")
st.title("Temperance")
st.caption("Local-first running load tracker (aerobic + mechanical)")

DEFAULT_RESTING_HR = 45.0
DEFAULT_MAX_HR = 200.0
DEFAULT_LTHR = 178.0

cfg = load_config()
init_db(cfg.db_path)
cfg.import_dir.mkdir(parents=True, exist_ok=True)
cfg.private_export_dir.mkdir(parents=True, exist_ok=True)


def format_pace_min_per_km(pace_s_per_km: float | None) -> str:
    if not pace_s_per_km or pace_s_per_km <= 0:
        return "-"
    total_seconds = int(round(float(pace_s_per_km)))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d} min/km"


def filter_by_activity_type(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    if df.empty or mode == "All Activities":
        return df

    sport = df["sport_type"].fillna("").astype(str).str.lower()
    if mode == "All Running":
        mask = sport.str.contains("run") | sport.str.contains("treadmill")
    elif mode == "Running":
        mask = sport.str.contains("run") & ~sport.str.contains("treadmill")
    elif mode == "Treadmill":
        mask = sport.str.contains("treadmill")
    elif mode == "Cycling":
        mask = sport.str.contains("cycl") | sport.str.contains("bike")
    elif mode == "Elliptical":
        mask = sport.str.contains("elliptical")
    else:
        mask = pd.Series([True] * len(df), index=df.index)

    return df.loc[mask].copy()

with st.sidebar:
    st.header("Navigation")
    view = st.radio("Page", ["Dashboard", "Activity Detail", "Recovery Data", "Data Extract"], index=0)
resting_hr = DEFAULT_RESTING_HR
max_hr = DEFAULT_MAX_HR
sex = "male"

st.divider()
if view != "Data Extract":
    st.header("Visualization")
    st.caption(
        f"TRIMP defaults: resting HR={int(DEFAULT_RESTING_HR)}, max HR={int(DEFAULT_MAX_HR)}, "
        f"LTHR={int(DEFAULT_LTHR)} bpm"
    )

runs_df = get_runs_df(cfg.db_path)
metrics_df = compute_metrics(runs_df, resting_hr=float(resting_hr), max_hr=float(max_hr), sex=sex)
if not metrics_df.empty:
    upsert_activity_trimp(
        cfg.db_path,
        [
            {"activity_id": str(r["activity_id"]), "trimp": float(r["trimp"])}
            for _, r in metrics_df[["activity_id", "trimp"]].iterrows()
            if pd.notna(r["trimp"])
        ],
    )
    upsert_daily_summary(
        cfg.db_path,
        build_daily_summary(metrics_df).to_dict(orient="records"),
    )
daily_summary_df = get_daily_summary_df(cfg.db_path)

if view == "Dashboard":
    st.divider()
    st.header("Dashboard")

    if metrics_df.empty:
        st.info(
            "No activities yet. Use Sync above. "
            "For your full archive, run Comprehensive Garmin Extract from Jan 1, 2025."
        )
    else:
        st.caption("Missing-day fill mode applies to chart calculations (SMA/EMA and aggregations).")
        controls = st.columns([1, 1, 1, 1, 1])
        with controls[0]:
            min_day = pd.to_datetime(daily_summary_df["day_utc"]).min().date() if not daily_summary_df.empty else metrics_df["start_time_utc"].min().date()
            max_day = pd.to_datetime(daily_summary_df["day_utc"]).max().date() if not daily_summary_df.empty else metrics_df["start_time_utc"].max().date()
            date_range = st.date_input("Date range", value=(min_day, max_day), min_value=min_day, max_value=max_day)
        with controls[1]:
            activity_filter = st.selectbox(
                "Activity filter",
                ["All Activities", "All Running", "Running", "Treadmill", "Cycling", "Elliptical"],
                index=0,
            )
        with controls[2]:
            chart_type = "line"
            st.caption("Chart type: line")
            weekly_toggle = st.checkbox("Weekly aggregation", value=True)
        with controls[3]:
            fill_mode = st.selectbox("Missing days", ["zero", "ffill"], index=0)
            compare_mode = st.checkbox("Compare mode (up to 3 metrics)", value=False)
        with controls[4]:
            normalize_compare = st.checkbox("Normalize compare (index=100)", value=False, disabled=not compare_mode)
            enable_zoom = st.checkbox("Zoom/pan", value=False)
            legend_toggle = st.checkbox("Legend toggle", value=True)

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = max_day
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)

        filtered_metrics = filter_by_activity_type(metrics_df, activity_filter)
        filtered_daily = build_daily_summary(filtered_metrics)
        if not filtered_daily.empty:
            filtered_daily = filtered_daily.sort_values("day_utc").copy()
            daily_index = pd.date_range(
                start=pd.to_datetime(filtered_daily["day_utc"]).min(),
                end=pd.to_datetime(filtered_daily["day_utc"]).max(),
                freq="D",
            )
            complete_daily = pd.DataFrame({"day_utc": daily_index.strftime("%Y-%m-%d")})
            filtered_daily = complete_daily.merge(filtered_daily, on="day_utc", how="left")
            # Fitness/Fatigue are always computed on continuous daily data with missing days as zero load.
            training_series = filtered_daily["training_load_garmin"].fillna(0.0)
            filtered_daily["fitness"] = ema(training_series, 42)
            filtered_daily["fatigue"] = ema(training_series, 7)
            filtered_daily["form"] = filtered_daily["fitness"] - filtered_daily["fatigue"]

        metric_map = {
            "Distance (km)": "distance_km",
            "Garmin Training Load": "training_load_garmin",
            "Fitness (EWMA 42)": "fitness",
            "Fatigue (EWMA 7)": "fatigue",
            "Form (Fitness - Fatigue)": "form",
            "TRIMP": "trimp_total",
            "Mechanical Load": "mechanical_load_total",
            "Edwards TRIMP": "edwards_trimp_total",
            "Calories Active": "calories_active",
            "Calories Total": "calories_total",
            "Vigorous Minutes": "intensity_minutes_vigorous",
            "Moderate Minutes": "intensity_minutes_moderate",
            "HR Zone 1 Time": "hr_time_in_zone_1",
            "HR Zone 2 Time": "hr_time_in_zone_2",
            "HR Zone 3 Time": "hr_time_in_zone_3",
            "HR Zone 4 Time": "hr_time_in_zone_4",
            "HR Zone 5 Time": "hr_time_in_zone_5",
        }

        base_df = filtered_daily.copy()
        if base_df.empty:
            st.info(f"No data for activity filter: {activity_filter}")
        else:
            if compare_mode:
                left_axis_labels = st.multiselect(
                    "Left axis metrics",
                    list(metric_map.keys()),
                    default=["Garmin Training Load"],
                    max_selections=3,
                )
                right_axis_labels = st.multiselect(
                    "Right axis metrics",
                    list(metric_map.keys()),
                    default=["TRIMP"],
                    max_selections=3,
                )
            else:
                selected_labels = [st.selectbox("Metric", list(metric_map.keys()), index=0)]

            sma_windows = st.text_input("SMA windows (days, comma-separated)", value="")
            ema_windows = st.text_input("EMA windows (days, comma-separated)", value="20,100")

            def _parse_windows(text: str) -> list[int]:
                out: list[int] = []
                for part in text.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        val = int(part)
                    except ValueError:
                        continue
                    if val > 0:
                        out.append(val)
                return out

            sma_ns = _parse_windows(sma_windows)
            ema_ns = _parse_windows(ema_windows)
            if ema_ns:
                alpha_text = ", ".join([f"EMA {n} -> alpha={ema_alpha_from_days(n):.4f}" for n in ema_ns])
                st.caption(alpha_text)

            plot_frames: list[pd.DataFrame] = []
            if compare_mode:
                labels_and_axis = [(label, "left") for label in left_axis_labels] + [
                    (label, "right") for label in right_axis_labels
                ]
            else:
                labels_and_axis = [(label, "left") for label in selected_labels]

            for label, axis_side in labels_and_axis:
                metric = metric_map[label]
                frame = prepare_metric_series(
                    daily_df=base_df.rename(columns={"day_utc": "day_utc"}),
                    metric=metric,
                    start_day=start_ts,
                    end_day=end_ts,
                    fill_method=fill_mode,
                    weekly=weekly_toggle,
                )
                if frame.empty:
                    continue
                frame = frame.rename(columns={metric: "value"})
                frame["series"] = label
                frame["axis_side"] = axis_side
                if compare_mode and normalize_compare:
                    first_value = float(frame["value"].iloc[0]) if not frame.empty else 0.0
                    denom = first_value if first_value != 0 else 1.0
                    frame["value"] = (frame["value"] / denom) * 100.0
                plot_frames.append(frame)

                if not compare_mode:
                    for n in sma_ns:
                        frame[f"sma_{n}"] = sma(frame["value"], n)
                    for n in ema_ns:
                        frame[f"ema_{n}"] = ema(frame["value"], n)
                    overlay_chart_df = frame[["day", "value"] + [c for c in frame.columns if c.startswith(("sma_", "ema_"))]]
                    overlay_long = overlay_chart_df.melt(
                        id_vars=["day"],
                        var_name="series",
                        value_name="metric_value",
                    )
                    mark = alt.Chart(overlay_long)
                    legend_sel = alt.selection_point(fields=["series"], bind="legend") if legend_toggle else None
                    if chart_type == "bar":
                        chart = mark.mark_bar().encode(
                            x="day:T",
                            y=alt.Y("metric_value:Q", axis=alt.Axis(format=".0f")),
                            color="series:N",
                            tooltip=["day:T", "series:N", alt.Tooltip("metric_value:Q", format=".0f")],
                        )
                    else:
                        chart = mark.mark_line(point=True).encode(
                            x="day:T",
                            y=alt.Y("metric_value:Q", axis=alt.Axis(format=".0f")),
                            color="series:N",
                            tooltip=["day:T", "series:N", alt.Tooltip("metric_value:Q", format=".0f")],
                        )
                    if legend_sel is not None:
                        chart = chart.encode(
                            opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.08))
                        ).add_params(legend_sel)
                    if enable_zoom:
                        chart = chart.interactive()
                        st.caption("Tip: drag chart to pan/zoom, double-click to reset.")
                    st.altair_chart(chart, use_container_width=True)

            if compare_mode and plot_frames:
                compare_df = pd.concat(plot_frames, ignore_index=True)
                legend_sel = alt.selection_point(fields=["series"], bind="legend") if legend_toggle else None

                left_df = compare_df[compare_df["axis_side"] == "left"]
                right_df = compare_df[compare_df["axis_side"] == "right"]

                left_chart = (
                    alt.Chart(left_df)
                    .mark_line(point=True)
                    .encode(
                        x="day:T",
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Left axis")),
                        color="series:N",
                        tooltip=["day:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                )
                right_chart = (
                    alt.Chart(right_df)
                    .mark_line(point=True)
                    .encode(
                        x="day:T",
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Right axis", orient="right")),
                        color="series:N",
                        tooltip=["day:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                )

                if legend_sel is not None:
                    left_chart = left_chart.encode(
                        opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.08))
                    )
                    right_chart = right_chart.encode(
                        opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.08))
                    )
                compare_chart = alt.layer(left_chart, right_chart).resolve_scale(y="independent")
                if legend_sel is not None:
                    compare_chart = compare_chart.add_params(legend_sel)
                if enable_zoom:
                    compare_chart = compare_chart.interactive()
                    st.caption("Tip: drag chart to pan/zoom, double-click to reset.")
                st.altair_chart(compare_chart, use_container_width=True)

        table_df = display_table(filtered_metrics)
        st.subheader("Runs")
        st.dataframe(
            table_df,
            use_container_width=True,
            column_config={
                "distance_km": st.column_config.NumberColumn(format="%.2f km"),
                "duration_min": st.column_config.NumberColumn(format="%.1f min"),
                "avg_pace_display": st.column_config.TextColumn("Pace"),
                "trimp": st.column_config.NumberColumn(format="%.1f"),
                "edwards_trimp": st.column_config.NumberColumn(format="%.1f"),
                "mechanical_load": st.column_config.NumberColumn(format="%.1f"),
                "training_load_garmin": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        weekly = weekly_summary(filtered_metrics)
        weekly["week_start"] = pd.to_datetime(weekly["week_start"])
        st.subheader("Weekly TRIMP vs Garmin Training Load")
        if "total_garmin_training_load" in weekly.columns:
            weekly_compare = weekly.melt(
                id_vars=["week_start"],
                value_vars=["total_trimp", "total_garmin_training_load"],
                var_name="series",
                value_name="value",
            )
            weekly_chart = (
                alt.Chart(weekly_compare)
                .mark_line(point=True)
                .encode(
                    x="week_start:T",
                    y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                    color="series:N",
                    tooltip=["week_start", "series", alt.Tooltip("value:Q", format=".0f")],
                )
            )
            if legend_toggle:
                weekly_sel = alt.selection_point(fields=["series"], bind="legend")
                weekly_chart = weekly_chart.encode(
                    opacity=alt.condition(weekly_sel, alt.value(1.0), alt.value(0.08))
                ).add_params(weekly_sel)
            if enable_zoom:
                weekly_chart = weekly_chart.interactive()
            st.altair_chart(weekly_chart, use_container_width=True)

if view == "Activity Detail":
    st.divider()
    st.header("Activity Detail")

    if metrics_df.empty:
        st.info("No activities available.")
    else:
        options_df = metrics_df.copy().sort_values("start_time_utc", ascending=False)
        options_df["label"] = (
            options_df["start_time_utc"].dt.strftime("%Y-%m-%d")
            + " | "
            + options_df["distance_m"].div(1000).round(2).astype(str)
            + " km | "
            + options_df["activity_id"].astype(str)
        )
        selected = st.selectbox("Select activity", options_df["label"].tolist())
        activity_id = options_df.loc[options_df["label"] == selected, "activity_id"].iloc[0]

        row = options_df.loc[options_df["activity_id"] == activity_id].iloc[0]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("TRIMP", f"{row['trimp']:.1f}")
        m2.metric("Garmin Training Load", f"{(row.get('training_load_garmin') or 0):.1f}")
        m3.metric("Edwards TRIMP", f"{(row.get('edwards_trimp') or 0):.1f}")
        sport_type = str(row.get("sport_type") or "").lower()
        show_pace = ("run" in sport_type) or ("treadmill" in sport_type)
        m4.metric("Avg Pace", format_pace_min_per_km(row.get("avg_pace_s_per_km")) if show_pace else "-")

        st.write(
            {
                "activity_id": row["activity_id"],
                "start_time_utc": row["start_time_utc"],
                "sport_type": row["sport_type"],
                "distance_m": row["distance_m"],
                "duration_s": row["duration_s"],
                "avg_hr": row["avg_hr"],
                "max_hr": row["max_hr"],
                "elevation_gain_m": row["elevation_gain_m"],
                "elevation_loss_m": row.get("elevation_loss_m"),
                "avg_cadence": row.get("avg_cadence"),
                "max_cadence": row.get("max_cadence"),
                "avg_stride_length": row.get("avg_stride_length"),
                "vertical_ratio": row.get("vertical_ratio"),
                "vertical_oscillation": row.get("vertical_oscillation"),
                "running_power_avg": row.get("running_power_avg"),
                "running_power_max": row.get("running_power_max"),
                "stamina_start": row.get("stamina_start"),
                "stamina_end": row.get("stamina_end"),
                "training_effect_aerobic": row.get("training_effect_aerobic"),
                "training_effect_anaerobic": row.get("training_effect_anaerobic"),
                "training_load_garmin": row.get("training_load_garmin"),
                "training_load_garmin_field_name": row.get("training_load_garmin_field_name"),
                "training_load_garmin_units": row.get("training_load_garmin_units"),
                "calories_active": row.get("calories_active"),
                "calories_total": row.get("calories_total"),
                "intensity_minutes_vigorous": row.get("intensity_minutes_vigorous"),
                "intensity_minutes_moderate": row.get("intensity_minutes_moderate"),
                "trimp": row.get("trimp"),
                "edwards_trimp": row.get("edwards_trimp"),
                "mechanical_load": row.get("mechanical_load"),
                "performance_condition": row.get("performance_condition"),
                "device_name": row.get("device_name"),
                "manufacturer": row.get("manufacturer"),
                "activity_uuid": row.get("activity_uuid"),
                "owner_id": row.get("owner_id"),
                "owner_full_name": row.get("owner_full_name"),
                "elapsed_duration_s": row.get("elapsed_duration_s"),
                "moving_duration_s": row.get("moving_duration_s"),
                "average_speed_mps": row.get("average_speed_mps"),
                "activity_type_key": row.get("activity_type_key"),
                "activity_type_id": row.get("activity_type_id"),
                "hr_time_in_zone_1": row.get("hr_time_in_zone_1"),
                "hr_time_in_zone_2": row.get("hr_time_in_zone_2"),
                "hr_time_in_zone_3": row.get("hr_time_in_zone_3"),
                "hr_time_in_zone_4": row.get("hr_time_in_zone_4"),
                "hr_time_in_zone_5": row.get("hr_time_in_zone_5"),
                "difference_body_battery": row.get("difference_body_battery"),
                "bmr_calories": row.get("bmr_calories"),
                "is_pr": row.get("is_pr"),
                "split_summaries_json": row.get("split_summaries_json"),
                "source": row["source"],
            }
        )

        records_df = get_activity_records_df(cfg.db_path, str(activity_id))
        if not records_df.empty:
            st.subheader("Per-Record FIT Series")
            records_df["record_time_utc"] = pd.to_datetime(records_df["record_time_utc"], utc=True, errors="coerce")
            record_metric = st.selectbox(
                "Record metric",
                ["heart_rate", "cadence", "power", "speed", "distance", "stamina"],
                index=0,
            )
            plot_df = records_df.dropna(subset=[record_metric])
            if plot_df.empty:
                st.caption(f"No {record_metric} records for this run.")
            else:
                record_chart = (
                    alt.Chart(plot_df)
                    .mark_line()
                    .encode(
                        x="record_time_utc:T",
                        y=f"{record_metric}:Q",
                        tooltip=["record_time_utc", record_metric],
                    )
                )
                st.altair_chart(record_chart, use_container_width=True)

        st.subheader("Data Availability")
        availability_cols = [
            "avg_hr",
            "avg_cadence",
            "avg_stride_length",
            "vertical_ratio",
            "vertical_oscillation",
            "running_power_avg",
            "stamina_start",
            "training_effect_aerobic",
            "performance_condition",
        ]
        availability_df = options_df[["activity_id", "start_time_utc"] + availability_cols].copy()
        for col in availability_cols:
            availability_df[col] = availability_df[col].notna()
        st.dataframe(availability_df, use_container_width=True)

        raw = get_activity_raw(cfg.db_path, str(activity_id))
        if raw:
            with st.expander("Raw summary payload"):
                st.json(raw)

        detail_raw = get_activity_detail_raw(cfg.db_path, str(activity_id))
        if detail_raw:
            with st.expander("Raw detail payload"):
                st.json(detail_raw)

if view == "Recovery Data":
    st.divider()
    st.header("Recovery Data (Garmin)")

    sleep_df = get_sleep_df(cfg.db_path)
    wellness_df = get_wellness_df(cfg.db_path)

    if sleep_df.empty and wellness_df.empty:
        st.info("No sleep/wellness data yet. Run Comprehensive Garmin Extract with wellness enabled.")
    else:
        if not sleep_df.empty:
            st.subheader("Sleep Daily")
            st.dataframe(sleep_df, use_container_width=True)

        if not wellness_df.empty:
            st.subheader("Wellness Daily")
            st.dataframe(wellness_df, use_container_width=True)

if view == "Data Extract":
    st.divider()
    st.header("Data Extract & Sync")

    last_sync = get_last_sync(cfg.db_path)
    if last_sync:
        ok = "success" if last_sync["success"] else "failed"
        st.caption(
            f"Last sync: {last_sync['sync_time_utc']} | source={last_sync['source']} | {ok} | {last_sync['message']}"
        )
    else:
        st.caption("No sync has been run yet.")

    counts = get_table_counts(cfg.db_path)
    st.caption(
        "Local records | "
        f"activities={counts['activities']}, details={counts['activity_details']}, "
        f"records={counts['activity_records']}, sleep={counts['sleep_daily']}, wellness={counts['wellness_daily']}, "
        f"daily_summary={counts['daily_summary']}"
    )
    st.caption(f"Private DB: {cfg.db_path}")
    st.caption(f"Private exports: {cfg.private_export_dir}")

    st.subheader("Quick Sync")
    quick_cols = st.columns([1, 1, 1, 1])
    with quick_cols[0]:
        days_back = st.number_input("Days to sync", min_value=7, max_value=365, value=90)
    with quick_cols[1]:
        source = st.selectbox("Source", ["Garmin API", "File Import", "Both"], index=2)
    with quick_cols[2]:
        run_sync = st.button("Sync activities")
    with quick_cols[3]:
        generate_demo = st.button("Generate demo data")

    st.caption(f"Import folder: {cfg.import_dir}")

    sync_triggered = False

    if run_sync:
        total_rows = 0
        messages: list[str] = []

        latest = get_latest_activity_time(cfg.db_path)

        if source in {"Garmin API", "Both"}:
            if cfg.garmin_email and cfg.garmin_password:
                try:
                    rows = fetch_garmin_runs(
                        email=cfg.garmin_email,
                        password=cfg.garmin_password,
                        days_back=int(days_back),
                        since_utc=latest,
                    )
                    changed = upsert_activities(cfg.db_path, rows)
                    total_rows += len(rows)
                    messages.append(f"Garmin: fetched {len(rows)} runs ({changed} DB row changes).")
                except Exception as exc:
                    msg = (
                        "Garmin login/fetch failed. Verify GARMIN_EMAIL / GARMIN_PASSWORD in .env or env vars. "
                        f"Error: {exc}"
                    )
                    messages.append(msg)
                    st.warning(msg)
            else:
                messages.append("Garmin credentials not set. Skipped Garmin API sync.")

        if source in {"File Import", "Both"}:
            rows = import_runs_from_folder(cfg.import_dir, days_back=int(days_back))
            changed = upsert_activities(cfg.db_path, rows)
            total_rows += len(rows)
            messages.append(f"File import: found {len(rows)} runs ({changed} DB row changes).")

        success = total_rows > 0 or any("Skipped" in m for m in messages)
        log_sync(cfg.db_path, source=source.lower().replace(" ", "_"), success=success, message=" | ".join(messages))

        if total_rows > 0:
            st.success("Quick sync complete. " + " ".join(messages))
        else:
            st.info(
                "No activities found. If Garmin sync fails, place .FIT/.TCX files in "
                f"{cfg.import_dir} and run sync again."
            )
        sync_triggered = True

    if generate_demo:
        demo_rows = generate_synthetic_runs(days_back=int(days_back))
        changes = upsert_activities(cfg.db_path, demo_rows)
        log_sync(
            cfg.db_path,
            source="synthetic",
            success=True,
            message=f"Generated {len(demo_rows)} synthetic runs ({changes} DB row changes).",
        )
        st.success(f"Added {len(demo_rows)} synthetic runs for demo.")
        sync_triggered = True

    st.subheader("Comprehensive Garmin Extract")
    extract_cols = st.columns([1, 1, 1, 1, 1])
    with extract_cols[0]:
        extract_start = st.date_input("Start date", value=date(2025, 1, 1))
    with extract_cols[1]:
        include_details = st.checkbox("Include activity details", value=True)
    with extract_cols[2]:
        include_wellness = st.checkbox("Include sleep + wellness", value=True)
    with extract_cols[3]:
        incremental_extract = st.checkbox("Incremental only", value=True)
    with extract_cols[4]:
        run_extract = st.button("Run comprehensive extract")

    if run_extract:
        if not (cfg.garmin_email and cfg.garmin_password):
            st.error("GARMIN_EMAIL / GARMIN_PASSWORD missing. Add them in environment or .env.")
        else:
            try:
                latest = get_latest_activity_time(cfg.db_path)
                start_day = extract_start
                if incremental_extract and latest:
                    start_day = max(start_day, (latest - timedelta(days=2)).date())
                with st.spinner("Extracting Garmin data. This can take a few minutes..."):
                    extract = fetch_garmin_comprehensive(
                        email=cfg.garmin_email,
                        password=cfg.garmin_password,
                        start_day=start_day,
                        end_day=datetime.now(timezone.utc).date(),
                        include_activity_details=include_details,
                        include_wellness=include_wellness,
                        raw_export_dir=cfg.private_export_dir / "raw",
                    )

                n_a = upsert_activities(cfg.db_path, extract.activities)
                n_d = upsert_activity_details(cfg.db_path, extract.activity_details)
                n_r = upsert_activity_records(cfg.db_path, extract.activity_records)
                n_s = upsert_sleep_daily(cfg.db_path, extract.sleep_daily)
                n_w = upsert_wellness_daily(cfg.db_path, extract.wellness_daily)

                snapshot_file = cfg.private_export_dir / f"garmin_extract_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
                dump_extract_to_json(snapshot_file, extract)

                msg = (
                    f"activities={len(extract.activities)} (db_changes={n_a}), "
                    f"details={len(extract.activity_details)} (db_changes={n_d}), "
                    f"records={len(extract.activity_records)} (db_changes={n_r}), "
                    f"sleep={len(extract.sleep_daily)} (db_changes={n_s}), "
                    f"wellness={len(extract.wellness_daily)} (db_changes={n_w}), "
                    f"errors={len(extract.errors)}"
                )
                log_sync(cfg.db_path, source="garmin_comprehensive", success=True, message=msg)
                st.success("Comprehensive extract complete. " + msg)
                st.info(f"Snapshot saved locally at: {snapshot_file}")
                if extract.errors:
                    st.warning("Some endpoints failed for specific days/activities. First 20 errors:")
                    st.code("\n".join(extract.errors[:20]))
                sync_triggered = True
            except Exception as exc:
                log_sync(cfg.db_path, source="garmin_comprehensive", success=False, message=str(exc))
                st.error(f"Comprehensive extract failed: {exc}")

    if sync_triggered:
        st.rerun()

st.caption(f"Now: {datetime.now(timezone.utc).isoformat()} UTC")

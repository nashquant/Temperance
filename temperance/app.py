from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st

from analytics import compute_metrics, display_table, weekly_summary
from config import load_config
from db import (
    get_activity_records_df,
    get_activity_detail_raw,
    get_activity_raw,
    get_last_sync,
    get_latest_activity_time,
    get_runs_df,
    get_setting,
    get_sleep_df,
    get_table_counts,
    get_wellness_df,
    init_db,
    log_sync,
    save_setting,
    upsert_activities,
    upsert_activity_details,
    upsert_activity_records,
    upsert_activity_metrics,
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

with st.sidebar:
    st.header("Navigation")
    view = st.radio("Page", ["Dashboard", "Activity Detail", "Recovery Data"], index=0)

st.header("Settings")
def_resting = float(get_setting(cfg.db_path, "resting_hr") or 60)
def_max = float(get_setting(cfg.db_path, "max_hr") or 190)
sex = get_setting(cfg.db_path, "sex") or "male"

col1, col2, col3 = st.columns(3)
with col1:
    resting_hr = st.number_input("Resting HR", min_value=30, max_value=100, value=int(def_resting))
with col2:
    max_hr = st.number_input("Max HR", min_value=120, max_value=230, value=int(def_max))
with col3:
    sex = st.selectbox("Sex constant (TRIMP)", ["male", "female"], index=0 if sex == "male" else 1)

if st.button("Save settings"):
    save_setting(cfg.db_path, "resting_hr", str(resting_hr))
    save_setting(cfg.db_path, "max_hr", str(max_hr))
    save_setting(cfg.db_path, "sex", sex)
    st.success("Settings saved.")

st.divider()
st.header("Sync")

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
    f"activities={counts['activities']}, metrics={counts['activity_metrics']}, details={counts['activity_details']}, "
    f"records={counts['activity_records']}, sleep={counts['sleep_daily']}, wellness={counts['wellness_daily']}"
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
            n_m = upsert_activity_metrics(cfg.db_path, extract.activity_metrics)
            n_d = upsert_activity_details(cfg.db_path, extract.activity_details)
            n_r = upsert_activity_records(cfg.db_path, extract.activity_records)
            n_s = upsert_sleep_daily(cfg.db_path, extract.sleep_daily)
            n_w = upsert_wellness_daily(cfg.db_path, extract.wellness_daily)

            snapshot_file = cfg.private_export_dir / f"garmin_extract_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            dump_extract_to_json(snapshot_file, extract)

            msg = (
                f"activities={len(extract.activities)} (db_changes={n_a}), "
                f"metrics={len(extract.activity_metrics)} (db_changes={n_m}), "
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
        except Exception as exc:
            log_sync(cfg.db_path, source="garmin_comprehensive", success=False, message=str(exc))
            st.error(f"Comprehensive extract failed: {exc}")

runs_df = get_runs_df(cfg.db_path)
metrics_df = compute_metrics(runs_df, resting_hr=float(resting_hr), max_hr=float(max_hr), sex=sex)

if view == "Dashboard":
    st.divider()
    st.header("Dashboard")

    if metrics_df.empty:
        st.info(
            "No running activities yet. Use Sync above. "
            "For your full archive, run Comprehensive Garmin Extract from Jan 1, 2025."
        )
    else:
        table_df = display_table(metrics_df)
        st.subheader("Runs")
        st.dataframe(
            table_df,
            use_container_width=True,
            column_config={
                "distance_km": st.column_config.NumberColumn(format="%.2f km"),
                "duration_min": st.column_config.NumberColumn(format="%.1f min"),
                "avg_pace_min_per_km": st.column_config.NumberColumn(format="%.2f min/km"),
                "aerobic_load": st.column_config.NumberColumn(format="%.1f"),
                "mechanical_load": st.column_config.NumberColumn(format="%.1f"),
                "garmin_training_load": st.column_config.NumberColumn(format="%.1f"),
                "aerobic_vs_garmin_delta": st.column_config.NumberColumn(format="%.1f"),
            },
        )

        st.subheader("Trend Overlay (Optional)")
        overlay_metric = st.selectbox(
            "Overlay metric",
            ["None", "running_power_avg", "avg_cadence"],
            index=0,
        )
        if overlay_metric != "None":
            overlay_df = metrics_df.dropna(subset=[overlay_metric]).copy()
            if overlay_df.empty:
                st.caption(f"No {overlay_metric} data available yet.")
            else:
                overlay_chart = (
                    alt.Chart(overlay_df)
                    .mark_line(point=True)
                    .encode(
                        x="start_time_utc:T",
                        y=alt.Y(f"{overlay_metric}:Q", title=overlay_metric),
                        tooltip=["activity_id", "start_time_utc", overlay_metric],
                    )
                )
                st.altair_chart(overlay_chart, use_container_width=True)

        weekly = weekly_summary(metrics_df)
        weekly["week_start"] = pd.to_datetime(weekly["week_start"])

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Weekly Aerobic Load (Model)")
            ch = (
                alt.Chart(weekly)
                .mark_bar()
                .encode(x="week_start:T", y="total_aerobic_load:Q", tooltip=list(weekly.columns))
            )
            st.altair_chart(ch, use_container_width=True)

        with c2:
            st.subheader("Weekly Mechanical Load")
            ch2 = (
                alt.Chart(weekly)
                .mark_bar(color="#f58518")
                .encode(x="week_start:T", y="total_mechanical_load:Q", tooltip=list(weekly.columns))
            )
            st.altair_chart(ch2, use_container_width=True)

        if "total_garmin_training_load" in weekly.columns:
            st.subheader("Weekly Model vs Garmin Training Load")
            compare = weekly.melt(
                id_vars=["week_start"],
                value_vars=["total_aerobic_load", "total_garmin_training_load"],
                var_name="series",
                value_name="value",
            )
            comp_chart = (
                alt.Chart(compare)
                .mark_line(point=True)
                .encode(x="week_start:T", y="value:Q", color="series:N", tooltip=["week_start", "series", "value"])
            )
            st.altair_chart(comp_chart, use_container_width=True)

            per_run = metrics_df.dropna(subset=["garmin_training_load"])
            if not per_run.empty:
                st.subheader("Per-Run: Model Aerobic Load vs Garmin Training Load")
                scatter = (
                    alt.Chart(per_run)
                    .mark_circle(size=90)
                    .encode(
                        x="aerobic_load:Q",
                        y="garmin_training_load:Q",
                        color=alt.Color("distance_m:Q", scale=alt.Scale(scheme="viridis")),
                        tooltip=[
                            "activity_id",
                            "start_time_utc",
                            "distance_m",
                            "aerobic_load",
                            "garmin_training_load",
                            "aerobic_vs_garmin_delta",
                        ],
                    )
                )
                st.altair_chart(scatter, use_container_width=True)

        st.subheader("Daily Run Scatter: Mechanical vs Aerobic")
        scatter2 = (
            alt.Chart(metrics_df)
            .mark_circle(size=90)
            .encode(
                x="aerobic_load:Q",
                y="mechanical_load:Q",
                color=alt.Color("distance_m:Q", scale=alt.Scale(scheme="viridis")),
                tooltip=[
                    "activity_id",
                    "start_time_utc",
                    "distance_m",
                    "duration_s",
                    "avg_hr",
                    "aerobic_load",
                    "mechanical_load",
                ],
            )
        )
        st.altair_chart(scatter2, use_container_width=True)

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
        m1.metric("Model Aerobic", f"{row['aerobic_load']:.1f}")
        m2.metric("Garmin Training Load", f"{(row.get('garmin_training_load') or 0):.1f}")
        m3.metric("Mechanical", f"{row['mechanical_load']:.1f}")
        m4.metric("Avg Pace", format_pace_min_per_km(row.get("avg_pace_s_per_km")))

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
                "moderate_intensity_minutes": row.get("moderate_intensity_minutes"),
                "vigorous_intensity_minutes": row.get("vigorous_intensity_minutes"),
                "difference_body_battery": row.get("difference_body_battery"),
                "bmr_calories": row.get("bmr_calories"),
                "is_pr": row.get("is_pr"),
                "split_summaries_json": row.get("split_summaries_json"),
                "source": row["source"],
                "garmin_training_load": row.get("garmin_training_load"),
                "garmin_aerobic_te": row.get("garmin_aerobic_te"),
                "garmin_anaerobic_te": row.get("garmin_anaerobic_te"),
                "garmin_vo2max": row.get("garmin_vo2max"),
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

st.caption(f"Now: {datetime.now(timezone.utc).isoformat()} UTC")

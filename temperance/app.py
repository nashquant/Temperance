from __future__ import annotations

import json
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
    parse_ma_windows,
    prepare_metric_series,
    weekly_summary,
)
from config import load_config
from db import (
    get_setting,
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
    save_setting,
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
DEFAULT_THRESHOLD_PACE_SEC_PER_KM = 300.0
INJURY_WINDOWS = [
    {"label": "Injury 1", "start": "2025-06-02", "end": "2025-07-15"},
    {"label": "Injury 2", "start": "2025-12-28", "end": "2026-01-20"},
]

cfg = load_config()
init_db(cfg.db_path)
cfg.import_dir.mkdir(parents=True, exist_ok=True)
cfg.private_export_dir.mkdir(parents=True, exist_ok=True)

SETTINGS_KEY_THRESHOLD_PACE_DEFAULT = "threshold_pace_default_sec_per_km"
SETTINGS_KEY_THRESHOLD_PACE_CURVE = "threshold_pace_curve_v1"


def _pace_sec_to_mmss(pace_sec_per_km: float) -> str:
    total_seconds = int(round(float(pace_sec_per_km)))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _pace_mmss_to_sec(text: str) -> float:
    raw = text.strip()
    if ":" in raw:
        mins_str, sec_str = raw.split(":", 1)
        mins = int(mins_str.strip())
        secs = int(sec_str.strip())
        if mins < 0 or secs < 0 or secs >= 60:
            raise ValueError("pace mm:ss must be valid")
        value = mins * 60 + secs
    else:
        value = float(raw)
    if value <= 0:
        raise ValueError("pace must be > 0")
    return float(value)


def _load_threshold_curve_points(db_path) -> list[tuple[datetime, float]]:
    raw = get_setting(db_path, SETTINGS_KEY_THRESHOLD_PACE_CURVE)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return []

    points: list[tuple[datetime, float]] = []
    if not isinstance(payload, list):
        return points
    for row in payload:
        if not isinstance(row, dict):
            continue
        date_s = str(row.get("date", "")).strip()
        pace = row.get("pace_sec_per_km")
        if not date_s:
            continue
        try:
            dt = datetime.fromisoformat(date_s).replace(tzinfo=timezone.utc)
            pace_v = float(pace)
            if pace_v > 0:
                points.append((dt, pace_v))
        except Exception:
            continue
    points.sort(key=lambda x: x[0])
    return points


def _curve_points_to_text(points: list[tuple[datetime, float]]) -> str:
    lines = [f"{dt.date().isoformat()}, {_pace_sec_to_mmss(pace)}" for dt, pace in points]
    return "\n".join(lines)


def _parse_curve_text(text: str) -> list[tuple[datetime, float]]:
    points: list[tuple[datetime, float]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "," not in line:
            raise ValueError(f"Invalid curve row (missing comma): {line}")
        date_part, pace_part = [p.strip() for p in line.split(",", 1)]
        dt = datetime.fromisoformat(date_part).replace(tzinfo=timezone.utc)
        pace_sec = _pace_mmss_to_sec(pace_part)
        points.append((dt, pace_sec))
    points.sort(key=lambda x: x[0])
    dedup: dict[str, float] = {}
    for dt, pace in points:
        dedup[dt.date().isoformat()] = pace
    return [
        (datetime.fromisoformat(d).replace(tzinfo=timezone.utc), p)
        for d, p in sorted(dedup.items(), key=lambda x: x[0])
    ]


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


def apply_specificity_factor(df: pd.DataFrame, enabled: bool, non_running_factor: float) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    sport = out["sport_type"].fillna("").astype(str).str.lower()
    is_running_like = sport.str.contains("run") | sport.str.contains("treadmill")
    out["specificity_factor"] = 1.0
    if enabled:
        out.loc[~is_running_like, "specificity_factor"] = float(non_running_factor)

    factor_cols = [
        "distance_m",
        "trimp",
        "edwards_trimp",
        "mechanical_load",
        "training_load_garmin",
        "calories_active",
        "calories_total",
        "intensity_minutes_vigorous",
        "intensity_minutes_moderate",
        "hr_time_in_zone_1",
        "hr_time_in_zone_2",
        "hr_time_in_zone_3",
        "hr_time_in_zone_4",
        "hr_time_in_zone_5",
    ]
    for col in factor_cols:
        if col in out.columns:
            out[col] = out[col] * out["specificity_factor"]
    return out


@st.cache_data(show_spinner=False)
def cached_compute_metrics(
    runs_df: pd.DataFrame,
    resting_hr: float,
    max_hr: float,
    sex: str,
    threshold_pace_default_sec: float,
    threshold_pace_curve_points: tuple[tuple[str, float], ...],
) -> pd.DataFrame:
    curve_points = [
        (datetime.fromisoformat(d).replace(tzinfo=timezone.utc), float(p))
        for d, p in threshold_pace_curve_points
    ]
    return compute_metrics(
        runs_df,
        resting_hr=resting_hr,
        max_hr=max_hr,
        sex=sex,
        threshold_pace_sec_per_km=threshold_pace_default_sec,
        threshold_pace_curve_points=curve_points,
    )


@st.cache_data(show_spinner=False)
def cached_filtered_views(
    metrics_df: pd.DataFrame,
    activity_filter: str,
    specificity_enabled: bool,
    specificity_factor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered_metrics = filter_by_activity_type(metrics_df, activity_filter)
    filtered_metrics = apply_specificity_factor(
        filtered_metrics, specificity_enabled, specificity_factor
    )
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
        training_series = (
            filtered_daily["tss_total"].fillna(0.0)
            if "tss_total" in filtered_daily.columns
            else filtered_daily["training_load_garmin"].fillna(0.0)
        )
        filtered_daily["fitness"] = ema(training_series, 42)
        filtered_daily["fatigue"] = ema(training_series, 7)
        filtered_daily["overreach"] = (filtered_daily["fatigue"] - filtered_daily["fitness"]).clip(lower=0.0)
        rtss_series = (
            filtered_daily["rtss_total"].fillna(0.0)
            if "rtss_total" in filtered_daily.columns
            else pd.Series([0.0] * len(filtered_daily), index=filtered_daily.index)
        )
        filtered_daily["rfitness"] = ema(rtss_series, 200)
        filtered_daily["rfatigue"] = ema(rtss_series, 7)
        filtered_daily["rform"] = (filtered_daily["rfatigue"] - filtered_daily["rfitness"]).clip(lower=0.0)
    return filtered_metrics, filtered_daily


def build_injury_layer() -> alt.Chart:
    injuries = pd.DataFrame(INJURY_WINDOWS).copy()
    injuries["start"] = pd.to_datetime(injuries["start"])
    # Inclusive end-date visual window.
    injuries["end_exclusive"] = pd.to_datetime(injuries["end"]) + pd.Timedelta(days=1)
    return (
        alt.Chart(injuries)
        .mark_rect(color="#ef4444", opacity=0.12)
        .encode(
            x="start:T",
            x2="end_exclusive:T",
            tooltip=["label:N", "start:T", "end:T"],
        )
    )


@st.cache_data(show_spinner=False)
def build_recovery_daily_frame(sleep_df: pd.DataFrame, wellness_df: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    if not sleep_df.empty:
        s = sleep_df.copy()
        s["day"] = pd.to_datetime(s["day_utc"], errors="coerce")
        s["sleep_duration_h"] = s["sleep_duration_s"] / 3600.0
        s["deep_sleep_h"] = s["deep_sleep_s"] / 3600.0
        s["rem_sleep_h"] = s["rem_sleep_s"] / 3600.0
        parts.append(
            s[
                [
                    "day",
                    "sleep_score",
                    "sleep_duration_h",
                    "deep_sleep_h",
                    "rem_sleep_h",
                ]
            ]
        )
    if not wellness_df.empty:
        w = wellness_df.copy()
        w["day"] = pd.to_datetime(w["day_utc"], errors="coerce")
        parts.append(
            w[
                [
                    "day",
                    "hrv_status",
                    "stress_avg",
                    "training_readiness",
                    "respiration_avg",
                    "resting_hr",
                ]
            ]
        )
    if not parts:
        return pd.DataFrame()

    merged = parts[0]
    for p in parts[1:]:
        merged = merged.merge(p, on="day", how="outer")
    return merged.sort_values("day")

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
    saved_tp_raw = get_setting(cfg.db_path, SETTINGS_KEY_THRESHOLD_PACE_DEFAULT)
    try:
        saved_threshold_pace_sec = float(saved_tp_raw) if saved_tp_raw else DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    except Exception:
        saved_threshold_pace_sec = DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    saved_curve_points = _load_threshold_curve_points(cfg.db_path)

    with st.expander("rTSS Threshold Pace Curve", expanded=False):
        st.caption("Default applies when no curve point is active for an activity date.")
        tp_default_text = st.text_input(
            "Default Threshold Pace (mm:ss per km)",
            value=_pace_sec_to_mmss(saved_threshold_pace_sec),
            key="tp_default_text",
        )
        tp_curve_text = st.text_area(
            "Curve (one per line: YYYY-MM-DD, mm:ss)",
            value=_curve_points_to_text(saved_curve_points),
            height=120,
            key="tp_curve_text",
        )
        if st.button("Save Threshold Curve", key="save_threshold_curve_btn"):
            try:
                default_sec = _pace_mmss_to_sec(tp_default_text)
                parsed_curve = _parse_curve_text(tp_curve_text)
                curve_payload = [
                    {"date": dt.date().isoformat(), "pace_sec_per_km": float(p)}
                    for dt, p in parsed_curve
                ]
                save_setting(cfg.db_path, SETTINGS_KEY_THRESHOLD_PACE_DEFAULT, str(default_sec))
                save_setting(cfg.db_path, SETTINGS_KEY_THRESHOLD_PACE_CURVE, json.dumps(curve_payload))
                cached_compute_metrics.clear()
                cached_filtered_views.clear()
                st.success("Threshold pace settings saved.")
            except Exception as exc:
                st.error(f"Could not save threshold pace settings: {exc}")
else:
    saved_tp_raw = get_setting(cfg.db_path, SETTINGS_KEY_THRESHOLD_PACE_DEFAULT)
    try:
        saved_threshold_pace_sec = float(saved_tp_raw) if saved_tp_raw else DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    except Exception:
        saved_threshold_pace_sec = DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    saved_curve_points = _load_threshold_curve_points(cfg.db_path)

runs_df = get_runs_df(cfg.db_path)
metrics_df = cached_compute_metrics(
    runs_df,
    resting_hr=float(resting_hr),
    max_hr=float(max_hr),
    sex=sex,
    threshold_pace_default_sec=float(saved_threshold_pace_sec),
    threshold_pace_curve_points=tuple((dt.date().isoformat(), float(p)) for dt, p in saved_curve_points),
)
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
        st.caption("Missing-day fill mode applies to chart calculations (EMA and aggregations).")
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
            specificity_factor_on = st.checkbox("Specificity factor", value=True)
            specificity_factor_value = st.number_input(
                "Non-running factor",
                min_value=0.0,
                max_value=1.5,
                value=0.85,
                step=0.05,
                format="%.2f",
                disabled=not specificity_factor_on,
            )

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = max_day
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)

        filtered_metrics, filtered_daily = cached_filtered_views(
            metrics_df,
            activity_filter=activity_filter,
            specificity_enabled=specificity_factor_on,
            specificity_factor=float(specificity_factor_value),
        )

        metric_map = {
            "Distance (km)": ("distance_km", "sum"),
            "Garmin Training Load": ("training_load_garmin", "sum"),
            "Fitness (EWMA 42)": ("fitness", "mean"),
            "Fatigue (EWMA 7)": ("fatigue", "mean"),
            "Overreach (Fatigue - Fitness)": ("overreach", "mean"),
            "Running Economy (EWMA 200, rTSS)": ("rfitness", "mean"),
            "Pounding (EWMA 7, rTSS)": ("rfatigue", "mean"),
            "Injury Risk (Pounding - Running Economy)": ("rform", "mean"),
            "rTSS": ("rtss_total", "sum"),
            "TSS": ("tss_total", "sum"),
            "TRIMP": ("trimp_total", "sum"),
            "Edwards TRIMP": ("edwards_trimp_total", "sum"),
            "Calories Active": ("calories_active", "sum"),
            "Calories Total": ("calories_total", "sum"),
            "Vigorous Minutes": ("intensity_minutes_vigorous", "sum"),
            "Moderate Minutes": ("intensity_minutes_moderate", "sum"),
            "HR Zone 1 %": ("hr_zone_1_pct", "mean"),
            "HR Zone 2 %": ("hr_zone_2_pct", "mean"),
            "HR Zone 3 %": ("hr_zone_3_pct", "mean"),
            "HR Zone 4 %": ("hr_zone_4_pct", "mean"),
            "HR Zone 5 %": ("hr_zone_5_pct", "mean"),
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
                metric_labels = list(metric_map.keys())
                default_metric = "rTSS"
                default_index = metric_labels.index(default_metric) if default_metric in metric_labels else 0
                selected_labels = [st.selectbox("Metric", metric_labels, index=default_index)]

            ema_windows = st.text_input("EMA windows (days, comma-separated)", value="4,16")
            ema_ns, ema_pairs = parse_ma_windows(ema_windows)
            if ema_ns:
                alpha_text = ", ".join([f"EMA {n} -> alpha={ema_alpha_from_days(n):.4f}" for n in ema_ns])
                st.caption(alpha_text)
            if ema_pairs:
                pair_text = ", ".join([f"EMA{a}-EMA{b}" for a, b in ema_pairs])
                st.caption(f"EMA spread overlays: {pair_text}")

            plot_frames: list[pd.DataFrame] = []
            if compare_mode:
                labels_and_axis = [(label, "left") for label in left_axis_labels] + [
                    (label, "right") for label in right_axis_labels
                ]
            else:
                labels_and_axis = [(label, "left") for label in selected_labels]

            for label, axis_side in labels_and_axis:
                metric, weekly_agg = metric_map[label]
                frame = prepare_metric_series(
                    daily_df=base_df.rename(columns={"day_utc": "day_utc"}),
                    metric=metric,
                    start_day=start_ts,
                    end_day=end_ts,
                    fill_method=fill_mode,
                    weekly=weekly_toggle,
                    weekly_agg=weekly_agg,
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
                    overlay_cols: list[str] = []
                    for n in ema_ns:
                        col = f"EMA{n}"
                        frame[col] = ema(frame["value"], n)
                        overlay_cols.append(col)
                    for a, b in ema_pairs:
                        col_a = f"EMA{a}"
                        col_b = f"EMA{b}"
                        if col_a not in frame.columns:
                            frame[col_a] = ema(frame["value"], a)
                        if col_b not in frame.columns:
                            frame[col_b] = ema(frame["value"], b)
                        spread_col = f"EMA{a}-EMA{b}"
                        frame[spread_col] = frame[col_a] - frame[col_b]
                        overlay_cols.append(spread_col)
                    overlay_cols = list(dict.fromkeys(overlay_cols))
                    overlay_chart_df = frame[["day", "value"] + overlay_cols]
                    overlay_long = overlay_chart_df.melt(
                        id_vars=["day"],
                        var_name="series",
                        value_name="metric_value",
                    )
                    mark = alt.Chart(overlay_long)
                    legend_sel = alt.selection_point(fields=["series"], bind="legend") if legend_toggle else None
                    chart = mark.mark_line(point=True, opacity=0.65).encode(
                        x="day:T",
                        y=alt.Y("metric_value:Q", axis=alt.Axis(format=".0f")),
                        color=alt.Color("series:N", legend=alt.Legend(orient="bottom", direction="horizontal")),
                        tooltip=["day:T", "series:N", alt.Tooltip("metric_value:Q", format=".0f")],
                    )
                    if legend_sel is not None:
                        chart = chart.encode(
                            opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.08))
                        ).add_params(legend_sel)
                    chart = alt.layer(build_injury_layer(), chart)
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
                    .mark_line(point=True, opacity=0.65)
                    .encode(
                        x="day:T",
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Left axis")),
                        color=alt.Color("series:N", legend=alt.Legend(orient="bottom", direction="horizontal")),
                        tooltip=["day:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                )
                right_chart = (
                    alt.Chart(right_df)
                    .mark_line(point=True, opacity=0.65)
                    .encode(
                        x="day:T",
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Right axis", orient="right")),
                        color=alt.Color("series:N", legend=alt.Legend(orient="bottom", direction="horizontal")),
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
                compare_chart = alt.layer(build_injury_layer(), left_chart, right_chart).resolve_scale(
                    y="independent"
                )
                if legend_sel is not None:
                    compare_chart = compare_chart.add_params(legend_sel)
                if enable_zoom:
                    compare_chart = compare_chart.interactive()
                    st.caption("Tip: drag chart to pan/zoom, double-click to reset.")
                st.altair_chart(compare_chart, use_container_width=True)

        table_df = display_table(filtered_metrics)
        st.subheader("Activities")
        st.dataframe(
            table_df,
            use_container_width=True,
            column_config={
                "distance_km": st.column_config.NumberColumn(format="%.2f km"),
                "duration_min": st.column_config.NumberColumn(format="%.1f min"),
                "avg_pace_display": st.column_config.TextColumn("Pace"),
                "trimp": st.column_config.NumberColumn(format="%.1f"),
                "rtss": st.column_config.NumberColumn("rTSS", format="%.1f"),
                "tss": st.column_config.NumberColumn("TSS", format="%.1f"),
                "edwards_trimp": st.column_config.NumberColumn(format="%.1f"),
                "training_load_garmin": st.column_config.NumberColumn(format="%.1f"),
                "specificity_factor": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        weekly = weekly_summary(filtered_metrics)
        weekly["week_start"] = pd.to_datetime(weekly["week_start"])

        if "total_tss" in weekly.columns and "total_rtss" in weekly.columns and not weekly.empty:
            weekly_tss = weekly[["week_start", "total_tss", "total_rtss"]].copy().sort_values("week_start")
            weekly_tss_plot = weekly_tss.melt(
                id_vars=["week_start"],
                value_vars=["total_tss", "total_rtss"],
                var_name="series",
                value_name="value",
            )
            st.subheader("Weekly TSS vs rTSS")
            weekly_tss_chart = (
                alt.Chart(weekly_tss_plot)
                .mark_line(point=True)
                .encode(
                    x=alt.X("week_start:T", axis=alt.Axis(title="")),
                    y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                    color=alt.Color("series:N", legend=alt.Legend(orient="bottom", direction="horizontal")),
                    tooltip=["week_start", "series", alt.Tooltip("value:Q", format=".0f")],
                )
            )
            if legend_toggle:
                weekly_tss_sel = alt.selection_point(fields=["series"], bind="legend")
                weekly_tss_chart = weekly_tss_chart.encode(
                    opacity=alt.condition(weekly_tss_sel, alt.value(1.0), alt.value(0.08))
                ).add_params(weekly_tss_sel)
            weekly_tss_chart = alt.layer(build_injury_layer(), weekly_tss_chart)
            if enable_zoom:
                weekly_tss_chart = weekly_tss_chart.interactive()
            st.altair_chart(weekly_tss_chart, use_container_width=True)

        st.subheader("Weekly Fitness vs Fatigue")
        if not filtered_daily.empty and "fitness" in filtered_daily.columns and "fatigue" in filtered_daily.columns:
            weekly_ff = filtered_daily[["day_utc", "fitness", "fatigue"]].copy()
            weekly_ff["day"] = pd.to_datetime(weekly_ff["day_utc"], errors="coerce")
            weekly_ff = weekly_ff.dropna(subset=["day"])
            weekly_ff["fitness"] = pd.to_numeric(weekly_ff["fitness"], errors="coerce").fillna(0.0)
            weekly_ff["fatigue"] = pd.to_numeric(weekly_ff["fatigue"], errors="coerce").fillna(0.0)
            weekly_ff["week_start"] = weekly_ff["day"].dt.to_period("W-SUN").dt.start_time
            weekly_ff = (
                weekly_ff.groupby("week_start", as_index=False)[["fitness", "fatigue"]]
                .mean()
                .sort_values("week_start")
            )
            weekly_ff_long = weekly_ff.melt(
                id_vars=["week_start"],
                value_vars=["fitness", "fatigue"],
                var_name="series",
                value_name="value",
            )
            weekly_ff_long["series"] = weekly_ff_long["series"].replace(
                {"fitness": "Fitness", "fatigue": "Fatigue"}
            )
            ff_chart = (
                alt.Chart(weekly_ff_long)
                .mark_line(point=True)
                .encode(
                    x=alt.X("week_start:T", axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10)),
                    y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                    color=alt.Color(
                        "series:N",
                        legend=alt.Legend(orient="bottom", direction="horizontal"),
                        scale=alt.Scale(domain=["Fitness", "Fatigue"], range=["#60a5fa", "#f59e0b"]),
                    ),
                    tooltip=["week_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                )
            )
            if legend_toggle:
                ff_sel = alt.selection_point(fields=["series"], bind="legend")
                ff_chart = ff_chart.encode(
                    opacity=alt.condition(ff_sel, alt.value(1.0), alt.value(0.08))
                ).add_params(ff_sel)
            ff_chart = alt.layer(build_injury_layer(), ff_chart)
            if enable_zoom:
                ff_chart = ff_chart.interactive()
            st.altair_chart(ff_chart, use_container_width=True)
        else:
            st.caption("No fitness/fatigue data to plot.")

        st.subheader("Weekly Running Economy vs Pounding")
        if not filtered_daily.empty and "rfitness" in filtered_daily.columns and "rfatigue" in filtered_daily.columns:
            weekly_rff = filtered_daily[["day_utc", "rfitness", "rfatigue"]].copy()
            weekly_rff["day"] = pd.to_datetime(weekly_rff["day_utc"], errors="coerce")
            weekly_rff = weekly_rff.dropna(subset=["day"])
            weekly_rff["rfitness"] = pd.to_numeric(weekly_rff["rfitness"], errors="coerce").fillna(0.0)
            weekly_rff["rfatigue"] = pd.to_numeric(weekly_rff["rfatigue"], errors="coerce").fillna(0.0)
            weekly_rff["week_start"] = weekly_rff["day"].dt.to_period("W-SUN").dt.start_time
            weekly_rff = (
                weekly_rff.groupby("week_start", as_index=False)[["rfitness", "rfatigue"]]
                .mean()
                .sort_values("week_start")
            )
            weekly_rff_long = weekly_rff.melt(
                id_vars=["week_start"],
                value_vars=["rfitness", "rfatigue"],
                var_name="series",
                value_name="value",
            )
            weekly_rff_long["series"] = weekly_rff_long["series"].replace(
                {"rfitness": "Running Economy", "rfatigue": "Pounding"}
            )
            rff_chart = (
                alt.Chart(weekly_rff_long)
                .mark_line(point=True)
                .encode(
                    x=alt.X("week_start:T", axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10)),
                    y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                    color=alt.Color(
                        "series:N",
                        legend=alt.Legend(orient="bottom", direction="horizontal"),
                        scale=alt.Scale(domain=["Running Economy", "Pounding"], range=["#22c55e", "#ef4444"]),
                    ),
                    tooltip=["week_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                )
            )
            if legend_toggle:
                rff_sel = alt.selection_point(fields=["series"], bind="legend")
                rff_chart = rff_chart.encode(
                    opacity=alt.condition(rff_sel, alt.value(1.0), alt.value(0.08))
                ).add_params(rff_sel)
            rff_chart = alt.layer(build_injury_layer(), rff_chart)
            if enable_zoom:
                rff_chart = rff_chart.interactive()
            st.altair_chart(rff_chart, use_container_width=True)
        else:
            st.caption("No Running Economy/Pounding data to plot.")

        st.subheader("Weekly Overreach vs Injury Risk")
        if not filtered_daily.empty and "overreach" in filtered_daily.columns and "rform" in filtered_daily.columns:
            weekly_fr = filtered_daily[["day_utc", "overreach", "rform"]].copy()
            weekly_fr["day"] = pd.to_datetime(weekly_fr["day_utc"], errors="coerce")
            weekly_fr = weekly_fr.dropna(subset=["day"])
            weekly_fr["overreach"] = pd.to_numeric(weekly_fr["overreach"], errors="coerce").fillna(0.0)
            weekly_fr["rform"] = pd.to_numeric(weekly_fr["rform"], errors="coerce").fillna(0.0)
            weekly_fr["week_start"] = weekly_fr["day"].dt.to_period("W-SUN").dt.start_time
            weekly_fr = (
                weekly_fr.groupby("week_start", as_index=False)[["overreach", "rform"]]
                .mean()
                .sort_values("week_start")
            )
            weekly_fr_long = weekly_fr.melt(
                id_vars=["week_start"],
                value_vars=["overreach", "rform"],
                var_name="series",
                value_name="value",
            )
            weekly_fr_long["series"] = weekly_fr_long["series"].replace(
                {"overreach": "Overreach", "rform": "Injury Risk"}
            )
            fr_chart = (
                alt.Chart(weekly_fr_long)
                .mark_line(point=True)
                .encode(
                    x=alt.X("week_start:T", axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10)),
                    y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                    color=alt.Color(
                        "series:N",
                        legend=alt.Legend(orient="bottom", direction="horizontal"),
                        scale=alt.Scale(domain=["Overreach", "Injury Risk"], range=["#60a5fa", "#ef4444"]),
                    ),
                    tooltip=["week_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                )
            )
            if legend_toggle:
                fr_sel = alt.selection_point(fields=["series"], bind="legend")
                fr_chart = fr_chart.encode(
                    opacity=alt.condition(fr_sel, alt.value(1.0), alt.value(0.08))
                ).add_params(fr_sel)
            fr_chart = alt.layer(build_injury_layer(), fr_chart)
            if enable_zoom:
                fr_chart = fr_chart.interactive()
            st.altair_chart(fr_chart, use_container_width=True)
        else:
            st.caption("No Overreach/Injury Risk data to plot.")

        st.subheader("Garmin Training Load vs. Total Calories")
        if (
            "total_garmin_training_load" in weekly.columns
            and "total_calories" in weekly.columns
            and not weekly.empty
        ):
            weekly_gc = weekly[["week_start", "total_garmin_training_load", "total_calories"]].copy()
            weekly_gc["week_start"] = pd.to_datetime(weekly_gc["week_start"], errors="coerce")
            weekly_gc["total_garmin_training_load"] = pd.to_numeric(
                weekly_gc["total_garmin_training_load"], errors="coerce"
            ).fillna(0.0)
            weekly_gc["total_calories"] = pd.to_numeric(
                weekly_gc["total_calories"], errors="coerce"
            ).fillna(0.0)
            weekly_gc = weekly_gc.dropna(subset=["week_start"]).sort_values("week_start")

            if weekly_gc.empty:
                st.caption("No weekly Garmin training load/calories data to plot.")
            else:
                weekly_gc_long = pd.DataFrame(
                    {
                        "week_start": pd.concat([weekly_gc["week_start"], weekly_gc["week_start"]], ignore_index=True),
                        "series": ["Garmin Training Load"] * len(weekly_gc) + ["Total Calories"] * len(weekly_gc),
                        "value": pd.concat(
                            [weekly_gc["total_garmin_training_load"], weekly_gc["total_calories"]],
                            ignore_index=True,
                        ),
                    }
                )

                base = alt.Chart(weekly_gc_long).encode(
                    x=alt.X(
                        "week_start:T",
                        axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10),
                    ),
                    color=alt.Color(
                        "series:N",
                        legend=alt.Legend(orient="bottom", direction="horizontal"),
                        scale=alt.Scale(
                            domain=["Garmin Training Load", "Total Calories"],
                            range=["#60a5fa", "#f59e0b"],
                        ),
                    ),
                    tooltip=["week_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                )
                legend_sel = alt.selection_point(fields=["series"], bind="legend") if legend_toggle else None
                left_chart = base.transform_filter(alt.datum.series == "Garmin Training Load").mark_line(point=True).encode(
                    y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Garmin Training Load"))
                )
                right_chart = base.transform_filter(alt.datum.series == "Total Calories").mark_line(point=True).encode(
                    y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Total Calories", orient="right"))
                )
                if legend_sel is not None:
                    left_chart = left_chart.encode(
                        opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.08))
                    )
                    right_chart = right_chart.encode(
                        opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.08))
                    )
                weekly_chart = alt.layer(left_chart, right_chart).resolve_scale(y="independent")
                if legend_sel is not None:
                    weekly_chart = weekly_chart.add_params(legend_sel)
                if enable_zoom:
                    weekly_chart = weekly_chart.interactive()
                st.altair_chart(weekly_chart, use_container_width=True)
        else:
            st.caption("No weekly Garmin training load/calories data to plot.")

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
        st.subheader("Recovery Analytics")
        recovery_df = build_recovery_daily_frame(sleep_df, wellness_df)
        if not recovery_df.empty:
            metric_map = {
                "HRV (avg)": ("hrv_status", "avg"),
                "Stress Avg (avg)": ("stress_avg", "avg"),
                "Training Readiness (avg)": ("training_readiness", "avg"),
                "Respiration Avg (avg)": ("respiration_avg", "avg"),
                "Resting HR (avg)": ("resting_hr", "avg"),
                "Sleep Score (avg)": ("sleep_score", "avg"),
                "Deep Sleep (h, sum)": ("deep_sleep_h", "sum"),
                "Sleep Duration (h, sum)": ("sleep_duration_h", "sum"),
                "REM Sleep (h, sum)": ("rem_sleep_h", "sum"),
            }
            rc1, rc2, rc3 = st.columns([1, 1, 1])
            with rc1:
                r_min = recovery_df["day"].min().date()
                r_max = recovery_df["day"].max().date()
                r_range = st.date_input(
                    "Recovery date range",
                    value=(r_min, r_max),
                    min_value=r_min,
                    max_value=r_max,
                    key="recovery_range",
                )
            with rc2:
                recovery_weekly = st.checkbox("Weekly aggregation", value=True, key="recovery_weekly")
            with rc3:
                selected_recovery_metrics = st.multiselect(
                    "Recovery metrics",
                    list(metric_map.keys()),
                    default=["Resting HR (avg)", "Sleep Duration (h, sum)"],
                    key="recovery_metrics",
                )

            if isinstance(r_range, tuple) and len(r_range) == 2:
                r_start, r_end = r_range
            else:
                r_start = r_end = r_max
            r_start_ts = pd.Timestamp(r_start)
            r_end_ts = pd.Timestamp(r_end)

            plot_long_frames: list[pd.DataFrame] = []
            frame = recovery_df[(recovery_df["day"] >= r_start_ts) & (recovery_df["day"] <= r_end_ts)].copy()
            if not frame.empty and selected_recovery_metrics:
                if recovery_weekly:
                    frame["week_start"] = frame["day"].dt.to_period("W-SUN").dt.start_time
                for label in selected_recovery_metrics:
                    col, agg_type = metric_map[label]
                    if col not in frame.columns:
                        continue
                    if recovery_weekly:
                        if agg_type == "sum":
                            g = (
                                frame.groupby("week_start", as_index=False)[col]
                                .sum()
                                .rename(columns={"week_start": "day", col: "value"})
                            )
                        else:
                            g = (
                                frame.groupby("week_start", as_index=False)[col]
                                .mean()
                                .rename(columns={"week_start": "day", col: "value"})
                            )
                    else:
                        g = frame[["day", col]].rename(columns={col: "value"})
                    g["series"] = label
                    plot_long_frames.append(g)

            if plot_long_frames:
                recovery_long = pd.concat(plot_long_frames, ignore_index=True).dropna(subset=["value"])
                if not recovery_long.empty:
                    rec_sel = alt.selection_point(fields=["series"], bind="legend")
                    recovery_chart = (
                        alt.Chart(recovery_long)
                        .mark_line(point=True)
                        .encode(
                            x="day:T",
                            y=alt.Y("value:Q", axis=alt.Axis(format=".2f")),
                            color="series:N",
                            tooltip=["day:T", "series:N", alt.Tooltip("value:Q", format=".2f")],
                            opacity=alt.condition(rec_sel, alt.value(1.0), alt.value(0.08)),
                        )
                        .add_params(rec_sel)
                    )
                    st.altair_chart(recovery_chart, use_container_width=True)
                else:
                    st.caption("No recovery values in selected range for selected metrics.")
            else:
                st.caption("Select at least one recovery metric to plot.")

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

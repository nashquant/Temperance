from __future__ import annotations

import math
import re
from datetime import datetime

import pandas as pd
import numpy as np

from models import mechanical_load


def compute_metrics(
    runs_df: pd.DataFrame,
    resting_hr: float | None = None,
    max_hr: float | None = None,
    sex: str = "male",
    threshold_pace_sec_per_km: float = 300.0,
    lthr_bpm: float = 178.0,
    threshold_pace_curve_points: list[tuple[datetime, float]] | None = None,
    lthr_curve_points: list[tuple[datetime, float]] | None = None,
) -> pd.DataFrame:
    if runs_df.empty:
        return runs_df

    def _piecewise_series(
        start_ts: pd.Series,
        default_value: float,
        points: list[tuple[datetime, float]] | None,
    ) -> pd.Series:
        out = pd.Series(float(default_value), index=start_ts.index, dtype=float)
        if not points:
            return out
        points_df = pd.DataFrame(points, columns=["effective_at", "value"]).copy()
        points_df["effective_at"] = pd.to_datetime(points_df["effective_at"], utc=True, errors="coerce")
        points_df["value"] = pd.to_numeric(points_df["value"], errors="coerce")
        points_df = points_df.dropna(subset=["effective_at", "value"]).sort_values("effective_at")
        if points_df.empty:
            return out

        ts_df = pd.DataFrame({"idx": start_ts.index, "ts": pd.to_datetime(start_ts, utc=True, errors="coerce")})
        ts_df = ts_df.dropna(subset=["ts"]).sort_values("ts")
        if ts_df.empty:
            return out

        merged = pd.merge_asof(
            ts_df,
            points_df.rename(columns={"effective_at": "ts"}),
            on="ts",
            direction="backward",
        )
        out.loc[merged["idx"].to_numpy()] = pd.to_numeric(merged["value"], errors="coerce").fillna(float(default_value)).to_numpy()
        return out

    df = runs_df.copy()
    df["start_time_utc"] = pd.to_datetime(df["start_time_utc"], utc=True, errors="coerce")

    # Fill pace where missing from duration and distance for running-like activities only.
    is_running_like = (
        df["sport_type"].fillna("").astype(str).str.lower().str.contains("run")
        | df["sport_type"].fillna("").astype(str).str.lower().str.contains("treadmill")
    )
    missing_pace = df["avg_pace_s_per_km"].isna() & is_running_like
    df.loc[missing_pace, "avg_pace_s_per_km"] = (
        df.loc[missing_pace, "duration_s"] / (df.loc[missing_pace, "distance_m"] / 1000.0)
    )

    # TRIMP-based models are disabled in curve-first v1.
    df["aerobic_load"] = 0.0
    df["trimp"] = 0.0
    df["edwards_trimp"] = 0.0

    tp_series = _piecewise_series(
        df["start_time_utc"],
        default_value=float(threshold_pace_sec_per_km),
        points=threshold_pace_curve_points,
    )
    lthr_series = _piecewise_series(
        df["start_time_utc"],
        default_value=float(lthr_bpm),
        points=lthr_curve_points,
    )
    df["rtss"] = pd.NA
    df["tss"] = pd.NA

    running_idx = is_running_like.fillna(False)
    duration_s = pd.to_numeric(df["duration_s"], errors="coerce")
    avg_hr = pd.to_numeric(df["avg_hr"], errors="coerce") if "avg_hr" in df.columns else pd.Series(float("nan"), index=df.index)
    avg_pace = (
        pd.to_numeric(df["avg_pace_s_per_km"], errors="coerce")
        if "avg_pace_s_per_km" in df.columns
        else pd.Series(float("nan"), index=df.index)
    )

    # hrTSS from LTHR curve.
    tss_mask = (duration_s > 0) & (avg_hr > 0) & (avg_hr <= 260) & (lthr_series > 0)
    df.loc[tss_mask, "tss"] = (
        duration_s[tss_mask] * ((avg_hr[tss_mask] / lthr_series[tss_mask]) ** 2) / 3600.0 * 100.0
    )

    # rTSS for running/treadmill only.
    rtss_mask = running_idx & (duration_s > 0) & (avg_pace > 0) & (tp_series > 0)
    df.loc[rtss_mask, "rtss"] = (
        duration_s[rtss_mask]
        * ((tp_series[rtss_mask] / avg_pace[rtss_mask]) ** 2)
        / 3600.0
        * 100.0
    )

    df["distance_proxy_km"] = pd.NA
    df["pace_proxy_sec_per_km"] = pd.NA
    df["distance_proxy_method"] = "unavailable"
    df["if_proxy"] = pd.NA
    sport_lower = df["sport_type"].fillna("").astype(str).str.lower()
    is_strength = sport_lower.str.contains("strength_training")
    distance_m_num = pd.to_numeric(df.get("distance_m"), errors="coerce")
    duration_num = pd.to_numeric(df.get("duration_s"), errors="coerce")
    avg_pace_num = pd.to_numeric(df.get("avg_pace_s_per_km"), errors="coerce")
    tss_num = pd.to_numeric(df.get("tss"), errors="coerce")

    # Running/treadmill: proxy equals actual distance/pace.
    run_mask = running_idx
    run_distance = distance_m_num / 1000.0
    df.loc[run_mask, "distance_proxy_km"] = run_distance[run_mask]
    run_pace_valid = run_mask & (avg_pace_num > 0)
    df.loc[run_pace_valid, "pace_proxy_sec_per_km"] = avg_pace_num[run_pace_valid].round()
    df.loc[run_mask, "distance_proxy_method"] = "none_running"
    run_if_valid = run_mask & (tp_series > 0) & (avg_pace_num > 0)
    df.loc[run_if_valid, "if_proxy"] = tp_series[run_if_valid] / avg_pace_num[run_if_valid]

    # Non-running: TSS parity solve with specificity_ratio fixed at 0.8.
    non_run_mask = (~run_mask) & (~is_strength)
    spec = 0.8
    effective_rtss_target = (tss_num * spec).clip(lower=0.0)
    common_valid = non_run_mask & (duration_num > 0) & (tp_series > 0) & np.isfinite(tss_num.to_numpy(dtype=float, na_value=np.nan))
    zero_target = common_valid & (effective_rtss_target <= 0)
    df.loc[zero_target, "distance_proxy_km"] = 0.0
    df.loc[zero_target, "distance_proxy_method"] = "tss_parity_root_solve"

    denom = (effective_rtss_target * 3600.0) / (duration_num * 100.0)
    solved_pace = tp_series / np.sqrt(denom)
    min_pace = np.maximum(90.0, tp_series / 2.0)
    max_pace = np.minimum(1800.0, tp_series * 6.0)
    parity_valid = (
        common_valid
        & (denom > 0)
        & np.isfinite(solved_pace.to_numpy(dtype=float, na_value=np.nan))
        & (solved_pace >= min_pace)
        & (solved_pace <= max_pace)
    )
    df.loc[parity_valid, "pace_proxy_sec_per_km"] = solved_pace[parity_valid].round()
    df.loc[parity_valid, "distance_proxy_km"] = duration_num[parity_valid] / solved_pace[parity_valid]
    df.loc[parity_valid, "distance_proxy_method"] = "tss_parity_root_solve"
    non_run_if_valid = parity_valid & (solved_pace > 0) & (tp_series > 0)
    df.loc[non_run_if_valid, "if_proxy"] = tp_series[non_run_if_valid] / solved_pace[non_run_if_valid]

    df["mechanical_load"] = pd.NA
    if running_idx.any():
        df.loc[running_idx, "mechanical_load"] = df.loc[running_idx].apply(
            lambda r: mechanical_load(
                distance_m=float(r.get("distance_m") or 0),
                duration_s=float(r.get("duration_s") or 0),
                elevation_gain_m=(
                    float(r.get("elevation_gain_m"))
                    if pd.notna(r.get("elevation_gain_m"))
                    else None
                ),
                avg_cadence=float(r.get("avg_cadence")) if pd.notna(r.get("avg_cadence")) else None,
                avg_stride_length=(
                    float(r.get("avg_stride_length"))
                    if pd.notna(r.get("avg_stride_length"))
                    else None
                ),
                running_power_avg=(
                    float(r.get("running_power_avg"))
                    if pd.notna(r.get("running_power_avg"))
                    else None
                ),
                hr_zone_1_s=(
                    float(r.get("hr_time_in_zone_1"))
                    if pd.notna(r.get("hr_time_in_zone_1"))
                    else None
                ),
                hr_zone_2_s=(
                    float(r.get("hr_time_in_zone_2"))
                    if pd.notna(r.get("hr_time_in_zone_2"))
                    else None
                ),
                hr_zone_3_s=(
                    float(r.get("hr_time_in_zone_3"))
                    if pd.notna(r.get("hr_time_in_zone_3"))
                    else None
                ),
                hr_zone_4_s=(
                    float(r.get("hr_time_in_zone_4"))
                    if pd.notna(r.get("hr_time_in_zone_4"))
                    else None
                ),
                hr_zone_5_s=(
                    float(r.get("hr_time_in_zone_5"))
                    if pd.notna(r.get("hr_time_in_zone_5"))
                    else None
                ),
                rtss=float(r.get("rtss")) if pd.notna(r.get("rtss")) else None,
            ),
            axis=1,
        )

    duration = pd.to_numeric(df.get("duration_s"), errors="coerce").replace(0, pd.NA)
    for zone_col, pct_col in (
        ("hr_time_in_zone_1", "hr_zone_1_pct"),
        ("hr_time_in_zone_2", "hr_zone_2_pct"),
        ("hr_time_in_zone_3", "hr_zone_3_pct"),
        ("hr_time_in_zone_4", "hr_zone_4_pct"),
        ("hr_time_in_zone_5", "hr_zone_5_pct"),
    ):
        if zone_col in df.columns:
            zone_s = pd.to_numeric(df[zone_col], errors="coerce")
            df[pct_col] = (zone_s / duration) * 100.0

    return df


def build_daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "day_utc",
                "distance_km",
                "distance_proxy_km",
                "duration_s_total",
                "mechanical_load_total",
                "rtss_total",
                "tss_total",
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
                "hr_zone_1_pct",
                "hr_zone_2_pct",
                "hr_zone_3_pct",
                "hr_zone_4_pct",
                "hr_zone_5_pct",
            ]
        )

    daily = df.copy()
    daily["day_utc"] = daily["start_time_utc"].dt.date.astype(str)
    sport = daily["sport_type"].fillna("").astype(str).str.lower()
    is_running_like = sport.str.contains("run") | sport.str.contains("treadmill")
    distance_m = pd.to_numeric(daily["distance_m"], errors="coerce").fillna(0.0)
    daily["distance_km"] = (distance_m.where(is_running_like, 0.0)) / 1000.0

    grouped = (
        daily.groupby("day_utc", as_index=False)
        .agg(
            distance_km=("distance_km", "sum"),
            distance_proxy_km=("distance_proxy_km", "sum"),
            duration_s_total=("duration_s", "sum"),
            mechanical_load_total=("mechanical_load", "sum"),
            rtss_total=("rtss", "sum"),
            tss_total=("tss", "sum"),
            training_load_garmin=("training_load_garmin", "sum"),
            calories_active=("calories_active", "sum"),
            calories_total=("calories_total", "sum"),
            intensity_minutes_vigorous=("intensity_minutes_vigorous", "sum"),
            intensity_minutes_moderate=("intensity_minutes_moderate", "sum"),
            hr_time_in_zone_1=("hr_time_in_zone_1", "sum"),
            hr_time_in_zone_2=("hr_time_in_zone_2", "sum"),
            hr_time_in_zone_3=("hr_time_in_zone_3", "sum"),
            hr_time_in_zone_4=("hr_time_in_zone_4", "sum"),
            hr_time_in_zone_5=("hr_time_in_zone_5", "sum"),
        )
        .sort_values("day_utc")
    )
    zone_total = (
        pd.to_numeric(grouped["hr_time_in_zone_1"], errors="coerce").fillna(0.0)
        + pd.to_numeric(grouped["hr_time_in_zone_2"], errors="coerce").fillna(0.0)
        + pd.to_numeric(grouped["hr_time_in_zone_3"], errors="coerce").fillna(0.0)
        + pd.to_numeric(grouped["hr_time_in_zone_4"], errors="coerce").fillna(0.0)
        + pd.to_numeric(grouped["hr_time_in_zone_5"], errors="coerce").fillna(0.0)
    ).replace(0, np.nan)
    grouped["hr_zone_1_pct"] = (pd.to_numeric(grouped["hr_time_in_zone_1"], errors="coerce") / zone_total * 100.0).fillna(0.0)
    grouped["hr_zone_2_pct"] = (pd.to_numeric(grouped["hr_time_in_zone_2"], errors="coerce") / zone_total * 100.0).fillna(0.0)
    grouped["hr_zone_3_pct"] = (pd.to_numeric(grouped["hr_time_in_zone_3"], errors="coerce") / zone_total * 100.0).fillna(0.0)
    grouped["hr_zone_4_pct"] = (pd.to_numeric(grouped["hr_time_in_zone_4"], errors="coerce") / zone_total * 100.0).fillna(0.0)
    grouped["hr_zone_5_pct"] = (pd.to_numeric(grouped["hr_time_in_zone_5"], errors="coerce") / zone_total * 100.0).fillna(0.0)
    return grouped


def sma(series: pd.Series, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("window must be > 0")
    return series.rolling(window=window, min_periods=1).mean()


def ema_alpha_from_days(window: int) -> float:
    if window <= 0:
        raise ValueError("window must be > 0")
    return 2.0 / (window + 1.0)


def ema(series: pd.Series, window: int) -> pd.Series:
    """
    EMA via recurrence:
    ema[t] = alpha * x[t] + (1-alpha) * ema[t-1]
    """
    alpha = ema_alpha_from_days(window)
    if series.empty:
        return series

    values = pd.to_numeric(series, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    out = np.empty_like(values, dtype=float)
    out[0] = values[0]
    one_minus_alpha = 1.0 - alpha
    for i in range(1, len(values)):
        out[i] = (alpha * values[i]) + (one_minus_alpha * out[i - 1])
    return pd.Series(out, index=series.index, dtype=float)


def parse_ma_windows(text: str) -> tuple[list[int], list[tuple[int, int]]]:
    pairs: list[tuple[int, int]] = []
    for a_str, b_str in re.findall(r"\((\d+)\s*,\s*(\d+)\)", text):
        a, b = int(a_str), int(b_str)
        if a > 0 and b > 0:
            pairs.append((a, b))

    cleaned = re.sub(r"\(\s*\d+\s*,\s*\d+\s*\)", "", text)
    singles: list[int] = []
    for part in cleaned.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            val = int(part)
        except ValueError:
            continue
        if val > 0:
            singles.append(val)

    singles = list(dict.fromkeys(singles))
    pairs = list(dict.fromkeys(pairs))
    return singles, pairs


def prepare_metric_series(
    daily_df: pd.DataFrame,
    metric: str,
    start_day: pd.Timestamp,
    end_day: pd.Timestamp,
    fill_method: str = "zero",
    weekly: bool = False,
    weekly_agg: str = "sum",
    full_index: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame(columns=["day", metric])

    series = daily_df.copy()
    if "day" in series.columns:
        series["day"] = pd.to_datetime(series["day"], utc=False, errors="coerce")
    else:
        series["day"] = pd.to_datetime(series["day_utc"], utc=False, errors="coerce")
    series = series[(series["day"] >= start_day) & (series["day"] <= end_day)]

    if series.empty:
        return pd.DataFrame(columns=["day", metric])

    if full_index is None:
        full_index = pd.date_range(start=start_day, end=end_day, freq="D")
    metric_df = series.set_index("day")[[metric]].reindex(full_index)
    metric_df[metric] = pd.to_numeric(metric_df[metric], errors="coerce")

    if fill_method == "ffill":
        metric_df[metric] = metric_df[metric].ffill().fillna(0.0)
    else:
        metric_df[metric] = metric_df[metric].fillna(0.0)

    metric_df = metric_df.reset_index().rename(columns={"index": "day"})

    if weekly:
        weekly_df = metric_df.copy()
        weekly_df["week_start"] = weekly_df["day"].dt.to_period("W-SUN").dt.start_time
        if weekly_agg == "mean":
            weekly_df = (
                weekly_df.groupby("week_start", as_index=False)[metric]
                .mean()
                .rename(columns={"week_start": "day"})
            )
        elif weekly_agg == "last":
            weekly_df = (
                weekly_df.sort_values("day")
                .groupby("week_start", as_index=False)[metric]
                .last()
                .rename(columns={"week_start": "day"})
            )
        else:
            weekly_df = (
                weekly_df.groupby("week_start", as_index=False)[metric]
                .sum()
                .rename(columns={"week_start": "day"})
            )
        return weekly_df

    return metric_df


def weekly_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    weekly = df.copy()
    # Ensure numeric aggregations run on numeric dtypes (avoids slow object-groupby and NA artifacts).
    numeric_cols = [
        "rtss",
        "tss",
        "mechanical_load",
        "distance_proxy_km",
        "training_load_garmin",
        "calories_total",
        "distance_m",
    ]
    for col in numeric_cols:
        if col in weekly.columns:
            weekly[col] = pd.to_numeric(weekly[col], errors="coerce").fillna(0.0)
    weekly["week_start"] = weekly["start_time_utc"].dt.to_period("W-SUN").dt.start_time
    sport = weekly["sport_type"].fillna("").astype(str).str.lower()
    is_running_like = sport.str.contains("run") | sport.str.contains("treadmill")
    distance_m = pd.to_numeric(weekly["distance_m"], errors="coerce").fillna(0.0)
    weekly["distance_km"] = (distance_m.where(is_running_like, 0.0)) / 1000.0

    agg_spec: dict[str, tuple[str, str]] = {
        "total_distance_km": ("distance_km", "sum"),
        "total_rtss": ("rtss", "sum"),
        "total_tss": ("tss", "sum"),
        "total_mechanical_load": ("mechanical_load", "sum"),
        "runs": ("activity_id", "count"),
    }
    if "distance_proxy_km" in weekly.columns:
        agg_spec["total_distance_proxy_km"] = ("distance_proxy_km", "sum")
    if "training_load_garmin" in weekly.columns:
        agg_spec["total_garmin_training_load"] = ("training_load_garmin", "sum")
    if "calories_total" in weekly.columns:
        agg_spec["total_calories"] = ("calories_total", "sum")

    grouped = weekly.groupby("week_start", as_index=False).agg(**agg_spec).sort_values("week_start")
    return grouped


def display_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    table = df.copy().sort_values("start_time_utc", ascending=False)
    table["date"] = table["start_time_utc"].dt.date
    table["distance_km"] = table["distance_m"] / 1000.0
    table["duration_min"] = table["duration_s"] / 60.0

    def _pace_str(pace_s_per_km: float | None, sport_type: str | None) -> str:
        sport = str(sport_type or "").lower()
        if "run" not in sport and "treadmill" not in sport:
            return "-"
        if pace_s_per_km is None or pd.isna(pace_s_per_km):
            return "-"
        try:
            pace_value = float(pace_s_per_km)
        except (TypeError, ValueError):
            return "-"
        if not math.isfinite(pace_value):
            return "-"
        if pace_value <= 0:
            return "-"
        total_seconds = int(round(pace_value))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}/km"

    table["avg_pace_display"] = table.apply(
        lambda r: _pace_str(r.get("avg_pace_s_per_km"), r.get("sport_type")),
        axis=1,
    )

    def _pace_proxy_str(pace_s_per_km: float | None) -> str:
        if pace_s_per_km is None or pd.isna(pace_s_per_km):
            return "-"
        try:
            pace_value = float(pace_s_per_km)
        except (TypeError, ValueError):
            return "-"
        if not math.isfinite(pace_value) or pace_value <= 0:
            return "-"
        total_seconds = int(round(pace_value))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}min/km"

    table["pace_proxy_display"] = table["pace_proxy_sec_per_km"].apply(_pace_proxy_str)

    cols = [
        "activity_id",
        "date",
        "sport_type",
        "distance_km",
        "duration_min",
        "avg_hr",
        "if_proxy",
        "fitness",
        "fatigue",
        "rtss",
        "tss",
        "avg_pace_display",
        "mechanical_load",
    ]
    cols = [c for c in cols if c in table.columns]

    optional = [
        "if_proxy",
        "distance_proxy_km",
        "pace_proxy_display",
        "distance_proxy_method",
        "avg_cadence",
        "running_power_avg",
        "training_load_garmin",
        "calories_active",
        "calories_total",
        "intensity_minutes_vigorous",
        "intensity_minutes_moderate",
    ]
    cols.extend([c for c in optional if c in table.columns])

    return table[cols]

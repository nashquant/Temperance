from __future__ import annotations

import math
import re
from datetime import datetime

import pandas as pd
import numpy as np

from models import aerobic_load, edwards_trimp_from_zones, mechanical_load
from tss import (
    PiecewiseThresholdPaceProvider,
)


def compute_metrics(
    runs_df: pd.DataFrame,
    resting_hr: float | None,
    max_hr: float | None,
    sex: str = "male",
    threshold_pace_sec_per_km: float = 300.0,
    lthr_bpm: float = 178.0,
    threshold_pace_curve_points: list[tuple[datetime, float]] | None = None,
) -> pd.DataFrame:
    if runs_df.empty:
        return runs_df

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

    df["aerobic_load"] = df.apply(
        lambda r: aerobic_load(
            duration_s=float(r.get("duration_s") or 0),
            avg_hr=float(r.get("avg_hr")) if pd.notna(r.get("avg_hr")) else None,
            resting_hr=resting_hr,
            max_hr=max_hr,
            sex=sex,
        ),
        axis=1,
    )
    # Persisted per-activity TRIMP proxy is this aerobic load output.
    df["trimp"] = df["aerobic_load"]

    df["edwards_trimp"] = df.apply(
        lambda r: edwards_trimp_from_zones(
            hr_zone_1_s=float(r.get("hr_time_in_zone_1")) if pd.notna(r.get("hr_time_in_zone_1")) else 0.0,
            hr_zone_2_s=float(r.get("hr_time_in_zone_2")) if pd.notna(r.get("hr_time_in_zone_2")) else 0.0,
            hr_zone_3_s=float(r.get("hr_time_in_zone_3")) if pd.notna(r.get("hr_time_in_zone_3")) else 0.0,
            hr_zone_4_s=float(r.get("hr_time_in_zone_4")) if pd.notna(r.get("hr_time_in_zone_4")) else 0.0,
            hr_zone_5_s=float(r.get("hr_time_in_zone_5")) if pd.notna(r.get("hr_time_in_zone_5")) else 0.0,
        ),
        axis=1,
    )

    pace_provider = None
    if threshold_pace_curve_points:
        pace_provider = PiecewiseThresholdPaceProvider(
            default_threshold_pace_sec_per_km=threshold_pace_sec_per_km,
            points=tuple(threshold_pace_curve_points),
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

    # Vectorized hrTSS.
    if lthr_bpm > 0:
        tss_mask = (duration_s > 0) & (avg_hr > 0) & (avg_hr <= 260)
        df.loc[tss_mask, "tss"] = (
            duration_s[tss_mask] * ((avg_hr[tss_mask] / float(lthr_bpm)) ** 2) / 3600.0 * 100.0
        )

    # rTSS for running/treadmill only.
    rtss_mask = running_idx & (duration_s > 0) & (avg_pace > 0)
    if threshold_pace_sec_per_km > 0 and not threshold_pace_curve_points:
        df.loc[rtss_mask, "rtss"] = (
            duration_s[rtss_mask]
            * ((float(threshold_pace_sec_per_km) / avg_pace[rtss_mask]) ** 2)
            / 3600.0
            * 100.0
        )
    elif threshold_pace_sec_per_km > 0 and pace_provider is not None:
        for idx in df.index[rtss_mask]:
            tp = float(pace_provider.get_threshold_pace_sec_per_km(df.at[idx, "start_time_utc"].to_pydatetime()))
            if tp <= 0:
                continue
            pace_v = float(avg_pace.loc[idx])
            dur_v = float(duration_s.loc[idx])
            df.at[idx, "rtss"] = (dur_v * ((tp / pace_v) ** 2) / 3600.0) * 100.0

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
                "trimp_total",
                "mechanical_load_total",
                "edwards_trimp_total",
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
    daily["distance_km"] = daily["distance_m"].fillna(0.0) / 1000.0

    grouped = (
        daily.groupby("day_utc", as_index=False)
        .agg(
            distance_km=("distance_km", "sum"),
            trimp_total=("trimp", "sum"),
            mechanical_load_total=("mechanical_load", "sum"),
            edwards_trimp_total=("edwards_trimp", "sum"),
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
            hr_zone_1_pct=("hr_zone_1_pct", "mean"),
            hr_zone_2_pct=("hr_zone_2_pct", "mean"),
            hr_zone_3_pct=("hr_zone_3_pct", "mean"),
            hr_zone_4_pct=("hr_zone_4_pct", "mean"),
            hr_zone_5_pct=("hr_zone_5_pct", "mean"),
        )
        .sort_values("day_utc")
    )
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
    weekly["week_start"] = weekly["start_time_utc"].dt.to_period("W-SUN").dt.start_time
    weekly["distance_km"] = weekly["distance_m"] / 1000.0

    agg_spec: dict[str, tuple[str, str]] = {
        "total_distance_km": ("distance_km", "sum"),
        "total_trimp": ("trimp", "sum"),
        "total_edwards_trimp": ("edwards_trimp", "sum"),
        "total_rtss": ("rtss", "sum"),
        "total_tss": ("tss", "sum"),
        "total_mechanical_load": ("mechanical_load", "sum"),
        "runs": ("activity_id", "count"),
    }
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

    cols = [
        "activity_id",
        "date",
        "distance_km",
        "duration_min",
        "avg_hr",
        "fitness",
        "fatigue",
        "rtss",
        "tss",
        "avg_pace_display",
        "trimp",
        "edwards_trimp",
        "mechanical_load",
    ]
    cols = [c for c in cols if c in table.columns]

    optional = [
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

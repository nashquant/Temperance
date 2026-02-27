from __future__ import annotations

import pandas as pd

from models import aerobic_load, mechanical_load


def compute_metrics(
    runs_df: pd.DataFrame,
    resting_hr: float | None,
    max_hr: float | None,
    sex: str = "male",
) -> pd.DataFrame:
    if runs_df.empty:
        return runs_df

    df = runs_df.copy()
    df["start_time_utc"] = pd.to_datetime(df["start_time_utc"], utc=True, errors="coerce")

    # Fill pace where missing from duration and distance.
    missing_pace = df["avg_pace_s_per_km"].isna()
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

    df["mechanical_load"] = df.apply(
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
        ),
        axis=1,
    )

    return df


def build_daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "day_utc",
                "trimp_total",
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
        )

    daily = df.copy()
    daily["day_utc"] = daily["start_time_utc"].dt.date.astype(str)

    grouped = (
        daily.groupby("day_utc", as_index=False)
        .agg(
            trimp_total=("trimp", "sum"),
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
    alpha = ema_alpha_from_days(window)
    return series.ewm(alpha=alpha, adjust=False).mean()


def prepare_metric_series(
    daily_df: pd.DataFrame,
    metric: str,
    start_day: pd.Timestamp,
    end_day: pd.Timestamp,
    fill_method: str = "zero",
    weekly: bool = False,
) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame(columns=["day", metric])

    series = daily_df.copy()
    series["day"] = pd.to_datetime(series["day_utc"], utc=False, errors="coerce")
    series = series[(series["day"] >= start_day) & (series["day"] <= end_day)]

    if series.empty:
        return pd.DataFrame(columns=["day", metric])

    full_index = pd.date_range(start=start_day, end=end_day, freq="D")
    metric_df = series.set_index("day")[[metric]].reindex(full_index)

    if fill_method == "ffill":
        metric_df[metric] = metric_df[metric].ffill().fillna(0.0)
    else:
        metric_df[metric] = metric_df[metric].fillna(0.0)

    metric_df = metric_df.reset_index().rename(columns={"index": "day"})

    if weekly:
        weekly_df = metric_df.copy()
        weekly_df["week_start"] = weekly_df["day"].dt.to_period("W-SUN").dt.start_time
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
        "total_mechanical_load": ("mechanical_load", "sum"),
        "runs": ("activity_id", "count"),
    }
    if "training_load_garmin" in weekly.columns:
        agg_spec["total_garmin_training_load"] = ("training_load_garmin", "sum")

    grouped = weekly.groupby("week_start", as_index=False).agg(**agg_spec).sort_values("week_start")
    return grouped


def display_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    table = df.copy().sort_values("start_time_utc", ascending=False)
    table["date"] = table["start_time_utc"].dt.date
    table["distance_km"] = table["distance_m"] / 1000.0
    table["duration_min"] = table["duration_s"] / 60.0

    def _pace_str(pace_s_per_km: float | None) -> str:
        if pace_s_per_km is None or pd.isna(pace_s_per_km):
            return "-"
        try:
            pace_value = float(pace_s_per_km)
        except (TypeError, ValueError):
            return "-"
        if pace_value <= 0:
            return "-"
        total_seconds = int(round(pace_value))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}/km"

    table["avg_pace_display"] = table["avg_pace_s_per_km"].apply(_pace_str)

    cols = [
        "activity_id",
        "date",
        "distance_km",
        "duration_min",
        "avg_hr",
        "avg_pace_display",
        "trimp",
        "mechanical_load",
    ]

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

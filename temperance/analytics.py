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

    df["mechanical_load"] = df.apply(
        lambda r: mechanical_load(
            distance_m=float(r.get("distance_m") or 0),
            duration_s=float(r.get("duration_s") or 0),
            elevation_gain_m=(
                float(r.get("elevation_gain_m"))
                if pd.notna(r.get("elevation_gain_m"))
                else None
            ),
        ),
        axis=1,
    )

    return df


def weekly_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    weekly = df.copy()
    weekly["week_start"] = weekly["start_time_utc"].dt.to_period("W-SUN").dt.start_time
    weekly["distance_km"] = weekly["distance_m"] / 1000.0

    grouped = (
        weekly.groupby("week_start", as_index=False)
        .agg(
            total_distance_km=("distance_km", "sum"),
            total_aerobic_load=("aerobic_load", "sum"),
            total_mechanical_load=("mechanical_load", "sum"),
            runs=("activity_id", "count"),
        )
        .sort_values("week_start")
    )

    return grouped


def display_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    table = df.copy().sort_values("start_time_utc", ascending=False)
    table["date"] = table["start_time_utc"].dt.date
    table["distance_km"] = table["distance_m"] / 1000.0
    table["duration_min"] = table["duration_s"] / 60.0

    return table[
        [
            "activity_id",
            "date",
            "distance_km",
            "duration_min",
            "avg_hr",
            "avg_pace_s_per_km",
            "aerobic_load",
            "mechanical_load",
        ]
    ]

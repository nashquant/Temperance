from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.app.main import _build_athlete_progression_payload


def _metrics_frame() -> pd.DataFrame:
    start = pd.Timestamp("2026-02-01", tz="UTC")
    rows: list[dict[str, object]] = []
    workouts = [
        ("running", 12000.0, 3600.0, 78.0, 82.0, 158.0),
        ("cycling", 0.0, 5400.0, 95.0, 0.0, 142.0),
        ("running", 18000.0, 6000.0, 110.0, 115.0, 160.0),
        ("running", 10000.0, 3000.0, 88.0, 92.0, 154.0),
    ]
    for index in range(28):
        sport, distance_m, duration_s, tss, rtss, avg_hr = workouts[index % len(workouts)]
        start_time = start + pd.Timedelta(days=index, hours=12)
        rows.append(
            {
                "activity_id": index + 1,
                "start_time_utc": start_time.isoformat(),
                "start_local": start_time.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S"),
                "sport_type": sport,
                "distance_m": distance_m,
                "distance_proxy_km": max(distance_m / 1000.0, 8.0),
                "duration_s": duration_s,
                "tss": tss,
                "rtss": rtss,
                "if_proxy": 0.93 if sport == "running" else 0.72,
                "avg_hr": avg_hr,
                "training_load_garmin": tss,
                "calories_total": 700.0,
                "hr_time_in_zone_1": 600.0,
                "hr_time_in_zone_2": 1800.0,
                "hr_time_in_zone_3": 900.0,
                "hr_time_in_zone_4": 300.0,
                "hr_time_in_zone_5": 0.0,
            }
        )
    return pd.DataFrame(rows)


def _wellness_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "day_utc": pd.date_range("2026-02-01", periods=28, freq="D"),
            "training_readiness": [72, 70, 55, 71, 68, 50, 72] * 4,
            "hrv_status": [0.0] * 28,
            "resting_hr": [46, 46, 49, 46, 47, 50, 46] * 4,
            "body_battery_end": [70, 68, 52, 69, 67, 49, 71] * 4,
        }
    )


def test_payload_exposes_new_metric_series() -> None:
    with (
        patch("backend.app.main._metrics_for_filters", return_value=_metrics_frame()),
        patch("backend.app.main.get_wellness_df", return_value=_wellness_frame()),
        patch("backend.app.main.get_sleep_df", return_value=pd.DataFrame()),
        patch("backend.app.main.get_setting", return_value=None),
        patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=420.0),
        patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=70.0),
        patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
    ):
        mock_datetime.now.return_value = datetime(2026, 3, 1, tzinfo=timezone.utc)
        payload = _build_athlete_progression_payload(
            db_path=Path("/tmp/progression-metrics.sqlite"),
            days=56,
            activity_filter="all",
            aggregation="daily",
            owner="tester",
        )

    point = payload["points"][-1]
    assert point["performance_trend"] >= 0
    assert point["performance_confidence"] >= 0
    assert point["readiness"] >= 0
    assert point["tissue_load_risk"] >= 0
    assert point["durability"] >= 0


def test_cross_training_load_does_not_dominate_tissue_load_risk() -> None:
    metrics = _metrics_frame()
    metrics.loc[metrics["sport_type"] == "cycling", "tss"] = 140.0
    metrics.loc[metrics["sport_type"] == "cycling", "rtss"] = 0.0

    with (
        patch("backend.app.main._metrics_for_filters", return_value=metrics),
        patch("backend.app.main.get_wellness_df", return_value=_wellness_frame()),
        patch("backend.app.main.get_sleep_df", return_value=pd.DataFrame()),
        patch("backend.app.main.get_setting", return_value=None),
        patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=420.0),
        patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=70.0),
        patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
    ):
        mock_datetime.now.return_value = datetime(2026, 3, 1, tzinfo=timezone.utc)
        payload = _build_athlete_progression_payload(
            db_path=Path("/tmp/progression-metrics.sqlite"),
            days=56,
            activity_filter="all",
            aggregation="daily",
            owner="tester",
        )

    point = payload["points"][-1]
    assert point["tissue_load_risk"] < 75

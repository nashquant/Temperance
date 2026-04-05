import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.app.main import _blended_weekly_targets_for_day, _build_planned_activities_payload, _build_week_outlook_payload


def _actual_metrics_frame(daily_tss_values: list[float], start_day: str = "2026-01-05") -> pd.DataFrame:
    start = pd.Timestamp(start_day, tz="UTC")
    rows: list[dict[str, object]] = []
    for index, tss in enumerate(daily_tss_values, start=1):
        start_time = start + pd.Timedelta(days=index - 1, hours=12)
        rows.append(
            {
                "activity_id": index,
                "start_time_utc": start_time.isoformat(),
                "sport_type": "running",
                "distance_m": 10_000.0,
                "distance_proxy_km": 10.0,
                "duration_s": 3_600.0,
                "tss": float(tss),
                "rtss": float(tss),
            }
        )
    return pd.DataFrame(rows)


def _planned_rows_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "day_utc": "2026-01-12",
                "line_no": 1,
                "workout_text": "easy run",
                "parsed_json": [],
                "manual_done": False,
                "tss": 50.0,
                "rtss": 45.0,
                "distance_proxy_km": 10.0,
                "duration_s": 3600.0,
                "if_proxy": 0.75,
            }
        ]
    )


class WeekPlannerBaselineTest(unittest.TestCase):
    def test_helper_reduces_targets_when_recent_load_is_low(self):
        metrics_df = _actual_metrics_frame([10.0] * 42)
        with (
            patch("backend.app.main.get_setting", return_value=None),
            patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=420.0),
            patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=70.0),
        ):
            targets = _blended_weekly_targets_for_day(
                db_path=Path("/tmp/week-planner-baseline-test.sqlite"),
                target_day="2026-02-09",
                actual_metrics_df=metrics_df,
            )

        self.assertLess(targets["tss"], 462.0)
        self.assertLess(targets["distance_eqv_km"], 70.0)

    def test_week_outlook_goal_uses_blended_baseline(self):
        metrics_df = _actual_metrics_frame([10.0] * 42)
        with (
            patch("backend.app.main._metrics_for_filters", return_value=metrics_df),
            patch("backend.app.main._blended_weekly_targets_for_day", return_value={"tss": 301.0, "rtss": 246.0, "distance_eqv_km": 48.0}),
        ):
            payload = _build_week_outlook_payload(
                db_path=Path("/tmp/week-planner-baseline-test.sqlite"),
                days=84,
                start_day=None,
                end_day=None,
                sport=None,
                metric="tss",
                compare="planned",
                week_start="2026-02-09",
            )

        self.assertEqual(payload["goal"], 301.0)

    def test_planned_activities_week_goals_use_selected_week_blended_baseline(self):
        planned_df = _planned_rows_frame()
        actual_metrics_df = _actual_metrics_frame([10.0] * 42)
        with (
            patch("backend.app.main.get_setting", return_value=None),
            patch("backend.app.main.get_planned_activities_df", return_value=planned_df),
            patch("backend.app.main._compute_planned_rows_metrics_df", return_value=planned_df),
            patch("backend.app.main._metrics_for_filters", return_value=actual_metrics_df),
            patch("backend.app.main._blended_weekly_targets_for_day", side_effect=[
                {"tss": 301.0, "rtss": 246.0, "distance_eqv_km": 48.0},
                {"tss": 287.0, "rtss": 235.0, "distance_eqv_km": 45.0},
            ]),
            patch("backend.app.main.datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2026, 1, 14, tzinfo=timezone.utc)
            payload = _build_planned_activities_payload(
                db_path=Path("/tmp/week-planner-baseline-test.sqlite"),
                owner="tester",
                weeks=4,
            )

        self.assertEqual(payload["goals"]["tss"], 301.0)
        self.assertEqual(len(payload["weeks"]), 1)
        self.assertEqual(payload["weeks"][0]["goal_tss"], 287.0)
        self.assertEqual(payload["weeks"][0]["goal_distance_eqv_km"], 45.0)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.app.main import _blend_baseline_tss, _build_athlete_progression_payload


def _metrics_frame(daily_tss_values: list[float], start_day: str = "2026-01-05") -> pd.DataFrame:
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
                "training_load_garmin": float(tss),
                "calories_total": 600.0,
            }
        )
    return pd.DataFrame(rows)


def _empty_vdot_frame(_: pd.DataFrame, __: Path) -> pd.DataFrame:
    return pd.DataFrame(columns=["day", "vdot", "vdot_max"])


class AthleteProgressionBaselineTest(unittest.TestCase):
    def _build_payload(
        self,
        daily_tss_values: list[float],
        *,
        weekly_tss_target: float = 420.0,
        weekly_distance_target: float = 70.0,
    ) -> dict[str, object]:
        metrics_df = _metrics_frame(daily_tss_values)
        with (
            patch("backend.app.main.get_setting", return_value=None),
            patch("backend.app.main._metrics_for_filters", return_value=metrics_df),
            patch("backend.app.main._build_daily_vdot_series", side_effect=_empty_vdot_frame),
            patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=float(weekly_tss_target)),
            patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=float(weekly_distance_target)),
        ):
            return _build_athlete_progression_payload(
                db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
                days=84,
                activity_filter="all",
                aggregation="weekly",
                owner="tester",
            )

    def test_low_recent_load_pulls_weekly_baselines_below_lt_targets(self):
        payload = self._build_payload([10.0] * 42)
        last_point = payload["points"][-1]

        self.assertLess(last_point["baseline_tss"], last_point["lt_target_tss"])
        self.assertLess(last_point["baseline_distance_km"], last_point["lt_target_distance_km"])
        self.assertAlmostEqual(
            last_point["baseline_distance_km"] / last_point["lt_target_distance_km"],
            last_point["baseline_tss"] / last_point["lt_target_tss"],
            places=3,
        )

    def test_recent_load_near_capacity_keeps_baselines_close_to_lt_targets(self):
        payload = self._build_payload([60.0] * 42)
        last_point = payload["points"][-1]

        self.assertAlmostEqual(last_point["baseline_tss"], last_point["lt_target_tss"], delta=15.0)
        self.assertAlmostEqual(
            last_point["baseline_distance_km"],
            last_point["lt_target_distance_km"],
            delta=3.0,
        )

    def test_high_recent_load_pushes_weekly_baselines_above_lt_targets(self):
        payload = self._build_payload([90.0] * 42)
        last_point = payload["points"][-1]

        self.assertGreater(last_point["baseline_tss"], last_point["lt_target_tss"])
        self.assertGreater(last_point["baseline_distance_km"], last_point["lt_target_distance_km"])
        self.assertAlmostEqual(
            last_point["baseline_distance_km"] / last_point["lt_target_distance_km"],
            last_point["baseline_tss"] / last_point["lt_target_tss"],
            places=3,
        )

    def test_weekly_baselines_change_with_trailing_twenty_one_day_history(self):
        payload = self._build_payload(([10.0] * 21) + ([90.0] * 21))
        points = payload["points"]

        low_load_payload = self._build_payload([10.0] * 42)
        high_load_payload = self._build_payload([90.0] * 42)

        self.assertGreater(points[-1]["baseline_tss"], low_load_payload["points"][-1]["baseline_tss"])
        self.assertLess(points[-1]["baseline_tss"], high_load_payload["points"][-1]["baseline_tss"])
        self.assertGreater(points[-1]["baseline_distance_km"], low_load_payload["points"][-1]["baseline_distance_km"])
        self.assertLess(points[-1]["baseline_distance_km"], high_load_payload["points"][-1]["baseline_distance_km"])

    def test_zero_lt_tss_target_keeps_distance_baseline_stable(self):
        payload = self._build_payload([40.0] * 42, weekly_tss_target=0.0, weekly_distance_target=70.0)
        last_point = payload["points"][-1]

        self.assertEqual(last_point["lt_target_tss"], 0.0)
        self.assertGreater(last_point["baseline_tss"], 0.0)
        self.assertAlmostEqual(last_point["baseline_distance_km"], last_point["lt_target_distance_km"], places=3)

    def test_smoothing_dampens_sharp_weekly_baseline_jumps(self):
        payload = self._build_payload(([10.0] * 21) + ([90.0] * 21))
        points = payload["points"]

        smoothed_jumps = [
            abs(points[index]["baseline_tss"] - points[index - 1]["baseline_tss"])
            for index in range(1, len(points))
        ]

        self.assertTrue(smoothed_jumps)
        self.assertLess(max(smoothed_jumps), 50.0)

    def test_points_include_baseline_history_components(self):
        payload = self._build_payload([55.0] * 42)
        last_point = payload["points"][-1]

        self.assertIn("baseline_tss", last_point)
        self.assertIn("baseline_distance_km", last_point)
        self.assertIn("lt_target_tss", last_point)
        self.assertIn("capacity_baseline_tss", last_point)
        self.assertIn("recent_load_anchor_tss", last_point)
        self.assertIn("blended_baseline_tss_before_smoothing", last_point)
        self.assertIn("smoothed_baseline_tss", last_point)
        self.assertAlmostEqual(last_point["smoothed_baseline_tss"], last_point["baseline_tss"], places=3)

    def test_points_include_raw_and_stateful_risk_signals(self):
        payload = self._build_payload(([90.0] * 10) + ([20.0] * 20) + ([5.0] * 12))
        last_point = payload["points"][-1]

        self.assertIn("raw_overreach_signal", last_point)
        self.assertIn("raw_injury_signal", last_point)
        self.assertIn("overreach_state", last_point)
        self.assertIn("injury_risk_state", last_point)
        self.assertGreaterEqual(last_point["overreach"], last_point["raw_overreach_signal"])
        self.assertGreaterEqual(last_point["injury_risk"], last_point["raw_injury_signal"])

    def test_sparse_history_keeps_baseline_history_components_populated(self):
        payload = self._build_payload([30.0, 40.0, 35.0])
        points = payload["points"]

        self.assertTrue(points)
        last_point = points[-1]
        self.assertGreaterEqual(last_point["baseline_tss"], 0.0)
        self.assertGreaterEqual(last_point["capacity_baseline_tss"], 0.0)
        self.assertGreaterEqual(last_point["recent_load_anchor_tss"], 0.0)
        self.assertGreaterEqual(last_point["blended_baseline_tss_before_smoothing"], 0.0)
        self.assertGreaterEqual(last_point["smoothed_baseline_tss"], 0.0)

    def test_weekly_view_extends_range_to_full_weeks(self):
        metrics_df = _metrics_frame([50.0] * 40, start_day="2026-01-01")
        with (
            patch("backend.app.main.get_setting", return_value=None),
            patch("backend.app.main._metrics_for_filters", return_value=metrics_df),
            patch("backend.app.main._build_daily_vdot_series", side_effect=_empty_vdot_frame),
            patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=420.0),
            patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=70.0),
            patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2026, 2, 10, tzinfo=timezone.utc)
            payload = _build_athlete_progression_payload(
                db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
                days=30,
                activity_filter="all",
                aggregation="weekly",
                owner="tester",
            )

        self.assertTrue(payload["points"])
        self.assertEqual(payload["points"][0]["period_start"], "2026-01-05")


if __name__ == "__main__":
    unittest.main()

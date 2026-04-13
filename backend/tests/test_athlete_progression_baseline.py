import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.app.main import (
    _blend_baseline_tss,
    _build_activity_dashboard_payload,
    _build_athlete_progression_payload,
    _day_lookup_with_daily_model,
)


def _metrics_frame(daily_tss_values: list[float], start_day: str = "2026-01-05") -> pd.DataFrame:
    start = pd.Timestamp(start_day, tz="UTC")
    rows: list[dict[str, object]] = []
    for index, tss in enumerate(daily_tss_values, start=1):
        start_time = start + pd.Timedelta(days=index - 1, hours=12)
        rows.append(
            {
                "activity_id": index,
                "start_time_utc": start_time.isoformat(),
                "start_local": start_time.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S"),
                "sport_type": "running",
                "distance_m": 10_000.0,
                "distance_km_running": 10.0,
                "distance_proxy_km": 10.0,
                "duration_s": 3_600.0,
                "tss": float(tss),
                "rtss": float(tss),
                "training_load_garmin": float(tss),
                "calories_total": 600.0,
                "hr_time_in_zone_1": 0.0,
                "hr_time_in_zone_2": 0.0,
                "hr_time_in_zone_3": 0.0,
                "hr_time_in_zone_4": 0.0,
                "hr_time_in_zone_5": 0.0,
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
        days: int = 84,
        aggregation: str = "weekly",
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
            patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2026, 2, 15, tzinfo=timezone.utc)
            return _build_athlete_progression_payload(
                db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
                days=days,
                activity_filter="all",
                aggregation=aggregation,
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
        payload = self._build_payload([60.0] * 140, days=140)
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

    def test_daily_baseline_no_longer_adds_extra_ema_lag(self):
        payload = self._build_payload(([10.0] * 21) + ([90.0] * 21))
        points = payload["points"]

        self.assertTrue(points)
        for point in points:
            self.assertAlmostEqual(
                float(point["baseline_tss"]),
                float(point["blended_baseline_tss_before_smoothing"]),
                places=3,
            )
            self.assertAlmostEqual(
                float(point["smoothed_baseline_tss"]),
                float(point["blended_baseline_tss_before_smoothing"]),
                places=3,
            )

    def test_resumed_training_recovers_daily_baseline_without_extra_ema(self):
        payload = self._build_payload(([10.0] * 100) + ([90.0] * 14), days=140, aggregation="daily")
        points = payload["points"]

        self.assertGreaterEqual(len(points), 56)
        raw_series = pd.Series(
            [float(point["blended_baseline_tss_before_smoothing"]) for point in points],
            dtype=float,
        )
        ema_counterfactual = raw_series.ewm(span=21, adjust=False).mean()

        for point in points:
            self.assertAlmostEqual(
                float(point["baseline_tss"]),
                float(point["blended_baseline_tss_before_smoothing"]),
                places=3,
            )

        recovery_advantage = (raw_series - ema_counterfactual).iloc[-14:]
        self.assertGreater(float(recovery_advantage.max()), 0.2)

    def test_weekly_rollup_uses_latest_modeled_point_in_week(self):
        daily_payload = self._build_payload(([30.0] * 7) + ([80.0] * 7) + ([25.0] * 7) + ([95.0] * 7), aggregation="daily")
        weekly_payload = self._build_payload(([30.0] * 7) + ([80.0] * 7) + ([25.0] * 7) + ([95.0] * 7), aggregation="weekly")

        expected_by_week: dict[str, dict[str, float]] = {}
        for point in daily_payload["points"]:
            day = pd.Timestamp(point["period_start"])
            week_start = (day - pd.Timedelta(days=int(day.weekday()))).date().isoformat()
            expected_by_week[week_start] = {
                "baseline_tss": float(point["baseline_tss"]) * 7.0,
                "lt_target_tss": float(point["lt_target_tss"]) * 7.0,
                "capacity_baseline_tss": float(point["capacity_baseline_tss"]) * 7.0,
                "smoothed_baseline_tss": float(point["smoothed_baseline_tss"]) * 7.0,
            }

        for row in weekly_payload["points"]:
            week_expected = expected_by_week[str(row["period_start"])]
            self.assertAlmostEqual(float(row["baseline_tss"]), week_expected["baseline_tss"], places=2)
            self.assertAlmostEqual(float(row["lt_target_tss"]), week_expected["lt_target_tss"], places=2)
            self.assertAlmostEqual(float(row["capacity_baseline_tss"]), week_expected["capacity_baseline_tss"], places=2)
            self.assertAlmostEqual(float(row["smoothed_baseline_tss"]), week_expected["smoothed_baseline_tss"], places=2)

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

    def test_repeated_moderate_overload_week_scores_higher_than_single_week(self):
        single_week_payload = self._build_payload(([45.0] * 77) + ([75.0] * 7), days=140, aggregation="daily")
        repeated_week_payload = self._build_payload(([45.0] * 70) + ([75.0] * 14), days=140, aggregation="daily")

        self.assertTrue(single_week_payload["points"])
        self.assertTrue(repeated_week_payload["points"])
        single_overreach_peak = max(float(point["overreach"]) for point in single_week_payload["points"][-14:])
        repeated_overreach_peak = max(float(point["overreach"]) for point in repeated_week_payload["points"][-14:])
        single_injury_peak = max(float(point["injury_risk"]) for point in single_week_payload["points"][-14:])
        repeated_injury_peak = max(float(point["injury_risk"]) for point in repeated_week_payload["points"][-14:])

        self.assertGreater(repeated_overreach_peak, single_overreach_peak)
        self.assertGreater(
            repeated_injury_peak,
            single_injury_peak,
        )

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

    def test_short_weekly_request_keeps_latest_baseline_from_long_history(self):
        daily_tss_values = ([55.0] * 60) + ([95.0] * 40)
        short_payload = self._build_payload(daily_tss_values, days=30, aggregation="weekly")
        long_payload = self._build_payload(daily_tss_values, days=120, aggregation="weekly")

        self.assertTrue(short_payload["points"])
        self.assertTrue(long_payload["points"])
        self.assertEqual(short_payload["points"][-1]["period_start"], long_payload["points"][-1]["period_start"])
        self.assertAlmostEqual(short_payload["points"][-1]["baseline_tss"], long_payload["points"][-1]["baseline_tss"], places=3)
        self.assertAlmostEqual(
            short_payload["points"][-1]["blended_baseline_tss_before_smoothing"],
            long_payload["points"][-1]["blended_baseline_tss_before_smoothing"],
            places=3,
        )

    def test_short_daily_request_keeps_latest_baseline_from_long_history(self):
        daily_tss_values = ([40.0] * 80) + ([90.0] * 20)
        short_payload = self._build_payload(daily_tss_values, days=30, aggregation="daily")
        long_payload = self._build_payload(daily_tss_values, days=120, aggregation="daily")

        self.assertTrue(short_payload["points"])
        self.assertTrue(long_payload["points"])
        self.assertEqual(short_payload["points"][-1]["period_start"], long_payload["points"][-1]["period_start"])
        self.assertAlmostEqual(short_payload["points"][-1]["baseline_tss"], long_payload["points"][-1]["baseline_tss"], places=3)
        self.assertAlmostEqual(short_payload["points"][-1]["smoothed_baseline_tss"], long_payload["points"][-1]["smoothed_baseline_tss"], places=3)

    def test_long_weekly_request_keeps_first_visible_baseline_from_hidden_warmup_history(self):
        metrics_df = _metrics_frame(([55.0] * 500) + ([95.0] * 300), start_day="2024-01-01")
        metrics_df["day"] = pd.to_datetime(metrics_df["start_time_utc"], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
        today = pd.Timestamp("2026-02-15")

        def _metrics_for_days(*, db_path: Path, days: int, start_day=None, end_day=None, sport=None) -> pd.DataFrame:
            cutoff = today - pd.Timedelta(days=int(days) - 1)
            return metrics_df[metrics_df["day"] >= cutoff].copy()

        with (
            patch("backend.app.main.get_setting", return_value=None),
            patch("backend.app.main._metrics_for_filters", side_effect=_metrics_for_days),
            patch("backend.app.main._build_daily_vdot_series", side_effect=_empty_vdot_frame),
            patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=420.0),
            patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=70.0),
            patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2026, 2, 15, tzinfo=timezone.utc)
            one_year_payload = _build_athlete_progression_payload(
                db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
                days=365,
                activity_filter="all",
                aggregation="weekly",
                owner="tester",
            )
            two_year_payload = _build_athlete_progression_payload(
                db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
                days=730,
                activity_filter="all",
                aggregation="weekly",
                owner="tester",
            )

        self.assertTrue(one_year_payload["points"])
        self.assertTrue(two_year_payload["points"])
        first_visible_week = one_year_payload["points"][0]["period_start"]
        matching_long_week = next(point for point in two_year_payload["points"] if point["period_start"] == first_visible_week)

        self.assertAlmostEqual(one_year_payload["points"][0]["baseline_tss"], matching_long_week["baseline_tss"], places=3)
        self.assertAlmostEqual(
            one_year_payload["points"][0]["recent_load_anchor_tss"],
            matching_long_week["recent_load_anchor_tss"],
            places=3,
        )

    def test_dashboard_week_summary_uses_canonical_weekly_baseline_tss(self):
        metrics_df = _metrics_frame(([45.0] * 42) + ([75.0] * 14))
        metrics_df["day"] = pd.to_datetime(metrics_df["start_time_utc"], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
        actual_metrics_df = metrics_df.copy()
        with (
            patch("backend.app.main._dashboard_metrics_frames", return_value=(metrics_df, actual_metrics_df)),
            patch("backend.app.main._build_daily_vdot_series", side_effect=_empty_vdot_frame),
            patch("backend.app.main.get_planned_activities_df", return_value=pd.DataFrame()),
            patch("backend.app.main.get_wellness_df", return_value=pd.DataFrame()),
            patch("backend.app.main.get_setting", return_value=None),
            patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=420.0),
            patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=70.0),
            patch("backend.app.main._load_curve_points", return_value=[]),
            patch("backend.app.main.get_active_merges", return_value=[]),
            patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2026, 2, 15, tzinfo=timezone.utc)
            dashboard_payload = _build_activity_dashboard_payload(
                db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
                visible_weeks=12,
                week_offset=0,
                sport=None,
            )

        canonical_weekly = self._build_payload(([45.0] * 42) + ([75.0] * 14), days=120, aggregation="weekly")
        expected_by_week = {
            str(point["period_start"]): float(point["baseline_tss"])
            for point in canonical_weekly["points"]
        }

        self.assertTrue(dashboard_payload["weeks"])
        for week in dashboard_payload["weeks"]:
            week_start = str(week["week_start"])
            if week_start not in expected_by_week:
                self.assertIsNone(week["summary"]["baseline_tss"])
                continue
            self.assertEqual(
                round(float(week["summary"]["baseline_tss"]), 1),
                round(expected_by_week[week_start], 1),
            )

    def test_dashboard_current_week_summary_leaves_baseline_blank_until_week_has_a_modeled_point(self):
        metrics_df = _metrics_frame([45.0] * 91, start_day="2026-01-05")
        metrics_df["day"] = pd.to_datetime(metrics_df["start_time_utc"], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
        actual_metrics_df = metrics_df.copy()
        with (
            patch("backend.app.main._build_daily_vdot_series", side_effect=_empty_vdot_frame),
            patch("backend.app.main.get_setting", return_value=None),
            patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=420.0),
            patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=70.0),
        ):
            expected_day_agg, _, _, _ = _day_lookup_with_daily_model(
                metrics_df=metrics_df,
                daily_tss_target=60.0,
                db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
            )
        self.assertFalse(expected_day_agg.empty)
        expected_week_start = "2026-04-06"

        with (
            patch("backend.app.main._dashboard_metrics_frames", return_value=(metrics_df, actual_metrics_df)),
            patch("backend.app.main._build_daily_vdot_series", side_effect=_empty_vdot_frame),
            patch("backend.app.main.get_planned_activities_df", return_value=pd.DataFrame()),
            patch("backend.app.main.get_wellness_df", return_value=pd.DataFrame()),
            patch("backend.app.main.get_setting", return_value=None),
            patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=420.0),
            patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=70.0),
            patch("backend.app.main._load_curve_points", return_value=[]),
            patch("backend.app.main.get_active_merges", return_value=[]),
            patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2026, 4, 6, 12, tzinfo=timezone.utc)
            dashboard_payload = _build_activity_dashboard_payload(
                db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
                visible_weeks=12,
                week_offset=0,
                sport=None,
            )

        current_week = next(week for week in dashboard_payload["weeks"] if week["week_start"] == expected_week_start)
        self.assertIsNone(current_week["summary"]["baseline_tss"])


if __name__ == "__main__":
    unittest.main()

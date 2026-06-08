import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.app.main import (
    _accumulated_burden_risk,
    _acwr_with_baseline_floor,
    _autoregressive_risk_state,
    _baseline_load_scale,
    _day_lookup_with_daily_model,
)
from temperance.db import init_db


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
                "distance_proxy_km": 10.0,
                "duration_s": 3_600.0,
                "tss": float(tss),
                "rtss": float(tss),
                "calories_total": 600.0,
            }
        )
    return pd.DataFrame(rows)


def _empty_vdot_frame(_: pd.DataFrame, __: Path) -> pd.DataFrame:
    return pd.DataFrame(columns=["day", "vdot", "vdot_max"])


class BaselineLoadScaleTest(unittest.TestCase):
    def test_scales_down_aggressively_below_seventy_percent_of_baseline(self):
        scale = _baseline_load_scale(pd.Series([50.0]), 100.0)
        self.assertAlmostEqual(float(scale.iloc[0]), (0.5 / 0.7) ** 2, places=6)

    def test_equals_one_at_seventy_percent_of_baseline(self):
        scale = _baseline_load_scale(pd.Series([70.0]), 100.0)
        self.assertAlmostEqual(float(scale.iloc[0]), 1.0, places=6)

    def test_scales_above_one_when_load_exceeds_baseline(self):
        scale = _baseline_load_scale(pd.Series([150.0]), 100.0)
        self.assertAlmostEqual(float(scale.iloc[0]), 1.28, places=6)

    def test_handles_series_baseline_targets(self):
        load = pd.Series([35.0, 70.0, 140.0])
        baseline = pd.Series([100.0, 100.0, 100.0])
        scale = _baseline_load_scale(load, baseline)
        self.assertLess(float(scale.iloc[0]), 0.3)
        self.assertAlmostEqual(float(scale.iloc[1]), 1.0, places=6)
        self.assertGreater(float(scale.iloc[2]), 1.2)



class AcwrWithBaselineFloorTest(unittest.TestCase):
    def test_uses_baseline_when_it_exceeds_chronic_ema(self):
        acwr = _acwr_with_baseline_floor(
            acute_ema=pd.Series([70.0]),
            chronic_ema=pd.Series([20.0]),
            baseline_daily_target=50.0,
        )
        self.assertAlmostEqual(float(acwr.iloc[0]), 1.4, places=6)

    def test_uses_chronic_when_it_exceeds_baseline(self):
        acwr = _acwr_with_baseline_floor(
            acute_ema=pd.Series([70.0]),
            chronic_ema=pd.Series([40.0]),
            baseline_daily_target=30.0,
        )
        self.assertAlmostEqual(float(acwr.iloc[0]), 1.75, places=6)


class AutoregressiveRiskStateTest(unittest.TestCase):
    def test_repeated_moderate_overload_accumulates(self):
        signal = pd.Series([12.0] * 7)
        state = _autoregressive_risk_state(signal, decay=0.82, impulse_gain=0.22, activation_floor=5.0, upper_bound=100.0)
        self.assertGreater(float(state.iloc[-1]), float(state.iloc[0]))

    def test_single_spike_decays_gradually(self):
        signal = pd.Series([40.0] + ([0.0] * 5))
        state = _autoregressive_risk_state(signal, decay=0.82, impulse_gain=0.22, activation_floor=5.0, upper_bound=100.0)
        self.assertGreater(float(state.iloc[0]), 0.0)
        self.assertGreater(float(state.iloc[1]), 0.0)
        self.assertLess(float(state.iloc[-1]), float(state.iloc[1]))

    def test_higher_decay_preserves_state_longer(self):
        signal = pd.Series([30.0] + ([0.0] * 7))
        overreach_like = _autoregressive_risk_state(
            signal, decay=0.82, impulse_gain=0.22, activation_floor=5.0, upper_bound=100.0
        )
        injury_like = _autoregressive_risk_state(
            signal, decay=0.90, impulse_gain=0.16, activation_floor=4.0, upper_bound=100.0
        )
        self.assertGreater(float(injury_like.iloc[-1]), float(overreach_like.iloc[-1]))

    def test_easy_days_reduce_state_without_zeroing_immediately(self):
        signal = pd.Series([28.0, 26.0, 0.0, 0.0, 0.0])
        state = _autoregressive_risk_state(signal, decay=0.82, impulse_gain=0.22, activation_floor=5.0, upper_bound=100.0)
        self.assertGreater(float(state.iloc[2]), 0.0)
        self.assertGreater(float(state.iloc[3]), 0.0)
        self.assertLess(float(state.iloc[4]), float(state.iloc[2]))

    def test_low_noise_does_not_accumulate_exaggerated_risk(self):
        signal = pd.Series([1.0, 2.0, 1.5, 0.0, 2.2, 1.8])
        state = _autoregressive_risk_state(signal, decay=0.90, impulse_gain=0.16, activation_floor=4.0, upper_bound=100.0)
        self.assertAlmostEqual(float(state.max()), 0.0, places=6)


class AccumulatedBurdenRiskTest(unittest.TestCase):
    def test_repeated_exposure_accumulates_more_total_burden(self):
        raw_signal = pd.Series([20.0, 20.0])
        state, burden = _accumulated_burden_risk(
            raw_signal,
            decay=0.82,
            impulse_gain=0.22,
            activation_floor=5.0,
            upper_bound=100.0,
        )

        self.assertAlmostEqual(float(burden.iloc[0]), float(raw_signal.iloc[0]), places=6)
        self.assertGreater(float(state.iloc[1]), float(state.iloc[0]))
        self.assertGreater(float(burden.iloc[1]), float(burden.iloc[0]))

    def test_stacked_overload_beats_spaced_overload_with_same_total_excess(self):
        stacked_signal = pd.Series([20.0] * 6 + [0.0] * 6)
        spaced_signal = pd.Series([20.0, 0.0] * 6)

        _, stacked_burden = _accumulated_burden_risk(
            stacked_signal,
            decay=0.82,
            impulse_gain=0.22,
            activation_floor=5.0,
            upper_bound=100.0,
        )
        _, spaced_burden = _accumulated_burden_risk(
            spaced_signal,
            decay=0.82,
            impulse_gain=0.22,
            activation_floor=5.0,
            upper_bound=100.0,
        )

        self.assertGreater(float(stacked_burden.max()), float(spaced_burden.max()))
        self.assertGreater(float(stacked_burden.iloc[5]), float(spaced_burden.iloc[10]))


class DayLookupAccumulatedRiskTest(unittest.TestCase):
    def _model_df(self, daily_tss_values: list[float]) -> pd.DataFrame:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "day-lookup-risk-test.sqlite"
            init_db(db_path)
            with (
                patch(
                    "backend.app.main._build_daily_vdot_series",
                    side_effect=_empty_vdot_frame,
                ),
                patch("backend.app.main._load_curve_points", return_value=[]),
            ):
                _, _, _, model_df = _day_lookup_with_daily_model(
                    metrics_df=_metrics_frame(daily_tss_values),
                    daily_tss_target=60.0,
                    db_path=db_path,
                )
        return model_df

    def test_repeated_overload_block_peaks_higher_than_single_week(self):
        single_week_model = self._model_df(([60.0] * 21) + ([90.0] * 7) + ([60.0] * 14))
        repeated_block_model = self._model_df(([60.0] * 21) + ([90.0] * 14) + ([60.0] * 7))

        self.assertGreater(float(repeated_block_model["overreach"].max()), float(single_week_model["overreach"].max()))
        self.assertGreater(float(repeated_block_model["injury_risk"].max()), float(single_week_model["injury_risk"].max()))

    def test_stacked_overload_block_peaks_higher_than_spaced_pattern(self):
        stacked_model = self._model_df(([60.0] * 21) + ([85.0] * 8) + ([60.0] * 13))
        spaced_model = self._model_df(([60.0] * 21) + ([85.0, 85.0, 60.0, 60.0, 85.0, 85.0, 60.0, 60.0]) + ([60.0] * 13))

        self.assertGreater(float(stacked_model["overreach"].max()), float(spaced_model["overreach"].max()))
        self.assertGreater(float(stacked_model["injury_risk"].max()), float(spaced_model["injury_risk"].max()))


if __name__ == "__main__":
    unittest.main()

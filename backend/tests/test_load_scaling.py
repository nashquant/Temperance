import unittest

import pandas as pd

from backend.app.main import _acwr_with_baseline_floor, _autoregressive_risk_state, _baseline_load_scale


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


if __name__ == "__main__":
    unittest.main()

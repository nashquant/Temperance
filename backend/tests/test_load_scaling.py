import unittest

import pandas as pd

from backend.app.main import _acwr_with_baseline_floor, _baseline_load_scale


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


if __name__ == "__main__":
    unittest.main()

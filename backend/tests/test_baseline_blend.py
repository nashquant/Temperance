import unittest

from backend.app.main import _blend_baseline_tss


class BlendBaselineTssTest(unittest.TestCase):
    def test_full_history_at_capacity_returns_capacity(self):
        # 3 weeks at 400/wk — empirical avg equals capacity model
        result = _blend_baseline_tss(capacity_baseline=400.0, recent_load_21d=1200.0)
        self.assertAlmostEqual(result, 400.0, places=1)

    def test_history_above_capacity_pulls_baseline_up(self):
        # 3 weeks at 600/wk while capacity is 400 — history weight = 0.65
        result = _blend_baseline_tss(capacity_baseline=400.0, recent_load_21d=1800.0)
        self.assertGreater(result, 400.0)
        self.assertLess(result, 600.0)

    def test_low_volume_history_anchors_toward_capacity(self):
        # 3 weeks at 100/wk — capacity pulls baseline well above empirical
        result = _blend_baseline_tss(capacity_baseline=400.0, recent_load_21d=300.0)
        self.assertGreater(result, 100.0)
        self.assertLess(result, 400.0)

    def test_zero_history_falls_back_to_capacity(self):
        result = _blend_baseline_tss(capacity_baseline=400.0, recent_load_21d=0.0)
        self.assertAlmostEqual(result, 400.0, places=6)

    def test_floor_is_thirty_percent_of_capacity(self):
        # Even with zero history the floor is 0.30 * capacity, not lower
        result = _blend_baseline_tss(capacity_baseline=400.0, recent_load_21d=0.0)
        self.assertGreaterEqual(result, 400.0 * 0.30)

    def test_history_weight_grows_with_data_richness(self):
        # Same per-week rate but different amounts of data available.
        # Simulate "1 week of data" vs "3 weeks of data", both at 200 TSS/week.
        # More data → higher history_weight → result pulled more toward 200 (below 400 cap).
        one_week = _blend_baseline_tss(capacity_baseline=400.0, recent_load_21d=200.0)   # 200/wk for 1wk
        three_week = _blend_baseline_tss(capacity_baseline=400.0, recent_load_21d=600.0)  # 200/wk for 3wk
        # Three weeks of data at 200/wk should produce a lower baseline than one week of data at 200/wk,
        # because more weight goes to the 200/wk empirical average vs the 400 capacity model.
        self.assertLess(three_week, one_week)

    def test_zero_capacity_falls_back_to_recent_avg(self):
        result = _blend_baseline_tss(capacity_baseline=0.0, recent_load_21d=600.0)
        self.assertAlmostEqual(result, 200.0, places=6)

    def test_history_weight_saturates_at_sixty_five_percent(self):
        # Even with huge recent load, weight caps at 0.65
        cap = 400.0
        recent_21d = 100_000.0  # absurdly high
        result = _blend_baseline_tss(cap, recent_21d)
        expected_avg = recent_21d / 3.0
        # With history_weight capped at 0.65:
        expected = 0.65 * expected_avg + 0.35 * cap
        self.assertAlmostEqual(result, expected, places=3)

    def test_typical_returning_athlete_scenario(self):
        # 4:30/km athlete, capacity ≈ 436 TSS/wk; 3 weeks averaging 200 TSS/wk
        capacity = 396.0 * 1.10  # ≈ 435.6
        recent_21d = 600.0       # 200/wk
        result = _blend_baseline_tss(capacity, recent_21d)
        # Should be meaningfully below capacity but above 200
        self.assertGreater(result, 200.0)
        self.assertLess(result, capacity)
        # history_weight = min(0.65, (600 / (435.6 * 3)) * 1.30) ≈ min(0.65, 0.597) = 0.597
        # blended = 0.597 * 200 + 0.403 * 435.6 ≈ 119.4 + 175.5 ≈ 295
        self.assertAlmostEqual(result, 0.597 * 200.0 + (1 - 0.597) * capacity, delta=5.0)


if __name__ == "__main__":
    unittest.main()

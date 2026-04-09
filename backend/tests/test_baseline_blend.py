import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.app.main import (
    SETTINGS_KEY_BASELINE_BLEND,
    _blend_baseline_tss,
    _default_baseline_blend_profile,
    _load_baseline_blend_profile,
    _normalize_baseline_blend_profile,
    _settings_update_core,
    _settings_view_core,
)
from temperance.db import init_db, save_setting


DEFAULT_BLEND = {
    "history_influence_pct": 65,
    "short_history_pct": 20,
    "medium_history_pct": 35,
    "long_history_pct": 45,
}


class BlendBaselineTssTest(unittest.TestCase):
    def test_history_influence_zero_keeps_capacity_baseline(self):
        result = _blend_baseline_tss(
            capacity_baseline=400.0,
            recent_load_21d=300.0,
            recent_load_63d=2700.0,
            recent_load_365d=15600.0,
            observed_days_21d=21,
            observed_days_63d=63,
            observed_days_365d=365,
            blend_profile={
                "history_influence_pct": 0,
                "short_history_pct": 20,
                "medium_history_pct": 35,
                "long_history_pct": 45,
            },
        )
        self.assertAlmostEqual(result, 400.0, places=6)

    def test_history_influence_full_uses_history_anchor(self):
        result = _blend_baseline_tss(
            capacity_baseline=400.0,
            recent_load_21d=300.0,
            recent_load_63d=2700.0,
            recent_load_365d=15600.0,
            observed_days_21d=21,
            observed_days_63d=63,
            observed_days_365d=365,
            blend_profile={
                "history_influence_pct": 100,
                "short_history_pct": 20,
                "medium_history_pct": 35,
                "long_history_pct": 45,
            },
        )
        expected_history_anchor = (0.20 * 100.0) + (0.35 * 300.0) + (0.45 * (15600.0 / (365.0 / 7.0)))
        self.assertAlmostEqual(result, expected_history_anchor, places=6)

    def test_intermediate_history_influence_linearly_interpolates(self):
        result = _blend_baseline_tss(
            capacity_baseline=400.0,
            recent_load_21d=300.0,
            recent_load_63d=2700.0,
            recent_load_365d=15600.0,
            observed_days_21d=21,
            observed_days_63d=63,
            observed_days_365d=365,
            blend_profile={
                "history_influence_pct": 50,
                "short_history_pct": 20,
                "medium_history_pct": 35,
                "long_history_pct": 45,
            },
        )
        expected_history_anchor = (0.20 * 100.0) + (0.35 * 300.0) + (0.45 * (15600.0 / (365.0 / 7.0)))
        self.assertAlmostEqual(result, (0.50 * expected_history_anchor) + (0.50 * 400.0), places=6)

    def test_sparse_history_under_hundred_days_disables_history_anchor(self):
        result = _blend_baseline_tss(
            capacity_baseline=400.0,
            recent_load_21d=1800.0,
            recent_load_63d=2700.0,
            recent_load_365d=0.0,
            observed_days_21d=21,
            observed_days_63d=63,
            observed_days_365d=99,
            blend_profile={
                "history_influence_pct": 100,
                "short_history_pct": 20,
                "medium_history_pct": 35,
                "long_history_pct": 45,
            },
        )
        self.assertAlmostEqual(result, 180.0, places=6)

    def test_hundred_days_enables_history_anchor_with_missing_long_horizon_reweighting(self):
        result = _blend_baseline_tss(
            capacity_baseline=400.0,
            recent_load_21d=300.0,
            recent_load_63d=2700.0,
            recent_load_365d=0.0,
            observed_days_21d=21,
            observed_days_63d=63,
            observed_days_365d=100,
            blend_profile={
                "history_influence_pct": 100,
                "short_history_pct": 20,
                "medium_history_pct": 35,
                "long_history_pct": 45,
            },
        )
        expected_history_anchor = ((20.0 / 55.0) * 100.0) + ((35.0 / 55.0) * 300.0)
        self.assertAlmostEqual(result, expected_history_anchor, places=6)

    def test_single_available_horizon_receives_full_weight(self):
        result = _blend_baseline_tss(
            capacity_baseline=200.0,
            recent_load_21d=300.0,
            recent_load_63d=0.0,
            recent_load_365d=0.0,
            observed_days_21d=21,
            observed_days_63d=62,
            observed_days_365d=120,
            blend_profile={
                "history_influence_pct": 100,
                "short_history_pct": 100,
                "medium_history_pct": 0,
                "long_history_pct": 0,
            },
        )
        self.assertAlmostEqual(result, 100.0, places=6)

    def test_full_influence_with_no_available_horizons_falls_to_fixed_floor(self):
        result = _blend_baseline_tss(
            capacity_baseline=400.0,
            recent_load_21d=0.0,
            recent_load_63d=0.0,
            recent_load_365d=0.0,
            observed_days_21d=21,
            observed_days_63d=63,
            observed_days_365d=365,
            blend_profile={
                "history_influence_pct": 100,
                "short_history_pct": 20,
                "medium_history_pct": 35,
                "long_history_pct": 45,
            },
        )
        self.assertAlmostEqual(result, 120.0, places=6)

    def test_zero_capacity_falls_back_to_history_anchor(self):
        result = _blend_baseline_tss(
            capacity_baseline=0.0,
            recent_load_21d=300.0,
            recent_load_63d=2700.0,
            recent_load_365d=15600.0,
            observed_days_21d=21,
            observed_days_63d=63,
            observed_days_365d=365,
            blend_profile=DEFAULT_BLEND,
        )
        expected_history_anchor = (0.20 * 100.0) + (0.35 * 300.0) + (0.45 * (15600.0 / (365.0 / 7.0)))
        self.assertAlmostEqual(result, expected_history_anchor, places=6)

    def test_normalized_profile_preserves_zero_values(self):
        normalized = _normalize_baseline_blend_profile(
            {
                "history_influence_pct": 0,
                "short_history_pct": 100,
                "medium_history_pct": 0,
                "long_history_pct": 0,
            }
        )
        self.assertEqual(
            normalized,
            {
                "history_influence_pct": 0,
                "short_history_pct": 100,
                "medium_history_pct": 0,
                "long_history_pct": 0,
            },
        )


class BaselineBlendSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "settings.sqlite"
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_settings_view_returns_only_simplified_baseline_fields(self):
        view = _settings_view_core(self.db_path)
        self.assertEqual(
            view["baseline_blend"],
            _default_baseline_blend_profile(),
        )
        self.assertEqual(
            set(view["baseline_blend"].keys()),
            {"history_influence_pct", "short_history_pct", "medium_history_pct", "long_history_pct"},
        )

    def test_settings_update_persists_valid_integer_baseline_fields(self):
        payload = {
            "baseline_blend": {
                "history_influence_pct": 0,
                "short_history_pct": 33,
                "medium_history_pct": 33,
                "long_history_pct": 34,
            }
        }
        result = _settings_update_core(self.db_path, payload)
        self.assertEqual(result["updated"], ["baseline_blend"])
        self.assertEqual(
            _load_baseline_blend_profile(self.db_path),
            payload["baseline_blend"],
        )

    def test_settings_update_rejects_horizon_totals_below_hundred(self):
        with self.assertRaises(HTTPException) as exc:
            _settings_update_core(
                self.db_path,
                {
                    "baseline_blend": {
                        "history_influence_pct": 65,
                        "short_history_pct": 33,
                        "medium_history_pct": 33,
                        "long_history_pct": 33,
                    }
                },
            )
        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("must equal 100", str(exc.exception.detail))

    def test_settings_update_rejects_horizon_totals_above_hundred(self):
        with self.assertRaises(HTTPException) as exc:
            _settings_update_core(
                self.db_path,
                {
                    "baseline_blend": {
                        "history_influence_pct": 65,
                        "short_history_pct": 50,
                        "medium_history_pct": 30,
                        "long_history_pct": 21,
                    }
                },
            )
        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("must equal 100", str(exc.exception.detail))

    def test_settings_update_rejects_non_integer_percentages(self):
        with self.assertRaises(HTTPException) as exc:
            _settings_update_core(
                self.db_path,
                {
                    "baseline_blend": {
                        "history_influence_pct": 65.5,
                        "short_history_pct": 20,
                        "medium_history_pct": 35,
                        "long_history_pct": 45,
                    }
                },
            )
        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("integer percentage", str(exc.exception.detail))

    def test_legacy_saved_payload_is_ignored_and_resets_to_defaults(self):
        save_setting(
            self.db_path,
            SETTINGS_KEY_BASELINE_BLEND,
            json.dumps(
                {
                    "history_weight_cap": 0.78,
                    "history_weight_scale": 1.30,
                    "window_21d_weight": 0.20,
                    "window_63d_weight": 0.35,
                    "window_365d_weight": 0.45,
                }
            ),
        )
        self.assertEqual(_load_baseline_blend_profile(self.db_path), _default_baseline_blend_profile())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tss import (  # noqa: E402
    ActivityTSSInput,
    ConstantLTHRProvider,
    ConstantThresholdPaceProvider,
    LTHRProvider,
    ThresholdPaceProvider,
    compute_hrtss,
    compute_rtss,
    compute_tss_bundle,
)


def _activity(
    duration_s: int = 3600,
    pace_s_per_km: float | None = 300.0,
    avg_hr: float | None = 170.0,
) -> ActivityTSSInput:
    return ActivityTSSInput(
        activity_duration_seconds=duration_s,
        activity_avg_pace_sec_per_km=pace_s_per_km,
        activity_avg_hr_bpm=avg_hr,
        activity_start_datetime=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
    )


def test_rtss_with_constant_threshold_pace() -> None:
    activity = _activity(duration_s=3600, pace_s_per_km=300.0, avg_hr=None)
    provider = ConstantThresholdPaceProvider(threshold_pace_sec_per_km=300.0)
    assert compute_rtss(activity, provider) == pytest.approx(100.0, rel=1e-9)


def test_hrtss_with_constant_lthr() -> None:
    activity = _activity(duration_s=3600, pace_s_per_km=None, avg_hr=178.0)
    provider = ConstantLTHRProvider(lthr_bpm=178.0)
    assert compute_hrtss(activity, provider) == pytest.approx(100.0, rel=1e-9)


def test_tss_bundle_both_metrics() -> None:
    activity = _activity(duration_s=1800, pace_s_per_km=320.0, avg_hr=160.0)
    bundle = compute_tss_bundle(
        activity,
        pace_provider=ConstantThresholdPaceProvider(threshold_pace_sec_per_km=300.0),
        lthr_provider=ConstantLTHRProvider(lthr_bpm=178.0),
    )
    assert "rTSS" in bundle and "hrTSS" in bundle
    assert bundle["rTSS"] > 0
    assert bundle["hrTSS"] > 0


def test_tss_bundle_missing_pace_hr_present() -> None:
    activity = _activity(duration_s=1800, pace_s_per_km=None, avg_hr=160.0)
    bundle = compute_tss_bundle(
        activity,
        pace_provider=ConstantThresholdPaceProvider(threshold_pace_sec_per_km=300.0),
        lthr_provider=ConstantLTHRProvider(lthr_bpm=178.0),
    )
    assert "rTSS" not in bundle
    assert "hrTSS" in bundle


def test_tss_bundle_missing_hr_pace_present() -> None:
    activity = _activity(duration_s=1800, pace_s_per_km=320.0, avg_hr=None)
    bundle = compute_tss_bundle(
        activity,
        pace_provider=ConstantThresholdPaceProvider(threshold_pace_sec_per_km=300.0),
        lthr_provider=ConstantLTHRProvider(lthr_bpm=178.0),
    )
    assert "rTSS" in bundle
    assert "hrTSS" not in bundle


@pytest.mark.parametrize("duration_s", [0, -1])
def test_invalid_duration_raises(duration_s: int) -> None:
    activity = _activity(duration_s=duration_s, pace_s_per_km=300.0, avg_hr=160.0)
    with pytest.raises(ValueError):
        compute_tss_bundle(
            activity,
            pace_provider=ConstantThresholdPaceProvider(threshold_pace_sec_per_km=300.0),
            lthr_provider=ConstantLTHRProvider(lthr_bpm=178.0),
        )


def test_invalid_provider_values_raise() -> None:
    activity = _activity(duration_s=1800, pace_s_per_km=300.0, avg_hr=160.0)
    with pytest.raises(ValueError):
        compute_rtss(activity, ConstantThresholdPaceProvider(threshold_pace_sec_per_km=0.0))
    with pytest.raises(ValueError):
        compute_hrtss(activity, ConstantLTHRProvider(lthr_bpm=0.0))


def test_hr_sanity_check_raises_when_unrealistic() -> None:
    activity = _activity(duration_s=1800, pace_s_per_km=None, avg_hr=300.0)
    with pytest.raises(ValueError):
        compute_hrtss(activity, ConstantLTHRProvider(lthr_bpm=178.0))


class CurveThresholdPaceProvider(ThresholdPaceProvider):
    def get_threshold_pace_sec_per_km(self, at: datetime) -> float:
        return 295.0 if at.year >= 2026 else 305.0


class CurveLTHRProvider(LTHRProvider):
    def get_lthr_bpm(self, at: datetime) -> float:
        return 180.0 if at.year >= 2026 else 175.0


def test_curve_providers_extensibility() -> None:
    activity = _activity(duration_s=3600, pace_s_per_km=300.0, avg_hr=178.0)
    bundle = compute_tss_bundle(
        activity,
        pace_provider=CurveThresholdPaceProvider(),
        lthr_provider=CurveLTHRProvider(),
    )
    assert bundle["rTSS"] == pytest.approx((3600 * (295.0 / 300.0) ** 2) / 3600 * 100, rel=1e-9)
    assert bundle["hrTSS"] == pytest.approx((3600 * (178.0 / 180.0) ** 2) / 3600 * 100, rel=1e-9)

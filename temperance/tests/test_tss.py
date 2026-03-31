from __future__ import annotations

from datetime import datetime, timezone

import pytest

from temperance.tss import (
    ActivityDistanceProxyInput,
    ActivityTSSInput,
    ConstantLTHRProvider,
    ConstantThresholdPaceProvider,
    LTHRProvider,
    PiecewiseThresholdPaceProvider,
    ThresholdPaceProvider,
    compute_hrtss,
    compute_distance_proxy,
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


def test_piecewise_threshold_provider_selects_latest_point() -> None:
    provider = PiecewiseThresholdPaceProvider(
        default_threshold_pace_sec_per_km=300.0,
        points=(
            (datetime(2025, 1, 1, tzinfo=timezone.utc), 220.0),
            (datetime(2026, 1, 1, tzinfo=timezone.utc), 210.0),
        ),
    )
    assert provider.get_threshold_pace_sec_per_km(datetime(2024, 12, 1, tzinfo=timezone.utc)) == 300.0
    assert provider.get_threshold_pace_sec_per_km(datetime(2025, 6, 1, tzinfo=timezone.utc)) == 220.0
    assert provider.get_threshold_pace_sec_per_km(datetime(2026, 2, 1, tzinfo=timezone.utc)) == 210.0


def test_distance_proxy_running_returns_original_distance() -> None:
    proxy = compute_distance_proxy(
        activity=ActivityDistanceProxyInput(
            sport_type="running",
            activity_duration_seconds=1800.0,
            activity_distance_km=5.0,
            activity_avg_pace_sec_per_km=360.0,
        ),
        threshold_pace_sec_per_km=300.0,
        tss=75.0,
        specificity_ratio=0.8,
    )
    assert proxy["distance_proxy_km"] == pytest.approx(5.0, rel=1e-9)
    assert proxy["pace_proxy_sec_per_km"] == 360
    assert proxy["distance_proxy_method"] == "none_running"


def test_distance_proxy_non_running_parity_matches_effective_rtss_target() -> None:
    duration_s = 3600.0
    threshold_pace = 300.0
    tss = 100.0
    specificity = 0.8
    proxy = compute_distance_proxy(
        activity=ActivityDistanceProxyInput(
            sport_type="cycling",
            activity_duration_seconds=duration_s,
            activity_distance_km=None,
            activity_avg_pace_sec_per_km=None,
        ),
        threshold_pace_sec_per_km=threshold_pace,
        tss=tss,
        specificity_ratio=specificity,
    )
    assert proxy["distance_proxy_method"] == "tss_parity_root_solve"
    assert proxy["distance_proxy_km"] is not None
    assert proxy["pace_proxy_sec_per_km"] is not None

    pace = float(proxy["pace_proxy_sec_per_km"])
    reconstructed_rtss = (duration_s * ((threshold_pace / pace) ** 2) / 3600.0) * 100.0
    assert reconstructed_rtss == pytest.approx(tss * specificity, rel=0.02)


def test_distance_proxy_specificity_not_applied_twice() -> None:
    duration_s = 3600.0
    threshold_pace = 300.0
    tss = 100.0
    specificity = 0.8
    proxy = compute_distance_proxy(
        activity=ActivityDistanceProxyInput(
            sport_type="elliptical",
            activity_duration_seconds=duration_s,
            activity_distance_km=None,
            activity_avg_pace_sec_per_km=None,
        ),
        threshold_pace_sec_per_km=threshold_pace,
        tss=tss,
        specificity_ratio=specificity,
    )
    assert proxy["distance_proxy_method"] == "tss_parity_root_solve"
    expected_pace_once = threshold_pace / ((tss * specificity / 100.0) ** 0.5)
    expected_distance_once = duration_s / expected_pace_once
    expected_distance_twice = expected_distance_once * specificity
    assert proxy["distance_proxy_km"] == pytest.approx(expected_distance_once, rel=1e-9)
    assert float(proxy["distance_proxy_km"]) != pytest.approx(expected_distance_twice, rel=1e-9)


def test_distance_proxy_unavailable_when_inputs_missing() -> None:
    proxy = compute_distance_proxy(
        activity=ActivityDistanceProxyInput(
            sport_type="cycling",
            activity_duration_seconds=0.0,
            activity_distance_km=None,
            activity_avg_pace_sec_per_km=None,
        ),
        threshold_pace_sec_per_km=300.0,
        tss=80.0,
        specificity_ratio=0.8,
    )
    assert proxy["distance_proxy_km"] is None
    assert proxy["pace_proxy_sec_per_km"] is None
    assert proxy["distance_proxy_method"] == "unavailable"


def test_distance_proxy_unavailable_for_strength_training() -> None:
    proxy = compute_distance_proxy(
        activity=ActivityDistanceProxyInput(
            sport_type="strength_training",
            activity_duration_seconds=3600.0,
            activity_distance_km=None,
            activity_avg_pace_sec_per_km=None,
        ),
        threshold_pace_sec_per_km=300.0,
        tss=80.0,
        specificity_ratio=0.8,
    )
    assert proxy["distance_proxy_km"] is None
    assert proxy["pace_proxy_sec_per_km"] is None
    assert proxy["distance_proxy_method"] == "unavailable"

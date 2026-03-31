from temperance.models import (
    aerobic_load,
    bannister_trimp,
    edwards_trimp,
    edwards_trimp_from_zones,
    mechanical_load,
)


def test_bannister_trimp_increases_with_hr() -> None:
    low = bannister_trimp(duration_s=3600, avg_hr=130, resting_hr=55, max_hr=190)
    high = bannister_trimp(duration_s=3600, avg_hr=160, resting_hr=55, max_hr=190)
    assert high > low > 0


def test_edwards_trimp_zone_weighting() -> None:
    z2 = edwards_trimp(duration_s=1800, avg_hr=120, max_hr=200)
    z4 = edwards_trimp(duration_s=1800, avg_hr=165, max_hr=200)
    assert z4 > z2


def test_aerobic_load_fallback_to_edwards() -> None:
    score = aerobic_load(duration_s=1800, avg_hr=150, resting_hr=None, max_hr=190)
    assert score > 0


def test_edwards_trimp_from_zones_weighting() -> None:
    score = edwards_trimp_from_zones(
        hr_zone_1_s=600,  # 10 min * 1
        hr_zone_2_s=600,  # 10 min * 2
        hr_zone_3_s=0,
        hr_zone_4_s=0,
        hr_zone_5_s=0,
    )
    assert score == 30.0


def test_edwards_trimp_from_zones_handles_missing() -> None:
    score = edwards_trimp_from_zones(None, None, None, None, None)
    assert score == 0.0


def test_mechanical_load_sensitive_to_pace_and_distance() -> None:
    easy_short = mechanical_load(distance_m=5000, duration_s=1800)
    faster_same_distance = mechanical_load(distance_m=5000, duration_s=1400)
    longer_same_pace = mechanical_load(distance_m=10000, duration_s=3600)
    assert faster_same_distance > easy_short
    assert longer_same_pace > easy_short


def test_mechanical_load_hills_increase_score() -> None:
    flat = mechanical_load(distance_m=10000, duration_s=3000, elevation_gain_m=0)
    hilly = mechanical_load(distance_m=10000, duration_s=3000, elevation_gain_m=300)
    assert hilly > flat


def test_mechanical_load_v15_cadence_stride_power_increase_score() -> None:
    baseline = mechanical_load(distance_m=10000, duration_s=3000, elevation_gain_m=50)
    enriched = mechanical_load(
        distance_m=10000,
        duration_s=3000,
        elevation_gain_m=50,
        avg_cadence=178,
        avg_stride_length=1.2,
        running_power_avg=320,
    )
    assert enriched > baseline


def test_mechanical_load_handles_missing_optional_inputs() -> None:
    score = mechanical_load(
        distance_m=8000,
        duration_s=2600,
        elevation_gain_m=None,
        avg_cadence=None,
        avg_stride_length=None,
        running_power_avg=None,
    )
    assert score > 0


def test_mechanical_load_zone_intensity_increases_score() -> None:
    easy_zones = mechanical_load(
        distance_m=10000,
        duration_s=3000,
        hr_zone_1_s=2200,
        hr_zone_2_s=700,
        hr_zone_3_s=100,
        hr_zone_4_s=0,
        hr_zone_5_s=0,
    )
    hard_zones = mechanical_load(
        distance_m=10000,
        duration_s=3000,
        hr_zone_1_s=200,
        hr_zone_2_s=700,
        hr_zone_3_s=1300,
        hr_zone_4_s=600,
        hr_zone_5_s=200,
    )
    assert hard_zones > easy_zones

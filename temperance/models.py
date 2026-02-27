from __future__ import annotations

import math


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def bannister_trimp(
    duration_s: float,
    avg_hr: float,
    resting_hr: float,
    max_hr: float,
    sex: str = "male",
) -> float:
    """
    Bannister TRIMP using average intensity over session.

    Assumptions/limits for v1:
    - Uses session average HR, not full HR time-series.
    - HR reserve intensity is clamped to [0, 1].
    - Sex-specific constants from common Bannister/TRIMP usage.
    """
    if duration_s <= 0 or max_hr <= resting_hr or avg_hr <= 0:
        return 0.0

    hr_r = _clamp((avg_hr - resting_hr) / (max_hr - resting_hr), 0.0, 1.0)
    duration_min = duration_s / 60.0

    sex_lower = sex.lower()
    if sex_lower.startswith("f"):
        a, b = 0.86, 1.67
    else:
        a, b = 0.64, 1.92

    return duration_min * hr_r * a * math.exp(b * hr_r)


def edwards_trimp(duration_s: float, avg_hr: float, max_hr: float) -> float:
    """
    Edwards TRIMP fallback using average HR zone.

    v1 limitation:
    - True Edwards TRIMP needs time in each HR zone.
    - Here we place all duration into the zone implied by average HR.
    """
    if duration_s <= 0 or avg_hr <= 0 or max_hr <= 0:
        return 0.0

    duration_min = duration_s / 60.0
    intensity = avg_hr / max_hr

    if intensity < 0.6:
        weight = 1
    elif intensity < 0.7:
        weight = 2
    elif intensity < 0.8:
        weight = 3
    elif intensity < 0.9:
        weight = 4
    else:
        weight = 5

    return duration_min * weight


def edwards_trimp_from_zones(
    hr_zone_1_s: float | None,
    hr_zone_2_s: float | None,
    hr_zone_3_s: float | None,
    hr_zone_4_s: float | None,
    hr_zone_5_s: float | None,
) -> float:
    """
    Edwards TRIMP using time spent in HR zones.

    Assumes Garmin zone time fields are in seconds.
    Zone multipliers are 1..5 respectively.
    """
    zone_seconds = [
        max(float(hr_zone_1_s or 0.0), 0.0),
        max(float(hr_zone_2_s or 0.0), 0.0),
        max(float(hr_zone_3_s or 0.0), 0.0),
        max(float(hr_zone_4_s or 0.0), 0.0),
        max(float(hr_zone_5_s or 0.0), 0.0),
    ]
    weights = [1.0, 2.0, 3.0, 4.0, 5.0]
    return sum((sec / 60.0) * w for sec, w in zip(zone_seconds, weights))


def aerobic_load(
    duration_s: float,
    avg_hr: float | None,
    resting_hr: float | None,
    max_hr: float | None,
    sex: str = "male",
) -> float:
    if duration_s <= 0 or not avg_hr:
        return 0.0

    if resting_hr and max_hr and max_hr > resting_hr:
        return bannister_trimp(duration_s, avg_hr, resting_hr, max_hr, sex=sex)

    if max_hr:
        return edwards_trimp(duration_s, avg_hr, max_hr)

    return 0.0


def mechanical_load(
    distance_m: float,
    duration_s: float,
    elevation_gain_m: float | None = None,
    baseline_pace_s_per_km: float = 300.0,
    avg_cadence: float | None = None,
    avg_stride_length: float | None = None,
    running_power_avg: float | None = None,
    step_weight: float = 0.2,
    stride_weight: float = 0.15,
    hill_weight: float = 0.2,
    power_weight: float = 0.2,
) -> float:
    """
    Mechanical load proxy for running.

    Assumptions/limits for v1:
    - Distance is primary driver.
    - Faster pace increases load (proxy for higher peak forces).
    - Hills add a moderate multiplier if ascent is available.
    """
    if distance_m <= 0 or duration_s <= 0:
        return 0.0

    distance_km = distance_m / 1000.0
    pace_s_per_km = duration_s / max(distance_km, 0.001)

    pace_factor = _clamp(baseline_pace_s_per_km / pace_s_per_km, 0.6, 1.8)

    hill_factor = 1.0
    if elevation_gain_m and elevation_gain_m > 0:
        grade_proxy = _clamp(elevation_gain_m / max(distance_m, 1.0), 0.0, 0.12)
        hill_factor += grade_proxy * (1.0 + hill_weight)

    step_factor = 1.0
    if avg_cadence and avg_cadence > 0:
        # cadence in steps/min * duration gives a step-count proxy.
        step_count_proxy = avg_cadence * (duration_s / 60.0)
        reference_steps = max(distance_km * 1000.0 / 1.2, 1.0)
        step_ratio = _clamp(step_count_proxy / reference_steps, 0.7, 1.4)
        step_factor += step_weight * (step_ratio - 1.0)

    stride_factor = 1.0
    if avg_stride_length and avg_stride_length > 0:
        stride_ratio = _clamp(avg_stride_length / 1.1, 0.7, 1.35)
        stride_factor += stride_weight * (stride_ratio - 1.0)

    power_factor = 1.0
    if running_power_avg and running_power_avg > 0:
        power_ratio = _clamp(running_power_avg / 260.0, 0.7, 1.5)
        power_factor += power_weight * (power_ratio - 1.0)

    return distance_km * pace_factor * hill_factor * step_factor * stride_factor * power_factor

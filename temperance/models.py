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
        hill_factor += grade_proxy * 1.5

    return distance_km * pace_factor * hill_factor

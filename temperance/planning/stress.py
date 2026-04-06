from __future__ import annotations

from temperance.planning.models import DayType, StressProfile


def compute_toughness_score(
    *,
    estimated_tss: float,
    avg_if: float,
    max_if: float,
    total_minutes: float,
    modality: str,
    bucket: str = "",
    weekly_baseline_tss: float | None = None,
) -> float:
    reference_tss = max(float(weekly_baseline_tss) * 0.18, 1.0) if weekly_baseline_tss is not None and weekly_baseline_tss > 0 else 100.0
    load_component = min(max(float(estimated_tss) / reference_tss, 0.0), 1.5)
    intensity_component = max(float(avg_if), (0.65 * float(avg_if)) + (0.35 * float(max_if)))
    duration_reference = 120.0 if str(modality or "").strip().lower() == "running" else 100.0
    duration_component = min(max(float(total_minutes), 0.0) / duration_reference, 1.25)
    normalized_bucket = str(bucket or "").strip().lower()
    bucket_adjustment = 0.0
    if normalized_bucket in {"intervals", "tempo", "fartlek"}:
        bucket_adjustment += 0.06
    elif normalized_bucket == "long":
        bucket_adjustment += 0.05
    elif normalized_bucket == "steady":
        bucket_adjustment += 0.02
    elif normalized_bucket in {"recovery", "easy"}:
        bucket_adjustment -= 0.03
    return (
        (0.45 * load_component)
        + (0.40 * intensity_component)
        + (0.15 * duration_component)
        + bucket_adjustment
    )


def classify_session_stress(
    *,
    estimated_tss: float,
    avg_if: float,
    max_if: float,
    total_minutes: float,
    modality: str,
    bucket: str = "",
    weekly_baseline_tss: float | None = None,
    stress_profile: StressProfile | None = None,
) -> tuple[DayType, float, str | None]:
    profile = stress_profile or StressProfile()
    score = compute_toughness_score(
        estimated_tss=estimated_tss,
        avg_if=avg_if,
        max_if=max_if,
        total_minutes=total_minutes,
        modality=modality,
        bucket=bucket,
        weekly_baseline_tss=weekly_baseline_tss,
    )

    day_type = DayType.EASY
    if score >= profile.moderate_max_score:
        day_type = DayType.HARD
    elif score >= profile.easy_max_score:
        day_type = DayType.MODERATE

    override_reason = None
    if day_type == DayType.MODERATE and max(float(avg_if), float(max_if)) >= 0.88 and float(estimated_tss) <= 65.0:
        override_reason = "stress_class_too_low_for_if"
    elif day_type == DayType.HARD and max(float(avg_if), float(max_if)) >= 0.90 and float(estimated_tss) <= 80.0:
        override_reason = "stress_class_too_low_for_if"
    return day_type, score, override_reason


def is_threshold_like(
    *,
    bucket: str,
    avg_if: float,
    max_if: float,
    stress_profile: StressProfile | None = None,
) -> bool:
    profile = stress_profile or StressProfile()
    normalized = str(bucket or "").strip().lower()
    return normalized in {"tempo", "intervals", "fartlek"} or avg_if > profile.moderate_max_avg_if or max_if > profile.moderate_max_max_if


def is_long_run_candidate(
    *,
    modality: str,
    total_minutes: float,
    avg_if: float,
    max_if: float,
    stress_profile: StressProfile | None = None,
) -> bool:
    profile = stress_profile or StressProfile()
    normalized_modality = str(modality or "").strip().lower()
    anchor_duration_floor = max(profile.long_run_min_minutes, profile.long_run_anchor_min_minutes)
    return (
        normalized_modality == "running"
        and float(total_minutes) >= anchor_duration_floor
        and float(total_minutes) <= profile.long_run_max_minutes
        and float(avg_if) >= profile.long_run_min_avg_if
        and float(avg_if) <= profile.long_run_max_avg_if
        and float(max_if) <= profile.long_run_max_max_if
    )

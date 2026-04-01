from __future__ import annotations

from collections.abc import Iterable, Mapping

from temperance.planning.models import (
    DayIntent,
    DayType,
    HardSubtype,
    SessionCandidate,
    StressProfile,
    UserPlanningState,
)
from temperance.planning.stress import classify_session_stress, is_long_run_candidate, is_threshold_like


def _normalized_modality(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"run", "running", "treadmill"}:
        return "running"
    if raw in {"elliptical", "xtrain", "x-train", "cross-train"}:
        return "elliptical"
    if raw in {"bike", "cycling"}:
        return "bike"
    return raw or "unknown"


def _candidate_hard_subtype(
    *,
    stress_class: DayType,
    modality: str,
    total_minutes: float,
    avg_if: float,
    max_if: float,
    stress_profile: StressProfile,
) -> HardSubtype | None:
    if stress_class != DayType.HARD:
        return None
    if is_long_run_candidate(
        modality=modality,
        total_minutes=total_minutes,
        avg_if=avg_if,
        max_if=max_if,
        stress_profile=stress_profile,
    ):
        return HardSubtype.H2
    return HardSubtype.H1


def build_session_candidates(
    raw_candidates: Iterable[Mapping[str, object]],
    *,
    weekly_baseline_tss: float | None = None,
    stress_profile: StressProfile | None = None,
) -> list[SessionCandidate]:
    profile = stress_profile or StressProfile()
    out: list[SessionCandidate] = []
    for raw in raw_candidates:
        bucket = str(raw.get("bucket") or "").strip().lower()
        total_minutes = float(raw.get("total_minutes") or 0.0)
        avg_if = float(raw.get("avg_if") or 0.0)
        max_if = float(raw.get("max_if") or 0.0)
        modality = _normalized_modality(str(raw.get("modality") or ""))
        stress_class, toughness_score, override_reason = classify_session_stress(
            estimated_tss=float(raw.get("estimated_tss") or 0.0),
            avg_if=avg_if,
            max_if=max_if,
            total_minutes=total_minutes,
            modality=modality,
            bucket=bucket,
            weekly_baseline_tss=weekly_baseline_tss,
            stress_profile=profile,
        )
        hard_subtype = _candidate_hard_subtype(
            stress_class=stress_class,
            modality=modality,
            total_minutes=total_minutes,
            avg_if=avg_if,
            max_if=max_if,
            stress_profile=profile,
        )
        threshold_like = is_threshold_like(
            bucket=bucket,
            avg_if=avg_if,
            max_if=max_if,
            stress_profile=profile,
        )
        is_long_run = is_long_run_candidate(
            modality=modality,
            total_minutes=total_minutes,
            avg_if=avg_if,
            max_if=max_if,
            stress_profile=profile,
        )
        mechanical_load = bool(modality == "running" and (is_long_run or total_minutes >= 75.0))
        out.append(
            SessionCandidate(
                activity_text=str(raw.get("activity_text") or "").strip(),
                estimated_tss=float(raw.get("estimated_tss") or 0.0),
                bucket=bucket,
                modality=modality,
                total_minutes=total_minutes,
                avg_if=avg_if,
                max_if=max_if,
                priority=int(raw.get("priority") or 0),
                stress_class=stress_class,
                hard_subtype=hard_subtype,
                threshold_like=threshold_like,
                mechanical_load=mechanical_load,
                toughness_score=toughness_score,
                is_long_run=is_long_run,
                long_run_duration_min=total_minutes if is_long_run else 0.0,
                stress_override_reason=override_reason,
                source=str(raw.get("source") or ""),
            )
        )
    return out


def select_session_candidate(
    *,
    candidates: Iterable[SessionCandidate],
    intent: DayIntent,
    state: UserPlanningState,
    previous_activity_text: str | None = None,
    stress_profile: StressProfile | None = None,
) -> tuple[SessionCandidate | None, tuple[str, ...]]:
    profile = stress_profile or StressProfile()
    if intent.day_type == DayType.REST or intent.planned_rest:
        return None, ("planned_rest_day",)

    scored: list[tuple[float, SessionCandidate]] = []
    rejections: list[str] = []
    previous_text = str(previous_activity_text or "").strip().lower()
    prefer_low_impact = bool(state.mechanical_risk.prefer_low_impact)

    for candidate in candidates:
        reasons: list[str] = []
        score = abs(float(candidate.estimated_tss) - float(intent.target_tss))

        if candidate.stress_override_reason == "stress_class_too_low_for_if" and intent.day_type == DayType.EASY:
            reasons.append("stress_class_too_low_for_if")
        if candidate.hard_subtype == HardSubtype.H2 and not intent.is_weekend:
            reasons.append("weekday_long_run_not_allowed")
        if intent.day_type == DayType.EASY and candidate.stress_class == DayType.HARD:
            reasons.append("easy_day_excludes_hard_candidate")
        if intent.day_type == DayType.MODERATE:
            if candidate.threshold_like or candidate.avg_if > profile.moderate_max_avg_if or candidate.max_if > profile.moderate_max_max_if:
                reasons.append("moderate_day_excludes_intensity_drift")
            elif candidate.stress_class == DayType.HARD:
                reasons.append("moderate_day_excludes_hard_candidate")

        if intent.day_type == DayType.HARD and intent.hard_subtype == HardSubtype.H2:
            if candidate.hard_subtype != HardSubtype.H2:
                reasons.append("metabolic_hard_day_excludes_non_long_run")
            if candidate.total_minutes < intent.min_duration_min:
                reasons.append("long_run_too_short")
            if intent.max_duration_min > 0 and candidate.total_minutes > intent.max_duration_min:
                reasons.append("long_run_too_long")
            if candidate.avg_if > intent.max_avg_if or candidate.max_if > profile.long_run_max_max_if:
                reasons.append("long_run_too_intense")
            if intent.target_duration_min > 0:
                score += abs(candidate.total_minutes - intent.target_duration_min) * 0.6
        elif intent.day_type == DayType.HARD and intent.hard_subtype == HardSubtype.H1 and candidate.hard_subtype == HardSubtype.H2:
            reasons.append("metabolic_hard_day_excludes_long_run")

        if intent.modality_bias == "elliptical" and candidate.modality != "elliptical":
            score += 9.0
        if intent.modality_bias == "running" and candidate.modality != "running":
            score += 6.0
        if prefer_low_impact and intent.day_type != DayType.HARD and candidate.modality == "running":
            score += 10.0
        if prefer_low_impact and candidate.mechanical_load and intent.day_type != DayType.HARD:
            score += 14.0
        if previous_text and previous_text == candidate.activity_text.lower():
            score += 12.0

        if candidate.stress_class != intent.day_type:
            if intent.day_type == DayType.MODERATE and candidate.stress_class == DayType.EASY:
                score += 5.0
            else:
                score += 18.0

        if reasons:
            rejections.extend(reasons)
            continue
        scored.append((score, candidate))

    if not scored:
        return None, tuple(dict.fromkeys(rejections))
    scored.sort(key=lambda pair: (pair[0], -pair[1].estimated_tss, pair[1].activity_text))
    return scored[0][1], tuple(dict.fromkeys(rejections))

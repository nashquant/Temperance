from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import date, timedelta
import random

from temperance.planning.day_type_sampler import DEFAULT_SAMPLER_CONFIG, compute_target_day_tss, sample_day_tss_share
from temperance.planning.models import (
    DayIntent,
    DayType,
    GeneratedWorkout,
    HardSubtype,
    PlanningDecision,
    PlanningExplanation,
    SessionCandidate,
    UserPlanningState,
)
from temperance.planning.session_selector import select_session_candidate
from temperance.planning.workout_formatter import render_generated_workout


CYCLE_ORDER: tuple[DayType, ...] = (DayType.EASY, DayType.MODERATE, DayType.HARD)


def _next_cycle_day(previous_day_type: DayType | None) -> DayType:
    if previous_day_type not in CYCLE_ORDER:
        return DayType.EASY
    idx = CYCLE_ORDER.index(previous_day_type)
    return CYCLE_ORDER[(idx + 1) % len(CYCLE_ORDER)]


def _constraint_for_day(state: UserPlanningState, day_utc: str):
    for constraint in state.schedule_constraints:
        if constraint.day_utc == day_utc:
            return constraint
    return None


def infer_cycle_position(state: UserPlanningState) -> tuple[DayType, str, DayType | None]:
    target_day = date.fromisoformat(state.target_day_utc)
    history = sorted(
        [
            item
            for item in (*state.recent_activities, *state.planned_activities)
            if item.stress_class in CYCLE_ORDER and date.fromisoformat(item.day_utc) < target_day
        ],
        key=lambda item: item.day_utc,
    )
    if history:
        previous = history[-1].stress_class
        assert previous is not None
        return _next_cycle_day(previous), history[-1].source, previous
    return DayType.EASY, "default", None


def _days_since_last_h2(state: UserPlanningState, day_utc: str) -> int | None:
    current_day = date.fromisoformat(day_utc)
    history = sorted(
        [
            item
            for item in (*state.recent_activities, *state.planned_activities)
            if item.hard_subtype == HardSubtype.H2 and date.fromisoformat(item.day_utc) < current_day
        ],
        key=lambda item: item.day_utc,
    )
    if not history:
        return None
    return (current_day - date.fromisoformat(history[-1].day_utc)).days


def _last_hard_subtype(state: UserPlanningState, day_utc: str) -> HardSubtype | None:
    current_day = date.fromisoformat(day_utc)
    history = sorted(
        [
            item
            for item in (*state.recent_activities, *state.planned_activities)
            if item.hard_subtype is not None and date.fromisoformat(item.day_utc) < current_day
        ],
        key=lambda item: item.day_utc,
    )
    return history[-1].hard_subtype if history else None


def _build_naive_horizon(start_day: date, first_day_type: DayType, horizon_days: int) -> list[DayIntent]:
    intents: list[DayIntent] = []
    current_type = first_day_type
    for idx in range(horizon_days):
        day_value = start_day + timedelta(days=idx)
        intents.append(
            DayIntent(
                day_utc=day_value.isoformat(),
                sequence_index=idx,
                day_type=current_type,
                is_weekend=day_value.weekday() >= 5,
            )
        )
        if current_type != DayType.REST:
            current_type = _next_cycle_day(current_type)
    return intents


def _recompute_after_override(intents: list[DayIntent], start_index: int, next_cycle_day: DayType) -> None:
    current_type = next_cycle_day
    for idx in range(start_index, len(intents)):
        intents[idx].day_type = current_type
        intents[idx].hard_subtype = None
        intents[idx].planned_rest = False
        intents[idx].explanation_tags = ()
        if current_type != DayType.REST:
            current_type = _next_cycle_day(current_type)


def _apply_friday_exception(intents: list[DayIntent], state: UserPlanningState) -> str | None:
    for idx, intent in enumerate(intents):
        day_value = date.fromisoformat(intent.day_utc)
        if day_value.weekday() != 4 or intent.day_type != DayType.HARD:
            continue
        saturday_idx = idx + 1 if idx + 1 < len(intents) and date.fromisoformat(intents[idx + 1].day_utc).weekday() == 5 else None
        sunday_idx = idx + 2 if idx + 2 < len(intents) and date.fromisoformat(intents[idx + 2].day_utc).weekday() == 6 else None
        weekend_idx = saturday_idx if saturday_idx is not None else sunday_idx
        if weekend_idx is None:
            continue
        weekend_day = intents[weekend_idx].day_utc
        days_since_last_h2 = _days_since_last_h2(state, weekend_day)
        if state.mechanical_risk.prefer_low_impact or (days_since_last_h2 is not None and days_since_last_h2 < 8):
            continue
        if idx > 0 and date.fromisoformat(intents[idx - 1].day_utc).weekday() == 3:
            intents[idx - 1].day_type = DayType.HARD
            intents[idx - 1].hard_subtype = HardSubtype.H1
            intents[idx - 1].explanation_tags = ("friday_exception_preload_h1",)
        intents[idx].day_type = DayType.REST
        intents[idx].planned_rest = True
        intents[idx].hard_subtype = None
        intents[idx].explanation_tags = ("friday_exception_rest",)
        intents[weekend_idx].day_type = DayType.HARD
        intents[weekend_idx].hard_subtype = HardSubtype.H2
        intents[weekend_idx].explanation_tags = ("friday_exception_weekend_h2",)
        if weekend_idx + 1 < len(intents):
            _recompute_after_override(intents, weekend_idx + 1, DayType.EASY)
        return "friday_rest_to_preserve_weekend_long_run"
    return None


def _assign_hard_subtypes(intents: list[DayIntent], state: UserPlanningState) -> list[str]:
    reasons: list[str] = []
    last_subtype = _last_hard_subtype(state, state.target_day_utc)
    for intent in intents:
        if intent.day_type != DayType.HARD or intent.hard_subtype is not None:
            continue
        days_since_last_h2 = _days_since_last_h2(state, intent.day_utc)
        if intent.is_weekend and not state.mechanical_risk.prefer_low_impact and (days_since_last_h2 is None or days_since_last_h2 >= 8):
            if last_subtype != HardSubtype.H2:
                intent.hard_subtype = HardSubtype.H2
                reasons.append(f"{intent.day_utc}:weekend_h2_long_run")
                last_subtype = HardSubtype.H2
                continue
        intent.hard_subtype = HardSubtype.H1
        reasons.append(f"{intent.day_utc}:metabolic_h1")
        last_subtype = HardSubtype.H1
    return reasons


def _modality_bias_for_intent(intent: DayIntent, state: UserPlanningState) -> tuple[str | None, str | None]:
    constraint = _constraint_for_day(state, intent.day_utc)
    if constraint and constraint.preferred_modality:
        return constraint.preferred_modality, "schedule_constraint_preferred_modality"
    if intent.day_type == DayType.EASY and state.mechanical_risk.prefer_low_impact:
        return "elliptical", "mechanical_fragility_easy_day_bias"
    if intent.day_type == DayType.HARD and intent.hard_subtype == HardSubtype.H2:
        return "running", "long_run_running_bias"
    return None, None


def _enforce_constraints(intent: DayIntent, state: UserPlanningState) -> DayIntent:
    constraint = _constraint_for_day(state, intent.day_utc)
    if not constraint:
        return intent
    if constraint.blocked:
        return replace(intent, day_type=DayType.REST, planned_rest=True, hard_subtype=None)
    if constraint.allow_long_run is False and intent.hard_subtype == HardSubtype.H2:
        return replace(intent, hard_subtype=HardSubtype.H1)
    return intent


def plan_day(
    *,
    state: UserPlanningState,
    candidates: Iterable[SessionCandidate],
    seed: int | None = None,
    horizon_days: int = 9,
    previous_activity_text: str | None = None,
) -> PlanningDecision:
    rng = random.Random(seed)
    first_day_type, inferred_from, previous_day_type = infer_cycle_position(state)
    start_day = date.fromisoformat(state.target_day_utc)
    intents = _build_naive_horizon(start_day=start_day, first_day_type=first_day_type, horizon_days=horizon_days)
    weekend_adjustment = _apply_friday_exception(intents, state)
    hard_subtype_reasons = _assign_hard_subtypes(intents, state)

    modality_bias_reason = None
    for idx, intent in enumerate(intents):
        bias, bias_reason = _modality_bias_for_intent(intent, state)
        intent.modality_bias = bias
        if idx == 0:
            modality_bias_reason = bias_reason
        adjusted_intent = _enforce_constraints(intent, state)
        intent.day_type = adjusted_intent.day_type
        intent.hard_subtype = adjusted_intent.hard_subtype
        intent.planned_rest = adjusted_intent.planned_rest
        share, was_clamped = sample_day_tss_share(intent.day_type, rng, DEFAULT_SAMPLER_CONFIG)
        intent.sampled_tss_share = share
        intent.share_was_clamped = was_clamped
        intent.target_tss = compute_target_day_tss(state.weekly_baseline_tss, share)

    selected_intent = intents[0]
    selected_candidate, candidate_rejections = select_session_candidate(
        candidates=candidates,
        intent=selected_intent,
        state=state,
        previous_activity_text=previous_activity_text,
    )
    generated_workout: GeneratedWorkout = render_generated_workout(
        selected_candidate,
        target_tss=selected_intent.target_tss,
    )
    hard_reason = None
    if selected_intent.day_type == DayType.HARD:
        if selected_intent.hard_subtype == HardSubtype.H2:
            hard_reason = "weekend_h2_preserved_for_long_run"
        else:
            hard_reason = "h1_selected_for_metabolic_hard_day"

    explanation = PlanningExplanation(
        inferred_from=inferred_from,
        previous_day_type=previous_day_type.value if previous_day_type is not None else None,
        next_day_type=selected_intent.day_type.value,
        sampled_share=float(selected_intent.sampled_tss_share),
        sampled_tss=float(selected_intent.target_tss),
        weekend_adjustment=weekend_adjustment,
        hard_subtype_reason=hard_reason,
        modality_bias_reason=modality_bias_reason,
        reasons=tuple(hard_subtype_reasons),
        candidate_rejections=candidate_rejections,
    )
    return PlanningDecision(
        target_day_utc=state.target_day_utc,
        selected_intent=selected_intent,
        horizon=tuple(intents),
        selected_candidate=selected_candidate,
        generated_workout=generated_workout,
        explanation=explanation,
    )

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import date, timedelta
import random

from temperance.planning.day_type_sampler import (
    compute_target_day_tss,
    sample_day_tss_share,
)
from temperance.planning.methodologies import get_methodology
from temperance.planning.models import (
    CycleStep,
    DayIntent,
    DayType,
    GeneratedWorkout,
    HardSubtype,
    MethodologyConfig,
    PlanningDecision,
    PlanningExplanation,
    SessionCandidate,
    UserPlanningState,
)
from temperance.planning.session_selector import select_session_candidate
from temperance.planning.workout_formatter import render_generated_workout


def _constraint_for_day(state: UserPlanningState, day_utc: str):
    for constraint in state.schedule_constraints:
        if constraint.day_utc == day_utc:
            return constraint
    return None


def _find_matching_cycle_step(
    methodology: MethodologyConfig,
    *,
    day_type: DayType | None,
    hard_subtype: HardSubtype | None,
) -> int | None:
    if day_type is None:
        return None
    exact_matches = [
        idx
        for idx, step in enumerate(methodology.cycle_steps)
        if step.day_type == day_type and step.hard_subtype == hard_subtype
    ]
    if exact_matches:
        return exact_matches[0]
    loose_matches = [
        idx
        for idx, step in enumerate(methodology.cycle_steps)
        if step.day_type == day_type
    ]
    return loose_matches[0] if loose_matches else None


def infer_cycle_position(
    state: UserPlanningState,
    methodology: MethodologyConfig,
) -> tuple[int, str, CycleStep | None]:
    target_day = date.fromisoformat(state.target_day_utc)
    history = sorted(
        [
            item
            for item in (*state.recent_activities, *state.planned_activities)
            if item.stress_class is not None
            and date.fromisoformat(item.day_utc) < target_day
        ],
        key=lambda item: item.day_utc,
    )
    if not history:
        return 0, "default", None
    previous = history[-1]
    if previous.methodology_step_id:
        for idx, step in enumerate(methodology.cycle_steps):
            if step.step_id == previous.methodology_step_id:
                return (idx + 1) % len(methodology.cycle_steps), previous.source, step
    previous_index = _find_matching_cycle_step(
        methodology,
        day_type=previous.stress_class,
        hard_subtype=previous.hard_subtype,
    )
    if previous_index is None:
        return 0, previous.source, None
    return (
        (previous_index + 1) % len(methodology.cycle_steps),
        previous.source,
        methodology.cycle_steps[previous_index],
    )


def _build_naive_horizon(
    *,
    start_day: date,
    methodology: MethodologyConfig,
    first_step_index: int,
    horizon_days: int,
) -> list[DayIntent]:
    intents: list[DayIntent] = []
    current_step_index = first_step_index
    for sequence_index in range(horizon_days):
        day_value = start_day + timedelta(days=sequence_index)
        step = methodology.cycle_steps[current_step_index]
        intents.append(
            DayIntent(
                day_utc=day_value.isoformat(),
                sequence_index=sequence_index,
                methodology_id=methodology.methodology_id,
                cycle_step_id=step.step_id,
                cycle_step_index=current_step_index,
                day_type=step.day_type,
                hard_subtype=step.hard_subtype,
                is_weekend=day_value.weekday() >= 5,
            )
        )
        current_step_index = (current_step_index + 1) % len(methodology.cycle_steps)
    return intents


def _recompute_after_override(
    intents: list[DayIntent],
    *,
    methodology: MethodologyConfig,
    start_index: int,
    next_cycle_step_index: int,
) -> None:
    current_step_index = next_cycle_step_index
    for idx in range(start_index, len(intents)):
        step = methodology.cycle_steps[current_step_index]
        intents[idx].cycle_step_id = step.step_id
        intents[idx].cycle_step_index = current_step_index
        intents[idx].day_type = step.day_type
        intents[idx].hard_subtype = step.hard_subtype
        intents[idx].planned_rest = False
        intents[idx].explanation_tags = ()
        current_step_index = (current_step_index + 1) % len(methodology.cycle_steps)


def _days_since_last_h2(state: UserPlanningState, day_utc: str) -> int | None:
    current_day = date.fromisoformat(day_utc)
    history = sorted(
        [
            item
            for item in (*state.recent_activities, *state.planned_activities)
            if item.hard_subtype == HardSubtype.H2
            and date.fromisoformat(item.day_utc) < current_day
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
            if item.hard_subtype is not None
            and date.fromisoformat(item.day_utc) < current_day
        ],
        key=lambda item: item.day_utc,
    )
    return history[-1].hard_subtype if history else None


def _compute_target_long_run_minutes(
    state: UserPlanningState, methodology: MethodologyConfig
) -> tuple[float, str]:
    profile = methodology.stress_profile
    last_minutes = state.last_long_run_minutes
    if last_minutes is None:
        return max(profile.long_run_min_minutes, 100.0), "default_long_run_seed"
    target = float(last_minutes)
    if state.fatigue.recovery_alert or state.mechanical_risk.prefer_low_impact:
        if target > profile.long_run_min_minutes:
            target = max(profile.long_run_min_minutes, target - 5.0)
            return target, "long_run_held_or_reduced_due_to_fatigue"
        return target, "long_run_held_due_to_fatigue"
    if len(state.recent_long_runs) >= 2:
        previous = float(state.recent_long_runs[-2].duration_min)
        if target >= previous:
            target = min(target + 5.0, profile.long_run_max_minutes)
            return target, "long_run_progressed_from_recent_history"
    target = min(
        max(target, profile.long_run_min_minutes) + 5.0, profile.long_run_max_minutes
    )
    return target, "long_run_progressed_from_last_long_run"


def _apply_friday_exception(
    intents: list[DayIntent],
    *,
    methodology: MethodologyConfig,
    state: UserPlanningState,
) -> str | None:
    for idx, intent in enumerate(intents):
        day_value = date.fromisoformat(intent.day_utc)
        if day_value.weekday() != 4 or intent.day_type != DayType.HARD:
            continue
        saturday_idx = (
            idx + 1
            if idx + 1 < len(intents)
            and date.fromisoformat(intents[idx + 1].day_utc).weekday() == 5
            else None
        )
        sunday_idx = (
            idx + 2
            if idx + 2 < len(intents)
            and date.fromisoformat(intents[idx + 2].day_utc).weekday() == 6
            else None
        )
        weekend_idx = saturday_idx if saturday_idx is not None else sunday_idx
        if weekend_idx is None:
            continue
        weekend_day = intents[weekend_idx].day_utc
        days_since_last_h2 = _days_since_last_h2(state, weekend_day)
        if state.mechanical_risk.prefer_low_impact or (
            days_since_last_h2 is not None and days_since_last_h2 < 8
        ):
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
            _recompute_after_override(
                intents,
                methodology=methodology,
                start_index=weekend_idx + 1,
                next_cycle_step_index=(intents[weekend_idx].cycle_step_index + 1)
                % len(methodology.cycle_steps),
            )
        return "friday_rest_to_preserve_weekend_long_run"
    return None


def _assign_hard_subtypes(
    intents: list[DayIntent],
    *,
    methodology: MethodologyConfig,
    state: UserPlanningState,
) -> list[str]:
    reasons: list[str] = []
    last_subtype = _last_hard_subtype(state, state.target_day_utc)
    for intent in intents:
        if intent.day_type != DayType.HARD or intent.hard_subtype is not None:
            continue
        step = methodology.cycle_steps[intent.cycle_step_index]
        if step.hard_subtype is not None:
            intent.hard_subtype = step.hard_subtype
            reasons.append(
                f"{intent.day_utc}:{step.hard_subtype.value}_from_methodology_step"
            )
            last_subtype = step.hard_subtype
            continue
        days_since_last_h2 = _days_since_last_h2(state, intent.day_utc)
        if (
            intent.is_weekend
            and not state.mechanical_risk.prefer_low_impact
            and (days_since_last_h2 is None or days_since_last_h2 >= 8)
        ):
            if last_subtype != HardSubtype.H2:
                intent.hard_subtype = HardSubtype.H2
                reasons.append(f"{intent.day_utc}:weekend_h2_long_run")
                last_subtype = HardSubtype.H2
                continue
        intent.hard_subtype = HardSubtype.H1
        reasons.append(f"{intent.day_utc}:metabolic_h1")
        last_subtype = HardSubtype.H1
    return reasons


def _use_rtss_anchor(intent: DayIntent, state: UserPlanningState) -> bool:
    """
    Return True when this intent should be sized from weekly_baseline_rtss rather
    than weekly_baseline_tss.

    The rule is conservative by design: only apply the run-specific ceiling when
    the session is confirmed or very likely to be a run.  This prevents
    cross-training-heavy weeks from mechanically inflating run targets (the
    early-January / early-June failure mode).

    Confirmed running:
      - H2 (long run) is always running.
      - Any intent where the modality bias is already forced to "running".

    Likely running:
      - H1 or undecided sessions when the athlete's recent 14-day mix is ≥ 50%
        running.  At that point undecided hard sessions are more likely to be
        runs than cross-training, so we size them conservatively.

    Confirmed cross-training:
      - Elliptical bias (set by mechanical fragility or schedule constraint)
        → keep TSS anchor so x-train load is not artificially squeezed.
    """
    if intent.day_type == DayType.REST or intent.planned_rest:
        return False
    if intent.modality_bias == "elliptical":
        return False
    if intent.hard_subtype == HardSubtype.H2:
        return True
    if intent.modality_bias == "running":
        return True
    # For undecided sessions: apply the run ceiling when the athlete is
    # predominantly a runner — this is exactly the high-risk scenario.
    return state.modality_mix_running >= 0.5


def _modality_bias_for_intent(
    intent: DayIntent, state: UserPlanningState
) -> tuple[str | None, str | None]:
    constraint = _constraint_for_day(state, intent.day_utc)
    if constraint and constraint.preferred_modality:
        return constraint.preferred_modality, "schedule_constraint_preferred_modality"
    if (
        intent.day_type in (DayType.EASY, DayType.MODERATE)
        and state.support_modality_preference in {"elliptical", "bike"}
    ):
        return state.support_modality_preference, "athlete_support_modality_preference"
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
        return replace(
            intent, day_type=DayType.REST, planned_rest=True, hard_subtype=None
        )
    if constraint.allow_long_run is False and intent.hard_subtype == HardSubtype.H2:
        return replace(intent, hard_subtype=HardSubtype.H1)
    return intent


def _has_48h_hard_gap(idx: int, hard_indices: list[int]) -> bool:
    return all(abs(idx - hard_idx) >= 2 for hard_idx in hard_indices)


def _respects_weekly_hard_cap(
    idx: int, hard_indices: list[int], horizon_len: int, cap: int = 2
) -> bool:
    merged = sorted({*hard_indices, idx})
    if horizon_len < 7:
        return len(merged) <= cap
    for start in range(0, horizon_len - 6):
        end = start + 6
        in_window = sum(start <= item <= end for item in merged)
        if in_window > cap:
            return False
    return True


def _apply_workout_minimum_preferences(intents: list[DayIntent], state: UserPlanningState) -> None:
    target_quality_min = max(0, min(int(state.weekly_quality_workouts_min), 4))
    target_long_run_min = max(0, min(int(state.weekly_long_run_min), 1))
    hard_cap = max(2, target_quality_min)
    if target_quality_min <= 0 and target_long_run_min <= 0:
        return
    hard_indices = [idx for idx, item in enumerate(intents) if item.day_type == DayType.HARD]
    quality_indices = list(hard_indices)
    long_run_indices = [
        idx
        for idx, item in enumerate(intents)
        if item.day_type == DayType.HARD and item.hard_subtype == HardSubtype.H2
    ]

    if len(long_run_indices) < target_long_run_min:
        weekend_candidates = [
            idx
            for idx, item in enumerate(intents)
            if item.is_weekend and item.day_type in (DayType.EASY, DayType.MODERATE, DayType.HARD)
            and not item.planned_rest
        ]
        for idx in weekend_candidates:
            if len(long_run_indices) >= target_long_run_min:
                break
            if intents[idx].day_type == DayType.HARD:
                intents[idx].hard_subtype = HardSubtype.H2
                intents[idx].explanation_tags = tuple(
                    [*intents[idx].explanation_tags, "long_run_minimum_preference"]
                )
                long_run_indices.append(idx)
                continue
            hard_reference = [hard_idx for hard_idx in hard_indices if hard_idx != idx]
            if not _has_48h_hard_gap(idx, hard_reference):
                continue
            if not _respects_weekly_hard_cap(
                idx, hard_reference, len(intents), cap=hard_cap
            ):
                continue
            intents[idx].day_type = DayType.HARD
            intents[idx].hard_subtype = HardSubtype.H2
            intents[idx].explanation_tags = tuple(
                [*intents[idx].explanation_tags, "long_run_minimum_preference"]
            )
            if idx not in hard_indices:
                hard_indices.append(idx)
            quality_indices.append(idx)
            long_run_indices.append(idx)

    if len(quality_indices) >= target_quality_min:
        return

    preferred_days = tuple(
        int(day) for day in state.quality_day_preference_weekdays if 0 <= int(day) <= 6
    )
    weekday_priority: dict[int, int] = {}
    for idx, weekday in enumerate(preferred_days):
        weekday_priority[weekday] = idx
    fallback_order = [1, 3, 2, 4, 0, 5, 6]
    cursor = len(weekday_priority)
    for weekday in fallback_order:
        if weekday in weekday_priority:
            continue
        weekday_priority[weekday] = cursor
        cursor += 1
    candidates = [
        idx
        for idx, item in enumerate(intents)
        if item.day_type in (DayType.EASY, DayType.MODERATE)
        and not item.planned_rest
    ]
    candidates = sorted(
        candidates,
        key=lambda idx: (
            weekday_priority.get(date.fromisoformat(intents[idx].day_utc).weekday(), 7),
            idx,
        ),
    )
    for idx in candidates:
        if len(quality_indices) >= target_quality_min:
            break
        if not _has_48h_hard_gap(idx, hard_indices):
            continue
        if not _respects_weekly_hard_cap(idx, hard_indices, len(intents), cap=hard_cap):
            continue
        intents[idx].day_type = DayType.HARD
        intents[idx].hard_subtype = HardSubtype.H1
        intents[idx].explanation_tags = tuple(
            [*intents[idx].explanation_tags, "quality_workout_minimum_preference"]
        )
        hard_indices.append(idx)
        quality_indices.append(idx)

    if not state.prefer_doubles_on_quality_days:
        return
    for intent in intents:
        if intent.day_type != DayType.HARD or intent.planned_rest:
            continue
        weekday = date.fromisoformat(intent.day_utc).weekday()
        if preferred_days and weekday not in preferred_days:
            continue
        if "double_preferred_quality_day" not in intent.explanation_tags:
            intent.explanation_tags = tuple(
                [*intent.explanation_tags, "double_preferred_quality_day"]
            )


def preview_horizon(
    *,
    state: UserPlanningState,
    methodology_id: str | None = None,
    seed: int | None = None,
    horizon_days: int | None = None,
) -> tuple[tuple[DayIntent, ...], dict[str, str | None]]:
    methodology = get_methodology(methodology_id)
    rng = random.Random(seed)
    first_step_index, inferred_from, previous_step = infer_cycle_position(
        state, methodology
    )
    start_day = date.fromisoformat(state.target_day_utc)
    horizon_size = int(horizon_days or methodology.horizon_days_default)
    intents = _build_naive_horizon(
        start_day=start_day,
        methodology=methodology,
        first_step_index=first_step_index,
        horizon_days=horizon_size,
    )
    weekend_adjustment = _apply_friday_exception(
        intents, methodology=methodology, state=state
    )
    _assign_hard_subtypes(intents, methodology=methodology, state=state)
    _apply_workout_minimum_preferences(intents, state)
    long_run_target_minutes, long_run_reason = _compute_target_long_run_minutes(
        state, methodology
    )

    # Weekly rTSS target is anchored to the run-specific baseline, not the total
    # aerobic baseline.  This prevents cross-training fitness from inflating run
    # session sizes — the failure mode behind early-January / early-June injuries.
    # baseline_rtss already adapts from recent run load, so no extra multiplier is
    # needed: the baseline itself IS the progression signal.
    weekly_rtss_target = float(state.weekly_baseline_rtss)

    for intent in intents:
        bias, _ = _modality_bias_for_intent(intent, state)
        intent.modality_bias = bias
        adjusted_intent = _enforce_constraints(intent, state)
        intent.day_type = adjusted_intent.day_type
        intent.hard_subtype = adjusted_intent.hard_subtype
        intent.planned_rest = adjusted_intent.planned_rest
        share, was_clamped = sample_day_tss_share(
            intent.day_type, rng, methodology.sampler_config
        )
        intent.sampled_tss_share = share
        intent.share_was_clamped = was_clamped
        # Use the run-specific baseline for confirmed or likely running sessions so
        # that x-train load cannot justify oversized run targets.
        tss_anchor = (
            weekly_rtss_target
            if _use_rtss_anchor(intent, state)
            else state.weekly_baseline_tss
        )
        intent.target_tss = compute_target_day_tss(tss_anchor, share)
        if intent.day_type == DayType.EASY:
            # Keep easy days constrained unless baseline load is notably high.
            # Approximate easy-day TSS ceiling from duration at ~0.75 IF.
            easy_cap_min = max(60, int(state.easy_day_max_duration_min))
            easy_tss_cap = (easy_cap_min / 60.0) * (0.75 * 0.75) * 100.0
            if state.weekly_baseline_tss >= 620.0:
                easy_tss_cap *= 1.15
            if intent.target_tss > easy_tss_cap:
                intent.target_tss = float(easy_tss_cap)
                if "easy_day_duration_cap_applied" not in intent.explanation_tags:
                    intent.explanation_tags = tuple(
                        [*intent.explanation_tags, "easy_day_duration_cap_applied"]
                    )
        if intent.day_type == DayType.HARD and intent.hard_subtype == HardSubtype.H2:
            intent.target_duration_min = long_run_target_minutes
            intent.min_duration_min = methodology.stress_profile.long_run_min_minutes
            intent.max_duration_min = methodology.stress_profile.long_run_max_minutes
            intent.min_avg_if = methodology.stress_profile.long_run_min_avg_if
            intent.max_avg_if = methodology.stress_profile.long_run_max_avg_if
    return tuple(intents), {
        "inferred_from": inferred_from,
        "previous_step_id": previous_step.step_id
        if previous_step is not None
        else None,
        "previous_day_type": previous_step.day_type.value
        if previous_step is not None
        else None,
        "weekend_adjustment": weekend_adjustment,
        "long_run_progression_reason": long_run_reason,
        "weekly_rtss_target": weekly_rtss_target,
    }


def plan_day(
    *,
    state: UserPlanningState,
    candidates: Iterable[SessionCandidate],
    methodology_id: str | None = None,
    seed: int | None = None,
    horizon_days: int | None = None,
    previous_activity_text: str | None = None,
) -> PlanningDecision:
    methodology = get_methodology(methodology_id)
    intents, horizon_meta = preview_horizon(
        state=state,
        methodology_id=methodology.methodology_id,
        seed=seed,
        horizon_days=horizon_days,
    )
    selected_intent = intents[0]
    modality_bias_reason = _modality_bias_for_intent(selected_intent, state)[1]
    selected_candidate, candidate_rejections = select_session_candidate(
        candidates=candidates,
        intent=selected_intent,
        state=state,
        previous_activity_text=previous_activity_text,
        stress_profile=methodology.stress_profile,
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
        methodology_id=methodology.methodology_id,
        inferred_from=str(horizon_meta.get("inferred_from") or "default"),
        previous_day_type=str(horizon_meta.get("previous_day_type") or "") or None,
        next_day_type=selected_intent.day_type.value,
        cycle_step_id=selected_intent.cycle_step_id,
        sampled_share=float(selected_intent.sampled_tss_share),
        sampled_tss=float(selected_intent.target_tss),
        weekend_adjustment=str(horizon_meta.get("weekend_adjustment") or "") or None,
        hard_subtype_reason=hard_reason,
        modality_bias_reason=modality_bias_reason,
        long_run_progression_reason=str(
            horizon_meta.get("long_run_progression_reason") or ""
        )
        or None,
        reasons=tuple(
            intent.explanation_tags[0] for intent in intents if intent.explanation_tags
        ),
        candidate_rejections=candidate_rejections,
    )
    return PlanningDecision(
        target_day_utc=state.target_day_utc,
        methodology_id=methodology.methodology_id,
        selected_intent=selected_intent,
        horizon=intents,
        selected_candidate=selected_candidate,
        generated_workout=generated_workout,
        explanation=explanation,
    )

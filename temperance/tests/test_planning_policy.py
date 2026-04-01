from temperance.planning import (
    CycleStep,
    DayType,
    MethodologyConfig,
    build_session_candidates,
    build_user_planning_state,
    get_default_methodology,
    get_methodology,
    plan_day,
    register_methodology,
)
from temperance.planning.day_type_sampler import DEFAULT_SAMPLER_CONFIG


def _candidates():
    return build_session_candidates(
        [
            {
                "activity_text": "60' run @ 4:40/km",
                "bucket": "easy",
                "estimated_tss": 56.0,
                "avg_if": 0.68,
                "max_if": 0.70,
                "total_minutes": 60.0,
                "modality": "running",
                "source": "planned",
            },
            {
                "activity_text": "75' elliptical @ 72%",
                "bucket": "steady",
                "estimated_tss": 77.0,
                "avg_if": 0.72,
                "max_if": 0.75,
                "total_minutes": 75.0,
                "modality": "elliptical",
                "source": "planned",
            },
            {
                "activity_text": "15' run @ 4:55/km + 4x8' @ 4:10/km",
                "bucket": "tempo",
                "estimated_tss": 98.0,
                "avg_if": 0.86,
                "max_if": 0.92,
                "total_minutes": 70.0,
                "modality": "running",
                "source": "planned",
            },
            {
                "activity_text": "120' run @ 4:55/km",
                "bucket": "long",
                "estimated_tss": 108.0,
                "avg_if": 0.79,
                "max_if": 0.82,
                "total_minutes": 120.0,
                "modality": "running",
                "source": "planned",
            },
        ],
        weekly_baseline_tss=554.0,
    )


def test_default_methodology_resolves_to_current_three_day_cycle() -> None:
    methodology = get_default_methodology()

    assert methodology.methodology_id == "rolling_3_day_v1"
    assert [step.day_type.value for step in methodology.cycle_steps] == ["easy", "moderate", "hard"]


def test_registry_can_register_future_methodology_without_changing_policy() -> None:
    register_methodology(
        MethodologyConfig(
            methodology_id="alternate_cycle_test",
            label="Alt Test",
            cycle_steps=(
                CycleStep(step_id="easy_a", day_type=DayType.EASY),
                CycleStep(step_id="hard_a", day_type=DayType.HARD),
                CycleStep(step_id="easy_b", day_type=DayType.EASY),
                CycleStep(step_id="moderate_b", day_type=DayType.MODERATE),
            ),
            horizon_days_default=8,
            sampler_config=DEFAULT_SAMPLER_CONFIG,
        )
    )

    methodology = get_methodology("alternate_cycle_test")

    assert [step.step_id for step in methodology.cycle_steps] == ["easy_a", "hard_a", "easy_b", "moderate_b"]


def test_policy_builds_horizon_from_registry_cycle_steps() -> None:
    state = build_user_planning_state(
        target_day_utc="2026-03-30",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {"day_utc": "2026-03-28", "tss": 55.0, "duration_s": 3600.0, "modality": "running", "avg_if": 0.68, "max_if": 0.70},
            {"day_utc": "2026-03-29", "tss": 78.0, "duration_s": 4500.0, "modality": "elliptical", "avg_if": 0.72, "max_if": 0.75},
        ],
        planned_activity_rows=[],
    )

    decision = plan_day(state=state, candidates=_candidates(), methodology_id="rolling_3_day_v1", seed=7)

    assert len(decision.horizon) == 9
    assert decision.methodology_id == "rolling_3_day_v1"
    assert decision.selected_intent.day_type.value == "hard"
    assert [intent.cycle_step_id for intent in decision.horizon[:4]] == ["hard", "easy", "moderate", "hard"]


def test_policy_applies_friday_rest_exception_and_preserves_weekend_long_run() -> None:
    state = build_user_planning_state(
        target_day_utc="2026-04-03",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {"day_utc": "2026-04-02", "tss": 78.0, "duration_s": 4200.0, "modality": "elliptical", "avg_if": 0.72, "max_if": 0.75},
        ],
        planned_activity_rows=[],
    )

    decision = plan_day(state=state, candidates=_candidates(), methodology_id="rolling_3_day_v1", seed=11)

    assert decision.generated_workout.activity_text == "Rest"
    assert decision.selected_intent.day_type.value == "rest"
    assert decision.explanation.weekend_adjustment == "friday_rest_to_preserve_weekend_long_run"
    assert decision.horizon[1].day_type.value == "hard"
    assert decision.horizon[1].hard_subtype is not None
    assert decision.horizon[1].hard_subtype.value == "h2"


def test_policy_long_run_progresses_from_recent_history_in_small_step() -> None:
    state = build_user_planning_state(
        target_day_utc="2026-04-05",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {"day_utc": "2026-03-21", "tss": 96.0, "duration_s": 6000.0, "modality": "running", "avg_if": 0.78, "max_if": 0.81},
            {"day_utc": "2026-03-29", "tss": 104.0, "duration_s": 6600.0, "modality": "running", "avg_if": 0.79, "max_if": 0.82},
            {"day_utc": "2026-04-04", "tss": 58.0, "duration_s": 3600.0, "modality": "running", "avg_if": 0.68, "max_if": 0.70},
        ],
        planned_activity_rows=[],
    )

    decision = plan_day(state=state, candidates=_candidates(), methodology_id="rolling_3_day_v1", seed=3)

    assert decision.selected_intent.day_type.value == "moderate"
    future_h2 = next(intent for intent in decision.horizon if intent.hard_subtype is not None and intent.hard_subtype.value == "h2")
    assert future_h2.target_duration_min == 115.0
    assert decision.explanation.long_run_progression_reason is not None


def test_policy_avoids_close_h2_when_recent_mechanical_hard_exists() -> None:
    state = build_user_planning_state(
        target_day_utc="2026-04-05",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {"day_utc": "2026-04-04", "tss": 108.0, "duration_s": 7200.0, "modality": "running", "avg_if": 0.79, "max_if": 0.82},
            {"day_utc": "2026-04-03", "tss": 10.0, "duration_s": 0.0, "modality": "running", "avg_if": 0.0, "max_if": 0.0},
        ],
        planned_activity_rows=[],
    )

    decision = plan_day(state=state, candidates=_candidates(), methodology_id="rolling_3_day_v1", seed=3)

    assert decision.selected_intent.day_type.value == "easy"
    weekend_hard_days = [intent for intent in decision.horizon if intent.day_type.value == "hard" and intent.is_weekend]
    assert all(intent.hard_subtype is None or intent.hard_subtype.value != "h2" for intent in weekend_hard_days[:1])

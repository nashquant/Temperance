from temperance.planning import build_session_candidates, build_user_planning_state, plan_day


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
                "estimated_tss": 101.0,
                "avg_if": 0.80,
                "max_if": 0.82,
                "total_minutes": 120.0,
                "modality": "running",
                "source": "planned",
            },
        ]
    )


def test_policy_builds_nine_day_horizon_from_recent_history() -> None:
    state = build_user_planning_state(
        target_day_utc="2026-03-30",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {"day_utc": "2026-03-28", "tss": 55.0, "duration_s": 3600.0, "modality": "running"},
            {"day_utc": "2026-03-29", "tss": 78.0, "duration_s": 4500.0, "modality": "elliptical"},
        ],
        planned_activity_rows=[],
    )

    decision = plan_day(state=state, candidates=_candidates(), seed=7)

    assert len(decision.horizon) == 9
    assert decision.selected_intent.day_type.value == "hard"
    assert [intent.day_type.value for intent in decision.horizon[:4]] == ["hard", "easy", "moderate", "hard"]


def test_policy_applies_friday_rest_exception_and_preserves_weekend_long_run() -> None:
    state = build_user_planning_state(
        target_day_utc="2026-04-03",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {"day_utc": "2026-04-02", "tss": 78.0, "duration_s": 4200.0, "modality": "elliptical"},
        ],
        planned_activity_rows=[],
    )

    decision = plan_day(state=state, candidates=_candidates(), seed=11)

    assert decision.generated_workout.activity_text == "Rest"
    assert decision.selected_intent.day_type.value == "rest"
    assert decision.explanation.weekend_adjustment == "friday_rest_to_preserve_weekend_long_run"
    assert decision.horizon[1].day_type.value == "hard"
    assert decision.horizon[1].hard_subtype is not None
    assert decision.horizon[1].hard_subtype.value == "h2"


def test_policy_has_no_routine_rest_days_without_exception() -> None:
    state = build_user_planning_state(
        target_day_utc="2026-03-30",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[],
        planned_activity_rows=[],
    )

    decision = plan_day(state=state, candidates=_candidates(), seed=5)

    assert all(intent.day_type.value != "rest" for intent in decision.horizon)


def test_policy_avoids_close_h2_when_recent_mechanical_hard_exists() -> None:
    state = build_user_planning_state(
        target_day_utc="2026-04-05",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {"day_utc": "2026-04-04", "tss": 101.0, "duration_s": 7200.0, "modality": "running"},
            {"day_utc": "2026-04-03", "tss": 10.0, "duration_s": 0.0, "modality": "running"},
        ],
        planned_activity_rows=[],
    )

    decision = plan_day(state=state, candidates=_candidates(), seed=3)

    assert decision.selected_intent.day_type.value == "easy"
    weekend_hard_days = [intent for intent in decision.horizon if intent.day_type.value == "hard" and intent.is_weekend]
    assert all(intent.hard_subtype is None or intent.hard_subtype.value != "h2" for intent in weekend_hard_days[:1])

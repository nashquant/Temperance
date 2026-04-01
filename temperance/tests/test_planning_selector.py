from temperance.planning import classify_session_stress
from temperance.planning.models import DayIntent, DayType, HardSubtype, UserPlanningState
from temperance.planning.session_selector import build_session_candidates, select_session_candidate
from temperance.planning.state_builder import build_user_planning_state


def _base_state(*, prefer_low_impact: bool = False) -> UserPlanningState:
    return build_user_planning_state(
        target_day_utc="2026-04-01",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {
                "day_utc": "2026-03-31",
                "tss": 58.0,
                "duration_s": 3600.0,
                "modality": "running",
                "avg_if": 0.68,
                "max_if": 0.70,
                "running_share": 1.0,
                "elliptical_share": 0.0,
            }
        ],
        planned_activity_rows=[],
        fatigue_payload={"recovery_alert": prefer_low_impact, "injury_risk": 120.0 if prefer_low_impact else 0.0},
        injury_windows=[{"label": "shin", "start": "2026-03-20", "end": "2026-04-10"}] if prefer_low_impact else [],
    )


def _intent(day_type: DayType, **kwargs) -> DayIntent:
    return DayIntent(
        day_utc="2026-04-01",
        sequence_index=0,
        methodology_id="rolling_3_day_v1",
        cycle_step_id=day_type.value,
        cycle_step_index=0,
        day_type=day_type,
        target_tss=float(kwargs.pop("target_tss", 77.0)),
        **kwargs,
    )


def test_high_if_low_tss_session_is_not_easy_by_default() -> None:
    day_type, _, override_reason = classify_session_stress(
        estimated_tss=50.0,
        avg_if=0.90,
        max_if=0.93,
        total_minutes=50.0,
        modality="running",
        bucket="easy",
    )

    assert day_type == DayType.MODERATE
    assert override_reason == "stress_class_too_low_for_if"


def test_moderate_day_excludes_intensity_drift_by_default() -> None:
    candidates = build_session_candidates(
        [
            {
                "activity_text": "10km @ 4:15/km + 5km @ 3:55/km",
                "bucket": "tempo",
                "estimated_tss": 80.0,
                "avg_if": 0.88,
                "max_if": 0.94,
                "total_minutes": 60.0,
                "modality": "running",
            },
            {
                "activity_text": "75' elliptical @ 72%",
                "bucket": "steady",
                "estimated_tss": 76.0,
                "avg_if": 0.72,
                "max_if": 0.75,
                "total_minutes": 75.0,
                "modality": "elliptical",
            },
        ]
    )
    selected, rejections = select_session_candidate(
        candidates=candidates,
        intent=_intent(DayType.MODERATE),
        state=_base_state(),
    )

    assert selected is not None
    assert selected.activity_text == "75' elliptical @ 72%"
    assert "moderate_day_excludes_intensity_drift" in rejections


def test_easy_day_fragility_bias_prefers_lower_impact_candidates() -> None:
    candidates = build_session_candidates(
        [
            {
                "activity_text": "60' run @ 4:40/km",
                "bucket": "easy",
                "estimated_tss": 55.0,
                "avg_if": 0.68,
                "max_if": 0.70,
                "total_minutes": 60.0,
                "modality": "running",
            },
            {
                "activity_text": "75' elliptical @ 72%",
                "bucket": "easy",
                "estimated_tss": 56.0,
                "avg_if": 0.70,
                "max_if": 0.72,
                "total_minutes": 75.0,
                "modality": "elliptical",
            },
        ]
    )
    selected, _ = select_session_candidate(
        candidates=candidates,
        intent=_intent(DayType.EASY, target_tss=55.4, modality_bias="elliptical"),
        state=_base_state(prefer_low_impact=True),
    )

    assert selected is not None
    assert selected.modality == "elliptical"


def test_long_run_candidate_must_fit_duration_and_intensity_bounds() -> None:
    candidates = build_session_candidates(
        [
            {
                "activity_text": "80' run @ 4:50/km",
                "bucket": "long",
                "estimated_tss": 88.0,
                "avg_if": 0.79,
                "max_if": 0.81,
                "total_minutes": 80.0,
                "modality": "running",
            },
            {
                "activity_text": "120' run @ 4:55/km",
                "bucket": "long",
                "estimated_tss": 108.0,
                "avg_if": 0.79,
                "max_if": 0.82,
                "total_minutes": 120.0,
                "modality": "running",
            },
            {
                "activity_text": "110' run @ 4:05/km",
                "bucket": "long",
                "estimated_tss": 120.0,
                "avg_if": 0.86,
                "max_if": 0.89,
                "total_minutes": 110.0,
                "modality": "running",
            },
        ]
    )
    selected, rejections = select_session_candidate(
        candidates=candidates,
        intent=_intent(
            DayType.HARD,
            hard_subtype=HardSubtype.H2,
            target_tss=105.0,
            target_duration_min=115.0,
            min_duration_min=90.0,
            max_duration_min=150.0,
            min_avg_if=0.68,
            max_avg_if=0.82,
            is_weekend=True,
        ),
        state=_base_state(),
    )

    assert selected is not None
    assert selected.activity_text == "120' run @ 4:55/km"
    assert "long_run_too_short" in rejections
    assert "long_run_too_intense" in rejections

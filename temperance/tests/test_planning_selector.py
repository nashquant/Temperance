from temperance.planning.models import DayIntent, DayType, UserPlanningState
from temperance.planning.session_selector import build_session_candidates, select_session_candidate
from temperance.planning.state_builder import build_user_planning_state


def _base_state(*, prefer_low_impact: bool = False) -> UserPlanningState:
    state = build_user_planning_state(
        target_day_utc="2026-04-01",
        weekly_baseline_tss=554.0,
        recent_activity_rows=[
            {
                "day_utc": "2026-03-31",
                "tss": 58.0,
                "duration_s": 3600.0,
                "modality": "running",
                "running_share": 1.0,
                "elliptical_share": 0.0,
            }
        ],
        planned_activity_rows=[],
        fatigue_payload={"recovery_alert": prefer_low_impact, "injury_risk": 120.0 if prefer_low_impact else 0.0},
        injury_windows=[{"label": "shin", "start": "2026-03-20", "end": "2026-04-10"}] if prefer_low_impact else [],
    )
    return state


def test_moderate_day_excludes_threshold_like_sessions_by_default() -> None:
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
        intent=DayIntent(day_utc="2026-04-01", sequence_index=0, day_type=DayType.MODERATE, target_tss=77.0),
        state=_base_state(),
    )

    assert selected is not None
    assert selected.activity_text == "75' elliptical @ 72%"
    assert "moderate_day_excludes_threshold_like" in rejections


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
        intent=DayIntent(
            day_utc="2026-04-01",
            sequence_index=0,
            day_type=DayType.EASY,
            target_tss=55.4,
            modality_bias="elliptical",
        ),
        state=_base_state(prefer_low_impact=True),
    )

    assert selected is not None
    assert selected.modality == "elliptical"

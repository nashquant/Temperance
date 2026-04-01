from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from temperance.planning.models import (
    FatigueSnapshot,
    HardSubtype,
    LongRunHistoryEntry,
    MechanicalRiskSnapshot,
    PlannedActivity,
    RecentActivity,
    ScheduleConstraint,
    StressProfile,
    UserPlanningState,
)
from temperance.planning.stress import classify_session_stress, is_long_run_candidate


def infer_hard_subtype(
    *,
    stress_class,
    modality: str,
    total_minutes: float,
    avg_if: float,
    max_if: float,
    workout_text: str = "",
    stress_profile: StressProfile | None = None,
) -> HardSubtype | None:
    if stress_class is None or str(getattr(stress_class, "value", stress_class)) != "hard":
        return None
    if is_long_run_candidate(
        modality=modality,
        total_minutes=total_minutes,
        avg_if=avg_if,
        max_if=max_if,
        stress_profile=stress_profile,
    ) or "long" in str(workout_text or "").strip().lower():
        return HardSubtype.H2
    return HardSubtype.H1


def _build_recent_activity(
    row: Mapping[str, object],
    weekly_baseline_tss: float,
    stress_profile: StressProfile,
) -> RecentActivity:
    modality = str(row.get("modality") or "unknown").strip().lower()
    avg_if = float(row.get("avg_if") or 0.0)
    max_if = float(row.get("max_if") or 0.0)
    total_minutes = float(row.get("duration_s") or 0.0) / 60.0
    stress_class, toughness_score, override_reason = classify_session_stress(
        estimated_tss=float(row.get("tss") or 0.0),
        avg_if=avg_if,
        max_if=max_if,
        total_minutes=total_minutes,
        modality=modality,
        bucket=str(row.get("bucket") or ""),
        weekly_baseline_tss=weekly_baseline_tss,
        stress_profile=stress_profile,
    )
    is_long_run = is_long_run_candidate(
        modality=modality,
        total_minutes=total_minutes,
        avg_if=avg_if,
        max_if=max_if,
        stress_profile=stress_profile,
    )
    return RecentActivity(
        day_utc=str(row.get("day_utc") or ""),
        tss=float(row.get("tss") or 0.0),
        duration_s=float(row.get("duration_s") or 0.0),
        modality=modality,
        avg_if=avg_if,
        max_if=max_if,
        toughness_score=toughness_score,
        is_long_run=is_long_run,
        long_run_duration_min=total_minutes if is_long_run else 0.0,
        running_share=float(row.get("running_share") or 0.0),
        elliptical_share=float(row.get("elliptical_share") or 0.0),
        stress_class=stress_class,
        hard_subtype=infer_hard_subtype(
            stress_class=stress_class,
            modality=modality,
            total_minutes=total_minutes,
            avg_if=avg_if,
            max_if=max_if,
            workout_text=str(row.get("workout_text") or ""),
            stress_profile=stress_profile,
        ),
        methodology_step_id=str(row.get("methodology_step_id") or "").strip() or None,
        source=str(row.get("source") or "actual"),
    )


def _build_planned_activity(
    row: Mapping[str, object],
    weekly_baseline_tss: float,
    stress_profile: StressProfile,
) -> PlannedActivity:
    modality = str(row.get("modality") or "unknown").strip().lower()
    avg_if = float(row.get("avg_if") or 0.0)
    max_if = float(row.get("max_if") or 0.0)
    total_minutes = float(row.get("duration_s") or 0.0) / 60.0
    stress_class, toughness_score, _ = classify_session_stress(
        estimated_tss=float(row.get("tss") or 0.0),
        avg_if=avg_if,
        max_if=max_if,
        total_minutes=total_minutes,
        modality=modality,
        bucket=str(row.get("bucket") or ""),
        weekly_baseline_tss=weekly_baseline_tss,
        stress_profile=stress_profile,
    )
    is_long_run = is_long_run_candidate(
        modality=modality,
        total_minutes=total_minutes,
        avg_if=avg_if,
        max_if=max_if,
        stress_profile=stress_profile,
    )
    return PlannedActivity(
        day_utc=str(row.get("day_utc") or ""),
        tss=float(row.get("tss") or 0.0),
        duration_s=float(row.get("duration_s") or 0.0),
        modality=modality,
        workout_text=str(row.get("workout_text") or ""),
        avg_if=avg_if,
        max_if=max_if,
        toughness_score=toughness_score,
        is_long_run=is_long_run,
        long_run_duration_min=total_minutes if is_long_run else 0.0,
        running_share=float(row.get("running_share") or 0.0),
        elliptical_share=float(row.get("elliptical_share") or 0.0),
        stress_class=stress_class,
        hard_subtype=infer_hard_subtype(
            stress_class=stress_class,
            modality=modality,
            total_minutes=total_minutes,
            avg_if=avg_if,
            max_if=max_if,
            workout_text=str(row.get("workout_text") or ""),
            stress_profile=stress_profile,
        ),
        methodology_step_id=str(row.get("methodology_step_id") or "").strip() or None,
        source=str(row.get("source") or "planned"),
    )


def _build_schedule_constraints(rows: Iterable[Mapping[str, object]] | None) -> tuple[ScheduleConstraint, ...]:
    out: list[ScheduleConstraint] = []
    for row in rows or ():
        out.append(
            ScheduleConstraint(
                day_utc=str(row.get("day_utc") or ""),
                allow_long_run=None if row.get("allow_long_run") is None else bool(row.get("allow_long_run")),
                preferred_modality=str(row.get("preferred_modality") or "").strip().lower() or None,
                blocked=bool(row.get("blocked")),
            )
        )
    return tuple(item for item in out if item.day_utc)


def _extract_long_run_history(
    recent_activities: tuple[RecentActivity, ...],
    planned_activities: tuple[PlannedActivity, ...],
) -> tuple[tuple[LongRunHistoryEntry, ...], float | None, str | None]:
    actuals = [
        LongRunHistoryEntry(
            day_utc=item.day_utc,
            source=item.source,
            duration_min=item.long_run_duration_min,
            avg_if=item.avg_if,
            tss=item.tss,
        )
        for item in recent_activities
        if item.is_long_run
    ]
    plans = [
        LongRunHistoryEntry(
            day_utc=item.day_utc,
            source=item.source,
            duration_min=item.long_run_duration_min,
            avg_if=item.avg_if,
            tss=item.tss,
        )
        for item in planned_activities
        if item.is_long_run
    ]
    history = tuple(sorted(actuals or plans, key=lambda item: item.day_utc))
    if not history:
        return (), None, None
    return history, float(history[-1].duration_min), str(history[-1].day_utc)


def build_user_planning_state(
    *,
    target_day_utc: str,
    weekly_baseline_tss: float,
    recent_activity_rows: Iterable[Mapping[str, object]],
    planned_activity_rows: Iterable[Mapping[str, object]],
    fatigue_payload: Mapping[str, object] | None = None,
    injury_windows: Iterable[Mapping[str, object]] | None = None,
    schedule_constraints: Iterable[Mapping[str, object]] | None = None,
    recent_load_ratio: float = 1.0,
    recent_load_7d: float = 0.0,
    recent_load_28d: float = 0.0,
    stress_profile: StressProfile | None = None,
) -> UserPlanningState:
    profile = stress_profile or StressProfile()
    recent_activities = tuple(
        _build_recent_activity(row, weekly_baseline_tss=weekly_baseline_tss, stress_profile=profile)
        for row in recent_activity_rows
        if str(row.get("day_utc") or "").strip()
    )
    planned_activities = tuple(
        _build_planned_activity(row, weekly_baseline_tss=weekly_baseline_tss, stress_profile=profile)
        for row in planned_activity_rows
        if str(row.get("day_utc") or "").strip()
    )

    fatigue_payload = fatigue_payload or {}
    fatigue = FatigueSnapshot(
        fitness=float(fatigue_payload.get("fitness") or 0.0),
        fatigue=float(fatigue_payload.get("fatigue") or 0.0),
        overreach=float(fatigue_payload.get("overreach") or 0.0),
        injury_risk=float(fatigue_payload.get("injury_risk") or 0.0),
        training_readiness=float(fatigue_payload.get("training_readiness") or 0.0),
        sleep_score=float(fatigue_payload.get("sleep_score") or 0.0),
        stress_avg=float(fatigue_payload.get("stress_avg") or 0.0),
        recovery_alert=bool(fatigue_payload.get("recovery_alert")),
    )

    recent_14d = [item for item in recent_activities if item.duration_s > 0.0][-14:]
    total_14d_duration = sum(item.duration_s for item in recent_14d)
    running_duration = sum(item.duration_s for item in recent_14d if item.modality == "running")
    elliptical_duration = sum(item.duration_s for item in recent_14d if item.modality == "elliptical")
    running_share_14d = (running_duration / total_14d_duration) if total_14d_duration > 0 else 0.0
    elliptical_share_14d = (elliptical_duration / total_14d_duration) if total_14d_duration > 0 else 0.0

    injury_labels: list[str] = []
    injury_window_active = False
    target_day = date.fromisoformat(target_day_utc)
    for row in injury_windows or ():
        start_value = str(row.get("start") or "").strip()
        end_value = str(row.get("end") or "").strip()
        if not start_value or not end_value:
            continue
        try:
            start_day = date.fromisoformat(start_value)
            end_day = date.fromisoformat(end_value)
        except ValueError:
            continue
        if start_day <= target_day <= end_day:
            injury_window_active = True
            label = str(row.get("label") or "injury").strip()
            if label:
                injury_labels.append(label)

    fragility_score = min(
        1.0,
        max(
            (1.0 if injury_window_active else 0.0) * 0.45
            + min(float(fatigue.injury_risk) / max(float(weekly_baseline_tss), 1.0), 1.0) * 0.25
            + min(float(fatigue.overreach) / max(float(weekly_baseline_tss), 1.0), 1.0) * 0.10
            + float(running_share_14d) * 0.20
            + (0.15 if fatigue.recovery_alert else 0.0),
            0.0,
        ),
    )
    mechanical_risk = MechanicalRiskSnapshot(
        injury_window_active=injury_window_active,
        injury_labels=tuple(injury_labels),
        running_share_14d=running_share_14d,
        elliptical_share_14d=elliptical_share_14d,
        mechanical_load_7d=float(recent_load_7d),
        fragility_score=fragility_score,
        prefer_low_impact=bool(injury_window_active or fragility_score >= 0.55 or fatigue.recovery_alert),
    )
    recent_long_runs, last_long_run_minutes, last_long_run_day_utc = _extract_long_run_history(
        recent_activities=recent_activities,
        planned_activities=planned_activities,
    )

    return UserPlanningState(
        target_day_utc=target_day_utc,
        weekly_baseline_tss=float(weekly_baseline_tss),
        recent_activities=recent_activities,
        planned_activities=planned_activities,
        recent_long_runs=recent_long_runs,
        last_long_run_minutes=last_long_run_minutes,
        last_long_run_day_utc=last_long_run_day_utc,
        fatigue=fatigue,
        mechanical_risk=mechanical_risk,
        schedule_constraints=_build_schedule_constraints(schedule_constraints),
        recent_load_ratio=float(recent_load_ratio),
        recent_load_7d=float(recent_load_7d),
        recent_load_28d=float(recent_load_28d),
        modality_mix_running=running_share_14d,
        modality_mix_elliptical=elliptical_share_14d,
    )

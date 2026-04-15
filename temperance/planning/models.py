from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DayType(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    REST = "rest"


class HardSubtype(str, Enum):
    H1 = "h1"
    H2 = "h2"


@dataclass(frozen=True)
class StressProfile:
    easy_max_score: float = 0.62
    moderate_max_score: float = 0.88
    moderate_max_avg_if: float = 0.82
    moderate_max_max_if: float = 0.86
    long_run_min_minutes: float = 90.0
    long_run_anchor_min_minutes: float = 100.0
    long_run_max_minutes: float = 150.0
    long_run_min_avg_if: float = 0.68
    long_run_max_avg_if: float = 0.82
    long_run_max_max_if: float = 0.86


@dataclass(frozen=True)
class CycleStep:
    step_id: str
    day_type: DayType
    hard_subtype: HardSubtype | None = None


@dataclass(frozen=True)
class MethodologyConfig:
    methodology_id: str
    label: str
    cycle_steps: tuple[CycleStep, ...]
    horizon_days_default: int
    sampler_config: Any
    stress_profile: StressProfile = field(default_factory=StressProfile)


@dataclass(frozen=True)
class RecentActivity:
    day_utc: str
    tss: float
    duration_s: float
    modality: str
    avg_if: float = 0.0
    max_if: float = 0.0
    toughness_score: float = 0.0
    is_long_run: bool = False
    long_run_duration_min: float = 0.0
    running_share: float = 0.0
    elliptical_share: float = 0.0
    stress_class: DayType | None = None
    hard_subtype: HardSubtype | None = None
    methodology_step_id: str | None = None
    source: str = "actual"


@dataclass(frozen=True)
class PlannedActivity:
    day_utc: str
    tss: float
    duration_s: float
    modality: str
    workout_text: str = ""
    avg_if: float = 0.0
    max_if: float = 0.0
    toughness_score: float = 0.0
    is_long_run: bool = False
    long_run_duration_min: float = 0.0
    running_share: float = 0.0
    elliptical_share: float = 0.0
    stress_class: DayType | None = None
    hard_subtype: HardSubtype | None = None
    methodology_step_id: str | None = None
    source: str = "planned"


@dataclass(frozen=True)
class LongRunHistoryEntry:
    day_utc: str
    source: str
    duration_min: float
    avg_if: float
    tss: float


@dataclass(frozen=True)
class FatigueSnapshot:
    fitness: float = 0.0
    fatigue: float = 0.0
    overreach: float = 0.0
    injury_risk: float = 0.0
    training_readiness: float = 0.0
    sleep_score: float = 0.0
    stress_avg: float = 0.0
    recovery_alert: bool = False


@dataclass(frozen=True)
class MechanicalRiskSnapshot:
    injury_window_active: bool = False
    injury_labels: tuple[str, ...] = ()
    running_share_14d: float = 0.0
    elliptical_share_14d: float = 0.0
    mechanical_load_7d: float = 0.0
    fragility_score: float = 0.0
    prefer_low_impact: bool = False


@dataclass(frozen=True)
class ScheduleConstraint:
    day_utc: str
    allow_long_run: bool | None = None
    preferred_modality: str | None = None
    blocked: bool = False


@dataclass(frozen=True)
class UserPlanningState:
    target_day_utc: str
    weekly_baseline_tss: float
    weekly_baseline_rtss: float = 0.0
    recent_activities: tuple[RecentActivity, ...] = ()
    planned_activities: tuple[PlannedActivity, ...] = ()
    recent_long_runs: tuple[LongRunHistoryEntry, ...] = ()
    last_long_run_minutes: float | None = None
    last_long_run_day_utc: str | None = None
    fatigue: FatigueSnapshot = field(default_factory=FatigueSnapshot)
    mechanical_risk: MechanicalRiskSnapshot = field(
        default_factory=MechanicalRiskSnapshot
    )
    schedule_constraints: tuple[ScheduleConstraint, ...] = ()
    recent_load_ratio: float = 1.0
    recent_load_7d: float = 0.0
    recent_load_28d: float = 0.0
    modality_mix_running: float = 0.0
    modality_mix_elliptical: float = 0.0


@dataclass
class DayIntent:
    day_utc: str
    sequence_index: int
    methodology_id: str
    cycle_step_id: str
    cycle_step_index: int
    day_type: DayType
    hard_subtype: HardSubtype | None = None
    is_weekend: bool = False
    modality_bias: str | None = None
    sampled_tss_share: float = 0.0
    target_tss: float = 0.0
    target_duration_min: float = 0.0
    min_duration_min: float = 0.0
    max_duration_min: float = 0.0
    min_avg_if: float = 0.0
    max_avg_if: float = 0.0
    share_was_clamped: bool = False
    planned_rest: bool = False
    explanation_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionCandidate:
    activity_text: str
    estimated_tss: float
    bucket: str
    modality: str
    total_minutes: float
    avg_if: float
    max_if: float
    priority: int = 0
    stress_class: DayType | None = None
    hard_subtype: HardSubtype | None = None
    threshold_like: bool = False
    mechanical_load: bool = False
    toughness_score: float = 0.0
    is_long_run: bool = False
    long_run_duration_min: float = 0.0
    stress_override_reason: str | None = None
    source: str = ""


@dataclass(frozen=True)
class GeneratedWorkout:
    activity_text: str
    modality: str
    target_tss: float
    estimated_tss: float
    source: str


@dataclass(frozen=True)
class PlanningExplanation:
    methodology_id: str
    inferred_from: str
    previous_day_type: str | None
    next_day_type: str
    cycle_step_id: str
    sampled_share: float
    sampled_tss: float
    weekend_adjustment: str | None = None
    hard_subtype_reason: str | None = None
    modality_bias_reason: str | None = None
    long_run_progression_reason: str | None = None
    reasons: tuple[str, ...] = ()
    candidate_rejections: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanningDecision:
    target_day_utc: str
    methodology_id: str
    selected_intent: DayIntent
    horizon: tuple[DayIntent, ...]
    selected_candidate: SessionCandidate | None
    generated_workout: GeneratedWorkout
    explanation: PlanningExplanation

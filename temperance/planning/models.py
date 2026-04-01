from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DayType(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    REST = "rest"


class HardSubtype(str, Enum):
    H1 = "h1"
    H2 = "h2"


@dataclass(frozen=True)
class RecentActivity:
    day_utc: str
    tss: float
    duration_s: float
    modality: str
    running_share: float = 0.0
    elliptical_share: float = 0.0
    stress_class: DayType | None = None
    hard_subtype: HardSubtype | None = None
    source: str = "actual"


@dataclass(frozen=True)
class PlannedActivity:
    day_utc: str
    tss: float
    duration_s: float
    modality: str
    workout_text: str = ""
    running_share: float = 0.0
    elliptical_share: float = 0.0
    stress_class: DayType | None = None
    hard_subtype: HardSubtype | None = None
    source: str = "planned"


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
    recent_activities: tuple[RecentActivity, ...] = ()
    planned_activities: tuple[PlannedActivity, ...] = ()
    fatigue: FatigueSnapshot = field(default_factory=FatigueSnapshot)
    mechanical_risk: MechanicalRiskSnapshot = field(default_factory=MechanicalRiskSnapshot)
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
    day_type: DayType
    hard_subtype: HardSubtype | None = None
    is_weekend: bool = False
    modality_bias: str | None = None
    sampled_tss_share: float = 0.0
    target_tss: float = 0.0
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
    inferred_from: str
    previous_day_type: str | None
    next_day_type: str
    sampled_share: float
    sampled_tss: float
    weekend_adjustment: str | None = None
    hard_subtype_reason: str | None = None
    modality_bias_reason: str | None = None
    reasons: tuple[str, ...] = ()
    candidate_rejections: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanningDecision:
    target_day_utc: str
    selected_intent: DayIntent
    horizon: tuple[DayIntent, ...]
    selected_candidate: SessionCandidate | None
    generated_workout: GeneratedWorkout
    explanation: PlanningExplanation

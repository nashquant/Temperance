from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntensityDistribution:
    easy_pct: float
    moderate_pct: float
    hard_pct: float


@dataclass(frozen=True)
class CorePrinciple:
    principle_id: str
    label: str
    rule: str


@dataclass(frozen=True)
class TrainingPhilosophy:
    philosophy_id: str
    label: str
    description: str
    distribution: IntensityDistribution
    preferred_hard_subtypes: tuple[str, ...]
    preferred_session_families: tuple[str, ...]


CORE_PRINCIPLES: tuple[CorePrinciple, ...] = (
    CorePrinciple(
        principle_id="hard_gap_min_48h",
        label="Hard Session Spacing",
        rule="No two Hard sessions within 48 hours of each other.",
    ),
    CorePrinciple(
        principle_id="weekly_hard_cap",
        label="Weekly Quality Cap",
        rule="Maximum 2 Hard sessions per 7-day rolling period.",
    ),
    CorePrinciple(
        principle_id="post_race_recovery",
        label="Post-Race Recovery",
        rule=(
            "After a marathon: minimum 14 easy days. "
            "After a half-marathon: minimum 7 easy days. "
            "After 10K or shorter: minimum 3 easy days. "
            "Easy days may include light cross-training."
        ),
    ),
    CorePrinciple(
        principle_id="acwr_ceiling",
        label="Load Ramp Ceiling",
        rule=(
            "When ACWR >= 1.5, all planned Hard sessions are downgraded to Moderate "
            "regardless of active philosophy. This principle cannot be overridden."
        ),
    ),
    CorePrinciple(
        principle_id="long_run_weekly_limit",
        label="Long Run Frequency",
        rule="At most one long run per 7-day period.",
    ),
    CorePrinciple(
        principle_id="recovery_week_frequency",
        label="Recovery Week",
        rule=(
            "After every 3-4 load weeks, schedule a recovery week at 60-70% of "
            "the preceding week's TSS. The exact timing adapts to accumulated "
            "overreach signal, but no more than 4 consecutive load weeks without "
            "a recovery week."
        ),
    ),
)


PHILOSOPHIES: dict[str, TrainingPhilosophy] = {
    "polarized": TrainingPhilosophy(
        philosophy_id="polarized",
        label="Polarized",
        description=(
            "80/20 model: the large majority of training time is easy aerobic work; "
            "hard sessions are genuinely hard (VO2max, strides). Moderate/threshold "
            "work is minimized. Based on Seiler's research on elite endurance athletes."
        ),
        distribution=IntensityDistribution(
            easy_pct=0.80, moderate_pct=0.05, hard_pct=0.15
        ),
        preferred_hard_subtypes=("h1",),
        preferred_session_families=(
            "vo2-max",
            "long-easy",
            "strides",
            "recovery-active",
        ),
    ),
    "pyramidal": TrainingPhilosophy(
        philosophy_id="pyramidal",
        label="Pyramidal",
        description=(
            "70/20/10 model: most volume is easy, a significant portion is moderate "
            "(LT1-adjacent), and a small portion is hard. Common pattern for runners "
            "building aerobic capacity before a race cycle."
        ),
        distribution=IntensityDistribution(
            easy_pct=0.70, moderate_pct=0.20, hard_pct=0.10
        ),
        preferred_hard_subtypes=("h2", "h1"),
        preferred_session_families=(
            "tempo",
            "lt1-cruise",
            "long-easy",
            "steady-state",
        ),
    ),
    "threshold": TrainingPhilosophy(
        philosophy_id="threshold",
        label="Threshold-Dominated",
        description=(
            "60/30/10 model: sustained LT1-LT2 work occupies most of the quality "
            "volume. Common in 10K to half-marathon focused cycles and double-threshold "
            "approaches. Requires good recovery capacity."
        ),
        distribution=IntensityDistribution(
            easy_pct=0.60, moderate_pct=0.30, hard_pct=0.10
        ),
        preferred_hard_subtypes=("h2",),
        preferred_session_families=(
            "lt1-cruise",
            "lt2-intervals",
            "tempo",
            "long-moderate",
        ),
    ),
}

_DEFAULT_PHILOSOPHY_ID = "polarized"


def get_philosophy(philosophy_id: str | None) -> TrainingPhilosophy:
    target = str(philosophy_id or _DEFAULT_PHILOSOPHY_ID).strip()
    if not target:
        target = _DEFAULT_PHILOSOPHY_ID
    if target not in PHILOSOPHIES:
        raise KeyError(f"Unknown philosophy_id: {target!r}")
    return PHILOSOPHIES[target]

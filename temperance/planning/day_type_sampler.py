from __future__ import annotations

from dataclasses import dataclass
import random

from temperance.planning.models import DayType


@dataclass(frozen=True)
class DayTypeDistribution:
    mean: float
    std: float
    min_share: float
    max_share: float


@dataclass(frozen=True)
class DayTypeSamplerConfig:
    easy: DayTypeDistribution = DayTypeDistribution(mean=0.10, std=0.01, min_share=0.08, max_share=0.12)
    moderate: DayTypeDistribution = DayTypeDistribution(mean=0.14, std=0.01, min_share=0.12, max_share=0.16)
    hard: DayTypeDistribution = DayTypeDistribution(mean=0.18, std=0.01, min_share=0.16, max_share=0.205)

    def distribution_for(self, day_type: DayType) -> DayTypeDistribution:
        if day_type == DayType.EASY:
            return self.easy
        if day_type == DayType.MODERATE:
            return self.moderate
        if day_type == DayType.HARD:
            return self.hard
        return DayTypeDistribution(mean=0.0, std=0.0, min_share=0.0, max_share=0.0)


DEFAULT_SAMPLER_CONFIG = DayTypeSamplerConfig()


def clamp_share(value: float, distribution: DayTypeDistribution) -> tuple[float, bool]:
    clamped = min(max(float(value), distribution.min_share), distribution.max_share)
    return clamped, clamped != float(value)


def sample_day_tss_share(
    day_type: DayType | str,
    rng: random.Random,
    config: DayTypeSamplerConfig = DEFAULT_SAMPLER_CONFIG,
) -> tuple[float, bool]:
    normalized = day_type if isinstance(day_type, DayType) else DayType(str(day_type).strip().lower())
    distribution = config.distribution_for(normalized)
    if normalized == DayType.REST:
        return 0.0, False
    sampled = rng.gauss(distribution.mean, distribution.std)
    return clamp_share(sampled, distribution)


def compute_target_day_tss(weekly_baseline_tss: float, sampled_share: float) -> float:
    return max(float(weekly_baseline_tss), 0.0) * max(float(sampled_share), 0.0)

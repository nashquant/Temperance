from __future__ import annotations

from temperance.planning.day_type_sampler import DEFAULT_SAMPLER_CONFIG
from temperance.planning.models import CycleStep, DayType, MethodologyConfig


class PlannerRegistry:
    def __init__(self) -> None:
        self._default_methodology_id = "rolling_3_day_v1"
        self._methodologies: dict[str, MethodologyConfig] = {}

    def register_methodology(self, config: MethodologyConfig) -> MethodologyConfig:
        self._methodologies[config.methodology_id] = config
        return config

    def get_methodology(self, methodology_id: str | None = None) -> MethodologyConfig:
        target = str(methodology_id or self._default_methodology_id).strip() or self._default_methodology_id
        if target not in self._methodologies:
            raise KeyError(f"Unknown methodology_id: {target}")
        return self._methodologies[target]

    def get_default_methodology(self) -> MethodologyConfig:
        return self.get_methodology(self._default_methodology_id)


REGISTRY = PlannerRegistry()


def _register_defaults() -> None:
    REGISTRY.register_methodology(
        MethodologyConfig(
            methodology_id="rolling_3_day_v1",
            label="Rolling 3-Day Cycle",
            cycle_steps=(
                CycleStep(step_id="easy", day_type=DayType.EASY),
                CycleStep(step_id="moderate", day_type=DayType.MODERATE),
                CycleStep(step_id="hard", day_type=DayType.HARD),
            ),
            horizon_days_default=9,
            sampler_config=DEFAULT_SAMPLER_CONFIG,
        )
    )


_register_defaults()


def register_methodology(config: MethodologyConfig) -> MethodologyConfig:
    return REGISTRY.register_methodology(config)


def get_methodology(methodology_id: str | None = None) -> MethodologyConfig:
    return REGISTRY.get_methodology(methodology_id)


def get_default_methodology() -> MethodologyConfig:
    return REGISTRY.get_default_methodology()

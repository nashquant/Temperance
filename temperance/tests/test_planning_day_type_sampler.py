import random

import pytest

from temperance.planning.day_type_sampler import compute_target_day_tss, sample_day_tss_share
from temperance.planning.models import DayType


def test_sample_day_tss_share_is_deterministic_with_fixed_seed() -> None:
    rng_a = random.Random(17)
    rng_b = random.Random(17)

    share_a, clamped_a = sample_day_tss_share(DayType.EASY, rng_a)
    share_b, clamped_b = sample_day_tss_share(DayType.EASY, rng_b)

    assert share_a == pytest.approx(share_b)
    assert clamped_a is clamped_b


def test_sample_day_tss_share_clamps_tail_draws() -> None:
    class FakeRandom:
        def __init__(self, value: float) -> None:
            self.value = value

        def gauss(self, mean: float, std: float) -> float:
            return self.value

    low_share, low_clamped = sample_day_tss_share(DayType.MODERATE, FakeRandom(0.01))  # type: ignore[arg-type]
    high_share, high_clamped = sample_day_tss_share(DayType.HARD, FakeRandom(0.50))  # type: ignore[arg-type]

    assert low_share == pytest.approx(0.12)
    assert low_clamped is True
    assert high_share == pytest.approx(0.205)
    assert high_clamped is True


def test_compute_target_day_tss_scales_from_weekly_baseline() -> None:
    assert compute_target_day_tss(554.0, 0.10) == pytest.approx(55.4)
    assert compute_target_day_tss(554.0, 0.14) == pytest.approx(77.56)
    assert compute_target_day_tss(554.0, 0.18) == pytest.approx(99.72)

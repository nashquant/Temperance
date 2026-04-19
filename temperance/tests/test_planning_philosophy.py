from temperance.planning.philosophy import (
    CORE_PRINCIPLES,
    PHILOSOPHIES,
    TrainingPhilosophy,
    get_philosophy,
)


def test_core_principles_are_non_empty() -> None:
    assert len(CORE_PRINCIPLES) >= 5


def test_all_principles_have_ids_and_descriptions() -> None:
    for principle in CORE_PRINCIPLES:
        assert principle.principle_id
        assert principle.label
        assert principle.rule


def test_philosophies_cover_expected_ids() -> None:
    ids = {philosophy.philosophy_id for philosophy in PHILOSOPHIES.values()}
    assert "polarized" in ids
    assert "pyramidal" in ids
    assert "threshold" in ids


def test_philosophy_distributions_sum_to_one() -> None:
    for philosophy in PHILOSOPHIES.values():
        total = (
            philosophy.distribution.easy_pct
            + philosophy.distribution.moderate_pct
            + philosophy.distribution.hard_pct
        )
        assert abs(total - 1.0) < 1e-9, f"{philosophy.philosophy_id}: sum={total}"


def test_get_philosophy_returns_correct() -> None:
    philosophy = get_philosophy("polarized")
    assert isinstance(philosophy, TrainingPhilosophy)
    assert philosophy.philosophy_id == "polarized"


def test_get_philosophy_unknown_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_philosophy("does_not_exist")


def test_get_philosophy_default_is_polarized() -> None:
    philosophy = get_philosophy(None)
    assert philosophy.philosophy_id == "polarized"

import json
from datetime import date, timedelta
from pathlib import Path

from temperance.db import get_planning_decisions, init_db, upsert_planning_decision


def _sample_payload(day: str = "2026-04-10") -> dict:
    return {
        "target_day_utc": day,
        "methodology_id": "m1",
        "selected_intent": {"day_type": "easy"},
        "explanation": {"reasons": ["low fatigue"]},
    }


def test_upsert_and_retrieve(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    target_day = date.today().isoformat()

    upsert_planning_decision(db_path, _sample_payload(target_day))
    rows = get_planning_decisions(db_path, days=30)

    assert len(rows) == 1
    assert rows[0]["target_day_utc"] == target_day
    assert rows[0]["planning"]["methodology_id"] == "m1"
    assert "id" in rows[0]
    assert "created_at" in rows[0]


def test_multiple_decisions_same_day(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    target_day = date.today().isoformat()

    upsert_planning_decision(db_path, _sample_payload(target_day))
    upsert_planning_decision(db_path, _sample_payload(target_day))
    rows = get_planning_decisions(db_path, days=30)

    assert len(rows) == 2


def test_cutoff_filters_old_decisions(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    old_day = (date.today() - timedelta(days=31)).isoformat()
    recent_day = date.today().isoformat()

    upsert_planning_decision(db_path, _sample_payload(old_day))
    upsert_planning_decision(db_path, _sample_payload(recent_day))
    rows = get_planning_decisions(db_path, days=30)

    assert len(rows) == 1
    assert rows[0]["target_day_utc"] == recent_day


def test_empty_db_returns_empty_list(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)

    rows = get_planning_decisions(db_path, days=30)
    assert rows == []

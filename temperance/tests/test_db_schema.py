import sqlite3
from pathlib import Path

from temperance.db import init_db


def _columns(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def test_init_db_applies_schema_and_migration_managed_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"

    init_db(db_path)

    assert {
        "activity_id",
        "start_time_utc",
        "sport_type",
        "is_invalid",
    }.issubset(_columns(db_path, "activities"))
    assert {
        "day_utc",
        "line_no",
        "workout_text",
        "parsed_json",
        "manual_done",
    }.issubset(_columns(db_path, "planned_activities"))
    assert {
        "day_utc",
        "line_no",
        "activity_text",
        "parsed_json",
        "source",
    }.issubset(_columns(db_path, "custom_activities"))
    assert {"id", "target_day_utc", "payload_json"}.issubset(
        _columns(db_path, "planning_decisions")
    )
    assert {"id", "activity_id_1", "activity_id_2", "merged_at"}.issubset(
        _columns(db_path, "activity_merges")
    )
    assert {"merge_id", "activity_id", "position"}.issubset(
        _columns(db_path, "activity_merge_members")
    )

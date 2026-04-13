import pytest
from pathlib import Path
from temperance.db import (
    get_conn,
    init_db,
    create_activity_merge,
    delete_activity_merge,
    get_activity_merge_by_id,
    get_active_merges,
    upsert_activities,
)

UTC_NOW_STR = "2026-04-10T07:00:00"


def _make_activity(activity_id: str, sport_type: str = "running") -> dict:
    return {
        "activity_id": activity_id,
        "start_time_utc": UTC_NOW_STR,
        "sport_type": sport_type,
        "source": "garmin_api",
        "raw": {},
    }


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    upsert_activities(
        path,
        [
            _make_activity("act-1", "running"),
            _make_activity("act-2", "running"),
            _make_activity("act-3", "treadmill_running"),
            _make_activity("act-4", "cycling"),
        ],
    )
    return path


def test_create_merge_returns_id(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, "act-1", "act-2")
    assert isinstance(merge_id, int)
    assert merge_id > 0


def test_get_merge_by_id(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, "act-1", "act-2")
    row = get_activity_merge_by_id(db_path, merge_id)
    assert row is not None
    assert row["activity_id_1"] == "act-1"
    assert row["activity_id_2"] == "act-2"


def test_delete_merge(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, "act-1", "act-2")
    assert delete_activity_merge(db_path, merge_id) is True
    assert get_activity_merge_by_id(db_path, merge_id) is None


def test_delete_nonexistent_merge_returns_false(db_path: Path) -> None:
    assert delete_activity_merge(db_path, 9999) is False


def test_get_active_merges(db_path: Path) -> None:
    create_activity_merge(db_path, "act-1", "act-2")
    merges = get_active_merges(db_path)
    assert len(merges) == 1
    assert merges[0]["activity_id_1"] == "act-1"


def test_duplicate_activity_in_merge_raises(db_path: Path) -> None:
    create_activity_merge(db_path, "act-1", "act-2")
    with pytest.raises(Exception):  # UNIQUE constraint violation
        create_activity_merge(db_path, "act-1", "act-3")


def test_activity_cant_appear_on_both_sides(db_path: Path) -> None:
    create_activity_merge(db_path, "act-1", "act-2")
    with pytest.raises(Exception):
        create_activity_merge(db_path, "act-3", "act-2")



def test_create_merge_stores_n_way_members(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, ["act-1", "act-2", "act-3"])

    row = get_activity_merge_by_id(db_path, merge_id)
    assert row is not None
    assert row["activity_id_1"] == "act-1"
    assert row["activity_id_2"] == "act-2"
    assert row["activity_ids"] == ["act-1", "act-2", "act-3"]

    with get_conn(db_path) as conn:
        members = conn.execute(
            """
            SELECT activity_id FROM activity_merge_members
            WHERE merge_id = ?
            ORDER BY position
            """,
            (merge_id,),
        ).fetchall()
    assert [member["activity_id"] for member in members] == ["act-1", "act-2", "act-3"]


def test_existing_pairwise_rows_backfill_members(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, "act-1", "act-2")
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM activity_merge_members WHERE merge_id = ?", (merge_id,))
        conn.commit()

    row = get_activity_merge_by_id(db_path, merge_id)

    assert row is not None
    assert row["activity_ids"] == ["act-1", "act-2"]


def test_n_way_member_cannot_be_merged_again(db_path: Path) -> None:
    create_activity_merge(db_path, ["act-1", "act-2", "act-3"])
    with pytest.raises(Exception):
        create_activity_merge(db_path, ["act-3", "act-4"])


def test_delete_n_way_merge_removes_member_rows(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, ["act-1", "act-2", "act-3"])

    assert delete_activity_merge(db_path, merge_id) is True

    with get_conn(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM activity_merge_members WHERE merge_id = ?",
            (merge_id,),
        ).fetchone()["n"]
    assert count == 0

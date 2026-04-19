# backend/tests/test_dashboard_cache.py
import tempfile
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

from temperance.db import get_conn, init_db


def _exec_sql(db_path: Path, sql: str, params: tuple[object, ...] = ()) -> None:
    with get_conn(db_path) as conn:
        conn.execute(sql, params)
        conn.commit()


def _exec_script(db_path: Path, sql: str) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(sql)
        conn.commit()


def test_dashboard_cache_key_changes_when_activities_change():
    """The cache key must differ when activity table content changes."""
    from backend.app.main import _dashboard_cache_key

    db = Path(tempfile.mktemp(suffix=".db"))
    with patch(
        "backend.app.main.get_dashboard_cache_components",
        side_effect=[
            {
                "activities": "v1",
                "planned_activities": "p1",
                "custom_activities": "c1",
                "settings": "s1",
                "wellness": "w1",
                "merges": "m1",
            },
            {
                "activities": "v2",
                "planned_activities": "p1",
                "custom_activities": "c1",
                "settings": "s1",
                "wellness": "w1",
                "merges": "m1",
            },
        ],
    ), patch("backend.app.main.datetime") as mock_dt:
        mock_dt.now.return_value.astimezone.return_value.date.return_value.isoformat.return_value = (
            "2026-04-12"
        )
        key1 = _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)
        key2 = _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)

    assert key1 != key2


def test_dashboard_cache_key_stable_for_same_inputs():
    """Identical inputs produce the same key every time."""
    from backend.app.main import _dashboard_cache_key

    db = Path(tempfile.mktemp(suffix=".db"))
    components = {
        "activities": "v1",
        "planned_activities": "p1",
        "custom_activities": "c1",
        "settings": "s1",
        "wellness": "w1",
        "merges": "m1",
    }
    with patch(
        "backend.app.main.get_dashboard_cache_components", return_value=components
    ), patch("backend.app.main.datetime") as mock_dt:
        mock_dt.now.return_value.astimezone.return_value.date.return_value.isoformat.return_value = (
            "2026-04-12"
        )
        key1 = _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)
        key2 = _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)

    assert key1 == key2


def test_dashboard_cache_key_changes_for_each_dashboard_component(tmp_path: Path):
    """Dashboard cache invalidates for every table family read by its payload builder."""
    from backend.app.main import _dashboard_cache_key

    db = tmp_path / "dashboard.db"
    init_db(db)

    def key() -> str:
        return _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)

    def assert_changes(mutator) -> None:
        before = key()
        mutator()
        after = key()
        assert after != before

    with patch("backend.app.main.datetime") as mock_dt:
        mock_dt.now.return_value.astimezone.return_value.date.return_value.isoformat.return_value = (
            "2026-04-12"
        )

        assert_changes(
            lambda: _exec_sql(
                db,
                """
                INSERT INTO activities(
                    activity_id, start_time_utc, sport_type, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "act-1",
                    "2026-04-10T07:00:00+00:00",
                    "running",
                    "test",
                    "t1",
                    "t1",
                ),
            )
        )
        assert_changes(
            lambda: _exec_sql(
                db,
                """
                INSERT INTO planned_activities(day_utc, line_no, workout_text, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("2026-04-11", 1, "45min run @ 70%", "t1", "t1"),
            )
        )
        assert_changes(
            lambda: _exec_sql(
                db,
                """
                INSERT INTO custom_activities(day_utc, line_no, activity_text, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("2026-04-11", 1, "30min bike @ 65%", "t1", "t1"),
            )
        )
        assert_changes(
            lambda: _exec_sql(
                db,
                "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
                ("user_timezone", "America/Sao_Paulo", "t1"),
            )
        )
        assert_changes(
            lambda: _exec_sql(
                db,
                "INSERT INTO wellness_daily(day_utc, resting_hr, updated_at) VALUES (?, ?, ?)",
                ("2026-04-11", 42.0, "t1"),
            )
        )
        _exec_sql(
            db,
            """
            INSERT INTO activities(
                activity_id, start_time_utc, sport_type, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "act-2",
                "2026-04-10T08:00:00+00:00",
                "running",
                "test",
                "t1",
                "t1",
            ),
        )
        assert_changes(
            lambda: _exec_script(
                db,
                """
                INSERT INTO activity_merges(id, activity_id_1, activity_id_2, merged_at)
                VALUES (1, 'act-1', 'act-2', 't1');
                INSERT INTO activity_merge_members(merge_id, activity_id, position)
                VALUES (1, 'act-1', 0), (1, 'act-2', 1);
                """,
            )
        )


def test_dashboard_cache_evicts_oldest_at_max_size():
    """Cache stays within _DASHBOARD_PAYLOAD_CACHE_MAXSIZE entries."""
    import backend.app.main as main_mod

    original_cache = main_mod._dashboard_payload_cache
    original_maxsize = main_mod._DASHBOARD_PAYLOAD_CACHE_MAXSIZE

    try:
        main_mod._DASHBOARD_PAYLOAD_CACHE_MAXSIZE = 3
        main_mod._dashboard_payload_cache = OrderedDict()

        lock = main_mod._dashboard_payload_cache_lock

        for i in range(5):
            key = f"key-{i}"
            with lock:
                main_mod._dashboard_payload_cache[key] = {"i": i}
                main_mod._dashboard_payload_cache.move_to_end(key)
                while (
                    len(main_mod._dashboard_payload_cache)
                    > main_mod._DASHBOARD_PAYLOAD_CACHE_MAXSIZE
                ):
                    main_mod._dashboard_payload_cache.popitem(last=False)

        assert len(main_mod._dashboard_payload_cache) == 3
        assert "key-0" not in main_mod._dashboard_payload_cache
        assert "key-1" not in main_mod._dashboard_payload_cache
        assert "key-4" in main_mod._dashboard_payload_cache
    finally:
        main_mod._dashboard_payload_cache = original_cache
        main_mod._DASHBOARD_PAYLOAD_CACHE_MAXSIZE = original_maxsize

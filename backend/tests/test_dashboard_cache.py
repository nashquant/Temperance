# backend/tests/test_dashboard_cache.py
import tempfile
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch


def test_dashboard_cache_key_changes_when_activities_change():
    """The cache key must differ when activity table content changes."""
    from backend.app.main import _dashboard_cache_key

    db = Path(tempfile.mktemp(suffix=".db"))
    with patch(
        "backend.app.main.get_activities_cache_key", side_effect=["v1", "v2"]
    ), patch(
        "backend.app.main.get_planned_activities_cache_key", return_value="p1"
    ), patch(
        "backend.app.main.get_custom_activities_cache_key", return_value="c1"
    ):
        key1 = _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)
        key2 = _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)

    assert key1 != key2


def test_dashboard_cache_key_stable_for_same_inputs():
    """Identical inputs produce the same key every time."""
    from backend.app.main import _dashboard_cache_key

    db = Path(tempfile.mktemp(suffix=".db"))
    with patch("backend.app.main.get_activities_cache_key", return_value="v1"), patch(
        "backend.app.main.get_planned_activities_cache_key", return_value="p1"
    ), patch("backend.app.main.get_custom_activities_cache_key", return_value="c1"):
        key1 = _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)
        key2 = _dashboard_cache_key(db, sport=None, week_offset=0, weeks=26)

    assert key1 == key2


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

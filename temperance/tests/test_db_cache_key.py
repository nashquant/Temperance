import tempfile
from pathlib import Path

from temperance.db import (
    get_activities_cache_key,
    get_custom_activities_cache_key,
    get_dashboard_cache_components,
    get_merges_cache_key,
    get_planned_activities_cache_key,
    get_settings_cache_key,
    get_wellness_cache_key,
    init_db,
)


def _make_db() -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = Path(f.name)
    f.close()
    init_db(path)
    return path


def test_cache_components_match_individual_calls():
    db = _make_db()
    components = get_dashboard_cache_components(db)

    assert components["activities"] == get_activities_cache_key(db)
    assert components["custom_activities"] == get_custom_activities_cache_key(db)
    assert components["planned_activities"] == get_planned_activities_cache_key(db)
    assert components["settings"] == get_settings_cache_key(db)
    assert components["wellness"] == get_wellness_cache_key(db)
    assert components["merges"] == get_merges_cache_key(db)

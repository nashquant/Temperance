# temperance/tests/test_db_runs_filter.py
import tempfile
from pathlib import Path

from temperance.db import init_db, get_runs_df, upsert_activities


def _make_tmp_db() -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = Path(tmp.name)
    init_db(p)
    return p


def _activity(activity_id: str, start_time_utc: str) -> dict:
    return {
        "activity_id": activity_id,
        "start_time_utc": start_time_utc,
        "sport_type": "running",
        "duration_s": 3600.0,
        "distance_m": 10000.0,
        "calories_total": 500.0,
        "avg_hr_bpm": 150.0,
        "max_hr_bpm": 170.0,
        "avg_pace_sec_per_km": 360.0,
        "trimp": None,
        "raw_json": None,
        "is_invalid": 0,
    }


def test_get_runs_df_start_day_filter_excludes_old_rows():
    db = _make_tmp_db()
    upsert_activities(
        db,
        [
            _activity("old-1", "2020-01-15T10:00:00Z"),
            _activity("old-2", "2021-06-01T08:00:00Z"),
            _activity("new-1", "2025-03-01T07:00:00Z"),
            _activity("new-2", "2025-04-10T07:00:00Z"),
        ],
    )

    all_df = get_runs_df(db)
    assert len(all_df) == 4, f"Expected 4 rows, got {len(all_df)}"

    filtered_df = get_runs_df(db, start_day_utc="2025-01-01")
    ids = set(filtered_df["activity_id"].tolist())
    assert ids == {"new-1", "new-2"}, f"Unexpected ids: {ids}"


def test_get_runs_df_no_filter_returns_all():
    db = _make_tmp_db()
    upsert_activities(
        db,
        [
            _activity("a1", "2019-05-01T07:00:00Z"),
            _activity("a2", "2025-04-01T07:00:00Z"),
        ],
    )
    df = get_runs_df(db, start_day_utc=None)
    assert len(df) == 2

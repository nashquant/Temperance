from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_runs_df, init_db, set_activity_invalid, upsert_activities


def test_set_activity_invalid_excludes_row_from_default_runs_df(tmp_path: Path) -> None:
    db_path = tmp_path / "activity_invalid.db"
    init_db(db_path)

    upsert_activities(
        db_path,
        [
            {
                "activity_id": "garmin-1",
                "start_time_utc": "2026-03-24T10:00:00+00:00",
                "sport_type": "running",
                "distance_m": 10000.0,
                "duration_s": 2700.0,
                "source": "garmin_api",
            }
        ],
    )

    assert len(get_runs_df(db_path)) == 1
    assert set_activity_invalid(db_path, "garmin-1", True) is True

    visible_df = get_runs_df(db_path)
    all_df = get_runs_df(db_path, include_invalid=True)

    assert visible_df.empty
    assert len(all_df) == 1
    assert int(all_df.iloc[0]["is_invalid"]) == 1

    assert set_activity_invalid(db_path, "garmin-1", False) is True
    restored_df = get_runs_df(db_path)
    assert len(restored_df) == 1
    assert int(restored_df.iloc[0]["is_invalid"]) == 0

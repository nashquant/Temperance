from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import init_db, upsert_activities, upsert_activity_details


def test_upsert_activity_details_skips_unchanged_updates(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)

    upsert_activities(
        db_path,
        [
            {
                "activity_id": "a1",
                "start_time_utc": "2026-01-01T00:00:00+00:00",
                "sport_type": "running",
                "distance_m": 1000.0,
                "duration_s": 300.0,
                "source": "garmin_api",
                "raw": {},
            }
        ],
    )

    first = upsert_activity_details(db_path, [{"activity_id": "a1", "details": {"k": 1}}])
    second = upsert_activity_details(db_path, [{"activity_id": "a1", "details": {"k": 1}}])
    third = upsert_activity_details(db_path, [{"activity_id": "a1", "details": {"k": 2}}])

    assert first == 1
    assert second == 0
    assert third == 1

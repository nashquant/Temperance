from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_conn, init_db, upsert_activities


def test_upsert_activity_maps_primary_garmin_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)

    upsert_activities(
        db_path,
        [
            {
                "activity_id": "a1",
                "start_time_utc": "2026-02-26T10:00:00+00:00",
                "sport_type": "running",
                "distance_m": 10000.0,
                "duration_s": 3000.0,
                "source": "garmin_api",
                "training_load_garmin": 64.5,
                "training_load_garmin_field_name": "activityTrainingLoad",
                "training_load_garmin_units": "load_points",
                "calories_active": 500.0,
                "calories_total": 560.0,
                "intensity_minutes_vigorous": 30.0,
                "intensity_minutes_moderate": 5.0,
                "raw": {"ok": True},
            }
        ],
    )

    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT training_load_garmin, training_load_garmin_field_name, training_load_garmin_units,
                   calories_active, calories_total, intensity_minutes_vigorous, intensity_minutes_moderate
            FROM activities WHERE activity_id = 'a1'
            """
        ).fetchone()

    assert row is not None
    assert float(row["training_load_garmin"]) == 64.5
    assert row["training_load_garmin_field_name"] == "activityTrainingLoad"
    assert row["training_load_garmin_units"] == "load_points"
    assert float(row["calories_active"]) == 500.0
    assert float(row["calories_total"]) == 560.0
    assert float(row["intensity_minutes_vigorous"]) == 30.0
    assert float(row["intensity_minutes_moderate"]) == 5.0

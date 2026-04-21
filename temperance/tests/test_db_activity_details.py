from pathlib import Path

from temperance.db import init_db, upsert_activities, upsert_activity_details


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


def test_upsert_activity_details_stores_compact_summary(tmp_path: Path) -> None:
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

    changed = upsert_activity_details(
        db_path,
        [
            {
                "activity_id": "a1",
                "details": {
                    "details": {
                        "activityId": "a1",
                        "metricsCount": 2000,
                        "metricDescriptors": [{"key": "directHeartRate"}],
                        "activityDetailMetrics": [{"metrics": [1, 2, 3]}],
                    },
                    "weather": {"temp": 20.0, "weatherStationDTO": {"name": "drop"}},
                },
            }
        ],
    )

    assert changed == 1

    from temperance.db import get_activity_detail_raw

    stored = get_activity_detail_raw(db_path, "a1")
    assert stored is not None
    assert stored["storage"] == "summary"
    assert stored["details"]["activityId"] == "a1"
    assert stored["details"]["metricsCount"] == 2000
    assert "metricDescriptors" not in stored["details"]
    assert "activityDetailMetrics" not in stored["details"]
    assert stored["weather"] == {"temp": 20.0}


def test_upsert_activity_details_can_store_full_payload_when_explicitly_requested(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TEMPERANCE_STORE_FULL_ACTIVITY_DETAILS", "1")
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

    upsert_activity_details(
        db_path,
        [
            {
                "activity_id": "a1",
                "details": {
                    "details": {
                        "activityId": "a1",
                        "activityDetailMetrics": [{"metrics": [1, 2, 3]}],
                    }
                },
            }
        ],
    )

    from temperance.db import get_activity_detail_raw

    stored = get_activity_detail_raw(db_path, "a1")
    assert stored is not None
    assert stored["details"]["activityDetailMetrics"] == [{"metrics": [1, 2, 3]}]

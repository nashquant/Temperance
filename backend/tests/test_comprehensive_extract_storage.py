from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.app import main as backend_main
from temperance.db import get_activity_detail_raw, get_conn, init_db


class FakeChunk:
    def __init__(self) -> None:
        self.activities = [
            {
                "activity_id": "a1",
                "start_time_utc": "2026-01-01T00:00:00+00:00",
                "sport_type": "running",
                "distance_m": 1000.0,
                "duration_s": 300.0,
                "source": "garmin_api",
                "raw": {},
            }
        ]
        self.activity_details = [
            {
                "activity_id": "a1",
                "details": {
                    "details": {
                        "activityId": "a1",
                        "metricsCount": 2000,
                        "activityDetailMetrics": [{"metrics": [1, 2, 3]}],
                        "metricDescriptors": [{"key": "directHeartRate"}],
                    }
                },
            }
        ]
        self.activity_records = [
            {
                "activity_id": "a1",
                "record_time_utc": "2026-01-01T00:00:01+00:00",
                "heart_rate": 140,
                "raw": {"grade_adjusted_speed": 3.2},
            }
        ]
        self.activity_splits = [
            {
                "activity_id": "a1",
                "split": {"lapDTOs": [{"duration": 300, "distance": 1000}]},
                "split_summaries": {"splitSummaries": [{"duration": 300}]},
            }
        ]


class FakeExtract:
    activities = []
    activity_details = []
    activity_records = []
    activity_splits = []
    sleep_daily = []
    wellness_daily = []
    errors = []


def test_background_comprehensive_extract_streams_processed_data_without_full_details(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "owner.db"
    init_db(db_path)
    calls: dict[str, object] = {}

    def fake_fetch_garmin_comprehensive(**kwargs):
        calls.update(kwargs)
        kwargs["activity_chunk_cb"](FakeChunk())
        return FakeExtract()

    monkeypatch.setattr(
        backend_main,
        "fetch_garmin_comprehensive",
        fake_fetch_garmin_comprehensive,
    )
    monkeypatch.setattr(backend_main, "_clear_garmin_rate_limit", lambda db_path: None)
    monkeypatch.setattr(backend_main, "log_sync", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        backend_main, "_extract_progress_append", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        backend_main, "_extract_progress_event", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        backend_main, "_extract_progress_finish", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        backend_main, "_extract_progress_fail", lambda *args, **kwargs: None
    )

    backend_main._run_comprehensive_extract_background(
        owner="admin",
        db_path=db_path,
        garmin_email="user@example.com",
        garmin_password="secret",
        start_day=date(2026, 1, 1),
        end_day=date(2026, 1, 2),
        include_details=True,
        include_wellness=False,
        target_activity_days=None,
        target_wellness_days=None,
    )

    assert calls["include_activity_details"] is True
    assert calls["include_splits"] is True

    with get_conn(db_path) as conn:
        activity_count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        record_count = conn.execute("SELECT COUNT(*) FROM activity_records").fetchone()[
            0
        ]
        split_count = conn.execute("SELECT COUNT(*) FROM activity_splits").fetchone()[0]

    assert activity_count == 1
    assert record_count == 1
    assert split_count == 1

    detail = get_activity_detail_raw(db_path, "a1")
    assert detail is not None
    assert detail["storage"] == "summary"
    assert "activityDetailMetrics" not in detail["details"]
    assert "metricDescriptors" not in detail["details"]

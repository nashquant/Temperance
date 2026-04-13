import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app
from temperance.db import create_activity_merge, init_db, upsert_activities, upsert_activity_splits

UTC_STR = "2026-04-10T07:00:00"


def _make_activity(activity_id: str, sport_type: str = "running") -> dict:
    return {
        "activity_id": activity_id,
        "start_time_utc": UTC_STR,
        "sport_type": sport_type,
        "source": "garmin_api",
        "raw": {},
    }


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    init_db(p)
    upsert_activities(
        p,
        [
            _make_activity("act-1", "running"),
            _make_activity("act-2", "running"),
            _make_activity("act-3", "treadmill_running"),
            _make_activity("act-4", "cycling"),
        ],
    )
    return p


def _call(tmp_db: Path, method: str, path: str, **kwargs):
    """Make a request with auth and db path fully patched for the duration of the call."""
    mock_ctx = MagicMock()
    mock_ctx.owner = "test"
    mock_ctx.is_admin = True
    with (
        patch("backend.app.main._db_path_for_owner", return_value=tmp_db),
        patch("backend.app.main._auth_context", return_value=mock_ctx),
        patch("backend.app.main._resolve_owner", return_value="test"),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        return getattr(client, method)(
            path, headers={"Authorization": "Bearer test"}, **kwargs
        )


def test_create_merge_compatible_activities(tmp_db: Path) -> None:
    resp = _call(
        tmp_db,
        "post",
        "/api/v1/activity-merges",
        json={"activity_id_1": "act-1", "activity_id_2": "act-2"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "merge_id" in body
    assert isinstance(body["merge_id"], int)


def test_create_merge_incompatible_types_returns_422(tmp_db: Path) -> None:
    resp = _call(
        tmp_db,
        "post",
        "/api/v1/activity-merges",
        json={"activity_id_1": "act-1", "activity_id_2": "act-4"},
    )
    assert resp.status_code == 422, resp.text


def test_create_merge_run_plus_treadmill_allowed(tmp_db: Path) -> None:
    resp = _call(
        tmp_db,
        "post",
        "/api/v1/activity-merges",
        json={"activity_id_1": "act-1", "activity_id_2": "act-3"},
    )
    assert resp.status_code == 200, resp.text


def test_delete_merge(tmp_db: Path) -> None:
    merge_id = create_activity_merge(tmp_db, "act-1", "act-2")
    resp = _call(tmp_db, "delete", f"/api/v1/activity-merges/{merge_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] is True


def test_delete_nonexistent_merge_returns_404(tmp_db: Path) -> None:
    resp = _call(tmp_db, "delete", "/api/v1/activity-merges/9999")
    assert resp.status_code == 404, resp.text



def test_create_merge_accepts_activity_ids_payload(tmp_db: Path) -> None:
    resp = _call(
        tmp_db,
        "post",
        "/api/v1/activity-merges",
        json={"activity_ids": ["act-1", "act-2", "act-3"]},
    )
    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json()["merge_id"], int)


def test_create_merge_duplicate_ids_returns_422(tmp_db: Path) -> None:
    resp = _call(
        tmp_db,
        "post",
        "/api/v1/activity-merges",
        json={"activity_ids": ["act-1", "act-1"]},
    )
    assert resp.status_code == 422, resp.text


def test_merged_activity_detail_orders_source_splits_chronologically(tmp_db: Path) -> None:
    upsert_activities(
        tmp_db,
        [
            {
                "activity_id": "act-5",
                "start_time_utc": "2026-04-10T08:00:00",
                "sport_type": "running",
                "source": "garmin_api",
                "distance_m": 1000,
                "duration_s": 300,
                "avg_hr": 150,
                "max_hr": 155,
                "avg_pace_s_per_km": 300,
                "training_load_garmin": 10,
                "hr_time_in_zone_2": 300,
                "raw": {},
            },
            {
                "activity_id": "act-6",
                "start_time_utc": "2026-04-10T07:00:00",
                "sport_type": "running",
                "source": "garmin_api",
                "distance_m": 1000,
                "duration_s": 300,
                "avg_hr": 145,
                "max_hr": 150,
                "avg_pace_s_per_km": 300,
                "training_load_garmin": 10,
                "hr_time_in_zone_2": 300,
                "raw": {},
            },
        ],
    )
    upsert_activity_splits(
        tmp_db,
        [
            {
                "activity_id": "act-5",
                "split": {"lapDTOs": [{"lapIndex": 1, "duration": 300, "distance": 1000, "averageHR": 150, "averageSpeed": 1000 / 300}]},
                "split_summaries": {},
                "lap_count": 1,
                "total_duration_s": 300,
                "total_distance_m": 1000,
            },
            {
                "activity_id": "act-6",
                "split": {"lapDTOs": [{"lapIndex": 1, "duration": 300, "distance": 1000, "averageHR": 145, "averageSpeed": 1000 / 300}]},
                "split_summaries": {},
                "lap_count": 1,
                "total_duration_s": 300,
                "total_distance_m": 1000,
            },
        ],
    )
    merge_id = create_activity_merge(tmp_db, ["act-5", "act-6"])

    resp = _call(tmp_db, "get", f"/api/v1/activities/merged-{merge_id}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["merged_activity_ids"] == ["act-6", "act-5"]
    assert [row["lap"] for row in body["split_rows"]] == [1, 2]
    assert all(row["if_pct"] > 0 for row in body["split_rows"])
    assert sum(row["seconds"] for row in body["zone_summary"]) == 600


def test_collapse_merged_cards_supports_n_way_chronological_sources() -> None:
    from backend.app.main import _collapse_merged_cards

    cards = [
        {"activity_id": "act-3", "sport": "Running", "start_time_utc": "2026-04-10T09:00:00", "start_time_hhmm": "09:00", "duration_label": "10min", "distance_label": "2 km", "hr_label": "150b", "pace_label": "5:00/km", "if_pct": 90, "tss": 10, "rtss": 11, "intensity": "orange"},
        {"activity_id": "act-1", "sport": "Running", "start_time_utc": "2026-04-10T07:00:00", "start_time_hhmm": "07:00", "duration_label": "20min", "distance_label": "4 km", "hr_label": "140b", "pace_label": "5:00/km", "if_pct": 80, "tss": 20, "rtss": 21, "intensity": "blue"},
        {"activity_id": "act-2", "sport": "Running", "start_time_utc": "2026-04-10T08:00:00", "start_time_hhmm": "08:00", "duration_label": "30min", "distance_label": "6 km", "hr_label": "145b", "pace_label": "5:00/km", "if_pct": 85, "tss": 30, "rtss": 31, "intensity": "red"},
    ]
    merge = {"id": 7, "activity_ids": ["act-3", "act-1", "act-2"]}

    collapsed = _collapse_merged_cards(cards, {activity_id: merge for activity_id in merge["activity_ids"]})

    assert len(collapsed) == 1
    assert collapsed[0]["activity_id"] == "merged-7"
    assert collapsed[0]["merged_activity_ids"] == ["act-1", "act-2", "act-3"]
    assert collapsed[0]["distance_label"] == "12 km"
    assert collapsed[0]["tss"] == 60
    assert collapsed[0]["rtss"] == 63

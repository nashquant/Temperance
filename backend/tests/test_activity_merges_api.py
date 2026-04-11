import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app
from temperance.db import create_activity_merge, init_db, upsert_activities

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

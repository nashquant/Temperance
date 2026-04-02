from pathlib import Path

from fastapi import HTTPException

from backend.app import main as backend_main
from temperance.db import get_conn, init_db


def test_garmin_auth_reset_endpoint_calls_reset_and_logs(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "owner.db"
    init_db(db_path)
    called = {"count": 0}

    monkeypatch.setattr(backend_main, "_auth_context", lambda authorization: {"user": "admin", "role": "admin"})
    monkeypatch.setattr(backend_main, "_resolve_owner", lambda ctx, owner: "admin")
    monkeypatch.setattr(backend_main, "_db_path_for_owner", lambda owner: db_path)
    monkeypatch.setattr(backend_main, "reset_garmin_auth", lambda: called.__setitem__("count", called["count"] + 1))

    payload = backend_main.data_extract_garmin_auth_reset()

    assert payload["success"] is True
    assert payload["message"] == "Garmin auth fully reset"
    assert payload["process_wide"] is True
    assert called["count"] == 1

    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT source, success, message FROM sync_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row is not None
    assert row["source"] == "garmin_auth_reset"
    assert int(row["success"]) == 1
    assert "Garmin auth fully reset via API." in row["message"]


def test_garmin_auth_reset_endpoint_requires_admin(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "_auth_context", lambda authorization: {"user": "viewer", "role": "viewer"})

    try:
        backend_main.data_extract_garmin_auth_reset()
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "Admin access required." in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException")

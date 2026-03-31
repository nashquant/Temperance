from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from backend.app import main as backend_main
from temperance.db import get_conn, init_db, save_setting


def test_auto_sync_gate_allows_owner_local_window(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "AUTO_SYNC_TEMPORARILY_DISABLED", False)
    db_path = tmp_path / "owner.db"
    init_db(db_path)
    save_setting(db_path, backend_main.SETTINGS_KEY_USER_TIMEZONE, "America/Sao_Paulo")

    gate = backend_main._auto_sync_gate(
        "admin",
        db_path,
        now_utc=datetime(2026, 3, 23, 11, 30, tzinfo=timezone.utc),
    )

    assert gate["allowed"] is True
    assert gate["reason"] == "ok"
    assert gate["timezone"] == "America/Sao_Paulo"


def test_auto_sync_gate_blocks_outside_owner_local_window(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "AUTO_SYNC_TEMPORARILY_DISABLED", False)
    db_path = tmp_path / "owner.db"
    init_db(db_path)
    save_setting(db_path, backend_main.SETTINGS_KEY_USER_TIMEZONE, "America/Sao_Paulo")

    gate = backend_main._auto_sync_gate(
        "admin",
        db_path,
        now_utc=datetime(2026, 3, 23, 14, 30, tzinfo=timezone.utc),
    )

    assert gate["allowed"] is False
    assert gate["reason"] == "outside_window"


def test_auto_sync_gate_enforces_30_minute_cooldown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "AUTO_SYNC_TEMPORARILY_DISABLED", False)
    db_path = tmp_path / "owner.db"
    init_db(db_path)
    save_setting(db_path, backend_main.SETTINGS_KEY_USER_TIMEZONE, "America/Sao_Paulo")

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sync_log(sync_time_utc, source, success, message)
            VALUES (?, ?, ?, ?)
            """,
            ("2026-03-23T11:15:00+00:00", "sync_garmin_auto_quick", 1, "ok"),
        )
        conn.commit()

    gate = backend_main._auto_sync_gate(
        "admin",
        db_path,
        now_utc=datetime(2026, 3, 23, 11, 30, tzinfo=timezone.utc),
    )

    assert gate["allowed"] is False
    assert gate["reason"] == "cooldown"
    assert gate["cooldown_remaining_seconds"] == 900


def test_auto_sync_gate_blocks_when_garmin_rate_limited(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "AUTO_SYNC_TEMPORARILY_DISABLED", False)
    db_path = tmp_path / "owner.db"
    init_db(db_path)
    save_setting(db_path, backend_main.SETTINGS_KEY_USER_TIMEZONE, "America/Sao_Paulo")
    save_setting(db_path, backend_main.SETTINGS_KEY_GARMIN_RATE_LIMIT_UNTIL, "2026-03-23T18:00:00+00:00")

    gate = backend_main._auto_sync_gate(
        "admin",
        db_path,
        now_utc=datetime(2026, 3, 23, 11, 30, tzinfo=timezone.utc),
    )

    assert gate["allowed"] is False
    assert gate["reason"] == "rate_limited"
    assert gate["rate_limited_until"] == "2026-03-23T18:00:00+00:00"
    assert gate["cooldown_remaining_seconds"] == 23400


def test_ensure_garmin_available_raises_429_when_rate_limited(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "AUTO_SYNC_TEMPORARILY_DISABLED", False)
    db_path = tmp_path / "owner.db"
    init_db(db_path)
    save_setting(db_path, backend_main.SETTINGS_KEY_GARMIN_RATE_LIMIT_UNTIL, "2026-03-23T18:00:00+00:00")

    try:
        backend_main._ensure_garmin_available(
            db_path,
            now_utc=datetime(2026, 3, 23, 11, 30, tzinfo=timezone.utc),
        )
    except HTTPException as exc:
        assert exc.status_code == 429
        assert "Retry after 2026-03-23T18:00:00+00:00" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException")

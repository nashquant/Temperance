from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "temperance"))

from db import get_conn, init_db, save_setting

BACKEND_MAIN_PATH = ROOT / "v2" / "backend" / "app" / "main.py"
BACKEND_MAIN_SPEC = importlib.util.spec_from_file_location("temperance_v2_backend_main", BACKEND_MAIN_PATH)
assert BACKEND_MAIN_SPEC is not None and BACKEND_MAIN_SPEC.loader is not None
backend_main = importlib.util.module_from_spec(BACKEND_MAIN_SPEC)
BACKEND_MAIN_SPEC.loader.exec_module(backend_main)


def test_auto_sync_gate_allows_owner_local_window(tmp_path: Path) -> None:
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


def test_auto_sync_gate_blocks_outside_owner_local_window(tmp_path: Path) -> None:
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


def test_auto_sync_gate_enforces_30_minute_cooldown(tmp_path: Path) -> None:
    db_path = tmp_path / "owner.db"
    init_db(db_path)
    save_setting(db_path, backend_main.SETTINGS_KEY_USER_TIMEZONE, "America/Sao_Paulo")

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sync_log(sync_time_utc, source, success, message)
            VALUES (?, ?, ?, ?)
            """,
            ("2026-03-23T11:15:00+00:00", "v2_sync_garmin_auto_quick", 1, "ok"),
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

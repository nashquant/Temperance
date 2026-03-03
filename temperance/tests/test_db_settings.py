from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_conn, get_setting, init_db, save_setting_if_changed


def test_save_setting_if_changed_only_updates_when_value_differs(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)

    assert save_setting_if_changed(db_path, "k1", "v1") is True
    with get_conn(db_path) as conn:
        first_updated = conn.execute("SELECT updated_at FROM settings WHERE key = ?", ("k1",)).fetchone()["updated_at"]

    assert save_setting_if_changed(db_path, "k1", "v1") is False
    with get_conn(db_path) as conn:
        second_updated = conn.execute("SELECT updated_at FROM settings WHERE key = ?", ("k1",)).fetchone()["updated_at"]

    assert first_updated == second_updated
    assert get_setting(db_path, "k1") == "v1"

    assert save_setting_if_changed(db_path, "k1", "v2") is True
    assert get_setting(db_path, "k1") == "v2"

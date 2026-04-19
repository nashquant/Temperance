from pathlib import Path

from backend.app import main as backend_main
from backend.app.owner_paths import user_slug


def test_user_slug_sanitizes_to_stable_filename() -> None:
    assert user_slug(" Runner One! ") == "Runner_One"
    assert user_slug("...") == "default"


def test_named_owner_uses_scoped_users_database(
    monkeypatch,
    tmp_path: Path,
) -> None:
    base_db = tmp_path / "temperance.db"
    monkeypatch.setattr(backend_main, "DB_PATH", base_db)

    owner_db = backend_main._db_path_for_owner("Runner One")

    assert owner_db == tmp_path / "users" / "Runner_One.db"
    assert owner_db.exists()


def test_default_owner_preserves_existing_base_database(
    monkeypatch,
    tmp_path: Path,
) -> None:
    base_db = tmp_path / "temperance.db"
    base_db.parent.mkdir(parents=True, exist_ok=True)
    base_db.touch()
    monkeypatch.setattr(backend_main, "DB_PATH", base_db)

    owner_db = backend_main._db_path_for_owner("default")

    assert owner_db == base_db
    assert owner_db.exists()

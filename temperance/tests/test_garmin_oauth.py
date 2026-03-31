from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import garmin_oauth
from backend.app import main as backend_main
from temperance.db import get_oauth_connection, init_db


def _configure_oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARMIN_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GARMIN_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GARMIN_OAUTH_REDIRECT_URI", "http://localhost:8000/api/v1/garmin/oauth/callback")
    monkeypatch.setenv("GARMIN_OAUTH_AUTHORIZE_URL", "https://garmin.example.test/oauth/authorize")
    monkeypatch.setenv("GARMIN_OAUTH_TOKEN_URL", "https://garmin.example.test/oauth/token")
    monkeypatch.setenv("GARMIN_OAUTH_USERINFO_URL", "https://garmin.example.test/oauth/userinfo")
    monkeypatch.setenv("TEMPERANCE_OAUTH_TOKEN_ENCRYPTION_KEY", "oauth-encryption-secret")


@pytest.fixture(autouse=True)
def _clear_runtime_credentials() -> None:
    backend_main._clear_runtime_garmin_credentials("runner")
    backend_main._clear_runtime_garmin_credentials("admin")
    yield
    backend_main._clear_runtime_garmin_credentials("runner")
    backend_main._clear_runtime_garmin_credentials("admin")


def test_garmin_oauth_state_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_oauth_env(monkeypatch)
    state = garmin_oauth.build_state(user="runner", role="viewer", owner="runner", ttl_seconds=600)

    parsed = garmin_oauth.parse_state(state)

    assert parsed["u"] == "runner"
    assert parsed["r"] == "viewer"
    assert parsed["o"] == "runner"


def test_garmin_oauth_state_rejects_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_oauth_env(monkeypatch)
    state = garmin_oauth.build_state(user="runner", role="viewer", owner="runner", ttl_seconds=600)
    tampered = f"{state[:-1]}x"

    with pytest.raises(garmin_oauth.GarminOAuthError):
        garmin_oauth.parse_state(tampered)


def test_encrypt_and_decrypt_token_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_oauth_env(monkeypatch)
    payload = {
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "scope": "activities wellness",
        "expires_in": 3600,
    }

    ciphertext = garmin_oauth.encrypt_token_payload(payload)
    restored = garmin_oauth.decrypt_token_payload(ciphertext)

    assert ciphertext != "access-1"
    assert restored["access_token"] == "access-1"
    assert restored["refresh_token"] == "refresh-1"


def test_oauth_start_returns_authorization_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_oauth_env(monkeypatch)
    monkeypatch.setattr(backend_main, "_auth_context", lambda authorization: {"user": "runner", "role": "viewer"})
    monkeypatch.setattr(backend_main, "_resolve_owner", lambda ctx, owner: "runner")

    payload = backend_main.garmin_oauth_start()

    assert payload["owner"] == "runner"
    assert payload["authorization_url"].startswith("https://garmin.example.test/oauth/authorize?")
    assert "state=" in payload["authorization_url"]


def test_oauth_start_rejects_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_oauth_env(monkeypatch)
    monkeypatch.setattr(backend_main, "_auth_context", lambda authorization: {"user": "admin", "role": "admin"})

    with pytest.raises(backend_main.HTTPException) as exc:
        backend_main.garmin_oauth_start()

    assert exc.value.status_code == 403


def test_oauth_callback_saves_owner_connection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_oauth_env(monkeypatch)
    db_path = tmp_path / "runner.db"
    init_db(db_path)
    monkeypatch.setattr(backend_main, "_db_path_for_owner", lambda owner: db_path)
    monkeypatch.setattr(
        backend_main,
        "exchange_garmin_oauth_code_for_tokens",
        lambda code: {
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "scope": "activities wellness",
            "expires_in": 1800,
            "refresh_token_expires_in": 7200,
        },
    )
    monkeypatch.setattr(
        backend_main,
        "fetch_garmin_oauth_userinfo",
        lambda access_token: {"sub": "garmin-user-1", "email": "runner@example.com"},
    )
    state = garmin_oauth.build_state(user="runner", role="viewer", owner="runner", ttl_seconds=600)

    response = backend_main.garmin_oauth_callback(code="auth-code", state=state)
    connection = get_oauth_connection(db_path, backend_main.GARMIN_OAUTH_PROVIDER)

    assert response.status_code == 303
    assert "garmin_oauth=success" in response.headers["location"]
    assert connection is not None
    assert connection["account_email"] == "runner@example.com"
    token_payload = garmin_oauth.decrypt_token_payload(connection["token_ciphertext"])
    assert token_payload["access_token"] == "access-1"


def test_oauth_disconnect_removes_connection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_oauth_env(monkeypatch)
    db_path = tmp_path / "runner.db"
    init_db(db_path)
    backend_main._save_garmin_oauth_connection(
        db_path,
        token_payload={"access_token": "access-1", "refresh_token": "refresh-1", "scope": "activities"},
        userinfo_payload={"sub": "garmin-user-1", "email": "runner@example.com"},
    )
    monkeypatch.setattr(backend_main, "_auth_context", lambda authorization: {"user": "runner", "role": "viewer"})
    monkeypatch.setattr(backend_main, "_resolve_owner", lambda ctx, owner: "runner")
    monkeypatch.setattr(backend_main, "_db_path_for_owner", lambda owner: db_path)

    payload = backend_main.garmin_oauth_disconnect()

    assert payload["success"] is True
    assert payload["disconnected"] is True
    assert get_oauth_connection(db_path, backend_main.GARMIN_OAUTH_PROVIDER) is None


def test_viewer_status_prefers_oauth_over_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_oauth_env(monkeypatch)
    db_path = tmp_path / "runner.db"
    init_db(db_path)
    backend_main._set_runtime_garmin_credentials("runner", email="runner@example.com", password="pw")
    backend_main._save_garmin_oauth_connection(
        db_path,
        token_payload={"access_token": "access-1", "refresh_token": "refresh-1", "scope": "activities"},
        userinfo_payload={"sub": "garmin-user-1", "email": "runner@example.com"},
    )
    monkeypatch.setattr(backend_main, "_auth_context", lambda authorization: {"user": "runner", "role": "viewer"})
    monkeypatch.setattr(backend_main, "_resolve_owner", lambda ctx, owner: "runner")
    monkeypatch.setattr(backend_main, "_db_path_for_owner", lambda owner: db_path)
    monkeypatch.setattr(backend_main, "load_config", lambda: SimpleNamespace(import_dir=str(tmp_path / "import")))

    payload = backend_main.data_extract_status()

    assert payload["garmin_connection_mode"] == "oauth"
    assert payload["garmin_oauth"]["connected"] is True
    assert payload["garmin_credentials_source"] == "session"


def test_viewer_sync_source_falls_back_to_session_when_oauth_sync_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_oauth_env(monkeypatch)
    monkeypatch.delenv("GARMIN_OAUTH_ACTIVITIES_URL", raising=False)
    monkeypatch.delenv("GARMIN_OAUTH_WELLNESS_URL", raising=False)
    db_path = tmp_path / "runner.db"
    init_db(db_path)
    backend_main._save_garmin_oauth_connection(
        db_path,
        token_payload={"access_token": "access-1", "refresh_token": "refresh-1", "scope": "activities"},
        userinfo_payload={"sub": "garmin-user-1", "email": "runner@example.com"},
    )
    backend_main._set_runtime_garmin_credentials("runner", email="runner@example.com", password="pw")

    selection = backend_main._resolve_garmin_sync_source(
        {"user": "runner", "role": "viewer"},
        "runner",
        db_path,
        require_wellness=False,
        require_comprehensive=True,
    )

    assert selection["mode"] == "session"
    assert selection["credentials_source"] == "session"


def test_admin_status_keeps_legacy_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_oauth_env(monkeypatch)
    db_path = tmp_path / "admin.db"
    init_db(db_path)
    backend_main._save_garmin_oauth_connection(
        db_path,
        token_payload={"access_token": "access-1", "refresh_token": "refresh-1", "scope": "activities"},
        userinfo_payload={"sub": "garmin-user-1", "email": "admin@example.com"},
    )
    monkeypatch.setenv("GARMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    monkeypatch.setattr(backend_main, "_auth_context", lambda authorization: {"user": "admin", "role": "admin"})
    monkeypatch.setattr(backend_main, "_resolve_owner", lambda ctx, owner: "admin")
    monkeypatch.setattr(backend_main, "_db_path_for_owner", lambda owner: db_path)
    monkeypatch.setattr(backend_main, "load_config", lambda: SimpleNamespace(import_dir=str(tmp_path / "import")))

    payload = backend_main.data_extract_status()

    assert payload["garmin_connection_mode"] == "env"
    assert payload["garmin_credentials_source"] == "env"
    assert payload["garmin_oauth"]["connected"] is True

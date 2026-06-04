import pytest

from backend.app import main as backend_main
from temperance.auth import (
    PBKDF2_SHA256_PREFIX,
    build_users,
    normalize_password_hash,
    password_matches,
    resolve_garmin_credentials,
    resolve_user,
)


def test_normalize_password_hash_accepts_sha_prefix_and_case() -> None:
    raw = " sha256:ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789 "
    assert normalize_password_hash(raw) == "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"


def test_build_users_prefers_hash_and_normalizes_it() -> None:
    users = build_users(
        admin_user="admin",
        admin_pass="secret",
        admin_pass_hash="SHA256:2BB80D537B1DA3E38BD30361AA855686BDE0EACB6E8A6A0F3D8D7A9F12AB8E3A",
        viewer_user="",
        viewer_pass="",
        viewer_pass_hash="",
        viewer_users="",
        viewer_users_hash="",
    )
    assert users["admin"]["password_hash"].islower()


def test_build_users_hashes_plaintext_passwords_with_pbkdf2() -> None:
    users = build_users(
        admin_user="admin",
        admin_pass="secret",
        admin_pass_hash="",
        viewer_user="",
        viewer_pass="",
        viewer_pass_hash="",
        viewer_users="",
        viewer_users_hash="",
    )
    assert users["admin"]["password_hash"].startswith(f"{PBKDF2_SHA256_PREFIX}$")
    assert password_matches("secret", users["admin"]["password_hash"])


def test_build_users_supports_multiple_viewers_plain_and_hash() -> None:
    users = build_users(
        admin_user="admin",
        admin_pass="secret",
        admin_pass_hash="",
        viewer_user="guest",
        viewer_pass="guest_pw",
        viewer_pass_hash="",
        viewer_users="sirpoc:sirpoc_pw,runner=runner_pw",
        viewer_users_hash="hashed:SHA256:2BB80D537B1DA3E38BD30361AA855686BDE0EACB6E8A6A0F3D8D7A9F12AB8E3A",
    )
    assert users["guest"]["role"] == "viewer"
    assert password_matches("guest_pw", users["guest"]["password_hash"])
    assert users["sirpoc"]["role"] == "viewer"
    assert password_matches("sirpoc_pw", users["sirpoc"]["password_hash"])
    assert users["runner"]["role"] == "viewer"
    assert password_matches("runner_pw", users["runner"]["password_hash"])
    assert users["hashed"]["role"] == "viewer"
    assert users["hashed"]["password_hash"].islower()


def test_password_matches_supports_pbkdf2_and_legacy_sha256() -> None:
    users = build_users(
        admin_user="admin",
        admin_pass="secret",
        admin_pass_hash="",
        viewer_user="",
        viewer_pass="",
        viewer_pass_hash="",
        viewer_users="",
        viewer_users_hash="",
    )
    assert password_matches("secret", users["admin"]["password_hash"])
    hash_value = "2bb80d537b1da3e38bd30361aa855686bde0eacd7162fef6a25fe97bf527a25b"
    assert password_matches("secret", hash_value)
    assert not password_matches("wrong", hash_value)
    assert not password_matches("secret", "secret")


def test_resolve_user_is_case_insensitive() -> None:
    users = {
        "AdminUser": {"password_hash": "x", "role": "admin"},
    }
    resolved_name, data = resolve_user(users, "adminuser")
    assert resolved_name == "AdminUser"
    assert data == users["AdminUser"]


def test_resolve_garmin_credentials_admin_can_fallback_to_env() -> None:
    email, password, source = resolve_garmin_credentials(
        auth_enabled=True,
        auth_role="admin",
        session_email="",
        session_password="",
        env_email="admin@example.com",
        env_password="admin_pw",
    )
    assert email == "admin@example.com"
    assert password == "admin_pw"
    assert source == "environment"


def test_resolve_garmin_credentials_external_user_must_use_session() -> None:
    email, password, source = resolve_garmin_credentials(
        auth_enabled=True,
        auth_role="viewer",
        session_email="",
        session_password="",
        env_email="admin@example.com",
        env_password="admin_pw",
    )
    assert email is None
    assert password is None
    assert source == "missing"


def test_resolve_garmin_credentials_prefers_session_values() -> None:
    email, password, source = resolve_garmin_credentials(
        auth_enabled=True,
        auth_role="viewer",
        session_email="runner@example.com",
        session_password="runner_pw",
        env_email="admin@example.com",
        env_password="admin_pw",
    )
    assert email == "runner@example.com"
    assert password == "runner_pw"
    assert source == "session"


def test_auth_login_fails_closed_when_enabled_without_users(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEMPERANCE_AUTH_ENABLED", "1")
    monkeypatch.delenv("TEMPERANCE_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("TEMPERANCE_ADMIN_PASSWORD_SHA256", raising=False)
    monkeypatch.delenv("TEMPERANCE_VIEWER_PASSWORD", raising=False)
    monkeypatch.delenv("TEMPERANCE_VIEWER_PASSWORD_SHA256", raising=False)
    monkeypatch.delenv("TEMPERANCE_VIEWER_USERS", raising=False)
    monkeypatch.delenv("TEMPERANCE_VIEWER_USERS_SHA256", raising=False)
    monkeypatch.setenv("TEMPERANCE_AUTH_SECRET", "auth-secret")

    with pytest.raises(backend_main.HTTPException) as exc:
        backend_main.auth_login(
            backend_main.LoginRequest(username="admin", password="secret"),
            response=backend_main.Response(),
        )

    assert exc.value.status_code == 503
    assert "no users" in str(exc.value.detail).lower()


def test_auth_login_fails_closed_when_signing_secret_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEMPERANCE_AUTH_ENABLED", "1")
    monkeypatch.setenv("TEMPERANCE_ADMIN_PASSWORD", "secret")
    monkeypatch.delenv("TEMPERANCE_AUTH_SECRET", raising=False)
    monkeypatch.delenv("TEMPERANCE_AUTH_COOKIE_SECRET", raising=False)

    with pytest.raises(backend_main.HTTPException) as exc:
        backend_main.auth_login(
            backend_main.LoginRequest(username="admin", password="secret"),
            response=backend_main.Response(),
        )

    assert exc.value.status_code == 503
    assert "signing secret" in str(exc.value.detail).lower()


def test_auth_login_returns_placeholder_token_when_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEMPERANCE_AUTH_ENABLED", "0")

    payload = backend_main.auth_login(
        backend_main.LoginRequest(username="ignored", password="ignored"),
        response=backend_main.Response(),
    )

    assert payload == {"token": "auth-disabled", "user": "default", "role": "admin"}


def test_auth_login_sets_http_only_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEMPERANCE_AUTH_ENABLED", "1")
    monkeypatch.setenv("TEMPERANCE_AUTH_SECRET", "auth-secret")
    monkeypatch.setenv("TEMPERANCE_ADMIN_PASSWORD", "secret")
    response = backend_main.Response()

    payload = backend_main.auth_login(
        backend_main.LoginRequest(username="admin", password="secret"),
        response=response,
    )

    assert payload["token"]
    cookie_header = ""
    raw_headers = getattr(response, "raw_headers", [])
    for key, value in raw_headers:
        if key.lower() == b"set-cookie":
            cookie_header = value.decode("latin1")
            break
    if not cookie_header:
        cookies = getattr(response, "cookies", [])
        assert cookies
        cookie_header = f"{cookies[0][1][0]}={cookies[0][1][1]}"
    assert backend_main._cookie_header_token(cookie_header) == payload["token"]
    assert "Max-Age=2592000" in cookie_header


def test_auth_cookie_header_parser_rejects_missing_cookie() -> None:
    assert backend_main._cookie_header_token("other=value") == ""

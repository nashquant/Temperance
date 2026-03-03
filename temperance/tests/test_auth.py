from auth import build_users, normalize_password_hash, password_matches, resolve_garmin_credentials, resolve_user


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
    )
    assert users["admin"]["password_hash"].islower()


def test_password_matches_sha256_hash_and_plaintext_fallback() -> None:
    hash_value = "2bb80d537b1da3e38bd30361aa855686bde0eacd7162fef6a25fe97bf527a25b"
    assert password_matches("secret", hash_value)
    assert password_matches("secret", "secret")
    assert not password_matches("wrong", hash_value)


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

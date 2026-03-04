from __future__ import annotations

import hashlib
import hmac


def auth_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_password_hash(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate.lower().startswith("sha256:"):
        candidate = candidate.split(":", 1)[1].strip()
    return candidate.lower()


def _parse_user_map(raw: str) -> dict[str, str]:
    """
    Parse comma/semicolon/newline-separated user credential pairs:
    - user:password
    - user=password
    """
    parsed: dict[str, str] = {}
    for chunk in str(raw or "").replace("\n", ",").replace(";", ",").split(","):
        token = chunk.strip()
        if not token:
            continue
        if ":" in token:
            username, secret = token.split(":", 1)
        elif "=" in token:
            username, secret = token.split("=", 1)
        else:
            continue
        user = username.strip()
        val = secret.strip()
        if user and val:
            parsed[user] = val
    return parsed


def build_users(
    *,
    admin_user: str,
    admin_pass: str,
    admin_pass_hash: str,
    viewer_user: str,
    viewer_pass: str,
    viewer_pass_hash: str,
    viewer_users: str = "",
    viewer_users_hash: str = "",
) -> dict[str, dict[str, str]]:
    users: dict[str, dict[str, str]] = {}

    admin_user_clean = str(admin_user or "").strip()
    if admin_user_clean and (admin_pass or admin_pass_hash):
        users[admin_user_clean] = {
            "password_hash": normalize_password_hash(admin_pass_hash) or auth_hash(admin_pass),
            "role": "admin",
        }

    viewer_user_clean = str(viewer_user or "").strip()
    if viewer_user_clean and (viewer_pass or viewer_pass_hash):
        users[viewer_user_clean] = {
            "password_hash": normalize_password_hash(viewer_pass_hash) or auth_hash(viewer_pass),
            "role": "viewer",
        }

    for username, password in _parse_user_map(viewer_users).items():
        users[username] = {
            "password_hash": auth_hash(password),
            "role": "viewer",
        }

    for username, password_hash in _parse_user_map(viewer_users_hash).items():
        normalized = normalize_password_hash(password_hash)
        if normalized:
            users[username] = {
                "password_hash": normalized,
                "role": "viewer",
            }

    return users


def resolve_user(users: dict[str, dict[str, str]], username: str) -> tuple[str, dict[str, str]] | tuple[None, None]:
    candidate = str(username or "").strip()
    if not candidate:
        return None, None
    if candidate in users:
        return candidate, users[candidate]

    folded = candidate.casefold()
    for known_user, data in users.items():
        if known_user.casefold() == folded:
            return known_user, data
    return None, None


def password_matches(password: str, configured_hash: str) -> bool:
    normalized = normalize_password_hash(configured_hash)
    if len(normalized) == 64 and all(ch in "0123456789abcdef" for ch in normalized):
        return hmac.compare_digest(auth_hash(password), normalized)
    # Backward-compatible fallback when a plain password is accidentally provided
    return hmac.compare_digest(str(password), str(configured_hash))


def resolve_garmin_credentials(
    *,
    auth_enabled: bool,
    auth_role: str | None,
    session_email: str,
    session_password: str,
    env_email: str | None,
    env_password: str | None,
) -> tuple[str | None, str | None, str]:
    email_input = str(session_email or "").strip()
    password_input = str(session_password or "")
    if email_input and password_input:
        return email_input, password_input, "session"

    role = str(auth_role or "").strip().lower()
    # When app auth is enabled, only admin can use env Garmin credentials.
    if auth_enabled and role != "admin":
        return None, None, "missing"

    email = str(env_email or "").strip()
    password = str(env_password or "")
    if email and password:
        return email, password, "environment"
    return None, None, "missing"

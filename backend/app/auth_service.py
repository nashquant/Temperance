from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
from datetime import datetime, timezone
from http.cookies import SimpleCookie

from fastapi import HTTPException
from fastapi.requests import Request
from fastapi.responses import Response

from temperance.auth import build_users, resolve_user, password_matches

TOKEN_TTL_S = int(
    os.getenv("TEMPERANCE_SESSION_TTL_S", str(4 * 60 * 60)) or (4 * 60 * 60)
)
AUTH_COOKIE_NAME = "temperance_session"


class AuthConfigurationError(RuntimeError):
    pass


_AUTH_USERS_CACHE: dict[str, dict[str, str]] | None = None
_AUTH_USERS_CACHE_LOCK = threading.Lock()


def auth_enabled() -> bool:
    return str(os.getenv("TEMPERANCE_AUTH_ENABLED", "1")).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def auth_users() -> dict[str, dict[str, str]]:
    global _AUTH_USERS_CACHE
    if _AUTH_USERS_CACHE is not None:
        return _AUTH_USERS_CACHE
    with _AUTH_USERS_CACHE_LOCK:
        if _AUTH_USERS_CACHE is None:
            _AUTH_USERS_CACHE = build_users(
                admin_user=os.getenv("TEMPERANCE_ADMIN_USER", "admin"),
                admin_pass=os.getenv("TEMPERANCE_ADMIN_PASSWORD", ""),
                admin_pass_hash=os.getenv("TEMPERANCE_ADMIN_PASSWORD_SHA256", ""),
                viewer_user=os.getenv("TEMPERANCE_VIEWER_USER", ""),
                viewer_pass=os.getenv("TEMPERANCE_VIEWER_PASSWORD", ""),
                viewer_pass_hash=os.getenv("TEMPERANCE_VIEWER_PASSWORD_SHA256", ""),
                viewer_users=os.getenv("TEMPERANCE_VIEWER_USERS", ""),
                viewer_users_hash=os.getenv("TEMPERANCE_VIEWER_USERS_SHA256", ""),
            )
    return _AUTH_USERS_CACHE


def auth_configuration_error() -> str | None:
    if not auth_enabled():
        return None
    if not auth_users():
        return "Authentication is enabled but no users are configured."
    if not (
        str(os.getenv("TEMPERANCE_AUTH_COOKIE_SECRET") or "").strip()
        or str(os.getenv("TEMPERANCE_AUTH_SECRET") or "").strip()
    ):
        return "Authentication is enabled but no signing secret is configured."
    return None


def require_auth_ready() -> None:
    error = auth_configuration_error()
    if error:
        raise HTTPException(status_code=503, detail=error)


def auth_cookie_secure() -> bool:
    return str(os.getenv("TEMPERANCE_AUTH_COOKIE_SECURE", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=max(int(TOKEN_TTL_S), 60),
        httponly=True,
        secure=auth_cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", samesite="lax")


def _auth_secret() -> str:
    secret = (
        str(os.getenv("TEMPERANCE_AUTH_COOKIE_SECRET") or "").strip()
        or str(os.getenv("TEMPERANCE_AUTH_SECRET") or "").strip()
    )
    if not secret:
        raise AuthConfigurationError("Authentication signing secret is not configured.")
    return secret


def _auth_sign(payload_b64: str) -> str:
    secret = _auth_secret().encode("utf-8")
    return hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def build_token(user: str, role: str, ttl_s: int = TOKEN_TTL_S) -> str:
    exp = int(datetime.now(timezone.utc).timestamp()) + max(60, int(ttl_s))
    payload = {"u": user, "r": role, "exp": exp}
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    return f"{payload_b64}.{_auth_sign(payload_b64)}"


def parse_token(token: str) -> tuple[str, str] | None:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        return None
    payload_b64, sig = raw.split(".", 1)
    if not hmac.compare_digest(_auth_sign(payload_b64), sig):
        return None
    try:
        padded = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        )
    except Exception:
        return None
    user = str(payload.get("u") or "").strip()
    role = str(payload.get("r") or "").strip().lower()
    exp = int(payload.get("exp") or 0)
    if not user or role not in {"admin", "viewer"}:
        return None
    if exp <= int(datetime.now(timezone.utc).timestamp()):
        return None
    return user, role


def bearer_token(authorization: str | None) -> str:
    raw = str(authorization or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw


def cookie_header_token(raw_cookie: str | None) -> str:
    if not raw_cookie:
        return ""
    parsed = SimpleCookie()
    try:
        parsed.load(str(raw_cookie))
    except Exception:
        return ""
    morsel = parsed.get(AUTH_COOKIE_NAME)
    return str(morsel.value or "").strip() if morsel else ""


def request_cookie_token(request: Request) -> str:
    try:
        cookie_value = getattr(request, "cookies", {}).get(AUTH_COOKIE_NAME)
        if cookie_value:
            return str(cookie_value).strip()
    except Exception:
        pass
    for key, value in request.scope.get("headers", []) or []:
        if key.lower() == b"cookie":
            return cookie_header_token(value.decode("latin1"))
    return ""


def scope_has_authorization(request: Request) -> bool:
    return any(
        key.lower() == b"authorization"
        for key, _value in request.scope.get("headers", []) or []
    )


def auth_context(authorization: str | None) -> dict[str, str]:
    if not auth_enabled():
        return {"user": "default", "role": "admin"}
    require_auth_ready()

    users = auth_users()
    token = bearer_token(authorization)
    parsed = parse_token(token)
    if not parsed:
        raise HTTPException(status_code=401, detail="Missing or invalid auth token")
    user, role = parsed

    resolved_user, user_data = resolve_user(users, user)
    if not user_data or not resolved_user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    expected_role = str(user_data.get("role") or "").strip().lower()
    if expected_role != role:
        raise HTTPException(status_code=401, detail="Role mismatch")

    return {"user": resolved_user, "role": role}


def resolve_owner(ctx: dict[str, str], requested_owner: str | None) -> str:
    role = str(ctx.get("role") or "viewer")
    user = str(ctx.get("user") or "default")
    candidate = str(requested_owner or "").strip()
    if role == "admin":
        return candidate or user
    return user

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response

from backend.app.auth_service import (
    auth_context,
    auth_enabled,
    auth_users,
    build_token,
    clear_auth_cookie,
    require_auth_ready,
    resolve_owner,
    set_auth_cookie,
)
from backend.app.models import LoginRequest
from temperance.auth import password_matches, resolve_user

router = APIRouter()


@router.post("/api/v1/auth/login")
def auth_login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    if not auth_enabled():
        clear_auth_cookie(response)
        return {"token": "auth-disabled", "user": "default", "role": "admin"}
    require_auth_ready()

    users = auth_users()
    resolved_user, user_data = resolve_user(users, payload.username)
    if not user_data or not resolved_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not password_matches(
        payload.password, str(user_data.get("password_hash") or "")
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = str(user_data.get("role") or "viewer").strip().lower()
    token = build_token(user=resolved_user, role=role)
    set_auth_cookie(response, token)
    return {"token": token, "user": resolved_user, "role": role}


@router.post("/api/v1/auth/logout")
def auth_logout(response: Response) -> dict[str, bool]:
    clear_auth_cookie(response)
    return {"ok": True}


@router.get("/api/v1/auth/me")
def auth_me(
    authorization: str | None = Header(default=None, alias="Authorization")
) -> dict[str, Any]:
    ctx = auth_context(authorization)
    owner = resolve_owner(ctx, None)
    return {
        "user": ctx["user"],
        "role": ctx["role"],
        "owner": owner,
        "auth_enabled": auth_enabled(),
    }


@router.get("/api/v1/auth/owners")
def auth_owners(
    authorization: str | None = Header(default=None, alias="Authorization")
) -> dict[str, Any]:
    ctx = auth_context(authorization)
    if str(ctx.get("role")) == "admin":
        users = auth_users()
        options = sorted(users.keys()) if users else [ctx["user"]]
        return {"owners": options}
    return {"owners": [ctx["user"]]}

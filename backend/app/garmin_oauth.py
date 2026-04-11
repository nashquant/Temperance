from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken


class GarminOAuthError(RuntimeError):
    pass


class GarminOAuthConfigurationError(GarminOAuthError):
    pass


@dataclass(frozen=True)
class GarminOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    userinfo_url: str | None
    scopes: tuple[str, ...]
    activities_url: str | None
    wellness_url: str | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _optional_env(name: str) -> str | None:
    value = str(os.getenv(name) or "").strip()
    return value or None


def _required_env(name: str) -> str:
    value = str(os.getenv(name) or "").strip()
    if not value:
        raise GarminOAuthConfigurationError(f"Missing required env var: {name}")
    return value


def load_config() -> GarminOAuthConfig:
    raw_scopes = str(os.getenv("GARMIN_OAUTH_SCOPES") or "activities wellness profile").replace(",", " ")
    scopes = tuple(token for token in (item.strip() for item in raw_scopes.split()) if token)
    return GarminOAuthConfig(
        client_id=_required_env("GARMIN_OAUTH_CLIENT_ID"),
        client_secret=_required_env("GARMIN_OAUTH_CLIENT_SECRET"),
        redirect_uri=_required_env("GARMIN_OAUTH_REDIRECT_URI"),
        authorize_url=_required_env("GARMIN_OAUTH_AUTHORIZE_URL"),
        token_url=_required_env("GARMIN_OAUTH_TOKEN_URL"),
        userinfo_url=_optional_env("GARMIN_OAUTH_USERINFO_URL"),
        scopes=scopes,
        activities_url=_optional_env("GARMIN_OAUTH_ACTIVITIES_URL"),
        wellness_url=_optional_env("GARMIN_OAUTH_WELLNESS_URL"),
    )


def configured() -> bool:
    try:
        load_config()
    except GarminOAuthConfigurationError:
        return False
    return True


def capabilities() -> dict[str, Any]:
    try:
        config = load_config()
    except GarminOAuthConfigurationError as exc:
        message = str(exc)
        return {
            "activities": False,
            "wellness": False,
            "details": False,
            "comprehensive": False,
            "reason": message,
            "configured": False,
        }
    activities_supported = bool(config.activities_url)
    wellness_supported = bool(config.wellness_url)
    return {
        "activities": activities_supported,
        "wellness": wellness_supported,
        "details": activities_supported,
        "comprehensive": activities_supported,
        "reason": None if (activities_supported or wellness_supported) else "Garmin OAuth sync endpoints are not configured.",
        "configured": True,
    }


def _state_secret() -> str:
    secret = (
        str(os.getenv("GARMIN_OAUTH_STATE_SECRET") or "").strip()
        or str(os.getenv("TEMPERANCE_AUTH_COOKIE_SECRET") or "").strip()
        or str(os.getenv("TEMPERANCE_AUTH_SECRET") or "").strip()
    )
    if not secret:
        raise GarminOAuthConfigurationError("Missing required signing secret: GARMIN_OAUTH_STATE_SECRET or TEMPERANCE_AUTH_SECRET")
    return secret


def _sign(payload_b64: str) -> str:
    return hmac.new(_state_secret().encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def build_state(*, user: str, role: str, owner: str, ttl_seconds: int = 10 * 60) -> str:
    payload = {
        "u": str(user or "").strip(),
        "r": str(role or "").strip().lower(),
        "o": str(owner or "").strip(),
        "n": secrets.token_urlsafe(12),
        "exp": int((_utc_now() + timedelta(seconds=max(int(ttl_seconds), 60))).timestamp()),
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    return f"{payload_b64}.{_sign(payload_b64)}"


def parse_state(raw_state: str) -> dict[str, Any]:
    raw = str(raw_state or "").strip()
    if not raw or "." not in raw:
        raise GarminOAuthError("Missing or invalid OAuth state.")
    payload_b64, provided_sig = raw.split(".", 1)
    if not hmac.compare_digest(_sign(payload_b64), provided_sig):
        raise GarminOAuthError("Garmin OAuth state signature is invalid.")
    padded = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    except Exception as exc:
        raise GarminOAuthError("Garmin OAuth state could not be decoded.") from exc
    if int(payload.get("exp") or 0) <= int(_utc_now().timestamp()):
        raise GarminOAuthError("Garmin OAuth state has expired.")
    owner = str(payload.get("o") or "").strip()
    user = str(payload.get("u") or "").strip()
    role = str(payload.get("r") or "").strip().lower()
    if not owner or not user or role not in {"admin", "viewer"}:
        raise GarminOAuthError("Garmin OAuth state is incomplete.")
    return payload


def _fernet() -> Fernet:
    secret = _required_env("TEMPERANCE_OAUTH_TOKEN_ENCRYPTION_KEY")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_token_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _fernet().encrypt(serialized).decode("utf-8")


def decrypt_token_payload(ciphertext: str) -> dict[str, Any]:
    try:
        raw = _fernet().decrypt(str(ciphertext or "").encode("utf-8"))
    except InvalidToken as exc:
        raise GarminOAuthError("Stored Garmin OAuth token is unreadable.") from exc
    return json.loads(raw.decode("utf-8"))


def build_authorization_url(state: str) -> str:
    config = load_config()
    query = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
    }
    return f"{config.authorize_url}?{urlencode(query)}"


def _decode_jwt_payload(token: str | None) -> dict[str, Any]:
    raw = str(token or "").strip()
    if raw.count(".") < 2:
        return {}
    parts = raw.split(".")
    padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_request(
    *,
    url: str,
    method: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> dict[str, Any]:
    request = Request(url=url, data=body, method=method.upper())
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else str(exc)
        raise GarminOAuthError(f"Garmin OAuth request failed ({exc.code}): {detail or exc.reason}") from exc
    except URLError as exc:
        raise GarminOAuthError(f"Garmin OAuth request failed: {exc.reason}") from exc
    try:
        data = json.loads(payload or "{}")
    except Exception as exc:
        raise GarminOAuthError("Garmin OAuth response was not valid JSON.") from exc
    return data if isinstance(data, dict) else {"data": data}


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    config = load_config()
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": str(code or "").strip(),
            "redirect_uri": config.redirect_uri,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }
    ).encode("utf-8")
    basic_auth = base64.b64encode(f"{config.client_id}:{config.client_secret}".encode("utf-8")).decode("utf-8")
    return _json_request(
        url=config.token_url,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=body,
    )


def refresh_tokens(token_payload: dict[str, Any]) -> dict[str, Any]:
    refresh_token = str(token_payload.get("refresh_token") or "").strip()
    if not refresh_token:
        raise GarminOAuthError("Garmin OAuth refresh token is missing.")
    config = load_config()
    body = urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }
    ).encode("utf-8")
    basic_auth = base64.b64encode(f"{config.client_id}:{config.client_secret}".encode("utf-8")).decode("utf-8")
    response = _json_request(
        url=config.token_url,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body=body,
    )
    merged = dict(token_payload)
    merged.update(response)
    return merged


def maybe_refresh_token_payload(token_payload: dict[str, Any], *, leeway_seconds: int = 60) -> tuple[dict[str, Any], bool]:
    expires_at = normalize_expiry(token_payload, "expires_at", "expires_in")
    if expires_at is None:
        return token_payload, False
    if expires_at > _utc_now() + timedelta(seconds=max(int(leeway_seconds), 0)):
        return token_payload, False
    refreshed = refresh_tokens(token_payload)
    return refreshed, True


def fetch_userinfo(access_token: str) -> dict[str, Any] | None:
    config = load_config()
    if not config.userinfo_url:
        return None
    return _json_request(
        url=config.userinfo_url,
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )


def normalize_expiry(payload: dict[str, Any], absolute_key: str, relative_key: str) -> datetime | None:
    absolute_value = str(payload.get(absolute_key) or "").strip()
    if absolute_value:
        try:
            parsed = datetime.fromisoformat(absolute_value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    try:
        relative_seconds = int(payload.get(relative_key) or 0)
    except Exception:
        relative_seconds = 0
    if relative_seconds <= 0:
        return None
    return _utc_now() + timedelta(seconds=relative_seconds)


def connection_metadata(token_payload: dict[str, Any], userinfo: dict[str, Any] | None = None) -> dict[str, Any]:
    userinfo_payload = userinfo if isinstance(userinfo, dict) else {}
    id_token_payload = _decode_jwt_payload(token_payload.get("id_token"))
    scopes_raw = str(token_payload.get("scope") or "").replace(",", " ").split()
    scopes = [scope for scope in (item.strip() for item in scopes_raw) if scope]
    subject = (
        str(userinfo_payload.get("sub") or "").strip()
        or str(id_token_payload.get("sub") or "").strip()
        or None
    )
    email = (
        str(userinfo_payload.get("email") or "").strip()
        or str(id_token_payload.get("email") or "").strip()
        or None
    )
    expires_at = normalize_expiry(token_payload, "expires_at", "expires_in")
    refresh_expires_at = normalize_expiry(token_payload, "refresh_expires_at", "refresh_token_expires_in")
    return {
        "account_subject": subject,
        "account_email": email,
        "scopes": scopes,
        "token_expires_at": expires_at.isoformat() if expires_at is not None else None,
        "refresh_expires_at": refresh_expires_at.isoformat() if refresh_expires_at is not None else None,
    }


def _format_sync_url(template: str, *, start_day: str, end_day: str) -> str:
    if "{start_day}" in template or "{end_day}" in template:
        return template.format(start_day=start_day, end_day=end_day)
    separator = "&" if "?" in template else "?"
    return f"{template}{separator}{urlencode({'start_day': start_day, 'end_day': end_day})}"


def fetch_normalized_activities(access_token: str, *, start_day: str, end_day: str) -> dict[str, Any]:
    config = load_config()
    if not config.activities_url:
        raise GarminOAuthError("Garmin OAuth activities endpoint is not configured.")
    payload = _json_request(
        url=_format_sync_url(config.activities_url, start_day=start_day, end_day=end_day),
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    return {
        "activities": list(payload.get("activities") or []),
        "activity_details": list(payload.get("activity_details") or []),
        "activity_records": list(payload.get("activity_records") or []),
        "activity_splits": list(payload.get("activity_splits") or []),
    }


def fetch_normalized_wellness(access_token: str, *, start_day: str, end_day: str) -> dict[str, Any]:
    config = load_config()
    if not config.wellness_url:
        raise GarminOAuthError("Garmin OAuth wellness endpoint is not configured.")
    payload = _json_request(
        url=_format_sync_url(config.wellness_url, start_day=start_day, end_day=end_day),
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    return {
        "sleep_daily": list(payload.get("sleep_daily") or []),
        "wellness_daily": list(payload.get("wellness_daily") or []),
    }

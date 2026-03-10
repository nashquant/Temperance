from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

TEMPERANCE_SRC = Path(__file__).resolve().parents[3] / "temperance"
if str(TEMPERANCE_SRC) not in sys.path:
    sys.path.insert(0, str(TEMPERANCE_SRC))

from config import load_config  # noqa: E402


def _default_db_path() -> Path:
    try:
        return Path(load_config().db_path)
    except Exception:
        return TEMPERANCE_SRC / "data" / "private" / "temperance.db"


DB_PATH = Path(str(os.getenv("TEMPERANCE_DB_PATH") or _default_db_path()))

from analytics import build_daily_summary, compute_metrics, display_table, ema_multi, weekly_summary  # noqa: E402
from auth import build_users, password_matches, resolve_user  # noqa: E402
from db import (  # noqa: E402
    delete_custom_activities,
    delete_planned_activities,
    init_db,
    get_custom_activities_df,
    get_last_sync,
    get_latest_activity_time,
    get_latest_recovery_day,
    get_activity_detail_raw,
    get_activity_splits_raw,
    get_activity_raw,
    get_activity_records_df,
    get_planned_activities_df,
    get_runs_df,
    get_sleep_df,
    get_setting,
    get_table_counts,
    get_wellness_df,
    log_sync,
    save_setting,
    upsert_activities,
    upsert_activity_details,
    upsert_activity_records,
    upsert_activity_splits,
    set_planned_activity_manual_done,
    upsert_sleep_daily,
    upsert_wellness_daily,
    upsert_planned_activities_rows,
    upsert_custom_activities_rows,
)
from garmin_client import (  # noqa: E402
    fetch_garmin_comprehensive,
    fetch_garmin_runs,
    import_runs_from_folder,
)

DEFAULT_LTHR = 178.0
DEFAULT_THRESHOLD_PACE_SEC_PER_KM = 300.0
SETTINGS_KEY_LTHR_CURVE = "lthr_curve_v1"
SETTINGS_KEY_LT_PACE_CURVE = "lt_pace_curve_v1"
SETTINGS_KEY_ACTIVITY_SPECIFICITY = "activity_specificity_v1"
SETTINGS_KEY_INJURY_WINDOWS = "injury_windows_v1"
SETTINGS_KEY_NON_RUNNING_FACTOR = "non_running_factor_v1"
APP_TIMEZONE_NAME = str(os.getenv("TEMPERANCE_TIMEZONE") or os.getenv("TZ") or "America/Sao_Paulo").strip() or "America/Sao_Paulo"


def _now_app_local() -> pd.Timestamp:
    try:
        return pd.Timestamp(datetime.now(ZoneInfo(APP_TIMEZONE_NAME))).tz_localize(None)
    except Exception:
        now_local = pd.Timestamp(datetime.now().astimezone())
        return now_local.tz_localize(None) if now_local.tzinfo is not None else now_local
SETTINGS_KEY_IF_ZONE_THRESHOLDS = "if_zone_thresholds_v1"
TOKEN_TTL_S = int(os.getenv("TEMPERANCE_SESSION_TTL_S", str(4 * 60 * 60)) or (4 * 60 * 60))
MAX_PLANNED_ENTRY_CHARS = 4000
MAX_PLANNED_ENTRIES_PER_SAVE = 40
CUSTOM_ACTIVITIES_LIMIT = 5000
LT_PACE_TO_WEEKLY_TARGET_POINTS = [
    (300.0, 67.0, 364.0),
    (270.0, 81.0, 396.0),
    (240.0, 96.0, 423.0),
    (225.0, 111.0, 464.0),
    (210.0, 127.0, 503.0),
    (200.0, 142.0, 540.0),
    (195.0, 154.0, 574.0),
    (190.0, 167.0, 615.0),
    (180.0, 194.0, 679.0),
]


class LoginRequest(BaseModel):
    username: str
    password: str


class PlannedManualDoneRequest(BaseModel):
    day_utc: str
    line_no: int
    manual_done: bool


class PlannedIngestRequest(BaseModel):
    entry_text: str


class PlannedWorkoutUpdateRequest(BaseModel):
    day_utc: str
    line_no: int
    workout_text: str
    manual_done: bool | None = None


class CustomIngestRequest(BaseModel):
    entry_text: str


class CustomActivityUpdateRequest(BaseModel):
    day_utc: str
    line_no: int
    activity_text: str


class UpdateSettingsRequest(BaseModel):
    if_zone_thresholds: dict[str, float] | None = None
    specificity_profile: dict[str, float] | None = None
    lthr_curve: list[dict[str, Any]] | None = None
    lt_pace_curve: list[dict[str, Any]] | None = None
    injury_windows: list[dict[str, Any]] | None = None


class SyncRequest(BaseModel):
    days_back: int = 180
    source: str = "both"  # garmin_api | file_import | both
    garmin_profile: str = "quick"  # quick | deep


class ComprehensiveExtractRequest(BaseModel):
    start_day: str
    incremental_only: bool = True
    include_details: bool = True
    include_wellness: bool = False
    verify_raw_integrity: bool = False


class GarminCredentialsRequest(BaseModel):
    email: str
    password: str


app = FastAPI(title="Temperance v2 API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _auth_enabled() -> bool:
    return str(os.getenv("TEMPERANCE_AUTH_ENABLED", "1")).strip().lower() not in {"0", "false", "no", "off"}


def _auth_users() -> dict[str, dict[str, str]]:
    return build_users(
        admin_user=os.getenv("TEMPERANCE_ADMIN_USER", "admin"),
        admin_pass=os.getenv("TEMPERANCE_ADMIN_PASSWORD", ""),
        admin_pass_hash=os.getenv("TEMPERANCE_ADMIN_PASSWORD_SHA256", ""),
        viewer_user=os.getenv("TEMPERANCE_VIEWER_USER", ""),
        viewer_pass=os.getenv("TEMPERANCE_VIEWER_PASSWORD", ""),
        viewer_pass_hash=os.getenv("TEMPERANCE_VIEWER_PASSWORD_SHA256", ""),
        viewer_users=os.getenv("TEMPERANCE_VIEWER_USERS", ""),
        viewer_users_hash=os.getenv("TEMPERANCE_VIEWER_USERS_SHA256", ""),
    )


def _auth_secret() -> str:
    return (
        str(os.getenv("TEMPERANCE_AUTH_COOKIE_SECRET") or "").strip()
        or str(os.getenv("TEMPERANCE_AUTH_SECRET") or "").strip()
        or "temperance-dev-secret"
    )


def _auth_sign(payload_b64: str) -> str:
    secret = _auth_secret().encode("utf-8")
    return hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def _build_token(user: str, role: str, ttl_s: int = TOKEN_TTL_S) -> str:
    exp = int(datetime.now(timezone.utc).timestamp()) + max(60, int(ttl_s))
    payload = {"u": user, "r": role, "exp": exp}
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    return f"{payload_b64}.{_auth_sign(payload_b64)}"


def _parse_token(token: str) -> tuple[str, str] | None:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        return None
    payload_b64, sig = raw.split(".", 1)
    if not hmac.compare_digest(_auth_sign(payload_b64), sig):
        return None
    try:
        padded = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
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


def _bearer_token(authorization: str | None) -> str:
    raw = str(authorization or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw


def _user_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()).strip("._-")
    return cleaned or "default"


def _db_path_for_owner(owner: str) -> Path:
    users_root = DB_PATH.parent / "users"
    owner_slug = _user_slug(owner)
    scoped = users_root / f"{owner_slug}.db"

    def _ensure_initialized(path: Path) -> Path:
        try:
            # Keep schema up-to-date for both new and existing DBs.
            init_db(path)
        except Exception:
            # Best effort; callers may still handle DB errors explicitly.
            pass
        return path

    # Keep legacy behavior only for the synthetic/default owner.
    if owner_slug == "default" and DB_PATH.exists():
        return _ensure_initialized(DB_PATH)

    # Named users always use isolated scoped DBs, created on demand.
    return _ensure_initialized(scoped)


def _auth_context(authorization: str | None) -> dict[str, str]:
    auth_on = _auth_enabled()
    if not auth_on:
        return {"user": "default", "role": "admin"}

    users = _auth_users()
    if not users:
        raise HTTPException(status_code=503, detail="Auth enabled but no users configured")

    token = _bearer_token(authorization)
    parsed = _parse_token(token)
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


def _resolve_owner(ctx: dict[str, str], requested_owner: str | None) -> str:
    role = str(ctx.get("role") or "viewer")
    user = str(ctx.get("user") or "default")
    candidate = str(requested_owner or "").strip()
    if role == "admin":
        return candidate or user
    return user


def _load_curve_points(
    db_path: Path,
    key: str,
    value_key: str,
    fallback_value: float,
) -> list[tuple[datetime, float]]:
    raw = get_setting(db_path, key)
    if not raw:
        return [(datetime(2025, 1, 1, tzinfo=timezone.utc), float(fallback_value))]
    try:
        rows = json.loads(raw)
    except Exception:
        return [(datetime(2025, 1, 1, tzinfo=timezone.utc), float(fallback_value))]
    if not isinstance(rows, list):
        return [(datetime(2025, 1, 1, tzinfo=timezone.utc), float(fallback_value))]

    out: list[tuple[datetime, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_raw = str(row.get("date") or "").strip()
        if not date_raw:
            continue
        try:
            parsed_date = datetime.fromisoformat(date_raw)
        except Exception:
            continue
        raw_value = row.get(value_key)
        if raw_value is None:
            if value_key == "lt_pace_sec":
                raw_value = row.get("lt_pace_sec_per_km")
            elif value_key == "lt_pace_sec_per_km":
                raw_value = row.get("lt_pace_sec")
            elif value_key == "lthr_bpm":
                raw_value = row.get("lthr")
        try:
            value = float(raw_value)
        except Exception:
            continue
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        out.append((parsed_date.astimezone(timezone.utc), value))
    if not out:
        return [(datetime(2025, 1, 1, tzinfo=timezone.utc), float(fallback_value))]
    out.sort(key=lambda item: item[0])
    return out


def _safe_float(value: Any) -> float:
    try:
        out = float(value)
        if not math.isfinite(out):
            return 0.0
        return out
    except Exception:
        return 0.0


def _optional_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return out


def _rounded_optional(value: Any, digits: int = 2) -> float | None:
    out = _optional_float(value)
    if out is None:
        return None
    return round(out, digits)


def _settings_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


_EXTRACT_PROGRESS_LOCK = threading.Lock()
_EXTRACT_PROGRESS_BY_OWNER: dict[str, dict[str, Any]] = {}
_GARMIN_RUNTIME_CREDENTIALS_LOCK = threading.Lock()
_GARMIN_RUNTIME_CREDENTIALS_BY_OWNER: dict[str, dict[str, str]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_progress_get(owner: str) -> dict[str, Any]:
    with _EXTRACT_PROGRESS_LOCK:
        state = _EXTRACT_PROGRESS_BY_OWNER.get(owner)
        if not state:
            return {
                "running": False,
                "phase": None,
                "message": None,
                "started_at": None,
                "finished_at": None,
                "updated_at": None,
                "logs": [],
                "log_count": 0,
                "activities": {"processed": 0, "total": 0, "day": None},
                "wellness": {"current": 0, "total": 0, "day": None},
            }
        return {
            "running": bool(state.get("running")),
            "phase": state.get("phase"),
            "message": state.get("message"),
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "updated_at": state.get("updated_at"),
            "logs": list(state.get("logs") or []),
            "log_count": int(state.get("log_count") or 0),
            "activities": dict(state.get("activities") or {"processed": 0, "total": 0, "day": None}),
            "wellness": dict(state.get("wellness") or {"current": 0, "total": 0, "day": None}),
        }


def _extract_progress_start(owner: str, start_day: str, end_day: str) -> None:
    now = _utc_now_iso()
    with _EXTRACT_PROGRESS_LOCK:
        _EXTRACT_PROGRESS_BY_OWNER[owner] = {
            "running": True,
            "phase": "starting",
            "message": "Starting comprehensive extract",
            "started_at": now,
            "finished_at": None,
            "updated_at": now,
            "logs": [f"[start] start_day={start_day} end_day={end_day}"],
            "log_count": 1,
            "activities": {"processed": 0, "total": 0, "day": None},
            "wellness": {"current": 0, "total": 0, "day": None},
            "last_activity_processed_logged": -1,
            "last_wellness_current_logged": -1,
        }


def _extract_progress_append(owner: str, line: str) -> None:
    if not line:
        return
    with _EXTRACT_PROGRESS_LOCK:
        state = _EXTRACT_PROGRESS_BY_OWNER.get(owner)
        if not state:
            return
        logs = list(state.get("logs") or [])
        logs.append(str(line))
        if len(logs) > 300:
            logs = logs[-300:]
        state["logs"] = logs
        state["log_count"] = int(state.get("log_count") or 0) + 1
        state["updated_at"] = _utc_now_iso()


def _extract_progress_event(owner: str, payload: dict[str, Any]) -> None:
    phase = str(payload.get("phase") or "").strip().lower()
    if not phase:
        return
    with _EXTRACT_PROGRESS_LOCK:
        state = _EXTRACT_PROGRESS_BY_OWNER.get(owner)
        if not state:
            return
        state["phase"] = phase
        state["message"] = str(payload.get("message") or state.get("message") or "")
        state["updated_at"] = _utc_now_iso()

        if phase == "activities":
            processed = int(payload.get("processed") or 0)
            total = int(payload.get("total") or 0)
            day = payload.get("day")
            state["activities"] = {"processed": processed, "total": total, "day": day}
            last_logged = int(state.get("last_activity_processed_logged") or -1)
            if processed > 0 and processed != last_logged:
                state["last_activity_processed_logged"] = processed
                logs = list(state.get("logs") or [])
                logs.append(
                    f"[progress] activities {processed}/{total if total > 0 else '?'}"
                    + (f" | day={day}" if day else "")
                )
                if len(logs) > 300:
                    logs = logs[-300:]
                state["logs"] = logs
                state["log_count"] = int(state.get("log_count") or 0) + 1
        elif phase == "wellness":
            current = int(payload.get("current") or 0)
            total = int(payload.get("total") or 0)
            day = payload.get("day")
            state["wellness"] = {"current": current, "total": total, "day": day}
            last_logged = int(state.get("last_wellness_current_logged") or -1)
            if current > 0 and current != last_logged:
                state["last_wellness_current_logged"] = current
                logs = list(state.get("logs") or [])
                logs.append(
                    f"[progress] wellness {current}/{total if total > 0 else '?'}"
                    + (f" | day={day}" if day else "")
                )
                if len(logs) > 300:
                    logs = logs[-300:]
                state["logs"] = logs
                state["log_count"] = int(state.get("log_count") or 0) + 1
        elif phase == "complete":
            logs = list(state.get("logs") or [])
            logs.append("[done] Fetch completed")
            if len(logs) > 300:
                logs = logs[-300:]
            state["logs"] = logs
            state["log_count"] = int(state.get("log_count") or 0) + 1


def _extract_progress_finish(owner: str, summary: str, errors: list[str]) -> None:
    with _EXTRACT_PROGRESS_LOCK:
        state = _EXTRACT_PROGRESS_BY_OWNER.get(owner)
        if not state:
            return
        state["running"] = False
        state["phase"] = "finished"
        state["message"] = "Comprehensive extract completed"
        state["finished_at"] = _utc_now_iso()
        state["updated_at"] = state["finished_at"]
        logs = list(state.get("logs") or [])
        logs.append(f"[done] {summary}")
        for err in (errors or [])[:20]:
            logs.append(f"[error] {err}")
        if len(logs) > 300:
            logs = logs[-300:]
        state["logs"] = logs
        state["log_count"] = int(state.get("log_count") or 0) + 1 + min(len(errors or []), 20)


def _extract_progress_fail(owner: str, message: str) -> None:
    with _EXTRACT_PROGRESS_LOCK:
        state = _EXTRACT_PROGRESS_BY_OWNER.get(owner)
        if not state:
            state = {
                "running": False,
                "phase": "failed",
                "message": message,
                "started_at": None,
                "finished_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
                "logs": [f"[fatal] {message}"],
                "log_count": 1,
                "activities": {"processed": 0, "total": 0, "day": None},
                "wellness": {"current": 0, "total": 0, "day": None},
            }
            _EXTRACT_PROGRESS_BY_OWNER[owner] = state
            return
        state["running"] = False
        state["phase"] = "failed"
        state["message"] = message
        state["finished_at"] = _utc_now_iso()
        state["updated_at"] = state["finished_at"]
        logs = list(state.get("logs") or [])
        logs.append(f"[fatal] {message}")
        if len(logs) > 300:
            logs = logs[-300:]
        state["logs"] = logs
        state["log_count"] = int(state.get("log_count") or 0) + 1


def _run_comprehensive_extract_background(
    *,
    owner: str,
    db_path: Path,
    garmin_email: str,
    garmin_password: str,
    start_day: date,
    end_day: date,
    include_details: bool,
    include_wellness: bool,
) -> None:
    try:
        extract = fetch_garmin_comprehensive(
            email=garmin_email,
            password=garmin_password,
            start_day=start_day,
            end_day=end_day,
            include_activity_details=bool(include_details),
            include_splits=bool(include_details),
            include_wellness=bool(include_wellness),
            raw_export_dir=None,
            progress_cb=lambda evt: _extract_progress_event(owner, evt),
        )
        _extract_progress_append(
            owner,
            (
                f"[fetch:done] activities={len(extract.activities)} details={len(extract.activity_details)} "
                f"records={len(extract.activity_records)} splits={len(extract.activity_splits)} "
                f"sleep={len(extract.sleep_daily)} wellness={len(extract.wellness_daily)} errors={len(extract.errors)}"
            ),
        )
        _extract_progress_append(owner, "[db] upserting activities/details/records/splits/sleep/wellness")
        n_a = upsert_activities(db_path, extract.activities)
        n_d = upsert_activity_details(db_path, extract.activity_details)
        n_r = upsert_activity_records(db_path, extract.activity_records)
        n_sp = upsert_activity_splits(db_path, extract.activity_splits)
        n_s = upsert_sleep_daily(db_path, extract.sleep_daily)
        n_w = upsert_wellness_daily(db_path, extract.wellness_daily)
        _extract_progress_append(
            owner,
            (
                f"[db:done] activities={n_a} details={n_d} records={n_r} "
                f"splits={n_sp} sleep={n_s} wellness={n_w}"
            ),
        )
        msg = (
            f"activities={len(extract.activities)}({n_a}), details={len(extract.activity_details)}({n_d}), "
            f"records={len(extract.activity_records)}({n_r}), splits={len(extract.activity_splits)}({n_sp}), "
            f"sleep={len(extract.sleep_daily)}({n_s}), wellness={len(extract.wellness_daily)}({n_w}), errors={len(extract.errors)}"
        )
        log_sync(db_path, source="v2_garmin_comprehensive", success=True, message=msg)
        _extract_progress_finish(owner, msg, extract.errors[:40])
    except Exception as exc:
        _extract_progress_fail(owner, str(exc))
        log_sync(db_path, source="v2_garmin_comprehensive", success=False, message=str(exc))


def _default_lthr_curve() -> list[dict[str, object]]:
    return [{"date": "2025-01-01", "lthr_bpm": DEFAULT_LTHR}]


def _default_lt_pace_curve() -> list[dict[str, object]]:
    return [{"date": "2025-01-01", "lt_pace_sec_per_km": DEFAULT_THRESHOLD_PACE_SEC_PER_KM}]


def _default_if_zone_thresholds() -> dict[str, float]:
    return {"z1_max": 0.70, "z2_max": 0.80, "z3_max": 0.90, "z4_max": 1.00}


def _normalize_if_zone_thresholds(payload: dict[str, object] | None) -> dict[str, float]:
    defaults = _default_if_zone_thresholds()
    if not isinstance(payload, dict):
        return defaults
    out = dict(defaults)
    for key in ["z1_max", "z2_max", "z3_max", "z4_max"]:
        try:
            if key in payload and payload.get(key) is not None:
                out[key] = float(payload.get(key))
        except Exception:
            continue
    out["z1_max"] = float(min(max(out["z1_max"], 0.01), 3.0))
    out["z2_max"] = float(min(max(out["z2_max"], out["z1_max"] + 0.01), 3.0))
    out["z3_max"] = float(min(max(out["z3_max"], out["z2_max"] + 0.01), 3.0))
    out["z4_max"] = float(min(max(out["z4_max"], out["z3_max"] + 0.01), 3.0))
    return out


def _normalize_lthr_curve(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    parsed: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_raw = str(row.get("date") or "").strip()
        if not date_raw:
            continue
        try:
            parsed_date = datetime.fromisoformat(date_raw).date().isoformat()
            lthr = float(row.get("lthr_bpm"))
        except Exception:
            continue
        if lthr <= 0:
            continue
        parsed.append((parsed_date, lthr))
    if not parsed:
        return _default_lthr_curve()
    parsed = sorted(dict(parsed).items(), key=lambda item: item[0])
    return [{"date": d, "lthr_bpm": round(v, 2)} for d, v in parsed]


def _normalize_lt_pace_curve(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    parsed: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_raw = str(row.get("date") or "").strip()
        if not date_raw:
            continue
        try:
            parsed_date = datetime.fromisoformat(date_raw).date().isoformat()
            v_raw = row.get("lt_pace_sec_per_km")
            if v_raw is None and row.get("lt_pace") is not None:
                v_raw = _pace_mmss_to_sec(str(row.get("lt_pace")))
            pace_sec = float(v_raw)
        except Exception:
            continue
        if pace_sec <= 0:
            continue
        parsed.append((parsed_date, pace_sec))
    if not parsed:
        return _default_lt_pace_curve()
    parsed = sorted(dict(parsed).items(), key=lambda item: item[0])
    return [{"date": d, "lt_pace_sec_per_km": round(v, 2)} for d, v in parsed]


def _normalize_injury_windows(rows: list[dict[str, object]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip() or "injury"
        sev = str(row.get("severity") or "injury").strip().lower()
        if sev not in {"injury", "light_injury"}:
            sev = "injury"
        try:
            start = datetime.fromisoformat(str(row.get("start") or "").strip()).date()
            end = datetime.fromisoformat(str(row.get("end") or "").strip()).date()
        except Exception:
            continue
        if end < start:
            start, end = end, start
        out.append(
            {
                "label": label,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "severity": sev,
            }
        )
    return out


def _garmin_credentials_from_env() -> tuple[str, str]:
    email = str(os.getenv("GARMIN_EMAIL") or "").strip()
    password = str(os.getenv("GARMIN_PASSWORD") or "").strip()
    return email, password


def _set_runtime_garmin_credentials(owner: str, email: str, password: str) -> None:
    with _GARMIN_RUNTIME_CREDENTIALS_LOCK:
        _GARMIN_RUNTIME_CREDENTIALS_BY_OWNER[owner] = {
            "email": str(email or "").strip(),
            "password": str(password or "").strip(),
            "updated_at": _utc_now_iso(),
        }


def _clear_runtime_garmin_credentials(owner: str) -> None:
    with _GARMIN_RUNTIME_CREDENTIALS_LOCK:
        _GARMIN_RUNTIME_CREDENTIALS_BY_OWNER.pop(owner, None)


def _runtime_garmin_credentials(owner: str) -> tuple[str, str]:
    with _GARMIN_RUNTIME_CREDENTIALS_LOCK:
        payload = _GARMIN_RUNTIME_CREDENTIALS_BY_OWNER.get(owner) or {}
    return str(payload.get("email") or "").strip(), str(payload.get("password") or "").strip()


def _resolve_garmin_credentials(ctx: dict[str, str], owner: str) -> tuple[str, str, str]:
    role = str(ctx.get("role") or "viewer").strip().lower()
    current_user = str(ctx.get("user") or "").strip()
    if role == "admin" and owner == current_user:
        env_email, env_password = _garmin_credentials_from_env()
        if env_email and env_password:
            return env_email, env_password, "env"
        runtime_email, runtime_password = _runtime_garmin_credentials(owner)
        if runtime_email and runtime_password:
            return runtime_email, runtime_password, "session"
        return "", "", "missing"

    runtime_email, runtime_password = _runtime_garmin_credentials(owner)
    if runtime_email and runtime_password:
        return runtime_email, runtime_password, "session"
    return "", "", "missing"


def _lt_target_from_regression(lt_pace_sec_per_km: float, value_index: int) -> float:
    points = sorted(LT_PACE_TO_WEEKLY_TARGET_POINTS, key=lambda p: p[0], reverse=True)
    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[value_index] for p in points], dtype=float)
    pace = float(max(1.0, lt_pace_sec_per_km))
    if pace >= x[0]:
        slope = (y[1] - y[0]) / (x[1] - x[0])
        return float(y[0] + slope * (pace - x[0]))
    if pace <= x[-1]:
        slope = (y[-1] - y[-2]) / (x[-1] - x[-2])
        return float(y[-1] + slope * (pace - x[-1]))
    coeff = np.polyfit(x, y, 3)
    return float(np.polyval(coeff, pace))


def _weekly_tss_target_from_lt_pace(lt_pace_sec_per_km: float) -> float:
    return max(_lt_target_from_regression(lt_pace_sec_per_km, value_index=2), 0.0)


def _weekly_distance_target_from_lt_pace(lt_pace_sec_per_km: float) -> float:
    return max(_lt_target_from_regression(lt_pace_sec_per_km, value_index=1), 0.0)


def _week_start_monday(ts: pd.Timestamp) -> pd.Timestamp:
    return (ts - pd.Timedelta(days=int(ts.weekday()))).normalize()


def _default_specificity_profile(default_non_running: float = 0.8) -> dict[str, float]:
    d = float(min(max(default_non_running, 0.0), 1.5))
    return {
        "non_running": d,
        "treadmill": 1.0,
        "elliptical": d,
        "cycling": d,
    }


def _normalize_specificity_profile(
    payload: dict[str, object] | None,
    fallback_default: float = 0.8,
) -> dict[str, float]:
    base = _default_specificity_profile(fallback_default)
    if not isinstance(payload, dict):
        return base
    out = dict(base)
    legacy_default = payload.get("default_non_running")
    if legacy_default is not None and "non_running" not in payload:
        payload = dict(payload)
        payload["non_running"] = legacy_default
    for key in out.keys():
        try:
            if key in payload and payload.get(key) is not None:
                out[key] = float(min(max(float(payload.get(key)), 0.0), 1.5))
        except Exception:
            continue
    return out


def _load_specificity_profile(db_path: Path, fallback_default: float = 0.8) -> dict[str, float]:
    raw = get_setting(db_path, SETTINGS_KEY_ACTIVITY_SPECIFICITY)
    if not raw:
        return _default_specificity_profile(fallback_default)
    try:
        payload = json.loads(raw)
    except Exception:
        return _default_specificity_profile(fallback_default)
    return _normalize_specificity_profile(payload, fallback_default=fallback_default)


def _specificity_factor_for_plan_kind(kind: str | None, profile: dict[str, float]) -> float:
    k = str(kind or "").strip().lower()
    if k == "run":
        return 1.0
    if k == "treadmill":
        return float(profile.get("treadmill", 1.0))
    if k == "elliptical":
        return float(profile.get("elliptical", profile.get("non_running", 0.8)))
    if k == "cycling":
        return float(profile.get("cycling", profile.get("non_running", 0.8)))
    return float(profile.get("non_running", 0.8))


def _specificity_factor_for_sport(sport_type: str | None, profile: dict[str, float]) -> float:
    sport = str(sport_type or "").strip().lower()
    if ("run" in sport) and ("treadmill" not in sport):
        return 1.0
    if "treadmill" in sport:
        return float(profile.get("treadmill", 1.0))
    if "elliptical" in sport:
        return float(profile.get("elliptical", profile.get("non_running", 0.8)))
    if ("cycl" in sport) or ("bike" in sport):
        return float(profile.get("cycling", profile.get("non_running", 0.8)))
    return float(profile.get("non_running", 0.8))


def _apply_specificity_factor(df: pd.DataFrame, specificity_profile: dict[str, float]) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    sport = out["sport_type"].fillna("").astype(str).str.lower()
    out["specificity_factor"] = out["sport_type"].apply(
        lambda s: _specificity_factor_for_sport(s, specificity_profile)
    )
    is_running_like = sport.str.contains("run") | sport.str.contains("treadmill")

    if "distance_proxy_km" in out.columns:
        base_proxy_factor = 0.8
        proxy_mask = ~is_running_like
        if "distance_proxy_method" in out.columns:
            proxy_mask = proxy_mask & out["distance_proxy_method"].fillna("").astype(str).eq("tss_parity_root_solve")
        if proxy_mask.any():
            proxy_factor = pd.to_numeric(out.loc[proxy_mask, "specificity_factor"], errors="coerce").fillna(0.0)
            ratio = proxy_factor / float(base_proxy_factor) if base_proxy_factor > 0 else 1.0
            proxy_scale = ratio.pow(0.5)
            out.loc[proxy_mask, "distance_proxy_km"] = (
                pd.to_numeric(out.loc[proxy_mask, "distance_proxy_km"], errors="coerce").fillna(0.0).values
                * proxy_scale.values
            )
            if "pace_proxy_sec_per_km" in out.columns:
                pace_scale = 1.0 / proxy_scale.replace(0.0, pd.NA)
                out.loc[proxy_mask, "pace_proxy_sec_per_km"] = (
                    pd.to_numeric(out.loc[proxy_mask, "pace_proxy_sec_per_km"], errors="coerce").fillna(0.0).values
                    * pd.to_numeric(pace_scale, errors="coerce").fillna(0.0).values
                )

    factor_cols = [
        "distance_m",
        "rtss",
        "tss",
        "mechanical_load",
        "training_load_garmin",
        "calories_active",
        "calories_total",
        "intensity_minutes_vigorous",
        "intensity_minutes_moderate",
        "hr_time_in_zone_1",
        "hr_time_in_zone_2",
        "hr_time_in_zone_3",
        "hr_time_in_zone_4",
        "hr_time_in_zone_5",
    ]
    for col in factor_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0) * out["specificity_factor"]
    return out


def _curve_value_at(
    points: list[tuple[datetime, float]],
    default_value: float,
    at_dt: datetime | pd.Timestamp | None,
) -> float:
    if at_dt is None or pd.isna(at_dt):
        return float(default_value)
    ts = at_dt.to_pydatetime() if isinstance(at_dt, pd.Timestamp) else at_dt
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    chosen = float(default_value)
    for d, v in points:
        d_cmp = d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo is not None else d
        if d_cmp <= ts:
            chosen = float(v)
        else:
            break
    return float(chosen)


def _pace_mmss_to_sec(value: str) -> float:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError("invalid pace format")
    minutes = int(parts[0])
    seconds = int(parts[1])
    total = minutes * 60 + seconds
    if total <= 0:
        raise ValueError("pace must be > 0")
    return float(total)


def _plan_activity_kind(text: str) -> str:
    t = str(text or "").lower()
    if "treadmill" in t:
        return "treadmill"
    if "run" in t:
        return "run"
    if "ellipt" in t:
        return "elliptical"
    if "cycl" in t or "bike" in t:
        return "cycling"
    return "other"


def _parse_minutes_token(text: str) -> float | None:
    t = str(text or "").lower().strip()
    hm = re.search(r"(\d+(?:\.\d+)?)\s*h(?:\s*(\d+(?:\.\d+)?)\s*m(?:in)?)?", t)
    if hm:
        h = float(hm.group(1))
        m = float(hm.group(2)) if hm.group(2) else 0.0
        total = h * 60.0 + m
        return total if total > 0 else None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes)\b", t)
    if m:
        total = float(m.group(1))
        return total if total > 0 else None
    q = re.search(r"(\d+(?:\.\d+)?)\s*[\'’](?=\D|$)", t)
    if q:
        total = float(q.group(1))
        return total if total > 0 else None
    s = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b", t)
    if s:
        total = float(s.group(1)) / 60.0
        return total if total > 0 else None
    return None


def _normalize_activity_id(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    # Guard against float-like ids coming from dataframe coercion, e.g. "21901941858.0".
    if raw.endswith(".0"):
        head = raw[:-2]
        if head.isdigit():
            return head
    return raw


def _parse_custom_activity_id(activity_id: str) -> tuple[str, int] | None:
    raw = _normalize_activity_id(activity_id)
    match = re.match(r"^custom-(\d{4}-\d{2}-\d{2})-(\d+)$", raw)
    if not match:
        return None
    day_utc = str(match.group(1))
    line_no = int(match.group(2))
    if line_no <= 0:
        return None
    return day_utc, line_no


def _parse_planned_activity_id(activity_id: str) -> tuple[str, int] | None:
    raw = _normalize_activity_id(activity_id)
    match = re.match(r"^planned-(\d{4}-\d{2}-\d{2})-(\d+)$", raw)
    if not match:
        return None
    day_utc = str(match.group(1))
    line_no = int(match.group(2))
    if line_no <= 0:
        return None
    return day_utc, line_no


def _parse_distance_km_token(text: str) -> float | None:
    lower = str(text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*km\b", lower)
    if m:
        try:
            km = float(m.group(1))
        except Exception:
            return None
        return km if km > 0 else None
    m_meters = re.search(r"(\d+(?:\.\d+)?)\s*m\b", lower)
    if not m_meters:
        return None
    try:
        meters = float(m_meters.group(1))
    except Exception:
        return None
    km = meters / 1000.0
    return km if km > 0 else None


def _parse_bpm_token(text: str) -> float | None:
    lower = str(text or "").lower()
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*bpm", lower)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*bpm", lower)
    if m:
        v = float(m.group(1))
        return v if v > 0 else None
    return None


def _parse_pace_token(text: str) -> float | None:
    lower = str(text or "").lower()
    m = re.search(r"@\s*(\d{1,2}:\d{2})(?:\s*/?\s*km)?", lower)
    if not m:
        m = re.search(r"(\d{1,2}:\d{2})\s*/\s*km", lower)
    if not m:
        return None
    try:
        return _pace_mmss_to_sec(m.group(1))
    except Exception:
        return None


def _parse_if_token(text: str) -> float | None:
    lower = str(text or "").lower()
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*%", lower)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", lower)
    if not m:
        return None
    try:
        v = float(m.group(1)) / 100.0
    except Exception:
        return None
    return v if v > 0 else None


def _parse_tss_token(text: str) -> float | None:
    lower = str(text or "").lower()
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*tss\b", lower)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*tss\b", lower)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except Exception:
        return None
    return v if v > 0 else None


def _normalize_plan_text(text: str) -> str:
    t = " ".join(str(text or "").strip().split())
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes)\b", r"\1min", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*[\'’](?=\D|$)", r"\1min", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b", r"\1s", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*h\b", r"\1h", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*km\b", r"\1km", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*m\b", r"\1m", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*bpm\b", r"\1bpm", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*/\s*km\b", "/km", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\+\s*", " + ", t)
    return t


def _strip_meridiem_tokens(text: str) -> tuple[str, str | None]:
    raw = str(text or "")
    token_matches = re.findall(r"(?<![A-Za-z0-9_])(AM|PM)(?![A-Za-z0-9_])", raw, flags=re.IGNORECASE)
    hint = str(token_matches[-1]).upper() if token_matches else None
    cleaned = re.sub(r"(?<![A-Za-z0-9_])(AM|PM)(?![A-Za-z0-9_])", " ", raw, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.strip().split())
    return cleaned, hint


def _parse_dated_activity_entry(text: str) -> tuple[pd.Timestamp | None, str, str | None]:
    raw = str(text or "").strip()
    if not raw:
        return None, "", "Input is empty. Use `[date]:[activity]`."
    if ":" in raw:
        date_text, activity_text = raw.split(":", 1)
    else:
        compact_match = re.match(r"^\s*([tT][+-]\d)(.+)$", raw)
        if compact_match:
            date_text = compact_match.group(1)
            activity_text = compact_match.group(2)
        else:
            return None, "", "Missing `:` separator. Use `[date]:[activity]`."
    date_text = date_text.strip()
    activity_text = activity_text.strip()
    date_text, date_hint = _strip_meridiem_tokens(date_text)
    activity_text, activity_hint = _strip_meridiem_tokens(activity_text)
    merged_hint = activity_hint or date_hint
    if merged_hint:
        activity_text = f"{activity_text} {merged_hint}".strip()
    activity_text = _normalize_plan_text(activity_text)
    if not date_text:
        return None, "", "Missing date before `:`."
    if not activity_text:
        return None, "", "Missing activity after `:`."

    date_value: pd.Timestamp | None = None
    date_key = date_text.strip().lower()
    if date_key in {"today", "tomorrow", "yesterday", "t"}:
        base_local = pd.Timestamp(datetime.now().astimezone().date())
        if date_key in {"today", "t"}:
            date_value = base_local
        elif date_key == "tomorrow":
            date_value = base_local + pd.Timedelta(days=1)
        else:
            date_value = base_local - pd.Timedelta(days=1)
    else:
        t_offset_match = re.match(r"^t([+-]\d+)$", date_key)
        if t_offset_match:
            try:
                offset_days = int(t_offset_match.group(1))
            except Exception:
                offset_days = 0
            base_local = pd.Timestamp(datetime.now().astimezone().date())
            date_value = base_local + pd.Timedelta(days=offset_days)

    for fmt in ("%d%b%y", "%Y-%m-%d", "%d/%m/%Y"):
        if date_value is not None:
            break
        try:
            date_value = pd.Timestamp(datetime.strptime(date_text, fmt))
            break
        except Exception:
            continue
    if date_value is None:
        return None, activity_text, (
            "Invalid date format. Use one of: `today`, `tomorrow`, `yesterday`, `T`, `T+1`, `T-1`, "
            "`3Mar26`, `2026-03-26`, `26/03/2026`."
        )
    return date_value, activity_text, None


def _split_dated_activity_entries(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    return [p.strip() for p in re.split(r"[\n;,]+", raw) if p.strip()]


def _planned_row_signature(day_utc: str, workout_text: str) -> str:
    day_key = str(day_utc or "").strip()
    workout_key = _normalize_plan_text(str(workout_text or "")).lower()
    return f"{day_key}::{workout_key}"


def _expand_planned_segments(
    line: str,
    lthr_bpm: float | None = None,
    threshold_pace_sec_per_km: float | None = None,
) -> tuple[list[dict[str, float | str | None]], list[str]]:
    segments: list[dict[str, float | str | None]] = []
    warnings: list[str] = []
    raw = _normalize_plan_text(line)
    raw, line_time_hint = _strip_meridiem_tokens(raw)
    if not raw:
        return segments, warnings
    lthr_value = float(lthr_bpm or 0.0)
    threshold_pace_value = float(threshold_pace_sec_per_km or 0.0)

    chunks = [c.strip() for c in re.split(r"\s*\+\s*", raw) if c.strip()]
    last_kind: str | None = None
    for chunk in chunks:
        kind = _plan_activity_kind(chunk)
        bpm = _parse_bpm_token(chunk)
        pace = _parse_pace_token(chunk)
        if_input = _parse_if_token(chunk)
        if_input_source: str | None = "explicit" if if_input is not None else None
        tss_input = _parse_tss_token(chunk)
        if kind == "other" and pace is not None:
            kind = "run"
        if kind == "other" and last_kind is not None:
            kind = last_kind
        if kind == "other":
            warnings.append(f"Missing/unknown activity in: `{chunk}` (include run/treadmill/elliptical/cycling)")
            continue
        is_running_like = kind in {"run", "treadmill"}
        if (not is_running_like) and (pace is not None):
            warnings.append(
                f"Pace is only allowed for running/treadmill in: `{chunk}` (use `@140bpm` or `@70%` for non-running)."
            )
            continue
        if bpm is None and pace is None and if_input is None and tss_input is None:
            warnings.append(f"Missing intensity in: `{chunk}` (add `@140bpm`, `@70%`, `@4:50/km`, or `@40TSS`)")
            continue

        rep_match = re.search(
            r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|min|mins|minute|minutes|s|sec|secs|second|seconds)\b",
            chunk.lower(),
        )
        if rep_match:
            reps = int(rep_match.group(1))
            rep_value = float(rep_match.group(2))
            rep_unit = rep_match.group(3)
            rep_minutes = rep_value * 60.0 if rep_unit.startswith("h") else (rep_value / 60.0 if rep_unit.startswith("s") else rep_value)
            if reps <= 0 or rep_minutes <= 0:
                warnings.append(f"Invalid interval block in: `{chunk}`")
                continue
            if tss_input is not None and tss_input > 0 and bpm is None and pace is None and if_input is None:
                seg_duration_h = rep_minutes / 60.0
                per_rep_tss = float(tss_input) / float(max(reps, 1))
                if seg_duration_h > 0:
                    derived_if = (per_rep_tss / (seg_duration_h * 100.0)) ** 0.5
                    if_input = max(float(derived_if), 0.0)
                    if_input_source = "tss_derived"
                    if is_running_like and pace is None and threshold_pace_value > 0 and if_input > 0:
                        pace = threshold_pace_value / if_input
                    elif (not is_running_like) and bpm is None and lthr_value > 0 and if_input > 0:
                        bpm = lthr_value * if_input
            for _ in range(max(reps, 0)):
                segments.append(
                    {
                        "kind": kind,
                        "duration_min": rep_minutes,
                        "avg_hr_bpm": bpm,
                        "pace_s_per_km": pace,
                        "if_input": if_input,
                        "if_input_source": if_input_source,
                        "tss_target": (float(tss_input) / float(max(reps, 1))) if tss_input else None,
                        "time_hint": line_time_hint,
                        "source": chunk,
                    }
                )
            last_kind = kind
            continue

        minutes = _parse_minutes_token(chunk)
        if minutes is None:
            distance_km = _parse_distance_km_token(chunk)
            if distance_km is not None:
                if not is_running_like:
                    warnings.append(
                        f"Distance-only segment requires running/treadmill with pace in: `{chunk}` (non-running should use minutes + bpm/%IF)."
                    )
                    continue
                if pace is None and tss_input is not None and tss_input > 0 and threshold_pace_value > 0:
                    pace = (distance_km * (threshold_pace_value**2) * 100.0) / (3600.0 * float(tss_input))
                    if pace > 0:
                        if_input = threshold_pace_value / pace
                if pace is None or pace <= 0:
                    warnings.append(f"Distance-based segment requires pace in: `{chunk}` (add `@4:50/km`)")
                    continue
                minutes = (distance_km * pace) / 60.0
        if minutes is None:
            warnings.append(f"Could not parse duration from: `{chunk}`")
            continue
        if minutes <= 0:
            warnings.append(f"Duration must be > 0 in: `{chunk}`")
            continue
        if tss_input is not None and tss_input > 0 and bpm is None and pace is None and if_input is None:
            duration_h = float(minutes) / 60.0
            if duration_h <= 0:
                warnings.append(f"TSS-based intensity requires positive duration in: `{chunk}`")
                continue
            derived_if = (float(tss_input) / (duration_h * 100.0)) ** 0.5
            if_input = max(float(derived_if), 0.0)
            if_input_source = "tss_derived"
            if is_running_like:
                if threshold_pace_value <= 0:
                    warnings.append(f"Missing LT pace to convert TSS to pace in: `{chunk}`")
                    continue
                if if_input > 0:
                    pace = threshold_pace_value / if_input
            else:
                if lthr_value <= 0:
                    warnings.append(f"Missing LTHR to convert TSS to HR in: `{chunk}`")
                    continue
                bpm = lthr_value * if_input
        segments.append(
            {
                "kind": kind,
                "duration_min": minutes,
                "avg_hr_bpm": bpm,
                "pace_s_per_km": pace,
                "if_input": if_input,
                "if_input_source": if_input_source,
                "tss_target": float(tss_input) if tss_input else None,
                "time_hint": line_time_hint,
                "source": chunk,
            }
        )
        last_kind = kind
    return segments, warnings


def _planned_segment_metrics(
    seg: dict[str, float | str | None],
    lthr_bpm: float,
    threshold_pace_sec_per_km: float,
    non_running_factor: float,
) -> dict[str, float]:
    duration_min = float(seg.get("duration_min") or 0.0)
    duration_s = max(duration_min * 60.0, 0.0)
    duration_h = duration_s / 3600.0 if duration_s > 0 else 0.0
    kind = str(seg.get("kind") or "other").lower()
    hr = float(seg.get("avg_hr_bpm")) if seg.get("avg_hr_bpm") else None
    pace = float(seg.get("pace_s_per_km")) if seg.get("pace_s_per_km") else None
    if_input = float(seg.get("if_input")) if seg.get("if_input") else None

    is_running_like = kind in {"run", "treadmill"}
    rtss = 0.0
    tss = 0.0
    distance_eqv_km = 0.0
    if_proxy = 0.0

    if duration_h <= 0:
        return {
            "duration_s": 0.0,
            "rtss": 0.0,
            "tss": 0.0,
            "distance_eqv_km": 0.0,
            "if_proxy": 0.0,
        }

    if is_running_like and pace and pace > 0:
        if_proxy = max(threshold_pace_sec_per_km / pace, 0.0)
        rtss = duration_h * (if_proxy**2) * 100.0
        distance_eqv_km = duration_s / pace
        if hr and lthr_bpm > 0:
            if_hr = max(hr / lthr_bpm, 0.0)
            tss = duration_h * (if_hr**2) * 100.0
        else:
            tss = rtss
    elif is_running_like and if_input and if_input > 0:
        if_proxy = max(float(if_input), 0.0)
        rtss = duration_h * (if_proxy**2) * 100.0
        tss = rtss
        if threshold_pace_sec_per_km > 0 and if_proxy > 0:
            eq_pace = threshold_pace_sec_per_km / if_proxy
            if eq_pace > 0:
                distance_eqv_km = duration_s / eq_pace
    else:
        if hr and lthr_bpm > 0:
            if_hr = max(hr / lthr_bpm, 0.0)
            tss = duration_h * (if_hr**2) * 100.0
            if_proxy = if_hr
            effective_rtss = max(tss * max(non_running_factor, 0.0), 0.0)
            if effective_rtss > 0:
                eq_if = (effective_rtss / (duration_h * 100.0)) ** 0.5
                if eq_if > 0:
                    eq_pace = threshold_pace_sec_per_km / eq_if
                    if eq_pace > 0:
                        distance_eqv_km = duration_s / eq_pace
        elif if_input and if_input > 0:
            if_proxy = max(float(if_input), 0.0)
            tss = duration_h * (if_proxy**2) * 100.0
            effective_rtss = max(tss * max(non_running_factor, 0.0), 0.0)
            if effective_rtss > 0:
                eq_if = (effective_rtss / (duration_h * 100.0)) ** 0.5
                if eq_if > 0:
                    eq_pace = threshold_pace_sec_per_km / eq_if
                    if eq_pace > 0:
                        distance_eqv_km = duration_s / eq_pace
        elif pace and pace > 0:
            if_proxy = max(threshold_pace_sec_per_km / pace, 0.0)
            tss = duration_h * (if_proxy**2) * 100.0
            effective_rtss = max(tss * max(non_running_factor, 0.0), 0.0)
            if effective_rtss > 0:
                eq_if = (effective_rtss / (duration_h * 100.0)) ** 0.5
                if eq_if > 0:
                    eq_pace = threshold_pace_sec_per_km / eq_if
                    if eq_pace > 0:
                        distance_eqv_km = duration_s / eq_pace

    return {
        "duration_s": float(duration_s),
        "rtss": float(rtss),
        "tss": float(tss),
        "distance_eqv_km": float(distance_eqv_km),
        "if_proxy": float(if_proxy),
    }


def _segment_with_effective_intensity_for_metrics(
    seg: dict[str, float | str | None],
    seg_kind: str,
    seg_spec: float,
) -> dict[str, float | str | None]:
    seg_for_metrics = dict(seg)
    if seg_kind in {"run", "treadmill"}:
        return seg_for_metrics
    if_input_source = str(seg_for_metrics.get("if_input_source") or "").strip().lower()
    if if_input_source != "tss_derived":
        source_text = str(seg_for_metrics.get("source") or "").lower()
        has_tss = bool(re.search(r"@\s*\d+(?:\.\d+)?\s*tss\b", source_text))
        has_bpm = bool(re.search(r"@\s*\d+(?:\.\d+)?\s*bpm\b", source_text))
        has_if_pct = bool(re.search(r"@\s*\d+(?:\.\d+)?\s*%", source_text))
        has_pace = bool(re.search(r"@\s*\d{1,2}:\d{2}\s*/?\s*km\b", source_text))
        if not (has_tss and (not has_bpm) and (not has_if_pct) and (not has_pace)):
            return seg_for_metrics
    tss_target = pd.to_numeric(pd.Series([seg_for_metrics.get("tss_target")]), errors="coerce").fillna(0.0).iloc[0]
    duration_min = pd.to_numeric(pd.Series([seg_for_metrics.get("duration_min")]), errors="coerce").fillna(0.0).iloc[0]
    spec = float(max(seg_spec, 0.0))
    duration_h = float(max(duration_min, 0.0)) / 60.0
    if spec <= 0 or duration_h <= 0 or float(tss_target) <= 0:
        return seg_for_metrics
    unscaled_tss_target = float(tss_target) / spec
    derived_if = (unscaled_tss_target / (duration_h * 100.0)) ** 0.5
    if derived_if > 0:
        seg_for_metrics["if_input"] = float(derived_if)
        seg_for_metrics["avg_hr_bpm"] = None
        seg_for_metrics["pace_s_per_km"] = None
    return seg_for_metrics


def _compute_planned_rows_metrics_df(
    planned_rows: pd.DataFrame,
    lthr_curve_points: list[tuple[datetime, float]],
    lthr_default_bpm: float,
    lt_pace_curve_points: list[tuple[datetime, float]],
    lt_pace_default_sec: float,
    specificity_profile: dict[str, float],
) -> pd.DataFrame:
    if planned_rows.empty:
        return pd.DataFrame(columns=["day_utc", "tss", "rtss", "distance_proxy_km", "duration_s", "if_proxy"])

    out = planned_rows.copy()
    tss_vals: list[float] = []
    rtss_vals: list[float] = []
    dist_eqv_vals: list[float] = []
    if_vals: list[float] = []
    pace_proxy_vals: list[float] = []
    dur_vals: list[float] = []
    for _, row in out.iterrows():
        raw_segments = row.get("parsed_json")
        segments: list[dict[str, float | str | None]] = []
        if isinstance(raw_segments, list):
            segments = [s for s in raw_segments if isinstance(s, dict)]
        elif isinstance(raw_segments, str) and raw_segments.strip():
            try:
                parsed = json.loads(raw_segments)
                if isinstance(parsed, list):
                    segments = [s for s in parsed if isinstance(s, dict)]
            except Exception:
                segments = []

        day_for_curve = pd.to_datetime(row.get("day_utc"), utc=True, errors="coerce")
        lthr_for_day = float(_curve_value_at(lthr_curve_points, float(lthr_default_bpm), day_for_curve))
        lt_pace_for_day = float(_curve_value_at(lt_pace_curve_points, float(lt_pace_default_sec), day_for_curve))

        total_tss = 0.0
        total_rtss = 0.0
        total_dist_eqv = 0.0
        if_weighted_sum = 0.0
        if_weight_seconds = 0.0
        for seg in segments:
            seg_kind = str(seg.get("kind") or "").strip().lower()
            seg_spec = _specificity_factor_for_plan_kind(seg_kind, specificity_profile)
            seg_for_metrics = _segment_with_effective_intensity_for_metrics(seg, seg_kind=seg_kind, seg_spec=seg_spec)
            m = _planned_segment_metrics(
                seg_for_metrics,
                lthr_bpm=lthr_for_day,
                threshold_pace_sec_per_km=lt_pace_for_day,
                non_running_factor=seg_spec,
            )
            seg_duration = float(m.get("duration_s") or 0.0)
            seg_if = float(m.get("if_proxy") or 0.0)
            total_tss += float(m.get("tss") or 0.0) * float(seg_spec)
            total_rtss += float(m.get("rtss") or 0.0) * float(seg_spec)
            total_dist_eqv += float(m.get("distance_eqv_km") or 0.0)
            if seg_duration > 0:
                if_weighted_sum += seg_if * seg_duration
                if_weight_seconds += seg_duration

        tss_vals.append(total_tss)
        rtss_vals.append(total_rtss)
        dist_eqv_vals.append(total_dist_eqv)
        dur_vals.append(if_weight_seconds)
        row_if = if_weighted_sum / if_weight_seconds if if_weight_seconds > 0 else 0.0
        if_vals.append(row_if)
        if row_if > 0 and lt_pace_for_day > 0:
            pace_proxy_vals.append(float(lt_pace_for_day / row_if))
        else:
            pace_proxy_vals.append(0.0)

    out["tss"] = tss_vals
    out["rtss"] = rtss_vals
    out["distance_proxy_km"] = dist_eqv_vals
    out["duration_s"] = dur_vals
    out["if_proxy"] = if_vals
    out["pace_proxy_sec_per_km"] = pace_proxy_vals
    return out


def _planned_row_time_hint(row: pd.Series) -> str | None:
    raw_segments = row.get("parsed_json")
    segments: list[dict[str, object]] = []
    if isinstance(raw_segments, list):
        segments = [s for s in raw_segments if isinstance(s, dict)]
    elif isinstance(raw_segments, str) and raw_segments.strip():
        try:
            parsed = json.loads(raw_segments)
            if isinstance(parsed, list):
                segments = [s for s in parsed if isinstance(s, dict)]
        except Exception:
            segments = []

    for seg in segments:
        hint = str(seg.get("time_hint") or "").strip().upper()
        if hint in {"AM", "PM"}:
            return hint

    workout_text = str(row.get("workout_text") or "")
    _, hint = _strip_meridiem_tokens(workout_text)
    return hint if hint in {"AM", "PM"} else None


def _planned_row_expiry_local(day_local: pd.Timestamp, time_hint: str | None) -> pd.Timestamp:
    day_norm = pd.Timestamp(day_local).normalize()
    hint = str(time_hint or "").strip().upper()
    if hint == "AM":
        return day_norm + pd.Timedelta(hours=12)
    if hint == "PM":
        return day_norm + pd.Timedelta(hours=21)
    return day_norm + pd.Timedelta(days=1)


def _filter_effective_planned_rows(
    planned_df: pd.DataFrame,
    today_local_day: pd.Timestamp,
    now_local_ts: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if planned_df.empty:
        return planned_df.copy()

    out = planned_df.copy()
    day_col = pd.to_datetime(out.get("day_utc"), errors="coerce").dt.normalize()
    manual_done_col = pd.to_numeric(out.get("manual_done"), errors="coerce").fillna(0.0) > 0
    now_local = pd.Timestamp(now_local_ts) if now_local_ts is not None else _now_app_local()
    if now_local.tzinfo is not None:
        now_local = now_local.tz_localize(None)

    auto_done_flags: list[bool] = []
    for row_idx, row in out.iterrows():
        day_local = pd.to_datetime(day_col.loc[row_idx], errors="coerce")
        if pd.isna(day_local):
            auto_done_flags.append(False)
            continue
        hint = _planned_row_time_hint(row)
        expiry_local = _planned_row_expiry_local(day_local, hint)
        auto_done_flags.append(now_local >= expiry_local)

    auto_done_col = pd.Series(auto_done_flags, index=out.index, dtype=bool)
    done_col = manual_done_col | auto_done_col
    keep_mask = ~done_col
    return out.loc[keep_mask].copy()


def _planned_daily_metric_map(
    db_path: Path,
    week_start: pd.Timestamp,
    week_end: pd.Timestamp,
    metric_key: str,
    sport_filter: str | None = None,
    today_local_day: pd.Timestamp | None = None,
) -> tuple[dict[pd.Timestamp, float], dict[pd.Timestamp, float], float]:
    try:
        planned_rows = get_planned_activities_df(
            db_path=db_path,
            start_day_utc=week_start.date().isoformat(),
            end_day_utc=week_end.date().isoformat(),
        )
    except Exception:
        return {}, {}, 0.0
    if planned_rows.empty:
        return {}, {}, 0.0

    lthr_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LTHR_CURVE,
        value_key="lthr_bpm",
        fallback_value=DEFAULT_LTHR,
    )
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)
    metrics_rows = _compute_planned_rows_metrics_df(
        planned_rows=planned_rows,
        lthr_curve_points=lthr_curve,
        lthr_default_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
        lt_pace_curve_points=pace_curve,
        lt_pace_default_sec=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
        specificity_profile=specificity_profile,
    )
    if metrics_rows.empty:
        return {}, {}, 0.0

    if sport_filter:
        sf = str(sport_filter).strip().lower()
        if sf:
            activity_text = metrics_rows.get("workout_text", pd.Series(index=metrics_rows.index, dtype=object)).fillna("").astype(str).str.lower()
            metrics_rows = metrics_rows[activity_text.str.contains(sf)]

    metrics_rows["day"] = pd.to_datetime(metrics_rows["day_utc"], errors="coerce").dt.normalize()
    metrics_rows = metrics_rows.dropna(subset=["day"])
    if metrics_rows.empty:
        return {}, {}, 0.0

    # Week Planner compare bars must represent full planned load for each day.
    # Do not apply AM/PM expiry or manual-done filtering here.
    metrics_for_compare = metrics_rows.copy()

    metric_col = "distance_proxy_km" if metric_key == "distance_eqv_km" else metric_key
    metric_by_day = (
        metrics_for_compare.groupby("day", as_index=False)[metric_col]
        .sum()
        .set_index("day")[metric_col]
        .to_dict()
    )
    tss_by_day = (
        metrics_for_compare.groupby("day", as_index=False)["tss"]
        .sum()
        .set_index("day")["tss"]
        .to_dict()
    )

    today_local = pd.Timestamp(today_local_day if today_local_day is not None else datetime.now().astimezone().date()).normalize()
    remaining_start_day = max(today_local, pd.Timestamp(week_start).normalize())
    # Remaining-to-go should ignore AM/PM expiry and only honor explicit manual done.
    metrics_remaining = metrics_rows.copy()
    metrics_remaining["manual_done"] = pd.to_numeric(
        metrics_remaining.get("manual_done"),
        errors="coerce",
    ).fillna(0.0) > 0
    metrics_remaining = metrics_remaining.loc[~metrics_remaining["manual_done"]].copy()
    remaining_metric_total = 0.0
    if not metrics_remaining.empty:
        metrics_remaining["day"] = pd.to_datetime(metrics_remaining.get("day"), errors="coerce").dt.normalize()
        metrics_remaining = metrics_remaining.dropna(subset=["day"])
        metrics_remaining = metrics_remaining[
            (metrics_remaining["day"] >= remaining_start_day)
            & (metrics_remaining["day"] <= week_end)
        ].copy()
        remaining_metric_total = float(
            pd.to_numeric(metrics_remaining.get(metric_col), errors="coerce").fillna(0.0).sum()
        )

    return (
        {pd.Timestamp(k): float(v) for k, v in metric_by_day.items()},
        {pd.Timestamp(k): float(v) for k, v in tss_by_day.items()},
        float(remaining_metric_total),
    )


def _format_duration_short(duration_s: float) -> str:
    total_minutes = max(int(round(float(duration_s) / 60.0)), 0)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
    return f"{minutes}m"


def _format_pace_short(pace_s_per_km: float | None) -> str:
    if pace_s_per_km is None:
        return "-"
    pace_v = _safe_float(pace_s_per_km)
    if pace_v <= 0:
        return "-"
    mm = int(pace_v // 60)
    ss = int(round(pace_v - mm * 60))
    if ss == 60:
        mm += 1
        ss = 0
    return f"{mm}:{ss:02d}/km"


def _format_duration_compact_with_seconds(duration_s: float | int | None) -> str:
    total = max(int(round(_safe_float(duration_s))), 0)
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours > 0:
        return f"{hours}h{minutes:02d}'{seconds:02d}\""
    return f"{minutes}'{seconds:02d}\""


def _load_if_zone_thresholds(db_path: Path) -> dict[str, float]:
    raw = get_setting(db_path, SETTINGS_KEY_IF_ZONE_THRESHOLDS)
    if not raw:
        return _default_if_zone_thresholds()
    try:
        payload = json.loads(raw)
    except Exception:
        return _default_if_zone_thresholds()
    return _normalize_if_zone_thresholds(payload if isinstance(payload, dict) else None)


def _split_description_from_if_proxy(if_proxy: float | int | None, thresholds: dict[str, float]) -> str:
    v = _safe_float(if_proxy)
    if v <= 0:
        return "Recovery"
    z1 = float(thresholds.get("z1_max", 0.70))
    z2 = float(thresholds.get("z2_max", 0.80))
    z3 = float(thresholds.get("z3_max", 0.90))
    z4 = float(thresholds.get("z4_max", 1.00))
    if v < z1:
        return "Recovery"
    if v < z2:
        return "Easy"
    if v < z3:
        return "Steady"
    if v < z4:
        return "Threshold"
    return "VO2max"


def _zone_key_from_if_proxy(if_proxy: float | int | None, thresholds: dict[str, float]) -> str:
    v = _safe_float(if_proxy)
    if v <= 0:
        return "Z1"
    z1 = float(thresholds.get("z1_max", 0.75))
    z2 = float(thresholds.get("z2_max", 0.85))
    z3 = float(thresholds.get("z3_max", 0.95))
    z4 = float(thresholds.get("z4_max", 1.03))
    if v < z1:
        return "Z1"
    if v < z2:
        return "Z2"
    if v < z3:
        return "Z3"
    if v < z4:
        return "Z4"
    return "Z5"


def _activity_intensity_token(if_proxy: float, tss: float) -> str:
    if if_proxy <= 0:
        return "gray"
    thresholds = _normalize_if_zone_thresholds(None)
    if if_proxy < float(thresholds["z1_max"]):
        return "gray"
    if if_proxy < float(thresholds["z2_max"]):
        return "blue"
    if if_proxy < float(thresholds["z3_max"]):
        return "orange"
    if if_proxy < float(thresholds["z4_max"]):
        return "red"
    return "purple"


def _activity_palette_token(
    db_path: Path,
    if_proxy: float | int | None,
    tss_value: float | int | None,
    rtss_value: float | int | None,
    sport_type: str | None,
    daily_tss_upper_bound: float,
) -> str:
    if_token = _activity_intensity_token(_safe_float(if_proxy), _safe_float(tss_value))
    sport_lower = str(sport_type or "").lower()
    is_running_like = ("run" in sport_lower) or ("treadmill" in sport_lower)
    override_load = _safe_float(rtss_value) if is_running_like else _safe_float(tss_value)
    daily_cap = float(max(_safe_float(daily_tss_upper_bound), 0.0))
    if daily_cap > 0:
        if override_load > (daily_cap * 1.5):
            return "purple"
        if override_load > daily_cap and if_token not in {"red", "purple"}:
            return "orange"
    return if_token


def _day_lookup_with_daily_model(
    metrics_df: pd.DataFrame,
    daily_tss_target: float,
) -> tuple[pd.DataFrame, dict[pd.Timestamp, dict[str, float]], dict[pd.Timestamp, dict[str, float]]]:
    if metrics_df.empty:
        return (
            pd.DataFrame(columns=["day", "distance_eqv_km", "calories", "duration_s", "tss", "rtss"]),
            {},
            {},
        )

    daily_df = metrics_df.copy()
    daily_df["day"] = pd.to_datetime(daily_df.get("start_time_utc"), utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
    daily_df = daily_df.dropna(subset=["day"]).copy()
    if daily_df.empty:
        return (
            pd.DataFrame(columns=["day", "distance_eqv_km", "calories", "duration_s", "tss", "rtss"]),
            {},
            {},
        )

    daily_agg = (
        daily_df.groupby("day", as_index=False)
        .agg(
            distance_eqv_km=("distance_proxy_km", "sum"),
            calories=("calories_total", "sum"),
            duration_s=("duration_s", "sum"),
            tss=("tss", "sum"),
            rtss=("rtss", "sum"),
        )
        .sort_values("day")
    )
    daily_agg["distance_eqv_km"] = pd.to_numeric(daily_agg["distance_eqv_km"], errors="coerce").fillna(0.0)
    daily_agg["calories"] = pd.to_numeric(daily_agg["calories"], errors="coerce").fillna(0.0)
    daily_agg["duration_s"] = pd.to_numeric(daily_agg["duration_s"], errors="coerce").fillna(0.0)
    daily_agg["tss"] = pd.to_numeric(daily_agg["tss"], errors="coerce").fillna(0.0)
    daily_agg["rtss"] = pd.to_numeric(daily_agg["rtss"], errors="coerce").fillna(0.0)

    min_day = pd.to_datetime(daily_agg["day"], errors="coerce").min()
    max_day = pd.to_datetime(daily_agg["day"], errors="coerce").max()
    if pd.isna(min_day) or pd.isna(max_day):
        return daily_agg, {}, {}

    day_index = pd.date_range(start=min_day, end=max_day, freq="D")
    model_df = pd.DataFrame({"day": day_index})
    model_df = model_df.merge(daily_agg, on="day", how="left")
    for col in ["distance_eqv_km", "calories", "duration_s", "tss", "rtss"]:
        model_df[col] = pd.to_numeric(model_df.get(col), errors="coerce").fillna(0.0)

    tss_series = pd.to_numeric(model_df.get("tss"), errors="coerce").fillna(0.0)
    rtss_series = pd.to_numeric(model_df.get("rtss"), errors="coerce").fillna(0.0)
    if float(rtss_series.abs().sum()) <= 1e-9:
        rtss_series = tss_series.copy()

    tss_emas = ema_multi(tss_series, [42, 7, 10])
    rtss_emas = ema_multi(rtss_series, [100, 10])
    target = float(max(daily_tss_target, 0.0))

    model_df["fitness"] = tss_emas[42]
    model_df["fatigue"] = tss_emas[7]
    model_df["overreach"] = (tss_emas[10] - target).clip(lower=0.0)
    model_df["injury_risk"] = (rtss_emas[10] - target).clip(lower=0.0)

    fitfat_lookup: dict[pd.Timestamp, dict[str, float]] = {}
    model_lookup: dict[pd.Timestamp, dict[str, float]] = {}
    for _, row in model_df.iterrows():
        day = pd.Timestamp(row["day"]).normalize()
        fitfat_lookup[day] = {
            "fitness": _safe_float(row.get("fitness")),
            "fatigue": _safe_float(row.get("fatigue")),
        }
        model_lookup[day] = {
            "fitness": _safe_float(row.get("fitness")),
            "fatigue": _safe_float(row.get("fatigue")),
            "overreach": _safe_float(row.get("overreach")),
            "injury_risk": _safe_float(row.get("injury_risk")),
        }

    return daily_agg, fitfat_lookup, model_lookup


def _metrics_for_filters(
    db_path: Path,
    days: int,
    start_day: str | None,
    end_day: str | None,
    sport: str | None,
) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()

    lthr_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LTHR_CURVE,
        value_key="lthr_bpm",
        fallback_value=DEFAULT_LTHR,
    )
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    if_thresholds = _load_if_zone_thresholds(db_path)

    specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)

    metrics_parts: list[pd.DataFrame] = []

    runs_df = get_runs_df(db_path)
    if not runs_df.empty:
        runs_metrics_df = compute_metrics(
            runs_df=runs_df,
            lthr_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
            threshold_pace_sec_per_km=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
            lthr_curve_points=lthr_curve,
            threshold_pace_curve_points=pace_curve,
        )
        if not runs_metrics_df.empty:
            runs_metrics_df = _apply_specificity_factor(runs_metrics_df, specificity_profile=specificity_profile)
            metrics_parts.append(runs_metrics_df)

    custom_df = get_custom_activities_df(db_path=db_path)
    if not custom_df.empty:
        custom_rows = custom_df.rename(columns={"activity_text": "workout_text"}).copy()
        custom_rows["manual_done"] = False
        custom_metrics = _compute_planned_rows_metrics_df(
            planned_rows=custom_rows,
            lthr_curve_points=lthr_curve,
            lthr_default_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
            lt_pace_curve_points=pace_curve,
            lt_pace_default_sec=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
            specificity_profile=specificity_profile,
        )
        if not custom_metrics.empty:
            merged_custom = custom_rows.merge(
                custom_metrics[
                    [
                        "day_utc",
                        "line_no",
                        "tss",
                        "rtss",
                        "distance_proxy_km",
                        "duration_s",
                        "if_proxy",
                        "pace_proxy_sec_per_km",
                    ]
                ],
                on=["day_utc", "line_no"],
                how="left",
            )

            def _custom_primary_sport(row: pd.Series) -> str:
                raw_segments = row.get("parsed_json")
                segments: list[dict[str, object]] = []
                if isinstance(raw_segments, list):
                    segments = [s for s in raw_segments if isinstance(s, dict)]
                elif isinstance(raw_segments, str) and raw_segments.strip():
                    try:
                        parsed = json.loads(raw_segments)
                        if isinstance(parsed, list):
                            segments = [s for s in parsed if isinstance(s, dict)]
                    except Exception:
                        segments = []
                if segments:
                    kind = str(segments[0].get("kind") or "").strip().lower()
                    if kind:
                        return kind
                text = str(row.get("workout_text") or "").lower()
                if "treadmill" in text:
                    return "treadmill"
                if "run" in text:
                    return "running"
                if "cycl" in text or "bike" in text:
                    return "cycling"
                if "swim" in text:
                    return "swimming"
                if "ellipt" in text:
                    return "elliptical"
                if "strength" in text or "lift" in text:
                    return "strength_training"
                return "custom"

            custom_records: list[dict[str, Any]] = []
            for _, row in merged_custom.iterrows():
                day_ts = pd.to_datetime(row.get("day_utc"), errors="coerce")
                if pd.isna(day_ts):
                    continue
                day_norm = pd.Timestamp(day_ts).normalize()
                line_no = int(_safe_float(row.get("line_no")))
                start_time = day_norm + pd.Timedelta(hours=12) + pd.Timedelta(minutes=max(0, line_no - 1))
                sport_type = _custom_primary_sport(row)
                dist_eqv_km = _safe_float(row.get("distance_proxy_km"))
                is_running_like = ("run" in sport_type) or ("treadmill" in sport_type)
                zone_seconds = {"Z1": 0.0, "Z2": 0.0, "Z3": 0.0, "Z4": 0.0, "Z5": 0.0}

                raw_segments = row.get("parsed_json")
                segments: list[dict[str, Any]] = []
                if isinstance(raw_segments, list):
                    segments = [s for s in raw_segments if isinstance(s, dict)]
                elif isinstance(raw_segments, str) and raw_segments.strip():
                    try:
                        parsed = json.loads(raw_segments)
                        if isinstance(parsed, list):
                            segments = [s for s in parsed if isinstance(s, dict)]
                    except Exception:
                        segments = []

                day_for_curve = pd.to_datetime(row.get("day_utc"), utc=True, errors="coerce")
                lthr_for_day = float(_curve_value_at(lthr_curve, float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR, day_for_curve))
                lt_pace_for_day = float(
                    _curve_value_at(
                        pace_curve,
                        float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
                        day_for_curve,
                    )
                )

                if segments:
                    for seg in segments:
                        seg_kind = str(seg.get("kind") or "").strip().lower()
                        seg_spec = _specificity_factor_for_plan_kind(seg_kind, specificity_profile)
                        seg_for_metrics = _segment_with_effective_intensity_for_metrics(seg, seg_kind=seg_kind, seg_spec=seg_spec)
                        seg_metrics = _planned_segment_metrics(
                            seg_for_metrics,
                            lthr_bpm=lthr_for_day,
                            threshold_pace_sec_per_km=lt_pace_for_day,
                            non_running_factor=seg_spec,
                        )
                        seg_duration_s = _safe_float(seg_metrics.get("duration_s"))
                        seg_if_proxy = _safe_float(seg_metrics.get("if_proxy"))
                        if seg_duration_s <= 0:
                            continue
                        zone_key = _zone_key_from_if_proxy(seg_if_proxy, if_thresholds)
                        zone_seconds[zone_key] = zone_seconds.get(zone_key, 0.0) + seg_duration_s
                else:
                    fallback_duration_s = _safe_float(row.get("duration_s"))
                    fallback_if_proxy = _safe_float(row.get("if_proxy"))
                    if fallback_duration_s > 0:
                        zone_key = _zone_key_from_if_proxy(fallback_if_proxy, if_thresholds)
                        zone_seconds[zone_key] = zone_seconds.get(zone_key, 0.0) + fallback_duration_s

                custom_records.append(
                    {
                        "activity_id": f"custom-{day_norm.date().isoformat()}-{line_no}",
                        "start_time_utc": start_time.isoformat(),
                        "source": "custom",
                        "sport_type": sport_type,
                        "distance_m": dist_eqv_km * 1000.0 if is_running_like else 0.0,
                        "duration_s": _safe_float(row.get("duration_s")),
                        "avg_hr": 0.0,
                        "avg_pace_s_per_km": _safe_float(row.get("pace_proxy_sec_per_km")) if is_running_like else 0.0,
                        "tss": _safe_float(row.get("tss")),
                        "rtss": _safe_float(row.get("rtss")),
                        "distance_proxy_km": dist_eqv_km,
                        "if_proxy": _safe_float(row.get("if_proxy")),
                        "pace_proxy_sec_per_km": _safe_float(row.get("pace_proxy_sec_per_km")),
                        "training_load_garmin": 0.0,
                        "calories_total": 0.0,
                        "hr_time_in_zone_1": _safe_float(zone_seconds.get("Z1")),
                        "hr_time_in_zone_2": _safe_float(zone_seconds.get("Z2")),
                        "hr_time_in_zone_3": _safe_float(zone_seconds.get("Z3")),
                        "hr_time_in_zone_4": _safe_float(zone_seconds.get("Z4")),
                        "hr_time_in_zone_5": _safe_float(zone_seconds.get("Z5")),
                    }
                )

            if custom_records:
                metrics_parts.append(pd.DataFrame(custom_records))

    if not metrics_parts:
        return pd.DataFrame()

    metrics_df = pd.concat(metrics_parts, ignore_index=True, sort=False)

    metrics_df["start_time_utc"] = pd.to_datetime(metrics_df["start_time_utc"], utc=True, errors="coerce")
    metrics_df = metrics_df.dropna(subset=["start_time_utc"]).copy()

    if start_day or end_day:
        if start_day:
            start_ts = pd.to_datetime(start_day, utc=True, errors="coerce")
            if pd.notna(start_ts):
                metrics_df = metrics_df[metrics_df["start_time_utc"] >= start_ts]
        if end_day:
            end_ts = pd.to_datetime(end_day, utc=True, errors="coerce")
            if pd.notna(end_ts):
                metrics_df = metrics_df[metrics_df["start_time_utc"] <= (end_ts + pd.Timedelta(days=1))]
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
        metrics_df = metrics_df[metrics_df["start_time_utc"] >= cutoff]

    sport_filter = str(sport or "").strip().lower()
    if sport_filter:
        mask = metrics_df["sport_type"].fillna("").astype(str).str.lower().str.contains(sport_filter)
        metrics_df = metrics_df[mask]

    return metrics_df


def _filter_metrics_by_activity(metrics_df: pd.DataFrame, activity_filter: str | None) -> pd.DataFrame:
    if metrics_df.empty:
        return metrics_df

    key = str(activity_filter or "all").strip().lower()
    if key in {"all", "all_activities"}:
        return metrics_df

    sport_lower = metrics_df.get("sport_type", pd.Series(index=metrics_df.index, dtype=object)).fillna("").astype(str).str.lower()
    is_running = sport_lower.str.contains("run") & ~sport_lower.str.contains("treadmill")
    is_treadmill = sport_lower.str.contains("treadmill")
    is_running_like = is_running | is_treadmill
    is_cycling = sport_lower.str.contains("cycl") | sport_lower.str.contains("bike")
    is_elliptical = sport_lower.str.contains("ellipt")

    if key in {"all_running", "running_all"}:
        return metrics_df[is_running_like].copy()
    if key == "running":
        return metrics_df[is_running].copy()
    if key == "treadmill":
        return metrics_df[is_treadmill].copy()
    if key == "cycling":
        return metrics_df[is_cycling].copy()
    if key == "elliptical":
        return metrics_df[is_elliptical].copy()

    return metrics_df


def _build_athlete_progression_payload(
    db_path: Path,
    days: int,
    activity_filter: str,
    aggregation: str,
    owner: str,
) -> dict[str, Any]:
    injury_rows: list[dict[str, str]] = []
    raw_injury = get_setting(db_path, SETTINGS_KEY_INJURY_WINDOWS)
    if raw_injury:
        try:
            parsed_injury = json.loads(raw_injury)
            if isinstance(parsed_injury, list):
                injury_rows = _normalize_injury_windows(parsed_injury)
        except Exception:
            injury_rows = []

    metrics_df = _metrics_for_filters(
        db_path=db_path,
        days=max(30, int(days)),
        start_day=None,
        end_day=None,
        sport=None,
    )
    if metrics_df.empty:
        return {
            "owner": owner,
            "days": max(30, int(days)),
            "activity_filter": str(activity_filter or "all"),
            "aggregation": "weekly" if str(aggregation).lower() == "weekly" else "daily",
            "range": {"start_day": "", "end_day": ""},
            "summary": {
                "activities": 0,
                "distance_km": 0.0,
                "distance_eqv_km": 0.0,
                "tss": 0.0,
                "rtss": 0.0,
            },
            "points": [],
            "injury_windows": injury_rows,
        }

    filtered = _filter_metrics_by_activity(metrics_df, activity_filter)
    if filtered.empty:
        return {
            "owner": owner,
            "days": max(30, int(days)),
            "activity_filter": str(activity_filter or "all"),
            "aggregation": "weekly" if str(aggregation).lower() == "weekly" else "daily",
            "range": {"start_day": "", "end_day": ""},
            "summary": {
                "activities": 0,
                "distance_km": 0.0,
                "distance_eqv_km": 0.0,
                "tss": 0.0,
                "rtss": 0.0,
            },
            "points": [],
            "injury_windows": injury_rows,
        }

    filtered = filtered.copy()
    filtered["start_local"] = pd.to_datetime(filtered.get("start_time_utc"), utc=True, errors="coerce").dt.tz_convert(None)
    filtered = filtered.dropna(subset=["start_local"]).copy()
    filtered["day"] = filtered["start_local"].dt.normalize()

    numeric_cols = [
        "distance_m",
        "distance_proxy_km",
        "duration_s",
        "tss",
        "rtss",
        "training_load_garmin",
        "calories_total",
        "hr_time_in_zone_1",
        "hr_time_in_zone_2",
        "hr_time_in_zone_3",
        "hr_time_in_zone_4",
        "hr_time_in_zone_5",
    ]
    for col in numeric_cols:
        if col not in filtered.columns:
            filtered[col] = 0.0
        filtered[col] = pd.to_numeric(filtered[col], errors="coerce").fillna(0.0)

    sport_lower = filtered["sport_type"].fillna("").astype(str).str.lower()
    is_running_like = sport_lower.str.contains("run") | sport_lower.str.contains("treadmill")
    filtered["distance_km_running"] = (filtered["distance_m"].where(is_running_like, 0.0) / 1000.0).fillna(0.0)

    daily_agg = (
        filtered.groupby("day", as_index=False)
        .agg(
            activities=("activity_id", "count"),
            distance_km=("distance_km_running", "sum"),
            distance_eqv_km=("distance_proxy_km", "sum"),
            duration_s=("duration_s", "sum"),
            tss=("tss", "sum"),
            rtss=("rtss", "sum"),
            training_load_garmin=("training_load_garmin", "sum"),
            calories_total=("calories_total", "sum"),
            hr_time_in_zone_1=("hr_time_in_zone_1", "sum"),
            hr_time_in_zone_2=("hr_time_in_zone_2", "sum"),
            hr_time_in_zone_3=("hr_time_in_zone_3", "sum"),
            hr_time_in_zone_4=("hr_time_in_zone_4", "sum"),
            hr_time_in_zone_5=("hr_time_in_zone_5", "sum"),
        )
        .sort_values("day")
    )
    for col in [c for c in daily_agg.columns if c != "day"]:
        daily_agg[col] = pd.to_numeric(daily_agg[col], errors="coerce").fillna(0.0)

    min_day = pd.to_datetime(daily_agg["day"], errors="coerce").min()
    max_day = pd.to_datetime(daily_agg["day"], errors="coerce").max()
    if pd.isna(min_day) or pd.isna(max_day):
        return {
            "owner": owner,
            "days": max(30, int(days)),
            "activity_filter": str(activity_filter or "all"),
            "aggregation": "weekly" if str(aggregation).lower() == "weekly" else "daily",
            "range": {"start_day": "", "end_day": ""},
            "summary": {
                "activities": int(len(filtered.index)),
                "distance_km": 0.0,
                "distance_eqv_km": 0.0,
                "tss": 0.0,
                "rtss": 0.0,
            },
            "points": [],
            "injury_windows": injury_rows,
        }

    day_index = pd.date_range(start=min_day, end=max_day, freq="D")
    model_df = pd.DataFrame({"day": day_index})
    model_df = model_df.merge(daily_agg, on="day", how="left")
    for col in [c for c in model_df.columns if c != "day"]:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce").fillna(0.0)

    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    latest_lt_pace = float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    daily_tss_target = float(max(_weekly_tss_target_from_lt_pace(latest_lt_pace) / 7.0, 0.0))
    daily_distance_target = float(max(_weekly_distance_target_from_lt_pace(latest_lt_pace) / 7.0, 0.0))

    tss_series = pd.to_numeric(model_df.get("tss"), errors="coerce").fillna(0.0)
    rtss_series = pd.to_numeric(model_df.get("rtss"), errors="coerce").fillna(0.0)
    if float(rtss_series.abs().sum()) <= 1e-9:
        rtss_series = tss_series.copy()

    tss_emas = ema_multi(tss_series, [42, 7, 10])
    rtss_emas = ema_multi(rtss_series, [100, 7, 10])
    model_df["fitness"] = tss_emas[42]
    model_df["fatigue"] = tss_emas[7]
    model_df["overreach"] = (tss_emas[10] - daily_tss_target).clip(lower=0.0)
    model_df["injury_risk"] = (rtss_emas[10] - daily_tss_target).clip(lower=0.0)
    model_df["leg_elasticity"] = rtss_emas[100]
    model_df["pounding"] = rtss_emas[7]

    model_df["zone_low_aerobic_h"] = model_df["hr_time_in_zone_1"] / 3600.0
    model_df["zone_moderate_aerobic_h"] = model_df["hr_time_in_zone_2"] / 3600.0
    model_df["zone_high_aerobic_h"] = (model_df["hr_time_in_zone_3"] + model_df["hr_time_in_zone_4"]) / 3600.0
    model_df["zone_total_h"] = model_df["duration_s"] / 3600.0

    mode = "weekly" if str(aggregation).strip().lower() == "weekly" else "daily"
    if mode == "weekly":
        weekly_df = model_df.copy()
        weekly_df["period_start"] = pd.to_datetime(weekly_df["day"], errors="coerce").map(_week_start_monday)
        points_df = (
            weekly_df.groupby("period_start", as_index=False)
            .agg(
                activities=("activities", "sum"),
                distance_km=("distance_km", "sum"),
                distance_eqv_km=("distance_eqv_km", "sum"),
                duration_s=("duration_s", "sum"),
                tss=("tss", "sum"),
                rtss=("rtss", "sum"),
                training_load_garmin=("training_load_garmin", "sum"),
                calories_total=("calories_total", "sum"),
                zone_low_aerobic_h=("zone_low_aerobic_h", "sum"),
                zone_moderate_aerobic_h=("zone_moderate_aerobic_h", "sum"),
                zone_high_aerobic_h=("zone_high_aerobic_h", "sum"),
                zone_total_h=("zone_total_h", "sum"),
                fitness=("fitness", "mean"),
                fatigue=("fatigue", "mean"),
                overreach=("overreach", "mean"),
                injury_risk=("injury_risk", "mean"),
                leg_elasticity=("leg_elasticity", "mean"),
                pounding=("pounding", "mean"),
            )
            .sort_values("period_start")
        )
        points_df["target_tss"] = daily_tss_target * 7.0
        points_df["target_distance_km"] = daily_distance_target * 7.0
    else:
        points_df = model_df.rename(columns={"day": "period_start"}).copy()
        points_df["target_tss"] = daily_tss_target
        points_df["target_distance_km"] = daily_distance_target

    summary = {
        "activities": int(len(filtered.index)),
        "distance_km": round(float(pd.to_numeric(filtered.get("distance_km_running"), errors="coerce").fillna(0.0).sum()), 1),
        "distance_eqv_km": round(float(pd.to_numeric(filtered.get("distance_proxy_km"), errors="coerce").fillna(0.0).sum()), 1),
        "tss": round(float(pd.to_numeric(filtered.get("tss"), errors="coerce").fillna(0.0).sum()), 1),
        "rtss": round(float(pd.to_numeric(filtered.get("rtss"), errors="coerce").fillna(0.0).sum()), 1),
    }

    points: list[dict[str, Any]] = []
    for _, row in points_df.iterrows():
        period_start = pd.to_datetime(row.get("period_start"), errors="coerce")
        if pd.isna(period_start):
            continue
        points.append(
            {
                "period_start": period_start.date().isoformat(),
                "activities": int(_safe_float(row.get("activities"))),
                "distance_km": round(_safe_float(row.get("distance_km")), 2),
                "distance_eqv_km": round(_safe_float(row.get("distance_eqv_km")), 2),
                "duration_h": round(_safe_float(row.get("duration_s")) / 3600.0, 2),
                "tss": round(_safe_float(row.get("tss")), 2),
                "rtss": round(_safe_float(row.get("rtss")), 2),
                "training_load_garmin": round(_safe_float(row.get("training_load_garmin")), 2),
                "calories_total": round(_safe_float(row.get("calories_total")), 2),
                "zone_low_aerobic_h": round(_safe_float(row.get("zone_low_aerobic_h")), 3),
                "zone_moderate_aerobic_h": round(_safe_float(row.get("zone_moderate_aerobic_h")), 3),
                "zone_high_aerobic_h": round(_safe_float(row.get("zone_high_aerobic_h")), 3),
                "zone_total_h": round(_safe_float(row.get("zone_total_h")), 3),
                "fitness": round(_safe_float(row.get("fitness")), 3),
                "fatigue": round(_safe_float(row.get("fatigue")), 3),
                "overreach": round(_safe_float(row.get("overreach")), 3),
                "injury_risk": round(_safe_float(row.get("injury_risk")), 3),
                "leg_elasticity": round(_safe_float(row.get("leg_elasticity")), 3),
                "pounding": round(_safe_float(row.get("pounding")), 3),
                "target_tss": round(_safe_float(row.get("target_tss")), 3),
                "target_distance_km": round(_safe_float(row.get("target_distance_km")), 3),
            }
        )

    return {
        "owner": owner,
        "days": max(30, int(days)),
        "activity_filter": str(activity_filter or "all"),
        "aggregation": mode,
        "range": {
            "start_day": pd.Timestamp(min_day).date().isoformat() if pd.notna(min_day) else "",
            "end_day": pd.Timestamp(max_day).date().isoformat() if pd.notna(max_day) else "",
        },
        "summary": summary,
        "points": points,
        "injury_windows": injury_rows,
    }


def _build_wellness_payload(
    db_path: Path,
    days: int,
    aggregation: str,
    owner: str,
) -> dict[str, Any]:
    sleep_df = get_sleep_df(db_path=db_path)
    wellness_df = get_wellness_df(db_path=db_path)

    if sleep_df.empty and wellness_df.empty:
        return {
            "owner": owner,
            "days": max(30, int(days)),
            "aggregation": "weekly" if str(aggregation).strip().lower() == "weekly" else "daily",
            "range": {"start_day": "", "end_day": ""},
            "summary": {},
            "points": [],
        }

    if not sleep_df.empty:
        sleep_df = sleep_df.copy()
        sleep_df["day"] = pd.to_datetime(sleep_df.get("day_utc"), errors="coerce").dt.normalize()
        sleep_df = sleep_df.dropna(subset=["day"]).sort_values("day").drop_duplicates(subset=["day"], keep="last")
    else:
        sleep_df = pd.DataFrame(columns=["day"])

    if not wellness_df.empty:
        wellness_df = wellness_df.copy()
        wellness_df["day"] = pd.to_datetime(wellness_df.get("day_utc"), errors="coerce").dt.normalize()
        wellness_df = wellness_df.dropna(subset=["day"]).sort_values("day").drop_duplicates(subset=["day"], keep="last")
    else:
        wellness_df = pd.DataFrame(columns=["day"])

    merged = pd.merge(
        sleep_df,
        wellness_df,
        on="day",
        how="outer",
        suffixes=("_sleep", "_well"),
    ).sort_values("day")
    if merged.empty:
        return {
            "owner": owner,
            "days": max(30, int(days)),
            "aggregation": "weekly" if str(aggregation).strip().lower() == "weekly" else "daily",
            "range": {"start_day": "", "end_day": ""},
            "summary": {},
            "points": [],
        }

    for col in [
        "sleep_score",
        "sleep_duration_s",
        "deep_sleep_s",
        "rem_sleep_s",
        "light_sleep_s",
        "awake_s",
        "resting_hr",
        "hrv_status",
        "training_readiness",
        "stress_avg",
        "stress_max",
        "body_battery_start",
        "body_battery_end",
        "body_battery_avg",
        "respiration_avg",
        "steps",
        "intensity_minutes",
        "calories_total",
    ]:
        merged[col] = pd.to_numeric(merged.get(col), errors="coerce")

    end_day = pd.to_datetime(merged["day"], errors="coerce").max()
    min_day = pd.to_datetime(merged["day"], errors="coerce").min()
    if pd.isna(end_day) or pd.isna(min_day):
        return {
            "owner": owner,
            "days": max(30, int(days)),
            "aggregation": "weekly" if str(aggregation).strip().lower() == "weekly" else "daily",
            "range": {"start_day": "", "end_day": ""},
            "summary": {},
            "points": [],
        }

    window_days = max(30, int(days))
    start_bound = pd.Timestamp(end_day).normalize() - pd.Timedelta(days=window_days - 1)
    merged = merged[merged["day"] >= start_bound].copy()

    merged["sleep_duration_h"] = pd.to_numeric(merged.get("sleep_duration_s"), errors="coerce") / 3600.0
    merged["deep_sleep_h"] = pd.to_numeric(merged.get("deep_sleep_s"), errors="coerce") / 3600.0
    merged["rem_sleep_h"] = pd.to_numeric(merged.get("rem_sleep_s"), errors="coerce") / 3600.0
    merged["light_sleep_h"] = pd.to_numeric(merged.get("light_sleep_s"), errors="coerce") / 3600.0
    merged["awake_h"] = pd.to_numeric(merged.get("awake_s"), errors="coerce") / 3600.0

    mode = "weekly" if str(aggregation).strip().lower() == "weekly" else "daily"
    if mode == "weekly":
        merged["period_start"] = pd.to_datetime(merged["day"], errors="coerce").map(_week_start_monday)
        points_df = (
            merged.groupby("period_start", as_index=False)
            .agg(
                sample_days=("day", "count"),
                sleep_score=("sleep_score", "mean"),
                sleep_duration_h=("sleep_duration_h", "sum"),
                deep_sleep_h=("deep_sleep_h", "sum"),
                rem_sleep_h=("rem_sleep_h", "sum"),
                light_sleep_h=("light_sleep_h", "sum"),
                awake_h=("awake_h", "sum"),
                resting_hr=("resting_hr", "mean"),
                hrv_status=("hrv_status", "mean"),
                training_readiness=("training_readiness", "mean"),
                stress_avg=("stress_avg", "mean"),
                stress_max=("stress_max", "mean"),
                body_battery_start=("body_battery_start", "mean"),
                body_battery_end=("body_battery_end", "mean"),
                body_battery_avg=("body_battery_avg", "mean"),
                respiration_avg=("respiration_avg", "mean"),
                steps=("steps", "sum"),
                intensity_minutes=("intensity_minutes", "sum"),
                calories_total=("calories_total", "sum"),
            )
            .sort_values("period_start")
        )
    else:
        points_df = merged.rename(columns={"day": "period_start"}).copy()
        points_df["sample_days"] = 1
        points_df = points_df.sort_values("period_start")

    def _latest_metric(column: str, digits: int = 1) -> float | None:
        if column not in merged.columns:
            return None
        series = pd.to_numeric(merged[column], errors="coerce").dropna()
        if series.empty:
            return None
        return round(float(series.iloc[-1]), digits)

    points: list[dict[str, Any]] = []
    for _, row in points_df.iterrows():
        period_start = pd.to_datetime(row.get("period_start"), errors="coerce")
        if pd.isna(period_start):
            continue
        points.append(
            {
                "period_start": period_start.date().isoformat(),
                "sample_days": int(_safe_float(row.get("sample_days"))),
                "sleep_score": _rounded_optional(row.get("sleep_score")),
                "sleep_duration_h": _rounded_optional(row.get("sleep_duration_h"), 3),
                "deep_sleep_h": _rounded_optional(row.get("deep_sleep_h"), 3),
                "rem_sleep_h": _rounded_optional(row.get("rem_sleep_h"), 3),
                "light_sleep_h": _rounded_optional(row.get("light_sleep_h"), 3),
                "awake_h": _rounded_optional(row.get("awake_h"), 3),
                "resting_hr": _rounded_optional(row.get("resting_hr")),
                "hrv_status": _rounded_optional(row.get("hrv_status")),
                "training_readiness": _rounded_optional(row.get("training_readiness")),
                "stress_avg": _rounded_optional(row.get("stress_avg")),
                "stress_max": _rounded_optional(row.get("stress_max")),
                "body_battery_start": _rounded_optional(row.get("body_battery_start")),
                "body_battery_end": _rounded_optional(row.get("body_battery_end")),
                "body_battery_avg": _rounded_optional(row.get("body_battery_avg")),
                "respiration_avg": _rounded_optional(row.get("respiration_avg")),
                "steps": _rounded_optional(row.get("steps")),
                "intensity_minutes": _rounded_optional(row.get("intensity_minutes")),
                "calories_total": _rounded_optional(row.get("calories_total")),
            }
        )

    summary = {
        "latest_sleep_score": _latest_metric("sleep_score"),
        "latest_resting_hr": _latest_metric("resting_hr"),
        "latest_stress_avg": _latest_metric("stress_avg"),
        "latest_training_readiness": _latest_metric("training_readiness"),
        "latest_body_battery_end": _latest_metric("body_battery_end"),
    }

    return {
        "owner": owner,
        "days": window_days,
        "aggregation": mode,
        "range": {
            "start_day": pd.Timestamp(start_bound).date().isoformat() if pd.notna(start_bound) else "",
            "end_day": pd.Timestamp(end_day).date().isoformat() if pd.notna(end_day) else "",
        },
        "summary": summary,
        "points": points,
    }


def _build_activity_dashboard_payload(
    db_path: Path,
    visible_weeks: int,
    week_offset: int,
    sport: str | None,
) -> dict[str, Any]:
    metrics_df = _metrics_for_filters(
        db_path=db_path,
        days=3650,
        start_day=None,
        end_day=None,
        sport=sport,
    )
    if metrics_df.empty:
        return {
            "weeks_total": 0,
            "weeks_visible": 0,
            "has_more_weeks": False,
            "summary": {
                "activities": 0,
                "distance_km": 0.0,
                "distance_eqv_km": 0.0,
                "tss": 0.0,
                "rtss": 0.0,
            },
            "weeks": [],
        }

    metrics_df = metrics_df.copy()
    metrics_df["start_local"] = pd.to_datetime(metrics_df.get("start_time_utc"), utc=True, errors="coerce").dt.tz_convert(None)
    metrics_df = metrics_df.dropna(subset=["start_local"]).copy()
    metrics_df["day"] = metrics_df["start_local"].dt.normalize()
    sport_lower = metrics_df["sport_type"].fillna("").astype(str).str.lower()
    is_running_like = sport_lower.str.contains("run") | sport_lower.str.contains("treadmill")
    metrics_df["distance_km_running"] = (
        pd.to_numeric(metrics_df.get("distance_m"), errors="coerce").fillna(0.0).where(is_running_like, 0.0) / 1000.0
    )
    if metrics_df.empty:
        return {
            "weeks_total": 0,
            "weeks_visible": 0,
            "has_more_weeks": False,
            "summary": {
                "activities": 0,
                "distance_km": 0.0,
                "distance_eqv_km": 0.0,
                "tss": 0.0,
                "rtss": 0.0,
            },
            "weeks": [],
        }

    min_day = pd.to_datetime(metrics_df["day"], errors="coerce").min()
    max_day = pd.to_datetime(metrics_df["day"], errors="coerce").max()
    if pd.isna(min_day) or pd.isna(max_day):
        return {
            "weeks_total": 0,
            "weeks_visible": 0,
            "has_more_weeks": False,
            "summary": {
                "activities": 0,
                "distance_km": 0.0,
                "distance_eqv_km": 0.0,
                "tss": 0.0,
                "rtss": 0.0,
            },
            "weeks": [],
        }

    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    latest_lt_pace = float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    daily_tss_target = max(_weekly_tss_target_from_lt_pace(latest_lt_pace) / 7.0, 0.0)
    day_agg, fitfat_lookup, model_lookup = _day_lookup_with_daily_model(
        metrics_df=metrics_df,
        daily_tss_target=daily_tss_target,
    )

    day_stats_lookup: dict[pd.Timestamp, dict[str, float]] = {}
    for _, row in day_agg.iterrows():
        d = pd.Timestamp(row["day"]).normalize()
        day_stats_lookup[d] = {
            "distance_eqv_km": _safe_float(row.get("distance_eqv_km")),
            "calories": _safe_float(row.get("calories")),
            "duration_s": _safe_float(row.get("duration_s")),
            "tss": _safe_float(row.get("tss")),
            "rtss": _safe_float(row.get("rtss")),
        }

    today_local = pd.Timestamp(datetime.now().astimezone().date()).normalize()
    render_max_day = max(pd.Timestamp(max_day).normalize(), today_local + pd.Timedelta(days=28))

    planned_rows = get_planned_activities_df(
        db_path=db_path,
        start_day_utc=min_day.date().isoformat(),
        end_day_utc=render_max_day.date().isoformat(),
    )
    planned_by_day: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    planned_summary_lookup: dict[pd.Timestamp, dict[str, float]] = {}
    planned_tss_lookup: dict[pd.Timestamp, float] = {}
    if not planned_rows.empty:
        lthr_curve = _load_curve_points(
            db_path=db_path,
            key=SETTINGS_KEY_LTHR_CURVE,
            value_key="lthr_bpm",
            fallback_value=DEFAULT_LTHR,
        )
        specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)
        planned_metrics = _compute_planned_rows_metrics_df(
            planned_rows=planned_rows,
            lthr_curve_points=lthr_curve,
            lthr_default_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
            lt_pace_curve_points=pace_curve,
            lt_pace_default_sec=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
            specificity_profile=specificity_profile,
        )
        if not planned_metrics.empty:
            planned_metrics["day"] = pd.to_datetime(planned_metrics.get("day_utc"), errors="coerce").dt.normalize()
            planned_metrics = planned_metrics.dropna(subset=["day"]).copy()
            planned_metrics["manual_done"] = pd.to_numeric(planned_metrics.get("manual_done"), errors="coerce").fillna(0.0) > 0
            effective_planned_metrics = _filter_effective_planned_rows(
                planned_metrics,
                today_local_day=today_local,
            )
            for day, grp in effective_planned_metrics.groupby("day"):
                day_key = pd.Timestamp(day).normalize()
                cards: list[dict[str, Any]] = []
                remaining_tss = 0.0
                for _, row in grp.iterrows():
                    remaining_tss += _safe_float(row.get("tss"))
                    cards.append(
                        {
                            "activity_id": f"planned-{day_key.date().isoformat()}-{int(_safe_float(row.get('line_no')))}",
                            "day_utc": day_key.date().isoformat(),
                            "line_no": int(_safe_float(row.get("line_no"))),
                            "activity": _planned_activity_label(row.get("parsed_json")),
                            "workout_text": str(row.get("workout_text") or ""),
                            "duration_s": _safe_float(row.get("duration_s")),
                            "distance_eqv_km": _safe_float(row.get("distance_proxy_km")),
                            "if_proxy": _safe_float(row.get("if_proxy")),
                            "pace_label": _format_pace_short(_safe_float(row.get("pace_proxy_sec_per_km"))),
                            "tss": _safe_float(row.get("tss")),
                            "rtss": _safe_float(row.get("rtss")),
                            "manual_done": bool(row.get("manual_done")),
                        }
                    )
                if cards:
                    planned_by_day[day_key] = cards
                planned_tss_lookup[day_key] = float(max(remaining_tss, 0.0))
                planned_summary_lookup[day_key] = {
                    "duration_s": float(pd.to_numeric(grp.get("duration_s"), errors="coerce").fillna(0.0).sum()),
                    "distance_eqv_km": float(pd.to_numeric(grp.get("distance_proxy_km"), errors="coerce").fillna(0.0).sum()),
                    "if_proxy": (
                        float(
                            (pd.to_numeric(grp.get("if_proxy"), errors="coerce").fillna(0.0)
                             * pd.to_numeric(grp.get("duration_s"), errors="coerce").fillna(0.0)).sum()
                        )
                        / float(pd.to_numeric(grp.get("duration_s"), errors="coerce").fillna(0.0).sum())
                        if float(pd.to_numeric(grp.get("duration_s"), errors="coerce").fillna(0.0).sum()) > 0
                        else 0.0
                    ),
                }

    wellness_lookup: dict[pd.Timestamp, dict[str, float]] = {}
    wellness_df = get_wellness_df(db_path=db_path)
    if not wellness_df.empty:
        wellness_df = wellness_df.copy()
        wellness_df["day"] = pd.to_datetime(wellness_df.get("day_utc"), errors="coerce").dt.normalize()
        wellness_df = wellness_df.dropna(subset=["day"]).sort_values("day").drop_duplicates(subset=["day"], keep="last")
        for _, row in wellness_df.iterrows():
            d = pd.Timestamp(row["day"]).normalize()
            wellness_lookup[d] = {
                "resting_hr": _safe_float(row.get("resting_hr")),
                "stress_avg": _safe_float(row.get("stress_avg")),
            }

    latest_actual_day = pd.Timestamp(max_day).normalize()
    display_anchor_day = pd.Timestamp(min(today_local, latest_actual_day)).normalize()
    current_week_start = _week_start_monday(display_anchor_day)
    fatigue_expected_lookup: dict[pd.Timestamp, float] = {}
    last_planned_day: pd.Timestamp | None = (
        max(planned_tss_lookup.keys()) if planned_tss_lookup else None
    )
    if not day_agg.empty:
        min_model_day = pd.to_datetime(day_agg.get("day"), errors="coerce").min()
        projection_end_day = render_max_day
        if pd.notna(min_model_day):
            projection_days = pd.date_range(start=pd.Timestamp(min_model_day).normalize(), end=projection_end_day, freq="D")
            actual_tss_lookup = {
                pd.Timestamp(row["day"]).normalize(): _safe_float(row.get("tss"))
                for _, row in day_agg.iterrows()
            }
            projected_tss = pd.Series(
                [
                    (
                        _safe_float(actual_tss_lookup.get(pd.Timestamp(day).normalize(), 0.0))
                        + _safe_float(planned_tss_lookup.get(pd.Timestamp(day).normalize(), 0.0))
                    )
                    if pd.Timestamp(day).normalize() == today_local
                    else (
                        actual_tss_lookup.get(pd.Timestamp(day).normalize(), 0.0)
                        if pd.Timestamp(day).normalize() < today_local
                        else _safe_float(planned_tss_lookup.get(pd.Timestamp(day).normalize(), 0.0))
                    )
                    for day in projection_days
                ],
                index=projection_days,
                dtype="float64",
            )
            projected_fatigue = ema_multi(projected_tss, [7])[7]
            for day, value in projected_fatigue.items():
                fatigue_expected_lookup[pd.Timestamp(day).normalize()] = _safe_float(value)

    actual_week_starts = {
        _week_start_monday(pd.Timestamp(day))
        for day in pd.to_datetime(metrics_df.get("day"), errors="coerce").dropna().tolist()
    }
    planned_week_starts = {
        _week_start_monday(pd.Timestamp(day))
        for day in list(planned_summary_lookup.keys())
    }

    all_week_starts = {pd.Timestamp(ws).normalize() for ws in actual_week_starts.union(planned_week_starts)}
    all_week_starts.add(current_week_start)
    # Strict chronological order: latest week first.
    ordered_week_starts = sorted(all_week_starts, reverse=True)

    weeks_total = int(len(ordered_week_starts))
    max_visible = max(1, min(int(visible_weeks), max(weeks_total, 1)))
    safe_offset = max(0, min(int(week_offset), max(weeks_total - 1, 0)))
    selected_week_starts = ordered_week_starts[safe_offset:safe_offset + max_visible]

    summary = {
        "activities": int(len(metrics_df.index)),
        "distance_km": round(float(pd.to_numeric(metrics_df.get("distance_km_running"), errors="coerce").fillna(0.0).sum()), 1),
        "distance_eqv_km": round(float(pd.to_numeric(metrics_df.get("distance_proxy_km"), errors="coerce").fillna(0.0).sum()), 1),
        "tss": round(float(pd.to_numeric(metrics_df.get("tss"), errors="coerce").fillna(0.0).sum()), 1),
        "rtss": round(float(pd.to_numeric(metrics_df.get("rtss"), errors="coerce").fillna(0.0).sum()), 1),
    }

    sorted_model_days = sorted(model_lookup.keys())

    def _model_on_or_before(day: pd.Timestamp) -> dict[str, float] | None:
        if not sorted_model_days:
            return None
        lookup_day = pd.Timestamp(day).normalize()
        for d in reversed(sorted_model_days):
            if d <= lookup_day:
                return model_lookup.get(d)
        return None

    weeks_out: list[dict[str, Any]] = []
    for ws in selected_week_starts:
        ws = pd.Timestamp(ws).normalize()
        we = ws + pd.Timedelta(days=6)
        week_df = metrics_df[(metrics_df["day"] >= ws) & (metrics_df["day"] <= we)].copy()
        has_planned_week = any(
            ((ws + pd.Timedelta(days=offset)) in planned_summary_lookup)
            or ((ws + pd.Timedelta(days=offset)) in planned_by_day)
            for offset in range(7)
        )
        if week_df.empty and not has_planned_week and ws != current_week_start:
            continue

        week_duration_s = float(pd.to_numeric(week_df.get("duration_s"), errors="coerce").fillna(0.0).sum())
        week_distance_km = float(pd.to_numeric(week_df.get("distance_km_running"), errors="coerce").fillna(0.0).sum())
        week_distance_eqv = float(pd.to_numeric(week_df.get("distance_proxy_km"), errors="coerce").fillna(0.0).sum())
        week_calories = float(pd.to_numeric(week_df.get("calories_total"), errors="coerce").fillna(0.0).sum())
        week_tss = float(pd.to_numeric(week_df.get("tss"), errors="coerce").fillna(0.0).sum())
        week_rtss = float(pd.to_numeric(week_df.get("rtss"), errors="coerce").fillna(0.0).sum())
        week_daily_model = _model_on_or_before(we)
        week_zones_seconds = {
            "Z1": float(pd.to_numeric(week_df.get("hr_time_in_zone_1"), errors="coerce").fillna(0.0).sum()),
            "Z2": float(pd.to_numeric(week_df.get("hr_time_in_zone_2"), errors="coerce").fillna(0.0).sum()),
            "Z3": float(pd.to_numeric(week_df.get("hr_time_in_zone_3"), errors="coerce").fillna(0.0).sum()),
            "Z4": float(pd.to_numeric(week_df.get("hr_time_in_zone_4"), errors="coerce").fillna(0.0).sum()),
            "Z5": float(pd.to_numeric(week_df.get("hr_time_in_zone_5"), errors="coerce").fillna(0.0).sum()),
        }
        week_zone_total = max(float(sum(week_zones_seconds.values())), 0.0)
        zones_out: list[dict[str, Any]] = []
        for zone in ["Z1", "Z2", "Z3", "Z4", "Z5"]:
            sec = week_zones_seconds.get(zone, 0.0)
            pct = (sec / week_zone_total * 100.0) if week_zone_total > 0 else 0.0
            zones_out.append({"zone": zone, "seconds": round(sec, 1), "pct": round(pct, 1)})

        day_cards: list[dict[str, Any]] = []
        for offset in range(7):
            day = ws + pd.Timedelta(days=offset)
            day_df = week_df[week_df["day"] == day].sort_values("start_local", ascending=False)
            day_is_today = bool(day == today_local)
            day_stats = day_stats_lookup.get(day, {})
            fitfat = fitfat_lookup.get(day, {})
            wellness = wellness_lookup.get(day, {})
            planned_summary = planned_summary_lookup.get(day, {})
            show_planned_meta = (
                day_df.empty
                and _safe_float(day_stats.get("distance_eqv_km")) <= 0
                and _safe_float(day_stats.get("calories")) <= 0
            )
            actual_cards: list[dict[str, Any]] = []
            for _, act in day_df.iterrows():
                sport_raw = str(act.get("sport_type") or "").strip()
                sport_lower = sport_raw.lower()
                is_running = ("run" in sport_lower) or ("treadmill" in sport_lower)
                dist_km = _safe_float(act.get("distance_m")) / 1000.0
                dist_eqv = _safe_float(act.get("distance_proxy_km"))
                if_proxy = _safe_float(act.get("if_proxy"))
                tss = _safe_float(act.get("tss"))
                rtss = _safe_float(act.get("rtss"))
                hr = _safe_float(act.get("avg_hr"))
                avg_pace = _safe_float(act.get("avg_pace_s_per_km"))
                eqv_pace = _safe_float(act.get("pace_proxy_sec_per_km"))
                start_local_ts = pd.to_datetime(act.get("start_local"), errors="coerce")
                actual_cards.append(
                    {
                        "activity_id": _normalize_activity_id(act.get("activity_id")),
                        "sport": sport_raw or "Activity",
                        "is_custom": bool(str(act.get("source") or "").strip().lower() == "custom"),
                        "day_utc": day.date().isoformat() if bool(str(act.get("source") or "").strip().lower() == "custom") else None,
                        "line_no": (
                            _parse_custom_activity_id(_normalize_activity_id(act.get("activity_id")))[1]
                            if _parse_custom_activity_id(_normalize_activity_id(act.get("activity_id"))) is not None
                            else None
                        ),
                        "start_time_utc": str(act.get("start_time_utc") or ""),
                        "start_time_hhmm": (
                            pd.Timestamp(start_local_ts).strftime("%H:%M")
                            if pd.notna(start_local_ts)
                            else ""
                        ),
                        "duration_label": _format_duration_short(_safe_float(act.get("duration_s"))),
                        "activity_text": str(act.get("activity_text") or "") if bool(str(act.get("source") or "").strip().lower() == "custom") else None,
                        "distance_label": (
                            f"{dist_km:.0f} km"
                            if is_running and dist_km > 0
                            else (f"{dist_eqv:.0f} km eqv." if dist_eqv > 0 else "0 km")
                        ),
                        "hr_label": f"{hr:.0f} bpm" if hr > 0 else "-",
                        "pace_label": (
                            _format_pace_short(avg_pace if avg_pace > 0 else None)
                            if is_running
                            else _format_pace_short(eqv_pace if eqv_pace > 0 else None)
                        ),
                        "if_pct": round(if_proxy * 100.0, 1),
                        "tss": round(tss, 1),
                        "rtss": round(rtss, 1),
                        "intensity": _activity_intensity_token(if_proxy=if_proxy, tss=tss),
                    }
                )

            planned_cards = planned_by_day.get(day, [])
            day_cards.append(
                {
                    "day_utc": day.date().isoformat(),
                    "day_label": day.strftime("%d %b (%a)"),
                    "is_today": day_is_today,
                    "is_past": bool(day < today_local),
                    "meta": {
                        "distance_eqv_km": round(_safe_float(day_stats.get("distance_eqv_km")), 1),
                        "calories": round(_safe_float(day_stats.get("calories")), 0),
                        "fitness": round(_safe_float(fitfat.get("fitness")), 1) if fitfat else None,
                        "fatigue": round(_safe_float(fitfat.get("fatigue")), 1) if fitfat else None,
                        "fatigue_expected": (
                            round(_safe_float(fatigue_expected_lookup.get(day)), 1)
                            if day in fatigue_expected_lookup
                            else None
                        ),
                        "resting_hr": (
                            None
                            if day_is_today
                            else (round(_safe_float(wellness.get("resting_hr")), 1) if wellness else None)
                        ),
                        "stress_avg": (
                            None
                            if day_is_today
                            else (round(_safe_float(wellness.get("stress_avg")), 1) if wellness else None)
                        ),
                        "planned_duration_s": round(_safe_float(planned_summary.get("duration_s")), 1) if show_planned_meta else 0.0,
                        "planned_if_pct": round(_safe_float(planned_summary.get("if_proxy")) * 100.0, 1) if show_planned_meta else 0.0,
                        "show_fatigue_expected": bool(
                            last_planned_day is not None
                            and day >= today_local
                            and day <= pd.Timestamp(last_planned_day).normalize()
                        ),
                    },
                    "actual_activities": actual_cards,
                    "planned_activities": [
                        {
                            "activity_id": str(row.get("activity_id") or ""),
                            "day_utc": str(row.get("day_utc") or ""),
                            "line_no": int(_safe_float(row.get("line_no"))),
                            "activity": str(row.get("activity") or "Planned"),
                            "workout_text": str(row.get("workout_text") or ""),
                            "duration_label": _format_duration_short(_safe_float(row.get("duration_s"))),
                            "distance_eqv_km": round(_safe_float(row.get("distance_eqv_km")), 1),
                            "if_pct": round(_safe_float(row.get("if_proxy")) * 100.0, 1),
                            "pace_label": str(
                                row.get("pace_label")
                                or _format_pace_short(_safe_float(row.get("pace_proxy_sec_per_km")))
                            ),
                            "tss": round(_safe_float(row.get("tss")), 1),
                            "rtss": round(_safe_float(row.get("rtss")), 1),
                            "manual_done": bool(row.get("manual_done")),
                            "intensity": _activity_intensity_token(
                                if_proxy=_safe_float(row.get("if_proxy")),
                                tss=_safe_float(row.get("tss")),
                            ),
                        }
                        for row in planned_cards
                    ],
                }
            )

        weeks_out.append(
            {
                "week_start": ws.date().isoformat(),
                "week_end": we.date().isoformat(),
                "week_number": int(ws.isocalendar().week),
                "summary": {
                    "duration_h": round(week_duration_s / 3600.0, 1),
                    "distance_km": round(week_distance_km, 1),
                    "distance_eqv_km": round(week_distance_eqv, 1),
                    "calories": round(week_calories, 0),
                    "tss": round(week_tss, 1),
                    "rtss": round(week_rtss, 1),
                    "fitness": (
                        round(_safe_float(week_daily_model.get("fitness")), 1)
                        if isinstance(week_daily_model, dict)
                        else None
                    ),
                    "fatigue": (
                        round(_safe_float(week_daily_model.get("fatigue")), 1)
                        if isinstance(week_daily_model, dict)
                        else None
                    ),
                    "overreach": (
                        round(_safe_float(week_daily_model.get("overreach")), 1)
                        if isinstance(week_daily_model, dict)
                        else None
                    ),
                    "injury_risk": (
                        round(_safe_float(week_daily_model.get("injury_risk")), 1)
                        if isinstance(week_daily_model, dict)
                        else None
                    ),
                    "zones": zones_out,
                },
                "days": day_cards,
            }
        )

    weeks_out = sorted(
        weeks_out,
        key=lambda week: pd.Timestamp(pd.to_datetime(week.get("week_start"), errors="coerce")).timestamp()
        if pd.notna(pd.to_datetime(week.get("week_start"), errors="coerce"))
        else float("-inf"),
        reverse=True,
    )

    return {
        "weeks_total": weeks_total,
        "weeks_visible": int(len(weeks_out)),
        "has_more_weeks": bool((safe_offset + max_visible) < weeks_total),
        "summary": summary,
        "weeks": weeks_out,
    }


def _build_weekly_payload(
    db_path: Path,
    days: int,
    start_day: str | None,
    end_day: str | None,
    sport: str | None,
) -> dict[str, Any]:
    metrics_df = _metrics_for_filters(
        db_path=db_path,
        days=days,
        start_day=start_day,
        end_day=end_day,
        sport=sport,
    )
    if metrics_df.empty:
        return {
            "range_days": int(days),
            "weeks": [],
            "summary": {"weeks": 0, "total_distance_km": 0.0, "total_tss": 0.0, "total_activities": 0},
        }

    weekly_df = weekly_summary(metrics_df)
    if weekly_df.empty:
        return {
            "range_days": int(days),
            "weeks": [],
            "summary": {"weeks": 0, "total_distance_km": 0.0, "total_tss": 0.0, "total_activities": 0},
        }

    rows: list[dict[str, Any]] = []
    for _, row in weekly_df.sort_values("week_start", ascending=False).iterrows():
        week_start = pd.to_datetime(row.get("week_start"), utc=False, errors="coerce")
        rows.append(
            {
                "week_start": week_start.date().isoformat() if pd.notna(week_start) else "",
                "distance_km": round(_safe_float(row.get("total_distance_km")), 2),
                "tss": round(_safe_float(row.get("total_tss")), 1),
                "rtss": round(_safe_float(row.get("total_rtss")), 1),
                "runs": int(_safe_float(row.get("runs"))),
                "distance_proxy_km": round(_safe_float(row.get("total_distance_proxy_km")), 2),
            }
        )

    return {
        "range_days": int(days),
        "weeks": rows,
        "summary": {
            "weeks": len(rows),
            "total_distance_km": round(sum(r["distance_km"] for r in rows), 2),
            "total_tss": round(sum(r["tss"] for r in rows), 1),
            "total_activities": int(sum(r["runs"] for r in rows)),
        },
    }


def _build_week_outlook_payload(
    db_path: Path,
    days: int,
    start_day: str | None,
    end_day: str | None,
    sport: str | None,
    metric: str,
    compare: str,
    week_start: str | None,
) -> dict[str, Any]:
    metric_key = str(metric or "tss").strip().lower()
    if metric_key not in {"tss", "rtss", "distance_eqv_km"}:
        metric_key = "tss"

    compare_key = str(compare or "planned").strip().lower()
    compare_offsets = {
        "planned": 0,
        "previous_week": -7,
        "two_weeks_ago": -14,
        "three_weeks_ago": -21,
        "four_weeks_ago": -28,
    }
    if compare_key not in compare_offsets:
        compare_key = "planned"

    metrics_df = _metrics_for_filters(
        db_path=db_path,
        days=days,
        start_day=start_day,
        end_day=end_day,
        sport=sport,
    )
    if metrics_df.empty and not start_day and not end_day:
        # Fallback for athletes with only historical data outside the default lookback.
        metrics_df = _metrics_for_filters(
            db_path=db_path,
            days=36500,
            start_day=None,
            end_day=None,
            sport=sport,
        )
    if metrics_df.empty:
        return {
            "metric": metric_key,
            "compare": compare_key,
            "week_start": "",
            "week_end": "",
            "compare_week_start": "",
            "compare_week_end": "",
            "goal": 0.0,
            "goal_progress_pct": 0,
            "wtd_current": 0.0,
            "wtd_compare": 0.0,
            "remaining_to_go": 0.0,
            "projected_finish": None,
            "estimated_fatigue_eow": None,
            "week_total_current": 0.0,
            "week_total_compare": 0.0,
            "rows": [],
            "min_week_start": "",
            "max_week_start": "",
            "today_day": "",
        }

    daily = metrics_df.copy()
    daily["day"] = pd.to_datetime(daily["start_time_utc"], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
    daily = daily.dropna(subset=["day"])
    if daily.empty:
        return {
            "metric": metric_key,
            "compare": compare_key,
            "week_start": "",
            "week_end": "",
            "compare_week_start": "",
            "compare_week_end": "",
            "goal": 0.0,
            "goal_progress_pct": 0,
            "wtd_current": 0.0,
            "wtd_compare": 0.0,
            "remaining_to_go": 0.0,
            "projected_finish": None,
            "estimated_fatigue_eow": None,
            "week_total_current": 0.0,
            "week_total_compare": 0.0,
            "rows": [],
            "min_week_start": "",
            "max_week_start": "",
            "today_day": "",
        }

    daily_agg = (
        daily.groupby("day", as_index=False)
        .agg(
            tss=("tss", "sum"),
            rtss=("rtss", "sum"),
            distance_eqv_km=("distance_proxy_km", "sum"),
        )
        .sort_values("day")
    )
    daily_agg["tss"] = pd.to_numeric(daily_agg["tss"], errors="coerce").fillna(0.0)
    daily_agg["rtss"] = pd.to_numeric(daily_agg["rtss"], errors="coerce").fillna(0.0)
    daily_agg["distance_eqv_km"] = pd.to_numeric(daily_agg["distance_eqv_km"], errors="coerce").fillna(0.0)
    daily_agg["week_start"] = daily_agg["day"].map(_week_start_monday)

    min_week_start = pd.to_datetime(daily_agg["week_start"], errors="coerce").min()
    max_week_start = pd.to_datetime(daily_agg["week_start"], errors="coerce").max()

    if week_start:
        ws = pd.to_datetime(week_start, errors="coerce")
        ws = _week_start_monday(ws) if pd.notna(ws) else pd.NaT
    else:
        ws = _week_start_monday(pd.Timestamp(datetime.now().astimezone().date()))
    if pd.isna(ws):
        ws = max_week_start
    if pd.notna(min_week_start) and ws < min_week_start:
        ws = min_week_start
    if pd.notna(max_week_start) and ws > max_week_start:
        ws = max_week_start

    week_end = ws + pd.Timedelta(days=6)
    if compare_key == "planned":
        compare_ws = ws
        compare_we = week_end
    else:
        compare_ws = ws + pd.Timedelta(days=int(compare_offsets[compare_key]))
        compare_we = compare_ws + pd.Timedelta(days=6)

    planned_metric_map: dict[pd.Timestamp, float] = {}
    planned_tss_map: dict[pd.Timestamp, float] = {}
    planned_remaining_metric_total = 0.0
    today = pd.Timestamp(datetime.now().astimezone().date()).normalize()
    if compare_key == "planned":
        planned_metric_map, planned_tss_map, planned_remaining_metric_total = _planned_daily_metric_map(
            db_path=db_path,
            week_start=ws,
            week_end=week_end,
            metric_key=metric_key,
            sport_filter=sport,
            today_local_day=today,
        )

    day_rows: list[dict[str, Any]] = []
    week_total_current = 0.0
    week_total_compare = 0.0
    cutoff_day = min(today, week_end)
    day_offset = int(max(min((cutoff_day - ws).days, 6), 0))
    compare_cutoff = compare_ws + pd.Timedelta(days=day_offset) if compare_key != "planned" else cutoff_day
    wtd_current = 0.0
    wtd_compare = 0.0
    remaining_to_go = 0.0

    for i in range(7):
        day = ws + pd.Timedelta(days=i)
        cday = compare_ws + pd.Timedelta(days=i) if compare_key != "planned" else day
        current_tss_v = float(
            pd.to_numeric(
                daily_agg.loc[daily_agg["day"] == day, "tss"],
                errors="coerce",
            ).fillna(0.0).sum()
        )
        current_v = float(
            pd.to_numeric(
                daily_agg.loc[daily_agg["day"] == day, metric_key],
                errors="coerce",
            ).fillna(0.0).sum()
        )
        if compare_key == "planned":
            compare_v = float(planned_metric_map.get(day, 0.0))
        else:
            compare_v = float(
                pd.to_numeric(
                    daily_agg.loc[daily_agg["day"] == cday, metric_key],
                    errors="coerce",
                ).fillna(0.0).sum()
            )
        week_total_current += current_v
        week_total_compare += compare_v
        if day <= cutoff_day:
            wtd_current += current_v
        if compare_key != "planned":
            if cday <= compare_cutoff:
                wtd_compare += compare_v
        day_rows.append(
            {
                "day": day.date().isoformat(),
                "day_label": day.strftime("%d %b (%a)"),
                "current": round(current_v, 1),
                "compare": round(compare_v, 1),
                "current_tss": round(current_tss_v, 1),
                "is_today": bool(day == today),
                "is_future": bool(day > today),
            }
        )

    if compare_key == "planned":
        # Sum raw daily planned values up to cutoff, then round only at payload formatting.
        wtd_compare = float(
            pd.to_numeric(
                pd.Series([v for d, v in planned_metric_map.items() if pd.Timestamp(d) <= cutoff_day], dtype=float),
                errors="coerce",
            ).fillna(0.0).sum()
        )
        remaining_to_go = float(planned_remaining_metric_total)

    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    latest_lt_pace = float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    if metric_key == "distance_eqv_km":
        goal = _weekly_distance_target_from_lt_pace(latest_lt_pace)
    elif metric_key == "rtss":
        goal = _weekly_tss_target_from_lt_pace(latest_lt_pace) * 0.90
    else:
        goal = _weekly_tss_target_from_lt_pace(latest_lt_pace) * 1.10

    progress = int(round((week_total_current / goal) * 100.0)) if goal > 0 else 0
    projected_finish = float(wtd_current + remaining_to_go) if compare_key == "planned" else float("nan")
    estimated_fatigue_eow: float | None = None
    if compare_key == "planned":
        try:
            tss_map = (
                daily_agg.groupby("day", as_index=False)["tss"]
                .sum()
                .set_index("day")["tss"]
                .to_dict()
            )
            # Match v1 behavior: use planned projection after the last day with actual activity.
            # This allows "today" to use planned TSS when no actual activity exists yet.
            actual_days = pd.to_datetime(list(tss_map.keys()), errors="coerce")
            actual_days = actual_days[pd.notna(actual_days)]
            last_actual_day = pd.Timestamp(actual_days.max()).normalize() if len(actual_days) else pd.NaT
            hist_start = ws - pd.Timedelta(days=42)
            full_days = pd.date_range(start=hist_start, end=week_end, freq="D")
            vals: list[float] = []
            for d in full_days:
                dd = pd.Timestamp(d).normalize()
                if pd.notna(last_actual_day) and dd <= last_actual_day:
                    vals.append(float(tss_map.get(dd, 0.0)))
                else:
                    vals.append(float(planned_tss_map.get(dd, 0.0)))
            if vals:
                alpha = 2.0 / (7.0 + 1.0)
                fatigue_series = pd.Series(vals, dtype=float).ewm(alpha=alpha, adjust=False).mean()
                estimated_fatigue_eow = float(fatigue_series.iloc[-1])
        except Exception:
            estimated_fatigue_eow = None

    return {
        "metric": metric_key,
        "compare": compare_key,
        "week_start": ws.date().isoformat(),
        "week_end": week_end.date().isoformat(),
        "compare_week_start": compare_ws.date().isoformat(),
        "compare_week_end": compare_we.date().isoformat(),
        "goal": round(float(goal), 1),
        "goal_progress_pct": int(progress),
        "wtd_current": round(float(wtd_current), 1),
        "wtd_compare": round(float(wtd_compare), 1),
        "remaining_to_go": round(float(remaining_to_go), 1),
        "projected_finish": round(float(projected_finish), 1) if math.isfinite(projected_finish) else None,
        "estimated_fatigue_eow": (
            round(float(estimated_fatigue_eow), 1)
            if estimated_fatigue_eow is not None and math.isfinite(float(estimated_fatigue_eow))
            else None
        ),
        "week_total_current": round(float(week_total_current), 1),
        "week_total_compare": round(float(week_total_compare), 1),
        "rows": day_rows,
        "min_week_start": min_week_start.date().isoformat() if pd.notna(min_week_start) else "",
        "max_week_start": max_week_start.date().isoformat() if pd.notna(max_week_start) else "",
        "today_day": today.date().isoformat(),
    }


def _planned_activity_label(parsed_json: Any) -> str:
    segments: list[dict[str, Any]] = []
    if isinstance(parsed_json, list):
        segments = [s for s in parsed_json if isinstance(s, dict)]
    elif isinstance(parsed_json, str) and parsed_json.strip():
        try:
            parsed = json.loads(parsed_json)
            if isinstance(parsed, list):
                segments = [s for s in parsed if isinstance(s, dict)]
        except Exception:
            segments = []

    kinds_seen: list[str] = []
    for seg in segments:
        kind = str(seg.get("kind") or "").strip().lower()
        if kind and kind not in kinds_seen:
            kinds_seen.append(kind)
    if not kinds_seen:
        return "-"
    return ", ".join([k.replace("_", " ").title() for k in kinds_seen])


def _build_planned_activities_payload(
    db_path: Path,
    owner: str,
    weeks: int = 4,
) -> dict[str, Any]:
    planned_rows = get_planned_activities_df(db_path=db_path)
    if planned_rows.empty:
        return {
            "owner": owner,
            "goals": {"tss": 0.0, "rtss": 0.0, "distance_eqv_km": 0.0},
            "weeks": [],
            "rows": [],
        }

    lthr_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LTHR_CURVE,
        value_key="lthr_bpm",
        fallback_value=DEFAULT_LTHR,
    )
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)
    planned_rows = _compute_planned_rows_metrics_df(
        planned_rows=planned_rows,
        lthr_curve_points=lthr_curve,
        lthr_default_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
        lt_pace_curve_points=pace_curve,
        lt_pace_default_sec=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
        specificity_profile=specificity_profile,
    )
    if planned_rows.empty:
        return {
            "owner": owner,
            "goals": {"tss": 0.0, "rtss": 0.0, "distance_eqv_km": 0.0},
            "weeks": [],
            "rows": [],
        }

    planned_rows["day"] = pd.to_datetime(planned_rows.get("day_utc"), errors="coerce").dt.normalize()
    planned_rows = planned_rows.dropna(subset=["day"]).copy()
    if planned_rows.empty:
        return {
            "owner": owner,
            "goals": {"tss": 0.0, "rtss": 0.0, "distance_eqv_km": 0.0},
            "weeks": [],
            "rows": [],
        }

    # v2 UI expects full week history in selectors/tables (not only a narrow window around current week).
    # Keep all planned rows in scope so users can choose any prior/future week.
    in_scope_rows = planned_rows.copy()

    latest_lt_pace = float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    goals = {
        "tss": round(_weekly_tss_target_from_lt_pace(latest_lt_pace) * 1.10, 1),
        "rtss": round(_weekly_tss_target_from_lt_pace(latest_lt_pace) * 0.90, 1),
        "distance_eqv_km": round(_weekly_distance_target_from_lt_pace(latest_lt_pace), 1),
    }

    weeks_rows: list[dict[str, Any]] = []
    if not in_scope_rows.empty:
        wk = in_scope_rows.copy()
        wk["week_start"] = wk["day"].map(_week_start_monday)
        wk["duration_s"] = pd.to_numeric(wk.get("duration_s"), errors="coerce").fillna(0.0)
        wk["if_proxy"] = pd.to_numeric(wk.get("if_proxy"), errors="coerce").fillna(0.0)
        wk["if_weighted"] = wk["if_proxy"] * wk["duration_s"]
        grouped = (
            wk.groupby("week_start", as_index=False)
            .agg(
                planned_activities=("line_no", "count"),
                duration_s=("duration_s", "sum"),
                tss=("tss", "sum"),
                rtss=("rtss", "sum"),
                distance_eqv_km=("distance_proxy_km", "sum"),
                if_weighted=("if_weighted", "sum"),
            )
            .sort_values("week_start")
        )
        for _, row in grouped.iterrows():
            ws = pd.Timestamp(row["week_start"]).normalize()
            we = ws + pd.Timedelta(days=6)
            dur_s = _safe_float(row.get("duration_s"))
            if_pct = (_safe_float(row.get("if_weighted")) / dur_s * 100.0) if dur_s > 0 else 0.0
            weeks_rows.append(
                {
                    "week_start": ws.date().isoformat(),
                    "week_end": we.date().isoformat(),
                    "week_label": f"{ws.strftime('%d %b')} - {we.strftime('%d %b')}",
                    "planned_activities": int(_safe_float(row.get("planned_activities"))),
                    "duration_h": round(dur_s / 3600.0, 1),
                    "tss": round(_safe_float(row.get("tss")), 1),
                    "rtss": round(_safe_float(row.get("rtss")), 1),
                    "distance_eqv_km": round(_safe_float(row.get("distance_eqv_km")), 1),
                    "if_proxy_pct": round(if_pct, 1),
                }
            )

    day_rows: list[dict[str, Any]] = []
    for _, row in in_scope_rows.sort_values(["day", "line_no"], ascending=[True, True]).iterrows():
        day_rows.append(
            {
                "day_utc": pd.Timestamp(row.get("day")).date().isoformat(),
                "line_no": int(_safe_float(row.get("line_no"))),
                "activity": _planned_activity_label(row.get("parsed_json")),
                "workout_text": str(row.get("workout_text") or ""),
                "manual_done": bool(_safe_float(row.get("manual_done")) > 0),
                "tss": round(_safe_float(row.get("tss")), 1),
                "rtss": round(_safe_float(row.get("rtss")), 1),
                "distance_eqv_km": round(_safe_float(row.get("distance_proxy_km")), 1),
                "duration_h": round(_safe_float(row.get("duration_s")) / 3600.0, 1),
                "if_proxy_pct": round(_safe_float(row.get("if_proxy")) * 100.0, 1),
            }
        )

    return {
        "owner": owner,
        "goals": goals,
        "weeks": weeks_rows,
        "rows": day_rows,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
def auth_login(payload: LoginRequest) -> dict[str, Any]:
    if not _auth_enabled():
        token = _build_token(user="default", role="admin")
        return {"token": token, "user": "default", "role": "admin"}

    users = _auth_users()
    if not users:
        raise HTTPException(status_code=503, detail="Auth enabled but no users configured")

    resolved_user, user_data = resolve_user(users, payload.username)
    if not user_data or not resolved_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not password_matches(payload.password, str(user_data.get("password_hash") or "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = str(user_data.get("role") or "viewer").strip().lower()
    token = _build_token(user=resolved_user, role=role)
    return {"token": token, "user": resolved_user, "role": role}


@app.get("/api/v1/auth/me")
def auth_me(authorization: str | None = Header(default=None, alias="Authorization")) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    owner = _resolve_owner(ctx, None)
    return {"user": ctx["user"], "role": ctx["role"], "owner": owner, "auth_enabled": _auth_enabled()}


@app.get("/api/v1/auth/owners")
def auth_owners(authorization: str | None = Header(default=None, alias="Authorization")) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    if str(ctx.get("role")) == "admin":
        users = _auth_users()
        options = sorted(users.keys()) if users else [ctx["user"]]
        return {"owners": options}
    return {"owners": [ctx["user"]]}


@app.get("/api/v1/overview")
def overview(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, int | str]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    if not db_path.exists():
        return {
            "owner": resolved_owner,
            "db_path": str(db_path),
            "activities": 0,
            "activity_details": 0,
            "wellness_daily": 0,
        }

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        try:
            activities = cur.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        except Exception:
            activities = 0
        try:
            activity_details = cur.execute("SELECT COUNT(*) FROM activity_details").fetchone()[0]
        except Exception:
            activity_details = 0
        try:
            wellness_daily = cur.execute("SELECT COUNT(*) FROM wellness_daily").fetchone()[0]
        except Exception:
            wellness_daily = 0

    return {
        "owner": resolved_owner,
        "db_path": str(db_path),
        "activities": int(activities),
        "activity_details": int(activity_details),
        "wellness_daily": int(wellness_daily),
    }


@app.get("/api/v1/settings")
def settings_view(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    if_raw = get_setting(db_path, SETTINGS_KEY_IF_ZONE_THRESHOLDS)
    try:
        if_payload = json.loads(if_raw) if if_raw else None
    except Exception:
        if_payload = None
    if_thresholds = _normalize_if_zone_thresholds(if_payload)

    spec_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)

    lthr_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LTHR_CURVE,
        value_key="lthr_bpm",
        fallback_value=DEFAULT_LTHR,
    )
    lt_pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    lthr_rows = [
        {"date": d.astimezone(timezone.utc).date().isoformat(), "lthr_bpm": round(float(v), 2)}
        for d, v in lthr_curve
    ]
    pace_rows = [
        {"date": d.astimezone(timezone.utc).date().isoformat(), "lt_pace_sec_per_km": round(float(v), 2)}
        for d, v in lt_pace_curve
    ]

    injury_rows: list[dict[str, str]] = []
    raw_injury = get_setting(db_path, SETTINGS_KEY_INJURY_WINDOWS)
    if raw_injury:
        try:
            payload = json.loads(raw_injury)
            if isinstance(payload, list):
                injury_rows = _normalize_injury_windows(payload)
        except Exception:
            injury_rows = []

    return {
        "owner": resolved_owner,
        "db_path": str(db_path),
        "if_zone_thresholds": if_thresholds,
        "specificity_profile": spec_profile,
        "lthr_curve": lthr_rows,
        "lt_pace_curve": pace_rows,
        "injury_windows": injury_rows,
    }


@app.put("/api/v1/settings")
def settings_update(
    payload: UpdateSettingsRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    updated: list[str] = []

    if payload.if_zone_thresholds is not None:
        normalized = _normalize_if_zone_thresholds(payload.if_zone_thresholds)
        save_setting(db_path, SETTINGS_KEY_IF_ZONE_THRESHOLDS, _settings_json(normalized))
        updated.append("if_zone_thresholds")

    if payload.specificity_profile is not None:
        fallback = _safe_float(payload.specificity_profile.get("non_running")) if isinstance(payload.specificity_profile, dict) else 0.8
        normalized = _normalize_specificity_profile(payload.specificity_profile, fallback_default=max(fallback, 0.1))
        save_setting(db_path, SETTINGS_KEY_ACTIVITY_SPECIFICITY, _settings_json(normalized))
        save_setting(db_path, SETTINGS_KEY_NON_RUNNING_FACTOR, f"{float(normalized['non_running']):.4f}")
        updated.append("specificity_profile")

    if payload.lthr_curve is not None:
        normalized = _normalize_lthr_curve(payload.lthr_curve)
        save_setting(db_path, SETTINGS_KEY_LTHR_CURVE, _settings_json(normalized))
        updated.append("lthr_curve")

    if payload.lt_pace_curve is not None:
        normalized = _normalize_lt_pace_curve(payload.lt_pace_curve)
        save_setting(db_path, SETTINGS_KEY_LT_PACE_CURVE, _settings_json(normalized))
        updated.append("lt_pace_curve")

    if payload.injury_windows is not None:
        normalized = _normalize_injury_windows(payload.injury_windows)
        save_setting(db_path, SETTINGS_KEY_INJURY_WINDOWS, _settings_json(normalized))
        updated.append("injury_windows")

    return {"updated": updated}


@app.get("/api/v1/data-extract/status")
def data_extract_status(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    last_sync = get_last_sync(db_path)
    counts = get_table_counts(db_path)
    role = str(ctx.get("role") or "viewer").strip().lower()
    current_user = str(ctx.get("user") or "").strip()
    runtime_email, runtime_password = _runtime_garmin_credentials(resolved_owner)
    garmin_email, garmin_password, garmin_source = _resolve_garmin_credentials(ctx, resolved_owner)
    return {
        "owner": resolved_owner,
        "db_path": str(db_path),
        "counts": counts,
        "last_sync": last_sync,
        "garmin_credentials_available": bool(garmin_email and garmin_password),
        "garmin_credentials_source": garmin_source,
        "garmin_runtime_credentials_set": bool(runtime_email and runtime_password),
        "garmin_credentials_hint": (
            "Using configured Garmin credentials for this owner scope."
            if role == "admin" and resolved_owner == current_user
            else "Provide Garmin credentials for this owner scope (memory only)."
            if role == "admin"
            else "Provide Garmin credentials for this user session (memory only)."
        ),
        "import_dir": str((Path(load_config().import_dir) if hasattr(load_config(), "import_dir") else (TEMPERANCE_SRC / "data" / "import"))),
        "extract_progress": _extract_progress_get(resolved_owner),
    }


@app.post("/api/v1/data-extract/credentials")
def data_extract_credentials(
    payload: GarminCredentialsRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    role = str(ctx.get("role") or "viewer").strip().lower()
    current_user = str(ctx.get("user") or "").strip()

    if role == "admin" and resolved_owner == current_user:
        env_email, env_password = _garmin_credentials_from_env()
        return {
            "updated": False,
            "source": "env" if (env_email and env_password) else "missing",
            "message": "Using configured Garmin credentials for this owner scope.",
        }

    email = str(payload.email or "").strip()
    password = str(payload.password or "").strip()
    if not email and not password:
        _clear_runtime_garmin_credentials(resolved_owner)
        return {
            "updated": True,
            "source": "missing",
            "message": "Owner credentials cleared from memory." if role == "admin" else "Session credentials cleared.",
        }
    if not email or not password:
        raise HTTPException(status_code=400, detail="Both email and password are required.")

    _set_runtime_garmin_credentials(resolved_owner, email=email, password=password)
    return {
        "updated": True,
        "source": "session",
        "message": "Owner credentials saved in memory only." if role == "admin" else "Session credentials saved in memory only.",
    }


@app.post("/api/v1/data-extract/sync")
def data_extract_sync(
    payload: SyncRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    source = str(payload.source or "both").strip().lower()
    if source not in {"garmin_api", "file_import", "both"}:
        source = "both"
    profile = str(payload.garmin_profile or "quick").strip().lower()
    if profile not in {"quick", "deep"}:
        profile = "quick"
    days_back = max(7, min(int(payload.days_back), 3650))

    messages: list[str] = []
    details: dict[str, Any] = {}
    total_rows = 0
    garmin_email, garmin_password, garmin_source = _resolve_garmin_credentials(ctx, resolved_owner)
    latest = get_latest_activity_time(db_path)

    if source in {"garmin_api", "both"}:
        if not (garmin_email and garmin_password):
            messages.append("Garmin credentials missing. Add credentials for the active owner scope.")
            details["garmin"] = {"skipped": True, "reason": "credentials_missing"}
        else:
            if profile == "quick":
                rows = fetch_garmin_runs(
                    email=garmin_email,
                    password=garmin_password,
                    days_back=days_back,
                    since_utc=latest,
                )
                changed = upsert_activities(db_path, rows)
                total_rows += len(rows)
                details["garmin"] = {"profile": "quick", "rows": len(rows), "db_changes": int(changed), "credentials_source": garmin_source}
            else:
                deep_start = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()
                extract = fetch_garmin_comprehensive(
                    email=garmin_email,
                    password=garmin_password,
                    start_day=deep_start,
                    end_day=datetime.now(timezone.utc).date(),
                    include_activity_details=True,
                    include_splits=True,
                    include_wellness=True,
                    raw_export_dir=None,
                    progress_cb=None,
                )
                n_a = upsert_activities(db_path, extract.activities)
                n_d = upsert_activity_details(db_path, extract.activity_details)
                n_r = upsert_activity_records(db_path, extract.activity_records)
                n_sp = upsert_activity_splits(db_path, extract.activity_splits)
                n_s = upsert_sleep_daily(db_path, extract.sleep_daily)
                n_w = upsert_wellness_daily(db_path, extract.wellness_daily)
                total_rows += len(extract.activities)
                details["garmin"] = {
                    "profile": "deep",
                    "credentials_source": garmin_source,
                    "activities": len(extract.activities),
                    "details": len(extract.activity_details),
                    "records": len(extract.activity_records),
                    "splits": len(extract.activity_splits),
                    "sleep": len(extract.sleep_daily),
                    "wellness": len(extract.wellness_daily),
                    "errors": extract.errors[:20],
                    "db_changes": {
                        "activities": int(n_a),
                        "details": int(n_d),
                        "records": int(n_r),
                        "splits": int(n_sp),
                        "sleep": int(n_s),
                        "wellness": int(n_w),
                    },
                }

    if source in {"file_import", "both"}:
        import_dir = Path(load_config().import_dir) if hasattr(load_config(), "import_dir") else (TEMPERANCE_SRC / "data" / "import")
        rows = import_runs_from_folder(import_dir=import_dir, days_back=days_back)
        changed = upsert_activities(db_path, rows)
        total_rows += len(rows)
        details["file_import"] = {"rows": len(rows), "db_changes": int(changed), "import_dir": str(import_dir)}

    success = total_rows > 0 or any("missing" in m.lower() for m in messages)
    msg = " | ".join(messages) if messages else f"total_rows={total_rows}"
    log_sync(db_path, source=f"v2_sync_{source}_{profile}", success=success, message=msg)
    return {"success": success, "messages": messages, "total_rows": total_rows, "details": details}


@app.post("/api/v1/data-extract/comprehensive")
def data_extract_comprehensive(
    payload: ComprehensiveExtractRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    garmin_email, garmin_password, _garmin_source = _resolve_garmin_credentials(ctx, resolved_owner)
    if not (garmin_email and garmin_password):
        raise HTTPException(
            status_code=400,
            detail="Garmin credentials missing. Add credentials for the active owner scope.",
        )

    try:
        start_day = datetime.fromisoformat(str(payload.start_day)).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_day. Use YYYY-MM-DD.")
    end_day = datetime.now(timezone.utc).date()

    if bool(payload.incremental_only):
        latest = get_latest_activity_time(db_path)
        latest_recovery = get_latest_recovery_day(db_path) if bool(payload.include_wellness) else None
        anchors = [a for a in [latest, latest_recovery] if a is not None]
        if anchors:
            anchor = min(anchors)
            start_day = max(start_day, (anchor - timedelta(days=2)).date())

    existing_progress = _extract_progress_get(resolved_owner)
    if bool(existing_progress.get("running")):
        raise HTTPException(status_code=409, detail="A comprehensive extract is already running for this owner.")

    _extract_progress_start(resolved_owner, start_day.isoformat(), end_day.isoformat())
    _extract_progress_append(
        resolved_owner,
        f"[config] include_details={bool(payload.include_details)} include_wellness={bool(payload.include_wellness)} incremental_only={bool(payload.incremental_only)}",
    )
    worker = threading.Thread(
        target=_run_comprehensive_extract_background,
        kwargs={
            "owner": resolved_owner,
            "db_path": db_path,
            "garmin_email": garmin_email,
            "garmin_password": garmin_password,
            "start_day": start_day,
            "end_day": end_day,
            "include_details": bool(payload.include_details),
            "include_wellness": bool(payload.include_wellness),
        },
        daemon=True,
    )
    worker.start()
    return {
        "success": True,
        "start_day": start_day.isoformat(),
        "end_day": end_day.isoformat(),
        "summary": "Comprehensive extract started in background.",
        "errors": [],
    }


@app.get("/api/v1/week-outlook")
def week_outlook_view(
    days: int = Query(default=3000, ge=14, le=10000),
    metric: str = Query(default="tss"),
    compare: str = Query(default="planned"),
    week_start: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    payload = _build_week_outlook_payload(
        db_path=db_path,
        days=days,
        start_day=None,
        end_day=None,
        sport=None,
        metric=metric,
        compare=compare,
        week_start=week_start,
    )
    payload["owner"] = resolved_owner
    payload["db_path"] = str(db_path)
    return payload


@app.get("/api/v1/athlete-progression")
def athlete_progression_view(
    days: int = Query(default=3000, ge=30, le=10000),
    activity_filter: str = Query(default="all"),
    aggregation: str = Query(default="weekly"),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    payload = _build_athlete_progression_payload(
        db_path=db_path,
        days=days,
        activity_filter=activity_filter,
        aggregation=aggregation,
        owner=resolved_owner,
    )
    payload["db_path"] = str(db_path)
    return payload


@app.get("/api/v1/wellness")
def wellness_view(
    days: int = Query(default=365, ge=30, le=5000),
    aggregation: str = Query(default="weekly"),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    payload = _build_wellness_payload(
        db_path=db_path,
        days=days,
        aggregation=aggregation,
        owner=resolved_owner,
    )
    payload["db_path"] = str(db_path)
    return payload


@app.get("/api/v1/dashboard")
def activity_dashboard(
    weeks: int = Query(default=6, ge=1, le=52),
    week_offset: int = Query(default=0, ge=0, le=5200),
    sport: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    payload = _build_activity_dashboard_payload(
        db_path=db_path,
        visible_weeks=weeks,
        week_offset=week_offset,
        sport=sport,
    )
    payload["owner"] = resolved_owner
    payload["db_path"] = str(db_path)
    return payload


@app.get("/api/v1/planned-activities")
def planned_activities_view(
    weeks: int = Query(default=4, ge=1, le=12),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    payload = _build_planned_activities_payload(
        db_path=db_path,
        owner=resolved_owner,
        weeks=weeks,
    )
    payload["db_path"] = str(db_path)
    return payload


@app.patch("/api/v1/planned-activities/manual-done")
def planned_activity_manual_done(
    payload: PlannedManualDoneRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    updated = set_planned_activity_manual_done(
        db_path=db_path,
        day_utc=str(payload.day_utc),
        line_no=int(payload.line_no),
        manual_done=bool(payload.manual_done),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Planned activity not found")
    return {"updated": True}


@app.delete("/api/v1/planned-activities")
def planned_activity_delete(
    day_utc: str = Query(...),
    line_no: int = Query(..., ge=1),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    deleted = delete_planned_activities(
        db_path=db_path,
        keys=[(str(day_utc), int(line_no))],
    )
    if deleted <= 0:
        raise HTTPException(status_code=404, detail="Planned activity not found")
    return {"deleted": int(deleted)}


@app.post("/api/v1/planned-activities/ingest")
def planned_activities_ingest(
    payload: PlannedIngestRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    entry_text = str(payload.entry_text or "")

    if len(entry_text) > int(MAX_PLANNED_ENTRY_CHARS):
        raise HTTPException(status_code=400, detail=f"Input too large. Max {MAX_PLANNED_ENTRY_CHARS} characters per save.")

    entries = _split_dated_activity_entries(entry_text)
    if not entries:
        raise HTTPException(status_code=400, detail="Input is empty. Use `[date]:[activity]`.")
    if len(entries) > int(MAX_PLANNED_ENTRIES_PER_SAVE):
        raise HTTPException(status_code=400, detail=f"Too many entries in one save. Max {MAX_PLANNED_ENTRIES_PER_SAVE}.")

    today_local = pd.Timestamp(datetime.now().astimezone().date())
    previous_sunday = today_local - pd.Timedelta(days=int(today_local.weekday()) + 1)

    existing = get_planned_activities_df(db_path=db_path)
    max_line_by_day = existing.groupby("day_utc")["line_no"].max().to_dict() if not existing.empty else {}
    existing_signatures: set[str] = set()
    if not existing.empty:
        for _, er in existing.iterrows():
            existing_signatures.add(_planned_row_signature(str(er.get("day_utc") or ""), str(er.get("workout_text") or "")))

    lthr_curve = _load_curve_points(db_path=db_path, key=SETTINGS_KEY_LTHR_CURVE, value_key="lthr_bpm", fallback_value=DEFAULT_LTHR)
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    lthr_default = float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR
    pace_default = float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM

    rows_to_upsert: list[dict[str, Any]] = []
    errors: list[str] = []
    for idx, raw_entry in enumerate(entries, start=1):
        day_ts, normalized, parse_err = _parse_dated_activity_entry(raw_entry)
        if parse_err:
            errors.append(f"entry {idx}: {parse_err}")
            continue
        if day_ts is None:
            errors.append(f"entry {idx}: could not parse date")
            continue
        if day_ts < previous_sunday:
            errors.append(f"entry {idx}: date `{day_ts:%Y-%m-%d}` is before `{previous_sunday:%Y-%m-%d}`")
            continue

        lthr_for_day = float(_curve_value_at(lthr_curve, lthr_default, day_ts))
        pace_for_day = float(_curve_value_at(pace_curve, pace_default, day_ts))
        segs, warns = _expand_planned_segments(
            normalized,
            lthr_bpm=lthr_for_day,
            threshold_pace_sec_per_km=pace_for_day,
        )
        if warns or not segs:
            details = "; ".join(warns[:2]) if warns else "Could not parse this activity."
            errors.append(f"entry {idx}: {details}")
            continue

        day_key = day_ts.date().isoformat()
        sig = _planned_row_signature(day_key, normalized)
        if sig in existing_signatures:
            errors.append(f"entry {idx}: duplicate skipped for `{day_key}` (`{normalized}` already exists).")
            continue

        next_line_no = int(max_line_by_day.get(day_key, 0)) + 1
        max_line_by_day[day_key] = next_line_no
        rows_to_upsert.append(
            {
                "day_utc": day_key,
                "line_no": next_line_no,
                "workout_text": normalized,
                "parsed_json": segs,
                "manual_done": False,
            }
        )
        existing_signatures.add(sig)

    if rows_to_upsert:
        upsert_planned_activities_rows(db_path=db_path, rows=rows_to_upsert)

    return {
        "saved_count": int(len(rows_to_upsert)),
        "errors": errors[:20],
    }


@app.patch("/api/v1/planned-activities/workout")
def planned_activity_workout_update(
    payload: PlannedWorkoutUpdateRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    day_utc = str(payload.day_utc or "").strip()
    line_no = int(payload.line_no)
    workout_text = _normalize_plan_text(str(payload.workout_text or ""))
    if not day_utc or line_no <= 0:
        raise HTTPException(status_code=400, detail="Invalid day_utc or line_no")
    if not workout_text:
        raise HTTPException(status_code=400, detail="Workout text cannot be empty")

    existing = get_planned_activities_df(db_path=db_path, start_day_utc=day_utc, end_day_utc=day_utc)
    if existing.empty:
        raise HTTPException(status_code=404, detail="Planned activity not found")
    existing = existing[pd.to_numeric(existing.get("line_no"), errors="coerce").fillna(0).astype(int) == line_no]
    if existing.empty:
        raise HTTPException(status_code=404, detail="Planned activity not found")
    current_row = existing.iloc[0]

    day_ts = pd.to_datetime(day_utc, errors="coerce")
    if pd.isna(day_ts):
        raise HTTPException(status_code=400, detail="Invalid day_utc")

    lthr_curve = _load_curve_points(db_path=db_path, key=SETTINGS_KEY_LTHR_CURVE, value_key="lthr_bpm", fallback_value=DEFAULT_LTHR)
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    lthr_default = float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR
    pace_default = float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    lthr_for_day = float(_curve_value_at(lthr_curve, lthr_default, day_ts))
    pace_for_day = float(_curve_value_at(pace_curve, pace_default, day_ts))
    segs, warns = _expand_planned_segments(
        workout_text,
        lthr_bpm=lthr_for_day,
        threshold_pace_sec_per_km=pace_for_day,
    )
    if warns or not segs:
        details = "; ".join(warns[:2]) if warns else "Could not parse this activity."
        raise HTTPException(status_code=400, detail=details)

    manual_done = (
        bool(payload.manual_done)
        if payload.manual_done is not None
        else bool(_safe_float(current_row.get("manual_done")) > 0)
    )
    upsert_planned_activities_rows(
        db_path=db_path,
        rows=[
            {
                "day_utc": day_utc,
                "line_no": line_no,
                "workout_text": workout_text,
                "parsed_json": segs,
                "manual_done": manual_done,
            }
        ],
    )
    return {"updated": True}


@app.get("/api/v1/custom-activities")
def custom_activities_view(
    weeks: int | None = Query(default=None, ge=1, le=5200),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    raw = get_custom_activities_df(db_path=db_path)
    if raw.empty:
        return {"owner": resolved_owner, "rows": [], "weeks": []}

    lthr_curve = _load_curve_points(db_path=db_path, key=SETTINGS_KEY_LTHR_CURVE, value_key="lthr_bpm", fallback_value=DEFAULT_LTHR)
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)
    custom_rows = raw.rename(columns={"activity_text": "workout_text"}).copy()
    custom_rows["manual_done"] = False
    metrics = _compute_planned_rows_metrics_df(
        planned_rows=custom_rows,
        lthr_curve_points=lthr_curve,
        lthr_default_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
        lt_pace_curve_points=pace_curve,
        lt_pace_default_sec=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
        specificity_profile=specificity_profile,
    )
    merged = custom_rows.merge(
        metrics[["day_utc", "line_no", "tss", "rtss", "distance_proxy_km", "duration_s", "if_proxy", "pace_proxy_sec_per_km"]],
        on=["day_utc", "line_no"],
        how="left",
        suffixes=("", "_metric"),
    )
    merged["day"] = pd.to_datetime(merged.get("day_utc"), errors="coerce")
    merged = merged.dropna(subset=["day"]).copy()
    merged["week_start"] = (merged["day"] - pd.to_timedelta(merged["day"].dt.weekday, unit="D")).dt.normalize()
    merged = merged.sort_values(["day_utc", "line_no"], ascending=[False, False]).copy()

    rows_out: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        rows_out.append(
            {
                "day_utc": str(row.get("day_utc") or ""),
                "line_no": int(_safe_float(row.get("line_no"))),
                "activity": _planned_activity_label(row.get("parsed_json")),
                "activity_text": str(row.get("workout_text") or ""),
                "duration_h": round(_safe_float(row.get("duration_s")) / 3600.0, 2),
                "tss": round(_safe_float(row.get("tss")), 1),
                "rtss": round(_safe_float(row.get("rtss")), 1),
                "distance_eqv_km": round(_safe_float(row.get("distance_proxy_km")), 1),
                "if_proxy_pct": round(_safe_float(row.get("if_proxy")) * 100.0, 1),
                "pace_label": _format_pace_short(_safe_float(row.get("pace_proxy_sec_per_km"))),
                "source": str(row.get("source") or "manual"),
            }
        )

    weekly = (
        merged.groupby("week_start", as_index=False)
        .agg(
            custom_activities=("line_no", "count"),
            duration_s=("duration_s", "sum"),
            tss=("tss", "sum"),
            rtss=("rtss", "sum"),
            distance_eqv_km=("distance_proxy_km", "sum"),
            if_weighted=("if_proxy", lambda v: float((pd.to_numeric(v, errors="coerce").fillna(0.0)).sum())),
        )
        .sort_values("week_start", ascending=False)
    )
    if weeks is not None:
        weekly = weekly.head(max(1, int(weeks)))
    weeks_out: list[dict[str, Any]] = []
    for _, row in weekly.iterrows():
        ws = pd.Timestamp(row.get("week_start")).normalize()
        we = ws + pd.Timedelta(days=6)
        dur_s = _safe_float(row.get("duration_s"))
        avg_if = _safe_float(row.get("if_weighted")) / max(float(_safe_float(row.get("custom_activities"))), 1.0)
        weeks_out.append(
            {
                "week_start": ws.date().isoformat(),
                "week_end": we.date().isoformat(),
                "custom_activities": int(_safe_float(row.get("custom_activities"))),
                "duration_h": round(dur_s / 3600.0, 1),
                "tss": round(_safe_float(row.get("tss")), 1),
                "rtss": round(_safe_float(row.get("rtss")), 1),
                "distance_eqv_km": round(_safe_float(row.get("distance_eqv_km")), 1),
                "if_proxy_pct": round(avg_if * 100.0, 1),
            }
        )

    return {"owner": resolved_owner, "rows": rows_out, "weeks": weeks_out}


@app.post("/api/v1/custom-activities/ingest")
def custom_activities_ingest(
    payload: CustomIngestRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    entry_text = str(payload.entry_text or "")

    if len(entry_text) > int(MAX_PLANNED_ENTRY_CHARS):
        raise HTTPException(status_code=400, detail=f"Input too large. Max {MAX_PLANNED_ENTRY_CHARS} characters per save.")

    entries = _split_dated_activity_entries(entry_text)
    if not entries:
        raise HTTPException(status_code=400, detail="Input is empty. Use `[date]:[activity]`.")
    if len(entries) > int(MAX_PLANNED_ENTRIES_PER_SAVE):
        raise HTTPException(status_code=400, detail=f"Too many entries in one save. Max {MAX_PLANNED_ENTRIES_PER_SAVE}.")

    existing = get_custom_activities_df(db_path=db_path)
    max_line_by_day = existing.groupby("day_utc")["line_no"].max().to_dict() if not existing.empty else {}

    lthr_curve = _load_curve_points(db_path=db_path, key=SETTINGS_KEY_LTHR_CURVE, value_key="lthr_bpm", fallback_value=DEFAULT_LTHR)
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    lthr_default = float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR
    pace_default = float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM

    rows_to_upsert: list[dict[str, Any]] = []
    errors: list[str] = []
    for idx, raw_entry in enumerate(entries, start=1):
        day_ts, normalized, parse_err = _parse_dated_activity_entry(raw_entry)
        if parse_err:
            errors.append(f"entry {idx}: {parse_err}")
            continue
        if day_ts is None:
            errors.append(f"entry {idx}: could not parse date")
            continue

        lthr_for_day = float(_curve_value_at(lthr_curve, lthr_default, day_ts))
        pace_for_day = float(_curve_value_at(pace_curve, pace_default, day_ts))
        segs, warns = _expand_planned_segments(
            normalized,
            lthr_bpm=lthr_for_day,
            threshold_pace_sec_per_km=pace_for_day,
        )
        if warns or not segs:
            details = "; ".join(warns[:2]) if warns else "Could not parse this activity."
            errors.append(f"entry {idx}: {details}")
            continue

        day_key = day_ts.date().isoformat()
        next_line_no = int(max_line_by_day.get(day_key, 0)) + 1
        max_line_by_day[day_key] = next_line_no
        rows_to_upsert.append(
            {
                "day_utc": day_key,
                "line_no": next_line_no,
                "activity_text": normalized,
                "parsed_json": segs,
                "source": "manual",
            }
        )

    if rows_to_upsert:
        try:
            upsert_custom_activities_rows(
                db_path=db_path,
                rows=rows_to_upsert,
                max_rows=CUSTOM_ACTIVITIES_LIMIT,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return {"saved_count": int(len(rows_to_upsert)), "errors": errors[:20]}


@app.patch("/api/v1/custom-activities/workout")
def custom_activity_workout_update(
    payload: CustomActivityUpdateRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    day_utc = str(payload.day_utc or "").strip()
    line_no = int(payload.line_no)
    activity_text = _normalize_plan_text(str(payload.activity_text or ""))
    if not day_utc or line_no <= 0:
        raise HTTPException(status_code=400, detail="Invalid day_utc or line_no")
    if not activity_text:
        raise HTTPException(status_code=400, detail="Activity text cannot be empty")

    existing = get_custom_activities_df(db_path=db_path)
    if existing.empty:
        raise HTTPException(status_code=404, detail="Custom activity not found")
    existing = existing[
        (existing.get("day_utc").astype(str) == day_utc)
        & (pd.to_numeric(existing.get("line_no"), errors="coerce").fillna(0).astype(int) == line_no)
    ]
    if existing.empty:
        raise HTTPException(status_code=404, detail="Custom activity not found")
    current_row = existing.iloc[0]

    day_ts = pd.to_datetime(day_utc, errors="coerce")
    if pd.isna(day_ts):
        raise HTTPException(status_code=400, detail="Invalid day_utc")

    lthr_curve = _load_curve_points(db_path=db_path, key=SETTINGS_KEY_LTHR_CURVE, value_key="lthr_bpm", fallback_value=DEFAULT_LTHR)
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    lthr_default = float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR
    pace_default = float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    lthr_for_day = float(_curve_value_at(lthr_curve, lthr_default, day_ts))
    pace_for_day = float(_curve_value_at(pace_curve, pace_default, day_ts))
    segs, warns = _expand_planned_segments(
        activity_text,
        lthr_bpm=lthr_for_day,
        threshold_pace_sec_per_km=pace_for_day,
    )
    if warns or not segs:
        details = "; ".join(warns[:2]) if warns else "Could not parse this activity."
        raise HTTPException(status_code=400, detail=details)

    upsert_custom_activities_rows(
        db_path=db_path,
        rows=[
            {
                "day_utc": day_utc,
                "line_no": line_no,
                "activity_text": activity_text,
                "parsed_json": segs,
                "source": str(current_row.get("source") or "manual"),
            }
        ],
        max_rows=CUSTOM_ACTIVITIES_LIMIT,
    )
    return {"updated": True}


@app.delete("/api/v1/custom-activities")
def custom_activity_delete(
    day_utc: str = Query(...),
    line_no: int = Query(..., ge=1),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    deleted = delete_custom_activities(
        db_path=db_path,
        keys=[(str(day_utc), int(line_no))],
    )
    if deleted <= 0:
        raise HTTPException(status_code=404, detail="Custom activity not found")
    return {"deleted": int(deleted)}


@app.get("/api/v1/activities/{activity_id}")
def activity_detail(
    activity_id: str,
    owner: str | None = Query(default=None),
    include_records: bool = Query(default=True),
    records_limit: int = Query(default=1000, ge=100, le=5000),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Owner database not found")

    lthr_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LTHR_CURVE,
        value_key="lthr_bpm",
        fallback_value=DEFAULT_LTHR,
    )
    pace_curve = _load_curve_points(
        db_path=db_path,
        key=SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )

    activity_id_norm = _normalize_activity_id(activity_id)
    custom_key = _parse_custom_activity_id(activity_id_norm)
    if custom_key is not None:
        day_utc, line_no = custom_key
        custom_df = get_custom_activities_df(db_path=db_path, start_day_utc=day_utc, end_day_utc=day_utc)
        if custom_df.empty:
            raise HTTPException(status_code=404, detail="Activity not found")
        selected_custom = custom_df[
            (custom_df["day_utc"].astype(str) == day_utc)
            & (pd.to_numeric(custom_df["line_no"], errors="coerce").fillna(0).astype(int) == int(line_no))
        ].head(1)
        if selected_custom.empty:
            raise HTTPException(status_code=404, detail="Activity not found")

        row = selected_custom.iloc[0]
        parsed_json = row.get("parsed_json")
        segments: list[dict[str, Any]] = []
        if isinstance(parsed_json, list):
            segments = [s for s in parsed_json if isinstance(s, dict)]
        elif isinstance(parsed_json, str) and parsed_json.strip():
            try:
                parsed = json.loads(parsed_json)
                if isinstance(parsed, list):
                    segments = [s for s in parsed if isinstance(s, dict)]
            except Exception:
                segments = []

        day_ts = pd.to_datetime(day_utc, utc=True, errors="coerce")
        lthr_for_day = float(_curve_value_at(lthr_curve, float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR, day_ts))
        threshold_pace_for_day = float(
            _curve_value_at(
                pace_curve,
                float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
                day_ts,
            )
        )
        if not segments:
            expanded, _warnings = _expand_planned_segments(
                str(row.get("activity_text") or ""),
                lthr_bpm=lthr_for_day,
                threshold_pace_sec_per_km=threshold_pace_for_day,
            )
            segments = [s for s in expanded if isinstance(s, dict)]

        if_thresholds = _load_if_zone_thresholds(db_path)
        specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)

        total_duration_s = 0.0
        total_tss = 0.0
        total_rtss = 0.0
        total_distance_eqv_km = 0.0
        if_weighted_sum = 0.0
        if_weight_seconds = 0.0
        pace_weighted_sum = 0.0
        pace_weight_seconds = 0.0
        hr_weighted_sum = 0.0
        hr_weight_seconds = 0.0
        split_rows: list[dict[str, Any]] = []
        lap_dtos: list[dict[str, Any]] = []
        kinds_seen: list[str] = []

        for idx, seg in enumerate(segments, start=1):
            seg_kind = str(seg.get("kind") or "").strip().lower()
            if seg_kind and seg_kind not in kinds_seen:
                kinds_seen.append(seg_kind)
            seg_spec = _specificity_factor_for_plan_kind(seg_kind, specificity_profile)
            seg_for_metrics = _segment_with_effective_intensity_for_metrics(seg, seg_kind=seg_kind, seg_spec=seg_spec)
            metric_row = _planned_segment_metrics(
                seg_for_metrics,
                lthr_bpm=lthr_for_day,
                threshold_pace_sec_per_km=threshold_pace_for_day,
                non_running_factor=seg_spec,
            )
            duration_s = float(metric_row.get("duration_s") or 0.0)
            if duration_s <= 0:
                continue
            if_proxy = float(metric_row.get("if_proxy") or 0.0)
            tss = float(metric_row.get("tss") or 0.0) * float(seg_spec)
            rtss = float(metric_row.get("rtss") or 0.0) * float(seg_spec)
            distance_eqv_km = float(metric_row.get("distance_eqv_km") or 0.0)
            is_running_like = seg_kind in {"run", "treadmill"}

            pace_raw = _safe_float(seg_for_metrics.get("pace_s_per_km"))
            pace_eqv_s_per_km = (threshold_pace_for_day / if_proxy) if (threshold_pace_for_day > 0 and if_proxy > 0) else 0.0
            pace_label_s_per_km = pace_raw if pace_raw > 0 else pace_eqv_s_per_km
            distance_km = distance_eqv_km
            avg_hr = _safe_float(seg_for_metrics.get("avg_hr_bpm"))
            avg_speed_mps = (1000.0 / pace_label_s_per_km) if pace_label_s_per_km > 0 else 0.0

            total_duration_s += duration_s
            total_tss += tss
            total_rtss += rtss
            total_distance_eqv_km += max(distance_eqv_km, 0.0)
            if if_proxy > 0:
                if_weighted_sum += if_proxy * duration_s
                if_weight_seconds += duration_s
            if pace_label_s_per_km > 0:
                pace_weighted_sum += pace_label_s_per_km * duration_s
                pace_weight_seconds += duration_s
            if avg_hr > 0:
                hr_weighted_sum += avg_hr * duration_s
                hr_weight_seconds += duration_s

            split_rows.append(
                {
                    "lap": idx,
                    "description": _split_description_from_if_proxy(if_proxy, if_thresholds),
                    "duration_label": _format_duration_compact_with_seconds(duration_s),
                    "avg_hr": round(avg_hr, 0) if avg_hr > 0 else 0.0,
                    "if_pct": round(if_proxy * 100.0, 1) if if_proxy > 0 else 0.0,
                    "distance_km": round(max(distance_km, 0.0), 2),
                    "distance_eqv_km": round(max(distance_eqv_km, 0.0), 2),
                    "pace_label": _format_pace_short(pace_label_s_per_km if pace_label_s_per_km > 0 else None),
                    "pace_eqv_label": _format_pace_short(pace_eqv_s_per_km if pace_eqv_s_per_km > 0 else None),
                    "display_mode": "running" if is_running_like else "eqv",
                }
            )
            lap_dtos.append(
                {
                    "lapIndex": idx,
                    "duration": duration_s,
                    "elapsedDuration": duration_s,
                    "distance": max(distance_km, 0.0) * 1000.0,
                    "averageHR": avg_hr if avg_hr > 0 else 0.0,
                    "maxHR": avg_hr if avg_hr > 0 else 0.0,
                    "averageSpeed": avg_speed_mps,
                    "calories": 0.0,
                }
            )

        sport_type = ", ".join([k.replace("_", " ").title() for k in kinds_seen]) if kinds_seen else "Custom"
        avg_if_proxy = (if_weighted_sum / if_weight_seconds) if if_weight_seconds > 0 else 0.0
        avg_pace_s_per_km = (pace_weighted_sum / pace_weight_seconds) if pace_weight_seconds > 0 else 0.0
        avg_hr = (hr_weighted_sum / hr_weight_seconds) if hr_weight_seconds > 0 else 0.0
        start_time = pd.Timestamp(day_ts).tz_convert("UTC").tz_localize(None) if pd.notna(day_ts) else pd.Timestamp.utcnow().tz_localize(None)
        start_time = start_time.normalize() + pd.Timedelta(hours=12) + pd.Timedelta(minutes=max(0, int(line_no) - 1))

        return {
            "owner": resolved_owner,
            "activity": {
                "activity_id": activity_id_norm,
                "date": day_utc,
                "start_time_utc": start_time.isoformat(),
                "sport_type": sport_type,
                "distance_km": round(max(total_distance_eqv_km, 0.0), 2),
                "duration_min": round(total_duration_s / 60.0, 1),
                "avg_pace_display": _format_pace_short(avg_pace_s_per_km if avg_pace_s_per_km > 0 else None),
                "avg_hr": round(avg_hr, 1) if avg_hr > 0 else 0.0,
                "max_hr": round(avg_hr, 1) if avg_hr > 0 else 0.0,
                "tss": round(total_tss, 1),
                "rtss": round(total_rtss, 1),
                "training_load_garmin": 0.0,
            },
            "records": [],
            "raw": {"day_utc": day_utc, "line_no": int(line_no), "activity_text": str(row.get("activity_text") or "")},
            "details": {"source": "custom", "if_proxy": avg_if_proxy, "segments": segments},
            "splits": {
                "lap_count": len(lap_dtos),
                "total_duration_s": round(total_duration_s, 1),
                "total_distance_m": round(max(total_distance_eqv_km, 0.0) * 1000.0, 1),
                "split": {"lapDTOs": lap_dtos},
                "split_summaries": {"splitSummaries": lap_dtos},
            },
            "split_rows": split_rows,
        }

    planned_key = _parse_planned_activity_id(activity_id_norm)
    if planned_key is not None:
        day_utc, line_no = planned_key
        planned_df = get_planned_activities_df(db_path=db_path, start_day_utc=day_utc, end_day_utc=day_utc)
        if planned_df.empty:
            raise HTTPException(status_code=404, detail="Activity not found")
        selected_planned = planned_df[
            (planned_df["day_utc"].astype(str) == day_utc)
            & (pd.to_numeric(planned_df["line_no"], errors="coerce").fillna(0).astype(int) == int(line_no))
        ].head(1)
        if selected_planned.empty:
            raise HTTPException(status_code=404, detail="Activity not found")

        row = selected_planned.iloc[0]
        parsed_json = row.get("parsed_json")
        segments: list[dict[str, Any]] = []
        if isinstance(parsed_json, list):
            segments = [s for s in parsed_json if isinstance(s, dict)]
        elif isinstance(parsed_json, str) and parsed_json.strip():
            try:
                parsed = json.loads(parsed_json)
                if isinstance(parsed, list):
                    segments = [s for s in parsed if isinstance(s, dict)]
            except Exception:
                segments = []

        day_ts = pd.to_datetime(day_utc, utc=True, errors="coerce")
        lthr_for_day = float(_curve_value_at(lthr_curve, float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR, day_ts))
        threshold_pace_for_day = float(
            _curve_value_at(
                pace_curve,
                float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
                day_ts,
            )
        )
        if not segments:
            expanded, _warnings = _expand_planned_segments(
                str(row.get("workout_text") or ""),
                lthr_bpm=lthr_for_day,
                threshold_pace_sec_per_km=threshold_pace_for_day,
            )
            segments = [s for s in expanded if isinstance(s, dict)]

        if_thresholds = _load_if_zone_thresholds(db_path)
        specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)

        total_duration_s = 0.0
        total_tss = 0.0
        total_rtss = 0.0
        total_distance_eqv_km = 0.0
        if_weighted_sum = 0.0
        if_weight_seconds = 0.0
        pace_weighted_sum = 0.0
        pace_weight_seconds = 0.0
        hr_weighted_sum = 0.0
        hr_weight_seconds = 0.0
        split_rows: list[dict[str, Any]] = []
        lap_dtos: list[dict[str, Any]] = []
        kinds_seen: list[str] = []

        for idx, seg in enumerate(segments, start=1):
            seg_kind = str(seg.get("kind") or "").strip().lower()
            if seg_kind and seg_kind not in kinds_seen:
                kinds_seen.append(seg_kind)
            seg_spec = _specificity_factor_for_plan_kind(seg_kind, specificity_profile)
            seg_for_metrics = _segment_with_effective_intensity_for_metrics(seg, seg_kind=seg_kind, seg_spec=seg_spec)
            metric_row = _planned_segment_metrics(
                seg_for_metrics,
                lthr_bpm=lthr_for_day,
                threshold_pace_sec_per_km=threshold_pace_for_day,
                non_running_factor=seg_spec,
            )
            duration_s = float(metric_row.get("duration_s") or 0.0)
            if duration_s <= 0:
                continue
            if_proxy = float(metric_row.get("if_proxy") or 0.0)
            tss = float(metric_row.get("tss") or 0.0) * float(seg_spec)
            rtss = float(metric_row.get("rtss") or 0.0) * float(seg_spec)
            distance_eqv_km = float(metric_row.get("distance_eqv_km") or 0.0)
            is_running_like = seg_kind in {"run", "treadmill"}

            pace_raw = _safe_float(seg_for_metrics.get("pace_s_per_km"))
            pace_eqv_s_per_km = (threshold_pace_for_day / if_proxy) if (threshold_pace_for_day > 0 and if_proxy > 0) else 0.0
            pace_label_s_per_km = pace_raw if pace_raw > 0 else pace_eqv_s_per_km
            distance_km = distance_eqv_km
            avg_hr = _safe_float(seg_for_metrics.get("avg_hr_bpm"))
            avg_speed_mps = (1000.0 / pace_label_s_per_km) if pace_label_s_per_km > 0 else 0.0

            total_duration_s += duration_s
            total_tss += tss
            total_rtss += rtss
            total_distance_eqv_km += max(distance_eqv_km, 0.0)
            if if_proxy > 0:
                if_weighted_sum += if_proxy * duration_s
                if_weight_seconds += duration_s
            if pace_label_s_per_km > 0:
                pace_weighted_sum += pace_label_s_per_km * duration_s
                pace_weight_seconds += duration_s
            if avg_hr > 0:
                hr_weighted_sum += avg_hr * duration_s
                hr_weight_seconds += duration_s

            split_rows.append(
                {
                    "lap": idx,
                    "description": _split_description_from_if_proxy(if_proxy, if_thresholds),
                    "duration_label": _format_duration_compact_with_seconds(duration_s),
                    "avg_hr": round(avg_hr, 0) if avg_hr > 0 else 0.0,
                    "if_pct": round(if_proxy * 100.0, 1) if if_proxy > 0 else 0.0,
                    "distance_km": round(max(distance_km, 0.0), 2),
                    "distance_eqv_km": round(max(distance_eqv_km, 0.0), 2),
                    "pace_label": _format_pace_short(pace_label_s_per_km if pace_label_s_per_km > 0 else None),
                    "pace_eqv_label": _format_pace_short(pace_eqv_s_per_km if pace_eqv_s_per_km > 0 else None),
                    "display_mode": "running" if is_running_like else "eqv",
                }
            )
            lap_dtos.append(
                {
                    "lapIndex": idx,
                    "duration": duration_s,
                    "elapsedDuration": duration_s,
                    "distance": max(distance_km, 0.0) * 1000.0,
                    "averageHR": avg_hr if avg_hr > 0 else 0.0,
                    "maxHR": avg_hr if avg_hr > 0 else 0.0,
                    "averageSpeed": avg_speed_mps,
                    "calories": 0.0,
                }
            )

        sport_type = ", ".join([k.replace("_", " ").title() for k in kinds_seen]) if kinds_seen else "Planned"
        avg_if_proxy = (if_weighted_sum / if_weight_seconds) if if_weight_seconds > 0 else 0.0
        avg_pace_s_per_km = (pace_weighted_sum / pace_weight_seconds) if pace_weight_seconds > 0 else 0.0
        avg_hr = (hr_weighted_sum / hr_weight_seconds) if hr_weight_seconds > 0 else 0.0
        start_time = pd.Timestamp(day_ts).tz_convert("UTC").tz_localize(None) if pd.notna(day_ts) else pd.Timestamp.utcnow().tz_localize(None)
        start_time = start_time.normalize() + pd.Timedelta(hours=12) + pd.Timedelta(minutes=max(0, int(line_no) - 1))

        return {
            "owner": resolved_owner,
            "activity": {
                "activity_id": activity_id_norm,
                "date": day_utc,
                "start_time_utc": start_time.isoformat(),
                "sport_type": sport_type,
                "distance_km": round(max(total_distance_eqv_km, 0.0), 2),
                "duration_min": round(total_duration_s / 60.0, 1),
                "avg_pace_display": _format_pace_short(avg_pace_s_per_km if avg_pace_s_per_km > 0 else None),
                "avg_hr": round(avg_hr, 1) if avg_hr > 0 else 0.0,
                "max_hr": round(avg_hr, 1) if avg_hr > 0 else 0.0,
                "tss": round(total_tss, 1),
                "rtss": round(total_rtss, 1),
                "training_load_garmin": 0.0,
            },
            "records": [],
            "raw": {"day_utc": day_utc, "line_no": int(line_no), "workout_text": str(row.get("workout_text") or "")},
            "details": {"source": "planned", "if_proxy": avg_if_proxy, "segments": segments},
            "splits": {
                "lap_count": len(lap_dtos),
                "total_duration_s": round(total_duration_s, 1),
                "total_distance_m": round(max(total_distance_eqv_km, 0.0) * 1000.0, 1),
                "split": {"lapDTOs": lap_dtos},
                "split_summaries": {"splitSummaries": lap_dtos},
            },
            "split_rows": split_rows,
        }

    runs_df = get_runs_df(db_path)
    if runs_df.empty:
        raise HTTPException(status_code=404, detail="No activities found")

    metrics_df = compute_metrics(
        runs_df=runs_df,
        lthr_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
        threshold_pace_sec_per_km=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
        lthr_curve_points=lthr_curve,
        threshold_pace_curve_points=pace_curve,
    )
    selected = metrics_df[
        metrics_df["activity_id"].astype(str).map(_normalize_activity_id) == activity_id_norm
    ].head(1)
    if selected.empty:
        raise HTTPException(status_code=404, detail="Activity not found")

    table_row = display_table(selected).head(1)
    base = table_row.iloc[0].to_dict() if not table_row.empty else selected.iloc[0].to_dict()
    selected_activity_id = _normalize_activity_id(base.get("activity_id") or activity_id_norm)

    records: list[dict[str, Any]] = []
    if include_records:
        records_df = get_activity_records_df(db_path, selected_activity_id).head(int(records_limit)).copy()
        if not records_df.empty:
            def _extract_from_raw(raw_payload: Any, keys: tuple[str, ...]) -> float:
                if raw_payload is None:
                    return 0.0
                payload_obj = raw_payload
                if isinstance(raw_payload, str):
                    try:
                        payload_obj = json.loads(raw_payload)
                    except Exception:
                        payload_obj = {}
                if not isinstance(payload_obj, dict):
                    return 0.0
                for key in keys:
                    val = _safe_float(payload_obj.get(key))
                    if val > 0:
                        return val
                return 0.0

            for _, row in records_df.iterrows():
                gap_mps = _extract_from_raw(
                    row.get("raw_json"),
                    (
                        "grade_adjusted_speed",
                        "grade_adjusted_speed_smoothed",
                        "enhanced_grade_adjusted_speed",
                    ),
                )
                records.append(
                    {
                        "record_time_utc": str(row.get("record_time_utc") or ""),
                        "heart_rate": _safe_float(row.get("heart_rate")),
                        "speed": _safe_float(row.get("speed")),
                        "distance": _safe_float(row.get("distance")),
                        "cadence": _safe_float(row.get("cadence")),
                        "power": _safe_float(row.get("power")),
                        "grade": _safe_float(row.get("grade")),
                        "altitude": _safe_float(row.get("altitude")),
                        "stamina": _safe_float(row.get("stamina")),
                        "grade_adjusted_speed": gap_mps,
                        "grade_adjusted_pace_s_per_km": (1000.0 / gap_mps) if gap_mps > 0 else 0.0,
                    }
                )

    splits_raw = get_activity_splits_raw(db_path, selected_activity_id) or {}
    split_rows: list[dict[str, Any]] = []
    split_payload = splits_raw.get("split") if isinstance(splits_raw, dict) else {}
    summaries_payload = splits_raw.get("split_summaries") if isinstance(splits_raw, dict) else {}
    laps = split_payload.get("lapDTOs") if isinstance(split_payload, dict) else None
    if not isinstance(laps, list) or not laps:
        maybe = summaries_payload.get("splitSummaries") if isinstance(summaries_payload, dict) else None
        if isinstance(maybe, list):
            laps = maybe
    if not isinstance(laps, list):
        laps = []

    start_ts = pd.to_datetime(base.get("start_time_utc"), utc=True, errors="coerce")
    lthr_for_day = float(_curve_value_at(lthr_curve, float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR, start_ts))
    threshold_pace_for_day = float(
        _curve_value_at(
            pace_curve,
            float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
            start_ts,
        )
    )
    if_thresholds = _load_if_zone_thresholds(db_path)
    specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)
    sport_type = str(base.get("sport_type") or "")
    sport_lower = sport_type.lower()
    is_running_like = ("run" in sport_lower) or ("treadmill" in sport_lower)
    specificity_factor = _specificity_factor_for_sport(sport_type, specificity_profile)
    for idx, lap in enumerate([x for x in laps if isinstance(x, dict)], start=1):
        duration_s = _safe_float(
            lap.get("duration")
            or lap.get("elapsedDuration")
            or lap.get("movingDuration")
            or lap.get("totalTimerTime")
        )
        if duration_s <= 0:
            continue
        distance_m = _safe_float(lap.get("distance") or lap.get("totalDistance") or lap.get("distanceMeters"))
        avg_hr = _safe_float(lap.get("averageHR"))
        avg_speed_mps = _safe_float(lap.get("averageSpeed"))
        pace_s_per_km = (1000.0 / avg_speed_mps) if avg_speed_mps > 0 else 0.0

        if_proxy = 0.0
        if is_running_like and pace_s_per_km > 0 and threshold_pace_for_day > 0:
            if_proxy = threshold_pace_for_day / pace_s_per_km
        elif avg_hr > 0 and lthr_for_day > 0:
            if_proxy = avg_hr / lthr_for_day
        elif pace_s_per_km > 0 and threshold_pace_for_day > 0:
            if_proxy = threshold_pace_for_day / pace_s_per_km

        pace_eqv_s_per_km = (threshold_pace_for_day / if_proxy) if (threshold_pace_for_day > 0 and if_proxy > 0) else 0.0
        if is_running_like:
            distance_eqv_km = (distance_m / 1000.0) if distance_m > 0 else (duration_s / pace_s_per_km if pace_s_per_km > 0 else 0.0)
            distance_km_ui = (distance_m / 1000.0) if distance_m > 0 else distance_eqv_km
            pace_ui_s_per_km = pace_s_per_km if pace_s_per_km > 0 else pace_eqv_s_per_km
        else:
            if pace_eqv_s_per_km <= 0 and pace_s_per_km > 0:
                pace_eqv_s_per_km = pace_s_per_km / max(specificity_factor, 0.01)
            distance_eqv_km = duration_s / pace_eqv_s_per_km if pace_eqv_s_per_km > 0 else 0.0
            if distance_eqv_km <= 0 and distance_m > 0:
                distance_eqv_km = (distance_m / 1000.0) * max(specificity_factor, 0.01)
            distance_km_ui = distance_eqv_km
            pace_ui_s_per_km = pace_eqv_s_per_km

        split_rows.append(
            {
                "lap": int(_safe_float(lap.get("lapIndex")) or idx),
                "description": _split_description_from_if_proxy(if_proxy, if_thresholds),
                "duration_label": _format_duration_compact_with_seconds(duration_s),
                "avg_hr": round(avg_hr, 0) if avg_hr > 0 else 0.0,
                "if_pct": round(if_proxy * 100.0, 1) if if_proxy > 0 else 0.0,
                "distance_km": round(max(distance_km_ui, 0.0), 2),
                "distance_eqv_km": round(max(distance_eqv_km, 0.0), 2),
                "pace_label": _format_pace_short(pace_ui_s_per_km if pace_ui_s_per_km > 0 else None),
                "pace_eqv_label": _format_pace_short(pace_eqv_s_per_km if pace_eqv_s_per_km > 0 else None),
                "display_mode": "running" if is_running_like else "eqv",
            }
        )

    split_rows = sorted(split_rows, key=lambda row: int(_safe_float(row.get("lap"))))

    return {
        "owner": resolved_owner,
        "activity": {
            "activity_id": selected_activity_id,
            "date": str(base.get("date") or ""),
            "start_time_utc": str(base.get("start_time_utc") or ""),
            "sport_type": str(base.get("sport_type") or ""),
            "distance_km": round(_safe_float(base.get("distance_km")), 2),
            "duration_min": round(_safe_float(base.get("duration_min")), 1),
            "avg_pace_display": str(base.get("avg_pace_display") or "-"),
            "avg_hr": round(_safe_float(base.get("avg_hr")), 1),
            "max_hr": round(_safe_float(base.get("max_hr")), 1),
            "tss": round(_safe_float(base.get("tss")), 1),
            "rtss": round(_safe_float(base.get("rtss")), 1),
            "training_load_garmin": round(_safe_float(base.get("training_load_garmin")), 1),
        },
        "records": records,
        "raw": get_activity_raw(db_path, selected_activity_id) or {},
        "details": get_activity_detail_raw(db_path, selected_activity_id) or {},
        "splits": splits_raw,
        "split_rows": split_rows,
    }

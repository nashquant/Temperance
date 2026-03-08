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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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

from analytics import build_daily_summary, compute_metrics, display_table, weekly_summary  # noqa: E402
from auth import build_users, password_matches, resolve_user  # noqa: E402
from db import (  # noqa: E402
    delete_planned_activities,
    get_activity_detail_raw,
    get_activity_raw,
    get_activity_records_df,
    get_planned_activities_df,
    get_runs_df,
    get_setting,
    set_planned_activity_manual_done,
    upsert_planned_activities_rows,
)

DEFAULT_LTHR = 178.0
DEFAULT_THRESHOLD_PACE_SEC_PER_KM = 300.0
SETTINGS_KEY_LTHR_CURVE = "lthr_curve_v1"
SETTINGS_KEY_LT_PACE_CURVE = "lt_pace_curve_v1"
SETTINGS_KEY_ACTIVITY_SPECIFICITY = "activity_specificity_v1"
TOKEN_TTL_S = int(os.getenv("TEMPERANCE_SESSION_TTL_S", str(4 * 60 * 60)) or (4 * 60 * 60))
MAX_PLANNED_ENTRY_CHARS = 4000
MAX_PLANNED_ENTRIES_PER_SAVE = 40
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
    if owner_slug == "default" and not scoped.exists() and DB_PATH.exists():
        return DB_PATH
    return scoped


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
        if_vals.append(if_weighted_sum / if_weight_seconds if if_weight_seconds > 0 else 0.0)

    out["tss"] = tss_vals
    out["rtss"] = rtss_vals
    out["distance_proxy_km"] = dist_eqv_vals
    out["duration_s"] = dur_vals
    out["if_proxy"] = if_vals
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
    match = re.search(r"\b(AM|PM)\b", workout_text, flags=re.IGNORECASE)
    if match:
        return str(match.group(1)).upper()
    return None


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
    now_local = pd.Timestamp(now_local_ts) if now_local_ts is not None else pd.Timestamp(datetime.now().astimezone())
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

    # Day rule for compare bars: if a day has at least one open planned row,
    # ignore done rows for that day; otherwise keep all rows.
    metrics_for_compare = metrics_rows.copy()
    metrics_for_compare["manual_done"] = pd.to_numeric(
        metrics_for_compare.get("manual_done"),
        errors="coerce",
    ).fillna(0.0) > 0
    day_has_open = metrics_for_compare.groupby("day")["manual_done"].transform(
        lambda s: bool((~s).any())
    )
    keep_compare = (~metrics_for_compare["manual_done"]) | (~day_has_open)
    metrics_for_compare = metrics_for_compare.loc[keep_compare].copy()
    if metrics_for_compare.empty:
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
    metrics_remaining = _filter_effective_planned_rows(metrics_rows, today_local_day=today_local)
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


def _empty_dashboard(days: int) -> dict[str, Any]:
    return {
        "range_days": int(days),
        "kpis": {
            "distance_km": 0.0,
            "distance_proxy_km": 0.0,
            "tss_total": 0.0,
            "activities": 0,
            "days_with_training": 0,
        },
        "daily": [],
        "activities": [],
    }


def _metrics_for_filters(
    db_path: Path,
    days: int,
    start_day: str | None,
    end_day: str | None,
    sport: str | None,
) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()

    runs_df = get_runs_df(db_path)
    if runs_df.empty:
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

    metrics_df = compute_metrics(
        runs_df=runs_df,
        lthr_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
        threshold_pace_sec_per_km=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
        lthr_curve_points=lthr_curve,
        threshold_pace_curve_points=pace_curve,
    )
    if metrics_df.empty:
        return metrics_df

    specificity_profile = _load_specificity_profile(db_path=db_path, fallback_default=0.8)
    metrics_df = _apply_specificity_factor(metrics_df, specificity_profile=specificity_profile)

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


def _build_dashboard_payload(
    db_path: Path,
    days: int,
    start_day: str | None,
    end_day: str | None,
    sport: str | None,
    limit: int,
) -> dict[str, Any]:
    metrics_df = _metrics_for_filters(
        db_path=db_path,
        days=days,
        start_day=start_day,
        end_day=end_day,
        sport=sport,
    )

    if metrics_df.empty:
        return _empty_dashboard(days)

    daily_df = build_daily_summary(metrics_df).sort_values("day_utc")
    table_df = display_table(metrics_df).copy()

    kpi_distance_km = _safe_float(pd.to_numeric(daily_df.get("distance_km"), errors="coerce").fillna(0.0).sum())
    kpi_proxy_km = _safe_float(pd.to_numeric(daily_df.get("distance_proxy_km"), errors="coerce").fillna(0.0).sum())
    kpi_tss_total = _safe_float(pd.to_numeric(daily_df.get("tss_total"), errors="coerce").fillna(0.0).sum())

    daily_rows: list[dict[str, Any]] = []
    for _, row in daily_df.iterrows():
        daily_rows.append(
            {
                "day_utc": str(row.get("day_utc") or ""),
                "distance_km": round(_safe_float(row.get("distance_km")), 2),
                "distance_proxy_km": round(_safe_float(row.get("distance_proxy_km")), 2),
                "tss_total": round(_safe_float(row.get("tss_total")), 1),
                "rtss_total": round(_safe_float(row.get("rtss_total")), 1),
                "duration_s_total": round(_safe_float(row.get("duration_s_total")), 1),
            }
        )

    activity_rows: list[dict[str, Any]] = []
    for _, row in table_df.head(max(1, int(limit))).iterrows():
        start_time = pd.to_datetime(row.get("start_time_utc"), utc=True, errors="coerce")
        activity_rows.append(
            {
                "activity_id": str(row.get("activity_id") or ""),
                "start_time_utc": start_time.isoformat() if pd.notna(start_time) else "",
                "date": str(row.get("date") or ""),
                "sport_type": str(row.get("sport_type") or ""),
                "distance_km": round(_safe_float(row.get("distance_km")), 2),
                "duration_min": round(_safe_float(row.get("duration_min")), 1),
                "avg_pace_display": str(row.get("avg_pace_display") or "-"),
                "tss": round(_safe_float(row.get("tss")), 1),
                "rtss": round(_safe_float(row.get("rtss")), 1),
                "avg_hr": round(_safe_float(row.get("avg_hr")), 1),
                "max_hr": round(_safe_float(row.get("max_hr")), 1),
            }
        )

    return {
        "range_days": int(days),
        "kpis": {
            "distance_km": round(kpi_distance_km, 2),
            "distance_proxy_km": round(kpi_proxy_km, 2),
            "tss_total": round(kpi_tss_total, 1),
            "activities": int(len(table_df.index)),
            "days_with_training": int(len(daily_rows)),
        },
        "daily": daily_rows,
        "activities": activity_rows,
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

    this_week_start = _week_start_monday(pd.Timestamp(datetime.now().astimezone().date())).normalize()
    horizon_end = this_week_start + pd.Timedelta(days=max(1, int(weeks)) * 7 - 1)
    in_scope_rows = planned_rows[(planned_rows["day"] >= this_week_start) & (planned_rows["day"] <= horizon_end)].copy()

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


@app.get("/api/v1/week-outlook")
def week_outlook_view(
    days: int = Query(default=84, ge=14, le=365),
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

    runs_df = get_runs_df(db_path)
    if runs_df.empty:
        raise HTTPException(status_code=404, detail="No activities found")

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

    metrics_df = compute_metrics(
        runs_df=runs_df,
        lthr_bpm=float(lthr_curve[-1][1]) if lthr_curve else DEFAULT_LTHR,
        threshold_pace_sec_per_km=float(pace_curve[-1][1]) if pace_curve else DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
        lthr_curve_points=lthr_curve,
        threshold_pace_curve_points=pace_curve,
    )
    selected = metrics_df[metrics_df["activity_id"].astype(str) == str(activity_id)].head(1)
    if selected.empty:
        raise HTTPException(status_code=404, detail="Activity not found")

    table_row = display_table(selected).head(1)
    base = table_row.iloc[0].to_dict() if not table_row.empty else selected.iloc[0].to_dict()

    records: list[dict[str, Any]] = []
    if include_records:
        records_df = get_activity_records_df(db_path, str(activity_id)).head(int(records_limit)).copy()
        if not records_df.empty:
            for _, row in records_df.iterrows():
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
                    }
                )

    return {
        "owner": resolved_owner,
        "activity": {
            "activity_id": str(base.get("activity_id") or activity_id),
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
        "raw": get_activity_raw(db_path, str(activity_id)) or {},
        "details": get_activity_detail_raw(db_path, str(activity_id)) or {},
    }

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
    get_activity_detail_raw,
    get_activity_raw,
    get_activity_records_df,
    get_planned_activities_df,
    get_runs_df,
    get_setting,
)

DEFAULT_LTHR = 178.0
DEFAULT_THRESHOLD_PACE_SEC_PER_KM = 300.0
SETTINGS_KEY_LTHR_CURVE = "lthr_curve_v1"
SETTINGS_KEY_LT_PACE_CURVE = "lt_pace_curve_v1"
SETTINGS_KEY_ACTIVITY_SPECIFICITY = "activity_specificity_v1"
TOKEN_TTL_S = int(os.getenv("TEMPERANCE_SESSION_TTL_S", str(4 * 60 * 60)) or (4 * 60 * 60))
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
        try:
            value = float(row.get(value_key))
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

    metric_col = "distance_proxy_km" if metric_key == "distance_eqv_km" else metric_key
    metric_by_day = (
        metrics_rows.groupby("day", as_index=False)[metric_col]
        .sum()
        .set_index("day")[metric_col]
        .to_dict()
    )
    tss_by_day = (
        metrics_rows.groupby("day", as_index=False)["tss"]
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
        ws = _week_start_monday(pd.Timestamp(datetime.now().date()))
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
    today = pd.Timestamp(datetime.now().date()).normalize()
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
        if compare_key == "planned":
            if day <= cutoff_day:
                wtd_compare += compare_v
        else:
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
            hist_start = ws - pd.Timedelta(days=42)
            full_days = pd.date_range(start=hist_start, end=week_end, freq="D")
            vals: list[float] = []
            for d in full_days:
                dd = pd.Timestamp(d).normalize()
                if dd <= today:
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


@app.get("/api/v1/dashboard")
def dashboard(
    days: int = Query(default=42, ge=7, le=365),
    start_day: str | None = Query(default=None),
    end_day: str | None = Query(default=None),
    sport: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    payload = _build_dashboard_payload(
        db_path=db_path,
        days=days,
        start_day=start_day,
        end_day=end_day,
        sport=sport,
        limit=limit,
    )
    payload["owner"] = resolved_owner
    payload["db_path"] = str(db_path)
    return payload


@app.get("/api/v1/weekly-summary")
def weekly_summary_view(
    days: int = Query(default=84, ge=14, le=365),
    start_day: str | None = Query(default=None),
    end_day: str | None = Query(default=None),
    sport: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    payload = _build_weekly_payload(
        db_path=db_path,
        days=days,
        start_day=start_day,
        end_day=end_day,
        sport=sport,
    )
    payload["owner"] = resolved_owner
    payload["db_path"] = str(db_path)
    return payload


@app.get("/api/v1/week-outlook")
def week_outlook_view(
    days: int = Query(default=84, ge=14, le=365),
    start_day: str | None = Query(default=None),
    end_day: str | None = Query(default=None),
    sport: str | None = Query(default=None),
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
        start_day=start_day,
        end_day=end_day,
        sport=sport,
        metric=metric,
        compare=compare,
        week_start=week_start,
    )
    payload["owner"] = resolved_owner
    payload["db_path"] = str(db_path)
    return payload


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

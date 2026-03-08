from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import hmac
import hashlib
import base64
from datetime import date, datetime, timedelta, timezone
from dataclasses import replace
from pathlib import Path
from time import perf_counter, time

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from analytics import (
    build_daily_summary,
    compute_metrics,
    display_table,
    ema_multi,
    ema_alpha_from_days,
    parse_ma_windows,
    prepare_metric_series,
    weekly_summary,
)
from auth import build_users, password_matches, resolve_garmin_credentials, resolve_user
from config import load_config
from db import (
    get_setting,
    get_activity_splits_cache_key,
    get_custom_activities_cache_key,
    get_planned_activities_cache_key,
    get_activity_splits_df,
    get_activity_records_df,
    get_activity_detail_raw,
    get_activity_raw,
    get_daily_summary_df,
    get_earliest_activity_time,
    get_last_sync,
    get_activities_cache_key,
    get_latest_activity_time,
    get_latest_recovery_day,
    get_runs_df,
    get_sleep_df,
    get_table_counts,
    get_planned_activities_df,
    get_custom_activities_df,
    get_wellness_df,
    init_db,
    log_sync,
    delete_planned_activities,
    set_planned_activity_manual_done,
    delete_custom_activities,
    replace_planned_activities_for_range,
    upsert_planned_activities_rows,
    upsert_custom_activities_rows,
    save_setting,
    upsert_activities,
    upsert_activity_details,
    upsert_activity_records,
    upsert_activity_splits,
    upsert_sleep_daily,
    upsert_wellness_daily,
)
from garmin_client import (
    dump_extract_to_json,
    fetch_garmin_comprehensive,
    fetch_garmin_runs,
    import_runs_from_folder,
)


st.set_page_config(page_title="Temperance", layout="wide")

DEFAULT_RESTING_HR = 45.0
DEFAULT_LTHR = 178.0
DEFAULT_THRESHOLD_PACE_SEC_PER_KM = 300.0
CUSTOM_ACTIVITIES_LIMIT = 5000
METRICS_LOCAL_CACHE_VERSION = 2
METRICS_DERIVATION_CACHE_VERSION = 2
OWNER_SCOPED_STATE_RESET_VERSION = 2
LOGIN_MAX_USER_LEN = 64
LOGIN_MAX_PASSWORD_LEN = 256
LOGIN_FAIL_WINDOW_S = 15 * 60
LOGIN_LOCK_BASE_S = 30
LOGIN_LOCK_MAX_S = 15 * 60
LOGIN_FAILS_BEFORE_LOCK = 5
SESSION_COOKIE_NAME = "temperance_auth"
SESSION_TTL_S = int(os.getenv("TEMPERANCE_SESSION_TTL_S", str(4 * 60 * 60)) or (4 * 60 * 60))
MAX_PLANNED_ENTRY_CHARS = 4000
MAX_PLANNED_ENTRIES_PER_SAVE = 40
USER_DB_QUOTA_BYTES = 1 * 1024 * 1024 * 1024
# LT pace (sec/km) -> upper-bound weekly targets derived from user-defined table.
# Points correspond to:
# 5:00, 4:30, 4:00, 3:45, 3:30, 3:20, 3:15, 3:10, 3:00
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
INJURY_WINDOWS = [
    {"label": "Injury 1", "start": "2025-05-15", "end": "2025-06-18", "severity": "injury"},
    {"label": "Light Injury", "start": "2025-11-03", "end": "2025-11-20", "severity": "light_injury"},
    {"label": "Injury 2", "start": "2025-12-28", "end": "2026-01-20", "severity": "injury"},
]

base_cfg = load_config()
cfg = base_cfg

SETTINGS_KEY_INJURY_WINDOWS = "injury_windows_v1"
SETTINGS_KEY_LTHR_CURVE = "lthr_curve_v1"
SETTINGS_KEY_LT_PACE_CURVE = "lt_pace_curve_v1"
SETTINGS_KEY_GARMIN_OWNER_SCOPE = "garmin_owner_scope_v1"
SETTINGS_KEY_NON_RUNNING_FACTOR = "non_running_factor_v1"
SETTINGS_KEY_ACTIVITY_SPECIFICITY = "activity_specificity_v1"
SETTINGS_KEY_IF_ZONE_THRESHOLDS = "if_zone_thresholds_v1"

DEFAULT_IF_ZONE_THRESHOLDS = {
    "z1_max": 0.75,
    "z2_max": 0.85,
    "z3_max": 0.95,
    "z4_max": 1.05,
}

IF_ZONE_VISUALS = {
    "Z1": {"token": "green", "accent": "rgba(156,163,175,0.96)", "bar": "#9ca3af", "description": "Recovery"},
    "Z2": {"token": "blue", "accent": "rgba(56,189,248,0.96)", "bar": "#38bdf8", "description": "Easy"},
    "Z3": {"token": "yellow", "accent": "rgba(251,191,36,0.96)", "bar": "#fbbf24", "description": "Steady"},
    "Z4": {"token": "red", "accent": "rgba(251,113,133,0.96)", "bar": "#fb7185", "description": "Interval"},
    "Z5": {"token": "purple", "accent": "rgba(168,85,247,0.96)", "bar": "#a855f7", "description": "VO2 Max"},
}


def _lt_target_from_regression(
    lt_pace_sec_per_km: float,
    value_index: int,  # 1=km/week, 2=tss/week
) -> float:
    points = sorted(LT_PACE_TO_WEEKLY_TARGET_POINTS, key=lambda p: p[0], reverse=True)
    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[value_index] for p in points], dtype=float)
    pace = float(max(1.0, lt_pace_sec_per_km))
    # Use smooth cubic regression in-range and linear edge extrapolation outside anchors.
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


def _daily_tss_target_from_lt_pace(lt_pace_sec_per_km: float) -> float:
    return _weekly_tss_target_from_lt_pace(lt_pace_sec_per_km) / 7.0


def _weekly_distance_target_from_lt_pace(lt_pace_sec_per_km: float) -> float:
    return max(_lt_target_from_regression(lt_pace_sec_per_km, value_index=1), 0.0)


def _daily_distance_target_from_lt_pace(lt_pace_sec_per_km: float) -> float:
    return _weekly_distance_target_from_lt_pace(lt_pace_sec_per_km) / 7.0

AUTH_ALL_TABS = [
    "Dashboard",
    "Model Metrics",
    "Weekly Summary",
    "Activity Summary",
    "Custom Activities",
    "Activity Detail",
    "Recovery Data",
    "Data Extract",
    "User Inputs",
]
AUTH_VIEWER_TABS = [
    "Dashboard",
    "Model Metrics",
    "Weekly Summary",
    "Activity Summary",
    "Custom Activities",
    "Activity Detail",
    "Recovery Data",
    "Data Extract",
    "User Inputs",
]

_LOGIN_GUARD_STATE: dict[str, dict[str, float]] = {}


def _auth_enabled() -> bool:
    return str(os.getenv("TEMPERANCE_AUTH_ENABLED", "1")).strip().lower() not in {"0", "false", "no", "off"}


def _auth_users() -> dict[str, dict[str, str]]:
    kwargs = {
        "admin_user": os.getenv("TEMPERANCE_ADMIN_USER", "admin"),
        "admin_pass": os.getenv("TEMPERANCE_ADMIN_PASSWORD", ""),
        "admin_pass_hash": os.getenv("TEMPERANCE_ADMIN_PASSWORD_SHA256", ""),
        "viewer_user": os.getenv("TEMPERANCE_VIEWER_USER", ""),
        "viewer_pass": os.getenv("TEMPERANCE_VIEWER_PASSWORD", ""),
        "viewer_pass_hash": os.getenv("TEMPERANCE_VIEWER_PASSWORD_SHA256", ""),
        "viewer_users": os.getenv("TEMPERANCE_VIEWER_USERS", ""),
        "viewer_users_hash": os.getenv("TEMPERANCE_VIEWER_USERS_SHA256", ""),
    }
    try:
        return build_users(**kwargs)
    except TypeError:
        # Backward-compat fallback in case an older auth.py is loaded in a stale process.
        legacy_kwargs = {k: v for k, v in kwargs.items() if k not in {"viewer_users", "viewer_users_hash"}}
        return build_users(**legacy_kwargs)


def _login_client_fingerprint() -> str:
    # Best-effort source IP from reverse-proxy headers; falls back to session-only guard.
    try:
        ctx = getattr(st, "context", None)
        headers = getattr(ctx, "headers", None)
        if headers:
            header_map = {str(k).lower(): str(v) for k, v in dict(headers).items()}
            ip_raw = header_map.get("x-forwarded-for") or header_map.get("x-real-ip")
            if ip_raw:
                first = str(ip_raw).split(",")[0].strip()
                if first:
                    return first
    except Exception:
        pass
    try:
        session_stub = str(st.session_state.get("_active_data_owner") or st.session_state.get("auth_user") or "anon")
    except Exception:
        session_stub = "anon"
    return f"session:{session_stub}"


def _is_probably_mobile_client() -> bool:
    try:
        ctx = getattr(st, "context", None)
        headers = getattr(ctx, "headers", None)
        if not headers:
            return False
        header_map = {str(k).lower(): str(v) for k, v in dict(headers).items()}
        ua = str(header_map.get("user-agent") or "").lower()
        if not ua:
            return False
        return any(token in ua for token in ["iphone", "android", "mobile", "ipad"])
    except Exception:
        return False


def _login_guard_key(username: str) -> str:
    user_key = str(username or "").strip().casefold() or "<blank>"
    return f"{_login_client_fingerprint()}|{user_key}"


def _login_lock_remaining_s(guard_key: str) -> int:
    rec = _LOGIN_GUARD_STATE.get(guard_key) or {}
    locked_until = float(rec.get("locked_until") or 0.0)
    remaining = int(round(max(0.0, locked_until - time())))
    return remaining


def _register_login_failure(guard_key: str) -> int:
    now_ts = time()
    rec = dict(_LOGIN_GUARD_STATE.get(guard_key) or {})
    window_start = float(rec.get("window_start") or 0.0)
    fail_count = int(rec.get("fail_count") or 0)
    if now_ts - window_start > float(LOGIN_FAIL_WINDOW_S):
        window_start = now_ts
        fail_count = 0
    fail_count += 1
    rec["window_start"] = window_start
    rec["fail_count"] = float(fail_count)
    lock_seconds = 0
    if fail_count >= int(LOGIN_FAILS_BEFORE_LOCK):
        exponent = max(fail_count - int(LOGIN_FAILS_BEFORE_LOCK), 0)
        lock_seconds = int(min(float(LOGIN_LOCK_BASE_S) * (2.0 ** exponent), float(LOGIN_LOCK_MAX_S)))
        rec["locked_until"] = float(now_ts + lock_seconds)
    _LOGIN_GUARD_STATE[guard_key] = rec
    return int(lock_seconds)


def _clear_login_guard(guard_key: str) -> None:
    _LOGIN_GUARD_STATE.pop(guard_key, None)


def _auth_cookie_secret() -> str:
    secret = str(os.getenv("TEMPERANCE_SESSION_SECRET", "") or "").strip()
    if secret:
        return secret
    admin_hash = str(os.getenv("TEMPERANCE_ADMIN_PASSWORD_SHA256", "") or "").strip()
    if admin_hash:
        return f"sha256:{admin_hash}"
    admin_pass = str(os.getenv("TEMPERANCE_ADMIN_PASSWORD", "") or "").strip()
    if admin_pass:
        return f"pass:{admin_pass}"
    return "temperance-local-dev-secret"


def _auth_cookie_sign(payload_b64: str) -> str:
    secret = _auth_cookie_secret().encode("utf-8")
    return hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def _auth_cookie_build_value(user: str, role: str, ttl_s: int = SESSION_TTL_S) -> str:
    exp_ts = int(time() + max(60, int(ttl_s)))
    payload = json.dumps({"u": str(user), "r": str(role), "e": exp_ts}, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    sig = _auth_cookie_sign(payload_b64)
    return f"{payload_b64}.{sig}"


def _auth_cookie_parse_value(cookie_value: str) -> tuple[str, str] | None:
    token = str(cookie_value or "").strip()
    if "." not in token:
        return None
    payload_b64, sig = token.split(".", 1)
    if not payload_b64 or not sig:
        return None
    expected_sig = _auth_cookie_sign(payload_b64)
    if not hmac.compare_digest(expected_sig, sig):
        return None
    padding = "=" * ((4 - (len(payload_b64) % 4)) % 4)
    try:
        payload_raw = base64.urlsafe_b64decode((payload_b64 + padding).encode("ascii")).decode("utf-8")
        payload = json.loads(payload_raw)
    except Exception:
        return None
    user = str(payload.get("u") or "").strip()
    role = str(payload.get("r") or "").strip().lower()
    exp_ts = int(pd.to_numeric(payload.get("e"), errors="coerce") or 0)
    if not user or not role or exp_ts <= int(time()):
        return None
    return user, role


def _auth_cookie_read() -> str:
    try:
        ctx = getattr(st, "context", None)
        cookies = getattr(ctx, "cookies", None)
        if cookies is None:
            return ""
        return str(dict(cookies).get(SESSION_COOKIE_NAME) or "")
    except Exception:
        return ""


def _auth_cookie_set(user: str, role: str, ttl_s: int = SESSION_TTL_S) -> None:
    token = _auth_cookie_build_value(user=user, role=role, ttl_s=ttl_s)
    js = (
        "<script>"
        f"document.cookie='{SESSION_COOKIE_NAME}={token}; Path=/; Max-Age={max(60, int(ttl_s))}; SameSite=Lax';"
        "</script>"
    )
    st.components.v1.html(js, height=0)


def _auth_cookie_clear() -> None:
    js = (
        "<script>"
        f"document.cookie='{SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax';"
        "</script>"
    )
    st.components.v1.html(js, height=0)


def _restore_auth_from_cookie(users: dict[str, dict[str, str]]) -> bool:
    parsed = _auth_cookie_parse_value(_auth_cookie_read())
    if not parsed:
        return False
    user, role = parsed
    resolved_user, user_data = resolve_user(users, user)
    if not user_data:
        return False
    expected_role = str(user_data.get("role") or "").strip().lower()
    if expected_role != role:
        return False
    st.session_state["auth_user"] = resolved_user
    st.session_state["auth_role"] = expected_role
    return True


def _get_garmin_credentials() -> tuple[str | None, str | None]:
    role = str(st.session_state.get("auth_role") or "")
    email, password, _ = resolve_garmin_credentials(
        auth_enabled=_auth_enabled(),
        auth_role=role,
        session_email=str(st.session_state.get("garmin_email_input") or ""),
        session_password=str(st.session_state.get("garmin_password_input") or ""),
        env_email=cfg.garmin_email,
        env_password=cfg.garmin_password,
    )
    return email, password


def _get_garmin_credential_source() -> str:
    role = str(st.session_state.get("auth_role") or "")
    _, _, source = resolve_garmin_credentials(
        auth_enabled=_auth_enabled(),
        auth_role=role,
        session_email=str(st.session_state.get("garmin_email_input") or ""),
        session_password=str(st.session_state.get("garmin_password_input") or ""),
        env_email=cfg.garmin_email,
        env_password=cfg.garmin_password,
    )
    return source


def _clear_garmin_session_credentials() -> None:
    st.session_state["garmin_email_input"] = ""
    st.session_state["garmin_password_input"] = ""


def _allow_raw_persistence_for_current_user() -> bool:
    role = str(st.session_state.get("auth_role") or "").strip().lower()
    if _auth_enabled():
        return role == "admin"
    # If auth is disabled, preserve legacy single-user local behavior.
    return True


def _db_file_size_bytes(db_path: Path) -> int:
    try:
        return int(db_path.stat().st_size)
    except Exception:
        return 0


def _db_usage_text(db_path: Path) -> str:
    used = _db_file_size_bytes(db_path)
    quota = int(USER_DB_QUOTA_BYTES)
    used_mb = used / (1024.0 * 1024.0)
    quota_mb = quota / (1024.0 * 1024.0)
    return f"{used_mb:.1f}MB / {quota_mb:.0f}MB"


def _db_quota_exceeded(db_path: Path) -> bool:
    return _db_file_size_bytes(db_path) >= int(USER_DB_QUOTA_BYTES)


def _ensure_db_writable_or_warn(db_path: Path, action_label: str = "write") -> bool:
    if _db_quota_exceeded(db_path):
        st.error(
            f"Database quota reached ({_db_usage_text(db_path)}). "
            f"Cannot {action_label}. Delete data or increase quota."
        )
        return False
    return True


def _cleanup_raw_garmin_artifacts(export_root: Path) -> tuple[int, int]:
    removed_files = 0
    removed_bytes = 0
    targets: list[Path] = []
    raw_dir = export_root / "raw"
    if raw_dir.exists():
        targets.append(raw_dir)
    targets.extend(export_root.glob("garmin_extract_*.json"))
    for target in targets:
        try:
            if target.is_file():
                removed_bytes += int(target.stat().st_size)
                target.unlink(missing_ok=True)
                removed_files += 1
                continue
            if target.is_dir():
                for p in target.rglob("*"):
                    if p.is_file():
                        try:
                            removed_bytes += int(p.stat().st_size)
                            removed_files += 1
                        except Exception:
                            continue
                shutil.rmtree(target, ignore_errors=True)
        except Exception:
            continue
    return removed_files, removed_bytes


def _settings_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def save_setting_if_changed(db_path: Path, key: str, value: str) -> bool:
    existing = get_setting(db_path, key)
    if existing == value:
        return False
    save_setting(db_path, key, value)
    return True


def _activity_owner_key(activity: dict[str, object]) -> str | None:
    owner_id = str(activity.get("owner_id") or "").strip()
    if owner_id:
        return f"owner_id:{owner_id}"
    owner_name = str(activity.get("owner_full_name") or "").strip()
    if owner_name:
        return f"owner_name:{owner_name.lower()}"
    return None


def _enforce_garmin_owner_scope(activities: list[dict[str, object]]) -> tuple[bool, str]:
    owner_keys = {k for k in (_activity_owner_key(a) for a in activities) if k}
    if not owner_keys:
        return True, ""
    if len(owner_keys) > 1:
        return False, "Garmin sync returned multiple owner identities in one batch; sync blocked to avoid data mix."

    incoming = next(iter(owner_keys))
    existing = get_setting(cfg.db_path, SETTINGS_KEY_GARMIN_OWNER_SCOPE)
    if existing and existing != incoming:
        return (
            False,
            f"Garmin owner mismatch: existing scope `{existing}` vs incoming `{incoming}`. "
            "Use a separate Temperance DB/workspace for different Garmin accounts.",
        )
    save_setting_if_changed(cfg.db_path, SETTINGS_KEY_GARMIN_OWNER_SCOPE, incoming)
    return True, ""


def _user_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()).strip("._-")
    return cleaned or "default"


def _scoped_config_for_owner(owner: str):
    owner_slug = _user_slug(owner)
    users_root = base_cfg.db_path.parent / "users"
    scoped_db = users_root / f"{owner_slug}.db"
    scoped_import_dir = base_cfg.import_dir / "users" / owner_slug
    scoped_export_dir = base_cfg.private_export_dir / "users" / owner_slug
    return replace(
        base_cfg,
        db_path=scoped_db,
        import_dir=scoped_import_dir,
        private_export_dir=scoped_export_dir,
    )


def _pace_sec_to_mmss(pace_sec_per_km: float) -> str:
    total_seconds = int(round(float(pace_sec_per_km)))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _pace_mmss_to_sec(text: str) -> float:
    raw = str(text or "").strip().lower()
    raw = raw.replace("min/km", "").replace("/km", "").strip()
    if ":" in raw:
        mins_str, sec_str = raw.split(":", 1)
        mins = int(mins_str.strip())
        secs = int(sec_str.strip())
        if mins < 0 or secs < 0 or secs >= 60:
            raise ValueError("pace mm:ss must be valid")
        value = mins * 60 + secs
    else:
        value = float(raw)
    if value <= 0:
        raise ValueError("pace must be > 0")
    return float(value)


def _parse_curve_date(raw: object) -> date:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("date required")
    for fmt in ("%Y-%m-%d", "%d%b%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError("invalid date")


def _normalize_injury_windows(rows: list[dict]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        try:
            label = str(row.get("label") or "").strip() or "Injury"
            start_s = str(row.get("start") or "").strip()
            end_s = str(row.get("end") or "").strip()
            severity = str(row.get("severity") or "injury").strip().lower()
            if severity not in {"injury", "light_injury"}:
                severity = "injury"
            start_d = date.fromisoformat(start_s)
            end_d = date.fromisoformat(end_s)
            if end_d < start_d:
                start_d, end_d = end_d, start_d
            out.append(
                {
                    "label": label,
                    "start": start_d.isoformat(),
                    "end": end_d.isoformat(),
                    "severity": severity,
                }
            )
        except Exception:
            continue
    if not out:
        return [dict(x) for x in INJURY_WINDOWS]
    return out


def _load_injury_windows(db_path) -> list[dict[str, str]]:
    raw = get_setting(db_path, SETTINGS_KEY_INJURY_WINDOWS)
    if not raw:
        return [dict(x) for x in INJURY_WINDOWS]
    try:
        payload = json.loads(raw)
    except Exception:
        return [dict(x) for x in INJURY_WINDOWS]
    if not isinstance(payload, list):
        return [dict(x) for x in INJURY_WINDOWS]
    rows = [r for r in payload if isinstance(r, dict)]
    return _normalize_injury_windows(rows)


def _pace_text_or_blank(seconds: float | None) -> str:
    if seconds is None:
        return ""
    try:
        if pd.isna(seconds):
            return ""
    except Exception:
        pass
    try:
        value = float(seconds)
    except Exception:
        return ""
    if value <= 0:
        return ""
    return _pace_sec_to_mmss(value)


def _pace_optional_to_sec(text: object) -> float | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    return _pace_mmss_to_sec(raw)


def _default_lthr_curve() -> list[dict[str, object]]:
    return [{"date": "2025-01-01", "lthr_bpm": float(DEFAULT_LTHR)}]


def _default_lt_pace_curve() -> list[dict[str, object]]:
    return [{"date": "2025-01-01", "lt_pace_sec_per_km": float(DEFAULT_THRESHOLD_PACE_SEC_PER_KM)}]


def _default_if_zone_thresholds() -> dict[str, float]:
    return dict(DEFAULT_IF_ZONE_THRESHOLDS)


def _normalize_if_zone_thresholds(payload: dict[str, object] | None) -> dict[str, float]:
    base = _default_if_zone_thresholds()
    if not isinstance(payload, dict):
        return base
    out = dict(base)
    prev = 0.0
    for key in ["z1_max", "z2_max", "z3_max", "z4_max"]:
        try:
            if key in payload and payload.get(key) is not None:
                out[key] = float(payload.get(key))
        except Exception:
            out[key] = float(base[key])
        out[key] = float(min(max(out[key], 0.01), 3.0))
        if out[key] <= prev:
            out[key] = min(max(prev + 0.01, 0.01), 3.0)
        prev = out[key]
    return out


def _if_zone_thresholds_tuple(thresholds: dict[str, object] | None) -> tuple[float, float, float, float]:
    normalized = _normalize_if_zone_thresholds(thresholds)
    return (
        float(normalized["z1_max"]),
        float(normalized["z2_max"]),
        float(normalized["z3_max"]),
        float(normalized["z4_max"]),
    )


def _if_zone_thresholds_from_tuple(
    thresholds_key: tuple[float, float, float, float] | None,
) -> dict[str, float]:
    if isinstance(thresholds_key, tuple) and len(thresholds_key) == 4:
        return _normalize_if_zone_thresholds(
            {
                "z1_max": thresholds_key[0],
                "z2_max": thresholds_key[1],
                "z3_max": thresholds_key[2],
                "z4_max": thresholds_key[3],
            }
        )
    return _default_if_zone_thresholds()


def _normalize_lthr_curve(rows: list[dict]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        try:
            d = _parse_curve_date(row.get("date"))
            v = float(row.get("lthr_bpm"))
            if v <= 0:
                continue
            out.append({"date": d.isoformat(), "lthr_bpm": v})
        except Exception:
            continue
    if not out:
        return _default_lthr_curve()
    out = sorted(out, key=lambda x: x["date"])
    dedup: dict[str, dict[str, object]] = {str(x["date"]): x for x in out}
    return [dedup[k] for k in sorted(dedup.keys())]


def _normalize_lt_pace_curve(rows: list[dict]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        try:
            d = _parse_curve_date(row.get("date"))
            pace_raw = row.get("lt_pace")
            pace = _pace_optional_to_sec(pace_raw) if pace_raw is not None else float(row.get("lt_pace_sec_per_km"))
            if pace is None or pace <= 0:
                continue
            out.append({"date": d.isoformat(), "lt_pace_sec_per_km": float(pace)})
        except Exception:
            continue
    if not out:
        return _default_lt_pace_curve()
    out = sorted(out, key=lambda x: x["date"])
    dedup: dict[str, dict[str, object]] = {str(x["date"]): x for x in out}
    return [dedup[k] for k in sorted(dedup.keys())]


def _load_lthr_curve(db_path: Path) -> list[dict[str, object]]:
    raw = get_setting(db_path, SETTINGS_KEY_LTHR_CURVE)
    if not raw:
        return _default_lthr_curve()
    try:
        payload = json.loads(raw)
    except Exception:
        return _default_lthr_curve()
    if not isinstance(payload, list):
        return _default_lthr_curve()
    rows = [r for r in payload if isinstance(r, dict)]
    return _normalize_lthr_curve(rows)


def _load_lt_pace_curve(db_path: Path) -> list[dict[str, object]]:
    raw = get_setting(db_path, SETTINGS_KEY_LT_PACE_CURVE)
    if not raw:
        return _default_lt_pace_curve()
    try:
        payload = json.loads(raw)
    except Exception:
        return _default_lt_pace_curve()
    if not isinstance(payload, list):
        return _default_lt_pace_curve()
    rows = [r for r in payload if isinstance(r, dict)]
    return _normalize_lt_pace_curve(rows)


def _load_if_zone_thresholds(db_path: Path) -> dict[str, float]:
    raw = get_setting(db_path, SETTINGS_KEY_IF_ZONE_THRESHOLDS)
    if not raw:
        return _default_if_zone_thresholds()
    try:
        payload = json.loads(raw)
    except Exception:
        return _default_if_zone_thresholds()
    return _normalize_if_zone_thresholds(payload if isinstance(payload, dict) else None)


def _load_non_running_factor(db_path: Path, default_value: float = 0.8) -> float:
    raw = get_setting(db_path, SETTINGS_KEY_NON_RUNNING_FACTOR)
    if raw is None:
        return float(default_value)
    try:
        val = float(raw)
    except Exception:
        return float(default_value)
    return float(min(max(val, 0.0), 1.5))


def _default_specificity_profile(default_non_running: float = 0.8) -> dict[str, float]:
    d = float(min(max(default_non_running, 0.0), 1.5))
    return {
        "non_running": d,
        "treadmill": 1.0,
        "elliptical": d,
        "cycling": d,
    }


def _normalize_specificity_profile(payload: dict[str, object] | None, fallback_default: float = 0.8) -> dict[str, float]:
    base = _default_specificity_profile(fallback_default)
    if not isinstance(payload, dict):
        return base
    out = dict(base)
    legacy_default = payload.get("default_non_running")
    if legacy_default is not None and "non_running" not in payload:
        payload = dict(payload)
        payload["non_running"] = legacy_default
    for k in out.keys():
        try:
            if k in payload and payload.get(k) is not None:
                out[k] = float(min(max(float(payload.get(k)), 0.0), 1.5))
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


def _specificity_factor_for_sport(sport_type: str | None, profile: dict[str, float]) -> float:
    lower = str(sport_type or "").strip().lower()
    if "treadmill" in lower:
        return float(profile.get("treadmill", 1.0))
    if "ellipt" in lower:
        return float(profile.get("elliptical", profile.get("non_running", 0.8)))
    if ("cycl" in lower) or ("bike" in lower):
        return float(profile.get("cycling", profile.get("non_running", 0.8)))
    if "run" in lower:
        return 1.0
    return float(profile.get("non_running", 0.8))


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


def _curve_points_from_rows(rows: list[dict[str, object]], value_key: str) -> list[tuple[datetime, float]]:
    points: list[tuple[datetime, float]] = []
    for row in rows:
        try:
            d = datetime.fromisoformat(str(row.get("date")))
            v = float(row.get(value_key))
            if v > 0:
                points.append((d, v))
        except Exception:
            continue
    return sorted(points, key=lambda x: x[0])


def _curve_value_at(points: list[tuple[datetime, float]], default_value: float, at_dt: datetime | pd.Timestamp | None) -> float:
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


def _curve_latest_value(rows: list[dict[str, object]], value_key: str, default_value: float) -> float:
    if not rows:
        return float(default_value)
    try:
        return float(rows[-1].get(value_key) or default_value)
    except Exception:
        return float(default_value)


def _check_raw_archive_integrity(raw_root, start_day: date, end_day: date) -> dict[str, object]:
    """
    Lightweight integrity check for cached raw activity/daily payload files.
    Flags unreadable JSON and suspicious FIT files.
    """
    errors: list[str] = []
    checked_json = 0
    checked_fit = 0

    def _check_json(path) -> None:
        nonlocal checked_json
        try:
            if path.exists() and path.is_file():
                checked_json += 1
                json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"corrupt_json {path}: {exc}")

    # Activity raw payloads.
    activities_dir = raw_root / "activities"
    if activities_dir.exists():
        for p in activities_dir.rglob("*.json"):
            _check_json(p)

    # Daily payloads for selected date range.
    daily_dir = raw_root / "daily"
    if daily_dir.exists():
        cur = start_day
        while cur <= end_day:
            day_dir = daily_dir / cur.isoformat()
            if day_dir.exists():
                for p in day_dir.glob("*.json"):
                    _check_json(p)
            cur += timedelta(days=1)

    # FIT cache sanity.
    fit_dir = raw_root / "fit"
    if fit_dir.exists():
        for p in fit_dir.glob("*.fit"):
            try:
                checked_fit += 1
                data = p.read_bytes()
                if len(data) < 12:
                    errors.append(f"corrupt_fit {p}: file too small")
                    continue
                if data[8:12] != b".FIT":
                    errors.append(f"corrupt_fit {p}: invalid FIT signature")
            except Exception as exc:
                errors.append(f"corrupt_fit {p}: {exc}")

    return {
        "checked_json": checked_json,
        "checked_fit": checked_fit,
        "errors": errors,
    }


def format_pace_min_per_km(pace_s_per_km: float | None) -> str:
    if not pace_s_per_km or pace_s_per_km <= 0:
        return "-"
    total_seconds = int(round(float(pace_s_per_km)))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d} min/km"


def _duration_short(seconds: float | int | None) -> str:
    if seconds is None:
        return "-"
    try:
        total = int(round(float(seconds)))
    except Exception:
        return "-"
    if total <= 0:
        return "0m"
    hours = total // 3600
    minutes = (total % 3600) // 60
    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m"


def _duration_zone(seconds: float | int | None) -> str:
    if seconds is None:
        return "0m"
    try:
        total = int(round(float(seconds)))
    except Exception:
        return "0m"
    if total <= 0:
        return "0m"
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    if minutes > 0:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _duration_compact_with_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return "-"
    try:
        total = int(round(float(seconds)))
    except Exception:
        return "-"
    if total < 0:
        total = 0
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}h{minutes:02d}'{secs:02d}\""
    return f"{minutes}'{secs:02d}\""


def _truncate_to_decimals(value: float | int | None, digits: int = 2) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if not pd.notna(v):
        return 0.0
    factor = 10.0 ** max(int(digits), 0)
    return float(np.floor(v * factor) / factor)


def _split_description_from_token(token: str) -> str:
    return {
        "green": "Recovery",
        "blue": "Easy",
        "yellow": "Steady",
        "red": "Interval",
        "orange": "Overload",
        "tss_orange": "Overload",
        "purple": "VO2 Max",
        "tss_purple": "VO2 Max",
    }.get(str(token or "").strip().lower(), "Recovery")


def _split_description_from_if_proxy(if_proxy: float | int | None) -> str:
    zone = _if_zone_from_if_proxy(if_proxy)
    return str(IF_ZONE_VISUALS.get(str(zone or ""), IF_ZONE_VISUALS["Z1"]).get("description") or "Recovery")


def _if_palette_from_if_proxy(if_proxy: float | int | None) -> tuple[str, str]:
    zone = _if_zone_from_if_proxy(if_proxy)
    style = IF_ZONE_VISUALS.get(str(zone or ""), IF_ZONE_VISUALS["Z1"])
    return str(style.get("token") or "green"), str(style.get("accent") or "rgba(156,163,175,0.96)")


def _sport_label(sport_type: str | None) -> str:
    raw = str(sport_type or "").strip().replace("_", " ")
    if not raw:
        return "Activity"
    return raw.title()


def _actual_activity_palette(
    if_proxy: float | int | None,
    tss_value: float | int | None = None,
    rtss_value: float | int | None = None,
    sport_type: str | None = None,
    daily_tss_upper_bound: float | int | None = None,
) -> dict[str, str]:
    if_token, if_accent = _if_palette_from_if_proxy(if_proxy)
    token, accent = if_token, if_accent

    try:
        tss_v = float(tss_value) if tss_value is not None else 0.0
    except Exception:
        tss_v = 0.0
    try:
        rtss_v = float(rtss_value) if rtss_value is not None else 0.0
    except Exception:
        rtss_v = 0.0
    try:
        daily_cap = float(daily_tss_upper_bound) if daily_tss_upper_bound is not None else 0.0
    except Exception:
        daily_cap = 0.0
    sport_lower = str(sport_type or "").lower()
    is_running_like = ("run" in sport_lower) or ("treadmill" in sport_lower)
    override_load = rtss_v if is_running_like else tss_v
    if pd.notna(override_load) and pd.notna(daily_cap) and daily_cap > 0:
        if override_load > (daily_cap * 1.5):
            token = "tss_purple"
            accent = "rgba(192,132,252,0.96)"
        elif override_load > daily_cap and if_token not in {"red", "purple"}:
            token = "tss_orange"
            accent = "rgba(251,146,60,0.96)"

    return {
        "token": token,
        "accent": accent,
        "border": accent,
        "background": "rgba(15,23,42,0.78)",
    }


def _pace_compact(pace_s_per_km: float | int | None) -> str:
    if pace_s_per_km is None:
        return "-"
    try:
        val = float(pace_s_per_km)
    except Exception:
        return "-"
    if not pd.notna(val) or val <= 0:
        return "-"
    total_seconds = int(round(val))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}/km"


def _to_local_naive(series: pd.Series) -> pd.Series:
    local_tz = datetime.now().astimezone().tzinfo
    return (
        pd.to_datetime(series, utc=True, errors="coerce")
        .dt.tz_convert(local_tz)
        .dt.tz_localize(None)
    )


def _active_if_zone_thresholds() -> dict[str, float]:
    try:
        payload = st.session_state.get("user_if_zone_thresholds")
    except Exception:
        payload = None
    return _normalize_if_zone_thresholds(payload if isinstance(payload, dict) else None)


def _if_zone_from_if_proxy(
    if_proxy: float | int | None,
    thresholds: dict[str, object] | None = None,
) -> str | None:
    if if_proxy is None:
        return None
    try:
        v = float(if_proxy)
    except Exception:
        return None
    if not pd.notna(v) or v <= 0:
        return None
    t = _normalize_if_zone_thresholds(
        thresholds if isinstance(thresholds, dict) else _active_if_zone_thresholds()
    )
    if v < float(t["z1_max"]):
        return "Z1"
    if v < float(t["z2_max"]):
        return "Z2"
    if v < float(t["z3_max"]):
        return "Z3"
    if v < float(t["z4_max"]):
        return "Z4"
    return "Z5"


def _zone_seconds_from_activity_row(row: pd.Series) -> dict[str, float]:
    zone_cols = {
        "Z1": "hr_time_in_zone_1",
        "Z2": "hr_time_in_zone_2",
        "Z3": "hr_time_in_zone_3",
        "Z4": "hr_time_in_zone_4",
        "Z5": "hr_time_in_zone_5",
    }
    out = {z: 0.0 for z in zone_cols}
    for zone, col in zone_cols.items():
        out[zone] = float(pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").fillna(0.0).iloc[0])
    if sum(out.values()) > 0:
        return out

    duration_s = float(pd.to_numeric(pd.Series([row.get("duration_s")]), errors="coerce").fillna(0.0).iloc[0])
    if duration_s <= 0:
        return out
    inferred_zone = _if_zone_from_if_proxy(row.get("if_proxy"))
    if inferred_zone:
        out[inferred_zone] = duration_s
    return out


def _if_zone_guidance_df(
    lthr_bpm: float,
    lt_pace_sec_per_km: float,
    thresholds: dict[str, object] | None = None,
) -> pd.DataFrame:
    t = _normalize_if_zone_thresholds(thresholds if isinstance(thresholds, dict) else _active_if_zone_thresholds())
    z1 = float(t["z1_max"])
    z2 = float(t["z2_max"])
    z3 = float(t["z3_max"])
    z4 = float(t["z4_max"])

    def _hr_range(lo: float | None, hi: float | None) -> str:
        if lthr_bpm <= 0:
            return "-"
        if lo is None and hi is not None:
            return f"< {int(round(hi * lthr_bpm))}"
        if lo is not None and hi is not None:
            return f"{int(round(lo * lthr_bpm))}-{int(round(hi * lthr_bpm))}"
        if lo is not None and hi is None:
            return f"> {int(round(lo * lthr_bpm))}"
        return "-"

    def _pace_range(lo: float | None, hi: float | None) -> str:
        if lt_pace_sec_per_km <= 0:
            return "-"
        if lo is None and hi is not None and hi > 0:
            return f"> {_pace_compact(lt_pace_sec_per_km / hi)}"
        if lo is not None and hi is not None and lo > 0 and hi > 0:
            fast = _pace_compact(lt_pace_sec_per_km / hi)
            slow = _pace_compact(lt_pace_sec_per_km / lo)
            return f"{fast} - {slow}"
        if lo is not None and hi is None and lo > 0:
            return f"< {_pace_compact(lt_pace_sec_per_km / lo)}"
        return "-"

    zone_specs: list[tuple[str, str, float | None, float | None]] = [
        ("Z1", f"< {z1 * 100.0:.0f}%", None, z1),
        ("Z2", f"{z1 * 100.0:.0f}% - <{z2 * 100.0:.0f}%", z1, z2),
        ("Z3", f"{z2 * 100.0:.0f}% - <{z3 * 100.0:.0f}%", z2, z3),
        ("Z4", f"{z3 * 100.0:.0f}% - <{z4 * 100.0:.0f}%", z3, z4),
        ("Z5", f">= {z4 * 100.0:.0f}%", z4, None),
    ]
    rows = []
    for zone, if_range, lo, hi in zone_specs:
        rows.append(
            {
                "Zone": zone,
                "IF Range": if_range,
                "Suggested HR (bpm)": _hr_range(lo, hi),
                "Suggested Pace": _pace_range(lo, hi),
            }
        )
    return pd.DataFrame(rows)


def _plan_activity_kind(text: str) -> str:
    t = text.lower()
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
    t = text.lower().strip()
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
    # Support shorthand minute notation like 20' or 20’.
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
    m = re.search(r"(\d+(?:\.\d+)?)\s*km\b", text.lower())
    if m:
        try:
            km = float(m.group(1))
        except Exception:
            return None
        return km if km > 0 else None
    m_meters = re.search(r"(\d+(?:\.\d+)?)\s*m\b", text.lower())
    if not m_meters:
        return None
    try:
        meters = float(m_meters.group(1))
    except Exception:
        return None
    km = meters / 1000.0
    return km if km > 0 else None


def _parse_bpm_token(text: str) -> float | None:
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*bpm", text.lower())
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*bpm", text.lower())
    if m:
        v = float(m.group(1))
        return v if v > 0 else None
    return None


def _parse_pace_token(text: str) -> float | None:
    m = re.search(r"@\s*(\d{1,2}:\d{2})(?:\s*/?\s*km)?", text.lower())
    if not m:
        m = re.search(r"(\d{1,2}:\d{2})\s*/\s*km", text.lower())
    if m:
        try:
            return _pace_mmss_to_sec(m.group(1))
        except Exception:
            return None
    return None


def _parse_if_token(text: str) -> float | None:
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*%", text.lower())
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", text.lower())
    if not m:
        return None
    try:
        v = float(m.group(1)) / 100.0
    except Exception:
        return None
    if v <= 0:
        return None
    return v


def _parse_tss_token(text: str) -> float | None:
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*tss\b", text.lower())
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*tss\b", text.lower())
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
        # Support shorthand without `:` such as `T-160' elliptical @140bpm`
        # interpreted as `T-1:60' elliptical @140bpm`.
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
        # Accept aliases: T+N / T-N (N days from today)
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
        return None, activity_text, "Invalid date format. Use one of: `today`, `tomorrow`, `yesterday`, `T`, `T+1`, `T-1`, `3Mar26`, `2026-03-26`, `26/03/2026`."
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
            # pace implies run-like segment
            kind = "run"
        if kind == "other" and last_kind is not None:
            # allow shorthand continuation like "5x6min @3:40/km" after a running chunk
            kind = last_kind

        if kind == "other":
            warnings.append(f"Missing/unknown activity in: `{chunk}` (include run/treadmill/elliptical/cycling)")
            continue
        is_running_like = kind in {"run", "treadmill"}
        if (not is_running_like) and (pace is not None):
            warnings.append(
                f"Pace is only allowed for running/treadmill in: `{chunk}` "
                "(use `@140bpm` or `@70%` for non-running)."
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
            if rep_unit.startswith("h"):
                rep_minutes = rep_value * 60.0
            elif rep_unit.startswith("s"):
                rep_minutes = rep_value / 60.0
            else:
                rep_minutes = rep_value
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

        rep_m_match = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*m\b", chunk.lower())
        if rep_m_match:
            reps = int(rep_m_match.group(1))
            rep_km = float(rep_m_match.group(2)) / 1000.0
            if reps <= 0 or rep_km <= 0:
                warnings.append(f"Invalid interval block in: `{chunk}`")
                continue
            if not is_running_like:
                warnings.append(f"Distance intervals are only supported for running/treadmill in: `{chunk}`")
                continue
            if pace is None and tss_input is not None and tss_input > 0 and threshold_pace_value > 0:
                per_rep_tss = float(tss_input) / float(max(reps, 1))
                pace = (rep_km * (threshold_pace_value ** 2) * 100.0) / (3600.0 * per_rep_tss)
                if pace > 0:
                    if_input = threshold_pace_value / pace
            if pace is None or pace <= 0:
                warnings.append(f"Distance intervals require pace in: `{chunk}` (add `@4:50/km`)")
                continue
            rep_minutes = (rep_km * pace) / 60.0
            for _ in range(max(reps, 0)):
                segments.append(
                    {
                        "kind": kind,
                        "duration_min": rep_minutes,
                        "distance_km": rep_km,
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

        rep_km_match = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*km\b", chunk.lower())
        if rep_km_match:
            reps = int(rep_km_match.group(1))
            rep_km = float(rep_km_match.group(2))
            if reps <= 0 or rep_km <= 0:
                warnings.append(f"Invalid interval block in: `{chunk}`")
                continue
            if not is_running_like:
                warnings.append(f"Distance intervals are only supported for running/treadmill in: `{chunk}`")
                continue
            if pace is None and tss_input is not None and tss_input > 0 and threshold_pace_value > 0:
                per_rep_tss = float(tss_input) / float(max(reps, 1))
                pace = (rep_km * (threshold_pace_value ** 2) * 100.0) / (3600.0 * per_rep_tss)
                if pace > 0:
                    if_input = threshold_pace_value / pace
            if pace is None or pace <= 0:
                warnings.append(f"Distance intervals require pace in: `{chunk}` (add `@4:50/km`)")
                continue
            rep_minutes = (rep_km * pace) / 60.0
            for _ in range(max(reps, 0)):
                segments.append(
                    {
                        "kind": kind,
                        "duration_min": rep_minutes,
                        "distance_km": rep_km,
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
                        f"Distance-only segment requires running/treadmill with pace in: `{chunk}` "
                        "(non-running should use minutes + bpm/%IF)."
                    )
                    continue
                if pace is None and tss_input is not None and tss_input > 0 and threshold_pace_value > 0:
                    pace = (distance_km * (threshold_pace_value ** 2) * 100.0) / (3600.0 * float(tss_input))
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
        rtss = duration_h * (if_proxy ** 2) * 100.0
        distance_eqv_km = duration_s / pace
        if hr and lthr_bpm > 0:
            if_hr = max(hr / lthr_bpm, 0.0)
            tss = duration_h * (if_hr ** 2) * 100.0
        else:
            tss = rtss
    elif is_running_like and if_input and if_input > 0:
        if_proxy = max(float(if_input), 0.0)
        rtss = duration_h * (if_proxy ** 2) * 100.0
        tss = rtss
        if threshold_pace_sec_per_km > 0 and if_proxy > 0:
            eq_pace = threshold_pace_sec_per_km / if_proxy
            if eq_pace > 0:
                distance_eqv_km = duration_s / eq_pace
    else:
        if hr and lthr_bpm > 0:
            if_hr = max(hr / lthr_bpm, 0.0)
            tss = duration_h * (if_hr ** 2) * 100.0
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
            tss = duration_h * (if_proxy ** 2) * 100.0
            effective_rtss = max(tss * max(non_running_factor, 0.0), 0.0)
            if effective_rtss > 0:
                eq_if = (effective_rtss / (duration_h * 100.0)) ** 0.5
                if eq_if > 0:
                    eq_pace = threshold_pace_sec_per_km / eq_if
                    if eq_pace > 0:
                        distance_eqv_km = duration_s / eq_pace
        elif pace and pace > 0:
            if_proxy = max(threshold_pace_sec_per_km / pace, 0.0)
            tss = duration_h * (if_proxy ** 2) * 100.0
            effective_rtss = max(tss * max(non_running_factor, 0.0), 0.0)
            if effective_rtss > 0:
                eq_if = (effective_rtss / (duration_h * 100.0)) ** 0.5
                if eq_if > 0:
                    eq_pace = threshold_pace_sec_per_km / eq_if
                    if eq_pace > 0:
                        distance_eqv_km = duration_s / eq_pace

    return {
        "duration_s": duration_s,
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
    """Ensure @TSS for non-running is treated as final post-scale TSS target."""
    seg_for_metrics = dict(seg)
    is_running_like = seg_kind in {"run", "treadmill"}
    if is_running_like:
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
    else:
        has_tss = True
    if not has_tss:
        return seg_for_metrics
    tss_target = pd.to_numeric(pd.Series([seg_for_metrics.get("tss_target")]), errors="coerce").fillna(0.0).iloc[0]
    duration_min = pd.to_numeric(pd.Series([seg_for_metrics.get("duration_min")]), errors="coerce").fillna(0.0).iloc[0]
    spec = float(max(seg_spec, 0.0))
    duration_h = float(max(duration_min, 0.0)) / 60.0
    if spec <= 0 or duration_h <= 0 or float(tss_target) <= 0:
        return seg_for_metrics
    # tss_target is user-facing final TSS; metrics apply seg_spec later, so invert it here.
    unscaled_tss_target = float(tss_target) / spec
    derived_if = (unscaled_tss_target / (duration_h * 100.0)) ** 0.5
    if derived_if > 0:
        seg_for_metrics["if_input"] = float(derived_if)
        seg_for_metrics["avg_hr_bpm"] = None
        seg_for_metrics["pace_s_per_km"] = None
    return seg_for_metrics


def _sum_duration_s_from_parsed_segments(raw_segments: object) -> float:
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
    total_s = 0.0
    for seg in segments:
        try:
            total_s += max(float(seg.get("duration_min") or 0.0), 0.0) * 60.0
        except Exception:
            continue
    return float(total_s)


def _compute_planned_rows_metrics_df(
    planned_rows: pd.DataFrame,
    lthr_curve_points: list[tuple[pd.Timestamp, float]],
    lthr_default_bpm: float,
    lt_pace_curve_points: list[tuple[pd.Timestamp, float]],
    lt_pace_default_sec: float,
    specificity_profile: dict[str, float],
) -> pd.DataFrame:
    if planned_rows.empty:
        return pd.DataFrame(
            columns=[
                "day_utc",
                "line_no",
                "activity",
                "sport_type",
                "workout_text",
                "tss",
                "rtss",
                "distance_proxy_km",
                "distance_km",
                "duration_s",
                "if_proxy",
                "if_weighted",
            ]
        )

    out = planned_rows.copy()
    tss_vals: list[float] = []
    rtss_vals: list[float] = []
    dist_eqv_vals: list[float] = []
    dist_run_vals: list[float] = []
    if_vals: list[float] = []
    dur_vals: list[float] = []
    if_weighted_vals: list[float] = []
    activity_vals: list[str] = []
    sport_vals: list[str] = []
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
        total_dist_run = 0.0
        if_weighted_sum = 0.0
        if_weight_seconds = 0.0
        kinds_seen: list[str] = []
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
            seg_dist_eqv = float(m.get("distance_eqv_km") or 0.0)
            total_tss += float(m.get("tss") or 0.0) * float(seg_spec)
            total_rtss += float(m.get("rtss") or 0.0) * float(seg_spec)
            total_dist_eqv += seg_dist_eqv
            if seg_kind in {"run", "treadmill"}:
                total_dist_run += seg_dist_eqv
            if seg_duration > 0:
                if_weighted_sum += seg_if * seg_duration
                if_weight_seconds += seg_duration
            if seg_kind and seg_kind not in kinds_seen:
                kinds_seen.append(seg_kind)

        tss_vals.append(total_tss)
        rtss_vals.append(total_rtss)
        dist_eqv_vals.append(total_dist_eqv)
        dist_run_vals.append(total_dist_run)
        dur_vals.append(if_weight_seconds)
        if_vals.append(if_weighted_sum / if_weight_seconds if if_weight_seconds > 0 else 0.0)
        if_weighted_vals.append(if_weighted_sum)
        activity_label = ", ".join([k.replace("_", " ").title() for k in kinds_seen]) if kinds_seen else "-"
        activity_vals.append(activity_label)
        sport_vals.append(activity_label.lower())

    out["activity"] = activity_vals
    out["sport_type"] = sport_vals
    out["tss"] = tss_vals
    out["rtss"] = rtss_vals
    out["distance_proxy_km"] = dist_eqv_vals
    out["distance_km"] = dist_run_vals
    out["duration_s"] = dur_vals
    out["if_proxy"] = if_vals
    out["if_weighted"] = if_weighted_vals
    return out


def _build_planned_daily_summary_df(rows_df: pd.DataFrame) -> pd.DataFrame:
    if rows_df.empty:
        return pd.DataFrame(
            columns=[
                "day_utc",
                "tss_total",
                "rtss_total",
                "distance_proxy_km",
                "distance_km",
                "duration_s",
                "if_proxy",
                "if_weighted",
            ]
        )
    out = rows_df.copy()
    out["day_utc"] = out["day_utc"].astype(str)
    grouped = (
        out.groupby("day_utc", as_index=False)
        .agg(
            tss_total=("tss", "sum"),
            rtss_total=("rtss", "sum"),
            distance_proxy_km=("distance_proxy_km", "sum"),
            distance_km=("distance_km", "sum"),
            duration_s=("duration_s", "sum"),
            if_weighted=("if_weighted", "sum"),
        )
        .sort_values("day_utc")
    )
    grouped["if_proxy"] = 0.0
    valid = pd.to_numeric(grouped["duration_s"], errors="coerce").fillna(0.0) > 0
    grouped.loc[valid, "if_proxy"] = (
        pd.to_numeric(grouped.loc[valid, "if_weighted"], errors="coerce").fillna(0.0)
        / pd.to_numeric(grouped.loc[valid, "duration_s"], errors="coerce").fillna(0.0)
    )
    return grouped


def _apply_planned_actual_matching(
    planned_rows: pd.DataFrame,
    actual_metrics: pd.DataFrame,
) -> pd.DataFrame:
    if planned_rows.empty:
        return planned_rows
    # Deprecated behavior: do not auto-drop planned rows by actual-count matching.
    # Visibility/completion is controlled by date + `manual_done`.
    return planned_rows.copy()


def _to_seconds(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value) if float(value) > 0 else None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        # Handles HH:MM:SS and MM:SS
        parts = [float(p) for p in raw.split(":")]
        if len(parts) == 3:
            h, m, s = parts
            total = h * 3600 + m * 60 + s
            return total if total > 0 else None
        if len(parts) == 2:
            m, s = parts
            total = m * 60 + s
            return total if total > 0 else None
    except Exception:
        pass
    try:
        v = float(raw)
        return v if v > 0 else None
    except Exception:
        return None


def _sync_splits_from_raw_activity_cache(raw_root: Path) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    activities_dir = raw_root / "activities"
    if not activities_dir.exists():
        return rows, [f"raw activities directory not found: {activities_dir}"]

    for act_dir in activities_dir.iterdir():
        if not act_dir.is_dir():
            continue
        activity_id = act_dir.name
        splits_path = act_dir / "splits.json"
        split_summaries_path = act_dir / "split_summaries.json"
        if not splits_path.exists() and not split_summaries_path.exists():
            continue
        try:
            split_payload = {}
            split_summaries_payload = {}
            if splits_path.exists():
                split_payload = json.loads(splits_path.read_text(encoding="utf-8"))
            if split_summaries_path.exists():
                split_summaries_payload = json.loads(split_summaries_path.read_text(encoding="utf-8"))

            laps: list[dict[str, object]] = []
            if isinstance(split_payload, dict):
                lap_rows = split_payload.get("lapDTOs")
                if isinstance(lap_rows, list):
                    laps = [x for x in lap_rows if isinstance(x, dict)]
            if not laps and isinstance(split_summaries_payload, list):
                laps = [x for x in split_summaries_payload if isinstance(x, dict)]
            elif not laps and isinstance(split_summaries_payload, dict):
                maybe = split_summaries_payload.get("splitSummaries")
                if isinstance(maybe, list):
                    laps = [x for x in maybe if isinstance(x, dict)]

            total_duration_s = 0.0
            total_distance_m = 0.0
            for lap in laps:
                d = pd.to_numeric(
                    lap.get("duration")
                    or lap.get("elapsedDuration")
                    or lap.get("movingDuration")
                    or lap.get("totalTimerTime"),
                    errors="coerce",
                )
                if pd.notna(d) and float(d) > 0:
                    total_duration_s += float(d)
                dist = pd.to_numeric(
                    lap.get("distance") or lap.get("totalDistance") or lap.get("distanceMeters"),
                    errors="coerce",
                )
                if pd.notna(dist) and float(dist) > 0:
                    total_distance_m += float(dist)

            rows.append(
                {
                    "activity_id": str(activity_id),
                    "split": split_payload,
                    "split_summaries": split_summaries_payload,
                    "lap_count": float(len(laps)) if len(laps) > 0 else None,
                    "total_duration_s": total_duration_s if total_duration_s > 0 else None,
                    "total_distance_m": total_distance_m if total_distance_m > 0 else None,
                }
            )
        except Exception as exc:
            errors.append(f"activity_id={activity_id}: {exc}")
    return rows, errors


def filter_by_activity_type(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    if df.empty or mode == "All Activities":
        return df

    sport = df["sport_type"].fillna("").astype(str).str.lower()
    if mode == "All Running":
        mask = sport.str.contains("run") | sport.str.contains("treadmill")
    elif mode == "Running":
        mask = sport.str.contains("run") & ~sport.str.contains("treadmill")
    elif mode == "Treadmill":
        mask = sport.str.contains("treadmill")
    elif mode == "Cycling":
        mask = sport.str.contains("cycl") | sport.str.contains("bike")
    elif mode == "Elliptical":
        mask = sport.str.contains("elliptical")
    else:
        mask = pd.Series([True] * len(df), index=df.index)

    return df.loc[mask].copy()


def apply_specificity_factor(df: pd.DataFrame, specificity_profile: dict[str, float]) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    sport = out["sport_type"].fillna("").astype(str).str.lower()
    out["specificity_factor"] = out["sport_type"].apply(
        lambda s: _specificity_factor_for_sport(s, specificity_profile)
    )
    is_running_like = sport.str.contains("run") | sport.str.contains("treadmill")

    # Distance equivalent is computed at ingest time with base non-running specificity 0.8.
    # Re-scale proxy distance/pace at view time so UI specificity changes are reflected
    # without full recompute. Keep IF proxy unchanged (raw intensity signal).
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
            out[col] = out[col] * out["specificity_factor"]
    return out


@st.cache_data(show_spinner=False)
def get_metrics_df_fast(
    db_path: Path,
    activities_cache_key: str,
    activity_splits_cache_key: str,
    lthr_bpm: float,
    lthr_curve_points: list[tuple[datetime, float]] | None,
    threshold_pace_default_sec: float,
    threshold_pace_curve_points: list[tuple[datetime, float]] | None,
    use_split_method: bool,
    if_zone_thresholds_key: tuple[float, float, float, float] | None = None,
    metrics_derivation_cache_version: int = 1,
) -> pd.DataFrame:
    _ = if_zone_thresholds_key, metrics_derivation_cache_version
    runs_df = get_runs_df(db_path)
    df = compute_metrics(
        runs_df,
        lthr_bpm=lthr_bpm,
        threshold_pace_sec_per_km=threshold_pace_default_sec,
        threshold_pace_curve_points=threshold_pace_curve_points,
        lthr_curve_points=lthr_curve_points,
    )
    if use_split_method and not df.empty:
        splits_df = get_activity_splits_df(db_path)
        if not splits_df.empty:
            split_lookup = {
                str(r.get("activity_id")): r
                for r in splits_df.to_dict(orient="records")
                if r.get("activity_id") is not None
            }
            def _num(d: dict, keys: list[str]) -> float | None:
                for k in keys:
                    if k not in d:
                        continue
                    try:
                        v = float(d.get(k))
                        if pd.notna(v):
                            return v
                    except Exception:
                        continue
                return None

            def _rel_diff(a: float | None, b: float | None) -> float | None:
                if a is None or b is None:
                    return None
                if a <= 0 or b <= 0:
                    return None
                return abs(a - b) / float(a)

            for idx, row in df.iterrows():
                split_row = split_lookup.get(str(row.get("activity_id")))
                if not split_row:
                    continue

                try:
                    split_payload = json.loads(split_row.get("split_json") or "{}")
                except Exception:
                    split_payload = {}
                laps = split_payload.get("lapDTOs") if isinstance(split_payload, dict) else None
                if not isinstance(laps, list) or not laps:
                    try:
                        summaries_payload = json.loads(split_row.get("split_summaries_json") or "[]")
                    except Exception:
                        summaries_payload = []
                    if isinstance(summaries_payload, list):
                        laps = [x for x in summaries_payload if isinstance(x, dict)]
                    elif isinstance(summaries_payload, dict):
                        maybe = summaries_payload.get("splitSummaries")
                        laps = [x for x in (maybe or []) if isinstance(x, dict)] if isinstance(maybe, list) else []
                    else:
                        laps = []
                if not laps:
                    continue

                avg_hr_activity = pd.to_numeric(pd.Series([row.get("avg_hr")]), errors="coerce").iloc[0]
                avg_hr_activity = float(avg_hr_activity) if pd.notna(avg_hr_activity) else None
                sport = str(row.get("sport_type") or "").lower()
                running_like = ("run" in sport) or ("treadmill" in sport)
                start_dt = pd.to_datetime(row.get("start_time_utc"), utc=True, errors="coerce")
                tp_sec = _curve_value_at(
                    threshold_pace_curve_points or [],
                    float(threshold_pace_default_sec),
                    start_dt,
                )
                lthr_at = _curve_value_at(
                    lthr_curve_points or [],
                    float(lthr_bpm),
                    start_dt,
                )

                tss_sum = 0.0
                rtss_sum = 0.0
                tss_any = False
                rtss_any = False
                lap_duration_total = 0.0
                lap_distance_total = 0.0
                for lap in laps:
                    if not isinstance(lap, dict):
                        continue
                    lap_duration_s = _num(
                        lap,
                        ["duration", "movingDuration", "elapsedDuration", "lapDuration", "totalDuration", "durationInSeconds"],
                    )
                    lap_distance_m = _num(
                        lap,
                        ["distance", "totalDistance", "sumDistance", "distanceInMeters", "distanceMeters"],
                    )
                    if lap_duration_s is None or lap_duration_s <= 0:
                        continue
                    lap_duration_total += float(lap_duration_s)
                    if lap_distance_m is not None and lap_distance_m > 0:
                        lap_distance_total += float(lap_distance_m)

                    lap_avg_hr = _num(
                        lap,
                        ["averageHR", "avgHR", "averageHeartRate", "meanHeartRate", "avgHeartRate"],
                    )
                    hr_for_tss = lap_avg_hr if lap_avg_hr is not None else avg_hr_activity
                    if hr_for_tss is not None and 0 < hr_for_tss <= 260 and lthr_at > 0:
                        tss_sum += (lap_duration_s * ((float(hr_for_tss) / float(lthr_at)) ** 2) / 3600.0) * 100.0
                        tss_any = True

                    if running_like and lap_distance_m is not None and lap_distance_m > 0 and tp_sec > 0:
                        lap_pace = lap_duration_s / (lap_distance_m / 1000.0)
                        if lap_pace > 0:
                            rtss_sum += (lap_duration_s * ((tp_sec / lap_pace) ** 2) / 3600.0) * 100.0
                            rtss_any = True

                summary_duration = _num(row.to_dict(), ["duration_s", "moving_duration_s", "elapsed_duration_s"])
                summary_distance = _num(row.to_dict(), ["distance_m"])
                duration_div = _rel_diff(summary_duration, lap_duration_total if lap_duration_total > 0 else None)
                distance_div = _rel_diff(summary_distance, lap_distance_total if lap_distance_total > 0 else None)
                if (duration_div is not None and duration_div > 0.05) or (
                    distance_div is not None and distance_div > 0.05
                ):
                    # Split payload diverges materially from summary; keep summary-based metrics.
                    continue

                if tss_any:
                    df.at[idx, "tss"] = tss_sum
                if rtss_any:
                    df.at[idx, "rtss"] = rtss_sum
    return df


@st.cache_data(show_spinner=False)
def _build_custom_metrics_df_for_plots(
    db_path: Path,
    custom_activities_cache_key: str,
    lthr_bpm: float,
    lthr_curve_points: list[tuple[datetime, float]] | None,
    threshold_pace_default_sec: float,
    threshold_pace_curve_points: list[tuple[datetime, float]] | None,
    if_zone_thresholds_key: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    zone_thresholds = _if_zone_thresholds_from_tuple(if_zone_thresholds_key)
    raw = get_custom_activities_df(db_path)
    if raw.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for _, custom_row in raw.iterrows():
        day_utc = str(custom_row.get("day_utc") or "").strip()
        line_no_raw = custom_row.get("line_no")
        try:
            line_no = int(line_no_raw)
        except Exception:
            line_no = 1
        if not day_utc:
            continue

        raw_segments = custom_row.get("parsed_json")
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
        if not segments:
            continue

        day_local_naive = pd.to_datetime(day_utc, errors="coerce")
        if pd.isna(day_local_naive):
            continue
        day_local_naive = pd.Timestamp(day_local_naive).normalize()
        local_tz = datetime.now().astimezone().tzinfo
        try:
            day_local = day_local_naive.tz_localize(local_tz)
        except Exception:
            day_local = day_local_naive.tz_localize("UTC")
        day_for_curve = day_local.tz_convert("UTC")
        lthr_for_day = float(_curve_value_at(lthr_curve_points or [], float(lthr_bpm), day_for_curve))
        tp_for_day = float(
            _curve_value_at(
                threshold_pace_curve_points or [],
                float(threshold_pace_default_sec),
                day_for_curve,
            )
        )

        total_duration_s = 0.0
        total_tss = 0.0
        total_rtss = 0.0
        total_dist_eqv_km = 0.0
        if_weighted_sum = 0.0
        if_weight_seconds = 0.0
        zone_seconds = {"Z1": 0.0, "Z2": 0.0, "Z3": 0.0, "Z4": 0.0, "Z5": 0.0}
        hr_weighted_sum = 0.0
        hr_weight_seconds = 0.0
        running_distance_m = 0.0
        kind_duration: dict[str, float] = {}

        for seg in segments:
            seg_kind = str(seg.get("kind") or "").strip().lower()
            # Keep custom rows "raw". Specificity is applied once in apply_specificity_factor().
            # For distance eqv, use the same 0.8 ingest baseline used by Garmin proxy rows.
            m = _planned_segment_metrics(
                seg,
                lthr_bpm=lthr_for_day,
                threshold_pace_sec_per_km=tp_for_day,
                non_running_factor=0.8,
            )
            seg_duration_s = float(m.get("duration_s") or 0.0)
            if seg_duration_s <= 0:
                continue

            total_duration_s += seg_duration_s
            total_tss += float(m.get("tss") or 0.0)
            total_rtss += float(m.get("rtss") or 0.0)
            total_dist_eqv_km += float(m.get("distance_eqv_km") or 0.0)
            seg_if = float(m.get("if_proxy") or 0.0)
            if seg_if > 0:
                if_weighted_sum += seg_if * seg_duration_s
                if_weight_seconds += seg_duration_s
                seg_zone = _if_zone_from_if_proxy(seg_if, thresholds=zone_thresholds)
                if seg_zone is not None:
                    zone_seconds[seg_zone] = zone_seconds.get(seg_zone, 0.0) + seg_duration_s

            seg_hr = pd.to_numeric(seg.get("avg_hr_bpm"), errors="coerce")
            if pd.notna(seg_hr) and float(seg_hr) > 0:
                hr_weighted_sum += float(seg_hr) * seg_duration_s
                hr_weight_seconds += seg_duration_s

            seg_pace = pd.to_numeric(seg.get("pace_s_per_km"), errors="coerce")
            if seg_kind in {"run", "treadmill"} and pd.notna(seg_pace) and float(seg_pace) > 0:
                running_distance_m += (seg_duration_s / float(seg_pace)) * 1000.0

            kind_duration[seg_kind or "other"] = kind_duration.get(seg_kind or "other", 0.0) + seg_duration_s

        if total_duration_s <= 0:
            continue

        dominant_kind = max(kind_duration.items(), key=lambda x: x[1])[0] if kind_duration else "other"
        if dominant_kind == "run":
            sport_type = "running"
        elif dominant_kind == "treadmill":
            sport_type = "treadmill_running"
        else:
            sport_type = dominant_kind

        avg_hr = (hr_weighted_sum / hr_weight_seconds) if hr_weight_seconds > 0 else None
        avg_pace = (total_duration_s / (running_distance_m / 1000.0)) if running_distance_m > 0 else None
        if_proxy = (if_weighted_sum / if_weight_seconds) if if_weight_seconds > 0 else 0.0
        zoned_duration = float(sum(zone_seconds.values()))
        remaining_duration = max(float(total_duration_s) - zoned_duration, 0.0)
        if remaining_duration > 0 and if_proxy > 0:
            fallback_zone = _if_zone_from_if_proxy(if_proxy, thresholds=zone_thresholds)
            if fallback_zone is not None:
                zone_seconds[fallback_zone] = zone_seconds.get(fallback_zone, 0.0) + remaining_duration
        pace_proxy = (total_duration_s / total_dist_eqv_km) if total_dist_eqv_km > 0 else None
        start_time = (day_local + pd.Timedelta(minutes=max(line_no, 1))).tz_convert("UTC")

        rows.append(
            {
                "activity_id": f"custom:{day_utc}:{line_no}",
                "activity_name": "Custom Activity",
                "start_time_utc": start_time,
                "sport_type": sport_type,
                "distance_m": running_distance_m,
                "duration_s": total_duration_s,
                "moving_duration_s": total_duration_s,
                "elapsed_duration_s": total_duration_s,
                "avg_hr": avg_hr,
                "avg_pace_s_per_km": avg_pace,
                "rtss": total_rtss,
                "tss": total_tss,
                "trimp": 0.0,
                "edwards_trimp": 0.0,
                "mechanical_load": 0.0,
                "distance_proxy_km": total_dist_eqv_km,
                "pace_proxy_sec_per_km": pace_proxy,
                "distance_proxy_method": "tss_parity_root_solve",
                "if_proxy": if_proxy,
                "training_load_garmin": 0.0,
                "calories_active": 0.0,
                "calories_total": 0.0,
                "intensity_minutes_vigorous": 0.0,
                "intensity_minutes_moderate": 0.0,
                "hr_time_in_zone_1": zone_seconds.get("Z1", 0.0),
                "hr_time_in_zone_2": zone_seconds.get("Z2", 0.0),
                "hr_time_in_zone_3": zone_seconds.get("Z3", 0.0),
                "hr_time_in_zone_4": zone_seconds.get("Z4", 0.0),
                "hr_time_in_zone_5": zone_seconds.get("Z5", 0.0),
            }
        )

    if not rows:
        return pd.DataFrame()
    custom_df = pd.DataFrame(rows)
    custom_df["start_time_utc"] = pd.to_datetime(custom_df["start_time_utc"], utc=True, errors="coerce")
    return custom_df


def _merge_metrics_with_custom(base_df: pd.DataFrame, custom_df: pd.DataFrame) -> pd.DataFrame:
    if custom_df.empty:
        return base_df
    if base_df.empty:
        return custom_df
    all_cols = sorted(set(base_df.columns).union(set(custom_df.columns)))
    merged = pd.concat(
        [base_df.reindex(columns=all_cols), custom_df.reindex(columns=all_cols)],
        ignore_index=True,
    )
    if "start_time_utc" in merged.columns:
        merged["start_time_utc"] = pd.to_datetime(merged["start_time_utc"], utc=True, errors="coerce")
    return merged


def _curve_points_cache_key(points: list[tuple[datetime, float]] | None) -> tuple[tuple[str, float], ...]:
    out: list[tuple[str, float]] = []
    for ts, val in (points or []):
        ts_norm = pd.to_datetime(ts, utc=True, errors="coerce")
        ts_key = ts_norm.isoformat() if pd.notna(ts_norm) else str(ts)
        try:
            v_key = float(val)
        except Exception:
            v_key = 0.0
        out.append((ts_key, v_key))
    return tuple(out)


def _get_metrics_df_local_cached(
    db_path: Path,
    activities_cache_key: str,
    activity_splits_cache_key: str,
    lthr_bpm: float,
    lthr_curve_points: list[tuple[datetime, float]] | None,
    threshold_pace_default_sec: float,
    threshold_pace_curve_points: list[tuple[datetime, float]] | None,
    use_split_method: bool,
    if_zone_thresholds_key: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    cache_key = (
        int(METRICS_LOCAL_CACHE_VERSION),
        int(METRICS_DERIVATION_CACHE_VERSION),
        str(db_path),
        str(activities_cache_key),
        str(activity_splits_cache_key),
        float(lthr_bpm),
        _curve_points_cache_key(lthr_curve_points),
        float(threshold_pace_default_sec),
        _curve_points_cache_key(threshold_pace_curve_points),
        bool(use_split_method),
        tuple(if_zone_thresholds_key or ()),
    )
    if st.session_state.get("_metrics_df_local_cache_key") == cache_key and isinstance(
        st.session_state.get("_metrics_df_local_cache_value"), pd.DataFrame
    ):
        return st.session_state["_metrics_df_local_cache_value"]
    df = get_metrics_df_fast(
        db_path=db_path,
        activities_cache_key=activities_cache_key,
        activity_splits_cache_key=activity_splits_cache_key,
        lthr_bpm=lthr_bpm,
        lthr_curve_points=lthr_curve_points,
        threshold_pace_default_sec=threshold_pace_default_sec,
        threshold_pace_curve_points=threshold_pace_curve_points,
        use_split_method=use_split_method,
        if_zone_thresholds_key=if_zone_thresholds_key,
        metrics_derivation_cache_version=int(METRICS_DERIVATION_CACHE_VERSION),
    )
    st.session_state["_metrics_df_local_cache_key"] = cache_key
    st.session_state["_metrics_df_local_cache_value"] = df
    return df


def _get_custom_metrics_df_local_cached(
    db_path: Path,
    custom_activities_cache_key: str,
    lthr_bpm: float,
    lthr_curve_points: list[tuple[datetime, float]] | None,
    threshold_pace_default_sec: float,
    threshold_pace_curve_points: list[tuple[datetime, float]] | None,
    if_zone_thresholds_key: tuple[float, float, float, float] | None = None,
) -> pd.DataFrame:
    cache_key = (
        str(db_path),
        str(custom_activities_cache_key),
        float(lthr_bpm),
        _curve_points_cache_key(lthr_curve_points),
        float(threshold_pace_default_sec),
        _curve_points_cache_key(threshold_pace_curve_points),
        tuple(if_zone_thresholds_key or ()),
    )
    if st.session_state.get("_custom_metrics_df_local_cache_key") == cache_key and isinstance(
        st.session_state.get("_custom_metrics_df_local_cache_value"), pd.DataFrame
    ):
        return st.session_state["_custom_metrics_df_local_cache_value"]
    df = _build_custom_metrics_df_for_plots(
        db_path=db_path,
        custom_activities_cache_key=custom_activities_cache_key,
        lthr_bpm=lthr_bpm,
        lthr_curve_points=lthr_curve_points,
        threshold_pace_default_sec=threshold_pace_default_sec,
        threshold_pace_curve_points=threshold_pace_curve_points,
        if_zone_thresholds_key=if_zone_thresholds_key,
    )
    st.session_state["_custom_metrics_df_local_cache_key"] = cache_key
    st.session_state["_custom_metrics_df_local_cache_value"] = df
    return df


def _build_split_metrics_for_activity(
    activity_row: pd.Series,
    split_row: dict | None,
    lthr: float,
    threshold_pace_default_sec: float,
) -> pd.DataFrame:
    if not split_row:
        return pd.DataFrame()
    try:
        split_payload = json.loads(split_row.get("split_json") or "{}")
    except Exception:
        split_payload = {}
    laps = split_payload.get("lapDTOs") if isinstance(split_payload, dict) else None
    if not isinstance(laps, list) or not laps:
        return pd.DataFrame()

    def _num(d: dict, keys: list[str]) -> float | None:
        for k in keys:
            if k not in d:
                continue
            try:
                v = float(d.get(k))
                if pd.notna(v):
                    return v
            except Exception:
                continue
        return None

    sport = str(activity_row.get("sport_type") or "").lower()
    is_running = ("run" in sport) or ("treadmill" in sport)

    tp_sec = float(threshold_pace_default_sec)

    avg_hr_activity = pd.to_numeric(pd.Series([activity_row.get("avg_hr")]), errors="coerce").iloc[0]
    avg_hr_activity = float(avg_hr_activity) if pd.notna(avg_hr_activity) else None

    rows: list[dict[str, float | int | str | None]] = []
    raw_tss_sum = 0.0
    raw_rtss_sum = 0.0
    for i, lap in enumerate(laps, start=1):
        if not isinstance(lap, dict):
            continue
        dur_raw = _num(lap, ["duration", "movingDuration", "elapsedDuration", "lapDuration", "totalDuration"])
        dist_m = _num(lap, ["distance", "totalDistance", "sumDistance", "distanceInMeters", "distanceMeters"])
        if dur_raw is None or dur_raw <= 0:
            continue
        # Match Strava-like lap timing display/computation: whole seconds.
        dur_s = float(int(dur_raw))
        if dur_s <= 0:
            continue
        # Garmin sometimes emits tiny transition laps without intensity marker.
        # Drop these to keep split rows aligned with Strava's lap table.
        intensity_type = str(lap.get("intensityType") or "").strip()
        if (not intensity_type) and dur_s <= 2 and (dist_m is None or float(dist_m) <= 10.0):
            continue
        dist_km = (float(dist_m) / 1000.0) if (dist_m is not None and dist_m > 0) else 0.0
        pace_s = (float(dur_s) / dist_km) if dist_km > 0 else None
        avg_hr_lap = _num(lap, ["averageHR", "avgHR", "averageHeartRate", "meanHeartRate", "avgHeartRate"])
        hr_for_tss = avg_hr_lap if avg_hr_lap is not None else avg_hr_activity

        tss_lap = 0.0
        if hr_for_tss is not None and 0 < float(hr_for_tss) <= 260 and lthr > 0:
            tss_lap = (float(dur_s) * ((float(hr_for_tss) / float(lthr)) ** 2) / 3600.0) * 100.0
        rtss_lap = 0.0
        if is_running and pace_s is not None and pace_s > 0 and tp_sec > 0:
            rtss_lap = (float(dur_s) * ((float(tp_sec) / float(pace_s)) ** 2) / 3600.0) * 100.0

        raw_tss_sum += tss_lap
        raw_rtss_sum += rtss_lap
        rows.append(
            {
                "split_idx": int(lap.get("lapIndex") or i),
                "intensity_type": intensity_type,
                "duration_s": float(dur_s),
                "distance_km": float(dist_km),
                "distance_eqv_km": float(dist_km) if is_running else 0.0,
                "avg_hr": float(avg_hr_lap) if avg_hr_lap is not None else None,
                "pace_s_per_km": float(pace_s) if pace_s is not None else None,
                "pace_eqv_s_per_km": float(pace_s) if is_running and pace_s is not None else None,
                "intensity_factor": (float(tp_sec) / float(pace_s)) if (is_running and pace_s is not None and pace_s > 0 and tp_sec > 0) else None,
                "tss": float(tss_lap),
                "rtss": float(rtss_lap),
            }
        )

    out = pd.DataFrame(rows).sort_values("split_idx").reset_index(drop=True)
    if out.empty:
        return out
    out["split_idx"] = np.arange(1, len(out) + 1)

    # Keep lap totals coherent with the activity-level values shown in the calendar.
    act_tss = float(pd.to_numeric(pd.Series([activity_row.get("tss")]), errors="coerce").fillna(0.0).iloc[0])
    act_rtss = float(pd.to_numeric(pd.Series([activity_row.get("rtss")]), errors="coerce").fillna(0.0).iloc[0])
    if raw_tss_sum > 0 and act_tss >= 0:
        out["tss"] = pd.to_numeric(out["tss"], errors="coerce").fillna(0.0) * (act_tss / raw_tss_sum)
    if raw_rtss_sum > 0 and act_rtss >= 0:
        out["rtss"] = pd.to_numeric(out["rtss"], errors="coerce").fillna(0.0) * (act_rtss / raw_rtss_sum)

    if is_running:
        out["distance_eqv_km"] = pd.to_numeric(out.get("distance_km"), errors="coerce").fillna(0.0)
        out["pace_eqv_s_per_km"] = pd.to_numeric(out.get("pace_s_per_km"), errors="coerce")
        pace_eqv = pd.to_numeric(out.get("pace_eqv_s_per_km"), errors="coerce")
        out["intensity_factor"] = pd.NA
        running_valid_if = (pace_eqv > 0) & (float(tp_sec) > 0)
        out.loc[running_valid_if, "intensity_factor"] = float(tp_sec) / pace_eqv[running_valid_if]
    else:
        # Non-running laps: derive running-equivalent pace/distance from split TSS parity and fixed threshold pace.
        dur = pd.to_numeric(out.get("duration_s"), errors="coerce").fillna(0.0)
        tss = pd.to_numeric(out.get("tss"), errors="coerce").fillna(0.0)
        valid = (dur > 0) & (tss > 0) & (float(tp_sec) > 0)
        out["pace_eqv_s_per_km"] = pd.NA
        out["distance_eqv_km"] = 0.0
        out["intensity_factor"] = pd.NA
        if valid.any():
            if_equiv = ((tss[valid] * 3600.0) / (dur[valid] * 100.0)) ** 0.5
            pace_eqv = float(tp_sec) / if_equiv
            out.loc[valid, "pace_eqv_s_per_km"] = pace_eqv
            out.loc[valid, "distance_eqv_km"] = dur[valid] / pace_eqv
            out.loc[valid, "intensity_factor"] = if_equiv
    return out


def cached_filtered_views(
    metrics_df: pd.DataFrame,
    activity_filter: str,
    specificity_profile: dict[str, float],
    daily_tss_target: float = 70.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered_metrics = filter_by_activity_type(metrics_df, activity_filter)
    filtered_metrics = apply_specificity_factor(filtered_metrics, specificity_profile)
    filtered_daily = build_daily_summary(filtered_metrics)
    if not filtered_daily.empty:
        filtered_daily = filtered_daily.sort_values("day_utc").copy()
        daily_index = pd.date_range(
            start=pd.to_datetime(filtered_daily["day_utc"]).min(),
            end=pd.to_datetime(filtered_daily["day_utc"]).max(),
            freq="D",
        )
        complete_daily = pd.DataFrame({"day_utc": daily_index.strftime("%Y-%m-%d")})
        filtered_daily = complete_daily.merge(filtered_daily, on="day_utc", how="left")
        # Fitness/Fatigue are always computed on continuous daily data with missing days as zero load.
        # Overreach should remain on the same stress model as TSS targeting:
        # use TSS only (no Garmin-load fallback) and subtract LT-derived daily target.
        training_series = (
            pd.to_numeric(filtered_daily.get("tss_total"), errors="coerce").fillna(0.0)
            if "tss_total" in filtered_daily.columns
            else pd.Series([0.0] * len(filtered_daily), index=filtered_daily.index, dtype=float)
        )
        daily_target = float(max(daily_tss_target, 0.0))
        training_ema = ema_multi(training_series, [42, 7, 10])
        filtered_daily["fitness"] = training_ema[42]
        filtered_daily["fatigue"] = training_ema[7]
        filtered_daily["overreach"] = (training_ema[10] - daily_target).clip(lower=0.0)
        rtss_series = (
            pd.to_numeric(filtered_daily["rtss_total"], errors="coerce").fillna(0.0)
            if "rtss_total" in filtered_daily.columns
            else pd.Series([0.0] * len(filtered_daily), index=filtered_daily.index)
        )
        # If rTSS is unavailable/flat-zero for the selected data (common in non-running-heavy blocks),
        # fallback to TSS so Injury Risk charts remain informative instead of appearing broken.
        if float(rtss_series.abs().sum()) <= 1e-9:
            rtss_series = pd.to_numeric(filtered_daily.get("tss_total"), errors="coerce").fillna(0.0)
        rtss_ema = ema_multi(rtss_series, [100, 7, 10])
        filtered_daily["leg_elasticity"] = rtss_ema[100]
        filtered_daily["pounding"] = rtss_ema[7]
        filtered_daily["injury_risk"] = (rtss_ema[10] - daily_target).clip(lower=0.0)
    return filtered_metrics, filtered_daily


def build_injury_layer(
    injury_windows: list[dict[str, str]],
    start_day: pd.Timestamp | None = None,
    end_day: pd.Timestamp | None = None,
) -> alt.Chart:
    injuries = pd.DataFrame(injury_windows).copy()
    injuries["start"] = pd.to_datetime(injuries["start"])
    injuries["severity"] = injuries.get("severity", "injury").fillna("injury")
    # Inclusive end-date visual window.
    injuries["end_exclusive"] = pd.to_datetime(injuries["end"]) + pd.Timedelta(days=1)
    if start_day is not None and end_day is not None:
        start_ts = pd.Timestamp(start_day)
        end_exclusive = pd.Timestamp(end_day) + pd.Timedelta(days=1)
        injuries = injuries[(injuries["end_exclusive"] > start_ts) & (injuries["start"] < end_exclusive)].copy()
        injuries["start"] = injuries["start"].clip(lower=start_ts)
        injuries["end_exclusive"] = injuries["end_exclusive"].clip(upper=end_exclusive)
    red = injuries[injuries["severity"] == "injury"].copy()
    yellow = injuries[injuries["severity"] == "light_injury"].copy()

    red_layer = (
        alt.Chart(red)
        .mark_rect(color="#ef4444", opacity=0.12)
        .encode(
            x="start:T",
            x2="end_exclusive:T",
            tooltip=["label:N", "severity:N", "start:T", "end:T"],
        )
    )
    yellow_layer = (
        alt.Chart(yellow)
        .mark_rect(color="#facc15", opacity=0.12)
        .encode(
            x="start:T",
            x2="end_exclusive:T",
            tooltip=["label:N", "severity:N", "start:T", "end:T"],
        )
    )
    return alt.layer(red_layer, yellow_layer)


def build_recovery_daily_frame(sleep_df: pd.DataFrame, wellness_df: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    if not sleep_df.empty:
        s = sleep_df.copy()
        s["day"] = pd.to_datetime(s["day_utc"], errors="coerce")
        s["sleep_duration_h"] = s["sleep_duration_s"] / 3600.0
        s["deep_sleep_h"] = s["deep_sleep_s"] / 3600.0
        s["rem_sleep_h"] = s["rem_sleep_s"] / 3600.0
        parts.append(
            s[
                [
                    "day",
                    "sleep_score",
                    "sleep_duration_h",
                    "deep_sleep_h",
                    "rem_sleep_h",
                ]
            ]
        )
    if not wellness_df.empty:
        w = wellness_df.copy()
        w["day"] = pd.to_datetime(w["day_utc"], errors="coerce")
        parts.append(
            w[
                [
                    "day",
                    "hrv_status",
                    "stress_avg",
                    "training_readiness",
                    "respiration_avg",
                    "resting_hr",
                ]
            ]
        )
    if not parts:
        return pd.DataFrame()

    merged = parts[0]
    for p in parts[1:]:
        merged = merged.merge(p, on="day", how="outer")
    return merged.sort_values("day")

auth_on = _auth_enabled()
users = _auth_users()
if "auth_user" not in st.session_state:
    st.session_state["auth_user"] = None
if "auth_role" not in st.session_state:
    st.session_state["auth_role"] = None

if auth_on and not users:
    st.error("Auth enabled but no credentials configured. Set TEMPERANCE_ADMIN_PASSWORD.")
    st.stop()

if auth_on and not st.session_state.get("auth_user"):
    _restore_auth_from_cookie(users)

if auth_on and not st.session_state.get("auth_user"):
    st.markdown(
        """
        <style>
        .auth-login-title {
            font-size: 1.35rem;
            font-weight: 700;
            line-height: 1.2;
            margin-bottom: 2px;
        }
        .auth-login-subtitle {
            color: rgba(148,163,184,0.95);
            font-size: 0.88rem;
            margin-bottom: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    login_error = None
    login_user_default = str(st.session_state.get("login_user_main") or "")
    lock_remaining = _login_lock_remaining_s(_login_guard_key(login_user_default))
    left_col, center_col, right_col = st.columns([1.45, 1.1, 1.45])
    with center_col:
        with st.container(border=True):
            st.markdown("<div class='auth-login-title'>Sign in</div>", unsafe_allow_html=True)
            st.markdown("<div class='auth-login-subtitle'>Access your Temperance dashboard</div>", unsafe_allow_html=True)
            with st.form("main_login_form", clear_on_submit=False):
                login_user = st.text_input("User", key="login_user_main")
                login_pass = st.text_input("Password", type="password", key="login_pass_main")
                lock_remaining = _login_lock_remaining_s(_login_guard_key(login_user))
                login_submit = st.form_submit_button(
                    "Sign in",
                    use_container_width=True,
                    disabled=lock_remaining > 0,
                )
                if login_submit:
                    guard_key = _login_guard_key(login_user)
                    current_remaining = _login_lock_remaining_s(guard_key)
                    if current_remaining > 0:
                        login_error = f"Too many attempts. Try again in {current_remaining}s."
                    elif len(str(login_user or "").strip()) > int(LOGIN_MAX_USER_LEN) or len(str(login_pass or "")) > int(
                        LOGIN_MAX_PASSWORD_LEN
                    ):
                        lock_s = _register_login_failure(guard_key)
                        if lock_s > 0:
                            login_error = f"Invalid credentials. Try again in {lock_s}s."
                        else:
                            login_error = "Invalid credentials."
                    else:
                        resolved_user, user_data = resolve_user(users, login_user)
                        if user_data and password_matches(login_pass, user_data["password_hash"]):
                            st.session_state["auth_user"] = resolved_user
                            st.session_state["auth_role"] = user_data["role"]
                            _auth_cookie_set(resolved_user, str(user_data["role"]), ttl_s=SESSION_TTL_S)
                            _clear_login_guard(guard_key)
                            login_error = None
                        lock_s = _register_login_failure(guard_key)
                        if lock_s > 0:
                            login_error = f"Invalid credentials. Try again in {lock_s}s."
                        else:
                            login_error = "Invalid credentials."
    if not st.session_state.get("auth_user"):
        if login_error:
            st.error(login_error)
        elif lock_remaining > 0:
            st.warning(f"Too many attempts. Try again in {lock_remaining}s.")
        st.stop()

with st.sidebar:
    st.header("Navigation")

    if auth_on:
        st.caption(f"Signed in as `{st.session_state.get('auth_user')}` ({st.session_state.get('auth_role')})")
        if st.button("Logout", key="logout_btn"):
            st.session_state["auth_user"] = None
            st.session_state["auth_role"] = None
            _auth_cookie_clear()
            st.rerun()

    if "garmin_email_input" not in st.session_state:
        st.session_state["garmin_email_input"] = ""
    if "garmin_password_input" not in st.session_state:
        st.session_state["garmin_password_input"] = ""

    with st.expander("Garmin API Credentials", expanded=False):
        if _auth_enabled() and str(st.session_state.get("auth_role") or "") != "admin":
            st.caption("Credentials are in-memory only for this session.")
        else:
            st.caption("Used for Garmin sync/extract. Stored in current session only.")
        st.text_input("Garmin Email", key="garmin_email_input")
        st.text_input("Garmin Password", type="password", key="garmin_password_input")
        st.button(
            "Clear Garmin session credentials",
            key="clear_garmin_creds",
            on_click=_clear_garmin_session_credentials,
        )

    role = str(st.session_state.get("auth_role") or "admin")
    auth_user = str(st.session_state.get("auth_user") or "default")
    if (
        "data_owner" not in st.session_state
        or st.session_state.get("_data_owner_auth_user") != auth_user
    ):
        st.session_state["data_owner"] = auth_user
        st.session_state["_data_owner_auth_user"] = auth_user

    if auth_on and role == "admin":
        owner_options = sorted(users.keys()) if users else [auth_user]
        default_owner = st.session_state.get("data_owner") or auth_user
        if default_owner not in owner_options:
            default_owner = owner_options[0]
        data_owner = st.selectbox(
            "Data owner",
            options=owner_options,
            index=owner_options.index(default_owner),
            help="Select which user's local dataset you want to load.",
        )
    elif auth_on:
        data_owner = auth_user
    else:
        data_owner = "default"
    st.session_state["data_owner"] = data_owner

    allowed_tabs = AUTH_ALL_TABS if (not auth_on or role == "admin") else AUTH_VIEWER_TABS
    preferred_order = ["Weekly Summary", "Activity Summary", "Dashboard", "Model Metrics"]
    ordered_tabs = [v for v in preferred_order if v in allowed_tabs] + [
        v for v in allowed_tabs if v not in preferred_order
    ]
    page_labels = {
        "Weekly Summary": "Week Outlook",
        "Activity Summary": "Activity Dashboard",
        "Custom Activities": "Custom Activities",
        "Dashboard": "Analytics Plots",
        "Model Metrics": "Model Metrics",
        "Activity Detail": "Activity Detail",
        "Recovery Data": "Recovery Data",
        "Data Extract": "Data Extract",
        "User Inputs": "User Inputs",
    }
    label_to_view = {page_labels.get(v, v): v for v in ordered_tabs}
    default_view = "Weekly Summary" if "Weekly Summary" in ordered_tabs else ordered_tabs[0]
    default_idx = ordered_tabs.index(default_view)
    selected_label = st.radio(
        "Page",
        list(label_to_view.keys()),
        index=default_idx,
    )
    view = label_to_view[selected_label]
    use_split_method = st.checkbox("Use splits for metrics", value=False)
    st.caption(f"Active data owner: `{data_owner}`")

if view not in allowed_tabs:
    st.error("You do not have access to this page.")
    st.stop()

active_owner = str(st.session_state.get("data_owner") or "default")
owner_scoped_keys = [
    "calendar_compact_week_start",
    "calendar_compact_compare_choice",
    "calendar_compact_metric",
    "calendar_quick_range",
    "calendar_split_activity_id",
    "calendar_split_open",
    "calendar_activity_weeks_visible",
    "planned_mark_done_pending",
    "_metrics_df_local_cache_key",
    "_metrics_df_local_cache_value",
    "_custom_metrics_df_local_cache_key",
    "_custom_metrics_df_local_cache_value",
    "_planned_metrics_df_local_cache_key",
    "_planned_metrics_df_local_cache_value",
    "_weekly_planned_metrics_cache_key",
    "_weekly_planned_metrics_cache_value",
    "dashboard_metric_select",
    "dashboard_ema_windows",
    "dashboard_compare_mode",
    "dashboard_top_injury_overlay",
]
owner_session_needs_reset = False
if "_active_data_owner" not in st.session_state:
    owner_session_needs_reset = True
elif str(st.session_state.get("_active_data_owner") or "") != active_owner:
    owner_session_needs_reset = True
if int(pd.to_numeric(st.session_state.get("_owner_scoped_state_reset_version", 0), errors="coerce") or 0) < int(
    OWNER_SCOPED_STATE_RESET_VERSION
):
    owner_session_needs_reset = True
if owner_session_needs_reset:
    st.session_state["_active_data_owner"] = active_owner
    st.session_state["_owner_scoped_state_reset_version"] = int(OWNER_SCOPED_STATE_RESET_VERSION)
    for key in owner_scoped_keys:
        st.session_state.pop(key, None)
    st.rerun()

previous_view = st.session_state.get("_previous_view")
st.session_state["_previous_view"] = view

cfg = _scoped_config_for_owner(st.session_state.get("data_owner") or "default")
init_db(cfg.db_path)
cfg.import_dir.mkdir(parents=True, exist_ok=True)
cfg.private_export_dir.mkdir(parents=True, exist_ok=True)

saved_injury_windows = _load_injury_windows(cfg.db_path)
saved_lthr_curve = _load_lthr_curve(cfg.db_path)
saved_lt_pace_curve = _load_lt_pace_curve(cfg.db_path)
saved_if_zone_thresholds = _load_if_zone_thresholds(cfg.db_path)
saved_non_running_factor = _load_non_running_factor(cfg.db_path, default_value=0.8)
saved_specificity_profile = _load_specificity_profile(cfg.db_path, fallback_default=saved_non_running_factor)
if "user_specificity_profile" not in st.session_state:
    st.session_state["user_specificity_profile"] = dict(saved_specificity_profile)
if "user_non_running_factor" not in st.session_state:
    st.session_state["user_non_running_factor"] = float(
        st.session_state["user_specificity_profile"].get("non_running", saved_non_running_factor)
    )
if "user_if_zone_thresholds" not in st.session_state:
    st.session_state["user_if_zone_thresholds"] = dict(saved_if_zone_thresholds)
active_if_zone_thresholds = _normalize_if_zone_thresholds(
    st.session_state.get("user_if_zone_thresholds")
)
active_if_zone_thresholds_key = _if_zone_thresholds_tuple(active_if_zone_thresholds)
derived_lthr_bpm = _curve_latest_value(saved_lthr_curve, "lthr_bpm", DEFAULT_LTHR)
derived_threshold_pace_sec = _curve_latest_value(
    saved_lt_pace_curve, "lt_pace_sec_per_km", DEFAULT_THRESHOLD_PACE_SEC_PER_KM
)
derived_weekly_distance_target = _weekly_distance_target_from_lt_pace(float(derived_threshold_pace_sec))
derived_daily_distance_target = derived_weekly_distance_target / 7.0
derived_weekly_tss_target = _weekly_tss_target_from_lt_pace(float(derived_threshold_pace_sec))
derived_daily_tss_target = derived_weekly_tss_target / 7.0
lthr_curve_points = _curve_points_from_rows(saved_lthr_curve, "lthr_bpm")
lt_pace_curve_points = _curve_points_from_rows(saved_lt_pace_curve, "lt_pace_sec_per_km")

if view == "User Inputs":
    st.header("User Inputs")
    st.markdown("##### IF Zones")
    z1_current = float(active_if_zone_thresholds["z1_max"])
    z2_current = float(active_if_zone_thresholds["z2_max"])
    z3_current = float(active_if_zone_thresholds["z3_max"])
    z4_current = float(active_if_zone_thresholds["z4_max"])
    st.caption(
        f"Using latest values as of {datetime.now().date().isoformat()} "
        f"(LTHR {float(derived_lthr_bpm):.0f} bpm, LT pace {_pace_compact(float(derived_threshold_pace_sec))}). "
        f"Current thresholds: Z1 <{z1_current * 100.0:.0f}%, "
        f"Z2 <{z2_current * 100.0:.0f}%, "
        f"Z3 <{z3_current * 100.0:.0f}%, "
        f"Z4 <{z4_current * 100.0:.0f}%, "
        f"Z5 >={z4_current * 100.0:.0f}%."
    )
    st.dataframe(
        _if_zone_guidance_df(
            float(derived_lthr_bpm),
            float(derived_threshold_pace_sec),
            thresholds=active_if_zone_thresholds,
        ),
        use_container_width=True,
        hide_index=True,
    )
    with st.expander("Edit IF Zone Thresholds", expanded=True):
        st.caption("Set upper bounds for Z1-Z4 in IF percent. Z5 is automatically >= Z4.")
        zone_editor_nonce = int(pd.to_numeric(st.session_state.get("if_zone_editor_nonce", 0), errors="coerce") or 0)
        zc1, zc2 = st.columns(2)
        with zc1:
            z1_pct = st.number_input(
                "Z1 max IF (%)",
                min_value=1.0,
                max_value=300.0,
                value=float(z1_current * 100.0),
                step=1.0,
                format="%.0f",
                key=f"if_zone_z1_pct_{zone_editor_nonce}",
            )
            z2_pct = st.number_input(
                "Z2 max IF (%)",
                min_value=1.0,
                max_value=300.0,
                value=float(z2_current * 100.0),
                step=1.0,
                format="%.0f",
                key=f"if_zone_z2_pct_{zone_editor_nonce}",
            )
        with zc2:
            z3_pct = st.number_input(
                "Z3 max IF (%)",
                min_value=1.0,
                max_value=300.0,
                value=float(z3_current * 100.0),
                step=1.0,
                format="%.0f",
                key=f"if_zone_z3_pct_{zone_editor_nonce}",
            )
            z4_pct = st.number_input(
                "Z4 max IF (%)",
                min_value=1.0,
                max_value=300.0,
                value=float(z4_current * 100.0),
                step=1.0,
                format="%.0f",
                key=f"if_zone_z4_pct_{zone_editor_nonce}",
            )
        save_col, reset_col = st.columns([1, 1])
        with save_col:
            if st.button("Save IF Zones", key="save_if_zone_thresholds_btn", use_container_width=True):
                new_thresholds = _normalize_if_zone_thresholds(
                    {
                        "z1_max": float(z1_pct) / 100.0,
                        "z2_max": float(z2_pct) / 100.0,
                        "z3_max": float(z3_pct) / 100.0,
                        "z4_max": float(z4_pct) / 100.0,
                    }
                )
                changed = save_setting_if_changed(
                    cfg.db_path,
                    SETTINGS_KEY_IF_ZONE_THRESHOLDS,
                    _settings_json(new_thresholds),
                )
                st.session_state["user_if_zone_thresholds"] = dict(new_thresholds)
                st.session_state["if_zone_editor_nonce"] = zone_editor_nonce + 1
                st.success("IF zones saved." if changed else "IF zones unchanged.")
                st.rerun()
        with reset_col:
            if st.button("Reset IF Zones Defaults", key="reset_if_zone_thresholds_btn", use_container_width=True):
                defaults = _default_if_zone_thresholds()
                changed = save_setting_if_changed(
                    cfg.db_path,
                    SETTINGS_KEY_IF_ZONE_THRESHOLDS,
                    _settings_json(defaults),
                )
                st.session_state["user_if_zone_thresholds"] = dict(defaults)
                st.session_state["if_zone_editor_nonce"] = zone_editor_nonce + 1
                st.success("IF zones reset to defaults." if changed else "IF zones already at defaults.")
                st.rerun()
    with st.expander("Specificity Factors", expanded=True):
        st.caption("Set base non-running factor plus activity-specific overrides.")
        profile_current = _normalize_specificity_profile(
            st.session_state.get("user_specificity_profile", {}),
            fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
        )
        f1, f2 = st.columns(2)
        with f1:
            f_non_running = st.number_input(
                "Non-running (base)",
                min_value=0.0,
                max_value=1.5,
                value=float(profile_current.get("non_running", 0.8)),
                step=0.01,
                format="%.2f",
                key="ui_spec_non_running",
            )
            f_treadmill = st.number_input(
                "Treadmill",
                min_value=0.0,
                max_value=1.5,
                value=float(profile_current.get("treadmill", 1.0)),
                step=0.01,
                format="%.2f",
                key="ui_spec_treadmill",
            )
        with f2:
            f_elliptical = st.number_input(
                "Elliptical",
                min_value=0.0,
                max_value=1.5,
                value=float(profile_current.get("elliptical", profile_current.get("non_running", 0.8))),
                step=0.01,
                format="%.2f",
                key="ui_spec_elliptical",
            )
            f_cycling = st.number_input(
                "Cycling",
                min_value=0.0,
                max_value=1.5,
                value=float(profile_current.get("cycling", profile_current.get("non_running", 0.8))),
                step=0.01,
                format="%.2f",
                key="ui_spec_cycling",
            )
        if st.button("Save Specificity Factors", key="save_specificity_factors_btn"):
            new_profile = _normalize_specificity_profile(
                {
                    "non_running": f_non_running,
                    "treadmill": f_treadmill,
                    "elliptical": f_elliptical,
                    "cycling": f_cycling,
                },
                fallback_default=f_non_running,
            )
            changed_profile = save_setting_if_changed(
                cfg.db_path, SETTINGS_KEY_ACTIVITY_SPECIFICITY, _settings_json(new_profile)
            )
            changed_default = save_setting_if_changed(
                cfg.db_path, SETTINGS_KEY_NON_RUNNING_FACTOR, f"{float(new_profile['non_running']):.4f}"
            )
            st.session_state["user_specificity_profile"] = dict(new_profile)
            st.session_state["user_non_running_factor"] = float(new_profile["non_running"])
            st.success(
                "Specificity factors saved."
                if (changed_profile or changed_default)
                else "Specificity factors unchanged."
            )
            st.rerun()
    with st.expander("LTHR Curve (date -> bpm)", expanded=True):
        lthr_df = pd.DataFrame(saved_lthr_curve)[["date", "lthr_bpm"]]
        edited_lthr = st.data_editor(
            lthr_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
                "lthr_bpm": st.column_config.NumberColumn("LTHR (bpm)", format="%.1f"),
            },
            key="lthr_curve_editor",
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Save LTHR Curve", key="save_lthr_curve_btn"):
                normalized = _normalize_lthr_curve(edited_lthr.fillna("").to_dict(orient="records"))
                changed = save_setting_if_changed(
                    cfg.db_path, SETTINGS_KEY_LTHR_CURVE, _settings_json(normalized)
                )
                st.success("LTHR curve saved." if changed else "LTHR curve unchanged.")
                st.rerun()
        with c2:
            if st.button("Reset LTHR Curve", key="reset_lthr_curve_btn"):
                defaults = _default_lthr_curve()
                changed = save_setting_if_changed(
                    cfg.db_path, SETTINGS_KEY_LTHR_CURVE, _settings_json(defaults)
                )
                st.success("LTHR curve reset." if changed else "LTHR curve unchanged.")
                st.rerun()

    with st.expander("LT Pace Curve (date -> mm:ss /km)", expanded=True):
        pace_df = pd.DataFrame(saved_lt_pace_curve)[["date", "lt_pace_sec_per_km"]].copy()
        pace_df["lt_pace"] = pace_df["lt_pace_sec_per_km"].apply(_pace_text_or_blank)
        pace_df = pace_df[["date", "lt_pace"]]
        edited_pace = st.data_editor(
            pace_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
                "lt_pace": st.column_config.TextColumn("LT Pace (mm:ss)"),
            },
            key="lt_pace_curve_editor",
        )
        c3, c4 = st.columns([1, 1])
        with c3:
            if st.button("Save LT Pace Curve", key="save_lt_pace_curve_btn"):
                rows = edited_pace.fillna("").to_dict(orient="records")
                normalized = _normalize_lt_pace_curve(rows)
                changed = save_setting_if_changed(
                    cfg.db_path, SETTINGS_KEY_LT_PACE_CURVE, _settings_json(normalized)
                )
                st.success("LT pace curve saved." if changed else "LT pace curve unchanged.")
                st.rerun()
        with c4:
            if st.button("Reset LT Pace Curve", key="reset_lt_pace_curve_btn"):
                defaults = _default_lt_pace_curve()
                changed = save_setting_if_changed(
                    cfg.db_path, SETTINGS_KEY_LT_PACE_CURVE, _settings_json(defaults)
                )
                st.success("LT pace curve reset." if changed else "LT pace curve unchanged.")
                st.rerun()
    with st.expander("Injury Overlays", expanded=False):
        st.caption("Edit injury windows used for chart shading.")
        editor_df = pd.DataFrame(saved_injury_windows)
        if editor_df.empty:
            editor_df = pd.DataFrame(columns=["label", "start", "end", "severity"])
        edited = st.data_editor(
            editor_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "label": st.column_config.TextColumn("Label"),
                "start": st.column_config.TextColumn("Start (YYYY-MM-DD)"),
                "end": st.column_config.TextColumn("End (YYYY-MM-DD)"),
                "severity": st.column_config.SelectboxColumn(
                    "Severity", options=["injury", "light_injury"]
                ),
            },
            key="injury_windows_editor",
        )
        if st.button("Save Injury Overlays", key="save_injury_windows_btn"):
            try:
                rows = edited.fillna("").to_dict(orient="records")
                normalized = _normalize_injury_windows(rows)
                payload = _settings_json(normalized)
                changed = save_setting_if_changed(cfg.db_path, SETTINGS_KEY_INJURY_WINDOWS, payload)
                st.success("Injury overlays saved." if changed else "Injury overlays unchanged.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save injury overlays: {exc}")

activities_cache_key = get_activities_cache_key(cfg.db_path)
activity_splits_cache_key = get_activity_splits_cache_key(cfg.db_path)
custom_activities_cache_key = get_custom_activities_cache_key(cfg.db_path)
planned_activities_cache_key = get_planned_activities_cache_key(cfg.db_path)
metrics_df = _get_metrics_df_local_cached(
    db_path=cfg.db_path,
    activities_cache_key=activities_cache_key,
    activity_splits_cache_key=activity_splits_cache_key,
    lthr_bpm=float(derived_lthr_bpm),
    lthr_curve_points=lthr_curve_points,
    threshold_pace_default_sec=float(derived_threshold_pace_sec),
    threshold_pace_curve_points=lt_pace_curve_points,
    use_split_method=bool(use_split_method),
    if_zone_thresholds_key=active_if_zone_thresholds_key,
)
daily_summary_df = get_daily_summary_df(cfg.db_path)

if view in {"Dashboard", "Model Metrics"}:
    st.header("Analytics Plots" if view == "Dashboard" else "Model Metrics")
    custom_metrics_df = _get_custom_metrics_df_local_cached(
        db_path=cfg.db_path,
        custom_activities_cache_key=custom_activities_cache_key,
        lthr_bpm=float(derived_lthr_bpm),
        lthr_curve_points=lthr_curve_points,
        threshold_pace_default_sec=float(derived_threshold_pace_sec),
        threshold_pace_curve_points=lt_pace_curve_points,
        if_zone_thresholds_key=active_if_zone_thresholds_key,
    )
    dashboard_metrics_df = _merge_metrics_with_custom(
        metrics_df,
        custom_metrics_df,
    )

    if dashboard_metrics_df.empty:
        st.info(
            "No activities yet. Use Sync above. "
            "For your full archive, run Comprehensive Garmin Extract from Jan 1, 2025."
        )
    else:
        dashboard_block_t0 = perf_counter()
        controls = st.columns([0.85, 0.85, 0.85, 2.45])
        with controls[0]:
            metrics_local_start = _to_local_naive(dashboard_metrics_df["start_time_utc"])
            metrics_min_day = metrics_local_start.min().date()
            metrics_max_day = metrics_local_start.max().date()
            if daily_summary_df.empty:
                min_day = metrics_min_day
                max_day = metrics_max_day
            else:
                daily_min_day = pd.to_datetime(daily_summary_df["day_utc"], errors="coerce").min().date()
                daily_max_day = pd.to_datetime(daily_summary_df["day_utc"], errors="coerce").max().date()
                min_day = min(metrics_min_day, daily_min_day)
                max_day = max(metrics_max_day, daily_max_day)
            quick_range = st.selectbox("Quick range", ["YTD", "3M", "6M", "9M", "1Y", "2Y", "ALL", "Custom"], index=1)
            if quick_range == "YTD":
                q_start = max(min_day, date(max_day.year, 1, 1))
                q_end = max_day
            elif quick_range == "3M":
                q_start = max(min_day, max_day - timedelta(days=90))
                q_end = max_day
            elif quick_range == "6M":
                q_start = max(min_day, max_day - timedelta(days=180))
                q_end = max_day
            elif quick_range == "9M":
                q_start = max(min_day, max_day - timedelta(days=270))
                q_end = max_day
            elif quick_range == "1Y":
                q_start = max(min_day, max_day - timedelta(days=365))
                q_end = max_day
            elif quick_range == "2Y":
                q_start = max(min_day, max_day - timedelta(days=730))
                q_end = max_day
            elif quick_range == "ALL":
                q_start = min_day
                q_end = max_day
            else:
                q_start = min_day
                q_end = max_day
            if quick_range == "Custom":
                date_range = st.date_input("Date range", value=(q_start, q_end), min_value=min_day, max_value=max_day)
            else:
                date_range = (q_start, q_end)
                st.caption(f"Range: {q_start.isoformat()} -> {q_end.isoformat()}")
        with controls[1]:
            activity_filter = st.selectbox(
                "Activity filter",
                ["All Activities", "All Running", "Running", "Treadmill", "Cycling", "Elliptical"],
                index=0,
            )
        with controls[2]:
            weekly_mode = st.selectbox("Aggregation", ["Weekly", "Daily"], index=0, key="dashboard_aggregation_mode")
            weekly_toggle = weekly_mode == "Weekly"
        enable_zoom = False

        run_custom_metric = view == "Model Metrics"
        compare_mode = False
        top_injury_overlay = False
        render_summary = view == "Dashboard"
        render_injury = view == "Dashboard"
        render_fitness = view == "Dashboard"
        render_activities = view == "Dashboard"

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = max_day
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        end_exclusive_ts = end_ts + pd.Timedelta(days=1)

        filtered_metrics, filtered_daily = cached_filtered_views(
            dashboard_metrics_df,
            activity_filter=activity_filter,
            specificity_profile=_normalize_specificity_profile(
                st.session_state.get("user_specificity_profile", {}),
                fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
            ),
            daily_tss_target=float(derived_daily_tss_target),
        )
        filtered_start_local = _to_local_naive(filtered_metrics["start_time_utc"])
        range_filtered_metrics = filtered_metrics[
            (filtered_start_local >= start_ts)
            & (filtered_start_local < end_exclusive_ts)
        ].copy()
        filtered_day_dt = pd.to_datetime(filtered_daily.get("day_utc"), errors="coerce")
        filtered_day_mask = (filtered_day_dt >= start_ts) & (filtered_day_dt < end_exclusive_ts)
        filtered_daily_range = filtered_daily.loc[filtered_day_mask].copy()
        filtered_daily_range["day_dt"] = filtered_day_dt.loc[filtered_day_mask].values
        filtered_daily_range = filtered_daily_range.dropna(subset=["day_dt"]).copy()

        metric_map = {
            "rTSS": ("rtss_total", "sum"),
            "TSS": ("tss_total", "sum"),
            "Distance (km)": ("distance_km", "sum"),
            "Distance Eqv. (km)": ("distance_proxy_km", "sum"),
            "Mechanical Load": ("mechanical_load_total", "sum"),
            "Fatigue (EWMA 7)": ("fatigue", "mean"),
            "Last Fatigue (week-end)": ("fatigue", "last"),
            "Pounding (EWMA 7, rTSS)": ("pounding", "mean"),
            "Garmin Training Load": ("training_load_garmin", "sum"),
            "Calories Active": ("calories_active", "sum"),
            "Calories Total": ("calories_total", "sum"),
            "Vigorous Minutes": ("intensity_minutes_vigorous", "sum"),
            "Moderate Minutes": ("intensity_minutes_moderate", "sum"),
        }
        all_plot_metric_cols = sorted({m for m, _ in metric_map.values()})
        for c in all_plot_metric_cols:
            if c not in filtered_daily_range.columns:
                filtered_daily_range[c] = 0.0
        if run_custom_metric:
            metric_labels = list(metric_map.keys())
            default_metric = "TSS"
            if "dashboard_metric_select" not in st.session_state:
                st.session_state["dashboard_metric_select"] = default_metric
            selected_metric_label = str(st.session_state.get("dashboard_metric_select") or default_metric)
            if selected_metric_label not in metric_labels:
                selected_metric_label = default_metric if default_metric in metric_labels else metric_labels[0]
                st.session_state["dashboard_metric_select"] = selected_metric_label
            if "dashboard_ema_windows" not in st.session_state:
                st.session_state["dashboard_ema_windows"] = "4,16"
            compare_mode = bool(st.session_state.get("dashboard_compare_mode", False))
            top_injury_overlay = bool(st.session_state.get("dashboard_top_injury_overlay", False))

        base_df = filtered_daily_range.copy()
        prep_ms = (perf_counter() - dashboard_block_t0) * 1000.0
        section_render_ms = 0.0
        if base_df.empty:
            st.info(f"No data for activity filter: {activity_filter}")
        else:
            section_render_t0 = perf_counter()
            prepared_base_df = base_df.copy()
            numeric_metric_cols = sorted({m for m, _ in metric_map.values()})
            for col in numeric_metric_cols:
                if col in prepared_base_df.columns:
                    prepared_base_df[col] = pd.to_numeric(prepared_base_df[col], errors="coerce").fillna(0.0)
            prepared_base_df["day"] = pd.to_datetime(prepared_base_df["day_utc"], errors="coerce")
            series_full_index = pd.date_range(start=start_ts, end=end_ts, freq="D")
            if not run_custom_metric:
                compare_mode = False
                top_injury_overlay = False
            if compare_mode:
                left_axis_labels = st.multiselect(
                    "Left axis metrics",
                    list(metric_map.keys()),
                    default=["Mechanical Load"],
                    max_selections=3,
                )
                right_axis_labels = st.multiselect(
                    "Right axis metrics",
                    list(metric_map.keys()),
                    default=["rTSS"],
                    max_selections=3,
                )
            else:
                metric_labels = list(metric_map.keys())
                default_metric = "TSS"
                if "dashboard_metric_select" not in st.session_state:
                    st.session_state["dashboard_metric_select"] = default_metric
                selected_metric_label = str(st.session_state.get("dashboard_metric_select") or default_metric)
                if selected_metric_label not in metric_labels:
                    selected_metric_label = default_metric if default_metric in metric_labels else metric_labels[0]
                    st.session_state["dashboard_metric_select"] = selected_metric_label
                selected_labels = [selected_metric_label]

            ema_ns: list[int] = []
            ema_pairs: list[tuple[int, int]] = []
            if not compare_mode:
                if "dashboard_ema_windows" not in st.session_state:
                    st.session_state["dashboard_ema_windows"] = "4,16"
                ema_windows = str(st.session_state.get("dashboard_ema_windows") or "4,16")
                ema_ns, ema_pairs = parse_ma_windows(ema_windows)

            custom_metric_main_chart = None
            custom_metric_compare_chart = None
            custom_metric_compare_empty = False
            plot_frames: list[pd.DataFrame] = []
            if compare_mode:
                labels_and_axis = [(label, "left") for label in left_axis_labels] + [
                    (label, "right") for label in right_axis_labels
                ]
            else:
                labels_and_axis = [(label, "left") for label in selected_labels]
            if not run_custom_metric:
                labels_and_axis = []

            for label, axis_side in labels_and_axis:
                metric, weekly_agg = metric_map[label]
                frame = prepare_metric_series(
                    daily_df=prepared_base_df,
                    metric=metric,
                    start_day=start_ts,
                    end_day=end_ts,
                    fill_method="zero",
                    weekly=weekly_toggle,
                    weekly_agg=weekly_agg,
                    full_index=series_full_index,
                )
                if frame.empty:
                    continue
                frame[metric] = pd.to_numeric(frame[metric], errors="coerce").fillna(0.0)
                frame = frame.rename(columns={metric: "value"})
                frame["series"] = label
                frame["axis_side"] = axis_side
                plot_frames.append(frame)

                if not compare_mode:
                    overlay_cols: list[str] = []
                    ema_windows_needed = list(ema_ns) + [w for pair in ema_pairs for w in pair]
                    ema_map = ema_multi(frame["value"], ema_windows_needed) if ema_windows_needed else {}
                    for n in ema_ns:
                        col = f"EMA{n}"
                        if n in ema_map:
                            frame[col] = ema_map[n]
                            overlay_cols.append(col)
                    for a, b in ema_pairs:
                        col_a = f"EMA{a}"
                        col_b = f"EMA{b}"
                        if a in ema_map:
                            frame[col_a] = ema_map[a]
                        if b in ema_map:
                            frame[col_b] = ema_map[b]
                        if col_a in frame.columns and col_b in frame.columns:
                            spread_col = f"EMA{a}-EMA{b}"
                            frame[spread_col] = frame[col_a] - frame[col_b]
                            overlay_cols.append(spread_col)
                    overlay_cols = list(dict.fromkeys(overlay_cols))
                    overlay_chart_df = frame[["day", "value"] + overlay_cols]
                    overlay_long = overlay_chart_df.melt(
                        id_vars=["day"],
                        var_name="series",
                        value_name="metric_value",
                    )
                    overlay_long["metric_value"] = pd.to_numeric(
                        overlay_long["metric_value"], errors="coerce"
                    ).fillna(0.0)
                    overlay_long["series"] = overlay_long["series"].replace({"value": "Metric"})
                    overlay_long["base_opacity"] = overlay_long["series"].apply(
                        lambda s: 0.18 if s == "Metric" else 1.0
                    )
                    metric_max_abs = float(
                        pd.to_numeric(overlay_long["metric_value"], errors="coerce")
                        .abs()
                        .max()
                        or 0.0
                    )
                    if metric == "if_proxy":
                        y_format = ".2f"
                    elif metric in {"sleep_duration_h", "deep_sleep_h", "rem_sleep_h"}:
                        y_format = ".1f"
                    elif metric_max_abs < 1:
                        y_format = ".2f"
                    else:
                        y_format = ".0f"
                    x_scale = alt.Scale(
                        domain=[pd.Timestamp(start_ts), pd.Timestamp(end_ts) + pd.Timedelta(days=1)]
                    )
                    chart_height = 320
                    chart = (
                        alt.Chart(overlay_long)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X(
                                "day:T",
                                axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=12),
                                scale=x_scale,
                            ),
                            y=alt.Y(
                                "metric_value:Q",
                                axis=alt.Axis(format=y_format, title=""),
                                scale=alt.Scale(zero=False, nice=True),
                            ),
                            color=alt.Color("series:N", legend=alt.Legend(title="", orient="bottom", direction="horizontal")),
                            opacity=alt.Opacity("base_opacity:Q", legend=None),
                            tooltip=["day:T", "series:N", alt.Tooltip("metric_value:Q", format=y_format)],
                        )
                        .properties(height=chart_height)
                    )
                    top_sel = alt.selection_point(name="dash_metric_legend_sel", fields=["series"], bind="legend")
                    chart = chart.encode(
                        opacity=alt.condition(
                            top_sel,
                            alt.Opacity("base_opacity:Q", legend=None),
                            alt.value(0.18),
                            empty=True,
                        )
                    ).add_params(top_sel)
                    chart = chart.properties(
                        height=chart_height, padding={"left": 72, "right": 12, "top": 6, "bottom": 44}
                    )
                    if top_injury_overlay:
                        overlay_df = pd.DataFrame(saved_injury_windows).copy()
                        overlay_df["start"] = pd.to_datetime(overlay_df["start"], errors="coerce")
                        overlay_df["end"] = pd.to_datetime(overlay_df["end"], errors="coerce")
                        overlay_df["severity"] = overlay_df.get("severity", "injury").fillna("injury")
                        range_start = pd.Timestamp(start_ts)
                        range_end_exclusive = pd.Timestamp(end_ts) + pd.Timedelta(days=1)
                        total_seconds = max((range_end_exclusive - range_start).total_seconds(), 1.0)
                        blocks: list[str] = []
                        for _, win in overlay_df.iterrows():
                            s = win.get("start")
                            e = win.get("end")
                            if pd.isna(s) or pd.isna(e):
                                continue
                            e_exclusive = pd.Timestamp(e) + pd.Timedelta(days=1)
                            if e_exclusive <= range_start or s >= range_end_exclusive:
                                continue
                            clipped_start = max(pd.Timestamp(s), range_start)
                            clipped_end = min(e_exclusive, range_end_exclusive)
                            left_pct = ((clipped_start - range_start).total_seconds() / total_seconds) * 100.0
                            width_pct = max(
                                ((clipped_end - clipped_start).total_seconds() / total_seconds) * 100.0,
                                0.6,
                            )
                            sev = str(win.get("severity") or "injury")
                            color = "#facc15" if sev == "light_injury" else "#ef4444"
                            label = str(win.get("label") or "Injury")
                            blocks.append(
                                f"<div title='{label}' style='position:absolute;left:{left_pct:.4f}%;"
                                f"width:{width_pct:.4f}%;top:1px;bottom:1px;background:{color};opacity:0.32;"
                                "border-radius:999px;'></div>"
                            )
                        if blocks:
                            strip_html = (
                                "<div style='display:flex;align-items:center;gap:10px;margin:2px 0 6px 0;"
                                "font-size:11px;color:rgba(226,232,240,0.72);'>"
                                "<span style='display:inline-flex;align-items:center;gap:4px;'>"
                                "<span style='display:inline-block;width:8px;height:8px;border-radius:999px;"
                                "background:#ef4444;opacity:0.8;'></span>injury</span>"
                                "<span style='display:inline-flex;align-items:center;gap:4px;'>"
                                "<span style='display:inline-block;width:8px;height:8px;border-radius:999px;"
                                "background:#facc15;opacity:0.8;'></span>light injury</span>"
                                "</div>"
                                "<div style='position:relative;height:10px;border-radius:999px;"
                                "background:linear-gradient(90deg, rgba(148,163,184,0.10), rgba(148,163,184,0.16));"
                                "border:1px solid rgba(148,163,184,0.25);margin:0 0 8px 0;overflow:hidden;'>"
                                + "".join(blocks)
                                + "</div>"
                            )
                            st.markdown(strip_html, unsafe_allow_html=True)
                    if enable_zoom:
                        chart = chart.interactive()
                    custom_metric_main_chart = chart

            if compare_mode and plot_frames:
                compare_df = pd.concat(plot_frames, ignore_index=True)

                left_df = compare_df[compare_df["axis_side"] == "left"]
                right_df = compare_df[compare_df["axis_side"] == "right"]
                x_scale = alt.Scale(
                    domain=[pd.Timestamp(start_ts), pd.Timestamp(end_ts) + pd.Timedelta(days=1)]
                )

                left_chart = (
                    alt.Chart(left_df)
                    .mark_line(point=True, opacity=0.65)
                    .encode(
                        x=alt.X(
                            "day:T",
                            axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=12),
                            scale=x_scale,
                        ),
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Left axis")),
                        color=alt.Color("series:N", legend=alt.Legend(orient="bottom", direction="horizontal")),
                        tooltip=["day:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                )
                right_chart = (
                    alt.Chart(right_df)
                    .mark_line(point=True, opacity=0.65)
                    .encode(
                        x=alt.X(
                            "day:T",
                            axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=12),
                            scale=x_scale,
                        ),
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Right axis", orient="right")),
                        color=alt.Color("series:N", legend=alt.Legend(orient="bottom", direction="horizontal")),
                        tooltip=["day:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                )
                compare_chart = alt.layer(left_chart, right_chart).resolve_scale(y="independent")
                if top_injury_overlay:
                    compare_chart = alt.layer(
                        build_injury_layer(saved_injury_windows, start_ts, end_ts),
                        left_chart,
                        right_chart,
                    ).resolve_scale(y="independent")
                compare_chart = compare_chart.properties(
                    height=360, padding={"left": 72, "right": 42, "top": 8, "bottom": 44}
                )
                if enable_zoom:
                    compare_chart = compare_chart.interactive()
                    st.caption("Tip: drag chart to pan/zoom, double-click to reset.")
                custom_metric_compare_chart = compare_chart
            elif compare_mode:
                custom_metric_compare_empty = True
        weekly = weekly_summary(range_filtered_metrics)
        weekly["week_start"] = pd.to_datetime(weekly["week_start"])

        def _section_long_series(
            source_df: pd.DataFrame,
            value_cols: list[str],
            label_map: dict[str, str],
            use_weekly: bool,
            start_day: pd.Timestamp | None = None,
            end_day: pd.Timestamp | None = None,
        ) -> pd.DataFrame:
            if source_df.empty:
                return pd.DataFrame(columns=["period_start", "series", "value"])
            needed_cols = ["day_dt"] + value_cols
            if any(c not in source_df.columns for c in needed_cols):
                return pd.DataFrame(columns=["period_start", "series", "value"])
            work = source_df[needed_cols].copy()
            work["period_start"] = pd.to_datetime(work["day_dt"], errors="coerce")
            work = work.dropna(subset=["period_start"])
            for c in value_cols:
                work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
            if use_weekly:
                work["period_start"] = work["period_start"].dt.to_period("W-SUN").dt.start_time
                work = work.groupby("period_start", as_index=False)[value_cols].mean()
            work = work.sort_values("period_start")
            if work.empty:
                return pd.DataFrame(columns=["period_start", "series", "value"])
            long_df = work.melt(
                id_vars=["period_start"],
                value_vars=value_cols,
                var_name="series",
                value_name="value",
            )
            long_df["period_start"] = pd.to_datetime(long_df["period_start"], errors="coerce")
            long_df = long_df.dropna(subset=["period_start"]).copy()
            # Keep chart range deterministic and prevent silently off-range points.
            if start_day is not None and end_day is not None:
                range_start = pd.Timestamp(start_day)
                range_end_exclusive = pd.Timestamp(end_day) + pd.Timedelta(days=1)
                long_df = long_df[
                    (long_df["period_start"] >= range_start)
                    & (long_df["period_start"] < range_end_exclusive)
                ].copy()
            long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce").fillna(0.0)
            long_df["series"] = long_df["series"].map(label_map).fillna(long_df["series"].astype(str))
            return long_df.dropna(subset=["period_start"]).sort_values(["period_start", "series"])

        def _safe_y_domain(vals: pd.Series) -> list[float]:
            v = pd.to_numeric(vals, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if v.empty:
                return [-1.0, 5.0]
            vmin = float(v.min())
            vmax = float(v.max())
            if abs(vmax - vmin) < 1e-9:
                pad = max(1.0, abs(vmax) * 0.1, 0.5)
                return [min(vmin - pad, 0.0), vmax + pad]
            pad = max(1.0, (vmax - vmin) * 0.10)
            return [min(vmin - pad, 0.0), vmax + pad]

        ordered_tss_container = st.container()
        ordered_leg_pounding_container = st.container()
        ordered_distance_container = st.container()
        ordered_overreach_container = st.container()
        ordered_fitness_container = st.container()

        if render_summary:
            if (
                (weekly_toggle and "total_tss" in weekly.columns and "total_rtss" in weekly.columns and not weekly.empty)
                or (
                    (not weekly_toggle)
                    and (not filtered_daily_range.empty)
                    and "tss_total" in filtered_daily_range.columns
                    and "rtss_total" in filtered_daily_range.columns
                )
            ):
                if weekly_toggle:
                    tss_base = weekly[["week_start", "total_tss", "total_rtss"]].copy().sort_values("week_start")
                    tss_base = tss_base.rename(
                        columns={"week_start": "period_start", "total_tss": "tss", "total_rtss": "rtss"}
                    )
                    tss_base["tss"] = pd.to_numeric(tss_base["tss"], errors="coerce").fillna(0.0)
                    tss_base["rtss"] = pd.to_numeric(tss_base["rtss"], errors="coerce").fillna(0.0)
                else:
                    tss_base = filtered_daily_range[["day_utc", "tss_total", "rtss_total"]].copy()
                    tss_base["period_start"] = pd.to_datetime(tss_base["day_utc"], errors="coerce")
                    tss_base["tss"] = pd.to_numeric(tss_base["tss_total"], errors="coerce").fillna(0.0)
                    tss_base["rtss"] = pd.to_numeric(tss_base["rtss_total"], errors="coerce").fillna(0.0)
                    tss_base = tss_base[["period_start", "tss", "rtss"]].dropna(subset=["period_start"]).sort_values("period_start")
                tss_base = tss_base.dropna(subset=["period_start"]).sort_values("period_start")
                tss_plot = tss_base.melt(
                    id_vars=["period_start"],
                    value_vars=["tss", "rtss"],
                    var_name="series",
                    value_name="value",
                )
                tss_plot["value"] = pd.to_numeric(tss_plot["value"], errors="coerce").fillna(0.0)
                tss_plot["series"] = tss_plot["series"].replace(
                    {"tss": "TSS", "rtss": "rTSS"}
                )
                ordered_tss_container.subheader("TSS vs rTSS")
                tss_chart = (
                    alt.Chart(tss_plot)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("period_start:T", axis=alt.Axis(title="")),
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                        color=alt.Color(
                            "series:N",
                            legend=alt.Legend(title=None, orient="bottom", direction="horizontal"),
                            scale=alt.Scale(domain=["TSS", "rTSS"], range=["#60a5fa", "#f59e0b"]),
                        ),
                        tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                    .properties(height=280)
                )
                threshold_value = float(derived_weekly_tss_target if weekly_toggle else derived_daily_tss_target)
                threshold_df = pd.DataFrame({"threshold": [threshold_value]})
                tss_threshold = (
                    alt.Chart(threshold_df)
                    .mark_rule(color="#fb923c", strokeDash=[6, 4], strokeWidth=2.5, opacity=1.0)
                    .encode(y="threshold:Q")
                )
                tss_threshold_label = (
                    alt.Chart(threshold_df)
                    .mark_text(
                        align="left",
                        dx=8,
                        dy=-6,
                        color="#fdba74",
                        fontSize=11,
                        fontWeight=700,
                    )
                    .encode(
                        x=alt.value(6),
                        y="threshold:Q",
                        text=alt.value(f"Target {int(round(threshold_value))}"),
                    )
                )
                tss_chart = alt.layer(tss_chart, tss_threshold, tss_threshold_label)
                tss_chart = alt.layer(
                    build_injury_layer(saved_injury_windows, start_ts, end_ts),
                    tss_chart,
                ).resolve_scale(y="independent")
                if enable_zoom:
                    tss_chart = tss_chart.interactive()
                ordered_tss_container.altair_chart(
                    tss_chart,
                    use_container_width=True,
                    key="dashboard_summary_tss_rtss",
                )
                ordered_tss_container.caption(
                    f"The dotted line is Stress Score {int(round(threshold_value))} "
                    f"({'weekly' if weekly_toggle else 'daily'} mode). "
                    f"Derived from LT pace {_pace_compact(float(derived_threshold_pace_sec))}. "
                    "For good training, keep TSS above it while rTSS stays below it."
                )

        if render_fitness:
            ordered_fitness_container.subheader("Fitness vs Fatigue")
            if not filtered_daily_range.empty and "fitness" in filtered_daily_range.columns and "fatigue" in filtered_daily_range.columns:
                weekly_ff_long = _section_long_series(
                    filtered_daily_range,
                    value_cols=["fitness", "fatigue"],
                    label_map={"fitness": "Fitness", "fatigue": "Fatigue"},
                    use_weekly=weekly_toggle,
                    start_day=start_ts,
                    end_day=end_ts,
                )
                if weekly_ff_long.empty:
                    st.caption("No fitness/fatigue data to plot.")
                else:
                    ff_domain = _safe_y_domain(weekly_ff_long["value"])
                    ff_chart = (
                        alt.Chart(weekly_ff_long)
                        .mark_line(point=alt.OverlayMarkDef(filled=True, size=54), strokeWidth=2.2)
                        .encode(
                            x=alt.X(
                                "period_start:T",
                                axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10),
                                scale=alt.Scale(
                                    domain=[pd.Timestamp(start_ts), pd.Timestamp(end_ts) + pd.Timedelta(days=1)]
                                ),
                            ),
                            y=alt.Y(
                                "value:Q",
                                axis=alt.Axis(format=".0f"),
                                scale=alt.Scale(domain=ff_domain),
                            ),
                            color=alt.Color(
                                "series:N",
                                legend=alt.Legend(orient="bottom", direction="horizontal"),
                                scale=alt.Scale(domain=["Fitness", "Fatigue"], range=["#22c55e", "#ef4444"]),
                            ),
                            tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                        )
                        .properties(height=280)
                    )
                    ff_chart = alt.layer(
                        build_injury_layer(saved_injury_windows, start_ts, end_ts),
                        ff_chart,
                    ).resolve_scale(y="independent")
                    if enable_zoom:
                        ff_chart = ff_chart.interactive()
                    ordered_fitness_container.altair_chart(
                        ff_chart,
                        use_container_width=True,
                        key="dashboard_fitness_fatigue",
                    )
            else:
                ordered_fitness_container.caption("No fitness/fatigue data to plot.")

        if render_injury:
            ordered_leg_pounding_container.subheader("Leg Elasticity vs Pounding")
            if not filtered_daily_range.empty and "leg_elasticity" in filtered_daily_range.columns and "pounding" in filtered_daily_range.columns:
                weekly_rff_long = _section_long_series(
                    filtered_daily_range,
                    value_cols=["leg_elasticity", "pounding"],
                    label_map={"leg_elasticity": "Leg Elasticity", "pounding": "Pounding"},
                    use_weekly=weekly_toggle,
                    start_day=start_ts,
                    end_day=end_ts,
                )
                if weekly_rff_long.empty:
                    st.caption("No Leg Elasticity/Pounding data in this range.")
                else:
                    # Keep threshold on the same scale users expect for this chart.
                    rff_threshold_value = float(derived_daily_tss_target)
                    rff_domain = _safe_y_domain(
                        pd.concat(
                            [weekly_rff_long["value"], pd.Series([rff_threshold_value])],
                            ignore_index=True,
                        )
                    )
                    rff_chart = (
                        alt.Chart(weekly_rff_long)
                        .mark_line(point=alt.OverlayMarkDef(filled=True, size=54), strokeWidth=2.2)
                        .encode(
                            x=alt.X(
                                "period_start:T",
                                axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10),
                                scale=alt.Scale(
                                    domain=[pd.Timestamp(start_ts), pd.Timestamp(end_ts) + pd.Timedelta(days=1)]
                                ),
                            ),
                            y=alt.Y(
                                "value:Q",
                                axis=alt.Axis(format=".0f"),
                                scale=alt.Scale(domain=rff_domain),
                            ),
                            color=alt.Color(
                                "series:N",
                                legend=alt.Legend(title=None, orient="bottom", direction="horizontal"),
                                scale=alt.Scale(domain=["Leg Elasticity", "Pounding"], range=["#22c55e", "#ef4444"]),
                            ),
                            tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                        )
                        .properties(height=280)
                    )
                    rff_threshold = (
                        alt.Chart(pd.DataFrame({"threshold": [rff_threshold_value]}))
                        .mark_rule(color="#f59e0b", strokeDash=[6, 4], opacity=0.8)
                        .encode(y=alt.Y("threshold:Q"))
                    )
                    rff_chart = alt.layer(
                        build_injury_layer(saved_injury_windows, start_ts, end_ts),
                        rff_chart,
                        rff_threshold,
                    )
                    if enable_zoom:
                        rff_chart = rff_chart.interactive()
                    ordered_leg_pounding_container.altair_chart(
                        rff_chart,
                        use_container_width=True,
                        key="dashboard_injury_leg_pounding",
                    )
            else:
                ordered_leg_pounding_container.caption("No Leg Elasticity/Pounding data to plot.")

        if render_summary:
            ordered_distance_container.subheader("Distance vs Distance Eqv.")
            if (
                (weekly_toggle and "total_distance_km" in weekly.columns and "total_distance_proxy_km" in weekly.columns and not weekly.empty)
                or (
                    (not weekly_toggle)
                    and (not filtered_daily_range.empty)
                    and "distance_km" in filtered_daily_range.columns
                    and "distance_proxy_km" in filtered_daily_range.columns
                )
            ):
                if weekly_toggle:
                    dist_base = weekly[["week_start", "total_distance_km", "total_distance_proxy_km"]].copy()
                    dist_base = dist_base.rename(
                        columns={"week_start": "period_start", "total_distance_km": "distance_km", "total_distance_proxy_km": "distance_proxy_km"}
                    )
                else:
                    dist_base = filtered_daily_range[["day_utc", "distance_km", "distance_proxy_km"]].copy()
                    dist_base["period_start"] = pd.to_datetime(dist_base["day_utc"], errors="coerce")
                    dist_base = dist_base.dropna(subset=["period_start"])
                dist_base = dist_base.sort_values("period_start")
                weekly_dist_long = dist_base.melt(
                    id_vars=["period_start"],
                    value_vars=["distance_km", "distance_proxy_km"],
                    var_name="series",
                    value_name="value",
                )
                weekly_dist_long["series"] = weekly_dist_long["series"].replace(
                    {
                        "distance_km": "Distance",
                        "distance_proxy_km": "Distance Eqv.",
                    }
                )
                weekly_dist_chart = (
                    alt.Chart(weekly_dist_long)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("period_start:T", axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10)),
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="km")),
                        color=alt.Color(
                            "series:N",
                            legend=alt.Legend(title="", orient="bottom", direction="horizontal"),
                            scale=alt.Scale(domain=["Distance", "Distance Eqv."], range=["#60a5fa", "#22c55e"]),
                        ),
                        tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                    .properties(height=280)
                )
                dist_threshold_value = float(
                    derived_weekly_distance_target if weekly_toggle else derived_daily_distance_target
                )
                dist_threshold_df = pd.DataFrame({"threshold": [dist_threshold_value]})
                dist_threshold = (
                    alt.Chart(dist_threshold_df)
                    .mark_rule(color="#f59e0b", strokeDash=[6, 4], strokeWidth=2.2, opacity=1.0)
                    .encode(y="threshold:Q")
                )
                dist_threshold_label = (
                    alt.Chart(dist_threshold_df)
                    .mark_text(
                        align="left",
                        dx=8,
                        dy=-6,
                        color="#fbbf24",
                        fontSize=11,
                        fontWeight=700,
                    )
                    .encode(
                        x=alt.value(6),
                        y="threshold:Q",
                        text=alt.value(f"Target {int(round(dist_threshold_value))} km"),
                    )
                )
                weekly_dist_chart = alt.layer(weekly_dist_chart, dist_threshold, dist_threshold_label)
                weekly_dist_chart = alt.layer(
                    build_injury_layer(saved_injury_windows, start_ts, end_ts),
                    weekly_dist_chart,
                ).resolve_scale(y="independent")
                if enable_zoom:
                    weekly_dist_chart = weekly_dist_chart.interactive()
                ordered_distance_container.altair_chart(
                    weekly_dist_chart,
                    use_container_width=True,
                    key="dashboard_summary_distance",
                )
                ordered_distance_container.caption(
                    f"The dotted line is Distance target {int(round(dist_threshold_value))} km "
                    f"({'weekly' if weekly_toggle else 'daily'} mode), derived from LT pace "
                    f"{_pace_compact(float(derived_threshold_pace_sec))}. "
                    "Distance Eqv. = running-equivalent distance inferred from non-running sessions by matching "
                    "running rTSS to HR-based TSS scaled by specificity (applied once)."
                )
            else:
                ordered_distance_container.caption("No distance-equivalent data to plot.")

        if render_injury:
            ordered_overreach_container.subheader("Overreach vs Injury Risk")
            if not filtered_daily_range.empty and "overreach" in filtered_daily_range.columns and "injury_risk" in filtered_daily_range.columns:
                weekly_fr_long = _section_long_series(
                    filtered_daily_range,
                    value_cols=["overreach", "injury_risk"],
                    label_map={"overreach": "Overreach", "injury_risk": "Injury Risk"},
                    use_weekly=weekly_toggle,
                    start_day=start_ts,
                    end_day=end_ts,
                )
                if weekly_fr_long.empty:
                    st.caption("No Overreach/Injury Risk data to plot.")
                else:
                    fr_domain = _safe_y_domain(weekly_fr_long["value"])
                    fr_chart = (
                        alt.Chart(weekly_fr_long)
                        .mark_line(point=alt.OverlayMarkDef(filled=True, size=54), strokeWidth=2.2)
                        .encode(
                            x=alt.X(
                                "period_start:T",
                                axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10),
                                scale=alt.Scale(
                                    domain=[pd.Timestamp(start_ts), pd.Timestamp(end_ts) + pd.Timedelta(days=1)]
                                ),
                            ),
                            y=alt.Y(
                                "value:Q",
                                axis=alt.Axis(format=".0f"),
                                scale=alt.Scale(domain=fr_domain),
                            ),
                            color=alt.Color(
                                "series:N",
                                legend=alt.Legend(title=None, orient="bottom", direction="horizontal"),
                                scale=alt.Scale(domain=["Overreach", "Injury Risk"], range=["#60a5fa", "#ef4444"]),
                            ),
                            tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                        )
                        .properties(height=280)
                    )
                    fr_chart = alt.layer(
                        build_injury_layer(saved_injury_windows, start_ts, end_ts),
                        fr_chart,
                    ).resolve_scale(y="independent")
                    if enable_zoom:
                        fr_chart = fr_chart.interactive()
                    ordered_overreach_container.altair_chart(
                        fr_chart,
                        use_container_width=True,
                        key="dashboard_injury_overreach",
                    )
            else:
                ordered_overreach_container.caption("No Overreach/Injury Risk data to plot.")

        if render_fitness:
            st.subheader("Garmin Training Load vs. Total Calories")
            if (
                (weekly_toggle and "total_garmin_training_load" in weekly.columns and "total_calories" in weekly.columns and not weekly.empty)
                or (
                    (not weekly_toggle)
                    and (not filtered_daily_range.empty)
                    and "training_load_garmin" in filtered_daily_range.columns
                    and "calories_total" in filtered_daily_range.columns
                )
            ):
                if weekly_toggle:
                    weekly_gc = weekly[["week_start", "total_garmin_training_load", "total_calories"]].copy()
                    weekly_gc = weekly_gc.rename(columns={"week_start": "period_start", "total_garmin_training_load": "garmin", "total_calories": "calories"})
                else:
                    weekly_gc = filtered_daily_range[["day_utc", "training_load_garmin", "calories_total"]].copy()
                    weekly_gc["period_start"] = pd.to_datetime(weekly_gc["day_utc"], errors="coerce")
                    weekly_gc = weekly_gc.rename(columns={"training_load_garmin": "garmin", "calories_total": "calories"})
                weekly_gc["period_start"] = pd.to_datetime(weekly_gc["period_start"], errors="coerce")
                weekly_gc["garmin"] = pd.to_numeric(weekly_gc["garmin"], errors="coerce").fillna(0.0)
                weekly_gc["calories"] = pd.to_numeric(weekly_gc["calories"], errors="coerce").fillna(0.0)
                weekly_gc = weekly_gc.dropna(subset=["period_start"]).sort_values("period_start")

                if weekly_gc.empty:
                    st.caption("No Garmin training load/calories data to plot.")
                else:
                    weekly_gc_long = pd.DataFrame(
                        {
                            "period_start": pd.concat([weekly_gc["period_start"], weekly_gc["period_start"]], ignore_index=True),
                            "series": ["Garmin Training Load"] * len(weekly_gc) + ["Total Calories"] * len(weekly_gc),
                            "value": pd.concat(
                                [weekly_gc["garmin"], weekly_gc["calories"]],
                                ignore_index=True,
                            ),
                        }
                    )

                    base = alt.Chart(weekly_gc_long).encode(
                        x=alt.X(
                            "period_start:T",
                            axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10),
                        ),
                        color=alt.Color(
                            "series:N",
                            legend=alt.Legend(orient="bottom", direction="horizontal"),
                            scale=alt.Scale(
                                domain=["Garmin Training Load", "Total Calories"],
                                range=["#60a5fa", "#f59e0b"],
                            ),
                        ),
                        tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                    legend_sel = alt.selection_point(name="activity_energy_legend_sel", fields=["series"], bind="legend")
                    left_chart = base.transform_filter(alt.datum.series == "Garmin Training Load").mark_line(point=True).encode(
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Garmin Training Load"))
                    )
                    right_chart = base.transform_filter(alt.datum.series == "Total Calories").mark_line(point=True).encode(
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Total Calories", orient="right"))
                    )
                    left_chart = left_chart.encode(
                        opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.2), empty=True)
                    )
                    right_chart = right_chart.encode(
                        opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.2), empty=True)
                    )
                    weekly_chart = alt.layer(left_chart, right_chart).resolve_scale(y="independent")
                    weekly_chart = weekly_chart.add_params(legend_sel)
                    if enable_zoom:
                        weekly_chart = weekly_chart.interactive()
                    st.altair_chart(
                        weekly_chart,
                        use_container_width=True,
                        key="dashboard_fitness_training_load",
                    )
            else:
                st.caption("No Garmin training load/calories data to plot.")

        if render_fitness:
            st.subheader("HR Zone Time (hours)")
            zone_cols = [
                "hr_time_in_zone_1",
                "hr_time_in_zone_2",
                "hr_time_in_zone_3",
                "hr_time_in_zone_4",
                "hr_time_in_zone_5",
            ]
            if not range_filtered_metrics.empty and all(col in range_filtered_metrics.columns for col in zone_cols):
                zone_df = range_filtered_metrics.copy()
                zone_df["day"] = _to_local_naive(zone_df["start_time_utc"])
                zone_df = zone_df.dropna(subset=["day"])
                zone_df["duration_s"] = pd.to_numeric(zone_df.get("duration_s"), errors="coerce").fillna(0.0)
                for col in zone_cols:
                    zone_df[col] = pd.to_numeric(zone_df.get(col), errors="coerce").fillna(0.0)

                if zone_df.empty:
                    st.caption("No heart-rate zone time data to plot.")
                else:
                    zone_df["period_start"] = zone_df["day"]
                    if weekly_toggle:
                        zone_df["period_start"] = zone_df["period_start"].dt.to_period("W-SUN").dt.start_time
                    period_zone = (
                        zone_df.groupby("period_start", as_index=False)[["duration_s"] + zone_cols]
                        .sum()
                        .sort_values("period_start")
                    )
                    weekly_zone_hours = pd.DataFrame(
                        {
                            "period_start": period_zone["period_start"],
                            "Low Aerobic": pd.to_numeric(period_zone["hr_time_in_zone_1"], errors="coerce").fillna(0.0) / 3600.0,
                            "Moderate Aerobic": pd.to_numeric(period_zone["hr_time_in_zone_2"], errors="coerce").fillna(0.0) / 3600.0,
                            "High Aerobic": (
                                pd.to_numeric(period_zone["hr_time_in_zone_3"], errors="coerce").fillna(0.0)
                                + pd.to_numeric(period_zone["hr_time_in_zone_4"], errors="coerce").fillna(0.0)
                            )
                            / 3600.0,
                            "Total Time": (
                                pd.to_numeric(period_zone["duration_s"], errors="coerce").fillna(0.0) / 3600.0
                            ),
                        }
                    )
                    weekly_zone_hours_long = weekly_zone_hours.melt(
                        id_vars=["period_start"],
                        value_vars=["Low Aerobic", "Moderate Aerobic", "High Aerobic", "Total Time"],
                        var_name="zone",
                        value_name="hours",
                    )
                    weekly_zone_hours_long["hours"] = pd.to_numeric(
                        weekly_zone_hours_long["hours"], errors="coerce"
                    ).fillna(0.0)
                    weekly_zone_hours_long["hours_label"] = weekly_zone_hours_long["hours"].map(lambda h: f"{h:.1f}h")
                    weekly_zone_hours_long["axis_side"] = weekly_zone_hours_long["zone"].map(
                        lambda z: "right" if z == "Total Time" else "left"
                    )

                    base = alt.Chart(weekly_zone_hours_long).encode(
                        x=alt.X(
                            "period_start:T",
                            axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10),
                        ),
                        color=alt.Color(
                            "zone:N",
                            legend=alt.Legend(title="", orient="bottom", direction="horizontal"),
                            scale=alt.Scale(
                                domain=["Low Aerobic", "Moderate Aerobic", "High Aerobic", "Total Time"],
                                range=["#3b82f6", "#facc15", "#ef4444", "#cbd5e1"],
                            ),
                        ),
                        tooltip=["period_start:T", "zone:N", alt.Tooltip("hours_label:N", title="hours")],
                    )
                    zone_hours_sel = alt.selection_point(name="zone_hours_legend_sel", fields=["zone"], bind="legend")
                    left_layer = (
                        base.transform_filter(alt.datum.axis_side == "left")
                        .mark_line(point=True)
                        .encode(
                            y=alt.Y("hours:Q", axis=alt.Axis(title="hours", format=".1f")),
                            opacity=alt.condition(zone_hours_sel, alt.value(1.0), alt.value(0.2), empty=True),
                        )
                    )
                    right_layer = (
                        base.transform_filter(alt.datum.axis_side == "right")
                        .mark_line(point=True, strokeDash=[6, 4])
                        .encode(
                            y=alt.Y("hours:Q", axis=alt.Axis(title="total hours", format=".1f", orient="right")),
                            opacity=alt.condition(zone_hours_sel, alt.value(1.0), alt.value(0.2), empty=True),
                        )
                    )
                    zone_hours_chart = (
                        alt.layer(left_layer, right_layer)
                        .resolve_scale(y="independent")
                        .add_params(zone_hours_sel)
                        .properties(height=260)
                    )
                    if enable_zoom:
                        zone_hours_chart = zone_hours_chart.interactive()
                    st.altair_chart(
                        zone_hours_chart,
                        use_container_width=True,
                        key="dashboard_fitness_hr_zones",
                    )
                    st.caption("Anaerobic (Z5) is tracked but not plotted in this view.")
            else:
                st.caption("No heart-rate zone time data to plot.")

        if render_activities:
            table_source = range_filtered_metrics.copy()
            if not table_source.empty and not filtered_daily.empty:
                table_source["day_utc"] = _to_local_naive(table_source["start_time_utc"]).dt.date.astype(str)
                daily_fit = (
                    filtered_daily[["day_utc", "fitness", "fatigue"]]
                    .dropna(subset=["day_utc"])
                    .drop_duplicates(subset=["day_utc"], keep="last")
                )
                table_source = table_source.merge(daily_fit, on="day_utc", how="left")
            table_df = display_table(table_source)
            st.subheader("Activities")
            table_df = table_df.copy()
            if "if_proxy" in table_df.columns:
                raw_if_proxy = table_df["if_proxy"]
                # Duplicate column labels can return a DataFrame here; force 1-D.
                if isinstance(raw_if_proxy, pd.DataFrame):
                    if_proxy_series = raw_if_proxy.iloc[:, 0]
                elif isinstance(raw_if_proxy, pd.Series):
                    if_proxy_series = raw_if_proxy
                else:
                    if_proxy_series = pd.Series(raw_if_proxy, index=table_df.index)
            else:
                if_proxy_series = pd.Series(0.0, index=table_df.index)
            table_df["if_proxy_pct"] = pd.to_numeric(if_proxy_series, errors="coerce").fillna(0.0) * 100.0
            table_df = table_df.drop(columns=["if_proxy"], errors="ignore")
            st.dataframe(
                table_df,
                use_container_width=True,
                column_config={
                    "sport_type": st.column_config.TextColumn("Activity Type"),
                    "distance_km": st.column_config.NumberColumn(format="%.0f km"),
                    "duration_min": st.column_config.NumberColumn(format="%.1f min"),
                    "avg_pace_display": st.column_config.TextColumn("Pace"),
                    "rtss": st.column_config.NumberColumn("rTSS", format="%.0f"),
                    "tss": st.column_config.NumberColumn("TSS", format="%.0f"),
                    "if_proxy_pct": st.column_config.NumberColumn("IF", format="%.0f%%"),
                    "training_load_garmin": st.column_config.NumberColumn(format="%.0f"),
                    "specificity_factor": st.column_config.NumberColumn(format="%.2f"),
                    "fitness": st.column_config.NumberColumn("Fitness", format="%.0f"),
                    "fatigue": st.column_config.NumberColumn("Fatigue", format="%.0f"),
                    "distance_proxy_km": st.column_config.NumberColumn("Distance Proxy", format="%.0f km"),
                    "pace_proxy_display": st.column_config.TextColumn("Pace Proxy"),
                    "distance_proxy_method": st.column_config.TextColumn("Distance Proxy Method"),
                },
            )
        if run_custom_metric:
            st.subheader("Custom Metric")
            metric_labels = list(metric_map.keys())
            selected_metric_label = str(st.session_state.get("dashboard_metric_select") or "TSS")
            if selected_metric_label not in metric_labels:
                selected_metric_label = "TSS" if "TSS" in metric_labels else metric_labels[0]
            custom_controls = st.columns([1.0, 1.0, 0.9, 0.9, 1.4])
            with custom_controls[0]:
                st.selectbox(
                    "Metric",
                    metric_labels,
                    index=metric_labels.index(selected_metric_label),
                    key="dashboard_metric_select",
                )
            with custom_controls[1]:
                st.text_input("EMA Days", key="dashboard_ema_windows")
            with custom_controls[2]:
                st.checkbox("Compare mode (up to 3 metrics)", key="dashboard_compare_mode")
            with custom_controls[3]:
                st.checkbox("Top injury overlay", key="dashboard_top_injury_overlay")

            compare_mode_active = bool(st.session_state.get("dashboard_compare_mode", False))
            if compare_mode_active:
                if custom_metric_compare_chart is not None:
                    st.altair_chart(
                        custom_metric_compare_chart,
                        use_container_width=True,
                        key="dashboard_custom_metric_compare",
                    )
                elif custom_metric_compare_empty:
                    st.caption("No comparable data found for the selected metrics/date range.")
            else:
                if custom_metric_main_chart is not None:
                    st.altair_chart(
                        custom_metric_main_chart,
                        use_container_width=True,
                        key="dashboard_custom_metric_main",
                    )
                else:
                    st.caption("No data found for selected custom metric/date range.")
        section_render_ms = (perf_counter() - section_render_t0) * 1000.0
        total_ms = (perf_counter() - dashboard_block_t0) * 1000.0
        st.caption(
            "Perf timings (Dashboard): "
            f"prep {prep_ms:.0f} ms · section {section_render_ms:.0f} ms · total {total_ms:.0f} ms"
        )

if view in {"Weekly Summary", "Activity Summary"}:
    st.header("Week Outlook" if view == "Weekly Summary" else "Activity Dashboard")

    custom_metrics_df = _get_custom_metrics_df_local_cached(
        db_path=cfg.db_path,
        custom_activities_cache_key=custom_activities_cache_key,
        lthr_bpm=float(derived_lthr_bpm),
        lthr_curve_points=lthr_curve_points,
        threshold_pace_default_sec=float(derived_threshold_pace_sec),
        threshold_pace_curve_points=lt_pace_curve_points,
        if_zone_thresholds_key=active_if_zone_thresholds_key,
    )
    calendar_metrics_df = _merge_metrics_with_custom(
        metrics_df,
        custom_metrics_df,
    )

    if calendar_metrics_df.empty:
        st.info("No activities available.")
    else:
        if previous_view not in {"Weekly Summary", "Activity Summary"}:
            st.session_state.pop("calendar_split_activity_id", None)
            st.session_state["calendar_split_open"] = False
        cal_base = calendar_metrics_df.copy()
        cal_base["start_local"] = _to_local_naive(cal_base["start_time_utc"])
        cal_base = cal_base.dropna(subset=["start_local"]).copy()

        if cal_base.empty:
            st.info("No valid activity timestamps available.")
        else:
            compact_mode_early = view == "Weekly Summary"
            compare_options: list[str] = ["Previous week", "2 weeks ago", "3 weeks ago", "4 weeks ago", "Planned"]
            cal_min_day = cal_base["start_local"].min().date()
            cal_max_day = cal_base["start_local"].max().date()
            min_week_start = pd.Timestamp(cal_min_day) - pd.Timedelta(days=int(pd.Timestamp(cal_min_day).weekday()))
            max_week_start = pd.Timestamp(cal_max_day) - pd.Timedelta(days=int(pd.Timestamp(cal_max_day).weekday()))
            today_week_start = pd.Timestamp(datetime.now().astimezone().date())
            today_week_start = today_week_start - pd.Timedelta(days=int(today_week_start.weekday()))
            default_week_start = (
                today_week_start
                if (today_week_start >= min_week_start and today_week_start <= max_week_start)
                else max_week_start
            )
            if compact_mode_early:
                latest_week_start = pd.Timestamp(cal_max_day) - pd.Timedelta(
                    days=int(pd.Timestamp(cal_max_day).weekday())
                )
                selected_preview = pd.to_datetime(
                    st.session_state.get("calendar_compact_week_start"), errors="coerce"
                )
                if pd.isna(selected_preview):
                    selected_preview = default_week_start
                selected_preview = selected_preview - pd.Timedelta(days=int(selected_preview.weekday()))
                if selected_preview < min_week_start:
                    selected_preview = min_week_start
                if selected_preview > max_week_start:
                    selected_preview = max_week_start
                is_future_week_preview = selected_preview > latest_week_start

                current_compare_choice = str(
                    st.session_state.get("calendar_compact_compare_choice", "Planned")
                )
                if is_future_week_preview and current_compare_choice == "Planned":
                    st.session_state["calendar_compact_compare_choice"] = "Previous week"
                    current_compare_choice = "Previous week"

                compare_options = ["Previous week", "2 weeks ago", "3 weeks ago", "4 weeks ago"]
                if not is_future_week_preview:
                    compare_options.append("Planned")
                    if "calendar_compact_compare_choice" not in st.session_state:
                        st.session_state["calendar_compact_compare_choice"] = "Planned"
                elif current_compare_choice not in compare_options:
                    st.session_state["calendar_compact_compare_choice"] = "Previous week"

                compare_choice = str(st.session_state.get("calendar_compact_compare_choice", "Planned"))
                range_start_day = cal_min_day
                range_end_day = cal_max_day
                cal_activity_filter = "All Activities"
            else:
                # Activity Dashboard now always renders full available history and all activities.
                range_start_day = cal_min_day
                range_end_day = cal_max_day
                cal_activity_filter = "All Activities"
            range_start_ts = pd.Timestamp(range_start_day)
            range_end_ts = pd.Timestamp(range_end_day)
            grid_start = range_start_ts - pd.Timedelta(days=int(range_start_ts.weekday()))
            grid_end = range_end_ts + pd.Timedelta(days=int(6 - range_end_ts.weekday()))

            calendar_specificity_profile = _normalize_specificity_profile(
                st.session_state.get("user_specificity_profile", {}),
                fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
            )
            cal_metrics, cal_daily = cached_filtered_views(
                calendar_metrics_df,
                activity_filter=cal_activity_filter,
                specificity_profile=calendar_specificity_profile,
                daily_tss_target=float(derived_daily_tss_target),
            )
            cal_metrics = cal_metrics.copy()
            cal_metrics["start_local"] = _to_local_naive(cal_metrics["start_time_utc"])
            cal_metrics = cal_metrics.dropna(subset=["start_local"]).copy()
            cal_metrics["day"] = cal_metrics["start_local"].dt.floor("D")
            cal_metrics = cal_metrics[
                (cal_metrics["start_local"] >= grid_start)
                & (cal_metrics["start_local"] < (grid_end + pd.Timedelta(days=1)))
            ].copy()
            cal_metrics["duration_s"] = pd.to_numeric(cal_metrics.get("duration_s"), errors="coerce").fillna(0.0)
            cal_metrics["avg_hr"] = pd.to_numeric(cal_metrics.get("avg_hr"), errors="coerce")
            cal_metrics["if_proxy"] = pd.to_numeric(cal_metrics.get("if_proxy"), errors="coerce").fillna(0.0)
            cal_metrics["tss"] = pd.to_numeric(cal_metrics.get("tss"), errors="coerce").fillna(0.0)
            cal_metrics["rtss"] = pd.to_numeric(cal_metrics.get("rtss"), errors="coerce").fillna(0.0)
            cal_metrics["distance_km"] = pd.to_numeric(cal_metrics.get("distance_m"), errors="coerce").fillna(0.0) / 1000.0
            cal_metrics["distance_proxy_km"] = pd.to_numeric(
                cal_metrics.get("distance_proxy_km"), errors="coerce"
            ).fillna(0.0)
            cal_metrics["calories_total"] = pd.to_numeric(
                cal_metrics.get("calories_total"), errors="coerce"
            ).fillna(0.0)
            split_rows_df = get_activity_splits_df(cfg.db_path)
            split_lookup: dict[str, dict] = {}
            if not split_rows_df.empty:
                split_lookup = {
                    str(r.get("activity_id")): r
                    for r in split_rows_df.to_dict(orient="records")
                    if r.get("activity_id") is not None
                }

            sport = cal_metrics["sport_type"].fillna("").astype(str).str.lower()
            is_running_like = sport.str.contains("run") | sport.str.contains("treadmill")
            cal_metrics.loc[~is_running_like, "distance_km"] = 0.0
            cal_metrics["if_weighted"] = cal_metrics["if_proxy"] * cal_metrics["duration_s"]
            day_activity_stats = (
                cal_metrics.groupby("day", as_index=False)
                .agg(
                    day_calories=("calories_total", "sum"),
                    day_distance_eqv_km=("distance_proxy_km", "sum"),
                    day_tss=("tss", "sum"),
                    day_rtss=("rtss", "sum"),
                    day_duration_s=("duration_s", "sum"),
                    day_if_weighted=("if_weighted", "sum"),
                )
                .sort_values("day")
            )
            planned_cards_by_day: dict[pd.Timestamp, list[dict[str, object]]] = {}
            planned_day_lookup = pd.DataFrame(
                columns=["day", "planned_distance_eqv_km", "planned_tss", "planned_rtss", "planned_duration_s", "planned_if"]
            )
            planned_rows_metrics_all = pd.DataFrame()
            planned_rows_for_calendar = get_planned_activities_df(
                cfg.db_path,
                start_day_utc=grid_start.date().isoformat(),
                end_day_utc=grid_end.date().isoformat(),
            )
            today_local_day = pd.Timestamp(datetime.now().astimezone().date()).normalize()
            planned_rows_for_calendar = _apply_planned_actual_matching(
                planned_rows_for_calendar,
                metrics_df,
            )
            if not planned_rows_for_calendar.empty:
                weekly_profile_key = tuple(
                    sorted((str(k), float(v)) for k, v in calendar_specificity_profile.items())
                )
                weekly_planned_metrics_cache_key = (
                    "weekly_planned_metrics_v1",
                    str(planned_activities_cache_key),
                    str(grid_start.date()),
                    str(grid_end.date()),
                    _curve_points_cache_key(lthr_curve_points),
                    float(derived_lthr_bpm),
                    _curve_points_cache_key(lt_pace_curve_points),
                    float(derived_threshold_pace_sec),
                    weekly_profile_key,
                )
                if (
                    st.session_state.get("_weekly_planned_metrics_cache_key") == weekly_planned_metrics_cache_key
                    and isinstance(st.session_state.get("_weekly_planned_metrics_cache_value"), pd.DataFrame)
                ):
                    planned_rows_metrics_all = st.session_state["_weekly_planned_metrics_cache_value"].copy()
                else:
                    planned_rows_metrics_all = _compute_planned_rows_metrics_df(
                        planned_rows=planned_rows_for_calendar,
                        lthr_curve_points=lthr_curve_points,
                        lthr_default_bpm=float(derived_lthr_bpm),
                        lt_pace_curve_points=lt_pace_curve_points,
                        lt_pace_default_sec=float(derived_threshold_pace_sec),
                        specificity_profile=calendar_specificity_profile,
                    )
                    st.session_state["_weekly_planned_metrics_cache_key"] = weekly_planned_metrics_cache_key
                    st.session_state["_weekly_planned_metrics_cache_value"] = planned_rows_metrics_all.copy()
                planned_rows_for_calendar = _filter_effective_planned_rows(
                    planned_rows_metrics_all,
                    today_local_day=today_local_day,
                )
                planned_rows_for_calendar = filter_by_activity_type(
                    planned_rows_for_calendar,
                    cal_activity_filter,
                )
                if not planned_rows_for_calendar.empty:
                    planned_rows_for_calendar["day"] = pd.to_datetime(
                        planned_rows_for_calendar["day_utc"], errors="coerce"
                    ).dt.floor("D")
                    planned_rows_for_calendar = planned_rows_for_calendar.dropna(subset=["day"]).sort_values(
                        ["day", "line_no"], ascending=[True, True]
                    )
                    planned_grouped = (
                        planned_rows_for_calendar.groupby("day", as_index=False)
                        .agg(
                            planned_distance_eqv_km=("distance_proxy_km", "sum"),
                            planned_tss=("tss", "sum"),
                            planned_rtss=("rtss", "sum"),
                            planned_duration_s=("duration_s", "sum"),
                            planned_if_weighted=("if_weighted", "sum"),
                        )
                        .sort_values("day")
                    )
                    planned_grouped["planned_if"] = 0.0
                    _planned_dur = pd.to_numeric(planned_grouped["planned_duration_s"], errors="coerce").fillna(0.0)
                    _planned_w = pd.to_numeric(planned_grouped["planned_if_weighted"], errors="coerce").fillna(0.0)
                    _planned_mask = _planned_dur > 0
                    planned_grouped.loc[_planned_mask, "planned_if"] = _planned_w[_planned_mask] / _planned_dur[_planned_mask]
                    planned_day_lookup = planned_grouped[
                        ["day", "planned_distance_eqv_km", "planned_tss", "planned_rtss", "planned_duration_s", "planned_if"]
                    ].copy()
                    for day_key, grp in planned_rows_for_calendar.groupby("day"):
                        planned_cards_by_day[pd.Timestamp(day_key)] = grp.to_dict(orient="records")

            cal_daily_lookup = pd.DataFrame()
            if not cal_daily.empty:
                cal_daily_lookup = cal_daily.copy()
                cal_daily_lookup["day"] = pd.to_datetime(cal_daily_lookup["day_utc"], errors="coerce")
                cal_daily_lookup = cal_daily_lookup.dropna(subset=["day"]).sort_values("day")
                cal_daily_lookup["fitness"] = pd.to_numeric(cal_daily_lookup.get("fitness"), errors="coerce")
                cal_daily_lookup["fatigue"] = pd.to_numeric(cal_daily_lookup.get("fatigue"), errors="coerce")
                cal_daily_lookup["overreach"] = pd.to_numeric(cal_daily_lookup.get("overreach"), errors="coerce")
                cal_daily_lookup["injury_risk"] = pd.to_numeric(cal_daily_lookup.get("injury_risk"), errors="coerce")
                cal_daily_lookup = cal_daily_lookup[["day", "fitness", "fatigue", "overreach", "injury_risk"]]
            daily_fitfat_lookup = {}
            if not cal_daily_lookup.empty:
                daily_fitfat_lookup = (
                    cal_daily_lookup.drop_duplicates(subset=["day"], keep="last")
                    .set_index("day")[["fitness", "fatigue"]]
                    .to_dict("index")
                )
            # Project future Fit/Fatigue from planned daily TSS using same EMA recurrence
            # as dashboard metrics (Fitness=EMA42, Fatigue=EMA7).
            daily_fitfat_with_projection = dict(daily_fitfat_lookup)
            if (not cal_daily_lookup.empty) and (not planned_day_lookup.empty):
                hist = (
                    cal_daily_lookup.dropna(subset=["day"])
                    .drop_duplicates(subset=["day"], keep="last")
                    .sort_values("day")
                )
                if not hist.empty:
                    last_hist = hist.iloc[-1]
                    last_day = pd.to_datetime(last_hist.get("day"), errors="coerce")
                    prev_fit = pd.to_numeric(pd.Series([last_hist.get("fitness")]), errors="coerce").fillna(0.0).iloc[0]
                    prev_fat = pd.to_numeric(pd.Series([last_hist.get("fatigue")]), errors="coerce").fillna(0.0).iloc[0]
                    if pd.notna(last_day):
                        planned_by_day = planned_day_lookup.copy()
                        planned_by_day["day"] = pd.to_datetime(planned_by_day.get("day"), errors="coerce")
                        planned_by_day["planned_tss"] = pd.to_numeric(
                            planned_by_day.get("planned_tss"), errors="coerce"
                        ).fillna(0.0)
                        planned_by_day = planned_by_day.dropna(subset=["day"])
                        if not planned_by_day.empty:
                            planned_tss_map = (
                                planned_by_day.groupby("day", as_index=False)["planned_tss"]
                                .sum()
                                .set_index("day")["planned_tss"]
                                .to_dict()
                            )
                            alpha_fit = float(ema_alpha_from_days(42))
                            alpha_fat = float(ema_alpha_from_days(7))
                            max_planned_day = max(planned_tss_map.keys())
                            cursor = pd.Timestamp(last_day) + pd.Timedelta(days=1)
                            horizon = max(pd.Timestamp(max_planned_day), pd.Timestamp(grid_end))
                            while cursor <= horizon:
                                tss_v = float(planned_tss_map.get(cursor, 0.0))
                                prev_fit = alpha_fit * tss_v + (1.0 - alpha_fit) * prev_fit
                                prev_fat = alpha_fat * tss_v + (1.0 - alpha_fat) * prev_fat
                                daily_fitfat_with_projection[pd.Timestamp(cursor)] = {
                                    "fitness": prev_fit,
                                    "fatigue": prev_fat,
                                }
                                cursor = cursor + pd.Timedelta(days=1)

            wellness_day_lookup = pd.DataFrame(columns=["day", "resting_hr", "stress_avg"])
            wellness_df = get_wellness_df(cfg.db_path)
            if not wellness_df.empty:
                wellness_day_lookup = wellness_df.copy()
                wellness_day_lookup["day"] = pd.to_datetime(
                    wellness_day_lookup.get("day_utc"), errors="coerce"
                )
                wellness_day_lookup["resting_hr"] = pd.to_numeric(
                    wellness_day_lookup.get("resting_hr"), errors="coerce"
                )
                wellness_day_lookup["stress_avg"] = pd.to_numeric(
                    wellness_day_lookup.get("stress_avg"), errors="coerce"
                )
                wellness_day_lookup = (
                    wellness_day_lookup.dropna(subset=["day"])
                    .sort_values("day")
                    .drop_duplicates(subset=["day"], keep="last")[["day", "resting_hr", "stress_avg"]]
                )

            st.markdown(
                """
                <style>
                .cal-week-summary {
                    background: rgba(148,163,184,0.10);
                    border: 1px solid rgba(148,163,184,0.24);
                    border-radius: 12px;
                    padding: 10px 12px;
                    margin-bottom: 8px;
                    font-size: 0.90rem;
                    line-height: 1.35;
                }
                .cal-day-header {
                    font-size: 0.82rem;
                    color: rgba(226,232,240,0.86);
                    margin-bottom: 6px;
                    font-weight: 600;
                }
                .cal-day-meta {
                    margin-bottom: 6px;
                    min-height: 32px;
                    max-height: 32px;
                    overflow: hidden;
                    line-height: 1.2;
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                }
                .cal-day-muted { opacity: 0.45; }
                .cal-card {
                    background: rgba(15,23,42,0.78);
                    border: 1px solid rgba(148,163,184,0.26);
                    border-radius: 10px;
                    padding: 8px 10px;
                    margin-bottom: 8px;
                }
                div[data-testid="stButton"] > button[kind="tertiary"],
                div[data-testid="stButton"] > button[kind="tertiary"]:hover,
                div[data-testid="stButton"] > button[kind="tertiary"]:focus,
                div[data-testid="stButton"] > button[kind="tertiary"]:focus-visible,
                div[data-testid="stButton"] > button[kind="tertiary"]:active {
                    background: rgba(15,23,42,0.78);
                    border: 1px solid rgba(148,163,184,0.26);
                    border-radius: 10px;
                    color: rgba(226,232,240,0.80);
                    text-align: left;
                    white-space: pre-line;
                    line-height: 1.12;
                    min-height: 78px;
                    padding: 7px 8px;
                    font-weight: 400;
                    letter-spacing: 0;
                    box-shadow: none !important;
                    transform: none !important;
                    transition: none !important;
                }
                div[data-testid="stButton"] > button[kind="tertiary"] p,
                div[data-testid="stButton"] > button[kind="tertiary"] span,
                div[data-testid="stButton"] > button[kind="tertiary"] div {
                    font-size: 0.8rem !important;
                    line-height: 1.12 !important;
                    font-weight: 400 !important;
                }
                div[class*="st-key-calendar_split_title_if_green_"] button[kind="tertiary"],
                div[class*="st-key-calendar_split_title_if_green_"] button[kind="tertiary"]:hover,
                div[class*="st-key-calendar_split_title_if_green_"] button[kind="tertiary"]:focus,
                div[class*="st-key-calendar_split_title_if_green_"] button[kind="tertiary"]:focus-visible,
                div[class*="st-key-calendar_split_title_if_green_"] button[kind="tertiary"]:active {
                    border: 2px solid rgba(156,163,175,0.96) !important;
                    background: rgba(15,23,42,0.78) !important;
                }
                div[class*="st-key-calendar_split_title_if_green_"] button[kind="tertiary"] strong {
                    color: rgba(156,163,175,0.96) !important;
                    font-weight: 700 !important;
                }
                div[class*="st-key-calendar_split_title_if_blue_"] button[kind="tertiary"],
                div[class*="st-key-calendar_split_title_if_blue_"] button[kind="tertiary"]:hover,
                div[class*="st-key-calendar_split_title_if_blue_"] button[kind="tertiary"]:focus,
                div[class*="st-key-calendar_split_title_if_blue_"] button[kind="tertiary"]:focus-visible,
                div[class*="st-key-calendar_split_title_if_blue_"] button[kind="tertiary"]:active {
                    border: 2px solid rgba(56,189,248,0.96) !important;
                    background: rgba(15,23,42,0.78) !important;
                }
                div[class*="st-key-calendar_split_title_if_blue_"] button[kind="tertiary"] strong {
                    color: rgba(56,189,248,0.96) !important;
                    font-weight: 700 !important;
                }
                div[class*="st-key-calendar_split_title_if_yellow_"] button[kind="tertiary"],
                div[class*="st-key-calendar_split_title_if_yellow_"] button[kind="tertiary"]:hover,
                div[class*="st-key-calendar_split_title_if_yellow_"] button[kind="tertiary"]:focus,
                div[class*="st-key-calendar_split_title_if_yellow_"] button[kind="tertiary"]:focus-visible,
                div[class*="st-key-calendar_split_title_if_yellow_"] button[kind="tertiary"]:active {
                    border: 2px solid rgba(251,191,36,0.96) !important;
                    background: rgba(15,23,42,0.78) !important;
                }
                div[class*="st-key-calendar_split_title_if_yellow_"] button[kind="tertiary"] strong {
                    color: rgba(251,191,36,0.96) !important;
                    font-weight: 700 !important;
                }
                div[class*="st-key-calendar_split_title_if_red_"] button[kind="tertiary"],
                div[class*="st-key-calendar_split_title_if_red_"] button[kind="tertiary"]:hover,
                div[class*="st-key-calendar_split_title_if_red_"] button[kind="tertiary"]:focus,
                div[class*="st-key-calendar_split_title_if_red_"] button[kind="tertiary"]:focus-visible,
                div[class*="st-key-calendar_split_title_if_red_"] button[kind="tertiary"]:active {
                    border: 2px solid rgba(251,113,133,0.96) !important;
                    background: rgba(15,23,42,0.78) !important;
                }
                div[class*="st-key-calendar_split_title_if_red_"] button[kind="tertiary"] strong {
                    color: rgba(251,113,133,0.96) !important;
                    font-weight: 700 !important;
                }
                div[class*="st-key-calendar_split_title_if_orange_"] button[kind="tertiary"],
                div[class*="st-key-calendar_split_title_if_orange_"] button[kind="tertiary"]:hover,
                div[class*="st-key-calendar_split_title_if_orange_"] button[kind="tertiary"]:focus,
                div[class*="st-key-calendar_split_title_if_orange_"] button[kind="tertiary"]:focus-visible,
                div[class*="st-key-calendar_split_title_if_orange_"] button[kind="tertiary"]:active {
                    border: 2px solid rgba(249,115,22,0.96) !important;
                    background: rgba(15,23,42,0.78) !important;
                }
                div[class*="st-key-calendar_split_title_if_orange_"] button[kind="tertiary"] strong {
                    color: rgba(249,115,22,0.96) !important;
                    font-weight: 700 !important;
                }
                div[class*="st-key-calendar_split_title_if_tss_orange_"] button[kind="tertiary"],
                div[class*="st-key-calendar_split_title_if_tss_orange_"] button[kind="tertiary"]:hover,
                div[class*="st-key-calendar_split_title_if_tss_orange_"] button[kind="tertiary"]:focus,
                div[class*="st-key-calendar_split_title_if_tss_orange_"] button[kind="tertiary"]:focus-visible,
                div[class*="st-key-calendar_split_title_if_tss_orange_"] button[kind="tertiary"]:active {
                    border: 2px solid rgba(251,146,60,0.96) !important;
                    background: rgba(15,23,42,0.78) !important;
                }
                div[class*="st-key-calendar_split_title_if_tss_orange_"] button[kind="tertiary"] strong {
                    color: rgba(251,146,60,0.96) !important;
                    font-weight: 700 !important;
                }
                div[class*="st-key-calendar_split_title_if_purple_"] button[kind="tertiary"],
                div[class*="st-key-calendar_split_title_if_purple_"] button[kind="tertiary"]:hover,
                div[class*="st-key-calendar_split_title_if_purple_"] button[kind="tertiary"]:focus,
                div[class*="st-key-calendar_split_title_if_purple_"] button[kind="tertiary"]:focus-visible,
                div[class*="st-key-calendar_split_title_if_purple_"] button[kind="tertiary"]:active {
                    border: 2px solid rgba(168,85,247,0.96) !important;
                    background: rgba(15,23,42,0.78) !important;
                }
                div[class*="st-key-calendar_split_title_if_purple_"] button[kind="tertiary"] strong {
                    color: rgba(168,85,247,0.96) !important;
                    font-weight: 700 !important;
                }
                div[class*="st-key-calendar_split_title_if_tss_purple_"] button[kind="tertiary"],
                div[class*="st-key-calendar_split_title_if_tss_purple_"] button[kind="tertiary"]:hover,
                div[class*="st-key-calendar_split_title_if_tss_purple_"] button[kind="tertiary"]:focus,
                div[class*="st-key-calendar_split_title_if_tss_purple_"] button[kind="tertiary"]:focus-visible,
                div[class*="st-key-calendar_split_title_if_tss_purple_"] button[kind="tertiary"]:active {
                    border: 2px solid rgba(192,132,252,0.96) !important;
                    background: rgba(15,23,42,0.78) !important;
                }
                div[class*="st-key-calendar_split_title_if_tss_purple_"] button[kind="tertiary"] strong {
                    color: rgba(192,132,252,0.96) !important;
                    font-weight: 700 !important;
                }
                .cal-card-title {
                    font-size: 0.78rem;
                    font-weight: 700;
                    color: rgba(226,232,240,0.94);
                    margin-bottom: 3px;
                }
                .cal-card-meta {
                    font-size: 0.76rem;
                    color: rgba(226,232,240,0.80);
                }
                .cal-card-load {
                    font-size: 0.74rem;
                    color: rgba(148,163,184,0.94);
                    margin-top: 2px;
                }
                .cal-card-placeholder {
                    min-height: 98px;
                    opacity: 0.0;
                    pointer-events: none;
                }
                .cal-rest-card {
                    background: rgba(15,23,42,0.60);
                    border: 1px dashed rgba(148,163,184,0.35);
                    border-radius: 10px;
                    padding: 10px 10px;
                    margin-bottom: 8px;
                    min-height: 78px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    gap: 4px;
                }
                .cal-rest-title {
                    font-size: 0.78rem;
                    font-weight: 700;
                    color: rgba(226,232,240,0.92);
                }
                .cal-rest-sub {
                    font-size: 0.72rem;
                    color: rgba(148,163,184,0.92);
                    line-height: 1.2;
                }
                .cal-planned-card {
                    background: rgba(15, 23, 42, 0.50);
                    border: 1px dashed rgba(52, 211, 153, 0.42);
                    border-radius: 10px;
                    padding: 8px 10px;
                    margin-bottom: 8px;
                    min-height: 78px;
                }
                .cal-planned-title {
                    font-size: 0.78rem;
                    font-weight: 700;
                    color: rgba(167,243,208,0.95);
                    margin-bottom: 3px;
                }
                .cal-planned-meta {
                    font-size: 0.74rem;
                    color: rgba(226,232,240,0.82);
                    line-height: 1.15;
                }
                div[data-testid="stButton"] > button[kind="primary"],
                div[data-testid="stButton"] > button[kind="primary"]:hover,
                div[data-testid="stButton"] > button[kind="primary"]:focus,
                div[data-testid="stButton"] > button[kind="primary"]:focus-visible,
                div[data-testid="stButton"] > button[kind="primary"]:active {
                    background: rgba(15,23,42,0.50);
                    border: 1px dashed rgba(156,163,175,0.42);
                    border-radius: 10px;
                    color: rgba(226,232,240,0.90);
                    text-align: left;
                    white-space: pre-line;
                    line-height: 1.12;
                    min-height: 78px;
                    padding: 7px 8px;
                    font-weight: 400;
                    letter-spacing: 0;
                    box-shadow: none !important;
                    transform: none !important;
                    transition: none !important;
                }
                div[data-testid="stButton"] > button[kind="primary"] p,
                div[data-testid="stButton"] > button[kind="primary"] span,
                div[data-testid="stButton"] > button[kind="primary"] div {
                    font-size: 0.8rem !important;
                    line-height: 1.12 !important;
                    color: rgba(226,232,240,0.90) !important;
                    font-weight: 400 !important;
                }
                div[data-testid="stButton"] > button[kind="primary"] strong {
                    color: rgba(203,213,225,0.95) !important;
                    font-weight: 700 !important;
                }
                div[class*="st-key-calendar_planned_done_if_green_"] button[kind="primary"],
                div[class*="st-key-calendar_planned_done_if_green_"] button[kind="primary"]:hover,
                div[class*="st-key-calendar_planned_done_if_green_"] button[kind="primary"]:focus,
                div[class*="st-key-calendar_planned_done_if_green_"] button[kind="primary"]:focus-visible,
                div[class*="st-key-calendar_planned_done_if_green_"] button[kind="primary"]:active {
                    border: 1px dashed rgba(156,163,175,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_green_"] button[kind="primary"] strong {
                    color: rgba(156,163,175,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_blue_"] button[kind="primary"],
                div[class*="st-key-calendar_planned_done_if_blue_"] button[kind="primary"]:hover,
                div[class*="st-key-calendar_planned_done_if_blue_"] button[kind="primary"]:focus,
                div[class*="st-key-calendar_planned_done_if_blue_"] button[kind="primary"]:focus-visible,
                div[class*="st-key-calendar_planned_done_if_blue_"] button[kind="primary"]:active {
                    border: 1px dashed rgba(56,189,248,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_blue_"] button[kind="primary"] strong {
                    color: rgba(56,189,248,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_yellow_"] button[kind="primary"],
                div[class*="st-key-calendar_planned_done_if_yellow_"] button[kind="primary"]:hover,
                div[class*="st-key-calendar_planned_done_if_yellow_"] button[kind="primary"]:focus,
                div[class*="st-key-calendar_planned_done_if_yellow_"] button[kind="primary"]:focus-visible,
                div[class*="st-key-calendar_planned_done_if_yellow_"] button[kind="primary"]:active {
                    border: 1px dashed rgba(251,191,36,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_yellow_"] button[kind="primary"] strong {
                    color: rgba(251,191,36,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_red_"] button[kind="primary"],
                div[class*="st-key-calendar_planned_done_if_red_"] button[kind="primary"]:hover,
                div[class*="st-key-calendar_planned_done_if_red_"] button[kind="primary"]:focus,
                div[class*="st-key-calendar_planned_done_if_red_"] button[kind="primary"]:focus-visible,
                div[class*="st-key-calendar_planned_done_if_red_"] button[kind="primary"]:active {
                    border: 1px dashed rgba(251,113,133,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_red_"] button[kind="primary"] strong {
                    color: rgba(251,113,133,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_orange_"] button[kind="primary"],
                div[class*="st-key-calendar_planned_done_if_orange_"] button[kind="primary"]:hover,
                div[class*="st-key-calendar_planned_done_if_orange_"] button[kind="primary"]:focus,
                div[class*="st-key-calendar_planned_done_if_orange_"] button[kind="primary"]:focus-visible,
                div[class*="st-key-calendar_planned_done_if_orange_"] button[kind="primary"]:active {
                    border: 1px dashed rgba(249,115,22,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_orange_"] button[kind="primary"] strong {
                    color: rgba(249,115,22,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_tss_orange_"] button[kind="primary"],
                div[class*="st-key-calendar_planned_done_if_tss_orange_"] button[kind="primary"]:hover,
                div[class*="st-key-calendar_planned_done_if_tss_orange_"] button[kind="primary"]:focus,
                div[class*="st-key-calendar_planned_done_if_tss_orange_"] button[kind="primary"]:focus-visible,
                div[class*="st-key-calendar_planned_done_if_tss_orange_"] button[kind="primary"]:active {
                    border: 1px dashed rgba(251,146,60,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_tss_orange_"] button[kind="primary"] strong {
                    color: rgba(251,146,60,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_purple_"] button[kind="primary"],
                div[class*="st-key-calendar_planned_done_if_purple_"] button[kind="primary"]:hover,
                div[class*="st-key-calendar_planned_done_if_purple_"] button[kind="primary"]:focus,
                div[class*="st-key-calendar_planned_done_if_purple_"] button[kind="primary"]:focus-visible,
                div[class*="st-key-calendar_planned_done_if_purple_"] button[kind="primary"]:active {
                    border: 1px dashed rgba(168,85,247,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_purple_"] button[kind="primary"] strong {
                    color: rgba(168,85,247,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_tss_purple_"] button[kind="primary"],
                div[class*="st-key-calendar_planned_done_if_tss_purple_"] button[kind="primary"]:hover,
                div[class*="st-key-calendar_planned_done_if_tss_purple_"] button[kind="primary"]:focus,
                div[class*="st-key-calendar_planned_done_if_tss_purple_"] button[kind="primary"]:focus-visible,
                div[class*="st-key-calendar_planned_done_if_tss_purple_"] button[kind="primary"]:active {
                    border: 1px dashed rgba(192,132,252,0.96) !important;
                }
                div[class*="st-key-calendar_planned_done_if_tss_purple_"] button[kind="primary"] strong {
                    color: rgba(192,132,252,0.96) !important;
                }
                div[class*="st-key-calendar_split_table_v4"] [role="columnheader"] {
                    font-weight: 700 !important;
                    color: rgba(226,232,240,0.96) !important;
                }
                .cal-zones {
                    margin-top: 8px;
                    padding-top: 8px;
                    border-top: 1px solid rgba(148,163,184,0.22);
                }
                .cal-zone-row {
                    display: grid;
                    grid-template-columns: 18px 1fr 54px 40px;
                    gap: 6px;
                    align-items: center;
                    margin-top: 4px;
                    font-size: 0.72rem;
                    color: rgba(226,232,240,0.90);
                }
                .cal-zone-track {
                    height: 10px;
                    border-radius: 999px;
                    background: rgba(148,163,184,0.22);
                    overflow: hidden;
                }
                .cal-zone-fill {
                    height: 100%;
                    border-radius: 999px;
                }
                .compact-week-shell {
                    border: none;
                    border-radius: 0;
                    padding: 0;
                    background: transparent;
                    margin-bottom: 2px;
                }
                .compact-metric-card {
                    border: 1px solid rgba(148, 163, 184, 0.24);
                    border-radius: 12px;
                    padding: 8px 10px;
                    min-height: 76px;
                    background: rgba(15, 23, 42, 0.72);
                }
                .compact-metric-card.selected {
                    border-color: rgba(52, 211, 153, 0.72);
                    box-shadow: inset 0 0 0 1px rgba(52, 211, 153, 0.18);
                    background: rgba(16, 185, 129, 0.10);
                }
                .compact-metric-title {
                    font-size: 0.74rem;
                    color: rgba(148, 163, 184, 0.95);
                    line-height: 1.2;
                }
                .compact-metric-value {
                    margin-top: 5px;
                    font-size: 1.15rem;
                    font-weight: 700;
                    color: rgba(241, 245, 249, 0.96);
                    line-height: 1.1;
                }
                @media (max-width: 768px) {
                    .block-container {
                        padding-top: 0.35rem !important;
                        padding-left: 0.55rem !important;
                        padding-right: 0.55rem !important;
                        max-width: 100% !important;
                    }
                    .compact-week-shell {
                        padding: 0;
                        border-radius: 0;
                    }
                    .compact-week-title {
                        margin: -6px 0 6px 0 !important;
                        font-size: 1.15rem !important;
                        line-height: 1.15 !important;
                    }
                    .compact-week-narrative {
                        margin: 0 0 2px 0 !important;
                        padding: 8px 10px !important;
                        border-radius: 8px !important;
                        font-size: 0.86rem !important;
                        line-height: 1.3 !important;
                    }
                    [class*="st-key-compact_mobile_nav_row"] {
                        width: 100% !important;
                        overflow-x: auto !important;
                        padding-bottom: 2px !important;
                    }
                    [class*="st-key-compact_mobile_nav_row"] [data-testid="stHorizontalBlock"] {
                        align-items: center !important;
                        column-gap: 0.16rem !important;
                    }
                    [class*="st-key-compact_prev_week"] button,
                    [class*="st-key-compact_next_week"] button {
                        width: 34px !important;
                        min-width: 34px !important;
                        max-width: 34px !important;
                        min-height: 28px !important;
                        height: 28px !important;
                        border-radius: 6px !important;
                        border: 1px solid rgba(71,85,105,0.78) !important;
                        background: rgba(15,23,42,0.42) !important;
                        padding: 0 !important;
                        font-size: 0.86rem !important;
                        line-height: 1 !important;
                    }
                    [class*="st-key-calendar_compact_compare_choice"],
                    [class*="st-key-calendar_compact_metric"] {
                        min-width: 0 !important;
                        width: auto !important;
                        max-width: 100% !important;
                    }
                    [class*="st-key-calendar_compact_compare_choice"] [data-baseweb="select"],
                    [class*="st-key-calendar_compact_metric"] [data-baseweb="select"] {
                        min-width: 0 !important;
                        max-width: 100% !important;
                    }
                    [class*="st-key-calendar_compact_compare_choice"] [data-baseweb="select"] > div,
                    [class*="st-key-calendar_compact_metric"] [data-baseweb="select"] > div {
                        min-width: 0 !important;
                        min-height: 28px !important;
                        height: 28px !important;
                        border-radius: 6px !important;
                        border: 1px solid rgba(71,85,105,0.78) !important;
                        background: rgba(15,23,42,0.42) !important;
                        padding: 0.04rem 0.32rem 0.04rem 0.28rem !important;
                        font-size: 0.74rem !important;
                        line-height: 1 !important;
                    }
                    [class*="st-key-calendar_compact_compare_choice"] [data-baseweb="select"] > div > div,
                    [class*="st-key-calendar_compact_metric"] [data-baseweb="select"] > div > div {
                        min-width: 0 !important;
                        overflow: hidden !important;
                        text-overflow: ellipsis !important;
                        white-space: nowrap !important;
                        line-height: 1 !important;
                    }
                    div[data-testid="stHorizontalBlock"]:has(.cal-week-summary) {
                        flex-direction: column !important;
                        align-items: stretch !important;
                        gap: 0.55rem !important;
                    }
                    div[data-testid="stHorizontalBlock"]:has(.cal-week-summary) > div[data-testid="column"] {
                        width: 100% !important;
                        min-width: 100% !important;
                        flex: 1 1 100% !important;
                    }
                    .cal-week-summary {
                        margin-bottom: 2px;
                        padding: 10px 12px;
                    }
                    .cal-day-header {
                        margin-top: 6px;
                        margin-bottom: 4px;
                        font-size: 0.96rem;
                    }
                    .cal-day-meta {
                        min-height: 0;
                        max-height: none;
                        margin-bottom: 6px;
                        -webkit-line-clamp: unset;
                    }
                }
                @media (max-width: 768px) and (orientation: portrait) {
                    [class*="st-key-compact_mobile_nav_row"] [data-testid="stHorizontalBlock"] {
                        column-gap: 0.14rem !important;
                    }
                }
                @media (max-width: 768px) and (orientation: landscape) {
                    [class*="st-key-compact_mobile_nav_row"] [data-testid="stHorizontalBlock"] {
                        column-gap: 0.20rem !important;
                    }
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            compact_mode = view == "Weekly Summary"

            if compact_mode:
                latest_day = pd.to_datetime(cal_metrics["day"], errors="coerce").max()
                if pd.isna(latest_day):
                    st.info("No activities available for compact view.")
                    st.stop()
                latest_week_start = latest_day - pd.Timedelta(days=int(latest_day.weekday()))
                if "calendar_compact_week_start" not in st.session_state:
                    st.session_state["calendar_compact_week_start"] = default_week_start
                selected_week_start = pd.to_datetime(
                    st.session_state.get("calendar_compact_week_start"), errors="coerce"
                )
                if pd.isna(selected_week_start):
                    selected_week_start = default_week_start
                selected_week_start = selected_week_start - pd.Timedelta(days=int(selected_week_start.weekday()))
                if selected_week_start < min_week_start:
                    selected_week_start = min_week_start
                if selected_week_start > max_week_start:
                    selected_week_start = max_week_start
                st.session_state["calendar_compact_week_start"] = selected_week_start
                selected_week_end = selected_week_start + pd.Timedelta(days=6)
                compare_choice = str(st.session_state.get("calendar_compact_compare_choice", "Planned"))
                if selected_week_start > latest_week_start and compare_choice == "Planned":
                    compare_choice = "Previous week"
                    st.session_state["calendar_compact_compare_choice"] = compare_choice

                st.markdown(
                    (
                        "<div class='compact-week-title' style='margin:-10px 0 8px 0;font-size:2rem;font-weight:700;"
                        "line-height:1.2;color:rgba(248,250,252,0.98);'>"
                        f"{selected_week_start:%B %-d} - {selected_week_end:%-d}"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
                compact_metric_keys = ["rtss", "tss", "distance_eqv_km"]
                compact_metric_labels = {
                    "rtss": "rTSS",
                    "tss": "TSS",
                    "distance_eqv_km": "Distance Eqv",
                }
                week_scope_for_selector = cal_metrics[
                    (cal_metrics["day"] >= selected_week_start)
                    & (cal_metrics["day"] <= selected_week_end)
                ].copy()
                metric_values_week = {
                    "rtss": float(pd.to_numeric(week_scope_for_selector.get("rtss"), errors="coerce").fillna(0.0).sum()),
                    "tss": float(pd.to_numeric(week_scope_for_selector.get("tss"), errors="coerce").fillna(0.0).sum()),
                    "distance_eqv_km": float(pd.to_numeric(week_scope_for_selector.get("distance_proxy_km"), errors="coerce").fillna(0.0).sum()),
                }
                if "calendar_compact_metric" not in st.session_state:
                    st.session_state["calendar_compact_metric"] = "tss"
                if str(st.session_state.get("calendar_compact_metric")) not in compact_metric_keys:
                    st.session_state["calendar_compact_metric"] = "tss"
                is_mobile_layout = _is_probably_mobile_client()
                # Keep one deterministic control layout across devices to avoid UA-dependent regressions.
                is_mobile_compact_ui = True
                active_compare_choice = str(st.session_state.get("calendar_compact_compare_choice", compare_choice))
                active_metric_choice = str(st.session_state.get("calendar_compact_metric", "tss"))

                if is_mobile_compact_ui:
                    compare_short = {
                        "Planned": "Plan",
                        "Previous week": "Prev-1w",
                        "2 weeks ago": "Prev-2w",
                        "3 weeks ago": "Prev-3w",
                        "4 weeks ago": "Prev-4w",
                    }
                    metric_short = {"rtss": "rTSS", "tss": "TSS", "distance_eqv_km": "Dist"}
                    # Backward-compatible support for older link-based mobile nav params.
                    _mobile_ctl_raw = st.query_params.get("compact_ctl")
                    if isinstance(_mobile_ctl_raw, (list, tuple)):
                        _mobile_ctl_raw = _mobile_ctl_raw[0] if _mobile_ctl_raw else ""
                    mobile_ctl = str(_mobile_ctl_raw or "").strip().lower()
                    if mobile_ctl == "prev":
                        st.session_state["calendar_compact_week_start"] = selected_week_start - pd.Timedelta(days=7)
                    elif mobile_ctl == "next":
                        st.session_state["calendar_compact_week_start"] = selected_week_start + pd.Timedelta(days=7)
                    if mobile_ctl in {"prev", "next"}:
                        try:
                            del st.query_params["compact_ctl"]
                        except Exception:
                            pass
                        st.rerun()
                    _mobile_compare_raw = st.query_params.get("compact_compare_idx")
                    if isinstance(_mobile_compare_raw, (list, tuple)):
                        _mobile_compare_raw = _mobile_compare_raw[0] if _mobile_compare_raw else ""
                    _mobile_compare_num = pd.to_numeric(_mobile_compare_raw, errors="coerce")
                    _mobile_compare_idx = int(_mobile_compare_num) if pd.notna(_mobile_compare_num) else -1
                    if 0 <= _mobile_compare_idx < len(compare_options):
                        st.session_state["calendar_compact_compare_choice"] = compare_options[_mobile_compare_idx]
                        try:
                            del st.query_params["compact_compare_idx"]
                        except Exception:
                            pass
                        st.rerun()

                    _mobile_metric_raw = st.query_params.get("compact_metric_key")
                    if isinstance(_mobile_metric_raw, (list, tuple)):
                        _mobile_metric_raw = _mobile_metric_raw[0] if _mobile_metric_raw else ""
                    _mobile_metric_key = str(_mobile_metric_raw or "").strip()
                    if _mobile_metric_key in compact_metric_keys:
                        st.session_state["calendar_compact_metric"] = _mobile_metric_key
                        try:
                            del st.query_params["compact_metric_key"]
                        except Exception:
                            pass
                        st.rerun()

                    current_compare = str(st.session_state.get("calendar_compact_compare_choice", compare_options[0]))
                    if current_compare not in compare_options:
                        current_compare = compare_options[0]
                        st.session_state["calendar_compact_compare_choice"] = current_compare
                    current_metric = str(st.session_state.get("calendar_compact_metric", compact_metric_keys[0]))
                    if current_metric not in compact_metric_keys:
                        current_metric = compact_metric_keys[0]
                        st.session_state["calendar_compact_metric"] = current_metric
                    active_compare_choice = current_compare
                    active_metric_choice = current_metric
                    compare_select_width = 96 if is_mobile_layout else 126
                    metric_select_width = 142 if is_mobile_layout else 186
                    with st.container(
                        key="compact_mobile_nav_row",
                        horizontal=True,
                        horizontal_alignment="left",
                        gap="small",
                    ):
                        if st.button("◀", key="compact_prev_week", width=34):
                            st.session_state["calendar_compact_week_start"] = selected_week_start - pd.Timedelta(days=7)
                            st.rerun()
                        if st.button("▶", key="compact_next_week", width=34):
                            st.session_state["calendar_compact_week_start"] = selected_week_start + pd.Timedelta(days=7)
                            st.rerun()
                        selected_compare_mobile = st.selectbox(
                            "Compare against",
                            compare_options,
                            key="calendar_compact_compare_choice",
                            label_visibility="collapsed",
                            format_func=lambda opt: compare_short.get(opt, opt),
                            width=compare_select_width,
                        )
                        active_compare_choice = str(selected_compare_mobile)
                        selected_metric_mobile = st.selectbox(
                            "Metric",
                            compact_metric_keys,
                            key="calendar_compact_metric",
                            label_visibility="collapsed",
                            format_func=lambda mk: (
                                f"{metric_short.get(mk, mk)} - {int(round(metric_values_week.get(mk, 0.0)))}"
                                + (" km" if mk == "distance_eqv_km" else "")
                            ),
                            width=metric_select_width,
                        )
                        active_metric_choice = str(selected_metric_mobile)
                else:
                    nav1, nav2, nav3, nav4, _nav_spacer = st.columns([0.75, 0.75, 1.0, 1.2, 0.8])
                    with nav1:
                        if st.button("◀ Prev week", key="compact_prev_week", use_container_width=True):
                            st.session_state["calendar_compact_week_start"] = selected_week_start - pd.Timedelta(days=7)
                            st.rerun()
                    with nav2:
                        if st.button("Next week ▶", key="compact_next_week", use_container_width=True):
                            st.session_state["calendar_compact_week_start"] = selected_week_start + pd.Timedelta(days=7)
                            st.rerun()
                    with nav3:
                        selected_compare_desktop = st.selectbox(
                            "Compare against",
                            compare_options,
                            key="calendar_compact_compare_choice",
                            label_visibility="collapsed",
                        )
                        active_compare_choice = str(selected_compare_desktop)
                    with nav4:
                        selected_metric_desktop = st.selectbox(
                            "Metric",
                            compact_metric_keys,
                            key="calendar_compact_metric",
                            label_visibility="collapsed",
                            format_func=lambda k: (
                                f"{compact_metric_labels.get(k, k)} - {int(round(metric_values_week.get(k, 0.0)))}"
                                + (" km" if k == "distance_eqv_km" else "")
                            ),
                        )
                        active_metric_choice = str(selected_metric_desktop)
                compare_choice = str(active_compare_choice or st.session_state.get("calendar_compact_compare_choice", compare_choice))
                compare_weeks = {
                    "Previous week": 1,
                    "2 weeks ago": 2,
                    "3 weeks ago": 3,
                    "4 weeks ago": 4,
                    "Planned": 1,
                }.get(compare_choice, 1)
                if compare_choice == "Planned":
                    # Planned compare is same selected week (actual vs plan in-week).
                    compare_week_start = selected_week_start
                    compare_week_end = selected_week_end
                else:
                    compare_week_start = selected_week_start - pd.Timedelta(days=7 * compare_weeks)
                    compare_week_end = compare_week_start + pd.Timedelta(days=6)

                compact_days = pd.DataFrame({"day": pd.date_range(selected_week_start, selected_week_end, freq="D")})
                _daily_perf = day_activity_stats.rename(
                    columns={
                        "day_distance_eqv_km": "distance_eqv_km",
                        "day_tss": "tss",
                        "day_rtss": "rtss",
                        "day_duration_s": "duration_s",
                        "day_if_weighted": "if_weighted",
                    }
                )
                compact_week = compact_days.merge(
                    _daily_perf[["day", "rtss", "tss", "distance_eqv_km", "duration_s", "if_weighted"]],
                    on="day",
                    how="left",
                )
                for col in ["rtss", "tss", "distance_eqv_km", "duration_s", "if_weighted"]:
                    compact_week[col] = pd.to_numeric(compact_week[col], errors="coerce").fillna(0.0)
                compact_week["if_proxy"] = 0.0
                _cw_dur = pd.to_numeric(compact_week["duration_s"], errors="coerce").fillna(0.0)
                _cw_w = pd.to_numeric(compact_week["if_weighted"], errors="coerce").fillna(0.0)
                _cw_mask = _cw_dur > 0
                compact_week.loc[_cw_mask, "if_proxy"] = _cw_w[_cw_mask] / _cw_dur[_cw_mask]
                compare_days = pd.DataFrame({"day": pd.date_range(compare_week_start, compare_week_end, freq="D")})
                planned_remaining_metric_totals = {"rtss": 0.0, "tss": 0.0, "distance_eqv_km": 0.0}
                planned_remaining_tss_by_day: dict[pd.Timestamp, float] = {}
                planned_rows_compare_source = pd.DataFrame()
                if compare_choice == "Planned":
                    # Use full precomputed planned metrics (not "effective" filtered rows),
                    # so planned-vs-actual compares against the full plan for the week.
                    planned_rows = planned_rows_metrics_all.copy() if "planned_rows_metrics_all" in locals() else pd.DataFrame()
                    today_local_now = pd.Timestamp(datetime.now().astimezone().date()).normalize()
                    if not planned_rows.empty:
                        planned_rows["day"] = pd.to_datetime(planned_rows.get("day_utc"), errors="coerce").dt.floor("D")
                        planned_rows = planned_rows.dropna(subset=["day"]).copy()
                        planned_rows = planned_rows[
                            (planned_rows["day"] >= selected_week_start) & (planned_rows["day"] <= selected_week_end)
                        ].copy()
                    planned_rows_compare_source = planned_rows.copy()
                    if not planned_rows.empty:
                        planned_daily = _build_planned_daily_summary_df(planned_rows)
                        planned_daily["day"] = pd.to_datetime(planned_daily.get("day_utc"), errors="coerce").dt.floor("D")
                        compare_agg = planned_daily.rename(
                            columns={
                                "rtss_total": "rtss",
                                "tss_total": "tss",
                                "distance_proxy_km": "distance_eqv_km",
                            }
                        )[["day", "rtss", "tss", "distance_eqv_km", "duration_s", "if_proxy"]]
                        compare_week = compare_days.merge(compare_agg, on="day", how="left")
                        for col in ["rtss", "tss", "distance_eqv_km", "duration_s", "if_proxy"]:
                            compare_week[col] = pd.to_numeric(compare_week[col], errors="coerce").fillna(0.0)

                        _planned_remaining_tss = compare_agg.dropna(subset=["day"])[["day", "tss"]].copy()
                        planned_remaining_tss_by_day = {
                            pd.Timestamp(r["day"]): float(pd.to_numeric(r["tss"], errors="coerce") or 0.0)
                            for _, r in _planned_remaining_tss.iterrows()
                        }

                        planned_rows_remaining = _filter_effective_planned_rows(planned_rows, today_local_day=today_local_now)
                        remaining_start_day = max(today_local_now, selected_week_start)
                        planned_rows_remaining = planned_rows_remaining[
                            (planned_rows_remaining["day"] >= remaining_start_day)
                            & (planned_rows_remaining["day"] <= selected_week_end)
                        ].copy()
                        planned_remaining_metric_totals = {
                            "rtss": float(
                                pd.to_numeric(planned_rows_remaining.get("rtss"), errors="coerce").fillna(0.0).sum()
                            ),
                            "tss": float(
                                pd.to_numeric(planned_rows_remaining.get("tss"), errors="coerce").fillna(0.0).sum()
                            ),
                            "distance_eqv_km": float(
                                pd.to_numeric(
                                    planned_rows_remaining.get("distance_proxy_km"), errors="coerce"
                                ).fillna(0.0).sum()
                            ),
                        }
                    else:
                        compare_week = compare_days.copy()
                        for col in ["rtss", "tss", "distance_eqv_km", "duration_s", "if_proxy"]:
                            compare_week[col] = 0.0
                else:
                    compare_week = compare_days.merge(
                        _daily_perf[["day", "rtss", "tss", "distance_eqv_km", "duration_s", "if_weighted"]],
                        on="day",
                        how="left",
                    )
                    for col in ["rtss", "tss", "distance_eqv_km", "duration_s", "if_weighted"]:
                        compare_week[col] = pd.to_numeric(compare_week[col], errors="coerce").fillna(0.0)
                    compare_week["if_proxy"] = 0.0
                    _cmp_dur = pd.to_numeric(compare_week["duration_s"], errors="coerce").fillna(0.0)
                    _cmp_w = pd.to_numeric(compare_week["if_weighted"], errors="coerce").fillna(0.0)
                    _cmp_mask = _cmp_dur > 0
                    compare_week.loc[_cmp_mask, "if_proxy"] = _cmp_w[_cmp_mask] / _cmp_dur[_cmp_mask]
                compact_week["day_label"] = compact_week["day"].dt.strftime("%a").str.upper()
                compact_week["day_num"] = compact_week["day"].dt.day

                metric_defs = [
                    ("rtss", "rTSS", ".0f", "", "sum"),
                    ("tss", "TSS", ".0f", "", "sum"),
                    ("distance_eqv_km", "Distance Eqv", ".0f", " km", "sum"),
                ]
                selected_metric = str(active_metric_choice or st.session_state.get("calendar_compact_metric") or "tss")
                if selected_metric not in {k for k, _, _, _, _ in metric_defs}:
                    selected_metric = "tss"
                    st.session_state["calendar_compact_metric"] = selected_metric

                chart_df = compact_week.copy()
                is_mobile_compact = bool(is_mobile_layout)
                chart_df["metric_value"] = pd.to_numeric(chart_df[selected_metric], errors="coerce").fillna(0.0)
                if is_mobile_compact:
                    chart_df["day_display"] = chart_df["day"].dt.strftime("%a %d")
                else:
                    chart_df["day_display"] = (
                        chart_df["day"].dt.strftime("%d %b")
                        + "\n("
                        + chart_df["day"].dt.strftime("%a")
                        + ")"
                    )
                chart_df["series"] = "Current"
                chart_df["opacity"] = 0.95
                chart_df = chart_df.sort_values("day").reset_index(drop=True)
                chart_df["slot_idx"] = chart_df.index.astype(int)
                compare_chart_df = compare_week.copy()
                compare_chart_df["metric_value"] = pd.to_numeric(
                    compare_chart_df[selected_metric], errors="coerce"
                ).fillna(0.0)
                if is_mobile_compact:
                    compare_chart_df["day_display"] = compare_chart_df["day"].dt.strftime("%a %d")
                else:
                    compare_chart_df["day_display"] = (
                        compare_chart_df["day"].dt.strftime("%d %b")
                        + "\n("
                        + compare_chart_df["day"].dt.strftime("%a")
                        + ")"
                    )
                compare_chart_df["series"] = "Compare"
                compare_chart_df["opacity"] = 0.35
                compare_chart_df = compare_chart_df.sort_values("day").reset_index(drop=True)
                compare_chart_df["slot_idx"] = compare_chart_df.index.astype(int)
                # Always align compare bars to current-week slots (Mon..Sun of selected week),
                # so historical weeks overlay by day-of-week instead of creating extra x categories.
                slot_to_display = {
                    int(slot): str(label)
                    for slot, label in zip(chart_df["slot_idx"], chart_df["day_display"])
                }
                compare_chart_df["day_display"] = compare_chart_df["slot_idx"].map(slot_to_display).fillna(
                    compare_chart_df["day_display"]
                )
                compare_chart_df = compare_chart_df[compare_chart_df["slot_idx"].isin(slot_to_display.keys())].copy()
                y_title = next(label for key, label, _, _, _ in metric_defs if key == selected_metric)
                chart_df["metric_label"] = chart_df["metric_value"].map(
                    lambda v: f"{v:.0f}" if float(v) > 0 else ""
                )
                compare_chart_df["metric_label"] = compare_chart_df["metric_value"].map(
                    lambda v: f"{v:.0f}" if float(v) > 0 else ""
                )

                def _compact_bar_color(metric_key: str, value: float) -> str:
                    if metric_key in {"tss", "rtss"}:
                        if value < 50:
                            return "#34d399"
                        if value <= 100:
                            return "#facc15"
                        return "#60a5fa"
                    if metric_key == "distance_eqv_km":
                        if value < 15:
                            return "#34d399"
                        if value <= 22:
                            return "#facc15"
                        return "#60a5fa"
                    return "#34d399"

                chart_df["bar_color"] = chart_df["metric_value"].map(
                    lambda v: _compact_bar_color(selected_metric, float(v))
                )
                compare_chart_df["bar_color"] = "#94a3b8"
                # Guard against index-alignment and stale/null category issues that can blank the chart.
                chart_df["day"] = pd.to_datetime(chart_df.get("day"), errors="coerce")
                compare_chart_df["day"] = pd.to_datetime(compare_chart_df.get("day"), errors="coerce")
                chart_df["metric_value"] = pd.to_numeric(chart_df.get("metric_value"), errors="coerce").fillna(0.0)
                compare_chart_df["metric_value"] = pd.to_numeric(compare_chart_df.get("metric_value"), errors="coerce").fillna(0.0)
                chart_df = chart_df.dropna(subset=["day", "day_display"]).copy()
                compare_chart_df = compare_chart_df.dropna(subset=["day", "day_display"]).copy()
                bar_df = pd.concat([compare_chart_df, chart_df], ignore_index=True)
                day_order = chart_df["day_display"].tolist()
                if bar_df.empty and not chart_df.empty:
                    bar_df = chart_df.copy()
                bars = (
                    alt.Chart(bar_df)
                    .mark_bar(
                        cornerRadiusTopLeft=10,
                        cornerRadiusTopRight=10,
                        size=(16 if is_mobile_compact else 24),
                        opacity=0.95,
                    )
                    .encode(
                        x=alt.X(
                            "day_display:N",
                            sort=day_order,
                            scale=alt.Scale(domain=day_order),
                            title=None,
                            axis=alt.Axis(
                                labelAngle=0,
                                labelLineHeight=(11 if is_mobile_compact else 14),
                                labelFontSize=(10 if is_mobile_compact else 12),
                                labelPadding=(6 if is_mobile_compact else 10),
                            ),
                        ),
                        xOffset=alt.XOffset(
                            "series:N",
                            sort=["Compare", "Current"],
                        ),
                        y=alt.Y("metric_value:Q", title=None, scale=alt.Scale(zero=True), stack=None),
                        color=alt.Color("bar_color:N", scale=None, legend=None),
                        opacity=alt.Opacity("opacity:Q", legend=None),
                        tooltip=[
                            alt.Tooltip("day:T", title="Day"),
                            alt.Tooltip("series:N", title="Series"),
                            alt.Tooltip(
                                "metric_value:Q",
                                title=y_title,
                                format=".0f",
                            ),
                        ],
                    )
                )
                current_labels = (
                    alt.Chart(chart_df.assign(series="Current"))
                    .transform_filter("datum.metric_value > 0")
                    .mark_text(
                        dy=-4,
                        baseline="bottom",
                        color="#e2e8f0",
                        fontSize=12,
                        fontWeight=700,
                        clip=False,
                    )
                    .encode(
                        x=alt.X("day_display:N", sort=day_order, scale=alt.Scale(domain=day_order)),
                        xOffset=alt.XOffset(
                            "series:N",
                            sort=["Compare", "Current"],
                        ),
                        y=alt.Y("metric_value:Q"),
                        text=alt.Text("metric_label:N"),
                    )
                )
                labels_layer = current_labels
                if compare_choice != "Planned":
                    compare_labels = (
                        alt.Chart(compare_chart_df.assign(series="Compare"))
                        .transform_filter("datum.metric_value > 0")
                        .mark_text(
                            dy=-4,
                            baseline="bottom",
                            color="#cbd5e1",
                            fontSize=11,
                            fontWeight=700,
                            opacity=0.8,
                            clip=False,
                        )
                        .encode(
                            x=alt.X("day_display:N", sort=day_order, scale=alt.Scale(domain=day_order)),
                            xOffset=alt.XOffset(
                                "series:N",
                                sort=["Compare", "Current"],
                            ),
                            y=alt.Y("metric_value:Q"),
                            text=alt.Text("metric_label:N"),
                        )
                    )
                    labels_layer = alt.layer(compare_labels, current_labels)
                today_local = pd.Timestamp(datetime.now().astimezone().date())
                cutoff_day = min(today_local, selected_week_end)
                day_offset = int((cutoff_day - selected_week_start).days)
                day_offset = min(max(day_offset, 0), 6)
                actual_to_date_mask = compact_week["day"] <= cutoff_day
                if compare_choice == "Planned":
                    compare_cutoff_day = cutoff_day
                else:
                    compare_cutoff_day = compare_week_start + pd.Timedelta(days=day_offset)
                compare_to_date_mask = compare_week["day"] <= compare_cutoff_day
                metric_label_map = {k: lbl for k, lbl, _, _, _ in metric_defs}
                compare_label = "planned" if compare_choice == "Planned" else str(compare_choice).lower()

                def _agg_metric(df: pd.DataFrame, mask: pd.Series, metric_key: str) -> float:
                    if df.empty or metric_key not in df.columns:
                        return 0.0
                    vals = pd.to_numeric(df.loc[mask, metric_key], errors="coerce").fillna(0.0)
                    return float(vals.sum())

                def _fmt_metric(metric_key: str, value: float) -> str:
                    if metric_key == "distance_eqv_km":
                        return f"{float(value):.0f} km"
                    return f"{float(value):.0f}"

                realized_to_date = _agg_metric(compact_week, actual_to_date_mask, selected_metric)
                realized_week_total = _agg_metric(compact_week, compact_week["day"].notna(), selected_metric)
                compare_to_date = _agg_metric(compare_week, compare_to_date_mask, selected_metric)
                compare_week_total = _agg_metric(compare_week, compare_week["day"].notna(), selected_metric)
                if compare_choice != "Planned" and not compare_chart_df.empty:
                    compare_to_date = float(
                        pd.to_numeric(
                            compare_chart_df.loc[
                                pd.to_numeric(compare_chart_df.get("slot_idx"), errors="coerce").fillna(-1).astype(int)
                                <= int(day_offset),
                                "metric_value",
                            ],
                            errors="coerce",
                        ).fillna(0.0).sum()
                    )
                    compare_week_total = float(
                        pd.to_numeric(compare_chart_df.get("metric_value"), errors="coerce").fillna(0.0).sum()
                    )
                if compare_choice == "Planned" and not planned_rows_compare_source.empty:
                    planned_metric_key = (
                        "distance_proxy_km"
                        if selected_metric == "distance_eqv_km"
                        else selected_metric
                    )
                    _planned_mask_to_date = (
                        planned_rows_compare_source["day"] <= cutoff_day
                    )
                    compare_to_date = float(
                        pd.to_numeric(
                            planned_rows_compare_source.loc[
                                _planned_mask_to_date,
                                planned_metric_key,
                            ] if planned_metric_key in planned_rows_compare_source.columns else pd.Series(dtype=float),
                            errors="coerce",
                        ).fillna(0.0).sum()
                    )
                    compare_week_total = float(
                        pd.to_numeric(
                            planned_rows_compare_source.get(planned_metric_key),
                            errors="coerce",
                        ).fillna(0.0).sum()
                    )
                if compare_choice == "Planned":
                    compare_remaining = float(planned_remaining_metric_totals.get(selected_metric, 0.0))
                    projected_finish = realized_to_date + compare_remaining
                else:
                    compare_remaining = 0.0
                    projected_finish = float("nan")
                projected_fatigue = float("nan")
                try:
                    if compare_choice == "Planned":
                        eow_day = pd.Timestamp(selected_week_end).normalize()
                        ff_row = daily_fitfat_with_projection.get(eow_day)
                        if isinstance(ff_row, dict):
                            projected_fatigue = float(
                                pd.to_numeric(
                                    pd.Series([ff_row.get("fatigue")]),
                                    errors="coerce",
                                ).iloc[0]
                            )
                    else:
                        projected_fatigue = float("nan")
                except Exception:
                    projected_fatigue = float("nan")

                def _emph(value_text: str) -> str:
                    return (
                        "<span style='display:inline-block;padding:1px 7px;border-radius:999px;"
                        "background:rgba(226,232,240,0.14);border:1px solid rgba(148,163,184,0.38);"
                        "font-weight:800;color:#f8fafc;'>"
                        f"{value_text}</span>"
                    )

                if compare_choice == "Planned":
                    narrative = (
                        f"Today is {today_local:%A}: "
                        f"WTD {metric_label_map.get(selected_metric, 'Metric')} delivered: {_emph(_fmt_metric(selected_metric, realized_to_date))} "
                        f"(vs. {compare_label} {_emph(_fmt_metric(selected_metric, compare_to_date))}). "
                        f"Remaining {metric_label_map.get(selected_metric, 'Metric')} to go "
                        f"{_emph(_fmt_metric(selected_metric, compare_remaining))}. "
                        f"Projected finish {metric_label_map.get(selected_metric, 'Metric')} "
                        f"{_emph(_fmt_metric(selected_metric, projected_finish))}."
                        + (
                            f" Estimated fatigue EoW {_emph(f'{projected_fatigue:.0f}')}."
                            if pd.notna(projected_fatigue)
                            else ""
                        )
                    )
                else:
                    narrative = (
                        f"Today is {today_local:%A}: "
                        f"WTD {metric_label_map.get(selected_metric, 'Metric')} delivered: {_emph(_fmt_metric(selected_metric, realized_to_date))} "
                        f"(vs. {compare_label} {_emph(_fmt_metric(selected_metric, compare_to_date))})."
                    )
                if is_mobile_compact:
                    if compare_choice == "Planned":
                        narrative_mobile = (
                            f"WTD {_fmt_metric(selected_metric, realized_to_date)} · "
                            f"Plan {_fmt_metric(selected_metric, compare_to_date)} · "
                            f"Left {_fmt_metric(selected_metric, compare_remaining)} · "
                            f"Proj {_fmt_metric(selected_metric, projected_finish)}"
                        )
                    else:
                        narrative_mobile = (
                            f"WTD {_fmt_metric(selected_metric, realized_to_date)} · "
                            f"{compare_label.title()} {_fmt_metric(selected_metric, compare_to_date)}"
                        )
                    st.caption(narrative_mobile)
                else:
                    st.markdown(
                        (
                            "<div class='compact-week-narrative' style='margin:0 0 2px 0;padding:10px 12px;border-radius:10px;"
                            "border:1px solid rgba(52,211,153,0.35);background:rgba(16,185,129,0.08);"
                            "color:rgba(226,232,240,0.96);font-size:0.9rem;line-height:1.35;'>"
                            f"{narrative}"
                            "</div>"
                        ),
                        unsafe_allow_html=True,
                    )
                compact_chart = alt.layer(bars, labels_layer).properties(
                    height=(205 if is_mobile_compact else 250),
                    padding=(
                        {"left": 36, "right": 6, "top": 8, "bottom": 26}
                        if is_mobile_compact
                        else {"left": 52, "right": 10, "top": 10, "bottom": 42}
                    ),
                )
                if is_mobile_compact:
                    compact_chart = bars.properties(
                        height=172,
                        padding={"left": 30, "right": 4, "top": 0, "bottom": 20},
                    )
                st.markdown("<div class='compact-week-shell'>", unsafe_allow_html=True)
                st.altair_chart(compact_chart, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            if not compact_mode:
                week_starts = pd.date_range(start=grid_start, end=grid_end, freq="7D")
                week_starts = week_starts.sort_values(ascending=False)
                week_count = int(len(week_starts))
                week_chunk = 6
                visible_weeks = int(
                    pd.to_numeric(st.session_state.get("calendar_activity_weeks_visible", week_chunk), errors="coerce")
                    or week_chunk
                )
                visible_weeks = max(week_chunk, min(visible_weeks, week_count if week_count > 0 else week_chunk))
                st.session_state["calendar_activity_weeks_visible"] = visible_weeks
                render_week_starts = week_starts[:visible_weeks]
                for ws in render_week_starts:
                    we = ws + pd.Timedelta(days=6)
                    week_df = cal_metrics[(cal_metrics["day"] >= ws) & (cal_metrics["day"] <= we)].copy()
                    if week_df.empty:
                        continue
                    total_duration_h = float(pd.to_numeric(week_df["duration_s"], errors="coerce").fillna(0.0).sum() / 3600.0)
                    total_distance = float(pd.to_numeric(week_df["distance_km"], errors="coerce").fillna(0.0).sum())
                    total_distance_eqv = float(pd.to_numeric(week_df["distance_proxy_km"], errors="coerce").fillna(0.0).sum())
                    total_calories = float(pd.to_numeric(week_df["calories_total"], errors="coerce").fillna(0.0).sum())
                    total_tss = float(pd.to_numeric(week_df["tss"], errors="coerce").fillna(0.0).sum())
                    total_rtss = float(pd.to_numeric(week_df["rtss"], errors="coerce").fillna(0.0).sum())
                    zone_totals = {"Z1": 0.0, "Z2": 0.0, "Z3": 0.0, "Z4": 0.0, "Z5": 0.0}
                    for _, act_row in week_df.iterrows():
                        activity_zone_seconds = _zone_seconds_from_activity_row(act_row)
                        for zone_key in zone_totals:
                            zone_totals[zone_key] += float(activity_zone_seconds.get(zone_key, 0.0))
                    zone_total_s = sum(zone_totals.values())
                    zone_colors = {
                        "Z1": str(IF_ZONE_VISUALS["Z1"]["bar"]),
                        "Z2": str(IF_ZONE_VISUALS["Z2"]["bar"]),
                        "Z3": str(IF_ZONE_VISUALS["Z3"]["bar"]),
                        "Z4": str(IF_ZONE_VISUALS["Z4"]["bar"]),
                        "Z5": str(IF_ZONE_VISUALS["Z5"]["bar"]),
                    }
                    zone_rows_html = []
                    for zone in ["Z1", "Z2", "Z3", "Z4", "Z5"]:
                        z_seconds = zone_totals.get(zone, 0.0)
                        z_pct = (z_seconds / zone_total_s * 100.0) if zone_total_s > 0 else 0.0
                        zone_rows_html.append(
                            "<div class='cal-zone-row'>"
                            f"<div>{zone}</div>"
                            "<div class='cal-zone-track'>"
                            f"<div class='cal-zone-fill' style='width:{z_pct:.1f}%;background:{zone_colors[zone]};'></div>"
                            "</div>"
                            f"<div>{_duration_zone(z_seconds)}</div>"
                            f"<div>{z_pct:.1f}%</div>"
                            "</div>"
                        )

                    week_fitness = float("nan")
                    week_fatigue = float("nan")
                    week_overreach = float("nan")
                    week_injury_risk = float("nan")
                    if not cal_daily_lookup.empty:
                        week_daily = cal_daily_lookup[cal_daily_lookup["day"] <= we]
                        if not week_daily.empty:
                            last_row = week_daily.iloc[-1]
                            week_fitness = float(last_row["fitness"]) if pd.notna(last_row["fitness"]) else float("nan")
                            week_fatigue = float(last_row["fatigue"]) if pd.notna(last_row["fatigue"]) else float("nan")
                            week_overreach = float(last_row["overreach"]) if pd.notna(last_row["overreach"]) else float("nan")
                            week_injury_risk = float(last_row["injury_risk"]) if pd.notna(last_row["injury_risk"]) else float("nan")

                    row_cols = st.columns([1.2, 1, 1, 1, 1, 1, 1, 1])
                    with row_cols[0]:
                        fitness_txt = "-" if pd.isna(week_fitness) else f"{week_fitness:.0f}"
                        fatigue_txt = "-" if pd.isna(week_fatigue) else f"{week_fatigue:.0f}"
                        overreach_txt = "-" if pd.isna(week_overreach) else f"{week_overreach:.0f}"
                        injury_risk_txt = "-" if pd.isna(week_injury_risk) else f"{week_injury_risk:.0f}"
                        st.markdown(
                            (
                                "<div class='cal-week-summary'>"
                                f"<div><b>Week {int(ws.isocalendar().week)}</b></div>"
                                f"<div>{ws:%d %b} - {we:%d %b}</div>"
                                f"<div style='margin-top:6px;'>Time: <b>{total_duration_h:.1f}h</b></div>"
                                f"<div>Dist: <b>{total_distance:.0f} km</b></div>"
                                f"<div>Eqv.: <b>{total_distance_eqv:.0f} km</b></div>"
                                f"<div>kcal: <b>{total_calories:.0f}</b></div>"
                                f"<div>TSS: <b>{total_tss:.0f}</b> | rTSS: <b>{total_rtss:.0f}</b></div>"
                                f"<div>Fit: <b>{fitness_txt}</b> | Fatg: <b>{fatigue_txt}</b></div>"
                                f"<div>Ovr: <b>{overreach_txt}</b> | Risk: <b>{injury_risk_txt}</b></div>"
                                "<div class='cal-zones'><b>Zones</b>"
                                + "".join(zone_rows_html)
                                + "</div>"
                                "</div>"
                            ),
                            unsafe_allow_html=True,
                        )

                    for day_offset in range(7):
                        day_ts = ws + pd.Timedelta(days=day_offset)
                        day_df = week_df[week_df["day"] == day_ts].sort_values("start_local", ascending=False)
                        with row_cols[day_offset + 1]:
                            st.markdown(
                                f"<div class='cal-day-header'>{day_ts:%d %b} ({day_ts:%a})</div>",
                                unsafe_allow_html=True,
                            )
                            has_actual_day = not day_df.empty
                            day_cal = 0.0
                            day_distance_eqv = 0.0
                            if not day_activity_stats.empty:
                                day_cal_rows = day_activity_stats[day_activity_stats["day"] == day_ts]
                                if not day_cal_rows.empty:
                                    day_cal = float(day_cal_rows.iloc[0]["day_calories"])
                                    day_distance_eqv = float(day_cal_rows.iloc[0]["day_distance_eqv_km"])
                            planned_distance_eqv = 0.0
                            planned_tss = 0.0
                            planned_rtss = 0.0
                            planned_duration_s = 0.0
                            planned_if = 0.0
                            if not planned_day_lookup.empty:
                                day_plan_rows = planned_day_lookup[planned_day_lookup["day"] == day_ts]
                                if not day_plan_rows.empty:
                                    p = day_plan_rows.iloc[0]
                                    planned_distance_eqv = float(pd.to_numeric(pd.Series([p.get("planned_distance_eqv_km")]), errors="coerce").fillna(0.0).iloc[0])
                                    planned_tss = float(pd.to_numeric(pd.Series([p.get("planned_tss")]), errors="coerce").fillna(0.0).iloc[0])
                                    planned_rtss = float(pd.to_numeric(pd.Series([p.get("planned_rtss")]), errors="coerce").fillna(0.0).iloc[0])
                                    planned_duration_s = float(pd.to_numeric(pd.Series([p.get("planned_duration_s")]), errors="coerce").fillna(0.0).iloc[0])
                                    planned_if = float(pd.to_numeric(pd.Series([p.get("planned_if")]), errors="coerce").fillna(0.0).iloc[0])
                            day_resting_hr = float("nan")
                            day_stress_avg = float("nan")
                            if not wellness_day_lookup.empty:
                                day_well_rows = wellness_day_lookup[wellness_day_lookup["day"] == day_ts]
                                if not day_well_rows.empty:
                                    day_resting_hr = float(day_well_rows.iloc[0]["resting_hr"]) if pd.notna(day_well_rows.iloc[0]["resting_hr"]) else float("nan")
                                    day_stress_avg = float(day_well_rows.iloc[0]["stress_avg"]) if pd.notna(day_well_rows.iloc[0]["stress_avg"]) else float("nan")
                            # Planned headline metrics should only appear when the day has no actual activity.
                            # Also guard against edge cases where grouped daily stats exist for the day.
                            show_planned_meta = (
                                (not has_actual_day)
                                and (day_distance_eqv <= 0)
                                and (day_cal <= 0)
                            )
                            day_meta_parts: list[str] = []
                            if day_distance_eqv > 0:
                                day_meta_parts.append(f"{day_distance_eqv:.0f} km")
                            elif show_planned_meta and planned_distance_eqv > 0:
                                day_meta_parts.append(f"{planned_distance_eqv:.0f} km")
                            else:
                                day_meta_parts.append("0 km")
                            if day_cal > 0:
                                day_meta_parts.append(f"{day_cal:.0f} kcal")
                            fitfat_row = daily_fitfat_with_projection.get(day_ts)
                            if fitfat_row:
                                day_fit = fitfat_row.get("fitness")
                                day_fat = fitfat_row.get("fatigue")
                                if pd.notna(day_fit):
                                    day_meta_parts.append(f"Fit {float(day_fit):.0f}")
                                if pd.notna(day_fat):
                                    day_meta_parts.append(f"Fatigue {float(day_fat):.0f}")
                            if not pd.isna(day_resting_hr):
                                day_meta_parts.append(f"RHR {day_resting_hr:.0f}")
                            if not pd.isna(day_stress_avg):
                                day_meta_parts.append(f"Stress {day_stress_avg:.0f}")
                            if show_planned_meta and planned_duration_s > 0:
                                day_meta_parts.append(_duration_short(planned_duration_s))
                            if show_planned_meta and planned_if > 0:
                                day_meta_parts.append(f"IF {(planned_if * 100.0):.0f}%")
                            st.markdown(
                                f"<div class='cal-card-meta cal-day-meta'>{' · '.join(day_meta_parts)}</div>",
                                unsafe_allow_html=True,
                            )
                            rendered_cards = 0
                            actual_render_items: list[dict[str, object]] = []
                            for act_idx, (_, act) in enumerate(day_df.iterrows()):
                                activity_id = str(act.get("activity_id"))
                                is_custom_activity = activity_id.startswith("custom:")
                                sport_label_raw = _sport_label(act.get("sport_type"))
                                dur_text = _duration_short(act.get("duration_s"))
                                hr_v = pd.to_numeric(act.get("avg_hr"), errors="coerce")
                                hr_text = "-" if pd.isna(hr_v) else f"{int(round(float(hr_v)))} bpm"
                                sport_lower = str(act.get("sport_type") or "").lower()
                                is_running_activity = ("run" in sport_lower) or ("treadmill" in sport_lower)
                                distance_v = pd.to_numeric(act.get("distance_km"), errors="coerce")
                                distance_eqv_v = pd.to_numeric(act.get("distance_proxy_km"), errors="coerce")
                                if is_running_activity:
                                    dist_text = (
                                        f"{float(distance_v):.0f} km"
                                        if pd.notna(distance_v) and float(distance_v) > 0
                                        else ""
                                    )
                                else:
                                    dist_text = (
                                        f"{float(distance_eqv_v):.0f} km eqv."
                                        if pd.notna(distance_eqv_v) and float(distance_eqv_v) > 0
                                        else ""
                                    )
                                tss_v = float(pd.to_numeric(act.get("tss"), errors="coerce") or 0.0)
                                rtss_v = float(pd.to_numeric(act.get("rtss"), errors="coerce") or 0.0)
                                pace_actual_v = pd.to_numeric(act.get("avg_pace_s_per_km"), errors="coerce")
                                pace_eqv_v = pd.to_numeric(act.get("pace_proxy_sec_per_km"), errors="coerce")
                                if_v = pd.to_numeric(act.get("if_proxy"), errors="coerce")
                                if is_running_activity:
                                    pace_text = (
                                        f"Pace {_pace_compact(pace_actual_v)}"
                                        if pd.notna(pace_actual_v) and float(pace_actual_v) > 0
                                        else "Pace -"
                                    )
                                else:
                                    pace_text = (
                                        f"Pace Eqv {_pace_compact(pace_eqv_v)}"
                                        if pd.notna(pace_eqv_v) and float(pace_eqv_v) > 0
                                        else "Pace Eqv -"
                                    )
                                if_text = (
                                    f"IF {(float(if_v) * 100.0):.0f}%"
                                    if pd.notna(if_v) and float(if_v) > 0
                                    else "IF -"
                                )
                                activity_colors = _actual_activity_palette(
                                    if_proxy=if_v,
                                    tss_value=tss_v,
                                    rtss_value=rtss_v,
                                    sport_type=str(act.get("sport_type") or ""),
                                    daily_tss_upper_bound=derived_daily_tss_target,
                                )
                                activity_token = str(activity_colors.get("token") or "green")
                                activity_accent = activity_colors["accent"]
                                activity_border = activity_colors["border"]
                                activity_bg = activity_colors["background"]
                                subtitle = f"{dur_text}" + (f" · {dist_text}" if dist_text else "")
                                card_label = (
                                    f"**{'Custom · ' if is_custom_activity else ''}{sport_label_raw}**\n"
                                    f"{subtitle}\n"
                                    f"{hr_text}\n"
                                    f"{pace_text} · {if_text}\n"
                                    f"TSS {tss_v:.0f} · rTSS {rtss_v:.0f}"
                                )
                                if is_custom_activity:
                                    card_html = (
                                        f"<div class='cal-card' style='border:2px solid {activity_border}; background:{activity_bg};'>"
                                        f"<div class='cal-card-title' style='color:{activity_accent};'>Custom · {sport_label_raw}</div>"
                                        f"<div class='cal-card-meta'>{subtitle}</div>"
                                        f"<div class='cal-card-meta'>{hr_text}</div>"
                                        f"<div class='cal-card-meta'>{pace_text} · {if_text}</div>"
                                        f"<div class='cal-card-load'>TSS {tss_v:.0f} · rTSS {rtss_v:.0f}</div>"
                                        "</div>"
                                    )
                                    actual_render_items.append({"kind": "custom", "card_html": card_html})
                                else:
                                    activity_key_slug = re.sub(r"[^0-9A-Za-z_]+", "_", activity_id).strip("_")
                                    if not activity_key_slug:
                                        activity_key_slug = "activity"
                                    button_key = (
                                        f"calendar_split_title_if_{activity_token}_{day_ts.date().strftime('%Y%m%d')}_{act_idx}_"
                                        f"{activity_key_slug[:24]}"
                                    )
                                    actual_render_items.append(
                                        {
                                            "kind": "button",
                                            "card_label": card_label,
                                            "button_key": button_key,
                                            "activity_id": activity_id,
                                        }
                                    )
                            for item in actual_render_items:
                                if str(item.get("kind")) == "custom":
                                    st.markdown(str(item.get("card_html") or ""), unsafe_allow_html=True)
                                else:
                                    if st.button(
                                        str(item.get("card_label") or ""),
                                        key=str(item.get("button_key") or ""),
                                        use_container_width=True,
                                        type="tertiary",
                                    ):
                                        st.session_state["calendar_split_activity_id"] = str(
                                            item.get("activity_id") or ""
                                        )
                                        st.session_state["calendar_split_open"] = True
                                rendered_cards += 1
                            today_local_date = pd.Timestamp(today_local_day).date()
                            day_planned_cards = planned_cards_by_day.get(day_ts, [])
                            if day_ts.date() >= today_local_date and day_planned_cards:
                                for prow in day_planned_cards:
                                    p_activity = str(prow.get("activity") or "Planned")
                                    p_duration = _duration_short(prow.get("duration_s"))
                                    p_dist = float(pd.to_numeric(pd.Series([prow.get("distance_proxy_km")]), errors="coerce").fillna(0.0).iloc[0])
                                    p_if = float(pd.to_numeric(pd.Series([prow.get("if_proxy")]), errors="coerce").fillna(0.0).iloc[0])
                                    p_tss = float(pd.to_numeric(pd.Series([prow.get("tss")]), errors="coerce").fillna(0.0).iloc[0])
                                    p_rtss = float(pd.to_numeric(pd.Series([prow.get("rtss")]), errors="coerce").fillna(0.0).iloc[0])
                                    p_day_utc = str(prow.get("day_utc") or day_ts.date().isoformat())
                                    p_line_no = int(
                                        pd.to_numeric(pd.Series([prow.get("line_no")]), errors="coerce").fillna(0).iloc[0]
                                    )
                                    planned_colors = _actual_activity_palette(
                                        if_proxy=p_if,
                                        tss_value=p_tss,
                                        rtss_value=p_rtss,
                                        sport_type=p_activity,
                                        daily_tss_upper_bound=derived_daily_tss_target,
                                    )
                                    planned_token = str(planned_colors.get("token") or "green")
                                    planned_card_label = (
                                        f"**Planned · {p_activity}**\n"
                                        f"{p_duration} · {p_dist:.0f} km eqv.\n"
                                        f"IF {(p_if * 100.0):.0f}%\n"
                                        f"TSS {p_tss:.0f} · rTSS {p_rtss:.0f}"
                                    )
                                    if st.button(
                                        planned_card_label,
                                        key=(
                                            f"calendar_planned_done_if_{planned_token}_"
                                            f"{p_day_utc}_{p_line_no}_{rendered_cards}"
                                        ),
                                        use_container_width=True,
                                        type="primary",
                                    ):
                                        st.session_state["planned_mark_done_pending"] = {
                                            "day_utc": p_day_utc,
                                            "line_no": p_line_no,
                                            "label": f"{p_day_utc} · Planned {p_activity}",
                                        }
                            if rendered_cards == 0 and not day_planned_cards and day_ts.date() < today_local_date:
                                st.markdown(
                                    (
                                        "<div class='cal-rest-card'>"
                                        "<div class='cal-rest-title'>Rest Day</div>"
                                        "<div class='cal-rest-sub'>Rest is part of training!</div>"
                                        "</div>"
                                    ),
                                    unsafe_allow_html=True,
                                )
                if visible_weeks < week_count:
                    _remaining = week_count - visible_weeks
                    load_cols = st.columns([1.2, 6.8])
                    with load_cols[1]:
                        if st.button(
                            f"Load older weeks ({_remaining} remaining)",
                            key="calendar_activity_load_more_weeks",
                            use_container_width=False,
                        ):
                            st.session_state["calendar_activity_weeks_visible"] = min(
                                week_count, visible_weeks + week_chunk
                            )
                            st.rerun()
                elif week_count > week_chunk:
                    st.caption(f"Showing all {week_count} weeks.")

                pending_planned_done = st.session_state.get("planned_mark_done_pending")
                if isinstance(pending_planned_done, dict):
                    pending_day_utc = str(pending_planned_done.get("day_utc") or "").strip()
                    pending_line_no = int(
                        pd.to_numeric(pd.Series([pending_planned_done.get("line_no")]), errors="coerce").fillna(0).iloc[0]
                    )
                    pending_label = str(pending_planned_done.get("label") or "planned activity")

                    @st.dialog("Mark this activity as done?", width="small")
                    def _confirm_mark_planned_done() -> None:
                        st.markdown(f"**{pending_label}**")
                        yes_col, no_col = st.columns(2)
                        with yes_col:
                            if st.button("Yes", key="planned_done_confirm_yes", use_container_width=True):
                                if not _ensure_db_writable_or_warn(cfg.db_path, action_label="mark planned activity as done"):
                                    return
                                pending_day_ts = pd.to_datetime(pending_day_utc, errors="coerce")
                                today_local_day = pd.Timestamp(datetime.now().astimezone().date()).normalize()
                                if pd.isna(pending_day_ts):
                                    st.error("Invalid planned activity date.")
                                    return
                                if pending_day_ts.normalize() > today_local_day:
                                    st.error("Cannot mark future planned activities as done.")
                                    return
                                updated = set_planned_activity_manual_done(
                                    cfg.db_path,
                                    day_utc=pending_day_utc,
                                    line_no=pending_line_no,
                                    manual_done=True,
                                )
                                if not updated:
                                    st.error("Could not mark activity as done. Please refresh and try again.")
                                    return
                                st.session_state.pop("planned_mark_done_pending", None)
                                st.success("Planned activity marked as done.")
                                st.rerun()
                        with no_col:
                            if st.button("No", key="planned_done_confirm_no", use_container_width=True):
                                st.session_state.pop("planned_mark_done_pending", None)
                                st.rerun()

                    _confirm_mark_planned_done()

                selected_split_activity_id = (
                    st.session_state.get("calendar_split_activity_id")
                    if bool(st.session_state.get("calendar_split_open"))
                    else None
                )
                if selected_split_activity_id:
                    selected_activity_df = cal_metrics[
                        cal_metrics["activity_id"].astype(str) == str(selected_split_activity_id)
                    ]
                    selected_activity_row = (
                        selected_activity_df.sort_values("start_local", ascending=False).iloc[0]
                        if not selected_activity_df.empty
                        else None
                    )
                    split_row = split_lookup.get(str(selected_split_activity_id))
                    split_metrics_df = (
                        _build_split_metrics_for_activity(
                            activity_row=selected_activity_row,
                            split_row=split_row,
                            lthr=float(
                                _curve_value_at(
                                    lthr_curve_points,
                                    float(derived_lthr_bpm),
                                    pd.to_datetime(selected_activity_row.get("start_time_utc"), utc=True, errors="coerce"),
                                )
                            ),
                            threshold_pace_default_sec=float(
                                _curve_value_at(
                                    lt_pace_curve_points,
                                    float(derived_threshold_pace_sec),
                                    pd.to_datetime(selected_activity_row.get("start_time_utc"), utc=True, errors="coerce"),
                                )
                            ),
                        )
                        if selected_activity_row is not None and split_row is not None
                        else pd.DataFrame()
                    )

                    @st.dialog(f"Activity Splits · {selected_split_activity_id}", width="large")
                    def _show_split_details_dialog() -> None:
                        if selected_activity_row is not None:
                            st.caption(
                                f"{pd.to_datetime(selected_activity_row.get('start_time_utc'), utc=True, errors='coerce'):%Y-%m-%d %H:%M UTC} · "
                                f"{_sport_label(str(selected_activity_row.get('sport_type')))}"
                            )
                        if split_metrics_df.empty:
                            st.info("No split laps found for this activity.")
                        else:
                            plot_df = split_metrics_df.copy()
                            plot_df["split_label"] = "Lap " + plot_df["split_idx"].astype(int).astype(str)
                            plot_df["distance_eqv_km"] = pd.to_numeric(
                                plot_df.get("distance_eqv_km"), errors="coerce"
                            ).fillna(0.0)
                            plot_df["distance_km_ui"] = pd.to_numeric(
                                plot_df.get("distance_km"), errors="coerce"
                            ).fillna(0.0).map(lambda v: _truncate_to_decimals(v, 2))
                            plot_df["distance_eqv_km_ui"] = pd.to_numeric(
                                plot_df.get("distance_eqv_km"), errors="coerce"
                            ).fillna(0.0).map(lambda v: _truncate_to_decimals(v, 2))
                            plot_df["pace_eqv_s_per_km"] = pd.to_numeric(
                                plot_df.get("pace_eqv_s_per_km"), errors="coerce"
                            )
                            plot_df["duration_display"] = plot_df["duration_s"].apply(_duration_compact_with_seconds)
                            plot_df["pace_display"] = plot_df["pace_s_per_km"].apply(_pace_compact)
                            plot_df["pace_eqv_display"] = plot_df["pace_eqv_s_per_km"].apply(_pace_compact)
                            plot_df["speed_eqv_kmh"] = pd.NA
                            valid_pace = plot_df["pace_eqv_s_per_km"] > 0
                            plot_df.loc[valid_pace, "speed_eqv_kmh"] = 3600.0 / plot_df.loc[valid_pace, "pace_eqv_s_per_km"]
                            plot_df["speed_eqv_kmh"] = pd.to_numeric(
                                plot_df["speed_eqv_kmh"], errors="coerce"
                            ).fillna(0.0)
                            plot_df["intensity_factor"] = pd.to_numeric(
                                plot_df.get("intensity_factor"), errors="coerce"
                            ).fillna(0.0).clip(lower=0.0)
                            plot_df["intensity_factor_color"] = pd.to_numeric(
                                plot_df.get("intensity_factor"), errors="coerce"
                            ).fillna(0.0).clip(lower=0.0, upper=1.0)
                            plot_df = plot_df.sort_values("split_idx").reset_index(drop=True)
                            if float(plot_df["distance_eqv_km"].sum()) <= 0:
                                plot_df["distance_eqv_km"] = 1.0
                            plot_df["x_end"] = plot_df["distance_eqv_km"].cumsum()
                            plot_df["x_start"] = plot_df["x_end"] - plot_df["distance_eqv_km"]
                            plot_df["y_zero"] = 0.0
                            chart = (
                                alt.Chart(plot_df)
                                .mark_bar()
                                .encode(
                                    x=alt.X(
                                        "x_start:Q",
                                        title="Eqv Dist (Km)",
                                    ),
                                    x2="x_end:Q",
                                    y=alt.Y(
                                        "speed_eqv_kmh:Q",
                                        title="Eqv Speed (Km/h)",
                                        scale=alt.Scale(zero=True),
                                    ),
                                    y2=alt.Y2("y_zero:Q"),
                                    color=alt.Color(
                                        "intensity_factor_color:Q",
                                        title="IF",
                                        scale=alt.Scale(
                                            domain=[0.0, 0.5, 1.0],
                                            range=["#2563eb", "#22c55e", "#ef4444"],
                                            clamp=True,
                                        ),
                                        legend=alt.Legend(orient="right"),
                                    ),
                                    tooltip=[
                                        alt.Tooltip("split_label:N", title="Split"),
                                        alt.Tooltip("intensity_type:N", title="Type"),
                                        alt.Tooltip("duration_display:N", title="Duration"),
                                        alt.Tooltip("distance_km_ui:Q", title="Distance (km)", format=".2f"),
                                        alt.Tooltip("distance_eqv_km_ui:Q", title="Dist Eqv (km)", format=".2f"),
                                        alt.Tooltip("speed_eqv_kmh:Q", title="Speed Eqv (km/h)", format=".2f"),
                                        alt.Tooltip("avg_hr:Q", title="Avg HR", format=".0f"),
                                        alt.Tooltip("intensity_factor:Q", title="IF", format=".1%"),
                                        alt.Tooltip("pace_display:N", title="Pace"),
                                        alt.Tooltip("pace_eqv_display:N", title="Pace Eqv"),
                                        alt.Tooltip("tss:Q", title="TSS", format=".0f"),
                                        alt.Tooltip("rtss:Q", title="rTSS", format=".0f"),
                                    ],
                                )
                                .properties(height=280)
                            )
                            st.altair_chart(chart, use_container_width=True)
                            table_df = plot_df.copy()
                            table_df["duration"] = table_df["duration_s"].apply(_duration_compact_with_seconds)
                            table_df["distance_display"] = pd.to_numeric(
                                table_df.get("distance_km_ui"), errors="coerce"
                            ).fillna(0.0).map(lambda v: f"{v:.2f}km")
                            table_df["pace"] = table_df["pace_s_per_km"].apply(_pace_compact)
                            table_df["pace_eqv"] = table_df["pace_eqv_s_per_km"].apply(_pace_compact)
                            table_df["description"] = table_df["intensity_factor"].apply(_split_description_from_if_proxy)
                            st.dataframe(
                                table_df[
                                    [
                                        "split_idx",
                                        "description",
                                        "duration",
                                        "distance_display",
                                        "pace",
                                        "avg_hr",
                                        "distance_eqv_km_ui",
                                        "pace_eqv",
                                    ]
                                ],
                                use_container_width=True,
                                hide_index=True,
                                key="calendar_split_table_v4",
                                column_config={
                                    "split_idx": st.column_config.NumberColumn("Lap", format="%d"),
                                    "description": st.column_config.TextColumn("Description"),
                                    "duration": st.column_config.TextColumn("Duration"),
                                    "distance_display": st.column_config.TextColumn("Distance"),
                                    "distance_eqv_km_ui": st.column_config.NumberColumn("Dist Eqv (km)", format="%.2f"),
                                    "avg_hr": st.column_config.NumberColumn("Avg HR", format="%.0f"),
                                    "pace": st.column_config.TextColumn("Pace"),
                                    "pace_eqv": st.column_config.TextColumn("Pace Eqv"),
                                },
                            )
                        if st.button("Close", key="calendar_split_modal_close"):
                            st.session_state.pop("calendar_split_activity_id", None)
                            st.session_state["calendar_split_open"] = False
                            st.rerun()
                    _show_split_details_dialog()

if view in {"Week Planner", "Weekly Summary"}:
    if view == "Weekly Summary":
        st.markdown(
            "<hr style='margin:6px 0 8px 0;border:0;border-top:1px solid rgba(148,163,184,0.28);'>",
            unsafe_allow_html=True,
        )
    if view == "Weekly Summary":
        st.markdown("### Plan Activities")
    else:
        st.header("Week Planner")
    st.caption("Plan one dated activity at a time with `[date]:[activity]`.")
    st.caption("You can ingest multiple activities in one save using separators: `;` or `,`.")

    today_local = pd.Timestamp(date.today())
    previous_sunday = today_local - pd.Timedelta(days=int(today_local.weekday()) + 1)
    planner_profile_current = _normalize_specificity_profile(
        st.session_state.get("user_specificity_profile", {}),
        fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
    )

    p1, p2 = st.columns([3.6, 0.6])
    with p1:
        plan_entry = st.text_input(
            "Plan entry",
            value=st.session_state.get("planner_single_entry", ""),
            key="planner_single_entry",
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm or 2026-03-26: 10min run @4:50 + 5x6min @3:40/km",
        )
    with p2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        save_clicked = st.button("Save", key="planner_single_save_btn", use_container_width=True)

    if save_clicked and not _ensure_db_writable_or_warn(cfg.db_path, action_label="save planned activities"):
        save_clicked = False
    if save_clicked:
        if len(str(plan_entry or "")) > int(MAX_PLANNED_ENTRY_CHARS):
            st.error(f"Input too large. Max {MAX_PLANNED_ENTRY_CHARS} characters per save.")
            entries = []
        else:
            entries = _split_dated_activity_entries(plan_entry)
        if not entries:
            st.error("Input is empty. Use `[date]:[activity]`.")
        elif len(entries) > int(MAX_PLANNED_ENTRIES_PER_SAVE):
            st.error(f"Too many entries in one save. Max {MAX_PLANNED_ENTRIES_PER_SAVE}.")
        else:
            existing = get_planned_activities_df(cfg.db_path)
            max_line_by_day = (
                existing.groupby("day_utc")["line_no"].max().to_dict() if not existing.empty else {}
            )
            existing_signatures: set[str] = set()
            if not existing.empty:
                for _, er in existing.iterrows():
                    existing_signatures.add(
                        _planned_row_signature(
                            str(er.get("day_utc") or ""),
                            str(er.get("workout_text") or ""),
                        )
                    )
            rows_to_upsert: list[dict[str, object]] = []
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
                segs, warns = _expand_planned_segments(
                    normalized,
                    lthr_bpm=float(derived_lthr_bpm),
                    threshold_pace_sec_per_km=float(derived_threshold_pace_sec),
                )
                if warns or not segs:
                    details = "; ".join(warns[:2]) if warns else "Could not parse this activity."
                    errors.append(f"entry {idx}: {details}")
                    continue
                day_key = day_ts.date().isoformat()
                sig = _planned_row_signature(day_key, normalized)
                if sig in existing_signatures:
                    errors.append(
                        f"entry {idx}: duplicate skipped for `{day_key}` (`{normalized}` already exists)."
                    )
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
                upsert_planned_activities_rows(cfg.db_path, rows_to_upsert)
            if errors:
                st.warning("Some entries were skipped:\n- " + "\n- ".join(errors[:10]))
            if rows_to_upsert:
                st.success(f"Saved {len(rows_to_upsert)} planned activit{'y' if len(rows_to_upsert)==1 else 'ies'}.")
                st.rerun()

    planned_raw = get_planned_activities_df(cfg.db_path)
    planned_raw = _apply_planned_actual_matching(planned_raw, metrics_df)
    if planned_raw.empty:
        st.caption("No planned activities saved yet.")
    else:
        planned_raw = planned_raw.sort_values(["day_utc", "line_no"], ascending=[False, True]).copy()
        planned_raw["row_id"] = planned_raw["day_utc"].astype(str) + "::" + planned_raw["line_no"].astype(int).astype(str)
        planned_raw["select"] = False
        planner_specificity_profile = _normalize_specificity_profile(
            st.session_state.get("user_specificity_profile", {}),
            fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
        )
        planner_profile_key = tuple(
            sorted(
                (str(k), float(v))
                for k, v in planner_specificity_profile.items()
            )
        )
        planned_metrics_cache_key = (
            "planned_metrics_v1",
            str(planned_activities_cache_key),
            _curve_points_cache_key(lthr_curve_points),
            float(derived_lthr_bpm),
            _curve_points_cache_key(lt_pace_curve_points),
            float(derived_threshold_pace_sec),
            planner_profile_key,
        )
        if (
            st.session_state.get("_planned_metrics_df_local_cache_key") == planned_metrics_cache_key
            and isinstance(st.session_state.get("_planned_metrics_df_local_cache_value"), pd.DataFrame)
        ):
            planned_raw = st.session_state["_planned_metrics_df_local_cache_value"].copy()
        else:
            planned_raw = _compute_planned_rows_metrics_df(
                planned_rows=planned_raw,
                lthr_curve_points=lthr_curve_points,
                lthr_default_bpm=float(derived_lthr_bpm),
                lt_pace_curve_points=lt_pace_curve_points,
                lt_pace_default_sec=float(derived_threshold_pace_sec),
                specificity_profile=planner_specificity_profile,
            )
            st.session_state["_planned_metrics_df_local_cache_key"] = planned_metrics_cache_key
            st.session_state["_planned_metrics_df_local_cache_value"] = planned_raw.copy()
        planned_raw["distance_eqv_km"] = pd.to_numeric(
            planned_raw.get("distance_proxy_km"),
            errors="coerce",
        ).fillna(0.0)

        tss_goal_week = float(derived_weekly_tss_target) * 1.10
        rtss_goal_week = float(derived_weekly_tss_target) * 0.90
        dist_goal_week = float(derived_weekly_distance_target)
        st.markdown("##### Planned weekly outlook")
        weekly_outlook = planned_raw.copy()
        selected_planned_week_start: pd.Timestamp | None = None
        weekly_outlook["day"] = pd.to_datetime(weekly_outlook["day_utc"], errors="coerce")
        weekly_outlook = weekly_outlook.dropna(subset=["day"])
        if not weekly_outlook.empty:
            week_start = weekly_outlook["day"] - pd.to_timedelta(weekly_outlook["day"].dt.weekday, unit="D")
            weekly_outlook["week_start"] = week_start.dt.normalize()
            weekly_outlook["if_weighted"] = pd.to_numeric(weekly_outlook["if_proxy"], errors="coerce").fillna(0.0) * pd.to_numeric(
                weekly_outlook["duration_s"], errors="coerce"
            ).fillna(0.0)
            this_week_start = (pd.Timestamp(date.today()) - pd.Timedelta(days=int(pd.Timestamp(date.today()).weekday()))).normalize()
            weekly_outlook = weekly_outlook[weekly_outlook["week_start"] >= this_week_start]
            weekly_grouped = (
                weekly_outlook.groupby("week_start", as_index=False)
                .agg(
                    tss=("tss", "sum"),
                    rtss=("rtss", "sum"),
                    distance_eqv_km=("distance_eqv_km", "sum"),
                    duration_s=("duration_s", "sum"),
                    if_weighted=("if_weighted", "sum"),
                    planned_activities=("row_id", "count"),
                )
                .sort_values("week_start")
                .head(4)
            )
            if not weekly_grouped.empty:
                weekly_grouped["if_proxy"] = 0.0
                valid_dur = weekly_grouped["duration_s"] > 0
                weekly_grouped.loc[valid_dur, "if_proxy"] = (
                    weekly_grouped.loc[valid_dur, "if_weighted"] / weekly_grouped.loc[valid_dur, "duration_s"]
                )
                weekly_grouped["if_proxy_pct"] = pd.to_numeric(
                    weekly_grouped.get("if_proxy"), errors="coerce"
                ).fillna(0.0) * 100.0
                weekly_grouped["duration_h"] = (
                    pd.to_numeric(weekly_grouped.get("duration_s"), errors="coerce").fillna(0.0) / 3600.0
                )
                weekly_grouped["week_label"] = (
                    weekly_grouped["week_start"].dt.strftime("%d %b")
                    + " - "
                    + (weekly_grouped["week_start"] + pd.Timedelta(days=6)).dt.strftime("%d %b")
                )
                week_keys = weekly_grouped["week_start"].dt.strftime("%Y-%m-%d").tolist()
                selected_week_key = str(st.session_state.get("planner_outlook_week_key") or "")
                if selected_week_key not in week_keys:
                    selected_week_key = week_keys[0]
                    st.session_state["planner_outlook_week_key"] = selected_week_key
                weekly_display = weekly_grouped[
                    [
                        "week_start",
                        "week_label",
                        "planned_activities",
                        "duration_h",
                        "tss",
                        "rtss",
                        "distance_eqv_km",
                        "if_proxy_pct",
                    ]
                ].copy()
                weekly_display["display"] = weekly_display["week_start"].dt.strftime("%Y-%m-%d") == selected_week_key
                weekly_display = weekly_display[
                    [
                        "display",
                        "week_label",
                        "planned_activities",
                        "duration_h",
                        "tss",
                        "rtss",
                        "distance_eqv_km",
                        "if_proxy_pct",
                    ]
                ]
                edited_weekly_display = st.data_editor(
                    weekly_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "display": st.column_config.CheckboxColumn("Display"),
                        "week_label": st.column_config.TextColumn("Week"),
                        "planned_activities": st.column_config.NumberColumn("Activities", format="%d"),
                        "duration_h": st.column_config.NumberColumn("Duration (h)", format="%.1f"),
                        "tss": st.column_config.NumberColumn("TSS", format="%.0f"),
                        "rtss": st.column_config.NumberColumn("rTSS", format="%.0f"),
                        "distance_eqv_km": st.column_config.NumberColumn("Dist Eqv (km)", format="%.0f"),
                        "if_proxy_pct": st.column_config.NumberColumn("IF", format="%.0f%%"),
                    },
                    disabled=[
                        "week_label",
                        "planned_activities",
                        "duration_h",
                        "tss",
                        "rtss",
                        "distance_eqv_km",
                        "if_proxy_pct",
                    ],
                    key="planner_weekly_outlook_editor",
                )
                checked_idx = edited_weekly_display[edited_weekly_display["display"] == True].index.tolist()
                if checked_idx:
                    # Enforce single select: keep the last checked row.
                    selected_idx = checked_idx[-1]
                    selected_week_key = str(weekly_grouped.loc[selected_idx, "week_start"].strftime("%Y-%m-%d"))
                    st.session_state["planner_outlook_week_key"] = selected_week_key
                    selected_planned_week_start = pd.to_datetime(selected_week_key, errors="coerce")
                    if len(checked_idx) > 1:
                        st.info("Only one week can be selected. Kept the latest checked row.")
                        st.rerun()
                else:
                    selected_planned_week_start = None

                selected_week_row = weekly_grouped[
                    weekly_grouped["week_start"].dt.strftime("%Y-%m-%d") == selected_week_key
                ]
                if selected_week_row.empty:
                    selected_week_row = weekly_grouped.iloc[[0]]
                _planned_tss = float(pd.to_numeric(selected_week_row["tss"], errors="coerce").fillna(0.0).iloc[0])
                _planned_rtss = float(pd.to_numeric(selected_week_row["rtss"], errors="coerce").fillna(0.0).iloc[0])
                _planned_dist = float(pd.to_numeric(selected_week_row["distance_eqv_km"], errors="coerce").fillna(0.0).iloc[0])
                _tss_pct = int(round((_planned_tss / tss_goal_week) * 100.0)) if tss_goal_week > 0 else 0
                _rtss_pct = int(round((_planned_rtss / rtss_goal_week) * 100.0)) if rtss_goal_week > 0 else 0
                _dist_pct = int(round((_planned_dist / dist_goal_week) * 100.0)) if dist_goal_week > 0 else 0
                st.caption(
                    f"TSS Goal = {int(round(tss_goal_week))} (vs. {_tss_pct}% plan). "
                    f"rTSS Goal = {int(round(rtss_goal_week))} (vs. {_rtss_pct}% plan). "
                    f"Dist Goal = {int(round(dist_goal_week))} km (vs. {_dist_pct}% planned)."
                )
            else:
                st.caption("No planned activities in the upcoming weeks.")
        else:
            st.caption(
                f"TSS Goal = {int(round(tss_goal_week))}. "
                f"rTSS Goal = {int(round(rtss_goal_week))}. "
                f"Dist Goal = {int(round(dist_goal_week))} km."
            )
            st.caption("No valid planned dates to build a weekly outlook.")
        if selected_planned_week_start is not None and pd.notna(selected_planned_week_start):
            selected_planned_week_end = selected_planned_week_start + pd.Timedelta(days=6)
            metric_select_col, _metric_spacer = st.columns([1, 4])
            with metric_select_col:
                planned_plot_metric = st.selectbox(
                    "Planned metric view",
                    ["TSS", "rTSS", "Dist Eqv (km)", "IF"],
                    index=0,
                    key="planned_metric_view_select",
                )
            plot_metric_col = {
                "TSS": "tss",
                "rTSS": "rtss",
                "Dist Eqv (km)": "distance_eqv_km",
                "IF": "if_proxy",
            }[planned_plot_metric]
            plot_df = planned_raw.copy()
            plot_df["day"] = pd.to_datetime(plot_df["day_utc"], errors="coerce")
            plot_df = plot_df.dropna(subset=["day"])
            plot_df = plot_df[
                (plot_df["day"] >= selected_planned_week_start) & (plot_df["day"] <= selected_planned_week_end)
            ]
            if not plot_df.empty:
                if plot_metric_col == "if_proxy":
                    aggregated = (
                        plot_df.groupby("day", as_index=False)["if_proxy"]
                        .mean()
                        .rename(columns={"if_proxy": "value"})
                    )
                else:
                    aggregated = (
                        plot_df.groupby("day", as_index=False)[plot_metric_col]
                        .sum()
                        .rename(columns={plot_metric_col: "value"})
                    )
                full_days = pd.DataFrame(
                    {
                        "day": pd.date_range(
                            selected_planned_week_start,
                            selected_planned_week_end,
                            freq="D",
                        )
                    }
                )
                planned_agg = full_days.merge(aggregated, on="day", how="left")
                planned_agg["value"] = pd.to_numeric(planned_agg["value"], errors="coerce").fillna(0.0)
                if plot_metric_col == "if_proxy":
                    planned_agg["label"] = planned_agg["value"].map(lambda v: f"{(float(v) * 100.0):.0f}%" if float(v) > 0 else "")
                elif plot_metric_col == "distance_eqv_km":
                    planned_agg["label"] = planned_agg["value"].map(lambda v: f"{v:.0f} km" if float(v) > 0 else "")
                else:
                    planned_agg["label"] = planned_agg["value"].map(lambda v: f"{v:.0f}" if float(v) > 0 else "")
                planned_agg["day_label"] = planned_agg["day"].dt.strftime("%d %b (%a)")
                planned_agg = planned_agg.sort_values("day")
                day_order = planned_agg["day_label"].tolist()
                planned_chart = (
                    alt.Chart(planned_agg)
                    .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color="#34d399", size=44)
                    .encode(
                        x=alt.X("day_label:N", sort=day_order, title="", axis=alt.Axis(labelAngle=0)),
                        y=alt.Y("value:Q", title=planned_plot_metric),
                        tooltip=[
                            alt.Tooltip("day:T", title="Day"),
                            alt.Tooltip(
                                "value:Q",
                                title=planned_plot_metric,
                                format=".0%" if plot_metric_col == "if_proxy" else ".0f",
                            ),
                        ],
                    )
                )
                planned_labels = (
                    alt.Chart(planned_agg)
                    .mark_text(dy=-8, color="#e2e8f0", fontSize=11, fontWeight=700)
                    .encode(x=alt.X("day_label:N", sort=day_order), y="value:Q", text="label:N")
                )
                st.altair_chart((planned_chart + planned_labels).properties(height=150), use_container_width=True)
        else:
            st.caption("Select a week in `Display` above to show the planned metric chart.")
        planned_rows_for_editor = planned_raw.copy()
        if selected_planned_week_start is not None and pd.notna(selected_planned_week_start):
            selected_planned_week_end = selected_planned_week_start + pd.Timedelta(days=6)
            _editor_day = pd.to_datetime(planned_rows_for_editor.get("day_utc"), errors="coerce")
            planned_rows_for_editor = planned_rows_for_editor[
                (_editor_day >= selected_planned_week_start)
                & (_editor_day <= selected_planned_week_end)
            ].copy()

        editor_source_df = planned_rows_for_editor[
            [
                "day_utc",
                "line_no",
                "activity",
                "workout_text",
                "duration_s",
                "tss",
                "rtss",
                "distance_eqv_km",
                "if_proxy",
                "manual_done",
                "parsed_json",
            ]
        ].copy()
        editor_source_df["day_of_week"] = pd.to_datetime(editor_source_df["day_utc"], errors="coerce").dt.strftime("%a")
        editor_source_df["if_proxy_pct"] = (
            pd.to_numeric(editor_source_df.get("if_proxy"), errors="coerce").fillna(0.0) * 100.0
        )
        editor_source_df["manual_done"] = (
            pd.to_numeric(editor_source_df.get("manual_done"), errors="coerce").fillna(0.0) > 0
        )
        if "duration_s" in editor_source_df.columns:
            planner_duration_s = pd.to_numeric(editor_source_df["duration_s"], errors="coerce")
        else:
            planner_duration_s = pd.Series(0.0, index=editor_source_df.index)
        planner_duration_fallback = editor_source_df.get(
            "parsed_json", pd.Series(index=editor_source_df.index)
        ).apply(_sum_duration_s_from_parsed_segments)
        planner_duration_s = planner_duration_s.where(
            planner_duration_s.fillna(0.0) > 0, planner_duration_fallback
        )
        editor_source_df["duration_h"] = planner_duration_s.fillna(0.0) / 3600.0
        editor_df = editor_source_df[
            [
                "manual_done",
                "day_of_week",
                "activity",
                "workout_text",
                "tss",
                "rtss",
                "distance_eqv_km",
                "duration_h",
                "if_proxy_pct",
            ]
        ].copy()
        editor_df = editor_df.reset_index(drop=True)
        editor_source_df = editor_source_df.reset_index(drop=True)
        edited_plan = st.data_editor(
            editor_df,
            use_container_width=True,
            hide_index=True,
            column_order=[
                "manual_done",
                "day_of_week",
                "activity",
                "workout_text",
                "tss",
                "rtss",
                "distance_eqv_km",
                "duration_h",
                "if_proxy_pct",
            ],
            column_config={
                "day_of_week": st.column_config.TextColumn("DOW", disabled=True),
                "activity": st.column_config.TextColumn("Activity", disabled=True),
                "workout_text": st.column_config.TextColumn("Activity String"),
                "duration_h": st.column_config.NumberColumn("Duration (h)", format="%.1f", disabled=True),
                "tss": st.column_config.NumberColumn("TSS", format="%.0f", disabled=True),
                "rtss": st.column_config.NumberColumn("rTSS", format="%.0f", disabled=True),
                "distance_eqv_km": st.column_config.NumberColumn("Dist Eqv (km)", format="%.0f", disabled=True),
                "if_proxy_pct": st.column_config.NumberColumn("IF", format="%.0f%%", disabled=True),
                "manual_done": st.column_config.CheckboxColumn("Done"),
            },
            key="planner_raw_editor",
        )

        _planner_save_col, _planner_save_spacer = st.columns([1, 6])
        with _planner_save_col:
            save_table_clicked = st.button("Save", key="planner_save_table_edits_btn", use_container_width=False)
        if save_table_clicked:
            if not _ensure_db_writable_or_warn(cfg.db_path, action_label="save planned edits"):
                st.stop()
            original_records = editor_source_df.to_dict(orient="records")
            changed_rows: list[dict[str, object]] = []
            for _, r in edited_plan.iterrows():
                row_idx = int(r.name)
                if row_idx < 0 or row_idx >= len(original_records):
                    continue
                orig = original_records[row_idx]
                new_workout = _normalize_plan_text(str(r.get("workout_text") or ""))
                old_workout = _normalize_plan_text(str(orig.get("workout_text") or ""))
                new_done = bool(r.get("manual_done", False))
                old_done = bool(orig.get("manual_done", False))
                if (new_workout != old_workout) or (new_done != old_done):
                    changed_rows.append(
                        {
                            "day_utc": str(orig.get("day_utc") or ""),
                            "line_no": int(pd.to_numeric(pd.Series([orig.get("line_no")]), errors="coerce").fillna(0).iloc[0]),
                            "workout_text": new_workout,
                            "manual_done": new_done,
                        }
                    )
            if not changed_rows:
                st.info("No table changes detected.")
            else:
                errors: list[str] = []
                upsert_rows: list[dict[str, object]] = []
                delete_keys: list[tuple[str, int]] = []
                today_local_day = pd.Timestamp(datetime.now().astimezone().date()).normalize()
                for r in changed_rows:
                    day_text = str(r.get("day_utc") or "").strip()
                    workout_text = str(r.get("workout_text") or "")
                    done_value = bool(r.get("manual_done", False))
                    line_no = int(r.get("line_no") or 0)
                    try:
                        day_ts = pd.Timestamp(day_text)
                    except Exception:
                        errors.append(f"Invalid date `{day_text}`")
                        continue
                    if workout_text == "":
                        delete_keys.append((day_text, line_no))
                        continue
                    if done_value and day_ts.normalize() > today_local_day:
                        errors.append(f"`{day_text}` is in the future. Cannot mark done for future planned activities.")
                        continue
                    segs, warns = _expand_planned_segments(
                        workout_text,
                        lthr_bpm=float(derived_lthr_bpm),
                        threshold_pace_sec_per_km=float(derived_threshold_pace_sec),
                    )
                    if warns or not segs:
                        errors.append(
                            f"`{workout_text}` invalid: " + ("; ".join(warns[:2]) if warns else "unparseable")
                        )
                        continue
                    upsert_rows.append(
                        {
                            "day_utc": day_text,
                            "line_no": line_no,
                            "workout_text": workout_text,
                            "parsed_json": segs,
                            "manual_done": done_value,
                        }
                    )
                if errors:
                    st.error("Cannot save edits:\n- " + "\n- ".join(errors[:8]))
                else:
                    if delete_keys:
                        delete_planned_activities(cfg.db_path, delete_keys)
                    if upsert_rows:
                        upsert_planned_activities_rows(cfg.db_path, upsert_rows)
                    if delete_keys or upsert_rows:
                        st.success(
                            f"Saved table changes: {len(upsert_rows)} updated, {len(delete_keys)} deleted."
                        )
                        st.rerun()
                    else:
                        st.info("No valid table changes to save.")

if view == "Custom Activities":
    st.header("Custom Activities")
    st.caption(
        "Save custom activities to a separate table. Manual input uses `[date]:[activity]` "
        "with date as `3Mar26`, `2026-03-26`, or `26/03/2026`."
    )
    st.caption("Multi-activity ingest supported via new line, `;`, or `,` separators.")

    today_local = pd.Timestamp(date.today())
    ex1 = today_local
    ex2 = today_local + pd.Timedelta(days=1)
    ex3 = today_local + pd.Timedelta(days=2)
    ex4 = today_local + pd.Timedelta(days=3)
    tp1 = float(_curve_value_at(lt_pace_curve_points, float(derived_threshold_pace_sec), ex1))
    tp4 = float(_curve_value_at(lt_pace_curve_points, float(derived_threshold_pace_sec), ex4))
    lthr2 = float(_curve_value_at(lthr_curve_points, float(derived_lthr_bpm), ex2))
    lthr3 = float(_curve_value_at(lthr_curve_points, float(derived_lthr_bpm), ex3))
    easy_run_pace = _pace_compact(tp1 / 0.70 if tp1 > 0 else None)
    treadmill_easy_pace = _pace_compact(tp4 / 0.75 if tp4 > 0 else None)
    treadmill_hard_pace = _pace_compact(tp4 / 0.95 if tp4 > 0 else None)
    easy_xtrain_hr = int(round(max(lthr2 * 0.70, 1.0)))
    xtrain_block1_hr = int(round(max(lthr3 * 0.75, 1.0)))
    xtrain_block2_hr = int(round(max(lthr3 * 0.80, 1.0)))
    st.markdown(
        "Examples:\n"
        f"- `{ex1:%-d%b%y}: 15km run @{easy_run_pace}`\n"
        f"- `{ex2:%Y-%m-%d}: 80min elliptical @{easy_xtrain_hr}bpm`\n"
        f"- `{ex3:%Y-%m-%d}: 10min cycling @{xtrain_block1_hr}bpm + 4x10min @{xtrain_block2_hr}bpm`\n"
        f"- `{ex4:%d/%m/%Y}: 10min treadmill @{treadmill_easy_pace} + 5x6min @{treadmill_hard_pace}`"
    )

    c1, c2 = st.columns([3.6, 0.6])
    with c1:
        custom_entry = st.text_input(
            "Custom entry",
            value=st.session_state.get("custom_activity_entry", ""),
            key="custom_activity_entry",
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm or 2026-03-26: 10min run @4:50 + 5x6min @3:40/km",
        )
    with c2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        custom_save_clicked = st.button("Save custom", key="custom_single_save_btn", use_container_width=True)

    if custom_save_clicked and not _ensure_db_writable_or_warn(cfg.db_path, action_label="save custom activities"):
        custom_save_clicked = False
    if custom_save_clicked:
        if len(str(custom_entry or "")) > int(MAX_PLANNED_ENTRY_CHARS):
            st.error(f"Input too large. Max {MAX_PLANNED_ENTRY_CHARS} characters per save.")
            entries = []
        else:
            entries = _split_dated_activity_entries(custom_entry)
        if not entries:
            st.error("Input is empty. Use `[date]:[activity]`.")
        elif len(entries) > int(MAX_PLANNED_ENTRIES_PER_SAVE):
            st.error(f"Too many entries in one save. Max {MAX_PLANNED_ENTRIES_PER_SAVE}.")
        else:
            existing = get_custom_activities_df(cfg.db_path)
            max_line_by_day = (
                existing.groupby("day_utc")["line_no"].max().to_dict() if not existing.empty else {}
            )
            rows_to_upsert: list[dict[str, object]] = []
            errors: list[str] = []
            for idx, raw_entry in enumerate(entries, start=1):
                custom_day_ts, normalized, parse_err = _parse_dated_activity_entry(raw_entry)
                if parse_err:
                    errors.append(f"entry {idx}: {parse_err}")
                    continue
                if custom_day_ts is None:
                    errors.append(f"entry {idx}: could not parse date")
                    continue
                segs, warns = _expand_planned_segments(
                    normalized,
                    lthr_bpm=float(derived_lthr_bpm),
                    threshold_pace_sec_per_km=float(derived_threshold_pace_sec),
                )
                if warns or not segs:
                    details = "; ".join(warns[:2]) if warns else "Could not parse this activity."
                    errors.append(f"entry {idx}: {details}")
                    continue
                day_key = custom_day_ts.date().isoformat()
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
                        cfg.db_path,
                        rows_to_upsert,
                        max_rows=CUSTOM_ACTIVITIES_LIMIT,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                    st.stop()
            if errors:
                st.warning("Some entries were skipped:\n- " + "\n- ".join(errors[:10]))
            if rows_to_upsert:
                st.success(f"Saved {len(rows_to_upsert)} custom activit{'y' if len(rows_to_upsert)==1 else 'ies'}.")
                st.rerun()

    custom_raw = get_custom_activities_df(cfg.db_path)
    st.markdown("##### Custom Activity outlook")
    if custom_raw.empty:
        placeholder_outlook = pd.DataFrame(
            columns=["Display", "Week", "Activities", "Duration (h)", "TSS", "rTSS", "Dist Eqv (km)", "IF"]
        )
        st.dataframe(placeholder_outlook, use_container_width=True, hide_index=True)
        custom_metric_col, _custom_metric_spacer = st.columns([1, 4])
        with custom_metric_col:
            st.selectbox(
                "Custom activity metric view",
                ["TSS", "rTSS", "Dist Eqv (km)", "IF"],
                index=0,
                key="custom_metric_view_select",
                disabled=True,
            )
        st.caption("No custom activities saved yet. Save one above to populate outlook, chart, and table.")
    else:
        custom_raw = custom_raw.sort_values(["day_utc", "line_no"], ascending=[False, True]).copy()
        custom_raw["row_id"] = custom_raw["day_utc"].astype(str) + "::" + custom_raw["line_no"].astype(int).astype(str)
        custom_raw["select"] = False
        custom_specificity_profile = _normalize_specificity_profile(
            st.session_state.get("user_specificity_profile", {}),
            fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
        )
        custom_tss_vals: list[float] = []
        custom_rtss_vals: list[float] = []
        custom_dist_eqv_vals: list[float] = []
        custom_if_vals: list[float] = []
        custom_duration_vals: list[float] = []
        custom_activity_vals: list[str] = []
        for _, custom_row in custom_raw.iterrows():
            raw_segments = custom_row.get("parsed_json")
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

            day_for_curve = pd.to_datetime(custom_row.get("day_utc"), utc=True, errors="coerce")
            lthr_for_day = float(
                _curve_value_at(
                    lthr_curve_points,
                    float(derived_lthr_bpm),
                    day_for_curve,
                )
            )
            lt_pace_for_day = float(
                _curve_value_at(
                    lt_pace_curve_points,
                    float(derived_threshold_pace_sec),
                    day_for_curve,
                )
            )

            total_tss = 0.0
            total_rtss = 0.0
            total_dist_eqv = 0.0
            if_weighted_sum = 0.0
            if_weight_seconds = 0.0
            kinds_seen: list[str] = []
            for seg in segments:
                seg_kind = str(seg.get("kind") or "").strip().lower()
                seg_spec = _specificity_factor_for_plan_kind(seg_kind, custom_specificity_profile)
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
                if seg_kind and seg_kind not in kinds_seen:
                    kinds_seen.append(seg_kind)

            custom_tss_vals.append(total_tss)
            custom_rtss_vals.append(total_rtss)
            custom_dist_eqv_vals.append(total_dist_eqv)
            custom_if_vals.append(if_weighted_sum / if_weight_seconds if if_weight_seconds > 0 else 0.0)
            custom_duration_vals.append(if_weight_seconds)
            custom_activity_vals.append(", ".join([k.replace("_", " ").title() for k in kinds_seen]) if kinds_seen else "-")

        custom_raw["activity"] = custom_activity_vals
        custom_raw["tss"] = custom_tss_vals
        custom_raw["rtss"] = custom_rtss_vals
        custom_raw["distance_eqv_km"] = custom_dist_eqv_vals
        custom_raw["if_proxy"] = custom_if_vals
        custom_raw["duration_s"] = custom_duration_vals

        custom_weekly_outlook = custom_raw.copy()
        selected_custom_week_start: pd.Timestamp | None = None
        tss_goal_week = float(derived_weekly_tss_target) * 1.10
        rtss_goal_week = float(derived_weekly_tss_target) * 0.90
        dist_goal_week = float(derived_weekly_distance_target)
        custom_weekly_outlook["day"] = pd.to_datetime(custom_weekly_outlook["day_utc"], errors="coerce")
        custom_weekly_outlook = custom_weekly_outlook.dropna(subset=["day"])
        if not custom_weekly_outlook.empty:
            week_start = custom_weekly_outlook["day"] - pd.to_timedelta(custom_weekly_outlook["day"].dt.weekday, unit="D")
            custom_weekly_outlook["week_start"] = week_start.dt.normalize()
            custom_weekly_outlook["if_weighted"] = pd.to_numeric(
                custom_weekly_outlook["if_proxy"], errors="coerce"
            ).fillna(0.0) * pd.to_numeric(custom_weekly_outlook["duration_s"], errors="coerce").fillna(0.0)
            custom_weekly_grouped = (
                custom_weekly_outlook.groupby("week_start", as_index=False)
                .agg(
                    tss=("tss", "sum"),
                    rtss=("rtss", "sum"),
                    distance_eqv_km=("distance_eqv_km", "sum"),
                    duration_s=("duration_s", "sum"),
                    if_weighted=("if_weighted", "sum"),
                    custom_activities=("row_id", "count"),
                )
                .sort_values("week_start")
            )
            if not custom_weekly_grouped.empty:
                custom_weekly_grouped = custom_weekly_grouped.sort_values("week_start", ascending=False).reset_index(drop=True)
                custom_weekly_grouped["if_proxy"] = 0.0
                valid_dur = custom_weekly_grouped["duration_s"] > 0
                custom_weekly_grouped.loc[valid_dur, "if_proxy"] = (
                    custom_weekly_grouped.loc[valid_dur, "if_weighted"] / custom_weekly_grouped.loc[valid_dur, "duration_s"]
                )
                custom_weekly_grouped["if_proxy_pct"] = pd.to_numeric(
                    custom_weekly_grouped.get("if_proxy"), errors="coerce"
                ).fillna(0.0) * 100.0
                custom_weekly_grouped["duration_h"] = (
                    pd.to_numeric(custom_weekly_grouped.get("duration_s"), errors="coerce").fillna(0.0) / 3600.0
                )
                custom_weekly_grouped["week_label"] = (
                    custom_weekly_grouped["week_start"].dt.strftime("%d %b")
                    + " - "
                    + (custom_weekly_grouped["week_start"] + pd.Timedelta(days=6)).dt.strftime("%d %b")
                )
                week_keys = custom_weekly_grouped["week_start"].dt.strftime("%Y-%m-%d").tolist()
                selected_week_key = str(st.session_state.get("custom_outlook_week_key") or "")
                if selected_week_key not in week_keys:
                    selected_week_key = week_keys[0]
                    st.session_state["custom_outlook_week_key"] = selected_week_key
                custom_weekly_display = custom_weekly_grouped[
                    [
                        "week_start",
                        "week_label",
                        "custom_activities",
                        "duration_h",
                        "tss",
                        "rtss",
                        "distance_eqv_km",
                        "if_proxy_pct",
                    ]
                ].copy()
                custom_weekly_display["display"] = custom_weekly_display["week_start"].dt.strftime("%Y-%m-%d") == selected_week_key
                custom_weekly_display = custom_weekly_display[
                    [
                        "display",
                        "week_label",
                        "custom_activities",
                        "duration_h",
                        "tss",
                        "rtss",
                        "distance_eqv_km",
                        "if_proxy_pct",
                    ]
                ]
                edited_custom_weekly = st.data_editor(
                    custom_weekly_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "display": st.column_config.CheckboxColumn("Display"),
                        "week_label": st.column_config.TextColumn("Week"),
                        "custom_activities": st.column_config.NumberColumn("Activities", format="%d"),
                        "duration_h": st.column_config.NumberColumn("Duration (h)", format="%.1f"),
                        "tss": st.column_config.NumberColumn("TSS", format="%.0f"),
                        "rtss": st.column_config.NumberColumn("rTSS", format="%.0f"),
                        "distance_eqv_km": st.column_config.NumberColumn("Dist Eqv (km)", format="%.0f"),
                        "if_proxy_pct": st.column_config.NumberColumn("IF", format="%.0f%%"),
                    },
                    disabled=[
                        "week_label",
                        "custom_activities",
                        "duration_h",
                        "tss",
                        "rtss",
                        "distance_eqv_km",
                        "if_proxy_pct",
                    ],
                    key="custom_weekly_outlook_editor",
                )
                checked_idx = edited_custom_weekly[edited_custom_weekly["display"] == True].index.tolist()
                if checked_idx:
                    # Enforce single select: keep the last checked row.
                    selected_idx = checked_idx[-1]
                    selected_week_key = str(custom_weekly_grouped.loc[selected_idx, "week_start"].strftime("%Y-%m-%d"))
                    st.session_state["custom_outlook_week_key"] = selected_week_key
                    selected_custom_week_start = pd.to_datetime(selected_week_key, errors="coerce")
                    if len(checked_idx) > 1:
                        st.info("Only one week can be selected. Kept the latest checked row.")
                        st.rerun()
                else:
                    selected_custom_week_start = None

                selected_week_row = custom_weekly_grouped[
                    custom_weekly_grouped["week_start"].dt.strftime("%Y-%m-%d") == selected_week_key
                ]
                if selected_week_row.empty:
                    selected_week_row = custom_weekly_grouped.iloc[[0]]
                _custom_tss = float(pd.to_numeric(selected_week_row["tss"], errors="coerce").fillna(0.0).iloc[0])
                _custom_rtss = float(pd.to_numeric(selected_week_row["rtss"], errors="coerce").fillna(0.0).iloc[0])
                _custom_dist = float(
                    pd.to_numeric(selected_week_row["distance_eqv_km"], errors="coerce").fillna(0.0).iloc[0]
                )
                _tss_pct = int(round((_custom_tss / tss_goal_week) * 100.0)) if tss_goal_week > 0 else 0
                _rtss_pct = int(round((_custom_rtss / rtss_goal_week) * 100.0)) if rtss_goal_week > 0 else 0
                _dist_pct = int(round((_custom_dist / dist_goal_week) * 100.0)) if dist_goal_week > 0 else 0
                st.caption(
                    f"TSS Goal = {int(round(tss_goal_week))} (vs. {_tss_pct}% custom). "
                    f"rTSS Goal = {int(round(rtss_goal_week))} (vs. {_rtss_pct}% custom). "
                    f"Dist Goal = {int(round(dist_goal_week))} km (vs. {_dist_pct}% custom)."
                )
            else:
                st.caption("No custom activities found.")
        else:
            st.caption("No valid custom dates to build a weekly outlook.")
        custom_metric_col, _custom_metric_spacer = st.columns([1, 4])
        with custom_metric_col:
            custom_plot_metric = st.selectbox(
                "Custom activity metric view",
                ["TSS", "rTSS", "Dist Eqv (km)", "IF"],
                index=0,
                key="custom_metric_view_select",
            )
        custom_plot_metric_col = {
            "TSS": "tss",
            "rTSS": "rtss",
            "Dist Eqv (km)": "distance_eqv_km",
            "IF": "if_proxy",
        }[custom_plot_metric]
        custom_plot_df = custom_raw.copy()
        custom_plot_df["day"] = pd.to_datetime(custom_plot_df["day_utc"], errors="coerce")
        custom_plot_df = custom_plot_df.dropna(subset=["day"])
        if selected_custom_week_start is not None and pd.notna(selected_custom_week_start):
            selected_custom_week_end = selected_custom_week_start + pd.Timedelta(days=6)
            custom_plot_df = custom_plot_df[
                (custom_plot_df["day"] >= selected_custom_week_start) & (custom_plot_df["day"] <= selected_custom_week_end)
            ]
        else:
            custom_plot_df = pd.DataFrame()

        if not custom_plot_df.empty:
            if custom_plot_metric_col == "if_proxy":
                custom_agg = (
                    custom_plot_df.groupby("day", as_index=False)["if_proxy"]
                    .mean()
                    .rename(columns={"if_proxy": "value"})
                )
            else:
                custom_agg = (
                    custom_plot_df.groupby("day", as_index=False)[custom_plot_metric_col]
                    .sum()
                    .rename(columns={custom_plot_metric_col: "value"})
                )
            custom_agg["value"] = pd.to_numeric(custom_agg["value"], errors="coerce").fillna(0.0)
            if custom_plot_metric_col == "if_proxy":
                custom_agg["label"] = custom_agg["value"].map(lambda v: f"{(float(v) * 100.0):.0f}%" if float(v) > 0 else "")
            elif custom_plot_metric_col == "distance_eqv_km":
                custom_agg["label"] = custom_agg["value"].map(lambda v: f"{v:.0f} km" if float(v) > 0 else "")
            else:
                custom_agg["label"] = custom_agg["value"].map(lambda v: f"{v:.0f}" if float(v) > 0 else "")
            custom_agg["day_label"] = custom_agg["day"].dt.strftime("%d %b (%a)")
            custom_agg = custom_agg.sort_values("day")
            custom_day_order = custom_agg["day_label"].tolist()
            custom_chart = (
                alt.Chart(custom_agg)
                .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color="#34d399", size=44)
                .encode(
                    x=alt.X("day_label:N", sort=custom_day_order, title="", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("value:Q", title=custom_plot_metric),
                    tooltip=[
                        alt.Tooltip("day:T", title="Day"),
                        alt.Tooltip(
                            "value:Q",
                            title=custom_plot_metric,
                            format=".0%" if custom_plot_metric_col == "if_proxy" else ".0f",
                        ),
                    ],
                )
            )
            custom_labels = (
                alt.Chart(custom_agg)
                .mark_text(dy=-8, color="#e2e8f0", fontSize=11, fontWeight=700)
                .encode(x=alt.X("day_label:N", sort=custom_day_order), y="value:Q", text="label:N")
            )
            st.altair_chart((custom_chart + custom_labels).properties(height=150), use_container_width=True)
        else:
            st.caption("Select a week in `Display` above to show the custom activity metric chart.")

        custom_rows_for_editor = custom_raw.copy()
        if selected_custom_week_start is not None and pd.notna(selected_custom_week_start):
            selected_custom_week_end = selected_custom_week_start + pd.Timedelta(days=6)
            _custom_editor_day = pd.to_datetime(custom_rows_for_editor.get("day_utc"), errors="coerce")
            custom_rows_for_editor = custom_rows_for_editor[
                (_custom_editor_day >= selected_custom_week_start)
                & (_custom_editor_day <= selected_custom_week_end)
            ].copy()

        custom_editor_df = custom_rows_for_editor[
            [
                "select",
                "row_id",
                "day_utc",
                "line_no",
                "activity",
                "activity_text",
                "duration_s",
                "tss",
                "rtss",
                "distance_eqv_km",
                "if_proxy",
                "source",
                "parsed_json",
                "updated_at",
            ]
        ].copy()
        custom_editor_df["day_of_week"] = pd.to_datetime(custom_editor_df["day_utc"], errors="coerce").dt.strftime("%a")
        custom_editor_df["if_proxy_pct"] = pd.to_numeric(custom_editor_df.get("if_proxy"), errors="coerce").fillna(0.0) * 100.0
        if "duration_s" in custom_editor_df.columns:
            custom_duration_s = pd.to_numeric(custom_editor_df["duration_s"], errors="coerce")
        else:
            custom_duration_s = pd.Series(0.0, index=custom_editor_df.index)
        custom_duration_fallback = custom_editor_df.get(
            "parsed_json", pd.Series(index=custom_editor_df.index)
        ).apply(_sum_duration_s_from_parsed_segments)
        custom_duration_s = custom_duration_s.where(
            custom_duration_s.fillna(0.0) > 0, custom_duration_fallback
        )
        custom_editor_df["duration_h"] = custom_duration_s.fillna(0.0) / 3600.0
        custom_editor_df = custom_editor_df.drop(columns=["duration_s"], errors="ignore")
        custom_editor_df = custom_editor_df.drop(columns=["if_proxy"], errors="ignore")
        custom_editor = st.data_editor(
            custom_editor_df,
            use_container_width=True,
            hide_index=True,
            column_order=[
                "select",
                "row_id",
                "day_utc",
                "day_of_week",
                "line_no",
                "activity",
                "activity_text",
                "tss",
                "rtss",
                "distance_eqv_km",
                "duration_h",
                "if_proxy_pct",
                "source",
                "parsed_json",
                "updated_at",
            ],
            column_config={
                "select": st.column_config.CheckboxColumn("Select"),
                "row_id": st.column_config.TextColumn("Row ID", disabled=True),
                "day_utc": st.column_config.TextColumn("Date"),
                "day_of_week": st.column_config.TextColumn("DOW", disabled=True),
                "line_no": st.column_config.NumberColumn("Line", format="%d", disabled=True),
                "activity": st.column_config.TextColumn("Activity", disabled=True),
                "activity_text": st.column_config.TextColumn("Activity String"),
                "duration_h": st.column_config.NumberColumn("Duration (h)", format="%.1f", disabled=True),
                "tss": st.column_config.NumberColumn("TSS", format="%.0f", disabled=True),
                "rtss": st.column_config.NumberColumn("rTSS", format="%.0f", disabled=True),
                "distance_eqv_km": st.column_config.NumberColumn("Dist Eqv (km)", format="%.0f", disabled=True),
                "if_proxy_pct": st.column_config.NumberColumn("IF", format="%.0f%%", disabled=True),
                "source": st.column_config.TextColumn("Source", disabled=True),
                "parsed_json": st.column_config.TextColumn("Parsed JSON", disabled=True),
                "updated_at": st.column_config.TextColumn("Updated At", disabled=True),
            },
            key="custom_raw_editor",
        )
        selected_custom = custom_editor[custom_editor["select"] == True].copy()
        cd1, cd2 = st.columns(2)
        with cd1:
            if st.button("Delete selected custom", key="custom_delete_selected_btn", use_container_width=True):
                if selected_custom.empty:
                    st.info("Select at least one custom activity.")
                else:
                    delete_keys = []
                    for _, r in selected_custom.iterrows():
                        rid = str(r.get("row_id") or "")
                        day_part, line_part = rid.split("::", 1)
                        delete_keys.append((day_part, int(line_part)))
                    delete_custom_activities(cfg.db_path, delete_keys)
                    st.success(f"Deleted {len(delete_keys)} custom activities.")
                    st.rerun()
        with cd2:
            if st.button("Save custom edits (selected)", key="custom_save_selected_edits_btn", use_container_width=True):
                if not _ensure_db_writable_or_warn(cfg.db_path, action_label="save custom edits"):
                    st.stop()
                if selected_custom.empty:
                    st.info("Select at least one row to edit.")
                else:
                    old_keys: list[tuple[str, int]] = []
                    rows_to_upsert: list[dict[str, object]] = []
                    remaining = custom_raw.copy()
                    for _, r in selected_custom.iterrows():
                        rid = str(r.get("row_id") or "")
                        day_part, line_part = rid.split("::", 1)
                        old_keys.append((day_part, int(line_part)))
                    old_key_set = {f"{d}::{ln}" for d, ln in old_keys}
                    remaining = remaining[~remaining["row_id"].isin(old_key_set)].copy()
                    max_line_by_day = (
                        remaining.groupby("day_utc")["line_no"].max().to_dict() if not remaining.empty else {}
                    )
                    errors: list[str] = []
                    for _, r in selected_custom.iterrows():
                        day_text = str(r.get("day_utc") or "").strip()
                        activity_text = _normalize_plan_text(str(r.get("activity_text") or ""))
                        try:
                            day_ts = pd.Timestamp(day_text)
                        except Exception:
                            errors.append(f"Invalid date `{day_text}`")
                            continue
                        segs, warns = _expand_planned_segments(
                            activity_text,
                            lthr_bpm=float(derived_lthr_bpm),
                            threshold_pace_sec_per_km=float(derived_threshold_pace_sec),
                        )
                        if warns or not segs:
                            errors.append(
                                f"`{activity_text}` invalid: " + ("; ".join(warns[:2]) if warns else "unparseable")
                            )
                            continue
                        day_key = day_ts.date().isoformat()
                        next_line = int(max_line_by_day.get(day_key, 0)) + 1
                        max_line_by_day[day_key] = next_line
                        rows_to_upsert.append(
                            {
                                "day_utc": day_key,
                                "line_no": next_line,
                                "activity_text": activity_text,
                                "parsed_json": segs,
                                "source": "manual_edit",
                            }
                        )
                    if errors:
                        st.error("Cannot save custom edits:\n- " + "\n- ".join(errors[:8]))
                    else:
                        delete_custom_activities(cfg.db_path, old_keys)
                        try:
                            upsert_custom_activities_rows(
                                cfg.db_path,
                                rows_to_upsert,
                                max_rows=CUSTOM_ACTIVITIES_LIMIT,
                            )
                        except ValueError as exc:
                            st.error(str(exc))
                            st.stop()
                        st.success(f"Updated {len(rows_to_upsert)} custom activities.")
                        st.rerun()

if view == "Activity Detail":
    st.header("Activity Detail")

    if metrics_df.empty:
        st.info("No activities available.")
    else:
        options_df = metrics_df.copy().sort_values("start_time_utc", ascending=False)
        options_df["label"] = (
            options_df["start_time_utc"].dt.strftime("%Y-%m-%d")
            + " | "
            + options_df["distance_m"].div(1000).round(2).astype(str)
            + " km | "
            + options_df["activity_id"].astype(str)
        )
        selected = st.selectbox("Select activity", options_df["label"].tolist())
        activity_id = options_df.loc[options_df["label"] == selected, "activity_id"].iloc[0]

        row = options_df.loc[options_df["activity_id"] == activity_id].iloc[0]

        m1, m2, m3, m4 = st.columns(4)
        tss_v = pd.to_numeric(row.get("tss"), errors="coerce")
        tl_v = pd.to_numeric(row.get("training_load_garmin"), errors="coerce")
        rtss_v = pd.to_numeric(row.get("rtss"), errors="coerce")
        m1.metric("TSS", f"{(float(tss_v) if pd.notna(tss_v) else 0.0):.0f}")
        m2.metric("Garmin Training Load", f"{(float(tl_v) if pd.notna(tl_v) else 0.0):.0f}")
        m3.metric("rTSS", f"{(float(rtss_v) if pd.notna(rtss_v) else 0.0):.0f}")
        sport_type = str(row.get("sport_type") or "").lower()
        show_pace = ("run" in sport_type) or ("treadmill" in sport_type)
        m4.metric("Avg Pace", format_pace_min_per_km(row.get("avg_pace_s_per_km")) if show_pace else "-")

        st.write(
            {
                "activity_id": row["activity_id"],
                "start_time_utc": row["start_time_utc"],
                "sport_type": row["sport_type"],
                "distance_m": row["distance_m"],
                "duration_s": row["duration_s"],
                "avg_hr": row["avg_hr"],
                "max_hr": row["max_hr"],
                "elevation_gain_m": row["elevation_gain_m"],
                "elevation_loss_m": row.get("elevation_loss_m"),
                "avg_cadence": row.get("avg_cadence"),
                "max_cadence": row.get("max_cadence"),
                "avg_stride_length": row.get("avg_stride_length"),
                "vertical_ratio": row.get("vertical_ratio"),
                "vertical_oscillation": row.get("vertical_oscillation"),
                "running_power_avg": row.get("running_power_avg"),
                "running_power_max": row.get("running_power_max"),
                "stamina_start": row.get("stamina_start"),
                "stamina_end": row.get("stamina_end"),
                "training_effect_aerobic": row.get("training_effect_aerobic"),
                "training_effect_anaerobic": row.get("training_effect_anaerobic"),
                "training_load_garmin": row.get("training_load_garmin"),
                "training_load_garmin_field_name": row.get("training_load_garmin_field_name"),
                "training_load_garmin_units": row.get("training_load_garmin_units"),
                "calories_active": row.get("calories_active"),
                "calories_total": row.get("calories_total"),
                "intensity_minutes_vigorous": row.get("intensity_minutes_vigorous"),
                "intensity_minutes_moderate": row.get("intensity_minutes_moderate"),
                "mechanical_load": row.get("mechanical_load"),
                "performance_condition": row.get("performance_condition"),
                "device_name": row.get("device_name"),
                "manufacturer": row.get("manufacturer"),
                "activity_uuid": row.get("activity_uuid"),
                "owner_id": row.get("owner_id"),
                "owner_full_name": row.get("owner_full_name"),
                "elapsed_duration_s": row.get("elapsed_duration_s"),
                "moving_duration_s": row.get("moving_duration_s"),
                "average_speed_mps": row.get("average_speed_mps"),
                "activity_type_key": row.get("activity_type_key"),
                "activity_type_id": row.get("activity_type_id"),
                "hr_time_in_zone_1": row.get("hr_time_in_zone_1"),
                "hr_time_in_zone_2": row.get("hr_time_in_zone_2"),
                "hr_time_in_zone_3": row.get("hr_time_in_zone_3"),
                "hr_time_in_zone_4": row.get("hr_time_in_zone_4"),
                "hr_time_in_zone_5": row.get("hr_time_in_zone_5"),
                "difference_body_battery": row.get("difference_body_battery"),
                "bmr_calories": row.get("bmr_calories"),
                "is_pr": row.get("is_pr"),
                "split_summaries_json": row.get("split_summaries_json"),
                "source": row["source"],
            }
        )

        records_df = get_activity_records_df(cfg.db_path, str(activity_id))
        if not records_df.empty:
            st.subheader("Per-Record FIT Series")
            records_df["record_time_utc"] = pd.to_datetime(records_df["record_time_utc"], utc=True, errors="coerce")
            record_metric = st.selectbox(
                "Record metric",
                ["heart_rate", "cadence", "power", "speed", "distance", "stamina"],
                index=0,
            )
            plot_df = records_df.dropna(subset=[record_metric])
            if plot_df.empty:
                st.caption(f"No {record_metric} records for this run.")
            else:
                record_chart = (
                    alt.Chart(plot_df)
                    .mark_line()
                    .encode(
                        x="record_time_utc:T",
                        y=f"{record_metric}:Q",
                        tooltip=["record_time_utc", record_metric],
                    )
                )
                st.altair_chart(record_chart, use_container_width=True)

        st.subheader("Data Availability")
        availability_cols = [
            "avg_hr",
            "avg_cadence",
            "avg_stride_length",
            "vertical_ratio",
            "vertical_oscillation",
            "running_power_avg",
            "stamina_start",
            "training_effect_aerobic",
            "performance_condition",
        ]
        availability_df = options_df[["activity_id", "start_time_utc"] + availability_cols].copy()
        for col in availability_cols:
            availability_df[col] = availability_df[col].notna()
        st.dataframe(availability_df, use_container_width=True)

        raw = get_activity_raw(cfg.db_path, str(activity_id))
        if raw:
            with st.expander("Raw summary payload"):
                st.json(raw)

        detail_raw = get_activity_detail_raw(cfg.db_path, str(activity_id))
        if detail_raw:
            with st.expander("Raw detail payload"):
                st.json(detail_raw)

if view == "Recovery Data":
    st.header("Recovery Data (Garmin)")

    sleep_df = get_sleep_df(cfg.db_path)
    wellness_df = get_wellness_df(cfg.db_path)

    if sleep_df.empty and wellness_df.empty:
        st.info("No sleep/wellness data yet. Run Comprehensive Garmin Extract with wellness enabled.")
    else:
        st.subheader("Recovery Analytics")
        recovery_df = build_recovery_daily_frame(sleep_df, wellness_df)
        if not recovery_df.empty:
            metric_map = {
                "HRV (avg)": ("hrv_status", "avg"),
                "Stress Avg (avg)": ("stress_avg", "avg"),
                "Training Readiness (avg)": ("training_readiness", "avg"),
                "Respiration Avg (avg)": ("respiration_avg", "avg"),
                "Resting HR (avg)": ("resting_hr", "avg"),
                "Sleep Score (avg)": ("sleep_score", "avg"),
                "Deep Sleep (h, sum)": ("deep_sleep_h", "sum"),
                "Sleep Duration (h, sum)": ("sleep_duration_h", "sum"),
                "REM Sleep (h, sum)": ("rem_sleep_h", "sum"),
            }
            rc1, rc2, rc3 = st.columns([1, 1, 1])
            with rc1:
                r_min = recovery_df["day"].min().date()
                r_max = recovery_df["day"].max().date()
                recovery_quick_range = st.selectbox(
                    "Quick range",
                    ["YTD", "1Y", "2Y", "ALL", "Custom"],
                    index=0,
                    key="recovery_quick_range",
                )
                if recovery_quick_range == "YTD":
                    rq_start = max(r_min, date(r_max.year, 1, 1))
                    rq_end = r_max
                elif recovery_quick_range == "1Y":
                    rq_start = max(r_min, r_max - timedelta(days=365))
                    rq_end = r_max
                elif recovery_quick_range == "2Y":
                    rq_start = max(r_min, r_max - timedelta(days=730))
                    rq_end = r_max
                elif recovery_quick_range == "ALL":
                    rq_start = r_min
                    rq_end = r_max
                else:
                    rq_start = r_min
                    rq_end = r_max
                if recovery_quick_range == "Custom":
                    r_range = st.date_input(
                        "Recovery date range",
                        value=(rq_start, rq_end),
                        min_value=r_min,
                        max_value=r_max,
                        key="recovery_range",
                    )
                else:
                    r_range = (rq_start, rq_end)
                    st.caption(f"Range: {rq_start.isoformat()} -> {rq_end.isoformat()}")
            with rc2:
                recovery_weekly = st.checkbox("Weekly aggregation", value=False, key="recovery_weekly")
            with rc3:
                selected_recovery_metrics = st.multiselect(
                    "Recovery metrics",
                    list(metric_map.keys()),
                    default=["Stress Avg (avg)", "Resting HR (avg)"],
                    key="recovery_metrics",
                )

            if isinstance(r_range, tuple) and len(r_range) == 2:
                r_start, r_end = r_range
            else:
                r_start = r_end = r_max
            r_start_ts = pd.Timestamp(r_start)
            r_end_ts = pd.Timestamp(r_end)

            plot_long_frames: list[pd.DataFrame] = []
            frame = recovery_df[(recovery_df["day"] >= r_start_ts) & (recovery_df["day"] <= r_end_ts)].copy()
            if not frame.empty and selected_recovery_metrics:
                if recovery_weekly:
                    frame["week_start"] = frame["day"].dt.to_period("W-SUN").dt.start_time
                for label in selected_recovery_metrics:
                    col, agg_type = metric_map[label]
                    if col not in frame.columns:
                        continue
                    if recovery_weekly:
                        if agg_type == "sum":
                            g = (
                                frame.groupby("week_start", as_index=False)[col]
                                .sum()
                                .rename(columns={"week_start": "day", col: "value"})
                            )
                        else:
                            g = (
                                frame.groupby("week_start", as_index=False)[col]
                                .mean()
                                .rename(columns={"week_start": "day", col: "value"})
                            )
                    else:
                        g = frame[["day", col]].rename(columns={col: "value"})
                    g["series"] = label
                    plot_long_frames.append(g)

            if plot_long_frames:
                recovery_long = pd.concat(plot_long_frames, ignore_index=True).dropna(subset=["value"])
                if not recovery_long.empty:
                    rec_sel = alt.selection_point(name="recovery_legend_sel", fields=["series"], bind="legend")
                    recovery_chart = (
                        alt.Chart(recovery_long)
                        .mark_line(point=True)
                        .encode(
                            x="day:T",
                            y=alt.Y("value:Q", axis=alt.Axis(format=".2f")),
                            color="series:N",
                            tooltip=["day:T", "series:N", alt.Tooltip("value:Q", format=".2f")],
                            opacity=alt.condition(rec_sel, alt.value(1.0), alt.value(0.2), empty=True),
                        )
                        .add_params(rec_sel)
                    )
                    st.altair_chart(recovery_chart, use_container_width=True)
                else:
                    st.caption("No recovery values in selected range for selected metrics.")
            else:
                st.caption("Select at least one recovery metric to plot.")

        if not sleep_df.empty:
            st.subheader("Sleep Daily")
            st.dataframe(sleep_df, use_container_width=True)

        if not wellness_df.empty:
            st.subheader("Wellness Daily")
            st.dataframe(wellness_df, use_container_width=True)

if view == "Data Extract":
    st.header("Data Extract & Sync")
    raw_persistence_allowed = _allow_raw_persistence_for_current_user()
    if not raw_persistence_allowed:
        _cleanup_raw_garmin_artifacts(cfg.private_export_dir)

    last_sync = get_last_sync(cfg.db_path)
    if last_sync:
        ok = "success" if last_sync["success"] else "failed"
        st.caption(
            f"Last sync: {last_sync['sync_time_utc']} | source={last_sync['source']} | {ok} | {last_sync['message']}"
        )
    else:
        st.caption("No sync has been run yet.")

    counts = get_table_counts(cfg.db_path)
    st.caption(
        "Local records | "
        f"activities={counts['activities']}, details={counts['activity_details']}, "
        f"records={counts['activity_records']}, splits={counts['activity_splits']}, "
        f"sleep={counts['sleep_daily']}, wellness={counts['wellness_daily']}, "
        f"daily_summary={counts['daily_summary']}"
    )
    st.caption(f"Private DB: {cfg.db_path}")
    st.caption(f"DB usage (quota): {_db_usage_text(cfg.db_path)}")
    st.caption(f"Private exports: {cfg.private_export_dir}")
    if raw_persistence_allowed:
        st.caption("Raw Garmin artifacts: enabled for admin.")
    else:
        st.caption("Raw Garmin artifacts: disabled for non-admin users (temp ingestion + cleanup).")
    garmin_email, garmin_password = _get_garmin_credentials()
    garmin_credential_source = _get_garmin_credential_source()
    if garmin_email and garmin_password:
        st.caption(f"Garmin API credential source: {garmin_credential_source}")
    else:
        if _auth_enabled() and str(st.session_state.get("auth_role") or "") != "admin":
            st.caption("Garmin API credentials missing: external users must set sidebar Garmin Email/Password.")
        else:
            st.caption("Garmin API credentials missing: set them in sidebar or via GARMIN_EMAIL / GARMIN_PASSWORD.")

    st.subheader("Unified Sync")
    quick_cols = st.columns([1, 1, 1])
    with quick_cols[0]:
        days_back = st.number_input("Days to sync", min_value=7, max_value=3650, value=180)
    with quick_cols[1]:
        source = st.selectbox("Source", ["Garmin API", "File Import", "Both"], index=2)
    with quick_cols[2]:
        run_sync = st.button("Sync all data", use_container_width=True)

    sync_profile = st.selectbox(
        "Garmin sync profile",
        ["Quick (activities only)", "Deep (activities + details + wellness)"],
        index=0,
        help="Quick is fast summaries-only. Deep also syncs activity details, splits, sleep, and wellness.",
    )

    st.caption(f"Import folder: {cfg.import_dir}")

    sync_triggered = False

    if run_sync:
        if not _ensure_db_writable_or_warn(cfg.db_path, action_label="run sync"):
            st.stop()
        if not raw_persistence_allowed:
            _cleanup_raw_garmin_artifacts(cfg.private_export_dir)
        total_rows = 0
        messages: list[str] = []
        sync_logs: list[str] = []
        sync_started_at = datetime.now(timezone.utc)
        sync_log_box = st.empty()
        sync_progress = st.progress(0, text="Starting unified sync...")
        max_sync_log_lines = 120

        def _render_sync_logs() -> None:
            lines = sync_logs[-max_sync_log_lines:]
            trimmed = len(sync_logs) - len(lines)
            prefix = [f"[info] showing last {len(lines)} logs (trimmed {trimmed})"] if trimmed > 0 else []
            sync_log_box.code("\n".join(prefix + lines) if lines else "(no logs)", language="text")

        def _sync_log(line: str) -> None:
            sync_logs.append(line)
            _render_sync_logs()

        latest = get_latest_activity_time(cfg.db_path)
        _sync_log(
            f"[start] {sync_started_at.isoformat()} | source={source} | days_back={int(days_back)} | "
            f"latest_activity_in_db={(latest.isoformat() if latest else 'None')}"
        )
        sync_progress.progress(10, text="Preparing sync...")

        if source in {"Garmin API", "Both"}:
            if garmin_email and garmin_password:
                try:
                    if sync_profile == "Quick (activities only)":
                        _sync_log("[fetch] Garmin quick sync: activity summaries only (no wellness/details)")

                        def _on_quick_progress(payload: dict) -> None:
                            phase = str(payload.get("phase") or "")
                            if phase == "activities":
                                frac = float(payload.get("fraction") or 0.0)
                                pct = int(10 + frac * 55)
                                pct = max(10, min(65, pct))
                                oldest = payload.get("oldest_in_batch")
                                sync_progress.progress(
                                    pct,
                                    text=(
                                        f"Quick sync: fetching activities... {pct}%"
                                        + (f" | oldest seen: {oldest}" if oldest else "")
                                    ),
                                )
                            elif phase == "complete":
                                sync_progress.progress(65, text="Quick sync: Garmin fetch complete.")

                        rows = fetch_garmin_runs(
                            email=garmin_email,
                            password=garmin_password,
                            days_back=int(days_back),
                            since_utc=latest,
                            progress_cb=_on_quick_progress,
                        )
                        owner_ok, owner_msg = _enforce_garmin_owner_scope(rows)
                        if not owner_ok:
                            raise RuntimeError(owner_msg)
                        sync_progress.progress(72, text="Quick sync: upserting Garmin activities...")
                        changed = upsert_activities(cfg.db_path, rows)
                        total_rows += len(rows)
                        messages.append(f"Garmin quick: fetched {len(rows)} activities ({changed} DB row changes).")
                        _sync_log(f"[fetch:done] garmin_rows={len(rows)} | db_changes={changed}")
                    else:
                        deep_start_day = (datetime.now(timezone.utc) - timedelta(days=int(days_back))).date()
                        _sync_log(
                            f"[fetch] Garmin deep sync: start_day={deep_start_day.isoformat()} | include_details=True | include_wellness=True"
                        )

                        def _on_deep_progress(payload: dict) -> None:
                            phase = str(payload.get("phase") or "")
                            if phase == "activities":
                                frac = float(payload.get("fraction") or 0.0)
                                pct = int(10 + frac * 60)
                                pct = max(10, min(75, pct))
                                sync_progress.progress(pct, text=f"Deep sync: fetching activities... {pct}%")
                            elif phase == "wellness":
                                frac = float(payload.get("fraction") or 0.0)
                                pct = int(75 + frac * 15)
                                pct = max(75, min(90, pct))
                                sync_progress.progress(pct, text=f"Deep sync: fetching wellness... {pct}%")
                            elif phase == "complete":
                                sync_progress.progress(92, text="Deep sync: upserting database...")

                        if raw_persistence_allowed:
                            extract = fetch_garmin_comprehensive(
                                email=garmin_email,
                                password=garmin_password,
                                start_day=deep_start_day,
                                end_day=datetime.now(timezone.utc).date(),
                                include_activity_details=True,
                                include_splits=True,
                                include_wellness=True,
                                raw_export_dir=cfg.private_export_dir / "raw",
                                progress_cb=_on_deep_progress,
                            )
                        else:
                            with tempfile.TemporaryDirectory(prefix="temperance_raw_ingest_") as _tmp_raw:
                                extract = fetch_garmin_comprehensive(
                                    email=garmin_email,
                                    password=garmin_password,
                                    start_day=deep_start_day,
                                    end_day=datetime.now(timezone.utc).date(),
                                    include_activity_details=True,
                                    include_splits=True,
                                    include_wellness=True,
                                    raw_export_dir=Path(_tmp_raw),
                                    progress_cb=_on_deep_progress,
                                )
                        owner_ok, owner_msg = _enforce_garmin_owner_scope(extract.activities)
                        if not owner_ok:
                            raise RuntimeError(owner_msg)
                        n_a = upsert_activities(cfg.db_path, extract.activities)
                        n_d = upsert_activity_details(cfg.db_path, extract.activity_details)
                        n_r = upsert_activity_records(cfg.db_path, extract.activity_records)
                        n_sp = upsert_activity_splits(cfg.db_path, extract.activity_splits)
                        n_s = upsert_sleep_daily(cfg.db_path, extract.sleep_daily)
                        n_w = upsert_wellness_daily(cfg.db_path, extract.wellness_daily)
                        total_rows += len(extract.activities)
                        _sync_log(
                            f"[fetch:done] deep activities={len(extract.activities)} details={len(extract.activity_details)} records={len(extract.activity_records)} splits={len(extract.activity_splits)} sleep={len(extract.sleep_daily)} wellness={len(extract.wellness_daily)} errors={len(extract.errors)}"
                        )
                        messages.append(
                            "Garmin deep: "
                            + f"activities={len(extract.activities)}({n_a}), details={len(extract.activity_details)}({n_d}), "
                            + f"records={len(extract.activity_records)}({n_r}), splits={len(extract.activity_splits)}({n_sp}), "
                            + f"sleep={len(extract.sleep_daily)}({n_s}), wellness={len(extract.wellness_daily)}({n_w}), errors={len(extract.errors)}"
                        )
                        if extract.errors:
                            st.warning("Deep sync completed with some endpoint errors. See logs below.")
                            for err in extract.errors[:20]:
                                _sync_log(f"[error] {err}")
                except Exception as exc:
                    msg = (
                        "Garmin login/fetch failed. Verify sidebar Garmin credentials or GARMIN_EMAIL / GARMIN_PASSWORD. "
                        f"Error: {exc}"
                    )
                    messages.append(msg)
                    st.warning(msg)
                    _sync_log(f"[error] garmin_fetch_failed {exc}")
            else:
                messages.append("Garmin credentials not set. Skipped Garmin API sync.")
                _sync_log("[skip] Garmin credentials missing.")

        if source in {"File Import", "Both"}:
            sync_progress.progress(80, text="Quick sync: scanning local import folder...")
            _sync_log(f"[fetch] file import from {cfg.import_dir}")
            rows = import_runs_from_folder(cfg.import_dir, days_back=int(days_back))
            sync_progress.progress(88, text="Quick sync: upserting imported activities...")
            changed = upsert_activities(cfg.db_path, rows)
            total_rows += len(rows)
            messages.append(f"File import: found {len(rows)} runs ({changed} DB row changes).")
            _sync_log(f"[fetch:done] file_rows={len(rows)} | db_changes={changed}")

        raw_cache_dir = cfg.private_export_dir / "raw"
        if raw_persistence_allowed and raw_cache_dir.exists():
            sync_progress.progress(94, text="Sync: updating splits from raw cache...")
            _sync_log("[splits] syncing splits from raw activity cache")
            split_rows, split_errors = _sync_splits_from_raw_activity_cache(raw_cache_dir)
            split_changes = upsert_activity_splits(cfg.db_path, split_rows)
            messages.append(f"Splits: synced {len(split_rows)} rows ({split_changes} DB row changes).")
            _sync_log(f"[splits:done] rows={len(split_rows)} | db_changes={split_changes} | errors={len(split_errors)}")
            if split_errors:
                st.warning("Some split files failed to parse during sync. First 20 shown in logs.")
                for err in split_errors[:20]:
                    _sync_log(f"[splits:error] {err}")
        else:
            _sync_log("[splits] no raw cache found; skipped raw split sync.")

        success = total_rows > 0 or any("Skipped" in m for m in messages)
        log_sync(cfg.db_path, source=source.lower().replace(" ", "_"), success=success, message=" | ".join(messages))
        sync_finished_at = datetime.now(timezone.utc)
        sync_duration_s = (sync_finished_at - sync_started_at).total_seconds()
        _sync_log(f"[done] {sync_finished_at.isoformat()} | duration_s={sync_duration_s:.1f}")
        if not raw_persistence_allowed:
            removed_files, removed_bytes = _cleanup_raw_garmin_artifacts(cfg.private_export_dir)
            _sync_log(
                f"[cleanup] removed raw artifacts: files={removed_files} bytes={removed_bytes}"
            )
        sync_progress.progress(100, text="Unified sync completed.")

        if total_rows > 0:
            st.success("Unified sync complete. " + " ".join(messages))
        else:
            st.info(
                "No activities found. If Garmin sync fails, place .FIT/.TCX files in "
                f"{cfg.import_dir} and run sync again."
            )
        with st.expander("Unified Sync Logs", expanded=True):
            _render_sync_logs()
        sync_triggered = True

    st.subheader("Comprehensive Garmin Extract")
    extract_row1 = st.columns([1.3, 1.0, 1.2, 1.0])
    with extract_row1[0]:
        extract_start = st.date_input("Start date", value=date(2025, 1, 1))
    with extract_row1[1]:
        incremental_extract = st.checkbox(
            "Incremental only",
            value=True,
            help=(
                "When enabled, extraction starts near the latest data already in DB. "
                "If Start date is explicitly older than the incremental anchor, that earlier date is honored."
            ),
        )
    with extract_row1[2]:
        run_extract = st.button("Run comprehensive extract", use_container_width=True)
    with extract_row1[3]:
        st.write("")

    extract_row2 = st.columns([1.3, 1.0, 1.2, 1.0])
    with extract_row2[0]:
        include_details = st.checkbox("Include activity details", value=True)
    with extract_row2[1]:
        include_wellness = st.checkbox("Include sleep + wellness", value=False)
    with extract_row2[2]:
        verify_raw_integrity = st.checkbox("Verify raw integrity", value=False)
    with extract_row2[3]:
        st.write("")

    if run_extract:
        if not _ensure_db_writable_or_warn(cfg.db_path, action_label="run comprehensive extract"):
            st.stop()
        if not raw_persistence_allowed:
            _cleanup_raw_garmin_artifacts(cfg.private_export_dir)
        if not (garmin_email and garmin_password):
            st.error("Garmin credentials missing. Add them in sidebar or GARMIN_EMAIL / GARMIN_PASSWORD.")
        else:
            extract_logs: list[str] = []
            extract_started_at = datetime.now(timezone.utc)
            log_box = st.empty()
            progress = st.progress(0, text="Starting comprehensive extract...")
            max_log_lines = 120

            def _render_logs() -> None:
                lines = extract_logs[-max_log_lines:]
                trimmed = len(extract_logs) - len(lines)
                prefix = [f"[info] showing last {len(lines)} logs (trimmed {trimmed})"] if trimmed > 0 else []
                log_box.code("\n".join(prefix + lines) if lines else "(no logs)", language="text")

            def _log(line: str) -> None:
                extract_logs.append(line)
                _render_logs()

            try:
                latest = get_latest_activity_time(cfg.db_path)
                earliest = get_earliest_activity_time(cfg.db_path)
                latest_recovery = get_latest_recovery_day(cfg.db_path) if include_wellness else None
                start_day = extract_start
                end_day = datetime.now(timezone.utc).date()
                if incremental_extract:
                    anchors: list[datetime] = []
                    if latest:
                        anchors.append(latest)
                    if latest_recovery:
                        anchors.append(latest_recovery)
                    if anchors:
                        # Incremental safety: use the earliest anchor across datasets so we
                        # don't skip activity updates when wellness is more recent (or vice-versa).
                        anchor = min(anchors)
                        incremental_anchor_day = (anchor - timedelta(days=2)).date()
                        historical_gap_backfill = bool(earliest and start_day < earliest.date())
                        if start_day < incremental_anchor_day:
                            if historical_gap_backfill:
                                _log(
                                    f"[info] incremental_anchor={anchor.isoformat()} "
                                    f"but honoring explicit earlier start_day={start_day.isoformat()} for historical gap backfill."
                                )
                            else:
                                start_day = incremental_anchor_day
                                _log(
                                    f"[info] incremental_anchor={anchor.isoformat()} "
                                    f"-> start_day clamped to {start_day.isoformat()} (ignored earlier non-gap start date)."
                                )
                        else:
                            start_day = max(start_day, incremental_anchor_day)
                            _log(
                                f"[info] incremental_anchor={anchor.isoformat()} -> computed_start_day={start_day.isoformat()}"
                            )
                    if earliest:
                        earliest_day = earliest.date()
                        if start_day < earliest_day:
                            capped_end_day = earliest_day - timedelta(days=1)
                            if capped_end_day < end_day:
                                end_day = capped_end_day
                                _log(
                                    f"[info] incremental_gap_backfill enabled: earliest_activity_in_db={earliest_day.isoformat()} "
                                    f"-> capping end_day={end_day.isoformat()} to avoid re-fetching existing newer activities."
                                )
                _log(
                    f"[start] {extract_started_at.isoformat()} | start_day={start_day} | "
                    f"end_day={end_day} | incremental_only={incremental_extract} | "
                    f"include_details={include_details} | "
                    f"include_wellness={include_wellness}"
                )
                if latest:
                    _log(f"[info] latest_activity_in_db={latest.isoformat()}")
                else:
                    _log("[info] latest_activity_in_db=None")
                if earliest:
                    _log(f"[info] earliest_activity_in_db={earliest.isoformat()}")
                else:
                    _log("[info] earliest_activity_in_db=None")
                if include_wellness:
                    if latest_recovery:
                        _log(f"[info] latest_recovery_day_in_db={latest_recovery.date().isoformat()}")
                    else:
                        _log("[info] latest_recovery_day_in_db=None")
                if end_day < start_day:
                    _log("[done] No missing date gap to backfill for the selected start date.")
                    progress.progress(100, text="No missing range detected. Nothing to fetch.")
                    st.info("No missing range detected for the selected start date with Incremental mode.")
                    with st.expander("Comprehensive Extract Logs", expanded=True):
                        _render_logs()
                    st.stop()
                _log("[fetch] activity summaries + FIT records")
                if include_details:
                    _log("[fetch] activity details endpoints: details/weather/hr_timezones + splits")
                if include_wellness:
                    _log("[fetch] daily wellness endpoints: sleep/stress/hrv/rhr/readiness/respiration/steps")
                progress.progress(15, text="Fetching Garmin data...")
                progress_state = {"last_activity_pct": -1, "last_wellness_idx": -1, "seeking_logged": False}

                def _on_fetch_progress(payload: dict) -> None:
                    phase = str(payload.get("phase") or "")
                    if phase == "activities":
                        frac = float(payload.get("fraction") or 0.0)
                        if include_wellness:
                            pct = int(15 + (frac * 50))
                        else:
                            pct = int(15 + (frac * 70))
                        pct = max(15, min(85, pct))
                        oldest = payload.get("oldest_in_batch")
                        processed = int(payload.get("processed") or 0)
                        fetched = int(payload.get("fetched") or 0)
                        total = int(payload.get("total") or 0)
                        day_s = payload.get("day")
                        oldest_day: date | None = None
                        if oldest:
                            try:
                                oldest_day = pd.to_datetime(oldest, errors="coerce").date()
                            except Exception:
                                oldest_day = None
                        seeking_window = bool(
                            oldest_day is not None and oldest_day > end_day and processed <= 0 and fetched <= 0
                        )
                        if seeking_window:
                            progress.progress(
                                15,
                                text=(
                                    "Seeking target date window..."
                                    + (f" | oldest seen: {oldest}" if oldest else "")
                                    + f" | target end: {end_day.isoformat()}"
                                ),
                            )
                            if not bool(progress_state.get("seeking_logged")):
                                _log(
                                    "[info] seeking target date window before fetch starts"
                                    + (f" | oldest_seen={oldest}" if oldest else "")
                                    + f" | target_end={end_day.isoformat()}"
                                )
                                progress_state["seeking_logged"] = True
                        else:
                            progress.progress(
                                pct,
                                text=(
                                    f"Fetching activities... {pct}%"
                                    + (f" | oldest seen: {oldest}" if oldest else "")
                                    + (f" | processed: {processed}" if processed > 0 else "")
                                    + (f" | {fetched}/{total}" if total > 0 else "")
                                ),
                            )
                        rounded = (pct // 5) * 5
                        if (not seeking_window) and (
                            rounded > int(progress_state["last_activity_pct"]) or (processed > 0 and (processed % 10 == 0))
                        ):
                            _log(
                                f"[progress] activities "
                                + (f"{fetched}/{total}" if total > 0 and fetched > 0 else f"{pct}%")
                                + (f" | day={day_s}" if day_s else "")
                                + (f" | oldest_seen={oldest}" if oldest else "")
                            )
                            progress_state["last_activity_pct"] = rounded
                    elif phase == "wellness" and include_wellness:
                        cur = int(payload.get("current") or 0)
                        total = int(payload.get("total") or 0)
                        frac = float(payload.get("fraction") or 0.0)
                        pct = int(65 + (frac * 20))
                        pct = max(65, min(90, pct))
                        day_s = payload.get("day")
                        progress.progress(
                            pct,
                            text=(
                                f"Fetching wellness... {pct}%"
                                + (f" | day {cur}/{total}" if total > 0 else "")
                                + (f" | {day_s}" if day_s else "")
                            ),
                        )
                        if cur != int(progress_state["last_wellness_idx"]) and (cur == 1 or (cur % 7 == 0) or cur == total):
                            _log(
                                f"[progress] wellness {cur}/{total}"
                                + (f" | day={day_s}" if day_s else "")
                            )
                            progress_state["last_wellness_idx"] = cur
                    elif phase == "complete":
                        progress.progress(90, text="Fetch completed. Upserting DB...")

                with st.spinner("Extracting Garmin data. This can take a few minutes..."):
                    if raw_persistence_allowed:
                        extract = fetch_garmin_comprehensive(
                            email=garmin_email,
                            password=garmin_password,
                            start_day=start_day,
                            end_day=end_day,
                            include_activity_details=include_details,
                            include_splits=include_details,
                            include_wellness=include_wellness,
                            raw_export_dir=cfg.private_export_dir / "raw",
                            progress_cb=_on_fetch_progress,
                        )
                    else:
                        with tempfile.TemporaryDirectory(prefix="temperance_raw_ingest_") as _tmp_raw:
                            extract = fetch_garmin_comprehensive(
                                email=garmin_email,
                                password=garmin_password,
                                start_day=start_day,
                                end_day=end_day,
                                include_activity_details=include_details,
                                include_splits=include_details,
                                include_wellness=include_wellness,
                                raw_export_dir=Path(_tmp_raw),
                                progress_cb=_on_fetch_progress,
                            )
                owner_ok, owner_msg = _enforce_garmin_owner_scope(extract.activities)
                if not owner_ok:
                    raise RuntimeError(owner_msg)
                progress.progress(55, text="Fetch complete. Upserting DB...")
                _log(
                    f"[fetch:done] activities={len(extract.activities)} details={len(extract.activity_details)} "
                    f"records={len(extract.activity_records)} splits={len(extract.activity_splits)} "
                    f"sleep={len(extract.sleep_daily)} "
                    f"wellness={len(extract.wellness_daily)} errors={len(extract.errors)}"
                )

                _log("[db] upserting activities/details/records/splits/sleep/wellness...")
                n_a = upsert_activities(cfg.db_path, extract.activities)
                n_d = upsert_activity_details(cfg.db_path, extract.activity_details)
                n_r = upsert_activity_records(cfg.db_path, extract.activity_records)
                n_sp = upsert_activity_splits(cfg.db_path, extract.activity_splits)
                n_s = upsert_sleep_daily(cfg.db_path, extract.sleep_daily)
                n_w = upsert_wellness_daily(cfg.db_path, extract.wellness_daily)
                _log(
                    f"[db:done] activities_changes={n_a} details_changes={n_d} records_changes={n_r} "
                    f"splits_changes={n_sp} "
                    f"sleep_changes={n_s} wellness_changes={n_w}"
                )

                if raw_persistence_allowed:
                    snapshot_file = cfg.private_export_dir / f"garmin_extract_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
                    dump_extract_to_json(snapshot_file, extract)
                    _log(f"[snapshot] {snapshot_file}")
                    st.info(f"Snapshot saved locally at: {snapshot_file}")
                else:
                    _log("[snapshot] disabled (raw artifacts are not persisted for non-admin).")
                progress.progress(80, text="Finalizing...")

                msg = (
                    f"activities={len(extract.activities)} (db_changes={n_a}), "
                    f"details={len(extract.activity_details)} (db_changes={n_d}), "
                    f"records={len(extract.activity_records)} (db_changes={n_r}), "
                    f"splits={len(extract.activity_splits)} (db_changes={n_sp}), "
                    f"sleep={len(extract.sleep_daily)} (db_changes={n_s}), "
                    f"wellness={len(extract.wellness_daily)} (db_changes={n_w}), "
                    f"errors={len(extract.errors)}"
                )
                log_sync(cfg.db_path, source="garmin_comprehensive", success=True, message=msg)
                st.success("Comprehensive extract complete. " + msg)
                if extract.errors:
                    st.warning("Some endpoints failed for specific days/activities. First 20 errors:")
                    st.code("\n".join(extract.errors[:20]))
                    _log("[errors] first 50 shown below")

                extract_finished_at = datetime.now(timezone.utc)
                duration_s = (extract_finished_at - extract_started_at).total_seconds()
                _log(f"[done] {extract_finished_at.isoformat()} | duration_s={duration_s:.1f}")
                if extract.errors:
                    for err in extract.errors[:50]:
                        _log(f"[error] {err}")

                if verify_raw_integrity:
                    if raw_persistence_allowed:
                        progress.progress(95, text="Running raw archive integrity check...")
                        _log("[verify] checking raw activities/wellness/FIT cache integrity...")
                        integrity = _check_raw_archive_integrity(
                            cfg.private_export_dir / "raw",
                            start_day=start_day,
                            end_day=datetime.now(timezone.utc).date(),
                        )
                        _log(
                            f"[verify:done] checked_json={integrity['checked_json']} checked_fit={integrity['checked_fit']} "
                            f"errors={len(integrity['errors'])}"
                        )
                        for err in list(integrity["errors"])[:40]:
                            _log(f"[verify:error] {err}")
                    else:
                        _log("[verify] skipped: raw archive persistence is disabled for non-admin.")
                if not raw_persistence_allowed:
                    removed_files, removed_bytes = _cleanup_raw_garmin_artifacts(cfg.private_export_dir)
                    _log(
                        f"[cleanup] removed raw artifacts: files={removed_files} bytes={removed_bytes}"
                    )
                progress.progress(100, text="Comprehensive extract completed.")
                with st.expander("Comprehensive Extract Logs", expanded=True):
                    _render_logs()
                sync_triggered = True
            except Exception as exc:
                _log(f"[fatal] {exc}")
                if not raw_persistence_allowed:
                    removed_files, removed_bytes = _cleanup_raw_garmin_artifacts(cfg.private_export_dir)
                    _log(f"[cleanup] removed raw artifacts: files={removed_files} bytes={removed_bytes}")
                progress.progress(100, text="Comprehensive extract failed.")
                log_sync(cfg.db_path, source="garmin_comprehensive", success=False, message=str(exc))
                st.error(f"Comprehensive extract failed: {exc}")

    if sync_triggered:
        st.rerun()

st.caption(f"Now: {datetime.now(timezone.utc).isoformat()} UTC")

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from dataclasses import replace
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from analytics import (
    build_daily_summary,
    compute_metrics,
    display_table,
    ema,
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
    get_activity_splits_df,
    get_activity_records_df,
    get_activity_detail_raw,
    get_activity_raw,
    get_daily_summary_df,
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

_assets_dir = Path(__file__).resolve().parent / "assets"
_logo_png = _assets_dir / "temperance_logo.png"
_logo_svg = _assets_dir / "temperance_logo.svg"
# Prefer SVG to avoid accidental baked backgrounds in raster exports.
_logo_file = _logo_svg if _logo_svg.exists() else _logo_png

st.markdown(
    """
    <style>
      .temp-hero-wrap {
        border: 1px solid rgba(148,163,184,0.3);
        background: linear-gradient(120deg, rgba(2,132,199,0.12), rgba(37,99,235,0.08));
        border-radius: 14px;
        padding: 14px 18px;
        margin-bottom: 0.4rem;
      }
      .temp-hero-title {
        margin: 0;
        font-size: 1.75rem;
      }
      .temp-hero-sub {
        margin: 0.35rem 0 0;
        color: #475569;
      }
      .temp-hero-logo {
        width: 112px;
        max-width: 100%;
        height: auto;
        object-fit: contain;
        display: block;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="temp-hero-wrap">', unsafe_allow_html=True)
logo_col, text_col = st.columns([1, 8], vertical_alignment="center")
with logo_col:
    if _logo_file.exists():
        st.image(str(_logo_file), width=112)
with text_col:
    st.markdown('<h1 class="temp-hero-title">Temperance</h1>', unsafe_allow_html=True)
    st.markdown('<p class="temp-hero-sub">Local-first running load tracker (aerobic + mechanical)</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

DEFAULT_RESTING_HR = 45.0
DEFAULT_LTHR = 178.0
DEFAULT_THRESHOLD_PACE_SEC_PER_KM = 300.0
CUSTOM_ACTIVITIES_LIMIT = 5000
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

AUTH_ALL_TABS = [
    "Dashboard",
    "Calendar",
    "Week Planner",
    "Custom Activities",
    "Activity Detail",
    "Recovery Data",
    "Data Extract",
    "User Inputs",
]
AUTH_VIEWER_TABS = [
    "Dashboard",
    "Calendar",
    "Week Planner",
    "Custom Activities",
    "Activity Detail",
    "Recovery Data",
    "Data Extract",
    "User Inputs",
]


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


def _sport_label(sport_type: str | None) -> str:
    raw = str(sport_type or "").strip().replace("_", " ")
    if not raw:
        return "Activity"
    return raw.title()


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
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)\b", t)
    if m:
        total = float(m.group(1))
        return total if total > 0 else None
    return None


def _parse_distance_km_token(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*km\b", text.lower())
    if not m:
        return None
    try:
        km = float(m.group(1))
    except Exception:
        return None
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


def _normalize_plan_text(text: str) -> str:
    t = " ".join(str(text or "").strip().split())
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)\b", r"\1min", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*h\b", r"\1h", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*km\b", r"\1km", t, flags=re.IGNORECASE)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*bpm\b", r"\1bpm", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*/\s*km\b", "/km", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\+\s*", " + ", t)
    return t


def _parse_dated_activity_entry(text: str) -> tuple[pd.Timestamp | None, str, str | None]:
    raw = str(text or "").strip()
    if not raw:
        return None, "", "Input is empty. Use `[date]:[activity]`."
    if ":" not in raw:
        return None, "", "Missing `:` separator. Use `[date]:[activity]`."
    date_text, activity_text = raw.split(":", 1)
    date_text = date_text.strip()
    activity_text = _normalize_plan_text(activity_text)
    if not date_text:
        return None, "", "Missing date before `:`."
    if not activity_text:
        return None, "", "Missing activity after `:`."

    date_value: pd.Timestamp | None = None
    for fmt in ("%d%b%y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            date_value = pd.Timestamp(datetime.strptime(date_text, fmt))
            break
        except Exception:
            continue
    if date_value is None:
        return None, activity_text, "Invalid date format. Use one of: `3Mar26`, `2026-03-26`, `26/03/2026`."
    return date_value, activity_text, None


def _split_dated_activity_entries(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    return [p.strip() for p in re.split(r"[\n;,]+", raw) if p.strip()]


def _expand_planned_segments(line: str) -> tuple[list[dict[str, float | str | None]], list[str]]:
    segments: list[dict[str, float | str | None]] = []
    warnings: list[str] = []
    raw = _normalize_plan_text(line)
    if not raw:
        return segments, warnings

    chunks = [c.strip() for c in re.split(r"\s*\+\s*", raw) if c.strip()]
    last_kind: str | None = None
    for chunk in chunks:
        kind = _plan_activity_kind(chunk)
        bpm = _parse_bpm_token(chunk)
        pace = _parse_pace_token(chunk)
        if_input = _parse_if_token(chunk)
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
        if bpm is None and pace is None and if_input is None:
            warnings.append(f"Missing intensity in: `{chunk}` (add `@140bpm`, `@70%`, or `@4:50/km`)")
            continue

        rep_match = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)\b", chunk.lower())
        if rep_match:
            reps = int(rep_match.group(1))
            rep_minutes = float(rep_match.group(2))
            if reps <= 0 or rep_minutes <= 0:
                warnings.append(f"Invalid interval block in: `{chunk}`")
                continue
            for _ in range(max(reps, 0)):
                segments.append(
                    {
                        "kind": kind,
                        "duration_min": rep_minutes,
                        "avg_hr_bpm": bpm,
                        "pace_s_per_km": pace,
                        "if_input": if_input,
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
        segments.append(
            {
                "kind": kind,
                "duration_min": minutes,
                "avg_hr_bpm": bpm,
                "pace_s_per_km": pace,
                "if_input": if_input,
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
            m = _planned_segment_metrics(
                seg,
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
    out = planned_rows.copy()
    out["day_utc"] = out["day_utc"].astype(str)
    out["line_no"] = pd.to_numeric(out["line_no"], errors="coerce").fillna(0).astype(int)
    out = out.sort_values(["day_utc", "line_no"], ascending=[True, True]).copy()

    actual_counts: dict[str, int] = {}
    if not actual_metrics.empty and "start_time_utc" in actual_metrics.columns:
        actual_ts = pd.to_datetime(actual_metrics["start_time_utc"], utc=True, errors="coerce")
        actual_ts = actual_ts.dropna()
        if not actual_ts.empty:
            local_tz = datetime.now().astimezone().tzinfo
            local_days = actual_ts.dt.tz_convert(local_tz).dt.strftime("%Y-%m-%d")
            actual_counts = local_days.value_counts().to_dict()

    now_local = datetime.now().astimezone()
    today_str = now_local.strftime("%Y-%m-%d")
    after_5pm_today = now_local.hour >= 17

    kept_parts: list[pd.DataFrame] = []
    for day_key, group in out.groupby("day_utc", sort=False):
        g = group.sort_values("line_no").copy()
        actual_n = int(actual_counts.get(str(day_key), 0))
        drop_n = 0
        if actual_n >= 1:
            drop_n = 1
        # Keep second planned workout for split morning sessions unless day is effectively "closed".
        day_closed = (str(day_key) < today_str) or (str(day_key) == today_str and after_5pm_today)
        if actual_n > 2 and day_closed:
            drop_n = 2
        g = g.iloc[min(drop_n, len(g)) :]
        if not g.empty:
            kept_parts.append(g)
    if not kept_parts:
        return out.iloc[0:0].copy()
    return pd.concat(kept_parts, ignore_index=True)


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
    # Re-scale it at view time so UI specificity changes are reflected without full recompute.
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
            if "if_proxy" in out.columns:
                out.loc[proxy_mask, "if_proxy"] = (
                    pd.to_numeric(out.loc[proxy_mask, "if_proxy"], errors="coerce").fillna(0.0).values
                    * proxy_scale.values
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


def get_metrics_df_fast(
    db_path: Path,
    activities_cache_key: str,
    activity_splits_cache_key: str,
    lthr_bpm: float,
    lthr_curve_points: list[tuple[datetime, float]] | None,
    threshold_pace_default_sec: float,
    threshold_pace_curve_points: list[tuple[datetime, float]] | None,
    use_split_method: bool,
) -> pd.DataFrame:
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


def _build_custom_metrics_df_for_plots(
    db_path: Path,
    lthr_bpm: float,
    lthr_curve_points: list[tuple[datetime, float]] | None,
    threshold_pace_default_sec: float,
    threshold_pace_curve_points: list[tuple[datetime, float]] | None,
) -> pd.DataFrame:
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

        day_for_curve = pd.to_datetime(day_utc, utc=True, errors="coerce")
        if pd.isna(day_for_curve):
            continue
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
        pace_proxy = (total_duration_s / total_dist_eqv_km) if total_dist_eqv_km > 0 else None
        start_time = day_for_curve + pd.Timedelta(minutes=max(line_no, 1))

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
                "hr_time_in_zone_1": 0.0,
                "hr_time_in_zone_2": 0.0,
                "hr_time_in_zone_3": 0.0,
                "hr_time_in_zone_4": 0.0,
                "hr_time_in_zone_5": 0.0,
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
        dur_s = _num(lap, ["duration", "movingDuration", "elapsedDuration", "lapDuration", "totalDuration"])
        dist_m = _num(lap, ["distance", "totalDistance", "sumDistance", "distanceInMeters", "distanceMeters"])
        if dur_s is None or dur_s <= 0:
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
                "intensity_type": str(lap.get("intensityType") or ""),
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

    out = pd.DataFrame(rows).sort_values("split_idx")
    if out.empty:
        return out

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
        training_series = pd.to_numeric(
            filtered_daily["tss_total"]
            if "tss_total" in filtered_daily.columns
            else filtered_daily["training_load_garmin"],
            errors="coerce",
        ).fillna(0.0)
        filtered_daily["fitness"] = ema(training_series, 42)
        filtered_daily["fatigue"] = ema(training_series, 7)
        filtered_daily["overreach"] = (ema(training_series, 10) - 70.0).clip(lower=0.0)
        rtss_series = (
            pd.to_numeric(filtered_daily["rtss_total"], errors="coerce").fillna(0.0)
            if "rtss_total" in filtered_daily.columns
            else pd.Series([0.0] * len(filtered_daily), index=filtered_daily.index)
        )
        filtered_daily["leg_elasticity"] = ema(rtss_series, 100)
        filtered_daily["pounding"] = ema(rtss_series, 7)
        filtered_daily["injury_risk"] = (ema(rtss_series, 10) - 70.0).clip(lower=0.0)
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


@st.cache_data(show_spinner=False)
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

with st.sidebar:
    st.header("Navigation")
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
        st.subheader("Login")
        login_user = st.text_input("User", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Sign in", key="login_submit"):
            resolved_user, user_data = resolve_user(users, login_user)
            if user_data and password_matches(login_pass, user_data["password_hash"]):
                st.session_state["auth_user"] = resolved_user
                st.session_state["auth_role"] = user_data["role"]
                st.rerun()
            st.error("Invalid credentials.")
        st.stop()

    if auth_on:
        st.caption(f"Signed in as `{st.session_state.get('auth_user')}` ({st.session_state.get('auth_role')})")
        if st.button("Logout", key="logout_btn"):
            st.session_state["auth_user"] = None
            st.session_state["auth_role"] = None
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
    preferred_order = ["Calendar", "Week Planner", "Dashboard"]
    ordered_tabs = [v for v in preferred_order if v in allowed_tabs] + [
        v for v in allowed_tabs if v not in preferred_order
    ]
    page_labels = {
        "Calendar": "Activity Summary",
        "Week Planner": "Week Planner",
        "Custom Activities": "Custom Activities",
        "Dashboard": "Plot Charts",
        "Activity Detail": "Activity Detail",
        "Recovery Data": "Recovery Data",
        "Data Extract": "Data Extract",
        "User Inputs": "User Inputs",
    }
    label_to_view = {page_labels.get(v, v): v for v in ordered_tabs}
    default_view = "Calendar" if "Calendar" in ordered_tabs else ordered_tabs[0]
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

previous_view = st.session_state.get("_previous_view")
st.session_state["_previous_view"] = view

cfg = _scoped_config_for_owner(st.session_state.get("data_owner") or "default")
init_db(cfg.db_path)
cfg.import_dir.mkdir(parents=True, exist_ok=True)
cfg.private_export_dir.mkdir(parents=True, exist_ok=True)

saved_injury_windows = _load_injury_windows(cfg.db_path)
saved_lthr_curve = _load_lthr_curve(cfg.db_path)
saved_lt_pace_curve = _load_lt_pace_curve(cfg.db_path)
saved_non_running_factor = _load_non_running_factor(cfg.db_path, default_value=0.8)
saved_specificity_profile = _load_specificity_profile(cfg.db_path, fallback_default=saved_non_running_factor)
if "user_specificity_profile" not in st.session_state:
    st.session_state["user_specificity_profile"] = dict(saved_specificity_profile)
if "user_non_running_factor" not in st.session_state:
    st.session_state["user_non_running_factor"] = float(
        st.session_state["user_specificity_profile"].get("non_running", saved_non_running_factor)
    )
derived_lthr_bpm = _curve_latest_value(saved_lthr_curve, "lthr_bpm", DEFAULT_LTHR)
derived_threshold_pace_sec = _curve_latest_value(
    saved_lt_pace_curve, "lt_pace_sec_per_km", DEFAULT_THRESHOLD_PACE_SEC_PER_KM
)
lthr_curve_points = _curve_points_from_rows(saved_lthr_curve, "lthr_bpm")
lt_pace_curve_points = _curve_points_from_rows(saved_lt_pace_curve, "lt_pace_sec_per_km")

if view == "User Inputs":
    st.divider()
    st.header("User Inputs")
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
metrics_df = get_metrics_df_fast(
    db_path=cfg.db_path,
    activities_cache_key=activities_cache_key,
    activity_splits_cache_key=activity_splits_cache_key,
    lthr_bpm=float(derived_lthr_bpm),
    lthr_curve_points=lthr_curve_points,
    threshold_pace_default_sec=float(derived_threshold_pace_sec),
    threshold_pace_curve_points=lt_pace_curve_points,
    use_split_method=bool(use_split_method),
)
daily_summary_df = get_daily_summary_df(cfg.db_path)

if view == "Dashboard":
    st.divider()
    st.header("Dashboard")
    dashboard_metrics_df = _merge_metrics_with_custom(
        metrics_df,
        _build_custom_metrics_df_for_plots(
            db_path=cfg.db_path,
            lthr_bpm=float(derived_lthr_bpm),
            lthr_curve_points=lthr_curve_points,
            threshold_pace_default_sec=float(derived_threshold_pace_sec),
            threshold_pace_curve_points=lt_pace_curve_points,
        ),
    )

    if dashboard_metrics_df.empty:
        st.info(
            "No activities yet. Use Sync above. "
            "For your full archive, run Comprehensive Garmin Extract from Jan 1, 2025."
        )
    else:
        st.caption("Missing-day fill mode is fixed to zero for chart calculations (EMA and aggregations).")
        controls = st.columns([1, 1, 1, 1.2])
        with controls[0]:
            metrics_min_day = pd.to_datetime(dashboard_metrics_df["start_time_utc"], utc=True, errors="coerce").dt.tz_localize(None).min().date()
            metrics_max_day = pd.to_datetime(dashboard_metrics_df["start_time_utc"], utc=True, errors="coerce").dt.tz_localize(None).max().date()
            if daily_summary_df.empty:
                min_day = metrics_min_day
                max_day = metrics_max_day
            else:
                daily_min_day = pd.to_datetime(daily_summary_df["day_utc"], errors="coerce").min().date()
                daily_max_day = pd.to_datetime(daily_summary_df["day_utc"], errors="coerce").max().date()
                min_day = min(metrics_min_day, daily_min_day)
                max_day = max(metrics_max_day, daily_max_day)
            quick_range = st.selectbox("Quick range", ["YTD", "3M", "6M", "9M", "1Y", "2Y", "ALL", "Custom"], index=4)
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
            chart_type = "line"
            st.caption("Chart type: line")
            weekly_toggle = st.checkbox("Weekly aggregation", value=True)
        with controls[3]:
            compare_mode = st.checkbox("Compare mode (up to 3 metrics)", value=False)
            enable_zoom = st.checkbox("Zoom/pan", value=False)
            top_injury_overlay = st.checkbox("Top injury overlay", value=False)

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
        )
        range_filtered_metrics = filtered_metrics[
            (pd.to_datetime(filtered_metrics["start_time_utc"], utc=True, errors="coerce").dt.tz_localize(None) >= start_ts)
            & (pd.to_datetime(filtered_metrics["start_time_utc"], utc=True, errors="coerce").dt.tz_localize(None) < end_exclusive_ts)
        ].copy()
        filtered_daily_range = filtered_daily[
            (pd.to_datetime(filtered_daily["day_utc"], errors="coerce") >= start_ts)
            & (pd.to_datetime(filtered_daily["day_utc"], errors="coerce") < end_exclusive_ts)
        ].copy()

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

        base_df = filtered_daily_range.copy()
        if base_df.empty:
            st.info(f"No data for activity filter: {activity_filter}")
        else:
            prepared_base_df = base_df.copy()
            numeric_metric_cols = sorted({m for m, _ in metric_map.values()})
            for col in numeric_metric_cols:
                if col in prepared_base_df.columns:
                    prepared_base_df[col] = pd.to_numeric(prepared_base_df[col], errors="coerce").fillna(0.0)
            prepared_base_df["day"] = pd.to_datetime(prepared_base_df["day_utc"], errors="coerce")
            series_full_index = pd.date_range(start=start_ts, end=end_ts, freq="D")
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
                default_index = metric_labels.index(default_metric) if default_metric in metric_labels else 0
                selected_labels = [st.selectbox("Metric", metric_labels, index=default_index)]

            ema_ns: list[int] = []
            ema_pairs: list[tuple[int, int]] = []
            if not compare_mode:
                ema_windows = st.text_input("EMA windows (days, comma-separated)", value="4,16")
                ema_ns, ema_pairs = parse_ma_windows(ema_windows)
                if ema_ns:
                    alpha_text = ", ".join([f"EMA {n} -> alpha={ema_alpha_from_days(n):.4f}" for n in ema_ns])
                    st.caption(alpha_text)
                if ema_pairs:
                    pair_text = ", ".join([f"EMA{a}-EMA{b}" for a, b in ema_pairs])
                    st.caption(f"EMA spread overlays: {pair_text}")

            plot_frames: list[pd.DataFrame] = []
            if compare_mode:
                labels_and_axis = [(label, "left") for label in left_axis_labels] + [
                    (label, "right") for label in right_axis_labels
                ]
            else:
                labels_and_axis = [(label, "left") for label in selected_labels]

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
                    for n in ema_ns:
                        col = f"EMA{n}"
                        frame[col] = ema(frame["value"], n)
                        overlay_cols.append(col)
                    for a, b in ema_pairs:
                        col_a = f"EMA{a}"
                        col_b = f"EMA{b}"
                        if col_a not in frame.columns:
                            frame[col_a] = ema(frame["value"], a)
                        if col_b not in frame.columns:
                            frame[col_b] = ema(frame["value"], b)
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
                    top_sel = alt.selection_point(fields=["series"], bind="legend")
                    chart = chart.encode(
                        opacity=alt.condition(
                            top_sel,
                            alt.Opacity("base_opacity:Q", legend=None),
                            alt.value(0.08),
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
                    st.altair_chart(chart, use_container_width=True)

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
                st.altair_chart(compare_chart, use_container_width=True)
            elif compare_mode:
                st.caption("No comparable data found for the selected metrics/date range.")

        section_choice = st.selectbox(
            "Section",
            ["Summary", "Injury Risk", "Fitness", "Activities"],
            index=0,
        )

        weekly = weekly_summary(range_filtered_metrics)
        weekly["week_start"] = pd.to_datetime(weekly["week_start"])

        if section_choice == "Summary":
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
                else:
                    tss_base = filtered_daily_range[["day_utc", "tss_total", "rtss_total"]].copy()
                    tss_base["period_start"] = pd.to_datetime(tss_base["day_utc"], errors="coerce")
                    tss_base["tss"] = pd.to_numeric(tss_base["tss_total"], errors="coerce").fillna(0.0)
                    tss_base["rtss"] = pd.to_numeric(tss_base["rtss_total"], errors="coerce").fillna(0.0)
                    tss_base = tss_base[["period_start", "tss", "rtss"]].dropna(subset=["period_start"]).sort_values("period_start")
                tss_plot = tss_base.melt(
                    id_vars=["period_start"],
                    value_vars=["tss", "rtss"],
                    var_name="series",
                    value_name="value",
                )
                tss_plot["series"] = tss_plot["series"].replace(
                    {"tss": "TSS", "rtss": "rTSS"}
                )
                st.subheader("TSS vs rTSS")
                tss_chart = (
                    alt.Chart(tss_plot)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("period_start:T", axis=alt.Axis(title="")),
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                        color=alt.Color(
                            "series:N",
                            legend=alt.Legend(title="", orient="bottom", direction="horizontal"),
                            scale=alt.Scale(domain=["TSS", "rTSS"], range=["#60a5fa", "#f59e0b"]),
                        ),
                        tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                    .properties(height=280)
                )
                tss_sel = alt.selection_point(fields=["series"], bind="legend")
                tss_chart = tss_chart.encode(
                    opacity=alt.condition(tss_sel, alt.value(1.0), alt.value(0.08), empty=True)
                ).add_params(tss_sel)
                threshold_value = 500.0 if weekly_toggle else 70.0
                tss_threshold = (
                    alt.Chart(pd.DataFrame({"threshold": [threshold_value]}))
                    .mark_rule(color="#f59e0b", strokeDash=[6, 4], opacity=0.8)
                    .encode(y="threshold:Q")
                )
                tss_chart = alt.layer(tss_chart, tss_threshold)
                tss_chart = alt.layer(build_injury_layer(saved_injury_windows, start_ts, end_ts), tss_chart)
                if enable_zoom:
                    tss_chart = tss_chart.interactive()
                st.altair_chart(tss_chart, use_container_width=True)
                st.caption(
                    f"The dotted line is Stress Score {int(threshold_value)} "
                    f"({'weekly' if weekly_toggle else 'daily'} mode). "
                    "For good training, keep TSS above it while rTSS stays below it."
                )

        if section_choice == "Fitness":
            st.subheader("Fitness vs Fatigue")
            if not filtered_daily_range.empty and "fitness" in filtered_daily_range.columns and "fatigue" in filtered_daily_range.columns:
                ff_base = filtered_daily_range[["day_utc", "fitness", "fatigue"]].copy()
                ff_base["period_start"] = pd.to_datetime(ff_base["day_utc"], errors="coerce")
                ff_base = ff_base.dropna(subset=["period_start"])
                ff_base["fitness"] = pd.to_numeric(ff_base["fitness"], errors="coerce").fillna(0.0)
                ff_base["fatigue"] = pd.to_numeric(ff_base["fatigue"], errors="coerce").fillna(0.0)
                if weekly_toggle:
                    ff_base["period_start"] = ff_base["period_start"].dt.to_period("W-SUN").dt.start_time
                    ff_base = ff_base.groupby("period_start", as_index=False)[["fitness", "fatigue"]].mean().sort_values("period_start")
                weekly_ff_long = ff_base.melt(
                    id_vars=["period_start"],
                    value_vars=["fitness", "fatigue"],
                    var_name="series",
                    value_name="value",
                )
                weekly_ff_long["series"] = (
                    weekly_ff_long["series"]
                    .astype(str)
                    .str.strip()
                    .map({"fitness": "Fitness", "fatigue": "Fatigue"})
                    .fillna("Unknown")
                )
                ff_chart = (
                    alt.Chart(weekly_ff_long)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("period_start:T", axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10)),
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                        color=alt.Color(
                            "series:N",
                            legend=alt.Legend(orient="bottom", direction="horizontal"),
                            scale=alt.Scale(domain=["Fitness", "Fatigue"], range=["#22c55e", "#ef4444"]),
                        ),
                        tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                )
                ff_sel = alt.selection_point(fields=["series"], bind="legend")
                ff_chart = ff_chart.encode(
                    opacity=alt.condition(ff_sel, alt.value(1.0), alt.value(0.08), empty=True)
                ).add_params(ff_sel)
                ff_chart = alt.layer(build_injury_layer(saved_injury_windows, start_ts, end_ts), ff_chart)
                if enable_zoom:
                    ff_chart = ff_chart.interactive()
                st.altair_chart(ff_chart, use_container_width=True)
            else:
                st.caption("No fitness/fatigue data to plot.")

        if section_choice == "Injury Risk":
            st.subheader("Leg Elasticity vs Pounding")
            if not filtered_daily_range.empty and "leg_elasticity" in filtered_daily_range.columns and "pounding" in filtered_daily_range.columns:
                rff_base = filtered_daily_range[["day_utc", "leg_elasticity", "pounding"]].copy()
                rff_base["period_start"] = pd.to_datetime(rff_base["day_utc"], errors="coerce")
                rff_base = rff_base.dropna(subset=["period_start"])
                rff_base["leg_elasticity"] = pd.to_numeric(rff_base["leg_elasticity"], errors="coerce").fillna(0.0)
                rff_base["pounding"] = pd.to_numeric(rff_base["pounding"], errors="coerce").fillna(0.0)
                if weekly_toggle:
                    rff_base["period_start"] = rff_base["period_start"].dt.to_period("W-SUN").dt.start_time
                    rff_base = rff_base.groupby("period_start", as_index=False)[["leg_elasticity", "pounding"]].mean().sort_values("period_start")
                weekly_rff_long = rff_base.melt(
                    id_vars=["period_start"],
                    value_vars=["leg_elasticity", "pounding"],
                    var_name="series",
                    value_name="value",
                )
                weekly_rff_long["series"] = weekly_rff_long["series"].replace(
                    {"leg_elasticity": "Leg Elasticity", "pounding": "Pounding"}
                )
                rff_chart = (
                    alt.Chart(weekly_rff_long)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("period_start:T", axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10)),
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                        color=alt.Color(
                            "series:N",
                            legend=alt.Legend(orient="bottom", direction="horizontal"),
                            scale=alt.Scale(domain=["Leg Elasticity", "Pounding"], range=["#22c55e", "#ef4444"]),
                        ),
                        tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                )
                rff_threshold = (
                    alt.Chart(pd.DataFrame({"threshold": [70.0]}))
                    .mark_rule(color="#f59e0b", strokeDash=[6, 4], opacity=0.8)
                    .encode(y="threshold:Q")
                )
                rff_chart = alt.layer(rff_chart, rff_threshold)
                rff_chart = alt.layer(build_injury_layer(saved_injury_windows, start_ts, end_ts), rff_chart)
                if enable_zoom:
                    rff_chart = rff_chart.interactive()
                st.altair_chart(rff_chart, use_container_width=True)
            else:
                st.caption("No Leg Elasticity/Pounding data to plot.")

        if section_choice == "Summary":
            st.subheader("Distance vs Distance Eqv.")
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
                weekly_dist_sel = alt.selection_point(fields=["series"], bind="legend")
                weekly_dist_chart = weekly_dist_chart.encode(
                    opacity=alt.condition(weekly_dist_sel, alt.value(1.0), alt.value(0.08), empty=True)
                ).add_params(weekly_dist_sel)
                weekly_dist_chart = alt.layer(build_injury_layer(saved_injury_windows, start_ts, end_ts), weekly_dist_chart)
                if enable_zoom:
                    weekly_dist_chart = weekly_dist_chart.interactive()
                st.altair_chart(weekly_dist_chart, use_container_width=True)
                st.caption(
                    "Distance Eqv. = running-equivalent distance inferred from non-running sessions by matching "
                    "running rTSS to HR-based TSS scaled by specificity (applied once)."
                )
            else:
                st.caption("No distance-equivalent data to plot.")

        if section_choice == "Injury Risk":
            st.subheader("Overreach vs Injury Risk")
            if not filtered_daily_range.empty and "overreach" in filtered_daily_range.columns and "injury_risk" in filtered_daily_range.columns:
                fr_base = filtered_daily_range[["day_utc", "overreach", "injury_risk"]].copy()
                fr_base["period_start"] = pd.to_datetime(fr_base["day_utc"], errors="coerce")
                fr_base = fr_base.dropna(subset=["period_start"])
                fr_base["overreach"] = pd.to_numeric(fr_base["overreach"], errors="coerce").fillna(0.0)
                fr_base["injury_risk"] = pd.to_numeric(fr_base["injury_risk"], errors="coerce").fillna(0.0)
                if weekly_toggle:
                    fr_base["period_start"] = fr_base["period_start"].dt.to_period("W-SUN").dt.start_time
                    fr_base = fr_base.groupby("period_start", as_index=False)[["overreach", "injury_risk"]].mean().sort_values("period_start")
                weekly_fr_long = fr_base.melt(
                    id_vars=["period_start"],
                    value_vars=["overreach", "injury_risk"],
                    var_name="series",
                    value_name="value",
                )
                weekly_fr_long["series"] = weekly_fr_long["series"].replace(
                    {"overreach": "Overreach", "injury_risk": "Injury Risk"}
                )
                fr_chart = (
                    alt.Chart(weekly_fr_long)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("period_start:T", axis=alt.Axis(title="", format="%b %d", labelOverlap="greedy", tickCount=10)),
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f")),
                        color=alt.Color(
                            "series:N",
                            legend=alt.Legend(orient="bottom", direction="horizontal"),
                            scale=alt.Scale(domain=["Overreach", "Injury Risk"], range=["#60a5fa", "#ef4444"]),
                        ),
                        tooltip=["period_start:T", "series:N", alt.Tooltip("value:Q", format=".0f")],
                    )
                )
                fr_chart = alt.layer(build_injury_layer(saved_injury_windows, start_ts, end_ts), fr_chart)
                if enable_zoom:
                    fr_chart = fr_chart.interactive()
                st.altair_chart(fr_chart, use_container_width=True)
            else:
                st.caption("No Overreach/Injury Risk data to plot.")

        if section_choice == "Fitness":
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
                    legend_sel = alt.selection_point(fields=["series"], bind="legend")
                    left_chart = base.transform_filter(alt.datum.series == "Garmin Training Load").mark_line(point=True).encode(
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Garmin Training Load"))
                    )
                    right_chart = base.transform_filter(alt.datum.series == "Total Calories").mark_line(point=True).encode(
                        y=alt.Y("value:Q", axis=alt.Axis(format=".0f", title="Total Calories", orient="right"))
                    )
                    left_chart = left_chart.encode(
                        opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.08), empty=True)
                    )
                    right_chart = right_chart.encode(
                        opacity=alt.condition(legend_sel, alt.value(1.0), alt.value(0.08), empty=True)
                    )
                    weekly_chart = alt.layer(left_chart, right_chart).resolve_scale(y="independent")
                    weekly_chart = weekly_chart.add_params(legend_sel)
                    if enable_zoom:
                        weekly_chart = weekly_chart.interactive()
                    st.altair_chart(weekly_chart, use_container_width=True)
            else:
                st.caption("No Garmin training load/calories data to plot.")

        if section_choice == "Fitness":
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
                zone_df["day"] = pd.to_datetime(zone_df["start_time_utc"], utc=True, errors="coerce").dt.tz_localize(None)
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
                    zone_hours_sel = alt.selection_point(fields=["zone"], bind="legend")
                    left_layer = (
                        base.transform_filter(alt.datum.axis_side == "left")
                        .mark_line(point=True)
                        .encode(
                            y=alt.Y("hours:Q", axis=alt.Axis(title="hours", format=".1f")),
                            opacity=alt.condition(zone_hours_sel, alt.value(1.0), alt.value(0.08), empty=True),
                        )
                    )
                    right_layer = (
                        base.transform_filter(alt.datum.axis_side == "right")
                        .mark_line(point=True, strokeDash=[6, 4])
                        .encode(
                            y=alt.Y("hours:Q", axis=alt.Axis(title="total hours", format=".1f", orient="right")),
                            opacity=alt.condition(zone_hours_sel, alt.value(1.0), alt.value(0.08), empty=True),
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
                    st.altair_chart(zone_hours_chart, use_container_width=True)
                    st.caption("Anaerobic (Z5) is tracked but not plotted in this view.")
            else:
                st.caption("No heart-rate zone time data to plot.")

        table_source = range_filtered_metrics.copy()
        if not table_source.empty and not filtered_daily.empty:
            table_source["day_utc"] = (
                pd.to_datetime(table_source["start_time_utc"], utc=True, errors="coerce")
                .dt.tz_localize(None)
                .dt.date.astype(str)
            )
            daily_fit = (
                filtered_daily[["day_utc", "fitness", "fatigue"]]
                .dropna(subset=["day_utc"])
                .drop_duplicates(subset=["day_utc"], keep="last")
            )
            table_source = table_source.merge(daily_fit, on="day_utc", how="left")
        table_df = display_table(table_source)
        if section_choice == "Activities":
            st.subheader("Activities")
            table_df = table_df.copy()
            table_df["if_proxy_pct"] = pd.to_numeric(table_df.get("if_proxy"), errors="coerce").fillna(0.0) * 100.0
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

if view == "Calendar":
    st.divider()
    st.header("Calendar")
    st.caption("Week grid with activity cards and weekly summary.")

    if metrics_df.empty:
        st.info("No activities available.")
    else:
        if previous_view != "Calendar":
            st.session_state.pop("calendar_split_activity_id", None)
            st.session_state["calendar_split_open"] = False
        cal_base = metrics_df.copy()
        cal_base["start_local"] = pd.to_datetime(cal_base["start_time_utc"], utc=True, errors="coerce").dt.tz_localize(None)
        cal_base = cal_base.dropna(subset=["start_local"]).copy()

        if cal_base.empty:
            st.info("No valid activity timestamps available.")
        else:
            compact_mode_early = bool(st.session_state.get("calendar_compact_week_mode", True))
            controls = st.columns([1.2, 1.0])
            with controls[0]:
                cal_min_day = cal_base["start_local"].min().date()
                cal_max_day = cal_base["start_local"].max().date()
                if compact_mode_early:
                    latest_week_start = pd.Timestamp(cal_max_day) - pd.Timedelta(
                        days=int(pd.Timestamp(cal_max_day).weekday())
                    )
                    selected_preview = pd.to_datetime(
                        st.session_state.get("calendar_compact_week_start"), errors="coerce"
                    )
                    if pd.isna(selected_preview):
                        selected_preview = latest_week_start
                    selected_preview = selected_preview - pd.Timedelta(days=int(selected_preview.weekday()))
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

                    compare_choice = st.selectbox(
                        "Compare against",
                        compare_options,
                        key="calendar_compact_compare_choice",
                    )
                    range_start_day = cal_min_day
                    range_end_day = cal_max_day
                else:
                    cal_range = st.selectbox(
                        "Quick range",
                        ["3M", "6M", "9M", "1Y", "2Y", "ALL"],
                        index=3,
                        key="calendar_quick_range",
                    )
                    if cal_range == "3M":
                        range_start_day = max(cal_min_day, cal_max_day - timedelta(days=90))
                    elif cal_range == "6M":
                        range_start_day = max(cal_min_day, cal_max_day - timedelta(days=180))
                    elif cal_range == "9M":
                        range_start_day = max(cal_min_day, cal_max_day - timedelta(days=270))
                    elif cal_range == "1Y":
                        range_start_day = max(cal_min_day, cal_max_day - timedelta(days=365))
                    elif cal_range == "2Y":
                        range_start_day = max(cal_min_day, cal_max_day - timedelta(days=730))
                    else:
                        range_start_day = cal_min_day
                    range_end_day = cal_max_day
            with controls[1]:
                cal_activity_filter = st.selectbox(
                    "Activity filter",
                    ["All Activities", "All Running", "Running", "Treadmill", "Cycling", "Elliptical"],
                    index=0,
                    key="calendar_activity_filter",
                )
            range_start_ts = pd.Timestamp(range_start_day)
            range_end_ts = pd.Timestamp(range_end_day)
            grid_start = range_start_ts - pd.Timedelta(days=int(range_start_ts.weekday()))
            grid_end = range_end_ts + pd.Timedelta(days=int(6 - range_end_ts.weekday()))

            cal_metrics, cal_daily = cached_filtered_views(
                metrics_df,
                activity_filter=cal_activity_filter,
                specificity_profile=_normalize_specificity_profile(
                    st.session_state.get("user_specificity_profile", {}),
                    fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
                ),
            )
            cal_metrics = cal_metrics.copy()
            cal_metrics["start_local"] = pd.to_datetime(
                cal_metrics["start_time_utc"], utc=True, errors="coerce"
            ).dt.tz_localize(None)
            cal_metrics = cal_metrics.dropna(subset=["start_local"]).copy()
            cal_metrics["day"] = cal_metrics["start_local"].dt.floor("D")
            cal_metrics = cal_metrics[
                (cal_metrics["start_local"] >= grid_start)
                & (cal_metrics["start_local"] < (grid_end + pd.Timedelta(days=1)))
            ].copy()
            cal_metrics["duration_s"] = pd.to_numeric(cal_metrics.get("duration_s"), errors="coerce").fillna(0.0)
            cal_metrics["avg_hr"] = pd.to_numeric(cal_metrics.get("avg_hr"), errors="coerce")
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
            day_activity_stats = (
                cal_metrics.groupby("day", as_index=False)
                .agg(
                    day_calories=("calories_total", "sum"),
                    day_distance_eqv_km=("distance_proxy_km", "sum"),
                )
                .sort_values("day")
            )
            planned_cards_by_day: dict[pd.Timestamp, list[dict[str, object]]] = {}
            planned_day_lookup = pd.DataFrame(
                columns=["day", "planned_distance_eqv_km", "planned_tss", "planned_rtss", "planned_duration_s", "planned_if"]
            )
            planned_rows_for_calendar = get_planned_activities_df(
                cfg.db_path,
                start_day_utc=grid_start.date().isoformat(),
                end_day_utc=grid_end.date().isoformat(),
            )
            planned_rows_for_calendar = _apply_planned_actual_matching(
                planned_rows_for_calendar,
                metrics_df,
            )
            if not planned_rows_for_calendar.empty:
                planned_rows_for_calendar = _compute_planned_rows_metrics_df(
                    planned_rows=planned_rows_for_calendar,
                    lthr_curve_points=lthr_curve_points,
                    lthr_default_bpm=float(derived_lthr_bpm),
                    lt_pace_curve_points=lt_pace_curve_points,
                    lt_pace_default_sec=float(derived_threshold_pace_sec),
                    specificity_profile=_normalize_specificity_profile(
                        st.session_state.get("user_specificity_profile", {}),
                        fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
                    ),
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
                .cal-day-muted { opacity: 0.45; }
                .cal-card {
                    background: rgba(15,23,42,0.78);
                    border: 1px solid rgba(148,163,184,0.26);
                    border-radius: 10px;
                    padding: 8px 10px;
                    margin-bottom: 8px;
                }
                div[data-testid="stButton"] > button[kind="tertiary"] {
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
                }
                div[data-testid="stButton"] > button[kind="tertiary"] p,
                div[data-testid="stButton"] > button[kind="tertiary"] span,
                div[data-testid="stButton"] > button[kind="tertiary"] div {
                    font-size: 0.8rem !important;
                    line-height: 1.12 !important;
                    font-weight: 400 !important;
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
                    border: 1px solid rgba(52, 211, 153, 0.20);
                    border-radius: 16px;
                    padding: 12px 14px 8px;
                    background: radial-gradient(circle at 50% 0%, rgba(16, 185, 129, 0.10), rgba(2, 6, 23, 0.0) 60%);
                    margin-bottom: 10px;
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
                    .compact-week-shell {
                        padding: 8px 10px 6px;
                        border-radius: 12px;
                    }
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            compact_mode = st.toggle(
                "Compact week view",
                value=True,
                key="calendar_compact_week_mode",
                help="Show one-week compact summary with metric-switch bars.",
            )

            if compact_mode:
                latest_day = pd.to_datetime(cal_metrics["day"], errors="coerce").max()
                if pd.isna(latest_day):
                    st.info("No activities available for compact view.")
                    st.stop()
                latest_week_start = latest_day - pd.Timedelta(days=int(latest_day.weekday()))
                if "calendar_compact_week_start" not in st.session_state:
                    st.session_state["calendar_compact_week_start"] = latest_week_start
                selected_week_start = pd.to_datetime(
                    st.session_state.get("calendar_compact_week_start"), errors="coerce"
                )
                if pd.isna(selected_week_start):
                    selected_week_start = latest_week_start
                selected_week_start = selected_week_start - pd.Timedelta(days=int(selected_week_start.weekday()))
                st.session_state["calendar_compact_week_start"] = selected_week_start
                selected_week_end = selected_week_start + pd.Timedelta(days=6)
                compare_choice = str(st.session_state.get("calendar_compact_compare_choice", "Planned"))
                if selected_week_start > latest_week_start and compare_choice == "Planned":
                    compare_choice = "Previous week"
                    st.session_state["calendar_compact_compare_choice"] = compare_choice
                compare_weeks = {
                    "Previous week": 1,
                    "2 weeks ago": 2,
                    "3 weeks ago": 3,
                    "4 weeks ago": 4,
                    "Planned": 1,
                }.get(compare_choice, 1)
                compare_week_start = selected_week_start - pd.Timedelta(days=7 * compare_weeks)
                compare_week_end = compare_week_start + pd.Timedelta(days=6)

                st.markdown(f"### {selected_week_start:%B %-d} - {selected_week_end:%-d}")
                if compare_choice == "Planned":
                    st.caption(f"Comparing: Planned {selected_week_start:%b %-d} - {selected_week_end:%-d}")
                else:
                    st.caption(f"Comparing: {compare_week_start:%b %-d} - {compare_week_end:%-d}")
                nav1, nav2 = st.columns(2)
                with nav1:
                    if st.button("◀ Prev week", key="compact_prev_week", use_container_width=True):
                        st.session_state["calendar_compact_week_start"] = selected_week_start - pd.Timedelta(days=7)
                        st.rerun()
                with nav2:
                    if st.button("Next week ▶", key="compact_next_week", use_container_width=True):
                        st.session_state["calendar_compact_week_start"] = selected_week_start + pd.Timedelta(days=7)
                        st.rerun()

                compact_days = pd.DataFrame({"day": pd.date_range(selected_week_start, selected_week_end, freq="D")})
                compact_agg = (
                    cal_metrics[
                        (cal_metrics["day"] >= selected_week_start)
                        & (cal_metrics["day"] <= selected_week_end)
                    ]
                    .groupby("day", as_index=False)
                    .agg(
                        rtss=("rtss", "sum"),
                        tss=("tss", "sum"),
                        distance_eqv_km=("distance_proxy_km", "sum"),
                        duration_s=("duration_s", "sum"),
                        if_duration_weighted=("if_proxy", lambda s: float((pd.to_numeric(s, errors="coerce").fillna(0.0)).sum())),
                    )
                )
                compact_week = compact_days.merge(compact_agg, on="day", how="left")
                for col in ["rtss", "tss", "distance_eqv_km", "duration_s", "if_duration_weighted"]:
                    compact_week[col] = pd.to_numeric(compact_week[col], errors="coerce").fillna(0.0)

                if_by_day = []
                for day_ts in compact_week["day"]:
                    day_df = cal_metrics[cal_metrics["day"] == day_ts]
                    dur = pd.to_numeric(day_df.get("duration_s"), errors="coerce").fillna(0.0)
                    ifv = pd.to_numeric(day_df.get("if_proxy"), errors="coerce").fillna(0.0)
                    if_total = float((dur * ifv).sum())
                    dur_total = float(dur.sum())
                    if_by_day.append(if_total / dur_total if dur_total > 0 else 0.0)
                compact_week["if_proxy"] = if_by_day
                compare_days = pd.DataFrame({"day": pd.date_range(compare_week_start, compare_week_end, freq="D")})
                if compare_choice == "Planned":
                    planned_rows = get_planned_activities_df(
                        cfg.db_path,
                        start_day_utc=selected_week_start.date().isoformat(),
                        end_day_utc=selected_week_end.date().isoformat(),
                    )
                    planned_rows = _apply_planned_actual_matching(planned_rows, metrics_df)
                    planner_specificity_profile = _normalize_specificity_profile(
                        st.session_state.get("user_specificity_profile", {}),
                        fallback_default=float(st.session_state.get("user_non_running_factor", 0.8)),
                    )
                    planned_day_stats: list[dict[str, float | pd.Timestamp]] = []
                    for day_ts in pd.date_range(selected_week_start, selected_week_end, freq="D"):
                        day_key = day_ts.date().isoformat()
                        day_rows = (
                            planned_rows[planned_rows["day_utc"] == day_key]
                            if not planned_rows.empty and "day_utc" in planned_rows.columns
                            else pd.DataFrame()
                        )
                        lthr_for_day = float(
                            _curve_value_at(
                                lthr_curve_points,
                                float(derived_lthr_bpm),
                                day_ts,
                            )
                        )
                        lt_pace_for_day = float(
                            _curve_value_at(
                                lt_pace_curve_points,
                                float(derived_threshold_pace_sec),
                                day_ts,
                            )
                        )
                        total_tss = 0.0
                        total_rtss = 0.0
                        total_dist_eqv = 0.0
                        if_weighted_sum = 0.0
                        if_weight_seconds = 0.0
                        if not day_rows.empty:
                            for _, prow in day_rows.iterrows():
                                raw_segments = prow.get("parsed_json")
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
                                for seg in segments:
                                    seg_spec = _specificity_factor_for_plan_kind(
                                        str(seg.get("kind")),
                                        planner_specificity_profile,
                                    )
                                    m = _planned_segment_metrics(
                                        seg,
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
                        planned_day_stats.append(
                            {
                                "day": day_ts,
                                "rtss": total_rtss,
                                "tss": total_tss,
                                "distance_eqv_km": total_dist_eqv,
                                "if_proxy": (if_weighted_sum / if_weight_seconds if if_weight_seconds > 0 else 0.0),
                            }
                        )
                    compare_week = pd.DataFrame(planned_day_stats)
                else:
                    compare_agg = (
                        cal_metrics[
                            (cal_metrics["day"] >= compare_week_start)
                            & (cal_metrics["day"] <= compare_week_end)
                        ]
                        .groupby("day", as_index=False)
                        .agg(
                            rtss=("rtss", "sum"),
                            tss=("tss", "sum"),
                            distance_eqv_km=("distance_proxy_km", "sum"),
                        )
                    )
                    compare_week = compare_days.merge(compare_agg, on="day", how="left")
                    for col in ["rtss", "tss", "distance_eqv_km"]:
                        compare_week[col] = pd.to_numeric(compare_week[col], errors="coerce").fillna(0.0)
                    compare_if_by_day = []
                    for day_ts in compare_week["day"]:
                        day_df = cal_metrics[cal_metrics["day"] == day_ts]
                        dur = pd.to_numeric(day_df.get("duration_s"), errors="coerce").fillna(0.0)
                        ifv = pd.to_numeric(day_df.get("if_proxy"), errors="coerce").fillna(0.0)
                        if_total = float((dur * ifv).sum())
                        dur_total = float(dur.sum())
                        compare_if_by_day.append(if_total / dur_total if dur_total > 0 else 0.0)
                    compare_week["if_proxy"] = compare_if_by_day
                week_scope_df = cal_metrics[
                    (cal_metrics["day"] >= selected_week_start)
                    & (cal_metrics["day"] <= selected_week_end)
                ].copy()
                week_scope_df["duration_s"] = pd.to_numeric(
                    week_scope_df.get("duration_s"), errors="coerce"
                )
                week_scope_df["if_proxy"] = pd.to_numeric(
                    week_scope_df.get("if_proxy"), errors="coerce"
                )
                valid_if_mask = (
                    week_scope_df["duration_s"].notna()
                    & week_scope_df["if_proxy"].notna()
                    & (week_scope_df["duration_s"] > 0)
                )
                if valid_if_mask.any():
                    week_if_weighted = float(
                        (
                            week_scope_df.loc[valid_if_mask, "if_proxy"]
                            * week_scope_df.loc[valid_if_mask, "duration_s"]
                        ).sum()
                        / week_scope_df.loc[valid_if_mask, "duration_s"].sum()
                    )
                else:
                    week_if_weighted = 0.0

                compact_week["day_label"] = compact_week["day"].dt.strftime("%a").str.upper()
                compact_week["day_num"] = compact_week["day"].dt.day

                metric_defs = [
                    ("rtss", "rTSS", ".0f", "", "sum"),
                    ("tss", "TSS", ".0f", "", "sum"),
                    ("distance_eqv_km", "Distance Eqv", ".0f", " km", "sum"),
                    ("if_proxy", "IF", ".0f", "%", "mean"),
                ]
                if "calendar_compact_metric" not in st.session_state:
                    st.session_state["calendar_compact_metric"] = "distance_eqv_km"
                selected_metric = str(st.session_state.get("calendar_compact_metric") or "distance_eqv_km")
                if selected_metric not in {k for k, _, _, _, _ in metric_defs}:
                    selected_metric = "distance_eqv_km"
                    st.session_state["calendar_compact_metric"] = selected_metric

                chart_df = compact_week.copy()
                chart_df["metric_value"] = pd.to_numeric(chart_df[selected_metric], errors="coerce").fillna(0.0)
                chart_df["day_display"] = (
                    chart_df["day"].dt.strftime("%d %b")
                    + "\n("
                    + chart_df["day"].dt.strftime("%a")
                    + ")"
                )
                chart_df["series"] = "Current"
                chart_df["opacity"] = 0.95
                compare_chart_df = compare_week.copy()
                compare_chart_df["metric_value"] = pd.to_numeric(
                    compare_chart_df[selected_metric], errors="coerce"
                ).fillna(0.0)
                compare_chart_df["day_display"] = (
                    compact_week["day"].dt.strftime("%d %b")
                    + "\n("
                    + compact_week["day"].dt.strftime("%a")
                    + ")"
                )
                compare_chart_df["series"] = "Compare"
                compare_chart_df["opacity"] = 0.35
                y_title = next(label for key, label, _, _, _ in metric_defs if key == selected_metric)
                if selected_metric == "distance_eqv_km":
                    chart_df["metric_label"] = chart_df["metric_value"].map(
                        lambda v: f"{v:.0f} km" if float(v) > 0 else ""
                    )
                elif selected_metric == "if_proxy":
                    chart_df["metric_label"] = chart_df["metric_value"].map(
                        lambda v: f"{(float(v) * 100.0):.0f}%" if float(v) > 0 else ""
                    )
                else:
                    chart_df["metric_label"] = chart_df["metric_value"].map(
                        lambda v: f"{v:.0f}" if float(v) > 0 else ""
                    )

                def _compact_bar_color(metric_key: str, value: float) -> str:
                    if metric_key in {"tss", "rtss"}:
                        if value < 50:
                            return "#34d399"
                        if value <= 100:
                            return "#facc15"
                        return "#60a5fa"
                    if metric_key == "if_proxy":
                        if value < 0.5:
                            return "#34d399"
                        if value <= 0.7:
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
                bar_df = pd.concat([compare_chart_df, chart_df], ignore_index=True)
                bars = (
                    alt.Chart(bar_df)
                    .mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10, size=24, opacity=0.95)
                    .encode(
                        x=alt.X(
                            "day_display:N",
                            sort=chart_df["day_display"].tolist(),
                            title=None,
                            axis=alt.Axis(
                                labelAngle=0,
                                labelLineHeight=14,
                            ),
                        ),
                        xOffset=alt.XOffset(
                            "series:N",
                            sort=["Compare", "Current"],
                        ),
                        y=alt.Y("metric_value:Q", title=None, scale=alt.Scale(zero=True)),
                        color=alt.Color("bar_color:N", scale=None, legend=None),
                        opacity=alt.Opacity("opacity:Q", legend=None),
                        tooltip=[
                            alt.Tooltip("day:T", title="Day"),
                            alt.Tooltip("series:N", title="Series"),
                            alt.Tooltip(
                                "metric_value:Q",
                                title=y_title,
                                format=(".0%" if selected_metric == "if_proxy" else ".0f"),
                            ),
                        ],
                    )
                )
                labels = (
                    alt.Chart(chart_df.assign(series="Current"))
                    .mark_text(dy=-10, color="#e2e8f0", fontSize=12, fontWeight=700)
                    .encode(
                        x=alt.X("day_display:N", sort=chart_df["day_display"].tolist()),
                        xOffset=alt.XOffset(
                            "series:N",
                            sort=["Compare", "Current"],
                        ),
                        y=alt.Y("metric_value:Q"),
                        text=alt.Text("metric_label:N"),
                    )
                )
                compact_chart = alt.layer(bars, labels).properties(
                    height=250,
                    padding={"left": 52, "right": 10, "top": 8, "bottom": 42},
                )
                st.markdown("<div class='compact-week-shell'>", unsafe_allow_html=True)
                st.altair_chart(compact_chart, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

                metric_values = []
                for metric_key, metric_label, metric_fmt, metric_unit, agg_mode in metric_defs:
                    metric_series = pd.to_numeric(compact_week[metric_key], errors="coerce").fillna(0.0)
                    if metric_key == "if_proxy":
                        value = week_if_weighted
                    else:
                        value = float(metric_series.mean() if agg_mode == "mean" else metric_series.sum())
                    metric_values.append((metric_key, metric_label, metric_fmt, metric_unit, value))

                row1 = st.columns(2)
                row2 = st.columns(2)
                button_rows = [row1, row2]
                for i, (metric_key, metric_label, metric_fmt, metric_unit, value) in enumerate(metric_values):
                    row = button_rows[i // 2]
                    with row[i % 2]:
                        if metric_key == "if_proxy":
                            button_label = f"{metric_label} {(float(value) * 100.0):.0f}%"
                        else:
                            button_label = f"{metric_label} {value:{metric_fmt}}{metric_unit}"
                        button_type = "primary" if metric_key == selected_metric else "secondary"
                        if st.button(
                            button_label,
                            key=f"compact_metric_select_{metric_key}",
                            use_container_width=True,
                            type=button_type,
                        ):
                            if metric_key != selected_metric:
                                st.session_state["calendar_compact_metric"] = metric_key
                                st.rerun()
                st.stop()

            header_cols = st.columns([1.2, 1, 1, 1, 1, 1, 1, 1])
            with header_cols[0]:
                st.markdown("**Week**")
            for i, day_name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
                with header_cols[i + 1]:
                    st.markdown(f"**{day_name}**")

            week_starts = pd.date_range(start=grid_start, end=grid_end, freq="7D")
            week_starts = week_starts.sort_values(ascending=False)
            for ws in week_starts:
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
                zone_totals = {
                    "Z1": float(pd.to_numeric(week_df.get("hr_time_in_zone_1"), errors="coerce").fillna(0.0).sum()),
                    "Z2": float(pd.to_numeric(week_df.get("hr_time_in_zone_2"), errors="coerce").fillna(0.0).sum()),
                    "Z3": float(pd.to_numeric(week_df.get("hr_time_in_zone_3"), errors="coerce").fillna(0.0).sum()),
                    "Z4": float(pd.to_numeric(week_df.get("hr_time_in_zone_4"), errors="coerce").fillna(0.0).sum()),
                    "Z5": float(pd.to_numeric(week_df.get("hr_time_in_zone_5"), errors="coerce").fillna(0.0).sum()),
                }
                zone_total_s = sum(zone_totals.values())
                zone_colors = {
                    "Z1": "#3b82f6",
                    "Z2": "#65a30d",
                    "Z3": "#facc15",
                    "Z4": "#fb923c",
                    "Z5": "#e11d48",
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
                            f"<div class='cal-day-header'>{day_ts:%d %b}</div>",
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
                            day_meta_parts.append(f"{day_distance_eqv:.0f} km eqv.")
                        elif show_planned_meta and planned_distance_eqv > 0:
                            day_meta_parts.append(f"Plan {planned_distance_eqv:.0f} km eqv.")
                        else:
                            day_meta_parts.append("0 km eqv.")
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
                            day_meta_parts.append(f"Plan {_duration_short(planned_duration_s)}")
                        if show_planned_meta and planned_tss > 0:
                            day_meta_parts.append(f"Plan TSS {planned_tss:.0f}")
                        if show_planned_meta and planned_rtss > 0:
                            day_meta_parts.append(f"Plan rTSS {planned_rtss:.0f}")
                        if show_planned_meta and planned_if > 0:
                            day_meta_parts.append(f"Plan IF {(planned_if * 100.0):.0f}%")
                        st.markdown(
                            f"<div class='cal-card-meta' style='margin-bottom:6px;'>{' · '.join(day_meta_parts)}</div>",
                            unsafe_allow_html=True,
                        )
                        rendered_cards = 0
                        for _, act in day_df.iterrows():
                            activity_id = str(act.get("activity_id"))
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
                            subtitle = f"{dur_text}" + (f" · {dist_text}" if dist_text else "")
                            card_label = (
                                f"**{sport_label_raw}**\n"
                                f"{subtitle}\n"
                                f"{hr_text}\n"
                                f"{pace_text} · {if_text}\n"
                                f"TSS {tss_v:.0f} · rTSS {rtss_v:.0f}"
                            )
                            if st.button(
                                card_label,
                                key=f"calendar_split_title_{activity_id}_{day_ts.date().isoformat()}",
                                use_container_width=True,
                                type="tertiary",
                            ):
                                st.session_state["calendar_split_activity_id"] = activity_id
                                st.session_state["calendar_split_open"] = True
                            rendered_cards += 1
                        today_utc = datetime.now(timezone.utc).date()
                        day_planned_cards = planned_cards_by_day.get(day_ts, [])
                        if day_ts.date() >= today_utc and rendered_cards == 0 and day_planned_cards:
                            for prow in day_planned_cards:
                                p_activity = str(prow.get("activity") or "Planned")
                                p_duration = _duration_short(prow.get("duration_s"))
                                p_dist = float(pd.to_numeric(pd.Series([prow.get("distance_proxy_km")]), errors="coerce").fillna(0.0).iloc[0])
                                p_if = float(pd.to_numeric(pd.Series([prow.get("if_proxy")]), errors="coerce").fillna(0.0).iloc[0])
                                p_tss = float(pd.to_numeric(pd.Series([prow.get("tss")]), errors="coerce").fillna(0.0).iloc[0])
                                p_rtss = float(pd.to_numeric(pd.Series([prow.get("rtss")]), errors="coerce").fillna(0.0).iloc[0])
                                st.markdown(
                                    (
                                        "<div class='cal-planned-card'>"
                                        f"<div class='cal-planned-title'>Planned · {p_activity}</div>"
                                        f"<div class='cal-planned-meta'>{p_duration} · {p_dist:.0f} km eqv.</div>"
                                        f"<div class='cal-planned-meta'>IF {(p_if * 100.0):.0f}%</div>"
                                        f"<div class='cal-planned-meta'>TSS {p_tss:.0f} · rTSS {p_rtss:.0f}</div>"
                                        "</div>"
                                    ),
                                    unsafe_allow_html=True,
                                )
                        if rendered_cards == 0 and day_ts.date() < today_utc:
                            st.markdown(
                                (
                                    "<div class='cal-rest-card'>"
                                    "<div class='cal-rest-title'>Rest Day</div>"
                                    "<div class='cal-rest-sub'>Rest is part of training!</div>"
                                    "</div>"
                                ),
                                unsafe_allow_html=True,
                            )

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
                        plot_df["pace_eqv_s_per_km"] = pd.to_numeric(
                            plot_df.get("pace_eqv_s_per_km"), errors="coerce"
                        )
                        plot_df["speed_eqv_kmh"] = pd.NA
                        valid_pace = plot_df["pace_eqv_s_per_km"] > 0
                        plot_df.loc[valid_pace, "speed_eqv_kmh"] = 3600.0 / plot_df.loc[valid_pace, "pace_eqv_s_per_km"]
                        plot_df["speed_eqv_kmh"] = pd.to_numeric(
                            plot_df["speed_eqv_kmh"], errors="coerce"
                        ).fillna(0.0)
                        plot_df["intensity_factor"] = pd.to_numeric(
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
                                    title="Equivalent Distance Progression (km)",
                                ),
                                x2="x_end:Q",
                                y=alt.Y(
                                    "speed_eqv_kmh:Q",
                                    title="Equivalent Speed (km/h)",
                                    scale=alt.Scale(zero=True),
                                ),
                                y2=alt.Y2("y_zero:Q"),
                                color=alt.Color(
                                    "intensity_factor:Q",
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
                                    alt.Tooltip("duration_s:Q", title="Duration (s)", format=".0f"),
                                    alt.Tooltip("distance_km:Q", title="Distance (km)", format=".0f"),
                                    alt.Tooltip("distance_eqv_km:Q", title="Dist Eqv (km)", format=".0f"),
                                    alt.Tooltip("speed_eqv_kmh:Q", title="Speed Eqv (km/h)", format=".2f"),
                                    alt.Tooltip("avg_hr:Q", title="Avg HR", format=".0f"),
                                    alt.Tooltip("intensity_factor:Q", title="IF", format=".0%"),
                                    alt.Tooltip("pace_s_per_km:Q", title="Pace s/km", format=".1f"),
                                    alt.Tooltip("pace_eqv_s_per_km:Q", title="Pace Eqv s/km", format=".1f"),
                                    alt.Tooltip("tss:Q", title="TSS", format=".0f"),
                                    alt.Tooltip("rtss:Q", title="rTSS", format=".0f"),
                                ],
                            )
                            .properties(height=280)
                        )
                        st.altair_chart(chart, use_container_width=True)
                        table_df = plot_df.copy()
                        table_df["duration"] = table_df["duration_s"].apply(_duration_short)
                        table_df["pace"] = table_df["pace_s_per_km"].apply(_pace_compact)
                        table_df["pace_eqv"] = table_df["pace_eqv_s_per_km"].apply(_pace_compact)
                        table_df["intensity_factor_pct"] = (
                            pd.to_numeric(table_df.get("intensity_factor"), errors="coerce").fillna(0.0) * 100.0
                        )
                        st.dataframe(
                            table_df[
                                [
                                    "split_idx",
                                    "duration",
                                    "distance_km",
                                    "distance_eqv_km",
                                    "avg_hr",
                                    "intensity_factor_pct",
                                    "pace",
                                    "pace_eqv",
                                    "tss",
                                    "rtss",
                                ]
                            ],
                            use_container_width=True,
                            column_config={
                                "split_idx": st.column_config.NumberColumn("Split", format="%d"),
                                "distance_km": st.column_config.NumberColumn("Distance (km)", format="%.0f"),
                                "distance_eqv_km": st.column_config.NumberColumn("Dist Eqv (km)", format="%.0f"),
                                "avg_hr": st.column_config.NumberColumn("Avg HR", format="%.0f"),
                                "intensity_factor_pct": st.column_config.NumberColumn("IF", format="%.0f%%"),
                                "tss": st.column_config.NumberColumn("TSS", format="%.0f"),
                                "rtss": st.column_config.NumberColumn("rTSS", format="%.0f"),
                            },
                        )
                    if st.button("Close", key="calendar_split_modal_close"):
                        st.session_state.pop("calendar_split_activity_id", None)
                        st.session_state["calendar_split_open"] = False
                        st.rerun()
                _show_split_details_dialog()

if view == "Week Planner":
    st.divider()
    st.header("Week Planner")
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
    st.caption("Plan one dated activity at a time with `[date]:[activity]`.")
    st.caption("Planner supports multiple planned activities per day.")
    st.markdown(
        "Date supports `3Mar26`, `2026-03-26`, or `26/03/2026`.\n\n"
        "You can ingest multiple activities in one save using separators: new line, `;`, or `,`.\n\n"
        "Examples:\n"
        f"- `{ex1:%-d%b%y}: 15km run @{easy_run_pace}`\n"
        f"- `{ex2:%Y-%m-%d}: 80min elliptical @{easy_xtrain_hr}bpm`\n"
        f"- `{ex3:%Y-%m-%d}: 10min cycling @{xtrain_block1_hr}bpm + 4x10min @{xtrain_block2_hr}bpm`\n"
        f"- `{ex4:%d/%m/%Y}: 10min treadmill @{treadmill_easy_pace} + 5x6min @{treadmill_hard_pace}`"
    )

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

    if save_clicked:
        entries = _split_dated_activity_entries(plan_entry)
        if not entries:
            st.error("Input is empty. Use `[date]:[activity]`.")
        else:
            existing = get_planned_activities_df(cfg.db_path)
            max_line_by_day = (
                existing.groupby("day_utc")["line_no"].max().to_dict() if not existing.empty else {}
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
                segs, warns = _expand_planned_segments(normalized)
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
                        "workout_text": normalized,
                        "parsed_json": segs,
                    }
                )
            if rows_to_upsert:
                upsert_planned_activities_rows(cfg.db_path, rows_to_upsert)
            if errors:
                st.warning("Some entries were skipped:\n- " + "\n- ".join(errors[:10]))
            if rows_to_upsert:
                st.success(f"Saved {len(rows_to_upsert)} planned activit{'y' if len(rows_to_upsert)==1 else 'ies'}.")
                st.rerun()

    st.markdown("#### View planned activities")
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
        plan_tss_vals: list[float] = []
        plan_rtss_vals: list[float] = []
        plan_dist_eqv_vals: list[float] = []
        plan_if_vals: list[float] = []
        plan_duration_s_vals: list[float] = []
        plan_activity_vals: list[str] = []
        for _, plan_row in planned_raw.iterrows():
            raw_segments = plan_row.get("parsed_json")
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

            day_for_curve = pd.to_datetime(plan_row.get("day_utc"), utc=True, errors="coerce")
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
                seg_spec = _specificity_factor_for_plan_kind(seg_kind, planner_specificity_profile)
                m = _planned_segment_metrics(
                    seg,
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
            plan_tss_vals.append(total_tss)
            plan_rtss_vals.append(total_rtss)
            plan_dist_eqv_vals.append(total_dist_eqv)
            plan_if_vals.append(if_weighted_sum / if_weight_seconds if if_weight_seconds > 0 else 0.0)
            plan_duration_s_vals.append(if_weight_seconds)
            plan_activity_vals.append(", ".join([k.replace("_", " ").title() for k in kinds_seen]) if kinds_seen else "-")

        planned_raw["activity"] = plan_activity_vals
        planned_raw["tss"] = plan_tss_vals
        planned_raw["rtss"] = plan_rtss_vals
        planned_raw["distance_eqv_km"] = plan_dist_eqv_vals
        planned_raw["if_proxy"] = plan_if_vals
        planned_raw["duration_s"] = plan_duration_s_vals

        st.markdown("##### Planned weekly outlook (next 4 weeks)")
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
                    selected_week_key = str(weekly_grouped.loc[checked_idx[0], "week_start"].strftime("%Y-%m-%d"))
                    st.session_state["planner_outlook_week_key"] = selected_week_key
                    selected_planned_week_start = pd.to_datetime(selected_week_key, errors="coerce")
                else:
                    selected_planned_week_start = None
            else:
                st.caption("No planned activities in the next 4 weeks.")
        else:
            st.caption("No valid planned dates to build a weekly outlook.")
        if selected_planned_week_start is not None and pd.notna(selected_planned_week_start):
            selected_planned_week_end = selected_planned_week_start + pd.Timedelta(days=6)
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

        editor_df = planned_rows_for_editor[
            [
                "select",
                "row_id",
                "day_utc",
                "line_no",
                "activity",
                "workout_text",
                "duration_s",
                "tss",
                "rtss",
                "distance_eqv_km",
                "if_proxy",
                "parsed_json",
                "updated_at",
            ]
        ].copy()
        editor_df["day_of_week"] = pd.to_datetime(editor_df["day_utc"], errors="coerce").dt.strftime("%a")
        editor_df["if_proxy_pct"] = pd.to_numeric(editor_df.get("if_proxy"), errors="coerce").fillna(0.0) * 100.0
        if "duration_s" in editor_df.columns:
            planner_duration_s = pd.to_numeric(editor_df["duration_s"], errors="coerce")
        else:
            planner_duration_s = pd.Series(0.0, index=editor_df.index)
        planner_duration_fallback = editor_df.get("parsed_json", pd.Series(index=editor_df.index)).apply(
            _sum_duration_s_from_parsed_segments
        )
        planner_duration_s = planner_duration_s.where(
            planner_duration_s.fillna(0.0) > 0, planner_duration_fallback
        )
        editor_df["duration_h"] = planner_duration_s.fillna(0.0) / 3600.0
        editor_df = editor_df.drop(columns=["duration_s"], errors="ignore")
        editor_df = editor_df.drop(columns=["if_proxy"], errors="ignore")
        edited_plan = st.data_editor(
            editor_df,
            use_container_width=True,
            hide_index=True,
            column_order=[
                "select",
                "row_id",
                "day_utc",
                "day_of_week",
                "line_no",
                "activity",
                "workout_text",
                "tss",
                "rtss",
                "distance_eqv_km",
                "duration_h",
                "if_proxy_pct",
                "parsed_json",
                "updated_at",
            ],
            column_config={
                "select": st.column_config.CheckboxColumn("Select"),
                "row_id": st.column_config.TextColumn("Row ID", disabled=True),
                "day_utc": st.column_config.TextColumn("Planned Date"),
                "day_of_week": st.column_config.TextColumn("DOW", disabled=True),
                "line_no": st.column_config.NumberColumn("Line", format="%d", disabled=True),
                "activity": st.column_config.TextColumn("Activity", disabled=True),
                "workout_text": st.column_config.TextColumn("Activity String"),
                "duration_h": st.column_config.NumberColumn("Duration (h)", format="%.1f", disabled=True),
                "tss": st.column_config.NumberColumn("TSS", format="%.0f", disabled=True),
                "rtss": st.column_config.NumberColumn("rTSS", format="%.0f", disabled=True),
                "distance_eqv_km": st.column_config.NumberColumn("Dist Eqv (km)", format="%.0f", disabled=True),
                "if_proxy_pct": st.column_config.NumberColumn("IF", format="%.0f%%", disabled=True),
                "parsed_json": st.column_config.TextColumn("Parsed JSON", disabled=True),
                "updated_at": st.column_config.TextColumn("Updated At", disabled=True),
            },
            key="planner_raw_editor",
        )

        selected_rows = edited_plan[edited_plan["select"] == True].copy()
        cdel, cedit = st.columns(2)
        with cdel:
            if st.button("Delete selected", key="planner_delete_selected_btn", use_container_width=True):
                if selected_rows.empty:
                    st.info("Select at least one planned activity.")
                else:
                    delete_keys = []
                    for _, r in selected_rows.iterrows():
                        rid = str(r.get("row_id") or "")
                        day_part, line_part = rid.split("::", 1)
                        delete_keys.append((day_part, int(line_part)))
                    delete_planned_activities(cfg.db_path, delete_keys)
                    st.success(f"Deleted {len(delete_keys)} planned activities.")
                    st.rerun()
        with cedit:
            if st.button("Save edits (selected rows)", key="planner_save_selected_edits_btn", use_container_width=True):
                if selected_rows.empty:
                    st.info("Select at least one row to edit.")
                else:
                    old_keys: list[tuple[str, int]] = []
                    edit_rows: list[dict[str, object]] = []
                    remaining = planned_raw.copy()
                    for _, r in selected_rows.iterrows():
                        rid = str(r.get("row_id") or "")
                        day_part, line_part = rid.split("::", 1)
                        old_keys.append((day_part, int(line_part)))
                    old_key_set = {f"{d}::{ln}" for d, ln in old_keys}
                    remaining = remaining[~remaining["row_id"].isin(old_key_set)].copy()
                    max_line_by_day = (
                        remaining.groupby("day_utc")["line_no"].max().to_dict() if not remaining.empty else {}
                    )
                    errors: list[str] = []
                    for _, r in selected_rows.iterrows():
                        day_text = str(r.get("day_utc") or "").strip()
                        workout_text = _normalize_plan_text(str(r.get("workout_text") or ""))
                        try:
                            day_ts = pd.Timestamp(day_text)
                        except Exception:
                            errors.append(f"Invalid date `{day_text}`")
                            continue
                        if day_ts < previous_sunday:
                            errors.append(f"Date `{day_text}` is before allowed floor `{previous_sunday:%Y-%m-%d}`")
                            continue
                        segs, warns = _expand_planned_segments(workout_text)
                        if warns or not segs:
                            errors.append(
                                f"`{workout_text}` invalid: " + ("; ".join(warns[:2]) if warns else "unparseable")
                            )
                            continue
                        day_key = day_ts.date().isoformat()
                        next_line = int(max_line_by_day.get(day_key, 0)) + 1
                        max_line_by_day[day_key] = next_line
                        edit_rows.append(
                            {
                                "day_utc": day_key,
                                "line_no": next_line,
                                "workout_text": workout_text,
                                "parsed_json": segs,
                            }
                        )
                    if errors:
                        st.error("Cannot save edits:\n- " + "\n- ".join(errors[:8]))
                    else:
                        delete_planned_activities(cfg.db_path, old_keys)
                        upsert_planned_activities_rows(cfg.db_path, edit_rows)
                        st.success(f"Updated {len(edit_rows)} planned activities.")
                        st.rerun()

if view == "Custom Activities":
    st.divider()
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

    if custom_save_clicked:
        entries = _split_dated_activity_entries(custom_entry)
        if not entries:
            st.error("Input is empty. Use `[date]:[activity]`.")
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
                segs, warns = _expand_planned_segments(normalized)
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
    if custom_raw.empty:
        st.caption("No custom activities saved yet.")
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
                m = _planned_segment_metrics(
                    seg,
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

        st.markdown("##### Custom weekly outlook")
        custom_weekly_outlook = custom_raw.copy()
        selected_custom_week_start: pd.Timestamp | None = None
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
            else:
                st.caption("No custom activities found.")
        else:
            st.caption("No valid custom dates to build a weekly outlook.")

        custom_plot_metric = st.selectbox(
            "Custom metric view",
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
            st.caption("Select a week in `Display` above to show the custom metric chart.")

        custom_editor_df = custom_raw[
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
                        segs, warns = _expand_planned_segments(activity_text)
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
    st.divider()
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
    st.divider()
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
                    rec_sel = alt.selection_point(fields=["series"], bind="legend")
                    recovery_chart = (
                        alt.Chart(recovery_long)
                        .mark_line(point=True)
                        .encode(
                            x="day:T",
                            y=alt.Y("value:Q", axis=alt.Axis(format=".2f")),
                            color="series:N",
                            tooltip=["day:T", "series:N", alt.Tooltip("value:Q", format=".2f")],
                            opacity=alt.condition(rec_sel, alt.value(1.0), alt.value(0.08), empty=True),
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
    st.divider()
    st.header("Data Extract & Sync")

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
    st.caption(f"Private exports: {cfg.private_export_dir}")
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

        sync_progress.progress(94, text="Sync: updating splits from raw cache...")
        _sync_log("[splits] syncing splits from raw activity cache")
        split_rows, split_errors = _sync_splits_from_raw_activity_cache(cfg.private_export_dir / "raw")
        split_changes = upsert_activity_splits(cfg.db_path, split_rows)
        messages.append(f"Splits: synced {len(split_rows)} rows ({split_changes} DB row changes).")
        _sync_log(f"[splits:done] rows={len(split_rows)} | db_changes={split_changes} | errors={len(split_errors)}")
        if split_errors:
            st.warning("Some split files failed to parse during sync. First 20 shown in logs.")
            for err in split_errors[:20]:
                _sync_log(f"[splits:error] {err}")

        success = total_rows > 0 or any("Skipped" in m for m in messages)
        log_sync(cfg.db_path, source=source.lower().replace(" ", "_"), success=success, message=" | ".join(messages))
        sync_finished_at = datetime.now(timezone.utc)
        sync_duration_s = (sync_finished_at - sync_started_at).total_seconds()
        _sync_log(f"[done] {sync_finished_at.isoformat()} | duration_s={sync_duration_s:.1f}")
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
        incremental_extract = st.checkbox("Incremental only", value=True)
    with extract_row1[2]:
        run_extract = st.button("Run comprehensive extract", use_container_width=True)
    with extract_row1[3]:
        st.write("")

    extract_row2 = st.columns([1.3, 1.0, 1.2, 1.0])
    with extract_row2[0]:
        include_details = st.checkbox("Include activity details", value=False)
    with extract_row2[1]:
        include_wellness = st.checkbox("Include sleep + wellness", value=True)
    with extract_row2[2]:
        verify_raw_integrity = st.checkbox("Verify raw integrity", value=False)
    with extract_row2[3]:
        st.write("")

    if run_extract:
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
                latest_recovery = get_latest_recovery_day(cfg.db_path) if include_wellness else None
                start_day = extract_start
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
                        start_day = max(start_day, (anchor - timedelta(days=2)).date())
                        _log(
                            f"[info] incremental_anchor={anchor.isoformat()} -> computed_start_day={start_day.isoformat()}"
                        )
                _log(
                    f"[start] {extract_started_at.isoformat()} | start_day={start_day} | "
                    f"end_day={datetime.now(timezone.utc).date()} | incremental_only={incremental_extract} | "
                    f"include_details={include_details} | "
                    f"include_wellness={include_wellness}"
                )
                if latest:
                    _log(f"[info] latest_activity_in_db={latest.isoformat()}")
                else:
                    _log("[info] latest_activity_in_db=None")
                if include_wellness:
                    if latest_recovery:
                        _log(f"[info] latest_recovery_day_in_db={latest_recovery.date().isoformat()}")
                    else:
                        _log("[info] latest_recovery_day_in_db=None")
                _log("[fetch] activity summaries + FIT records")
                if include_details:
                    _log("[fetch] activity details endpoints: details/weather/hr_timezones + splits")
                if include_wellness:
                    _log("[fetch] daily wellness endpoints: sleep/stress/hrv/rhr/readiness/respiration/steps")
                progress.progress(15, text="Fetching Garmin data...")
                progress_state = {"last_activity_pct": -1, "last_wellness_idx": -1}

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
                        if rounded > int(progress_state["last_activity_pct"]) or (processed > 0 and (processed % 10 == 0)):
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
                    extract = fetch_garmin_comprehensive(
                        email=garmin_email,
                        password=garmin_password,
                        start_day=start_day,
                        end_day=datetime.now(timezone.utc).date(),
                        include_activity_details=include_details,
                        include_splits=include_details,
                        include_wellness=include_wellness,
                        raw_export_dir=cfg.private_export_dir / "raw",
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

                snapshot_file = cfg.private_export_dir / f"garmin_extract_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
                dump_extract_to_json(snapshot_file, extract)
                _log(f"[snapshot] {snapshot_file}")
                progress.progress(80, text="Writing snapshot and finalizing...")

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
                st.info(f"Snapshot saved locally at: {snapshot_file}")
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
                progress.progress(100, text="Comprehensive extract completed.")
                with st.expander("Comprehensive Extract Logs", expanded=True):
                    _render_logs()
                sync_triggered = True
            except Exception as exc:
                _log(f"[fatal] {exc}")
                progress.progress(100, text="Comprehensive extract failed.")
                log_sync(cfg.db_path, source="garmin_comprehensive", success=False, message=str(exc))
                st.error(f"Comprehensive extract failed: {exc}")

    if sync_triggered:
        st.rerun()

st.caption(f"Now: {datetime.now(timezone.utc).isoformat()} UTC")

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
    get_runs_df,
    get_setting,
)

DEFAULT_LTHR = 178.0
DEFAULT_THRESHOLD_PACE_SEC_PER_KM = 300.0
SETTINGS_KEY_LTHR_CURVE = "lthr_curve_v1"
SETTINGS_KEY_LT_PACE_CURVE = "lt_pace_curve_v1"
TOKEN_TTL_S = int(os.getenv("TEMPERANCE_SESSION_TTL_S", str(4 * 60 * 60)) or (4 * 60 * 60))


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

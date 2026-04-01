from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - optional in pure-helper test environments
    pd = None

from pydantic import BaseModel

JSONRPC_VERSION = "2.0"
DEFAULT_OWNER = "admin"
SERVER_PROTOCOL_VERSION = "2025-03-26"


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class RecommendationContext:
    readiness: float
    sleep_score: float
    stress_avg: float
    week_remaining: float
    target_today: float
    remaining_days: int


class OwnerArgs(BaseModel):
    owner: str = DEFAULT_OWNER


class TodayStatusArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    sport: Optional[str] = None


class RecentActivitiesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    limit: int = 5
    sport: Optional[str] = None
    days: int = 30


class PlannedActivitiesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    days_ahead: int = 7


class WeekOutlookArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    days: int = 120
    metric: str = "tss"
    compare: str = "planned"
    week_start: Optional[str] = None


class RecommendTrainingArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    activity_type: str = "running"
    day: Optional[str] = None


class ActivityDetailArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    activity_id: str
    include_records: bool = True
    records_limit: int = 300


class ExplainRecommendationArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    activity_type: str = "running"
    day: Optional[str] = None


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if pd is not None and isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _analytics_helpers() -> dict[str, Any]:
    from backend.app.main import (
        SETTINGS_KEY_USER_TIMEZONE,
        _build_week_outlook_payload,
        _build_wellness_payload,
        _db_path_for_owner,
        _metrics_for_filters,
        get_planned_activities_df,
    )

    return {
        "SETTINGS_KEY_USER_TIMEZONE": SETTINGS_KEY_USER_TIMEZONE,
        "_build_week_outlook_payload": _build_week_outlook_payload,
        "_build_wellness_payload": _build_wellness_payload,
        "_db_path_for_owner": _db_path_for_owner,
        "_metrics_for_filters": _metrics_for_filters,
        "get_planned_activities_df": get_planned_activities_df,
    }


def _db_helpers() -> dict[str, Any]:
    from temperance.db import get_last_sync, get_setting

    return {
        "get_last_sync": get_last_sync,
        "get_setting": get_setting,
    }


def _activity_detail_handler() -> Callable[..., dict[str, Any]]:
    from backend.app.main import activity_detail

    return activity_detail


def _resolve_db_path(owner: str) -> Path:
    helpers = _analytics_helpers()
    resolver = helpers["_db_path_for_owner"]
    return resolver(str(owner or DEFAULT_OWNER).strip() or DEFAULT_OWNER)


def _owner_timezone(owner: str, db_path: Path) -> str:
    analytics = _analytics_helpers()
    db = _db_helpers()
    raw = db["get_setting"](db_path, analytics["SETTINGS_KEY_USER_TIMEZONE"])
    tz_name = str(raw or "").strip()
    return tz_name or "UTC"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if pd is not None:
        try:
            return bool(pd.isna(value))
        except Exception:
            return False
    return False


def _extract_numeric(value: Any) -> Optional[float]:
    if _is_missing(value):
        return None
    return float(_safe_float(value))


def _extract_bool(value: Any) -> Optional[bool]:
    if _is_missing(value):
        return None
    return bool(value)


def _clean_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if v is not None}


def _normalize_timestamp(value: Any) -> Optional[datetime]:
    if _is_missing(value):
        return None
    if pd is not None:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso_or_none(value: Any) -> Optional[str]:
    ts = _normalize_timestamp(value)
    return ts.isoformat() if ts is not None else None


def _format_duration_minutes(seconds: Optional[float]) -> float:
    return round(max(_safe_float(seconds), 0.0) / 60.0, 1)


def _distance_km(value_meters: Any) -> float:
    return round(max(_safe_float(value_meters), 0.0) / 1000.0, 2)


def _daily_tss_target_from_week_outlook(payload: dict[str, Any]) -> float:
    goal = max(_safe_float(payload.get("goal")), 0.0)
    return round(goal / 7.0, 1) if goal > 0 else 0.0


def _remaining_days_in_week(payload: dict[str, Any]) -> int:
    rows = payload.get("rows") or []
    today_day = str(payload.get("today_day") or "").strip()
    if not rows:
        return 0
    return sum(1 for row in rows if str(row.get("day") or "") >= today_day)


def _recent_metrics_df(owner: str, sport: Optional[str] = None, days: int = 45) -> tuple[Path, pd.DataFrame]:
    helpers = _analytics_helpers()
    db_path = _resolve_db_path(owner)
    metrics_df = helpers["_metrics_for_filters"](
        db_path=db_path,
        days=max(int(days), 1),
        start_day=None,
        end_day=None,
        sport=sport,
        include_invalid=False,
        include_mechanical_load=True,
    )
    if not metrics_df.empty:
        metrics_df = metrics_df.sort_values("start_time_utc", ascending=False).copy()
    return db_path, metrics_df


def _activity_row_summary(row: Any, include_extended_metrics: bool = True) -> dict[str, Any]:
    payload = {
        "activity_id": str(row.get("activity_id") or ""),
        "start_time_utc": _iso_or_none(row.get("start_time_utc")),
        "sport_type": str(row.get("sport_type") or ""),
        "duration_min": _format_duration_minutes(row.get("duration_s")),
        "distance_km": _distance_km(row.get("distance_m")),
        "tss": round(_safe_float(row.get("tss")), 1),
        "rtss": round(_safe_float(row.get("rtss")), 1),
        "if_proxy": round(_safe_float(row.get("if_proxy")), 3),
        "avg_hr": round(_safe_float(row.get("avg_hr")), 1),
    }
    if include_extended_metrics:
        payload.update(
            {
                "distance_equivalent_km": round(_safe_float(row.get("distance_proxy_km")), 2),
                "training_load_garmin": round(_safe_float(row.get("training_load_garmin")), 1),
                "mechanical_load": round(_safe_float(row.get("mechanical_load")), 2),
            }
        )
    else:
        payload["mechanical_load"] = round(_safe_float(row.get("mechanical_load")), 2)
    return _clean_mapping(payload)


def _latest_wellness_point(wellness_payload: dict[str, Any]) -> dict[str, Any]:
    points = list(wellness_payload.get("points") or [])
    return _clean_mapping(dict(points[-1])) if points else {}


def _recommendation_status(context: RecommendationContext) -> tuple[str, str]:
    if context.readiness > 0 and context.readiness <= 35:
        return "recover", "Training readiness is very low, so the safest call is recovery-first work."
    if context.sleep_score > 0 and context.sleep_score <= 65:
        return "easy", "Sleep score is suppressed, so keep the day aerobic and controlled."
    if context.stress_avg >= 60:
        return "easy", "Average stress is elevated, so avoid stacking another hard session."
    if context.week_remaining > context.target_today * 1.5 and context.target_today > 0:
        return "build", "You are behind the weekly load target and recovery signals still look usable."
    return "steady", "Load and recovery look balanced enough for a normal quality day."


def _normalize_activity_type(value: Optional[str]) -> str:
    sport = str(value or "running").strip().lower() or "running"
    aliases = {
        "run": "running",
        "treadmill": "running",
        "cycle": "bike",
        "cycling": "bike",
        "ride": "bike",
        "trainer": "bike",
        "xtrain": "elliptical",
        "x-train": "elliptical",
        "cross train": "elliptical",
        "cross-train": "elliptical",
    }
    return aliases.get(sport, sport)


def _recommendation_text(activity_type: str, status: str) -> str:
    suggestion_map = {
        "running": {
            "recover": "Run 35-45min easy in Z1/Z2. Add 4-6 relaxed strides only if the legs open up during the cooldown.",
            "easy": "Run 45-60min easy aerobic. Keep it conversational and leave threshold work for another day.",
            "steady": "Run 15min easy, then 3x8min steady/threshold with easy recoveries, then cool down well.",
            "build": "Run 20min easy, then 4x10min threshold with short recoveries, or swap to a medium-long aerobic run if volume matters more today.",
        },
        "elliptical": {
            "recover": "Elliptical 35-45min very easy at low HR. Treat it as circulation work, not training stress.",
            "easy": "Elliptical 45-60min aerobic at controlled HR with no hard surges.",
            "steady": "Elliptical 15min easy, then 3x10min strong aerobic/tempo with easy recoveries, then cool down.",
            "build": "Elliptical 20min easy, then 4x10min tempo/threshold with controlled recoveries.",
        },
        "bike": {
            "recover": "Bike 45min recovery spin with light legs only.",
            "easy": "Bike 60-90min aerobic endurance and cap the effort before it drifts upward.",
            "steady": "Bike 20min easy, then 3x12min tempo/threshold, then cool down.",
            "build": "Bike 20min easy, then 4x12min sweet spot/threshold, or extend into a longer endurance ride if time is available.",
        },
    }
    family = suggestion_map.get(activity_type, suggestion_map["running"])
    return family[status]


def _recommendation_headline(activity_type: str, status: str) -> str:
    labels = {
        "recover": "Recovery day",
        "easy": "Easy day",
        "steady": "Steady quality day",
        "build": "Build day",
    }
    return f"{labels.get(status, 'Training day')} for {activity_type}"


def _recommendation_explanation(context: RecommendationContext, status: str) -> str:
    parts = [
        f"readiness={context.readiness:.0f}" if context.readiness > 0 else "readiness=unknown",
        f"sleep={context.sleep_score:.0f}" if context.sleep_score > 0 else "sleep=unknown",
        f"stress={context.stress_avg:.0f}" if context.stress_avg > 0 else "stress=unknown",
        f"remaining_week_tss={context.week_remaining:.1f}",
        f"remaining_days={context.remaining_days}",
    ]
    if status == "build" and context.remaining_days > 0:
        parts.append(f"pace_needed≈{context.week_remaining / context.remaining_days:.1f} TSS/day")
    return "; ".join(parts)


def _recommendation_signal_rows(context: RecommendationContext, status: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "signal": "training_readiness",
            "value": round(context.readiness, 1) if context.readiness > 0 else None,
            "status_impact": "recover" if context.readiness > 0 and context.readiness <= 35 else "supports_training",
            "why": "Very low readiness forces recovery-first guidance." if context.readiness > 0 and context.readiness <= 35 else "Readiness is not the main limiter right now.",
        },
        {
            "signal": "sleep_score",
            "value": round(context.sleep_score, 1) if context.sleep_score > 0 else None,
            "status_impact": "easy" if context.sleep_score > 0 and context.sleep_score <= 65 else "supports_training",
            "why": "Suppressed sleep score keeps the day aerobic." if context.sleep_score > 0 and context.sleep_score <= 65 else "Sleep score is acceptable for normal training.",
        },
        {
            "signal": "stress_avg",
            "value": round(context.stress_avg, 1) if context.stress_avg > 0 else None,
            "status_impact": "easy" if context.stress_avg >= 60 else "supports_training",
            "why": "Elevated stress argues against stacking intensity." if context.stress_avg >= 60 else "Stress is not high enough to dominate the call.",
        },
        {
            "signal": "remaining_week_tss",
            "value": round(context.week_remaining, 1),
            "status_impact": "build" if context.week_remaining > context.target_today * 1.5 and context.target_today > 0 else "balanced",
            "why": "Weekly load is still behind target, so more work can be justified." if context.week_remaining > context.target_today * 1.5 and context.target_today > 0 else "Remaining weekly load does not strongly push for a build day.",
        },
        {
            "signal": "remaining_days",
            "value": int(context.remaining_days),
            "status_impact": status,
            "why": (
                f"That leaves about {context.week_remaining / context.remaining_days:.1f} TSS/day to distribute."
                if context.remaining_days > 0 and context.week_remaining > 0
                else "No meaningful per-day pacing signal is available."
            ),
        },
    ]
    return rows


def _recommendation_decision_trace(context: RecommendationContext, status: str, rationale: str) -> dict[str, Any]:
    return {
        "status": status,
        "rationale": rationale,
        "signals": _recommendation_signal_rows(context, status),
        "compact_explanation": _recommendation_explanation(context, status),
    }


def _build_recommendation_payload(args: RecommendTrainingArgs | ExplainRecommendationArgs) -> dict[str, Any]:
    _require_pandas()
    helpers = _analytics_helpers()
    db_path, metrics_df = _recent_metrics_df(args.owner, sport=None, days=60)
    wellness_payload = helpers["_build_wellness_payload"](db_path=db_path, days=14, aggregation="daily", owner=args.owner)
    week_outlook = helpers["_build_week_outlook_payload"](
        db_path=db_path,
        days=120,
        start_day=None,
        end_day=None,
        sport=None,
        metric="tss",
        compare="planned",
        week_start=None,
    )
    planned_payload = tool_get_planned_activities({"owner": args.owner, "days_ahead": 7})

    latest_wellness = _latest_wellness_point(wellness_payload)
    latest_activity = metrics_df.iloc[0] if not metrics_df.empty else None
    week_remaining = _safe_float(week_outlook.get("remaining_to_go"))
    target_today = _daily_tss_target_from_week_outlook(week_outlook)
    remaining_days = max(_remaining_days_in_week(week_outlook), 1)
    context = RecommendationContext(
        readiness=_safe_float(latest_wellness.get("training_readiness")),
        sleep_score=_safe_float(latest_wellness.get("sleep_score")),
        stress_avg=_safe_float(latest_wellness.get("stress_avg")),
        week_remaining=week_remaining,
        target_today=target_today,
        remaining_days=remaining_days,
    )
    status, rationale = _recommendation_status(context)
    sport = _normalize_activity_type(args.activity_type)
    suggestion = _recommendation_text(sport, status)
    per_remaining_day = round(week_remaining / remaining_days, 1) if week_remaining > 0 else 0.0
    last_session_summary = _activity_row_summary(latest_activity, include_extended_metrics=False) if latest_activity is not None else None
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "activity_type": sport,
        "status": status,
        "headline": _recommendation_headline(sport, status),
        "rationale": rationale,
        "explanation": _recommendation_explanation(context, status),
        "suggestion": suggestion,
        "target_today_tss": round(target_today, 1),
        "remaining_tss_this_week": round(week_remaining, 1),
        "remaining_days_in_week": int(remaining_days),
        "balanced_tss_per_remaining_day": float(per_remaining_day),
        "latest_wellness": latest_wellness,
        "last_session": last_session_summary,
        "upcoming_planned": (planned_payload.get("planned") or [])[:3],
        "decision_trace": _recommendation_decision_trace(context, status, rationale),
        "note": "Heuristic MVP only: useful for triage and chat workflows, not a medical or coaching guarantee.",
    }


def tool_get_today_status(arguments: dict[str, Any]) -> dict[str, Any]:
    args = TodayStatusArgs.model_validate(arguments or {})
    db = _db_helpers()
    analytics = _analytics_helpers()
    db_path, metrics_df = _recent_metrics_df(args.owner, sport=args.sport, days=45)
    wellness_payload = analytics["_build_wellness_payload"](db_path=db_path, days=14, aggregation="daily", owner=args.owner)
    week_outlook = analytics["_build_week_outlook_payload"](
        db_path=db_path,
        days=120,
        start_day=None,
        end_day=None,
        sport=args.sport,
        metric="tss",
        compare="planned",
        week_start=None,
    )

    latest_activity: Optional[dict[str, Any]] = None
    if not metrics_df.empty:
        latest_activity = _activity_row_summary(metrics_df.iloc[0], include_extended_metrics=False)

    latest_wellness = _latest_wellness_point(wellness_payload)

    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "timezone": _owner_timezone(args.owner, db_path),
        "generated_at_utc": _utc_now().isoformat(),
        "latest_activity": latest_activity,
        "latest_wellness": latest_wellness,
        "week_outlook": _clean_mapping(
            {
                "metric": str(week_outlook.get("metric") or "tss"),
                "compare": str(week_outlook.get("compare") or "planned"),
                "week_start": str(week_outlook.get("week_start") or ""),
                "week_end": str(week_outlook.get("week_end") or ""),
                "goal": round(_safe_float(week_outlook.get("goal")), 1),
                "goal_progress_pct": int(_safe_float(week_outlook.get("goal_progress_pct"))),
                "week_total_current": round(_safe_float(week_outlook.get("week_total_current")), 1),
                "week_total_compare": round(_safe_float(week_outlook.get("week_total_compare")), 1),
                "wtd_current": round(_safe_float(week_outlook.get("wtd_current")), 1),
                "wtd_compare": round(_safe_float(week_outlook.get("wtd_compare")), 1),
                "remaining_to_go": round(_safe_float(week_outlook.get("remaining_to_go")), 1),
                "projected_finish": _extract_numeric(week_outlook.get("projected_finish")),
                "estimated_fatigue_eow": _extract_numeric(week_outlook.get("estimated_fatigue_eow")),
                "daily_tss_target": _daily_tss_target_from_week_outlook(week_outlook),
                "remaining_days_in_week": _remaining_days_in_week(week_outlook),
            }
        ),
        "last_sync": db["get_last_sync"](db_path),
    }


def tool_get_recent_activities(arguments: dict[str, Any]) -> dict[str, Any]:
    args = RecentActivitiesArgs.model_validate(arguments or {})
    db_path, metrics_df = _recent_metrics_df(args.owner, sport=args.sport, days=max(args.days, args.limit))
    limit = max(1, min(int(args.limit), 50))
    items = [_activity_row_summary(row) for _, row in metrics_df.head(limit).iterrows()]
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "count": len(items),
        "activities": items,
    }


def tool_get_planned_activities(arguments: dict[str, Any]) -> dict[str, Any]:
    args = PlannedActivitiesArgs.model_validate(arguments or {})
    helpers = _analytics_helpers()
    db_path = _resolve_db_path(args.owner)
    start_day = _utc_now().date().isoformat()
    end_day = (_utc_now().date() + timedelta(days=max(int(args.days_ahead), 1) - 1)).isoformat()
    planned_df = helpers["get_planned_activities_df"](db_path=db_path, start_day_utc=start_day, end_day_utc=end_day)
    items: list[dict[str, Any]] = []
    if not planned_df.empty:
        planned_df = planned_df.sort_values(["day_utc", "line_no"], ascending=[True, True])
        for _, row in planned_df.iterrows():
            items.append(
                {
                    "day_utc": str(row.get("day_utc") or ""),
                    "line_no": int(_safe_float(row.get("line_no"))),
                    "workout_text": str(row.get("workout_text") or ""),
                    "manual_done": bool(_safe_float(row.get("manual_done")) > 0),
                }
            )
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "range": {"start_day": start_day, "end_day": end_day},
        "count": len(items),
        "planned": items,
    }


def tool_get_week_outlook(arguments: dict[str, Any]) -> dict[str, Any]:
    args = WeekOutlookArgs.model_validate(arguments or {})
    helpers = _analytics_helpers()
    db_path = _resolve_db_path(args.owner)
    payload = helpers["_build_week_outlook_payload"](
        db_path=db_path,
        days=max(int(args.days), 14),
        start_day=None,
        end_day=None,
        sport=None,
        metric=args.metric,
        compare=args.compare,
        week_start=args.week_start,
    )
    payload["owner"] = args.owner
    payload["db_path"] = str(db_path)
    payload["daily_tss_target"] = _daily_tss_target_from_week_outlook(payload)
    payload["remaining_days_in_week"] = _remaining_days_in_week(payload)
    return payload


def tool_get_load_trend(arguments: dict[str, Any]) -> dict[str, Any]:
    _require_pandas()
    args = RecentActivitiesArgs.model_validate(arguments or {})
    db_path, metrics_df = _recent_metrics_df(args.owner, sport=args.sport, days=max(args.days, 14))
    if metrics_df.empty:
        return {
            "owner": args.owner,
            "db_path": str(db_path),
            "days": int(max(args.days, 14)),
            "summary": {},
            "daily": [],
        }

    daily = metrics_df.copy()
    daily["day"] = pd.to_datetime(daily.get("start_time_utc"), utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
    daily = daily.dropna(subset=["day"]).copy()
    grouped = (
        daily.groupby("day", as_index=False)
        .agg(
            tss=("tss", "sum"),
            rtss=("rtss", "sum"),
            duration_s=("duration_s", "sum"),
            activities=("activity_id", "count"),
            distance_equivalent_km=("distance_proxy_km", "sum"),
        )
        .sort_values("day")
    )
    grouped["tss"] = pd.to_numeric(grouped["tss"], errors="coerce").fillna(0.0)
    grouped["rtss"] = pd.to_numeric(grouped["rtss"], errors="coerce").fillna(0.0)
    grouped["duration_s"] = pd.to_numeric(grouped["duration_s"], errors="coerce").fillna(0.0)
    grouped["distance_equivalent_km"] = pd.to_numeric(grouped["distance_equivalent_km"], errors="coerce").fillna(0.0)
    grouped["ctl_42_tss"] = grouped["tss"].ewm(alpha=(2.0 / 43.0), adjust=False).mean()
    grouped["atl_7_tss"] = grouped["tss"].ewm(alpha=(2.0 / 8.0), adjust=False).mean()
    grouped["tsb_proxy"] = grouped["ctl_42_tss"] - grouped["atl_7_tss"]

    daily_rows: list[dict[str, Any]] = []
    for _, row in grouped.tail(21).iterrows():
        day = pd.to_datetime(row.get("day"), errors="coerce")
        if pd.isna(day):
            continue
        daily_rows.append(
            {
                "day": day.date().isoformat(),
                "tss": round(_safe_float(row.get("tss")), 1),
                "rtss": round(_safe_float(row.get("rtss")), 1),
                "duration_min": _format_duration_minutes(row.get("duration_s")),
                "activities": int(_safe_float(row.get("activities"))),
                "distance_equivalent_km": round(_safe_float(row.get("distance_equivalent_km")), 2),
                "ctl_42_tss": round(_safe_float(row.get("ctl_42_tss")), 1),
                "atl_7_tss": round(_safe_float(row.get("atl_7_tss")), 1),
                "tsb_proxy": round(_safe_float(row.get("tsb_proxy")), 1),
            }
        )

    summary = {
        "days": int(max(args.days, 14)),
        "total_tss": round(_safe_float(grouped["tss"].sum()), 1),
        "total_rtss": round(_safe_float(grouped["rtss"].sum()), 1),
        "avg_daily_tss": round(_safe_float(grouped["tss"].mean()), 1),
        "avg_daily_rtss": round(_safe_float(grouped["rtss"].mean()), 1),
        "latest_ctl_42_tss": round(_safe_float(grouped["ctl_42_tss"].iloc[-1]), 1),
        "latest_atl_7_tss": round(_safe_float(grouped["atl_7_tss"].iloc[-1]), 1),
        "latest_tsb_proxy": round(_safe_float(grouped["tsb_proxy"].iloc[-1]), 1),
    }
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "summary": summary,
        "daily": daily_rows,
    }


def tool_get_recovery_trend(arguments: dict[str, Any]) -> dict[str, Any]:
    args = OwnerArgs.model_validate(arguments or {})
    helpers = _analytics_helpers()
    db_path = _resolve_db_path(args.owner)
    payload = helpers["_build_wellness_payload"](db_path=db_path, days=28, aggregation="daily", owner=args.owner)
    points = list(payload.get("points") or [])
    if not points:
        return {
            "owner": args.owner,
            "db_path": str(db_path),
            "summary": {},
            "daily": [],
        }

    cleaned_points = [_clean_mapping(dict(point)) for point in points[-21:]]
    latest = cleaned_points[-1]
    recent_readiness = [float(p["training_readiness"]) for p in cleaned_points if p.get("training_readiness") is not None]
    recent_sleep = [float(p["sleep_score"]) for p in cleaned_points if p.get("sleep_score") is not None]
    recent_stress = [float(p["stress_avg"]) for p in cleaned_points if p.get("stress_avg") is not None]
    summary = _clean_mapping(
        {
            "latest_day": latest.get("period_start"),
            "latest_training_readiness": latest.get("training_readiness"),
            "latest_sleep_score": latest.get("sleep_score"),
            "latest_stress_avg": latest.get("stress_avg"),
            "latest_body_battery_end": latest.get("body_battery_end"),
            "avg_training_readiness_7": round(sum(recent_readiness[-7:]) / len(recent_readiness[-7:]), 1) if recent_readiness[-7:] else None,
            "avg_sleep_score_7": round(sum(recent_sleep[-7:]) / len(recent_sleep[-7:]), 1) if recent_sleep[-7:] else None,
            "avg_stress_avg_7": round(sum(recent_stress[-7:]) / len(recent_stress[-7:]), 1) if recent_stress[-7:] else None,
        }
    )
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "summary": summary,
        "daily": cleaned_points,
    }


def tool_recommend_training(arguments: dict[str, Any]) -> dict[str, Any]:
    args = RecommendTrainingArgs.model_validate(arguments or {})
    return _build_recommendation_payload(args)


def tool_explain_recommendation(arguments: dict[str, Any]) -> dict[str, Any]:
    args = ExplainRecommendationArgs.model_validate(arguments or {})
    payload = _build_recommendation_payload(args)
    return {
        "owner": payload.get("owner"),
        "db_path": payload.get("db_path"),
        "activity_type": payload.get("activity_type"),
        "status": payload.get("status"),
        "headline": payload.get("headline"),
        "rationale": payload.get("rationale"),
        "explanation": payload.get("explanation"),
        "decision_trace": payload.get("decision_trace") or {},
        "latest_wellness": payload.get("latest_wellness"),
        "last_session": payload.get("last_session"),
        "upcoming_planned": payload.get("upcoming_planned"),
    }


def tool_get_activity_detail(arguments: dict[str, Any]) -> dict[str, Any]:
    args = ActivityDetailArgs.model_validate(arguments or {})
    handler = _activity_detail_handler()
    payload = handler(
        activity_id=args.activity_id,
        owner=args.owner,
        include_records=bool(args.include_records),
        records_limit=max(100, min(int(args.records_limit), 5000)),
        authorization=None,
    )
    if not isinstance(payload, dict):
        raise ValueError("Unexpected activity detail payload")
    return payload


TOOLS: dict[str, ToolSpec] = {
    "get_today_status": ToolSpec(
        name="get_today_status",
        description="Get latest training, recovery, and weekly-load status for an owner.",
        input_schema=TodayStatusArgs.model_json_schema(),
        handler=tool_get_today_status,
    ),
    "get_recent_activities": ToolSpec(
        name="get_recent_activities",
        description="List recent Temperance activities with key load metrics.",
        input_schema=RecentActivitiesArgs.model_json_schema(),
        handler=tool_get_recent_activities,
    ),
    "get_planned_activities": ToolSpec(
        name="get_planned_activities",
        description="List planned workouts for the next few days.",
        input_schema=PlannedActivitiesArgs.model_json_schema(),
        handler=tool_get_planned_activities,
    ),
    "get_week_outlook": ToolSpec(
        name="get_week_outlook",
        description="Return the Temperance weekly outlook payload for current or requested week.",
        input_schema=WeekOutlookArgs.model_json_schema(),
        handler=tool_get_week_outlook,
    ),
    "get_load_trend": ToolSpec(
        name="get_load_trend",
        description="Summarize recent load trend with daily TSS/rTSS and simple CTL/ATL proxies.",
        input_schema=RecentActivitiesArgs.model_json_schema(),
        handler=tool_get_load_trend,
    ),
    "get_recovery_trend": ToolSpec(
        name="get_recovery_trend",
        description="Summarize recent wellness and recovery trend from Temperance daily recovery data.",
        input_schema=OwnerArgs.model_json_schema(),
        handler=tool_get_recovery_trend,
    ),
    "recommend_training": ToolSpec(
        name="recommend_training",
        description="Provide a heuristic training recommendation from readiness, recent load, and planned work.",
        input_schema=RecommendTrainingArgs.model_json_schema(),
        handler=tool_recommend_training,
    ),
    "explain_recommendation": ToolSpec(
        name="explain_recommendation",
        description="Explain why the current heuristic recommendation was made, including the decision trace and contributing signals.",
        input_schema=ExplainRecommendationArgs.model_json_schema(),
        handler=tool_explain_recommendation,
    ),
    "get_activity_detail": ToolSpec(
        name="get_activity_detail",
        description="Return the existing Temperance activity detail payload for a specific activity id.",
        input_schema=ActivityDetailArgs.model_json_schema(),
        handler=tool_get_activity_detail,
    ),
}


SERVER_INFO = {
    "name": "temperance-mcp",
    "version": "0.1.0",
}


def _success_response(msg_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": msg_id, "result": result}


def _error_response(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": msg_id, "error": {"code": code, "message": message}}


def _handle_initialize(msg_id: Any) -> dict[str, Any]:
    return _success_response(
        msg_id,
        {
            "protocolVersion": SERVER_PROTOCOL_VERSION,
            "serverInfo": SERVER_INFO,
            "capabilities": {
                "tools": {},
            },
        },
    )


def _handle_tools_list(msg_id: Any) -> dict[str, Any]:
    tools = [
        {
            "name": spec.name,
            "description": spec.description,
            "inputSchema": spec.input_schema,
        }
        for spec in TOOLS.values()
    ]
    return _success_response(msg_id, {"tools": tools})


def _tool_result_content(payload: Any) -> list[dict[str, Any]]:
    return [{"type": "text", "text": json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2)}]


def _handle_tools_call(msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = str((params or {}).get("name") or "").strip()
    arguments = (params or {}).get("arguments") or {}
    spec = TOOLS.get(name)
    if spec is None:
        return _error_response(msg_id, -32602, f"Unknown tool: {name}")
    try:
        payload = spec.handler(arguments if isinstance(arguments, dict) else {})
    except Exception as exc:
        return _success_response(
            msg_id,
            {
                "content": _tool_result_content({"error": str(exc)}),
                "isError": True,
            },
        )
    return _success_response(
        msg_id,
        {
            "content": _tool_result_content(payload),
            "isError": False,
        },
    )


def handle_message(message: dict[str, Any]) -> Optional[dict[str, Any]]:
    method = str(message.get("method") or "").strip()
    msg_id = message.get("id")
    if method == "initialize":
        return _handle_initialize(msg_id)
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return _handle_tools_list(msg_id)
    if method == "tools/call":
        return _handle_tools_call(msg_id, message.get("params") or {})
    if msg_id is None:
        return None
    return _error_response(msg_id, -32601, f"Method not found: {method}")


def serve_stdio() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error_response(None, -32700, f"Parse error: {exc}")
            print(json.dumps(response, ensure_ascii=False), flush=True)
            continue
        response = handle_message(message)
        if response is not None:
            print(json.dumps(response, default=_json_default, ensure_ascii=False), flush=True)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Temperance MCP server")
    parser.add_argument("--stdio", action="store_true", help="Run the server over stdio (default).")
    args = parser.parse_args(argv)
    if args.stdio or True:
        return serve_stdio()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote, urlsplit

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - optional in pure-helper test environments
    pd = None

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional in pure-helper test environments
    yaml = None

from pydantic import BaseModel, Field
from temperance.analytics import ema_multi
from temperance.planning import get_methodology, preview_horizon
from temperance.planning.state_builder import infer_hard_subtype
from temperance.planning.stress import classify_session_stress, is_long_run_candidate

JSONRPC_VERSION = "2.0"
DEFAULT_OWNER = "admin"
SERVER_PROTOCOL_VERSION = "2025-03-26"
ROOT_DIR = Path(__file__).resolve().parents[2]
GUIDELINES_DIR = ROOT_DIR / "temperance" / "guidelines" / "temperance-guidelines"
WORKOUTS_DIR = ROOT_DIR / "temperance" / "guidelines" / "temperance-workouts"
STATIC_RESOURCE_MIME_TYPE = "application/json"
RESOURCE_URI_PREFIX = "temperance://"
LOCAL_OVERRIDE_SUFFIX = ".local.md"
MARKDOWN_SUFFIX = ".md"
ACTIVE_BUILD_DOC_ID = "training-recent-cache"
HISTORY_DOC_ID = "training-history-memo"
READ_ORDER_DOC_ID = "training-llm-instructions"
CORE_BUNDLE_DOC_IDS = (
    "training-doctrine-governance",
    "training-control-system-doctrine",
    "training-phase-doctrine",
    "training-overlay-contract",
)
WORKOUT_OVERVIEW_DOCS = ("README.md", "quick-reference.md", "taxonomy.md")
WORKOUT_SHARED_DOCS = {"README.md", "catalog.md", "quick-reference.md", "taxonomy.md", "template-contract.md"}
DEFAULT_METHODOLOGY_ID = None
_BACKEND_MAIN_MODULE: Any = None


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class ResourceSpec:
    uri: str
    name: str
    description: str
    mime_type: str
    handler: Callable[[], dict[str, Any]]


@dataclass
class ResourceTemplateSpec:
    uri_template: str
    name: str
    description: str
    mime_type: str


@dataclass
class ResolvedDoc:
    doc_id: str
    path: Path
    is_local_override: bool
    status: str
    markdown: str


@dataclass
class WorkoutTemplateDoc:
    template_id: str
    session_family: str
    path: Path
    front_matter: dict[str, Any]
    body_markdown: str


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

class ActivityDetailArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    activity_id: str
    include_records: bool = True
    records_limit: int = 300

class PlanningToolArgs(BaseModel):
    owner: str = "default"
    target_day_utc: str
    mode: str = "planned"
    activity_type_preference: Optional[str] = None
    previous_activity_text: Optional[str] = None
    methodology_id: Optional[str] = None
    seed: Optional[int] = None
    schedule_constraints: list[dict[str, Any]] = Field(default_factory=list)


class PreviewCycleArgs(BaseModel):
    owner: str = "default"
    target_day_utc: str
    methodology_id: Optional[str] = None
    seed: Optional[int] = None
    horizon_days: Optional[int] = None
    schedule_constraints: list[dict[str, Any]] = Field(default_factory=list)


class ExplainPlanningArgs(PlanningToolArgs):
    question: Optional[str] = None


class HistoryJudgmentArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    window_days: int = 42
    end_day_utc: Optional[str] = None
    include_planned_comparison: bool = False


class ExplainHistoryJudgmentArgs(HistoryJudgmentArgs):
    question: Optional[str] = None


# --- Phase 1: Planning write models ---

class PlannedEntry(BaseModel):
    day_utc: str
    workout_text: str


class SavePlannedActivitiesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    entries: list[PlannedEntry]


class UpdatePlannedActivityArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    day_utc: str
    line_no: int
    workout_text: str


class DeletePlannedActivitiesKey(BaseModel):
    day_utc: str
    line_no: int


class DeletePlannedActivitiesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    keys: list[DeletePlannedActivitiesKey]


class MarkPlannedDoneArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    day_utc: str
    line_no: int
    manual_done: bool = True


# --- Phase 2: Custom activities, sync, activity management models ---

class SaveCustomActivitiesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    entries: list[PlannedEntry]


class DeleteCustomActivitiesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    keys: list[DeletePlannedActivitiesKey]


class TriggerSyncArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    days_back: int = 30
    profile: str = "quick"


class SyncStatusArgs(BaseModel):
    owner: str = DEFAULT_OWNER


class MarkActivityInvalidArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    activity_id: str
    is_invalid: bool = True


# --- Phase 3: Settings, workout search, fitness form models ---

class GetSettingsArgs(BaseModel):
    owner: str = DEFAULT_OWNER


class UpdateSettingsArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    lthr_curve: Optional[list[dict[str, Any]]] = None
    lt_pace_curve: Optional[list[dict[str, Any]]] = None
    timezone: Optional[str] = None
    specificity_profile: Optional[dict[str, Any]] = None
    injury_windows: Optional[list[dict[str, str]]] = None
    if_zone_thresholds: Optional[dict[str, Any]] = None
    vdot_lookback_days: Optional[int] = None


class SearchWorkoutsArgs(BaseModel):
    category: Optional[str] = None
    load_role: Optional[str] = None
    session_family: Optional[str] = None
    stress_class: Optional[str] = None
    phase_fit: Optional[str] = None
    modality_pattern: Optional[str] = None
    tss_min: Optional[float] = None
    tss_max: Optional[float] = None
    planning_intent: Optional[str] = None


class FitnessFormArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    days: int = 90
    sport: Optional[str] = None


class WeeklyVolumeArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    weeks: int = 8
    sport: Optional[str] = None


class CoachingBriefArgs(BaseModel):
    owner: str = DEFAULT_OWNER


# --- Phase 4: Load analysis and estimation models ---

class WorkoutTSSEntry(BaseModel):
    workout_text: str
    day_utc: Optional[str] = None


class EstimateWorkoutTSSArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    entries: list[WorkoutTSSEntry]


class SimulatePlanWeekArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    entries: list[PlannedEntry]


class CritiqueDayPlanArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    start_day_utc: Optional[str] = None
    end_day_utc: Optional[str] = None
    extra_entries: Optional[list[PlannedEntry]] = None


class EstimateXtrainTSSArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    activity_kind: str
    duration_min: float
    avg_hr_bpm: float
    target_day_utc: Optional[str] = None


def _backend_main_module() -> Any:
    global _BACKEND_MAIN_MODULE
    if _BACKEND_MAIN_MODULE is None:
        from backend.app import main as backend_main_module

        _BACKEND_MAIN_MODULE = backend_main_module
    return _BACKEND_MAIN_MODULE


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
    backend_main = _backend_main_module()

    return {
        "SETTINGS_KEY_USER_TIMEZONE": backend_main.SETTINGS_KEY_USER_TIMEZONE,
        "_build_athlete_progression_payload": backend_main._build_athlete_progression_payload,
        "_build_week_outlook_payload": backend_main._build_week_outlook_payload,
        "_build_wellness_payload": backend_main._build_wellness_payload,
        "_db_path_for_owner": backend_main._db_path_for_owner,
        "_metrics_for_filters": backend_main._metrics_for_filters,
        "get_planned_activities_df": backend_main.get_planned_activities_df,
    }


def _db_helpers() -> dict[str, Any]:
    from temperance.db import (
        delete_custom_activities,
        delete_planned_activities,
        get_last_sync,
        get_setting,
        set_activity_invalid,
        set_planned_activity_manual_done,
    )

    return {
        "get_last_sync": get_last_sync,
        "get_setting": get_setting,
        "delete_planned_activities": delete_planned_activities,
        "set_planned_activity_manual_done": set_planned_activity_manual_done,
        "delete_custom_activities": delete_custom_activities,
        "set_activity_invalid": set_activity_invalid,
    }


def _activity_detail_handler() -> Callable[..., dict[str, Any]]:
    return _backend_main_module().activity_detail


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


def _format_pace(sec_per_km: Any) -> Optional[str]:
    """Format seconds-per-km as a 'M:SS' pace string, or None if unavailable."""
    val = _safe_float(sec_per_km)
    if val <= 0:
        return None
    minutes = int(val // 60)
    seconds = int(val % 60)
    return f"{minutes}:{seconds:02d}"


def _hr_zone_dict(row: Any) -> Optional[dict[str, float]]:
    """Extract HR zone percentages as a compact dict, or None if all zeros."""
    zones = {}
    total = 0.0
    for i in range(1, 6):
        pct = _safe_float(row.get(f"hr_zone_{i}_pct"))
        zones[f"z{i}"] = round(pct, 1)
        total += pct
    if total <= 0:
        return None
    return zones


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


def _require_pandas() -> None:
    if pd is None:
        raise RuntimeError("pandas is required but not installed")


def _compute_fitness_metrics(db_path: Any, owner: str) -> dict[str, Any]:
    """Compute current fitness metrics from the athlete progression model.

    Uses the same ema_multi-based computation as the Athlete Progression dashboard,
    including rTSS/specificity-aware metrics. Returns empty dict if no data.

    Metric glossary:
      fitness    — 42-day TSS EMA (≈ CTL, chronic training load)
      fatigue    — 7-day TSS EMA (≈ ATL, acute training load)
      form       — fitness − fatigue (≈ TSB, training stress balance)
      acwr       — fatigue / fitness (acute:chronic workload ratio)
      overreach  — excess 10-day TSS load above daily target (0 when on-plan)
      injury_risk— excess 10-day rTSS load above daily target (running-specific overreach)
      durability — 100-day rTSS EMA (long-term running robustness)
      pounding   — 7-day rTSS EMA (acute running mechanical load)
    """
    _require_pandas()
    try:
        progression = _analytics_helpers()["_build_athlete_progression_payload"](
            db_path=db_path,
            days=180,
            activity_filter="all",
            aggregation="daily",
            owner=owner,
        )
    except Exception:
        return {}
    points = progression.get("points") or []
    if not points:
        return {}
    last = points[-1]
    fitness = _safe_float(last.get("fitness"))
    fatigue = _safe_float(last.get("fatigue"))
    return _clean_mapping({
        "fitness": round(fitness, 1),
        "fatigue": round(fatigue, 1),
        "form": round(fitness - fatigue, 1),
        "acwr": round(fatigue / fitness, 2) if fitness > 0 else None,
        "overreach": round(_safe_float(last.get("overreach")), 1),
        "injury_risk": round(_safe_float(last.get("injury_risk")), 1),
        "durability": round(_safe_float(last.get("durability")), 1),
        "pounding": round(_safe_float(last.get("pounding")), 1),
        "_note": (
            "fitness\u2248CTL (42-day TSS EMA), fatigue\u2248ATL (7-day TSS EMA); "
            "overreach and injury_risk measure excess load above daily target"
        ),
    })


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
        "max_hr": round(_safe_float(row.get("max_hr")), 1) or None,
        "avg_pace": _format_pace(row.get("avg_pace_s_per_km")),
        "elevation_gain_m": round(_safe_float(row.get("elevation_gain_m")), 0) or None,
    }
    if include_extended_metrics:
        payload.update(
            {
                "distance_equivalent_km": round(_safe_float(row.get("distance_proxy_km")), 2),
                "training_load_garmin": round(_safe_float(row.get("training_load_garmin")), 1),
                "mechanical_load": round(_safe_float(row.get("mechanical_load")), 2),
                "avg_cadence": round(_safe_float(row.get("avg_cadence")), 0) or None,
                "hr_zones": _hr_zone_dict(row),
            }
        )
    else:
        payload["mechanical_load"] = round(_safe_float(row.get("mechanical_load")), 2)
    return _clean_mapping(payload)


def _latest_wellness_point(wellness_payload: dict[str, Any]) -> dict[str, Any]:
    points = list(wellness_payload.get("points") or [])
    return _clean_mapping(dict(points[-1])) if points else {}


def tool_get_today_status(arguments: dict[str, Any]) -> dict[str, Any]:
    args = TodayStatusArgs.model_validate(arguments or {})
    db = _db_helpers()
    analytics = _analytics_helpers()
    db_path, metrics_df = _recent_metrics_df(args.owner, sport=args.sport, days=90)
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

    fitness_form = _compute_fitness_metrics(db_path, args.owner) if pd is not None else {}

    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "timezone": _owner_timezone(args.owner, db_path),
        "generated_at_utc": _utc_now().isoformat(),
        "latest_activity": latest_activity,
        "latest_wellness": latest_wellness,
        "fitness_form": fitness_form or None,
        "guideline_context": _active_build_brief() or None,
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
    today_str = _utc_now().date().isoformat()
    weekly_baseline = _weekly_baseline_tss_for_day(db_path, today_str)
    items: list[dict[str, Any]] = []
    for _, row in metrics_df.head(limit).iterrows():
        summary = _activity_row_summary(row)
        sport = str(row.get("sport_type") or "").strip().lower()
        modality = "running" if sport in ("running", "treadmill_running", "trail_running") else sport
        dur_min = _format_duration_minutes(row.get("duration_s"))
        avg_if = _safe_float(row.get("if_proxy"))
        max_if = avg_if
        stress_class, _, _ = classify_session_stress(
            estimated_tss=_safe_float(row.get("tss")),
            avg_if=avg_if,
            max_if=max_if,
            total_minutes=dur_min,
            modality=modality,
            weekly_baseline_tss=weekly_baseline,
        )
        summary["stress_class"] = stress_class.value
        summary["is_long_run"] = is_long_run_candidate(
            modality=modality,
            total_minutes=dur_min,
            avg_if=avg_if,
            max_if=max_if,
        )
        items.append(summary)
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

    # Use shared ema_multi (same function as Athlete Progression dashboard)
    tss_emas = ema_multi(grouped["tss"], [42, 7])
    rtss_emas = ema_multi(grouped["rtss"], [100, 7])
    grouped["fitness"] = tss_emas[42]       # 42-day TSS EMA (≈ CTL)
    grouped["fatigue"] = tss_emas[7]        # 7-day TSS EMA (≈ ATL)
    grouped["form"] = grouped["fitness"] - grouped["fatigue"]
    grouped["durability"] = rtss_emas[100]  # 100-day rTSS EMA
    grouped["pounding"] = rtss_emas[7]      # 7-day rTSS EMA

    daily_rows: list[dict[str, Any]] = []
    for _, row in grouped.tail(21).iterrows():
        day = pd.to_datetime(row.get("day"), errors="coerce")
        if pd.isna(day):
            continue
        fitness = _safe_float(row.get("fitness"))
        fatigue = _safe_float(row.get("fatigue"))
        acwr = round(fatigue / fitness, 2) if fitness > 0 else None
        daily_rows.append(
            _clean_mapping({
                "day": day.date().isoformat(),
                "tss": round(_safe_float(row.get("tss")), 1),
                "rtss": round(_safe_float(row.get("rtss")), 1),
                "duration_min": _format_duration_minutes(row.get("duration_s")),
                "activities": int(_safe_float(row.get("activities"))),
                "distance_equivalent_km": round(_safe_float(row.get("distance_equivalent_km")), 2),
                "fitness": round(fitness, 1),
                "fatigue": round(fatigue, 1),
                "form": round(_safe_float(row.get("form")), 1),
                "acwr": acwr,
                "durability": round(_safe_float(row.get("durability")), 1),
                "pounding": round(_safe_float(row.get("pounding")), 1),
                # backward-compat aliases
                "ctl_42_tss": round(fitness, 1),
                "atl_7_tss": round(fatigue, 1),
                "tsb_proxy": round(_safe_float(row.get("form")), 1),
            })
        )

    latest_fitness = _safe_float(grouped["fitness"].iloc[-1])
    latest_fatigue = _safe_float(grouped["fatigue"].iloc[-1])
    latest_durability = _safe_float(grouped["durability"].iloc[-1])
    latest_pounding = _safe_float(grouped["pounding"].iloc[-1])
    summary = {
        "days": int(max(args.days, 14)),
        "total_tss": round(_safe_float(grouped["tss"].sum()), 1),
        "total_rtss": round(_safe_float(grouped["rtss"].sum()), 1),
        "avg_daily_tss": round(_safe_float(grouped["tss"].mean()), 1),
        "avg_daily_rtss": round(_safe_float(grouped["rtss"].mean()), 1),
        "latest_fitness": round(latest_fitness, 1),
        "latest_fatigue": round(latest_fatigue, 1),
        "latest_form": round(latest_fitness - latest_fatigue, 1),
        "latest_acwr": round(latest_fatigue / latest_fitness, 2) if latest_fitness > 0 else None,
        "latest_durability": round(latest_durability, 1),
        "latest_pounding": round(latest_pounding, 1),
        # backward-compat aliases
        "latest_ctl_42_tss": round(latest_fitness, 1),
        "latest_atl_7_tss": round(latest_fatigue, 1),
        "latest_tsb_proxy": round(latest_fitness - latest_fatigue, 1),
        "_note": (
            "fitness\u2248CTL (42-day TSS EMA), fatigue\u2248ATL (7-day TSS EMA); "
            "durability=100-day rTSS EMA, pounding=7-day rTSS EMA; "
            "for overreach/injury_risk use get_fitness_form"
        ),
    }

    hr_zone_summary: Optional[dict[str, Any]] = None
    zone_cols = [f"hr_zone_{i}_pct" for i in range(1, 6)]
    if all(col in metrics_df.columns for col in zone_cols):
        dur_s = pd.to_numeric(metrics_df["duration_s"], errors="coerce").fillna(0.0)
        total_dur = dur_s.sum()
        if total_dur > 0:
            zone_pcts = {}
            for i in range(1, 6):
                col = f"hr_zone_{i}_pct"
                weighted = (pd.to_numeric(metrics_df[col], errors="coerce").fillna(0.0) * dur_s).sum() / total_dur
                zone_pcts[f"z{i}_pct"] = round(float(weighted), 1)
            low_intensity = zone_pcts.get("z1_pct", 0) + zone_pcts.get("z2_pct", 0)
            hr_zone_summary = {
                **zone_pcts,
                "polarization_index": round(low_intensity / 100.0, 2) if low_intensity > 0 else 0.0,
            }

    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "summary": _clean_mapping(summary),
        "daily": daily_rows,
        "hr_zone_summary": hr_zone_summary,
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


def _resource_uri(path: str) -> str:
    return f"{RESOURCE_URI_PREFIX}{path}"


def _resource_uri_for_doc_id(doc_id: str) -> str:
    return _resource_uri(f"guidelines/doc/{doc_id}")


def _resource_uri_for_template_id(template_id: str) -> str:
    return _resource_uri(f"workouts/template/{template_id}")


def _resource_uri_for_family(session_family: str) -> str:
    return _resource_uri(f"workouts/family/{session_family}")


def _extract_status(markdown: str) -> str:
    match = re.search(r"^Status:\s*(.+?)\s*$", markdown, flags=re.MULTILINE)
    return str(match.group(1)).strip() if match else ""


def _doc_id_from_filename(filename: str) -> str:
    if filename.endswith(LOCAL_OVERRIDE_SUFFIX):
        return filename[: -len(LOCAL_OVERRIDE_SUFFIX)]
    if filename.endswith(MARKDOWN_SUFFIX):
        return filename[: -len(MARKDOWN_SUFFIX)]
    return filename


def _normalize_doc_reference(value: str) -> str:
    return _doc_id_from_filename(str(value or "").strip().strip("`"))


def _slugify_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _parse_markdown_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "_intro"
    sections[current] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _section_bullets(section_body: str) -> list[str]:
    out: list[str] = []
    for raw_line in str(section_body or "").splitlines():
        line = raw_line.strip()
        if line.startswith("- "):
            out.append(line[2:].strip())
    return out


def _keyed_bullets(section_body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in _section_bullets(section_body):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        out[str(key).strip()] = str(value).strip()
    return out


def _numbered_items(section_body: str) -> list[str]:
    out: list[str] = []
    for raw_line in str(section_body or "").splitlines():
        match = re.match(r"^\d+\.\s+(.+?)\s*$", raw_line.strip())
        if match:
            out.append(match.group(1).strip())
    return out


def _parse_markdown_table(section_body: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in str(section_body or "").splitlines() if line.strip().startswith("|")]
    if len(lines) < 3:
        return []
    headers = [part.strip() for part in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for raw_line in lines[2:]:
        parts = [part.strip() for part in raw_line.strip("|").split("|")]
        if len(parts) != len(headers):
            continue
        rows.append({header: value for header, value in zip(headers, parts)})
    return rows


def _read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _scan_guideline_docs() -> dict[str, ResolvedDoc]:
    grouped: dict[str, dict[str, ResolvedDoc]] = defaultdict(dict)
    for path in sorted(GUIDELINES_DIR.glob("*.md")):
        doc_id = _doc_id_from_filename(path.name)
        markdown = _read_markdown(path)
        resolved = ResolvedDoc(
            doc_id=doc_id,
            path=path.resolve(),
            is_local_override=path.name.endswith(LOCAL_OVERRIDE_SUFFIX),
            status=_extract_status(markdown),
            markdown=markdown,
        )
        grouped[doc_id]["local" if resolved.is_local_override else "tracked"] = resolved
    return {
        doc_id: candidates.get("local") or candidates.get("tracked")
        for doc_id, candidates in grouped.items()
    }


def _resolve_guideline_doc(doc_id: str) -> ResolvedDoc:
    normalized = _normalize_doc_reference(doc_id)
    resolved = _scan_guideline_docs().get(normalized)
    if resolved is None:
        raise ValueError(f"Unknown guideline doc: {doc_id}")
    return resolved


def _resolved_doc_payload(doc: ResolvedDoc) -> dict[str, Any]:
    return {
        "doc_id": doc.doc_id,
        "resolved_path": str(doc.path),
        "is_local_override": doc.is_local_override,
        "status": doc.status,
        "markdown": doc.markdown,
        "resource_uri": _resource_uri_for_doc_id(doc.doc_id),
    }


def _build_guideline_doc_payload(doc_id: str) -> dict[str, Any]:
    return _resolved_doc_payload(_resolve_guideline_doc(doc_id))


def _split_front_matter(markdown: str) -> tuple[dict[str, Any], str]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            if yaml is None:
                raise RuntimeError("PyYAML is required to read workout template resources.")
            front_matter = yaml.safe_load("\n".join(lines[1:index])) or {}
            if not isinstance(front_matter, dict):
                front_matter = {}
            body = "\n".join(lines[index + 1 :]).lstrip("\n")
            return front_matter, body
    return {}, markdown


def _scan_workout_templates() -> dict[str, WorkoutTemplateDoc]:
    templates: dict[str, WorkoutTemplateDoc] = {}
    for path in sorted(WORKOUTS_DIR.glob("*/*.md")):
        markdown = _read_markdown(path)
        front_matter, body_markdown = _split_front_matter(markdown)
        template_id = str(front_matter.get("template_id") or path.stem).strip()
        session_family = str(front_matter.get("session_family") or path.parent.name).strip()
        templates[template_id] = WorkoutTemplateDoc(
            template_id=template_id,
            session_family=session_family,
            path=path.resolve(),
            front_matter=front_matter,
            body_markdown=body_markdown,
        )
    return templates


def _template_summary(template: WorkoutTemplateDoc) -> dict[str, Any]:
    front_matter = dict(template.front_matter)
    return {
        "template_id": template.template_id,
        "session_family": template.session_family,
        "category": front_matter.get("category"),
        "load_role": front_matter.get("load_role"),
        "structural_subtype": front_matter.get("structural_subtype"),
        "planning_intent": front_matter.get("planning_intent"),
        "modality_pattern": front_matter.get("modality_pattern"),
        "specificity_target": front_matter.get("specificity_target"),
        "durability_cost": front_matter.get("durability_cost"),
        "baseline_activity_text": front_matter.get("baseline_activity_text"),
        "baseline_estimated_tss": front_matter.get("baseline_estimated_tss"),
        "selection_window_tss": front_matter.get("selection_window_tss"),
        "resolved_path": str(template.path),
        "resource_uri": _resource_uri_for_template_id(template.template_id),
    }


def _default_family_anchor_map() -> dict[str, dict[str, str]]:
    workout_quick_reference = _read_markdown(WORKOUTS_DIR / "quick-reference.md")
    sections = _parse_markdown_sections(workout_quick_reference)
    rows = _parse_markdown_table(sections.get("Default Family Anchors", ""))
    anchors: dict[str, dict[str, str]] = {}
    for row in rows:
        family = str(row.get("Family") or "").strip().strip("`")
        template_link = str(row.get("Default template") or "").strip()
        match = re.search(r"\(([^)]+)\)", template_link)
        anchors[family] = {
            "need": str(row.get("Need") or "").strip(),
            "default_template_link": template_link,
            "default_template_path": match.group(1) if match else "",
        }
    return anchors


def _taxonomy_family_map() -> dict[str, dict[str, str]]:
    taxonomy_markdown = _read_markdown(WORKOUTS_DIR / "taxonomy.md")
    sections = _parse_markdown_sections(taxonomy_markdown)
    rows = _parse_markdown_table(sections.get("Family Map", ""))
    family_map: dict[str, dict[str, str]] = {}
    for row in rows:
        family = str(row.get("`session_family`") or "").strip().strip("`")
        family_map[family] = {
            "typical_category": str(row.get("Typical `category`") or "").strip(),
            "typical_load_role": str(row.get("Typical `load_role`") or "").strip(),
            "common_structural_subtype": str(row.get("Common `structural_subtype`") or "").strip(),
            "typical_doctrine_fit": str(row.get("Typical doctrine fit") or "").strip(),
        }
    return family_map


def _family_chooser_guidance(session_family: str) -> list[str]:
    quick_reference_markdown = _read_markdown(WORKOUTS_DIR / "quick-reference.md")
    sections = _parse_markdown_sections(quick_reference_markdown)
    rules: list[str] = []
    family = str(session_family or "").strip()
    section_map = {
        "split-quality": "Double Threshold Rule",
        "lt1-threshold": "Threshold Target Guide",
        "lt2-threshold": "Threshold Target Guide",
        "cruise-intervals": "Threshold Target Guide",
        "vo2-max": "VO2 Rule",
        "fartlek-alternations": "Fartlek Rule",
        "support": "Moderate-Support Chooser",
        "steady-aerobic": "Moderate-Support Chooser",
        "progressive": "Moderate-Support Chooser",
        "medium-long": "Moderate-Support Chooser",
        "x-train-specific": "Moderate-Support Chooser",
        "specific-endurance": "Specific-Endurance Chooser",
    }
    for section_name in filter(None, [section_map.get(family), "LT2 Ladder" if family == "lt2-threshold" else None]):
        rules.extend(_section_bullets(sections.get(section_name, "")))
    return rules


def _build_read_order_payload() -> dict[str, Any]:
    doc = _resolve_guideline_doc(READ_ORDER_DOC_ID)
    sections = _parse_markdown_sections(doc.markdown)
    return {
        "doc": _resolved_doc_payload(doc),
        "read_order": _numbered_items(sections.get("Read order", "")),
        "local_private_resolution": _section_bullets(sections.get("Local/private resolution", "")),
        "precedence": _numbered_items(sections.get("Precedence", "")),
        "interpretation_rules": _section_bullets(sections.get("Interpretation rules", "")),
        "recommendation_behavior": _section_bullets(sections.get("Recommendation behavior", "")),
        "workout_template_behavior": _section_bullets(sections.get("Workout-template behavior", "")),
        "update_behavior": _section_bullets(sections.get("Update behavior", "")),
    }


def _build_core_bundle_payload() -> dict[str, Any]:
    docs = [_resolve_guideline_doc(doc_id) for doc_id in CORE_BUNDLE_DOC_IDS]
    return {
        "docs": [_resolved_doc_payload(doc) for doc in docs],
        "doc_refs": [_resource_uri_for_doc_id(doc.doc_id) for doc in docs],
    }


def _build_active_build_payload() -> dict[str, Any]:
    active_doc = _resolve_guideline_doc(ACTIVE_BUILD_DOC_ID)
    sections = _parse_markdown_sections(active_doc.markdown)
    overlay_entries = _keyed_bullets(sections.get("Active overlay set", ""))
    overlay_profiles: dict[str, Any] = {}
    for label, value in overlay_entries.items():
        normalized_key = _slugify_label(label)
        doc_id = _normalize_doc_reference(value)
        try:
            overlay_profiles[normalized_key] = _resolved_doc_payload(_resolve_guideline_doc(doc_id))
        except ValueError:
            overlay_profiles[normalized_key] = {
                "doc_id": doc_id,
                "requested_value": value,
                "resource_uri": _resource_uri_for_doc_id(doc_id),
            }
    return {
        "active_build_doc": _resolved_doc_payload(active_doc),
        "overlay_set": overlay_entries,
        "selected_profiles": overlay_profiles,
        "active_anchor_mapping": _keyed_bullets(sections.get("Active anchor mapping", "")),
        "current_planning_anchors": _section_bullets(sections.get("Current planning anchors", "")),
        "current_phase_and_immediate_objective": _section_bullets(sections.get("Current phase and immediate objective", "")),
        "temporary_constraints": _section_bullets(sections.get("Temporary exceptions / current constraints", "")),
        "near_term_interpretation": _section_bullets(sections.get("Near-term interpretation", "")),
        "near_term_hard_session_emphasis": _section_bullets(sections.get("Near-term hard-session emphasis", "")),
        "recommendation_style_preferences": _section_bullets(sections.get("Current recommendation style preferences", "")),
        "watchouts": _section_bullets(sections.get("Current watchouts", "")),
        "history_memo_ref": _resource_uri_for_doc_id(HISTORY_DOC_ID),
    }


def _active_build_brief() -> dict[str, Any]:
    """Lightweight summary of active build context for embedding in tool outputs."""
    try:
        active_build = _build_active_build_payload()
    except Exception:
        return {}
    phase_bullets = active_build.get("current_phase_and_immediate_objective") or []
    phase = phase_bullets[0] if phase_bullets else None
    overlays = list((active_build.get("overlay_set") or {}).values())
    anchors = active_build.get("active_anchor_mapping") or {}
    weekly_baseline = None
    for key, value in anchors.items():
        if "weekly" in key.lower() and "tss" in key.lower():
            try:
                weekly_baseline = float("".join(c for c in str(value) if c.isdigit() or c == "."))
            except (ValueError, TypeError):
                pass
            break
    return _clean_mapping({
        "phase": phase,
        "overlays": overlays if overlays else None,
        "weekly_baseline_tss": weekly_baseline,
        "watchouts": active_build.get("watchouts") or None,
        "resource_refs": [
            _resource_uri("guidelines/active-build"),
            _resource_uri("guidelines/read-order"),
        ],
    })


def _build_workout_overview_payload() -> dict[str, Any]:
    docs = []
    for filename in WORKOUT_OVERVIEW_DOCS:
        path = (WORKOUTS_DIR / filename).resolve()
        docs.append(
            {
                "doc_id": _doc_id_from_filename(filename),
                "resolved_path": str(path),
                "markdown": _read_markdown(path),
                "resource_uri": _resource_uri("workouts/overview"),
            }
        )
    templates = _scan_workout_templates()
    return {
        "docs": docs,
        "template_count": len(templates),
        "session_family_count": len({template.session_family for template in templates.values()}),
    }


def _build_workout_catalog_payload() -> dict[str, Any]:
    templates = _scan_workout_templates()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for template in templates.values():
        grouped[template.session_family].append(_template_summary(template))
    return {
        "session_families": [
            {
                "session_family": family,
                "templates": sorted(items, key=lambda item: item["template_id"]),
            }
            for family, items in sorted(grouped.items())
        ],
        "template_count": len(templates),
    }


def _build_workout_template_payload(template_id: str) -> dict[str, Any]:
    template = _scan_workout_templates().get(str(template_id or "").strip())
    if template is None:
        raise ValueError(f"Unknown workout template: {template_id}")
    return {
        "template_id": template.template_id,
        "resolved_path": str(template.path),
        "front_matter": template.front_matter,
        "body_markdown": template.body_markdown,
    }


def _build_workout_family_payload(session_family: str) -> dict[str, Any]:
    templates = [template for template in _scan_workout_templates().values() if template.session_family == session_family]
    if not templates:
        raise ValueError(f"Unknown workout family: {session_family}")
    taxonomy = _taxonomy_family_map().get(session_family, {})
    anchors = _default_family_anchor_map().get(session_family, {})
    return {
        "session_family": session_family,
        "family_metadata": taxonomy,
        "default_anchor": anchors,
        "chooser_guidance": _family_chooser_guidance(session_family),
        "templates": sorted((_template_summary(template) for template in templates), key=lambda item: item["template_id"]),
    }


def _build_static_resource_payload(uri: str) -> dict[str, Any]:
    if uri == _resource_uri("guidelines/read-order"):
        return _build_read_order_payload()
    if uri == _resource_uri("guidelines/core-bundle"):
        return _build_core_bundle_payload()
    if uri == _resource_uri("guidelines/active-build"):
        return _build_active_build_payload()
    if uri == _resource_uri("workouts/overview"):
        return _build_workout_overview_payload()
    if uri == _resource_uri("workouts/catalog"):
        return _build_workout_catalog_payload()
    raise ValueError(f"Unknown resource: {uri}")


def _coerce_day_utc(value: str | None, *, default: Optional[date] = None) -> str:
    raw = str(value or "").strip()
    if not raw:
        if default is None:
            raise ValueError("A day_utc value is required.")
        return default.isoformat()
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError as exc:
        raise ValueError(f"Invalid day_utc: {value}") from exc


def _window_bounds(window_days: int, end_day_utc: Optional[str] = None) -> tuple[str, str]:
    safe_window = max(1, min(int(window_days), 365))
    end_day = date.fromisoformat(_coerce_day_utc(end_day_utc, default=_utc_now().date()))
    start_day = end_day - timedelta(days=safe_window - 1)
    return start_day.isoformat(), end_day.isoformat()


def _lt_pace_for_day(db_path: Path, day_utc: str) -> float:
    backend_main = _backend_main_module()
    pace_curve = backend_main._load_curve_points(
        db_path=db_path,
        key=backend_main.SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=backend_main.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    pace_default = float(pace_curve[-1][1]) if pace_curve else backend_main.DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    day_ts = backend_main.pd.to_datetime(day_utc, utc=True, errors="coerce")
    if backend_main.pd.isna(day_ts):
        raise ValueError(f"Invalid target_day_utc: {day_utc}")
    return float(backend_main._curve_value_at(pace_curve, pace_default, day_ts))


def _lthr_for_day(db_path: Path, day_utc: str) -> float:
    backend_main = _backend_main_module()
    lthr_curve = backend_main._load_curve_points(
        db_path=db_path,
        key=backend_main.SETTINGS_KEY_LTHR_CURVE,
        value_key="lthr_bpm",
        fallback_value=backend_main.DEFAULT_LTHR,
    )
    lthr_default = float(lthr_curve[-1][1]) if lthr_curve else backend_main.DEFAULT_LTHR
    day_ts = backend_main.pd.to_datetime(day_utc, utc=True, errors="coerce")
    if backend_main.pd.isna(day_ts):
        raise ValueError(f"Invalid target_day_utc: {day_utc}")
    return float(backend_main._curve_value_at(lthr_curve, lthr_default, day_ts))


def _weekly_baseline_tss_for_day(db_path: Path, day_utc: str) -> float:
    backend_main = _backend_main_module()
    pace_for_day = _lt_pace_for_day(db_path, day_utc)
    return backend_main._weekly_tss_target_from_lt_pace(pace_for_day) * 1.10 if pace_for_day > 0 else 350.0


def _planning_context_parts(
    *,
    owner: str,
    target_day_utc: str,
    methodology_id: Optional[str] = None,
    seed: Optional[int] = None,
    horizon_days: Optional[int] = None,
    schedule_constraints: list[dict[str, Any]] | None = None,
) -> tuple[Path, Any, Any, tuple[Any, ...], dict[str, Any]]:
    backend_main = _backend_main_module()
    db_path = backend_main._db_path_for_owner(owner)
    planning_state = backend_main._generated_activity_planning_state(
        db_path=db_path,
        day_utc=target_day_utc,
        threshold_pace_sec_per_km=_lt_pace_for_day(db_path, target_day_utc),
        methodology_id=methodology_id,
        schedule_constraints=schedule_constraints or [],
    )
    if planning_state is None:
        raise ValueError("Invalid target_day_utc")
    methodology = get_methodology(methodology_id)
    horizon, preview_meta = preview_horizon(
        state=planning_state,
        methodology_id=methodology.methodology_id,
        seed=seed,
        horizon_days=horizon_days,
    )
    return db_path, methodology, planning_state, horizon, preview_meta


def _preview_intents_payload(horizon: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [
        {
            "day_utc": intent.day_utc,
            "cycle_step_id": intent.cycle_step_id,
            "day_type": intent.day_type.value,
            "hard_subtype": intent.hard_subtype.value if intent.hard_subtype is not None else None,
            "target_tss": intent.target_tss,
            "sampled_tss_share": intent.sampled_tss_share,
            "target_duration_min": intent.target_duration_min,
            "modality_bias": intent.modality_bias,
            "planned_rest": intent.planned_rest,
        }
        for intent in horizon
    ]


def _planning_state_summary(planning_state: Any) -> dict[str, Any]:
    return {
        "weekly_baseline_tss": planning_state.weekly_baseline_tss,
        "recent_load_7d": planning_state.recent_load_7d,
        "recent_load_28d": planning_state.recent_load_28d,
        "recent_load_ratio": planning_state.recent_load_ratio,
        "fatigue": {
            "fitness": planning_state.fatigue.fitness,
            "fatigue": planning_state.fatigue.fatigue,
            "overreach": planning_state.fatigue.overreach,
            "injury_risk": planning_state.fatigue.injury_risk,
            "training_readiness": planning_state.fatigue.training_readiness,
            "sleep_score": planning_state.fatigue.sleep_score,
            "stress_avg": planning_state.fatigue.stress_avg,
            "recovery_alert": planning_state.fatigue.recovery_alert,
        },
        "mechanical_risk": {
            "injury_window_active": planning_state.mechanical_risk.injury_window_active,
            "injury_labels": list(planning_state.mechanical_risk.injury_labels),
            "running_share_14d": planning_state.mechanical_risk.running_share_14d,
            "elliptical_share_14d": planning_state.mechanical_risk.elliptical_share_14d,
            "mechanical_load_7d": planning_state.mechanical_risk.mechanical_load_7d,
            "fragility_score": planning_state.mechanical_risk.fragility_score,
            "prefer_low_impact": planning_state.mechanical_risk.prefer_low_impact,
        },
        "modality_mix": {
            "running": planning_state.modality_mix_running,
            "elliptical": planning_state.modality_mix_elliptical,
        },
        "last_long_run": {
            "day_utc": planning_state.last_long_run_day_utc,
            "duration_min": planning_state.last_long_run_minutes,
        },
    }


def _build_planning_context_payload(owner: str, target_day_utc: str) -> dict[str, Any]:
    normalized_day = _coerce_day_utc(target_day_utc)
    db_path, methodology, planning_state, horizon, preview_meta = _planning_context_parts(
        owner=owner,
        target_day_utc=normalized_day,
        methodology_id=DEFAULT_METHODOLOGY_ID,
    )
    active_build = _build_active_build_payload()
    return {
        "owner": owner,
        "target_day_utc": normalized_day,
        "db_path": str(db_path),
        "active_build": active_build,
        "planning_state_summary": _planning_state_summary(planning_state),
        "today_status": tool_get_today_status({"owner": owner}),
        "preview_horizon": _preview_intents_payload(horizon),
        "preview_meta": preview_meta,
        "recent_long_run_summary": [
            {
                "day_utc": item.day_utc,
                "duration_min": item.duration_min,
                "avg_if": item.avg_if,
                "tss": item.tss,
                "source": item.source,
            }
            for item in planning_state.recent_long_runs
        ],
        "schedule_constraints": [
            {
                "day_utc": constraint.day_utc,
                "allow_long_run": constraint.allow_long_run,
                "preferred_modality": constraint.preferred_modality,
                "blocked": constraint.blocked,
            }
            for constraint in planning_state.schedule_constraints
        ],
        "doctrine_resource_refs": [
            _resource_uri("guidelines/read-order"),
            _resource_uri("guidelines/active-build"),
            _resource_uri("workouts/overview"),
        ]
        + [profile.get("resource_uri") for profile in active_build.get("selected_profiles", {}).values() if isinstance(profile, dict) and profile.get("resource_uri")],
        "methodology_id": methodology.methodology_id,
    }


def _aggregate_actual_day_rows(owner: str, start_day_utc: str, end_day_utc: str) -> tuple[Path, list[dict[str, Any]]]:
    backend_main = _backend_main_module()
    db_path = _resolve_db_path(owner)
    metrics_df = _analytics_helpers()["_metrics_for_filters"](
        db_path=db_path,
        days=max((date.fromisoformat(end_day_utc) - date.fromisoformat(start_day_utc)).days + 1, 1),
        start_day=start_day_utc,
        end_day=end_day_utc,
        sport=None,
        include_invalid=False,
        include_mechanical_load=True,
    )
    selected_day = backend_main.pd.Timestamp(date.fromisoformat(end_day_utc) + timedelta(days=1))
    return db_path, backend_main._aggregate_actual_days_for_planning(metrics_df=metrics_df, selected_day=selected_day)


def _aggregate_planned_day_rows(db_path: Path, start_day_utc: str, end_day_utc: str) -> list[dict[str, Any]]:
    backend_main = _backend_main_module()
    return backend_main._aggregate_planned_days_for_planning(
        db_path=db_path,
        start_day=backend_main.pd.Timestamp(start_day_utc),
        end_day=backend_main.pd.Timestamp(end_day_utc),
    )


def _hard_flavor_from_row(row: dict[str, Any], stress_profile: Any, hard_subtype: Any) -> Optional[str]:
    modality = str(row.get("modality") or "").strip().lower()
    total_minutes = _format_duration_minutes(row.get("duration_s"))
    avg_if = _safe_float(row.get("avg_if"))
    max_if = _safe_float(row.get("max_if"))
    if hard_subtype is None:
        return None
    if is_long_run_candidate(
        modality=modality,
        total_minutes=total_minutes,
        avg_if=avg_if,
        max_if=max_if,
        stress_profile=stress_profile,
    ):
        return "long-run-hard"
    if avg_if >= 0.93 or max_if >= 0.98:
        return "sharp-hard"
    if modality == "running" and total_minutes >= 60.0 and avg_if >= 0.79:
        return "specific-hard"
    return "threshold-hard"


def _classify_history_rows(rows: list[dict[str, Any]], weekly_baseline_tss: float, stress_profile: Any) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []
    for row in rows:
        modality = str(row.get("modality") or "").strip().lower()
        total_minutes = _format_duration_minutes(row.get("duration_s"))
        avg_if = _safe_float(row.get("avg_if"))
        max_if = _safe_float(row.get("max_if"))
        stress_class, toughness_score, override_reason = classify_session_stress(
            estimated_tss=_safe_float(row.get("tss")),
            avg_if=avg_if,
            max_if=max_if,
            total_minutes=total_minutes,
            modality=modality,
            bucket=str(row.get("bucket") or ""),
            weekly_baseline_tss=weekly_baseline_tss,
            stress_profile=stress_profile,
        )
        hard_subtype = infer_hard_subtype(
            stress_class=stress_class,
            modality=modality,
            total_minutes=total_minutes,
            avg_if=avg_if,
            max_if=max_if,
            workout_text=str(row.get("workout_text") or ""),
            stress_profile=stress_profile,
        )
        is_long = is_long_run_candidate(
            modality=modality,
            total_minutes=total_minutes,
            avg_if=avg_if,
            max_if=max_if,
            stress_profile=stress_profile,
        )
        classified.append(
            {
                **row,
                "stress_class": stress_class.value,
                "hard_subtype": hard_subtype.value if hard_subtype is not None else None,
                "toughness_score": toughness_score,
                "stress_override_reason": override_reason,
                "is_long_run": is_long,
                "hard_flavor": _hard_flavor_from_row(row, stress_profile, hard_subtype),
            }
        )
    return classified


def _load_summary(rows: list[dict[str, Any]], window_days: int) -> dict[str, Any]:
    total_tss = sum(_safe_float(row.get("tss")) for row in rows)
    total_duration_min = sum(_format_duration_minutes(row.get("duration_s")) for row in rows)
    return {
        "total_tss": round(total_tss, 1),
        "avg_daily_tss": round(total_tss / max(window_days, 1), 1),
        "total_duration_min": round(total_duration_min, 1),
        "days_with_activities": len(rows),
    }


def _hard_session_mix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hard_rows = [row for row in rows if row.get("stress_class") == "hard"]
    subtype_counts = Counter(str(row.get("hard_subtype") or "unknown") for row in hard_rows)
    flavor_counts = Counter(str(row.get("hard_flavor") or "unclassified") for row in hard_rows)
    return {
        "hard_day_count": len(hard_rows),
        "hard_subtype_counts": dict(subtype_counts),
        "hard_flavor_counts": dict(flavor_counts),
        "hard_days": [
            {
                "day_utc": row.get("day_utc"),
                "tss": round(_safe_float(row.get("tss")), 1),
                "avg_if": round(_safe_float(row.get("avg_if")), 3),
                "hard_subtype": row.get("hard_subtype"),
                "hard_flavor": row.get("hard_flavor"),
            }
            for row in hard_rows
        ],
    }


def _spacing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hard_days = sorted(date.fromisoformat(str(row.get("day_utc"))) for row in rows if row.get("stress_class") == "hard")
    gaps = [(current - previous).days for previous, current in zip(hard_days, hard_days[1:])]
    return {
        "hard_day_count": len(hard_days),
        "min_gap_days": min(gaps) if gaps else None,
        "avg_gap_days": round(sum(gaps) / len(gaps), 1) if gaps else None,
        "tight_spacings": [
            {"gap_days": gap, "from_day_utc": previous.isoformat(), "to_day_utc": current.isoformat()}
            for previous, current, gap in zip(hard_days, hard_days[1:], gaps)
            if gap < 2
        ],
    }


def _long_run_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    long_runs = [row for row in rows if bool(row.get("is_long_run"))]
    durations = [_format_duration_minutes(row.get("duration_s")) for row in long_runs]
    latest = long_runs[-1] if long_runs else None
    previous = long_runs[-2] if len(long_runs) >= 2 else None
    latest_duration = _format_duration_minutes(latest.get("duration_s")) if latest else None
    previous_duration = _format_duration_minutes(previous.get("duration_s")) if previous else None
    return {
        "count": len(long_runs),
        "latest": (
            {
                "day_utc": latest.get("day_utc"),
                "duration_min": latest_duration,
                "avg_if": round(_safe_float(latest.get("avg_if")), 3),
                "tss": round(_safe_float(latest.get("tss")), 1),
            }
            if latest
            else None
        ),
        "latest_progression_delta_min": round(latest_duration - previous_duration, 1)
        if latest_duration is not None and previous_duration is not None
        else None,
        "durations_min": durations,
    }


def _modality_mix_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    duration_by_modality: Counter[str] = Counter()
    total_duration = 0.0
    for row in rows:
        duration_min = _format_duration_minutes(row.get("duration_s"))
        modality = str(row.get("modality") or "unknown").strip().lower() or "unknown"
        duration_by_modality[modality] += duration_min
        total_duration += duration_min
    return {
        "duration_min_by_modality": {key: round(value, 1) for key, value in duration_by_modality.items()},
        "share_by_modality": {
            key: round((value / total_duration), 3) if total_duration > 0 else 0.0
            for key, value in duration_by_modality.items()
        },
    }


def _coverage_summary(owner: str, db_path: Path, start_day_utc: str, end_day_utc: str, actual_rows: list[dict[str, Any]]) -> dict[str, Any]:
    wellness_payload = _analytics_helpers()["_build_wellness_payload"](db_path=db_path, days=max((date.fromisoformat(end_day_utc) - date.fromisoformat(start_day_utc)).days + 1, 1), aggregation="daily", owner=owner)
    points = [
        point
        for point in list(wellness_payload.get("points") or [])
        if start_day_utc <= str(point.get("period_start") or "") <= end_day_utc
    ]
    return {
        "has_actual_data": bool(actual_rows),
        "actual_days_with_activities": len(actual_rows),
        "wellness_days_available": len(points),
        "has_wellness_data": bool(points),
    }


def _history_snapshot_components(owner: str, window_days: int, end_day_utc: Optional[str] = None) -> dict[str, Any]:
    start_day_utc, normalized_end_day_utc = _window_bounds(window_days, end_day_utc)
    reference_day_utc = (date.fromisoformat(normalized_end_day_utc) + timedelta(days=1)).isoformat()
    db_path, methodology, planning_state, _, _ = _planning_context_parts(
        owner=owner,
        target_day_utc=reference_day_utc,
        methodology_id=DEFAULT_METHODOLOGY_ID,
    )
    actual_db_path, actual_rows = _aggregate_actual_day_rows(owner, start_day_utc, normalized_end_day_utc)
    classified_actuals = _classify_history_rows(actual_rows, planning_state.weekly_baseline_tss, methodology.stress_profile)
    return {
        "owner": owner,
        "window_days": max(1, min(int(window_days), 365)),
        "start_day_utc": start_day_utc,
        "end_day_utc": normalized_end_day_utc,
        "db_path": str(db_path),
        "planning_state": planning_state,
        "methodology": methodology,
        "coverage": _coverage_summary(owner, actual_db_path, start_day_utc, normalized_end_day_utc, classified_actuals),
        "actual_rows": classified_actuals,
        "planned_rows": _aggregate_planned_day_rows(db_path, start_day_utc, normalized_end_day_utc),
    }


def _build_history_snapshot_payload(owner: str, window_days: int, end_day_utc: Optional[str] = None) -> dict[str, Any]:
    snapshot = _history_snapshot_components(owner, window_days, end_day_utc=end_day_utc)
    rows = snapshot["actual_rows"]
    return {
        "owner": owner,
        "window_days": snapshot["window_days"],
        "end_day_utc": snapshot["end_day_utc"],
        "start_day_utc": snapshot["start_day_utc"],
        "actual_history_coverage_flags": snapshot["coverage"],
        "load_summary": _load_summary(rows, snapshot["window_days"]),
        "hard_session_mix": _hard_session_mix(rows),
        "spacing_summary": _spacing_summary(rows),
        "long_run_summary": _long_run_summary(rows),
        "modality_mix": _modality_mix_summary(rows),
        "evidence_refs": [
            _resource_uri("guidelines/active-build"),
            _resource_uri_for_doc_id(HISTORY_DOC_ID),
            _resource_uri("workouts/overview"),
        ],
    }


def _build_planned_comparison(snapshot: dict[str, Any]) -> dict[str, Any]:
    actual_rows = snapshot["actual_rows"]
    planned_rows = _classify_history_rows(snapshot["planned_rows"], snapshot["planning_state"].weekly_baseline_tss, snapshot["methodology"].stress_profile)
    actual_total_tss = sum(_safe_float(row.get("tss")) for row in actual_rows)
    planned_total_tss = sum(_safe_float(row.get("tss")) for row in planned_rows)
    return {
        "actual_total_tss": round(actual_total_tss, 1),
        "planned_total_tss": round(planned_total_tss, 1),
        "tss_delta": round(actual_total_tss - planned_total_tss, 1),
        "actual_hard_days": _hard_session_mix(actual_rows).get("hard_day_count"),
        "planned_hard_days": _hard_session_mix(planned_rows).get("hard_day_count"),
    }


def _assess_history_against_doctrine(snapshot: dict[str, Any], active_build: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], str]:
    actual_rows = snapshot["actual_rows"]
    planning_state = snapshot["planning_state"]
    load_summary = _load_summary(actual_rows, snapshot["window_days"])
    hard_mix = _hard_session_mix(actual_rows)
    spacing = _spacing_summary(actual_rows)
    long_run = _long_run_summary(actual_rows)
    modality_mix = _modality_mix_summary(actual_rows)
    active_markdown = str(active_build.get("active_build_doc", {}).get("markdown") or "").lower()
    concerns: list[str] = []
    imbalances: list[str] = []
    aligned: list[str] = []
    alerts: list[dict[str, Any]] = []

    if not snapshot["coverage"].get("has_actual_data"):
        alerts.append({"severity": "hard", "type": "coverage", "message": "No actual activity data is available in the requested window."})
        concerns.append("Actual-history coverage is missing, so the judgment is necessarily partial.")
    else:
        aligned.append(f"Window includes {snapshot['coverage']['actual_days_with_activities']} actual training days.")

    if spacing.get("min_gap_days") is not None and spacing["min_gap_days"] < 2 and hard_mix.get("hard_day_count", 0) >= 3:
        alerts.append({"severity": "hard", "type": "spacing", "message": "Hard sessions are stacked with less than two days between them."})
        concerns.append("Hard-session spacing is tighter than the default control logic usually wants.")
    elif hard_mix.get("hard_day_count", 0) > 0:
        aligned.append("Hard-session spacing stays within a usable range for the requested window.")

    sharp_count = int(hard_mix.get("hard_flavor_counts", {}).get("sharp-hard", 0))
    threshold_count = int(hard_mix.get("hard_flavor_counts", {}).get("threshold-hard", 0))
    if sharp_count > threshold_count and "threshold" in active_markdown:
        alerts.append({"severity": "soft", "type": "mix", "message": "Sharp work is outnumbering threshold-oriented hard work."})
        imbalances.append("The hard-session mix is skewing sharper than the active philosophy suggests.")
    elif threshold_count > 0:
        aligned.append("Threshold-oriented hard work is represented in the window.")

    if long_run.get("count", 0) == 0 and snapshot["window_days"] >= 14 and ("long-run" in active_markdown or "marathon" in active_markdown):
        alerts.append({"severity": "soft", "type": "long_run", "message": "No qualifying long run appears in a window where the active build still values long-run continuity."})
        concerns.append("Long-run continuity is missing for the active build.")
    elif long_run.get("count", 0) > 0:
        aligned.append("The window contains long-run contact.")

    running_share = _safe_float(modality_mix.get("share_by_modality", {}).get("running"))
    if planning_state.mechanical_risk.prefer_low_impact and running_share >= 0.75:
        alerts.append({"severity": "hard", "type": "durability", "message": "Running is dominating the window despite a low-impact preference in the current state."})
        concerns.append("The modality mix may be too run-heavy for the current durability context.")
    elif running_share > 0:
        aligned.append("The modality mix is explicit enough to judge against current constraints.")

    if planning_state.recent_load_ratio >= 1.25 and planning_state.fatigue.recovery_alert:
        alerts.append({"severity": "hard", "type": "load_shape", "message": "Recent load is elevated while recovery alerts are already active."})
        concerns.append("Recent load shape and recovery status are both flashing caution.")

    status = "aligned"
    if any(alert["severity"] == "hard" for alert in alerts):
        status = "risky"
    elif alerts or imbalances or concerns:
        status = "mixed"
    headline_map = {
        "aligned": "History is broadly aligned with the active build and current control logic.",
        "mixed": "History is usable but shows gaps or imbalances against the active doctrine.",
        "risky": "History is carrying meaningful structural risk against the active doctrine.",
    }
    doctrine_assessment = {
        "aligned": aligned,
        "gaps": concerns,
        "imbalances": imbalances,
        "evidence_refs": [
            _resource_uri("guidelines/active-build"),
            _resource_uri("guidelines/read-order"),
            _resource_uri_for_doc_id(HISTORY_DOC_ID),
        ],
    }
    judgment = {
        "status": status,
        "headline": headline_map[status],
        "primary_risk": alerts[0]["message"] if alerts else None,
    }
    narrative = " ".join(
        part
        for part in [
            headline_map[status],
            f"Load: {load_summary['total_tss']} TSS across {load_summary['days_with_activities']} active days."
            if snapshot["coverage"].get("has_actual_data")
            else None,
            f"Hard mix: {hard_mix.get('hard_day_count', 0)} hard days."
            if hard_mix.get("hard_day_count", 0)
            else "No hard days were detected.",
            f"Long runs: {long_run.get('count', 0)}."
            if long_run.get("count", 0) or snapshot["window_days"] >= 14
            else None,
        ]
        if part
    )
    return doctrine_assessment, alerts, judgment, narrative


def _build_history_judgment_payload(arguments: dict[str, Any]) -> dict[str, Any]:
    args = HistoryJudgmentArgs.model_validate(arguments or {})
    snapshot = _history_snapshot_components(args.owner, args.window_days, end_day_utc=args.end_day_utc)
    active_build = _build_active_build_payload()
    actual_summary = {
        "coverage": snapshot["coverage"],
        "load_summary": _load_summary(snapshot["actual_rows"], snapshot["window_days"]),
    }
    structure_summary = {
        "hard_session_mix": _hard_session_mix(snapshot["actual_rows"]),
        "spacing_summary": _spacing_summary(snapshot["actual_rows"]),
        "long_run_summary": _long_run_summary(snapshot["actual_rows"]),
        "modality_mix": _modality_mix_summary(snapshot["actual_rows"]),
    }
    doctrine_assessment, alerts, judgment, narrative = _assess_history_against_doctrine(snapshot, active_build)
    payload = {
        "window": {
            "owner": args.owner,
            "window_days": snapshot["window_days"],
            "start_day_utc": snapshot["start_day_utc"],
            "end_day_utc": snapshot["end_day_utc"],
        },
        "active_build": active_build,
        "actual_summary": actual_summary,
        "structure_summary": structure_summary,
        "doctrine_assessment": doctrine_assessment,
        "alerts": alerts,
        "judgment": judgment,
        "narrative": narrative,
    }
    if args.include_planned_comparison:
        payload["planned_comparison"] = _build_planned_comparison(snapshot)
    return payload


def _answer_history_question(payload: dict[str, Any], question: Optional[str]) -> str:
    q = str(question or "").strip().lower()
    structure = dict(payload.get("structure_summary") or {})
    judgment = dict(payload.get("judgment") or {})
    if "spacing" in q:
        spacing = dict(structure.get("spacing_summary") or {})
        return (
            f"{judgment.get('headline')} Min hard-session gap: {spacing.get('min_gap_days')}; "
            f"tight spacings: {len(spacing.get('tight_spacings') or [])}."
        )
    if "long" in q:
        long_run = dict(structure.get("long_run_summary") or {})
        return (
            f"{judgment.get('headline')} Long-run count: {long_run.get('count')}; "
            f"latest progression delta: {long_run.get('latest_progression_delta_min')} min."
        )
    if "mix" in q or "threshold" in q or "sharp" in q:
        hard_mix = dict(structure.get("hard_session_mix") or {})
        return (
            f"{judgment.get('headline')} Hard-flavor mix: "
            f"{json.dumps(hard_mix.get('hard_flavor_counts') or {}, ensure_ascii=False)}."
        )
    return str(payload.get("narrative") or judgment.get("headline") or "")


def tool_judge_training_history(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = _build_history_judgment_payload(arguments)
    payload["guideline_context"] = _active_build_brief() or None
    return payload


def tool_explain_history_judgment(arguments: dict[str, Any]) -> dict[str, Any]:
    args = ExplainHistoryJudgmentArgs.model_validate(arguments or {})
    payload = _build_history_judgment_payload(arguments)
    return {
        "judgment": payload.get("judgment"),
        "answer": _answer_history_question(payload, args.question),
        "evidence_refs": payload.get("doctrine_assessment", {}).get("evidence_refs", []),
    }


def _coerce_constraints(args: dict[str, Any]) -> list[dict[str, Any]]:
    constraints = args.get("schedule_constraints")
    if not isinstance(constraints, list):
        return []
    out: list[dict[str, Any]] = []
    for item in constraints:
        if not isinstance(item, dict):
            continue
        day_utc = str(item.get("day_utc") or "").strip()
        if not day_utc:
            continue
        out.append(
            {
                "day_utc": day_utc,
                "allow_long_run": item.get("allow_long_run"),
                "preferred_modality": str(item.get("preferred_modality") or "").strip().lower() or None,
                "blocked": bool(item.get("blocked")),
            }
        )
    return out


def _build_preview_payload(args: dict[str, Any]) -> dict[str, Any]:
    owner = str(args.get("owner") or "default").strip() or "default"
    day_utc = _coerce_day_utc(str(args.get("target_day_utc") or "").strip())
    methodology_id = str(args.get("methodology_id") or "").strip() or None
    seed = int(args["seed"]) if args.get("seed") is not None else None
    horizon_days = int(args["horizon_days"]) if args.get("horizon_days") is not None else None
    db_path, methodology, planning_state, horizon, preview_meta = _planning_context_parts(
        owner=owner,
        target_day_utc=day_utc,
        methodology_id=methodology_id,
        seed=seed,
        horizon_days=horizon_days,
        schedule_constraints=_coerce_constraints(args),
    )
    return {
        "owner": owner,
        "db_path": str(db_path),
        "methodology_id": methodology.methodology_id,
        "target_day_utc": day_utc,
        "preview": _preview_intents_payload(horizon),
        "recent_long_runs": [
            {
                "day_utc": item.day_utc,
                "duration_min": item.duration_min,
                "avg_if": item.avg_if,
                "tss": item.tss,
                "source": item.source,
            }
            for item in planning_state.recent_long_runs
        ],
        "preview_meta": preview_meta,
    }


def _explain_response(plan_payload: dict[str, Any], question: str | None = None) -> str:
    planning = dict(plan_payload.get("planning") or {})
    selected = dict(planning.get("selected_intent") or {})
    explanation = dict(planning.get("explanation") or {})
    lines = [
        f"Methodology: {planning.get('methodology_id') or explanation.get('methodology_id') or 'unknown'}",
        f"Cycle step: {selected.get('cycle_step_id') or explanation.get('cycle_step_id') or 'unknown'}",
        f"Selected day type: {selected.get('day_type') or explanation.get('next_day_type') or 'unknown'}",
        f"Sampled target: {round(float(selected.get('target_tss') or 0.0), 1)} TSS from share {round(float(selected.get('sampled_tss_share') or 0.0) * 100.0, 1)}%",
    ]
    if selected.get("hard_subtype"):
        lines.append(f"Hard subtype: {selected['hard_subtype']}")
    if explanation.get("weekend_adjustment"):
        lines.append(f"Weekend adjustment: {explanation['weekend_adjustment']}")
    if explanation.get("long_run_progression_reason"):
        lines.append(f"Long-run progression: {explanation['long_run_progression_reason']}")
    if explanation.get("candidate_rejections"):
        lines.append(f"Candidate rejections: {', '.join(explanation['candidate_rejections'])}")
    if question:
        lines.append(f"Question: {question}")
    return "\n".join(lines)


def tool_plan_next_day(arguments: dict[str, Any]) -> dict[str, Any]:
    planning_args = PlanningToolArgs.model_validate(arguments or {})
    backend_main = _backend_main_module()
    payload, _ = backend_main._planning_decision_for_owner(
        owner=planning_args.owner,
        day_utc=_coerce_day_utc(planning_args.target_day_utc),
        mode=str(planning_args.mode or "planned").strip().lower() or "planned",
        activity_type=str(planning_args.activity_type_preference or "").strip().lower() or None,
        previous_activity_text=str(planning_args.previous_activity_text or "").strip() or None,
        seed=planning_args.seed,
        methodology_id=str(planning_args.methodology_id or "").strip() or None,
        schedule_constraints=_coerce_constraints(arguments),
    )
    payload["guideline_context"] = _active_build_brief() or None
    return payload


def tool_preview_cycle(arguments: dict[str, Any]) -> dict[str, Any]:
    PreviewCycleArgs.model_validate(arguments or {})
    return _build_preview_payload(arguments)


def tool_explain_planning_decision(arguments: dict[str, Any]) -> dict[str, Any]:
    explain_args = ExplainPlanningArgs.model_validate(arguments or {})
    payload = tool_plan_next_day(arguments)
    return {
        "planning": payload.get("planning"),
        "answer": _explain_response(payload, str(explain_args.question or "").strip() or None),
    }


# ---------------------------------------------------------------------------
# Phase 1: Planning write tools
# ---------------------------------------------------------------------------


def tool_save_planned_activities(arguments: dict[str, Any]) -> dict[str, Any]:
    args = SavePlannedActivitiesArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    backend_main = _backend_main_module()
    entry_lines = [f"[{e.day_utc}]: {e.workout_text}" for e in args.entries]
    entry_text = "\n".join(entry_lines)
    result = backend_main._ingest_planned_entries_core(db_path, entry_text)
    result["owner"] = args.owner
    result["db_path"] = str(db_path)
    return result


def tool_update_planned_activity(arguments: dict[str, Any]) -> dict[str, Any]:
    args = UpdatePlannedActivityArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    backend_main = _backend_main_module()
    result = backend_main._update_planned_workout_core(
        db_path,
        day_utc=args.day_utc,
        line_no=args.line_no,
        workout_text=args.workout_text,
    )
    result["owner"] = args.owner
    result["db_path"] = str(db_path)
    return result


def tool_delete_planned_activities(arguments: dict[str, Any]) -> dict[str, Any]:
    args = DeletePlannedActivitiesArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    db = _db_helpers()
    keys = [(k.day_utc, k.line_no) for k in args.keys]
    deleted = db["delete_planned_activities"](db_path, keys)
    return {"owner": args.owner, "db_path": str(db_path), "deleted_count": int(deleted)}


def tool_mark_planned_done(arguments: dict[str, Any]) -> dict[str, Any]:
    args = MarkPlannedDoneArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    db = _db_helpers()
    success = db["set_planned_activity_manual_done"](db_path, args.day_utc, args.line_no, args.manual_done)
    return {"owner": args.owner, "db_path": str(db_path), "success": success}


# ---------------------------------------------------------------------------
# Phase 2: Custom activities, sync, and activity management tools
# ---------------------------------------------------------------------------


def tool_save_custom_activities(arguments: dict[str, Any]) -> dict[str, Any]:
    args = SaveCustomActivitiesArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    backend_main = _backend_main_module()
    entry_lines = [f"[{e.day_utc}]: {e.workout_text}" for e in args.entries]
    entry_text = "\n".join(entry_lines)
    result = backend_main._ingest_custom_entries_core(db_path, entry_text)
    result["owner"] = args.owner
    result["db_path"] = str(db_path)
    return result


def tool_delete_custom_activities(arguments: dict[str, Any]) -> dict[str, Any]:
    args = DeleteCustomActivitiesArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    db = _db_helpers()
    keys = [(k.day_utc, k.line_no) for k in args.keys]
    deleted = db["delete_custom_activities"](db_path, keys)
    return {"owner": args.owner, "db_path": str(db_path), "deleted_count": int(deleted)}


def tool_trigger_sync(arguments: dict[str, Any]) -> dict[str, Any]:
    args = TriggerSyncArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    backend_main = _backend_main_module()

    profile = args.profile if args.profile in ("quick", "deep") else "quick"
    days_back = max(7, min(int(args.days_back), 3650))

    rate_limit = backend_main._garmin_rate_limit_state(db_path)
    if rate_limit["active"]:
        return {
            "owner": args.owner,
            "status": "rate_limited",
            "message": f"Garmin sync paused after 429. Retry after {rate_limit['until_utc']}.",
            "rate_limited_until": rate_limit["until_utc"],
        }

    if not backend_main._AUTO_SYNC_LOCK.acquire(blocking=False):
        return {
            "owner": args.owner,
            "status": "already_running",
            "message": "Garmin sync already running. Try again shortly.",
        }

    try:
        ctx = backend_main._AuthContext(role="admin", username="admin")
        selection = backend_main._resolve_garmin_sync_source(ctx, args.owner, db_path)
        if selection["mode"] == "missing":
            return {
                "owner": args.owner,
                "status": "credentials_missing",
                "message": "Garmin credentials missing.",
            }

        if selection["mode"] == "oauth" and profile == "quick":
            sync_result = backend_main._run_quick_oauth_sync(
                db_path,
                days_back=days_back,
                source_label=f"mcp_sync_{profile}_oauth",
            )
        elif selection["mode"] == "oauth":
            from backend.app.garmin_oauth import (
                fetch_normalized_activities as fetch_garmin_oauth_normalized_activities,
                fetch_normalized_wellness as fetch_garmin_oauth_normalized_wellness,
            )

            token_payload, _connection = backend_main._garmin_oauth_token_payload(db_path)
            deep_start = (_utc_now() - timedelta(days=days_back)).date()
            access_token = str(token_payload.get("access_token") or "")
            activity_payload = fetch_garmin_oauth_normalized_activities(
                access_token,
                start_day=deep_start.isoformat(),
                end_day=_utc_now().date().isoformat(),
            )
            wellness_payload = fetch_garmin_oauth_normalized_wellness(
                access_token,
                start_day=deep_start.isoformat(),
                end_day=_utc_now().date().isoformat(),
            )
            persisted = backend_main._persist_normalized_garmin_payload(
                db_path,
                activity_payload=activity_payload,
                wellness_payload=wellness_payload,
            )
            sync_result = {
                "total_rows": len(persisted["activities"]),
                "details": {"garmin": {
                    "profile": "deep",
                    "activities": len(persisted["activities"]),
                    "wellness": len(persisted["wellness_daily"]),
                }},
            }
        else:
            sync_result = backend_main._run_quick_activity_sync(
                db_path,
                str(selection.get("email") or ""),
                str(selection.get("password") or ""),
                days_back=days_back,
                source_label=f"mcp_sync_{profile}",
                credentials_source=str(selection.get("credentials_source") or "session"),
            )
        return {
            "owner": args.owner,
            "status": "completed",
            "total_rows": int(sync_result.get("total_rows") or 0),
            "details": sync_result.get("details") or {},
        }
    except Exception as exc:
        return {
            "owner": args.owner,
            "status": "error",
            "message": str(exc),
        }
    finally:
        backend_main._AUTO_SYNC_LOCK.release()


def tool_get_sync_status(arguments: dict[str, Any]) -> dict[str, Any]:
    args = SyncStatusArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    db = _db_helpers()
    last_sync = db["get_last_sync"](db_path)
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "last_sync": last_sync,
    }


def tool_mark_activity_invalid(arguments: dict[str, Any]) -> dict[str, Any]:
    args = MarkActivityInvalidArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    db = _db_helpers()
    success = db["set_activity_invalid"](db_path, args.activity_id, args.is_invalid)
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "activity_id": args.activity_id,
        "is_invalid": args.is_invalid,
        "success": success,
    }


# ---------------------------------------------------------------------------
# Phase 3: Settings, workout search, and fitness form tools
# ---------------------------------------------------------------------------


def tool_get_settings(arguments: dict[str, Any]) -> dict[str, Any]:
    args = GetSettingsArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    backend_main = _backend_main_module()
    result = backend_main._settings_view_core(db_path)
    result["owner"] = args.owner
    return result


def tool_update_settings(arguments: dict[str, Any]) -> dict[str, Any]:
    args = UpdateSettingsArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    backend_main = _backend_main_module()
    settings_dict: dict[str, Any] = {}
    if args.lthr_curve is not None:
        settings_dict["lthr_curve"] = args.lthr_curve
    if args.lt_pace_curve is not None:
        settings_dict["lt_pace_curve"] = args.lt_pace_curve
    if args.timezone is not None:
        settings_dict["timezone"] = args.timezone
    if args.specificity_profile is not None:
        settings_dict["specificity_profile"] = args.specificity_profile
    if args.injury_windows is not None:
        settings_dict["injury_windows"] = args.injury_windows
    if args.if_zone_thresholds is not None:
        settings_dict["if_zone_thresholds"] = args.if_zone_thresholds
    if args.vdot_lookback_days is not None:
        settings_dict["vdot_lookback_days"] = args.vdot_lookback_days
    result = backend_main._settings_update_core(db_path, settings_dict)
    result["owner"] = args.owner
    result["db_path"] = str(db_path)
    return result


def tool_search_workouts(arguments: dict[str, Any]) -> dict[str, Any]:
    args = SearchWorkoutsArgs.model_validate(arguments or {})
    all_templates = _scan_workout_templates()
    matches: list[dict[str, Any]] = []
    for _tid, tmpl in all_templates.items():
        fm = tmpl.front_matter
        if args.category and fm.get("category") != args.category:
            continue
        if args.load_role and fm.get("load_role") != args.load_role:
            continue
        if args.session_family and tmpl.session_family != args.session_family:
            continue
        if args.stress_class and fm.get("stress_class") != args.stress_class:
            continue
        if args.modality_pattern and fm.get("modality_pattern") != args.modality_pattern:
            continue
        if args.planning_intent and args.planning_intent.lower() not in str(fm.get("planning_intent") or "").lower():
            continue
        if args.phase_fit:
            phase_fit_list = fm.get("phase_fit") or []
            if isinstance(phase_fit_list, list) and args.phase_fit not in phase_fit_list:
                continue
            elif isinstance(phase_fit_list, str) and args.phase_fit != phase_fit_list:
                continue
        baseline_tss = _safe_float(fm.get("baseline_estimated_tss"))
        if args.tss_min is not None and baseline_tss < args.tss_min:
            continue
        if args.tss_max is not None and baseline_tss > args.tss_max:
            continue
        matches.append(_template_summary(tmpl))
    return {
        "count": len(matches),
        "filters": {k: v for k, v in arguments.items() if v is not None},
        "templates": matches,
    }


def tool_get_fitness_form(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the full daily fitness model time series.

    Delegates to _build_athlete_progression_payload so the metrics here are
    identical to those shown on the Athlete Progression dashboard, including
    rTSS/specificity-aware overreach and injury_risk.

    Field glossary (per daily point):
      fitness    — 42-day TSS EMA (≈ CTL); aliased as ctl
      fatigue    — 7-day TSS EMA (≈ ATL); aliased as atl
      form       — fitness − fatigue (≈ TSB); aliased as tsb
      acwr       — fatigue / fitness
      overreach  — excess 10-day TSS load above daily target
      injury_risk— excess 10-day rTSS above daily target (running-specific)
      durability — 100-day rTSS EMA (long-term running robustness)
      pounding   — 7-day rTSS EMA (acute running mechanical load)
    """
    _require_pandas()
    args = FitnessFormArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    days = max(args.days, 14)

    progression = _analytics_helpers()["_build_athlete_progression_payload"](
        db_path=db_path,
        days=days,
        activity_filter="all",
        aggregation="daily",
        owner=args.owner,
    )

    points = progression.get("points") or []
    if not points:
        return {
            "owner": args.owner,
            "db_path": str(db_path),
            "days": days,
            "_note": (
                "fitness\u2248CTL (42-day TSS EMA), fatigue\u2248ATL (7-day TSS EMA); "
                "overreach and injury_risk measure excess load above daily target"
            ),
            "summary": {},
            "daily": [],
        }

    daily_out: list[dict[str, Any]] = []
    peak_fitness = 0.0
    for pt in points:
        fitness = _safe_float(pt.get("fitness"))
        fatigue = _safe_float(pt.get("fatigue"))
        form = round(fitness - fatigue, 1)
        acwr = round(fatigue / fitness, 2) if fitness > 0 else None
        peak_fitness = max(peak_fitness, fitness)
        daily_out.append(_clean_mapping({
            "day": str(pt.get("period_start") or ""),
            "tss": round(_safe_float(pt.get("tss")), 1),
            "rtss": round(_safe_float(pt.get("rtss")), 1),
            "duration_h": round(_safe_float(pt.get("duration_h")), 2),
            "distance_km": round(_safe_float(pt.get("distance_km")), 2),
            "distance_eqv_km": round(_safe_float(pt.get("distance_eqv_km")), 2),
            "target_tss": round(_safe_float(pt.get("target_tss")), 1),
            "fitness": round(fitness, 1),
            "fatigue": round(fatigue, 1),
            "form": form,
            "acwr": acwr,
            "overreach": round(_safe_float(pt.get("overreach")), 1),
            "injury_risk": round(_safe_float(pt.get("injury_risk")), 1),
            "durability": round(_safe_float(pt.get("durability")), 1),
            "pounding": round(_safe_float(pt.get("pounding")), 1),
            # backward-compat aliases
            "ctl": round(fitness, 1),
            "atl": round(fatigue, 1),
            "tsb": form,
        }))

    current = daily_out[-1] if daily_out else {}
    current_fitness = _safe_float(current.get("fitness"))
    current_fatigue = _safe_float(current.get("fatigue"))
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "days": days,
        "_note": (
            "fitness\u2248CTL (42-day TSS EMA), fatigue\u2248ATL (7-day TSS EMA); "
            "overreach and injury_risk measure excess load above daily target"
        ),
        "summary": _clean_mapping({
            "current_fitness": round(current_fitness, 1),
            "current_fatigue": round(current_fatigue, 1),
            "current_form": current.get("form"),
            "current_acwr": round(current_fatigue / current_fitness, 2) if current_fitness > 0 else None,
            "current_overreach": current.get("overreach"),
            "current_injury_risk": current.get("injury_risk"),
            "current_durability": current.get("durability"),
            "current_pounding": current.get("pounding"),
            "peak_fitness": round(peak_fitness, 1),
            "total_days": len(daily_out),
            # backward-compat aliases
            "current_ctl": round(current_fitness, 1),
            "current_atl": round(current_fatigue, 1),
            "current_tsb": current.get("form"),
        }),
        "daily": daily_out,
    }


def tool_get_weekly_volume(arguments: dict[str, Any]) -> dict[str, Any]:
    _require_pandas()
    args = WeeklyVolumeArgs.model_validate(arguments or {})
    weeks = max(1, min(int(args.weeks), 52))
    days_needed = weeks * 7 + 7
    db_path, metrics_df = _recent_metrics_df(args.owner, sport=args.sport, days=days_needed)
    if metrics_df.empty:
        return {
            "owner": args.owner,
            "db_path": str(db_path),
            "weeks": weeks,
            "weekly": [],
        }

    daily = metrics_df.copy()
    daily["day"] = pd.to_datetime(
        daily.get("start_time_utc"), utc=True, errors="coerce"
    ).dt.tz_convert(None).dt.normalize()
    daily = daily.dropna(subset=["day"]).copy()
    daily["week"] = daily["day"].dt.to_period("W-SUN")

    sport_col = daily.get("sport_type")
    if sport_col is not None:
        sport_lower = sport_col.astype(str).str.strip().str.lower()
        daily["is_running"] = sport_lower.isin(["running", "treadmill_running", "trail_running"])
        daily["modality"] = sport_lower.where(~daily["is_running"], "running")
    else:
        daily["is_running"] = False
        daily["modality"] = "unknown"

    grouped = daily.groupby("week", as_index=False).agg(
        total_distance_km=("distance_m", lambda x: round(x.sum() / 1000.0, 2)),
        total_duration_min=("duration_s", lambda x: round(x.sum() / 60.0, 1)),
        total_tss=("tss", "sum"),
        total_rtss=("rtss", "sum"),
        activity_count=("activity_id", "count"),
        run_count=("is_running", "sum"),
    )
    grouped = grouped.sort_values("week", ascending=False).head(weeks)

    weekly_rows: list[dict[str, Any]] = []
    for _, row in grouped.iterrows():
        period = row["week"]
        week_data = daily[daily["week"] == period]
        total_dur = _safe_float(week_data["duration_s"].sum())
        modality_dur: dict[str, float] = {}
        for mod, group in week_data.groupby("modality"):
            mod_dur = _safe_float(group["duration_s"].sum())
            if mod_dur > 0:
                modality_dur[str(mod)] = round(mod_dur / total_dur, 2) if total_dur > 0 else 0.0
        weekly_rows.append(_clean_mapping({
            "week_start": period.start_time.date().isoformat(),
            "week_end": period.end_time.date().isoformat(),
            "total_distance_km": round(_safe_float(row["total_distance_km"]), 2),
            "total_duration_min": round(_safe_float(row["total_duration_min"]), 1),
            "total_tss": round(_safe_float(row["total_tss"]), 1),
            "total_rtss": round(_safe_float(row["total_rtss"]), 1),
            "activity_count": int(_safe_float(row["activity_count"])),
            "run_count": int(_safe_float(row["run_count"])),
            "avg_daily_tss": round(_safe_float(row["total_tss"]) / 7.0, 1),
            "modality_split": modality_dur if modality_dur else None,
        }))
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "weeks": len(weekly_rows),
        "weekly": weekly_rows,
    }


def tool_get_coaching_brief(arguments: dict[str, Any]) -> dict[str, Any]:
    args = CoachingBriefArgs.model_validate(arguments or {})
    db_path, metrics_df = _recent_metrics_df(args.owner, days=90)
    analytics = _analytics_helpers()
    db = _db_helpers()
    today_str = _utc_now().date().isoformat()

    fitness_form = _compute_fitness_metrics(db_path, args.owner) if pd is not None else {}

    wellness_payload = analytics["_build_wellness_payload"](
        db_path=db_path, days=14, aggregation="daily", owner=args.owner,
    )
    latest_w = _latest_wellness_point(wellness_payload)
    recovery_snapshot = _clean_mapping({
        "training_readiness": latest_w.get("training_readiness"),
        "sleep_score": latest_w.get("sleep_score"),
        "stress_avg": latest_w.get("stress_avg"),
        "body_battery_end": latest_w.get("body_battery_end"),
        "resting_hr": latest_w.get("resting_hr"),
        "hrv_status": latest_w.get("hrv_status"),
    }) if latest_w else {}

    guideline_ctx = _active_build_brief()

    week_outlook = analytics["_build_week_outlook_payload"](
        db_path=db_path, days=120, start_day=None, end_day=None,
        sport=None, metric="tss", compare="planned", week_start=None,
    )
    week_progress = _clean_mapping({
        "goal": round(_safe_float(week_outlook.get("goal")), 1),
        "wtd_current": round(_safe_float(week_outlook.get("wtd_current")), 1),
        "remaining_to_go": round(_safe_float(week_outlook.get("remaining_to_go")), 1),
        "remaining_days": _remaining_days_in_week(week_outlook),
    })

    recent_pattern: list[dict[str, Any]] = []
    if not metrics_df.empty:
        weekly_baseline = _weekly_baseline_tss_for_day(db_path, today_str)
        recent_7 = metrics_df.head(14)
        day_seen: set[str] = set()
        for _, row in recent_7.iterrows():
            ts = _normalize_timestamp(row.get("start_time_utc"))
            if ts is None:
                continue
            day_key = ts.date().isoformat()
            if day_key in day_seen:
                continue
            day_seen.add(day_key)
            sport = str(row.get("sport_type") or "").strip().lower()
            modality = "running" if sport in ("running", "treadmill_running", "trail_running") else sport
            dur_min = _format_duration_minutes(row.get("duration_s"))
            avg_if = _safe_float(row.get("if_proxy"))
            stress_class, _, _ = classify_session_stress(
                estimated_tss=_safe_float(row.get("tss")),
                avg_if=avg_if, max_if=avg_if,
                total_minutes=dur_min, modality=modality,
                weekly_baseline_tss=weekly_baseline,
            )
            recent_pattern.append({"day": day_key, "stress_class": stress_class.value})
            if len(recent_pattern) >= 7:
                break

    flags: list[str] = []
    acwr_val = _safe_float(fitness_form.get("acwr"))
    if acwr_val > 1.5:
        flags.append("high_acwr")
    elif acwr_val > 1.3:
        flags.append("elevated_acwr")
    overreach_val = _safe_float(fitness_form.get("overreach"))
    if overreach_val > 10:
        flags.append("overreaching")
    injury_risk_val = _safe_float(fitness_form.get("injury_risk"))
    if injury_risk_val > 10:
        flags.append("elevated_injury_risk")
    if latest_w.get("training_readiness") is not None and _safe_float(latest_w["training_readiness"]) < 40:
        flags.append("low_training_readiness")
    sleep_score = latest_w.get("sleep_score")
    if sleep_score is not None and _safe_float(sleep_score) < 60:
        flags.append("poor_sleep")

    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "generated_at_utc": _utc_now().isoformat(),
        "fitness_form": fitness_form or None,
        "recovery_snapshot": recovery_snapshot or None,
        "active_build_summary": guideline_ctx or None,
        "week_progress": week_progress or None,
        "recent_pattern": recent_pattern or None,
        "flags": flags or None,
        "guideline_refs": [
            _resource_uri("guidelines/read-order"),
            _resource_uri("guidelines/active-build"),
            _resource_uri("workouts/overview"),
        ],
        "last_sync": db["get_last_sync"](db_path),
    }


# ---------------------------------------------------------------------------
# Phase 4: Load analysis and estimation tools
# ---------------------------------------------------------------------------


def _modality_from_workout_text(text: str) -> str:
    """Infer primary modality from workout text prefix for stress classification."""
    t = str(text or "").strip().lower()
    if t.startswith("elliptical") or " elliptical" in t[:30]:
        return "elliptical"
    if t.startswith("cycl") or t.startswith("bike") or " cycling" in t[:30] or " bike" in t[:30]:
        return "cycling"
    if t.startswith("treadmill"):
        return "treadmill"
    if t.startswith("swim"):
        return "swim"
    return "running"


def _build_metrics_df_for_entries(
    entries: list[dict[str, Any]],
    db_path: Path,
) -> Any:
    """Build a TSS metrics DataFrame for a list of {day_utc, workout_text} dicts."""
    backend_main = _backend_main_module()
    today_str = _utc_now().date().isoformat()
    rows = [
        {
            "day_utc": str(e.get("day_utc") or today_str),
            "workout_text": str(e.get("workout_text") or ""),
            "parsed_json": None,
        }
        for e in entries
    ]
    planned_df = backend_main.pd.DataFrame(rows)
    lthr_curve = backend_main._load_curve_points(
        db_path=db_path,
        key=backend_main.SETTINGS_KEY_LTHR_CURVE,
        value_key="lthr_bpm",
        fallback_value=backend_main.DEFAULT_LTHR,
    )
    pace_curve = backend_main._load_curve_points(
        db_path=db_path,
        key=backend_main.SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=backend_main.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    specificity_profile = backend_main._load_specificity_profile(db_path=db_path, fallback_default=0.8)
    return backend_main._compute_planned_rows_metrics_df(
        planned_rows=planned_df,
        lthr_curve_points=lthr_curve,
        lthr_default_bpm=float(lthr_curve[-1][1]) if lthr_curve else backend_main.DEFAULT_LTHR,
        lt_pace_curve_points=pace_curve,
        lt_pace_default_sec=float(pace_curve[-1][1]) if pace_curve else backend_main.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
        specificity_profile=specificity_profile,
    )


def _day_summaries_from_entries(
    entries: list[dict[str, str]],
    metrics_df: Any,
    weekly_baseline_tss: float = 350.0,
) -> list[dict[str, Any]]:
    """Aggregate entry-level metrics to day-level summaries with stress classification."""
    day_map: dict[str, dict[str, Any]] = {}
    for idx, e in enumerate(entries):
        day_utc = str(e["day_utc"])
        workout_text = str(e["workout_text"])
        if idx < len(metrics_df):
            row = metrics_df.iloc[idx]
            tss = float(row.get("tss") or 0.0)
            rtss = float(row.get("rtss") or 0.0)
            dur_s = float(row.get("duration_s") or 0.0)
            if_proxy = float(row.get("if_proxy") or 0.0)
        else:
            tss = rtss = dur_s = if_proxy = 0.0
        if day_utc not in day_map:
            day_map[day_utc] = {
                "day_utc": day_utc,
                "total_tss": 0.0,
                "total_rtss": 0.0,
                "total_duration_s": 0.0,
                "max_if": 0.0,
                "sum_if_dur": 0.0,
                "activities": 0,
                "first_workout_text": workout_text,
            }
        d = day_map[day_utc]
        d["total_tss"] += tss
        d["total_rtss"] += rtss
        d["total_duration_s"] += dur_s
        if dur_s > 0:
            d["sum_if_dur"] += if_proxy * dur_s
        d["max_if"] = max(d["max_if"], if_proxy)
        d["activities"] += 1

    summaries = []
    for day_utc in sorted(day_map):
        d = day_map[day_utc]
        dur_s = d["total_duration_s"]
        avg_if = d["sum_if_dur"] / dur_s if dur_s > 0 else 0.0
        max_if_val = d["max_if"]
        dur_min = dur_s / 60.0
        modality = _modality_from_workout_text(d["first_workout_text"])
        stress_class, _, _ = classify_session_stress(
            estimated_tss=d["total_tss"],
            avg_if=avg_if,
            max_if=max_if_val,
            total_minutes=dur_min,
            modality=modality,
            weekly_baseline_tss=weekly_baseline_tss,
        )
        is_long = is_long_run_candidate(
            modality=modality,
            total_minutes=dur_min,
            avg_if=avg_if,
            max_if=max_if_val,
        )
        summaries.append({
            "day_utc": day_utc,
            "total_tss": round(d["total_tss"], 1),
            "total_rtss": round(d["total_rtss"], 1),
            "duration_min": round(dur_min, 1),
            "stress_class": stress_class.value,
            "is_long_run": is_long,
            "activities": d["activities"],
        })
    return summaries


def _scan_density_warnings(
    day_summaries: list[dict[str, Any]],
    three_day_threshold: float,
) -> list[dict[str, Any]]:
    """Scan sorted day summaries for stress-class and TSS-cluster density warnings."""
    warnings: list[dict[str, Any]] = []
    days_sorted = sorted(day_summaries, key=lambda d: d["day_utc"])
    n = len(days_sorted)
    if n == 0:
        return warnings

    # --- Tier A: stress-class pattern checks ---
    streak: int = 0
    streak_days: list[str] = []
    for i, day in enumerate(days_sorted):
        sc = day.get("stress_class", "easy")
        is_loading = sc in ("moderate", "hard")
        is_long = day.get("is_long_run", False)

        if is_loading:
            streak += 1
            streak_days.append(day["day_utc"])
        else:
            if streak >= 3:
                tag = "consecutive_loading_streak_4" if streak >= 4 else "consecutive_loading_streak_3"
                warnings.append({
                    "tag": tag,
                    "days": streak_days[:],
                    "message": f"{streak} consecutive moderate/hard days with no rest or easy gap",
                })
            streak = 0
            streak_days = []

        if sc == "hard" and i > 0 and days_sorted[i - 1].get("stress_class") == "hard":
            warnings.append({
                "tag": "back_to_back_hard",
                "days": [days_sorted[i - 1]["day_utc"], day["day_utc"]],
                "message": "Two consecutive hard days with no recovery gap",
            })

        if is_long and i > 0 and days_sorted[i - 1].get("stress_class") == "hard":
            warnings.append({
                "tag": "pre_long_run_heavy",
                "days": [days_sorted[i - 1]["day_utc"], day["day_utc"]],
                "message": "Hard session the day before a long run — insufficient recovery going in",
            })

    # flush trailing streak
    if streak >= 3:
        tag = "consecutive_loading_streak_4" if streak >= 4 else "consecutive_loading_streak_3"
        warnings.append({
            "tag": tag,
            "days": streak_days[:],
            "message": f"{streak} consecutive moderate/hard days with no rest or easy gap",
        })

    # long run spacing
    long_run_days = [d["day_utc"] for d in days_sorted if d.get("is_long_run")]
    for i in range(1, len(long_run_days)):
        gap = (date.fromisoformat(long_run_days[i]) - date.fromisoformat(long_run_days[i - 1])).days
        if gap < 6:
            warnings.append({
                "tag": "long_run_spacing_tight",
                "days": [long_run_days[i - 1], long_run_days[i]],
                "gap_days": gap,
                "message": f"Long runs only {gap} days apart (minimum 6 recommended)",
            })

    # --- Tier B: rolling 3-day TSS cluster density ---
    window_tss_vals: list[float] = []
    for i in range(max(0, n - 2)):
        w = days_sorted[i:i + 3]
        window_tss_vals.append(sum(d.get("total_tss", 0.0) for d in w))

    for i, w_tss in enumerate(window_tss_vals):
        if w_tss > three_day_threshold:
            pct = round((w_tss / three_day_threshold - 1.0) * 100)
            warnings.append({
                "tag": "tss_cluster_spike",
                "days": [d["day_utc"] for d in days_sorted[i:i + 3]],
                "window_tss": round(w_tss, 1),
                "threshold": round(three_day_threshold, 1),
                "message": f"3-day TSS of {w_tss:.1f} is {pct}% above the {three_day_threshold:.1f} density threshold",
            })

    # runaway: contiguous runs of 2+ over-threshold windows
    over_flags = [v > three_day_threshold for v in window_tss_vals] + [False]
    run_start: int | None = None
    for i, over in enumerate(over_flags):
        if over and run_start is None:
            run_start = i
        elif not over and run_start is not None:
            run_len = i - run_start
            if run_len >= 2:
                span_end = min(run_start + run_len + 2, n)
                warnings.append({
                    "tag": "tss_cluster_runaway",
                    "days": [d["day_utc"] for d in days_sorted[run_start:span_end]],
                    "message": (
                        f"Sustained overload: {run_len + 1} consecutive 3-day windows "
                        f"all exceed the {three_day_threshold:.1f} density threshold"
                    ),
                })
            run_start = None

    return warnings


def tool_estimate_workout_tss(arguments: dict[str, Any]) -> dict[str, Any]:
    args = EstimateWorkoutTSSArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    today_str = _utc_now().date().isoformat()
    raw_entries = [
        {"day_utc": e.day_utc or today_str, "workout_text": e.workout_text}
        for e in args.entries
    ]
    if not raw_entries:
        return {"owner": args.owner, "results": []}
    metrics_df = _build_metrics_df_for_entries(raw_entries, db_path)
    results = []
    for idx, e in enumerate(raw_entries):
        if idx < len(metrics_df):
            row = metrics_df.iloc[idx]
            dur_s = float(row.get("duration_s") or 0.0)
            results.append({
                "workout_text": e["workout_text"],
                "day_utc": e["day_utc"],
                "tss": round(float(row.get("tss") or 0.0), 1),
                "rtss": round(float(row.get("rtss") or 0.0), 1),
                "distance_proxy_km": round(float(row.get("distance_proxy_km") or 0.0), 2),
                "duration_min": round(dur_s / 60.0, 1),
                "if_proxy": round(float(row.get("if_proxy") or 0.0), 3),
                "avg_hr_bpm": round(float(row.get("avg_hr_bpm") or 0.0), 1),
                "pace_proxy_sec_per_km": round(float(row.get("pace_proxy_sec_per_km") or 0.0), 1),
            })
        else:
            results.append({
                "workout_text": e["workout_text"],
                "day_utc": e["day_utc"],
                "tss": 0.0, "rtss": 0.0, "distance_proxy_km": 0.0,
                "duration_min": 0.0, "if_proxy": 0.0, "avg_hr_bpm": 0.0,
                "pace_proxy_sec_per_km": 0.0,
            })
    return {"owner": args.owner, "results": results}


def tool_simulate_plan_week(arguments: dict[str, Any]) -> dict[str, Any]:
    args = SimulatePlanWeekArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    if not args.entries:
        return {
            "owner": args.owner,
            "weekly_tss": 0.0, "weekly_rtss": 0.0,
            "weekly_distance_proxy_km": 0.0, "run_share": 0.0,
            "daily_breakdown": [], "warnings": [],
        }
    today_str = _utc_now().date().isoformat()
    raw_entries = [{"day_utc": e.day_utc, "workout_text": e.workout_text} for e in args.entries]
    metrics_df = _build_metrics_df_for_entries(raw_entries, db_path)
    weekly_baseline = _weekly_baseline_tss_for_day(db_path, today_str)

    # Compute run share from entry-level durations
    total_dur_s = 0.0
    running_dur_s = 0.0
    weekly_tss = 0.0
    weekly_rtss = 0.0
    weekly_dist = 0.0
    for idx, e in enumerate(raw_entries):
        modality = _modality_from_workout_text(e["workout_text"])
        dur_s = float(metrics_df.iloc[idx].get("duration_s") or 0.0) if idx < len(metrics_df) else 0.0
        total_dur_s += dur_s
        if modality in ("running", "treadmill"):
            running_dur_s += dur_s
        if idx < len(metrics_df):
            row = metrics_df.iloc[idx]
            weekly_tss += float(row.get("tss") or 0.0)
            weekly_rtss += float(row.get("rtss") or 0.0)
            weekly_dist += float(row.get("distance_proxy_km") or 0.0)

    run_share = running_dur_s / total_dur_s if total_dur_s > 0 else 0.0
    three_day_threshold = weekly_baseline / 7.0 * 3.0 * 1.5

    day_summaries = _day_summaries_from_entries(raw_entries, metrics_df, weekly_baseline)
    warnings = _scan_density_warnings(day_summaries, three_day_threshold)

    daily_breakdown = [
        {
            "day_utc": d["day_utc"],
            "tss": d["total_tss"],
            "rtss": d["total_rtss"],
            "duration_min": d["duration_min"],
            "stress_class": d["stress_class"],
            "is_long_run": d["is_long_run"],
        }
        for d in day_summaries
    ]
    return {
        "owner": args.owner,
        "weekly_tss": round(weekly_tss, 1),
        "weekly_rtss": round(weekly_rtss, 1),
        "weekly_distance_proxy_km": round(weekly_dist, 2),
        "run_share": round(run_share, 3),
        "weekly_baseline_tss_ref": round(weekly_baseline, 1),
        "three_day_density_threshold": round(three_day_threshold, 1),
        "daily_breakdown": daily_breakdown,
        "warnings": warnings,
    }


def tool_critique_day_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    args = CritiqueDayPlanArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    backend_main = _backend_main_module()
    today = _utc_now().date()

    # Default range: current week start to two weeks out
    start_day = date.fromisoformat(args.start_day_utc) if args.start_day_utc else today - timedelta(days=today.weekday())
    end_day = date.fromisoformat(args.end_day_utc) if args.end_day_utc else start_day + timedelta(days=13)

    # Fetch existing planned activities
    try:
        planned_df = backend_main.get_planned_activities_df(
            db_path=db_path,
            start_day_utc=start_day.isoformat(),
            end_day_utc=end_day.isoformat(),
        )
    except Exception:
        planned_df = backend_main.pd.DataFrame(columns=["day_utc", "workout_text"])

    raw_entries: list[dict[str, str]] = []
    if not planned_df.empty and "workout_text" in planned_df.columns:
        for _, row in planned_df.iterrows():
            day_val = str(row.get("day_utc") or "")
            text_val = str(row.get("workout_text") or "")
            if day_val and text_val:
                raw_entries.append({"day_utc": day_val, "workout_text": text_val})

    # Merge extra_entries (append, do not replace)
    if args.extra_entries:
        for e in args.extra_entries:
            raw_entries.append({"day_utc": e.day_utc, "workout_text": e.workout_text})

    today_str = today.isoformat()
    weekly_baseline = _weekly_baseline_tss_for_day(db_path, today_str)
    three_day_threshold = weekly_baseline / 7.0 * 3.0 * 1.5

    if not raw_entries:
        return {
            "owner": args.owner,
            "period": {"start": start_day.isoformat(), "end": end_day.isoformat()},
            "weekly_baseline_tss_ref": round(weekly_baseline, 1),
            "three_day_density_threshold": round(three_day_threshold, 1),
            "day_summary": [],
            "warnings": [],
        }

    metrics_df = _build_metrics_df_for_entries(raw_entries, db_path)
    day_summaries = _day_summaries_from_entries(raw_entries, metrics_df, weekly_baseline)

    # Additional critique checks (weekday long run, heavy Monday after long Sunday)
    days_sorted = sorted(day_summaries, key=lambda d: d["day_utc"])
    extra_warnings: list[dict[str, Any]] = []
    for i, day in enumerate(days_sorted):
        if day.get("is_long_run"):
            try:
                dow = date.fromisoformat(day["day_utc"]).weekday()  # 0=Mon, 6=Sun
                if dow <= 3:  # Mon–Thu
                    extra_warnings.append({
                        "tag": "long_run_on_weekday",
                        "days": [day["day_utc"]],
                        "message": "Long run placed on a weekday (Mon–Thu) — weekend placement preferred for recovery",
                    })
            except ValueError:
                pass
        if i > 0:
            prev = days_sorted[i - 1]
            try:
                curr_dow = date.fromisoformat(day["day_utc"]).weekday()
                prev_dow = date.fromisoformat(prev["day_utc"]).weekday()
                if curr_dow == 0 and prev_dow == 6 and prev.get("is_long_run") and day.get("stress_class") == "hard":
                    extra_warnings.append({
                        "tag": "heavy_monday_after_long_sunday",
                        "days": [prev["day_utc"], day["day_utc"]],
                        "message": "Hard Monday immediately after a long Sunday — recovery window is too short",
                    })
            except ValueError:
                pass

    warnings = _scan_density_warnings(day_summaries, three_day_threshold) + extra_warnings
    return {
        "owner": args.owner,
        "period": {"start": start_day.isoformat(), "end": end_day.isoformat()},
        "weekly_baseline_tss_ref": round(weekly_baseline, 1),
        "three_day_density_threshold": round(three_day_threshold, 1),
        "day_summary": day_summaries,
        "warnings": warnings,
    }


def tool_estimate_xtrain_tss(arguments: dict[str, Any]) -> dict[str, Any]:
    args = EstimateXtrainTSSArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    today_str = _utc_now().date().isoformat()
    target_day = args.target_day_utc or today_str
    backend_main = _backend_main_module()

    lthr_bpm = _lthr_for_day(db_path, target_day)
    lt_pace = _lt_pace_for_day(db_path, target_day)
    specificity_profile = backend_main._load_specificity_profile(db_path=db_path, fallback_default=0.8)
    specificity_factor = backend_main._specificity_factor_for_plan_kind(args.activity_kind, specificity_profile)

    duration_s = args.duration_min * 60.0
    if lthr_bpm <= 0 or args.avg_hr_bpm <= 0 or duration_s <= 0:
        return {
            "owner": args.owner, "activity_kind": args.activity_kind,
            "error": "Invalid inputs: lthr, avg_hr_bpm, and duration_min must all be positive",
        }

    if_proxy = args.avg_hr_bpm / lthr_bpm
    tss = (duration_s * (if_proxy ** 2) / 3600.0) * 100.0
    effective_rtss = tss * specificity_factor

    # Solve running-equivalent distance proxy (mirrors compute_distance_proxy in tss.py)
    distance_proxy_km: float | None = None
    pace_proxy_sec_per_km: float | None = None
    if effective_rtss > 0 and lt_pace > 0:
        denom = (effective_rtss * 3600.0) / (duration_s * 100.0)
        if denom > 0:
            solved_pace = lt_pace / (denom ** 0.5)
            min_pace = max(90.0, lt_pace / 2.0)
            max_pace = min(1800.0, lt_pace * 6.0)
            if min_pace <= solved_pace <= max_pace and solved_pace > 0:
                distance_proxy_km = round(duration_s / solved_pace, 2)
                pace_proxy_sec_per_km = round(solved_pace, 1)

    # Build human-readable explanation
    pace_str = ""
    if pace_proxy_sec_per_km:
        mins = int(pace_proxy_sec_per_km) // 60
        secs = int(pace_proxy_sec_per_km) % 60
        pace_str = f", equivalent to ~{distance_proxy_km} km at {mins}:{secs:02d}/km running pace"
    explanation = (
        f"TSS {tss:.1f} × {specificity_factor:.2f} specificity = {effective_rtss:.1f} effective rTSS{pace_str}"
    )

    return {
        "owner": args.owner,
        "activity_kind": args.activity_kind,
        "duration_min": args.duration_min,
        "avg_hr_bpm": args.avg_hr_bpm,
        "lthr_bpm": round(lthr_bpm, 1),
        "if_proxy": round(if_proxy, 3),
        "tss": round(tss, 1),
        "specificity_factor": specificity_factor,
        "effective_rtss": round(effective_rtss, 1),
        "distance_proxy_km": distance_proxy_km,
        "pace_proxy_sec_per_km": pace_proxy_sec_per_km,
        "explanation": explanation,
    }


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(name or "").strip()
    spec = TOOLS.get(tool_name)
    if spec is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    return spec.handler(args if isinstance(args, dict) else {})


TOOLS: dict[str, ToolSpec] = {
    # --- Read / planning suggestion tools ---
    "plan_next_day": ToolSpec(
        name="plan_next_day",
        description="Generate the next workout suggestion plus the full planning decision metadata.",
        input_schema=PlanningToolArgs.model_json_schema(),
        handler=tool_plan_next_day,
    ),
    "preview_cycle": ToolSpec(
        name="preview_cycle",
        description="Preview the next cycle horizon using the selected methodology and current athlete state.",
        input_schema=PreviewCycleArgs.model_json_schema(),
        handler=tool_preview_cycle,
    ),
    "explain_planning_decision": ToolSpec(
        name="explain_planning_decision",
        description="Explain why the planner chose the current intent, including long-run and weekend constraints.",
        input_schema=ExplainPlanningArgs.model_json_schema(),
        handler=tool_explain_planning_decision,
    ),
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
        description=(
            "Summarize recent load trend with daily TSS/rTSS and specificity-aware training metrics. "
            "Returns fitness (42-day TSS EMA \u2248CTL), fatigue (7-day TSS EMA \u2248ATL), form (fitness\u2212fatigue), "
            "ACWR, durability (100-day rTSS EMA), and pounding (7-day rTSS EMA). "
            "For overreach and injury_risk use get_fitness_form."
        ),
        input_schema=RecentActivitiesArgs.model_json_schema(),
        handler=tool_get_load_trend,
    ),
    "get_recovery_trend": ToolSpec(
        name="get_recovery_trend",
        description="Summarize recent wellness and recovery trend from Temperance daily recovery data.",
        input_schema=OwnerArgs.model_json_schema(),
        handler=tool_get_recovery_trend,
    ),
    "get_activity_detail": ToolSpec(
        name="get_activity_detail",
        description="Return the existing Temperance activity detail payload for a specific activity id.",
        input_schema=ActivityDetailArgs.model_json_schema(),
        handler=tool_get_activity_detail,
    ),
    "judge_training_history": ToolSpec(
        name="judge_training_history",
        description="Judge recent actual training history against the active build, doctrine, and current planning state.",
        input_schema=HistoryJudgmentArgs.model_json_schema(),
        handler=tool_judge_training_history,
    ),
    "explain_history_judgment": ToolSpec(
        name="explain_history_judgment",
        description="Explain the structured history judgment with evidence refs and optional question-specific focus.",
        input_schema=ExplainHistoryJudgmentArgs.model_json_schema(),
        handler=tool_explain_history_judgment,
    ),
    # --- Planning write tools ---
    "save_planned_activities": ToolSpec(
        name="save_planned_activities",
        description="Write one or more planned workouts to the database. Entries are parsed and validated using the standard activity text format.",
        input_schema=SavePlannedActivitiesArgs.model_json_schema(),
        handler=tool_save_planned_activities,
    ),
    "update_planned_activity": ToolSpec(
        name="update_planned_activity",
        description="Modify the workout text for an existing planned activity entry.",
        input_schema=UpdatePlannedActivityArgs.model_json_schema(),
        handler=tool_update_planned_activity,
    ),
    "delete_planned_activities": ToolSpec(
        name="delete_planned_activities",
        description="Remove one or more planned workouts by day_utc and line_no.",
        input_schema=DeletePlannedActivitiesArgs.model_json_schema(),
        handler=tool_delete_planned_activities,
    ),
    "mark_planned_done": ToolSpec(
        name="mark_planned_done",
        description="Toggle the manual_done flag on a planned activity (mark as completed or not).",
        input_schema=MarkPlannedDoneArgs.model_json_schema(),
        handler=tool_mark_planned_done,
    ),
    # --- Custom activities & sync tools ---
    "save_custom_activities": ToolSpec(
        name="save_custom_activities",
        description="Record one or more manual activities not captured by Garmin (e.g., gym sessions, manual entries).",
        input_schema=SaveCustomActivitiesArgs.model_json_schema(),
        handler=tool_save_custom_activities,
    ),
    "delete_custom_activities": ToolSpec(
        name="delete_custom_activities",
        description="Remove one or more custom activity entries by day_utc and line_no.",
        input_schema=DeleteCustomActivitiesArgs.model_json_schema(),
        handler=tool_delete_custom_activities,
    ),
    "trigger_sync": ToolSpec(
        name="trigger_sync",
        description="Trigger a Garmin data sync to refresh activities and wellness data.",
        input_schema=TriggerSyncArgs.model_json_schema(),
        handler=tool_trigger_sync,
    ),
    "get_sync_status": ToolSpec(
        name="get_sync_status",
        description="Check the last Garmin sync time and result.",
        input_schema=SyncStatusArgs.model_json_schema(),
        handler=tool_get_sync_status,
    ),
    "mark_activity_invalid": ToolSpec(
        name="mark_activity_invalid",
        description="Flag an activity as invalid (e.g., GPS glitch, bad data) or restore it.",
        input_schema=MarkActivityInvalidArgs.model_json_schema(),
        handler=tool_mark_activity_invalid,
    ),
    # --- Settings & analytics tools ---
    "get_settings": ToolSpec(
        name="get_settings",
        description="View athlete configuration: LTHR curve, threshold pace curve, timezone, specificity profile, injury windows, and IF zone thresholds.",
        input_schema=GetSettingsArgs.model_json_schema(),
        handler=tool_get_settings,
    ),
    "update_settings": ToolSpec(
        name="update_settings",
        description="Modify athlete configuration. Partial update: only provided fields change. Supports lthr_curve, lt_pace_curve, timezone, specificity_profile, injury_windows, if_zone_thresholds, vdot_lookback_days.",
        input_schema=UpdateSettingsArgs.model_json_schema(),
        handler=tool_update_settings,
    ),
    "search_workouts": ToolSpec(
        name="search_workouts",
        description="Search and filter the workout template catalog by category, load_role, session_family, stress_class, phase_fit, modality_pattern, planning_intent, and/or TSS range.",
        input_schema=SearchWorkoutsArgs.model_json_schema(),
        handler=tool_search_workouts,
    ),
    "get_fitness_form": ToolSpec(
        name="get_fitness_form",
        description=(
            "Full daily fitness model time series using the same rTSS/specificity-aware computation "
            "as the Athlete Progression dashboard. Returns per-day: fitness (42-day TSS EMA \u2248CTL), "
            "fatigue (7-day TSS EMA \u2248ATL), form (\u2248TSB), ACWR, overreach (excess 10-day TSS above "
            "daily target), injury_risk (excess 10-day rTSS above daily target, running-specific), "
            "durability (100-day rTSS EMA), and pounding (7-day rTSS EMA). "
            "ctl/atl/tsb fields are included as backward-compat aliases."
        ),
        input_schema=FitnessFormArgs.model_json_schema(),
        handler=tool_get_fitness_form,
    ),
    "get_weekly_volume": ToolSpec(
        name="get_weekly_volume",
        description=(
            "Return weekly volume summaries for the last N weeks: distance, duration, TSS, run count, "
            "modality split, and average daily TSS. Essential for volume management conversations."
        ),
        input_schema=WeeklyVolumeArgs.model_json_schema(),
        handler=tool_get_weekly_volume,
    ),
    "get_coaching_brief": ToolSpec(
        name="get_coaching_brief",
        description=(
            "Single-call coaching situational awareness. Returns current fitness metrics (fitness\u2248CTL, "
            "fatigue\u2248ATL, form\u2248TSB, ACWR, overreach, injury_risk, durability, pounding), "
            "recovery snapshot, active build context with guideline refs, week progress, recent 7-day stress "
            "pattern, and actionable flags (including overreaching and elevated_injury_risk). "
            "Start here for coaching conversations."
        ),
        input_schema=CoachingBriefArgs.model_json_schema(),
        handler=tool_get_coaching_brief,
    ),
    # --- Phase 4: Load analysis and estimation tools ---
    "estimate_workout_tss": ToolSpec(
        name="estimate_workout_tss",
        description=(
            "Parse one or more workout text strings and return predicted TSS, rTSS, distance proxy, IF, and duration. "
            "Does not save anything. Useful for evaluating planned sessions before committing them."
        ),
        input_schema=EstimateWorkoutTSSArgs.model_json_schema(),
        handler=tool_estimate_workout_tss,
    ),
    "simulate_plan_week": ToolSpec(
        name="simulate_plan_week",
        description=(
            "Given a list of dated planned entries, return projected weekly TSS, rTSS, distance, run share, "
            "and spacing/density warnings (back-to-back hard days, consecutive loading streaks, 3-day TSS cluster spikes)."
        ),
        input_schema=SimulatePlanWeekArgs.model_json_schema(),
        handler=tool_simulate_plan_week,
    ),
    "critique_day_plan": ToolSpec(
        name="critique_day_plan",
        description=(
            "Audit a range of existing planned days (optionally blended with extra proposed entries) for hidden density "
            "and spacing problems. Runs both stress-class pattern checks and rolling 3-day TSS cluster analysis. "
            "Detects patterns like Thu+Fri+Sat+Sun consecutive loading, long run spacing violations, and sustained overload."
        ),
        input_schema=CritiqueDayPlanArgs.model_json_schema(),
        handler=tool_critique_day_plan,
    ),
    "estimate_xtrain_tss": ToolSpec(
        name="estimate_xtrain_tss",
        description=(
            "Estimate TSS and effective rTSS for a cross-training session (elliptical, cycling, etc.) from HR. "
            "Returns raw TSS (HR-based), specificity factor, effective rTSS after applying the specificity ratio, "
            "and a running-equivalent distance/pace proxy."
        ),
        input_schema=EstimateXtrainTSSArgs.model_json_schema(),
        handler=tool_estimate_xtrain_tss,
    ),
}


SERVER_INFO = {
    "name": "temperance-mcp",
    "version": "0.4.0",
}


RESOURCES: dict[str, ResourceSpec] = {
    _resource_uri("guidelines/read-order"): ResourceSpec(
        uri=_resource_uri("guidelines/read-order"),
        name="Guidelines Read Order",
        description="Distilled machine-facing read order and precedence for the Temperance doctrine stack.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
        handler=_build_read_order_payload,
    ),
    _resource_uri("guidelines/core-bundle"): ResourceSpec(
        uri=_resource_uri("guidelines/core-bundle"),
        name="Guidelines Core Bundle",
        description="Governance, control doctrine, phase doctrine, and overlay contract as one MCP context bundle.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
        handler=_build_core_bundle_payload,
    ),
    _resource_uri("guidelines/active-build"): ResourceSpec(
        uri=_resource_uri("guidelines/active-build"),
        name="Guidelines Active Build",
        description="Resolved active build declaration plus selected athlete-state, event, and philosophy overlays.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
        handler=_build_active_build_payload,
    ),
    _resource_uri("workouts/overview"): ResourceSpec(
        uri=_resource_uri("workouts/overview"),
        name="Workout Overview",
        description="Workout README, quick reference, and taxonomy guidance in one overview resource.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
        handler=_build_workout_overview_payload,
    ),
    _resource_uri("workouts/catalog"): ResourceSpec(
        uri=_resource_uri("workouts/catalog"),
        name="Workout Catalog",
        description="Machine-friendly full workout catalog summary.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
        handler=_build_workout_catalog_payload,
    ),
}


RESOURCE_TEMPLATES: tuple[ResourceTemplateSpec, ...] = (
    ResourceTemplateSpec(
        uri_template=_resource_uri("guidelines/doc/{doc_id}"),
        name="Guideline Doc",
        description="Resolve a specific guideline doc id, preferring local overrides when available.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
    ),
    ResourceTemplateSpec(
        uri_template=_resource_uri("workouts/family/{session_family}"),
        name="Workout Family",
        description="Return metadata, chooser guidance, and template summaries for a workout family.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
    ),
    ResourceTemplateSpec(
        uri_template=_resource_uri("workouts/template/{template_id}"),
        name="Workout Template",
        description="Return a parsed workout template with front matter and body markdown.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
    ),
    ResourceTemplateSpec(
        uri_template=_resource_uri("planning/context/{owner}/{target_day_utc}"),
        name="Planning Context",
        description="Return resolved doctrine context plus live planning state for an owner and target day.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
    ),
    ResourceTemplateSpec(
        uri_template=_resource_uri("history/snapshot/{owner}/{window_days}"),
        name="History Snapshot",
        description="Return actual-first history structure and coverage summary for the requested owner and window.",
        mime_type=STATIC_RESOURCE_MIME_TYPE,
    ),
)


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
                "resources": {},
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


def _resource_result_content(uri: str, payload: Any) -> list[dict[str, Any]]:
    return [
        {
            "uri": uri,
            "mimeType": STATIC_RESOURCE_MIME_TYPE,
            "text": json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2),
        }
    ]


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
                "structuredContent": {"error": str(exc)},
                "isError": True,
            },
        )
    return _success_response(
        msg_id,
        {
            "content": _tool_result_content(payload),
            "structuredContent": payload,
            "isError": False,
        },
    )


def _handle_resources_list(msg_id: Any) -> dict[str, Any]:
    return _success_response(
        msg_id,
        {
            "resources": [
                {
                    "uri": spec.uri,
                    "name": spec.name,
                    "description": spec.description,
                    "mimeType": spec.mime_type,
                }
                for spec in RESOURCES.values()
            ]
        },
    )


def _handle_resource_templates_list(msg_id: Any) -> dict[str, Any]:
    return _success_response(
        msg_id,
        {
            "resourceTemplates": [
                {
                    "uriTemplate": spec.uri_template,
                    "name": spec.name,
                    "description": spec.description,
                    "mimeType": spec.mime_type,
                }
                for spec in RESOURCE_TEMPLATES
            ]
        },
    )


def _uri_path(uri: str) -> str:
    parsed = urlsplit(uri)
    if parsed.scheme != "temperance":
        raise ValueError(f"Unknown resource: {uri}")
    return unquote("/".join(part for part in [parsed.netloc, parsed.path.lstrip("/")] if part))


def _resource_payload_for_uri(uri: str) -> dict[str, Any]:
    normalized_uri = str(uri or "").strip()
    static_resource = RESOURCES.get(normalized_uri)
    if static_resource is not None:
        return static_resource.handler()
    path = _uri_path(normalized_uri)
    if path.startswith("guidelines/doc/"):
        return _build_guideline_doc_payload(path.split("/", 2)[2])
    if path.startswith("workouts/family/"):
        return _build_workout_family_payload(path.split("/", 2)[2])
    if path.startswith("workouts/template/"):
        return _build_workout_template_payload(path.split("/", 2)[2])
    if path.startswith("planning/context/"):
        parts = path.split("/")
        if len(parts) != 4:
            raise ValueError(f"Unknown resource: {uri}")
        _, _, owner, target_day_utc = parts
        return _build_planning_context_payload(owner, target_day_utc)
    if path.startswith("history/snapshot/"):
        parts = path.split("/")
        if len(parts) != 4:
            raise ValueError(f"Unknown resource: {uri}")
        _, _, owner, window_days = parts
        return _build_history_snapshot_payload(owner, int(window_days))
    raise ValueError(f"Unknown resource: {uri}")


def _handle_resources_read(msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    uri = str((params or {}).get("uri") or "").strip()
    if not uri:
        return _error_response(msg_id, -32602, "Missing resource uri.")
    try:
        payload = _resource_payload_for_uri(uri)
    except ValueError as exc:
        return _error_response(msg_id, -32002, str(exc))
    except Exception as exc:
        return _error_response(msg_id, -32000, str(exc))
    return _success_response(
        msg_id,
        {
            "contents": _resource_result_content(uri, payload),
        },
    )


def _dispatch_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = str(request.get("method") or "").strip()
    msg_id = request.get("id")
    params = request.get("params") or {}
    if method == "initialize":
        return _handle_initialize(msg_id)
    if method in {"initialized", "notifications/initialized"}:
        return None
    if method == "ping":
        return _success_response(msg_id, {})
    if method == "tools/list":
        return _handle_tools_list(msg_id)
    if method == "tools/call":
        return _handle_tools_call(msg_id, params)
    if method == "resources/list":
        return _handle_resources_list(msg_id)
    if method == "resources/templates/list":
        return _handle_resource_templates_list(msg_id)
    if method == "resources/read":
        return _handle_resources_read(msg_id, params)
    if msg_id is None:
        return None
    return _error_response(msg_id, -32601, f"Method not found: {method}")


class TemperanceMCPServer:
    server_name = SERVER_INFO["name"]
    protocol_version = SERVER_PROTOCOL_VERSION

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        return _dispatch_request(request)


def handle_message(message: dict[str, Any]) -> Optional[dict[str, Any]]:
    return _dispatch_request(message)


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

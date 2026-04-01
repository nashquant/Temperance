from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - helper-only import mode
    pd = None

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # pragma: no cover - lightweight helper-only fallback
    class BaseModel:
        def __init__(self, **kwargs: Any) -> None:
            annotations = self._model_annotations()
            for name in annotations:
                if name in kwargs:
                    value = kwargs[name]
                elif hasattr(self.__class__, name):
                    value = getattr(self.__class__, name)
                else:
                    value = None
                setattr(self, name, value)

        @classmethod
        def _model_annotations(cls) -> dict[str, Any]:
            annotations: dict[str, Any] = {}
            for base in reversed(cls.__mro__):
                annotations.update(getattr(base, "__annotations__", {}))
            return annotations

        @classmethod
        def model_validate(cls, data: Any) -> "BaseModel":
            if isinstance(data, cls):
                return data
            if not isinstance(data, dict):
                data = {}
            return cls(**data)

        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": {name: {} for name in cls._model_annotations()},
            }

        def model_dump(self) -> dict[str, Any]:
            return {name: getattr(self, name, None) for name in self._model_annotations()}

    def Field(default: Any = None, *, default_factory: Callable[[], Any] | None = None, **_: Any) -> Any:
        if default_factory is not None:
            return default_factory()
        return default

JSONRPC_VERSION = "2.0"
SERVER_PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {
    "name": "temperance-mcp",
    "version": "0.2.0",
}
DEFAULT_OWNER = "admin"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ResourceSpec:
    uri: str
    name: str
    title: str
    description: str
    mime_type: str
    reader: Callable[[], str]


@dataclass(frozen=True)
class PromptSpec:
    name: str
    title: str
    description: str
    arguments: list[dict[str, Any]]
    renderer: Callable[[dict[str, Any]], list[dict[str, Any]]]


class OwnerArgs(BaseModel):
    owner: str = DEFAULT_OWNER


class TodayStatusArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    sport: str | None = None


class RecentActivitiesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    limit: int = 5
    sport: str | None = None
    days: int = 30


class PlannedActivitiesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    weeks: int = 4


class WeekOutlookArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    days: int = 120
    metric: str = "tss"
    compare: str = "planned"
    week_start: str | None = None


class ActivityDetailArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    activity_id: str
    include_records: bool = True
    records_limit: int = 300


class GeneratedActivityCandidatesArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    day_utc: str
    mode: str = "planned"
    activity_type: str | None = None
    limit: int = 5


class ValidateWorkoutTextArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    day_utc: str | None = None
    workout_text: str


class DayPlanningArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    day_utc: str | None = None
    mode: str = "planned"
    activity_type: str | None = None
    limit: int = 3


class WeekPlanningArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    week_start: str | None = None
    mode: str = "planned"
    activity_type: str | None = None
    limit_per_day: int = 1


class AnalyzeWeekGapArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    week_start: str | None = None
    metric: str = "tss"
    compare: str = "planned"


class PlanChange(BaseModel):
    type: Literal["create_entry", "update_entry", "delete_entry", "set_manual_done"]
    day_utc: str
    line_no: int | None = None
    workout_text: str | None = None
    manual_done: bool | None = None


class PlanChangeArgs(BaseModel):
    owner: str = DEFAULT_OWNER
    changes: list[PlanChange] = Field(default_factory=list)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if pd is not None and isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _backend_main() -> Any:
    from backend.app import main as backend_main

    return backend_main


def _db_module() -> Any:
    from temperance import db as db_module

    return db_module


def _require_pandas() -> None:
    if pd is None:  # pragma: no cover - guarded in helper-only mode
        raise RuntimeError("pandas is required for Temperance MCP data tools")


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if pd is not None:
        try:
            ts = pd.to_datetime(value, utc=True, errors="coerce")
            if pd.isna(ts):
                return None
            return ts.to_pydatetime()
        except Exception:
            pass
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _iso_or_none(value: Any) -> str | None:
    ts = _normalize_timestamp(value)
    return ts.isoformat() if ts is not None else None


def _format_duration_minutes(seconds: Any) -> float:
    return round(max(_safe_float(seconds), 0.0) / 60.0, 1)


def _distance_km(value_meters: Any) -> float:
    return round(max(_safe_float(value_meters), 0.0) / 1000.0, 2)


def _clean_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_db_path(owner: str) -> Path:
    backend_main = _backend_main()
    normalized_owner = str(owner or DEFAULT_OWNER).strip() or DEFAULT_OWNER
    return backend_main._db_path_for_owner(normalized_owner)


def _ensure_db_ready(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        _db_module().run_migrations(db_path)
    else:
        _db_module().init_db(db_path)


def _owner_timezone(owner: str, db_path: Path) -> str:
    backend_main = _backend_main()
    configured = _db_module().get_setting(db_path, backend_main.SETTINGS_KEY_USER_TIMEZONE)
    tz_name = str(configured or "").strip()
    return tz_name or "UTC"


def _resource_temperance_lingo() -> str:
    return """Temperance Lingo v1

Activity kinds and aliases:
- running: run, treadmill
- bike: cycling, cycle, ride, trainer
- elliptical: xtrain, x-train, cross train, cross-train

Canonical planning text:
- Use compact Temperance workout text.
- Valid dated input is `[date]:[activity]` when ingesting multiple entries.
- A single stored workout text should remain parseable by the existing planner.
- Examples:
  - Run 45min @4:50/km
  - Elliptical 70min @138bpm
  - Bike 90min @72%
  - Run 15min @5:00/km + 4x8min @4:10/km / 2min @5:00/km

Core metrics:
- tss: heart-rate or generic load proxy
- rtss: running-specific load proxy
- distance_eqv_km: distance-equivalent volume
- if_proxy: intensity factor proxy
- training_readiness: Garmin readiness score when available
- sleep_score: Garmin sleep score when available
- stress_avg: Garmin average stress when available

Weekly planning concepts:
- remaining_to_go: current week's remaining planned load gap vs compare target
- balanced_tss_per_remaining_day: even pacing needed across remaining days
- manual_done: explicit completion override for planned workouts
- week gap: shorthand for current deficit or surplus vs the current weekly compare target

Coaching language expectations:
- Stay grounded in tool outputs and cite decisive metrics.
- Keep guidance concise and practical.
- Explain tradeoffs and how today fits the rest of the week.
- Do not make medical claims.
"""


def _resource_planning_rules() -> str:
    return """Temperance Planning Rules v1

Accepted date forms for dated bulk input:
- today, tomorrow, yesterday, T, T+1, T-1
- 2026-03-26
- 26/03/2026
- 26Mar26

Accepted intensity forms:
- pace: @4:40 or @4:40/km
- named running pace: @mp, @hmp, @10k
- heart rate: @138bpm
- intensity factor: @72%
- explicit load: @80tss

Accepted duration and distance forms:
- 45min, 45', 1h, 1h30m, 20s
- 42.2km, 400m, 6x1km, 8x400m

Rules:
- Running pace tokens are only valid for running/treadmill.
- Non-running segments should use bpm or % intensity.
- Preserve canonical workout text because clients treat it as display-plus-roundtrip content.
- Draft outputs should be valid workout text, not prose.
"""


RESOURCES: dict[str, ResourceSpec] = {
    "resource://temperance/lingo": ResourceSpec(
        uri="resource://temperance/lingo",
        name="temperance_lingo",
        title="Temperance Lingo",
        description="Canonical Temperance vocabulary, metrics, aliases, and coaching expectations.",
        mime_type="text/plain",
        reader=_resource_temperance_lingo,
    ),
    "resource://temperance/planning-rules": ResourceSpec(
        uri="resource://temperance/planning-rules",
        name="planning_rules",
        title="Planning Rules",
        description="Accepted Temperance planning syntax and round-trip rules.",
        mime_type="text/plain",
        reader=_resource_planning_rules,
    ),
}


def _prompt_message(text: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": text.strip(),
            }
        ],
    }


def _render_daily_checkin(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    owner = str(arguments.get("owner") or DEFAULT_OWNER)
    return [
        _prompt_message(
            f"""
            You are preparing a Temperance daily check-in for owner `{owner}`.
            First read `temperance_lingo` and `planning_rules`.
            Then call `get_today_status`, `get_data_freshness`, and `get_recent_activities`.
            If recovery or freshness is unclear, say so explicitly.
            Respond in Temperance language and cite the decisive metrics.
            """
        )
    ]


def _render_plan_week(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    owner = str(arguments.get("owner") or DEFAULT_OWNER)
    return [
        _prompt_message(
            f"""
            Plan the week for owner `{owner}` using Temperance language.
            Read `temperance_lingo` and `planning_rules` first.
            Then call `analyze_week_gap`, `get_planned_activities`, `get_data_freshness`, and `draft_week_plan`.
            Do not invent Garmin or recovery facts that are not present in tool outputs.
            Present the proposed entries, the decisive signals, and any limitations or stale-data warnings.
            """
        )
    ]


def _render_adjust_today(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    owner = str(arguments.get("owner") or DEFAULT_OWNER)
    return [
        _prompt_message(
            f"""
            Adjust today's training guidance for owner `{owner}`.
            Fetch `get_today_status`, `get_data_freshness`, and `explain_day_recommendation`.
            If recovery data is missing or stale, keep the guidance conservative and state the limitation.
            Explain why today's recommendation fits the rest of the week.
            """
        )
    ]


def _render_explain_session(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    owner = str(arguments.get("owner") or DEFAULT_OWNER)
    return [
        _prompt_message(
            f"""
            Explain why a Temperance session fits for owner `{owner}`.
            Read `temperance_lingo`, then call `explain_day_recommendation`.
            Focus on decisive metrics, weekly fit, and any confidence limits.
            Avoid generic coaching language that is not grounded in the tool output.
            """
        )
    ]


def _render_review_week(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    owner = str(arguments.get("owner") or DEFAULT_OWNER)
    return [
        _prompt_message(
            f"""
            Review the current week for owner `{owner}`.
            Read `temperance_lingo` and `planning_rules`.
            Then call `get_week_outlook`, `get_planned_activities`, `get_recent_activities`, `get_recovery_trend`, and `analyze_week_gap`.
            Summarize the week state, call out challenges, and suggest concrete Temperance-style plan changes without applying them automatically.
            """
        )
    ]


PROMPTS: dict[str, PromptSpec] = {
    "daily_checkin": PromptSpec(
        name="daily_checkin",
        title="Daily Check-in",
        description="Grounded daily Temperance check-in based on current state and freshness.",
        arguments=[{"name": "owner", "required": False}],
        renderer=_render_daily_checkin,
    ),
    "plan_this_week": PromptSpec(
        name="plan_this_week",
        title="Plan This Week",
        description="Grounded weekly planning flow using Temperance lingo and draft plan tools.",
        arguments=[{"name": "owner", "required": False}],
        renderer=_render_plan_week,
    ),
    "adjust_today_based_on_recovery": PromptSpec(
        name="adjust_today_based_on_recovery",
        title="Adjust Today Based On Recovery",
        description="Fetch current state and explain how recovery should change today's session.",
        arguments=[{"name": "owner", "required": False}],
        renderer=_render_adjust_today,
    ),
    "explain_why_this_session_fits": PromptSpec(
        name="explain_why_this_session_fits",
        title="Explain Why This Session Fits",
        description="Explain the fit of a Temperance recommendation using decisive metrics only.",
        arguments=[{"name": "owner", "required": False}],
        renderer=_render_explain_session,
    ),
    "review_my_week_and_suggest_changes": PromptSpec(
        name="review_my_week_and_suggest_changes",
        title="Review My Week And Suggest Changes",
        description="Weekly review prompt grounded in current activities, recovery, and plan state.",
        arguments=[{"name": "owner", "required": False}],
        renderer=_render_review_week,
    ),
}


def _db_setup_payload(owner: str, db_path: Path) -> dict[str, Any]:
    return {
        "owner": owner,
        "db_path": str(db_path),
        "db_exists": False,
        "warnings": [
            "Owner database not found yet.",
            "Run Temperance once or apply a planned-entry change to initialize the local database.",
        ],
    }


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


def _recent_metrics_df(owner: str, sport: str | None = None, days: int = 45) -> tuple[Path, Any]:
    _require_pandas()
    backend_main = _backend_main()
    db_path = _resolve_db_path(owner)
    if not db_path.exists():
        return db_path, pd.DataFrame()
    metrics_df = backend_main._metrics_for_filters(
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


def _load_workout_curves(db_path: Path, day_utc: str | None) -> dict[str, Any]:
    backend_main = _backend_main()
    if day_utc:
        day_ts = pd.to_datetime(day_utc, utc=True, errors="coerce")
    else:
        day_ts = pd.Timestamp(_utc_now().date(), tz="UTC")
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
    lthr_default = float(lthr_curve[-1][1]) if lthr_curve else backend_main.DEFAULT_LTHR
    pace_default = float(pace_curve[-1][1]) if pace_curve else backend_main.DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    return {
        "lthr_curve": lthr_curve,
        "pace_curve": pace_curve,
        "specificity_profile": specificity_profile,
        "lthr_for_day": float(backend_main._curve_value_at(lthr_curve, lthr_default, day_ts)),
        "pace_for_day": float(backend_main._curve_value_at(pace_curve, pace_default, day_ts)),
        "has_vdot_basis": backend_main._has_explicit_lt_pace_curve(db_path),
    }


def _validate_single_workout(owner: str, db_path: Path, day_utc: str | None, workout_text: str) -> dict[str, Any]:
    _require_pandas()
    backend_main = _backend_main()
    normalized = backend_main._normalize_plan_text(str(workout_text or ""))
    day_key = str(day_utc or _utc_now().date().isoformat()).strip()
    curves = _load_workout_curves(db_path, day_key)
    segments, warnings = backend_main._expand_planned_segments(
        normalized,
        lthr_bpm=curves["lthr_for_day"],
        threshold_pace_sec_per_km=curves["pace_for_day"],
        has_vdot_basis=bool(curves["has_vdot_basis"]),
    )
    metrics_rows = []
    if segments and not warnings:
        frame = pd.DataFrame(
            [
                {
                    "day_utc": day_key,
                    "line_no": 1,
                    "workout_text": normalized,
                    "parsed_json": segments,
                    "manual_done": False,
                }
            ]
        )
        metrics_df = backend_main._compute_planned_rows_metrics_df(
            planned_rows=frame,
            lthr_curve_points=curves["lthr_curve"],
            lthr_default_bpm=float(curves["lthr_for_day"]),
            lt_pace_curve_points=curves["pace_curve"],
            lt_pace_default_sec=float(curves["pace_for_day"]),
            specificity_profile=curves["specificity_profile"],
        )
        if not metrics_df.empty:
            metrics_rows.append(metrics_df.iloc[0])
    metrics = metrics_rows[0] if metrics_rows else {}
    return {
        "owner": owner,
        "day_utc": day_key,
        "workout_text": str(workout_text or ""),
        "normalized_text": normalized,
        "is_valid": bool(segments and not warnings),
        "safe_to_persist": bool(segments and not warnings),
        "warnings": warnings,
        "segments": segments,
        "estimated_metrics": _clean_mapping(
            {
                "duration_min": _format_duration_minutes(metrics.get("duration_s")),
                "tss": round(_safe_float(metrics.get("tss")), 1),
                "rtss": round(_safe_float(metrics.get("rtss")), 1),
                "distance_eqv_km": round(_safe_float(metrics.get("distance_proxy_km")), 2),
                "if_proxy": round(_safe_float(metrics.get("if_proxy")), 3),
                "avg_hr_bpm": round(_safe_float(metrics.get("avg_hr_bpm")), 1),
                "pace_proxy_sec_per_km": round(_safe_float(metrics.get("pace_proxy_sec_per_km")), 1),
            }
        ),
    }


def _daily_tss_target_from_week_outlook(payload: dict[str, Any]) -> float:
    goal = max(_safe_float(payload.get("goal")), 0.0)
    return round(goal / 7.0, 1) if goal > 0 else 0.0


def _remaining_days_in_week(payload: dict[str, Any]) -> int:
    rows = payload.get("rows") or []
    today_day = str(payload.get("today_day") or "").strip()
    if not rows:
        return 0
    return sum(1 for row in rows if str(row.get("day") or "") >= today_day)


def _data_freshness(owner: str) -> dict[str, Any]:
    db_path = _resolve_db_path(owner)
    if not db_path.exists():
        return _db_setup_payload(owner, db_path)
    db = _db_module()
    last_sync = db.get_last_sync(db_path)
    latest_activity = db.get_latest_activity_time(db_path)
    latest_recovery = db.get_latest_recovery_day(db_path)
    now = _utc_now()
    activity_age_days = (now - latest_activity).total_seconds() / 86400.0 if latest_activity else None
    recovery_age_days = (now - latest_recovery).total_seconds() / 86400.0 if latest_recovery else None
    warnings: list[str] = []
    if latest_recovery is None:
        warnings.append("Recovery data is missing.")
    elif recovery_age_days is not None and recovery_age_days > 3:
        warnings.append("Recovery data looks stale.")
    if latest_activity is None:
        warnings.append("No activity data found.")
    elif activity_age_days is not None and activity_age_days > 7:
        warnings.append("Recent activity data looks stale.")
    return {
        "owner": owner,
        "db_path": str(db_path),
        "db_exists": True,
        "last_sync": last_sync,
        "latest_activity_time_utc": _iso_or_none(latest_activity),
        "latest_recovery_day_utc": _iso_or_none(latest_recovery),
        "activity_age_days": round(float(activity_age_days), 1) if activity_age_days is not None else None,
        "recovery_age_days": round(float(recovery_age_days), 1) if recovery_age_days is not None else None,
        "is_recovery_stale": bool(recovery_age_days is not None and recovery_age_days > 3),
        "is_activity_stale": bool(activity_age_days is not None and activity_age_days > 7),
        "warnings": warnings,
    }


def _guidance_status(context: dict[str, Any]) -> tuple[str, str]:
    if bool(context.get("recovery_alert")):
        return "recover", "Recovery signals are suppressed, so the safest call is recovery-first work."
    if bool(context.get("easy_bias")):
        return "easy", "Load and recovery signals point to controlled aerobic work instead of stacking intensity."
    if bool(context.get("progression_green")) and bool(context.get("week_behind")):
        return "build", "Recovery is usable and the week is still behind target, so a bigger session is justified."
    return "steady", "Load and recovery look balanced enough for a normal quality day."


def _guidance_confidence(context: dict[str, Any], freshness: dict[str, Any]) -> str:
    if freshness.get("is_recovery_stale") or freshness.get("latest_recovery_day_utc") is None:
        return "low"
    if not context:
        return "low"
    if bool(context.get("progression_green")) or bool(context.get("recovery_alert")):
        return "high"
    return "medium"


def _guidance_limitations(freshness: dict[str, Any], planned_rows_today: list[dict[str, Any]]) -> list[str]:
    warnings = list(freshness.get("warnings") or [])
    if planned_rows_today:
        warnings.append("This recommendation does not apply changes automatically; the current day already has planned work.")
    warnings.append("Training guidance only; not medical advice.")
    deduped: list[str] = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)
    return deduped


def _generated_candidates_payload(owner: str, day_utc: str, mode: str, activity_type: str | None, limit: int) -> dict[str, Any]:
    _require_pandas()
    backend_main = _backend_main()
    db_path = _resolve_db_path(owner)
    if not db_path.exists():
        return _db_setup_payload(owner, db_path)
    curves = _load_workout_curves(db_path, day_utc)
    context = backend_main._generated_activity_context(
        db_path=db_path,
        day_utc=day_utc,
        threshold_pace_sec_per_km=curves["pace_for_day"],
        activity_type=activity_type,
    )
    suggestions = backend_main._generated_activity_candidates(
        db_path=db_path,
        mode=mode,
        day_utc=day_utc,
        activity_type=activity_type,
    )
    if not suggestions:
        fallback_bucket = (backend_main._generated_activity_preferred_buckets(day_utc, context) or ["easy"])[0]
        fallback_goal = backend_main._generated_activity_day_goal_tss(
            day_utc=day_utc,
            threshold_pace_sec_per_km=curves["pace_for_day"],
            context=context,
        )
        fallback_suggestions = backend_main._generated_activity_fallbacks(activity_type=activity_type, mode=mode)
        suggestions = [{"activity_text": text, "priority": 0, "bucket": fallback_bucket, "estimated_tss": fallback_goal} for text in fallback_suggestions]
    preferred_buckets = backend_main._generated_activity_preferred_buckets(day_utc, context)
    target_tss = backend_main._generated_activity_day_goal_tss(
        day_utc=day_utc,
        threshold_pace_sec_per_km=curves["pace_for_day"],
        context=context,
    )
    shortlist = backend_main._generated_activity_shortlist(
        suggestions=suggestions,
        target_tss=target_tss,
        preferred_buckets=preferred_buckets,
        context=context,
    )
    candidate_score = getattr(backend_main, "_generated_activity_candidate_score", None)
    items = []
    for score, item in shortlist[: max(1, min(limit, 10))]:
        chosen_score = float(score)
        if candidate_score is not None:
            chosen_score = float(
                candidate_score(
                    item=item,
                    target_tss=target_tss,
                    preferred_buckets=preferred_buckets,
                    context=context,
                )
            )
        items.append(
            {
                "workout_text": str(item.get("activity_text") or ""),
                "estimated_tss": round(_safe_float(item.get("estimated_tss")), 1),
                "bucket": str(item.get("bucket") or ""),
                "priority": _safe_int(item.get("priority")),
                "score": round(chosen_score, 2),
            }
        )
    return {
        "owner": owner,
        "db_path": str(db_path),
        "day_utc": day_utc,
        "mode": mode,
        "activity_type": str(activity_type or context.get("activity_type") or "running"),
        "preferred_buckets": preferred_buckets,
        "target_tss": round(_safe_float(target_tss), 1),
        "source_context": {
            "base_daily_goal_tss": round(_safe_float(context.get("base_daily_goal_tss")), 1),
            "week_balanced_daily_tss": round(_safe_float(context.get("week_balanced_daily_tss")), 1),
            "week_gap_tss": round(_safe_float(context.get("week_gap_tss")), 1),
            "days_remaining_in_week": _safe_int(context.get("days_remaining_in_week")),
            "recovery_alert": bool(context.get("recovery_alert")),
            "easy_bias": bool(context.get("easy_bias")),
            "progression_green": bool(context.get("progression_green")),
            "adjacent_hard_days": bool(context.get("adjacent_hard_days")),
            "week_behind": bool(context.get("week_behind")),
            "training_readiness": round(_safe_float(context.get("training_readiness")), 1),
            "sleep_score": round(_safe_float(context.get("sleep_score")), 1),
            "stress_avg": round(_safe_float(context.get("stress_avg")), 1),
        },
        "candidates": items,
    }


def _day_plan_core(owner: str, day_utc: str | None, mode: str, activity_type: str | None, limit: int) -> dict[str, Any]:
    backend_main = _backend_main()
    target_day = str(day_utc or _utc_now().date().isoformat())
    freshness = _data_freshness(owner)
    candidates_payload = _generated_candidates_payload(owner, target_day, mode, activity_type, limit=max(limit, 3))
    if not candidates_payload.get("db_exists", True):
        return candidates_payload
    db_path = Path(str(candidates_payload.get("db_path") or ""))
    context = dict(candidates_payload.get("source_context") or {})
    status, rationale = _guidance_status(context)
    planned_df = _db_module().get_planned_activities_df(db_path, start_day_utc=target_day, end_day_utc=target_day)
    today_rows = []
    if not planned_df.empty:
        for _, row in planned_df.sort_values(["day_utc", "line_no"]).iterrows():
            today_rows.append(
                {
                    "day_utc": str(row.get("day_utc") or ""),
                    "line_no": _safe_int(row.get("line_no")),
                    "workout_text": str(row.get("workout_text") or ""),
                    "manual_done": bool(_safe_int(row.get("manual_done")) > 0),
                }
            )
    top_candidates = list(candidates_payload.get("candidates") or [])[: max(1, min(limit, 5))]
    summary = {
        "recover": "Recovery-first day",
        "easy": "Controlled aerobic day",
        "steady": "Steady quality day",
        "build": "Build day",
    }.get(status, "Training day")
    reasoning = [
        rationale,
        f"Weekly gap is {round(_safe_float(context.get('week_gap_tss')), 1)} TSS with {int(_safe_int(context.get('days_remaining_in_week')))} days left.",
    ]
    if _safe_float(context.get("training_readiness")) > 0:
        reasoning.append(f"Training readiness is {round(_safe_float(context.get('training_readiness')), 1)}.")
    if _safe_float(context.get("sleep_score")) > 0:
        reasoning.append(f"Sleep score is {round(_safe_float(context.get('sleep_score')), 1)}.")
    if _safe_float(context.get("stress_avg")) > 0:
        reasoning.append(f"Average stress is {round(_safe_float(context.get('stress_avg')), 1)}.")
    proposed_entries = [
        {
            "day_utc": target_day,
            "workout_text": candidate["workout_text"],
            "estimated_tss": candidate["estimated_tss"],
            "bucket": candidate["bucket"],
            "priority": candidate["priority"],
            "score": candidate["score"],
        }
        for candidate in top_candidates
    ]
    return {
        "owner": owner,
        "db_path": str(db_path),
        "day_utc": target_day,
        "activity_type": candidates_payload.get("activity_type"),
        "summary": summary,
        "reasoning": reasoning,
        "proposed_entries": proposed_entries,
        "source_signals": {
            "status": status,
            "confidence": _guidance_confidence(context, freshness),
            "limitations": _guidance_limitations(freshness, today_rows),
            "week_gap_tss": round(_safe_float(context.get("week_gap_tss")), 1),
            "week_balanced_daily_tss": round(_safe_float(context.get("week_balanced_daily_tss")), 1),
            "base_daily_goal_tss": round(_safe_float(context.get("base_daily_goal_tss")), 1),
            "training_readiness": round(_safe_float(context.get("training_readiness")), 1),
            "sleep_score": round(_safe_float(context.get("sleep_score")), 1),
            "stress_avg": round(_safe_float(context.get("stress_avg")), 1),
            "recovery_alert": bool(context.get("recovery_alert")),
            "easy_bias": bool(context.get("easy_bias")),
            "progression_green": bool(context.get("progression_green")),
            "adjacent_hard_days": bool(context.get("adjacent_hard_days")),
            "freshness": freshness,
        },
        "warnings": _guidance_limitations(freshness, today_rows),
        "existing_day_plan": today_rows,
        "note": "Deterministic Temperance draft only; final coaching prose should be produced by the client after reading these signals.",
    }


def _week_start_for_value(value: str | None) -> str:
    backend_main = _backend_main()
    if value:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.notna(parsed):
            return backend_main._week_start_monday(parsed).date().isoformat()
    return backend_main._week_start_monday(pd.Timestamp(_utc_now().date())).date().isoformat()


def _week_day_sequence(week_start: str) -> list[str]:
    start = date.fromisoformat(week_start)
    return [(start + timedelta(days=offset)).isoformat() for offset in range(7)]


def _day_candidate_for_target(owner: str, day_utc: str, mode: str, activity_type: str | None, target_tss: float) -> dict[str, Any] | None:
    payload = _generated_candidates_payload(owner, day_utc, mode, activity_type, limit=5)
    if not payload.get("db_exists", True):
        return None
    context = dict(payload.get("source_context") or {})
    preferred_buckets = list(payload.get("preferred_buckets") or [])
    backend_main = _backend_main()
    scorer = getattr(backend_main, "_generated_activity_candidate_score", None)
    candidates = list(payload.get("candidates") or [])
    if not candidates:
        return None
    best_item = None
    best_score = None
    for item in candidates:
        item_payload = {
            "activity_text": item.get("workout_text"),
            "estimated_tss": item.get("estimated_tss"),
            "bucket": item.get("bucket"),
            "priority": item.get("priority"),
        }
        if scorer is not None:
            score = float(
                scorer(
                    item=item_payload,
                    target_tss=target_tss,
                    preferred_buckets=preferred_buckets,
                    context=context,
                )
            )
        else:
            score = abs(_safe_float(item.get("estimated_tss")) - float(target_tss))
        if best_score is None or score < best_score:
            best_score = score
            best_item = item
    if best_item is None:
        return None
    return {
        "day_utc": day_utc,
        "workout_text": str(best_item.get("workout_text") or ""),
        "estimated_tss": round(_safe_float(best_item.get("estimated_tss")), 1),
        "bucket": str(best_item.get("bucket") or ""),
        "priority": _safe_int(best_item.get("priority")),
        "score": round(float(best_score or 0.0), 2),
        "target_tss": round(float(target_tss), 1),
    }


def _plan_day_rows_by_day(db_path: Path, week_start: str, today_day: str) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    backend_main = _backend_main()
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
    planned_rows = _db_module().get_planned_activities_df(db_path, start_day_utc=week_start, end_day_utc=week_end)
    rows_by_day: dict[str, list[dict[str, Any]]] = {}
    effective_days: set[str] = set()
    if planned_rows.empty:
        return rows_by_day, effective_days
    curves = _load_workout_curves(db_path, today_day)
    metrics_df = backend_main._compute_planned_rows_metrics_df(
        planned_rows=planned_rows,
        lthr_curve_points=curves["lthr_curve"],
        lthr_default_bpm=float(curves["lthr_for_day"]),
        lt_pace_curve_points=curves["pace_curve"],
        lt_pace_default_sec=float(curves["pace_for_day"]),
        specificity_profile=curves["specificity_profile"],
    )
    filtered = backend_main._filter_effective_planned_rows(
        planned_df=metrics_df,
        today_local_day=backend_main._now_app_local().normalize(),
    )
    if not filtered.empty:
        effective_days = {str(value) for value in filtered.get("day_utc", pd.Series(dtype=str)).astype(str).tolist()}
    for _, row in planned_rows.sort_values(["day_utc", "line_no"]).iterrows():
        day_key = str(row.get("day_utc") or "")
        rows_by_day.setdefault(day_key, []).append(
            {
                "day_utc": day_key,
                "line_no": _safe_int(row.get("line_no")),
                "workout_text": str(row.get("workout_text") or ""),
                "manual_done": bool(_safe_int(row.get("manual_done")) > 0),
            }
        )
    return rows_by_day, effective_days


def _normalize_change(change: PlanChange | dict[str, Any]) -> dict[str, Any]:
    payload = change.model_dump() if hasattr(change, "model_dump") else dict(change or {})
    payload["day_utc"] = str(payload.get("day_utc") or "").strip()
    if payload.get("workout_text") is not None:
        payload["workout_text"] = str(payload.get("workout_text") or "")
    return payload


def _existing_planned_rows_lookup(planned_df: Any) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[str, int], set[str]]:
    row_lookup: dict[tuple[str, int], dict[str, Any]] = {}
    max_line_by_day: dict[str, int] = {}
    signatures: set[str] = set()
    backend_main = _backend_main()
    if planned_df.empty:
        return row_lookup, max_line_by_day, signatures
    for _, row in planned_df.iterrows():
        day_key = str(row.get("day_utc") or "")
        line_no = _safe_int(row.get("line_no"))
        workout_text = str(row.get("workout_text") or "")
        row_lookup[(day_key, line_no)] = {
            "day_utc": day_key,
            "line_no": line_no,
            "workout_text": workout_text,
            "parsed_json": row.get("parsed_json"),
            "manual_done": bool(_safe_int(row.get("manual_done")) > 0),
        }
        max_line_by_day[day_key] = max(max_line_by_day.get(day_key, 0), line_no)
        signatures.add(backend_main._planned_row_signature(day_key, workout_text))
    return row_lookup, max_line_by_day, signatures


def _preview_changes(owner: str, changes: list[PlanChange], apply: bool) -> dict[str, Any]:
    _require_pandas()
    backend_main = _backend_main()
    db_path = _resolve_db_path(owner)
    if apply:
        _ensure_db_ready(db_path)
    if not db_path.exists():
        return _db_setup_payload(owner, db_path)

    planned_df = _db_module().get_planned_activities_df(db_path)
    row_lookup, max_line_by_day, signatures = _existing_planned_rows_lookup(planned_df)
    to_upsert: list[dict[str, Any]] = []
    to_delete: list[tuple[str, int]] = []
    to_manual_done: list[tuple[str, int, bool]] = []
    preview_operations: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    affected_days: set[str] = set()

    for index, raw_change in enumerate(changes, start=1):
        change = _normalize_change(raw_change)
        op_type = str(change.get("type") or "")
        day_utc = str(change.get("day_utc") or "").strip()
        line_no = change.get("line_no")
        if not day_utc:
            rejected.append({"index": index, "change": change, "error": "Missing day_utc."})
            continue
        try:
            date.fromisoformat(day_utc)
        except ValueError:
            rejected.append({"index": index, "change": change, "error": "day_utc must be YYYY-MM-DD."})
            continue

        if op_type == "create_entry":
            workout_text = str(change.get("workout_text") or "")
            validation = _validate_single_workout(owner, db_path, day_utc, workout_text)
            if not validation["safe_to_persist"]:
                rejected.append({"index": index, "change": change, "error": "Workout text is not valid.", "warnings": validation["warnings"]})
                continue
            signature = backend_main._planned_row_signature(day_utc, validation["normalized_text"])
            if signature in signatures:
                rejected.append({"index": index, "change": change, "error": "A matching planned workout already exists for that day."})
                continue
            next_line = max_line_by_day.get(day_utc, 0) + 1
            max_line_by_day[day_utc] = next_line
            signatures.add(signature)
            row_payload = {
                "day_utc": day_utc,
                "line_no": next_line,
                "workout_text": validation["normalized_text"],
                "parsed_json": validation["segments"],
                "manual_done": False,
            }
            row_lookup[(day_utc, next_line)] = row_payload
            to_upsert.append(row_payload)
            affected_days.add(day_utc)
            preview_operations.append(
                {
                    "index": index,
                    "type": op_type,
                    "day_utc": day_utc,
                    "line_no": next_line,
                    "normalized_text": validation["normalized_text"],
                    "estimated_metrics": validation["estimated_metrics"],
                }
            )
            continue

        if op_type == "update_entry":
            if line_no is None:
                rejected.append({"index": index, "change": change, "error": "update_entry requires line_no."})
                continue
            key = (day_utc, int(line_no))
            existing = row_lookup.get(key)
            if existing is None:
                rejected.append({"index": index, "change": change, "error": "Planned entry not found."})
                continue
            workout_text = str(change.get("workout_text") or "")
            validation = _validate_single_workout(owner, db_path, day_utc, workout_text)
            if not validation["safe_to_persist"]:
                rejected.append({"index": index, "change": change, "error": "Workout text is not valid.", "warnings": validation["warnings"]})
                continue
            signature = backend_main._planned_row_signature(day_utc, validation["normalized_text"])
            old_signature = backend_main._planned_row_signature(day_utc, str(existing.get("workout_text") or ""))
            if signature != old_signature and signature in signatures:
                rejected.append({"index": index, "change": change, "error": "Another planned workout already uses that normalized text for the same day."})
                continue
            signatures.discard(old_signature)
            signatures.add(signature)
            row_payload = {
                "day_utc": day_utc,
                "line_no": int(line_no),
                "workout_text": validation["normalized_text"],
                "parsed_json": validation["segments"],
                "manual_done": bool(existing.get("manual_done")),
            }
            row_lookup[key] = row_payload
            to_upsert.append(row_payload)
            affected_days.add(day_utc)
            preview_operations.append(
                {
                    "index": index,
                    "type": op_type,
                    "day_utc": day_utc,
                    "line_no": int(line_no),
                    "normalized_text": validation["normalized_text"],
                    "estimated_metrics": validation["estimated_metrics"],
                }
            )
            continue

        if op_type == "delete_entry":
            if line_no is None:
                rejected.append({"index": index, "change": change, "error": "delete_entry requires line_no."})
                continue
            key = (day_utc, int(line_no))
            existing = row_lookup.get(key)
            if existing is None:
                rejected.append({"index": index, "change": change, "error": "Planned entry not found."})
                continue
            signatures.discard(backend_main._planned_row_signature(day_utc, str(existing.get("workout_text") or "")))
            row_lookup.pop(key, None)
            to_delete.append((day_utc, int(line_no)))
            affected_days.add(day_utc)
            preview_operations.append({"index": index, "type": op_type, "day_utc": day_utc, "line_no": int(line_no)})
            continue

        if op_type == "set_manual_done":
            if line_no is None or change.get("manual_done") is None:
                rejected.append({"index": index, "change": change, "error": "set_manual_done requires line_no and manual_done."})
                continue
            key = (day_utc, int(line_no))
            existing = row_lookup.get(key)
            if existing is None:
                rejected.append({"index": index, "change": change, "error": "Planned entry not found."})
                continue
            row_lookup[key] = {**existing, "manual_done": bool(change["manual_done"])}
            to_manual_done.append((day_utc, int(line_no), bool(change["manual_done"])))
            affected_days.add(day_utc)
            preview_operations.append(
                {
                    "index": index,
                    "type": op_type,
                    "day_utc": day_utc,
                    "line_no": int(line_no),
                    "manual_done": bool(change["manual_done"]),
                }
            )
            continue

        rejected.append({"index": index, "change": change, "error": f"Unknown change type: {op_type}"})

    before_planned = _db_module().get_planned_activities_df(db_path)
    if preview_operations:
        simulated_rows = list(row_lookup.values())
        simulated_df = pd.DataFrame(simulated_rows)
        if simulated_df.empty:
            after_planned = pd.DataFrame(columns=["day_utc", "line_no", "workout_text", "parsed_json", "manual_done"])
        else:
            after_planned = simulated_df.sort_values(["day_utc", "line_no"]).copy()
    else:
        after_planned = before_planned.copy()

    week_impact: list[dict[str, Any]] = []
    if affected_days:
        impacted_weeks = sorted({_week_start_for_value(day) for day in affected_days})
        curves = _load_workout_curves(db_path, min(affected_days))
        before_metrics = backend_main._compute_planned_rows_metrics_df(
            planned_rows=before_planned,
            lthr_curve_points=curves["lthr_curve"],
            lthr_default_bpm=float(curves["lthr_for_day"]),
            lt_pace_curve_points=curves["pace_curve"],
            lt_pace_default_sec=float(curves["pace_for_day"]),
            specificity_profile=curves["specificity_profile"],
        ) if not before_planned.empty else pd.DataFrame()
        after_metrics = backend_main._compute_planned_rows_metrics_df(
            planned_rows=after_planned,
            lthr_curve_points=curves["lthr_curve"],
            lthr_default_bpm=float(curves["lthr_for_day"]),
            lt_pace_curve_points=curves["pace_curve"],
            lt_pace_default_sec=float(curves["pace_for_day"]),
            specificity_profile=curves["specificity_profile"],
        ) if not after_planned.empty else pd.DataFrame()
        for week_start in impacted_weeks:
            week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
            before_slice = before_metrics.loc[
                (before_metrics.get("day_utc", pd.Series(dtype=str)).astype(str) >= week_start)
                & (before_metrics.get("day_utc", pd.Series(dtype=str)).astype(str) <= week_end)
            ] if not before_metrics.empty else pd.DataFrame()
            after_slice = after_metrics.loc[
                (after_metrics.get("day_utc", pd.Series(dtype=str)).astype(str) >= week_start)
                & (after_metrics.get("day_utc", pd.Series(dtype=str)).astype(str) <= week_end)
            ] if not after_metrics.empty else pd.DataFrame()
            before_tss = round(_safe_float(before_slice.get("tss", pd.Series(dtype=float)).sum()), 1) if not before_slice.empty else 0.0
            after_tss = round(_safe_float(after_slice.get("tss", pd.Series(dtype=float)).sum()), 1) if not after_slice.empty else 0.0
            before_rtss = round(_safe_float(before_slice.get("rtss", pd.Series(dtype=float)).sum()), 1) if not before_slice.empty else 0.0
            after_rtss = round(_safe_float(after_slice.get("rtss", pd.Series(dtype=float)).sum()), 1) if not after_slice.empty else 0.0
            before_distance = round(_safe_float(before_slice.get("distance_proxy_km", pd.Series(dtype=float)).sum()), 1) if not before_slice.empty else 0.0
            after_distance = round(_safe_float(after_slice.get("distance_proxy_km", pd.Series(dtype=float)).sum()), 1) if not after_slice.empty else 0.0
            week_impact.append(
                {
                    "week_start": week_start,
                    "week_end": week_end,
                    "before": {
                        "tss": before_tss,
                        "rtss": before_rtss,
                        "distance_eqv_km": before_distance,
                    },
                    "after": {
                        "tss": after_tss,
                        "rtss": after_rtss,
                        "distance_eqv_km": after_distance,
                    },
                    "delta": {
                        "tss": round(after_tss - before_tss, 1),
                        "rtss": round(after_rtss - before_rtss, 1),
                        "distance_eqv_km": round(after_distance - before_distance, 1),
                    },
                }
            )

    if apply:
        if to_delete:
            _db_module().delete_planned_activities(db_path=db_path, keys=to_delete)
        if to_upsert:
            _db_module().upsert_planned_activities_rows(db_path=db_path, rows=to_upsert)
        for day_utc, line_no, manual_done in to_manual_done:
            _db_module().set_planned_activity_manual_done(
                db_path=db_path,
                day_utc=day_utc,
                line_no=line_no,
                manual_done=manual_done,
            )

    return {
        "owner": owner,
        "db_path": str(db_path),
        "applied": bool(apply),
        "accepted_count": len(preview_operations),
        "rejected_count": len(rejected),
        "operations": preview_operations,
        "rejected": rejected,
        "week_impact": week_impact,
    }


def tool_get_today_status(arguments: dict[str, Any]) -> dict[str, Any]:
    args = TodayStatusArgs.model_validate(arguments or {})
    db_path, metrics_df = _recent_metrics_df(args.owner, sport=args.sport, days=45)
    if not db_path.exists():
        return _db_setup_payload(args.owner, db_path)
    backend_main = _backend_main()
    db = _db_module()
    wellness_payload = backend_main._build_wellness_payload(db_path=db_path, days=14, aggregation="daily", owner=args.owner)
    week_outlook = backend_main._build_week_outlook_payload(
        db_path=db_path,
        days=120,
        start_day=None,
        end_day=None,
        sport=args.sport,
        metric="tss",
        compare="planned",
        week_start=None,
    )
    latest_activity = _activity_row_summary(metrics_df.iloc[0], include_extended_metrics=False) if not metrics_df.empty else None
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
                "projected_finish": week_outlook.get("projected_finish"),
                "estimated_fatigue_eow": week_outlook.get("estimated_fatigue_eow"),
                "daily_tss_target": _daily_tss_target_from_week_outlook(week_outlook),
                "remaining_days_in_week": _remaining_days_in_week(week_outlook),
            }
        ),
        "last_sync": db.get_last_sync(db_path),
        "freshness": _data_freshness(args.owner),
    }


def tool_get_recent_activities(arguments: dict[str, Any]) -> dict[str, Any]:
    args = RecentActivitiesArgs.model_validate(arguments or {})
    db_path, metrics_df = _recent_metrics_df(args.owner, sport=args.sport, days=max(args.days, args.limit))
    if not db_path.exists():
        return _db_setup_payload(args.owner, db_path)
    limit = max(1, min(int(args.limit), 50))
    items = [_activity_row_summary(row) for _, row in metrics_df.head(limit).iterrows()]
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "count": len(items),
        "activities": items,
    }


def tool_get_activity_detail(arguments: dict[str, Any]) -> dict[str, Any]:
    args = ActivityDetailArgs.model_validate(arguments or {})
    if not _resolve_db_path(args.owner).exists():
        return _db_setup_payload(args.owner, _resolve_db_path(args.owner))
    payload = _backend_main().activity_detail(
        activity_id=args.activity_id,
        owner=args.owner,
        include_records=bool(args.include_records),
        records_limit=max(100, min(int(args.records_limit), 5000)),
        authorization=None,
    )
    if not isinstance(payload, dict):
        raise ValueError("Unexpected activity detail payload")
    return payload


def tool_get_week_outlook(arguments: dict[str, Any]) -> dict[str, Any]:
    args = WeekOutlookArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    if not db_path.exists():
        return _db_setup_payload(args.owner, db_path)
    payload = _backend_main()._build_week_outlook_payload(
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
    if not db_path.exists():
        return _db_setup_payload(args.owner, db_path)
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
    rows = []
    for _, row in grouped.tail(21).iterrows():
        day = pd.to_datetime(row.get("day"), errors="coerce")
        if pd.isna(day):
            continue
        rows.append(
            {
                "day": day.date().isoformat(),
                "tss": round(_safe_float(row.get("tss")), 1),
                "rtss": round(_safe_float(row.get("rtss")), 1),
                "duration_min": _format_duration_minutes(row.get("duration_s")),
                "activities": _safe_int(row.get("activities")),
                "distance_equivalent_km": round(_safe_float(row.get("distance_equivalent_km")), 2),
                "ctl_42_tss": round(_safe_float(row.get("ctl_42_tss")), 1),
                "atl_7_tss": round(_safe_float(row.get("atl_7_tss")), 1),
                "tsb_proxy": round(_safe_float(row.get("tsb_proxy")), 1),
            }
        )
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "summary": {
            "days": int(max(args.days, 14)),
            "total_tss": round(_safe_float(grouped["tss"].sum()), 1),
            "total_rtss": round(_safe_float(grouped["rtss"].sum()), 1),
            "avg_daily_tss": round(_safe_float(grouped["tss"].mean()), 1),
            "avg_daily_rtss": round(_safe_float(grouped["rtss"].mean()), 1),
            "latest_ctl_42_tss": round(_safe_float(grouped["ctl_42_tss"].iloc[-1]), 1),
            "latest_atl_7_tss": round(_safe_float(grouped["atl_7_tss"].iloc[-1]), 1),
            "latest_tsb_proxy": round(_safe_float(grouped["tsb_proxy"].iloc[-1]), 1),
        },
        "daily": rows,
    }


def tool_get_recovery_trend(arguments: dict[str, Any]) -> dict[str, Any]:
    args = OwnerArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    if not db_path.exists():
        return _db_setup_payload(args.owner, db_path)
    payload = _backend_main()._build_wellness_payload(db_path=db_path, days=28, aggregation="daily", owner=args.owner)
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
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "summary": _clean_mapping(
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
        ),
        "daily": cleaned_points,
    }


def tool_get_planned_activities(arguments: dict[str, Any]) -> dict[str, Any]:
    args = PlannedActivitiesArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    if not db_path.exists():
        return _db_setup_payload(args.owner, db_path)
    payload = _backend_main()._build_planned_activities_payload(db_path=db_path, owner=args.owner, weeks=max(int(args.weeks), 1))
    payload["db_path"] = str(db_path)
    return payload


def tool_get_generated_activity_candidates(arguments: dict[str, Any]) -> dict[str, Any]:
    args = GeneratedActivityCandidatesArgs.model_validate(arguments or {})
    return _generated_candidates_payload(
        owner=args.owner,
        day_utc=args.day_utc,
        mode=str(args.mode or "planned").strip().lower(),
        activity_type=(str(args.activity_type).strip().lower() if args.activity_type else None),
        limit=max(1, min(int(args.limit), 10)),
    )


def tool_get_data_freshness(arguments: dict[str, Any]) -> dict[str, Any]:
    args = OwnerArgs.model_validate(arguments or {})
    return _data_freshness(args.owner)


def tool_explain_day_recommendation(arguments: dict[str, Any]) -> dict[str, Any]:
    args = DayPlanningArgs.model_validate(arguments or {})
    draft = _day_plan_core(
        owner=args.owner,
        day_utc=args.day_utc,
        mode=str(args.mode or "planned").strip().lower(),
        activity_type=(str(args.activity_type).strip().lower() if args.activity_type else None),
        limit=max(1, min(int(args.limit), 3)),
    )
    if not draft.get("db_exists", True):
        return draft
    top_entry = (draft.get("proposed_entries") or [None])[0]
    return {
        "owner": draft.get("owner"),
        "db_path": draft.get("db_path"),
        "day_utc": draft.get("day_utc"),
        "summary": draft.get("summary"),
        "headline": draft.get("summary"),
        "rationale": (draft.get("reasoning") or [""])[0],
        "why_today": draft.get("reasoning"),
        "how_it_fits_the_week": {
            "week_gap_tss": draft.get("source_signals", {}).get("week_gap_tss"),
            "week_balanced_daily_tss": draft.get("source_signals", {}).get("week_balanced_daily_tss"),
            "base_daily_goal_tss": draft.get("source_signals", {}).get("base_daily_goal_tss"),
        },
        "recommended_entry": top_entry,
        "source_signals": draft.get("source_signals"),
        "warnings": draft.get("warnings"),
        "caveat": "Training guidance only; not medical advice.",
    }


def tool_analyze_week_gap(arguments: dict[str, Any]) -> dict[str, Any]:
    args = AnalyzeWeekGapArgs.model_validate(arguments or {})
    week_outlook = tool_get_week_outlook(
        {
            "owner": args.owner,
            "week_start": args.week_start,
            "metric": args.metric,
            "compare": args.compare,
            "days": 120,
        }
    )
    if not week_outlook.get("db_exists", True):
        return week_outlook
    planned = tool_get_planned_activities({"owner": args.owner, "weeks": 8})
    summary = "Week is on track."
    remaining_to_go = _safe_float(week_outlook.get("remaining_to_go"))
    daily_target = _safe_float(week_outlook.get("daily_tss_target"))
    remaining_days = _safe_int(week_outlook.get("remaining_days_in_week"))
    if remaining_to_go > daily_target * 1.5 and daily_target > 0:
        summary = "Week is behind target."
    elif remaining_to_go <= 0:
        summary = "Week is already at or above target."
    reasoning = [
        f"Remaining load to go is {round(remaining_to_go, 1)} {week_outlook.get('metric', 'tss')} for the current compare target.",
        f"That implies roughly {round((remaining_to_go / max(remaining_days, 1)), 1) if remaining_to_go > 0 else 0.0} per remaining day.",
    ]
    return {
        "owner": args.owner,
        "db_path": week_outlook.get("db_path"),
        "summary": summary,
        "reasoning": reasoning,
        "proposed_entries": [],
        "warnings": list(_data_freshness(args.owner).get("warnings") or []),
        "source_signals": {
            "metric": week_outlook.get("metric"),
            "compare": week_outlook.get("compare"),
            "week_start": week_outlook.get("week_start"),
            "week_end": week_outlook.get("week_end"),
            "goal": week_outlook.get("goal"),
            "goal_progress_pct": week_outlook.get("goal_progress_pct"),
            "week_total_current": week_outlook.get("week_total_current"),
            "week_total_compare": week_outlook.get("week_total_compare"),
            "remaining_to_go": week_outlook.get("remaining_to_go"),
            "daily_tss_target": week_outlook.get("daily_tss_target"),
            "remaining_days_in_week": week_outlook.get("remaining_days_in_week"),
            "projected_finish": week_outlook.get("projected_finish"),
            "estimated_fatigue_eow": week_outlook.get("estimated_fatigue_eow"),
            "planned_rows_count": len(planned.get("rows") or []),
        },
        "week_rows": week_outlook.get("rows") or [],
    }


def tool_draft_day_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    args = DayPlanningArgs.model_validate(arguments or {})
    return _day_plan_core(
        owner=args.owner,
        day_utc=args.day_utc,
        mode=str(args.mode or "planned").strip().lower(),
        activity_type=(str(args.activity_type).strip().lower() if args.activity_type else None),
        limit=max(1, min(int(args.limit), 5)),
    )


def tool_draft_week_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    args = WeekPlanningArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    if not db_path.exists():
        return _db_setup_payload(args.owner, db_path)
    week_start = _week_start_for_value(args.week_start)
    week_gap = tool_analyze_week_gap({"owner": args.owner, "week_start": week_start, "metric": "tss", "compare": "planned"})
    if not week_gap.get("db_exists", True):
        return week_gap
    today_day = _utc_now().date().isoformat()
    rows_by_day, effective_days = _plan_day_rows_by_day(db_path, week_start, today_day)
    open_days = [day for day in _week_day_sequence(week_start) if day >= today_day and day not in effective_days]
    remaining_gap = max(_safe_float(week_gap.get("source_signals", {}).get("remaining_to_go")), 0.0)
    proposed_entries: list[dict[str, Any]] = []
    day_notes: list[dict[str, Any]] = []
    open_count = max(len(open_days), 1)
    for day in _week_day_sequence(week_start):
        existing = rows_by_day.get(day, [])
        if day in open_days:
            target_tss = max(remaining_gap / max(open_count, 1), 0.0)
            candidate = _day_candidate_for_target(
                owner=args.owner,
                day_utc=day,
                mode=str(args.mode or "planned").strip().lower(),
                activity_type=(str(args.activity_type).strip().lower() if args.activity_type else None),
                target_tss=target_tss,
            )
            if candidate is not None:
                proposed_entries.append(candidate)
                remaining_gap = max(remaining_gap - _safe_float(candidate.get("estimated_tss")), 0.0)
                open_count = max(open_count - 1, 1)
                day_notes.append({"day_utc": day, "status": "drafted", "existing_entries": existing})
            else:
                day_notes.append({"day_utc": day, "status": "no_candidate", "existing_entries": existing})
        else:
            day_notes.append({"day_utc": day, "status": "already_planned" if existing else "outside_window", "existing_entries": existing})
    summary = "Weekly draft created for the remaining open days."
    if not proposed_entries:
        summary = "No new week draft was needed; the remaining days are already planned or no candidates were available."
    reasoning = [
        f"Current week gap is {week_gap.get('source_signals', {}).get('remaining_to_go')} TSS against the planned compare target.",
        f"Drafted {len(proposed_entries)} remaining day entries while leaving existing planned rows untouched.",
    ]
    warnings = list(week_gap.get("warnings") or [])
    if not proposed_entries:
        warnings.append("No open days required a new draft, or no valid generated candidates were available.")
    return {
        "owner": args.owner,
        "db_path": str(db_path),
        "week_start": week_start,
        "summary": summary,
        "reasoning": reasoning,
        "proposed_entries": proposed_entries,
        "warnings": warnings,
        "source_signals": week_gap.get("source_signals"),
        "day_notes": day_notes,
        "note": "Draft outputs are canonical Temperance workout text and still require explicit apply_plan_changes to persist.",
    }


def tool_validate_workout_text(arguments: dict[str, Any]) -> dict[str, Any]:
    args = ValidateWorkoutTextArgs.model_validate(arguments or {})
    db_path = _resolve_db_path(args.owner)
    _ensure_db_ready(db_path)
    return _validate_single_workout(args.owner, db_path, args.day_utc, args.workout_text)


def tool_preview_plan_changes(arguments: dict[str, Any]) -> dict[str, Any]:
    args = PlanChangeArgs.model_validate(arguments or {})
    return _preview_changes(args.owner, args.changes, apply=False)


def tool_apply_plan_changes(arguments: dict[str, Any]) -> dict[str, Any]:
    args = PlanChangeArgs.model_validate(arguments or {})
    return _preview_changes(args.owner, args.changes, apply=True)


TOOLS: dict[str, ToolSpec] = {
    "get_today_status": ToolSpec("get_today_status", "Get latest training, recovery, weekly outlook, and freshness state for an owner.", TodayStatusArgs.model_json_schema(), tool_get_today_status),
    "get_recent_activities": ToolSpec("get_recent_activities", "List recent Temperance activities with core load metrics.", RecentActivitiesArgs.model_json_schema(), tool_get_recent_activities),
    "get_activity_detail": ToolSpec("get_activity_detail", "Return the existing Temperance activity detail payload for an activity id.", ActivityDetailArgs.model_json_schema(), tool_get_activity_detail),
    "get_week_outlook": ToolSpec("get_week_outlook", "Return the Temperance weekly outlook payload for the selected week.", WeekOutlookArgs.model_json_schema(), tool_get_week_outlook),
    "get_load_trend": ToolSpec("get_load_trend", "Summarize recent load trend using daily TSS, rTSS, and simple CTL/ATL proxies.", RecentActivitiesArgs.model_json_schema(), tool_get_load_trend),
    "get_recovery_trend": ToolSpec("get_recovery_trend", "Summarize recent recovery and wellness trend points.", OwnerArgs.model_json_schema(), tool_get_recovery_trend),
    "get_planned_activities": ToolSpec("get_planned_activities", "Return planned activity rows and weekly plan summaries.", PlannedActivitiesArgs.model_json_schema(), tool_get_planned_activities),
    "get_generated_activity_candidates": ToolSpec("get_generated_activity_candidates", "Return deterministic generated activity candidates for a target day.", GeneratedActivityCandidatesArgs.model_json_schema(), tool_get_generated_activity_candidates),
    "get_data_freshness": ToolSpec("get_data_freshness", "Report last sync, latest activity, latest recovery day, and stale-data warnings.", OwnerArgs.model_json_schema(), tool_get_data_freshness),
    "explain_day_recommendation": ToolSpec("explain_day_recommendation", "Explain what today's session should look like and why it fits the current week.", DayPlanningArgs.model_json_schema(), tool_explain_day_recommendation),
    "analyze_week_gap": ToolSpec("analyze_week_gap", "Analyze the current week's remaining load gap versus the compare target.", AnalyzeWeekGapArgs.model_json_schema(), tool_analyze_week_gap),
    "draft_week_plan": ToolSpec("draft_week_plan", "Draft Temperance workout text for the remaining open days in the selected week.", WeekPlanningArgs.model_json_schema(), tool_draft_week_plan),
    "draft_day_plan": ToolSpec("draft_day_plan", "Draft Temperance workout text for a selected day using current load and recovery signals.", DayPlanningArgs.model_json_schema(), tool_draft_day_plan),
    "validate_workout_text": ToolSpec("validate_workout_text", "Validate and normalize a Temperance workout string and estimate its metrics.", ValidateWorkoutTextArgs.model_json_schema(), tool_validate_workout_text),
    "preview_plan_changes": ToolSpec("preview_plan_changes", "Validate explicit planned-entry change operations and estimate weekly impact without writing.", PlanChangeArgs.model_json_schema(), tool_preview_plan_changes),
    "apply_plan_changes": ToolSpec("apply_plan_changes", "Apply explicit planned-entry change operations and return exactly what changed.", PlanChangeArgs.model_json_schema(), tool_apply_plan_changes),
}


def _success_response(msg_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": msg_id, "result": result}


def _error_response(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": msg_id, "error": {"code": code, "message": message}}


def _tool_result(payload: Any) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2)}],
        "structuredContent": payload,
        "isError": False,
    }


def _resource_result(resource: ResourceSpec) -> dict[str, Any]:
    text = resource.reader()
    return {
        "contents": [
            {
                "uri": resource.uri,
                "mimeType": resource.mime_type,
                "text": text,
            }
        ]
    }


def _handle_initialize(msg_id: Any) -> dict[str, Any]:
    return _success_response(
        msg_id,
        {
            "protocolVersion": SERVER_PROTOCOL_VERSION,
            "serverInfo": SERVER_INFO,
            "capabilities": {
                "tools": {},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
        },
    )


def _handle_tools_list(msg_id: Any) -> dict[str, Any]:
    return _success_response(
        msg_id,
        {
            "tools": [
                {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": spec.input_schema,
                }
                for spec in TOOLS.values()
            ]
        },
    )


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
                "content": [{"type": "text", "text": json.dumps({"error": str(exc)}, ensure_ascii=False)}],
                "structuredContent": {"error": str(exc)},
                "isError": True,
            },
        )
    return _success_response(msg_id, _tool_result(payload))


def _handle_resources_list(msg_id: Any) -> dict[str, Any]:
    return _success_response(
        msg_id,
        {
            "resources": [
                {
                    "uri": spec.uri,
                    "name": spec.name,
                    "title": spec.title,
                    "description": spec.description,
                    "mimeType": spec.mime_type,
                }
                for spec in RESOURCES.values()
            ]
        },
    )


def _handle_resources_read(msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    uri = str((params or {}).get("uri") or "").strip()
    spec = RESOURCES.get(uri)
    if spec is None:
        return _error_response(msg_id, -32602, f"Unknown resource: {uri}")
    return _success_response(msg_id, _resource_result(spec))


def _handle_prompts_list(msg_id: Any) -> dict[str, Any]:
    return _success_response(
        msg_id,
        {
            "prompts": [
                {
                    "name": spec.name,
                    "title": spec.title,
                    "description": spec.description,
                    "arguments": spec.arguments,
                }
                for spec in PROMPTS.values()
            ]
        },
    )


def _handle_prompts_get(msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = str((params or {}).get("name") or "").strip()
    spec = PROMPTS.get(name)
    if spec is None:
        return _error_response(msg_id, -32602, f"Unknown prompt: {name}")
    arguments = (params or {}).get("arguments") or {}
    return _success_response(
        msg_id,
        {
            "description": spec.description,
            "messages": spec.renderer(arguments if isinstance(arguments, dict) else {}),
        },
    )


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = str(message.get("method") or "").strip()
    msg_id = message.get("id")
    if method == "initialize":
        return _handle_initialize(msg_id)
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _success_response(msg_id, {})
    if method == "tools/list":
        return _handle_tools_list(msg_id)
    if method == "tools/call":
        return _handle_tools_call(msg_id, message.get("params") or {})
    if method == "resources/list":
        return _handle_resources_list(msg_id)
    if method == "resources/read":
        return _handle_resources_read(msg_id, message.get("params") or {})
    if method == "prompts/list":
        return _handle_prompts_list(msg_id)
    if method == "prompts/get":
        return _handle_prompts_get(msg_id, message.get("params") or {})
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
            print(json.dumps(_error_response(None, -32700, f"Parse error: {exc}"), ensure_ascii=False), flush=True)
            continue
        response = handle_message(message)
        if response is not None:
            print(json.dumps(response, default=_json_default, ensure_ascii=False), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Temperance MCP server")
    parser.add_argument("--stdio", action="store_true", help="Run the server over stdio (default).")
    parser.parse_args(argv)
    return serve_stdio()


if __name__ == "__main__":
    raise SystemExit(main())

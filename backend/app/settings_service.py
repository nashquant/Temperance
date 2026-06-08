from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temperance.db import get_setting, save_setting


def settings_view_core(db_path: Path) -> dict[str, Any]:
    """Core settings view logic shared by the HTTP endpoint and MCP tool."""
    from backend.app import main as main_module

    if_raw = get_setting(db_path, main_module.SETTINGS_KEY_IF_ZONE_THRESHOLDS)
    try:
        if_payload = json.loads(if_raw) if if_raw else None
    except Exception:
        if_payload = None
    if_thresholds = main_module._normalize_if_zone_thresholds(if_payload)
    vdot_lookback_days = main_module._load_vdot_lookback_days(db_path)

    spec_profile = main_module._load_specificity_profile(
        db_path=db_path, fallback_default=0.8
    )
    coach_preferences = main_module._load_coach_preferences(db_path)
    baseline_blend = main_module._load_baseline_blend_profile(db_path)

    lthr_curve = main_module._load_curve_points(
        db_path=db_path,
        key=main_module.SETTINGS_KEY_LTHR_CURVE,
        value_key="lthr_bpm",
        fallback_value=main_module.DEFAULT_LTHR,
    )
    lt_pace_curve = main_module._load_curve_points(
        db_path=db_path,
        key=main_module.SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=main_module.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    lthr_rows = [
        {
            "date": d.astimezone(main_module.timezone.utc).date().isoformat(),
            "lthr_bpm": round(float(v), 2),
        }
        for d, v in lthr_curve
    ]
    pace_rows = [
        {
            "date": d.astimezone(main_module.timezone.utc).date().isoformat(),
            "lt_pace_sec_per_km": round(float(v), 2),
        }
        for d, v in lt_pace_curve
    ]

    injury_rows: list[dict[str, str]] = []
    raw_injury = get_setting(db_path, main_module.SETTINGS_KEY_INJURY_WINDOWS)
    if raw_injury:
        try:
            payload = json.loads(raw_injury)
            if isinstance(payload, list):
                injury_rows = main_module._normalize_injury_windows(payload)
        except Exception:
            injury_rows = []

    race_context: dict[str, str] | None = None
    raw_race_context = get_setting(db_path, main_module.SETTINGS_KEY_RACE_CONTEXT)
    if raw_race_context:
        try:
            payload = json.loads(raw_race_context)
            normalized = main_module._normalize_race_context(payload)
            if any(normalized.values()):
                race_context = normalized
        except Exception:
            race_context = None

    return {
        "if_zone_thresholds": if_thresholds,
        "vdot_lookback_days": vdot_lookback_days,
        "specificity_profile": spec_profile,
        "coach_preferences": coach_preferences,
        "baseline_blend": baseline_blend,
        "lthr_curve": lthr_rows,
        "lt_pace_curve": pace_rows,
        "injury_windows": injury_rows,
        "training_philosophy_id": main_module._load_active_philosophy_id(db_path),
        "timezone": main_module._owner_timezone_info(db_path)[0],
        "race_context": race_context,
    }


def settings_update_core(db_path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    """Core settings update logic shared by the HTTP endpoint and MCP tool."""
    from backend.app import main as main_module

    updated: list[str] = []

    if settings.get("if_zone_thresholds") is not None:
        normalized = main_module._normalize_if_zone_thresholds(
            settings["if_zone_thresholds"]
        )
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_IF_ZONE_THRESHOLDS,
            main_module._settings_json(normalized),
        )
        updated.append("if_zone_thresholds")

    if settings.get("vdot_lookback_days") is not None:
        normalized = main_module._normalize_vdot_lookback_days(
            settings["vdot_lookback_days"]
        )
        save_setting(
            db_path, main_module.SETTINGS_KEY_VDOT_LOOKBACK_DAYS, str(int(normalized))
        )
        updated.append("vdot_lookback_days")

    if settings.get("specificity_profile") is not None:
        sp = settings["specificity_profile"]
        fallback = main_module._safe_float(sp.get("non_running")) if isinstance(sp, dict) else 0.8
        normalized = main_module._normalize_specificity_profile(
            sp, fallback_default=max(fallback, 0.1)
        )
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_ACTIVITY_SPECIFICITY,
            main_module._settings_json(normalized),
        )
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_NON_RUNNING_FACTOR,
            f"{float(normalized['non_running']):.4f}",
        )
        updated.append("specificity_profile")

    if settings.get("coach_preferences") is not None:
        normalized = main_module._normalize_coach_preferences(
            settings.get("coach_preferences"), strict=True
        )
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_COACH_PREFERENCES,
            main_module._settings_json(normalized),
        )
        updated.append("coach_preferences")

    if settings.get("baseline_blend") is not None:
        normalized = main_module._normalize_baseline_blend_profile(
            settings["baseline_blend"], strict=True
        )
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_BASELINE_BLEND,
            main_module._settings_json(normalized),
        )
        updated.append("baseline_blend")

    if settings.get("lthr_curve") is not None:
        normalized = main_module._normalize_lthr_curve(settings["lthr_curve"])
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_LTHR_CURVE,
            main_module._settings_json(normalized),
        )
        updated.append("lthr_curve")

    if settings.get("lt_pace_curve") is not None:
        normalized = main_module._normalize_lt_pace_curve(settings["lt_pace_curve"])
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_LT_PACE_CURVE,
            main_module._settings_json(normalized),
        )
        updated.append("lt_pace_curve")

    if settings.get("injury_windows") is not None:
        normalized = main_module._normalize_injury_windows(settings["injury_windows"])
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_INJURY_WINDOWS,
            main_module._settings_json(normalized),
        )
        updated.append("injury_windows")

    if settings.get("training_philosophy_id") is not None:
        from temperance.planning.philosophy import PHILOSOPHIES

        philosophy_id = str(settings["training_philosophy_id"] or "").strip()
        if philosophy_id not in PHILOSOPHIES:
            raise main_module.HTTPException(
                status_code=400,
                detail=f"Unknown philosophy_id: {philosophy_id!r}",
            )
        save_setting(db_path, main_module.SETTINGS_KEY_TRAINING_PHILOSOPHY, philosophy_id)
        updated.append("training_philosophy_id")

    if settings.get("timezone") is not None:
        normalized_timezone = str(settings["timezone"] or "").strip()
        if normalized_timezone:
            normalized_timezone = main_module._normalize_timezone_name(normalized_timezone)
        save_setting(db_path, main_module.SETTINGS_KEY_USER_TIMEZONE, normalized_timezone)
        updated.append("timezone")

    if settings.get("race_context") is not None:
        normalized = main_module._normalize_race_context(
            settings["race_context"], strict=True
        )
        save_setting(
            db_path,
            main_module.SETTINGS_KEY_RACE_CONTEXT,
            main_module._settings_json(normalized),
        )
        updated.append("race_context")

    return {"updated": updated}

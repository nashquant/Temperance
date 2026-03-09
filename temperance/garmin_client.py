from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from fitparse import FitFile
except Exception:  # pragma: no cover
    FitFile = None


@dataclass
class GarminExtractResult:
    activities: list[dict[str, Any]]
    activity_details: list[dict[str, Any]]
    activity_records: list[dict[str, Any]]
    activity_splits: list[dict[str, Any]]
    sleep_daily: list[dict[str, Any]]
    wellness_daily: list[dict[str, Any]]
    errors: list[str]


def _to_iso_utc(value: str | datetime) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _safe_call(fn: Callable[..., Any], *args: Any) -> tuple[Any, str | None]:
    try:
        return fn(*args), None
    except Exception as exc:  # pragma: no cover
        return None, str(exc)


def _safe_call_method(
    client: Any,
    method_names: tuple[str, ...],
    *args: Any,
) -> tuple[Any, str | None, str | None]:
    for method_name in method_names:
        method = getattr(client, method_name, None)
        if method is None:
            continue
        payload, err = _safe_call(method, *args)
        return payload, err, method_name
    return None, None, None


def _safe_call_method_with_variants(
    client: Any,
    method_name: str,
    arg_variants: list[tuple[Any, ...]],
) -> tuple[Any, str | None]:
    method = getattr(client, method_name, None)
    if method is None:
        return None, None

    last_err: str | None = None
    for args in arg_variants:
        payload, err = _safe_call(method, *args)
        if err is None:
            return payload, None
        last_err = err
    return None, last_err


def _iter_days(start: date, end: date) -> list[date]:
    days = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _deep_first(data: Any, keys: set[str]) -> Any:
    if isinstance(data, dict):
        for k, v in data.items():
            if k in keys and v is not None:
                return v
            nested = _deep_first(v, keys)
            if nested is not None:
                return nested
    elif isinstance(data, list):
        for item in data:
            nested = _deep_first(item, keys)
            if nested is not None:
                return nested
    return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _extract_numeric(value: Any) -> float | None:
    direct = _to_float(value)
    if direct is not None:
        return direct
    if isinstance(value, dict):
        for key in (
            "value",
            "score",
            "overallSleepScore",
            "sleepScore",
            "seconds",
            "duration",
            "totalSeconds",
        ):
            nested = _to_float(value.get(key))
            if nested is not None:
                return nested
        nested_any = _deep_first(
            value,
            {"value", "score", "overallSleepScore", "sleepScore", "seconds", "duration", "totalSeconds"},
        )
        return _to_float(nested_any)
    if isinstance(value, list) and len(value) == 1:
        return _extract_numeric(value[0])
    return None


def _first_numeric(data: Any, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        raw = _deep_first(data, {key})
        val = _extract_numeric(raw)
        if val is not None:
            return val
    return None


def _is_running_activity(sport_type: str | None) -> bool:
    if not sport_type:
        return False
    lower = sport_type.lower()
    return "run" in lower or "treadmill" in lower


def _extract_sport_type(a: dict[str, Any]) -> str:
    activity_type = a.get("activityType")
    if isinstance(activity_type, dict):
        return str(activity_type.get("typeKey") or activity_type.get("typeId") or "unknown")
    return str(a.get("typeKey") or activity_type or "unknown")


def _extract_device_name(a: dict[str, Any], details_bundle: dict[str, Any] | None = None) -> str | None:
    return _to_str(
        a.get("deviceName")
        or _deep_first(a, {"deviceName", "productName"})
        or _deep_first(details_bundle or {}, {"deviceName", "productName"})
    )


def _extract_stamina_values(summary: dict[str, Any], details_bundle: dict[str, Any] | None) -> tuple[float | None, float | None]:
    combined = {"summary": summary, "details": details_bundle or {}}
    stamina_start = _to_float(
        _deep_first(combined, {"staminaStart", "startStamina", "stamina_start", "staminaBefore"})
    )
    stamina_end = _to_float(
        _deep_first(combined, {"staminaEnd", "endStamina", "stamina_end", "staminaAfter", "remainingStamina"})
    )
    return stamina_start, stamina_end


def _normalize_activity(
    a: dict[str, Any],
    source: str = "garmin_api",
    details_bundle: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    activity_id = a.get("activityId")
    if not activity_id:
        return None

    start_time = a.get("startTimeGMT") or a.get("startTimeLocal")
    if not start_time:
        return None

    sport_type = _extract_sport_type(a)
    distance_m = _to_float(a.get("distance")) or 0.0
    duration_s = _to_float(a.get("duration") or a.get("movingDuration")) or 0.0

    avg_pace_s_per_km = None
    if distance_m > 0 and duration_s > 0:
        avg_pace_s_per_km = duration_s / (distance_m / 1000.0)

    stamina_start, stamina_end = _extract_stamina_values(a, details_bundle)
    activity_type = a.get("activityType") if isinstance(a.get("activityType"), dict) else {}
    split_summaries = a.get("splitSummaries")
    training_load_field_name = None
    training_load_value = None
    for field in ("activityTrainingLoad", "trainingLoad", "exerciseTrainingLoad"):
        v = _to_float(a.get(field))
        if v is not None:
            training_load_field_name = field
            training_load_value = v
            break
    calories_total = _to_float(a.get("calories") or a.get("totalCalories"))
    calories_active = _to_float(a.get("activeKilocalories") or a.get("activeCalories"))
    if calories_active is None and calories_total is not None:
        bmr = _to_float(a.get("bmrCalories"))
        calories_active = calories_total - bmr if bmr is not None else calories_total

    return {
        "activity_id": str(activity_id),
        "start_time_utc": _to_iso_utc(start_time),
        "sport_type": sport_type,
        "distance_m": distance_m,
        "duration_s": duration_s,
        "avg_hr": _to_float(a.get("averageHR") or a.get("averageHeartRate")),
        "max_hr": _to_float(a.get("maxHR") or a.get("maxHeartRate")),
        "avg_pace_s_per_km": avg_pace_s_per_km,
        "elevation_gain_m": _to_float(a.get("elevationGain") or a.get("totalAscent")),
        "elevation_loss_m": _to_float(a.get("elevationLoss") or a.get("totalDescent")),
        "avg_cadence": _to_float(
            a.get("averageRunCadence")
            or a.get("averageCadence")
            or a.get("averageRunningCadenceInStepsPerMinute")
        ),
        "max_cadence": _to_float(
            a.get("maxRunCadence")
            or a.get("maxCadence")
            or a.get("maxRunningCadenceInStepsPerMinute")
            or a.get("maxDoubleCadence")
        ),
        "avg_stride_length": _to_float(a.get("avgStrideLength") or a.get("averageStrideLength")),
        "vertical_ratio": _to_float(a.get("verticalRatio") or a.get("avgVerticalRatio")),
        "vertical_oscillation": _to_float(a.get("verticalOscillation") or a.get("avgVerticalOscillation")),
        "running_power_avg": _to_float(a.get("avgPower") or a.get("averagePower")),
        "running_power_max": _to_float(a.get("maxPower")),
        "stamina_start": stamina_start,
        "stamina_end": stamina_end,
        "training_effect_aerobic": _to_float(a.get("aerobicTrainingEffect")),
        "training_effect_anaerobic": _to_float(a.get("anaerobicTrainingEffect")),
        "performance_condition": _to_float(
            a.get("performanceCondition") or _deep_first(a, {"avgPerformanceCondition", "performanceCondition"})
        ),
        "device_name": _extract_device_name(a, details_bundle),
        "manufacturer": _to_str(a.get("manufacturer")),
        "activity_uuid": _to_str(a.get("activityUUID")),
        "owner_id": _to_str(a.get("ownerId")),
        "owner_full_name": _to_str(a.get("ownerFullName")),
        "elapsed_duration_s": _to_float(a.get("elapsedDuration")),
        "moving_duration_s": _to_float(a.get("movingDuration")),
        "average_speed_mps": _to_float(a.get("averageSpeed")),
        "activity_type_key": _to_str(activity_type.get("typeKey")),
        "activity_type_id": _to_float(activity_type.get("typeId")),
        "hr_time_in_zone_1": _to_float(a.get("hrTimeInZone_1")),
        "hr_time_in_zone_2": _to_float(a.get("hrTimeInZone_2")),
        "hr_time_in_zone_3": _to_float(a.get("hrTimeInZone_3")),
        "hr_time_in_zone_4": _to_float(a.get("hrTimeInZone_4")),
        "hr_time_in_zone_5": _to_float(a.get("hrTimeInZone_5")),
        "difference_body_battery": _to_float(a.get("differenceBodyBattery")),
        "bmr_calories": _to_float(a.get("bmrCalories")),
        "is_pr": _to_float(a.get("pr")),
        "split_summaries_json": json.dumps(split_summaries, default=str) if split_summaries is not None else None,
        "training_load_garmin": training_load_value,
        "training_load_garmin_field_name": training_load_field_name,
        "training_load_garmin_units": "load_points" if training_load_value is not None else None,
        "calories_active": calories_active,
        "calories_total": calories_total,
        "intensity_minutes_vigorous": _to_float(a.get("vigorousIntensityMinutes")),
        "intensity_minutes_moderate": _to_float(a.get("moderateIntensityMinutes")),
        "trimp": None,
        "source": source,
        "raw": a,
    }


def _extract_sleep_row(day: date, sleep_data: dict[str, Any] | None) -> dict[str, Any]:
    blob = sleep_data or {}
    daily_sleep = blob.get("dailySleepDTO") if isinstance(blob.get("dailySleepDTO"), dict) else {}
    sleep_scores = daily_sleep.get("sleepScores") if isinstance(daily_sleep.get("sleepScores"), dict) else {}
    overall_sleep = sleep_scores.get("overall") if isinstance(sleep_scores.get("overall"), dict) else {}
    return {
        "day_utc": day.isoformat(),
        "sleep_score": (
            _to_float(overall_sleep.get("value"))
            or _first_numeric(blob, ("overallSleepScore", "sleepScore", "overallScore", "score"))
        ),
        "sleep_duration_s": _first_numeric(blob, ("sleepTimeSeconds", "totalSleepSeconds")),
        "deep_sleep_s": _first_numeric(blob, ("deepSleepSeconds", "deepSleepDuration")),
        "rem_sleep_s": _first_numeric(blob, ("remSleepSeconds", "remSleepDuration")),
        "light_sleep_s": _first_numeric(blob, ("lightSleepSeconds", "lightSleepDuration")),
        "awake_s": _first_numeric(blob, ("awakeSleepSeconds", "awakeTimeSeconds", "awakeDuration")),
        "sleep_start_utc": _to_str(_deep_first(blob, {"sleepStartTimestampGMT", "sleepStartTimestamp"})),
        "sleep_end_utc": _to_str(_deep_first(blob, {"sleepEndTimestampGMT", "sleepEndTimestamp"})),
        "raw": blob,
    }


def _extract_wellness_row(
    day: date,
    body_battery: list[dict[str, Any]] | None,
    stress: dict[str, Any] | None,
    hrv: dict[str, Any] | None,
    rhr: dict[str, Any] | None,
    readiness: dict[str, Any] | None,
    stats_body: dict[str, Any] | None,
    respiration: dict[str, Any] | None,
    intensity_minutes: dict[str, Any] | None,
    steps_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    battery_values: list[float] = []
    for row in body_battery or []:
        val = _to_float(row.get("bodyBattery") or row.get("bodyBatteryLevel"))
        if val is not None:
            battery_values.append(val)
        series = row.get("bodyBatteryValuesArray")
        if isinstance(series, list):
            for sample in series:
                if not isinstance(sample, (list, tuple)) or len(sample) < 2:
                    continue
                sample_val = _to_float(sample[1])
                if sample_val is not None:
                    battery_values.append(sample_val)

    stats = stats_body or {}
    stress_values: list[float] = []
    for k in ("averageStressLevel", "avgStressLevel", "overallStressLevel"):
        val = _to_float(_deep_first(stress or {}, {k}))
        if val is not None:
            stress_values.append(val)

    stress_max = _to_float(_deep_first(stress or {}, {"maxStressLevel", "highestStressLevel"}))
    if stress_max is None and stress_values:
        stress_max = max(stress_values)

    intensity_value = _to_float(
        _deep_first(intensity_minutes or {}, {"intensityMinutes", "totalIntensityMinutes", "totalDurationMinutes"})
        or _deep_first(stats, {"moderateIntensityMinutes", "vigorousIntensityMinutes", "intensityMinutes"})
    )

    return {
        "day_utc": day.isoformat(),
        "resting_hr": (
            _first_numeric(rhr, ("restingHeartRate", "allDayRestingHeartRate", "value"))
            or _first_numeric(stats, ("restingHeartRate", "allDayRestingHeartRate"))
            or _extract_numeric(rhr)
        ),
        "hrv_status": _first_numeric(hrv, ("weeklyAvg", "lastNightAvg", "hrvValue", "value")),
        "training_readiness": _first_numeric(readiness, ("trainingReadinessScore", "score", "value")),
        "stress_avg": _first_numeric(stress, ("averageStressLevel", "avgStressLevel", "overallStressLevel")),
        "stress_max": stress_max,
        "body_battery_start": battery_values[0] if battery_values else None,
        "body_battery_end": battery_values[-1] if battery_values else None,
        "body_battery_avg": (sum(battery_values) / len(battery_values)) if battery_values else None,
        "respiration_avg": _first_numeric(
            respiration,
            ("avgWakingRespirationValue", "avgRespirationValue", "averageRespiration", "value"),
        ),
        "steps": _to_float(
            _deep_first(stats, {"totalSteps", "steps"})
            or _deep_first(steps_payload or {}, {"totalSteps", "steps"})
        ),
        "intensity_minutes": intensity_value,
        "calories_total": _to_float(_deep_first(stats, {"totalKilocalories", "totalCalories", "activeKilocalories"})),
        "raw": {
            "body_battery": body_battery,
            "stress": stress,
            "hrv": hrv,
            "rhr": rhr,
            "training_readiness": readiness,
            "stats_and_body": stats_body,
            "respiration": respiration,
            "intensity_minutes": intensity_minutes,
            "steps": steps_payload,
        },
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _archive_activity_payload(raw_root: Path | None, activity_id: str, name: str, payload: Any) -> None:
    if raw_root is None:
        return
    _write_json(raw_root / "activities" / str(activity_id) / f"{name}.json", payload)


def _archive_daily_payload(raw_root: Path | None, day: str, name: str, payload: Any) -> None:
    if raw_root is None:
        return
    _write_json(raw_root / "daily" / day / f"{name}.json", payload)


def _download_fit_if_missing(client: Any, activity_id: str, raw_root: Path | None) -> tuple[Path | None, str | None]:
    if raw_root is None:
        return None, None

    fit_path = raw_root / "fit" / f"{activity_id}.fit"
    if fit_path.exists():
        return fit_path, None

    fit_path.parent.mkdir(parents=True, exist_ok=True)

    attempts: list[Callable[[], Any]] = []
    if hasattr(client, "download_activity"):
        attempts.append(lambda: client.download_activity(int(activity_id), dl_fmt="fit"))
    if hasattr(client, "download_original_activity"):
        attempts.append(lambda: client.download_original_activity(int(activity_id)))

    last_error: str | None = None
    for attempt in attempts:
        payload, err = _safe_call(attempt)
        if err:
            # Some garminconnect versions do not support FIT download via dl_fmt.
            # Treat this as "not available" instead of surfacing noisy per-activity errors.
            if "Unexpected value fit for dl_fmt" in err:
                return None, None
            last_error = err
            continue

        if payload is None:
            continue

        try:
            if isinstance(payload, bytes):
                fit_path.write_bytes(payload)
                return fit_path, None

            if hasattr(payload, "read"):
                fit_path.write_bytes(payload.read())
                return fit_path, None

            if isinstance(payload, str):
                fit_path.write_text(payload, encoding="utf-8")
                return fit_path, None
        except Exception as write_err:  # pragma: no cover
            last_error = str(write_err)

    return None, last_error


def _extract_fit_session(path: Path) -> dict[str, Any] | None:
    if FitFile is None:
        return None

    fit_file = FitFile(path)
    for msg in fit_file.get_messages("session"):
        return {field.name: field.value for field in msg}
    return None


def _parse_fit_records(path: Path, activity_id: str) -> list[dict[str, Any]]:
    if FitFile is None:
        return []

    fit_file = FitFile(path)
    records: list[dict[str, Any]] = []

    for msg in fit_file.get_messages("record"):
        row = {field.name: field.value for field in msg}
        timestamp = row.get("timestamp")
        if not timestamp:
            continue

        stamina = None
        for key, value in row.items():
            if "stamina" in str(key).lower():
                stamina = _to_float(value)
                if stamina is not None:
                    break

        records.append(
            {
                "activity_id": activity_id,
                "record_time_utc": _to_iso_utc(timestamp),
                "heart_rate": _to_float(row.get("heart_rate")),
                "cadence": _to_float(row.get("cadence")),
                "step_length": _to_float(row.get("step_length")),
                "stride_length": _to_float(row.get("stride_length")),
                "vertical_ratio": _to_float(row.get("vertical_ratio")),
                "vertical_oscillation": _to_float(row.get("vertical_oscillation")),
                "power": _to_float(row.get("power")),
                "grade": _to_float(row.get("grade")),
                "altitude": _to_float(row.get("altitude") or row.get("enhanced_altitude")),
                "speed": _to_float(row.get("speed") or row.get("enhanced_speed")),
                "distance": _to_float(row.get("distance") or row.get("enhanced_distance")),
                "stamina": stamina,
                "raw": row,
            }
        )

    return records


def _merge_session_into_activity(activity: dict[str, Any], session_data: dict[str, Any] | None) -> dict[str, Any]:
    if not session_data:
        return activity

    merged = dict(activity)

    # Fill only when API summary did not provide the value.
    fallback_map: dict[str, tuple[str, ...]] = {
        "avg_cadence": ("avg_cadence", "enhanced_avg_running_cadence", "avg_running_cadence"),
        "max_cadence": ("max_cadence", "enhanced_max_running_cadence", "max_running_cadence"),
        "avg_stride_length": ("avg_step_length", "step_length"),
        "vertical_ratio": ("avg_vertical_ratio", "vertical_ratio"),
        "vertical_oscillation": ("avg_vertical_oscillation", "vertical_oscillation"),
        "running_power_avg": ("avg_power", "enhanced_avg_power"),
        "running_power_max": ("max_power",),
        "elevation_gain_m": ("total_ascent",),
        "elevation_loss_m": ("total_descent",),
    }

    for key, fit_keys in fallback_map.items():
        if merged.get(key) is not None:
            continue
        for fit_key in fit_keys:
            value = _to_float(session_data.get(fit_key))
            if value is not None:
                merged[key] = value
                break

    if merged.get("device_name") is None:
        merged["device_name"] = _to_str(session_data.get("device_name") or session_data.get("manufacturer"))

    if merged.get("stamina_start") is None:
        merged["stamina_start"] = _to_float(session_data.get("stamina_start"))
    if merged.get("stamina_end") is None:
        merged["stamina_end"] = _to_float(session_data.get("stamina_end") or session_data.get("remaining_stamina"))

    return merged


def _parse_split_payload(split_payload: Any, split_summaries_payload: Any, activity_id: str) -> dict[str, Any]:
    laps: list[dict[str, Any]] = []
    if isinstance(split_payload, dict):
        lap_rows = split_payload.get("lapDTOs")
        if isinstance(lap_rows, list):
            laps = [x for x in lap_rows if isinstance(x, dict)]

    # Fall back to split summaries if lapDTOs are unavailable.
    if not laps and isinstance(split_summaries_payload, list):
        laps = [x for x in split_summaries_payload if isinstance(x, dict)]
    elif not laps and isinstance(split_summaries_payload, dict):
        maybe = split_summaries_payload.get("splitSummaries")
        if isinstance(maybe, list):
            laps = [x for x in maybe if isinstance(x, dict)]

    total_duration_s = 0.0
    total_distance_m = 0.0
    lap_count = float(len(laps))

    for lap in laps:
        d = _to_float(
            lap.get("duration")
            or lap.get("elapsedDuration")
            or lap.get("movingDuration")
            or lap.get("totalTimerTime")
        )
        if d is not None and d > 0:
            total_duration_s += d
        dist = _to_float(lap.get("distance") or lap.get("totalDistance") or lap.get("distanceMeters"))
        if dist is not None and dist > 0:
            total_distance_m += dist

    return {
        "activity_id": str(activity_id),
        "split": split_payload,
        "split_summaries": split_summaries_payload,
        "lap_count": lap_count if lap_count > 0 else None,
        "total_duration_s": total_duration_s if total_duration_s > 0 else None,
        "total_distance_m": total_distance_m if total_distance_m > 0 else None,
    }


def fetch_garmin_runs(
    email: str,
    password: str,
    days_back: int = 90,
    since_utc: datetime | None = None,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Backward-compatible run fetch used by the simple sync path."""
    end_day = datetime.now(timezone.utc).date()
    start_day = end_day - timedelta(days=days_back)
    if since_utc:
        start_day = max(start_day, (since_utc - timedelta(days=2)).date())

    result = fetch_garmin_comprehensive(
        email=email,
        password=password,
        start_day=start_day,
        end_day=end_day,
        include_activity_details=False,
        include_wellness=False,
        page_size=100,
        raw_export_dir=None,
        progress_cb=progress_cb,
    )
    return [a for a in result.activities if _is_running_activity(a.get("sport_type"))]


def fetch_garmin_comprehensive(
    email: str,
    password: str,
    start_day: date,
    end_day: date | None = None,
    include_activity_details: bool = True,
    include_splits: bool = False,
    include_wellness: bool = True,
    page_size: int = 100,
    raw_export_dir: Path | None = None,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
) -> GarminExtractResult:
    """
    Pull a broad local archive from Garmin with incremental behavior:
    - activity summaries in date range
    - optional per-activity detail endpoints
    - optional per-activity FIT download + time-series parsing
    - optional daily sleep/wellness endpoints
    - raw endpoint payload archival to disk for rebuilds
    """
    from garminconnect import Garmin

    end_day = end_day or datetime.now(timezone.utc).date()

    def _progress(payload: dict[str, Any]) -> None:
        if progress_cb is None:
            return
        try:
            progress_cb(payload)
        except Exception:
            return

    client = Garmin(email=email, password=password)
    client.login()

    errors: list[str] = []
    activities: list[dict[str, Any]] = []
    activity_details: list[dict[str, Any]] = []
    activity_records: list[dict[str, Any]] = []
    activity_splits: list[dict[str, Any]] = []

    def _count_activities_in_window() -> int:
        total = 0
        probe_offset = 0
        while True:
            probe_batch, probe_err = _safe_call(client.get_activities, probe_offset, page_size)
            if probe_err:
                return 0
            probe_rows = probe_batch or []
            if not probe_rows:
                break
            keep = True
            for probe_row in probe_rows:
                normalized = _normalize_activity(probe_row, source="garmin_api")
                if not normalized:
                    continue
                start_dt = datetime.fromisoformat(normalized["start_time_utc"].replace("Z", "+00:00"))
                day = start_dt.date()
                if day < start_day:
                    keep = False
                    continue
                if day > end_day:
                    continue
                total += 1
            probe_offset += page_size
            if not keep:
                break
        return total

    total_activities_target = _count_activities_in_window()

    offset = 0
    effective_page_size = 25 if (include_activity_details or include_splits) else page_size
    processed_activities = 0
    total_days = max((end_day - start_day).days + 1, 1)
    _progress(
        {
            "phase": "activities",
            "message": "Fetching activity summaries",
            "fraction": 0.0,
            "total_days": total_days,
        }
    )
    while True:
        batch, err = _safe_call(client.get_activities, offset, effective_page_size)
        if err:
            raise RuntimeError(f"Garmin activities fetch failed at offset {offset}: {err}") from None

        rows = batch or []
        if not rows:
            break

        keep_going = True
        oldest_in_batch: date | None = None

        for row in rows:
            normalized = _normalize_activity(row, source="garmin_api")
            if not normalized:
                continue

            start_dt = datetime.fromisoformat(normalized["start_time_utc"].replace("Z", "+00:00"))
            day = start_dt.date()
            oldest_in_batch = day if oldest_in_batch is None else min(oldest_in_batch, day)

            if day < start_day:
                keep_going = False
                continue
            if day > end_day:
                continue
            processed_activities += 1
            fraction_live = min(max(((end_day - max(day, start_day)).days + 1) / float(total_days), 0.0), 1.0)
            _progress(
                {
                    "phase": "activities",
                    "message": "Processing activity details/FIT",
                    "fraction": fraction_live,
                    "oldest_in_batch": day.isoformat(),
                    "day": day.isoformat(),
                    "offset": offset,
                    "processed": processed_activities,
                    "fetched": len(activities) + 1,
                    "total": total_activities_target,
                }
            )

            activity_id = normalized["activity_id"]
            _archive_activity_payload(raw_export_dir, activity_id, "summary", row)

            details_bundle: dict[str, Any] | None = None
            if include_activity_details:
                details_bundle = {}
                for endpoint_name, method_name in (
                    ("details", "get_activity_details"),
                    ("weather", "get_activity_weather"),
                    ("hr_timezones", "get_activity_hr_in_timezones"),
                ):
                    method = getattr(client, method_name, None)
                    if method is None:
                        continue
                    payload, call_err = _safe_call(method, int(activity_id))
                    if call_err:
                        errors.append(f"activity_id={activity_id} {endpoint_name}: {call_err}")
                    details_bundle[endpoint_name] = payload
                    _archive_activity_payload(raw_export_dir, activity_id, endpoint_name, payload)

                activity_details.append(
                    {
                        "activity_id": activity_id,
                        "details": details_bundle,
                    }
                )

            if include_splits:
                split_payload = None
                split_summaries_payload = None
                for endpoint_name, method_name in (
                    ("splits", "get_activity_splits"),
                    ("split_summaries", "get_activity_split_summaries"),
                ):
                    method = getattr(client, method_name, None)
                    if method is None:
                        continue
                    payload, call_err = _safe_call(method, int(activity_id))
                    if call_err:
                        errors.append(f"activity_id={activity_id} {endpoint_name}: {call_err}")
                    if endpoint_name == "splits":
                        split_payload = payload
                    else:
                        split_summaries_payload = payload
                    _archive_activity_payload(raw_export_dir, activity_id, endpoint_name, payload)
                activity_splits.append(
                    _parse_split_payload(split_payload, split_summaries_payload, activity_id)
                )

            normalized = _normalize_activity(row, source="garmin_api", details_bundle=details_bundle) or normalized

            fit_path, fit_err = _download_fit_if_missing(client, activity_id, raw_export_dir)
            if fit_err:
                errors.append(f"activity_id={activity_id} fit_download: {fit_err}")

            if fit_path and fit_path.exists():
                try:
                    session_data = _extract_fit_session(fit_path)
                    normalized = _merge_session_into_activity(normalized, session_data)
                    if _is_running_activity(normalized.get("sport_type")):
                        activity_records.extend(_parse_fit_records(fit_path, activity_id))
                except Exception as parse_err:
                    errors.append(f"activity_id={activity_id} fit_parse: {parse_err}")

            activities.append(normalized)

        offset += effective_page_size
        if oldest_in_batch:
            clamped_oldest = max(oldest_in_batch, start_day)
            covered_days = max((end_day - clamped_oldest).days + 1, 0)
            fraction = min(max(covered_days / float(total_days), 0.0), 1.0)
            _progress(
                {
                    "phase": "activities",
                    "message": "Fetching activity summaries",
                    "fraction": fraction,
                    "oldest_in_batch": clamped_oldest.isoformat(),
                    "day": clamped_oldest.isoformat(),
                    "offset": offset,
                    "processed": processed_activities,
                    "fetched": len(activities),
                    "total": total_activities_target,
                }
            )
        if not keep_going:
            break
        if oldest_in_batch and oldest_in_batch < start_day:
            break

    # Deduplicate by activity_id in case APIs return overlapping windows.
    activities = list({row["activity_id"]: row for row in activities}.values())
    activity_details = list({row["activity_id"]: row for row in activity_details}.values())
    activity_records = list(
        {
            (row["activity_id"], row["record_time_utc"]): row
            for row in activity_records
            if row.get("record_time_utc")
        }.values()
    )
    activity_splits = list({row["activity_id"]: row for row in activity_splits}.values())

    sleep_daily: list[dict[str, Any]] = []
    wellness_daily: list[dict[str, Any]] = []

    if include_wellness:
        days = _iter_days(start_day, end_day)
        total_wellness_days = len(days)
        _progress(
            {
                "phase": "wellness",
                "message": "Fetching daily wellness endpoints",
                "current": 0,
                "total": total_wellness_days,
                "fraction": 0.0,
            }
        )
        for idx, day in enumerate(days, start=1):
            cdate = day.isoformat()

            sleep_data, sleep_err, _ = _safe_call_method(client, ("get_sleep_data",), cdate)
            if sleep_err:
                errors.append(f"date={cdate} sleep: {sleep_err}")
            _archive_daily_payload(raw_export_dir, cdate, "sleep", sleep_data)
            sleep_daily.append(_extract_sleep_row(day, sleep_data))

            body_battery, bb_err, _ = _safe_call_method(client, ("get_body_battery",), cdate)
            stress, stress_err, _ = _safe_call_method(client, ("get_all_day_stress",), cdate)
            hrv, hrv_err, _ = _safe_call_method(client, ("get_hrv_data",), cdate)
            rhr, rhr_err, _ = _safe_call_method(client, ("get_rhr_day",), cdate)
            readiness, read_err, _ = _safe_call_method(client, ("get_training_readiness",), cdate)
            stats_body, stats_err, _ = _safe_call_method(client, ("get_stats_and_body",), cdate)
            respiration, resp_err, _ = _safe_call_method(
                client,
                ("get_respiration_data", "get_daily_respiration_data", "get_respiration"),
                cdate,
            )
            intensity, intensity_err, _ = _safe_call_method(
                client,
                ("get_intensity_minutes_data", "get_intensity_minutes"),
                cdate,
            )
            steps_data = None
            steps_err = None
            # Different garminconnect versions expose either one-day or start/end signatures.
            if hasattr(client, "get_daily_steps"):
                steps_data, steps_err = _safe_call_method_with_variants(
                    client,
                    "get_daily_steps",
                    [(cdate,), (cdate, cdate)],
                )
            if steps_data is None and hasattr(client, "get_steps_data"):
                steps_data, steps_err = _safe_call_method_with_variants(
                    client,
                    "get_steps_data",
                    [(cdate,), (cdate, cdate)],
                )

            for label, err in (
                ("body_battery", bb_err),
                ("stress", stress_err),
                ("hrv", hrv_err),
                ("rhr", rhr_err),
                ("training_readiness", read_err),
                ("stats_and_body", stats_err),
                ("respiration", resp_err),
                ("intensity_minutes", intensity_err),
                ("steps", steps_err),
            ):
                if err:
                    errors.append(f"date={cdate} {label}: {err}")

            _archive_daily_payload(raw_export_dir, cdate, "body_battery", body_battery)
            _archive_daily_payload(raw_export_dir, cdate, "stress", stress)
            _archive_daily_payload(raw_export_dir, cdate, "hrv", hrv)
            _archive_daily_payload(raw_export_dir, cdate, "resting_hr", rhr)
            _archive_daily_payload(raw_export_dir, cdate, "training_readiness", readiness)
            _archive_daily_payload(raw_export_dir, cdate, "stats_and_body", stats_body)
            _archive_daily_payload(raw_export_dir, cdate, "respiration", respiration)
            _archive_daily_payload(raw_export_dir, cdate, "intensity_minutes", intensity)
            _archive_daily_payload(raw_export_dir, cdate, "steps", steps_data)

            wellness_daily.append(
                _extract_wellness_row(
                    day=day,
                    body_battery=body_battery,
                    stress=stress,
                    hrv=hrv,
                    rhr=rhr,
                    readiness=readiness,
                    stats_body=stats_body,
                    respiration=respiration,
                    intensity_minutes=intensity,
                    steps_payload=steps_data,
                )
            )
            _progress(
                {
                    "phase": "wellness",
                    "message": "Fetching daily wellness endpoints",
                    "current": idx,
                    "total": total_wellness_days,
                    "fraction": (idx / float(total_wellness_days)) if total_wellness_days else 1.0,
                    "day": cdate,
                }
            )

    _progress({"phase": "complete", "message": "Fetch completed", "fraction": 1.0})

    return GarminExtractResult(
        activities=activities,
        activity_details=activity_details,
        activity_records=activity_records,
        activity_splits=activity_splits,
        sleep_daily=sleep_daily,
        wellness_daily=wellness_daily,
        errors=errors,
    )


def import_runs_from_folder(import_dir: Path, days_back: int = 90) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    results: list[dict[str, Any]] = []

    if not import_dir.exists():
        return []

    for path in sorted(import_dir.rglob("*")):
        if path.suffix.lower() == ".tcx":
            record = _parse_tcx(path)
        elif path.suffix.lower() == ".fit":
            record = _parse_fit(path)
        else:
            record = None

        if not record:
            continue

        start_dt = datetime.fromisoformat(record["start_time_utc"].replace("Z", "+00:00"))
        if start_dt >= cutoff:
            results.append(record)

    deduped = {a["activity_id"]: a for a in results}
    return list(deduped.values())


def _parse_tcx(path: Path) -> dict[str, Any] | None:
    ns = {
        "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    }
    root = ET.parse(path).getroot()
    activity = root.find(".//tcx:Activity", ns)
    if activity is None:
        return None

    sport = (activity.get("Sport") or "").lower()
    if "running" not in sport:
        return None

    id_node = activity.find("tcx:Id", ns)
    start_time_utc = id_node.text if id_node is not None else None
    if not start_time_utc:
        return None

    laps = activity.findall("tcx:Lap", ns)
    distance_m = 0.0
    duration_s = 0.0
    avg_hr_values: list[float] = []
    max_hr_values: list[float] = []

    for lap in laps:
        dist = lap.find("tcx:DistanceMeters", ns)
        dur = lap.find("tcx:TotalTimeSeconds", ns)
        avg_hr = lap.find("tcx:AverageHeartRateBpm/tcx:Value", ns)
        max_hr = lap.find("tcx:MaximumHeartRateBpm/tcx:Value", ns)

        distance_m += float(dist.text) if dist is not None and dist.text else 0.0
        duration_s += float(dur.text) if dur is not None and dur.text else 0.0

        if avg_hr is not None and avg_hr.text:
            avg_hr_values.append(float(avg_hr.text))
        if max_hr is not None and max_hr.text:
            max_hr_values.append(float(max_hr.text))

    if distance_m <= 0 or duration_s <= 0:
        return None

    avg_pace = duration_s / (distance_m / 1000.0)
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]

    return {
        "activity_id": f"tcx_{digest}_{start_time_utc}",
        "start_time_utc": _to_iso_utc(start_time_utc),
        "sport_type": "running",
        "distance_m": distance_m,
        "duration_s": duration_s,
        "avg_hr": sum(avg_hr_values) / len(avg_hr_values) if avg_hr_values else None,
        "max_hr": max(max_hr_values) if max_hr_values else None,
        "avg_pace_s_per_km": avg_pace,
        "elevation_gain_m": None,
        "elevation_loss_m": None,
        "avg_cadence": None,
        "max_cadence": None,
        "avg_stride_length": None,
        "vertical_ratio": None,
        "vertical_oscillation": None,
        "running_power_avg": None,
        "running_power_max": None,
        "stamina_start": None,
        "stamina_end": None,
        "training_effect_aerobic": None,
        "training_effect_anaerobic": None,
        "performance_condition": None,
        "device_name": None,
        "manufacturer": None,
        "activity_uuid": None,
        "owner_id": None,
        "owner_full_name": None,
        "elapsed_duration_s": None,
        "moving_duration_s": None,
        "average_speed_mps": None,
        "activity_type_key": "running",
        "activity_type_id": None,
        "hr_time_in_zone_1": None,
        "hr_time_in_zone_2": None,
        "hr_time_in_zone_3": None,
        "hr_time_in_zone_4": None,
        "hr_time_in_zone_5": None,
        "difference_body_battery": None,
        "bmr_calories": None,
        "is_pr": None,
        "split_summaries_json": None,
        "training_load_garmin": None,
        "training_load_garmin_field_name": None,
        "training_load_garmin_units": None,
        "calories_active": None,
        "calories_total": None,
        "intensity_minutes_vigorous": None,
        "intensity_minutes_moderate": None,
        "trimp": None,
        "source": "file_import",
        "raw": {"file": str(path), "format": "tcx"},
    }


def _parse_fit(path: Path) -> dict[str, Any] | None:
    if FitFile is None:
        return None

    session_data = _extract_fit_session(path) or {}

    sport = str(session_data.get("sport") or "").lower()
    sub_sport = str(session_data.get("sub_sport") or "").lower()
    if "run" not in sport and "run" not in sub_sport:
        return None

    distance_m = float(session_data.get("total_distance") or 0.0)
    duration_s = float(session_data.get("total_elapsed_time") or 0.0)
    start_time = session_data.get("start_time") or session_data.get("timestamp")

    if distance_m <= 0 or duration_s <= 0 or not start_time:
        return None

    avg_pace = duration_s / (distance_m / 1000.0)
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]

    return {
        "activity_id": f"fit_{digest}_{int(datetime.now().timestamp())}",
        "start_time_utc": _to_iso_utc(start_time),
        "sport_type": "running",
        "distance_m": distance_m,
        "duration_s": duration_s,
        "avg_hr": _to_float(session_data.get("avg_heart_rate")),
        "max_hr": _to_float(session_data.get("max_heart_rate")),
        "avg_pace_s_per_km": avg_pace,
        "elevation_gain_m": _to_float(session_data.get("total_ascent")),
        "elevation_loss_m": _to_float(session_data.get("total_descent")),
        "avg_cadence": _to_float(session_data.get("avg_cadence") or session_data.get("enhanced_avg_running_cadence")),
        "max_cadence": _to_float(session_data.get("max_cadence") or session_data.get("enhanced_max_running_cadence")),
        "avg_stride_length": _to_float(session_data.get("avg_step_length")),
        "vertical_ratio": _to_float(session_data.get("avg_vertical_ratio")),
        "vertical_oscillation": _to_float(session_data.get("avg_vertical_oscillation")),
        "running_power_avg": _to_float(session_data.get("avg_power") or session_data.get("enhanced_avg_power")),
        "running_power_max": _to_float(session_data.get("max_power")),
        "stamina_start": _to_float(session_data.get("stamina_start")),
        "stamina_end": _to_float(session_data.get("stamina_end") or session_data.get("remaining_stamina")),
        "training_effect_aerobic": None,
        "training_effect_anaerobic": None,
        "performance_condition": None,
        "device_name": _to_str(session_data.get("device_name") or session_data.get("manufacturer")),
        "manufacturer": _to_str(session_data.get("manufacturer")),
        "activity_uuid": None,
        "owner_id": None,
        "owner_full_name": None,
        "elapsed_duration_s": _to_float(session_data.get("total_timer_time")),
        "moving_duration_s": duration_s,
        "average_speed_mps": _to_float(session_data.get("enhanced_avg_speed") or session_data.get("avg_speed")),
        "activity_type_key": "running",
        "activity_type_id": None,
        "hr_time_in_zone_1": None,
        "hr_time_in_zone_2": None,
        "hr_time_in_zone_3": None,
        "hr_time_in_zone_4": None,
        "hr_time_in_zone_5": None,
        "difference_body_battery": None,
        "bmr_calories": None,
        "is_pr": None,
        "split_summaries_json": None,
        "training_load_garmin": None,
        "training_load_garmin_field_name": None,
        "training_load_garmin_units": None,
        "calories_active": None,
        "calories_total": None,
        "intensity_minutes_vigorous": None,
        "intensity_minutes_moderate": None,
        "trimp": None,
        "source": "file_import",
        "raw": {"file": str(path), "format": "fit"},
    }


def dump_extract_to_json(path: Path, extract: GarminExtractResult) -> None:
    payload = {
        "activities": extract.activities,
        "activity_details": extract.activity_details,
        "activity_records": extract.activity_records,
        "activity_splits": extract.activity_splits,
        "sleep_daily": extract.sleep_daily,
        "wellness_daily": extract.wellness_daily,
        "errors": extract.errors,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

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
    activity_metrics: list[dict[str, Any]]
    activity_details: list[dict[str, Any]]
    activity_records: list[dict[str, Any]]
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
        "avg_cadence": _to_float(a.get("averageRunCadence") or a.get("averageCadence")),
        "max_cadence": _to_float(a.get("maxRunCadence") or a.get("maxCadence")),
        "avg_stride_length": _to_float(a.get("avgStrideLength") or a.get("averageStrideLength")),
        "vertical_ratio": _to_float(a.get("verticalRatio")),
        "vertical_oscillation": _to_float(a.get("verticalOscillation")),
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
        "source": source,
        "raw": a,
    }


def _extract_activity_metrics(
    activity_id: str,
    summary: dict[str, Any],
    details_bundle: dict[str, Any] | None,
) -> dict[str, Any]:
    combined = {"summary": summary, "details": details_bundle or {}}

    training_effect_label = _to_str(
        summary.get("trainingEffectLabel")
        or _deep_first(combined, {"trainingEffectLabel", "benefit", "trainingEffect"})
    )

    return {
        "activity_id": activity_id,
        "garmin_training_load": _to_float(
            summary.get("activityTrainingLoad")
            or summary.get("trainingLoad")
            or _deep_first(combined, {"activityTrainingLoad", "trainingLoad", "exerciseTrainingLoad"})
        ),
        "garmin_aerobic_te": _to_float(
            summary.get("aerobicTrainingEffect")
            or _deep_first(combined, {"aerobicTrainingEffect", "aerobicTrainingEffectMessage"})
        ),
        "garmin_anaerobic_te": _to_float(
            summary.get("anaerobicTrainingEffect")
            or _deep_first(combined, {"anaerobicTrainingEffect", "anaerobicTrainingEffectMessage"})
        ),
        "garmin_vo2max": _to_float(
            summary.get("vO2MaxValue")
            or _deep_first(combined, {"vO2MaxValue", "vo2Max", "vo2max"})
        ),
        "garmin_calories": _to_float(summary.get("calories") or _deep_first(combined, {"calories"})),
        "garmin_avg_power": _to_float(summary.get("averagePower") or _deep_first(combined, {"avgPower", "averagePower"})),
        "garmin_norm_power": _to_float(summary.get("normPower") or _deep_first(combined, {"normPower", "normalizedPower"})),
        "garmin_training_effect_label": training_effect_label,
        "raw": {
            "summary_keys": sorted(summary.keys()),
            "summary": summary,
            "detail_keys": sorted((details_bundle or {}).keys()),
        },
    }


def _extract_sleep_row(day: date, sleep_data: dict[str, Any] | None) -> dict[str, Any]:
    blob = sleep_data or {}
    return {
        "day_utc": day.isoformat(),
        "sleep_score": _to_float(_deep_first(blob, {"overallSleepScore", "sleepScore"})),
        "sleep_duration_s": _to_float(_deep_first(blob, {"sleepTimeSeconds", "totalSleepSeconds"})),
        "deep_sleep_s": _to_float(_deep_first(blob, {"deepSleepSeconds", "deepSleepDuration"})),
        "rem_sleep_s": _to_float(_deep_first(blob, {"remSleepSeconds", "remSleepDuration"})),
        "light_sleep_s": _to_float(_deep_first(blob, {"lightSleepSeconds", "lightSleepDuration"})),
        "awake_s": _to_float(_deep_first(blob, {"awakeTimeSeconds", "awakeDuration"})),
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
        val = _to_float(row.get("bodyBattery"))
        if val is not None:
            battery_values.append(val)

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
        "resting_hr": _to_float(_deep_first(rhr or {}, {"restingHeartRate", "allDayRestingHeartRate"})),
        "hrv_status": _to_float(_deep_first(hrv or {}, {"weeklyAvg", "lastNightAvg", "hrvValue"})),
        "training_readiness": _to_float(_deep_first(readiness or {}, {"trainingReadinessScore", "score"})),
        "stress_avg": _to_float(_deep_first(stress or {}, {"averageStressLevel", "avgStressLevel", "overallStressLevel"})),
        "stress_max": stress_max,
        "body_battery_start": min(battery_values) if battery_values else None,
        "body_battery_end": max(battery_values) if battery_values else None,
        "body_battery_avg": (sum(battery_values) / len(battery_values)) if battery_values else None,
        "respiration_avg": _to_float(_deep_first(respiration or {}, {"avgWakingRespirationValue", "avgRespirationValue", "averageRespiration"})),
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

    attempts = [
        lambda: client.download_activity(int(activity_id), dl_fmt="fit"),
        lambda: client.download_activity(int(activity_id), dl_fmt="original"),
        lambda: client.download_original_activity(int(activity_id)),
    ]

    last_error: str | None = None
    for attempt in attempts:
        payload, err = _safe_call(attempt)
        if err:
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


def fetch_garmin_runs(
    email: str,
    password: str,
    days_back: int = 90,
    since_utc: datetime | None = None,
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
    )
    return [a for a in result.activities if _is_running_activity(a.get("sport_type"))]


def fetch_garmin_comprehensive(
    email: str,
    password: str,
    start_day: date,
    end_day: date | None = None,
    include_activity_details: bool = True,
    include_wellness: bool = True,
    page_size: int = 100,
    raw_export_dir: Path | None = None,
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
    client = Garmin(email=email, password=password)
    client.login()

    errors: list[str] = []
    activities: list[dict[str, Any]] = []
    activity_metrics: list[dict[str, Any]] = []
    activity_details: list[dict[str, Any]] = []
    activity_records: list[dict[str, Any]] = []

    offset = 0
    while True:
        batch, err = _safe_call(client.get_activities, offset, page_size)
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

            activity_id = normalized["activity_id"]
            _archive_activity_payload(raw_export_dir, activity_id, "summary", row)

            details_bundle: dict[str, Any] | None = None
            if include_activity_details:
                details_bundle = {}
                for endpoint_name, method_name in (
                    ("details", "get_activity_details"),
                    ("splits", "get_activity_splits"),
                    ("split_summaries", "get_activity_split_summaries"),
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

            activity_metrics.append(
                _extract_activity_metrics(
                    activity_id=activity_id,
                    summary=row,
                    details_bundle=details_bundle,
                )
            )

        offset += page_size
        if not keep_going:
            break
        if oldest_in_batch and oldest_in_batch < start_day:
            break

    # Deduplicate by activity_id in case APIs return overlapping windows.
    activities = list({row["activity_id"]: row for row in activities}.values())
    activity_metrics = list({row["activity_id"]: row for row in activity_metrics}.values())
    activity_details = list({row["activity_id"]: row for row in activity_details}.values())
    activity_records = list(
        {
            (row["activity_id"], row["record_time_utc"]): row
            for row in activity_records
            if row.get("record_time_utc")
        }.values()
    )

    sleep_daily: list[dict[str, Any]] = []
    wellness_daily: list[dict[str, Any]] = []

    if include_wellness:
        for day in _iter_days(start_day, end_day):
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
            steps_data, steps_err, _ = _safe_call_method(
                client,
                ("get_daily_steps", "get_steps_data"),
                cdate,
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

    return GarminExtractResult(
        activities=activities,
        activity_metrics=activity_metrics,
        activity_details=activity_details,
        activity_records=activity_records,
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
        "source": "file_import",
        "raw": {"file": str(path), "format": "fit"},
    }


def dump_extract_to_json(path: Path, extract: GarminExtractResult) -> None:
    payload = {
        "activities": extract.activities,
        "activity_metrics": extract.activity_metrics,
        "activity_details": extract.activity_details,
        "activity_records": extract.activity_records,
        "sleep_daily": extract.sleep_daily,
        "wellness_daily": extract.wellness_daily,
        "errors": extract.errors,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

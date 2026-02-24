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
    return "run" in sport_type.lower()


def _extract_sport_type(a: dict[str, Any]) -> str:
    activity_type = a.get("activityType")
    if isinstance(activity_type, dict):
        return str(activity_type.get("typeKey") or activity_type.get("typeId") or "unknown")
    return str(a.get("typeKey") or activity_type or "unknown")


def _normalize_activity(a: dict[str, Any], source: str = "garmin_api") -> dict[str, Any] | None:
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

    return {
        "activity_id": str(activity_id),
        "start_time_utc": _to_iso_utc(start_time),
        "sport_type": sport_type,
        "distance_m": distance_m,
        "duration_s": duration_s,
        "avg_hr": _to_float(a.get("averageHR")),
        "max_hr": _to_float(a.get("maxHR")),
        "avg_pace_s_per_km": avg_pace_s_per_km,
        "elevation_gain_m": _to_float(a.get("elevationGain")),
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
        "awake_s": _to_float(_deep_first(blob, {"awakeTimeSeconds", "awakeDuration"})),
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
) -> dict[str, Any]:
    battery_values: list[float] = []
    for row in body_battery or []:
        val = _to_float(row.get("bodyBattery"))
        if val is not None:
            battery_values.append(val)

    stats = stats_body or {}
    return {
        "day_utc": day.isoformat(),
        "resting_hr": _to_float(_deep_first(rhr or {}, {"restingHeartRate", "allDayRestingHeartRate"})),
        "hrv_status": _to_float(_deep_first(hrv or {}, {"weeklyAvg", "lastNightAvg", "hrvValue"})),
        "training_readiness": _to_float(_deep_first(readiness or {}, {"trainingReadinessScore", "score"})),
        "stress_avg": _to_float(_deep_first(stress or {}, {"averageStressLevel", "avgStressLevel", "overallStressLevel"})),
        "body_battery_start": min(battery_values) if battery_values else None,
        "body_battery_end": max(battery_values) if battery_values else None,
        "steps": _to_float(_deep_first(stats, {"totalSteps", "steps"})),
        "calories_total": _to_float(_deep_first(stats, {"totalKilocalories", "totalCalories", "activeKilocalories"})),
        "raw": {
            "body_battery": body_battery,
            "stress": stress,
            "hrv": hrv,
            "rhr": rhr,
            "training_readiness": readiness,
            "stats_and_body": stats_body,
        },
    }


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
) -> GarminExtractResult:
    """
    Pull a broad local archive from Garmin:
    - all activity summaries in date range
    - optional per-activity detail endpoints
    - optional daily sleep/wellness endpoints
    """
    from garminconnect import Garmin

    end_day = end_day or datetime.now(timezone.utc).date()
    client = Garmin(email=email, password=password)
    client.login()

    errors: list[str] = []
    activities: list[dict[str, Any]] = []
    activity_metrics: list[dict[str, Any]] = []
    activity_details: list[dict[str, Any]] = []

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

            activities.append(normalized)

            details_bundle: dict[str, Any] | None = None
            if include_activity_details:
                details_bundle = {}
                for name, call in (
                    ("details", client.get_activity_details),
                    ("splits", client.get_activity_splits),
                    ("split_summaries", client.get_activity_split_summaries),
                    ("weather", client.get_activity_weather),
                    ("hr_timezones", client.get_activity_hr_in_timezones),
                ):
                    payload, call_err = _safe_call(call, int(normalized["activity_id"]))
                    if call_err:
                        errors.append(f"activity_id={normalized['activity_id']} {name}: {call_err}")
                    details_bundle[name] = payload

                activity_details.append(
                    {
                        "activity_id": normalized["activity_id"],
                        "details": details_bundle,
                    }
                )

            activity_metrics.append(
                _extract_activity_metrics(
                    activity_id=normalized["activity_id"],
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

    sleep_daily: list[dict[str, Any]] = []
    wellness_daily: list[dict[str, Any]] = []

    if include_wellness:
        for day in _iter_days(start_day, end_day):
            cdate = day.isoformat()

            sleep_data, sleep_err = _safe_call(client.get_sleep_data, cdate)
            if sleep_err:
                errors.append(f"date={cdate} sleep: {sleep_err}")
            sleep_daily.append(_extract_sleep_row(day, sleep_data))

            body_battery, bb_err = _safe_call(client.get_body_battery, cdate)
            stress, stress_err = _safe_call(client.get_all_day_stress, cdate)
            hrv, hrv_err = _safe_call(client.get_hrv_data, cdate)
            rhr, rhr_err = _safe_call(client.get_rhr_day, cdate)
            readiness, read_err = _safe_call(client.get_training_readiness, cdate)
            stats_body, stats_err = _safe_call(client.get_stats_and_body, cdate)

            for label, err in (
                ("body_battery", bb_err),
                ("stress", stress_err),
                ("hrv", hrv_err),
                ("rhr", rhr_err),
                ("training_readiness", read_err),
                ("stats_and_body", stats_err),
            ):
                if err:
                    errors.append(f"date={cdate} {label}: {err}")

            wellness_daily.append(
                _extract_wellness_row(
                    day=day,
                    body_battery=body_battery,
                    stress=stress,
                    hrv=hrv,
                    rhr=rhr,
                    readiness=readiness,
                    stats_body=stats_body,
                )
            )

    return GarminExtractResult(
        activities=activities,
        activity_metrics=activity_metrics,
        activity_details=activity_details,
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
        "source": "file_import",
        "raw": {"file": str(path), "format": "tcx"},
    }


def _parse_fit(path: Path) -> dict[str, Any] | None:
    if FitFile is None:
        return None

    fit_file = FitFile(path)
    session_data: dict[str, Any] = {}

    for msg in fit_file.get_messages("session"):
        for field in msg:
            session_data[field.name] = field.value
        break

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
        "avg_hr": session_data.get("avg_heart_rate"),
        "max_hr": session_data.get("max_heart_rate"),
        "avg_pace_s_per_km": avg_pace,
        "elevation_gain_m": session_data.get("total_ascent"),
        "source": "file_import",
        "raw": {"file": str(path), "format": "fit"},
    }


def dump_extract_to_json(path: Path, extract: GarminExtractResult) -> None:
    payload = {
        "activities": extract.activities,
        "activity_metrics": extract.activity_metrics,
        "activity_details": extract.activity_details,
        "sleep_daily": extract.sleep_daily,
        "wellness_daily": extract.wellness_daily,
        "errors": extract.errors,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

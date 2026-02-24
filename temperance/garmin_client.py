from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from fitparse import FitFile
except Exception:  # pragma: no cover
    FitFile = None


def _to_iso_utc(value: str | datetime) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _is_running_activity(sport_type: str | None) -> bool:
    if not sport_type:
        return False
    s = sport_type.lower()
    return "running" in s or "run" == s


def _normalize_garmin_activity(a: dict[str, Any]) -> dict[str, Any] | None:
    activity_id = a.get("activityId")
    sport_type = (
        a.get("activityType", {}).get("typeKey")
        if isinstance(a.get("activityType"), dict)
        else a.get("activityType")
    ) or a.get("typeKey")

    if not activity_id or not _is_running_activity(str(sport_type)):
        return None

    distance_m = float(a.get("distance") or 0.0)
    duration_s = float(a.get("duration") or a.get("movingDuration") or 0.0)
    avg_pace = float(a.get("averageRunCadence") or 0.0)  # placeholder to force compute below
    if distance_m > 0 and duration_s > 0:
        avg_pace = duration_s / (distance_m / 1000.0)

    start_time = a.get("startTimeGMT") or a.get("startTimeLocal")
    if not start_time:
        return None

    return {
        "activity_id": str(activity_id),
        "start_time_utc": _to_iso_utc(start_time),
        "sport_type": str(sport_type),
        "distance_m": distance_m,
        "duration_s": duration_s,
        "avg_hr": a.get("averageHR"),
        "max_hr": a.get("maxHR"),
        "avg_pace_s_per_km": avg_pace if avg_pace > 0 else None,
        "elevation_gain_m": a.get("elevationGain"),
        "source": "garmin_api",
        "raw": a,
    }


def fetch_garmin_runs(
    email: str,
    password: str,
    days_back: int = 90,
    since_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    """Fetch running activities from Garmin Connect and normalize records."""
    from garminconnect import Garmin

    end_date = datetime.now(timezone.utc).date()
    start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()

    if since_utc:
        smart_start = (since_utc - timedelta(days=2)).date()
        if smart_start > start_date:
            start_date = smart_start

    client = Garmin(email=email, password=password)
    client.login()

    activities: list[dict[str, Any]] = []

    fetch_attempts = [
        lambda: client.get_activities_by_date(
            start_date.isoformat(), end_date.isoformat(), "running"
        ),
        lambda: client.get_activities_by_date(start_date.isoformat(), end_date.isoformat()),
        lambda: client.get_activities(0, 300),
    ]

    last_error: Exception | None = None
    for attempt in fetch_attempts:
        try:
            rows = attempt() or []
            for row in rows:
                norm = _normalize_garmin_activity(row)
                if norm:
                    activities.append(norm)
            break
        except Exception as exc:  # pragma: no cover
            last_error = exc
            continue

    if not activities and last_error:
        raise RuntimeError(f"Garmin fetch failed: {last_error}") from last_error

    deduped = {a["activity_id"]: a for a in activities}
    return list(deduped.values())


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

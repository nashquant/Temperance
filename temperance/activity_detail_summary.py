from __future__ import annotations

from typing import Any


HEAVY_DETAIL_KEYS = {
    "activityDetailMetrics",
    "metricDescriptors",
    "heartRateDTOs",
    "geoPolylineDTO",
}

DETAIL_SCALAR_KEYS = {
    "activityId",
    "detailsAvailable",
    "measurementCount",
    "metricsCount",
    "totalMetricsCount",
    "deviceName",
    "productName",
    "trainingEffectLabel",
    "activityTrainingLoad",
    "trainingLoad",
    "exerciseTrainingLoad",
}

WEATHER_SCALAR_KEYS = {
    "temp",
    "apparentTemp",
    "dewPoint",
    "relativeHumidity",
    "windDirection",
    "windDirectionCompassPoint",
    "windGust",
    "windSpeed",
    "issueDate",
    "latitude",
    "longitude",
}


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _compact_scalars(payload: Any, preferred_keys: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    out: dict[str, Any] = {}
    for key in sorted(payload.keys()):
        value = payload.get(key)
        if key in preferred_keys and _is_scalar(value):
            out[key] = value
        elif key not in HEAVY_DETAIL_KEYS and _is_scalar(value):
            out[key] = value
    return out


def _compact_hr_timezones(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        compact = {key: value for key, value in item.items() if _is_scalar(value)}
        if compact:
            rows.append(compact)
    return rows


def summarize_activity_detail_bundle(bundle: dict[str, Any] | None) -> dict[str, Any]:
    payload = bundle if isinstance(bundle, dict) else {}
    details = payload.get("details")
    weather = payload.get("weather")
    hr_timezones = payload.get("hr_timezones")

    dropped_detail_keys: list[str] = []
    if isinstance(details, dict):
        dropped_detail_keys = sorted(key for key in HEAVY_DETAIL_KEYS if key in details)

    return {
        "storage": "summary",
        "details": _compact_scalars(details, DETAIL_SCALAR_KEYS),
        "weather": _compact_scalars(weather, WEATHER_SCALAR_KEYS),
        "hr_timezones": _compact_hr_timezones(hr_timezones),
        "dropped_detail_keys": dropped_detail_keys,
    }

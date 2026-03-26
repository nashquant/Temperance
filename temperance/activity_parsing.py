from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime

import pandas as pd


_MONTH_ABBR_TO_NUMBER = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _pace_mmss_to_sec(text: str) -> float:
    parts = str(text or "").strip().split(":")
    if len(parts) != 2:
        raise ValueError("pace must be mm:ss")
    minutes = int(parts[0])
    seconds = int(parts[1])
    total = minutes * 60 + seconds
    if total <= 0:
        raise ValueError("pace must be > 0")
    return float(total)


def _parse_supported_day_value(raw_value: str) -> date | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        pass
    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if slash_match:
        try:
            day = int(slash_match.group(1))
            month = int(slash_match.group(2))
            year = int(slash_match.group(3))
            return date(year, month, day)
        except Exception:
            return None
    compact_match = re.fullmatch(r"(\d{1,2})([A-Za-z]{3})(\d{2})", value)
    if compact_match:
        month = _MONTH_ABBR_TO_NUMBER.get(compact_match.group(2).lower())
        if month is None:
            return None
        try:
            day = int(compact_match.group(1))
            year = 2000 + int(compact_match.group(3))
            return date(year, month, day)
        except Exception:
            return None
    return None


def _plan_activity_kind(text: str) -> str:
    lower = str(text or "").lower()
    if "treadmill" in lower:
        return "treadmill"
    if "run" in lower:
        return "run"
    if "ellipt" in lower or "xtrain" in lower or "x-train" in lower or "cross train" in lower or "cross-train" in lower:
        return "elliptical"
    if "cycl" in lower or "bike" in lower:
        return "cycling"
    return "other"


def _parse_minutes_token(text: str) -> float | None:
    lower = str(text or "").lower().strip()
    hm = re.search(r"(\d+(?:\.\d+)?)\s*h(?:\s*(\d+(?:\.\d+)?)\s*m(?:in)?)?", lower)
    if hm:
        hours = float(hm.group(1))
        minutes = float(hm.group(2)) if hm.group(2) else 0.0
        total = hours * 60.0 + minutes
        return total if total > 0 else None
    minute_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes)\b", lower)
    if minute_match:
        total = float(minute_match.group(1))
        return total if total > 0 else None
    minute_quote_match = re.search(r"(\d+(?:\.\d+)?)\s*[\'’](?=\D|$)", lower)
    if minute_quote_match:
        total = float(minute_quote_match.group(1))
        return total if total > 0 else None
    second_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b", lower)
    if second_match:
        total = float(second_match.group(1)) / 60.0
        return total if total > 0 else None
    second_quote_match = re.search(r"(\d+(?:\.\d+)?)\s*[\"”″](?=\D|$)", lower)
    if second_quote_match:
        total = float(second_quote_match.group(1)) / 60.0
        return total if total > 0 else None
    return None


def _parse_distance_km_token(text: str) -> float | None:
    lower = str(text or "").lower()
    km_match = re.search(r"(\d+(?:\.\d+)?)\s*km\b", lower)
    if km_match:
        try:
            km = float(km_match.group(1))
        except Exception:
            return None
        return km if km > 0 else None
    meter_match = re.search(r"(\d+(?:\.\d+)?)\s*m\b", lower)
    if not meter_match:
        return None
    try:
        meters = float(meter_match.group(1))
    except Exception:
        return None
    km = meters / 1000.0
    return km if km > 0 else None


def _parse_repeated_distance_token(text: str) -> tuple[int, float] | None:
    lower = str(text or "").lower()
    match = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(km|m)\b", lower)
    if not match:
        return None
    reps = int(match.group(1))
    distance_value = float(match.group(2))
    distance_km = distance_value / 1000.0 if str(match.group(3)) == "m" else distance_value
    if reps <= 0 or distance_km <= 0:
        return None
    return reps, distance_km


def _split_interval_recovery_chunk(text: str) -> tuple[str, str | None]:
    raw = str(text or "").strip()
    if not raw:
        return "", None
    slash_parts = re.split(r"\s+/\s+", raw, maxsplit=1)
    if len(slash_parts) == 2:
        return slash_parts[0].strip(), slash_parts[1].strip() or None
    paren_match = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", raw)
    if paren_match:
        return paren_match.group(1).strip(), paren_match.group(2).strip() or None
    return raw, None


def _parse_bpm_token(text: str) -> float | None:
    lower = str(text or "").lower()
    match = re.search(r"@\s*(\d+(?:\.\d+)?)\s*bpm", lower)
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?)\s*bpm", lower)
    if not match:
        return None
    value = float(match.group(1))
    return value if value > 0 else None


def _parse_pace_token(text: str) -> float | None:
    lower = str(text or "").lower()
    match = re.search(r"@\s*(\d{1,2}:\d{2})(?:\s*/?\s*km)?", lower)
    if not match:
        match = re.search(r"(\d{1,2}:\d{2})\s*/\s*km", lower)
    if not match:
        return None
    try:
        return _pace_mmss_to_sec(match.group(1))
    except Exception:
        return None


def _parse_named_pace_token(text: str) -> str | None:
    lower = str(text or "").lower()
    match = re.search(r"@\s*(mp|hmp|10k)\b", lower)
    if not match:
        return None
    token = str(match.group(1) or "").strip().lower()
    return token or None


def _parse_if_token(text: str) -> float | None:
    lower = str(text or "").lower()
    match = re.search(r"@\s*(\d+(?:\.\d+)?)\s*%", lower)
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", lower)
    if not match:
        return None
    try:
        value = float(match.group(1)) / 100.0
    except Exception:
        return None
    return value if value > 0 else None


def _parse_tss_token(text: str) -> float | None:
    lower = str(text or "").lower()
    match = re.search(r"@\s*(\d+(?:\.\d+)?)\s*tss\b", lower)
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?)\s*tss\b", lower)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except Exception:
        return None
    return value if value > 0 else None


def normalize_plan_text(text: str) -> str:
    normalized = " ".join(str(text or "").strip().split())
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes)\b", r"\1min", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*[\'’](?=\D|$)", r"\1min", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds)\b", r"\1s", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*[\"”″](?=\D|$)", r"\1s", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*h\b", r"\1h", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*km\b", r"\1km", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*m\b", r"\1m", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*bpm\b", r"\1bpm", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*/\s*km\b", "/km", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s*\+\s*", " + ", normalized)
    return normalized


def strip_meridiem_tokens(text: str) -> tuple[str, str | None]:
    raw = str(text or "")
    token_matches = re.findall(r"(?<![A-Za-z0-9_])(AM|PM)(?![A-Za-z0-9_])", raw, flags=re.IGNORECASE)
    hint = str(token_matches[-1]).upper() if token_matches else None
    cleaned = re.sub(r"(?<![A-Za-z0-9_])(AM|PM)(?![A-Za-z0-9_])", " ", raw, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.strip().split())
    return cleaned, hint


def parse_dated_activity_entry(text: str) -> tuple[pd.Timestamp | None, str, str | None]:
    raw = str(text or "").strip()
    if not raw:
        return None, "", "Input is empty. Use `[date]:[activity]`."
    if ":" in raw:
        date_text, activity_text = raw.split(":", 1)
    else:
        compact_match = re.match(r"^\s*([tT][+-]\d)(.+)$", raw)
        if compact_match:
            date_text = compact_match.group(1)
            activity_text = compact_match.group(2)
        else:
            return None, "", "Missing `:` separator. Use `[date]:[activity]`."
    date_text = date_text.strip()
    activity_text = activity_text.strip()
    date_text, date_hint = strip_meridiem_tokens(date_text)
    activity_text, activity_hint = strip_meridiem_tokens(activity_text)
    merged_hint = activity_hint or date_hint
    if merged_hint:
        activity_text = f"{activity_text} {merged_hint}".strip()
    activity_text = normalize_plan_text(activity_text)
    if not date_text:
        return None, "", "Missing date before `:`."
    if not activity_text:
        return None, "", "Missing activity after `:`."

    date_value: pd.Timestamp | None = None
    date_key = date_text.strip().lower()
    if date_key in {"today", "tomorrow", "yesterday", "t"}:
        base_local = pd.Timestamp(datetime.now().astimezone().date())
        if date_key in {"today", "t"}:
            date_value = base_local
        elif date_key == "tomorrow":
            date_value = base_local + pd.Timedelta(days=1)
        else:
            date_value = base_local - pd.Timedelta(days=1)
    else:
        offset_match = re.match(r"^t([+-]\d+)$", date_key)
        if offset_match:
            try:
                offset_days = int(offset_match.group(1))
            except Exception:
                offset_days = 0
            date_value = pd.Timestamp(datetime.now().astimezone().date()) + pd.Timedelta(days=offset_days)

    if date_value is None:
        parsed_day = _parse_supported_day_value(date_text)
        if parsed_day is not None:
            date_value = pd.Timestamp(parsed_day)
    if date_value is None:
        return None, activity_text, (
            "Invalid date format. Use one of: `today`, `tomorrow`, `yesterday`, `T`, `T+1`, `T-1`, "
            "`3Mar26`, `2026-03-26`, `26/03/2026`."
        )
    return date_value, activity_text, None


def split_dated_activity_entries(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[\n;,]+", raw) if part.strip()]


def planned_row_signature(day_utc: str, workout_text: str) -> str:
    day_key = str(day_utc or "").strip()
    workout_key = normalize_plan_text(str(workout_text or "")).lower()
    return f"{day_key}::{workout_key}"


def expand_planned_segments(
    line: str,
    lthr_bpm: float | None = None,
    threshold_pace_sec_per_km: float | None = None,
    has_vdot_basis: bool = False,
    named_pace_resolver: Callable[[str, float], float | None] | None = None,
) -> tuple[list[dict[str, float | str | None]], list[str]]:
    segments: list[dict[str, float | str | None]] = []
    warnings: list[str] = []
    raw = normalize_plan_text(line)
    raw, line_time_hint = strip_meridiem_tokens(raw)
    if not raw:
        return segments, warnings
    lthr_value = float(lthr_bpm or 0.0)
    threshold_pace_value = float(threshold_pace_sec_per_km or 0.0)

    chunks = [chunk.strip() for chunk in re.split(r"\s*\+\s*", raw) if chunk.strip()]
    last_kind: str | None = None
    for chunk in chunks:
        work_chunk, recovery_chunk = _split_interval_recovery_chunk(chunk)

        kind = _plan_activity_kind(work_chunk)
        bpm = _parse_bpm_token(work_chunk)
        pace = _parse_pace_token(work_chunk)
        named_pace = _parse_named_pace_token(work_chunk)
        if_input = _parse_if_token(work_chunk)
        if_input_source: str | None = "explicit" if if_input is not None else None
        tss_input = _parse_tss_token(work_chunk)
        if kind == "other" and pace is not None:
            kind = "run"
        if kind == "other" and named_pace is not None:
            kind = "run"
        if kind == "other" and last_kind is not None:
            kind = last_kind
        if kind == "other":
            warnings.append(f"Missing/unknown activity in: `{chunk}` (include run/treadmill/elliptical/cycling)")
            continue

        is_running_like = kind in {"run", "treadmill"}
        if named_pace is not None:
            if not is_running_like:
                warnings.append(
                    f"Named pace is only allowed for running/treadmill in: `{chunk}` (use `@140bpm` or `@70%` for non-running)."
                )
                continue
            if not has_vdot_basis:
                warnings.append(f"Named pace token requires configured LT pace/VDOT in Settings for: `{chunk}`.")
                continue
            if pace is None and named_pace_resolver is not None:
                pace = named_pace_resolver(named_pace, threshold_pace_value)
            if pace is None or pace <= 0:
                warnings.append(f"Could not derive `{named_pace.upper()}` pace from VDOT for: `{chunk}`.")
                continue
        if (not is_running_like) and (pace is not None):
            warnings.append(
                f"Pace is only allowed for running/treadmill in: `{chunk}` (use `@140bpm` or `@70%` for non-running)."
            )
            continue
        if bpm is None and pace is None and if_input is None and tss_input is None:
            warnings.append(
                f"Missing intensity in: `{chunk}` (add `@140bpm`, `@70%`, `@4:50/km`, `@MP`, `@HMP`, `@10k`, or `@40TSS`)"
            )
            continue

        recovery_minutes = _parse_minutes_token(recovery_chunk) if recovery_chunk else None
        recovery_distance_km = _parse_distance_km_token(recovery_chunk) if recovery_chunk else None
        recovery_bpm = _parse_bpm_token(recovery_chunk) if recovery_chunk else None
        recovery_pace = _parse_pace_token(recovery_chunk) if recovery_chunk else None
        recovery_if_input = _parse_if_token(recovery_chunk) if recovery_chunk else None
        recovery_if_source: str | None = "explicit" if recovery_if_input is not None else None
        recovery_tss_input = _parse_tss_token(recovery_chunk) if recovery_chunk else None
        if recovery_chunk and recovery_bpm is None and recovery_pace is None and recovery_if_input is None and recovery_tss_input is None:
            warnings.append(f"Missing recovery intensity in: `{chunk}`")
            continue

        rep_match = re.search(
            r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|min|mins|minute|minutes|s|sec|secs|second|seconds)\b",
            work_chunk.lower(),
        )
        if rep_match:
            reps = int(rep_match.group(1))
            rep_value = float(rep_match.group(2))
            rep_unit = rep_match.group(3)
            rep_minutes = rep_value * 60.0 if rep_unit.startswith("h") else (rep_value / 60.0 if rep_unit.startswith("s") else rep_value)
            if reps <= 0 or rep_minutes <= 0:
                warnings.append(f"Invalid interval block in: `{chunk}`")
                continue
            if tss_input is not None and tss_input > 0 and bpm is None and pace is None and if_input is None:
                seg_duration_h = rep_minutes / 60.0
                per_rep_tss = float(tss_input) / float(max(reps, 1))
                if seg_duration_h > 0:
                    derived_if = (per_rep_tss / (seg_duration_h * 100.0)) ** 0.5
                    if_input = max(float(derived_if), 0.0)
                    if_input_source = "tss_derived"
                    if is_running_like and threshold_pace_value > 0 and if_input > 0:
                        pace = threshold_pace_value / if_input
                    elif (not is_running_like) and lthr_value > 0 and if_input > 0:
                        bpm = lthr_value * if_input
            recovery_duration_min = recovery_minutes
            if recovery_duration_min is None and recovery_distance_km is not None:
                if not is_running_like:
                    warnings.append(f"Distance-based recovery requires running/treadmill with pace in: `{chunk}`.")
                    continue
                if recovery_pace is None or recovery_pace <= 0:
                    warnings.append(f"Distance-based recovery requires pace in: `{chunk}`")
                    continue
                recovery_duration_min = (recovery_distance_km * recovery_pace) / 60.0
            if recovery_chunk and (recovery_duration_min is None or recovery_duration_min <= 0):
                warnings.append(f"Could not parse recovery duration from: `{chunk}`")
                continue
            if recovery_tss_input is not None and recovery_tss_input > 0 and recovery_bpm is None and recovery_pace is None and recovery_if_input is None:
                recovery_duration_h = float(recovery_duration_min or 0.0) / 60.0
                if recovery_duration_h <= 0:
                    warnings.append(f"TSS-based recovery requires positive duration in: `{chunk}`")
                    continue
                recovery_if_input = max((float(recovery_tss_input) / (recovery_duration_h * 100.0)) ** 0.5, 0.0)
                recovery_if_source = "tss_derived"
                if is_running_like:
                    if threshold_pace_value <= 0:
                        warnings.append(f"Missing LT pace to convert recovery TSS to pace in: `{chunk}`")
                        continue
                    if recovery_if_input > 0:
                        recovery_pace = threshold_pace_value / recovery_if_input
                else:
                    if lthr_value <= 0:
                        warnings.append(f"Missing LTHR to convert recovery TSS to HR in: `{chunk}`")
                        continue
                    recovery_bpm = lthr_value * recovery_if_input
            for rep_idx in range(max(reps, 0)):
                segments.append(
                    {
                        "kind": kind,
                        "duration_min": rep_minutes,
                        "avg_hr_bpm": bpm,
                        "pace_s_per_km": pace,
                        "if_input": if_input,
                        "if_input_source": if_input_source,
                        "tss_target": (float(tss_input) / float(max(reps, 1))) if tss_input else None,
                        "time_hint": line_time_hint,
                        "source": chunk,
                    }
                )
                if recovery_chunk and rep_idx < reps - 1:
                    segments.append(
                        {
                            "kind": kind,
                            "duration_min": float(recovery_duration_min or 0.0),
                            "avg_hr_bpm": recovery_bpm,
                            "pace_s_per_km": recovery_pace,
                            "if_input": recovery_if_input,
                            "if_input_source": recovery_if_source,
                            "tss_target": float(recovery_tss_input) if recovery_tss_input else None,
                            "time_hint": line_time_hint,
                            "source": chunk,
                        }
                    )
            last_kind = kind
            continue

        repeated_distance = _parse_repeated_distance_token(work_chunk)
        if repeated_distance is not None:
            reps, rep_distance_km = repeated_distance
            if not is_running_like:
                warnings.append(
                    f"Distance-only reps require running/treadmill with pace in: `{chunk}` (non-running should use time + bpm/%IF)."
                )
                continue
            if pace is None and if_input is not None and if_input > 0 and threshold_pace_value > 0:
                pace = threshold_pace_value / float(if_input)
                if_input_source = if_input_source or "if_input"
            if pace is None and tss_input is not None and tss_input > 0 and threshold_pace_value > 0:
                total_distance_km = rep_distance_km * float(max(reps, 1))
                pace = (total_distance_km * (threshold_pace_value**2) * 100.0) / (3600.0 * float(tss_input))
                if pace > 0:
                    if_input = threshold_pace_value / pace
                    if_input_source = "tss_derived"
            if pace is None or pace <= 0:
                warnings.append(f"Distance-based reps require pace in: `{chunk}` (add `@4:50/km`)")
                continue
            rep_minutes = (rep_distance_km * pace) / 60.0
            if rep_minutes <= 0:
                warnings.append(f"Could not derive duration from repeated distance in: `{chunk}`")
                continue
            recovery_duration_min = recovery_minutes
            if recovery_duration_min is None and recovery_distance_km is not None:
                if recovery_pace is None or recovery_pace <= 0:
                    warnings.append(f"Distance-based recovery requires pace in: `{chunk}`")
                    continue
                recovery_duration_min = (recovery_distance_km * recovery_pace) / 60.0
            if recovery_chunk and (recovery_duration_min is None or recovery_duration_min <= 0):
                warnings.append(f"Could not parse recovery duration from: `{chunk}`")
                continue
            if recovery_tss_input is not None and recovery_tss_input > 0 and recovery_bpm is None and recovery_pace is None and recovery_if_input is None:
                recovery_duration_h = float(recovery_duration_min or 0.0) / 60.0
                if recovery_duration_h <= 0:
                    warnings.append(f"TSS-based recovery requires positive duration in: `{chunk}`")
                    continue
                recovery_if_input = max((float(recovery_tss_input) / (recovery_duration_h * 100.0)) ** 0.5, 0.0)
                recovery_if_source = "tss_derived"
                if threshold_pace_value <= 0:
                    warnings.append(f"Missing LT pace to convert recovery TSS to pace in: `{chunk}`")
                    continue
                if recovery_if_input > 0:
                    recovery_pace = threshold_pace_value / recovery_if_input
            per_rep_tss = (float(tss_input) / float(max(reps, 1))) if tss_input else None
            for rep_idx in range(max(reps, 0)):
                segments.append(
                    {
                        "kind": kind,
                        "duration_min": rep_minutes,
                        "avg_hr_bpm": bpm,
                        "pace_s_per_km": pace,
                        "if_input": if_input,
                        "if_input_source": if_input_source,
                        "tss_target": per_rep_tss,
                        "time_hint": line_time_hint,
                        "source": chunk,
                    }
                )
                if recovery_chunk and rep_idx < reps - 1:
                    segments.append(
                        {
                            "kind": kind,
                            "duration_min": float(recovery_duration_min or 0.0),
                            "avg_hr_bpm": recovery_bpm,
                            "pace_s_per_km": recovery_pace,
                            "if_input": recovery_if_input,
                            "if_input_source": recovery_if_source,
                            "tss_target": float(recovery_tss_input) if recovery_tss_input else None,
                            "time_hint": line_time_hint,
                            "source": chunk,
                        }
                    )
            last_kind = kind
            continue

        minutes = _parse_minutes_token(work_chunk)
        if minutes is None:
            distance_km = _parse_distance_km_token(work_chunk)
            if distance_km is not None:
                if not is_running_like:
                    warnings.append(
                        f"Distance-only segment requires running/treadmill with pace in: `{chunk}` (non-running should use minutes + bpm/%IF)."
                    )
                    continue
                if pace is None and if_input is not None and if_input > 0 and threshold_pace_value > 0:
                    pace = threshold_pace_value / float(if_input)
                    if_input_source = if_input_source or "if_input"
                if pace is None and tss_input is not None and tss_input > 0 and threshold_pace_value > 0:
                    pace = (distance_km * (threshold_pace_value**2) * 100.0) / (3600.0 * float(tss_input))
                    if pace > 0:
                        if_input = threshold_pace_value / pace
                if pace is None or pace <= 0:
                    warnings.append(f"Distance-based segment requires pace in: `{chunk}` (add `@4:50/km`)")
                    continue
                minutes = (distance_km * pace) / 60.0
        if minutes is None:
            warnings.append(f"Could not parse duration from: `{chunk}`")
            continue
        if minutes <= 0:
            warnings.append(f"Duration must be > 0 in: `{chunk}`")
            continue
        if tss_input is not None and tss_input > 0 and bpm is None and pace is None and if_input is None:
            duration_h = float(minutes) / 60.0
            if duration_h <= 0:
                warnings.append(f"TSS-based intensity requires positive duration in: `{chunk}`")
                continue
            if_input = max((float(tss_input) / (duration_h * 100.0)) ** 0.5, 0.0)
            if_input_source = "tss_derived"
            if is_running_like:
                if threshold_pace_value <= 0:
                    warnings.append(f"Missing LT pace to convert TSS to pace in: `{chunk}`")
                    continue
                if if_input > 0:
                    pace = threshold_pace_value / if_input
            else:
                if lthr_value <= 0:
                    warnings.append(f"Missing LTHR to convert TSS to HR in: `{chunk}`")
                    continue
                bpm = lthr_value * if_input
        segments.append(
            {
                "kind": kind,
                "duration_min": minutes,
                "avg_hr_bpm": bpm,
                "pace_s_per_km": pace,
                "if_input": if_input,
                "if_input_source": if_input_source,
                "tss_target": float(tss_input) if tss_input else None,
                "time_hint": line_time_hint,
                "source": chunk,
            }
        )
        last_kind = kind

    return segments, warnings

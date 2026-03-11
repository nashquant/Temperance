from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


DEFAULT_LTHR = 178.0
DEFAULT_LT_PACE_SEC_PER_KM = 300.0
MIN_PER_BUCKET = 20
PRIMARY_BUCKETS = [
    "recovery",
    "easy aerobic",
    "aerobic endurance",
    "long run",
    "steady / tempo",
    "short reps",
    "long reps",
    "fartlek",
]


@dataclass(frozen=True)
class CurvePoint:
    day: date
    value: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export normalized activity-card samples from Temperance user databases."
    )
    parser.add_argument(
        "--db-root",
        default="/Users/matheus/Temperance/temperance/data/private/users",
        help="Directory containing per-user SQLite databases.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=150,
        help="Maximum number of unique normalized cards to export.",
    )
    parser.add_argument(
        "--output",
        default="/Users/matheus/Temperance/v2/frontend/src/features/dashboard/activity-card-samples.json",
        help="Output JSON file path.",
    )
    return parser.parse_args()


def parse_iso_day(raw: str) -> date | None:
    try:
        return datetime.fromisoformat(str(raw).strip()).date()
    except Exception:
        return None


def parse_curve_points(raw: str, value_keys: tuple[str, ...], fallback: float) -> list[CurvePoint]:
    if not raw:
        return [CurvePoint(day=date(2025, 1, 1), value=fallback)]
    try:
        payload = json.loads(raw)
    except Exception:
        return [CurvePoint(day=date(2025, 1, 1), value=fallback)]
    points: list[CurvePoint] = []
    if not isinstance(payload, list):
        return [CurvePoint(day=date(2025, 1, 1), value=fallback)]
    for item in payload:
        if not isinstance(item, dict):
            continue
        day = parse_iso_day(str(item.get("date") or ""))
        if day is None:
            continue
        value: float | None = None
        for key in value_keys:
            if item.get(key) is None:
                continue
            try:
                value = float(item[key])
                break
            except Exception:
                continue
        if value is None or value <= 0:
            continue
        points.append(CurvePoint(day=day, value=value))
    if not points:
        return [CurvePoint(day=date(2025, 1, 1), value=fallback)]
    return sorted(points, key=lambda point: point.day)


def curve_value_at(points: list[CurvePoint], target_day: date | None, fallback: float) -> float:
    if not points:
        return fallback
    if target_day is None:
        return points[-1].value
    current = points[0].value
    for point in points:
        if point.day > target_day:
            break
        current = point.value
    return current


def format_duration_minutes(total_minutes: float) -> str:
    rounded_minutes = max(int(round(float(total_minutes))), 0)
    hours = rounded_minutes // 60
    minutes = rounded_minutes % 60
    if hours > 0:
        return f"{hours}h{minutes}'" if minutes > 0 else f"{hours}h"
    return f"{minutes}'"


def type_label(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized == "treadmill":
        return "treadmill"
    if normalized == "run":
        return "run"
    if normalized == "elliptical":
        return "elliptical"
    if normalized == "cycling":
        return "bike"
    return "other"


def load_segments(parsed_json: str | None) -> list[dict[str, Any]]:
    if not parsed_json:
        return []
    try:
        payload = json.loads(parsed_json)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [segment for segment in payload if isinstance(segment, dict)]


def infer_if_proxy(segment: dict[str, Any], lthr_bpm: float, lt_pace_sec_per_km: float) -> float | None:
    try:
        explicit_if = float(segment.get("if_input") or 0.0)
    except Exception:
        explicit_if = 0.0
    if explicit_if > 0:
        return explicit_if

    kind = str(segment.get("kind") or "").strip().lower()
    try:
        pace = float(segment.get("pace_s_per_km") or 0.0)
    except Exception:
        pace = 0.0
    if kind in {"run", "treadmill"} and pace > 0 and lt_pace_sec_per_km > 0:
        return lt_pace_sec_per_km / pace

    try:
        avg_hr_bpm = float(segment.get("avg_hr_bpm") or 0.0)
    except Exception:
        avg_hr_bpm = 0.0
    if avg_hr_bpm > 0 and lthr_bpm > 0:
        return avg_hr_bpm / lthr_bpm

    return None


def bucket_label(
    total_minutes: float,
    if_pct: int | None,
    segment_count: int,
    segment_minutes: list[float],
    raw_text: str,
) -> str:
    if segment_count > 1:
        lower_text = raw_text.lower()
        rounded_segments = sorted({int(round(value)) for value in segment_minutes if value > 0})
        if "fartlek" in lower_text or len(rounded_segments) >= 3:
            return "fartlek"
        avg_segment_minutes = sum(segment_minutes) / max(len(segment_minutes), 1)
        if avg_segment_minutes <= 3.5:
            return "short reps"
        return "long reps"

    if total_minutes >= 95:
        return "long run"
    if if_pct is None:
        return "easy aerobic"
    if if_pct < 65:
        return "recovery"
    if if_pct < 78:
        return "easy aerobic" if total_minutes < 60 else "aerobic endurance"
    return "steady / tempo"


def select_balanced_cards(cards: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in PRIMARY_BUCKETS}
    fallback: list[dict[str, Any]] = []
    for card in cards:
        bucket = str(card.get("bucket") or "")
        if bucket in grouped:
            grouped[bucket].append(card)
        else:
            fallback.append(card)

    selected: list[dict[str, Any]] = []
    used_keys: set[str] = set()
    made_progress = True
    while len(selected) < limit and made_progress:
        made_progress = False
        for bucket in PRIMARY_BUCKETS:
            while grouped[bucket]:
                card = grouped[bucket].pop(0)
                key = str(card.get("normalized_label", "")).lower()
                if key in used_keys:
                    continue
                used_keys.add(key)
                selected.append(card)
                made_progress = True
                break
            if len(selected) >= limit:
                break

    if len(selected) < limit:
        for card in fallback:
            key = str(card.get("normalized_label", "")).lower()
            if key in used_keys:
                continue
            used_keys.add(key)
            selected.append(card)
            if len(selected) >= limit:
                break

    return selected[:limit]


def fabricate_bucket_examples(cards: list[dict[str, Any]], min_per_bucket: int) -> list[dict[str, Any]]:
    by_bucket: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in PRIMARY_BUCKETS}
    for card in cards:
        bucket = str(card.get("bucket") or "")
        if bucket in by_bucket:
            by_bucket[bucket].append(card)

    fabricated: list[dict[str, Any]] = []
    seen_labels = {str(card.get("normalized_label") or "").lower() for card in cards}

    plans: dict[str, list[tuple[str, list[int], list[int], str]]] = {
        "recovery": [
            ("run", [20, 25, 30, 35, 40, 45], [55, 58, 60, 62, 64], "run {duration} @ {if_pct}%"),
            ("elliptical", [25, 30, 35, 40], [56, 60, 62, 64], "elliptical {duration} @ {if_pct}%"),
        ],
        "easy aerobic": [
            ("run", [35, 40, 45, 50, 55], [66, 68, 70, 72, 74], "run {duration} @ {if_pct}%"),
            ("elliptical", [35, 40, 45, 50, 55], [66, 68, 70, 72, 74], "elliptical {duration} @ {if_pct}%"),
        ],
        "aerobic endurance": [
            ("run", [60, 70, 75, 80, 85, 90], [68, 70, 72, 74, 76], "run {duration} @ {if_pct}%"),
            ("bike", [70, 80, 90], [68, 70, 72, 74, 76], "bike {duration} @ {if_pct}%"),
        ],
        "long run": [
            ("run", [100, 110, 120, 130, 140, 150, 160], [70, 72, 74, 76, 78], "run {duration} @ {if_pct}%"),
        ],
        "steady / tempo": [
            ("run", [45, 50, 55, 60, 65, 70, 75, 80], [78, 80, 82, 84, 86, 88, 90], "run {duration} @ {if_pct}%"),
            ("treadmill", [40, 45, 50, 55, 60], [80, 82, 84, 86], "treadmill {duration} @ {if_pct}%"),
        ],
        "short reps": [
            ("run", [24, 28, 32, 36, 40], [88, 90, 92, 94, 96], "run {duration} @ {if_pct}%"),
            ("treadmill", [24, 28, 32, 36], [88, 90, 92], "treadmill {duration} @ {if_pct}%"),
        ],
        "long reps": [
            ("run", [36, 42, 48, 54, 60], [86, 88, 90, 92, 94], "run {duration} @ {if_pct}%"),
            ("treadmill", [36, 42, 48, 54], [86, 88, 90, 92], "treadmill {duration} @ {if_pct}%"),
        ],
        "fartlek": [
            ("run", [40, 45, 50, 55, 60], [82, 84, 86, 88, 90], "run {duration} @ {if_pct}%"),
            ("treadmill", [35, 40, 45, 50], [82, 84, 86, 88], "treadmill {duration} @ {if_pct}%"),
        ],
    }

    for bucket in PRIMARY_BUCKETS:
        needed = max(0, min_per_bucket - len(by_bucket[bucket]))
        if needed <= 0:
            continue
        sequence_no = 1
        for activity_type, durations, if_values, template in plans.get(bucket, []):
            for duration_min in durations:
                for if_pct in if_values:
                    if needed <= 0:
                        break
                    duration_label = format_duration_minutes(float(duration_min))
                    normalized_label = template.format(duration=duration_label, if_pct=if_pct)
                    key = normalized_label.lower()
                    if key in seen_labels:
                        continue
                    seen_labels.add(key)
                    fabricated_card = {
                        "owner": "examples",
                        "source": "fabricated",
                        "day_utc": "2026-01-01",
                        "line_no": sequence_no,
                        "raw_text": normalized_label,
                        "normalized_label": normalized_label,
                        "type": activity_type,
                        "bucket": bucket,
                        "label": bucket,
                        "duration_label": duration_label,
                        "duration_min": float(duration_min),
                        "if_pct": if_pct,
                        "segment_count": 1 if bucket in {"recovery", "easy aerobic", "aerobic endurance", "long run", "steady / tempo"} else 4,
                        "kinds": [activity_type],
                        "fabricated": True,
                        "fabricated_from_bucket": bucket,
                    }
                    fabricated.append(fabricated_card)
                    by_bucket[bucket].append(fabricated_card)
                    needed -= 1
                    sequence_no += 1
                if needed <= 0:
                    break
            if needed <= 0:
                break
    return cards + fabricated


def normalize_row(
    owner: str,
    source: str,
    day_utc: str,
    line_no: int,
    raw_text: str,
    parsed_json: str | None,
    lthr_curve: list[CurvePoint],
    lt_pace_curve: list[CurvePoint],
) -> dict[str, Any] | None:
    target_day = parse_iso_day(day_utc)
    segments = load_segments(parsed_json)
    if not segments:
        return None

    duration_by_kind: dict[str, float] = defaultdict(float)
    kinds_seen: list[str] = []
    segment_minutes: list[float] = []
    total_minutes = 0.0
    if_weighted_sum = 0.0
    if_weight_seconds = 0.0
    lthr_bpm = curve_value_at(lthr_curve, target_day, DEFAULT_LTHR)
    lt_pace_sec_per_km = curve_value_at(lt_pace_curve, target_day, DEFAULT_LT_PACE_SEC_PER_KM)

    for segment in segments:
        try:
            duration_min = float(segment.get("duration_min") or 0.0)
        except Exception:
            duration_min = 0.0
        if duration_min <= 0:
            continue
        total_minutes += duration_min
        segment_minutes.append(duration_min)
        kind = str(segment.get("kind") or "other").strip().lower() or "other"
        duration_by_kind[kind] += duration_min
        if kind not in kinds_seen:
            kinds_seen.append(kind)
        if_proxy = infer_if_proxy(segment, lthr_bpm=lthr_bpm, lt_pace_sec_per_km=lt_pace_sec_per_km)
        if if_proxy is None or if_proxy <= 0:
            continue
        duration_seconds = duration_min * 60.0
        if_weighted_sum += if_proxy * duration_seconds
        if_weight_seconds += duration_seconds

    if total_minutes <= 0:
        return None

    dominant_kind = max(duration_by_kind.items(), key=lambda item: item[1])[0] if duration_by_kind else "other"
    normalized_type = type_label(dominant_kind)
    duration_label = format_duration_minutes(total_minutes)
    if_pct = round((if_weighted_sum / if_weight_seconds) * 100.0) if if_weight_seconds > 0 else None
    normalized_label = f"{normalized_type} {duration_label}"
    if if_pct is not None and if_pct > 0:
        normalized_label = f"{normalized_label} @ {if_pct}%"
    bucket = bucket_label(
        total_minutes=total_minutes,
        if_pct=if_pct,
        segment_count=len(segments),
        segment_minutes=segment_minutes,
        raw_text=raw_text,
    )

    return {
        "owner": owner,
        "source": source,
        "day_utc": day_utc,
        "line_no": line_no,
        "raw_text": raw_text,
        "normalized_label": normalized_label,
        "type": normalized_type,
        "bucket": bucket,
        "label": bucket,
        "duration_label": duration_label,
        "duration_min": round(total_minutes, 1),
        "if_pct": if_pct,
        "segment_count": len(segments),
        "kinds": [type_label(kind) for kind in kinds_seen],
    }


def load_settings(conn: sqlite3.Connection) -> tuple[list[CurvePoint], list[CurvePoint]]:
    rows = conn.execute("select key, value from settings").fetchall()
    settings = {str(key): str(value) for key, value in rows}
    lthr_curve = parse_curve_points(
        settings.get("lthr_curve_v1", ""),
        ("lthr_bpm",),
        DEFAULT_LTHR,
    )
    lt_pace_curve = parse_curve_points(
        settings.get("lt_pace_curve_v1", ""),
        ("lt_pace_sec_per_km", "lt_pace_sec"),
        DEFAULT_LT_PACE_SEC_PER_KM,
    )
    return lthr_curve, lt_pace_curve


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type = 'table' and name = ? limit 1",
        (table_name,),
    ).fetchone()
    return row is not None


def export_samples(db_root: Path, limit: int) -> dict[str, Any]:
    rows_out: list[dict[str, Any]] = []
    seen_labels: set[str] = set()

    for db_path in sorted(db_root.glob("*.db")):
        owner = db_path.stem
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        lthr_curve, lt_pace_curve = load_settings(conn) if table_exists(conn, "settings") else (
            [CurvePoint(day=date(2025, 1, 1), value=DEFAULT_LTHR)],
            [CurvePoint(day=date(2025, 1, 1), value=DEFAULT_LT_PACE_SEC_PER_KM)],
        )

        sources: list[tuple[str, str, str]] = []
        if table_exists(conn, "planned_activities"):
            sources.append(("planned", "planned_activities", "workout_text"))
        if table_exists(conn, "custom_activities"):
            sources.append(("custom", "custom_activities", "activity_text"))

        for source_name, table_name, text_column in sources:
            query = (
                f"select day_utc, line_no, {text_column} as raw_text, parsed_json "
                f"from {table_name} order by day_utc desc, line_no desc"
            )
            for row in conn.execute(query):
                normalized = normalize_row(
                    owner=owner,
                    source=source_name,
                    day_utc=str(row["day_utc"] or ""),
                    line_no=int(row["line_no"] or 0),
                    raw_text=str(row["raw_text"] or ""),
                    parsed_json=str(row["parsed_json"] or ""),
                    lthr_curve=lthr_curve,
                    lt_pace_curve=lt_pace_curve,
                )
                if normalized is None:
                    continue
                label_key = normalized["normalized_label"].lower()
                if label_key in seen_labels:
                    continue
                seen_labels.add(label_key)
                rows_out.append(normalized)

        conn.close()

    required_limit = max(limit, MIN_PER_BUCKET * len(PRIMARY_BUCKETS))
    completed_rows = fabricate_bucket_examples(rows_out, MIN_PER_BUCKET)
    selected_cards = select_balanced_cards(completed_rows, required_limit)
    bucket_counts: dict[str, int] = {}
    for card in selected_cards:
        bucket = str(card.get("bucket") or "other")
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    return {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "db_root": str(db_root),
        "count": len(selected_cards),
        "bucket_counts": bucket_counts,
        "buckets": PRIMARY_BUCKETS,
        "minimum_per_bucket": MIN_PER_BUCKET,
        "cards": selected_cards,
    }


def main() -> None:
    args = parse_args()
    payload = export_samples(
        db_root=Path(args.db_root),
        limit=max(1, int(args.limit)),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {payload['count']} cards to {output_path}")


if __name__ == "__main__":
    main()

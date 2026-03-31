from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

UTC_NOW = lambda: datetime.now(timezone.utc).isoformat()
DB_FILE_MAX_BYTES = int(os.getenv("TEMPERANCE_DB_MAX_BYTES", str(1 * 1024 * 1024 * 1024)))
DB_EXECUTEMANY_CHUNK_SIZE = max(int(os.getenv("TEMPERANCE_DB_EXECUTEMANY_CHUNK_SIZE", "10")), 1)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS activities (
    activity_id TEXT PRIMARY KEY,
    start_time_utc TEXT NOT NULL,
    sport_type TEXT NOT NULL,
    distance_m REAL,
    duration_s REAL,
    avg_hr REAL,
    max_hr REAL,
    avg_pace_s_per_km REAL,
    elevation_gain_m REAL,
    elevation_loss_m REAL,
    avg_cadence REAL,
    max_cadence REAL,
    avg_stride_length REAL,
    vertical_ratio REAL,
    vertical_oscillation REAL,
    running_power_avg REAL,
    running_power_max REAL,
    stamina_start REAL,
    stamina_end REAL,
    training_effect_aerobic REAL,
    training_effect_anaerobic REAL,
    performance_condition REAL,
    device_name TEXT,
    manufacturer TEXT,
    activity_uuid TEXT,
    owner_id TEXT,
    owner_full_name TEXT,
    elapsed_duration_s REAL,
    moving_duration_s REAL,
    average_speed_mps REAL,
    activity_type_key TEXT,
    activity_type_id REAL,
    hr_time_in_zone_1 REAL,
    hr_time_in_zone_2 REAL,
    hr_time_in_zone_3 REAL,
    hr_time_in_zone_4 REAL,
    hr_time_in_zone_5 REAL,
    difference_body_battery REAL,
    bmr_calories REAL,
    is_pr REAL,
    split_summaries_json TEXT,
    training_load_garmin REAL,
    training_load_garmin_field_name TEXT,
    training_load_garmin_units TEXT,
    calories_active REAL,
    calories_total REAL,
    intensity_minutes_vigorous REAL,
    intensity_minutes_moderate REAL,
    trimp REAL,
    is_invalid INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_details (
    activity_id TEXT PRIMARY KEY,
    details_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(activity_id) REFERENCES activities(activity_id)
);

CREATE TABLE IF NOT EXISTS activity_records (
    activity_id TEXT NOT NULL,
    record_time_utc TEXT NOT NULL,
    heart_rate REAL,
    cadence REAL,
    step_length REAL,
    stride_length REAL,
    vertical_ratio REAL,
    vertical_oscillation REAL,
    power REAL,
    grade REAL,
    altitude REAL,
    speed REAL,
    distance REAL,
    stamina REAL,
    raw_json TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (activity_id, record_time_utc),
    FOREIGN KEY(activity_id) REFERENCES activities(activity_id)
);

CREATE TABLE IF NOT EXISTS activity_splits (
    activity_id TEXT PRIMARY KEY,
    split_json TEXT,
    split_summaries_json TEXT,
    lap_count REAL,
    total_duration_s REAL,
    total_distance_m REAL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(activity_id) REFERENCES activities(activity_id)
);

CREATE TABLE IF NOT EXISTS sleep_daily (
    day_utc TEXT PRIMARY KEY,
    sleep_score REAL,
    sleep_duration_s REAL,
    deep_sleep_s REAL,
    rem_sleep_s REAL,
    light_sleep_s REAL,
    awake_s REAL,
    sleep_start_utc TEXT,
    sleep_end_utc TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wellness_daily (
    day_utc TEXT PRIMARY KEY,
    resting_hr REAL,
    hrv_status REAL,
    training_readiness REAL,
    stress_avg REAL,
    stress_max REAL,
    body_battery_start REAL,
    body_battery_end REAL,
    body_battery_avg REAL,
    respiration_avg REAL,
    steps REAL,
    intensity_minutes REAL,
    calories_total REAL,
    raw_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_summary (
    day_utc TEXT PRIMARY KEY,
    trimp_total REAL,
    training_load_garmin REAL,
    calories_active REAL,
    calories_total REAL,
    intensity_minutes_vigorous REAL,
    intensity_minutes_moderate REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_connections (
    provider TEXT PRIMARY KEY,
    account_subject TEXT,
    account_email TEXT,
    scopes_json TEXT NOT NULL,
    token_ciphertext TEXT NOT NULL,
    token_expires_at TEXT,
    refresh_expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS planned_activities (
    day_utc TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    workout_text TEXT NOT NULL,
    parsed_json TEXT,
    manual_done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (day_utc, line_no)
);

CREATE TABLE IF NOT EXISTS custom_activities (
    day_utc TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    activity_text TEXT NOT NULL,
    parsed_json TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (day_utc, line_no)
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_time_utc TEXT NOT NULL,
    source TEXT NOT NULL,
    success INTEGER NOT NULL,
    message TEXT
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time_utc);
CREATE INDEX IF NOT EXISTS idx_activity_records_activity_time ON activity_records(activity_id, record_time_utc);
CREATE INDEX IF NOT EXISTS idx_activity_splits_activity ON activity_splits(activity_id);
CREATE INDEX IF NOT EXISTS idx_daily_summary_day ON daily_summary(day_utc);
CREATE INDEX IF NOT EXISTS idx_sync_log_time ON sync_log(sync_time_utc DESC);
CREATE INDEX IF NOT EXISTS idx_planned_activities_day ON planned_activities(day_utc);
CREATE INDEX IF NOT EXISTS idx_custom_activities_day ON custom_activities(day_utc);
CREATE INDEX IF NOT EXISTS idx_oauth_connections_provider ON oauth_connections(provider);
"""


def get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        page_size_row = conn.execute("PRAGMA page_size").fetchone()
        page_size = int(page_size_row[0]) if page_size_row and page_size_row[0] else 4096
        page_size = max(page_size, 1024)
        max_pages = max(int(DB_FILE_MAX_BYTES) // page_size, 1)
        conn.execute(f"PRAGMA max_page_count = {int(max_pages)}")
    except Exception:
        # If pragma is unsupported/fails, continue with default SQLite behavior.
        pass
    return conn


def _executemany_in_chunks(
    conn: sqlite3.Connection,
    sql: str,
    rows: list[dict[str, Any]],
    *,
    chunk_size: int = DB_EXECUTEMANY_CHUNK_SIZE,
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    if not rows:
        return 0
    effective_chunk_size = max(int(chunk_size), 1)
    start_total_changes = conn.total_changes
    total_rows = len(rows)
    processed_rows = 0
    for idx in range(0, len(rows), effective_chunk_size):
        batch = rows[idx : idx + effective_chunk_size]
        conn.executemany(sql, batch)
        processed_rows += len(batch)
        if progress_cb is not None:
            progress_cb(processed_rows, total_rows)
    return conn.total_changes - start_total_changes


def run_migrations(db_path: Path) -> None:
    # v1 canonical schema: no legacy backfill migrations.
    with closing(get_conn(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                applied_at TEXT NOT NULL
            )
            """
        )
        # Ensure split table exists for optional split-based method.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_splits (
                activity_id TEXT PRIMARY KEY,
                split_json TEXT,
                split_summaries_json TEXT,
                lap_count REAL,
                total_duration_s REAL,
                total_distance_m REAL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planned_activities (
                day_utc TEXT NOT NULL,
                line_no INTEGER NOT NULL,
                workout_text TEXT NOT NULL,
                parsed_json TEXT,
                manual_done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (day_utc, line_no)
            )
            """
        )
        existing_cols = {
            str(r["name"])
            for r in conn.execute("PRAGMA table_info(planned_activities)").fetchall()
        }
        if "manual_done" not in existing_cols:
            conn.execute(
                """
                ALTER TABLE planned_activities
                ADD COLUMN manual_done INTEGER NOT NULL DEFAULT 0
                """
            )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_planned_activities_day
            ON planned_activities(day_utc)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_activities (
                day_utc TEXT NOT NULL,
                line_no INTEGER NOT NULL,
                activity_text TEXT NOT NULL,
                parsed_json TEXT,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (day_utc, line_no)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_custom_activities_day
            ON custom_activities(day_utc)
            """
        )
        activity_cols = {
            str(r["name"])
            for r in conn.execute("PRAGMA table_info(activities)").fetchall()
        }
        if "is_invalid" not in activity_cols:
            conn.execute(
                """
                ALTER TABLE activities
                ADD COLUMN is_invalid INTEGER NOT NULL DEFAULT 0
                """
            )
        conn.commit()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(get_conn(db_path)) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    run_migrations(db_path)


def upsert_activities(
    db_path: Path,
    activities: list[dict[str, Any]],
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    if not activities:
        return 0

    now = UTC_NOW()
    params = [
        {
            "activity_id": row.get("activity_id"),
            "start_time_utc": row.get("start_time_utc"),
            "sport_type": row.get("sport_type") or "unknown",
            "distance_m": row.get("distance_m"),
            "duration_s": row.get("duration_s"),
            "avg_hr": row.get("avg_hr"),
            "max_hr": row.get("max_hr"),
            "avg_pace_s_per_km": row.get("avg_pace_s_per_km"),
            "elevation_gain_m": row.get("elevation_gain_m"),
            "elevation_loss_m": row.get("elevation_loss_m"),
            "avg_cadence": row.get("avg_cadence"),
            "max_cadence": row.get("max_cadence"),
            "avg_stride_length": row.get("avg_stride_length"),
            "vertical_ratio": row.get("vertical_ratio"),
            "vertical_oscillation": row.get("vertical_oscillation"),
            "running_power_avg": row.get("running_power_avg"),
            "running_power_max": row.get("running_power_max"),
            "stamina_start": row.get("stamina_start"),
            "stamina_end": row.get("stamina_end"),
            "training_effect_aerobic": row.get("training_effect_aerobic"),
            "training_effect_anaerobic": row.get("training_effect_anaerobic"),
            "performance_condition": row.get("performance_condition"),
            "device_name": row.get("device_name"),
            "manufacturer": row.get("manufacturer"),
            "activity_uuid": row.get("activity_uuid"),
            "owner_id": row.get("owner_id"),
            "owner_full_name": row.get("owner_full_name"),
            "elapsed_duration_s": row.get("elapsed_duration_s"),
            "moving_duration_s": row.get("moving_duration_s"),
            "average_speed_mps": row.get("average_speed_mps"),
            "activity_type_key": row.get("activity_type_key"),
            "activity_type_id": row.get("activity_type_id"),
            "hr_time_in_zone_1": row.get("hr_time_in_zone_1"),
            "hr_time_in_zone_2": row.get("hr_time_in_zone_2"),
            "hr_time_in_zone_3": row.get("hr_time_in_zone_3"),
            "hr_time_in_zone_4": row.get("hr_time_in_zone_4"),
            "hr_time_in_zone_5": row.get("hr_time_in_zone_5"),
            "difference_body_battery": row.get("difference_body_battery"),
            "bmr_calories": row.get("bmr_calories"),
            "is_pr": row.get("is_pr"),
            "split_summaries_json": row.get("split_summaries_json"),
            "training_load_garmin": row.get("training_load_garmin"),
            "training_load_garmin_field_name": row.get("training_load_garmin_field_name"),
            "training_load_garmin_units": row.get("training_load_garmin_units"),
            "calories_active": row.get("calories_active"),
            "calories_total": row.get("calories_total"),
            "intensity_minutes_vigorous": row.get("intensity_minutes_vigorous"),
            "intensity_minutes_moderate": row.get("intensity_minutes_moderate"),
            "trimp": row.get("trimp"),
            "source": row.get("source") or "unknown",
            "raw_json": json.dumps(row.get("raw", {}), default=str),
            "created_at": now,
            "updated_at": now,
        }
        for row in activities
    ]
    with closing(get_conn(db_path)) as conn:
        changed = _executemany_in_chunks(
            conn,
            """
            INSERT INTO activities (
                activity_id, start_time_utc, sport_type, distance_m, duration_s,
                avg_hr, max_hr, avg_pace_s_per_km, elevation_gain_m, elevation_loss_m,
                avg_cadence, max_cadence, avg_stride_length, vertical_ratio,
                vertical_oscillation, running_power_avg, running_power_max,
                stamina_start, stamina_end, training_effect_aerobic,
                training_effect_anaerobic, performance_condition, device_name,
                manufacturer, activity_uuid, owner_id, owner_full_name,
                elapsed_duration_s, moving_duration_s, average_speed_mps,
                activity_type_key, activity_type_id, hr_time_in_zone_1,
                hr_time_in_zone_2, hr_time_in_zone_3, hr_time_in_zone_4,
                hr_time_in_zone_5, difference_body_battery, bmr_calories,
                is_pr, split_summaries_json, training_load_garmin,
                training_load_garmin_field_name, training_load_garmin_units,
                calories_active, calories_total, intensity_minutes_vigorous,
                intensity_minutes_moderate, trimp, source, raw_json,
                created_at, updated_at
            ) VALUES (
                :activity_id, :start_time_utc, :sport_type, :distance_m, :duration_s,
                :avg_hr, :max_hr, :avg_pace_s_per_km, :elevation_gain_m, :elevation_loss_m,
                :avg_cadence, :max_cadence, :avg_stride_length, :vertical_ratio,
                :vertical_oscillation, :running_power_avg, :running_power_max,
                :stamina_start, :stamina_end, :training_effect_aerobic,
                :training_effect_anaerobic, :performance_condition, :device_name,
                :manufacturer, :activity_uuid, :owner_id, :owner_full_name,
                :elapsed_duration_s, :moving_duration_s, :average_speed_mps,
                :activity_type_key, :activity_type_id, :hr_time_in_zone_1,
                :hr_time_in_zone_2, :hr_time_in_zone_3, :hr_time_in_zone_4,
                :hr_time_in_zone_5, :difference_body_battery, :bmr_calories,
                :is_pr, :split_summaries_json, :training_load_garmin,
                :training_load_garmin_field_name, :training_load_garmin_units,
                :calories_active, :calories_total, :intensity_minutes_vigorous,
                :intensity_minutes_moderate, :trimp, :source, :raw_json,
                :created_at, :updated_at
            )
            ON CONFLICT(activity_id) DO UPDATE SET
                start_time_utc=excluded.start_time_utc,
                sport_type=excluded.sport_type,
                distance_m=excluded.distance_m,
                duration_s=excluded.duration_s,
                avg_hr=excluded.avg_hr,
                max_hr=excluded.max_hr,
                avg_pace_s_per_km=excluded.avg_pace_s_per_km,
                elevation_gain_m=excluded.elevation_gain_m,
                elevation_loss_m=excluded.elevation_loss_m,
                avg_cadence=excluded.avg_cadence,
                max_cadence=excluded.max_cadence,
                avg_stride_length=excluded.avg_stride_length,
                vertical_ratio=excluded.vertical_ratio,
                vertical_oscillation=excluded.vertical_oscillation,
                running_power_avg=excluded.running_power_avg,
                running_power_max=excluded.running_power_max,
                stamina_start=excluded.stamina_start,
                stamina_end=excluded.stamina_end,
                training_effect_aerobic=excluded.training_effect_aerobic,
                training_effect_anaerobic=excluded.training_effect_anaerobic,
                performance_condition=excluded.performance_condition,
                device_name=excluded.device_name,
                manufacturer=excluded.manufacturer,
                activity_uuid=excluded.activity_uuid,
                owner_id=excluded.owner_id,
                owner_full_name=excluded.owner_full_name,
                elapsed_duration_s=excluded.elapsed_duration_s,
                moving_duration_s=excluded.moving_duration_s,
                average_speed_mps=excluded.average_speed_mps,
                activity_type_key=excluded.activity_type_key,
                activity_type_id=excluded.activity_type_id,
                hr_time_in_zone_1=excluded.hr_time_in_zone_1,
                hr_time_in_zone_2=excluded.hr_time_in_zone_2,
                hr_time_in_zone_3=excluded.hr_time_in_zone_3,
                hr_time_in_zone_4=excluded.hr_time_in_zone_4,
                hr_time_in_zone_5=excluded.hr_time_in_zone_5,
                difference_body_battery=excluded.difference_body_battery,
                bmr_calories=excluded.bmr_calories,
                is_pr=excluded.is_pr,
                split_summaries_json=excluded.split_summaries_json,
                training_load_garmin=excluded.training_load_garmin,
                training_load_garmin_field_name=excluded.training_load_garmin_field_name,
                training_load_garmin_units=excluded.training_load_garmin_units,
                calories_active=excluded.calories_active,
                calories_total=excluded.calories_total,
                intensity_minutes_vigorous=excluded.intensity_minutes_vigorous,
                intensity_minutes_moderate=excluded.intensity_minutes_moderate,
                trimp=excluded.trimp,
                source=excluded.source,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            params,
            progress_cb=progress_cb,
        )
        conn.commit()
        return changed


def upsert_activity_details(
    db_path: Path,
    details: list[dict[str, Any]],
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    if not details:
        return 0

    now = UTC_NOW()
    params = [
        {
            "activity_id": row["activity_id"],
            "details_json": json.dumps(row.get("details", {}), default=str),
            "updated_at": now,
        }
        for row in details
    ]
    with closing(get_conn(db_path)) as conn:
        changed = _executemany_in_chunks(
            conn,
            """
            INSERT INTO activity_details(activity_id, details_json, updated_at)
            VALUES (:activity_id, :details_json, :updated_at)
            ON CONFLICT(activity_id) DO UPDATE SET
                details_json=excluded.details_json,
                updated_at=excluded.updated_at
            WHERE activity_details.details_json IS NOT excluded.details_json
            """,
            params,
            progress_cb=progress_cb,
        )
        conn.commit()
        return changed


def upsert_activity_records(
    db_path: Path,
    records: list[dict[str, Any]],
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    if not records:
        return 0

    now = UTC_NOW()
    params = [
        {
            "activity_id": row.get("activity_id"),
            "record_time_utc": row.get("record_time_utc"),
            "heart_rate": row.get("heart_rate"),
            "cadence": row.get("cadence"),
            "step_length": row.get("step_length"),
            "stride_length": row.get("stride_length"),
            "vertical_ratio": row.get("vertical_ratio"),
            "vertical_oscillation": row.get("vertical_oscillation"),
            "power": row.get("power"),
            "grade": row.get("grade"),
            "altitude": row.get("altitude"),
            "speed": row.get("speed"),
            "distance": row.get("distance"),
            "stamina": row.get("stamina"),
            "raw_json": json.dumps(row.get("raw", {}), default=str),
            "updated_at": now,
        }
        for row in records
    ]
    with closing(get_conn(db_path)) as conn:
        changed = _executemany_in_chunks(
            conn,
            """
            INSERT INTO activity_records (
                activity_id, record_time_utc, heart_rate, cadence, step_length,
                stride_length, vertical_ratio, vertical_oscillation, power,
                grade, altitude, speed, distance, stamina, raw_json, updated_at
            ) VALUES (
                :activity_id, :record_time_utc, :heart_rate, :cadence, :step_length,
                :stride_length, :vertical_ratio, :vertical_oscillation, :power,
                :grade, :altitude, :speed, :distance, :stamina, :raw_json, :updated_at
            )
            ON CONFLICT(activity_id, record_time_utc) DO UPDATE SET
                heart_rate=excluded.heart_rate,
                cadence=excluded.cadence,
                step_length=excluded.step_length,
                stride_length=excluded.stride_length,
                vertical_ratio=excluded.vertical_ratio,
                vertical_oscillation=excluded.vertical_oscillation,
                power=excluded.power,
                grade=excluded.grade,
                altitude=excluded.altitude,
                speed=excluded.speed,
                distance=excluded.distance,
                stamina=excluded.stamina,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            params,
            progress_cb=progress_cb,
        )
        conn.commit()
        return changed


def upsert_activity_splits(
    db_path: Path,
    rows: list[dict[str, Any]],
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    if not rows:
        return 0

    now = UTC_NOW()
    params = [
        {
            "activity_id": row.get("activity_id"),
            "split_json": json.dumps(row.get("split"), default=str),
            "split_summaries_json": json.dumps(row.get("split_summaries"), default=str),
            "lap_count": row.get("lap_count"),
            "total_duration_s": row.get("total_duration_s"),
            "total_distance_m": row.get("total_distance_m"),
            "updated_at": now,
        }
        for row in rows
    ]
    with closing(get_conn(db_path)) as conn:
        changed = _executemany_in_chunks(
            conn,
            """
            INSERT INTO activity_splits (
                activity_id, split_json, split_summaries_json, lap_count,
                total_duration_s, total_distance_m, updated_at
            ) VALUES (
                :activity_id, :split_json, :split_summaries_json, :lap_count,
                :total_duration_s, :total_distance_m, :updated_at
            )
            ON CONFLICT(activity_id) DO UPDATE SET
                split_json=excluded.split_json,
                split_summaries_json=excluded.split_summaries_json,
                lap_count=excluded.lap_count,
                total_duration_s=excluded.total_duration_s,
                total_distance_m=excluded.total_distance_m,
                updated_at=excluded.updated_at
            """,
            params,
            progress_cb=progress_cb,
        )
        conn.commit()
        return changed


def upsert_sleep_daily(
    db_path: Path,
    rows: list[dict[str, Any]],
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    if not rows:
        return 0

    now = UTC_NOW()
    params = [
        {
            **row,
            "raw_json": json.dumps(row.get("raw", {}), default=str),
            "updated_at": now,
        }
        for row in rows
    ]
    with closing(get_conn(db_path)) as conn:
        changed = _executemany_in_chunks(
            conn,
            """
            INSERT INTO sleep_daily (
                day_utc, sleep_score, sleep_duration_s, deep_sleep_s,
                rem_sleep_s, light_sleep_s, awake_s, sleep_start_utc,
                sleep_end_utc, raw_json, updated_at
            ) VALUES (
                :day_utc, :sleep_score, :sleep_duration_s, :deep_sleep_s,
                :rem_sleep_s, :light_sleep_s, :awake_s, :sleep_start_utc,
                :sleep_end_utc, :raw_json, :updated_at
            )
            ON CONFLICT(day_utc) DO UPDATE SET
                sleep_score=excluded.sleep_score,
                sleep_duration_s=excluded.sleep_duration_s,
                deep_sleep_s=excluded.deep_sleep_s,
                rem_sleep_s=excluded.rem_sleep_s,
                light_sleep_s=excluded.light_sleep_s,
                awake_s=excluded.awake_s,
                sleep_start_utc=excluded.sleep_start_utc,
                sleep_end_utc=excluded.sleep_end_utc,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            params,
            progress_cb=progress_cb,
        )
        conn.commit()
        return changed


def upsert_wellness_daily(
    db_path: Path,
    rows: list[dict[str, Any]],
    *,
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    if not rows:
        return 0

    now = UTC_NOW()
    params = [
        {
            **row,
            "raw_json": json.dumps(row.get("raw", {}), default=str),
            "updated_at": now,
        }
        for row in rows
    ]
    with closing(get_conn(db_path)) as conn:
        changed = _executemany_in_chunks(
            conn,
            """
            INSERT INTO wellness_daily (
                day_utc, resting_hr, hrv_status, training_readiness,
                stress_avg, stress_max, body_battery_start, body_battery_end,
                body_battery_avg, respiration_avg, steps, intensity_minutes,
                calories_total, raw_json, updated_at
            ) VALUES (
                :day_utc, :resting_hr, :hrv_status, :training_readiness,
                :stress_avg, :stress_max, :body_battery_start, :body_battery_end,
                :body_battery_avg, :respiration_avg, :steps, :intensity_minutes,
                :calories_total, :raw_json, :updated_at
            )
            ON CONFLICT(day_utc) DO UPDATE SET
                resting_hr=excluded.resting_hr,
                hrv_status=excluded.hrv_status,
                training_readiness=excluded.training_readiness,
                stress_avg=excluded.stress_avg,
                stress_max=excluded.stress_max,
                body_battery_start=excluded.body_battery_start,
                body_battery_end=excluded.body_battery_end,
                body_battery_avg=excluded.body_battery_avg,
                respiration_avg=excluded.respiration_avg,
                steps=excluded.steps,
                intensity_minutes=excluded.intensity_minutes,
                calories_total=excluded.calories_total,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            params,
            progress_cb=progress_cb,
        )
        conn.commit()
        return changed


def get_runs_df(db_path: Path, include_invalid: bool = False) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        # Avoid loading heavy raw payload blobs on every rerun; charts/metrics do not use raw_json.
        cols = [
            row["name"]
            for row in conn.execute("PRAGMA table_info(activities)").fetchall()
            if str(row["name"]) != "raw_json"
        ]
        col_sql = ", ".join([f'"{c}"' for c in cols]) if cols else "*"
        where_sql = "" if include_invalid else "WHERE COALESCE(is_invalid, 0) = 0"
        return pd.read_sql_query(
            f"SELECT {col_sql} FROM activities {where_sql} ORDER BY start_time_utc DESC",
            conn,
        )


def set_activity_invalid(
    db_path: Path,
    activity_id: str,
    is_invalid: bool,
) -> bool:
    with closing(get_conn(db_path)) as conn:
        cursor = conn.execute(
            """
            UPDATE activities
            SET is_invalid = ?, updated_at = ?
            WHERE activity_id = ?
            """,
            (
                int(bool(is_invalid)),
                UTC_NOW(),
                str(activity_id or "").strip(),
            ),
        )
        conn.commit()
        return max(int(cursor.rowcount or 0), 0) > 0


def upsert_activity_trimp(db_path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            UPDATE activities
            SET trimp = :trimp, updated_at = :updated_at
            WHERE activity_id = :activity_id
            """,
            [
                {
                    "activity_id": row["activity_id"],
                    "trimp": row.get("trimp"),
                    "updated_at": now,
                }
                for row in rows
            ],
        )
        conn.commit()
        return conn.total_changes


def upsert_daily_summary(db_path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO daily_summary(
                day_utc, trimp_total, training_load_garmin,
                calories_active, calories_total, intensity_minutes_vigorous,
                intensity_minutes_moderate, updated_at
            ) VALUES (
                :day_utc, :trimp_total, :training_load_garmin,
                :calories_active, :calories_total, :intensity_minutes_vigorous,
                :intensity_minutes_moderate, :updated_at
            )
            ON CONFLICT(day_utc) DO UPDATE SET
                trimp_total=excluded.trimp_total,
                training_load_garmin=excluded.training_load_garmin,
                calories_active=excluded.calories_active,
                calories_total=excluded.calories_total,
                intensity_minutes_vigorous=excluded.intensity_minutes_vigorous,
                intensity_minutes_moderate=excluded.intensity_minutes_moderate,
                updated_at=excluded.updated_at
            """,
            [{**row, "updated_at": now} for row in rows],
        )
        conn.commit()
        return conn.total_changes


def get_daily_summary_df(db_path: Path) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT day_utc, trimp_total, training_load_garmin,
                   calories_active, calories_total, intensity_minutes_vigorous,
                   intensity_minutes_moderate
            FROM daily_summary
            ORDER BY day_utc ASC
            """,
            conn,
        )


def get_activity_splits_summary_df(db_path: Path) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT activity_id, lap_count, total_duration_s, total_distance_m
            FROM activity_splits
            ORDER BY activity_id
            """,
            conn,
        )


def get_activity_splits_df(db_path: Path) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT activity_id, split_json, split_summaries_json, lap_count, total_duration_s, total_distance_m
            FROM activity_splits
            ORDER BY activity_id
            """,
            conn,
        )


def get_activity_records_df(db_path: Path, activity_id: str) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT record_time_utc, heart_rate, cadence, step_length, stride_length,
                   vertical_ratio, vertical_oscillation, power, grade, altitude,
                   speed, distance, stamina, raw_json
            FROM activity_records
            WHERE activity_id = ?
            ORDER BY record_time_utc
            """,
            conn,
            params=(activity_id,),
        )


def get_activity_splits_raw(db_path: Path, activity_id: str) -> dict[str, Any] | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            """
            SELECT split_json, split_summaries_json, lap_count, total_duration_s, total_distance_m
            FROM activity_splits
            WHERE activity_id = ?
            """,
            (activity_id,),
        ).fetchone()
    if not row:
        return None
    out: dict[str, Any] = {
        "lap_count": float(row["lap_count"]) if row["lap_count"] is not None else None,
        "total_duration_s": float(row["total_duration_s"]) if row["total_duration_s"] is not None else None,
        "total_distance_m": float(row["total_distance_m"]) if row["total_distance_m"] is not None else None,
    }
    try:
        out["split"] = json.loads(row["split_json"]) if row["split_json"] else {}
    except Exception:
        out["split"] = {}
    try:
        out["split_summaries"] = json.loads(row["split_summaries_json"]) if row["split_summaries_json"] else {}
    except Exception:
        out["split_summaries"] = {}
    return out


def get_activity_raw(db_path: Path, activity_id: str) -> dict[str, Any] | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            "SELECT raw_json FROM activities WHERE activity_id = ?",
            (activity_id,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["raw_json"]) if row["raw_json"] else {}


def get_activity_local_start_map(db_path: Path, activity_ids: list[str]) -> dict[str, str]:
    ids = [str(activity_id or "").strip() for activity_id in activity_ids if str(activity_id or "").strip()]
    if not ids:
        return {}

    placeholders = ", ".join(["?"] * len(ids))
    with closing(get_conn(db_path)) as conn:
        rows = conn.execute(
            f"SELECT activity_id, raw_json FROM activities WHERE activity_id IN ({placeholders})",
            ids,
        ).fetchall()

    out: dict[str, str] = {}
    for row in rows:
        activity_id = str(row["activity_id"] or "").strip()
        raw = row["raw_json"]
        if not activity_id or not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        local_start = str(payload.get("startTimeLocal") or "").strip()
        if local_start:
            out[activity_id] = local_start
    return out


def get_activity_detail_raw(db_path: Path, activity_id: str) -> dict[str, Any] | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            "SELECT details_json FROM activity_details WHERE activity_id = ?",
            (activity_id,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["details_json"]) if row["details_json"] else {}


def get_latest_activity_time(db_path: Path) -> datetime | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            "SELECT MAX(start_time_utc) AS latest FROM activities"
        ).fetchone()
    if not row or not row["latest"]:
        return None
    return datetime.fromisoformat(row["latest"].replace("Z", "+00:00"))


def get_earliest_activity_time(db_path: Path) -> datetime | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            "SELECT MIN(start_time_utc) AS earliest FROM activities"
        ).fetchone()
    if not row or not row["earliest"]:
        return None
    return datetime.fromisoformat(row["earliest"].replace("Z", "+00:00"))


def get_latest_recovery_day(db_path: Path) -> datetime | None:
    """
    Latest available recovery date across sleep_daily and wellness_daily.
    Returned as UTC midnight datetime for anchor calculations.
    """
    with closing(get_conn(db_path)) as conn:
        sleep_row = conn.execute("SELECT MAX(day_utc) AS latest FROM sleep_daily").fetchone()
        wellness_row = conn.execute("SELECT MAX(day_utc) AS latest FROM wellness_daily").fetchone()

    latest_day: str | None = None
    for row in (sleep_row, wellness_row):
        if row and row["latest"]:
            day = str(row["latest"])
            if latest_day is None or day > latest_day:
                latest_day = day

    if not latest_day:
        return None
    return datetime.fromisoformat(f"{latest_day}T00:00:00+00:00")


def get_activity_days(db_path: Path) -> set[date]:
    with closing(get_conn(db_path)) as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(start_time_utc, 1, 10) AS day_utc FROM activities WHERE start_time_utc IS NOT NULL"
        ).fetchall()
    out: set[date] = set()
    for row in rows:
        day_raw = row["day_utc"] if row else None
        if not day_raw:
            continue
        try:
            out.add(datetime.fromisoformat(f"{day_raw}T00:00:00+00:00").date())
        except Exception:
            continue
    return out


def get_recovery_days(db_path: Path) -> set[date]:
    with closing(get_conn(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT day_utc FROM sleep_daily
            UNION
            SELECT day_utc FROM wellness_daily
            """
        ).fetchall()
    out: set[date] = set()
    for row in rows:
        day_raw = row["day_utc"] if row else None
        if not day_raw:
            continue
        try:
            out.add(datetime.fromisoformat(f"{day_raw}T00:00:00+00:00").date())
        except Exception:
            continue
    return out


def get_activities_cache_key(db_path: Path) -> str:
    """
    Stable digest for activity-table-driven computation caching.
    Changes whenever activities content is updated (via updated_at/count).
    """
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n,
                   MAX(updated_at) AS max_updated_at,
                   MAX(start_time_utc) AS max_start_time
            FROM activities
            """
        ).fetchone()
    if not row:
        return "0:none:none"
    return f"{int(row['n'] or 0)}:{row['max_updated_at'] or 'none'}:{row['max_start_time'] or 'none'}"


def get_activity_splits_cache_key(db_path: Path) -> str:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n, MAX(updated_at) AS max_updated_at
            FROM activity_splits
            """
        ).fetchone()
    if not row:
        return "0:none"
    return f"{int(row['n'] or 0)}:{row['max_updated_at'] or 'none'}"


def get_custom_activities_cache_key(db_path: Path) -> str:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n, MAX(updated_at) AS max_updated_at, MAX(day_utc) AS max_day
            FROM custom_activities
            """
        ).fetchone()
    if not row:
        return "0:none:none"
    return f"{int(row['n'] or 0)}:{row['max_updated_at'] or 'none'}:{row['max_day'] or 'none'}"


def get_planned_activities_cache_key(db_path: Path) -> str:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n, MAX(updated_at) AS max_updated_at, MAX(day_utc) AS max_day
            FROM planned_activities
            """
        ).fetchone()
    if not row:
        return "0:none:none"
    return f"{int(row['n'] or 0)}:{row['max_updated_at'] or 'none'}:{row['max_day'] or 'none'}"


def get_table_counts(db_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    tables = [
        "activities",
        "activity_details",
        "activity_records",
        "activity_splits",
        "sleep_daily",
        "wellness_daily",
        "daily_summary",
        "planned_activities",
        "custom_activities",
    ]
    with closing(get_conn(db_path)) as conn:
        for table in tables:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            counts[table] = int(row["n"]) if row else 0
    return counts


def get_sleep_df(db_path: Path) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT day_utc, sleep_score, sleep_duration_s, deep_sleep_s,
                   rem_sleep_s, light_sleep_s, awake_s, sleep_start_utc, sleep_end_utc
            FROM sleep_daily
            ORDER BY day_utc DESC
            """,
            conn,
        )


def get_wellness_df(db_path: Path) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT day_utc, resting_hr, hrv_status, training_readiness, stress_avg,
                   stress_max, body_battery_start, body_battery_end, body_battery_avg,
                   respiration_avg, steps, intensity_minutes, calories_total
            FROM wellness_daily
            ORDER BY day_utc DESC
            """,
            conn,
        )


def save_setting(db_path: Path, key: str, value: str) -> None:
    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
        conn.commit()


def save_setting_if_changed(db_path: Path, key: str, value: str) -> bool:
    existing = get_setting(db_path, key)
    if existing == value:
        return False
    save_setting(db_path, key, value)
    return True


def get_setting(db_path: Path, key: str) -> str | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def upsert_oauth_connection(
    db_path: Path,
    *,
    provider: str,
    account_subject: str | None,
    account_email: str | None,
    scopes_json: str,
    token_ciphertext: str,
    token_expires_at: str | None,
    refresh_expires_at: str | None,
) -> None:
    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO oauth_connections(
                provider, account_subject, account_email, scopes_json, token_ciphertext,
                token_expires_at, refresh_expires_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                account_subject = excluded.account_subject,
                account_email = excluded.account_email,
                scopes_json = excluded.scopes_json,
                token_ciphertext = excluded.token_ciphertext,
                token_expires_at = excluded.token_expires_at,
                refresh_expires_at = excluded.refresh_expires_at,
                updated_at = excluded.updated_at
            """,
            (
                provider,
                account_subject,
                account_email,
                scopes_json,
                token_ciphertext,
                token_expires_at,
                refresh_expires_at,
                now,
                now,
            ),
        )
        conn.commit()


def get_oauth_connection(db_path: Path, provider: str) -> dict[str, Any] | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            """
            SELECT provider, account_subject, account_email, scopes_json, token_ciphertext,
                   token_expires_at, refresh_expires_at, created_at, updated_at
            FROM oauth_connections
            WHERE provider = ?
            """,
            (provider,),
        ).fetchone()
    return dict(row) if row else None


def delete_oauth_connection(db_path: Path, provider: str) -> bool:
    with closing(get_conn(db_path)) as conn:
        cursor = conn.execute("DELETE FROM oauth_connections WHERE provider = ?", (provider,))
        conn.commit()
    return cursor.rowcount > 0


def log_sync(db_path: Path, source: str, success: bool, message: str = "") -> None:
    with closing(get_conn(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO sync_log(sync_time_utc, source, success, message)
            VALUES (?, ?, ?, ?)
            """,
            (UTC_NOW(), source, int(success), message[:2000]),
        )
        conn.commit()


def get_last_sync(db_path: Path) -> dict[str, Any] | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            """
            SELECT sync_time_utc, source, success, message
            FROM sync_log
            ORDER BY sync_time_utc DESC
            LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def get_last_sync_for_source_like(db_path: Path, pattern: str) -> dict[str, Any] | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            """
            SELECT sync_time_utc, source, success, message
            FROM sync_log
            WHERE lower(source) LIKE lower(?)
            ORDER BY sync_time_utc DESC
            LIMIT 1
            """,
            (pattern,),
        ).fetchone()
    return dict(row) if row else None


def get_planned_activities_df(
    db_path: Path,
    start_day_utc: str | None = None,
    end_day_utc: str | None = None,
) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if start_day_utc:
        where.append("day_utc >= ?")
        params.append(start_day_utc)
    if end_day_utc:
        where.append("day_utc <= ?")
        params.append(end_day_utc)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            f"""
            SELECT day_utc, line_no, workout_text, parsed_json, manual_done, created_at, updated_at
            FROM planned_activities
            {where_sql}
            ORDER BY day_utc ASC, line_no ASC
            """,
            conn,
            params=params,
        )


def replace_planned_activities_for_range(
    db_path: Path,
    start_day_utc: str,
    end_day_utc: str,
    rows: list[dict[str, Any]],
) -> int:
    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.execute(
            """
            DELETE FROM planned_activities
            WHERE day_utc >= ? AND day_utc <= ?
            """,
            (start_day_utc, end_day_utc),
        )
        if rows:
            conn.executemany(
                """
                INSERT INTO planned_activities (
                    day_utc, line_no, workout_text, parsed_json, manual_done, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(r.get("day_utc") or ""),
                        int(r.get("line_no") or 0),
                        str(r.get("workout_text") or "").strip(),
                        json.dumps(r.get("parsed_json")) if r.get("parsed_json") is not None else None,
                        int(bool(r.get("manual_done", False))),
                        now,
                        now,
                    )
                    for r in rows
                    if str(r.get("day_utc") or "").strip() and str(r.get("workout_text") or "").strip()
                ],
            )
        conn.commit()
    return len(rows)


def delete_planned_activities(
    db_path: Path,
    keys: list[tuple[str, int]],
) -> int:
    if not keys:
        return 0
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            DELETE FROM planned_activities
            WHERE day_utc = ? AND line_no = ?
            """,
            [(str(day), int(line_no)) for day, line_no in keys],
        )
        conn.commit()
    return len(keys)


def set_planned_activity_manual_done(
    db_path: Path,
    day_utc: str,
    line_no: int,
    manual_done: bool,
) -> bool:
    with closing(get_conn(db_path)) as conn:
        cur = conn.execute(
            """
            UPDATE planned_activities
            SET manual_done = ?, updated_at = ?
            WHERE day_utc = ? AND line_no = ?
            """,
            (
                int(bool(manual_done)),
                UTC_NOW(),
                str(day_utc),
                int(line_no),
            ),
        )
        conn.commit()
        return int(cur.rowcount or 0) > 0


def upsert_planned_activities_rows(
    db_path: Path,
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0
    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO planned_activities (
                day_utc, line_no, workout_text, parsed_json, manual_done, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(day_utc, line_no) DO UPDATE SET
                workout_text = excluded.workout_text,
                parsed_json = excluded.parsed_json,
                manual_done = excluded.manual_done,
                updated_at = excluded.updated_at
            """,
            [
                (
                    str(r.get("day_utc") or ""),
                    int(r.get("line_no") or 0),
                    str(r.get("workout_text") or "").strip(),
                    json.dumps(r.get("parsed_json")) if r.get("parsed_json") is not None else None,
                    int(bool(r.get("manual_done", False))),
                    now,
                    now,
                )
                for r in rows
                if str(r.get("day_utc") or "").strip() and str(r.get("workout_text") or "").strip()
            ],
        )
        conn.commit()
    return len(rows)


def get_custom_activities_df(
    db_path: Path,
    start_day_utc: str | None = None,
    end_day_utc: str | None = None,
) -> pd.DataFrame:
    where = []
    params: list[Any] = []
    if start_day_utc:
        where.append("day_utc >= ?")
        params.append(start_day_utc)
    if end_day_utc:
        where.append("day_utc <= ?")
        params.append(end_day_utc)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            f"""
            SELECT day_utc, line_no, activity_text, parsed_json, source, created_at, updated_at
            FROM custom_activities
            {where_sql}
            ORDER BY day_utc ASC, line_no ASC
            """,
            conn,
            params=params,
        )


def delete_custom_activities(
    db_path: Path,
    keys: list[tuple[str, int]],
) -> int:
    if not keys:
        return 0
    with closing(get_conn(db_path)) as conn:
        deleted = 0
        for day, line_no in keys:
            cursor = conn.execute(
                """
                DELETE FROM custom_activities
                WHERE day_utc = ? AND line_no = ?
                """,
                (str(day), int(line_no)),
            )
            deleted += max(int(cursor.rowcount or 0), 0)
        conn.commit()
        return deleted


def upsert_custom_activities_rows(
    db_path: Path,
    rows: list[dict[str, Any]],
    max_rows: int | None = None,
) -> int:
    if not rows:
        return 0
    valid_rows = [
        (
            str(r.get("day_utc") or "").strip(),
            int(r.get("line_no") or 0),
            str(r.get("activity_text") or "").strip(),
            json.dumps(r.get("parsed_json")) if r.get("parsed_json") is not None else None,
            str(r.get("source") or "manual"),
        )
        for r in rows
        if str(r.get("day_utc") or "").strip() and str(r.get("activity_text") or "").strip()
    ]
    if not valid_rows:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        if max_rows is not None and int(max_rows) > 0:
            current_count = int(
                conn.execute("SELECT COUNT(*) AS n FROM custom_activities").fetchone()["n"] or 0
            )
            incoming_keys = {(day_utc, line_no) for day_utc, line_no, *_ in valid_rows}
            existing_keys = 0
            for day_utc, line_no in incoming_keys:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM custom_activities
                    WHERE day_utc = ? AND line_no = ?
                    LIMIT 1
                    """,
                    (day_utc, line_no),
                ).fetchone()
                if row:
                    existing_keys += 1
            delta_new_rows = max(len(incoming_keys) - existing_keys, 0)
            if current_count + delta_new_rows > int(max_rows):
                raise ValueError(
                    f"Custom activities limit reached ({max_rows}). "
                    f"Current={current_count}, incoming_new={delta_new_rows}."
                )

        conn.executemany(
            """
            INSERT INTO custom_activities (
                day_utc, line_no, activity_text, parsed_json, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(day_utc, line_no) DO UPDATE SET
                activity_text = excluded.activity_text,
                parsed_json = excluded.parsed_json,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            [
                (
                    day_utc,
                    line_no,
                    activity_text,
                    parsed_json,
                    source,
                    now,
                    now,
                )
                for day_utc, line_no, activity_text, parsed_json, source in valid_rows
            ],
        )
        conn.commit()
    return len(valid_rows)

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

UTC_NOW = lambda: datetime.now(timezone.utc).isoformat()

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
    moderate_intensity_minutes REAL,
    vigorous_intensity_minutes REAL,
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
    source TEXT NOT NULL,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_metrics (
    activity_id TEXT PRIMARY KEY,
    garmin_training_load REAL,
    garmin_aerobic_te REAL,
    garmin_anaerobic_te REAL,
    garmin_vo2max REAL,
    garmin_calories REAL,
    garmin_avg_power REAL,
    garmin_norm_power REAL,
    garmin_training_effect_label TEXT,
    raw_json TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(activity_id) REFERENCES activities(activity_id)
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

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS daily_summary (
    day_utc TEXT PRIMARY KEY,
    activities_count INTEGER,
    trimp_total REAL,
    training_load_garmin REAL,
    calories_active REAL,
    calories_total REAL,
    intensity_minutes_vigorous REAL,
    intensity_minutes_moderate REAL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time_utc);
CREATE INDEX IF NOT EXISTS idx_activity_records_activity_time ON activity_records(activity_id, record_time_utc);
CREATE INDEX IF NOT EXISTS idx_daily_summary_day ON daily_summary(day_utc);
CREATE INDEX IF NOT EXISTS idx_sync_log_time ON sync_log(sync_time_utc DESC);
"""


def get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r["name"]) == column for r in rows)


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def run_migrations(db_path: Path) -> None:
    migrations: list[tuple[str, Callable[[sqlite3.Connection], None]]] = [
        ("001_expand_activity_summary_fields", _migration_expand_activity_summary_fields),
        ("002_add_activity_records", _migration_add_activity_records),
        ("003_expand_daily_monitoring", _migration_expand_daily_monitoring),
        ("004_expand_activity_training_context", _migration_expand_activity_training_context),
        ("005_v1_primary_garmin_metrics", _migration_v1_primary_garmin_metrics),
    ]

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

        applied = {
            row["name"]
            for row in conn.execute("SELECT name FROM schema_migrations").fetchall()
        }

        for name, migration_fn in migrations:
            if name in applied:
                continue
            migration_fn(conn)
            conn.execute(
                "INSERT INTO schema_migrations(name, applied_at) VALUES (?, ?)",
                (name, UTC_NOW()),
            )
        conn.commit()


def _migration_expand_activity_summary_fields(conn: sqlite3.Connection) -> None:
    fields = {
        "elevation_loss_m": "REAL",
        "avg_cadence": "REAL",
        "max_cadence": "REAL",
        "avg_stride_length": "REAL",
        "vertical_ratio": "REAL",
        "vertical_oscillation": "REAL",
        "running_power_avg": "REAL",
        "running_power_max": "REAL",
        "stamina_start": "REAL",
        "stamina_end": "REAL",
        "training_effect_aerobic": "REAL",
        "training_effect_anaerobic": "REAL",
        "performance_condition": "REAL",
        "device_name": "TEXT",
    }
    for column, col_type in fields.items():
        _add_column_if_missing(conn, "activities", column, col_type)


def _migration_add_activity_records(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
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
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_activity_records_activity_time
        ON activity_records(activity_id, record_time_utc)
        """
    )


def _migration_expand_daily_monitoring(conn: sqlite3.Connection) -> None:
    sleep_fields = {
        "light_sleep_s": "REAL",
        "sleep_start_utc": "TEXT",
        "sleep_end_utc": "TEXT",
    }
    for column, col_type in sleep_fields.items():
        _add_column_if_missing(conn, "sleep_daily", column, col_type)

    wellness_fields = {
        "stress_max": "REAL",
        "body_battery_avg": "REAL",
        "respiration_avg": "REAL",
        "intensity_minutes": "REAL",
    }
    for column, col_type in wellness_fields.items():
        _add_column_if_missing(conn, "wellness_daily", column, col_type)


def _migration_expand_activity_training_context(conn: sqlite3.Connection) -> None:
    fields = {
        "activity_uuid": "TEXT",
        "manufacturer": "TEXT",
        "owner_id": "TEXT",
        "owner_full_name": "TEXT",
        "elapsed_duration_s": "REAL",
        "moving_duration_s": "REAL",
        "average_speed_mps": "REAL",
        "activity_type_key": "TEXT",
        "activity_type_id": "REAL",
        "hr_time_in_zone_1": "REAL",
        "hr_time_in_zone_2": "REAL",
        "hr_time_in_zone_3": "REAL",
        "hr_time_in_zone_4": "REAL",
        "hr_time_in_zone_5": "REAL",
        "moderate_intensity_minutes": "REAL",
        "vigorous_intensity_minutes": "REAL",
        "difference_body_battery": "REAL",
        "bmr_calories": "REAL",
        "is_pr": "REAL",
        "split_summaries_json": "TEXT",
    }
    for column, col_type in fields.items():
        _add_column_if_missing(conn, "activities", column, col_type)


def _migration_v1_primary_garmin_metrics(conn: sqlite3.Connection) -> None:
    activity_fields = {
        "training_load_garmin": "REAL",
        "training_load_garmin_field_name": "TEXT",
        "training_load_garmin_units": "TEXT",
        "calories_active": "REAL",
        "calories_total": "REAL",
        "intensity_minutes_vigorous": "REAL",
        "intensity_minutes_moderate": "REAL",
        "trimp": "REAL",
    }
    for column, col_type in activity_fields.items():
        _add_column_if_missing(conn, "activities", column, col_type)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_summary (
            day_utc TEXT PRIMARY KEY,
            activities_count INTEGER,
            trimp_total REAL,
            training_load_garmin REAL,
            calories_active REAL,
            calories_total REAL,
            intensity_minutes_vigorous REAL,
            intensity_minutes_moderate REAL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_daily_summary_day
        ON daily_summary(day_utc)
        """
    )


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(get_conn(db_path)) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    run_migrations(db_path)


def upsert_activities(db_path: Path, activities: list[dict[str, Any]]) -> int:
    if not activities:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO activities (
                activity_id, start_time_utc, sport_type, distance_m, duration_s,
                avg_hr, max_hr, avg_pace_s_per_km, elevation_gain_m, elevation_loss_m,
                avg_cadence, max_cadence, avg_stride_length, vertical_ratio,
                vertical_oscillation, running_power_avg, running_power_max,
                stamina_start, stamina_end, training_effect_aerobic,
                training_effect_anaerobic, performance_condition, device_name,
                manufacturer,
                activity_uuid, owner_id, owner_full_name, elapsed_duration_s,
                moving_duration_s, average_speed_mps, activity_type_key, activity_type_id,
                hr_time_in_zone_1, hr_time_in_zone_2, hr_time_in_zone_3, hr_time_in_zone_4,
                hr_time_in_zone_5, moderate_intensity_minutes, vigorous_intensity_minutes,
                difference_body_battery, bmr_calories, is_pr, split_summaries_json,
                training_load_garmin, training_load_garmin_field_name, training_load_garmin_units,
                calories_active, calories_total, intensity_minutes_vigorous,
                intensity_minutes_moderate, trimp,
                source, raw_json, created_at, updated_at
            ) VALUES (
                :activity_id, :start_time_utc, :sport_type, :distance_m, :duration_s,
                :avg_hr, :max_hr, :avg_pace_s_per_km, :elevation_gain_m, :elevation_loss_m,
                :avg_cadence, :max_cadence, :avg_stride_length, :vertical_ratio,
                :vertical_oscillation, :running_power_avg, :running_power_max,
                :stamina_start, :stamina_end, :training_effect_aerobic,
                :training_effect_anaerobic, :performance_condition, :device_name,
                :manufacturer,
                :activity_uuid, :owner_id, :owner_full_name, :elapsed_duration_s,
                :moving_duration_s, :average_speed_mps, :activity_type_key, :activity_type_id,
                :hr_time_in_zone_1, :hr_time_in_zone_2, :hr_time_in_zone_3, :hr_time_in_zone_4,
                :hr_time_in_zone_5, :moderate_intensity_minutes, :vigorous_intensity_minutes,
                :difference_body_battery, :bmr_calories, :is_pr, :split_summaries_json,
                :training_load_garmin, :training_load_garmin_field_name, :training_load_garmin_units,
                :calories_active, :calories_total, :intensity_minutes_vigorous,
                :intensity_minutes_moderate, :trimp,
                :source, :raw_json, :created_at, :updated_at
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
                moderate_intensity_minutes=excluded.moderate_intensity_minutes,
                vigorous_intensity_minutes=excluded.vigorous_intensity_minutes,
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
            [
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
                    "moderate_intensity_minutes": row.get("moderate_intensity_minutes"),
                    "vigorous_intensity_minutes": row.get("vigorous_intensity_minutes"),
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
            ],
        )
        conn.commit()
        return conn.total_changes


def upsert_activity_metrics(db_path: Path, metrics: list[dict[str, Any]]) -> int:
    if not metrics:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO activity_metrics (
                activity_id, garmin_training_load, garmin_aerobic_te,
                garmin_anaerobic_te, garmin_vo2max, garmin_calories,
                garmin_avg_power, garmin_norm_power, garmin_training_effect_label,
                raw_json, updated_at
            ) VALUES (
                :activity_id, :garmin_training_load, :garmin_aerobic_te,
                :garmin_anaerobic_te, :garmin_vo2max, :garmin_calories,
                :garmin_avg_power, :garmin_norm_power, :garmin_training_effect_label,
                :raw_json, :updated_at
            )
            ON CONFLICT(activity_id) DO UPDATE SET
                garmin_training_load=excluded.garmin_training_load,
                garmin_aerobic_te=excluded.garmin_aerobic_te,
                garmin_anaerobic_te=excluded.garmin_anaerobic_te,
                garmin_vo2max=excluded.garmin_vo2max,
                garmin_calories=excluded.garmin_calories,
                garmin_avg_power=excluded.garmin_avg_power,
                garmin_norm_power=excluded.garmin_norm_power,
                garmin_training_effect_label=excluded.garmin_training_effect_label,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            [
                {
                    **row,
                    "raw_json": json.dumps(row.get("raw", {}), default=str),
                    "updated_at": now,
                }
                for row in metrics
            ],
        )
        conn.commit()
        return conn.total_changes


def upsert_activity_details(db_path: Path, details: list[dict[str, Any]]) -> int:
    if not details:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO activity_details(activity_id, details_json, updated_at)
            VALUES (:activity_id, :details_json, :updated_at)
            ON CONFLICT(activity_id) DO UPDATE SET
                details_json=excluded.details_json,
                updated_at=excluded.updated_at
            """,
            [
                {
                    "activity_id": row["activity_id"],
                    "details_json": json.dumps(row.get("details", {}), default=str),
                    "updated_at": now,
                }
                for row in details
            ],
        )
        conn.commit()
        return conn.total_changes


def upsert_activity_records(db_path: Path, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
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
            [
                {
                    **row,
                    "raw_json": json.dumps(row.get("raw", {}), default=str),
                    "updated_at": now,
                }
                for row in records
            ],
        )
        conn.commit()
        return conn.total_changes


def upsert_sleep_daily(db_path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
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
            [
                {
                    **row,
                    "raw_json": json.dumps(row.get("raw", {}), default=str),
                    "updated_at": now,
                }
                for row in rows
            ],
        )
        conn.commit()
        return conn.total_changes


def upsert_wellness_daily(db_path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
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
            [
                {
                    **row,
                    "raw_json": json.dumps(row.get("raw", {}), default=str),
                    "updated_at": now,
                }
                for row in rows
            ],
        )
        conn.commit()
        return conn.total_changes


def get_runs_df(db_path: Path) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT a.activity_id, a.start_time_utc, a.sport_type, a.distance_m, a.duration_s,
                   a.avg_hr, a.max_hr, a.avg_pace_s_per_km, a.elevation_gain_m,
                   a.elevation_loss_m, a.avg_cadence, a.max_cadence, a.avg_stride_length,
                   a.vertical_ratio, a.vertical_oscillation, a.running_power_avg,
                   a.running_power_max, a.stamina_start, a.stamina_end,
                   a.training_effect_aerobic, a.training_effect_anaerobic,
                   a.performance_condition, a.device_name, a.manufacturer, a.activity_uuid,
                   a.owner_id, a.owner_full_name, a.elapsed_duration_s,
                   a.moving_duration_s, a.average_speed_mps, a.activity_type_key,
                   a.activity_type_id, a.hr_time_in_zone_1, a.hr_time_in_zone_2,
                   a.hr_time_in_zone_3, a.hr_time_in_zone_4, a.hr_time_in_zone_5,
                   a.moderate_intensity_minutes, a.vigorous_intensity_minutes,
                   a.difference_body_battery, a.bmr_calories, a.is_pr, a.split_summaries_json,
                   a.training_load_garmin, a.training_load_garmin_field_name,
                   a.training_load_garmin_units, a.calories_active, a.calories_total,
                   a.intensity_minutes_vigorous, a.intensity_minutes_moderate, a.trimp,
                   a.source,
                   m.garmin_aerobic_te, m.garmin_anaerobic_te,
                   m.garmin_vo2max, m.garmin_training_effect_label
            FROM activities a
            LEFT JOIN activity_metrics m ON m.activity_id = a.activity_id
            ORDER BY a.start_time_utc DESC
            """,
            conn,
        )


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


def get_activity_records_df(db_path: Path, activity_id: str) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT record_time_utc, heart_rate, cadence, step_length, stride_length,
                   vertical_ratio, vertical_oscillation, power, grade, altitude,
                   speed, distance, stamina
            FROM activity_records
            WHERE activity_id = ?
            ORDER BY record_time_utc
            """,
            conn,
            params=(activity_id,),
        )


def get_activity_raw(db_path: Path, activity_id: str) -> dict[str, Any] | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            "SELECT raw_json FROM activities WHERE activity_id = ?",
            (activity_id,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["raw_json"]) if row["raw_json"] else {}


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


def get_table_counts(db_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    tables = [
        "activities",
        "activity_metrics",
        "activity_details",
        "activity_records",
        "sleep_daily",
        "wellness_daily",
        "daily_summary",
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


def get_setting(db_path: Path, key: str) -> str | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


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

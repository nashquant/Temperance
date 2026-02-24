from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

CREATE TABLE IF NOT EXISTS sleep_daily (
    day_utc TEXT PRIMARY KEY,
    sleep_score REAL,
    sleep_duration_s REAL,
    deep_sleep_s REAL,
    rem_sleep_s REAL,
    awake_s REAL,
    raw_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wellness_daily (
    day_utc TEXT PRIMARY KEY,
    resting_hr REAL,
    hrv_status REAL,
    training_readiness REAL,
    stress_avg REAL,
    body_battery_start REAL,
    body_battery_end REAL,
    steps REAL,
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

CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time_utc);
CREATE INDEX IF NOT EXISTS idx_sync_log_time ON sync_log(sync_time_utc DESC);
"""


def get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(get_conn(db_path)) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def upsert_activities(db_path: Path, activities: list[dict[str, Any]]) -> int:
    if not activities:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO activities (
                activity_id, start_time_utc, sport_type, distance_m, duration_s,
                avg_hr, max_hr, avg_pace_s_per_km, elevation_gain_m, source,
                raw_json, created_at, updated_at
            ) VALUES (
                :activity_id, :start_time_utc, :sport_type, :distance_m, :duration_s,
                :avg_hr, :max_hr, :avg_pace_s_per_km, :elevation_gain_m, :source,
                :raw_json, :created_at, :updated_at
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
                source=excluded.source,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            [
                {
                    **row,
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


def upsert_sleep_daily(db_path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        conn.executemany(
            """
            INSERT INTO sleep_daily (
                day_utc, sleep_score, sleep_duration_s, deep_sleep_s,
                rem_sleep_s, awake_s, raw_json, updated_at
            ) VALUES (
                :day_utc, :sleep_score, :sleep_duration_s, :deep_sleep_s,
                :rem_sleep_s, :awake_s, :raw_json, :updated_at
            )
            ON CONFLICT(day_utc) DO UPDATE SET
                sleep_score=excluded.sleep_score,
                sleep_duration_s=excluded.sleep_duration_s,
                deep_sleep_s=excluded.deep_sleep_s,
                rem_sleep_s=excluded.rem_sleep_s,
                awake_s=excluded.awake_s,
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
                stress_avg, body_battery_start, body_battery_end,
                steps, calories_total, raw_json, updated_at
            ) VALUES (
                :day_utc, :resting_hr, :hrv_status, :training_readiness,
                :stress_avg, :body_battery_start, :body_battery_end,
                :steps, :calories_total, :raw_json, :updated_at
            )
            ON CONFLICT(day_utc) DO UPDATE SET
                resting_hr=excluded.resting_hr,
                hrv_status=excluded.hrv_status,
                training_readiness=excluded.training_readiness,
                stress_avg=excluded.stress_avg,
                body_battery_start=excluded.body_battery_start,
                body_battery_end=excluded.body_battery_end,
                steps=excluded.steps,
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
                   a.avg_hr, a.max_hr, a.avg_pace_s_per_km, a.elevation_gain_m, a.source,
                   m.garmin_training_load, m.garmin_aerobic_te, m.garmin_anaerobic_te,
                   m.garmin_vo2max, m.garmin_training_effect_label
            FROM activities a
            LEFT JOIN activity_metrics m ON m.activity_id = a.activity_id
            WHERE lower(a.sport_type) LIKE '%run%'
            ORDER BY a.start_time_utc DESC
            """,
            conn,
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
        "sleep_daily",
        "wellness_daily",
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
            SELECT day_utc, sleep_score, sleep_duration_s, deep_sleep_s, rem_sleep_s, awake_s
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
                   body_battery_start, body_battery_end, steps, calories_total
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

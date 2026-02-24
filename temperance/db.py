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


def get_runs_df(db_path: Path) -> pd.DataFrame:
    with closing(get_conn(db_path)) as conn:
        return pd.read_sql_query(
            """
            SELECT activity_id, start_time_utc, sport_type, distance_m, duration_s,
                   avg_hr, max_hr, avg_pace_s_per_km, elevation_gain_m, source
            FROM activities
            ORDER BY start_time_utc DESC
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


def get_latest_activity_time(db_path: Path) -> datetime | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            "SELECT MAX(start_time_utc) AS latest FROM activities"
        ).fetchone()
    if not row or not row["latest"]:
        return None
    return datetime.fromisoformat(row["latest"].replace("Z", "+00:00"))


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
            (UTC_NOW(), source, int(success), message[:500]),
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

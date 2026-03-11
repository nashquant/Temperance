from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import _executemany_in_chunks, get_conn, init_db, upsert_activity_records


class TrackingConnection:
    def __init__(self) -> None:
        self.total_changes = 0
        self.calls: list[int] = []

    def executemany(self, _sql: str, params: list[dict[str, object]]) -> None:
        self.calls.append(len(params))
        self.total_changes += len(params)


def test_executemany_in_chunks_splits_large_batches(tmp_path: Path) -> None:
    conn = TrackingConnection()
    changed = _executemany_in_chunks(
        conn,  # type: ignore[arg-type]
        "INSERT INTO anything VALUES (:id)",
        [{"id": idx} for idx in range(5)],
        chunk_size=2,
    )

    assert changed == 5
    assert conn.calls == [2, 2, 1]


def test_upsert_activity_records_preserves_row_count_across_chunks(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)

    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO activities (
                activity_id, start_time_utc, sport_type, source, raw_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("a1", "2026-03-10T10:00:00+00:00", "running", "test", "{}", "now", "now"),
        )
        conn.commit()

    changed = upsert_activity_records(
        db_path,
        [
            {
                "activity_id": "a1",
                "record_time_utc": f"2026-03-10T10:{idx:02d}:00+00:00",
                "heart_rate": 140 + idx,
                "raw": {"idx": idx},
            }
            for idx in range(1005)
        ],
    )

    with get_conn(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM activity_records WHERE activity_id = 'a1'").fetchone()

    assert changed == 1005
    assert int(row["n"]) == 1005

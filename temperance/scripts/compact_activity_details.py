from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from temperance.activity_detail_summary import summarize_activity_detail_bundle


def compact(
    db_path: Path, *, backup: bool = True, vacuum: bool = True
) -> dict[str, int | str]:
    if backup:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = db_path.with_suffix(db_path.suffix + f".backup-{stamp}")
        shutil.copy2(db_path, backup_path)
    else:
        backup_path = Path("")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT activity_id, details_json FROM activity_details"
    ).fetchall()
    changed = 0
    before_bytes = 0
    after_bytes = 0

    for row in rows:
        raw = row["details_json"] or ""
        before_bytes += len(raw.encode("utf-8"))
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        summary = summarize_activity_detail_bundle(
            payload if isinstance(payload, dict) else {}
        )
        encoded = json.dumps(summary, default=str, separators=(",", ":"))
        after_bytes += len(encoded.encode("utf-8"))
        if encoded != raw:
            conn.execute(
                """
                UPDATE activity_details
                SET details_json = ?, updated_at = ?
                WHERE activity_id = ?
                """,
                (
                    encoded,
                    datetime.now(timezone.utc).isoformat(),
                    row["activity_id"],
                ),
            )
            changed += 1

    conn.commit()
    if vacuum:
        conn.execute("VACUUM")
    conn.close()
    return {
        "rows": len(rows),
        "changed": changed,
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "backup_path": str(backup_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path", type=Path)
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--no-vacuum", action="store_true")
    args = parser.parse_args()
    result = compact(
        args.db_path,
        backup=not args.no_backup,
        vacuum=not args.no_vacuum,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

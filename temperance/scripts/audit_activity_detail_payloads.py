from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


HEAVY_DETAIL_KEYS = {
    "activityDetailMetrics",
    "metricDescriptors",
    "heartRateDTOs",
    "geoPolylineDTO",
}


def _loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _byte_len(value: Any) -> int:
    return len(json.dumps(value, default=str, separators=(",", ":")).encode("utf-8"))


def audit(db_path: Path, sample_limit: int = 5) -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT activity_id, details_json
        FROM activity_details
        ORDER BY length(details_json) DESC
        """
    ).fetchall()
    conn.close()

    total_bytes = 0
    detail_key_counts: Counter[str] = Counter()
    top_rows: list[tuple[str, int]] = []
    heavy_bytes: Counter[str] = Counter()

    for row in rows:
        payload = _loads(row["details_json"])
        row_bytes = len((row["details_json"] or "").encode("utf-8"))
        total_bytes += row_bytes
        top_rows.append((str(row["activity_id"]), row_bytes))
        details = payload.get("details")
        if isinstance(details, dict):
            detail_key_counts.update(details.keys())
            for key in HEAVY_DETAIL_KEYS:
                if key in details:
                    heavy_bytes[key] += _byte_len(details[key])

    top_rows = sorted(top_rows, key=lambda item: item[1], reverse=True)[:sample_limit]
    lines = [
        "# Activity Detail Payload Audit",
        "",
        f"DB: `{db_path}`",
        f"Rows: `{len(rows)}`",
        f"Total details_json MB: `{total_bytes / 1024 / 1024:.1f}`",
        "",
        "## Largest Rows",
        "",
    ]
    for activity_id, size in top_rows:
        lines.append(f"- `{activity_id}`: `{size / 1024:.1f} KB`")

    lines.extend(["", "## Detail Key Counts", ""])
    for key, count in detail_key_counts.most_common():
        lines.append(f"- `{key}`: `{count}`")

    lines.extend(["", "## Heavy Key Estimated Bytes", ""])
    for key, size in heavy_bytes.most_common():
        lines.append(f"- `{key}`: `{size / 1024 / 1024:.1f} MB`")

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "Keep compact metadata, weather scalar fields, and HR zone rows. Drop full metric arrays, metric descriptors, heart-rate DTO arrays, and polylines from default DB storage.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path", type=Path)
    parser.add_argument("--sample-limit", type=int, default=5)
    args = parser.parse_args()
    print(audit(args.db_path, sample_limit=args.sample_limit), end="")


if __name__ == "__main__":
    main()

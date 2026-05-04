#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


WATCH_PATTERNS = (
    "Lost connection with the edge",
    "Unable to reach the origin service",
    "Failed to proxy HTTP",
    "Incoming request ended abruptly",
)

LAUNCHD_LABELS = (
    "com.temperance.backend",
    "com.temperance.frontend",
    "com.temperance.mcp",
    "com.temperance.cloudflared",
)


def run_cmd(*args: str) -> dict[str, object]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return {
            "command": list(args),
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover
        return {
            "command": list(args),
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
        }


def collect_snapshot(trigger_line: str) -> dict[str, object]:
    uid = str(os.getuid())
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "trigger_line": trigger_line,
        "memory_pressure": run_cmd("/usr/bin/memory_pressure"),
        "vm_stat": run_cmd("/usr/bin/vm_stat"),
        "listeners": run_cmd(
            "/usr/sbin/lsof",
            "-nP",
            "-iTCP:5173",
            "-iTCP:8000",
            "-iTCP:37701",
            "-sTCP:LISTEN",
        ),
        "service_state": {
            label: run_cmd(
                "/bin/launchctl",
                "print",
                f"gui/{uid}/{label}",
            )
            for label in LAUNCHD_LABELS
        },
    }


def should_capture(line: str) -> bool:
    return any(pattern in line for pattern in WATCH_PATTERNS)


def main() -> None:
    cloudflared_log = Path(
        os.environ.get(
            "TEMPERANCE_CLOUDFLARED_LOG",
            "/Users/matheus/Temperance/temperance/data/private/logs/cloudflared_launchd.err.log",
        )
    )
    output_log = Path(
        os.environ.get(
            "TEMPERANCE_WATCHDOG_EVENTS",
            "/Users/matheus/Temperance/temperance/data/private/logs/tunnel_watchdog_events.jsonl",
        )
    )
    cooldown_seconds = int(os.environ.get("TEMPERANCE_WATCHDOG_COOLDOWN", "60"))

    cloudflared_log.parent.mkdir(parents=True, exist_ok=True)
    output_log.parent.mkdir(parents=True, exist_ok=True)
    cloudflared_log.touch(exist_ok=True)
    output_log.touch(exist_ok=True)

    last_capture = 0.0
    with cloudflared_log.open("r", encoding="utf-8", errors="ignore") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(0.5)
                continue
            line = line.rstrip("\n")
            if not should_capture(line):
                continue
            now = time.time()
            if now - last_capture < cooldown_seconds:
                continue
            snapshot = collect_snapshot(line)
            with output_log.open("a", encoding="utf-8") as out:
                out.write(json.dumps(snapshot) + "\n")
            last_capture = now


if __name__ == "__main__":
    main()

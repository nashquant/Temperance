from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_backend_runner_does_not_shell_source_env_file() -> None:
    script = (ROOT / "backend" / "run.sh").read_text()

    assert "source \"${LOCAL_ENV_FILE}\"" not in script
    assert "set -a" not in script

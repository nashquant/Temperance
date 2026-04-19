from __future__ import annotations

import re
from pathlib import Path
from typing import Callable


def user_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()).strip("._-")
    return cleaned or "default"


def db_path_for_owner(
    owner: str,
    *,
    base_db_path: Path,
    initializer: Callable[[Path], None],
) -> Path:
    users_root = base_db_path.parent / "users"
    owner_slug = user_slug(owner)
    scoped = users_root / f"{owner_slug}.db"

    def ensure_initialized(path: Path) -> Path:
        try:
            # Keep schema up-to-date for both new and existing DBs.
            initializer(path)
        except Exception:
            # Best effort; callers may still handle DB errors explicitly.
            pass
        return path

    # Keep legacy behavior only for the synthetic/default owner.
    if owner_slug == "default" and base_db_path.exists():
        return ensure_initialized(base_db_path)

    # Named users always use isolated scoped DBs, created on demand.
    return ensure_initialized(scoped)

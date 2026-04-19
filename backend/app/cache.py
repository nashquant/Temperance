from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from temperance.db import get_dashboard_cache_components

# This cache is intentionally process-local. It is suitable for the local
# single-worker backend, but multi-worker deployments need a shared cache or must
# accept independent per-worker entries and no cross-worker invalidation.
_DASHBOARD_PAYLOAD_CACHE_MAXSIZE = 32
_dashboard_payload_cache: OrderedDict[str, dict] = OrderedDict()
_dashboard_payload_cache_lock = threading.Lock()


def dashboard_cache_key(
    db_path: Path,
    sport: str | None,
    week_offset: int,
    weeks: int,
) -> str:
    components = get_dashboard_cache_components(db_path)
    today = datetime.now().astimezone().date().isoformat()
    raw = (
        f"{db_path}|{sport}|{week_offset}|{weeks}"
        f"|{components['activities']}"
        f"|{components['planned_activities']}"
        f"|{components['custom_activities']}"
        f"|{components['settings']}"
        f"|{components['wellness']}"
        f"|{components['merges']}"
        f"|{today}"
    )
    return hashlib.sha1(raw.encode()).hexdigest()

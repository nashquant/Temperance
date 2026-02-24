from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone


def generate_synthetic_runs(days_back: int = 42, seed: int = 42) -> list[dict]:
    """Generate synthetic running activities for local UI demos."""
    random.seed(seed)
    now = datetime.now(timezone.utc)

    activities: list[dict] = []
    for d in range(days_back):
        if random.random() < 0.45:
            continue

        start = now - timedelta(days=d, hours=random.randint(5, 19), minutes=random.randint(0, 59))
        distance_km = random.uniform(4.0, 16.0)
        pace_s = random.uniform(260, 380)
        duration_s = distance_km * pace_s
        avg_hr = random.randint(130, 168)
        max_hr = min(avg_hr + random.randint(8, 22), 198)
        elev = max(0.0, random.gauss(60, 35))

        activities.append(
            {
                "activity_id": f"synthetic_{int(start.timestamp())}",
                "start_time_utc": start.isoformat(),
                "sport_type": "running",
                "distance_m": round(distance_km * 1000, 1),
                "duration_s": round(duration_s, 1),
                "avg_hr": avg_hr,
                "max_hr": max_hr,
                "avg_pace_s_per_km": round(pace_s, 1),
                "elevation_gain_m": round(elev, 1),
                "source": "synthetic",
                "raw": {"generator": "v1"},
            }
        )

    return activities

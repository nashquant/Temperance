from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from temperance.db import (
    create_activity_merge,
    delete_activity_merge,
    get_activity_local_start_map,
    get_activity_meta,
)


def create_activity_merge_for_ids(
    db_path: Path,
    raw_ids: list[str | None],
) -> dict[str, Any]:
    from backend.app import main as main_module

    activity_ids = [
        main_module._normalize_activity_id(activity_id)
        for activity_id in raw_ids
        if activity_id
    ]
    if len(activity_ids) < 2:
        raise HTTPException(status_code=422, detail="At least two activities are required")
    if len(set(activity_ids)) != len(activity_ids):
        raise HTTPException(
            status_code=422, detail="Duplicate activity ids cannot be merged"
        )

    metas = {activity_id: get_activity_meta(db_path, activity_id) for activity_id in activity_ids}
    if any(meta is None for meta in metas.values()):
        raise HTTPException(status_code=404, detail="One or more activities not found")
    if any(
        str(meta["source"]).lower() == "custom"
        for meta in metas.values()
        if meta is not None
    ):
        raise HTTPException(status_code=422, detail="Custom activities cannot be merged")

    sport_by_id = {
        activity_id: str(meta["sport_type"]).strip().lower()
        for activity_id, meta in metas.items()
        if meta is not None
    }
    base_sport = sport_by_id[activity_ids[0]]
    for activity_id in activity_ids[1:]:
        sport = sport_by_id[activity_id]
        if not main_module._merge_compatible(base_sport, sport):
            raise HTTPException(
                status_code=422,
                detail=f"Incompatible sport types: {base_sport!r} and {sport!r}",
            )

    local_map = get_activity_local_start_map(db_path=db_path, activity_ids=activity_ids)
    local_dates = {
        pd.Timestamp(ts).date()
        for ts in (local_map.get(activity_id) for activity_id in activity_ids)
        if ts is not None
    }
    if len(local_dates) > 1:
        raise HTTPException(
            status_code=422,
            detail="Activities must be on the same day to be merged",
        )

    try:
        merge_id = create_activity_merge(db_path, activity_ids)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="One or more activities are already part of a merge",
        ) from exc

    return {"merge_id": merge_id}


def delete_activity_merge_by_id(db_path: Path, merge_id: int) -> dict[str, bool]:
    deleted = delete_activity_merge(db_path, merge_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Merge not found")
    return {"deleted": True}

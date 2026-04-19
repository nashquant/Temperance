from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd
from fastapi import APIRouter, Header, HTTPException, Query

from backend.app.models import ActivityMergeRequest
from temperance.db import (
    create_activity_merge,
    delete_activity_merge,
    get_activity_local_start_map,
    get_activity_meta,
)

router = APIRouter()


@router.post("/api/v1/activity-merges")
def create_merge(
    payload: ActivityMergeRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)

    raw_ids = (
        payload.activity_ids
        if payload.activity_ids is not None
        else [payload.activity_id_1, payload.activity_id_2]
    )
    activity_ids = [
        main_module._normalize_activity_id(activity_id)
        for activity_id in raw_ids
        if activity_id
    ]
    if len(activity_ids) < 2:
        raise HTTPException(
            status_code=422, detail="At least two activities are required"
        )
    if len(set(activity_ids)) != len(activity_ids):
        raise HTTPException(
            status_code=422, detail="Duplicate activity ids cannot be merged"
        )

    metas = {
        activity_id: get_activity_meta(db_path, activity_id)
        for activity_id in activity_ids
    }
    if any(meta is None for meta in metas.values()):
        raise HTTPException(status_code=404, detail="One or more activities not found")
    if any(
        str(meta["source"]).lower() == "custom"
        for meta in metas.values()
        if meta is not None
    ):
        raise HTTPException(
            status_code=422, detail="Custom activities cannot be merged"
        )

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


@router.delete("/api/v1/activity-merges/{merge_id}")
def delete_merge(
    merge_id: int,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)
    deleted = delete_activity_merge(db_path, merge_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Merge not found")
    return {"deleted": True}


@router.get("/api/v1/activities/{activity_id}")
def activity_detail(
    activity_id: str,
    owner: str | None = Query(default=None),
    include_records: bool = Query(default=True),
    records_limit: int = Query(default=1000, ge=100, le=5000),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.activity_detail(
        activity_id=activity_id,
        owner=owner,
        include_records=include_records,
        records_limit=records_limit,
        authorization=authorization,
    )

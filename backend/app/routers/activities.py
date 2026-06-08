from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query

from backend.app.activity_service import (
    create_activity_merge_for_ids,
    delete_activity_merge_by_id,
)
from backend.app.models import ActivityMergeRequest

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
    return create_activity_merge_for_ids(db_path, raw_ids)


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
    return delete_activity_merge_by_id(db_path, merge_id)


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

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query

from backend.app.models import (
    CustomActivityUpdateRequest,
    CustomIngestRequest,
    GeneratedActivityRequest,
    PlannedIngestRequest,
    PlannedManualDoneRequest,
    PlannedWorkoutUpdateRequest,
)

router = APIRouter()


@router.get("/api/v1/planned-activities")
def planned_activities_view(
    weeks: int = Query(default=4, ge=1, le=12),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.planned_activities_view(
        weeks=weeks,
        owner=owner,
        authorization=authorization,
    )


@router.patch("/api/v1/planned-activities/manual-done")
def planned_activity_manual_done(
    payload: PlannedManualDoneRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.planned_activity_manual_done(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )


@router.delete("/api/v1/planned-activities")
def planned_activity_delete(
    day_utc: str = Query(...),
    line_no: int = Query(..., ge=1),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.planned_activity_delete(
        day_utc=day_utc,
        line_no=line_no,
        owner=owner,
        authorization=authorization,
    )


@router.post("/api/v1/planned-activities/ingest")
def planned_activities_ingest(
    payload: PlannedIngestRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.planned_activities_ingest(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )


@router.patch("/api/v1/planned-activities/workout")
def planned_activity_workout_update(
    payload: PlannedWorkoutUpdateRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.planned_activity_workout_update(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )


@router.get("/api/v1/custom-activities")
def custom_activities_view(
    weeks: int | None = Query(default=None, ge=1, le=5200),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.custom_activities_view(
        weeks=weeks,
        owner=owner,
        authorization=authorization,
    )


@router.post("/api/v1/generated-activity")
def generated_activity(
    payload: GeneratedActivityRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.generated_activity(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )


@router.post("/api/v1/custom-activities/ingest")
def custom_activities_ingest(
    payload: CustomIngestRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.custom_activities_ingest(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )


@router.patch("/api/v1/custom-activities/workout")
def custom_activity_workout_update(
    payload: CustomActivityUpdateRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.custom_activity_workout_update(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )


@router.delete("/api/v1/custom-activities")
def custom_activity_delete(
    day_utc: str = Query(...),
    line_no: int = Query(..., ge=1),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.custom_activity_delete(
        day_utc=day_utc,
        line_no=line_no,
        owner=owner,
        authorization=authorization,
    )

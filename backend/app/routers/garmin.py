from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query
from fastapi.responses import RedirectResponse

from backend.app.models import (
    ComprehensiveExtractRequest,
    GarminCredentialsRequest,
    SyncRequest,
)

router = APIRouter()


@router.post("/api/v1/garmin/oauth/start")
def garmin_oauth_start(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.garmin_oauth_start(owner=owner, authorization=authorization)


@router.get("/api/v1/garmin/oauth/callback")
def garmin_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    from backend.app import main as main_module

    return main_module.garmin_oauth_callback(
        code=code,
        state=state,
        error=error,
        error_description=error_description,
    )


@router.post("/api/v1/garmin/oauth/disconnect")
def garmin_oauth_disconnect(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.garmin_oauth_disconnect(
        owner=owner,
        authorization=authorization,
    )


@router.get("/api/v1/data-extract/status")
def data_extract_status(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.data_extract_status(owner=owner, authorization=authorization)


@router.post("/api/v1/data-extract/credentials")
def data_extract_credentials(
    payload: GarminCredentialsRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.data_extract_credentials(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )


@router.post("/api/v1/data-extract/garmin-auth/reset")
def data_extract_garmin_auth_reset(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.data_extract_garmin_auth_reset(
        owner=owner,
        authorization=authorization,
    )


@router.post("/api/v1/data-extract/sync")
def data_extract_sync(
    payload: SyncRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.data_extract_sync(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )


@router.post("/api/v1/data-extract/comprehensive")
def data_extract_comprehensive(
    payload: ComprehensiveExtractRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    return main_module.data_extract_comprehensive(
        payload=payload,
        owner=owner,
        authorization=authorization,
    )

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query

router = APIRouter()


@router.get("/api/v1/overview")
def overview(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, int | str]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)

    if not db_path.exists():
        return {
            "owner": resolved_owner,
            "activities": 0,
            "activity_details": 0,
            "wellness_daily": 0,
        }

    with main_module.sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        try:
            activities = cur.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        except Exception:
            activities = 0
        try:
            activity_details = cur.execute(
                "SELECT COUNT(*) FROM activity_details"
            ).fetchone()[0]
        except Exception:
            activity_details = 0
        try:
            wellness_daily = cur.execute(
                "SELECT COUNT(*) FROM wellness_daily"
            ).fetchone()[0]
        except Exception:
            wellness_daily = 0

    return {
        "owner": resolved_owner,
        "activities": int(activities),
        "activity_details": int(activity_details),
        "wellness_daily": int(wellness_daily),
    }


@router.get("/api/v1/week-outlook")
def week_outlook_view(
    days: int = Query(default=3000, ge=14, le=10000),
    metric: str = Query(default="tss"),
    compare: str = Query(default="planned"),
    week_start: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)
    payload = main_module._build_week_outlook_payload(
        db_path=db_path,
        days=days,
        start_day=None,
        end_day=None,
        sport=None,
        metric=metric,
        compare=compare,
        week_start=week_start,
    )
    payload["owner"] = resolved_owner
    return payload


@router.get("/api/v1/athlete-progression")
def athlete_progression_view(
    days: int = Query(default=3000, ge=30, le=10000),
    activity_filter: str = Query(default="all"),
    aggregation: str = Query(default="weekly"),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)
    return main_module._build_athlete_progression_payload(
        db_path=db_path,
        days=days,
        activity_filter=activity_filter,
        aggregation=aggregation,
        owner=resolved_owner,
    )


@router.get("/api/v1/wellness")
def wellness_view(
    days: int = Query(default=365, ge=30, le=5000),
    aggregation: str = Query(default="weekly"),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)
    return main_module._build_wellness_payload(
        db_path=db_path,
        days=days,
        aggregation=aggregation,
        owner=resolved_owner,
    )


@router.get("/api/v1/dashboard")
def activity_dashboard(
    weeks: int = Query(default=6, ge=1, le=52),
    week_offset: int = Query(default=0, ge=0, le=5200),
    sport: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)
    payload = main_module._build_activity_dashboard_payload(
        db_path=db_path,
        visible_weeks=weeks,
        week_offset=week_offset,
        sport=sport,
    )
    payload["owner"] = resolved_owner
    return payload

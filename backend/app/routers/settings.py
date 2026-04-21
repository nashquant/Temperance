from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from backend.app.models import UpdateSettingsRequest

router = APIRouter()


@router.get("/api/v1/settings")
def settings_view(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)
    result = main_module._settings_view_core(db_path)
    result["owner"] = resolved_owner
    return result


@router.get("/api/v1/coach-snapshot")
def coach_snapshot_view(
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)
    payload = main_module._coach_snapshot_view_core(db_path, owner=resolved_owner)
    payload["owner"] = resolved_owner
    payload["db_path"] = str(db_path)
    return payload


@router.put("/api/v1/settings")
def settings_update(
    payload: UpdateSettingsRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)
    return main_module._settings_update_core(
        db_path,
        {
            "if_zone_thresholds": payload.if_zone_thresholds,
            "vdot_lookback_days": payload.vdot_lookback_days,
            "specificity_profile": payload.specificity_profile,
            "coach_preferences": payload.coach_preferences,
            "baseline_blend": payload.baseline_blend,
            "lthr_curve": payload.lthr_curve,
            "lt_pace_curve": payload.lt_pace_curve,
            "injury_windows": payload.injury_windows,
            "timezone": payload.timezone,
            "race_context": payload.race_context,
        },
    )


@router.get("/api/v1/vdot")
def vdot_view(
    owner: str | None = Query(default=None),
    as_of: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    from backend.app import main as main_module

    ctx = main_module._auth_context(authorization)
    resolved_owner = main_module._resolve_owner(ctx, owner)
    db_path = main_module._db_path_for_owner(resolved_owner)

    lt_pace_curve = main_module._load_curve_points(
        db_path=db_path,
        key=main_module.SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=main_module.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    if not lt_pace_curve:
        raise HTTPException(status_code=404, detail="LT pace curve unavailable")

    if as_of:
        try:
            as_of_dt = main_module.datetime.fromisoformat(str(as_of).strip())
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail="Invalid as_of date. Use YYYY-MM-DD."
            ) from exc
        if as_of_dt.tzinfo is None:
            as_of_dt = as_of_dt.replace(tzinfo=main_module.timezone.utc)
        as_of_ts = as_of_dt.astimezone(main_module.timezone.utc)
        lt_pace = float(
            main_module._curve_value_at(
                lt_pace_curve, float(lt_pace_curve[-1][1]), as_of_ts
            )
        )
        source_date = as_of_ts.date().isoformat()
    else:
        source_date = (
            lt_pace_curve[-1][0].astimezone(main_module.timezone.utc).date().isoformat()
        )
        lt_pace = float(lt_pace_curve[-1][1])

    payload = main_module._vdot_payload_from_lt_pace(lt_pace)

    observed_max: dict[str, Any] | None = None
    vdot_lookback_days = main_module._load_vdot_lookback_days(db_path)
    metrics_df = main_module._metrics_for_filters(
        db_path=db_path,
        days=3650,
        start_day=None,
        end_day=None,
        sport=None,
    )
    if not metrics_df.empty:
        metrics_df = metrics_df.copy()
        metrics_df["distance_m"] = main_module.pd.to_numeric(
            metrics_df.get("distance_m"), errors="coerce"
        ).fillna(0.0)
        metrics_df["duration_s"] = main_module.pd.to_numeric(
            metrics_df.get("duration_s"), errors="coerce"
        ).fillna(0.0)
        metrics_df["if_proxy"] = main_module.pd.to_numeric(
            metrics_df.get("if_proxy"), errors="coerce"
        ).fillna(0.0)
        metrics_df["start_time_utc"] = main_module.pd.to_datetime(
            metrics_df.get("start_time_utc"), utc=True, errors="coerce"
        )
        sport_lower = (
            metrics_df.get(
                "sport_type",
                main_module.pd.Series(index=metrics_df.index, dtype=object),
            )
            .fillna("")
            .astype(str)
            .str.lower()
        )
        eligible_mask = (
            (sport_lower.str.contains("run") | sport_lower.str.contains("treadmill"))
            & (metrics_df["distance_m"] > 0)
            & (metrics_df["duration_s"] > 0)
            & (metrics_df["if_proxy"] > 0.90)
        )
        observed_candidates = metrics_df.loc[
            eligible_mask, ["distance_m", "duration_s", "start_time_utc"]
        ].copy()
        if not observed_candidates.empty:
            observed_candidates["vdot"] = observed_candidates.apply(
                lambda row: main_module._activity_vdot(
                    distance_m=main_module._safe_float(row.get("distance_m")),
                    duration_s=main_module._safe_float(row.get("duration_s")),
                ),
                axis=1,
            )
            observed_candidates["vdot"] = main_module.pd.to_numeric(
                observed_candidates["vdot"], errors="coerce"
            )
            observed_candidates = observed_candidates.dropna(subset=["vdot"]).copy()
            if not observed_candidates.empty:
                if as_of:
                    observed_window_end = as_of_ts
                else:
                    observed_window_end = main_module.pd.to_datetime(
                        observed_candidates["start_time_utc"], utc=True, errors="coerce"
                    ).max()
                if main_module.pd.notna(observed_window_end):
                    window_start = main_module.pd.Timestamp(
                        observed_window_end
                    ) - main_module.pd.Timedelta(days=max(vdot_lookback_days - 1, 0))
                    observed_candidates = observed_candidates[
                        (
                            main_module.pd.to_datetime(
                                observed_candidates["start_time_utc"],
                                utc=True,
                                errors="coerce",
                            )
                            >= window_start
                        )
                        & (
                            main_module.pd.to_datetime(
                                observed_candidates["start_time_utc"],
                                utc=True,
                                errors="coerce",
                            )
                            <= observed_window_end
                        )
                    ].copy()
                observed_candidates = observed_candidates.sort_values(
                    ["vdot", "start_time_utc"], ascending=[False, False]
                )
            if not observed_candidates.empty:
                best = observed_candidates.iloc[0]
                best_vdot = float(best.get("vdot") or 0.0)
                best_ts = main_module.pd.to_datetime(
                    best.get("start_time_utc"), utc=True, errors="coerce"
                )
                pred_lt_pace_sec = main_module._lt_pace_sec_per_km_from_vdot(best_vdot)
                observed_max = {
                    "vdot": round(best_vdot, 2),
                    "source_date": best_ts.date().isoformat()
                    if main_module.pd.notna(best_ts)
                    else "",
                    "window_days": int(vdot_lookback_days),
                    "pred_lt_pace_sec_per_km": round(pred_lt_pace_sec, 2),
                    "pred_lt_pace_label": (
                        f"{main_module._format_mmss(pred_lt_pace_sec)}/km"
                        if pred_lt_pace_sec > 0
                        else "-"
                    ),
                    "equivalents": main_module._vdot_equivalents(best_vdot),
                }

    payload.update(
        {
            "owner": resolved_owner,
            "as_of": source_date,
            "observed_max": observed_max,
        }
    )
    return payload

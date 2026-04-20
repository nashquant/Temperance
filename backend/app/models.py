from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class PlannedManualDoneRequest(BaseModel):
    day_utc: str
    line_no: int
    manual_done: bool


class ActivityMergeRequest(BaseModel):
    activity_ids: list[str] | None = None
    activity_id_1: str | None = None
    activity_id_2: str | None = None


class PlannedIngestRequest(BaseModel):
    entry_text: str


class PlannedWorkoutUpdateRequest(BaseModel):
    day_utc: str
    line_no: int
    workout_text: str
    manual_done: bool | None = None


class CustomIngestRequest(BaseModel):
    entry_text: str


class CustomActivityUpdateRequest(BaseModel):
    day_utc: str
    line_no: int
    activity_text: str


class GeneratedActivityScheduleConstraintRequest(BaseModel):
    day_utc: str
    allow_long_run: bool | None = None
    preferred_modality: str | None = None
    blocked: bool = False


class GeneratedActivityRequest(BaseModel):
    day_utc: str
    mode: str = "planned"
    activity_type: str | None = None
    previous_activity_text: str | None = None
    seed: int | None = None
    methodology_id: str | None = None
    schedule_constraints: list[GeneratedActivityScheduleConstraintRequest] | None = None


class UpdateSettingsRequest(BaseModel):
    if_zone_thresholds: dict[str, float] | None = None
    vdot_lookback_days: int | None = None
    specificity_profile: dict[str, float] | None = None
    coach_preferences: dict[str, Any] | None = None
    baseline_blend: dict[str, Any] | None = None
    lthr_curve: list[dict[str, Any]] | None = None
    lt_pace_curve: list[dict[str, Any]] | None = None
    injury_windows: list[dict[str, Any]] | None = None
    timezone: str | None = None


class SyncRequest(BaseModel):
    days_back: int = 180
    source: str = "both"  # garmin_api | file_import | both
    garmin_profile: str = "quick"  # quick | deep


class ComprehensiveExtractRequest(BaseModel):
    start_day: str
    incremental_only: bool = True
    include_details: bool = True
    include_wellness: bool = False
    verify_raw_integrity: bool = False


class GarminCredentialsRequest(BaseModel):
    email: str
    password: str

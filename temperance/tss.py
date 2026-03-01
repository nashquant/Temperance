from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Protocol


class ThresholdPaceProvider(Protocol):
    """Provider of threshold pace (sec/km) at a given datetime."""

    def get_threshold_pace_sec_per_km(self, at: datetime) -> float:
        ...


class LTHRProvider(Protocol):
    """Provider of lactate threshold HR (bpm) at a given datetime."""

    def get_lthr_bpm(self, at: datetime) -> float:
        ...


@dataclass(frozen=True)
class ConstantThresholdPaceProvider:
    threshold_pace_sec_per_km: float

    def get_threshold_pace_sec_per_km(self, at: datetime) -> float:
        return float(self.threshold_pace_sec_per_km)


@dataclass(frozen=True)
class ConstantLTHRProvider:
    lthr_bpm: float

    def get_lthr_bpm(self, at: datetime) -> float:
        return float(self.lthr_bpm)


@dataclass(frozen=True)
class PiecewiseThresholdPaceProvider:
    """
    Date-based threshold pace curve with a constant fallback.

    Points are tuples of (effective_datetime, threshold_pace_sec_per_km).
    Provider returns the latest point with effective_datetime <= activity time.
    """

    default_threshold_pace_sec_per_km: float
    points: tuple[tuple[datetime, float], ...] = ()

    def __post_init__(self) -> None:
        if self.default_threshold_pace_sec_per_km <= 0:
            raise ValueError("default threshold pace must be > 0")
        for _, pace in self.points:
            if pace <= 0:
                raise ValueError("all threshold pace curve values must be > 0")

    def get_threshold_pace_sec_per_km(self, at: datetime) -> float:
        chosen = float(self.default_threshold_pace_sec_per_km)
        for effective_at, pace in sorted(self.points, key=lambda x: x[0]):
            if effective_at <= at:
                chosen = float(pace)
            else:
                break
        return chosen


@dataclass(frozen=True)
class ActivityTSSInput:
    activity_duration_seconds: int
    activity_avg_pace_sec_per_km: float | None
    activity_avg_hr_bpm: float | None
    activity_start_datetime: datetime


@dataclass(frozen=True)
class ActivityDistanceProxyInput:
    sport_type: str | None
    activity_duration_seconds: float | None
    activity_distance_km: float | None
    activity_avg_pace_sec_per_km: float | None


def normalized_graded_pace_v1(activity: ActivityTSSInput) -> float:
    """
    v1 NGP proxy.

    Assumption:
    - Ignore grade/elevation.
    - NGP == average pace in sec/km.
    """
    pace = activity.activity_avg_pace_sec_per_km
    if pace is None or pace <= 0:
        raise ValueError("activity_avg_pace_sec_per_km must be > 0")
    return float(pace)


def normalized_hr_v1(activity: ActivityTSSInput) -> float:
    """
    v1 NHR proxy.

    Assumption:
    - NHR == average HR for the activity.
    """
    hr = activity.activity_avg_hr_bpm
    if hr is None or hr <= 0:
        raise ValueError("activity_avg_hr_bpm must be > 0")
    if hr > 260:
        raise ValueError("activity_avg_hr_bpm is out of physiological range (>260)")
    return float(hr)


def _validate_duration(activity: ActivityTSSInput) -> None:
    if activity.activity_duration_seconds <= 0:
        raise ValueError("activity_duration_seconds must be > 0")


def compute_rtss(activity: ActivityTSSInput, pace_provider: ThresholdPaceProvider) -> float:
    """
    rTSS (pace-based).

    Formula:
    - IF_pace = TP / NGP
    - rTSS = (duration_seconds * IF_pace^2) / 3600 * 100
    """
    _validate_duration(activity)
    ngp = normalized_graded_pace_v1(activity)
    tp = float(pace_provider.get_threshold_pace_sec_per_km(activity.activity_start_datetime))
    if tp <= 0:
        raise ValueError("threshold pace must be > 0")

    if_pace = tp / ngp
    return (float(activity.activity_duration_seconds) * (if_pace**2) / 3600.0) * 100.0


def compute_hrtss(activity: ActivityTSSInput, lthr_provider: LTHRProvider) -> float:
    """
    hrTSS (HR-based).

    Formula:
    - IF_hr = NHR / LTHR
    - hrTSS = (duration_seconds * IF_hr^2) / 3600 * 100
    """
    _validate_duration(activity)
    nhr = normalized_hr_v1(activity)
    lthr = float(lthr_provider.get_lthr_bpm(activity.activity_start_datetime))
    if lthr <= 0:
        raise ValueError("LTHR must be > 0")

    if_hr = nhr / lthr
    return (float(activity.activity_duration_seconds) * (if_hr**2) / 3600.0) * 100.0


def compute_tss_bundle(
    activity: ActivityTSSInput,
    pace_provider: ThresholdPaceProvider,
    lthr_provider: LTHRProvider,
) -> dict[str, float]:
    """
    Compute both TSS variants when inputs exist.

    Behavior:
    - Always validates duration (>0).
    - Omits rTSS when pace is missing.
    - Omits hrTSS when HR is missing.
    - Raises for invalid provided values.
    """
    _validate_duration(activity)
    out: dict[str, float] = {}

    if activity.activity_avg_pace_sec_per_km is not None:
        out["rTSS"] = compute_rtss(activity, pace_provider)

    if activity.activity_avg_hr_bpm is not None:
        out["hrTSS"] = compute_hrtss(activity, lthr_provider)

    return out


def _is_running_like(sport_type: str | None) -> bool:
    lower = str(sport_type or "").lower()
    return ("run" in lower) or ("treadmill" in lower)


def compute_distance_proxy(
    activity: ActivityDistanceProxyInput,
    threshold_pace_sec_per_km: float | None,
    tss: float | None,
    specificity_ratio: float,
) -> dict[str, float | int | str | None]:
    """
    Infer running-equivalent distance for non-running activities via TSS parity.

    Rules:
    - Running/treadmill: proxy equals actual distance/pace (no specificity applied).
    - Non-running: effective_rTSS_target = TSS * specificity_ratio (applied once),
      then solve pace from rTSS formula with fixed duration.
    - Returns method enum: "none_running", "tss_parity_root_solve", "unavailable".
    """
    if _is_running_like(activity.sport_type):
        pace_out: int | None = None
        if activity.activity_avg_pace_sec_per_km is not None and activity.activity_avg_pace_sec_per_km > 0:
            pace_out = int(round(float(activity.activity_avg_pace_sec_per_km)))
        return {
            "distance_proxy_km": (
                float(activity.activity_distance_km)
                if activity.activity_distance_km is not None
                else None
            ),
            "pace_proxy_sec_per_km": pace_out,
            "distance_proxy_method": "none_running",
        }

    duration_s = float(activity.activity_duration_seconds) if activity.activity_duration_seconds is not None else 0.0
    tp = float(threshold_pace_sec_per_km) if threshold_pace_sec_per_km is not None else 0.0
    tss_value = float(tss) if tss is not None else float("nan")
    if duration_s <= 0 or tp <= 0 or not math.isfinite(tss_value):
        return {
            "distance_proxy_km": None,
            "pace_proxy_sec_per_km": None,
            "distance_proxy_method": "unavailable",
        }

    spec = float(specificity_ratio)
    if not math.isfinite(spec):
        return {
            "distance_proxy_km": None,
            "pace_proxy_sec_per_km": None,
            "distance_proxy_method": "unavailable",
        }
    spec = max(0.0, min(1.0, spec))
    effective_rtss_target = max(0.0, tss_value * spec)
    if effective_rtss_target == 0.0:
        return {
            "distance_proxy_km": 0.0,
            "pace_proxy_sec_per_km": None,
            "distance_proxy_method": "tss_parity_root_solve",
        }

    # Analytical solve from: target = (duration * (tp/pace)^2 / 3600) * 100.
    denom = (effective_rtss_target * 3600.0) / (duration_s * 100.0)
    if denom <= 0:
        return {
            "distance_proxy_km": None,
            "pace_proxy_sec_per_km": None,
            "distance_proxy_method": "unavailable",
        }

    solved_pace = tp / math.sqrt(denom)
    min_pace = max(90.0, tp / 2.0)
    max_pace = min(1800.0, tp * 6.0)
    if (not math.isfinite(solved_pace)) or solved_pace < min_pace or solved_pace > max_pace:
        return {
            "distance_proxy_km": None,
            "pace_proxy_sec_per_km": None,
            "distance_proxy_method": "unavailable",
        }

    distance_proxy_km = duration_s / solved_pace
    return {
        "distance_proxy_km": float(distance_proxy_km),
        "pace_proxy_sec_per_km": int(round(solved_pace)),
        "distance_proxy_method": "tss_parity_root_solve",
    }

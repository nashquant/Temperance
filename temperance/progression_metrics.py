from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from temperance.analytics import ema


@dataclass(frozen=True)
class ProgressionMetricConfig:
    performance_days: int = 42
    performance_confirmation_days: int = 21
    readiness_acute_days: int = 10
    readiness_carry_days: int = 3
    tissue_acute_days: int = 7
    tissue_base_days: int = 28
    tissue_concentration_days: int = 14
    durability_single_days: int = 56
    durability_weekly_days: int = 84
    min_vdot_runs_for_full_confidence: int = 3


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0).astype(float)


def _clamp(series: pd.Series, low: float = 0.0, high: float = 100.0) -> pd.Series:
    return _to_numeric(series).clip(lower=low, upper=high)


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    numerator = _to_numeric(num)
    denominator = _to_numeric(den)
    out = pd.Series(0.0, index=numerator.index, dtype=float)
    valid = denominator > 0
    out.loc[valid] = numerator.loc[valid] / denominator.loc[valid]
    return out


def _normalize(series: pd.Series) -> pd.Series:
    numeric = _to_numeric(series)
    lo = float(numeric.min())
    hi = float(numeric.max())
    if hi - lo <= 1e-9:
        return pd.Series(50.0, index=numeric.index, dtype=float)
    return ((numeric - lo) / (hi - lo) * 100.0).astype(float)


def build_derived_progression_metrics(
    evidence_df: pd.DataFrame,
    *,
    config: ProgressionMetricConfig = ProgressionMetricConfig(),
) -> pd.DataFrame:
    frame = evidence_df.copy().sort_values("day").reset_index(drop=True)

    efficiency_trend = _normalize(ema(_to_numeric(frame["efficiency_evidence"]), config.performance_days))
    threshold_trend = _normalize(ema(_to_numeric(frame["threshold_pace_index"]), config.performance_days))
    quality_confirmation = _normalize(
        _to_numeric(frame["quality_session_load"]).rolling(
            config.performance_confirmation_days, min_periods=1
        ).sum()
    )
    durability_support = _normalize(
        _to_numeric(frame["rtss"]).rolling(
            config.performance_confirmation_days, min_periods=1
        ).mean()
    )
    frame["performance_trend"] = _clamp(
        0.40 * efficiency_trend
        + 0.25 * threshold_trend
        + 0.20 * quality_confirmation
        + 0.15 * durability_support
    )

    acute_strain = _normalize(
        _to_numeric(frame["tss"]).rolling(config.readiness_acute_days, min_periods=1).mean()
        + 0.6
        * _to_numeric(frame["hard_run_count"]).rolling(
            config.readiness_acute_days, min_periods=1
        ).sum()
    )
    carryover_friction = _normalize(
        _to_numeric(frame["quality_session_load"]).rolling(
            config.readiness_carry_days, min_periods=1
        ).sum()
    )
    recovery_response = _normalize(
        (100.0 - _to_numeric(frame["training_readiness"])).clip(lower=0.0)
        + (100.0 - _to_numeric(frame["body_battery_end"])).clip(lower=0.0)
    )
    frame["readiness"] = _clamp(
        100.0
        - (0.50 * acute_strain + 0.30 * carryover_friction + 0.20 * recovery_response)
    )

    run_ramp = _normalize(
        _safe_ratio(
            ema(_to_numeric(frame["rtss"]), config.tissue_acute_days),
            ema(_to_numeric(frame["rtss"]), config.tissue_base_days).clip(lower=1.0),
        )
    )
    single_run_spike = _normalize(
        _safe_ratio(_to_numeric(frame["single_run_rtss_max"]), _to_numeric(frame["baseline_rtss"]).clip(lower=1.0))
    )
    load_concentration = _normalize(
        _to_numeric(frame["long_run_share"]).rolling(
            config.tissue_concentration_days, min_periods=1
        ).mean()
        * 100.0
        + _to_numeric(frame["hard_run_count"]).rolling(
            config.tissue_concentration_days, min_periods=1
        ).sum()
        * 5.0
    )
    wellness_friction = _normalize(
        (100.0 - _to_numeric(frame["training_readiness"])).clip(lower=0.0)
        + _to_numeric(frame["resting_hr_delta"]).clip(lower=0.0) * 8.0
    )
    frame["tissue_load_risk"] = _clamp(
        0.35 * run_ramp
        + 0.25 * single_run_spike
        + 0.25 * load_concentration
        + 0.15 * wellness_friction
    )

    single_run_tolerance = _normalize(
        _to_numeric(frame["single_run_rtss_max"]).rolling(
            config.durability_single_days, min_periods=1
        ).quantile(0.75)
    )
    weekly_specific_tolerance = _normalize(
        _to_numeric(frame["rtss"]).rolling(
            config.durability_weekly_days, min_periods=1
        ).mean()
    )
    specific_load_consistency = _normalize(
        _to_numeric(frame["running_day"]).rolling(
            config.durability_single_days, min_periods=1
        ).mean()
        * _to_numeric(frame["rtss"]).rolling(
            config.durability_single_days, min_periods=1
        ).mean()
    )
    frame["durability"] = _clamp(
        0.40 * single_run_tolerance
        + 0.35 * weekly_specific_tolerance
        + 0.25 * specific_load_consistency
    )

    vdot_density = _to_numeric(frame["vdot_eligible_runs"]).rolling(
        config.performance_days, min_periods=1
    ).sum()
    performance_confidence = (vdot_density / float(config.min_vdot_runs_for_full_confidence) * 100.0).clip(upper=100.0)
    load_confidence = _clamp(
        _to_numeric(frame["running_day"]).rolling(
            config.tissue_base_days, min_periods=1
        ).mean()
        * 100.0
    )

    frame["performance_confidence"] = performance_confidence
    frame["readiness_confidence"] = _clamp(
        70.0 + _to_numeric(frame["training_readiness"]).gt(0).astype(float) * 30.0
    )
    frame["tissue_load_risk_confidence"] = load_confidence
    frame["durability_confidence"] = load_confidence

    frame["performance_efficiency"] = efficiency_trend
    frame["performance_threshold"] = threshold_trend
    frame["performance_quality_confirmation"] = quality_confirmation
    frame["performance_durability_support"] = durability_support
    frame["readiness_acute_strain"] = acute_strain
    frame["readiness_carryover_friction"] = carryover_friction
    frame["readiness_recovery_response"] = recovery_response
    frame["tissue_run_ramp"] = run_ramp
    frame["tissue_single_run_spike"] = single_run_spike
    frame["tissue_load_concentration"] = load_concentration
    frame["tissue_wellness_friction"] = wellness_friction
    frame["durability_single_run_tolerance"] = single_run_tolerance
    frame["durability_weekly_specific_tolerance"] = weekly_specific_tolerance
    frame["durability_specific_load_consistency"] = specific_load_consistency
    return frame

from __future__ import annotations

import pandas as pd

from temperance.progression_metrics import build_derived_progression_metrics


def _evidence_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "day": pd.date_range("2026-01-01", periods=14, freq="D"),
            "efficiency_evidence": [
                50,
                50,
                51,
                51,
                52,
                52,
                53,
                53,
                54,
                54,
                55,
                55,
                56,
                56,
            ],
            "threshold_pace_index": [
                0.40,
                0.40,
                0.41,
                0.41,
                0.42,
                0.42,
                0.43,
                0.43,
                0.44,
                0.44,
                0.45,
                0.45,
                0.46,
                0.46,
            ],
            "quality_session_load": [0, 0, 35, 0, 0, 40, 0, 0, 45, 0, 0, 50, 0, 0],
            "vdot_eligible_runs": [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
            "tss": [60] * 14,
            "rtss": [48] * 14,
            "hard_run_count": [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
            "single_run_rtss_max": [35, 35, 70, 35, 35, 72, 35, 35, 74, 35, 35, 76, 35, 35],
            "long_run_load": [0, 0, 0, 0, 0, 65, 0, 0, 0, 0, 0, 68, 0, 0],
            "long_run_share": [0.10] * 14,
            "baseline_rtss": [42] * 14,
            "running_day": [1] * 14,
            "training_readiness": [72, 71, 65, 70, 69, 63, 70, 69, 61, 70, 69, 60, 71, 72],
            "hrv_status": [0.0] * 14,
            "resting_hr_delta": [0.0] * 14,
            "body_battery_end": [68, 69, 55, 70, 69, 52, 70, 69, 50, 70, 69, 49, 71, 72],
        }
    )


def test_performance_trend_rewards_better_efficiency_not_bigger_load() -> None:
    frame = _evidence_frame()
    improved = build_derived_progression_metrics(frame)

    load_only = frame.copy()
    load_only["tss"] = [60, 60, 70, 70, 75, 75, 80, 80, 85, 85, 90, 90, 95, 95]
    load_only["rtss"] = [48, 48, 58, 58, 60, 60, 64, 64, 68, 68, 72, 72, 76, 76]
    load_only["efficiency_evidence"] = [50] * 14
    load_only["threshold_pace_index"] = [0.40] * 14
    plain = build_derived_progression_metrics(load_only)

    assert improved["performance_trend"].iloc[-1] > plain["performance_trend"].iloc[-1]


def test_readiness_falls_when_hard_days_stack() -> None:
    frame = _evidence_frame()
    stacked = build_derived_progression_metrics(frame)

    spaced = frame.copy()
    spaced["hard_run_count"] = [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0]
    spaced["quality_session_load"] = [0, 35, 0, 0, 40, 0, 0, 45, 0, 0, 50, 0, 0, 0]
    spaced_metrics = build_derived_progression_metrics(spaced)

    assert stacked["readiness"].iloc[-1] < spaced_metrics["readiness"].iloc[-1]


def test_tissue_load_risk_and_durability_diverge_for_repeated_exposure() -> None:
    frame = _evidence_frame()
    first_pass = build_derived_progression_metrics(frame)

    adapted = pd.concat(
        [
            frame,
            frame.assign(day=pd.date_range("2026-01-15", periods=14, freq="D")),
        ],
        ignore_index=True,
    )
    second_pass = build_derived_progression_metrics(adapted)

    assert second_pass["durability"].iloc[-1] > first_pass["durability"].iloc[-1]
    assert second_pass["tissue_load_risk"].iloc[-1] <= first_pass["tissue_load_risk"].iloc[-1]

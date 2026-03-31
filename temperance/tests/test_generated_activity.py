from pathlib import Path
import importlib.util
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "temperance"))
sys.path.insert(0, str(ROOT / "v2" / "backend"))

BACKEND_MAIN_PATH = ROOT / "v2" / "backend" / "app" / "main.py"
BACKEND_MAIN_SPEC = importlib.util.spec_from_file_location("temperance_v2_backend_main_generated_activity", BACKEND_MAIN_PATH)
assert BACKEND_MAIN_SPEC is not None and BACKEND_MAIN_SPEC.loader is not None
backend_main = importlib.util.module_from_spec(BACKEND_MAIN_SPEC)
BACKEND_MAIN_SPEC.loader.exec_module(backend_main)


def test_generated_activity_preferred_buckets_respect_context() -> None:
    assert backend_main._generated_activity_preferred_buckets("2026-03-30") == ["easy", "recovery", "aerobic"]
    assert backend_main._generated_activity_preferred_buckets(
        "2026-03-30",
        {"recovery_alert": True},
    ) == ["recovery", "easy", "aerobic"]
    assert backend_main._generated_activity_preferred_buckets(
        "2026-03-31",
        {"progression_green": True, "week_behind": True},
    ) == ["intervals", "fartlek", "tempo", "steady"]
    assert backend_main._generated_activity_preferred_buckets(
        "2026-04-05",
        {"easy_bias": True, "progression_green": True, "week_behind": True},
    ) == ["long", "tempo", "steady", "easy"]


def test_generated_activity_day_goal_tss_keeps_easy_days_near_base_goal() -> None:
    threshold_pace = 300.0
    base_daily_goal = (backend_main._weekly_tss_target_from_lt_pace(threshold_pace) * 1.10) / 7.0

    monday_target = backend_main._generated_activity_day_goal_tss("2026-03-30", threshold_pace)

    assert monday_target == pytest.approx(base_daily_goal * 0.92)
    assert monday_target >= base_daily_goal * 0.90


def test_generated_activity_day_goal_tss_downshifts_for_recovery_and_raises_when_behind() -> None:
    threshold_pace = 300.0
    base_daily_goal = (backend_main._weekly_tss_target_from_lt_pace(threshold_pace) * 1.10) / 7.0

    recovery_target = backend_main._generated_activity_day_goal_tss(
        "2026-04-02",
        threshold_pace,
        {
            "base_daily_goal_tss": base_daily_goal,
            "week_balanced_daily_tss": 0.0,
            "recovery_alert": True,
        },
    )
    assert recovery_target == pytest.approx(base_daily_goal * 0.80)

    progression_target = backend_main._generated_activity_day_goal_tss(
        "2026-03-30",
        threshold_pace,
        {
            "base_daily_goal_tss": base_daily_goal,
            "week_balanced_daily_tss": base_daily_goal * 1.08,
            "progression_green": True,
            "week_behind": True,
        },
    )
    assert progression_target > base_daily_goal


def test_generated_activity_selection_penalty_downweights_hard_options_on_recovery_alert() -> None:
    context = {
        "recovery_alert": True,
        "easy_bias": True,
        "adjacent_hard_days": True,
        "activity_type": "running",
        "week_gap_rtss": -5.0,
        "base_daily_goal_tss": 50.0,
    }
    hard_item = {"bucket": "intervals", "priority": 2, "estimated_tss": 60.0}
    easy_item = {"bucket": "easy", "priority": 0, "estimated_tss": 45.0}

    assert backend_main._generated_activity_selection_penalty(hard_item, context) > backend_main._generated_activity_selection_penalty(easy_item, context)


def test_generated_activity_preference_penalty_allows_more_substantial_easy_day_match() -> None:
    context = {"easy_bias": True}
    preferred_buckets = ["easy", "aerobic", "steady", "recovery"]
    easy_item = {"bucket": "easy", "priority": 0, "estimated_tss": 32.0}
    aerobic_item = {"bucket": "aerobic", "priority": 1, "estimated_tss": 47.0}
    target_tss = 48.0

    easy_score = abs(float(easy_item["estimated_tss"]) - target_tss) + backend_main._generated_activity_preference_penalty(
        easy_item,
        preferred_buckets,
        context,
    )
    aerobic_score = abs(float(aerobic_item["estimated_tss"]) - target_tss) + backend_main._generated_activity_preference_penalty(
        aerobic_item,
        preferred_buckets,
        context,
    )

    assert aerobic_score < easy_score


def test_generated_activity_shortlist_drops_far_worse_candidates() -> None:
    suggestions = [
        {"activity_text": "Run 2h37min @3:43/km", "bucket": "long", "priority": 3, "estimated_tss": 232.0},
        {"activity_text": "Run 1h5min @5:00/km", "bucket": "aerobic", "priority": 0, "estimated_tss": 53.1},
        {"activity_text": "Run 40min @4:40/km", "bucket": "easy", "priority": 0, "estimated_tss": 37.5},
    ]
    shortlist = backend_main._generated_activity_shortlist(
        suggestions=suggestions,
        target_tss=400.0,
        preferred_buckets=["long", "tempo", "steady", "easy"],
        context={"progression_green": True, "week_behind": True},
    )

    assert [item["activity_text"] for _, item in shortlist] == ["Run 2h37min @3:43/km"]


def test_compute_planned_rows_metrics_reparses_valid_workout_text_when_parsed_json_is_missing() -> None:
    planned_rows = backend_main.pd.DataFrame(
        [
            {
                "day_utc": "2026-04-01",
                "line_no": 1,
                "workout_text": "xtrain 58min @57%",
                "parsed_json": "",
                "manual_done": False,
            }
        ]
    )

    metrics = backend_main._compute_planned_rows_metrics_df(
        planned_rows=planned_rows,
        lthr_curve_points=[],
        lthr_default_bpm=178.0,
        lt_pace_curve_points=[],
        lt_pace_default_sec=300.0,
        specificity_profile={"default": 0.8, "elliptical": 0.8, "non_running": 0.8},
    )

    assert len(metrics) == 1
    row = metrics.iloc[0]
    assert float(row["duration_s"]) == pytest.approx(58.0 * 60.0)
    assert float(row["if_proxy"]) == pytest.approx(0.57)
    assert float(row["tss"]) > 0
    assert float(row["distance_proxy_km"]) > 0


def test_planned_activity_label_reparses_valid_workout_text_when_parsed_json_is_missing() -> None:
    assert backend_main._planned_activity_label("", source_text="xtrain 58min @57%") == "Elliptical"


def test_compute_planned_rows_metrics_supports_legacy_segment_schema() -> None:
    planned_rows = backend_main.pd.DataFrame(
        [
            {
                "day_utc": "2026-04-01",
                "line_no": 1,
                "workout_text": "elliptical 70min @138bpm",
                "parsed_json": '[{"kind":"elliptical","minutes":70.0,"distance_km":null,"bpm":138.0,"pace_sec_per_km":null,"if_input":null,"if_input_source":null,"tss_input":null,"time_hint":null}]',
                "manual_done": False,
            }
        ]
    )

    metrics = backend_main._compute_planned_rows_metrics_df(
        planned_rows=planned_rows,
        lthr_curve_points=[],
        lthr_default_bpm=178.0,
        lt_pace_curve_points=[],
        lt_pace_default_sec=300.0,
        specificity_profile={"default": 0.8, "elliptical": 0.8, "non_running": 0.8},
    )

    assert len(metrics) == 1
    row = metrics.iloc[0]
    assert float(row["duration_s"]) == pytest.approx(70.0 * 60.0)
    assert float(row["if_proxy"]) > 0
    assert float(row["tss"]) > 0
    assert float(row["distance_proxy_km"]) > 0

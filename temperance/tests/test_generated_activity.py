import pytest

from backend.app import main as backend_main


def test_generated_activity_endpoint_returns_deterministic_planning_for_fixed_seed(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "_auth_context", lambda _authorization: {"user": "default", "role": "admin"})
    monkeypatch.setattr(backend_main, "_resolve_owner", lambda ctx, owner: "default")
    monkeypatch.setattr(backend_main, "_db_path_for_owner", lambda owner: backend_main.Path("ignored.db"))
    monkeypatch.setattr(backend_main, "_load_curve_points", lambda **kwargs: [])
    monkeypatch.setattr(backend_main, "_curve_value_at", lambda curve, default, when: 300.0)
    monkeypatch.setattr(
        backend_main,
        "_generated_activity_candidates",
        lambda **kwargs: [
            {
                "activity_text": "60' run @ 4:40/km",
                "bucket": "easy",
                "estimated_tss": 56.0,
                "avg_if": 0.68,
                "max_if": 0.70,
                "total_minutes": 60.0,
                "modality": "running",
                "source": "planned",
            },
            {
                "activity_text": "75' elliptical @ 72%",
                "bucket": "steady",
                "estimated_tss": 77.0,
                "avg_if": 0.72,
                "max_if": 0.75,
                "total_minutes": 75.0,
                "modality": "elliptical",
                "source": "planned",
            },
        ],
    )
    monkeypatch.setattr(
        backend_main,
        "_generated_activity_planning_state",
        lambda **kwargs: backend_main.build_user_planning_state(
            target_day_utc="2026-03-30",
            weekly_baseline_tss=554.0,
            recent_activity_rows=[],
            planned_activity_rows=[],
        ),
    )

    payload = backend_main.GeneratedActivityRequest(day_utc="2026-03-30", mode="planned", activity_type="running", seed=19)
    response_a = backend_main.generated_activity(payload, owner=None, authorization=None)
    response_b = backend_main.generated_activity(payload, owner=None, authorization=None)

    assert response_a["activity_text"] == response_b["activity_text"]
    assert response_a["planning"]["selected_intent"]["day_type"] == "easy"
    assert response_a["planning"]["selected_intent"]["target_tss"] == pytest.approx(
        response_b["planning"]["selected_intent"]["target_tss"]
    )


def test_generated_activity_endpoint_uses_policy_for_friday_rest_exception(monkeypatch) -> None:
    monkeypatch.setattr(backend_main, "_auth_context", lambda _authorization: {"user": "default", "role": "admin"})
    monkeypatch.setattr(backend_main, "_resolve_owner", lambda ctx, owner: "default")
    monkeypatch.setattr(backend_main, "_db_path_for_owner", lambda owner: backend_main.Path("ignored.db"))
    monkeypatch.setattr(backend_main, "_load_curve_points", lambda **kwargs: [])
    monkeypatch.setattr(backend_main, "_curve_value_at", lambda curve, default, when: 300.0)
    monkeypatch.setattr(
        backend_main,
        "_generated_activity_candidates",
        lambda **kwargs: [
            {
                "activity_text": "120' run @ 4:55/km",
                "bucket": "long",
                "estimated_tss": 101.0,
                "avg_if": 0.80,
                "max_if": 0.82,
                "total_minutes": 120.0,
                "modality": "running",
                "source": "planned",
            }
        ],
    )
    monkeypatch.setattr(
        backend_main,
        "_generated_activity_planning_state",
        lambda **kwargs: backend_main.build_user_planning_state(
            target_day_utc="2026-04-03",
            weekly_baseline_tss=554.0,
            recent_activity_rows=[
                {"day_utc": "2026-04-02", "tss": 78.0, "duration_s": 4200.0, "modality": "elliptical"},
            ],
            planned_activity_rows=[],
        ),
    )

    payload = backend_main.GeneratedActivityRequest(day_utc="2026-04-03", mode="planned", activity_type="running", seed=11)
    response = backend_main.generated_activity(payload, owner=None, authorization=None)

    assert response["activity_text"] == "Rest"
    assert response["planning"]["explanation"]["weekend_adjustment"] == "friday_rest_to_preserve_weekend_long_run"
    assert response["planning"]["selected_intent"]["day_type"] == "rest"


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

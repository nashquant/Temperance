from backend.app import mcp_server


def test_mcp_server_lists_expected_tools() -> None:
    server = mcp_server.TemperanceMCPServer()

    response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response is not None
    tool_names = [tool["name"] for tool in response["result"]["tools"]]
    assert tool_names == ["plan_next_day", "preview_cycle", "explain_planning_decision"]


def test_mcp_plan_next_day_calls_shared_planning_service(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server.backend_main,
        "_planning_decision_for_owner",
        lambda **kwargs: (
            {
                "owner": kwargs["owner"],
                "mode": kwargs["mode"],
                "activity_text": "75' elliptical @ 72%",
                "total_candidates": 2,
                "planning": {
                    "methodology_id": kwargs["methodology_id"] or "rolling_3_day_v1",
                    "selected_intent": {"day_type": "moderate", "cycle_step_id": "moderate"},
                    "explanation": {"cycle_step_id": "moderate"},
                },
            },
            None,
        ),
    )

    result = mcp_server.call_tool(
        "plan_next_day",
        {
            "owner": "default",
            "target_day_utc": "2026-04-01",
            "methodology_id": "rolling_3_day_v1",
        },
    )

    assert result["activity_text"] == "75' elliptical @ 72%"
    assert result["planning"]["methodology_id"] == "rolling_3_day_v1"


def test_mcp_explain_planning_decision_includes_methodology_and_cycle_step(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp_server.backend_main,
        "_planning_decision_for_owner",
        lambda **kwargs: (
            {
                "owner": kwargs["owner"],
                "mode": kwargs["mode"],
                "activity_text": "Rest",
                "planning": {
                    "methodology_id": "rolling_3_day_v1",
                    "selected_intent": {
                        "day_type": "rest",
                        "cycle_step_id": "hard",
                        "target_tss": 99.7,
                        "sampled_tss_share": 0.18,
                        "hard_subtype": None,
                    },
                    "explanation": {
                        "methodology_id": "rolling_3_day_v1",
                        "cycle_step_id": "hard",
                        "weekend_adjustment": "friday_rest_to_preserve_weekend_long_run",
                        "long_run_progression_reason": "long_run_progressed_from_last_long_run",
                        "candidate_rejections": ["long_run_too_short"],
                    },
                },
            },
            None,
        ),
    )

    result = mcp_server.call_tool(
        "explain_planning_decision",
        {
            "owner": "default",
            "target_day_utc": "2026-04-03",
            "methodology_id": "rolling_3_day_v1",
            "question": "Why not put the long run on Friday?",
        },
    )

    assert "rolling_3_day_v1" in result["answer"]
    assert "friday_rest_to_preserve_weekend_long_run" in result["answer"]
    assert "long_run_progressed_from_last_long_run" in result["answer"]

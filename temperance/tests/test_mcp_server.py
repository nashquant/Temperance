import unittest
from types import SimpleNamespace

from backend.app import mcp_server


class TemperanceMCPServerTest(unittest.TestCase):
    def test_mcp_server_lists_expected_tools(self) -> None:
        server = mcp_server.TemperanceMCPServer()

        response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

        self.assertIsNotNone(response)
        tool_names = [tool["name"] for tool in response["result"]["tools"]]
        self.assertIn("plan_next_day", tool_names)
        self.assertIn("preview_cycle", tool_names)
        self.assertIn("explain_planning_decision", tool_names)
        self.assertIn("get_today_status", tool_names)
        self.assertIn("get_recent_activities", tool_names)
        self.assertIn("get_planned_activities", tool_names)
        self.assertIn("get_week_outlook", tool_names)
        self.assertIn("get_load_trend", tool_names)
        self.assertIn("get_recovery_trend", tool_names)
        self.assertIn("get_activity_detail", tool_names)
        self.assertIn("judge_training_history", tool_names)
        self.assertIn("explain_history_judgment", tool_names)
        self.assertIn("save_planned_activities", tool_names)
        self.assertIn("update_planned_activity", tool_names)
        self.assertIn("delete_planned_activities", tool_names)
        self.assertIn("mark_planned_done", tool_names)
        self.assertIn("search_workouts", tool_names)
        self.assertIn("get_fitness_form", tool_names)
        self.assertIn("get_settings", tool_names)
        self.assertIn("update_settings", tool_names)
        self.assertIn("trigger_sync", tool_names)
        self.assertIn("get_sync_status", tool_names)
        self.assertIn("mark_activity_invalid", tool_names)
        self.assertNotIn("recommend_training", tool_names)
        self.assertNotIn("explain_recommendation", tool_names)
        self.assertEqual(len(tool_names), len(mcp_server.TOOLS))

    def test_mcp_server_initialize_is_unified(self) -> None:
        server = mcp_server.TemperanceMCPServer()

        response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

        self.assertIsNotNone(response)
        self.assertEqual(response["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(response["result"]["serverInfo"]["name"], "temperance-mcp")
        self.assertEqual(response["result"]["capabilities"], {"tools": {}, "resources": {}})

    def test_mcp_server_lists_static_resources(self) -> None:
        server = mcp_server.TemperanceMCPServer()

        response = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "resources/list"})

        self.assertIsNotNone(response)
        resource_uris = [resource["uri"] for resource in response["result"]["resources"]]
        self.assertEqual(
            resource_uris,
            [
                "temperance://guidelines/read-order",
                "temperance://guidelines/core-bundle",
                "temperance://guidelines/active-build",
                "temperance://workouts/overview",
                "temperance://workouts/catalog",
            ],
        )

    def test_mcp_plan_next_day_calls_shared_planning_service(self) -> None:
        original = mcp_server._backend_main_module
        try:
            mcp_server._backend_main_module = lambda: SimpleNamespace(
                _planning_decision_for_owner=lambda **kwargs: (
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
                )
            )

            result = mcp_server.call_tool(
                "plan_next_day",
                {
                    "owner": "default",
                    "target_day_utc": "2026-04-01",
                    "methodology_id": "rolling_3_day_v1",
                },
            )
        finally:
            mcp_server._backend_main_module = original

        self.assertEqual(result["activity_text"], "75' elliptical @ 72%")
        self.assertEqual(result["planning"]["methodology_id"], "rolling_3_day_v1")

    def test_mcp_explain_planning_decision_includes_methodology_and_cycle_step(self) -> None:
        original = mcp_server._backend_main_module
        try:
            mcp_server._backend_main_module = lambda: SimpleNamespace(
                _planning_decision_for_owner=lambda **kwargs: (
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
                )
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
        finally:
            mcp_server._backend_main_module = original

        self.assertIn("rolling_3_day_v1", result["answer"])
        self.assertIn("friday_rest_to_preserve_weekend_long_run", result["answer"])
        self.assertIn("long_run_progressed_from_last_long_run", result["answer"])

    def test_mcp_judge_history_uses_structured_builder(self) -> None:
        original = mcp_server._build_history_judgment_payload
        try:
            mcp_server._build_history_judgment_payload = lambda arguments: {
                "window": {"owner": arguments["owner"], "window_days": 42},
                "judgment": {"status": "mixed", "headline": "History is usable but mixed."},
                "doctrine_assessment": {"evidence_refs": ["temperance://guidelines/active-build"]},
                "narrative": "History is usable but mixed.",
            }

            result = mcp_server.call_tool("judge_training_history", {"owner": "default", "window_days": 42})
        finally:
            mcp_server._build_history_judgment_payload = original

        self.assertEqual(result["judgment"]["status"], "mixed")
        self.assertEqual(result["window"]["owner"], "default")


if __name__ == "__main__":
    unittest.main()

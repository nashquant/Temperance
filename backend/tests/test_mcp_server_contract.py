import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from backend.app import mcp_server


class TemperanceMCPServerTest(unittest.TestCase):
    def _critique_with_entries(self, entries: list[dict[str, str]], metrics_rows: list[dict[str, float]]) -> dict:
        empty_backend = SimpleNamespace(
            get_planned_activities_df=lambda **kwargs: pd.DataFrame(columns=["day_utc", "workout_text"]),
            pd=pd,
        )
        with (
            patch.object(mcp_server, "_resolve_db_path", return_value=":memory:"),
            patch.object(mcp_server, "_backend_main_module", return_value=empty_backend),
            patch.object(mcp_server, "_weekly_baseline_tss_for_day", return_value=550.0),
            patch.object(mcp_server, "_build_metrics_df_for_entries", return_value=pd.DataFrame(metrics_rows)),
        ):
            return mcp_server.tool_critique_day_plan(
                {
                    "owner": "default",
                    "start_day_utc": "2026-04-06",
                    "end_day_utc": "2026-04-14",
                    "extra_entries": entries,
                }
            )

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
        self.assertIn("prepare_week_dialogue", tool_names)
        self.assertIn("plan_week_with_dialogue", tool_names)
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

    def test_critique_day_plan_does_not_flag_support_heavy_loading_streak_as_run_density(self) -> None:
        result = self._critique_with_entries(
            entries=[
                {"day_utc": "2026-04-06", "workout_text": "35min @ 72%"},
                {"day_utc": "2026-04-07", "workout_text": "Elliptical 75min @ 78%"},
                {"day_utc": "2026-04-08", "workout_text": "Bike 90min @ 76%"},
                {"day_utc": "2026-04-09", "workout_text": "Elliptical 70min @ 77%"},
                {"day_utc": "2026-04-12", "workout_text": "100min @ 74%"},
            ],
            metrics_rows=[
                {"tss": 28.0, "rtss": 28.0, "duration_s": 2100.0, "if_proxy": 0.72},
                {"tss": 82.0, "rtss": 0.0, "duration_s": 4500.0, "if_proxy": 0.78},
                {"tss": 76.0, "rtss": 0.0, "duration_s": 5400.0, "if_proxy": 0.76},
                {"tss": 70.0, "rtss": 0.0, "duration_s": 4200.0, "if_proxy": 0.77},
                {"tss": 92.0, "rtss": 92.0, "duration_s": 6000.0, "if_proxy": 0.74},
            ],
        )

        tags = {warning["tag"] for warning in result["warnings"]}
        self.assertNotIn("consecutive_loading_streak_3", tags)
        self.assertNotIn("consecutive_loading_streak_4", tags)
        self.assertNotIn("mechanical_run_streak_3", tags)
        self.assertNotIn("mechanical_run_streak_4", tags)
        thursday = next(day for day in result["day_summary"] if day["day_utc"] == "2026-04-09")
        self.assertEqual(thursday["support_tss"], 70.0)
        self.assertFalse(thursday["meaningful_run_stress"])

    def test_modality_from_workout_text_treats_generic_xtrain_aliases_as_support(self) -> None:
        for text in [
            "75min xtrain @ 78% + 10min @ 82%",
            "Cross-train 60min @ 72%",
            "Cross training 45min @ 70%",
        ]:
            self.assertEqual(mcp_server._modality_from_workout_text(text), "support")

    def test_critique_day_plan_routes_generic_xtrain_load_into_support_tss(self) -> None:
        result = self._critique_with_entries(
            entries=[
                {"day_utc": "2026-04-06", "workout_text": "75min xtrain @ 78% + 10min @ 82%"},
            ],
            metrics_rows=[
                {"tss": 69.8, "rtss": 0.0, "duration_s": 5100.0, "if_proxy": 0.785},
            ],
        )

        monday = next(day for day in result["day_summary"] if day["day_utc"] == "2026-04-06")
        self.assertEqual(monday["run_tss"], 0.0)
        self.assertEqual(monday["support_tss"], 69.8)
        self.assertFalse(monday["meaningful_run_stress"])
        self.assertFalse(monday["hard_run_stress"])

    def test_critique_day_plan_preserves_true_run_clustering_alerts(self) -> None:
        result = self._critique_with_entries(
            entries=[
                {"day_utc": "2026-04-10", "workout_text": "15min @ 72% + 3x10min @ 90% (2min @ 72%)"},
                {"day_utc": "2026-04-11", "workout_text": "20min @ 72% + 3x12min @ 82%"},
                {"day_utc": "2026-04-12", "workout_text": "110min @ 76%"},
            ],
            metrics_rows=[
                {"tss": 72.0, "rtss": 72.0, "duration_s": 4200.0, "if_proxy": 0.90},
                {"tss": 78.0, "rtss": 78.0, "duration_s": 4800.0, "if_proxy": 0.82},
                {"tss": 102.0, "rtss": 102.0, "duration_s": 6600.0, "if_proxy": 0.76},
            ],
        )

        tags = {warning["tag"] for warning in result["warnings"]}
        self.assertIn("back_to_back_hard_run", tags)
        self.assertIn("pre_long_run_heavy", tags)
        self.assertIn("pre_long_run_run_stress_stack", tags)
        self.assertIn("quality_too_close_to_long_run", tags)
        self.assertIn("mechanical_run_streak_3", tags)
        self.assertIn("consecutive_loading_streak_3", tags)

    def test_critique_day_plan_reserves_long_run_flag_for_true_anchor_duration(self) -> None:
        result = self._critique_with_entries(
            entries=[
                {"day_utc": "2026-04-07", "workout_text": "15min run @ 72% + 5x8min @ 90% (2min @ 72%)"},
                {"day_utc": "2026-04-12", "workout_text": "110min @ 76%"},
            ],
            metrics_rows=[
                {"tss": 75.6, "rtss": 75.6, "duration_s": 5700.0, "if_proxy": 0.81},
                {"tss": 102.0, "rtss": 102.0, "duration_s": 6600.0, "if_proxy": 0.76},
            ],
        )

        tuesday = next(day for day in result["day_summary"] if day["day_utc"] == "2026-04-07")
        sunday = next(day for day in result["day_summary"] if day["day_utc"] == "2026-04-12")

        self.assertFalse(tuesday["is_long_run"])
        self.assertTrue(tuesday["meaningful_run_stress"])
        self.assertTrue(tuesday["specific_like_run"])
        self.assertFalse(tuesday["long_duration_run"])

        self.assertTrue(sunday["is_long_run"])
        self.assertTrue(sunday["long_duration_run"])

    def test_critique_day_plan_flags_long_runs_too_close_together(self) -> None:
        result = self._critique_with_entries(
            entries=[
                {"day_utc": "2026-04-06", "workout_text": "100min @ 74%"},
                {"day_utc": "2026-04-11", "workout_text": "105min @ 75%"},
            ],
            metrics_rows=[
                {"tss": 92.0, "rtss": 92.0, "duration_s": 6000.0, "if_proxy": 0.74},
                {"tss": 96.0, "rtss": 96.0, "duration_s": 6300.0, "if_proxy": 0.75},
            ],
        )

        long_run_warning = next(
            warning for warning in result["warnings"] if warning["tag"] == "long_run_spacing_tight"
        )
        self.assertEqual(long_run_warning["gap_days"], 5)

    def test_critique_day_plan_keeps_hard_support_recovery_warnings_before_run_stress(self) -> None:
        result = self._critique_with_entries(
            entries=[
                {"day_utc": "2026-04-10", "workout_text": "Elliptical 90min @ 90%"},
                {"day_utc": "2026-04-11", "workout_text": "15min @ 72% + 3x10min @ 90% (2min @ 72%)"},
            ],
            metrics_rows=[
                {"tss": 90.0, "rtss": 0.0, "duration_s": 5400.0, "if_proxy": 0.90},
                {"tss": 72.0, "rtss": 72.0, "duration_s": 4200.0, "if_proxy": 0.90},
            ],
        )

        tags = {warning["tag"] for warning in result["warnings"]}
        self.assertIn("back_to_back_hard_run", tags)

        long_run_result = self._critique_with_entries(
            entries=[
                {"day_utc": "2026-04-11", "workout_text": "Elliptical 90min @ 90%"},
                {"day_utc": "2026-04-12", "workout_text": "110min @ 76%"},
            ],
            metrics_rows=[
                {"tss": 90.0, "rtss": 0.0, "duration_s": 5400.0, "if_proxy": 0.90},
                {"tss": 102.0, "rtss": 102.0, "duration_s": 6600.0, "if_proxy": 0.76},
            ],
        )

        long_run_tags = {warning["tag"] for warning in long_run_result["warnings"]}
        self.assertIn("pre_long_run_heavy", long_run_tags)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

from backend.app import mcp_server


class MCPServerHelpersTest(unittest.TestCase):
    def test_module_imports_without_fastapi_dependency_path(self):
        self.assertEqual(mcp_server.SERVER_INFO["name"], "temperance-mcp")
        self.assertEqual(mcp_server.SERVER_INFO["version"], "0.4.0")
        self.assertEqual(mcp_server.SERVER_PROTOCOL_VERSION, "2025-03-26")
        self.assertIn("plan_next_day", mcp_server.TOOLS)
        self.assertIn("get_activity_detail", mcp_server.TOOLS)
        self.assertIn("judge_training_history", mcp_server.TOOLS)
        self.assertNotIn("recommend_training", mcp_server.TOOLS)
        self.assertNotIn("explain_recommendation", mcp_server.TOOLS)
        self.assertIsNone(mcp_server._BACKEND_MAIN_MODULE)

    def test_new_write_tools_are_registered(self):
        for tool_name in [
            "save_planned_activities",
            "update_planned_activity",
            "delete_planned_activities",
            "mark_planned_done",
            "save_custom_activities",
            "delete_custom_activities",
            "trigger_sync",
            "get_sync_status",
            "mark_activity_invalid",
            "get_settings",
            "update_settings",
            "search_workouts",
            "get_fitness_form",
        ]:
            self.assertIn(tool_name, mcp_server.TOOLS, f"Missing tool: {tool_name}")

    def test_tools_list_returns_all_registered_tools(self):
        response = mcp_server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tool_names = {t["name"] for t in response["result"]["tools"]}
        self.assertEqual(len(tool_names), len(mcp_server.TOOLS))
        for name in mcp_server.TOOLS:
            self.assertIn(name, tool_names)

    def test_initialize_advertises_tools_and_resources(self):
        response = mcp_server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(response["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(response["result"]["serverInfo"]["name"], "temperance-mcp")
        self.assertEqual(response["result"]["capabilities"], {"tools": {}, "resources": {}})

    def test_activity_row_summary_is_stable_for_pure_formatting(self):
        summary = mcp_server._activity_row_summary(
            {
                "activity_id": 42,
                "start_time_utc": "2026-03-31T09:15:00Z",
                "sport_type": "running",
                "duration_s": 3660,
                "distance_m": 12345,
                "tss": 71.27,
                "rtss": 74.61,
                "if_proxy": 0.8871,
                "avg_hr": 151.3,
                "mechanical_load": 88.812,
            },
            include_extended_metrics=False,
        )
        self.assertEqual(
            summary,
            {
                "activity_id": "42",
                "start_time_utc": "2026-03-31T09:15:00+00:00",
                "sport_type": "running",
                "duration_min": 61.0,
                "distance_km": 12.35,
                "tss": 71.3,
                "rtss": 74.6,
                "if_proxy": 0.887,
                "avg_hr": 151.3,
                "mechanical_load": 88.81,
            },
        )

    def test_handle_message_reports_unknown_method(self):
        response = mcp_server.handle_message({"jsonrpc": "2.0", "id": 9, "method": "bogus"})
        self.assertEqual(
            response,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "error": {"code": -32601, "message": "Method not found: bogus"},
            },
        )

    def test_resources_list_exposes_static_resources(self):
        response = mcp_server.handle_message({"jsonrpc": "2.0", "id": 10, "method": "resources/list"})
        uris = [resource["uri"] for resource in response["result"]["resources"]]
        self.assertEqual(
            uris,
            [
                "temperance://guidelines/read-order",
                "temperance://guidelines/core-bundle",
                "temperance://guidelines/active-build",
                "temperance://workouts/overview",
                "temperance://workouts/catalog",
            ],
        )

    def test_resource_templates_list_exposes_dynamic_templates(self):
        response = mcp_server.handle_message({"jsonrpc": "2.0", "id": 11, "method": "resources/templates/list"})
        templates = [item["uriTemplate"] for item in response["result"]["resourceTemplates"]]
        self.assertEqual(
            templates,
            [
                "temperance://guidelines/doc/{doc_id}",
                "temperance://workouts/family/{session_family}",
                "temperance://workouts/template/{template_id}",
                "temperance://planning/context/{owner}/{target_day_utc}",
                "temperance://history/snapshot/{owner}/{window_days}",
            ],
        )

    def test_resources_read_returns_static_json_content(self):
        response = mcp_server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "resources/read",
                "params": {"uri": "temperance://guidelines/read-order"},
            }
        )
        self.assertIn("contents", response["result"])
        payload = json.loads(response["result"]["contents"][0]["text"])
        self.assertEqual(payload["doc"]["doc_id"], "training-llm-instructions")
        self.assertIn("read_order", payload)
        self.assertIn("precedence", payload)
        self.assertTrue(payload["precedence"])
        self.assertIn("interpretation_rules", payload)
        self.assertTrue(payload["interpretation_rules"])

    def test_resources_read_prefers_local_override_for_guideline_docs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            guidelines_dir = Path(temp_dir)
            (guidelines_dir / "example.md").write_text("# Example\n\nStatus: tracked.\n", encoding="utf-8")
            (guidelines_dir / "example.local.md").write_text("# Example Local\n\nStatus: local.\n", encoding="utf-8")
            original = mcp_server.GUIDELINES_DIR
            try:
                mcp_server.GUIDELINES_DIR = guidelines_dir
                response = mcp_server.handle_message(
                    {
                        "jsonrpc": "2.0",
                        "id": 13,
                        "method": "resources/read",
                        "params": {"uri": "temperance://guidelines/doc/example"},
                    }
                )
            finally:
                mcp_server.GUIDELINES_DIR = original
            payload = json.loads(response["result"]["contents"][0]["text"])
            self.assertTrue(payload["is_local_override"])
            self.assertEqual(payload["status"], "local.")

    def test_resources_read_returns_32002_for_unknown_resource(self):
        response = mcp_server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "resources/read",
                "params": {"uri": "temperance://guidelines/doc/does-not-exist"},
            }
        )
        self.assertEqual(response["error"]["code"], -32002)

    def test_workout_template_resource_exposes_front_matter(self):
        response = mcp_server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 15,
                "method": "resources/read",
                "params": {"uri": "temperance://workouts/template/threshold_15min_72_3x10_90_2rec"},
            }
        )
        payload = json.loads(response["result"]["contents"][0]["text"])
        self.assertEqual(payload["template_id"], "threshold_15min_72_3x10_90_2rec")
        self.assertEqual(payload["front_matter"]["session_family"], "lt1-threshold")

    def test_family_resource_exposes_template_summaries(self):
        response = mcp_server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 16,
                "method": "resources/read",
                "params": {"uri": "temperance://workouts/family/lt2-threshold"},
            }
        )
        payload = json.loads(response["result"]["contents"][0]["text"])
        self.assertEqual(payload["session_family"], "lt2-threshold")
        self.assertGreaterEqual(len(payload["templates"]), 3)

    def test_planning_context_resource_dispatches_to_context_builder(self):
        original = mcp_server._build_planning_context_payload
        try:
            mcp_server._build_planning_context_payload = lambda owner, target_day_utc: {
                "owner": owner,
                "target_day_utc": target_day_utc,
                "preview_horizon": [],
            }
            response = mcp_server.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": 17,
                    "method": "resources/read",
                    "params": {"uri": "temperance://planning/context/admin/2026-04-05"},
                }
            )
        finally:
            mcp_server._build_planning_context_payload = original
        payload = json.loads(response["result"]["contents"][0]["text"])
        self.assertEqual(payload["owner"], "admin")
        self.assertEqual(payload["target_day_utc"], "2026-04-05")

    def test_history_snapshot_resource_dispatches_to_snapshot_builder(self):
        original = mcp_server._build_history_snapshot_payload
        try:
            mcp_server._build_history_snapshot_payload = lambda owner, window_days: {
                "owner": owner,
                "window_days": window_days,
                "load_summary": {"total_tss": 321.0},
            }
            response = mcp_server.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": 18,
                    "method": "resources/read",
                    "params": {"uri": "temperance://history/snapshot/admin/42"},
                }
            )
        finally:
            mcp_server._build_history_snapshot_payload = original
        payload = json.loads(response["result"]["contents"][0]["text"])
        self.assertEqual(payload["owner"], "admin")
        self.assertEqual(payload["window_days"], 42)

    def test_tool_get_activity_detail_delegates_to_backend_handler(self):
        captured = {}

        def fake_handler(*, activity_id, owner, include_records, records_limit, authorization):
            captured.update(
                {
                    "activity_id": activity_id,
                    "owner": owner,
                    "include_records": include_records,
                    "records_limit": records_limit,
                    "authorization": authorization,
                }
            )
            return {"activity": {"activity_id": activity_id}, "records": []}

        original = mcp_server._activity_detail_handler
        try:
            mcp_server._activity_detail_handler = lambda: fake_handler
            payload = mcp_server.tool_get_activity_detail(
                {
                    "owner": "admin",
                    "activity_id": "run-123",
                    "include_records": False,
                    "records_limit": 25,
                }
            )
        finally:
            mcp_server._activity_detail_handler = original

        self.assertEqual(payload["activity"]["activity_id"], "run-123")
        self.assertEqual(
            captured,
            {
                "activity_id": "run-123",
                "owner": "admin",
                "include_records": False,
                "records_limit": 100,
                "authorization": None,
            },
        )

    def test_search_workouts_returns_all_when_no_filters(self):
        result = mcp_server.tool_search_workouts({})
        self.assertGreater(result["count"], 0)
        self.assertIn("templates", result)
        for tmpl in result["templates"]:
            self.assertIn("template_id", tmpl)
            self.assertIn("session_family", tmpl)
            self.assertIn("category", tmpl)

    def test_search_workouts_filters_by_category(self):
        result = mcp_server.tool_search_workouts({"category": "threshold-hard"})
        self.assertGreater(result["count"], 0)
        for tmpl in result["templates"]:
            self.assertEqual(tmpl["category"], "threshold-hard")

    def test_search_workouts_filters_by_session_family(self):
        result = mcp_server.tool_search_workouts({"session_family": "lt1-threshold"})
        self.assertGreater(result["count"], 0)
        for tmpl in result["templates"]:
            self.assertEqual(tmpl["session_family"], "lt1-threshold")

    def test_search_workouts_filters_by_tss_range(self):
        result = mcp_server.tool_search_workouts({"tss_min": 50, "tss_max": 80})
        for tmpl in result["templates"]:
            tss = float(tmpl.get("baseline_estimated_tss") or 0)
            self.assertGreaterEqual(tss, 50)
            self.assertLessEqual(tss, 80)

    def test_search_workouts_empty_result_for_impossible_filter(self):
        result = mcp_server.tool_search_workouts({"category": "nonexistent-category-xyz"})
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["templates"], [])

    def test_get_fitness_form_exposes_baseline_history_fields(self):
        fake_daily_progression = {
            "points": [
                {
                    "period_start": "2026-03-01",
                    "tss": 55.0,
                    "rtss": 57.0,
                    "duration_h": 1.0,
                    "distance_km": 10.0,
                    "distance_eqv_km": 10.2,
                    "target_tss": 60.0,
                    "baseline_tss": 60.0,
                    "baseline_distance_km": 11.0,
                    "lt_target_tss": 63.0,
                    "lt_target_distance_km": 11.5,
                    "capacity_baseline_tss": 62.0,
                    "recent_load_anchor_tss": 58.0,
                    "blended_baseline_tss_before_smoothing": 59.0,
                    "smoothed_baseline_tss": 60.0,
                    "fitness": 45.0,
                    "fatigue": 50.0,
                    "overreach": 20.0,
                    "injury_risk": 15.0,
                    "durability": 40.0,
                    "pounding": 42.0,
                }
            ]
        }
        fake_weekly_progression = {
            "points": [
                {
                    "period_start": "2026-02-23",
                    "baseline_tss": 57.0,
                    "baseline_distance_km": 10.5,
                    "lt_target_tss": 63.0,
                    "lt_target_distance_km": 11.5,
                    "capacity_baseline_tss": 61.0,
                    "recent_load_anchor_tss": 56.0,
                    "blended_baseline_tss_before_smoothing": 57.5,
                    "smoothed_baseline_tss": 57.0,
                }
            ]
        }

        def _fake_progression_builder(**kwargs):
            if kwargs.get("aggregation") == "weekly":
                return fake_weekly_progression
            return fake_daily_progression

        with (
            patch("backend.app.mcp_server._resolve_db_path", return_value=Path("/tmp/fake.sqlite")),
            patch(
                "backend.app.mcp_server._analytics_helpers",
                return_value={"_build_athlete_progression_payload": _fake_progression_builder},
            ),
        ):
            result = mcp_server.tool_get_fitness_form({"owner": "admin", "days": 14})

        self.assertEqual(len(result["daily"]), 1)
        point = result["daily"][0]
        self.assertEqual(point["day"], "2026-03-01")
        self.assertEqual(point["baseline_tss"], 60.0)
        self.assertEqual(point["baseline_distance_km"], 11.0)
        self.assertEqual(point["lt_target_tss"], 63.0)
        self.assertEqual(point["capacity_baseline_tss"], 62.0)
        self.assertEqual(point["recent_load_anchor_tss"], 58.0)
        self.assertEqual(point["blended_baseline_tss_before_smoothing"], 59.0)
        self.assertEqual(point["smoothed_baseline_tss"], 60.0)
        self.assertEqual(point["fitness"], 45.0)
        self.assertEqual(point["target_tss"], 60.0)
        self.assertEqual(len(result["weekly_baseline"]), 1)
        weekly_point = result["weekly_baseline"][0]
        self.assertEqual(weekly_point["week_start"], "2026-02-23")
        self.assertEqual(weekly_point["baseline_tss"], 57.0)
        self.assertEqual(weekly_point["capacity_baseline_tss"], 61.0)
        self.assertEqual(weekly_point["deviation_from_lt_tss"], -6.0)
        self.assertAlmostEqual(weekly_point["deviation_from_lt_pct"], -0.0952, places=4)
        self.assertEqual(weekly_point["capacity_vs_lt_tss"], -2.0)
        self.assertEqual(weekly_point["recent_vs_capacity_tss"], -5.0)
        self.assertEqual(weekly_point["smoothing_adjustment_tss"], -0.5)
        self.assertEqual(weekly_point["deviation_reason"], "balanced_blend")

    def test_get_fitness_form_weekly_baseline_includes_current_week(self):
        fake_daily_progression = {
            "points": [
                {
                    "period_start": "2026-03-05",
                    "tss": 40.0,
                    "rtss": 40.0,
                    "duration_h": 1.0,
                    "distance_km": 8.0,
                    "distance_eqv_km": 8.0,
                    "target_tss": 60.0,
                    "baseline_tss": 60.0,
                    "baseline_distance_km": 10.0,
                    "lt_target_tss": 70.0,
                    "lt_target_distance_km": 11.0,
                    "capacity_baseline_tss": 77.0,
                    "recent_load_anchor_tss": 80.0,
                    "blended_baseline_tss_before_smoothing": 61.5,
                    "smoothed_baseline_tss": 60.0,
                    "fitness": 45.0,
                    "fatigue": 48.0,
                    "overreach": 10.0,
                    "injury_risk": 8.0,
                    "durability": 41.0,
                    "pounding": 42.0,
                }
            ]
        }
        fake_weekly_progression = {
            "points": [
                {
                    "period_start": "2026-02-23",
                    "baseline_tss": 55.0,
                    "baseline_distance_km": 9.5,
                    "lt_target_tss": 70.0,
                    "lt_target_distance_km": 11.0,
                    "capacity_baseline_tss": 77.0,
                    "recent_load_anchor_tss": 60.0,
                    "blended_baseline_tss_before_smoothing": 56.0,
                    "smoothed_baseline_tss": 55.0,
                }
            ]
        }

        def _fake_progression_builder(**kwargs):
            if kwargs.get("aggregation") == "weekly":
                return fake_weekly_progression
            return fake_daily_progression

        with (
            patch("backend.app.mcp_server._resolve_db_path", return_value=Path("/tmp/fake.sqlite")),
            patch(
                "backend.app.mcp_server._analytics_helpers",
                return_value={"_build_athlete_progression_payload": _fake_progression_builder},
            ),
            patch("backend.app.mcp_server.datetime", wraps=datetime) as mock_datetime,
        ):
            mock_datetime.now.return_value = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)
            result = mcp_server.tool_get_fitness_form({"owner": "admin", "days": 14})

        week_starts = [row["week_start"] for row in result["weekly_baseline"]]
        self.assertIn("2026-03-02", week_starts)
        current_week = next(row for row in result["weekly_baseline"] if row["week_start"] == "2026-03-02")
        self.assertEqual(current_week["baseline_tss"], 60.0)
        self.assertEqual(current_week["deviation_from_lt_tss"], -10.0)

    def test_activity_row_summary_includes_pace_and_extended_metrics(self):
        summary = mcp_server._activity_row_summary(
            {
                "activity_id": 99,
                "start_time_utc": "2026-03-31T09:15:00Z",
                "sport_type": "running",
                "duration_s": 3660,
                "distance_m": 12345,
                "tss": 71.27,
                "rtss": 74.61,
                "if_proxy": 0.8871,
                "avg_hr": 151.3,
                "max_hr": 172.0,
                "avg_pace_s_per_km": 280,
                "elevation_gain_m": 95.5,
                "mechanical_load": 88.812,
                "distance_proxy_km": 12.35,
                "training_load_garmin": 45.2,
                "avg_cadence": 178.0,
                "hr_zone_1_pct": 10.0,
                "hr_zone_2_pct": 40.0,
                "hr_zone_3_pct": 30.0,
                "hr_zone_4_pct": 15.0,
                "hr_zone_5_pct": 5.0,
            },
            include_extended_metrics=True,
        )
        self.assertEqual(summary["avg_pace"], "4:40")
        self.assertEqual(summary["max_hr"], 172.0)
        self.assertEqual(summary["elevation_gain_m"], 96.0)
        self.assertEqual(summary["avg_cadence"], 178.0)
        self.assertIn("hr_zones", summary)
        self.assertEqual(summary["hr_zones"]["z1"], 10.0)
        self.assertEqual(summary["hr_zones"]["z5"], 5.0)

    def test_format_pace_helper(self):
        self.assertEqual(mcp_server._format_pace(280), "4:40")
        self.assertEqual(mcp_server._format_pace(300), "5:00")
        self.assertEqual(mcp_server._format_pace(195), "3:15")
        self.assertIsNone(mcp_server._format_pace(0))
        self.assertIsNone(mcp_server._format_pace(None))

    def test_hr_zone_dict_returns_none_for_zero_zones(self):
        result = mcp_server._hr_zone_dict({
            "hr_zone_1_pct": 0,
            "hr_zone_2_pct": 0,
            "hr_zone_3_pct": 0,
            "hr_zone_4_pct": 0,
            "hr_zone_5_pct": 0,
        })
        self.assertIsNone(result)

    def test_hr_zone_dict_returns_dict_for_valid_zones(self):
        result = mcp_server._hr_zone_dict({
            "hr_zone_1_pct": 50.0,
            "hr_zone_2_pct": 30.0,
            "hr_zone_3_pct": 10.0,
            "hr_zone_4_pct": 7.0,
            "hr_zone_5_pct": 3.0,
        })
        self.assertIsNotNone(result)
        self.assertEqual(result["z1"], 50.0)

    def test_new_tools_are_registered(self):
        for tool_name in [
            "get_weekly_volume",
            "get_coaching_brief",
        ]:
            self.assertIn(tool_name, mcp_server.TOOLS, f"Missing tool: {tool_name}")

    def test_require_pandas_raises_when_missing(self):
        original_pd = mcp_server.pd
        try:
            mcp_server.pd = None
            with self.assertRaises(RuntimeError):
                mcp_server._require_pandas()
        finally:
            mcp_server.pd = original_pd

    def test_active_build_brief_returns_dict(self):
        brief = mcp_server._active_build_brief()
        self.assertIsInstance(brief, dict)
        if brief:
            self.assertIn("resource_refs", brief)

    def test_all_tool_schemas_are_valid_json_schema(self):
        for name, spec in mcp_server.TOOLS.items():
            schema = spec.input_schema
            self.assertIn("type", schema, f"Tool {name} schema missing 'type'")
            self.assertIn("properties", schema, f"Tool {name} schema missing 'properties'")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pandas as pd

from backend.app import mcp_server


def _metrics_frame(daily_tss_values: list[float], start_day: str = "2026-01-05") -> pd.DataFrame:
    start = pd.Timestamp(start_day, tz="UTC")
    rows: list[dict[str, object]] = []
    for index, tss in enumerate(daily_tss_values, start=1):
        start_time = start + pd.Timedelta(days=index - 1, hours=12)
        rows.append(
            {
                "activity_id": index,
                "start_time_utc": start_time.isoformat(),
                "sport_type": "running",
                "distance_m": 10_000.0,
                "distance_proxy_km": 10.0,
                "duration_s": 3_600.0,
                "tss": float(tss),
                "rtss": float(tss),
                "training_load_garmin": float(tss),
                "calories_total": 600.0,
            }
        )
    return pd.DataFrame(rows)


def _empty_vdot_frame(_: pd.DataFrame, __: Path) -> pd.DataFrame:
    return pd.DataFrame(columns=["day", "vdot", "vdot_max"])


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

    def test_tools_call_reports_unknown_tool(self):
        response = mcp_server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": "does_not_exist", "arguments": {}},
            }
        )
        self.assertEqual(
            response,
            {
                "jsonrpc": "2.0",
                "id": 9,
                "error": {"code": -32602, "message": "Unknown tool: does_not_exist"},
            },
        )

    def test_main_defaults_to_stdio(self):
        with patch("backend.app.mcp_server.serve_stdio", return_value=7) as mock_serve_stdio:
            result = mcp_server.main([])

        self.assertEqual(result, 7)
        mock_serve_stdio.assert_called_once_with()

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
        self.assertIn("workout_template_behavior", payload)
        self.assertIn(
            "do not classify a template as `run-only` just because the prose discusses running-specific load, mechanical run stress, durability, or injury-risk tradeoffs; those are generic doctrine concepts unless the stored session itself requires running",
            payload["workout_template_behavior"],
        )

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

    def test_planning_context_builder_delegates_to_backend_core(self):
        original = mcp_server._backend_main_module
        original_active_build = mcp_server._build_active_build_payload
        original_today_status = mcp_server.tool_get_today_status
        try:
            mcp_server._build_active_build_payload = lambda: {"active_build_doc": {"markdown": "phase"}}
            mcp_server.tool_get_today_status = lambda arguments: {"owner": arguments["owner"], "status": "ok"}
            mcp_server._backend_main_module = lambda: type(
                "BackendMain",
                (),
                {
                    "_mcp_planning_context_payload": staticmethod(
                        lambda **kwargs: {
                            "owner": kwargs["owner"],
                            "target_day_utc": kwargs["target_day_utc"],
                            "active_build": kwargs["active_build"],
                            "today_status": kwargs["today_status"],
                            "doctrine_resource_refs": kwargs["doctrine_resource_refs"],
                            "methodology_id": kwargs["methodology_id"],
                        }
                    )
                },
            )()

            payload = mcp_server._build_planning_context_payload("admin", "2026-04-05")
        finally:
            mcp_server._backend_main_module = original
            mcp_server._build_active_build_payload = original_active_build
            mcp_server.tool_get_today_status = original_today_status

        self.assertEqual(payload["owner"], "admin")
        self.assertEqual(payload["target_day_utc"], "2026-04-05")
        self.assertEqual(payload["today_status"]["status"], "ok")
        self.assertEqual(payload["methodology_id"], mcp_server.DEFAULT_METHODOLOGY_ID)
        self.assertTrue(payload["doctrine_resource_refs"])

    def test_history_judgment_builder_delegates_to_backend_core(self):
        original = mcp_server._backend_main_module
        original_active_build = mcp_server._build_active_build_payload
        try:
            mcp_server._build_active_build_payload = lambda: {"active_build_doc": {"markdown": "threshold"}}
            mcp_server._backend_main_module = lambda: type(
                "BackendMain",
                (),
                {
                    "_mcp_build_history_judgment_payload": staticmethod(
                        lambda **kwargs: {
                            "window": {"owner": kwargs["owner"], "window_days": kwargs["window_days"]},
                            "active_build": kwargs["active_build"],
                            "doctrine_assessment": {"evidence_refs": kwargs["evidence_refs"]},
                            "judgment": {"status": "mixed"},
                        }
                    )
                },
            )()

            payload = mcp_server._build_history_judgment_payload({"owner": "admin", "window_days": 42})
        finally:
            mcp_server._backend_main_module = original
            mcp_server._build_active_build_payload = original_active_build

        self.assertEqual(payload["window"]["owner"], "admin")
        self.assertEqual(payload["window"]["window_days"], 42)
        self.assertEqual(payload["judgment"]["status"], "mixed")
        self.assertTrue(payload["doctrine_assessment"]["evidence_refs"])

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

    def _build_canonical_progression_payload(
        self,
        daily_tss_values: list[float],
        *,
        aggregation: str,
        days: int = 84,
        start_day: str = "2026-01-05",
        weekly_tss_target: float = 420.0,
        weekly_distance_target: float = 70.0,
        now_dt: Optional[datetime] = None,
    ) -> dict[str, object]:
        metrics_df = _metrics_frame(daily_tss_values, start_day=start_day)
        effective_now = now_dt or datetime(2026, 2, 15, tzinfo=timezone.utc)
        original_backend_main_module = mcp_server._BACKEND_MAIN_MODULE
        try:
            with (
                patch("backend.app.main.get_setting", return_value=None),
                patch("backend.app.main._metrics_for_filters", return_value=metrics_df),
                patch("backend.app.main._build_daily_vdot_series", side_effect=_empty_vdot_frame),
                patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=float(weekly_tss_target)),
                patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=float(weekly_distance_target)),
                patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
            ):
                from backend.app.main import _build_athlete_progression_payload

                mock_datetime.now.return_value = effective_now
                return _build_athlete_progression_payload(
                    db_path=Path("/tmp/athlete-progression-baseline-test.sqlite"),
                    days=days,
                    activity_filter="all",
                    aggregation=aggregation,
                    owner="tester",
                )
        finally:
            mcp_server._BACKEND_MAIN_MODULE = original_backend_main_module

    def _run_fitness_form_with_canonical_progression(
        self,
        daily_tss_values: list[float],
        *,
        days: int = 84,
        start_day: str = "2026-01-05",
        weekly_tss_target: float = 420.0,
        weekly_distance_target: float = 70.0,
        now_dt: Optional[datetime] = None,
    ) -> dict[str, object]:
        metrics_df = _metrics_frame(daily_tss_values, start_day=start_day)
        effective_now = now_dt or datetime(2026, 2, 15, tzinfo=timezone.utc)
        original_backend_main_module = mcp_server._BACKEND_MAIN_MODULE
        try:
            with (
                patch("backend.app.mcp_server._resolve_db_path", return_value=Path("/tmp/athlete-progression-baseline-test.sqlite")),
                patch("backend.app.main.get_setting", return_value=None),
                patch("backend.app.main._metrics_for_filters", return_value=metrics_df),
                patch("backend.app.main._build_daily_vdot_series", side_effect=_empty_vdot_frame),
                patch("backend.app.main._weekly_tss_target_from_lt_pace", return_value=float(weekly_tss_target)),
                patch("backend.app.main._weekly_distance_target_from_lt_pace", return_value=float(weekly_distance_target)),
                patch("backend.app.main.datetime", wraps=datetime) as mock_datetime,
            ):
                mock_datetime.now.return_value = effective_now
                return mcp_server.tool_get_fitness_form({"owner": "admin", "days": days})
        finally:
            mcp_server._BACKEND_MAIN_MODULE = original_backend_main_module

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
                return_value={
                    "_build_athlete_progression_payload": _fake_progression_builder,
                    "_format_athlete_progression_weekly_baseline_point": lambda point: {
                        "week_start": str(point.get("period_start") or ""),
                        "baseline_tss": round(float(point.get("baseline_tss") or 0.0), 1),
                        "baseline_distance_km": round(float(point.get("baseline_distance_km") or 0.0), 2),
                        "lt_target_tss": round(float(point.get("lt_target_tss") or 0.0), 1),
                        "capacity_baseline_tss": round(float(point.get("capacity_baseline_tss") or 0.0), 1),
                        "recent_load_anchor_tss": round(float(point.get("recent_load_anchor_tss") or 0.0), 1),
                        "blended_baseline_tss_before_smoothing": round(float(point.get("blended_baseline_tss_before_smoothing") or 0.0), 1),
                        "smoothed_baseline_tss": round(float(point.get("smoothed_baseline_tss") or 0.0), 1),
                        "deviation_from_lt_tss": round(float(point.get("baseline_tss") or 0.0) - float(point.get("lt_target_tss") or 0.0), 1),
                        "deviation_from_lt_pct": round((float(point.get("baseline_tss") or 0.0) / float(point.get("lt_target_tss") or 1.0)) - 1.0, 4)
                        if float(point.get("lt_target_tss") or 0.0) > 0
                        else None,
                        "capacity_vs_lt_tss": round(float(point.get("capacity_baseline_tss") or 0.0) - float(point.get("lt_target_tss") or 0.0), 1),
                        "recent_vs_capacity_tss": round(float(point.get("recent_load_anchor_tss") or 0.0) - float(point.get("capacity_baseline_tss") or 0.0), 1),
                        "smoothing_adjustment_tss": round(float(point.get("smoothed_baseline_tss") or 0.0) - float(point.get("blended_baseline_tss_before_smoothing") or 0.0), 1),
                        "deviation_reason": "balanced_blend",
                    },
                },
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
        self.assertIn(weekly_point["deviation_reason"], {"history_anchor_below_capacity", "balanced_blend"})

    def test_get_fitness_form_weekly_baseline_includes_current_week_from_weekly_progression(self):
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
                },
                {
                    "period_start": "2026-03-02",
                    "baseline_tss": 60.0,
                    "baseline_distance_km": 10.0,
                    "lt_target_tss": 70.0,
                    "lt_target_distance_km": 11.0,
                    "capacity_baseline_tss": 77.0,
                    "recent_load_anchor_tss": 80.0,
                    "blended_baseline_tss_before_smoothing": 61.5,
                    "smoothed_baseline_tss": 60.0,
                },
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
                return_value={
                    "_build_athlete_progression_payload": _fake_progression_builder,
                    "_format_athlete_progression_weekly_baseline_point": lambda point: {
                        "week_start": str(point.get("period_start") or ""),
                        "baseline_tss": round(float(point.get("baseline_tss") or 0.0), 1),
                        "deviation_from_lt_tss": round(float(point.get("baseline_tss") or 0.0) - float(point.get("lt_target_tss") or 0.0), 1),
                    },
                },
            ),
        ):
            result = mcp_server.tool_get_fitness_form({"owner": "admin", "days": 14})

        week_starts = [row["week_start"] for row in result["weekly_baseline"]]
        self.assertIn("2026-03-02", week_starts)
        current_week = next(row for row in result["weekly_baseline"] if row["week_start"] == "2026-03-02")
        self.assertEqual(current_week["baseline_tss"], 60.0)
        self.assertEqual(current_week["deviation_from_lt_tss"], -10.0)

    def test_get_fitness_form_weekly_baseline_uses_weekly_progression_values_without_projection(self):
        fake_daily_progression = {
            "points": [
                {
                    "period_start": "2026-03-03",
                    "baseline_tss": 60.0,
                    "baseline_distance_km": 10.0,
                    "lt_target_tss": 70.0,
                    "lt_target_distance_km": 11.0,
                    "capacity_baseline_tss": 77.0,
                    "recent_load_anchor_tss": 66.0,
                    "blended_baseline_tss_before_smoothing": 60.0,
                    "smoothed_baseline_tss": 60.0,
                    "tss": 40.0,
                    "rtss": 40.0,
                    "duration_h": 1.0,
                    "distance_km": 8.0,
                    "distance_eqv_km": 8.0,
                    "target_tss": 60.0,
                    "fitness": 45.0,
                    "fatigue": 48.0,
                    "overreach": 10.0,
                    "injury_risk": 8.0,
                    "durability": 41.0,
                    "pounding": 42.0,
                },
                {
                    "period_start": "2026-03-04",
                    "baseline_tss": 62.0,
                    "baseline_distance_km": 10.2,
                    "lt_target_tss": 70.0,
                    "lt_target_distance_km": 11.0,
                    "capacity_baseline_tss": 77.0,
                    "recent_load_anchor_tss": 68.0,
                    "blended_baseline_tss_before_smoothing": 62.0,
                    "smoothed_baseline_tss": 62.0,
                    "tss": 41.0,
                    "rtss": 41.0,
                    "duration_h": 1.0,
                    "distance_km": 8.2,
                    "distance_eqv_km": 8.2,
                    "target_tss": 62.0,
                    "fitness": 45.5,
                    "fatigue": 48.5,
                    "overreach": 10.2,
                    "injury_risk": 8.2,
                    "durability": 41.0,
                    "pounding": 42.0,
                },
                {
                    "period_start": "2026-03-05",
                    "baseline_tss": 64.0,
                    "baseline_distance_km": 10.4,
                    "lt_target_tss": 70.0,
                    "lt_target_distance_km": 11.0,
                    "capacity_baseline_tss": 77.0,
                    "recent_load_anchor_tss": 70.0,
                    "blended_baseline_tss_before_smoothing": 64.0,
                    "smoothed_baseline_tss": 64.0,
                    "tss": 42.0,
                    "rtss": 42.0,
                    "duration_h": 1.0,
                    "distance_km": 8.4,
                    "distance_eqv_km": 8.4,
                    "target_tss": 64.0,
                    "fitness": 46.0,
                    "fatigue": 49.0,
                    "overreach": 10.5,
                    "injury_risk": 8.4,
                    "durability": 41.0,
                    "pounding": 42.0,
                },
            ]
        }
        fake_weekly_progression = {
            "points": [
                {
                    "period_start": "2026-03-02",
                    "baseline_tss": 58.0,
                    "baseline_distance_km": 9.8,
                    "lt_target_tss": 70.0,
                    "lt_target_distance_km": 11.0,
                    "capacity_baseline_tss": 77.0,
                    "recent_load_anchor_tss": 67.0,
                    "blended_baseline_tss_before_smoothing": 58.0,
                    "smoothed_baseline_tss": 58.0,
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
                return_value={
                    "_build_athlete_progression_payload": _fake_progression_builder,
                    "_format_athlete_progression_weekly_baseline_point": lambda point: {
                        "week_start": str(point.get("period_start") or ""),
                        "baseline_tss": round(float(point.get("baseline_tss") or 0.0), 1),
                        "baseline_distance_km": round(float(point.get("baseline_distance_km") or 0.0), 2),
                    },
                },
            ),
        ):
            result = mcp_server.tool_get_fitness_form({"owner": "admin", "days": 14})

        current_week = next(row for row in result["weekly_baseline"] if row["week_start"] == "2026-03-02")
        self.assertEqual(current_week["baseline_tss"], 58.0)
        self.assertEqual(current_week["baseline_distance_km"], 9.8)

    def test_get_fitness_form_uses_backend_weekly_baseline_formatter(self):
        fake_daily_progression = {
            "points": [
                {
                    "period_start": "2026-03-03",
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
                    "recent_load_anchor_tss": 66.0,
                    "blended_baseline_tss_before_smoothing": 60.0,
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
                    "period_start": "2026-03-02",
                    "baseline_tss": 58.0,
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
                return_value={
                    "_build_athlete_progression_payload": _fake_progression_builder,
                    "_format_athlete_progression_weekly_baseline_point": lambda point: {
                        "week_start": "formatted-by-backend",
                        "baseline_tss": 999.0,
                        "deviation_reason": "formatter_override",
                    },
                },
            ),
        ):
            result = mcp_server.tool_get_fitness_form({"owner": "admin", "days": 14})

        self.assertEqual(
            result["weekly_baseline"],
            [{"week_start": "formatted-by-backend", "baseline_tss": 999.0, "deviation_reason": "formatter_override"}],
        )

    def test_get_fitness_form_weekly_baseline_matches_canonical_athlete_progression_output(self):
        daily_tss_values = ([10.0] * 21) + ([90.0] * 21)
        expected_weekly = self._build_canonical_progression_payload(daily_tss_values, aggregation="weekly")["points"]
        result = self._run_fitness_form_with_canonical_progression(daily_tss_values)

        actual_weekly = result["weekly_baseline"]
        self.assertEqual(
            [row["week_start"] for row in actual_weekly],
            [row["period_start"] for row in expected_weekly],
        )
        for actual, expected in zip(actual_weekly, expected_weekly):
            self.assertEqual(actual["week_start"], expected["period_start"])
            self.assertAlmostEqual(actual["baseline_tss"], round(float(expected["baseline_tss"]), 1), places=1)
            self.assertAlmostEqual(actual["baseline_distance_km"], round(float(expected["baseline_distance_km"]), 2), places=2)
            self.assertAlmostEqual(actual["lt_target_tss"], round(float(expected["lt_target_tss"]), 1), places=1)
            self.assertAlmostEqual(actual["capacity_baseline_tss"], round(float(expected["capacity_baseline_tss"]), 1), places=1)
            self.assertAlmostEqual(actual["recent_load_anchor_tss"], round(float(expected["recent_load_anchor_tss"]), 1), places=1)
            self.assertAlmostEqual(
                actual["blended_baseline_tss_before_smoothing"],
                round(float(expected["blended_baseline_tss_before_smoothing"]), 1),
                places=1,
            )
            self.assertAlmostEqual(actual["smoothed_baseline_tss"], round(float(expected["smoothed_baseline_tss"]), 1), places=1)
            self.assertIn("deviation_reason", actual)

    def test_get_fitness_form_weekly_baseline_uses_latest_modeled_point_in_week(self):
        daily_tss_values = ([30.0] * 7) + ([80.0] * 7) + ([25.0] * 7) + ([95.0] * 7)
        daily_payload = self._build_canonical_progression_payload(daily_tss_values, aggregation="daily")
        result = self._run_fitness_form_with_canonical_progression(daily_tss_values)

        expected_by_week: dict[str, dict[str, float]] = {}
        for point in daily_payload["points"]:
            day = pd.Timestamp(point["period_start"])
            week_start = (day - pd.Timedelta(days=int(day.weekday()))).date().isoformat()
            expected_by_week[week_start] = {
                "baseline_tss": float(point["baseline_tss"]) * 7.0,
                "lt_target_tss": float(point["lt_target_tss"]) * 7.0,
                "capacity_baseline_tss": float(point["capacity_baseline_tss"]) * 7.0,
                "smoothed_baseline_tss": float(point["smoothed_baseline_tss"]) * 7.0,
            }

        for row in result["weekly_baseline"]:
            week_expected = expected_by_week[row["week_start"]]
            self.assertAlmostEqual(row["baseline_tss"], round(week_expected["baseline_tss"], 1), delta=0.11)
            self.assertAlmostEqual(row["lt_target_tss"], round(week_expected["lt_target_tss"], 1), delta=0.11)
            self.assertAlmostEqual(row["capacity_baseline_tss"], round(week_expected["capacity_baseline_tss"], 1), delta=0.11)
            self.assertAlmostEqual(row["smoothed_baseline_tss"], round(week_expected["smoothed_baseline_tss"], 1), delta=0.11)

    def test_get_fitness_form_weekly_baseline_current_week_matches_dashboard_and_keeps_explanations(self):
        now_dt = datetime(2026, 2, 15, tzinfo=timezone.utc)
        daily_tss_values = ([45.0] * 35) + ([70.0] * 7)
        expected_weekly = self._build_canonical_progression_payload(
            daily_tss_values,
            aggregation="weekly",
            days=42,
            now_dt=now_dt,
        )["points"]
        result = self._run_fitness_form_with_canonical_progression(
            daily_tss_values,
            days=42,
            now_dt=now_dt,
        )

        self.assertTrue(expected_weekly)
        expected_current_week = expected_weekly[-1]
        actual_current_week = result["weekly_baseline"][-1]
        self.assertEqual(actual_current_week["week_start"], expected_current_week["period_start"])
        self.assertAlmostEqual(actual_current_week["baseline_tss"], round(float(expected_current_week["baseline_tss"]), 1), places=1)
        self.assertAlmostEqual(
            actual_current_week["blended_baseline_tss_before_smoothing"],
            round(float(expected_current_week["blended_baseline_tss_before_smoothing"]), 1),
            places=1,
        )
        self.assertIn("deviation_from_lt_tss", actual_current_week)
        self.assertIn("deviation_from_lt_pct", actual_current_week)
        self.assertIn("capacity_vs_lt_tss", actual_current_week)
        self.assertIn("recent_vs_capacity_tss", actual_current_week)
        self.assertIn("smoothing_adjustment_tss", actual_current_week)
        self.assertIn("deviation_reason", actual_current_week)

    def test_get_fitness_form_short_window_keeps_latest_weekly_baseline_from_long_history(self):
        daily_tss_values = ([50.0] * 70) + ([95.0] * 30)
        short_result = self._run_fitness_form_with_canonical_progression(daily_tss_values, days=14)
        long_result = self._run_fitness_form_with_canonical_progression(daily_tss_values, days=365)

        self.assertTrue(short_result["weekly_baseline"])
        self.assertTrue(long_result["weekly_baseline"])
        self.assertEqual(short_result["weekly_baseline"][-1]["week_start"], long_result["weekly_baseline"][-1]["week_start"])
        self.assertAlmostEqual(
            short_result["weekly_baseline"][-1]["baseline_tss"],
            long_result["weekly_baseline"][-1]["baseline_tss"],
            places=1,
        )
        self.assertAlmostEqual(
            short_result["weekly_baseline"][-1]["smoothed_baseline_tss"],
            long_result["weekly_baseline"][-1]["smoothed_baseline_tss"],
            places=1,
        )

    def test_compute_fitness_metrics_short_window_path_keeps_latest_baseline_driven_metrics(self):
        daily_tss_values = ([45.0] * 90) + ([85.0] * 20)
        short_form = self._run_fitness_form_with_canonical_progression(daily_tss_values, days=30)
        long_form = self._run_fitness_form_with_canonical_progression(daily_tss_values, days=365)

        self.assertTrue(short_form["daily"])
        self.assertTrue(long_form["daily"])
        self.assertEqual(short_form["daily"][-1]["day"], long_form["daily"][-1]["day"])
        self.assertAlmostEqual(short_form["daily"][-1]["baseline_tss"], long_form["daily"][-1]["baseline_tss"], places=1)
        self.assertAlmostEqual(short_form["daily"][-1]["overreach"], long_form["daily"][-1]["overreach"], places=1)
        self.assertAlmostEqual(short_form["daily"][-1]["injury_risk"], long_form["daily"][-1]["injury_risk"], places=1)

    def test_get_fitness_form_note_describes_accumulated_burden(self):
        result = self._run_fitness_form_with_canonical_progression([55.0] * 84)

        self.assertIn("accumulated burden", result["_note"])

    def test_get_fitness_form_stacked_overload_exceeds_spaced_overload_with_same_total_excess(self):
        stacked = ([45.0] * 84) + ([75.0] * 6) + ([45.0] * 6)
        spaced = ([45.0] * 84) + ([75.0, 45.0] * 6)

        stacked_result = self._run_fitness_form_with_canonical_progression(stacked, days=140)
        spaced_result = self._run_fitness_form_with_canonical_progression(spaced, days=140)

        stacked_overreach_peak = max(float(point["overreach"]) for point in stacked_result["daily"][-12:])
        spaced_overreach_peak = max(float(point["overreach"]) for point in spaced_result["daily"][-12:])
        stacked_injury_peak = max(float(point["injury_risk"]) for point in stacked_result["daily"][-12:])
        spaced_injury_peak = max(float(point["injury_risk"]) for point in spaced_result["daily"][-12:])

        self.assertGreater(stacked_overreach_peak, spaced_overreach_peak)
        self.assertGreater(stacked_injury_peak, spaced_injury_peak)

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

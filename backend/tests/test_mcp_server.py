import unittest

from backend.app import mcp_server


class MCPServerHelpersTest(unittest.TestCase):
    def test_module_imports_without_fastapi_dependency_path(self):
        self.assertEqual(mcp_server.SERVER_INFO["name"], "temperance-mcp")
        self.assertIn("recommend_training", mcp_server.TOOLS)
        self.assertIn("explain_recommendation", mcp_server.TOOLS)
        self.assertIn("get_activity_detail", mcp_server.TOOLS)

    def test_recommendation_status_prefers_recovery_when_readiness_is_low(self):
        status, rationale = mcp_server._recommendation_status(
            mcp_server.RecommendationContext(
                readiness=28,
                sleep_score=82,
                stress_avg=32,
                week_remaining=140,
                target_today=55,
                remaining_days=3,
            )
        )
        self.assertEqual(status, "recover")
        self.assertIn("recovery", rationale.lower())

    def test_recommendation_status_prefers_build_when_recovered_and_behind_load(self):
        status, rationale = mcp_server._recommendation_status(
            mcp_server.RecommendationContext(
                readiness=81,
                sleep_score=84,
                stress_avg=22,
                week_remaining=160,
                target_today=50,
                remaining_days=2,
            )
        )
        self.assertEqual(status, "build")
        self.assertIn("behind the weekly load target", rationale.lower())

    def test_recommendation_text_normalizes_aliases_and_is_more_specific(self):
        sport = mcp_server._normalize_activity_type("cycling")
        self.assertEqual(sport, "bike")
        suggestion = mcp_server._recommendation_text(sport, "easy")
        self.assertIn("aerobic endurance", suggestion.lower())
        self.assertIn("cap the effort", suggestion.lower())

    def test_recommendation_explanation_includes_compact_signal_summary(self):
        explanation = mcp_server._recommendation_explanation(
            mcp_server.RecommendationContext(
                readiness=74,
                sleep_score=77,
                stress_avg=19,
                week_remaining=90,
                target_today=30,
                remaining_days=3,
            ),
            "build",
        )
        self.assertIn("readiness=74", explanation)
        self.assertIn("sleep=77", explanation)
        self.assertIn("pace_needed≈30.0 TSS/day", explanation)

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


    def test_recommendation_signal_rows_surface_primary_build_driver(self):
        rows = mcp_server._recommendation_signal_rows(
            mcp_server.RecommendationContext(
                readiness=82,
                sleep_score=80,
                stress_avg=24,
                week_remaining=150,
                target_today=45,
                remaining_days=2,
            ),
            "build",
        )
        self.assertEqual(rows[0]["signal"], "training_readiness")
        weekly_load = next(row for row in rows if row["signal"] == "remaining_week_tss")
        self.assertEqual(weekly_load["status_impact"], "build")
        self.assertIn("behind target", weekly_load["why"].lower())

    def test_recommendation_decision_trace_keeps_signal_breakdown(self):
        trace = mcp_server._recommendation_decision_trace(
            mcp_server.RecommendationContext(
                readiness=30,
                sleep_score=78,
                stress_avg=18,
                week_remaining=70,
                target_today=35,
                remaining_days=2,
            ),
            "recover",
            "Training readiness is very low, so the safest call is recovery-first work.",
        )
        self.assertEqual(trace["status"], "recover")
        self.assertIn("compact_explanation", trace)
        readiness_row = next(row for row in trace["signals"] if row["signal"] == "training_readiness")
        self.assertEqual(readiness_row["status_impact"], "recover")
        self.assertIn("recovery-first", readiness_row["why"].lower())

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


if __name__ == "__main__":
    unittest.main()

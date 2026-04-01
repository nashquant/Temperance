from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from backend.app import mcp_server
from temperance import db as temperance_db


class BackendStub:
    SETTINGS_KEY_LTHR_CURVE = "lthr_curve"
    SETTINGS_KEY_LT_PACE_CURVE = "lt_pace_curve"
    SETTINGS_KEY_USER_TIMEZONE = "user_timezone"
    DEFAULT_LTHR = 170.0
    DEFAULT_THRESHOLD_PACE_SEC_PER_KM = 240.0

    @staticmethod
    def _normalize_plan_text(text: str) -> str:
        return " ".join(str(text or "").strip().split())

    @staticmethod
    def _planned_row_signature(day_utc: str, workout_text: str) -> str:
        return f"{day_utc}::{BackendStub._normalize_plan_text(workout_text).lower()}"

    @staticmethod
    def _expand_planned_segments(line: str, **_: object):
        normalized = BackendStub._normalize_plan_text(line)
        if "@" not in normalized:
            return [], ["Missing intensity"]
        duration = 45.0 if "45min" in normalized else 60.0
        return [{"kind": "run", "duration_min": duration, "pace_s_per_km": 290.0, "avg_hr_bpm": 150.0}], []

    @staticmethod
    def _load_curve_points(**_: object):
        return []

    @staticmethod
    def _curve_value_at(_points, fallback: float, _day) -> float:
        return float(fallback)

    @staticmethod
    def _load_specificity_profile(**_: object):
        return {"run": 1.0}

    @staticmethod
    def _has_explicit_lt_pace_curve(_db_path: Path) -> bool:
        return False

    @staticmethod
    def _compute_planned_rows_metrics_df(planned_rows: pd.DataFrame, **_: object) -> pd.DataFrame:
        out = planned_rows.copy()
        out["tss"] = [55.0 for _ in range(len(out))]
        out["rtss"] = [58.0 for _ in range(len(out))]
        out["distance_proxy_km"] = [9.3 for _ in range(len(out))]
        out["duration_s"] = [2700.0 for _ in range(len(out))]
        out["if_proxy"] = [0.88 for _ in range(len(out))]
        out["avg_hr_bpm"] = [150.0 for _ in range(len(out))]
        out["pace_proxy_sec_per_km"] = [290.0 for _ in range(len(out))]
        return out

    @staticmethod
    def _week_start_monday(value) -> pd.Timestamp:
        ts = pd.Timestamp(value).normalize()
        return ts - pd.Timedelta(days=int(ts.weekday()))

    @staticmethod
    def _build_week_outlook_payload(*, week_start: str | None = None, **_: object) -> dict[str, object]:
        ws = BackendStub._week_start_monday(week_start or "2026-03-30")
        we = ws + pd.Timedelta(days=6)
        return {
            "metric": "tss",
            "compare": "planned",
            "week_start": ws.date().isoformat(),
            "week_end": we.date().isoformat(),
            "goal": 350.0,
            "goal_progress_pct": 40,
            "week_total_current": 140.0,
            "week_total_compare": 260.0,
            "wtd_current": 140.0,
            "wtd_compare": 180.0,
            "remaining_to_go": 120.0,
            "projected_finish": 260.0,
            "estimated_fatigue_eow": 68.0,
            "rows": [{"day": (ws + pd.Timedelta(days=offset)).date().isoformat()} for offset in range(7)],
            "today_day": "2026-03-31",
        }

    @staticmethod
    def _build_planned_activities_payload(*, db_path: Path, owner: str, weeks: int = 4) -> dict[str, object]:
        rows_df = temperance_db.get_planned_activities_df(db_path)
        rows = []
        for _, row in rows_df.iterrows():
            rows.append(
                {
                    "day_utc": str(row["day_utc"]),
                    "line_no": int(row["line_no"]),
                    "workout_text": str(row["workout_text"]),
                    "manual_done": bool(int(row["manual_done"])),
                }
            )
        return {"owner": owner, "weeks": [{"weeks": weeks}], "rows": rows}

    @staticmethod
    def _generated_activity_context(**_: object) -> dict[str, object]:
        return {
            "activity_type": "running",
            "base_daily_goal_tss": 50.0,
            "week_balanced_daily_tss": 45.0,
            "week_gap_tss": 120.0,
            "days_remaining_in_week": 5,
            "training_readiness": 72.0,
            "sleep_score": 81.0,
            "stress_avg": 24.0,
            "recovery_alert": False,
            "easy_bias": False,
            "progression_green": True,
            "adjacent_hard_days": False,
            "week_behind": True,
        }

    @staticmethod
    def _generated_activity_candidates(**_: object) -> list[dict[str, object]]:
        return [
            {"activity_text": "Run 45min @4:50/km", "priority": 0, "bucket": "easy", "estimated_tss": 55.0},
            {"activity_text": "Run 60min @4:45/km", "priority": 1, "bucket": "steady", "estimated_tss": 70.0},
        ]

    @staticmethod
    def _generated_activity_fallbacks(activity_type: str | None = None, mode: str = "planned") -> list[str]:
        return ["Run 40min @4:55/km"]

    @staticmethod
    def _generated_activity_preferred_buckets(_day_utc: str, _context: dict | None = None) -> list[str]:
        return ["easy", "steady", "long"]

    @staticmethod
    def _generated_activity_day_goal_tss(**_: object) -> float:
        return 50.0

    @staticmethod
    def _generated_activity_candidate_score(*, item: dict[str, object], target_tss: float, **_: object) -> float:
        return abs(float(item.get("estimated_tss") or 0.0) - float(target_tss))

    @staticmethod
    def _generated_activity_shortlist(*, suggestions: list[dict[str, object]], target_tss: float, **_: object):
        scored = sorted(
            [(BackendStub._generated_activity_candidate_score(item=item, target_tss=target_tss), item) for item in suggestions],
            key=lambda pair: pair[0],
        )
        return scored[:3]

    @staticmethod
    def _filter_effective_planned_rows(*, planned_df: pd.DataFrame, **_: object) -> pd.DataFrame:
        return planned_df.copy()

    @staticmethod
    def _now_app_local() -> pd.Timestamp:
        return pd.Timestamp("2026-03-31")

    @staticmethod
    def _metrics_for_filters(**_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "activity_id": "run-1",
                    "start_time_utc": "2026-03-30T10:00:00Z",
                    "sport_type": "running",
                    "duration_s": 2700.0,
                    "distance_m": 9000.0,
                    "tss": 52.0,
                    "rtss": 55.0,
                    "if_proxy": 0.86,
                    "avg_hr": 149.0,
                    "distance_proxy_km": 9.0,
                    "training_load_garmin": 50.0,
                    "mechanical_load": 80.0,
                }
            ]
        )

    @staticmethod
    def _build_wellness_payload(**_: object) -> dict[str, object]:
        return {
            "points": [
                {
                    "period_start": "2026-03-30",
                    "training_readiness": 72.0,
                    "sleep_score": 81.0,
                    "stress_avg": 24.0,
                    "body_battery_end": 65.0,
                }
            ]
        }

    @staticmethod
    def activity_detail(**kwargs: object) -> dict[str, object]:
        return {"activity": {"activity_id": kwargs["activity_id"]}, "records": []}


class MCPServerTest(unittest.TestCase):
    def test_module_imports_and_registers_surface(self) -> None:
        self.assertEqual(mcp_server.SERVER_INFO["name"], "temperance-mcp")
        self.assertIn("draft_week_plan", mcp_server.TOOLS)
        self.assertIn("apply_plan_changes", mcp_server.TOOLS)
        self.assertIn("resource://temperance/lingo", mcp_server.RESOURCES)
        self.assertIn("plan_this_week", mcp_server.PROMPTS)

    def test_handle_initialize_and_unknown_method(self) -> None:
        initialize = mcp_server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(initialize["result"]["serverInfo"]["name"], "temperance-mcp")
        self.assertIn("resources", initialize["result"]["capabilities"])

        response = mcp_server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "bogus"})
        self.assertEqual(
            response,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "error": {"code": -32601, "message": "Method not found: bogus"},
            },
        )

    def test_resources_and_prompts_are_exposed(self) -> None:
        resources = mcp_server.handle_message({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
        self.assertTrue(any(item["name"] == "temperance_lingo" for item in resources["result"]["resources"]))

        read = mcp_server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/read",
                "params": {"uri": "resource://temperance/lingo"},
            }
        )
        self.assertIn("Temperance Lingo", read["result"]["contents"][0]["text"])

        prompts = mcp_server.handle_message({"jsonrpc": "2.0", "id": 5, "method": "prompts/list"})
        self.assertTrue(any(item["name"] == "daily_checkin" for item in prompts["result"]["prompts"]))

        prompt_get = mcp_server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "prompts/get",
                "params": {"name": "plan_this_week", "arguments": {"owner": "admin"}},
            }
        )
        self.assertIn("draft_week_plan", prompt_get["result"]["messages"][0]["content"][0]["text"])

    def test_validate_workout_text_on_temp_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "planner.db"
            original = mcp_server._resolve_db_path
            original_backend = mcp_server._backend_main
            try:
                mcp_server._resolve_db_path = lambda owner: db_path
                mcp_server._backend_main = lambda: BackendStub
                payload = mcp_server.tool_validate_workout_text(
                    {
                        "owner": "admin",
                        "day_utc": "2026-04-01",
                        "workout_text": "Run 45min @4:50/km",
                    }
                )
            finally:
                mcp_server._resolve_db_path = original
                mcp_server._backend_main = original_backend

            self.assertTrue(payload["is_valid"])
            self.assertEqual(payload["normalized_text"], "Run 45min @4:50/km")
            self.assertGreater(payload["estimated_metrics"]["tss"], 0.0)

    def test_preview_and_apply_plan_changes_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "planner.db"
            temperance_db.init_db(db_path)
            original = mcp_server._resolve_db_path
            original_backend = mcp_server._backend_main
            try:
                mcp_server._resolve_db_path = lambda owner: db_path
                mcp_server._backend_main = lambda: BackendStub

                preview = mcp_server.tool_preview_plan_changes(
                    {
                        "owner": "admin",
                        "changes": [
                            {
                                "type": "create_entry",
                                "day_utc": "2026-04-01",
                                "workout_text": "Run 45min @4:50/km",
                            }
                        ],
                    }
                )
                self.assertEqual(preview["accepted_count"], 1)
                self.assertEqual(preview["operations"][0]["line_no"], 1)
                self.assertGreater(preview["week_impact"][0]["delta"]["tss"], 0.0)

                apply_payload = mcp_server.tool_apply_plan_changes(
                    {
                        "owner": "admin",
                        "changes": [
                            {
                                "type": "create_entry",
                                "day_utc": "2026-04-01",
                                "workout_text": "Run 45min @4:50/km",
                            }
                        ],
                    }
                )
                self.assertTrue(apply_payload["applied"])
                self.assertEqual(apply_payload["accepted_count"], 1)

                stored = temperance_db.get_planned_activities_df(db_path, "2026-04-01", "2026-04-01")
                self.assertEqual(len(stored), 1)
                self.assertEqual(str(stored.iloc[0]["workout_text"]), "Run 45min @4:50/km")

                manual_done = mcp_server.tool_apply_plan_changes(
                    {
                        "owner": "admin",
                        "changes": [
                            {
                                "type": "set_manual_done",
                                "day_utc": "2026-04-01",
                                "line_no": 1,
                                "manual_done": True,
                            }
                        ],
                    }
                )
                self.assertEqual(manual_done["accepted_count"], 1)
                stored_after = temperance_db.get_planned_activities_df(db_path, "2026-04-01", "2026-04-01")
                self.assertEqual(int(stored_after.iloc[0]["manual_done"]), 1)
            finally:
                mcp_server._resolve_db_path = original
                mcp_server._backend_main = original_backend

    def test_draft_day_and_week_plan_return_temperance_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "planner.db"
            temperance_db.init_db(db_path)
            original = mcp_server._resolve_db_path
            original_backend = mcp_server._backend_main
            try:
                mcp_server._resolve_db_path = lambda owner: db_path
                mcp_server._backend_main = lambda: BackendStub

                day_plan = mcp_server.tool_draft_day_plan(
                    {
                        "owner": "admin",
                        "day_utc": "2026-04-01",
                        "activity_type": "running",
                    }
                )
                self.assertTrue(day_plan["proposed_entries"])
                self.assertIn("workout_text", day_plan["proposed_entries"][0])
                self.assertIn("confidence", day_plan["source_signals"])

                week_plan = mcp_server.tool_draft_week_plan(
                    {
                        "owner": "admin",
                        "week_start": "2026-03-30",
                        "activity_type": "running",
                    }
                )
                self.assertIn("proposed_entries", week_plan)
                self.assertIn("summary", week_plan)
            finally:
                mcp_server._resolve_db_path = original
                mcp_server._backend_main = original_backend

    def test_get_today_status_uses_stubbed_backend_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "planner.db"
            temperance_db.init_db(db_path)
            temperance_db.save_setting(db_path, BackendStub.SETTINGS_KEY_USER_TIMEZONE, "America/Sao_Paulo")
            original = mcp_server._resolve_db_path
            original_backend = mcp_server._backend_main
            try:
                mcp_server._resolve_db_path = lambda owner: db_path
                mcp_server._backend_main = lambda: BackendStub
                payload = mcp_server.tool_get_today_status({"owner": "admin"})
            finally:
                mcp_server._resolve_db_path = original
                mcp_server._backend_main = original_backend

            self.assertEqual(payload["timezone"], "America/Sao_Paulo")
            self.assertEqual(payload["latest_activity"]["activity_id"], "run-1")
            self.assertEqual(payload["latest_wellness"]["training_readiness"], 72.0)


if __name__ == "__main__":
    unittest.main()

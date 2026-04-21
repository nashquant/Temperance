import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.app import main as backend_main
from temperance.db import init_db


class CoachSnapshotCoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "coach-snapshot.sqlite"
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_settings_update_and_view_roundtrip_race_context(self) -> None:
        payload = {
            "race_context": {
                "next_race_date": "2026-07-12",
                "next_race_type": "marathon",
                "next_phase": "Specificity",
            }
        }
        result = backend_main._settings_update_core(self.db_path, payload)
        self.assertIn("race_context", result["updated"])

        view = backend_main._settings_view_core(self.db_path)
        self.assertEqual(view["race_context"], payload["race_context"])

    def test_settings_update_rejects_invalid_next_phase(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            backend_main._settings_update_core(
                self.db_path,
                {
                    "race_context": {
                        "next_race_date": "2026-07-12",
                        "next_race_type": "marathon",
                        "next_phase": "Unknown",
                    }
                },
            )
        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("race_context.next_phase", str(exc.exception.detail))

    def test_coach_snapshot_uses_runtime_fallback_when_race_context_missing(self) -> None:
        runtime_file = Path(self.temp_dir.name) / "training-runtime-active.md"
        runtime_file.write_text(
            "\n".join(
                [
                    "- Generic phase = `Base / Capacity Build`",
                    "- Goal event = July 12, 2026 marathon",
                ]
            ),
            encoding="utf-8",
        )
        with patch.object(backend_main, "RUNTIME_ACTIVE_GUIDELINE_PATH", runtime_file):
            snapshot = backend_main._coach_snapshot_view_core(self.db_path, owner="test")

        self.assertEqual(snapshot["current_phase"], "Base / Capacity Build")
        self.assertEqual(snapshot["next_race_date"], "2026-07-12")
        self.assertEqual(snapshot["next_race_type"], "marathon")
        self.assertEqual(snapshot["next_phase"], "Specificity")

    def test_mcp_window_bounds_has_safe_default(self) -> None:
        start, end = backend_main._mcp_window_bounds(7)
        self.assertLessEqual(start, end)
        self.assertEqual((date.fromisoformat(end) - date.fromisoformat(start)).days, 6)


if __name__ == "__main__":
    unittest.main()

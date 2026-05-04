import json
import subprocess
import sys
import unittest


class MCPStartupTest(unittest.TestCase):
    def test_mcp_server_import_keeps_heavy_modules_lazy(self) -> None:
        script = """
import json
import os
import sys

import backend.app.mcp_server

print(json.dumps({
    "pydantic_plugins_disabled": os.environ.get("PYDANTIC_DISABLE_PLUGINS"),
    "pandas_loaded": "pandas" in sys.modules,
    "logfire_loaded": "logfire" in sys.modules,
}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["pydantic_plugins_disabled"], "1")
        self.assertFalse(payload["pandas_loaded"])
        self.assertFalse(payload["logfire_loaded"])


if __name__ == "__main__":
    unittest.main()

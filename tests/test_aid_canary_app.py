import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "aid_canary_app.py"


class CanaryAppTests(unittest.TestCase):
    def test_health_payload(self):
        sys.path.insert(0, str(ROOT / "src"))
        import aid_canary_app

        payload = aid_canary_app.health()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["managed_delivery"], "enabled")
        self.assertIn("AI Delivery", payload["app"])

    def test_smoke_cli_outputs_ok_json(self):
        result = subprocess.run([sys.executable, str(SRC), "--smoke"], text=True, capture_output=True, check=True)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["managed_delivery"], "enabled")


if __name__ == "__main__":
    unittest.main()

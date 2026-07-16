import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

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

    def test_token_is_environment_only_and_cli_rejects_token_option(self):
        sys.path.insert(0, str(ROOT / "src"))
        import aid_canary_app

        with mock.patch.dict(os.environ, {"DELIVERY_OPS_TOKEN": " environment-token "}, clear=False):
            self.assertEqual(aid_canary_app.resolve_token(), "environment-token")
        with self.assertRaises(SystemExit):
            aid_canary_app.parse_args(["--token", "command-line-secret"])

        for relative_path in (
            "README.md",
            "docs/operations-runbook.md",
            "scripts/smoke.sh",
            ".github/workflows/ai-delivery-ci.yml",
        ):
            with self.subTest(path=relative_path):
                content = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("--token", content)

        smoke_script = (ROOT / "scripts" / "smoke.sh").read_text(encoding="utf-8")
        self.assertNotIn('python3 - "${PORT}" "${TOKEN}"', smoke_script)
        self.assertGreaterEqual(smoke_script.count('DELIVERY_OPS_TOKEN="${TOKEN}"'), 2)

    def test_cli_startup_test_closes_subprocess_pipes(self):
        environment = dict(os.environ)
        environment["PYTHONTRACEMALLOC"] = "25"
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "always::ResourceWarning",
                "-m",
                "unittest",
                "tests.test_aid_canary_app.CanaryAppTests.test_cli_starts_without_token_and_serves_read_endpoints",
                "-v",
            ],
            cwd=str(ROOT),
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("ResourceWarning", result.stdout + result.stderr)

    def test_cli_starts_without_token_and_serves_read_endpoints(self):
        with socket.socket() as candidate:
            candidate.bind(("127.0.0.1", 0))
            port = candidate.getsockname()[1]

        process = subprocess.Popen(
            [
                sys.executable,
                str(SRC),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={key: value for key, value in os.environ.items() if key != "DELIVERY_OPS_TOKEN"},
        )
        try:
            deadline = time.time() + 8
            last_error: Exception | None = None
            while time.time() < deadline:
                if process.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
                        health = json.loads(response.read().decode("utf-8"))
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/releases", timeout=1) as response:
                        releases = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(health["status"], "ok")
                    self.assertEqual(releases["releases"], [])
                    return
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.2)
            stdout, stderr = process.communicate(timeout=2)
            self.fail(f"server did not stay up without a token: {last_error}; stdout={stdout!r}; stderr={stderr!r}")
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()

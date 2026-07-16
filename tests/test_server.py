from __future__ import annotations

import io
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from delivery_ops import server  # type: ignore[import-not-found]


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.web_dir = Path(self.temp_dir.name) / "web"
        self.web_dir.mkdir(parents=True, exist_ok=True)
        (self.web_dir / "index.html").write_text("<!doctype html><title>Delivery Operations Console</title>", encoding="utf-8")
        (self.web_dir / "app.js").write_text("console.log('console');", encoding="utf-8")
        (self.web_dir / "styles.css").write_text("body{background:#0b1020;}", encoding="utf-8")
        self.token = "test-token"
        self.httpd = server.create_server(
            host="127.0.0.1",
            port=0,
            token=self.token,
            data_dir=self.data_dir,
            web_root=self.web_dir,
        )
        self.httpd.read_timeout = 0.25
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self.temp_dir.cleanup()

    def test_server_factory_rejects_non_loopback_bindings(self) -> None:
        exposed_server = None
        try:
            with self.assertRaisesRegex(ValueError, "127.0.0.1"):
                exposed_server = server.create_server(
                    host="0.0.0.0",
                    port=0,
                    token=self.token,
                    data_dir=self.data_dir,
                    web_root=self.web_dir,
                )
        finally:
            if exposed_server is not None:
                exposed_server.server_close()

    def test_health_and_static_assets_include_security_headers(self) -> None:
        health = self.request("GET", "/api/health")
        self.assertEqual(health["status"], 200)
        self.assertEqual(health["body"]["status"], "ok")
        self.assertEqual(health["headers"]["Content-Security-Policy"], "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.assertEqual(health["headers"]["X-Content-Type-Options"], "nosniff")
        self.assertEqual(health["headers"]["Referrer-Policy"], "no-referrer")
        self.assertEqual(health["headers"]["Cache-Control"], "no-store")

        index = self.request("GET", "/")
        self.assertEqual(index["status"], 200)
        self.assertIn("Delivery Operations Console", index["text"])

        script = self.request("GET", "/app.js")
        self.assertEqual(script["status"], 200)
        self.assertEqual(script["headers"]["Content-Type"], "application/javascript; charset=utf-8")

        styles = self.request("GET", "/styles.css")
        self.assertEqual(styles["status"], 200)
        self.assertEqual(styles["headers"]["Content-Type"], "text/css; charset=utf-8")

        favicon = self.request("GET", "/favicon.ico")
        self.assertEqual(favicon["status"], 204)
        self.assertEqual(favicon["headers"]["X-Content-Type-Options"], "nosniff")

        traversal = self.request("GET", "/../README.md")
        self.assertEqual(traversal["status"], 404)

    def test_read_endpoints_work_without_runtime_token_but_mutations_return_401(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

        self.httpd = server.create_server(
            host="127.0.0.1",
            port=0,
            token=None,
            data_dir=self.data_dir,
            web_root=self.web_dir,
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"

        health = self.request("GET", "/api/health")
        releases = self.request("GET", "/api/releases")
        unauthorized = self.request(
            "POST",
            "/api/releases",
            body={"title": "Canary", "version": "1.0.0"},
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(health["status"], 200)
        self.assertEqual(releases["status"], 200)
        self.assertEqual(releases["body"]["releases"], [])
        self.assertEqual(unauthorized["status"], 401)

    def test_mutation_endpoints_require_bearer_token_using_compare_digest(self) -> None:
        unauthorized = self.request(
            "POST",
            "/api/releases",
            body={"title": "Canary", "version": "1.0.0"},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(unauthorized["status"], 401)

        with mock.patch("delivery_ops.server.hmac.compare_digest", wraps=server.hmac.compare_digest) as compare_mock:
            authorized = self.request(
                "POST",
                "/api/releases",
                body={"title": "Canary", "version": "1.0.0"},
                headers=self.auth_headers(),
            )

        self.assertEqual(authorized["status"], 201)
        self.assertGreaterEqual(compare_mock.call_count, 1)

    def test_release_gate_risk_and_audit_end_to_end(self) -> None:
        created = self.request(
            "POST",
            "/api/releases",
            body={"title": "Operator console rollout", "version": "2026.07.16"},
            headers=self.auth_headers(),
        )
        self.assertEqual(created["status"], 201)
        release_id = created["body"]["id"]

        listed = self.request("GET", "/api/releases")
        self.assertEqual(listed["status"], 200)
        self.assertEqual(len(listed["body"]["releases"]), 1)

        validating = self.request(
            "PATCH",
            f"/api/releases/{release_id}",
            body={"status": "validating"},
            headers=self.auth_headers(),
        )
        self.assertEqual(validating["status"], 200)

        gate = self.request(
            "POST",
            f"/api/releases/{release_id}/gates",
            body={"name": "Build", "required": True},
            headers=self.auth_headers(),
        )
        self.assertEqual(gate["status"], 201)
        gate_id = gate["body"]["id"]

        gate_update = self.request(
            "PATCH",
            f"/api/releases/{release_id}/gates/{gate_id}",
            body={"status": "passed"},
            headers=self.auth_headers(),
        )
        self.assertEqual(gate_update["status"], 200)

        risk = self.request(
            "POST",
            f"/api/releases/{release_id}/risks",
            body={
                "description": "Rollback checklist pending sign-off",
                "severity": "high",
                "blocking": True,
            },
            headers=self.auth_headers(),
        )
        self.assertEqual(risk["status"], 201)
        risk_id = risk["body"]["id"]

        risk_update = self.request(
            "PATCH",
            f"/api/releases/{release_id}/risks/{risk_id}",
            body={"status": "closed"},
            headers=self.auth_headers(),
        )
        self.assertEqual(risk_update["status"], 200)

        ready = self.request(
            "PATCH",
            f"/api/releases/{release_id}",
            body={"status": "ready"},
            headers=self.auth_headers(),
        )
        self.assertEqual(ready["status"], 200)

        release_audit = self.request("GET", f"/api/releases/{release_id}/audit")
        self.assertEqual(release_audit["status"], 200)
        self.assertEqual(len(release_audit["body"]["events"]), 7)
        self.assertEqual(release_audit["body"]["events"][0]["action"], "release.updated")

        audit = self.request("GET", "/api/audit")
        self.assertEqual(audit["status"], 200)
        self.assertEqual(len(audit["body"]["events"]), 7)
        self.assertEqual(audit["body"]["events"][0]["action"], "release.updated")

    def test_validation_and_not_found_errors_are_json(self) -> None:
        wrong_type = self.request(
            "POST",
            "/api/releases",
            data=b"{}",
            headers={"Authorization": "Bearer test-token", "Content-Type": "text/plain"},
        )
        self.assertEqual(wrong_type["status"], 415)
        self.assertEqual(wrong_type["body"]["error"]["code"], "unsupported_media_type")

        unknown_fields = self.request(
            "POST",
            "/api/releases",
            body={"title": "Canary", "version": "1.0.0", "extra": True},
            headers=self.auth_headers(),
        )
        self.assertEqual(unknown_fields["status"], 400)

        missing = self.request("GET", "/api/releases/00000000-0000-0000-0000-000000000000")
        self.assertEqual(missing["status"], 404)

        created = self.request(
            "POST",
            "/api/releases",
            body={"title": "Canary", "version": "1.0.0"},
            headers=self.auth_headers(),
        )
        conflict = self.request(
            "PATCH",
            f"/api/releases/{created['body']['id']}",
            body={"status": "ready"},
            headers=self.auth_headers(),
        )
        self.assertEqual(conflict["status"], 409)
        self.assertEqual(conflict["body"]["current"]["status"], "planned")
        self.assertIn("not allowed", conflict["body"]["error"]["message"])

        method = self.request("DELETE", "/api/releases")
        self.assertEqual(method["status"], 405)
        self.assertEqual(method["headers"]["Allow"], "GET, POST")

    def test_put_options_and_head_return_405_with_allow_and_security_headers(self) -> None:
        put_response = self.request("PUT", "/api/releases")
        options_response = self.request("OPTIONS", "/api/releases")
        head_response = self.request("HEAD", "/api/releases")

        self.assertEqual(put_response["status"], 405)
        self.assertEqual(put_response["headers"]["Allow"], "GET, POST")
        self.assertEqual(put_response["headers"]["X-Content-Type-Options"], "nosniff")

        self.assertEqual(options_response["status"], 405)
        self.assertEqual(options_response["headers"]["Allow"], "GET, POST")

        self.assertEqual(head_response["status"], 405)
        self.assertEqual(head_response["headers"]["Allow"], "GET, POST")

    def test_trace_connect_unknown_method_and_parser_errors_use_security_headers(self) -> None:
        for method in ("TRACE", "CONNECT"):
            with self.subTest(method=method):
                response = self.request(method, "/api/releases")
                self.assertEqual(response["status"], 405)
                self.assertEqual(response["headers"]["Allow"], "GET, POST")
                self.assert_security_headers(response["headers"], api=True)

        unknown_method = self.raw_request(
            (
                "BREW /api/releases HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.httpd.server_port}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
        ).decode("utf-8", errors="replace")
        self.assertIn("501", unknown_method)
        self.assertIn("X-Content-Type-Options: nosniff", unknown_method)
        self.assertIn("Referrer-Policy: no-referrer", unknown_method)

        parser_refusal = self.raw_request(
            (
                "GET /api/health HTTP/9.9\r\n"
                f"Host: 127.0.0.1:{self.httpd.server_port}\r\n\r\n"
            ).encode("ascii")
        ).decode("utf-8", errors="replace")
        self.assertIn("505", parser_refusal)
        self.assertIn("Content-Security-Policy:", parser_refusal)
        self.assertIn("X-Content-Type-Options: nosniff", parser_refusal)

    def test_incomplete_body_and_read_timeout_return_400_without_mutation(self) -> None:
        body = json.dumps({"title": "Canary", "version": "1.0.0"}).encode("utf-8")
        incomplete = self.raw_request(
            (
                "POST /api/releases HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.httpd.server_port}\r\n"
                "Authorization: Bearer test-token\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body) + 5}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            + body
        ).decode("utf-8", errors="replace")
        self.assertIn("400 Bad Request", incomplete)
        self.assertIn("incomplete_body", incomplete)
        self.assertEqual(self.request("GET", "/api/releases")["body"]["releases"], [])

        with socket.create_connection(("127.0.0.1", self.httpd.server_port), timeout=2) as sock:
            sock.settimeout(2)
            sock.sendall(
                (
                    "POST /api/releases HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{self.httpd.server_port}\r\n"
                    "Authorization: Bearer test-token\r\n"
                    "Content-Type: application/json\r\n"
                    "Content-Length: 50\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
            )
            started = time.monotonic()
            timed_out_body = self.receive_all(sock).decode("utf-8", errors="replace")
            elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.5)
        self.assertIn("400 Bad Request", timed_out_body)
        self.assertIn("incomplete_body", timed_out_body)
        self.assertEqual(self.request("GET", "/api/releases")["body"]["releases"], [])

    def test_authentication_precedes_body_parsing_and_wrong_token_is_refused(self) -> None:
        response = self.request(
            "POST",
            "/api/releases",
            data=b"not-json",
            headers={"Authorization": "Bearer wrong-token", "Content-Type": "text/plain"},
        )
        self.assertEqual(response["status"], 401)
        self.assert_security_headers(response["headers"], api=True)

        raw = self.raw_request(
            (
                "POST /api/releases HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.httpd.server_port}\r\n"
                "Authorization: Bearer wrong-token\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {server.MAX_BODY_BYTES + 1}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
        ).decode("utf-8", errors="replace")
        self.assertIn("401 Unauthorized", raw)
        self.assertNotIn("413 Request Entity Too Large", raw)

    def test_invalid_entity_ids_return_404_and_all_refusals_have_security_headers(self) -> None:
        for method, path, body, headers in (
            ("GET", "/api/releases/not-a-uuid", None, None),
            ("GET", "/api/releases/not-a-uuid/audit", None, None),
            ("PATCH", "/api/releases/not-a-uuid", {"status": "validating"}, self.auth_headers()),
            ("PATCH", "/api/releases/00000000-0000-0000-0000-000000000000/gates/not-a-uuid", {"status": "passed"}, self.auth_headers()),
        ):
            with self.subTest(method=method, path=path):
                response = self.request(method, path, body=body, headers=headers)
                self.assertEqual(response["status"], 404)
                self.assert_security_headers(response["headers"], api=True)

        created = self.request(
            "POST",
            "/api/releases",
            body={"title": "Canary", "version": "1.0.0"},
            headers=self.auth_headers(),
        )
        conflict = self.request(
            "PATCH",
            f"/api/releases/{created['body']['id']}",
            body={"status": "ready"},
            headers=self.auth_headers(),
        )
        refusals = (
            self.request("POST", "/api/releases", data=b"{", headers=self.auth_headers()),
            self.request("POST", "/api/releases", body={"title": "Canary", "version": "1.0.0"}, headers={"Authorization": "Bearer wrong-token", "Content-Type": "application/json"}),
            self.request("GET", "/api/releases/00000000-0000-0000-0000-000000000000"),
            self.request("DELETE", "/api/releases"),
            conflict,
            self.request("POST", "/api/releases", data=b"{}", headers={"Authorization": "Bearer test-token", "Content-Type": "text/plain"}),
        )
        self.assertEqual([item["status"] for item in refusals], [400, 401, 404, 405, 409, 415])
        for refusal in refusals:
            self.assert_security_headers(refusal["headers"], api=True)

    def test_create_ignores_client_ids_and_assigns_new_entity_ids(self) -> None:
        supplied_id = "11111111-1111-4111-8111-111111111111"
        release = self.request(
            "POST",
            "/api/releases",
            body={"id": supplied_id, "title": "Canary", "version": "1.0.0"},
            headers=self.auth_headers(),
        )
        release_id = release["body"]["id"]
        gate = self.request(
            "POST",
            f"/api/releases/{release_id}/gates",
            body={"id": supplied_id, "name": "Build", "required": True},
            headers=self.auth_headers(),
        )
        risk = self.request(
            "POST",
            f"/api/releases/{release_id}/risks",
            body={"id": supplied_id, "description": "Rollback readiness", "severity": "high", "blocking": True},
            headers=self.auth_headers(),
        )

        self.assertEqual((release["status"], gate["status"], risk["status"]), (201, 201, 201))
        self.assertNotEqual(release_id, supplied_id)
        self.assertNotEqual(gate["body"]["id"], supplied_id)
        self.assertNotEqual(risk["body"]["id"], supplied_id)
        self.assertEqual(gate["body"]["status"], "pending")
        self.assertEqual(risk["body"]["status"], "open")

    def test_logs_only_method_normalized_path_and_status(self) -> None:
        captured = io.StringIO()
        with mock.patch("delivery_ops.server.sys.stderr", captured):
            response = self.request(
                "POST",
                "/api/releases?operator-secret=query-value",
                data=b"private-body",
                headers={"Authorization": "Bearer header-secret", "Content-Type": "text/plain"},
            )

        self.assertEqual(response["status"], 401)
        logs = captured.getvalue()
        self.assertNotIn("operator-secret", logs)
        self.assertNotIn("query-value", logs)
        self.assertNotIn("header-secret", logs)
        self.assertNotIn("private-body", logs)
        self.assertEqual(json.loads(logs), {"method": "POST", "path": "/api/releases", "status": 401})

    def test_request_body_limit_and_invalid_content_length(self) -> None:
        with socket.create_connection(("127.0.0.1", self.httpd.server_port), timeout=5) as sock:
            payload = (
                "POST /api/releases HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.httpd.server_port}\r\n"
                "Authorization: Bearer test-token\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {server.MAX_BODY_BYTES + 1}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode()
            sock.sendall(payload)
            oversized = sock.recv(4096).decode("utf-8")

        self.assertIn("413 Request Entity Too Large", oversized)
        self.assertIn("Content-Security-Policy:", oversized)
        self.assertIn("X-Content-Type-Options: nosniff", oversized)
        self.assertIn("Referrer-Policy: no-referrer", oversized)
        self.assertIn("Cache-Control: no-store", oversized)

        with socket.create_connection(("127.0.0.1", self.httpd.server_port), timeout=5) as sock:
            payload = (
                "POST /api/releases HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.httpd.server_port}\r\n"
                "Authorization: Bearer test-token\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: nope\r\n"
                "Connection: close\r\n"
                "\r\n"
                "{}"
            ).encode()
            sock.sendall(payload)
            raw = sock.recv(4096).decode("utf-8")

        self.assertIn("400 Bad Request", raw)

    def test_request_body_reader_rechecks_stream_limit(self) -> None:
        class FakeStream:
            def __init__(self, payload: bytes) -> None:
                self.payload = payload
                self.offset = 0

            def read(self, requested: int) -> bytes:
                chunk = self.payload[self.offset : self.offset + min(requested + 1, len(self.payload) - self.offset)]
                self.offset += len(chunk)
                return chunk

        status, body = server.read_request_body(FakeStream(b"x" * (server.MAX_BODY_BYTES + 1)), server.MAX_BODY_BYTES)
        self.assertEqual(status, "too_large")
        self.assertEqual(body, b"")

        status, body = server.read_request_body(FakeStream(b"{}"), 5)
        self.assertEqual(status, "incomplete")
        self.assertEqual(body, b"{}")

    def auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        payload = data
        request_headers = dict(headers or {})
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(f"{self.base_url}{path}", data=payload, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                raw = response.read()
                return self._response_dict(response.status, dict(response.headers.items()), raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            return self._response_dict(exc.code, dict(exc.headers.items()), raw)

    def _response_dict(self, status: int, headers: dict[str, str], raw: bytes) -> dict[str, object]:
        text = raw.decode("utf-8")
        parsed: object
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        return {
            "status": status,
            "headers": headers,
            "text": text,
            "body": parsed,
        }

    def raw_request(self, payload: bytes) -> bytes:
        with socket.create_connection(("127.0.0.1", self.httpd.server_port), timeout=3) as sock:
            sock.settimeout(3)
            sock.sendall(payload)
            sock.shutdown(socket.SHUT_WR)
            return self.receive_all(sock)

    def receive_all(self, sock: socket.socket) -> bytes:
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(65_536)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)

    def assert_security_headers(self, headers: dict[str, str], *, api: bool) -> None:
        self.assertEqual(
            headers["Content-Security-Policy"],
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        if api:
            self.assertEqual(headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()

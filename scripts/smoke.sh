#!/usr/bin/env bash
set -euo pipefail

mkdir -p ./.ai-delivery
RUN_DIR="$(mktemp -d ./.ai-delivery/smoke-run-XXXXXX)"
PORT="$(python3 - <<'PY'
import socket
with socket.socket() as candidate:
    candidate.bind(("127.0.0.1", 0))
    print(candidate.getsockname()[1])
PY
)"
TOKEN="smoke-local-token"
SERVER_PID=""

cleanup() {
  if [ -n "${SERVER_PID}" ] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  rm -rf "${RUN_DIR}"
}
trap cleanup EXIT INT TERM

wait_for_server() {
  python3 - "${PORT}" <<'PY'
from __future__ import annotations

import json
import sys
import time
import urllib.request

port = int(sys.argv[1])
deadline = time.time() + 10
last_error: Exception | None = None

while time.time() < deadline:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") == "ok":
                raise SystemExit(0)
    except Exception as exc:  # pragma: no cover - smoke path
        last_error = exc
        time.sleep(0.2)

raise SystemExit(f"server did not become ready: {last_error}")
PY
}

start_server() {
  DELIVERY_OPS_TOKEN="${TOKEN}" PYTHONDONTWRITEBYTECODE=1 python3 src/aid_canary_app.py \
    --host 127.0.0.1 \
    --port "${PORT}" \
    --data-dir "${RUN_DIR}/data" \
    >"${RUN_DIR}/server.log" 2>&1 &
  SERVER_PID=$!
  wait_for_server
}

stop_server() {
  if [ -n "${SERVER_PID}" ] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  SERVER_PID=""
}

start_server

DELIVERY_OPS_TOKEN="${TOKEN}" python3 - "${PORT}" <<'PY'
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

port = int(sys.argv[1])
token = os.environ["DELIVERY_OPS_TOKEN"]
base_url = f"http://127.0.0.1:{port}"


def request(path: str, *, method: str = "GET", body: dict[str, object] | None = None, auth: bool = False) -> tuple[int, dict[str, str], object]:
    headers: dict[str, str] = {}
    data: bytes | None = None
    if auth:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw and response.headers.get("Content-Type", "").startswith("application/json") else raw
            return response.status, dict(response.headers.items()), parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        parsed = json.loads(raw) if raw and exc.headers.get("Content-Type", "").startswith("application/json") else raw
        return exc.code, dict(exc.headers.items()), parsed


status, headers, payload = request("/api/health")
assert status == 200, status
assert payload["status"] == "ok"
assert headers["Content-Security-Policy"].startswith("default-src 'self'")
assert headers["X-Content-Type-Options"] == "nosniff"
assert headers["Referrer-Policy"] == "no-referrer"
assert headers["Cache-Control"] == "no-store"

status, _, release = request(
    "/api/releases",
    method="POST",
    body={"title": "Checkout release", "version": "2026.07.16"},
    auth=True,
)
assert status == 201, status
release_id = release["id"]

status, _, release = request(
    f"/api/releases/{release_id}",
    method="PATCH",
    body={"title": "Checkout release", "version": "2026.07.16", "status": "validating"},
    auth=True,
)
assert status == 200, status

status, _, gate = request(
    f"/api/releases/{release_id}/gates",
    method="POST",
    body={"name": "Build", "required": True},
    auth=True,
)
assert status == 201, status
gate_id = gate["id"]

status, _, gate = request(
    f"/api/releases/{release_id}/gates/{gate_id}",
    method="PATCH",
    body={"status": "passed", "required": True},
    auth=True,
)
assert status == 200, status

status, _, risk = request(
    f"/api/releases/{release_id}/risks",
    method="POST",
    body={"description": "Rollback note review", "severity": "high", "blocking": True},
    auth=True,
)
assert status == 201, status
risk_id = risk["id"]

status, _, risk = request(
    f"/api/releases/{release_id}/risks/{risk_id}",
    method="PATCH",
    body={"status": "accepted", "severity": "high", "blocking": True, "acceptance_reason": "Operator approved monitored launch"},
    auth=True,
)
assert status == 200, status

status, _, release = request(
    f"/api/releases/{release_id}",
    method="PATCH",
    body={"title": "Checkout release", "version": "2026.07.16", "status": "ready"},
    auth=True,
)
assert status == 200, status

status, _, audit = request(f"/api/releases/{release_id}/audit")
assert status == 200, status
assert len(audit["events"]) == 7, len(audit["events"])

status, headers, _ = request("/")
assert status == 200, status
assert headers["Content-Security-Policy"].startswith("default-src 'self'")
assert headers["X-Content-Type-Options"] == "nosniff"
assert headers["Referrer-Policy"] == "no-referrer"

status, _, _ = request("/app.js")
assert status == 200, status
status, _, _ = request("/styles.css")
assert status == 200, status
PY

stop_server
start_server

python3 - "${PORT}" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.request

port = int(sys.argv[1])
base_url = f"http://127.0.0.1:{port}"

with urllib.request.urlopen(f"{base_url}/api/releases", timeout=5) as response:
    releases = json.loads(response.read().decode("utf-8"))["releases"]
    assert len(releases) == 1, len(releases)
    assert releases[0]["status"] == "ready", releases[0]["status"]

with urllib.request.urlopen(f"{base_url}/api/audit", timeout=5) as response:
    events = json.loads(response.read().decode("utf-8"))["events"]
    assert len(events) == 7, len(events)

with urllib.request.urlopen(f"{base_url}/", timeout=5) as response:
    page = response.read().decode("utf-8")
    for marker in ("Delivery Operations Console", "Connected", "Token", "Releases", "Create release", "Delivery gates", "Risks", "Audit history"):
        assert marker in page, marker
PY

echo "smoke: ok"

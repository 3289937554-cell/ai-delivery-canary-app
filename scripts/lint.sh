#!/usr/bin/env bash
set -euo pipefail

if [ -x .venv/bin/python3 ]; then
  export PATH="$(pwd)/.venv/bin:${PATH}"
fi

python3 -m ruff check src tests scripts/*.py

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import os
import sys

root = Path(".")
required = [
    Path("src/delivery_ops/__init__.py"),
    Path("src/delivery_ops/domain.py"),
    Path("src/delivery_ops/store.py"),
    Path("src/delivery_ops/server.py"),
    Path("src/aid_canary_app.py"),
    Path("web/index.html"),
    Path("web/app.js"),
    Path("web/styles.css"),
    Path("tests/test_domain.py"),
    Path("tests/test_store.py"),
    Path("tests/test_server.py"),
    Path("docs/operations-runbook.md"),
    Path("scripts/lint.sh"),
    Path("scripts/typecheck.sh"),
    Path("scripts/build.sh"),
    Path("scripts/smoke.sh"),
    Path("scripts/validate_model_execution.py"),
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(f"Missing required files: {missing}")

for root_name in ("src", "tests"):
    for path in sorted(Path(root_name).rglob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

for path in [Path("scripts/lint.sh"), Path("scripts/typecheck.sh"), Path("scripts/build.sh"), Path("scripts/smoke.sh")]:
    mode = path.stat().st_mode
    if not (mode & os.X_OK):
        raise SystemExit(f"{path} must be executable")

forbidden_terms = [
    "example",
    "placeholder",
    "dummy",
    "fake",
    "lorem ipsum",
    "todo",
    "t-d-o",
    "待填写",
    "示例",
    "样例",
    "占位",
]
for path in [
    Path("web/index.html"),
    Path("web/app.js"),
    Path("web/styles.css"),
    Path("src/delivery_ops/server.py"),
    Path("docs/operations-runbook.md"),
]:
    text = path.read_text(encoding="utf-8").lower()
    for term in forbidden_terms:
        if term in text:
            raise SystemExit(f"Forbidden term {term!r} found in {path}")

index_text = Path("web/index.html").read_text(encoding="utf-8")
for marker in ("Delivery Operations Console", "Connected", "Token", "Releases", "Create release", "Delivery gates", "Risks", "Audit history", '/styles.css', '/app.js'):
    if marker not in index_text:
        raise SystemExit(f"Required marker {marker!r} missing from web/index.html")

wrapper_text = Path("src/aid_canary_app.py").read_text(encoding="utf-8")
if '127.0.0.1' not in wrapper_text:
    raise SystemExit("src/aid_canary_app.py must enforce loopback binding")

print("lint: ok")
PY

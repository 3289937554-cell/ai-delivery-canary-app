#!/usr/bin/env bash
set -euo pipefail

mkdir -p ./.ai-delivery/build

python3 - <<'PY'
from __future__ import annotations

import compileall
import hashlib
import json
import py_compile
import shutil
from pathlib import Path

root = Path(".")
build_dir = root / ".ai-delivery" / "build"
compile_root = build_dir / "compile-root"
pycache_dir = build_dir / "pycache"
manifest_path = build_dir / "asset-manifest.json"

if compile_root.exists():
    shutil.rmtree(compile_root)
if pycache_dir.exists():
    shutil.rmtree(pycache_dir)
compile_root.mkdir(parents=True, exist_ok=True)
pycache_dir.mkdir(parents=True, exist_ok=True)

source_files = sorted((root / "src").rglob("*.py"))
snapshot_src = compile_root / "src"
shutil.copytree(root / "src", snapshot_src, dirs_exist_ok=True)

# Keep the build step explicitly compileall-style while directing the
# compiled output into the deterministic build directory instead of src/.
for path in source_files:
    relative_path = path.relative_to(root)
    snapshot_path = compile_root / relative_path
    compileall.compile_file(str(snapshot_path), quiet=1, force=True)
    target = pycache_dir / relative_path.with_suffix(".pyc")
    target.parent.mkdir(parents=True, exist_ok=True)
    py_compile.compile(str(path), cfile=str(target), dfile=str(relative_path), doraise=True)

index_text = Path("web/index.html").read_text(encoding="utf-8")
required_assets = {
    "/app.js": Path("web/app.js"),
    "/styles.css": Path("web/styles.css"),
}
for reference, asset_path in required_assets.items():
    if reference not in index_text:
        raise SystemExit(f"Missing asset reference {reference} in web/index.html")
    if not asset_path.exists() or not asset_path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"Missing or empty asset: {asset_path}")

for marker in ("Delivery Operations Console", "Releases", "Delivery gates", "Risks", "Audit history"):
    if marker not in index_text:
        raise SystemExit(f"Missing UI marker {marker!r} in web/index.html")

manifest: dict[str, str] = {}
for asset_path in sorted(Path("web").glob("*")):
    if not asset_path.is_file():
        continue
    digest = hashlib.sha256(asset_path.read_bytes()).hexdigest()
    manifest[asset_path.name] = digest

manifest_path.write_text(
    json.dumps(
        {
            "schema_version": "delivery-ops-build-manifest/v1",
            "assets": manifest,
        },
        sort_keys=True,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

print("build: ok")
PY

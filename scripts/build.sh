#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
for root in (Path('src'), Path('tests')):
    for path in sorted(root.rglob('*.py')):
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
PY

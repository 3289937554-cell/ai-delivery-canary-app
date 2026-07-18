#!/usr/bin/env bash
set -euo pipefail

if [ -x .venv/bin/python3 ]; then
  export PATH="$(pwd)/.venv/bin:${PATH}"
fi

python3 -m mypy src/delivery_ops src/aid_canary_app.py scripts/validate_model_execution.py
printf '%s\n' "typecheck: ok"

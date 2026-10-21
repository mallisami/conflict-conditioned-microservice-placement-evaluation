#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
python3 tools/verify_rq3_inputs.py
if [[ ! -x .venv-rq3/bin/python ]]; then
  python3 -m venv .venv-rq3
  .venv-rq3/bin/python -m pip install --upgrade pip
  .venv-rq3/bin/python -m pip install -r requirements-b5-vm.txt
fi
PY="$ROOT/.venv-rq3/bin/python"
"$PY" -m pytest -q tests/test_rq3_extension.py tests/test_rq3_hybrid_design.py
# One command: locks -> historical selector reproduction -> 256 frozen selections ->
# frozen 1152-cell hybrid plan -> cluster preflight -> resumable science -> complete-only analysis.
exec "$PY" src/run_rq3_complete.py complete --workers "${RQ3_SELECTION_WORKERS:-3}"

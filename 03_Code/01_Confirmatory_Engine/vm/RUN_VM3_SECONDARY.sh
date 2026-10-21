#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; PY="$ROOT/.venv-b5/bin/python"
BUNDLE="${1:-$ROOT/vm_exchange/STAGE_A_FROZEN_FOR_WORKERS.tar.gz}"
(cd "$(dirname "$BUNDLE")" && sha256sum -c "$(basename "$BUNDLE").sha256")
"$PY" "$ROOT/src/vm_cluster_runner.py" import-stage-a --role vm3 --bundle "$BUNDLE"
"$PY" "$ROOT/src/vm_cluster_runner.py" secondary-vm3

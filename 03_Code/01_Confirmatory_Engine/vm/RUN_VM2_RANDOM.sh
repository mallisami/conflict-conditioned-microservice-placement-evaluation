#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; PY="$ROOT/.venv-b5/bin/python"
"$PY" "$ROOT/src/vm_cluster_runner.py" random-shard --role vm2

#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; PY="$ROOT/.venv-b5/bin/python"
VM1="${1:-$ROOT/vm_exchange/vm1_RANDOM_SHARD.tar.gz}"
VM2="${2:-$ROOT/vm_exchange/vm2_RANDOM_SHARD.tar.gz}"
VM3="${3:-$ROOT/vm_exchange/vm3_SECONDARY_RESULTS.tar.gz}"
"$PY" "$ROOT/src/vm_cluster_runner.py" merge-random --vm1 "$VM1" --vm2 "$VM2"
"$PY" "$ROOT/src/vm_cluster_runner.py" import-secondary --bundle "$VM3"
"$PY" "$ROOT/src/vm_cluster_runner.py" post-merge

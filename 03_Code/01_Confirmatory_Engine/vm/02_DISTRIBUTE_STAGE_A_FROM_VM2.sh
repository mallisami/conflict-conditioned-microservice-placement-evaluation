#!/usr/bin/env bash
set -euo pipefail
# Run on VM-2 after RUN_VM2_STAGE_A.sh. Fill the three variables or export them first.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_USER="${SSH_USER:-azureuser}"
VM1_PRIVATE_IP="${VM1_PRIVATE_IP:?export VM1_PRIVATE_IP}"
VM3_PRIVATE_IP="${VM3_PRIVATE_IP:?export VM3_PRIVATE_IP}"
REMOTE_ROOT="${REMOTE_ROOT:-$HOME/PAPER2_B5_3VM_CONFIRMATORY_CAMPAIGN_V1_0_20261009}"
B="$ROOT/vm_exchange/STAGE_A_FROZEN_FOR_WORKERS.tar.gz"
H="$B.sha256"
[[ -f "$B" && -f "$H" ]] || { echo "Stage-A bundle missing" >&2; exit 2; }
scp "$B" "$H" "$SSH_USER@$VM1_PRIVATE_IP:$REMOTE_ROOT/vm_exchange/"
scp "$B" "$H" "$SSH_USER@$VM3_PRIVATE_IP:$REMOTE_ROOT/vm_exchange/"
echo "STAGE-A FROZEN SNAPSHOT DISTRIBUTED TO VM-1 AND VM-3"

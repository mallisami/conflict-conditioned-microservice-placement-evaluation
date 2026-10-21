#!/usr/bin/env bash
set -euo pipefail
# Run on VM-2 after VM-1 and VM-3 finish their assigned jobs.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_USER="${SSH_USER:-azureuser}"
VM1_PRIVATE_IP="${VM1_PRIVATE_IP:?export VM1_PRIVATE_IP}"
VM3_PRIVATE_IP="${VM3_PRIVATE_IP:?export VM3_PRIVATE_IP}"
REMOTE_ROOT="${REMOTE_ROOT:-$HOME/PAPER2_B5_3VM_CONFIRMATORY_CAMPAIGN_V1_0_20261009}"
scp "$SSH_USER@$VM1_PRIVATE_IP:$REMOTE_ROOT/vm_exchange/vm1_RANDOM_SHARD.tar.gz" "$ROOT/vm_exchange/"
scp "$SSH_USER@$VM1_PRIVATE_IP:$REMOTE_ROOT/vm_exchange/vm1_RANDOM_SHARD.tar.gz.sha256" "$ROOT/vm_exchange/"
scp "$SSH_USER@$VM3_PRIVATE_IP:$REMOTE_ROOT/vm_exchange/vm3_SECONDARY_RESULTS.tar.gz" "$ROOT/vm_exchange/"
scp "$SSH_USER@$VM3_PRIVATE_IP:$REMOTE_ROOT/vm_exchange/vm3_SECONDARY_RESULTS.tar.gz.sha256" "$ROOT/vm_exchange/"
(cd "$ROOT/vm_exchange" && sha256sum -c vm1_RANDOM_SHARD.tar.gz.sha256 && sha256sum -c vm3_SECONDARY_RESULTS.tar.gz.sha256)
echo "WORKER RESULTS COLLECTED AND HASH-VERIFIED ON VM-2"

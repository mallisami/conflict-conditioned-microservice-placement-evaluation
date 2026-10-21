#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip git curl unzip rsync jq ca-certificates
if ! command -v docker >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io
  sudo systemctl enable --now docker
else
  echo "Preserving existing Docker installation: $(docker --version)"
fi
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
  sudo usermod -aG docker "$USER"
  echo "Added $USER to docker group. Log out/SSH back in, then rerun." >&2
  exit 10
fi
docker version >/dev/null
python3 - <<'PY'
import sys
if not ((3,10) <= sys.version_info[:2] <= (3,12)):
    raise SystemExit(f"B5 runtime expects Python 3.10-3.12; got {sys.version}")
print('Python runtime:',sys.version)
PY
rm -rf "$ROOT/.venv-b5"
python3 -m venv "$ROOT/.venv-b5"
PY="$ROOT/.venv-b5/bin/python"
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r "$ROOT/requirements-b5-vm.txt"
"$PY" "$ROOT/tools/verify_base.py"
"$PY" "$ROOT/tools/verify_stage_a_harness.py"
"$PY" "$ROOT/tools/verify_vm_execution.py"
"$PY" -m pytest -q "$ROOT/tests"
echo "COMMON B5 VM INSTALL/PREFLIGHT COMPLETE"

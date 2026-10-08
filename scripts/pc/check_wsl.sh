#!/usr/bin/env bash
set -euo pipefail
source_root="$(cd "$(dirname "$0")/../.." && pwd)"
target="${1:-$HOME/secure-agent-platform}"
test -d "$target/.git"
# Carry only changed source files; local environments, databases, and credentials stay in Ubuntu.
python3 "$source_root/scripts/pc/sync_wsl.py" --target "$target"
cd "$target"
make check ui-build ui-check release-validate demo-replay demo-durable control-smoke
make sandbox-build sandbox-smoke demo-isolated eval-tools-isolated

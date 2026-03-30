#!/usr/bin/env bash
set -euo pipefail

git config --global --add safe.directory /workspaces/CommDev || true

cat <<'EOF'
Devcontainer ready.

Next steps:
1. Replace scripts/run-opc-app.sh with the command that starts your OPC UA application.
2. Start the two-node testbed with ./scripts/testbed.sh up.
3. Follow both nodes with ./scripts/testbed.sh logs.
EOF
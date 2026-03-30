#!/usr/bin/env bash
set -euo pipefail

git config --global --add safe.directory /workspaces/CommDev || true

cat <<'EOF'
Devcontainer ready.

Next steps:
1. Replace scripts/run-sample-app.sh with the command that starts your sample communication application.
2. Start the live communication testbed with ./scripts/testbed.sh run.
3. Stop the live testbed with ./scripts/testbed.sh down.
EOF
#!/usr/bin/env bash
set -euo pipefail

board_name="${COMM_INSTANCE_NAME:-board}"
runner="/workspace/scripts/run-sample-app.sh"

cat <<EOF
[$board_name] container is ready
[$board_name] endpoint: ${COMM_ENDPOINT:-unset}
[$board_name] peer endpoint: ${COMM_PEER_ENDPOINT:-unset}
EOF

if [[ ! -f "$runner" ]]; then
  echo "[$board_name] missing runner script at $runner"
  echo "[$board_name] create that file to start your sample application"
  exit 1
fi

exec /bin/bash "$runner" "$@"
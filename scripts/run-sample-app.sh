#!/usr/bin/env bash
set -euo pipefail

role="${COMM_ROLE:-}"

if [[ -z "$role" ]]; then
  case "${COMM_INSTANCE_NAME:-}" in
    board-a)
      role="server"
      ;;
    board-b)
      role="client"
      ;;
    *)
      echo "Unable to infer COMM_ROLE for ${COMM_INSTANCE_NAME:-unknown}."
      exit 1
      ;;
  esac
fi

case "$role" in
  server)
    exec python3 -u /workspace/apps/opcua_server.py serve "$@"
    ;;
  client)
    if [[ "$#" -gt 0 ]]; then
      exec python3 -u /workspace/apps/opcua_client.py "$@"
    fi

    exec python3 -u /workspace/apps/opcua_client.py run
    ;;
  *)
    echo "Unsupported COMM_ROLE: $role"
    exit 1
    ;;
esac
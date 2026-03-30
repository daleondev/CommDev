#!/usr/bin/env bash
set -euo pipefail

role="${OPC_ROLE:-}"

if [[ -z "$role" ]]; then
  case "${OPC_INSTANCE_NAME:-}" in
    opc-node-a)
      role="server"
      ;;
    opc-node-b)
      role="client"
      ;;
    *)
      echo "Unable to infer OPC_ROLE for ${OPC_INSTANCE_NAME:-unknown}."
      exit 1
      ;;
  esac
fi

case "$role" in
  server)
    exec python3 -u /workspace/apps/opcua_server.py
    ;;
  client)
    exec python3 -u /workspace/apps/opcua_client.py
    ;;
  *)
    echo "Unsupported OPC_ROLE: $role"
    exit 1
    ;;
esac
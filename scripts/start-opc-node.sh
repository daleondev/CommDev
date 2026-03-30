#!/usr/bin/env bash
set -euo pipefail

node_name="${OPC_INSTANCE_NAME:-opc-node}"
runner="/workspace/scripts/run-opc-app.sh"
data_dir="${OPC_DATA_DIR:-/var/lib/opcua/data}"
pki_dir="${OPC_PKI_DIR:-/var/lib/opcua/pki}"

mkdir -p "$data_dir" "$pki_dir"

cat <<EOF
[$node_name] testbed container is ready
[$node_name] endpoint: ${OPC_ENDPOINT:-unset}
[$node_name] peer endpoint: ${OPC_PEER_ENDPOINT:-unset}
[$node_name] data dir: $data_dir
[$node_name] pki dir: $pki_dir
EOF

if [[ ! -f "$runner" ]]; then
  echo "[$node_name] missing runner script at $runner"
  echo "[$node_name] create that file to start your OPC UA application"
  exec sleep infinity
fi

exec /bin/bash "$runner" "$@"
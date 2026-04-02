#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dockerfile_path="$repo_root/.devcontainer/Dockerfile"
image_target="comms-toolchain"
testbed_name="${COMMDEV_TESTBED_NAME:-commdev-comms-testbed}"
resource_name_prefix="${testbed_name//[^a-zA-Z0-9_.-]/-}"
resource_name_prefix="${resource_name_prefix,,}"
resource_name_prefix="${resource_name_prefix:-commdev-comms-testbed}"
testbed_image="${COMMDEV_TESTBED_IMAGE:-${resource_name_prefix}:local}"
tmux_session_name="${COMMDEV_TESTBED_TMUX_SESSION:-commdev-comms-live}"
shared_network_name="${COMMDEV_COMMS_NETWORK:-commdev-comms-net}"
shared_network_subnet="${COMMDEV_COMMS_SUBNET:-192.168.10.0/24}"
shared_network_gateway="${COMMDEV_COMMS_GATEWAY:-192.168.10.1}"
board_a_ipv4_address="${BOARD_A_IPV4_ADDRESS:-192.168.10.10}"
board_b_ipv4_address="${BOARD_B_IPV4_ADDRESS:-192.168.10.11}"
board_port="${COMM_PORT:-4840}"
comm_log_level="${COMM_LOG_LEVEL:-info}"
opcua_namespace="${OPCUA_NAMESPACE:-urn:commdev:opcua}"
tmux_attach="${COMMDEV_TMUX_ATTACH:-1}"

docker_cmd=()

resolve_docker_command() {
  if docker version >/dev/null 2>&1; then
    docker_cmd=(docker)
    return
  fi

  if sudo docker version >/dev/null 2>&1; then
    docker_cmd=(sudo docker)
    return
  fi

  echo "No Docker command is reachable from this shell."
  exit 1
}

docker_cli() {
  "${docker_cmd[@]}" "$@"
}

quote_command() {
  local parts=()
  local arg

  for arg in "$@"; do
    parts+=("$(printf '%q' "$arg")")
  done

  local IFS=' '
  printf '%s' "${parts[*]}"
}

board_container_name() {
  printf '%s-%s' "$resource_name_prefix" "$1"
}

board_ipv4_address() {
  case "$1" in
    board-a)
      printf '%s' "$board_a_ipv4_address"
      ;;
    board-b)
      printf '%s' "$board_b_ipv4_address"
      ;;
    *)
      echo "Unsupported board: $1" >&2
      exit 1
      ;;
  esac
}

board_role() {
  case "$1" in
    board-a)
      printf '%s' server
      ;;
    board-b)
      printf '%s' client
      ;;
    *)
      echo "Unsupported board: $1" >&2
      exit 1
      ;;
  esac
}

board_endpoint() {
  local board_ip

  board_ip="$(board_ipv4_address "$1")"
  printf 'opc.tcp://%s:%s' "$board_ip" "$board_port"
}

board_peer_endpoint() {
  case "$1" in
    board-a)
      board_endpoint board-b
      ;;
    board-b)
      board_endpoint board-a
      ;;
    *)
      echo "Unsupported board: $1" >&2
      exit 1
      ;;
  esac
}

remove_board_container() {
  docker_cli rm -f "$(board_container_name "$1")" >/dev/null 2>&1 || true
}

cleanup_live_resources() {
  tmux kill-session -t "$tmux_session_name" 2>/dev/null || true
  remove_board_container board-a
  remove_board_container board-b
}

ensure_tmux() {
  if command -v tmux >/dev/null 2>&1; then
    return
  fi

  echo "tmux is required for the live communication console."
  echo "If this devcontainer was opened before tmux was added to the Dockerfile, rebuild or reopen the devcontainer first."
  exit 1
}

ensure_shared_network() {
  local actual_subnet
  local actual_gateway

  if docker_cli network inspect "$shared_network_name" >/dev/null 2>&1; then
    actual_subnet="$(docker_cli network inspect -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}' "$shared_network_name")"
    actual_gateway="$(docker_cli network inspect -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}' "$shared_network_name")"

    if [[ "$actual_subnet" != "$shared_network_subnet" || "$actual_gateway" != "$shared_network_gateway" ]]; then
      echo "Shared network $shared_network_name exists with subnet=$actual_subnet gateway=$actual_gateway."
      echo "Expected subnet=$shared_network_subnet gateway=$shared_network_gateway."
      echo "Remove or recreate that network before starting the live testbed."
      exit 1
    fi

    return
  fi

  docker_cli network create \
    --driver bridge \
    --subnet "$shared_network_subnet" \
    --gateway "$shared_network_gateway" \
    "$shared_network_name" >/dev/null
}

build_image() {
  docker_cli build \
    --target "$image_target" \
    -f "$dockerfile_path" \
    -t "$testbed_image" \
    "$repo_root"
}

rebuild_image() {
  docker_cli build \
    --no-cache \
    --target "$image_target" \
    -f "$dockerfile_path" \
    -t "$testbed_image" \
    "$repo_root"
}

create_board_container() {
  local board_name="$1"
  local container_name
  local board_ip
  local board_role_value
  local board_endpoint_value
  local board_peer_endpoint_value

  container_name="$(board_container_name "$board_name")"
  board_ip="$(board_ipv4_address "$board_name")"
  board_role_value="$(board_role "$board_name")"
  board_endpoint_value="$(board_endpoint "$board_name")"
  board_peer_endpoint_value="$(board_peer_endpoint "$board_name")"

  remove_board_container "$board_name"

  docker_cli create \
    --name "$container_name" \
    --hostname "$board_name" \
    --init \
    --interactive \
    --tty \
    --workdir /workspace \
    --network "$shared_network_name" \
    --ip "$board_ip" \
    --label "commdev.testbed=true" \
    --label "commdev.testbed.name=$testbed_name" \
    --label "commdev.board=$board_name" \
    --env "COMM_ROLE=$board_role_value" \
    --env "COMM_INSTANCE_NAME=$board_name" \
    --env "COMM_PORT=$board_port" \
    --env "COMM_ENDPOINT=$board_endpoint_value" \
    --env "COMM_PEER_ENDPOINT=$board_peer_endpoint_value" \
    --env "COMM_LOG_LEVEL=$comm_log_level" \
    --env "OPCUA_NAMESPACE=$opcua_namespace" \
    "$testbed_image" \
    /bin/bash /workspace/scripts/start-board.sh >/dev/null
}

prepare_live_containers() {
  create_board_container board-a
  create_board_container board-b
}

open_live_console() {
  local board_a_container_name
  local board_b_container_name
  local client_command
  local server_command

  ensure_tmux
  prepare_live_containers

  board_a_container_name="$(board_container_name board-a)"
  board_b_container_name="$(board_container_name board-b)"

  client_command="$(quote_command "${docker_cmd[@]}" start -ai "$board_b_container_name")"
  server_command="$(quote_command "${docker_cmd[@]}" start -ai "$board_a_container_name")"

  tmux kill-session -t "$tmux_session_name" 2>/dev/null || true
  tmux new-session -d -x 240 -y 60 -s "$tmux_session_name" -n live "$client_command"
  tmux split-window -h -t "$tmux_session_name:0" "$server_command"
  tmux select-pane -t "$tmux_session_name:0.0"
  tmux setw -t "$tmux_session_name:0" remain-on-exit off
  tmux set-hook -t "$tmux_session_name" pane-exited "kill-session -t $tmux_session_name"

  if [[ "$tmux_attach" == "0" ]]; then
    return
  fi

  set +e
  tmux attach-session -t "$tmux_session_name"
  set -e

  cleanup_live_resources
}

usage() {
  cat <<'EOF'
Usage: ./scripts/testbed.sh [run|rebuild|down]

Commands:
  run      Build if needed and start the live communication console
  rebuild  Rebuild the image and start the live communication console
  down     Stop and remove any live testbed containers and tmux session
EOF
}

command="${1:-run}"

case "$command" in
  run|up)
    resolve_docker_command
    cleanup_live_resources
    ensure_shared_network
    build_image
    open_live_console
    ;;
  rebuild)
    resolve_docker_command
    cleanup_live_resources
    ensure_shared_network
    rebuild_image
    open_live_console
    ;;
  down)
    resolve_docker_command
    cleanup_live_resources
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
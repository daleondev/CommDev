#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repo_root/compose.testbed.yml"
tmux_session_name="${COMMDEV_TESTBED_TMUX_SESSION:-commdev-comms-live}"
shared_network_name="${COMMDEV_COMMS_NETWORK:-commdev-comms-net}"
shared_network_subnet="${COMMDEV_COMMS_SUBNET:-192.168.10.0/24}"
shared_network_gateway="${COMMDEV_COMMS_GATEWAY:-192.168.10.1}"
tmux_attach="${COMMDEV_TMUX_ATTACH:-1}"

compose_cmd=()
docker_cmd=()

resolve_compose_command() {
  if docker compose version >/dev/null 2>&1; then
    compose_cmd=(docker compose -f "$compose_file")
    return
  fi

  if docker-compose version >/dev/null 2>&1; then
    compose_cmd=(docker-compose -f "$compose_file")
    return
  fi

  if sudo docker compose version >/dev/null 2>&1; then
    compose_cmd=(sudo docker compose -f "$compose_file")
    return
  fi

  if sudo docker-compose version >/dev/null 2>&1; then
    compose_cmd=(sudo docker-compose -f "$compose_file")
    return
  fi

  echo "No Docker Compose command is reachable from this shell."
  echo "Inside the devcontainer, the Docker feature should provide docker compose automatically."
  exit 1
}

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

docker_compose() {
  "${compose_cmd[@]}" "$@"
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

cleanup_live_resources() {
  tmux kill-session -t "$tmux_session_name" 2>/dev/null || true
  docker_compose down --remove-orphans >/dev/null 2>&1 || true
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

build_images() {
  docker_compose build board-a board-b
}

rebuild_images() {
  docker_compose build --no-cache board-a board-b
}

prepare_live_containers() {
  docker_compose create --force-recreate board-a board-b >/dev/null
}

compose_container_id() {
  docker_compose ps -a -q "$1"
}

open_live_console() {
  local board_a_container_id
  local board_b_container_id
  local client_command
  local server_command

  ensure_tmux
  prepare_live_containers

  board_a_container_id="$(compose_container_id board-a)"
  board_b_container_id="$(compose_container_id board-b)"

  if [[ -z "$board_a_container_id" || -z "$board_b_container_id" ]]; then
    echo "Failed to create the live board containers."
    exit 1
  fi

  client_command="$(quote_command "${docker_cmd[@]}" start -ai "$board_b_container_id")"
  server_command="$(quote_command "${docker_cmd[@]}" start -ai "$board_a_container_id")"

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
  rebuild  Rebuild the images and start the live communication console
  down     Stop and remove any live testbed containers and tmux session
EOF
}

resolve_compose_command
resolve_docker_command

command="${1:-run}"

case "$command" in
  run|up)
    cleanup_live_resources
    ensure_shared_network
    build_images
    open_live_console
    ;;
  rebuild)
    cleanup_live_resources
    ensure_shared_network
    rebuild_images
    open_live_console
    ;;
  down)
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
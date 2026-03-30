#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repo_root/compose.testbed.yml"
tmux_session_name="${COMMDEV_TESTBED_TMUX_SESSION:-commdev-testbed-live}"
client_container_name="${COMMDEV_CLIENT_CONTAINER_NAME:-commdev-opc-node-b-live}"
server_container_name="${COMMDEV_SERVER_CONTAINER_NAME:-commdev-opc-node-a-live}"
tmux_attach="${COMMDEV_TMUX_ATTACH:-1}"
cleanup_on_exit="${COMMDEV_TESTBED_CLEANUP_ON_EXIT:-1}"

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

compose_run_command() {
  local service="$1"
  local name="$2"

  quote_command \
    "${compose_cmd[@]}" \
    run \
    --rm \
    --no-deps \
    --service-ports \
    --use-aliases \
    --name "$name" \
    "$service"
}

cleanup_live_resources() {
  tmux kill-session -t "$tmux_session_name" 2>/dev/null || true
  docker_cli rm -f "$client_container_name" "$server_container_name" >/dev/null 2>&1 || true
  docker_compose down --remove-orphans >/dev/null 2>&1 || true
}

ensure_tmux() {
  if command -v tmux >/dev/null 2>&1; then
    return
  fi

  echo "tmux is required for the live testbed console."
  echo "If this devcontainer was opened before tmux was added to the Dockerfile, rebuild or reopen the devcontainer first."
  exit 1
}

build_images() {
  docker_compose build opc-node-a opc-node-b
}

rebuild_images() {
  docker_compose build --no-cache opc-node-a opc-node-b
}

open_live_console() {
  local client_command
  local server_command

  ensure_tmux

  client_command="$(compose_run_command opc-node-b "$client_container_name")"
  server_command="$(compose_run_command opc-node-a "$server_container_name")"

  tmux kill-session -t "$tmux_session_name" 2>/dev/null || true
  tmux new-session -d -x 240 -y 60 -s "$tmux_session_name" -n live "$client_command"
  tmux split-window -h -t "$tmux_session_name:0" "$server_command"
  tmux select-pane -t "$tmux_session_name:0.0"
  tmux setw -t "$tmux_session_name:0" remain-on-exit off
  tmux set-hook -t "$tmux_session_name" pane-exited "kill-session -t $tmux_session_name"

  if [[ "$tmux_attach" == "0" ]]; then
    return
  fi

  if [[ "$cleanup_on_exit" == "1" ]]; then
    trap cleanup_live_resources EXIT INT TERM
  fi

  tmux attach-session -t "$tmux_session_name"
}

usage() {
  cat <<'EOF'
Usage: ./scripts/testbed.sh [run|rebuild|down]

Commands:
  run      Build if needed and start the live tmux console
  rebuild  Rebuild the images and start the live tmux console
  down     Stop and remove any live testbed containers and tmux session
EOF
}

resolve_compose_command
resolve_docker_command

command="${1:-run}"

case "$command" in
  run|up)
    cleanup_live_resources
    build_images
    open_live_console
    ;;
  rebuild)
    cleanup_live_resources
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
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repo_root/compose.testbed.yml"

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose -f "$compose_file" "$@"
    return
  fi

  if docker-compose version >/dev/null 2>&1; then
    docker-compose -f "$compose_file" "$@"
    return
  fi

  if sudo docker compose version >/dev/null 2>&1; then
    sudo docker compose -f "$compose_file" "$@"
    return
  fi

  if sudo docker-compose version >/dev/null 2>&1; then
    sudo docker-compose -f "$compose_file" "$@"
    return
  fi

  echo "No Docker Compose command is reachable from this shell."
  echo "Inside the devcontainer, the Docker feature should provide docker compose automatically."
  exit 1
}

usage() {
  cat <<'EOF'
Usage: ./scripts/testbed.sh <command> [args]

Commands:
  up              Build and start opc-node-a and opc-node-b
  rebuild         Force rebuild and recreate both nodes
  down            Stop the testbed and remove containers
  logs [service]  Follow logs for both nodes or one service
  ps              Show testbed container status
  shell <service> Open a shell in opc-node-a or opc-node-b
  restart         Restart both nodes
EOF
}

command="${1:-}"

case "$command" in
  up)
    docker_compose up -d --build opc-node-a opc-node-b
    ;;
  rebuild)
    docker_compose up -d --build --force-recreate opc-node-a opc-node-b
    ;;
  down)
    docker_compose down --remove-orphans
    ;;
  logs)
    if [[ -n "${2:-}" ]]; then
      docker_compose logs -f "$2"
    else
      docker_compose logs -f opc-node-a opc-node-b
    fi
    ;;
  ps)
    docker_compose ps
    ;;
  shell)
    service="${2:-}"

    if [[ "$service" != "opc-node-a" && "$service" != "opc-node-b" ]]; then
      echo "Choose opc-node-a or opc-node-b."
      exit 1
    fi

    docker_compose exec "$service" bash
    ;;
  restart)
    docker_compose restart opc-node-a opc-node-b
    ;;
  *)
    usage
    exit 1
    ;;
esac
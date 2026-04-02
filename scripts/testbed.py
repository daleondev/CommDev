#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / ".devcontainer" / "Dockerfile"
IMAGE_TARGET = "comms-toolchain"
TESTBED_NAME = os.environ.get("COMMDEV_TESTBED_NAME", "commdev-comms-testbed")
TESTBED_IMAGE = os.environ.get("COMMDEV_TESTBED_IMAGE", "commdev-comms-testbed:local")
TMUX_SESSION = os.environ.get("COMMDEV_TESTBED_TMUX_SESSION", "commdev-comms-live")
NETWORK_NAME = os.environ.get("COMMDEV_COMMS_NETWORK", "commdev-comms-net")
NETWORK_SUBNET = os.environ.get("COMMDEV_COMMS_SUBNET", "192.168.10.0/24")
NETWORK_GATEWAY = os.environ.get("COMMDEV_COMMS_GATEWAY", "192.168.10.1")
BOARD_PORT = os.environ.get("COMM_PORT", "4840")
COMM_LOG_LEVEL = os.environ.get("COMM_LOG_LEVEL", "info")
OPCUA_NAMESPACE = os.environ.get("OPCUA_NAMESPACE", "urn:commdev:opcua")
TMUX_ATTACH = os.environ.get("COMMDEV_TMUX_ATTACH", "1") != "0"
BOARDS = {
    "board-a": {
        "role": "server",
        "ip": os.environ.get("BOARD_A_IPV4_ADDRESS", "192.168.10.10"),
    },
    "board-b": {
        "role": "client",
        "ip": os.environ.get("BOARD_B_IPV4_ADDRESS", "192.168.10.11"),
    },
}


def run(command: list[str], *, check: bool = True, capture: bool = False, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {"cwd": ROOT, "text": True, "check": check}

    if capture:
        kwargs["capture_output"] = True
    elif quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

    return subprocess.run(command, **kwargs)


def resolve_docker() -> list[str]:
    for command in (["docker"], ["sudo", "docker"]):
        if run(command + ["version"], check=False, quiet=True).returncode == 0:
            return command

    raise SystemExit("No Docker command is reachable from this shell.")


DOCKER = resolve_docker()


def docker(*args: str, check: bool = True, capture: bool = False, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    return run(DOCKER + list(args), check=check, capture=capture, quiet=quiet)


def container_name(board: str) -> str:
    return f"{TESTBED_NAME}-{board}"


def endpoint(board: str) -> str:
    return f"opc.tcp://{BOARDS[board]['ip']}:{BOARD_PORT}"


def cleanup() -> None:
    if shutil.which("tmux"):
        subprocess.run(["tmux", "kill-session", "-t", TMUX_SESSION], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for board in BOARDS:
        docker("rm", "-f", container_name(board), check=False, quiet=True)


def ensure_tmux() -> None:
    if shutil.which("tmux"):
        return

    raise SystemExit(
        "tmux is required for the live communication console.\n"
        "If this devcontainer was opened before tmux was added to the Dockerfile, rebuild or reopen the devcontainer first."
    )


def ensure_shared_network() -> None:
    result = docker("network", "inspect", NETWORK_NAME, "--format", "{{json .IPAM.Config}}", check=False, capture=True)

    if result.returncode == 0:
        configs = json.loads(result.stdout.strip() or "[]")
        config = configs[0] if configs else {}
        actual_subnet = config.get("Subnet", "")
        actual_gateway = config.get("Gateway", "")

        if actual_subnet != NETWORK_SUBNET or actual_gateway != NETWORK_GATEWAY:
            raise SystemExit(
                f"Shared network {NETWORK_NAME} exists with subnet={actual_subnet} gateway={actual_gateway}.\n"
                f"Expected subnet={NETWORK_SUBNET} gateway={NETWORK_GATEWAY}.\n"
                "Remove or recreate that network before starting the live testbed."
            )

        return

    docker(
        "network",
        "create",
        "--driver",
        "bridge",
        "--subnet",
        NETWORK_SUBNET,
        "--gateway",
        NETWORK_GATEWAY,
        NETWORK_NAME,
        quiet=True,
    )


def build_image(*, no_cache: bool) -> None:
    command = ["build"]

    if no_cache:
        command.append("--no-cache")

    command.extend(["--target", IMAGE_TARGET, "-f", str(DOCKERFILE), "-t", TESTBED_IMAGE, str(ROOT)])
    docker(*command)


def create_board(board: str) -> None:
    peer = "board-b" if board == "board-a" else "board-a"

    docker("rm", "-f", container_name(board), check=False, quiet=True)
    docker(
        "create",
        "--name",
        container_name(board),
        "--hostname",
        board,
        "--init",
        "--interactive",
        "--tty",
        "--workdir",
        "/workspace",
        "--network",
        NETWORK_NAME,
        "--ip",
        BOARDS[board]["ip"],
        "--label",
        "commdev.testbed=true",
        "--label",
        f"commdev.board={board}",
        "--env",
        f"COMM_ROLE={BOARDS[board]['role']}",
        "--env",
        f"COMM_INSTANCE_NAME={board}",
        "--env",
        f"COMM_PORT={BOARD_PORT}",
        "--env",
        f"COMM_ENDPOINT={endpoint(board)}",
        "--env",
        f"COMM_PEER_ENDPOINT={endpoint(peer)}",
        "--env",
        f"COMM_LOG_LEVEL={COMM_LOG_LEVEL}",
        "--env",
        f"OPCUA_NAMESPACE={OPCUA_NAMESPACE}",
        TESTBED_IMAGE,
        "python3",
        "/workspace/scripts/run_sample_app.py",
        quiet=True,
    )


def run_tmux(command: list[str]) -> None:
    subprocess.run(command, check=True)


def open_console() -> None:
    ensure_tmux()

    try:
        create_board("board-a")
        create_board("board-b")

        client_command = shlex.join(DOCKER + ["start", "-ai", container_name("board-b")])
        server_command = shlex.join(DOCKER + ["start", "-ai", container_name("board-a")])

        subprocess.run(["tmux", "kill-session", "-t", TMUX_SESSION], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run_tmux(["tmux", "new-session", "-d", "-x", "240", "-y", "60", "-s", TMUX_SESSION, "-n", "live", client_command])
        run_tmux(["tmux", "split-window", "-h", "-t", f"{TMUX_SESSION}:0", server_command])
        run_tmux(["tmux", "select-pane", "-t", f"{TMUX_SESSION}:0.0"])
        run_tmux(["tmux", "setw", "-t", f"{TMUX_SESSION}:0", "remain-on-exit", "off"])
        run_tmux(["tmux", "set-hook", "-t", TMUX_SESSION, "pane-exited", f"kill-session -t {TMUX_SESSION}"])

        if not TMUX_ATTACH:
            return

        try:
            subprocess.run(["tmux", "attach-session", "-t", TMUX_SESSION], check=False)
        finally:
            cleanup()
    except Exception:
        cleanup()
        raise


def print_usage() -> None:
    print(
        "Usage: python3 ./scripts/testbed.py [run|rebuild|down]\n\n"
        "Commands:\n"
        "  run      Build if needed and start the live communication console\n"
        "  rebuild  Rebuild the image and start the live communication console\n"
        "  down     Stop and remove any live testbed containers and tmux session"
    )


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "run"

    if command in {"help", "-h", "--help"}:
        print_usage()
        return 0

    if command in {"run", "up"}:
        cleanup()
        ensure_shared_network()
        build_image(no_cache=False)
        open_console()
        return 0

    if command == "rebuild":
        cleanup()
        ensure_shared_network()
        build_image(no_cache=True)
        open_console()
        return 0

    if command == "down":
        cleanup()
        return 0

    print_usage()
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except subprocess.CalledProcessError as error:
        print(f"Command failed: {shlex.join(error.cmd)}", file=sys.stderr)
        raise SystemExit(error.returncode or 1)
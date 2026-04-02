#!/usr/bin/env python3

from __future__ import annotations

import os
import sys


def resolve_role() -> str:
    role = os.environ.get("COMM_ROLE")

    if role:
        return role

    instance_name = os.environ.get("COMM_INSTANCE_NAME")
    if instance_name == "board-a":
        return "server"
    if instance_name == "board-b":
        return "client"

    raise SystemExit(f"Unable to infer COMM_ROLE for {instance_name or 'unknown'}.")


def main(argv: list[str]) -> int:
    board_name = os.environ.get("COMM_INSTANCE_NAME", "board")
    print(f"[{board_name}] container is ready", flush=True)
    print(f"[{board_name}] endpoint: {os.environ.get('COMM_ENDPOINT', 'unset')}", flush=True)
    print(f"[{board_name}] peer endpoint: {os.environ.get('COMM_PEER_ENDPOINT', 'unset')}", flush=True)

    role = resolve_role()
    if role == "server":
        os.execvp("python3", ["python3", "-u", "/workspace/apps/opcua_server.py", "serve", *argv[1:]])

    if role == "client":
        command = argv[1:] or ["run"]
        os.execvp("python3", ["python3", "-u", "/workspace/apps/opcua_client.py", *command])

    raise SystemExit(f"Unsupported COMM_ROLE: {role}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
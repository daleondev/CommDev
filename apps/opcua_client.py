#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import os
import queue as queue_module
import shlex
import sys
import threading
import time
from datetime import datetime, timezone

from asyncua import Client, ua


DEFAULT_QUERY_PATHS = [
    "CommDevDemo/Heartbeat",
    "CommDevDemo/Command",
    "CommDevDemo/Ack",
]


def env_default(name: str, fallback: str) -> str:
    return os.environ.get(name, fallback)


def log(instance_name: str, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] [{instance_name}] [client] {message}", flush=True)


def add_connection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--instance-name", default=env_default("COMM_INSTANCE_NAME", "board-b"))
    parser.add_argument("--endpoint", default=env_default("COMM_PEER_ENDPOINT", "opc.tcp://192.168.10.10:4840"))
    parser.add_argument("--namespace", default=env_default("OPCUA_NAMESPACE", "urn:commdev:opcua"))
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--log-level", default=env_default("COMM_LOG_LEVEL", "info"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CommDev sample OPC UA client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the continuous client loop")
    add_connection_arguments(run_parser)
    run_parser.add_argument("--connect-retry-seconds", type=float, default=2.0)
    run_parser.add_argument("--transaction-interval", type=float, default=3.0)
    run_parser.add_argument("--ack-timeout", type=float, default=10.0)

    browse_parser = subparsers.add_parser("browse", help="Browse and print nodes")
    add_connection_arguments(browse_parser)
    browse_parser.add_argument("--start-path", default="objects")
    browse_parser.add_argument("--depth", type=int, default=3)
    browse_parser.add_argument("--include-values", action="store_true")

    read_parser = subparsers.add_parser("read", help="Read and print specific nodes")
    add_connection_arguments(read_parser)
    read_parser.add_argument("paths", nargs="+", help="Node paths such as CommDevDemo/Heartbeat")

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0].startswith("-"):
        args = ["run", *args]

    return parser.parse_args(args)


def normalize_segment(segment: str, namespace_index: int) -> str:
    if ":" in segment:
        prefix, _ = segment.split(":", 1)
        if prefix.isdigit():
            return segment

    return f"{namespace_index}:{segment}"


async def resolve_namespace_index(client: Client, namespace: str) -> int:
    return await client.get_namespace_index(namespace)


async def resolve_node(client: Client, namespace_index: int, path: str):
    stripped = path.strip().strip("/")
    lowered = stripped.lower()

    if not stripped or lowered == "objects":
        return client.nodes.objects

    if lowered == "server":
        return client.nodes.server

    if stripped.startswith(("ns=", "i=", "s=", "g=", "b=")):
        return client.get_node(stripped)

    segments = [segment for segment in stripped.split("/") if segment]
    if segments and segments[0].lower() == "objects":
        segments = segments[1:]

    if not segments:
        return client.nodes.objects

    qualified_segments = [normalize_segment(segment, namespace_index) for segment in segments]
    return await client.nodes.objects.get_child(qualified_segments)


async def describe_node(node, include_value: bool = True) -> str:
    browse_name = await node.read_browse_name()
    node_class = await node.read_node_class()
    description = f"{browse_name.NamespaceIndex}:{browse_name.Name} [{node_class.name}] id={node.nodeid}"

    if include_value and node_class == ua.NodeClass.Variable:
        try:
            value = await node.read_value()
            description += f" value={value!r}"
        except Exception as exc:
            description += f" value=<error {exc!r}>"

    return description


async def print_tree(instance_name: str, node, depth: int, include_values: bool, indent: int = 0) -> None:
    log(instance_name, f"tree {'  ' * indent}{await describe_node(node, include_value=include_values)}")

    if depth <= 0:
        return

    children = await node.get_children()
    child_entries: list[tuple[int, str, object]] = []

    for child in children:
        browse_name = await child.read_browse_name()
        child_entries.append((browse_name.NamespaceIndex, browse_name.Name, child))

    for _, _, child in sorted(child_entries):
        await print_tree(instance_name, child, depth - 1, include_values, indent + 1)


async def print_requested_nodes(instance_name: str, nodes: list[tuple[str, object]]) -> None:
    for path, node in nodes:
        log(instance_name, f"query {path} => {await describe_node(node, include_value=True)}")


def start_stdin_reader(instance_name: str) -> queue_module.SimpleQueue[str] | None:
    if sys.stdin is None or sys.stdin.closed:
        return None

    command_queue: queue_module.SimpleQueue[str] = queue_module.SimpleQueue()

    def reader() -> None:
        while True:
            line = sys.stdin.readline()
            if line == "":
                time.sleep(0.2)
                continue

            command_queue.put(line.rstrip("\n"))

    thread = threading.Thread(target=reader, name=f"{instance_name}-stdin-reader", daemon=True)
    thread.start()
    return command_queue


async def handle_interactive_command(
    instance_name: str,
    command_line: str,
    client: Client | None,
    namespace_index: int | None,
) -> None:
    stripped = command_line.strip()
    if not stripped:
        return

    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        log(instance_name, f"command parse error: {exc}")
        return

    if not tokens:
        return

    command = tokens[0].lower()

    if command in {"help", "?"}:
        log(instance_name, "interactive commands: query [node-path ...], help")
        return

    if command != "query":
        log(instance_name, f"unknown interactive command: {tokens[0]!r}")
        log(instance_name, "interactive commands: query [node-path ...], help")
        return

    if client is None or namespace_index is None:
        log(instance_name, "query requested while the client is not connected")
        return

    paths = tokens[1:] or DEFAULT_QUERY_PATHS
    nodes: list[tuple[str, object]] = []

    for path in paths:
        try:
            node = await resolve_node(client, namespace_index, path)
        except Exception as exc:
            log(instance_name, f"query {path} failed: {exc!r}")
            continue

        nodes.append((path, node))

    if nodes:
        await print_requested_nodes(instance_name, nodes)


async def drain_interactive_commands(
    instance_name: str,
    command_queue: queue_module.SimpleQueue[str] | None,
    client: Client | None,
    namespace_index: int | None,
) -> None:
    if command_queue is None:
        return

    while True:
        try:
            command_line = command_queue.get_nowait()
        except queue_module.Empty:
            return

        await handle_interactive_command(instance_name, command_line, client, namespace_index)


async def sleep_with_interactive_commands(
    duration: float,
    instance_name: str,
    command_queue: queue_module.SimpleQueue[str] | None,
    client: Client | None,
    namespace_index: int | None,
) -> None:
    deadline = time.monotonic() + duration

    while True:
        await drain_interactive_commands(instance_name, command_queue, client, namespace_index)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return

        await asyncio.sleep(min(0.2, remaining))


async def resolve_demo_nodes(client: Client, namespace_index: int):
    demo_object = await client.nodes.objects.get_child([f"{namespace_index}:CommDevDemo"])
    heartbeat_node = await demo_object.get_child([f"{namespace_index}:Heartbeat"])
    command_node = await demo_object.get_child([f"{namespace_index}:Command"])
    ack_node = await demo_object.get_child([f"{namespace_index}:Ack"])
    return heartbeat_node, command_node, ack_node


async def wait_for_ack(instance_name: str, ack_node, expected_ack: str, ack_timeout: float) -> str:
    deadline = time.monotonic() + ack_timeout

    while time.monotonic() < deadline:
        current_ack = await ack_node.read_value()
        if current_ack == expected_ack:
            return current_ack

        await asyncio.sleep(0.5)

    raise TimeoutError(f"{instance_name} timed out waiting for ack={expected_ack!r}")


async def run_client(args: argparse.Namespace) -> None:
    log(args.instance_name, f"starting endpoint={args.endpoint} namespace={args.namespace} log_level={args.log_level}")
    log(args.instance_name, "interactive commands: query [node-path ...], help")

    command_queue = start_stdin_reader(args.instance_name)
    sequence = 1

    while True:
        try:
            async with Client(url=args.endpoint, timeout=args.timeout) as client:
                namespace_index = await resolve_namespace_index(client, args.namespace)
                heartbeat_node, command_node, ack_node = await resolve_demo_nodes(client, namespace_index)

                log(args.instance_name, "connected to peer")
                await drain_interactive_commands(args.instance_name, command_queue, client, namespace_index)

                while True:
                    await drain_interactive_commands(args.instance_name, command_queue, client, namespace_index)

                    heartbeat = await heartbeat_node.read_value()
                    command = f"{args.instance_name}-ping-{sequence}"
                    expected_ack = f"ack:{command}"

                    await command_node.write_value(command)
                    log(args.instance_name, f"wrote command={command!r} peer_heartbeat={heartbeat}")

                    ack = await wait_for_ack(args.instance_name, ack_node, expected_ack, args.ack_timeout)
                    log(args.instance_name, f"verified ack={ack!r}")

                    sequence += 1
                    await sleep_with_interactive_commands(
                        args.transaction_interval,
                        args.instance_name,
                        command_queue,
                        client,
                        namespace_index,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log(
                args.instance_name,
                f"connection cycle failed: {exc!r}; retrying in {args.connect_retry_seconds}s",
            )
            await sleep_with_interactive_commands(
                args.connect_retry_seconds,
                args.instance_name,
                command_queue,
                None,
                None,
            )


async def browse_nodes(args: argparse.Namespace) -> None:
    async with Client(url=args.endpoint, timeout=args.timeout) as client:
        namespace_index = await resolve_namespace_index(client, args.namespace)
        node = await resolve_node(client, namespace_index, args.start_path)
        log(args.instance_name, f"browsing start_path={args.start_path!r} depth={args.depth}")
        await print_tree(args.instance_name, node, args.depth, include_values=args.include_values)


async def read_nodes(args: argparse.Namespace) -> None:
    async with Client(url=args.endpoint, timeout=args.timeout) as client:
        namespace_index = await resolve_namespace_index(client, args.namespace)
        nodes = [(path, await resolve_node(client, namespace_index, path)) for path in args.paths]
        await print_requested_nodes(args.instance_name, nodes)


def main() -> None:
    args = parse_args()

    if args.command == "run":
        asyncio.run(run_client(args))
        return

    if args.command == "browse":
        asyncio.run(browse_nodes(args))
        return

    if args.command == "read":
        asyncio.run(read_nodes(args))
        return

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
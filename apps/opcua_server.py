#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import os
import time
from datetime import datetime, timezone

from asyncua import Server, ua


def env_default(name: str, fallback: str) -> str:
    return os.environ.get(name, fallback)


def log(instance_name: str, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] [{instance_name}] [server] {message}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CommDev sample OPC UA server")
    parser.add_argument("command", nargs="?", choices=["serve"], default="serve")
    parser.add_argument("--instance-name", default=env_default("COMM_INSTANCE_NAME", "board-a"))
    parser.add_argument("--endpoint", default=env_default("COMM_ENDPOINT", "opc.tcp://192.168.10.10:4840"))
    parser.add_argument("--namespace", default=env_default("OPCUA_NAMESPACE", "urn:commdev:opcua"))
    parser.add_argument("--port", type=int, default=int(env_default("COMM_PORT", "4840")))
    parser.add_argument("--log-level", default=env_default("COMM_LOG_LEVEL", "info"))
    parser.add_argument("--heartbeat-interval", type=float, default=1.0)
    parser.add_argument("--activity-timeout", type=float, default=8.0)
    return parser


async def serve(args: argparse.Namespace) -> None:
    server = Server()
    await server.init()
    server.set_endpoint(args.endpoint)
    server.set_server_name(f"{args.instance_name} sample OPC UA server")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])

    namespace_index = await server.register_namespace(args.namespace)
    demo_object = await server.nodes.objects.add_object(namespace_index, "CommDevDemo")
    heartbeat_node = await demo_object.add_variable(namespace_index, "Heartbeat", 0)
    command_node = await demo_object.add_variable(namespace_index, "Command", "bootstrap")
    ack_node = await demo_object.add_variable(namespace_index, "Ack", "ack:bootstrap")

    await command_node.set_writable()

    heartbeat = 0
    last_command = await command_node.read_value()
    client_active = False
    last_activity_at: float | None = None

    log(
        args.instance_name,
        f"starting endpoint={args.endpoint} port={args.port} namespace={args.namespace} log_level={args.log_level}",
    )

    async with server:
        log(args.instance_name, "server online and waiting for client activity")

        while True:
            heartbeat += 1
            await heartbeat_node.write_value(heartbeat)

            current_command = await command_node.read_value()
            if current_command != last_command:
                await ack_node.write_value(f"ack:{current_command}")

                if not client_active:
                    log(args.instance_name, f"client activity detected via command channel: {current_command!r}")

                client_active = True
                last_activity_at = time.monotonic()
                last_command = current_command

            if (
                client_active
                and args.activity_timeout > 0
                and last_activity_at is not None
                and (time.monotonic() - last_activity_at) >= args.activity_timeout
            ):
                log(args.instance_name, "no recent client activity")
                client_active = False
                last_activity_at = None

            await asyncio.sleep(args.heartbeat_interval)


def main() -> None:
    args = build_parser().parse_args()

    if args.command != "serve":
        raise SystemExit(f"Unsupported command: {args.command}")

    asyncio.run(serve(args))


if __name__ == "__main__":
    main()
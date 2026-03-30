#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone

from asyncua import Client


INSTANCE_NAME = os.environ.get("OPC_INSTANCE_NAME", "opc-node-b")
PEER_ENDPOINT = os.environ.get("OPC_PEER_ENDPOINT", "opc.tcp://opc-node-a:4840")
NAMESPACE = os.environ.get("OPC_NAMESPACE", "urn:commdev:opcua")
LOG_LEVEL = os.environ.get("OPC_LOG_LEVEL", "info")
CONNECT_RETRY_SECONDS = 2
TRANSACTION_INTERVAL_SECONDS = 3
ACK_TIMEOUT_SECONDS = 10


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] [{INSTANCE_NAME}] [client] {message}", flush=True)


async def wait_for_ack(ack_node, expected_ack: str) -> str:
    deadline = time.monotonic() + ACK_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        current_ack = await ack_node.read_value()
        if current_ack == expected_ack:
            return current_ack

        await asyncio.sleep(0.5)

    raise TimeoutError(f"timed out waiting for ack={expected_ack!r}")


async def resolve_demo_nodes(client: Client):
    namespace_index = await client.get_namespace_index(NAMESPACE)
    demo_object = await client.nodes.objects.get_child([f"{namespace_index}:CommDevDemo"])
    heartbeat_node = await demo_object.get_child([f"{namespace_index}:Heartbeat"])
    command_node = await demo_object.get_child([f"{namespace_index}:Command"])
    ack_node = await demo_object.get_child([f"{namespace_index}:Ack"])
    return heartbeat_node, command_node, ack_node


async def main() -> None:
    log(f"starting peer_endpoint={PEER_ENDPOINT} namespace={NAMESPACE} log_level={LOG_LEVEL}")

    sequence = 1

    while True:
        try:
            async with Client(url=PEER_ENDPOINT, timeout=5) as client:
                log("connected to peer")
                heartbeat_node, command_node, ack_node = await resolve_demo_nodes(client)

                while True:
                    heartbeat = await heartbeat_node.read_value()
                    command = f"{INSTANCE_NAME}-ping-{sequence}"
                    expected_ack = f"ack:{command}"

                    await command_node.write_value(command)
                    log(f"wrote command={command!r} peer_heartbeat={heartbeat}")

                    ack = await wait_for_ack(ack_node, expected_ack)
                    log(f"verified ack={ack!r}")

                    sequence += 1
                    await asyncio.sleep(TRANSACTION_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log(f"connection cycle failed: {exc!r}; retrying in {CONNECT_RETRY_SECONDS}s")
            await asyncio.sleep(CONNECT_RETRY_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
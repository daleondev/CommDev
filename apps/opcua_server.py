#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from asyncua import Server, ua


INSTANCE_NAME = os.environ.get("OPC_INSTANCE_NAME", "opc-node-a")
ENDPOINT = os.environ.get("OPC_ENDPOINT", "opc.tcp://opc-node-a:4840")
NAMESPACE = os.environ.get("OPC_NAMESPACE", "urn:commdev:opcua")
PORT = int(os.environ.get("OPC_PORT", "4840"))
LOG_LEVEL = os.environ.get("OPC_LOG_LEVEL", "info")


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[{timestamp}] [{INSTANCE_NAME}] [server] {message}", flush=True)


async def main() -> None:
    server = Server()
    await server.init()
    server.set_endpoint(ENDPOINT)
    server.set_server_name(f"{INSTANCE_NAME} demo server")
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])

    namespace_index = await server.register_namespace(NAMESPACE)
    demo_object = await server.nodes.objects.add_object(namespace_index, "CommDevDemo")
    heartbeat_node = await demo_object.add_variable(namespace_index, "Heartbeat", 0)
    command_node = await demo_object.add_variable(namespace_index, "Command", "bootstrap")
    ack_node = await demo_object.add_variable(namespace_index, "Ack", "ack:bootstrap")

    await command_node.set_writable()

    heartbeat = 0
    last_command = await command_node.read_value()

    log(f"starting endpoint={ENDPOINT} port={PORT} namespace={NAMESPACE} log_level={LOG_LEVEL}")

    async with server:
        log("server online")

        while True:
            heartbeat += 1
            await heartbeat_node.write_value(heartbeat)

            current_command = await command_node.read_value()
            if current_command != last_command:
                ack_value = f"ack:{current_command}"
                await ack_node.write_value(ack_value)
                log(f"processed command={current_command!r} ack={ack_value!r}")
                last_command = current_command

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
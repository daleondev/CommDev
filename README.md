# CommDev OPC UA Devcontainer

This repository is prepared for a VS Code devcontainer plus a separate two-node Docker testbed for OPC UA integration work.

The setup is intentionally split in two parts:

- The devcontainer gives you a stable development environment with Python, Node.js, C and C++ toolchains, network diagnostics, and Docker CLI access.
- The testbed runs two copies of your application as `opc-node-a` and `opc-node-b` on the same Docker bridge network so they can talk to each other exactly like two deployed nodes.

## What is included

- `.devcontainer/devcontainer.json` wires VS Code into the workspace container.
- `.devcontainer/Dockerfile` installs a broad toolchain that fits common OPC UA stacks.
- `compose.testbed.yml` defines the two application containers.
- `scripts/testbed.sh` wraps the common Docker Compose commands.
- `scripts/start-opc-node.sh` injects per-node environment and launches your app wrapper.
- `scripts/run-opc-app.sh` now starts a small built-in Python demo.
- `apps/opcua_server.py` exposes a simple OPC UA server.
- `apps/opcua_client.py` connects to the peer server and verifies round-trips.

## Workflow

1. Open the folder in VS Code.
2. Reopen in the devcontainer.
3. Start the testbed with `./scripts/testbed.sh up`.
4. Watch both nodes with `./scripts/testbed.sh logs`.
5. Open shells with `./scripts/testbed.sh shell opc-node-a` or `./scripts/testbed.sh shell opc-node-b`.

The testbed containers bake the demo code into the image, so after changing the Python apps or scripts you should run `./scripts/testbed.sh rebuild`.

VS Code tasks are included for the same commands under the `Testbed:` prefix.

## Runtime contract

Each node receives a fixed set of environment variables:

- `OPC_INSTANCE_NAME`
- `OPC_BIND_HOST`
- `OPC_PORT`
- `OPC_ENDPOINT`
- `OPC_PEER_ENDPOINT`
- `OPC_DATA_DIR`
- `OPC_PKI_DIR`
- `OPC_NAMESPACE`
- `OPC_LOG_LEVEL`

The built-in demo uses `OPC_ROLE` to choose whether a node runs the server or the client.

Default endpoints are:

- `opc-node-a`: `opc.tcp://opc-node-a:4840`
- `opc-node-b`: `opc.tcp://opc-node-b:4841`

The devcontainer joins the same `commdev-opc-net` bridge network, so code you run inside VS Code can also reach both nodes by service name.

## Example runner shape

The default wiring is:

- `opc-node-a` runs the demo server.
- `opc-node-b` runs the demo client against `opc-node-a`.

If you want to replace the demo with your own implementation, update `scripts/run-opc-app.sh` with a shell wrapper around your real entrypoint. For example:

```bash
#!/usr/bin/env bash
set -euo pipefail

exec python -m your_package.main \
  --name "$OPC_INSTANCE_NAME" \
  --host "$OPC_BIND_HOST" \
  --port "$OPC_PORT" \
  --endpoint "$OPC_ENDPOINT" \
  --peer "$OPC_PEER_ENDPOINT"
```

The same pattern works for Node.js, CMake-built binaries, or any other runtime as long as this wrapper starts the process in the foreground.

## Verifying the demo

When the testbed is healthy, the logs should show:

- the server coming online on `opc.tcp://opc-node-a:4840`
- the client connecting to `opc-node-a`
- repeated `verified ack=...` messages from the client
- repeated `processed command=...` messages from the server

## Optional overrides

If you want different host ports, namespace, or log level, copy `.env.example` to `.env` and adjust the values there.
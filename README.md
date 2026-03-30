# CommDev OPC UA Devcontainer

This repository provides a VS Code devcontainer plus a two-node Docker testbed for OPC UA work.

The setup is intentionally split in two parts:

- The devcontainer gives you a stable development environment with Python, Node.js, C and C++ toolchains, network diagnostics, Docker CLI access, and tmux.
- The testbed runs two copies of your application as `opc-node-a` and `opc-node-b` on the same Docker bridge network so they can talk to each other like deployed nodes.

## What is included

- `.devcontainer/devcontainer.json` wires VS Code into the workspace container.
- `.devcontainer/Dockerfile` installs the common toolchain.
- `compose.testbed.yml` defines the two application containers.
- `scripts/testbed.sh` is the one live runner: it builds the images, starts both containers directly in tmux, and tears them down when you leave.
- `scripts/start-opc-node.sh` injects per-node environment and launches the foreground app wrapper.
- `scripts/run-opc-app.sh` starts the built-in demo server or client.
- `apps/opcua_server.py` exposes a continuously running OPC UA server.
- `apps/opcua_client.py` exposes a continuously running OPC UA client with an interactive `query` command.

## Workflow

1. Open the folder in VS Code.
2. Reopen in the devcontainer.
3. Start the live testbed with `./scripts/testbed.sh`.
4. A tmux window opens with the client on the left and the server on the right.
5. Type `query` in the left pane to print the demo nodes from the server.
6. Press `Ctrl+C` in either pane to stop that app. The tmux session closes and both live containers are cleaned up.

The testbed containers bake the demo code into the image, so after changing the Python apps or scripts you should run `./scripts/testbed.sh rebuild`.

VS Code tasks are included for the same commands under the `Testbed:` prefix. `Testbed: Run Live` is the normal entry point.

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

## Live Console

`./scripts/testbed.sh` creates one tmux window with a vertical split:

- left pane: the foreground client process
- right pane: the foreground server process

Nothing is started in detached mode. The pane commands themselves launch the containers, and leaving the tmux session cleans those live containers up.

The client pane accepts interactive commands while it keeps running:

- `query` prints `CommDevDemo/Heartbeat`, `CommDevDemo/Command`, and `CommDevDemo/Ack`
- `query CommDevDemo/Ack` prints a specific node
- `help` prints the available interactive commands

The standalone client subcommands still work if you want them:

- `python3 -u /workspace/apps/opcua_client.py browse --depth 2 --include-values`
- `python3 -u /workspace/apps/opcua_client.py read CommDevDemo/Heartbeat CommDevDemo/Command CommDevDemo/Ack`

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

When the testbed is healthy, the panes and logs should show:

- the server coming online on `opc.tcp://opc-node-a:4840`
- the client connecting to `opc-node-a`
- repeated `verified ack=...` messages from the client
- `query ... => ...` output when you type `query` in the left pane
- lightweight server-side client activity messages in the right pane

## Optional overrides

If you want different host ports, namespace, or log level, copy `.env.example` to `.env` and adjust the values there.
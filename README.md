# CommDev Communication Devcontainer

This repository is a generic two-application communication testbed that runs inside a VS Code devcontainer and opens both applications side by side in a live tmux session.

The live testbed only needs the Docker CLI.

The framework is generic:

- two application containers, `board-a` and `board-b`
- one live runner script, `scripts/testbed.sh`
- one shared private network with fixed IP addresses
- one current sample application pair, the OPC UA server and client in `apps/`

The current sample apps are OPC UA only for demonstration. The framework around them is intended to stay generic so later application pairs, including STM32 emulations, can reuse the same runner and network model.

## What is included

- `.devcontainer/devcontainer.json` connects the workspace container to the shared communication network.
- `.devcontainer/Dockerfile` installs the common toolchain.
- `scripts/testbed.sh` builds the testbed image, creates `board-a` and `board-b`, and opens the live tmux session.
- `scripts/start-board.sh` starts a board container in the foreground.
- `scripts/run-sample-app.sh` dispatches to the current sample server or client.
- `apps/opcua_server.py` and `apps/opcua_client.py` are the current sample applications.

## Live workflow

1. Open the folder in VS Code.
2. Reopen in the devcontainer.
3. Run `./scripts/testbed.sh`.
4. A tmux window opens with `board-b` on the left and `board-a` on the right.
5. Type `query` in the left pane to read the sample OPC UA nodes from the peer.
6. Press `Ctrl+C` in either pane to stop that board. The tmux session closes and the live testbed containers are removed.

Nothing is left running in detached mode. If you detach from tmux, the script immediately cleans the live containers up.

After changing scripts or sample apps, run `./scripts/testbed.sh rebuild`.

Container names are derived from `COMMDEV_TESTBED_NAME`, so the default containers are `commdev-comms-testbed-board-a` and `commdev-comms-testbed-board-b`.

## Static network model

The live boards run on a fixed private Docker network:

- network: `commdev-comms-net`
- subnet: `192.168.10.0/24`
- gateway: `192.168.10.1`
- `board-a`: `192.168.10.10`
- `board-b`: `192.168.10.11`

There is no host port publishing. The sample apps communicate only over the shared board network, which makes the setup closer to real separate devices.

## Runtime contract

The framework passes these generic environment variables to each board:

- `COMM_ROLE`
- `COMM_INSTANCE_NAME`
- `COMM_PORT`
- `COMM_ENDPOINT`
- `COMM_PEER_ENDPOINT`
- `COMM_LOG_LEVEL`

The current sample apps also use one sample-specific variable:

- `OPCUA_NAMESPACE`

Current defaults are:

- `board-a` endpoint: `opc.tcp://192.168.10.10:4840`
- `board-b` endpoint: `opc.tcp://192.168.10.11:4840`

`board-b` currently acts as the client sample and connects to `board-a`.

## Current sample app behavior

The sample client keeps running in the foreground and accepts interactive commands:

- `query` prints `CommDevDemo/Heartbeat`, `CommDevDemo/Command`, and `CommDevDemo/Ack`
- `query CommDevDemo/Ack` prints a specific node
- `help` prints the available interactive commands

The sample server stays in the foreground and logs startup plus detected peer activity.

The standalone sample commands still work if you need them inside a board container:

- `python3 -u /workspace/apps/opcua_client.py browse --depth 2 --include-values`
- `python3 -u /workspace/apps/opcua_client.py read CommDevDemo/Heartbeat CommDevDemo/Command CommDevDemo/Ack`

## Tasks

The VS Code tasks are:

- `Comms: Run Live`
- `Comms: Rebuild Live`
- `Comms: Down`

## Replacing the sample apps later

When you swap the OPC UA sample out for another application pair, the main handoff point is `scripts/run-sample-app.sh`. The goal is to keep the board names, live tmux runner, and static network model intact while only changing the applications that each board starts.
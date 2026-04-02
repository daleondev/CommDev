#!/usr/bin/env python3

from __future__ import annotations

import subprocess


def main() -> int:
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", "/workspaces/CommDev"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print(
        "Devcontainer ready.\n\n"
        "Next steps:\n"
        "1. Replace scripts/run_sample_app.py with the command that starts your sample communication application.\n"
        "2. Start the live communication testbed with python3 ./scripts/testbed.py run.\n"
        "3. Stop the live testbed with python3 ./scripts/testbed.py down."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
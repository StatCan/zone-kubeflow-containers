#!/usr/bin/env python3
"""
Persist a user's default OneLake workspace/lakehouse selection.

This stores configuration in ~/.onelake_config so future notebook restarts
can remount OneLake without asking the user again.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ENDPOINT = "https://onelake.dfs.fabric.microsoft.com"
CONFIG_FILE = Path.home() / ".onelake_config"
STATUS_FILE = Path.home() / ".onelake_status"
MOUNT_PATH = Path.home() / "onelake"


def _load_saved():
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_config(workspace, lakehouse):
    CONFIG_FILE.write_text(
        json.dumps(
            {
                "workspace": workspace,
                "lakehouse": lakehouse,
            }
        )
    )


def _write_status(workspace, lakehouse, mounted=None):
    payload = {
        "configured": True,
        "workspace": workspace,
        "lakehouse": lakehouse,
        "endpoint": ENDPOINT,
    }
    if mounted is not None:
        payload["mounted"] = mounted
        if mounted:
            payload["mount_path"] = str(MOUNT_PATH)
    STATUS_FILE.write_text(json.dumps(payload))


def _prompt_value(label, current):
    suffix = f" [{current}]" if current else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or current


def _mount_now(workspace, lakehouse):
    env = os.environ.copy()
    env["ONELAKE_WORKSPACE"] = workspace
    env["ONELAKE_LAKEHOUSE"] = lakehouse

    result = subprocess.run(
        ["bash", "/etc/cont-init.d/04-onelake-mount"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    mounted = subprocess.run(
        ["mountpoint", "-q", str(MOUNT_PATH)],
        check=False,
    ).returncode == 0
    return result, mounted


def main():
    parser = argparse.ArgumentParser(
        description="Save a default OneLake workspace/lakehouse for future notebook startups."
    )
    parser.add_argument("workspace", nargs="?", help="OneLake workspace GUID or name")
    parser.add_argument("lakehouse", nargs="?", help="OneLake lakehouse GUID or name")
    parser.add_argument(
        "--mount-now",
        action="store_true",
        help="Attempt a OneLake mount immediately after saving the config",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Print the currently saved OneLake configuration",
    )
    args = parser.parse_args()

    saved = _load_saved()

    if args.show:
        if saved:
            print(json.dumps(saved, indent=2))
            return 0
        print("No OneLake configuration saved yet.")
        return 0

    workspace = args.workspace or _prompt_value("Workspace", saved.get("workspace", ""))
    lakehouse = args.lakehouse or _prompt_value("Lakehouse", saved.get("lakehouse", ""))

    if not workspace or not lakehouse:
        print("Workspace and lakehouse are both required.", file=sys.stderr)
        return 1

    _write_config(workspace, lakehouse)
    _write_status(workspace, lakehouse, mounted=MOUNT_PATH.is_mount())

    print(f"Saved OneLake default workspace '{workspace}' and lakehouse '{lakehouse}'.")
    print(f"Config file: {CONFIG_FILE}")

    if not args.mount_now:
        print("Future notebook restarts will reuse this saved config automatically.")
        print("Run 'onelake-configure --mount-now' if you want to try mounting now.")
        return 0

    result, mounted = _mount_now(workspace, lakehouse)
    _write_status(workspace, lakehouse, mounted=mounted)

    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)

    if mounted:
        print(f"OneLake mounted at {MOUNT_PATH}")
    else:
        print("OneLake was not mounted. Check /tmp/blobfuse2-mount.log for details.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

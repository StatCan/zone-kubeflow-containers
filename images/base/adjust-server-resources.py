#!/usr/bin/env python3
"""
Automate calling kubectl to adjust server resources.
"""

import argparse
import os


def get_cpu_cores(cpu_request: float, cpu_limit: float | None) -> tuple:
    """
    Get CPU cores specified by user.
    """

    # If limit missing, set to request.
    if cpu_limit is None:
        cpu_limit = cpu_request

    # Convert to int if possible.
    if cpu_request == round(cpu_request, 0):
        cpu_request = int(cpu_request)

    if cpu_limit == round(cpu_limit, 0):
        cpu_limit = int(cpu_limit)

    # Print the values.
    print(f"CPU requested: {cpu_request} CPU cores")
    print(f"CPU limit: {cpu_limit} CPU cores")

    # Validate the values.
    if cpu_request < 0.5:
        raise ValueError("Cannot have less than 0.1 CPU cores specified.")

    if cpu_limit > 14:
        raise ValueError("Cannot have more than 14 CPU cores specified.")

    if cpu_request > cpu_limit:
        raise ValueError("Cannot have requested CPU cores be greater than limit.")

    return cpu_request, cpu_limit


def get_ram(ram_request: float, ram_limit: float | None) -> tuple:
    """
    Get RAM in GiB specified by user.
    """

    # If limit missing, set to request.
    if ram_limit is None:
        ram_limit = ram_request

    # Convert to int if possible.
    if ram_request == round(ram_request, 0):
        ram_request = int(ram_request)

    if ram_limit == round(ram_limit, 0):
        ram_limit = int(ram_limit)

    # Print the values.
    print(f"RAM requested: {ram_request} GiB RAM")
    print(f"RAM limit: {ram_limit} GiB RAM")

    # Validate the values.
    if ram_request < 1:
        raise ValueError("Cannot have less than 1 GiB of RAM specified.")

    if ram_limit > 48:
        raise ValueError("Cannot have more than 48 GiB of RAM specified.")

    if ram_request > ram_limit:
        raise ValueError("Cannot have requested RAM be greater than limit.")

    return ram_request, ram_limit


def get_cmd(
    cpu_request: int | float,
    cpu_limit: int | float,
    ram_request: int | float,
    ram_limit: int | float,
):
    """
    Get kubectl command to execute to adjust current notebook server resources.
    """
    main_cmd = (
        "kubectl patch notebook ${NB_PREFIX##*/} -n $NB_NAMESPACE --type='json' -p="
    )
    op_cpu_limit = (
        "    "
        '{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", '
        f'"value":"{cpu_limit}"'
        "}"
    )
    op_ram_limit = (
        "    "
        '{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", '
        f'"value":"{ram_limit}Gi"'
        "}"
    )
    op_cpu_req = (
        "    "
        '{"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", '
        f'"value":"{cpu_request}"'
        "}"
    )
    op_ram_req = (
        "    "
        '{"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", '
        f'"value":"{ram_request}Gi"'
        "}"
    )
    return (
        f"{main_cmd}'[\n{op_cpu_limit},\n{op_ram_limit},\n{op_cpu_req},\n{op_ram_req}]'"
    )


def adjust_server(
    cpu_request: float | None,
    ram_request: float | None,
    cpu_limit: float | None,
    ram_limit: float | None,
):
    """
    Function that adjusts the server resources, to specified amount of CPU cores and RAM.
    """

    print("Adjust notebook server to user specification...")

    cpu_request, cpu_limit = get_cpu_cores(cpu_request, cpu_limit)
    ram_request, ram_limit = get_ram(ram_request, ram_limit)

    cmd = get_cmd(
        cpu_limit=cpu_limit,
        cpu_request=cpu_request,
        ram_limit=ram_limit,
        ram_request=ram_request,
    )
    print("Execute command:", cmd)

    r = os.system(cmd)
    print("Return code of kubectl command:", r)


def main():
    """
    Function invoked when run from command line.
    """

    cmd_parser = argparse.ArgumentParser(
        description=(
            "Adjust notebook server resources."
            " Specify number of CPU cores (first parameter) and"
            " RAM in GiB (second parameter) notebook should have."
            " Notebook server will restart with these."
        )
    )
    cmd_parser.add_argument(
        "cpu_request",
        type=float,
        help="Requested number of CPU cores for notebook server. Must be between 0.1 and 14.",
    )
    cmd_parser.add_argument(
        "ram_request",
        type=float,
        help="Requested RAM in GiBs for notebook server. Must be between 1 and 48.",
    )
    cmd_parser.add_argument(
        "cpu_limit",
        type=float,
        nargs="?",
        help=(
            "Optional limit on number of CPU cores for notebook server, default to requested."
            " Must be between 0.5 and 14, and must be at least cpu_request."
        ),
    )
    cmd_parser.add_argument(
        "ram_limit",
        type=float,
        nargs="?",
        help=(
            "Optional limit on RAM in GiBs for notebook server, default to requested."
            " Must be between 1 and 48, and must be at least ram_request."
        ),
    )
    args = cmd_parser.parse_args()

    adjust_server(args.cpu_request, args.ram_request, args.cpu_limit, args.ram_limit)


if __name__ == "__main__":
    main()

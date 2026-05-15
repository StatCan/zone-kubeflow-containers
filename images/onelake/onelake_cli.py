"""Command line interface for delegated OneLake access."""

import argparse
import sys

import onelake_utils as onelake


def _cmd_status(_args):
    onelake.info()
    return 0


def _cmd_doctor(args):
    checks = onelake.doctor(check_access=args.live)
    for check in checks:
        state = "OK" if check["ok"] else "MISSING"
        print(f"{state:7} {check['name']}: {check['detail']}")
    return 0 if all(check["ok"] for check in checks) else 1


def _cmd_configure(args):
    onelake.configure(args.workspace, args.lakehouse)
    print("OneLake configuration saved.")
    return 0


def _cmd_ls(args):
    for entry in onelake.ls(args.path):
        kind = "DIR " if entry["is_directory"] else "FILE"
        print(f"{kind} {entry['size']:>10} {entry['name']}")
    return 0


def _cmd_cat(args):
    data = onelake.read(args.path)
    sys.stdout.buffer.write(data)
    return 0


def _cmd_cp(args):
    src_is_remote = args.source.startswith("onelake:")
    dst_is_remote = args.destination.startswith("onelake:")
    if src_is_remote == dst_is_remote:
        raise SystemExit("cp requires exactly one onelake: path")

    if src_is_remote:
        onelake.download(args.source[len("onelake:"):], args.destination)
    else:
        onelake.upload(args.source, args.destination[len("onelake:"):])
    return 0


def _cmd_append(args):
    data = sys.stdin.buffer.read()
    onelake.append(args.path, data)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="onelake")
    parser.add_argument(
        "--access-token-stdin",
        action="store_true",
        help="read a temporary delegated OneLake access token from stdin for this command only",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.set_defaults(func=_cmd_status)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--live", action="store_true", help="also attempt a live OneLake directory listing")
    doctor.set_defaults(func=_cmd_doctor)

    configure = subparsers.add_parser("configure")
    configure.add_argument("workspace")
    configure.add_argument("lakehouse")
    configure.set_defaults(func=_cmd_configure)

    list_parser = subparsers.add_parser("ls")
    list_parser.add_argument("path", nargs="?", default="/")
    list_parser.set_defaults(func=_cmd_ls)

    cat = subparsers.add_parser("cat")
    cat.add_argument("path")
    cat.set_defaults(func=_cmd_cat)

    copy = subparsers.add_parser("cp")
    copy.add_argument("source")
    copy.add_argument("destination")
    copy.set_defaults(func=_cmd_cp)

    append = subparsers.add_parser("append")
    append.add_argument("path")
    append.set_defaults(func=_cmd_append)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.access_token_stdin:
        if args.command == "append":
            parser.error("--access-token-stdin cannot be combined with append because append reads stdin")
        onelake.use_ephemeral_access_token(sys.stdin.read())
    return args.func(args)

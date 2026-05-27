"""Command line interface for OneLake access."""

import argparse
import sys

import onelake


def _cmd_status(args):
    current = onelake.status(live=args.live)
    state = "ready" if current["ready"] else "not ready"
    print(f"OneLake status: {state}")
    print(f"Workspace: {current['workspace'] or 'N/A'}")
    print(f"Lakehouse: {current['lakehouse'] or 'N/A'}")
    print(f"Endpoint: {current['endpoint']}")
    print(f"Broker: {current['broker_url']}")
    print("Token storage: in-memory only; re-requested from AuthService after restart")
    if current["missing"]:
        print(f"Missing: {', '.join(current['missing'])}")
    if args.live:
        live = current.get("live", {"ok": False, "detail": "not checked"})
        print(f"Live: {'OK' if live['ok'] else 'FAILED'} - {live['detail']}")
        return 0 if current["ready"] and live["ok"] else 1
    return 0 if current["ready"] else 1


def _cmd_connect(args):
    onelake.connect(args.workspace, args.lakehouse)
    print("OneLake configuration saved.")
    return 0


def _cmd_ls(args):
    for entry in onelake.ls(args.path):
        kind = "DIR " if entry["is_directory"] else "FILE"
        print(f"{kind} {entry['size']:>10} {entry['name']}")
    return 0


def _cmd_cat(args):
    sys.stdout.buffer.write(onelake.read(args.path))
    return 0


def _cmd_write(args):
    onelake.write(args.path, sys.stdin.buffer.read())
    return 0


def _cmd_get(args):
    onelake.download(args.remote_path, args.local_path)
    return 0


def _cmd_put(args):
    onelake.upload(args.local_path, args.remote_path)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="onelake")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--live", action="store_true", help="attempt a live OneLake Files listing")
    status.set_defaults(func=_cmd_status)

    connect = subparsers.add_parser("connect")
    connect.add_argument("workspace")
    connect.add_argument("lakehouse")
    connect.set_defaults(func=_cmd_connect)

    list_parser = subparsers.add_parser("ls")
    list_parser.add_argument("path", nargs="?", default="/")
    list_parser.set_defaults(func=_cmd_ls)

    cat = subparsers.add_parser("cat")
    cat.add_argument("path")
    cat.set_defaults(func=_cmd_cat)

    write = subparsers.add_parser("write")
    write.add_argument("path")
    write.set_defaults(func=_cmd_write)

    get = subparsers.add_parser("get")
    get.add_argument("remote_path")
    get.add_argument("local_path")
    get.set_defaults(func=_cmd_get)

    put = subparsers.add_parser("put")
    put.add_argument("local_path")
    put.add_argument("remote_path")
    put.set_defaults(func=_cmd_put)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Command line interface for the Zone AuthService token helper."""

import argparse
import sys

import zonetokenbroker


def _cmd_get(args):
    token = zonetokenbroker.get_access_token(
        args.scope,
        broker_url=args.broker_url,
        token_path=args.token_path,
        token_file=args.token_file,
        allow_insecure_broker=args.allow_insecure_broker,
    )
    print(token)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="zone-token")
    subparsers = parser.add_subparsers(dest="command", required=True)

    get = subparsers.add_parser("get", help="get an access token from AuthService")
    get.add_argument("--scope", required=True, help="delegated scope to request, for example https://storage.azure.com/.default")
    get.add_argument("--broker-url", help="override ZONE_TOKEN_BROKER_URL")
    get.add_argument("--token-path", help="override ZONE_TOKEN_BROKER_TOKEN_PATH")
    get.add_argument("--token-file", help="override ZONE_TOKEN_BROKER_TOKEN_FILE")
    get.add_argument("--allow-insecure-broker", action="store_const", const=True, default=None, help=argparse.SUPPRESS)
    get.set_defaults(func=_cmd_get)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except zonetokenbroker.TokenBrokerError as error:
        print(f"zone-token: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

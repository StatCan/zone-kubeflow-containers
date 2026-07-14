"""Localhost App Service managed-identity endpoint backed by the Zone token broker."""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import zone_token_broker

# Loopback only: the shim mints user-delegated tokens, so it must never be
# reachable from outside the single-user pod.
BIND_ADDRESS = "127.0.0.1"
DEFAULT_PORT = 8901
PORT_ENV = "ZONE_MSI_PORT"
IDENTITY_HEADER_ENV = "IDENTITY_HEADER"


class MsiRequestHandler(BaseHTTPRequestHandler):
    """Speak the App Service 2019-08-01 managed-identity protocol.

    azure-identity and MSAL (so `az login --identity` too) detect the
    IDENTITY_ENDPOINT/IDENTITY_HEADER env vars and GET this endpoint with
    api-version and resource query params plus an X-IDENTITY-HEADER header.
    Every response is answered from zone_token_broker, which performs the
    on-behalf-of exchange (and caching) through AuthService.
    """

    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self._handle(include_body=True)

    # Probes may HEAD the endpoint; answer with headers only.
    def do_HEAD(self):
        self._handle(include_body=False)

    def _handle(self, include_body):
        expected_header = os.environ.get(IDENTITY_HEADER_ENV)
        if expected_header and self.headers.get("X-IDENTITY-HEADER") != expected_header:
            self._send_json(
                401,
                {"error": "unauthorized", "error_description": "X-IDENTITY-HEADER mismatch"},
                include_body,
            )
            return

        query = parse_qs(urlparse(self.path).query)
        resource = (query.get("resource") or [""])[0].strip()
        if not resource:
            self._send_json(
                400,
                {"error": "invalid_request", "error_description": "resource query parameter is required"},
                include_body,
            )
            return

        # There is exactly one identity (the pod user), so the api-version and
        # the client_id/object_id/mi_res_id selectors are accepted but ignored.
        scope = resource.rstrip("/") + "/.default"
        try:
            token = zone_token_broker.get_token(scope)
        except Exception as error:
            self._send_json(
                500,
                {"error": "broker_error", "error_description": zone_token_broker._redact(error)},
                include_body,
            )
            return

        # expires_on must be numeric epoch seconds as a string: both MSAL and
        # azure-identity call int() on it.
        self._send_json(
            200,
            {
                "access_token": token.access_token,
                "expires_on": str(int(token.expires_on)),
                "token_type": "Bearer",
                "resource": resource,
            },
            include_body,
        )

    def _send_json(self, status, payload, include_body):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    # One terse line per request to stderr; never log query strings verbatim
    # so future protocol changes cannot leak secrets into service logs.
    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        print(f"zone-msi-shim: {format % args}", file=sys.stderr)

    def log_request(self, code="-", size="-"):
        self.log_message("%s %s %s", self.command, urlparse(self.path).path, code)


def main():
    port = int(os.environ.get(PORT_ENV, DEFAULT_PORT))
    server = ThreadingHTTPServer((BIND_ADDRESS, port), MsiRequestHandler)
    print(f"zone-msi-shim: serving managed-identity tokens on http://{BIND_ADDRESS}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
test_zone_msi
~~~~~~~~~~~~~
Test the managed-identity endpoint shim (zone-msi-shim).

The mid image emulates the App Service managed-identity protocol so that
`az login --identity`, DefaultAzureCredential, and ManagedIdentityCredential
authenticate as the pod user through the Zone token broker. This test
verifies that:

- zone-msi-shim is installed and IDENTITY_ENDPOINT/IDENTITY_HEADER are set
- the shim translates an MSI token request into a broker call and returns
  the App Service response shape (numeric expires_on, Bearer token_type)
- requests with a wrong X-IDENTITY-HEADER are rejected with 401
- azure-identity's ManagedIdentityCredential works end-to-end against the
  shim (skipped when azure-identity is not installed in the image)

The broker itself is mocked with a stdlib HTTP server inside the container,
so no cluster AuthService is needed.

Example:

    $ make test/mid

    # [...]
    # test/mid/test_zone_msi.py::test_zone_msi_shim_installed
    # test/mid/test_zone_msi.py::test_zone_msi_shim_returns_broker_token
"""

import json
import logging
import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)

# Distinct ports so the probe never collides with the s6-managed shim on 8901.
MOCK_BROKER_PORT = 18902
PROBE_SHIM_PORT = 18903

# Bash driver: mock broker + private shim instance + curl probes. Written via
# heredoc (like test_parquet) to avoid shell quoting issues, and printing
# MARKER: lines that the test parses from the combined output.
PROBE_SCRIPT = (
    "set -u\n"
    "cat > /tmp/zone_msi_mock_broker.py <<'PYEOF'\n"
    "import json, time\n"
    "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
    "class Handler(BaseHTTPRequestHandler):\n"
    "    def do_GET(self):\n"
    "        body = json.dumps({'access_token': 'testtoken123', 'expires_on': int(time.time()) + 3600}).encode()\n"
    "        self.send_response(200)\n"
    "        self.send_header('Content-Type', 'application/json')\n"
    "        self.send_header('Content-Length', str(len(body)))\n"
    "        self.end_headers()\n"
    "        self.wfile.write(body)\n"
    "    def log_message(self, *args):\n"
    "        pass\n"
    f"HTTPServer(('127.0.0.1', {MOCK_BROKER_PORT}), Handler).serve_forever()\n"
    "PYEOF\n"
    "python3 /tmp/zone_msi_mock_broker.py &\n"
    "BROKER_PID=$!\n"
    f"AUTHSERVICE_BROKER_URL=http://127.0.0.1:{MOCK_BROKER_PORT} "
    f"ZONE_MSI_PORT={PROBE_SHIM_PORT} IDENTITY_HEADER=zone-test zone-msi-shim &\n"
    "SHIM_PID=$!\n"
    "trap 'kill $BROKER_PID $SHIM_PID 2>/dev/null' EXIT\n"
    f"MSI_URL='http://127.0.0.1:{PROBE_SHIM_PORT}/msi/token"
    "?api-version=2019-08-01&resource=https://management.azure.com/'\n"
    "for _ in $(seq 1 30); do\n"
    "  curl -sf -H 'X-IDENTITY-HEADER: zone-test' \"$MSI_URL\" > /tmp/zone_msi_token.json && break\n"
    "  sleep 0.5\n"
    "done\n"
    "echo \"TOKEN_RESPONSE:$(cat /tmp/zone_msi_token.json)\"\n"
    "echo \"MISMATCH_STATUS:$(curl -s -o /dev/null -w '%{http_code}' -H 'X-IDENTITY-HEADER: wrong' \"$MSI_URL\")\"\n"
    "if python3 -c 'import azure.identity' 2>/dev/null; then\n"
    f"  IDENTITY_ENDPOINT=http://127.0.0.1:{PROBE_SHIM_PORT}/msi/token "
    "IDENTITY_HEADER=zone-test python3 - <<'PYEOF'\n"
    "from azure.identity import ManagedIdentityCredential\n"
    "token = ManagedIdentityCredential().get_token('https://management.azure.com/.default')\n"
    "assert token.token == 'testtoken123', token.token\n"
    "print('AZURE_IDENTITY:OK')\n"
    "PYEOF\n"
    "else\n"
    "  echo 'AZURE_IDENTITY:ABSENT'\n"
    "fi\n"
)


def _marker_value(output, marker):
    for line in output.splitlines():
        if line.startswith(marker):
            return line[len(marker):]
    return None


@pytest.mark.integration
def test_zone_msi_shim_installed(container):
    """Test that the shim binary and MSI discovery env vars are in the image.

    azure-identity and MSAL only speak the App Service protocol when both
    IDENTITY_ENDPOINT and IDENTITY_HEADER are present, so these env vars are
    as load-bearing as the shim binary itself.
    """
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("zone-msi-shim not expected in base image")

    LOGGER.info("Testing zone-msi-shim installation...")

    container.run()

    success, output = wait_for_exec_success(
        container=container,
        command=["which", "zone-msi-shim"],
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(
            f"zone-msi-shim not found on PATH within timeout. Output: {output}"
        )

    result = container.container.exec_run(
        ["sh", "-c", "printenv IDENTITY_ENDPOINT && printenv IDENTITY_HEADER"]
    )
    env_output = result.output.decode('utf-8')
    assert result.exit_code == 0, f"IDENTITY_ENDPOINT/IDENTITY_HEADER not set: {env_output}"

    lines = env_output.splitlines()
    assert len(lines) >= 2, f"Unexpected printenv output: {env_output}"
    identity_endpoint, identity_header = lines[0].strip(), lines[1].strip()
    LOGGER.info(f"IDENTITY_ENDPOINT={identity_endpoint} IDENTITY_HEADER={identity_header}")

    assert identity_endpoint.startswith("http://127.0.0.1:"), \
        f"IDENTITY_ENDPOINT should point at loopback: {identity_endpoint}"
    assert identity_header, "IDENTITY_HEADER should be non-empty"

    LOGGER.info("zone-msi-shim installation test passed successfully")


@pytest.mark.integration
def test_zone_msi_shim_returns_broker_token(container):
    """Test the shim end-to-end against a mock broker inside the container.

    Starts a stdlib HTTP server standing in for AuthService, points a private
    shim instance at it, then asserts the App Service response shape via curl
    and (when azure-identity is installed) via ManagedIdentityCredential.
    """
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("zone-msi-shim not expected in base image")

    LOGGER.info("Testing zone-msi-shim token exchange against a mock broker...")

    container.run()

    success, output = wait_for_exec_success(
        container=container,
        command=["which", "zone-msi-shim"],
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(
            f"Container failed to be ready for execution within timeout. Output: {output}"
        )

    # Execute via heredoc to prevent shell quoting issues
    command = [
        "bash", "-c",
        f"cat << 'EOF' > /tmp/zone_msi_probe.sh\n{PROBE_SCRIPT}\nEOF\nbash /tmp/zone_msi_probe.sh"
    ]

    result = container.container.exec_run(command)
    probe_output = result.output.decode('utf-8')

    if result.exit_code != 0:
        LOGGER.error(f"zone-msi probe failed: {probe_output}")
        assert False, f"zone-msi probe failed with exit code {result.exit_code}: {probe_output}"

    token_response = _marker_value(probe_output, "TOKEN_RESPONSE:")
    assert token_response, f"No token response from shim: {probe_output}"
    payload = json.loads(token_response)
    assert payload.get("access_token") == "testtoken123", f"Unexpected token payload: {payload}"
    assert payload.get("token_type") == "Bearer", f"Unexpected token payload: {payload}"
    # MSAL and azure-identity call int() on expires_on, so it must be numeric.
    assert str(int(payload["expires_on"])) == payload["expires_on"], \
        f"expires_on must be numeric epoch seconds: {payload}"

    mismatch_status = _marker_value(probe_output, "MISMATCH_STATUS:")
    assert mismatch_status == "401", \
        f"Wrong X-IDENTITY-HEADER should be rejected with 401, got {mismatch_status}: {probe_output}"

    azure_identity = _marker_value(probe_output, "AZURE_IDENTITY:")
    if azure_identity == "ABSENT":
        LOGGER.info("azure-identity not installed in image; skipping ManagedIdentityCredential sub-check")
    else:
        assert azure_identity == "OK", \
            f"ManagedIdentityCredential sub-check failed: {probe_output}"

    LOGGER.info("zone-msi-shim token exchange test passed successfully")

import pytest

from tests.general.wait_utils import wait_for_exec_success


def _skip_if_base_image(image_name):
    image_name = image_name.lower()
    if "/base:" in image_name or image_name.endswith("/base") or "base:" in image_name.split("/")[-1]:
        pytest.skip("zone_token_broker is installed from the mid image onward")


@pytest.mark.integration
def test_zone_token_broker_package_imports(container):
    _skip_if_base_image(container.image_name)
    container.run()

    success, output = wait_for_exec_success(
        container=container,
        command=["python", "--version"],
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0,
    )
    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    result = container.container.exec_run([
        "python",
        "-c",
        (
            "import importlib.metadata as metadata; "
            "import adlfs; "
            "import zone_token_broker as ztb; "
            "assert metadata.version('zone-token-broker') == '0.1.0'; "
            "assert ztb.DEFAULT_TOKEN_PATH == '/authservice/getPassthroughToken'; "
            "assert ztb.credential('https://storage.azure.com/.default').scope == "
            "'https://storage.azure.com/.default'; "
            "assert ztb.async_credential('https://storage.azure.com/.default').scope == "
            "'https://storage.azure.com/.default'"
        ),
    ])

    assert result.exit_code == 0, result.output.decode("utf-8")


@pytest.mark.integration
def test_zone_token_broker_can_install_into_new_venv(container):
    _skip_if_base_image(container.image_name)
    container.run()

    result = container.container.exec_run([
        "sh",
        "-c",
        """
set -eu
test -f /opt/zone-token-broker/pyproject.toml
wheel="$(ls /opt/zone-token-broker/dist/zone_token_broker-*.whl | head -n 1)"
test -f "$wheel"
python -m venv /tmp/zone-token-broker-venv
/tmp/zone-token-broker-venv/bin/python -m pip install --no-deps "$wheel"
/tmp/zone-token-broker-venv/bin/python - <<'PY'
import importlib.metadata as metadata
import asyncio
import zone_token_broker as ztb

assert metadata.version("zone-token-broker") == "0.1.0"
assert ztb.BrokerClient(broker_url="http://example.test").broker_url == "http://example.test"

class FakeClient:
    def __init__(self):
        self.scopes = []

    def get_token(self, scope):
        self.scopes.append(scope)
        return ztb.BrokerToken("token-a", 123)

async def main():
    client = FakeClient()
    credential = ztb.AsyncBrokerCredential("scope-a", client=client)
    token = await credential.get_token()
    assert token.token == "token-a"
    assert token.expires_on == 123
    await credential.get_token("scope-b")
    assert client.scopes == ["scope-a", "scope-b"]
    await credential.close()

asyncio.run(main())
PY
""",
    ])

    assert result.exit_code == 0, result.output.decode("utf-8")


@pytest.mark.integration
def test_zone_token_broker_r_package_can_install_into_user_library(container):
    _skip_if_base_image(container.image_name)
    container.run()

    result = container.container.exec_run([
        "R",
        "--slave",
        "-e",
        (
            "src <- '/opt/zone-token-broker/zone-token-broker-r'; "
            "stopifnot(file.exists(file.path(src, 'DESCRIPTION'))); "
            "lib <- tempfile('ztb-r-lib-'); "
            "dir.create(lib); "
            "install.packages(src, lib = lib, repos = NULL, type = 'source'); "
            "library(zonetokenbroker, lib.loc = lib); "
            "stopifnot(exists('zone_get_token'))"
        ),
    ])

    assert result.exit_code == 0, result.output.decode("utf-8")

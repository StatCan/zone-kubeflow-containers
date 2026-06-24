import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.general.wait_utils import wait_for_exec_success


def _load_zone_dvc():
    module_path = Path(__file__).resolve().parents[2] / "images" / "mid" / "zone-token-broker" / "zone_dvc.py"
    spec = importlib.util.spec_from_file_location("zone_dvc_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zone_dvc_patches_dvc_default_azure_credential(monkeypatch):
    zone_dvc = _load_zone_dvc()
    default_credential = object()

    class FakeBrokerCredential:
        def __init__(self, scope):
            self.scope = scope

    class FakeAzureFileSystem:
        def _prepare_credentials(self, **config):
            return {
                "account_name": config.get("account_name"),
                "connection_string": config.get("connection_string"),
                "account_key": config.get("account_key"),
                "sas_token": config.get("sas_token"),
                "tenant_id": config.get("tenant_id"),
                "client_id": config.get("client_id"),
                "client_secret": config.get("client_secret"),
                "credential": default_credential,
            }

    monkeypatch.setitem(sys.modules, "dvc_azure", SimpleNamespace(AzureFileSystem=FakeAzureFileSystem))
    monkeypatch.setitem(
        sys.modules,
        "zone_token_broker",
        SimpleNamespace(async_credential=lambda scope: FakeBrokerCredential(scope)),
    )

    zone_dvc._patch_dvc_azure()

    login_info = FakeAzureFileSystem()._prepare_credentials(account_name="stpdlppdprd00sa")
    assert isinstance(login_info["credential"], FakeBrokerCredential)
    assert login_info["credential"].scope == "https://storage.azure.com/.default"

    login_info = FakeAzureFileSystem()._prepare_credentials(
        account_name="stpdlppdprd00sa",
        sas_token="explicit-sas",
    )
    assert login_info["credential"] is default_credential


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
            "import zone_dvc; "
            "import zone_token_broker as ztb; "
            "assert metadata.version('zone-token-broker') == '0.1.0'; "
            "assert zone_dvc.STORAGE_SCOPE == 'https://storage.azure.com/.default'; "
            "assert ztb.DEFAULT_TOKEN_PATH == '/authservice/getPassthroughToken'; "
            "assert ztb.credential('https://storage.azure.com/.default').scope == "
            "'https://storage.azure.com/.default'; "
            "assert ztb.async_credential('https://storage.azure.com/.default').scope == "
            "'https://storage.azure.com/.default'; "
            "assert any(entry.name == 'zone-dvc' for entry in metadata.entry_points(group='console_scripts'))"
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
import zone_dvc
import zone_token_broker as ztb

assert metadata.version("zone-token-broker") == "0.1.0"
assert any(entry.name == "zone-dvc" for entry in metadata.entry_points(group="console_scripts"))
assert zone_dvc.STORAGE_SCOPE == "https://storage.azure.com/.default"
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

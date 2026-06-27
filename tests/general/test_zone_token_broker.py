import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.general.wait_utils import wait_for_exec_success

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


def _load_zone_dvc():
    module_path = Path(__file__).resolve().parents[2] / "images" / "mid" / "zone-token-broker" / "zone_dvc.py"
    spec = importlib.util.spec_from_file_location("zone_dvc_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_zone_token_broker():
    module_path = Path(__file__).resolve().parents[2] / "images" / "mid" / "zone-token-broker" / "zone_token_broker.py"
    spec = importlib.util.spec_from_file_location("zone_token_broker_test", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_consent_error_names_scope_and_preserves_request_ids():
    zone_token_broker = _load_zone_token_broker()

    class FakeResponse:
        text = json.dumps({
            "error": "invalid_grant",
            "error_description": (
                "AADSTS65001: The user or administrator has not consented. token "
                "headerpart.payloadpart.signaturepart"
            ),
            "trace_id": "trace-123",
            "correlation_id": "corr-456",
        })

    with pytest.raises(zone_token_broker.TokenBrokerError) as error:
        zone_token_broker._parse_token_response(FakeResponse(), scope="https://database.windows.net/.default")

    message = str(error.value)
    assert "https://database.windows.net/.default" in message
    assert "Azure/Entra admin consent is required" in message
    assert "DAaaS/Kubeflow" in message
    assert "trace_id=trace-123" in message
    assert "correlation_id=corr-456" in message
    assert "headerpart.payloadpart.signaturepart" not in message
    assert "[redacted-token]" in message


def test_preflight_scopes_do_not_print_token_values(capsys):
    zone_token_broker = _load_zone_token_broker()

    class FakeClient:
        def get_token(self, scope):
            if scope == "https://database.windows.net/.default":
                raise zone_token_broker.TokenBrokerError("secret-token-value")
            return zone_token_broker.BrokerToken("secret-token-value", 123)

    ok = zone_token_broker.preflight_scopes(client=FakeClient())

    output = capsys.readouterr().out
    assert not ok
    assert "OK scope=https://storage.azure.com/.default expires_on=123" in output
    assert "FAILED scope=https://database.windows.net/.default error=TokenBrokerError" in output
    assert "secret-token-value" not in output


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


def test_zone_dvc_reports_missing_optional_dependencies(monkeypatch, capsys):
    zone_dvc = _load_zone_dvc()

    def raise_missing_dvc_azure():
        raise ModuleNotFoundError("No module named 'dvc_azure'", name="dvc_azure")

    monkeypatch.setattr(zone_dvc, "_patch_dvc_azure", raise_missing_dvc_azure)

    assert zone_dvc.main([]) == 2
    assert "zone-token-broker[zone-dvc]" in capsys.readouterr().err


def test_package_metadata_declares_zone_dvc_extra_and_preflight_script():
    if tomllib is None:
        pytest.skip("tomllib is unavailable")

    pyproject_path = Path(__file__).resolve().parents[2] / "images" / "mid" / "zone-token-broker" / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text())

    assert pyproject["project"]["optional-dependencies"]["zone-dvc"] == ["dvc", "dvc-azure"]
    assert pyproject["project"]["scripts"]["zone-dvc"] == "zone_dvc:main"
    assert pyproject["project"]["scripts"]["zone-token-broker-preflight"] == "zone_token_broker:preflight_main"


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

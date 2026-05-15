import importlib.util
import json
import sys
import types
from pathlib import Path


def _load_module(monkeypatch, config_path):
    monkeypatch.setenv("ONELAKE_CONFIG", str(config_path))
    module_path = Path(__file__).resolve().parents[2] / "images" / "onelake" / "onelake_utils.py"
    spec = importlib.util.spec_from_file_location("test_onelake_utils_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_configure_persists_non_secret_selection(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")

    module.configure("workspace-guid", "lakehouse-guid")

    assert json.loads((tmp_path / "config.json").read_text()) == {
        "workspace": "workspace-guid",
        "lakehouse": "lakehouse-guid",
    }


def test_env_config_overrides_saved_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"workspace": "saved-ws", "lakehouse": "saved-lh"}))
    monkeypatch.setenv("ONELAKE_WORKSPACE", "env-ws")
    monkeypatch.setenv("ONELAKE_LAKEHOUSE", "env-lh")
    module = _load_module(monkeypatch, config_path)

    assert module._get_config() == ("env-ws", "env-lh")


def test_status_reports_missing_auth_wiring(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")

    current = module.status()

    assert current["ready"] is False
    assert "ONELAKE_BROKER_URL or temporary ONELAKE_ACCESS_TOKEN" in current["missing"]


def test_doctor_reports_image_and_live_readiness(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")
    monkeypatch.setenv("ONELAKE_BROKER_URL", "https://broker.example")
    module.configure("workspace", "lakehouse")
    monkeypatch.setattr(module.importlib, "import_module", lambda _name: object())
    monkeypatch.setattr(module, "ls", lambda _path: [{"name": "file.txt", "is_directory": False, "size": 1}])

    checks = module.doctor(check_access=True)

    assert all(check["ok"] for check in checks)
    assert checks[-1] == {"name": "Live OneLake list", "ok": True, "detail": "1 entries"}


def test_build_path_supports_names_and_guids(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")

    assert module._build_path("raw/file.csv", lakehouse="Lake") == "Lake.Lakehouse/Files/raw/file.csv"
    assert module._build_path("/raw/file.csv", lakehouse="11111111-2222-3333-4444-555555555555") == (
        "11111111-2222-3333-4444-555555555555/Files/raw/file.csv"
    )


def test_broker_credential_uses_token_file(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")
    token_file = tmp_path / "broker-token"
    token_file.write_text("session-token\n")
    calls = {}
    expires_on = int(module.time.time()) + 3600

    class Response:
        def raise_for_status(self):
            calls["raised"] = True

        def json(self):
            return {"access_token": "storage-token", "expires_on": expires_on}

    class Session:
        def get(self, url, params, headers, timeout):
            calls.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
            return Response()

    class AccessToken:
        def __init__(self, token, expires_on):
            self.token = token
            self.expires_on = expires_on

    requests_module = types.ModuleType("requests")
    requests_module.Session = Session
    azure_module = types.ModuleType("azure")
    azure_core_module = types.ModuleType("azure.core")
    credentials_module = types.ModuleType("azure.core.credentials")
    credentials_module.AccessToken = AccessToken

    monkeypatch.setitem(sys.modules, "requests", requests_module)
    monkeypatch.setitem(sys.modules, "azure", azure_module)
    monkeypatch.setitem(sys.modules, "azure.core", azure_core_module)
    monkeypatch.setitem(sys.modules, "azure.core.credentials", credentials_module)

    credential = module.BrokerCredential("https://broker.example", str(token_file))
    token = credential.get_token("scope-a")

    assert token.token == "storage-token"
    assert token.expires_on == expires_on
    assert calls == {
        "url": "https://broker.example/onelake/token",
        "params": {"scope": "scope-a"},
        "headers": {"Authorization": "Bearer session-token"},
        "timeout": 30,
        "raised": True,
    }


def test_broker_credential_requires_https(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")

    try:
        module.BrokerCredential("http://broker.example").get_token("scope-a")
    except RuntimeError as error:
        assert "must use https" in str(error)
    else:
        raise AssertionError("non-HTTPS broker URLs should fail closed")

    assert module._allowed_broker_url("http://localhost:8080") is True
    assert module._allowed_broker_url("http://localhost.example:8080") is False

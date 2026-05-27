import base64
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load_module(monkeypatch):
    module_dir = ROOT / "images" / "onelake"
    monkeypatch.syspath_prepend(str(module_dir))
    sys.modules.pop("zone_token_broker", None)
    module_path = module_dir / "zone_token_broker.py"
    spec = importlib.util.spec_from_file_location("zone_token_broker", module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "zone_token_broker", module)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _jwt(expires_on):
    def encode(payload):
        data = json.dumps(payload).encode("utf-8")
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode({'exp': expires_on})}.sig"


def test_get_token_calls_authservice_with_storage_scope(monkeypatch):
    module = _load_module(monkeypatch)
    calls = {}
    expires_on = int(module.time.time()) + 3600
    access_token = _jwt(expires_on)

    class Response:
        text = access_token

        def raise_for_status(self):
            calls["raised"] = True

    class Session:
        def get(self, url, params, timeout):
            calls.update({"url": url, "params": params, "timeout": timeout})
            return Response()

    requests_module = types.ModuleType("requests")
    requests_module.Session = Session
    monkeypatch.setitem(sys.modules, "requests", requests_module)

    token = module.BrokerClient("https://broker.example/authservice").get_token()

    assert token.access_token == access_token
    assert token.expires_on == expires_on
    assert calls == {
        "url": "https://broker.example/authservice/getPassthroughToken",
        "params": {"scope": "https://storage.azure.com/.default"},
        "timeout": 30,
        "raised": True,
    }


def test_error_response_reports_failure_without_token(monkeypatch):
    module = _load_module(monkeypatch)
    token = _jwt(int(module.time.time()) + 3600)

    class Response:
        text = json.dumps({
            "error": "invalid_grant",
            "error_description": f"AADSTS65001: consent_required {token}",
        })

    with pytest.raises(module.TokenBrokerError) as error:
        module._parse_token_response(Response())

    assert "AADSTS65001" in str(error.value)
    assert token not in str(error.value)


def test_http_broker_policy_allows_default_and_rejects_other_http(monkeypatch):
    module = _load_module(monkeypatch)

    assert module._allowed_broker_url(module.DEFAULT_BROKER_URL) is True
    assert module._allowed_broker_url("http://localhost:8080/authservice") is True
    assert module._allowed_broker_url("https://broker.example/authservice") is True
    assert module._allowed_broker_url("http://broker.example/authservice") is False
    assert module._allowed_broker_url("http://broker.example/authservice", allow_insecure_broker=True) is True


def test_broker_credential_caches_per_scope(monkeypatch):
    module = _load_module(monkeypatch)
    calls = {"count": 0}
    expires_on = int(module.time.time()) + 3600

    class Response:
        @property
        def text(self):
            return _jwt(expires_on)

        def raise_for_status(self):
            pass

    class Session:
        def get(self, *_args, **_kwargs):
            calls["count"] += 1
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

    credential = module.BrokerCredential(client=module.BrokerClient("https://broker.example/authservice"))
    first = credential.get_token("scope-a")
    second = credential.get_token("scope-a")

    assert first.token == second.token
    assert first.expires_on == expires_on
    assert calls["count"] == 1

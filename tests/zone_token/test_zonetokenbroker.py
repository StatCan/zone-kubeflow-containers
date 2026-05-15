import base64
import importlib.util
import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_module(monkeypatch):
    module_path = ROOT / "images" / "zone_token" / "zonetokenbroker.py"
    spec = importlib.util.spec_from_file_location("test_zonetokenbroker_module", module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "test_zonetokenbroker_module", module)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _jwt(expires_on):
    def encode(payload):
        data = json.dumps(payload).encode("utf-8")
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode({'exp': expires_on})}.sig"


def test_get_access_token_calls_authservice_with_scope_and_token_file(tmp_path, monkeypatch):
    module = _load_module(monkeypatch)
    token_file = tmp_path / "broker-token"
    token_file.write_text("session-token\n")
    calls = {}
    expires_on = int(module.time.time()) + 3600

    class Response:
        text = ""

        def raise_for_status(self):
            calls["raised"] = True

        def json(self):
            return {"access_token": "access-token", "expires_on": expires_on}

    class Session:
        def get(self, url, params, headers, timeout):
            calls.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
            return Response()

    requests_module = types.ModuleType("requests")
    requests_module.Session = Session
    monkeypatch.setitem(sys.modules, "requests", requests_module)

    token = module.get_access_token(
        "scope-a",
        broker_url="https://broker.example/authservice",
        token_path="/getToken",
        token_file=str(token_file),
    )

    assert token == "access-token"
    assert calls == {
        "url": "https://broker.example/authservice/getToken",
        "params": {"scope": "scope-a"},
        "headers": {"Authorization": "Bearer session-token"},
        "timeout": 30,
        "raised": True,
    }


def test_raw_text_jwt_response_is_supported(monkeypatch):
    module = _load_module(monkeypatch)
    token = _jwt(int(module.time.time()) + 3600)

    class Response:
        text = token

        def json(self):
            raise ValueError("not json")

    parsed = module.parse_token_response(Response())

    assert parsed.access_token == token
    assert parsed.expires_on > int(module.time.time()) + 3000


def test_error_response_reports_consent_failure_without_token(monkeypatch):
    module = _load_module(monkeypatch)
    token = _jwt(int(module.time.time()) + 3600)

    class Response:
        text = ""

        def json(self):
            return {
                "error": "invalid_grant",
                "error_description": f"AADSTS65001: consent_required {token}",
            }

    try:
        module.parse_token_response(Response())
    except module.TokenBrokerError as error:
        message = str(error)
        assert "AADSTS65001" in message
        assert token not in message
    else:
        raise AssertionError("broker error responses should fail")


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
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": f"token-{calls['count']}", "expires_on": expires_on}

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

    credential = module.BrokerCredential("https://broker.example/authservice")
    first = credential.get_token("scope-a")
    second = credential.get_token("scope-a")

    assert first.token == "token-1"
    assert second.token == "token-1"
    assert calls["count"] == 1

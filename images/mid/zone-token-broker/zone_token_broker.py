"""Internal AuthService client for delegated access tokens."""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import namedtuple
from dataclasses import dataclass

# Stand-in for azure.core.credentials.AccessToken (same (token, expires_on)
# shape) so credential() works as a TokenCredential without requiring
# azure-core to be installed in the image.
AccessToken = namedtuple("AccessToken", ["token", "expires_on"])

DEFAULT_BROKER_URL = "http://authservice.kubeflow.svc.cluster.local:8080"
DEFAULT_TOKEN_PATH = "/authservice/getPassthroughToken"
EXPIRY_BUFFER_SECONDS = 300

BROKER_URL_ENV = "AUTHSERVICE_BROKER_URL"
BROKER_TOKEN_PATH_ENV = "AUTHSERVICE_BROKER_TOKEN_PATH"

CONSENT_ERROR_MARKERS = (
    "invalid_grant",
    "aadsts65001",
    "consent_required",
    "consent required",
    "has not consented",
    "admin consent",
)
PREFLIGHT_SCOPES = (
    "https://storage.azure.com/.default",
    "https://database.windows.net/.default",
)


class TokenBrokerError(RuntimeError):
    """Raised when AuthService cannot return a delegated token."""


@dataclass(frozen=True)
class BrokerToken:
    access_token: str
    expires_on: int


def _join_url(base_url, path):
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _redact(text):
    redacted = re.sub(r"\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b", "[redacted-token]", str(text))
    return " ".join(redacted.split())[:500]


def _load_error_payload(text):
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _error_detail(payload, text):
    if not isinstance(payload, dict):
        return text

    parts = []
    for name in ("error", "trace_id", "correlation_id", "timestamp", "error_description"):
        value = payload.get(name)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(item) for item in value)
        value = str(value).strip()
        if not value:
            continue
        parts.append(value if name == "error_description" else f"{name}={value}")
    return "; ".join(parts) if parts else text


def _is_consent_error(detail):
    lowered = str(detail).lower()
    return any(marker in lowered for marker in CONSENT_ERROR_MARKERS)


def _format_broker_failure(detail, scope=None):
    redacted_detail = _redact(detail)
    if _is_consent_error(detail):
        scope_label = _redact(scope or "requested scope")
        return (
            f"Token broker request failed for scope '{scope_label}': Azure/Entra admin consent is required "
            "for the DAaaS/Kubeflow app/resource before AuthService can issue this delegated token. "
            f"Ask an Azure/Entra administrator to grant consent for scope '{scope_label}', then retry. "
            f"AuthService detail: {redacted_detail}"
        )

    scope_detail = f" for scope '{_redact(scope)}'" if scope else ""
    return f"Token broker request failed{scope_detail}: {redacted_detail}"


def _parse_token_response(response, scope=None):
    text = getattr(response, "text", "").strip()
    if not text:
        raise TokenBrokerError("Token broker response is empty")

    # AuthService returns JSON: {"access_token": ..., "expires_on": <epoch seconds>, ...}.
    payload = _load_error_payload(text)
    if payload is None:
        raise TokenBrokerError(f"Token broker returned an unparseable response: {_redact(text)}")

    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise TokenBrokerError(_format_broker_failure(_error_detail(payload, text), scope=scope))

    try:
        expires_on = int(payload["expires_on"])
    except (KeyError, TypeError, ValueError) as error:
        raise TokenBrokerError("Token broker response did not include a valid expires_on") from error

    return BrokerToken(str(payload["access_token"]), expires_on)


class BrokerClient:
    """Small AuthService client with in-memory token caching."""

    def __init__(self, broker_url=None, token_path=None):
        self.broker_url = (broker_url if broker_url is not None else os.environ.get(BROKER_URL_ENV, DEFAULT_BROKER_URL))
        self.broker_url = self.broker_url.rstrip("/")
        self.token_path = token_path or os.environ.get(BROKER_TOKEN_PATH_ENV, DEFAULT_TOKEN_PATH)
        self._cached_tokens = {}
        self._session = None

    def _get_session(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def get_token(self, scope):
        scope = str(scope or "").strip()
        if not scope:
            raise TokenBrokerError("scope is required")
        if not self.broker_url:
            raise TokenBrokerError("token broker URL is not set")

        cached = self._cached_tokens.get(scope)
        now = int(time.time())
        if cached and now < cached.expires_on - EXPIRY_BUFFER_SECONDS:
            return cached

        response = self._get_session().get(
            _join_url(self.broker_url, self.token_path),
            params={"scope": scope},
            timeout=30,
        )
        try:
            response.raise_for_status()
        except Exception as error:
            text = getattr(response, "text", "")
            detail = _error_detail(_load_error_payload(text), text)
            if detail:
                raise TokenBrokerError(_format_broker_failure(detail, scope=scope)) from error
            raise TokenBrokerError(f"Token broker request failed: {error}") from error

        token = _parse_token_response(response, scope=scope)
        self._cached_tokens[scope] = token
        return token


class BrokerCredential:
    """Azure TokenCredential backed by AuthService."""

    def __init__(self, scope, client=None):
        self.scope = scope
        self.client = client or BrokerClient()

    def get_token(self, *scopes, **_kwargs):
        scope = " ".join(scopes) if scopes else self.scope
        token = self.client.get_token(scope)
        return AccessToken(token.access_token, token.expires_on)


class AsyncBrokerCredential:
    """Async Azure TokenCredential backed by AuthService for adlfs/fsspec."""

    def __init__(self, scope, client=None):
        self.scope = scope
        self.client = client or BrokerClient()

    async def get_token(self, *scopes, **_kwargs):
        scope = " ".join(scopes) if scopes else self.scope
        token = await asyncio.to_thread(self.client.get_token, scope)
        return AccessToken(token.access_token, token.expires_on)

    async def close(self):
        session = getattr(self.client, "_session", None)
        if session is not None:
            session.close()
            self.client._session = None


_default_client = BrokerClient()


def get_token(scope):
    return _default_client.get_token(scope)


def credential(scope):
    return BrokerCredential(scope=scope)


def async_credential(scope):
    return AsyncBrokerCredential(scope=scope)


def preflight_scopes(scopes=None, client=None, output=None):
    """Check broker access for scopes without printing token values."""
    client = client or BrokerClient()
    output = output or sys.stdout
    ok = True
    for scope in scopes or PREFLIGHT_SCOPES:
        try:
            token = client.get_token(scope)
        except Exception as error:
            print(f"FAILED scope={scope} error={error.__class__.__name__}", file=output)
            ok = False
        else:
            print(f"OK scope={scope} expires_on={token.expires_on}", file=output)
    return ok


def preflight_main(argv=None):
    parser = argparse.ArgumentParser(description="Preflight Zone AuthService token broker scopes without printing tokens.")
    parser.add_argument("scopes", nargs="*", default=list(PREFLIGHT_SCOPES), help="Scopes to check.")
    args = parser.parse_args(argv)
    return 0 if preflight_scopes(args.scopes) else 1

"""Internal AuthService client for delegated OneLake tokens."""

import base64
import binascii
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse

STORAGE_SCOPE = "https://storage.azure.com/.default"
DEFAULT_BROKER_URL = "http://authservice.kubeflow.svc.cluster.local:8080/authservice"
DEFAULT_TOKEN_PATH = "/getPassthroughToken"
EXPIRY_BUFFER_SECONDS = 300

BROKER_URL_ENV = "ONELAKE_BROKER_URL"
BROKER_TOKEN_PATH_ENV = "ONELAKE_BROKER_TOKEN_PATH"
ALLOW_INSECURE_BROKER_ENV = "ONELAKE_ALLOW_INSECURE_BROKER"


class TokenBrokerError(RuntimeError):
    """Raised when AuthService cannot return a delegated token."""


@dataclass(frozen=True)
class BrokerToken:
    access_token: str
    expires_on: int


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").lower() in {"1", "true", "yes"}


def _join_url(base_url, path):
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _allowed_broker_url(broker_url, allow_insecure_broker=None):
    parsed = urlparse(broker_url)
    if parsed.scheme == "https":
        return True
    if parsed.scheme != "http":
        return False
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    if broker_url.rstrip("/") == DEFAULT_BROKER_URL:
        return True
    return _truthy(allow_insecure_broker)


def _expires_on(token):
    parts = token.split(".")
    if len(parts) < 2:
        raise TokenBrokerError("Token broker response did not contain a JWT access token")
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return int(claims["exp"])
    except (KeyError, TypeError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        raise TokenBrokerError("Token broker response did not contain a usable JWT exp claim") from error


def _looks_like_jwt(token):
    return len(token.split(".")) >= 3


def _redact(text):
    redacted = re.sub(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[redacted-token]", str(text))
    return " ".join(redacted.split())[:500]


def _parse_token_response(response):
    text = getattr(response, "text", "").strip()
    if not text:
        raise TokenBrokerError("Token broker response is empty")

    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {}
        detail = payload.get("error_description") or payload.get("error") or text
        raise TokenBrokerError(f"Token broker request failed: {_redact(detail)}")

    token = text.removeprefix("Bearer ").strip()
    if not _looks_like_jwt(token):
        raise TokenBrokerError(f"Token broker response did not contain an access token: {_redact(text)}")
    return BrokerToken(token, _expires_on(token))


class BrokerClient:
    """Small AuthService client with in-memory token caching."""

    def __init__(self, broker_url=None, token_path=None, allow_insecure_broker=None):
        self.broker_url = (broker_url if broker_url is not None else os.environ.get(BROKER_URL_ENV, DEFAULT_BROKER_URL))
        self.broker_url = self.broker_url.rstrip("/")
        self.token_path = token_path or os.environ.get(BROKER_TOKEN_PATH_ENV, DEFAULT_TOKEN_PATH)
        self.allow_insecure_broker = (
            allow_insecure_broker
            if allow_insecure_broker is not None
            else os.environ.get(ALLOW_INSECURE_BROKER_ENV, "")
        )
        self._cached_tokens = {}
        self._session = None
        self._lock = threading.Lock()

    def _get_session(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def get_token(self, scope=STORAGE_SCOPE):
        scope = str(scope or STORAGE_SCOPE).strip()
        if not self.broker_url:
            raise TokenBrokerError("token broker URL is not set")
        if not _allowed_broker_url(self.broker_url, self.allow_insecure_broker):
            raise TokenBrokerError("token broker URL must use https, localhost http, or the default in-cluster AuthService")

        with self._lock:
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
                detail = _redact(getattr(response, "text", ""))
                if detail:
                    raise TokenBrokerError(f"Token broker request failed: {detail}") from error
                raise TokenBrokerError(f"Token broker request failed: {error}") from error

            token = _parse_token_response(response)
            self._cached_tokens[scope] = token
            return token


class BrokerCredential:
    """Azure TokenCredential backed by AuthService."""

    def __init__(self, scope=STORAGE_SCOPE, client=None):
        self.scope = scope
        self.client = client or BrokerClient()

    def get_token(self, *scopes, **_kwargs):
        scope = " ".join(scopes) if scopes else self.scope
        token = self.client.get_token(scope)

        from azure.core.credentials import AccessToken

        return AccessToken(token.access_token, token.expires_on)


_default_client = BrokerClient()


def get_token(scope=STORAGE_SCOPE):
    return _default_client.get_token(scope)


def credential(scope=STORAGE_SCOPE):
    return BrokerCredential(scope=scope)

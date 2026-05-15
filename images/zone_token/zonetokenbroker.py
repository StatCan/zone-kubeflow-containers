"""Notebook-side client for the Zone AuthService token endpoint."""

import base64
import binascii
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_BROKER_URL = "http://authservice.kubeflow.svc.cluster.local:8080/authservice"
DEFAULT_TOKEN_PATH = "/getToken"
DEFAULT_MIN_TOKEN_TTL_SECONDS = 1800
DEFAULT_EXPIRY_BUFFER_SECONDS = 300

BROKER_URL_ENV = "ZONE_TOKEN_BROKER_URL"
BROKER_TOKEN_PATH_ENV = "ZONE_TOKEN_BROKER_TOKEN_PATH"
BROKER_TOKEN_FILE_ENV = "ZONE_TOKEN_BROKER_TOKEN_FILE"
ALLOW_INSECURE_BROKER_ENV = "ZONE_TOKEN_ALLOW_INSECURE_BROKER"


class TokenBrokerError(RuntimeError):
    """Raised when a token cannot be retrieved from AuthService."""


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


def token_expires_on(token):
    parts = token.split(".")
    if len(parts) >= 2:
        try:
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
            if claims.get("exp"):
                return int(claims["exp"])
        except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            pass
    return int(time.time()) + 300


def _looks_like_jwt(token):
    return len(token.split(".")) >= 3


def _shorten_error(text):
    redacted = re.sub(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[redacted-token]", text)
    return " ".join(redacted.split())[:500]


def parse_token_response(response):
    payload = None
    try:
        payload = response.json()
    except ValueError:
        pass

    if isinstance(payload, dict):
        if payload.get("error"):
            description = payload.get("error_description") or payload["error"]
            raise TokenBrokerError(f"Token broker request failed: {_shorten_error(str(description))}")
        token_type = payload.get("token_type", "Bearer")
        if token_type.lower() != "bearer":
            raise TokenBrokerError("Token broker returned unsupported token type")
        token = payload.get("access_token") or payload.get("accessToken") or payload.get("token")
        if not token:
            raise TokenBrokerError("Token broker response is missing access_token")
        expires_on = payload.get("expires_on") or payload.get("expiresOn")
        if expires_on:
            return BrokerToken(token, int(expires_on))
        expires_in = payload.get("expires_in") or payload.get("expiresIn")
        if expires_in:
            return BrokerToken(token, int(time.time()) + int(expires_in))
        return BrokerToken(token, token_expires_on(token))

    text = getattr(response, "text", "").strip()
    if not text:
        raise TokenBrokerError("Token broker response is empty")
    token = text.removeprefix("Bearer ").strip()
    if not _looks_like_jwt(token):
        detail = _shorten_error(text)
        raise TokenBrokerError(f"Token broker response did not contain an access token: {detail}")
    return BrokerToken(token, token_expires_on(token))


class BrokerClient:
    """Small AuthService client with in-memory per-scope token caching."""

    def __init__(
        self,
        broker_url=None,
        token_path=None,
        token_file=None,
        minimum_token_ttl_seconds=DEFAULT_MIN_TOKEN_TTL_SECONDS,
        expiry_buffer_seconds=DEFAULT_EXPIRY_BUFFER_SECONDS,
        allow_insecure_broker=None,
    ):
        self.broker_url = (broker_url if broker_url is not None else os.environ.get(BROKER_URL_ENV, DEFAULT_BROKER_URL))
        self.broker_url = self.broker_url.rstrip("/")
        self.token_path = token_path or os.environ.get(BROKER_TOKEN_PATH_ENV, DEFAULT_TOKEN_PATH)
        self.token_file = token_file or os.environ.get(BROKER_TOKEN_FILE_ENV, "")
        self.minimum_token_ttl_seconds = minimum_token_ttl_seconds
        self.expiry_buffer_seconds = expiry_buffer_seconds
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

    def _headers(self):
        if not self.token_file:
            return {}
        token = Path(self.token_file).read_text(encoding="utf-8").strip()
        return {"Authorization": f"Bearer {token}"}

    def get_token(self, scope):
        scope = str(scope or "").strip()
        if not scope:
            raise TokenBrokerError("scope is required")
        if not self.broker_url:
            raise TokenBrokerError("token broker URL is not set")
        if not _allowed_broker_url(self.broker_url, self.allow_insecure_broker):
            raise TokenBrokerError("token broker URL must use https, localhost http, or the default in-cluster AuthService")

        with self._lock:
            cached = self._cached_tokens.get(scope)
            now = int(time.time())
            if cached and now < cached.expires_on - self.expiry_buffer_seconds:
                return cached

            response = self._get_session().get(
                _join_url(self.broker_url, self.token_path),
                params={"scope": scope},
                headers=self._headers(),
                timeout=30,
            )
            try:
                response.raise_for_status()
            except Exception as error:
                detail = _shorten_error(getattr(response, "text", ""))
                if detail:
                    raise TokenBrokerError(f"Token broker request failed: {detail}") from error
                raise TokenBrokerError(f"Token broker request failed: {error}") from error

            token = parse_token_response(response)
            ttl = token.expires_on - now
            if ttl < self.minimum_token_ttl_seconds:
                raise TokenBrokerError(
                    "Token broker response expires too soon; "
                    f"minimum TTL is {self.minimum_token_ttl_seconds} seconds"
                )
            self._cached_tokens[scope] = token
            return token

    def get_access_token(self, scope):
        return self.get_token(scope).access_token


def get_access_token(scope, **kwargs):
    """Return an access token for the requested delegated scope."""
    return BrokerClient(**kwargs).get_access_token(scope)


class BrokerCredential:
    """Azure TokenCredential that retrieves delegated user tokens from AuthService."""

    def __init__(
        self,
        broker_url=None,
        token_file=None,
        token_path=None,
        default_scope=None,
        minimum_token_ttl_seconds=DEFAULT_MIN_TOKEN_TTL_SECONDS,
        allow_insecure_broker=None,
    ):
        self.default_scope = default_scope
        self.client = BrokerClient(
            broker_url=broker_url,
            token_path=token_path,
            token_file=token_file,
            minimum_token_ttl_seconds=minimum_token_ttl_seconds,
            allow_insecure_broker=allow_insecure_broker,
        )

    def get_token(self, *scopes, **_kwargs):
        scope = " ".join(scopes or (() if self.default_scope is None else (self.default_scope,)))
        token = self.client.get_token(scope)

        from azure.core.credentials import AccessToken

        return AccessToken(token.access_token, token.expires_on)

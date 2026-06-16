"""Internal AuthService client for delegated access tokens."""

import json
import os
import re
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


class TokenBrokerError(RuntimeError):
    """Raised when AuthService cannot return a delegated token."""


@dataclass(frozen=True)
class BrokerToken:
    access_token: str
    expires_on: int


def _join_url(base_url, path):
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _redact(text):
    redacted = re.sub(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[redacted-token]", str(text))
    return " ".join(redacted.split())[:500]


def _parse_token_response(response):
    text = getattr(response, "text", "").strip()
    if not text:
        raise TokenBrokerError("Token broker response is empty")

    # AuthService returns JSON: {"access_token": ..., "expires_on": <epoch seconds>, ...}.
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        raise TokenBrokerError(f"Token broker returned an unparseable response: {_redact(text)}")

    if not isinstance(payload, dict) or not payload.get("access_token"):
        detail = text
        if isinstance(payload, dict):
            detail = payload.get("error_description") or payload.get("error") or text
        raise TokenBrokerError(f"Token broker request failed: {_redact(detail)}")

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
            detail = _redact(getattr(response, "text", ""))
            if detail:
                raise TokenBrokerError(f"Token broker request failed: {detail}") from error
            raise TokenBrokerError(f"Token broker request failed: {error}") from error

        token = _parse_token_response(response)
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


_default_client = BrokerClient()


def get_token(scope):
    return _default_client.get_token(scope)


def credential(scope):
    return BrokerCredential(scope=scope)

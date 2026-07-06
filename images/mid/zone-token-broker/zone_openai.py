"""Broker-backed Azure OpenAI client helpers.

On-platform, tokens come from AuthService via zone_token_broker (delegated
per-user identity, no API keys). For local development the helpers fall back
to azure-identity (`az login`) or an AZURE_OPENAI_API_KEY environment
variable.
"""

import os

from zone_token_broker import BrokerCredential, TokenBrokerError

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"

ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
API_KEY_ENV = "AZURE_OPENAI_API_KEY"
API_VERSION_ENV = "AZURE_OPENAI_API_VERSION"
DEFAULT_API_VERSION = "2024-10-21"


class ZoneOpenAIError(RuntimeError):
    """Raised when an Azure OpenAI client cannot be configured."""


def token_provider(scope=COGNITIVE_SERVICES_SCOPE):
    """Return a zero-argument callable yielding a bearer token for `scope`.

    Tries the AuthService broker first; if it is unreachable (e.g. running
    outside the cluster) falls back to azure.identity.DefaultAzureCredential,
    which picks up `az login`, environment, or managed identity.
    """
    broker = BrokerCredential(scope=scope)
    fallback = {}

    def _fallback_credential():
        if "credential" not in fallback:
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError as error:
                raise ZoneOpenAIError(
                    "Token broker is unavailable and azure-identity is not "
                    "installed for local fallback (pip install azure-identity)"
                ) from error
            fallback["credential"] = DefaultAzureCredential()
        return fallback["credential"]

    def _get_token():
        try:
            return broker.get_token(scope).token
        except Exception as broker_error:
            try:
                return _fallback_credential().get_token(scope).token
            except ZoneOpenAIError:
                raise
            except Exception as error:
                raise ZoneOpenAIError(
                    f"Could not get an Azure OpenAI token from the broker "
                    f"({broker_error}) or local credentials ({error})"
                ) from error

    return _get_token


def client(deployment=None, endpoint=None, api_version=None, scope=COGNITIVE_SERVICES_SCOPE, **kwargs):
    """Return a preauthenticated openai.AzureOpenAI client.

    Credential precedence: AZURE_OPENAI_API_KEY if set, otherwise Entra ID
    tokens (broker on-platform, `az login` locally).
    """
    try:
        from openai import AzureOpenAI
    except ImportError as error:
        raise ZoneOpenAIError("The openai package is required (pip install openai)") from error

    endpoint = endpoint or os.environ.get(ENDPOINT_ENV)
    if not endpoint:
        raise ZoneOpenAIError(f"Set {ENDPOINT_ENV} or pass endpoint= (https://<resource>.openai.azure.com)")
    api_version = api_version or os.environ.get(API_VERSION_ENV, DEFAULT_API_VERSION)

    options = dict(azure_endpoint=endpoint, api_version=api_version, **kwargs)
    if deployment:
        options["azure_deployment"] = deployment

    api_key = os.environ.get(API_KEY_ENV)
    if api_key:
        return AzureOpenAI(api_key=api_key, **options)
    return AzureOpenAI(azure_ad_token_provider=token_provider(scope), **options)

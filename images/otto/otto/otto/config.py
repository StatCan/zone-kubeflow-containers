"""Model and provider configuration: how otto reaches Azure.

Layered sources, later wins:

  1. /etc/otto/config.toml   platform-managed (ConfigMap / PodDefault)
  2. ~/.otto/config.toml     user-managed
  3. environment variables         AZURE_OPENAI_*, OTTO_*
  4. command line flags            --model, --deployment

Config files declare named model profiles; the environment alone (endpoint +
deployment, as in the pilot) keeps working with no files present.

    default_model = "gpt-5-mini"

    [models.gpt-5-mini]
    provider = "azure-openai"    # azure-openai | foundry | foundry-models
    endpoint = "https://<resource>.openai.azure.com"
    deployment = "gpt-5-mini"
    auth = "broker"              # broker | api-key
    # api_version = "2024-10-21"
    # api_key_env = "AZURE_OPENAI_API_KEY"   (auth = "api-key" only)
    # reasoning = "low"

Providers:
  azure-openai    a classic Azure OpenAI resource (*.openai.azure.com)
  foundry         an Azure AI Foundry / AI Services resource serving OpenAI
                  models through the same API (*.services.ai.azure.com)
  foundry-models  the Foundry model-inference API for non-OpenAI catalog
                  models (endpoint + /models)

Auth:
  broker          delegated per-user Entra token from the Zone AuthService
                  (zone_token_broker); falls back to `az login` locally.
                  No secrets anywhere.
  api-key         key read from the environment variable named by
                  api_key_env (delivered by a Kubernetes Secret in prod,
                  never written into config files or images).
"""

import os

PLATFORM_CONFIG = "/etc/otto/config.toml"
USER_CONFIG = "~/.otto/config.toml"

ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
API_KEY_ENV = "AZURE_OPENAI_API_KEY"
API_VERSION_ENV = "AZURE_OPENAI_API_VERSION"
DEPLOYMENT_ENV = "OTTO_DEPLOYMENT"
MODEL_ENV = "OTTO_MODEL"

DEFAULT_API_VERSION = "2024-10-21"
FOUNDRY_MODELS_API_VERSION = "2024-05-01-preview"
COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"
PROVIDERS = ("azure-openai", "foundry", "foundry-models")

# Prod behaviour for a CLI in a terminal: keep retrying transient faults,
# allow reasoning models their thinking time, but never hang on connect.
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 600.0
MAX_RETRIES = 4


class ConfigError(RuntimeError):
    """Raised when no usable model configuration can be resolved."""


class ModelConfig:
    """One resolved model profile."""

    def __init__(self, name, endpoint, deployment, provider="azure-openai",
                 auth="broker", api_version=None, api_key_env=API_KEY_ENV,
                 scope=COGNITIVE_SERVICES_SCOPE, reasoning=None, source="env"):
        if provider not in PROVIDERS:
            raise ConfigError(
                "model %r: unknown provider %r (expected one of %s)"
                % (name, provider, ", ".join(PROVIDERS))
            )
        if auth not in ("broker", "api-key"):
            raise ConfigError(
                "model %r: unknown auth %r (expected broker or api-key)" % (name, auth)
            )
        if not endpoint:
            raise ConfigError("model %r: endpoint is required" % name)
        if not deployment:
            raise ConfigError("model %r: deployment is required" % name)
        self.name = name
        self.provider = provider
        self.endpoint = endpoint.rstrip("/")
        self.deployment = deployment
        self.auth = auth
        self.api_version = api_version or (
            FOUNDRY_MODELS_API_VERSION if provider == "foundry-models"
            else os.environ.get(API_VERSION_ENV, DEFAULT_API_VERSION)
        )
        self.api_key_env = api_key_env or API_KEY_ENV
        self.scope = scope
        self.reasoning = reasoning
        self.source = source

    def describe(self):
        """Ordered facts for --doctor and error messages. No secrets."""
        return [
            ("model", self.name),
            ("provider", self.provider),
            ("endpoint", self.endpoint),
            ("deployment", self.deployment),
            ("api version", self.api_version),
            ("auth", self.auth if self.auth == "broker"
             else "api-key ($%s)" % self.api_key_env),
            ("configured by", self.source),
        ]


def _read_toml(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return {}
    try:
        import tomllib
    except ImportError:  # Python < 3.11: config files are unavailable
        import sys
        print(
            "otto: ignoring %s (Python %d.%d has no tomllib)"
            % (path, *sys.version_info[:2]),
            file=sys.stderr,
        )
        return {}
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError("could not read %s: %s" % (path, error)) from error


def load():
    """Merge platform and user config files. User settings win."""
    merged = {"default_model": None, "models": {}}
    for path, source in ((PLATFORM_CONFIG, "platform"), (USER_CONFIG, "user")):
        data = _read_toml(path)
        if data.get("default_model"):
            merged["default_model"] = data["default_model"]
        for name, entry in (data.get("models") or {}).items():
            if not isinstance(entry, dict):
                raise ConfigError("models.%s in %s must be a table" % (name, path))
            merged["models"][name] = (dict(entry), source + " config (%s)" % path)
    return merged


def _from_env(name="environment"):
    endpoint = os.environ.get(ENDPOINT_ENV)
    deployment = os.environ.get(DEPLOYMENT_ENV)
    if not (endpoint and deployment):
        return None
    return ModelConfig(
        name=name,
        endpoint=endpoint,
        deployment=deployment,
        auth="api-key" if os.environ.get(API_KEY_ENV) else "broker",
        source="environment",
    )


def resolve(model=None, deployment=None):
    """Return the ModelConfig for `model` (or the default), or raise.

    `deployment` overrides the profile's deployment name (the --deployment
    flag). With no config files and no model name, the environment
    (AZURE_OPENAI_ENDPOINT + OTTO_DEPLOYMENT) is used as-is.
    """
    config = load()
    model = model or os.environ.get(MODEL_ENV) or config["default_model"]

    if model and model in config["models"]:
        entry, source = config["models"][model]
        known = {"provider", "endpoint", "deployment", "auth", "api_version",
                 "api_key_env", "scope", "reasoning"}
        unknown = set(entry) - known
        if unknown:
            raise ConfigError(
                "model %r: unknown settings %s" % (model, ", ".join(sorted(unknown)))
            )
        resolved = ModelConfig(name=model, source=source, **entry)
    elif model:
        available = ", ".join(sorted(config["models"])) or "none defined"
        env_model = _from_env(model)
        if env_model is None:
            raise ConfigError(
                "unknown model %r (configured models: %s)" % (model, available)
            )
        resolved = env_model
    else:
        resolved = _from_env()
        if resolved is None:
            raise ConfigError(
                "no model configured: define one in %s or %s, or set %s and %s"
                % (PLATFORM_CONFIG, USER_CONFIG, ENDPOINT_ENV, DEPLOYMENT_ENV)
            )

    if deployment:
        resolved.deployment = deployment
    return resolved


def listing():
    """(name, provider, deployment, is_default) rows for --list-models."""
    config = load()
    rows = []
    for name in sorted(config["models"]):
        entry, _ = config["models"][name]
        rows.append(
            (name, entry.get("provider", "azure-openai"),
             entry.get("deployment", "?"), name == config["default_model"])
        )
    return rows


def _http_client():
    """An httpx client that honours the Zone's TLS-inspection CA bundle.

    httpx only reads SSL_CERT_FILE; the images set REQUESTS_CA_BUNDLE. With
    neither set this returns None and the SDK uses its defaults.
    """
    import httpx

    timeout = httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)
    bundle = (
        os.environ.get("SSL_CERT_FILE")
        or os.environ.get("REQUESTS_CA_BUNDLE")
        or os.environ.get("CURL_CA_BUNDLE")
    )
    if bundle and os.path.exists(bundle):
        return httpx.Client(verify=bundle, timeout=timeout)
    return httpx.Client(timeout=timeout)


def _bearer_auth(token_provider):
    """httpx auth hook: a fresh bearer token on every request."""
    import httpx

    class _Bearer(httpx.Auth):
        def auth_flow(self, request):
            request.headers["Authorization"] = "Bearer " + token_provider()
            yield request

    return _Bearer()


def _api_key(config):
    key = os.environ.get(config.api_key_env, "")
    if not key:
        raise ConfigError(
            "model %r uses auth=api-key but $%s is not set (in prod it is "
            "delivered by a Kubernetes Secret; see images/otto/deploy/)"
            % (config.name, config.api_key_env)
        )
    return key


def _token_provider(config):
    import zone_openai

    return zone_openai.token_provider(config.scope)


def build_client(config):
    """An `openai` SDK client wired for the profile's provider and auth."""
    from openai import AzureOpenAI, OpenAI

    if config.provider in ("azure-openai", "foundry"):
        options = dict(
            azure_endpoint=config.endpoint,
            api_version=config.api_version,
            max_retries=MAX_RETRIES,
            http_client=_http_client(),
        )
        if config.auth == "api-key":
            return AzureOpenAI(api_key=_api_key(config), **options)
        return AzureOpenAI(
            azure_ad_token_provider=_token_provider(config), **options
        )

    # foundry-models: the model-inference API for non-OpenAI catalog models.
    # The OpenAI client only carries a static key, so both auth modes ride an
    # httpx auth hook (Bearer <key or fresh broker token>).
    http_client = _http_client()
    if config.auth == "api-key":
        key = _api_key(config)
        http_client.auth = _bearer_auth(lambda: key)
    else:
        http_client.auth = _bearer_auth(_token_provider(config))
    return OpenAI(
        base_url=config.endpoint + "/models",
        api_key="unused-see-auth-hook",
        default_query={"api-version": config.api_version},
        max_retries=MAX_RETRIES,
        http_client=http_client,
    )


def doctor(config, out):
    """Preflight: show the resolved profile, get a token, make one call.

    Returns an exit code; writes human-readable findings to `out`.
    """
    for key, value in config.describe():
        out.write("%14s  %s\n" % (key, value))

    if config.auth == "broker":
        try:
            token = _token_provider(config)()
            out.write("%14s  acquired (%d chars) for %s\n"
                      % ("token", len(token), config.scope))
        except Exception as error:
            out.write("%14s  FAILED: %s\n" % ("token", error))
            return 1
    else:
        try:
            _api_key(config)
            out.write("%14s  present in $%s\n" % ("api key", config.api_key_env))
        except ConfigError as error:
            out.write("%14s  FAILED: %s\n" % ("api key", error))
            return 1

    try:
        client = build_client(config)
        response = client.chat.completions.create(
            model=config.deployment,
            messages=[{"role": "user", "content": "Reply with the word: ok"}],
        )
        content = (response.choices[0].message.content or "").strip()
        out.write("%14s  %r from %s\n" % ("model reply", content[:40], config.deployment))
    except Exception as error:
        out.write("%14s  FAILED: %s\n" % ("model call", error))
        return 1
    out.write("otto: ready\n")
    return 0

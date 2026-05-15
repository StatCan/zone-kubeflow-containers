"""API-backed OneLake helpers for Zone Kubeflow containers."""

import base64
import binascii
import importlib
import json
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

ONELAKE_REGION = os.environ.get("ONELAKE_REGION", "canadacentral")
ONELAKE_ENDPOINT = f"https://{ONELAKE_REGION}-onelake.dfs.fabric.microsoft.com"
TOKEN_SCOPE = "https://storage.azure.com/.default"
MIN_BROKER_TOKEN_TTL_SECONDS = 1800
BROKER_TOKEN_PATH = "/onelake/token"
CONFIG_FILE = Path(os.environ.get("ONELAKE_CONFIG", Path.home() / ".onelake" / "config.json"))
MANUAL_ACCESS_TOKEN_ENV = "ONELAKE_ACCESS_TOKEN"
MANUAL_ACCESS_TOKEN_FILE_ENV = "ONELAKE_ACCESS_TOKEN_FILE"

_client = None
_fs_client = None
_manual_access_token = None
_config_cache = None
_client_lock = threading.Lock()
_fs_client_lock = threading.Lock()


def _allowed_broker_url(broker_url):
    parsed = urlparse(broker_url)
    if parsed.scheme == "https":
        return True
    if os.environ.get("ONELAKE_ALLOW_INSECURE_BROKER", "").lower() in {"1", "true", "yes"}:
        return parsed.scheme == "http"
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def _join_url(base_url, path):
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


class BrokerCredential:
    """Azure TokenCredential that retrieves delegated user tokens from the broker."""

    _EXPIRY_BUFFER_SECONDS = 300

    def __init__(self, broker_url=None, token_file=None):
        self.broker_url = (broker_url or os.environ.get("ONELAKE_BROKER_URL", "")).rstrip("/")
        self.token_path = os.environ.get("ONELAKE_BROKER_TOKEN_PATH", BROKER_TOKEN_PATH)
        self.token_file = token_file or os.environ.get("ONELAKE_BROKER_TOKEN_FILE", "")
        self._cached_token = None
        self._session = None
        self._lock = threading.Lock()

    def _get_session(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def get_token(self, *scopes, **_kwargs):
        if not self.broker_url:
            raise RuntimeError("ONELAKE_BROKER_URL is not set")
        if not _allowed_broker_url(self.broker_url):
            raise RuntimeError("ONELAKE_BROKER_URL must use https unless ONELAKE_ALLOW_INSECURE_BROKER is enabled")

        from azure.core.credentials import AccessToken

        with self._lock:
            if self._cached_token:
                token, expires_on = self._cached_token
                if time.time() < expires_on - self._EXPIRY_BUFFER_SECONDS:
                    return AccessToken(token, expires_on)

            headers = {}
            if self.token_file:
                token = Path(self.token_file).read_text(encoding="utf-8").strip()
                headers["Authorization"] = f"Bearer {token}"

            response = self._get_session().get(
                _join_url(self.broker_url, self.token_path),
                params={"scope": " ".join(scopes or (TOKEN_SCOPE,))},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            token, expires_on = _parse_broker_token_response(response)
            ttl = expires_on - int(time.time())
            if ttl < MIN_BROKER_TOKEN_TTL_SECONDS:
                raise RuntimeError(
                    f"Broker token response expires too soon; minimum TTL is {MIN_BROKER_TOKEN_TTL_SECONDS} seconds"
                )

            self._cached_token = (token, expires_on)

            return AccessToken(token, expires_on)


class ManualAccessTokenCredential:
    """TokenCredential for temporary manual delegated-token smoke tests."""

    def get_token(self, *_scopes, **_kwargs):
        token = _read_manual_access_token()
        if not token:
            raise RuntimeError(f"{MANUAL_ACCESS_TOKEN_ENV} is not set")

        from azure.core.credentials import AccessToken

        return AccessToken(token, _token_expires_on(token))


def use_ephemeral_access_token(token):
    """Use an in-memory delegated access token for this Python process only."""
    global _manual_access_token
    _manual_access_token = token.strip()
    reset_clients()


def _manual_access_token_configured():
    token_file = os.environ.get(MANUAL_ACCESS_TOKEN_FILE_ENV)
    return bool(
        _manual_access_token
        or os.environ.get(MANUAL_ACCESS_TOKEN_ENV)
        or (token_file and Path(token_file).exists())
    )


def _read_manual_access_token():
    if _manual_access_token:
        return _manual_access_token

    token = os.environ.get(MANUAL_ACCESS_TOKEN_ENV, "").strip()
    if token:
        return token

    token_file = os.environ.get(MANUAL_ACCESS_TOKEN_FILE_ENV, "")
    if token_file:
        return Path(token_file).read_text(encoding="utf-8").strip()

    return ""


def _token_expires_on(token):
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


def _parse_broker_token_response(response):
    payload = None
    try:
        payload = response.json()
    except ValueError:
        pass

    if isinstance(payload, dict):
        if payload.get("error"):
            description = payload.get("error_description") or payload["error"]
            raise RuntimeError(f"Broker token request failed: {description}")
        token_type = payload.get("token_type", "Bearer")
        if token_type.lower() != "bearer":
            raise RuntimeError("Broker returned unsupported token type")
        token = payload.get("access_token") or payload.get("accessToken") or payload.get("token")
        if not token:
            raise RuntimeError("Broker token response is missing access_token")
        expires_on = payload.get("expires_on") or payload.get("expiresOn")
        if expires_on:
            return token, int(expires_on)
        expires_in = payload.get("expires_in") or payload.get("expiresIn")
        if expires_in:
            return token, int(time.time()) + int(expires_in)
        return token, _token_expires_on(token)

    text = getattr(response, "text", "").strip()
    if not text:
        raise RuntimeError("Broker token response is empty")
    token = text.removeprefix("Bearer ").strip()
    return token, _token_expires_on(token)


def _is_guid(value):
    return bool(re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        value,
        re.IGNORECASE,
    ))


def _read_saved_config():
    global _config_cache
    if _config_cache is None:
        if not CONFIG_FILE.exists():
            _config_cache = {}
        else:
            try:
                _config_cache = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                _config_cache = {}
    return _config_cache


def _get_config():
    saved = _read_saved_config()
    return (
        os.environ.get("ONELAKE_WORKSPACE") or saved.get("workspace", ""),
        os.environ.get("ONELAKE_LAKEHOUSE") or saved.get("lakehouse", ""),
    )


def configure(workspace, lakehouse):
    """Persist the default workspace and lakehouse selection."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps({"workspace": workspace, "lakehouse": lakehouse}, indent=2) + "\n",
        encoding="utf-8",
    )
    os.environ["ONELAKE_WORKSPACE"] = workspace
    os.environ["ONELAKE_LAKEHOUSE"] = lakehouse
    reset_clients()


connect = configure


def reset_clients():
    global _client, _fs_client, _config_cache
    _client = None
    _fs_client = None
    _config_cache = None


def _build_path(path, lakehouse=None):
    if not lakehouse:
        _, lakehouse = _get_config()
    if not lakehouse:
        raise RuntimeError("ONELAKE_LAKEHOUSE is not set")

    path = path.lstrip("/")
    prefix = lakehouse if _is_guid(lakehouse) else f"{lakehouse}.Lakehouse"
    return f"{prefix}/Files/{path}"


def _strip_prefix(name, lakehouse=None):
    if not lakehouse:
        _, lakehouse = _get_config()
    prefix = f"{lakehouse}/Files/" if _is_guid(lakehouse) else f"{lakehouse}.Lakehouse/Files/"
    return name[len(prefix):] if name.startswith(prefix) else name


def _get_credential():
    if _manual_access_token_configured():
        return ManualAccessTokenCredential()
    return BrokerCredential()


def _get_service_client():
    global _client
    with _client_lock:
        if _client is None:
            from azure.storage.filedatalake import DataLakeServiceClient

            _client = DataLakeServiceClient(
                account_url=os.environ.get("ONELAKE_ENDPOINT", ONELAKE_ENDPOINT),
                credential=_get_credential(),
                retry_total=4,
                retry_backoff_factor=0.5,
            )
    return _client


def _get_fs_client():
    global _fs_client
    with _fs_client_lock:
        if _fs_client is None:
            workspace, _lakehouse = _get_config()
            if not workspace:
                raise RuntimeError("ONELAKE_WORKSPACE is not set")
            _fs_client = _get_service_client().get_file_system_client(file_system=workspace)
    return _fs_client


def _get_file_client(path):
    return _get_fs_client().get_file_client(_build_path(path))


def info():
    """Print non-secret OneLake configuration status."""
    current = status()
    missing = ", ".join(current["missing"]) if current["missing"] else "none"
    workspace, lakehouse = _get_config()
    print(f"OneLake status: {'ready' if current['ready'] else 'not ready'}")
    print(f"Workspace: {workspace or 'N/A'}")
    print(f"Lakehouse: {lakehouse or 'N/A'}")
    print(f"Endpoint: {os.environ.get('ONELAKE_ENDPOINT', ONELAKE_ENDPOINT)}")
    print(f"Auth: {current['auth_mode'] or 'not configured'}")
    print(f"Missing: {missing}")


def status():
    """Return non-secret OneLake readiness state."""
    workspace, lakehouse = _get_config()
    broker_url = os.environ.get("ONELAKE_BROKER_URL", "")
    manual_token_configured = _manual_access_token_configured()
    auth_configured = bool(broker_url) or manual_token_configured
    auth_mode = "manual-token" if manual_token_configured else ("broker" if broker_url else "")
    missing = []
    if not workspace:
        missing.append("ONELAKE_WORKSPACE or saved workspace")
    if not lakehouse:
        missing.append("ONELAKE_LAKEHOUSE or saved lakehouse")
    if not auth_configured:
        missing.append("ONELAKE_BROKER_URL or temporary ONELAKE_ACCESS_TOKEN")
    return {
        "workspace": workspace,
        "lakehouse": lakehouse,
        "endpoint": os.environ.get("ONELAKE_ENDPOINT", ONELAKE_ENDPOINT),
        "auth_mode": auth_mode,
        "auth_configured": auth_configured,
        "broker_configured": bool(broker_url),
        "broker_token_file_configured": bool(os.environ.get("ONELAKE_BROKER_TOKEN_FILE")),
        "manual_access_token_configured": manual_token_configured,
        "missing": missing,
        "ready": not missing,
    }


def _check_import(module_name):
    try:
        importlib.import_module(module_name)
        return {"name": f"Python module {module_name}", "ok": True, "detail": "available"}
    except ImportError as error:
        return {"name": f"Python module {module_name}", "ok": False, "detail": str(error)}


def doctor(check_access=False):
    """Return readiness checks for notebook smoke testing."""
    current = status()
    checks = [
        {
            "name": "Workspace configured",
            "ok": bool(current["workspace"]),
            "detail": current["workspace"] or "set ONELAKE_WORKSPACE or run onelake configure",
        },
        {
            "name": "Lakehouse configured",
            "ok": bool(current["lakehouse"]),
            "detail": current["lakehouse"] or "set ONELAKE_LAKEHOUSE or run onelake configure",
        },
        {
            "name": "OneLake auth path configured",
            "ok": current["auth_configured"],
            "detail": (
                "temporary manual delegated token configured"
                if current["manual_access_token_configured"]
                else "ONELAKE_BROKER_URL is set"
                if current["broker_configured"]
                else "set ONELAKE_BROKER_URL or use a temporary manual token"
            ),
        },
        {
            "name": "Broker session credential",
            "ok": True,
            "detail": (
                "not used with temporary manual token"
                if current["manual_access_token_configured"]
                else "ONELAKE_BROKER_TOKEN_FILE is set"
                if current["broker_token_file_configured"]
                else "not set; broker must authenticate the notebook another way"
            ),
        },
        {"name": "OneLake endpoint", "ok": bool(current["endpoint"]), "detail": current["endpoint"]},
        _check_import("requests"),
        _check_import("azure.storage.filedatalake"),
        _check_import("fsspec"),
    ]
    if check_access:
        try:
            entries = ls("/")
            checks.append({"name": "Live OneLake list", "ok": True, "detail": f"{len(entries)} entries"})
        except Exception as error:
            checks.append({
                "name": "Live OneLake list",
                "ok": False,
                "detail": f"{error.__class__.__name__}: {error}",
            })
    return checks


def ls(path="/"):
    """List files and directories under the active lakehouse Files path."""
    results = []
    for item in _get_fs_client().get_paths(path=_build_path(path)):
        results.append({
            "name": _strip_prefix(item.name),
            "is_directory": bool(item.is_directory),
            "size": getattr(item, "content_length", 0) or 0,
        })
    return results


def read(path, as_text=False):
    """Read a OneLake file as bytes or text."""
    data = _get_file_client(path).download_file().readall()
    return data.decode("utf-8") if as_text else data


def write(path, data):
    """Overwrite a OneLake file."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    _get_file_client(path).upload_data(data, overwrite=True)


def download(remote_path, local_path):
    """Download a OneLake file to local disk."""
    local = Path(local_path)
    local.parent.mkdir(parents=True, exist_ok=True)
    data = _get_file_client(remote_path).download_file()
    with local.open("wb") as handle:
        data.readinto(handle)


def upload(local_path, remote_path):
    """Upload a local file to OneLake."""
    with Path(local_path).open("rb") as handle:
        _get_file_client(remote_path).upload_data(handle, overwrite=True)


def append(path, data):
    """Append bytes or text to a OneLake file through the API."""
    from azure.core.exceptions import ResourceNotFoundError

    if isinstance(data, str):
        data = data.encode("utf-8")
    file_client = _get_file_client(path)
    try:
        offset = int(file_client.get_file_properties().size)
    except ResourceNotFoundError:
        file_client.create_file()
        offset = 0
    file_client.append_data(data, offset=offset, length=len(data))
    file_client.flush_data(offset + len(data))

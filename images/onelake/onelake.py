"""Small OneLake API for Zone Kubeflow notebook containers."""

import io
import json
import os
import re
import threading
from pathlib import Path

import zone_token_broker

ONELAKE_REGION = os.environ.get("ONELAKE_REGION", "canadacentral")
ONELAKE_ENDPOINT = f"https://{ONELAKE_REGION}-onelake.dfs.fabric.microsoft.com"
CONFIG_FILE = Path(os.environ.get("ONELAKE_CONFIG", str(Path.home() / ".onelake" / "config.json")))
MANAGED_ROOTS = ("Files", "Tables")

_client = None
_fs_client = None
_config_cache = None
_client_lock = threading.Lock()
_fs_client_lock = threading.Lock()


def _is_guid(value):
    return bool(re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        str(value or ""),
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


def connect(workspace, lakehouse):
    """Persist the default workspace and lakehouse selection."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps({"workspace": workspace, "lakehouse": lakehouse}, indent=2) + "\n",
        encoding="utf-8",
    )
    os.environ["ONELAKE_WORKSPACE"] = workspace
    os.environ["ONELAKE_LAKEHOUSE"] = lakehouse
    reset_clients()


def reset_clients():
    global _client, _fs_client, _config_cache
    _client = None
    _fs_client = None
    _config_cache = None


def _lakehouse_prefix(lakehouse=None):
    if not lakehouse:
        _, lakehouse = _get_config()
    if not lakehouse:
        raise RuntimeError("ONELAKE_LAKEHOUSE is not set")
    return lakehouse if _is_guid(lakehouse) else f"{lakehouse}.Lakehouse"


def _strip_onelake_url(path):
    path = str(path or "")
    if path.startswith("onelake://"):
        path = path[len("onelake://"):]
    return path


def _normalize_path(path="/"):
    path = _strip_onelake_url(path).replace("\\", "/").strip("/")
    if not path:
        return ""
    first, _, rest = path.partition("/")
    if first in MANAGED_ROOTS:
        return first if not rest else f"{first}/{rest.strip('/')}"
    return f"Files/{path}"


def _require_file_path(path):
    normalized = _normalize_path(path)
    if not normalized or normalized in MANAGED_ROOTS:
        raise RuntimeError("OneLake writes must target a file inside Files/ or Tables/")
    return normalized


def _build_path(path, lakehouse=None):
    normalized = _normalize_path(path)
    if not normalized:
        raise RuntimeError("OneLake root is synthetic and has no DFS path")
    return f"{_lakehouse_prefix(lakehouse)}/{normalized}"


def _strip_prefix(name, lakehouse=None):
    prefix = f"{_lakehouse_prefix(lakehouse)}/"
    return name[len(prefix):] if name.startswith(prefix) else name


def _get_service_client():
    global _client
    with _client_lock:
        if _client is None:
            from azure.storage.filedatalake import DataLakeServiceClient

            _client = DataLakeServiceClient(
                account_url=os.environ.get("ONELAKE_ENDPOINT", ONELAKE_ENDPOINT),
                credential=zone_token_broker.credential(),
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
    return _get_fs_client().get_file_client(_build_path(_require_file_path(path)))


def _read_range(path, start=0, length=None):
    return _get_file_client(path).download_file(offset=start, length=length).readall()


def status(live=False):
    """Return non-secret OneLake readiness state."""
    workspace, lakehouse = _get_config()
    missing = []
    if not workspace:
        missing.append("ONELAKE_WORKSPACE or saved workspace")
    if not lakehouse:
        missing.append("ONELAKE_LAKEHOUSE or saved lakehouse")

    current = {
        "workspace": workspace,
        "lakehouse": lakehouse,
        "endpoint": os.environ.get("ONELAKE_ENDPOINT", ONELAKE_ENDPOINT),
        "broker_url": os.environ.get("ONELAKE_BROKER_URL", zone_token_broker.DEFAULT_BROKER_URL),
        "token_storage": "memory",
        "missing": missing,
        "ready": not missing,
    }
    if live:
        if not current["ready"]:
            current["live"] = {"ok": False, "detail": "missing workspace/lakehouse configuration"}
        else:
            try:
                entries = ls("Files")
                current["live"] = {"ok": True, "detail": f"{len(entries)} entries under Files"}
            except Exception as error:
                current["live"] = {"ok": False, "detail": f"{error.__class__.__name__}: {error}"}
    return current


def ls(path="/"):
    """List OneLake files and directories."""
    normalized = _normalize_path(path)
    if not normalized:
        return [
            {"name": "Files", "is_directory": True, "size": 0},
            {"name": "Tables", "is_directory": True, "size": 0},
        ]

    results = []
    for item in _get_fs_client().get_paths(path=_build_path(normalized), recursive=False):
        results.append({
            "name": _strip_prefix(item.name).rstrip("/"),
            "is_directory": bool(item.is_directory),
            "size": getattr(item, "content_length", 0) or 0,
        })
    return results


def read(path, text=False):
    """Read a OneLake file as bytes or text."""
    data = _get_file_client(path).download_file().readall()
    return data.decode("utf-8") if text else data


def write(path, data):
    """Overwrite a OneLake file."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    _get_file_client(path).upload_data(data, overwrite=True)


class _BinaryUploadBuffer(io.BytesIO):
    def __init__(self, path):
        super().__init__()
        self._path = path

    def close(self):
        if not self.closed:
            write(self._path, self.getvalue())
        super().close()


class _TextUploadBuffer(io.StringIO):
    def __init__(self, path):
        super().__init__()
        self._path = path

    def close(self):
        if not self.closed:
            write(self._path, self.getvalue())
        super().close()


def open(path, mode="rb"):
    """Open a OneLake file for simple full-file reads or overwrites."""
    if "+" in mode or "a" in mode:
        raise ValueError("OneLake open supports read or overwrite modes only")
    if "r" in mode:
        data = read(path, text="b" not in mode)
        return io.BytesIO(data) if "b" in mode else io.StringIO(data)
    if "w" in mode:
        _require_file_path(path)
        return _BinaryUploadBuffer(path) if "b" in mode else _TextUploadBuffer(path)
    raise ValueError(f"unsupported mode: {mode}")


def download(path, local_path):
    """Download a OneLake file to local disk."""
    local = Path(local_path)
    local.parent.mkdir(parents=True, exist_ok=True)
    data = _get_file_client(path).download_file()
    with local.open("wb") as handle:
        data.readinto(handle)


def upload(local_path, path):
    """Upload a local file to OneLake."""
    with Path(local_path).open("rb") as handle:
        _get_file_client(path).upload_data(handle, overwrite=True)

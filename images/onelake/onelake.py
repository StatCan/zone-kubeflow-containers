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
_fs_clients = {}
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


def _clean_path(path="/"):
    return _strip_onelake_url(path).replace("\\", "/").strip("/")


def _connection(workspace, lakehouse):
    workspace = str(workspace or "").strip()
    lakehouse = str(lakehouse or "").strip()
    if not workspace or not lakehouse:
        return None
    return {"workspace": workspace, "lakehouse": lakehouse}


def _parse_connection(value):
    if isinstance(value, dict):
        return _connection(value.get("workspace"), value.get("lakehouse"))
    if isinstance(value, str) and "/" in value:
        workspace, lakehouse = value.split("/", 1)
        return _connection(workspace, lakehouse)
    return None


def _read_env_connections():
    raw = os.environ.get("ONELAKE_CONNECTIONS", "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = [item.strip() for item in raw.split(";") if item.strip()]

    if isinstance(parsed, dict) and "connections" in parsed:
        parsed = parsed.get("connections", [])
    elif isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    return [conn for conn in (_parse_connection(item) for item in parsed) if conn]


def connections():
    """Return configured OneLake workspace/lakehouse pairs."""
    saved = _read_saved_config()
    configured = []

    workspace, lakehouse = _get_config()
    default = _connection(workspace, lakehouse)
    if default:
        configured.append(default)

    configured.extend(_read_env_connections())
    configured.extend(
        conn for conn in (_parse_connection(item) for item in saved.get("connections", [])) if conn
    )

    seen = set()
    unique = []
    for conn in configured:
        key = (conn["workspace"], conn["lakehouse"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(conn)
    return unique


def _default_connection():
    workspace, lakehouse = _get_config()
    default = _connection(workspace, lakehouse)
    if default:
        return default
    configured = connections()
    if len(configured) == 1:
        return configured[0]
    return None


def connect(workspace, lakehouse):
    """Persist the default workspace and lakehouse selection."""
    new_connection = _connection(workspace, lakehouse)
    if not new_connection:
        raise RuntimeError("workspace and lakehouse are required")

    saved = _read_saved_config()
    saved_connections = [
        conn for conn in (_parse_connection(item) for item in saved.get("connections", [])) if conn
    ]
    merged = [new_connection, *saved_connections]
    seen = set()
    unique = []
    for conn in merged:
        key = (conn["workspace"], conn["lakehouse"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(conn)

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps({
            "workspace": new_connection["workspace"],
            "lakehouse": new_connection["lakehouse"],
            "connections": unique,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    os.environ["ONELAKE_WORKSPACE"] = new_connection["workspace"]
    os.environ["ONELAKE_LAKEHOUSE"] = new_connection["lakehouse"]
    reset_clients()


def reset_clients():
    global _client, _fs_clients, _config_cache
    _client = None
    _fs_clients = {}
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
    path = _clean_path(path)
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


def _require_directory_path(path):
    normalized = _normalize_path(path)
    if not normalized or normalized in MANAGED_ROOTS:
        raise RuntimeError("OneLake directories must be inside Files/ or Tables/")
    return normalized


def _build_path(path, lakehouse=None):
    normalized = _normalize_path(path)
    if not normalized:
        raise RuntimeError("OneLake root is synthetic and has no DFS path")
    return f"{_lakehouse_prefix(lakehouse)}/{normalized}"


def _strip_prefix(name, lakehouse=None):
    prefix = f"{_lakehouse_prefix(lakehouse)}/"
    return name[len(prefix):] if name.startswith(prefix) else name


def _connection_prefix(connection):
    return f"{connection['workspace']}/{connection['lakehouse']}"


def _match_connection(path):
    parts = _clean_path(path).split("/")
    if len(parts) < 2:
        return None, ""
    for conn in connections():
        lakehouse_names = {conn["lakehouse"], _lakehouse_prefix(conn["lakehouse"])}
        if parts[0] == conn["workspace"] and parts[1] in lakehouse_names:
            return conn, "/".join(parts[2:])
    return None, ""


def _resolve_path(path="/"):
    matched, remainder = _match_connection(path)
    if matched:
        return matched, _normalize_path(remainder), True

    default = _default_connection()
    if not default:
        raise RuntimeError("OneLake workspace/lakehouse is not configured")
    return default, _normalize_path(path), False


def _display_name(connection, remote_name, qualified):
    if not qualified:
        return remote_name
    return f"{_connection_prefix(connection)}/{remote_name}".rstrip("/")


def _synthetic_entry(name):
    return {"name": name, "is_directory": True, "size": 0}


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


def _get_fs_client(workspace=None):
    global _fs_clients
    with _fs_client_lock:
        if not workspace:
            default = _default_connection()
            if not default:
                raise RuntimeError("OneLake workspace/lakehouse is not configured")
            workspace = default["workspace"]
        if workspace not in _fs_clients:
            _fs_clients[workspace] = _get_service_client().get_file_system_client(file_system=workspace)
    return _fs_clients[workspace]


def _get_file_client(path, connection=None):
    if connection is None:
        connection, remote_path, _qualified = _resolve_path(path)
    else:
        remote_path = _normalize_path(path)
    remote_path = _require_file_path(remote_path)
    return _get_fs_client(connection["workspace"]).get_file_client(
        _build_path(remote_path, connection["lakehouse"])
    )


def _get_directory_client(path, connection=None):
    if connection is None:
        connection, remote_path, _qualified = _resolve_path(path)
    else:
        remote_path = _normalize_path(path)
    return _get_fs_client(connection["workspace"]).get_directory_client(
        _build_path(_require_directory_path(remote_path), connection["lakehouse"])
    )


def _read_range(path, start=0, length=None):
    return _get_file_client(path).download_file(offset=start, length=length).readall()


def status(live=False):
    """Return non-secret OneLake readiness state."""
    configured = connections()
    default = _default_connection()
    workspace = default["workspace"] if default else ""
    lakehouse = default["lakehouse"] if default else ""
    missing = []
    if not configured:
        missing.append("ONELAKE_WORKSPACE/ONELAKE_LAKEHOUSE, ONELAKE_CONNECTIONS, or saved config")

    current = {
        "workspace": workspace,
        "lakehouse": lakehouse,
        "connections": configured,
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
                live_root = "Files" if default else f"{_connection_prefix(configured[0])}/Files"
                entries = ls(live_root)
                current["live"] = {"ok": True, "detail": f"{len(entries)} entries under Files"}
            except Exception as error:
                current["live"] = {"ok": False, "detail": f"{error.__class__.__name__}: {error}"}
    return current


def ls(path="/"):
    """List OneLake files and directories."""
    clean = _clean_path(path)
    configured = connections()
    if not clean:
        if len(configured) > 1:
            workspaces = []
            seen = set()
            for conn in configured:
                if conn["workspace"] in seen:
                    continue
                seen.add(conn["workspace"])
                workspaces.append(_synthetic_entry(conn["workspace"]))
            return workspaces
        return [_synthetic_entry("Files"), _synthetic_entry("Tables")]

    workspace_matches = [conn for conn in configured if conn["workspace"] == clean]
    if workspace_matches:
        return [_synthetic_entry(_connection_prefix(conn)) for conn in workspace_matches]

    connection, normalized, qualified = _resolve_path(path)
    if not normalized:
        return [
            _synthetic_entry(_display_name(connection, "Files", qualified)),
            _synthetic_entry(_display_name(connection, "Tables", qualified)),
        ]

    results = []
    fs_client = _get_fs_client(connection["workspace"])
    for item in fs_client.get_paths(path=_build_path(normalized, connection["lakehouse"]), recursive=False):
        remote_name = _strip_prefix(item.name, connection["lakehouse"]).rstrip("/")
        results.append({
            "name": _display_name(connection, remote_name, qualified),
            "is_directory": bool(item.is_directory),
            "size": getattr(item, "content_length", 0) or 0,
        })
    return results


def info(path):
    """Return basic OneLake file or directory metadata."""
    clean = _clean_path(path)
    configured = connections()
    if not clean:
        return _synthetic_entry("")
    if any(conn["workspace"] == clean for conn in configured):
        return _synthetic_entry(clean)

    connection, normalized, qualified = _resolve_path(path)
    if not normalized:
        return _synthetic_entry(_connection_prefix(connection) if qualified else "")
    if normalized in MANAGED_ROOTS:
        return _synthetic_entry(_display_name(connection, normalized, qualified))

    try:
        props = _get_file_client(normalized, connection).get_file_properties()
    except Exception as error:
        if error.__class__.__name__ == "ResourceNotFoundError":
            raise FileNotFoundError(path)
        raise

    is_dir = dict(getattr(props, "metadata", None) or {}).get("hdi_isfolder") == "true"
    return {
        "name": _display_name(connection, normalized, qualified),
        "is_directory": is_dir,
        "size": 0 if is_dir else int(getattr(props, "size", 0) or 0),
    }


def read(path, text=False):
    """Read a OneLake file as bytes or text."""
    data = _get_file_client(path).download_file().readall()
    return data.decode("utf-8") if text else data


def write(path, data):
    """Overwrite a OneLake file."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    _get_file_client(path).upload_data(data, overwrite=True)


def mkdir(path):
    """Create a OneLake directory inside Files/ or Tables/."""
    _get_directory_client(path).create_directory()


def rm(path):
    """Delete a OneLake file or directory."""
    current = info(path)
    if current["is_directory"]:
        _get_directory_client(path).delete_directory()
    else:
        _get_file_client(path).delete_file()


def mv(old_path, new_path):
    """Rename a OneLake file or directory within the same workspace."""
    old_connection, old_remote, _old_qualified = _resolve_path(old_path)
    new_connection, new_remote, _new_qualified = _resolve_path(new_path)
    if old_connection["workspace"] != new_connection["workspace"]:
        raise RuntimeError("OneLake rename cannot move files between workspaces")
    target = f"{new_connection['workspace']}/{_build_path(new_remote, new_connection['lakehouse'])}"
    if info(old_path)["is_directory"]:
        _get_directory_client(old_remote, old_connection).rename_directory(target)
    else:
        _get_file_client(old_remote, old_connection).rename_file(target)


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
        _connection, remote_path, _qualified = _resolve_path(path)
        _require_file_path(remote_path)
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

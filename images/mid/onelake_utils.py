"""
OneLake utility module for Zone Kubeflow containers.

Provides simple functions to interact with Microsoft OneLake (ADLS Gen2)
storage from within JupyterLab, VS Code, or any Python environment.

Usage:
    import onelake_utils as onelake

    onelake.info()              # Show connection status
    onelake.ls("/")             # List files at root
    onelake.read("data.csv")    # Read a file
    onelake.write("out.csv", d) # Write data
    onelake.download("data.csv", "local.csv")
    onelake.upload("local.csv", "data.csv")

    # Switch workspace/lakehouse on the fly
    onelake.connect(workspace="<guid>", lakehouse="<guid>")
    onelake.ls("/")             # Now lists the new workspace
"""

import json
import os
import re
from pathlib import Path

# Lazy imports - only loaded on first use to keep import fast
_client = None
_fs_client = None

# OneLake DFS endpoint (ADLS Gen2 compatible)
ONELAKE_ENDPOINT = "https://onelake.dfs.fabric.microsoft.com"

# Messages in EN/FR
_MSG = {
    "en": {
        "no_workspace": "ONELAKE_WORKSPACE is not set. Use onelake.connect(workspace='...', lakehouse='...') or contact your admin.",
        "no_lakehouse": "ONELAKE_LAKEHOUSE is not set. Use onelake.connect(workspace='...', lakehouse='...') or contact your admin.",
        "auth_fail": "Authentication failed. Ensure your pod has valid credentials (Workload Identity or SPN).",
        "connected": "Connected",
        "not_configured": "Not configured",
        "status": "Status",
        "workspace": "Workspace",
        "lakehouse": "Lakehouse",
        "endpoint": "Endpoint",
        "base_path": "Base path",
        "switched": "Switched to workspace '{ws}', lakehouse '{lh}'",
    },
    "fr": {
        "no_workspace": "ONELAKE_WORKSPACE n'est pas defini. Utilisez onelake.connect(workspace='...', lakehouse='...') ou contactez votre admin.",
        "no_lakehouse": "ONELAKE_LAKEHOUSE n'est pas defini. Utilisez onelake.connect(workspace='...', lakehouse='...') ou contactez votre admin.",
        "auth_fail": "Echec d'authentification. Verifiez les identifiants du pod (Workload Identity ou SPN).",
        "connected": "Connecte",
        "not_configured": "Non configure",
        "status": "Statut",
        "workspace": "Espace de travail",
        "lakehouse": "Lakehouse",
        "endpoint": "Point de terminaison",
        "base_path": "Chemin de base",
        "switched": "Bascule vers l'espace de travail '{ws}', lakehouse '{lh}'",
    },
}


def _lang():
    """Return 'fr' if user locale is French, else 'en'."""
    lang = os.environ.get("LANG", "en_US")
    return "fr" if lang.startswith("fr") else "en"


def _msg(key):
    """Get a bilingual message."""
    return _MSG[_lang()].get(key, _MSG["en"].get(key, key))


def _get_config():
    """Read OneLake configuration from environment variables."""
    workspace = os.environ.get("ONELAKE_WORKSPACE", "")
    lakehouse = os.environ.get("ONELAKE_LAKEHOUSE", "")
    return workspace, lakehouse


def _get_credential():
    """Get Azure credential using DefaultAzureCredential (lazy)."""
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential()


def _get_service_client():
    """Get or create the DataLakeServiceClient (singleton, lazy)."""
    global _client
    if _client is not None:
        return _client

    workspace, lakehouse = _get_config()
    if not workspace:
        raise RuntimeError(_msg("no_workspace"))

    from azure.storage.filedatalake import DataLakeServiceClient

    _client = DataLakeServiceClient(
        account_url=ONELAKE_ENDPOINT,
        credential=_get_credential(),
    )
    return _client


def _get_fs_client():
    """Get or create the FileSystemClient for the user's workspace (singleton, lazy)."""
    global _fs_client
    if _fs_client is not None:
        return _fs_client

    workspace, lakehouse = _get_config()
    if not workspace:
        raise RuntimeError(_msg("no_workspace"))

    _fs_client = _get_service_client().get_file_system_client(file_system=workspace)
    return _fs_client


def _is_guid(value):
    """Check if a string looks like a GUID/UUID."""
    return bool(re.match(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        value, re.IGNORECASE,
    ))


def _build_path(path, lakehouse=None):
    """Build the full OneLake path including lakehouse prefix.

    Users pass paths relative to their lakehouse Files directory.
    With friendly names: "<name>.Lakehouse/Files/<path>"
    With GUIDs:          "<guid>/Files/<path>"
    """
    if not lakehouse:
        _, lakehouse = _get_config()
    if not lakehouse:
        raise RuntimeError(_msg("no_lakehouse"))

    path = path.lstrip("/")
    if _is_guid(lakehouse):
        return f"{lakehouse}/Files/{path}"
    return f"{lakehouse}.Lakehouse/Files/{path}"


def _strip_prefix(name, lakehouse=None):
    """Strip the lakehouse/Files prefix from a path for clean display."""
    if not lakehouse:
        _, lakehouse = _get_config()
    prefix = f"{lakehouse}/Files/" if _is_guid(lakehouse) else f"{lakehouse}.Lakehouse/Files/"
    if name.startswith(prefix):
        return name[len(prefix):]
    return name


def connect(workspace, lakehouse):
    """Switch to a different workspace and lakehouse.

    Args:
        workspace: Workspace name or GUID.
        lakehouse: Lakehouse name or GUID.

    Usage:
        onelake.connect("1dd0411c-...", "88dd60d0-...")
        onelake.ls("/")  # now lists files in the new workspace
    """
    global _client, _fs_client
    os.environ["ONELAKE_WORKSPACE"] = workspace
    os.environ["ONELAKE_LAKEHOUSE"] = lakehouse
    # Reset cached clients so they reconnect to the new workspace
    _client = None
    _fs_client = None
    print(_msg("switched").format(ws=workspace, lh=lakehouse))


def info():
    """Print OneLake connection status."""
    workspace, lakehouse = _get_config()

    status = _msg("connected") if (workspace and lakehouse) else _msg("not_configured")

    print(f"  OneLake {_msg('status')}: {status}")
    print(f"  {_msg('workspace')}: {workspace or 'N/A'}")
    print(f"  {_msg('lakehouse')}: {lakehouse or 'N/A'}")
    print(f"  {_msg('endpoint')}: {ONELAKE_ENDPOINT}")
    if workspace and lakehouse:
        base = f"{lakehouse}/Files/" if _is_guid(lakehouse) else f"{lakehouse}.Lakehouse/Files/"
        print(f"  {_msg('base_path')}: {base}")


def ls(path="/"):
    """List files and directories at the given path.

    Args:
        path: Path relative to the lakehouse Files directory. Default "/".

    Returns:
        List of dicts with 'name', 'is_directory', and 'size' keys.
    """
    fs = _get_fs_client()
    full_path = _build_path(path)
    results = []
    for item in fs.get_paths(path=full_path):
        results.append({
            "name": _strip_prefix(item.name),
            "is_directory": item.is_directory,
            "size": getattr(item, "content_length", 0),
        })
    return results


def download(remote_path, local_path):
    """Download a file from OneLake to local filesystem.

    Args:
        remote_path: Path in OneLake (relative to lakehouse Files/).
        local_path: Local destination path.
    """
    fs = _get_fs_client()
    full_path = _build_path(remote_path)
    file_client = fs.get_file_client(full_path)

    local = Path(local_path)
    local.parent.mkdir(parents=True, exist_ok=True)

    with open(local, "wb") as f:
        data = file_client.download_file()
        data.readinto(f)


def upload(local_path, remote_path):
    """Upload a local file to OneLake.

    Args:
        local_path: Local file path.
        remote_path: Destination path in OneLake (relative to lakehouse Files/).
    """
    fs = _get_fs_client()
    full_path = _build_path(remote_path)
    file_client = fs.get_file_client(full_path)

    with open(local_path, "rb") as f:
        file_client.upload_data(f, overwrite=True)


def read(path, as_text=False):
    """Read a file from OneLake and return its contents.

    Args:
        path: Path in OneLake (relative to lakehouse Files/).
        as_text: If True, return as string. Otherwise return bytes.

    Returns:
        File contents as bytes or string.
    """
    fs = _get_fs_client()
    full_path = _build_path(path)
    file_client = fs.get_file_client(full_path)
    data = file_client.download_file().readall()
    return data.decode("utf-8") if as_text else data


def write(path, data):
    """Write data to a file on OneLake.

    Args:
        path: Destination path in OneLake (relative to lakehouse Files/).
        data: bytes or string to write.
    """
    fs = _get_fs_client()
    full_path = _build_path(path)
    file_client = fs.get_file_client(full_path)

    if isinstance(data, str):
        data = data.encode("utf-8")
    file_client.upload_data(data, overwrite=True)

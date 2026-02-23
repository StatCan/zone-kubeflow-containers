"""
OneLake utility module for Zone Kubeflow containers.

Provides simple functions to interact with Microsoft OneLake (ADLS Gen2)
storage from within JupyterLab, VS Code, or any Python environment.

Usage:
    import onelake_utils as onelake

    onelake.info()              # Show connection status
    onelake.ls("/")             # List files at root
    onelake.download("data.csv", "local.csv")
    onelake.upload("local.csv", "data.csv")
"""

import json
import os
from pathlib import Path

# Lazy imports - only loaded on first use to keep import fast
_client = None
_fs_client = None

# OneLake DFS endpoint (ADLS Gen2 compatible)
ONELAKE_ENDPOINT = "https://onelake.dfs.fabric.microsoft.com"

# Messages in EN/FR
_MSG = {
    "en": {
        "no_workspace": "ONELAKE_WORKSPACE is not set. Contact your admin to enable OneLake for your namespace.",
        "no_lakehouse": "ONELAKE_LAKEHOUSE is not set. Contact your admin to configure your lakehouse.",
        "auth_fail": "Authentication failed. Ensure your pod has valid credentials (Workload Identity or SPN).",
        "connected": "Connected",
        "not_configured": "Not configured",
        "status": "Status",
        "workspace": "Workspace",
        "lakehouse": "Lakehouse",
        "endpoint": "Endpoint",
        "base_path": "Base path",
    },
    "fr": {
        "no_workspace": "ONELAKE_WORKSPACE n'est pas defini. Contactez votre admin pour activer OneLake.",
        "no_lakehouse": "ONELAKE_LAKEHOUSE n'est pas defini. Contactez votre admin pour configurer votre lakehouse.",
        "auth_fail": "Echec d'authentification. Verifiez les identifiants du pod (Workload Identity ou SPN).",
        "connected": "Connecte",
        "not_configured": "Non configure",
        "status": "Statut",
        "workspace": "Espace de travail",
        "lakehouse": "Lakehouse",
        "endpoint": "Point de terminaison",
        "base_path": "Chemin de base",
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


def _build_path(path):
    """Build the full OneLake path including lakehouse prefix.

    Users pass paths relative to their lakehouse Files directory.
    e.g., "data.csv" becomes "<lakehouse>.Lakehouse/Files/data.csv"
    """
    _, lakehouse = _get_config()
    if not lakehouse:
        raise RuntimeError(_msg("no_lakehouse"))

    path = path.lstrip("/")
    return f"{lakehouse}.Lakehouse/Files/{path}"


def info():
    """Print OneLake connection status."""
    workspace, lakehouse = _get_config()
    lang = _lang()

    status = _msg("connected") if (workspace and lakehouse) else _msg("not_configured")

    print(f"  OneLake {_msg('status')}: {status}")
    print(f"  {_msg('workspace')}: {workspace or 'N/A'}")
    print(f"  {_msg('lakehouse')}: {lakehouse or 'N/A'}")
    print(f"  {_msg('endpoint')}: {ONELAKE_ENDPOINT}")
    if workspace and lakehouse:
        print(f"  {_msg('base_path')}: {lakehouse}.Lakehouse/Files/")


def ls(path="/", workspace=None):
    """List files and directories at the given path.

    Args:
        path: Path relative to the lakehouse Files directory. Default "/".
        workspace: Optional workspace override for cross-workspace access.

    Returns:
        List of dicts with 'name', 'is_directory', and 'size' keys.
    """
    fs = _get_fs_client()
    if workspace:
        fs = _get_service_client().get_file_system_client(file_system=workspace)

    full_path = _build_path(path)
    results = []
    for item in fs.get_paths(path=full_path):
        name = item.name
        # Strip the lakehouse prefix for cleaner display
        _, lh = _get_config()
        prefix = f"{lh}.Lakehouse/Files/"
        if name.startswith(prefix):
            name = name[len(prefix):]
        results.append({
            "name": name,
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

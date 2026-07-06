"""Azure Storage and OneLake tools: list, bring here, push back.

URLs are the az://, abfs:// or abfss:// form users copy from the portal or
Fabric, with the account in the host: abfss://<container>@<account>.dfs.
core.windows.net/path or abfss://<workspace>@onelake.dfs.fabric.microsoft.
com/<item>/Files/path. Credentials follow the same chain as everything on
Zone: the AuthService broker's delegated user token, falling back to
azure-identity (`az login`) off-platform. Downloads and uploads are
approval-gated — upload is the one tool that moves data out of the pod.
"""

from urllib.parse import urlsplit

STORAGE_SCOPE = "https://storage.azure.com/.default"
MAX_LS_ENTRIES = 200

DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "azure_ls",
            "description": (
                "List a path in Azure Storage (ADLS/Blob) or OneLake. Takes a "
                "full az:// or abfss:// URL with the account in the host."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "e.g. abfss://container@account.dfs.core.windows.net/path"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "azure_download",
            "description": (
                "Download a file or directory from Azure Storage / OneLake "
                "into the workspace (directories copy recursively)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Remote az:// / abfss:// URL."},
                    "dest": {"type": "string", "description": "Local destination path."},
                },
                "required": ["url", "dest"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "azure_upload",
            "description": (
                "Upload a local file or directory to Azure Storage / OneLake "
                "(directories copy recursively). This sends data out of the "
                "pod, as the signed-in user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "src": {"type": "string", "description": "Local source path."},
                    "url": {"type": "string", "description": "Remote az:// / abfss:// URL destination."},
                },
                "required": ["src", "url"],
            },
        },
    },
]

_state = {}


def _credential():
    """Async credential for adlfs: broker on-platform, azure-identity locally."""
    if "credential" in _state:
        return _state["credential"]
    import zone_token_broker

    try:
        zone_token_broker.get_token(STORAGE_SCOPE)  # cheap probe; cached by the client
        credential = zone_token_broker.async_credential(STORAGE_SCOPE)
    except Exception:
        try:
            from azure.identity.aio import DefaultAzureCredential
        except ImportError as error:
            raise RuntimeError(
                "token broker unavailable and azure-identity is not installed "
                "for local fallback (pip install azure-identity)"
            ) from error
        credential = DefaultAzureCredential()
    _state["credential"] = credential
    return credential


def _fs_and_path(url):
    """Parse an az/abfs/abfss URL into an adlfs filesystem and container path."""
    from adlfs import AzureBlobFileSystem

    parts = urlsplit(url)
    if parts.scheme not in ("az", "abfs", "abfss"):
        raise ValueError("use an az://, abfs:// or abfss:// URL, got %r" % url)
    if "@" not in parts.netloc:
        raise ValueError(
            "URL must carry the account: %s://<container>@<account host>/<path>" % parts.scheme
        )
    container, host = parts.netloc.split("@", 1)
    account = host.split(".", 1)[0]
    options = {"anon": False, "credential": _credential()}
    if "fabric.microsoft.com" in host:
        # OneLake speaks the same API under one fixed account name; adlfs
        # needs the blob endpoint even when the URL was copied as dfs.
        options["account_name"] = "onelake"
        options["account_host"] = host.replace(".dfs.", ".blob.")
    else:
        options["account_name"] = account
    return AzureBlobFileSystem(**options), container + "/" + parts.path.lstrip("/")


def azure_ls(url):
    fs, path = _fs_and_path(url)
    entries = fs.ls(path, detail=True)
    lines = []
    for entry in entries[:MAX_LS_ENTRIES]:
        name = entry["name"]
        if entry.get("type") == "directory":
            lines.append(name + "/")
        else:
            lines.append("%s  (%s bytes)" % (name, entry.get("size", "?")))
    if len(entries) > MAX_LS_ENTRIES:
        lines.append("... (%d more entries)" % (len(entries) - MAX_LS_ENTRIES))
    return "\n".join(lines) or "(empty)"


def azure_download(url, dest):
    import pathlib

    fs, path = _fs_and_path(url)
    target = pathlib.Path(dest).expanduser()
    recursive = fs.isdir(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fs.get(path, str(target), recursive=recursive)
    return "Downloaded %s to %s%s" % (url, target, " (recursive)" if recursive else "")


def azure_upload(src, url):
    import pathlib

    source = pathlib.Path(src).expanduser()
    if not source.exists():
        return "error: %s does not exist" % source
    fs, path = _fs_and_path(url)
    fs.put(str(source), path, recursive=source.is_dir())
    return "Uploaded %s to %s%s" % (source, url, " (recursive)" if source.is_dir() else "")


HANDLERS = {"azure_ls": azure_ls, "azure_download": azure_download, "azure_upload": azure_upload}
MUTATING = frozenset({"azure_download", "azure_upload"})

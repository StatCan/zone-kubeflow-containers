"""fsspec backend used by jupyter-fs to show OneLake in JupyterLab."""

from __future__ import annotations

from datetime import datetime, timezone

from azure.core.exceptions import ResourceNotFoundError
from fsspec.spec import AbstractBufferedFile, AbstractFileSystem

import onelake_utils as onelake


_MARKER = "_ONELAKE_NOT_CONFIGURED.txt"
_MARKER_TEXT = (
    "OneLake is not configured for this notebook yet.\n\n"
    "The platform must set ONELAKE_BROKER_URL for delegated user auth. "
    "For initial smoke tests only, the Jupyter server process may use a temporary "
    "delegated token through ONELAKE_ACCESS_TOKEN or ONELAKE_ACCESS_TOKEN_FILE. "
    "Workspace and lakehouse can be injected by the platform or saved with "
    "onelake configure <workspace> <lakehouse>.\n"
)


def _clean(path):
    return str(path or "").replace("\\", "/").strip("/")


def _now():
    return datetime.now(timezone.utc).timestamp()


class OneLakeFile(AbstractBufferedFile):
    def _fetch_range(self, start, end):
        file_client = onelake._get_file_client(self.path)
        return file_client.download_file(offset=start, length=end - start).readall()

    def _upload_chunk(self, final=False):
        if not final:
            return False
        self.buffer.seek(0)
        onelake.write(self.path, self.buffer.read())
        return True


class OneLakeFileSystem(AbstractFileSystem):
    protocol = "onelake"
    root_marker = "/"

    def __init__(self, **_kwargs):
        super().__init__(**_kwargs)

    @classmethod
    def _strip_protocol(cls, path):
        path = str(path or "")
        if path.startswith("onelake://"):
            path = path[len("onelake://"):]
        return "/" + _clean(path) if _clean(path) else "/"

    def _configured(self):
        return onelake.status()["ready"]

    def _marker_info(self):
        return {
            "name": _MARKER,
            "type": "file",
            "size": len(_MARKER_TEXT.encode("utf-8")),
            "created": _now(),
            "mtime": _now(),
        }

    def ls(self, path, detail=True, **_kwargs):
        path = _clean(self._strip_protocol(path))
        if not self._configured():
            entries = [self._marker_info()] if path == "" else []
            return entries if detail else [entry["name"] for entry in entries]

        entries = []
        for item in onelake.ls(path):
            entries.append({
                "name": item["name"].rstrip("/"),
                "type": "directory" if item["is_directory"] else "file",
                "size": item["size"],
                "created": _now(),
                "mtime": _now(),
            })
        return entries if detail else [entry["name"] for entry in entries]

    def info(self, path, **_kwargs):
        path = _clean(self._strip_protocol(path))
        if path == "":
            return {"name": "", "type": "directory", "size": 0, "created": _now(), "mtime": _now()}
        if not self._configured():
            if path == _MARKER:
                return self._marker_info()
            raise FileNotFoundError(path)

        try:
            props = onelake._get_file_client(path).get_file_properties()
        except ResourceNotFoundError:
            raise FileNotFoundError(path)

        is_dir = dict(getattr(props, "metadata", None) or {}).get("hdi_isfolder") == "true"
        return {
            "name": path,
            "type": "directory" if is_dir else "file",
            "size": 0 if is_dir else int(getattr(props, "size", 0) or 0),
            "created": _now(),
            "mtime": _now(),
        }

    def exists(self, path, **_kwargs):
        try:
            self.info(path)
            return True
        except FileNotFoundError:
            return False

    def isdir(self, path):
        try:
            return self.info(path)["type"] == "directory"
        except FileNotFoundError:
            return False

    def isfile(self, path):
        try:
            return self.info(path)["type"] == "file"
        except FileNotFoundError:
            return False

    def _open(self, path, mode="rb", block_size=None, **kwargs):
        path = _clean(self._strip_protocol(path))
        return OneLakeFile(
            self,
            path,
            mode=mode,
            block_size=block_size or 5 * 1024 * 1024,
            **kwargs,
        )

    def cat_file(self, path, start=None, end=None, **_kwargs):
        path = _clean(self._strip_protocol(path))
        if not self._configured() and path == _MARKER:
            data = _MARKER_TEXT.encode("utf-8")
        elif start is not None or end is not None:
            start = start or 0
            length = None if end is None else end - start
            return onelake._get_file_client(path).download_file(offset=start, length=length).readall()
        else:
            data = onelake.read(path)
        return data[slice(start, end)]

    def cat(self, path, recursive=False, on_error="raise", **kwargs):
        if recursive:
            raise NotImplementedError("recursive cat is not supported for OneLake")
        return self.cat_file(path, **kwargs)

    def pipe_file(self, path, value, **_kwargs):
        onelake.write(_clean(self._strip_protocol(path)), value)

    def pipe(self, path, value=None, **kwargs):
        if not isinstance(path, str):
            raise ValueError("path must be a string")
        self.pipe_file(path, value, **kwargs)

    def mkdir(self, path, create_parents=True, **_kwargs):
        onelake._get_fs_client().get_directory_client(onelake._build_path(path)).create_directory()

    def rm(self, path, recursive=False, **_kwargs):
        path = _clean(self._strip_protocol(path))
        if self.isdir(path):
            onelake._get_fs_client().get_directory_client(onelake._build_path(path)).delete_directory()
        else:
            onelake._get_file_client(path).delete_file()

    def mv(self, path1, path2, **_kwargs):
        src = _clean(self._strip_protocol(path1))
        workspace, _lakehouse = onelake._get_config()
        dst = f"{workspace}/{onelake._build_path(_clean(self._strip_protocol(path2)))}"
        if self.isdir(src):
            onelake._get_fs_client().get_directory_client(onelake._build_path(src)).rename_directory(dst)
        else:
            onelake._get_file_client(src).rename_file(dst)

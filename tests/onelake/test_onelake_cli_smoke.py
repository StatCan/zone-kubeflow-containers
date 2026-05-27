import base64
import importlib.util
import io
import json
import sys
import time
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _jwt():
    def encode(payload):
        data = json.dumps(payload).encode("utf-8")
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode({'exp': int(time.time()) + 3600})}.sig"


class _Download:
    def __init__(self, data):
        self._data = data

    def readall(self):
        return self._data

    def readinto(self, handle):
        handle.write(self._data)


class _PathItem:
    def __init__(self, name, is_directory=False, content_length=0):
        self.name = name
        self.is_directory = is_directory
        self.content_length = content_length


def _install_fake_dependencies(monkeypatch, store, token_calls):
    class Response:
        text = _jwt()

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, params, timeout):
            token_calls.append({"url": url, "scope": params["scope"], "timeout": timeout})
            return Response()

    requests_module = types.ModuleType("requests")
    requests_module.Session = Session

    class FileClient:
        def __init__(self, path):
            self.path = path

        def upload_data(self, data, overwrite=True):
            if hasattr(data, "read"):
                data = data.read()
            if isinstance(data, str):
                data = data.encode("utf-8")
            store[self.path] = bytes(data)

        def download_file(self, offset=0, length=None):
            data = store[self.path]
            end = None if length is None else offset + length
            return _Download(data[offset:end])

    class FileSystemClient:
        def __init__(self, workspace):
            self.workspace = workspace

        def get_file_client(self, path):
            return FileClient(path)

        def get_paths(self, path, recursive=False):
            prefix = f"{path.rstrip('/')}/"
            seen = set()
            for name, data in store.items():
                if not name.startswith(prefix):
                    continue
                remainder = name[len(prefix):]
                first = remainder.split("/", 1)[0]
                child = f"{prefix}{first}".rstrip("/")
                if child in seen:
                    continue
                seen.add(child)
                yield _PathItem(child, "/" in remainder, 0 if "/" in remainder else len(data))

    class DataLakeServiceClient:
        def __init__(self, account_url, credential, retry_total, retry_backoff_factor):
            credential.get_token()

        def get_file_system_client(self, file_system):
            return FileSystemClient(file_system)

    filedatalake_module = types.ModuleType("azure.storage.filedatalake")
    filedatalake_module.DataLakeServiceClient = DataLakeServiceClient

    class AccessToken:
        def __init__(self, token, expires_on):
            self.token = token
            self.expires_on = expires_on

    monkeypatch.setitem(sys.modules, "requests", requests_module)
    monkeypatch.setitem(sys.modules, "azure", types.ModuleType("azure"))
    monkeypatch.setitem(sys.modules, "azure.storage", types.ModuleType("azure.storage"))
    monkeypatch.setitem(sys.modules, "azure.storage.filedatalake", filedatalake_module)
    monkeypatch.setitem(sys.modules, "azure.core", types.ModuleType("azure.core"))
    credentials_module = types.ModuleType("azure.core.credentials")
    credentials_module.AccessToken = AccessToken
    monkeypatch.setitem(sys.modules, "azure.core.credentials", credentials_module)


def _load_cli(monkeypatch, tmp_path):
    module_dir = ROOT / "images" / "onelake"
    monkeypatch.syspath_prepend(str(module_dir))
    monkeypatch.setenv("ONELAKE_CONFIG", str(tmp_path / "config.json"))
    for name in ("onelake_cli", "onelake", "zone_token_broker"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("onelake_cli", module_dir / "onelake_cli.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "onelake_cli", module)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cli_commands_read_write_and_reuse_authservice_token(tmp_path, monkeypatch, capsys):
    store = {"Lake.Lakehouse/Files/existing.txt": b"existing"}
    token_calls = []
    _install_fake_dependencies(monkeypatch, store, token_calls)
    cli = _load_cli(monkeypatch, tmp_path)

    assert cli.main(["connect", "Workspace", "Lake"]) == 0
    assert cli.main(["status", "--live"]) == 0
    assert cli.main(["ls", "/"]) == 0

    class Stdin:
        buffer = io.BytesIO(b"hello from cli")

    monkeypatch.setattr(cli.sys, "stdin", Stdin())
    assert cli.main(["write", "Files/smoke.txt"]) == 0

    class Stdout:
        def __init__(self):
            self.buffer = io.BytesIO()

        def write(self, _text):
            return 0

        def flush(self):
            return None

    stdout = Stdout()
    monkeypatch.setattr(cli.sys, "stdout", stdout)
    assert cli.main(["cat", "Files/smoke.txt"]) == 0
    assert stdout.buffer.getvalue() == b"hello from cli"

    local = tmp_path / "download.txt"
    assert cli.main(["get", "Files/smoke.txt", str(local)]) == 0
    assert local.read_bytes() == b"hello from cli"

    upload = tmp_path / "upload.txt"
    upload.write_bytes(b"uploaded")
    assert cli.main(["put", str(upload), "Files/uploaded.txt"]) == 0
    assert store["Lake.Lakehouse/Files/uploaded.txt"] == b"uploaded"

    assert token_calls == [
        {
            "url": "http://authservice.kubeflow.svc.cluster.local:8080/authservice/getPassthroughToken",
            "scope": "https://storage.azure.com/.default",
            "timeout": 30,
        }
    ]
    assert "Token storage: in-memory only" in capsys.readouterr().out

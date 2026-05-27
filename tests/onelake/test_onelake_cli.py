import importlib.util
from pathlib import Path

import pytest


def _load_cli(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "images" / "onelake"))
    module_path = root / "images" / "onelake" / "onelake_cli.py"
    spec = importlib.util.spec_from_file_location("test_onelake_cli_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_connect_command_persists_selection(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ONELAKE_CONFIG", str(tmp_path / "config.json"))
    cli = _load_cli(monkeypatch)

    assert cli.main(["connect", "workspace", "lakehouse"]) == 0

    assert "saved" in capsys.readouterr().out
    assert (tmp_path / "config.json").exists()


def test_status_live_passes_live_flag(monkeypatch, capsys):
    cli = _load_cli(monkeypatch)
    calls = {}

    def fake_status(live=False):
        calls["live"] = live
        return {
            "ready": True,
            "workspace": "workspace",
            "lakehouse": "lakehouse",
            "endpoint": "https://example",
            "broker_url": "https://broker",
            "token_storage": "memory",
            "missing": [],
            "live": {"ok": True, "detail": "0 entries under Files"},
        }

    monkeypatch.setattr(cli.onelake, "status", fake_status)

    assert cli.main(["status", "--live"]) == 0
    assert calls == {"live": True}
    assert "Live: OK" in capsys.readouterr().out


def test_write_reads_stdin(monkeypatch):
    cli = _load_cli(monkeypatch)
    calls = {}

    class Stdin:
        class buffer:
            @staticmethod
            def read():
                return b"line\n"

    monkeypatch.setattr(cli.sys, "stdin", Stdin())
    monkeypatch.setattr(cli.onelake, "write", lambda path, data: calls.update({"path": path, "data": data}))

    assert cli.main(["write", "Files/logs/job.log"]) == 0
    assert calls == {"path": "Files/logs/job.log", "data": b"line\n"}


def test_get_and_put_call_clear_directional_helpers(monkeypatch):
    cli = _load_cli(monkeypatch)
    calls = []
    monkeypatch.setattr(cli.onelake, "download", lambda remote, local: calls.append(("get", remote, local)))
    monkeypatch.setattr(cli.onelake, "upload", lambda local, remote: calls.append(("put", local, remote)))

    assert cli.main(["get", "Files/input.csv", "/tmp/input.csv"]) == 0
    assert cli.main(["put", "/tmp/output.csv", "Files/output.csv"]) == 0

    assert calls == [
        ("get", "Files/input.csv", "/tmp/input.csv"),
        ("put", "/tmp/output.csv", "Files/output.csv"),
    ]


def test_old_commands_are_not_supported(monkeypatch):
    cli = _load_cli(monkeypatch)

    for argv in (["doctor"], ["configure", "w", "l"], ["cp", "a", "b"], ["append", "Files/a.txt"]):
        with pytest.raises(SystemExit):
            cli.main(argv)

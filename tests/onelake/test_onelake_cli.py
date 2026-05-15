import importlib.util
from pathlib import Path


def _load_cli(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "images" / "onelake"))
    module_path = root / "images" / "onelake" / "onelake_cli.py"
    spec = importlib.util.spec_from_file_location("test_onelake_cli_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_configure_command_persists_selection(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ONELAKE_CONFIG", str(tmp_path / "config.json"))
    cli = _load_cli(monkeypatch)

    assert cli.main(["configure", "workspace", "lakehouse"]) == 0

    assert "saved" in capsys.readouterr().out
    assert (tmp_path / "config.json").exists()


def test_cp_requires_one_remote_path(monkeypatch):
    cli = _load_cli(monkeypatch)

    try:
        cli.main(["cp", "local-a", "local-b"])
    except SystemExit as error:
        assert "exactly one onelake: path" in str(error)
    else:
        raise AssertionError("cp without a remote path should fail")


def test_doctor_command_returns_nonzero_for_missing_check(monkeypatch, capsys):
    cli = _load_cli(monkeypatch)
    monkeypatch.setattr(cli.onelake, "doctor", lambda check_access=False: [
        {"name": "Token broker configured", "ok": False, "detail": "set ONELAKE_BROKER_URL"},
    ])

    assert cli.main(["doctor"]) == 1

    assert "MISSING Token broker configured" in capsys.readouterr().out


def test_doctor_live_passes_live_flag(monkeypatch):
    cli = _load_cli(monkeypatch)
    calls = {}

    def fake_doctor(check_access=False):
        calls["check_access"] = check_access
        return [{"name": "Live OneLake list", "ok": True, "detail": "0 entries"}]

    monkeypatch.setattr(cli.onelake, "doctor", fake_doctor)

    assert cli.main(["doctor", "--live"]) == 0
    assert calls == {"check_access": True}


def test_append_reads_stdin(monkeypatch):
    cli = _load_cli(monkeypatch)
    calls = {}

    class Stdin:
        class buffer:
            @staticmethod
            def read():
                return b"line\n"

    monkeypatch.setattr(cli.sys, "stdin", Stdin())
    monkeypatch.setattr(cli.onelake, "append", lambda path, data: calls.update({"path": path, "data": data}))

    assert cli.main(["append", "logs/job.log"]) == 0
    assert calls == {"path": "logs/job.log", "data": b"line\n"}

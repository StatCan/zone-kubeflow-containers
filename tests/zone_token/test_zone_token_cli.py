import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_cli(monkeypatch):
    module_dir = ROOT / "images" / "zone_token"
    monkeypatch.syspath_prepend(str(module_dir))
    spec = importlib.util.spec_from_file_location("test_zone_token_cli_module", module_dir / "zone_token_cli.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_get_prints_only_access_token(monkeypatch, capsys):
    module = _load_cli(monkeypatch)
    monkeypatch.setattr(module.zonetokenbroker, "get_access_token", lambda *_args, **_kwargs: "access-token")

    exit_code = module.main(["get", "--scope", "scope-a"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "access-token\n"
    assert captured.err == ""


def test_missing_scope_exits_nonzero(monkeypatch):
    module = _load_cli(monkeypatch)

    try:
        module.main(["get"])
    except SystemExit as error:
        assert error.code != 0
    else:
        raise AssertionError("missing --scope should fail argparse validation")


def test_broker_error_goes_to_stderr(monkeypatch, capsys):
    module = _load_cli(monkeypatch)

    def fail(*_args, **_kwargs):
        raise module.zonetokenbroker.TokenBrokerError("AADSTS65001: consent_required")

    monkeypatch.setattr(module.zonetokenbroker, "get_access_token", fail)

    exit_code = module.main(["get", "--scope", "scope-a"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "AADSTS65001" in captured.err

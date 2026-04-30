import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "images" / "onelake" / "onelake_utils.py"
    spec = importlib.util.spec_from_file_location("test_onelake_utils_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_connect_persists_config_and_status(tmp_path, monkeypatch):
    module = _load_module()

    config_file = tmp_path / ".onelake_config"
    status_file = tmp_path / ".onelake_status"

    monkeypatch.setattr(module, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(module, "_STATUS_FILE", status_file)
    monkeypatch.setattr(module, "_is_mounted", lambda: False)

    module.connect("workspace-guid", "lakehouse-guid")

    assert json.loads(config_file.read_text()) == {
        "workspace": "workspace-guid",
        "lakehouse": "lakehouse-guid",
    }
    assert json.loads(status_file.read_text()) == {
        "configured": True,
        "workspace": "workspace-guid",
        "lakehouse": "lakehouse-guid",
        "endpoint": module.ONELAKE_ENDPOINT,
        "mounted": False,
    }


def test_mount_runs_helper_and_updates_status(tmp_path, monkeypatch, capsys):
    module = _load_module()

    config_file = tmp_path / ".onelake_config"
    status_file = tmp_path / ".onelake_status"
    mount_script = tmp_path / "04-onelake-mount"
    mount_script.write_text("#!/usr/bin/env bash\n")

    monkeypatch.setattr(module, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(module, "_STATUS_FILE", status_file)
    monkeypatch.setattr(module, "_MOUNT_SCRIPT", mount_script)

    state = {"mounted": False}

    def fake_is_mounted():
        return state["mounted"]

    def fake_run(command, **kwargs):
        assert command == ["bash", str(mount_script)]
        state["mounted"] = True

        class Result:
            returncode = 0
            stdout = "OneLake mount: mounted at /tmp/onelake\n"
            stderr = ""

        return Result()

    monkeypatch.setattr(module, "_is_mounted", fake_is_mounted)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.mount("workspace-guid", "lakehouse-guid") is True

    status = json.loads(status_file.read_text())
    assert status == {
        "configured": True,
        "workspace": "workspace-guid",
        "lakehouse": "lakehouse-guid",
        "endpoint": module.ONELAKE_ENDPOINT,
        "mounted": True,
        "mount_path": str(module.MOUNT_PATH),
    }

    output = capsys.readouterr().out
    assert "mounted" in output.lower()

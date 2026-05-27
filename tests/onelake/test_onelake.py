import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load_module(monkeypatch, config_path):
    monkeypatch.setenv("ONELAKE_CONFIG", str(config_path))
    module_dir = ROOT / "images" / "onelake"
    monkeypatch.syspath_prepend(str(module_dir))
    sys.modules.pop("onelake", None)
    sys.modules.pop("zone_token_broker", None)
    module_path = module_dir / "onelake.py"
    spec = importlib.util.spec_from_file_location("onelake", module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "onelake", module)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_connect_persists_non_secret_selection(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")

    module.connect("workspace-guid", "lakehouse-guid")

    assert json.loads((tmp_path / "config.json").read_text()) == {
        "workspace": "workspace-guid",
        "lakehouse": "lakehouse-guid",
    }


def test_env_config_overrides_saved_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"workspace": "saved-ws", "lakehouse": "saved-lh"}))
    monkeypatch.setenv("ONELAKE_WORKSPACE", "env-ws")
    monkeypatch.setenv("ONELAKE_LAKEHOUSE", "env-lh")
    module = _load_module(monkeypatch, config_path)

    assert module._get_config() == ("env-ws", "env-lh")


def test_status_reports_missing_workspace_and_lakehouse(tmp_path, monkeypatch):
    monkeypatch.delenv("ONELAKE_WORKSPACE", raising=False)
    monkeypatch.delenv("ONELAKE_LAKEHOUSE", raising=False)
    module = _load_module(monkeypatch, tmp_path / "config.json")

    current = module.status()

    assert current["ready"] is False
    assert current["missing"] == [
        "ONELAKE_WORKSPACE or saved workspace",
        "ONELAKE_LAKEHOUSE or saved lakehouse",
    ]


def test_status_live_reports_live_listing(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")
    module.connect("workspace", "lakehouse")
    monkeypatch.setattr(module, "ls", lambda path: [{"name": path, "is_directory": True, "size": 0}])

    current = module.status(live=True)

    assert current["ready"] is True
    assert current["token_storage"] == "memory"
    assert current["live"] == {"ok": True, "detail": "1 entries under Files"}


def test_path_model_supports_root_files_tables_and_bare_paths(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")

    assert module._normalize_path("/") == ""
    assert module._normalize_path("Files/raw/file.csv") == "Files/raw/file.csv"
    assert module._normalize_path("Tables/sales/part.parquet") == "Tables/sales/part.parquet"
    assert module._normalize_path("raw/file.csv") == "Files/raw/file.csv"
    assert module._build_path("raw/file.csv", lakehouse="Lake") == "Lake.Lakehouse/Files/raw/file.csv"
    assert module._build_path("Files/raw/file.csv", lakehouse="Lake") == "Lake.Lakehouse/Files/raw/file.csv"
    assert module._build_path("Tables/sales", lakehouse="Lake") == "Lake.Lakehouse/Tables/sales"
    assert module._build_path("Files/a.csv", lakehouse="11111111-2222-3333-4444-555555555555") == (
        "11111111-2222-3333-4444-555555555555/Files/a.csv"
    )


def test_root_listing_is_synthetic(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")

    assert module.ls("/") == [
        {"name": "Files", "is_directory": True, "size": 0},
        {"name": "Tables", "is_directory": True, "size": 0},
    ]


def test_writes_must_target_files_inside_managed_roots(tmp_path, monkeypatch):
    module = _load_module(monkeypatch, tmp_path / "config.json")

    for path in ("/", "Files", "Tables"):
        with pytest.raises(RuntimeError, match="inside Files/ or Tables"):
            module._require_file_path(path)

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_onelake_layer_is_between_base_and_mid():
    bake = (ROOT / "docker-bake.hcl").read_text(encoding="utf-8")

    assert 'target "onelake"' in bake
    assert 'context = "./images/onelake"' in bake
    assert 'target "mid"' in bake
    assert 'BASE_IMAGE="onelake"' in bake


def test_onelake_layer_does_not_use_fuse_or_device_code():
    files = [
        ROOT / "images" / "onelake" / "Dockerfile",
        ROOT / "images" / "onelake" / "onelake_utils.py",
        ROOT / "images" / "onelake" / "onelake_cli.py",
        ROOT / "images" / "onelake" / "onelake_fsspec.py",
        ROOT / "images" / "onelake" / "onelake_sitecustomize.py",
        ROOT / "images" / "onelake" / "onelake",
        ROOT / "images" / "onelake" / "jupyter_server_config.d" / "onelake.json",
    ]
    content = "\n".join(path.read_text(encoding="utf-8").lower() for path in files)

    for forbidden in ("blobfuse", "/dev/fuse", "sys_admin", "device-code", "device code", "az login"):
        assert forbidden not in content


def test_onelake_layer_configures_jupyterfs_resource():
    config = json.loads((ROOT / "images" / "onelake" / "jupyter_server_config.d" / "onelake.json").read_text())

    assert config["ServerApp"]["contents_manager_class"] == "jupyterfs.metamanager.MetaManager"
    assert config["ServerApp"]["jpserver_extensions"]["jupyterfs.extension"] is True
    assert config["JupyterFs"]["resources"] == [
        {
            "name": "OneLake",
            "url": "onelake:///",
            "type": "fsspec",
            "auth": "none",
            "defaultWritable": True,
        }
    ]


def test_onelake_layer_registers_fsspec_without_overwriting_sitecustomize():
    dockerfile = (ROOT / "images" / "onelake" / "Dockerfile").read_text(encoding="utf-8")

    assert "onelake_fsspec_register.pth" in dockerfile
    assert "import onelake_sitecustomize" in dockerfile
    assert "purelib / 'sitecustomize.py'" not in dockerfile


def test_jupyterfs_waits_for_full_onelake_readiness():
    fsspec_backend = (ROOT / "images" / "onelake" / "onelake_fsspec.py").read_text(encoding="utf-8")

    assert 'return onelake.status()["ready"]' in fsspec_backend
    assert "The platform must set ONELAKE_BROKER_URL" in fsspec_backend

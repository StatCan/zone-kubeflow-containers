import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_onelake_layer_is_between_base_and_mid():
    bake = (ROOT / "docker-bake.hcl").read_text(encoding="utf-8")

    assert 'target "onelake"' in bake
    assert 'context = "./images/onelake"' in bake
    assert 'target "mid"' in bake
    assert 'BASE_IMAGE="onelake"' in bake


def test_onelake_layer_has_one_public_product_and_no_old_auth_surfaces():
    files = [
        ROOT / "images" / "onelake" / "Dockerfile",
        ROOT / "images" / "onelake" / "onelake.py",
        ROOT / "images" / "onelake" / "onelake_cli.py",
        ROOT / "images" / "onelake" / "onelake_fsspec.py",
        ROOT / "images" / "onelake" / "onelake_register.py",
        ROOT / "images" / "onelake" / "zone_token_broker.py",
        ROOT / "images" / "onelake" / "onelake",
        ROOT / "images" / "onelake" / "onelake-r" / "R" / "onelake.R",
        ROOT / "images" / "onelake" / "jupyter_server_config.d" / "onelake.json",
    ]
    content = "\n".join(path.read_text(encoding="utf-8").lower() for path in files)

    forbidden = (
        "blobfuse",
        "/dev/fuse",
        "sys_admin",
        "device-code",
        "device code",
        "az login",
        "zone-token",
        "onelake_access_token",
        "access-token-stdin",
    )
    for value in forbidden:
        assert value not in content


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


def test_onelake_layer_registers_fsspec_with_explicit_register_module():
    dockerfile = (ROOT / "images" / "onelake" / "Dockerfile").read_text(encoding="utf-8")

    assert "onelake_fsspec_register.pth" in dockerfile
    assert "import onelake_register" in dockerfile
    assert "sitecustomize" not in dockerfile


def test_jupyterfs_waits_for_basic_onelake_readiness():
    fsspec_backend = (ROOT / "images" / "onelake" / "onelake_fsspec.py").read_text(encoding="utf-8")

    assert 'return onelake.status()["ready"]' in fsspec_backend
    assert "onelake connect <workspace> <lakehouse>" in fsspec_backend

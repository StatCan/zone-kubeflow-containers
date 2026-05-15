from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_zone_token_layer_is_between_base_and_onelake():
    bake = (ROOT / "docker-bake.hcl").read_text(encoding="utf-8")

    assert 'target "zone-token"' in bake
    assert 'context = "./images/zone_token"' in bake
    assert 'target "onelake"' in bake
    assert 'BASE_IMAGE="zone-token"' in bake


def test_zone_token_layer_installs_cli_python_and_r_helpers():
    dockerfile = (ROOT / "images" / "zone_token" / "Dockerfile").read_text(encoding="utf-8")

    assert "zonetokenbroker.py" in dockerfile
    assert "zone_token_cli.py" in dockerfile
    assert "zone-token /usr/local/bin/zone-token" in dockerfile
    assert "R CMD INSTALL /tmp/zonetokenbroker-r" in dockerfile


def test_zone_token_layer_does_not_use_device_code():
    files = [
        ROOT / "images" / "zone_token" / "Dockerfile",
        ROOT / "images" / "zone_token" / "zonetokenbroker.py",
        ROOT / "images" / "zone_token" / "zone_token_cli.py",
        ROOT / "images" / "zone_token" / "zone-token",
        ROOT / "images" / "zone_token" / "zonetokenbroker-r" / "R" / "zonetokenbroker.R",
    ]
    content = "\n".join(path.read_text(encoding="utf-8").lower() for path in files)

    for forbidden in ("device-code", "device code", "az login"):
        assert forbidden not in content

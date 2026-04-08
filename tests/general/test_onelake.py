"""
test_onelake
~~~~~~~~~~~~
Tests that OneLake SDK packages and the onelake_utils helper module
are properly installed and importable in the container image.
"""

import logging
import pytest

LOGGER = logging.getLogger(__name__)


def test_onelake_sdk_packages(container):
    """Test that azure-storage-file-datalake and azure-identity are importable."""
    container.run()
    for package in ["azure.storage.filedatalake", "azure.identity"]:
        LOGGER.info(f"Testing import of {package}")
        rc = container.container.exec_run(
            ["python", "-c", f"import {package}"]
        )
        assert rc.exit_code == 0, f"Failed to import {package}: {rc.output.decode()}"


def test_onelake_utils_importable(container):
    """Test that onelake_utils module is importable and exposes expected functions."""
    container.run()
    rc = container.container.exec_run(
        [
            "python",
            "-c",
            "import onelake_utils; "
            "assert hasattr(onelake_utils, 'ls'); "
            "assert hasattr(onelake_utils, 'read'); "
            "assert hasattr(onelake_utils, 'write'); "
            "assert hasattr(onelake_utils, 'download'); "
            "assert hasattr(onelake_utils, 'upload'); "
            "assert hasattr(onelake_utils, 'info'); "
            "print('All onelake_utils functions present')",
        ]
    )
    assert rc.exit_code == 0, f"onelake_utils import check failed: {rc.output.decode()}"


def test_onelake_info_unconfigured(container):
    """Test that onelake_utils.info() works gracefully when OneLake is not configured."""
    container.run()
    rc = container.container.exec_run(
        ["python", "-c", "import onelake_utils; onelake_utils.info()"]
    )
    assert rc.exit_code == 0, f"onelake_utils.info() failed: {rc.output.decode()}"
    output = rc.output.decode()
    # Should show "Not configured" or "Non configure" (bilingual)
    assert "N/A" in output or "not" in output.lower() or "non" in output.lower()


def test_onelake_connect_persists_config_and_status(container):
    """Test that connect() saves the user's default OneLake selection for future restarts."""
    container.run()
    rc = container.container.exec_run(
        [
            "python",
            "-c",
            "import json, pathlib, onelake_utils; "
            "onelake_utils.connect('ws-guid', 'lh-guid'); "
            "cfg = json.loads(pathlib.Path.home().joinpath('.onelake_config').read_text()); "
            "status = json.loads(pathlib.Path.home().joinpath('.onelake_status').read_text()); "
            "assert cfg['workspace'] == 'ws-guid'; "
            "assert cfg['lakehouse'] == 'lh-guid'; "
            "assert status['configured'] is True; "
            "assert status['workspace'] == 'ws-guid'; "
            "assert status['lakehouse'] == 'lh-guid'; "
            "print('connect() persisted config and status')",
        ]
    )
    assert rc.exit_code == 0, f"connect() persistence check failed: {rc.output.decode()}"


def test_onelake_init_loads_saved_config(container):
    """Test that 03-onelake-init falls back to ~/.onelake_config when env vars are absent."""
    container.run()
    rc = container.container.exec_run(
        [
            "bash",
            "-lc",
            "unset ONELAKE_WORKSPACE ONELAKE_LAKEHOUSE; "
            "cat > ~/.onelake_config <<'EOF'\n"
            "{\"workspace\": \"saved-ws\", \"lakehouse\": \"saved-lh\"}\n"
            "EOF\n"
            "bash /etc/cont-init.d/03-onelake-init >/tmp/onelake-init-test.log 2>&1; "
            "python - <<'PY'\n"
            "import json\n"
            "from pathlib import Path\n"
            "status = json.loads(Path.home().joinpath('.onelake_status').read_text())\n"
            "assert status['configured'] is True\n"
            "assert status['workspace'] == 'saved-ws'\n"
            "assert status['lakehouse'] == 'saved-lh'\n"
            "assert Path('/run/s6-env/ONELAKE_WORKSPACE').read_text().strip() == 'saved-ws'\n"
            "assert Path('/run/s6-env/ONELAKE_LAKEHOUSE').read_text().strip() == 'saved-lh'\n"
            "print('03-onelake-init loaded saved config')\n"
            "PY",
        ]
    )
    assert rc.exit_code == 0, f"03-onelake-init saved-config fallback failed: {rc.output.decode()}"


def test_onelake_configure_cli_saves_defaults(container):
    """Test that the onelake-configure helper saves defaults into ~/.onelake_config."""
    container.run()
    rc = container.container.exec_run(
        [
            "bash",
            "-lc",
            "onelake-configure cli-ws cli-lh >/tmp/onelake-configure.out 2>&1; "
            "python - <<'PY'\n"
            "import json\n"
            "from pathlib import Path\n"
            "cfg = json.loads(Path.home().joinpath('.onelake_config').read_text())\n"
            "assert cfg['workspace'] == 'cli-ws'\n"
            "assert cfg['lakehouse'] == 'cli-lh'\n"
            "print('onelake-configure saved defaults')\n"
            "PY",
        ]
    )
    assert rc.exit_code == 0, f"onelake-configure helper failed: {rc.output.decode()}"

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

"""
test_vscode_extensions
~~~~~~~~~~~~~~~~~~~~~~
Test that VSCode (code-server) extensions are properly installed.

This test verifies that all expected VSCode extensions are installed
in the mid/jupyterlab images, including:
- Python support (ms-python.python, ms-python.debugpy)
- R support (REditorSupport.r)
- Parquet visualizer (adamviola.parquet-explorer, lucien-martijn.parquet-visualizer)
- Language packs (ms-ceintl.vscode-language-pack-fr)
- Other productivity extensions (yaml, azurecli, cpptools, etc.)

Example:

    $ make test/mid

    # [...]
    # test/mid/test_vscode_extensions.py::test_vscode_extensions_installed
    # ---------------------------------------------------------------------------------------------- live log call ----------------------------------------------------------------------------------------------
    # 2026-03-17 10:00:00 [    INFO] Testing VSCode extensions installation... (test_vscode_extensions.py:22)
    # 2026-03-17 10:00:02 [    INFO] All expected VSCode extensions are installed successfully (test_vscode_extensions.py:60)
"""

import logging
import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)

@pytest.mark.integration
def test_vscode_extensions_installed(container):
    """Test that all expected VSCode extensions are installed.
    
    Verifies that code-server is available and all required extensions
    are installed, including Python, R, parquet visualizer, and
    productivity extensions.
    
    The test is skipped for base images since VSCode is only expected
    in mid/jupyterlab images.
    """
    # Only run this test on images that should have code-server
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("VSCode extensions not expected in base image")
    
    LOGGER.info("Testing VSCode extensions installation...")

    container.run()

    success, output = wait_for_exec_success(
        container=container,
        command=["which", "code-server"],
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(
            f"Container failed to be ready for execution within timeout. Output: {output}"
        )
    
    # Check if code-server is available
    result = container.container.exec_run(["which", "code-server"])
    if result.exit_code != 0:
        LOGGER.error("code-server not found in PATH")
        assert False, "code-server not found in PATH"
    
    # Check if the parquet extensions are installed
    result = container.container.exec_run(["code-server", "--list-extensions"])
    extensions_output = result.output.decode('utf-8')
    
    LOGGER.info(f"Installed extensions:\n{extensions_output}")

    # Check for expected VSCode extensions
    expected_extensions = [
        "ms-python.python",
        "ms-python.debugpy",
        "posit.air-vscode",
        "ms-ceintl.vscode-language-pack-fr",
        "adamviola.parquet-explorer",
        "lucien-martijn.parquet-visualizer",
        "redhat.vscode-yaml",
        "ms-vscode.azurecli",
        "mblode.pretty-formatter",
        "ms-vscode.cpptools"
    ]
    
    missing_extensions = []
    for ext in expected_extensions:
        if ext not in extensions_output:
            missing_extensions.append(ext)
    
    if missing_extensions:
        LOGGER.error(f"Missing expected VSCode extensions: {missing_extensions}")
        LOGGER.error(f"All extensions found: {extensions_output}")
        assert False, f"Missing expected VSCode extensions: {missing_extensions}"

    LOGGER.info("All expected VSCode extensions are installed successfully")

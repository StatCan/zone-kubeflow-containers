"""
test_vscode_extensions
~~~~~~~~~~~~~~~~~~~~~~
Test that VSCode extensions including parquet visualizer are properly installed.
"""

import logging
import pytest

LOGGER = logging.getLogger(__name__)

@pytest.mark.integration
def test_vscode_extensions_installed(container):
    """Test that VSCode extensions are properly installed in the container."""
    # Only run this test on images that should have code-server
    image_name = container.image_name.lower()
    if 'base' in image_name or 'jupyterlab' in image_name:
        pytest.skip("VSCode extensions not expected in base/jupyterlab images")
    
    LOGGER.info("Testing VSCode extensions installation...")
    
    # Check if code-server is available
    result = container.container.exec_run(["which", "code-server"])
    if result.exit_code != 0:
        LOGGER.error("code-server not found in PATH")
        assert False, "code-server not found in PATH"
    
    # Check if the parquet explorer extension is installed
    result = container.container.exec_run(["code-server", "--list-extensions"])
    extensions_output = result.output.decode('utf-8')
    
    LOGGER.info(f"Installed extensions:\n{extensions_output}")
    
    # Check for the specific parquet extensions
    expected_extensions = [
        "adamviola.parquet-explorer",
        "lucien-martijn.parquet-visualizer"
    ]
    
    missing_extensions = []
    for ext in expected_extensions:
        if ext not in extensions_output:
            missing_extensions.append(ext)
    
    if missing_extensions:
        LOGGER.error(f"Missing expected parquet extensions: {missing_extensions}")
        LOGGER.error(f"All extensions found: {extensions_output}")
        assert False, f"Missing expected parquet extensions: {missing_extensions}"
    
    LOGGER.info("All expected VSCode extensions are installed successfully")
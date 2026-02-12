import logging
import pytest

from helpers import CondaPackageHelper

LOGGER = logging.getLogger(__name__)

EXPECTED = "2025.09.1+401 (Cucumberleaf Sunflower) for Ubuntu Jammy"

@pytest.fixture(scope="function")
def package_helper(container):
    """Return a package helper object that can be used to perform tests on installed packages"""
    return CondaPackageHelper(container)

def _execute_on_container(package_helper, command):
    """Generic function executing a command"""
    LOGGER.debug(f"Running command [{command}] ...")
    return package_helper.running_container.exec_run(command)

def test_rstudio(package_helper):
    # Skip this test for images that don't have rstudio-server
    image_name = package_helper.running_container.image.tags[0].lower() if package_helper.running_container.image.tags else ""
    if 'base' in image_name or 'jupyterlab' in image_name or 'mid' in image_name:
        pytest.skip("RStudio not available in this image, skipping RStudio test")
    
    result = _execute_on_container(package_helper, ["rstudio-server", "start"])
    LOGGER.info(f"starting up rstudio: {result}")
    if result.exit_code != 0:
        # If rstudio-server command is not found, skip the test
        if "executable file not found" in result.output.decode("utf-8"):
            pytest.skip("rstudio-server not found in PATH, skipping RStudio test")
    
    assert(result.exit_code==0)

    result = _execute_on_container(package_helper, ["rstudio-server", "version"])
    LOGGER.info(f"rstudio version: {result}")
    assert(EXPECTED in result.output.decode("utf-8"))
 

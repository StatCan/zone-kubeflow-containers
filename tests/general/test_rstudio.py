import logging
import pytest

from helpers import CondaPackageHelper

LOGGER = logging.getLogger(__name__)

# Expected RStudio version string for validation
EXPECTED = "2025.09.1+401 (Cucumberleaf Sunflower) for Ubuntu Jammy"

@pytest.fixture(scope="function")
def package_helper(container):
    """Return a package helper object that can be used to perform tests on installed packages"""
    # Create and return a helper for package operations on the test container
    return CondaPackageHelper(container)

def _execute_on_container(package_helper, command):
    """Generic function executing a command"""
    LOGGER.debug(f"Running command [{command}] ...")
    # Execute command on running container and return result
    return package_helper.running_container.exec_run(command)


def _skip_if_no_rstudio(package_helper):
    # Extract container image name and check if RStudio is expected to be installed
    image_name = package_helper.running_container.image.tags[0].lower() if package_helper.running_container.image.tags else ""
    # Skip test for base and mid images that don't include RStudio
    if 'base' in image_name or 'mid' in image_name:
        pytest.skip("RStudio not available in this image, skipping RStudio test")


def test_rstudio(package_helper):
    # Skip this test for images that don't have rstudio-server
    _skip_if_no_rstudio(package_helper)
    
    # Attempt to start RStudio server
    result = _execute_on_container(package_helper, ["rstudio-server", "start"])
    LOGGER.info(f"starting up rstudio: {result}")
    if result.exit_code != 0:
        # If rstudio-server command is not found, skip the test
        if "executable file not found" in result.output.decode("utf-8"):
            pytest.skip("rstudio-server not found in PATH, skipping RStudio test")
    
    # Verify that RStudio server started successfully
    assert(result.exit_code==0)

    # Verify RStudio version matches expected version
    result = _execute_on_container(package_helper, ["rstudio-server", "version"])
    LOGGER.info(f"rstudio version: {result}")
    assert(EXPECTED in result.output.decode("utf-8"))


def test_custom_rstudio_proxy(package_helper):
    _skip_if_no_rstudio(package_helper)

    # Verify custom RStudio proxy module can be imported
    result = _execute_on_container(package_helper, ["python", "-c", "import jupyter_custom_rstudio_proxy"])
    assert result.exit_code == 0, result.output.decode("utf-8")

    # Verify RStudio conda helper script exists and is executable
    result = _execute_on_container(package_helper, ["test", "-x", "/usr/local/bin/rstudio-use-current-conda"])
    assert result.exit_code == 0, "rstudio-use-current-conda helper is missing or not executable"
 

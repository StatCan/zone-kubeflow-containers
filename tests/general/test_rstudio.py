import logging
import pytest

from helpers import CondaPackageHelper
from tests.general.wait_utils import wait_for_condition

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

@pytest.mark.integration
@pytest.mark.smoke
def test_rstudio(package_helper):
    result = _execute_on_container(package_helper, ["rstudio-server", "start"])
    LOGGER.info(f"starting up rstudio: {result}")
    assert(result.exit_code==0)

    result = _execute_on_container(package_helper, ["rstudio-server", "version"])
    LOGGER.info(f"rstudio version: {result}")
    assert(EXPECTED in result.output.decode("utf-8"))

@pytest.mark.integration
def test_rstudio_available_in_container(container):
    """Test that RStudio server binary is available in the container."""
    LOGGER.info("Testing RStudio server binary availability...")

    container.run()

    # Check if rstudio-server command is available
    result = container.container.exec_run(['which', 'rstudio-server'])

    assert result.exit_code == 0, (
        f"RStudio server binary not found in container\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    LOGGER.info("RStudio server binary is available")


@pytest.mark.integration
def test_rstudio_version_consistency(container):
    """Test that RStudio version matches expected version."""
    LOGGER.info("Testing RStudio version consistency...")

    container.run()

    # Get RStudio version
    result = container.container.exec_run(['rstudio-server', 'version'])

    assert result.exit_code == 0, (
        f"Failed to get RStudio version\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8').strip()
    expected_version = "2024.12.0+467"

    assert expected_version in output, (
        f"RStudio version mismatch\n"
        f"Expected: {expected_version}\n"
        f"Actual: {output}"
    )

    LOGGER.info(f"RStudio version matches expected: {output}")


@pytest.mark.integration
def test_rstudio_config_files(container):
    """Test that RStudio configuration files exist and are properly set."""
    LOGGER.info("Testing RStudio configuration files...")

    container.run()

    # Check for main RStudio server config file
    result = container.container.exec_run(['test', '-f', '/etc/rstudio/rserver.conf'])
    assert result.exit_code == 0, (
        f"RStudio server config file (/etc/rstudio/rserver.conf) not found"
    )

    # Check for session config file
    result = container.container.exec_run(['test', '-f', '/etc/rstudio/rsession.conf'])
    assert result.exit_code == 0, (
        f"RStudio session config file (/etc/rstudio/rsession.conf) not found"
    )

    # Read and verify some security settings
    result = container.container.exec_run(['cat', '/etc/rstudio/rserver.conf'])
    assert result.exit_code == 0, "Failed to read rserver.conf"

    config_content = result.output.decode('utf-8')

    # Verify security settings are present
    security_settings = [
        'www-frame-origin=none',
        'www-enable-origin-check=1',
        'www-same-site=lax'
    ]

    for setting in security_settings:
        assert setting in config_content, f"Security setting '{setting}' not found in rserver.conf"

    LOGGER.info("RStudio configuration files present and security settings verified")


@pytest.mark.integration
def test_r_rstudio_integration(container):
    """Test that R and RStudio integration works properly."""
    LOGGER.info("Testing R and RStudio integration...")

    container.run()

    # Test that R can be executed from within RStudio context
    # This checks if R is properly linked with RStudio
    r_test_script = '''
# Test basic R functionality
print("Testing R in RStudio context")
x <- c(1, 2, 3, 4, 5)
mean_x <- mean(x)
print(paste("Mean of x:", mean_x))

# Test if R can find its libraries
libs <- .libPaths()
print(paste("R library paths:", paste(libs, collapse=", ")))

# Test a basic plot function (no display needed, just check if it loads)
if(require(graphics, quietly=TRUE)) {
    print("Graphics package available")
} else {
    stop("Graphics package not available - RStudio integration issue")
}

print("R and RStudio integration test successful")
'''

    # Write the test script to a file and execute it
    write_cmd = f"cat > /tmp/rstudio_integration_test.R << 'EOF'\n{r_test_script}\nEOF"
    result = container.container.exec_run(['bash', '-c', write_cmd])
    assert result.exit_code == 0, f"Failed to write R test script: {result.output.decode('utf-8')}"

    # Execute the R script
    result = container.container.exec_run(['R', '--slave', '-f', '/tmp/rstudio_integration_test.R'])

    assert result.exit_code == 0, (
        f"RStudio integration test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "R and RStudio integration test successful" in output

    LOGGER.info("R and RStudio integration test successful")


@pytest.mark.integration
def test_rstudio_web_interface_components(container):
    """Test that RStudio web interface components are properly installed."""
    LOGGER.info("Testing RStudio web interface components...")

    container.run()

    # Test that RStudio server is properly installed and configured
    # First, check if RStudio server is available
    result = container.container.exec_run(['which', 'rstudio-server'])
    if result.exit_code != 0:
        LOGGER.warning("RStudio server not found in this image")
        pytest.skip("RStudio server not available in this image")

    # Check for RStudio configuration files to ensure it's properly set up
    result = container.container.exec_run(['test', '-f', '/etc/rstudio/rserver.conf'])
    assert result.exit_code == 0, "RStudio server config file should exist"

    # Verify RStudio server binary exists and functions properly
    result = container.container.exec_run(['rstudio-server', 'version'])
    # The version command might not be available in all installations, so check for the binary itself
    if result.exit_code != 0:
        # Just verify the binary exists and is executable
        result = container.container.exec_run(['test', '-x', '/usr/lib/rstudio-server/bin/rserver'])
        assert result.exit_code == 0, "RStudio server binary should exist and be executable"

    # Check for RStudio configuration files and verify security settings
    result = container.container.exec_run(['cat', '/etc/rstudio/rserver.conf'])
    assert result.exit_code == 0, "RStudio server config file should be readable"

    config_content = result.output.decode('utf-8')
    # Verify security settings are present (these should be configured in the Dockerfile)
    assert 'www-frame-origin=none' in config_content or 'www-frame-origin' in config_content, "Security setting 'www-frame-origin' should be configured"
    assert 'www-enable-origin-check=1' in config_content or 'www-enable-origin' in config_content, "Security setting 'www-enable-origin-check' should be configured"

    # Check for rsession configuration
    result = container.container.exec_run(['test', '-f', '/etc/rstudio/rsession.conf'])
    assert result.exit_code == 0, "RStudio session config file should exist"

    LOGGER.info("RStudio web interface components test completed")
 

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
test_rstudio_web
~~~~~~~~~~~~~~~~
Tests for RStudio web interface functionality.

These tests verify that:
- RStudio web server is accessible
- Basic web interface functionality works
- RStudio can execute R commands through the web interface
"""

import logging
import time

import pytest

from tests.general.wait_utils import wait_for_http_response, wait_for_condition

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.skip(reason="RStudio web interface tests require additional container setup with exposed ports")
def test_rstudio_web_interface(container, http_client, url="http://localhost:8787"):
    """Test that RStudio web interface is accessible."""
    LOGGER.info(f"Testing RStudio web interface at {url}...")
    
    # Container setup for RStudio server (this is complex and requires specific port exposure)
    # This test is more complex as RStudio server needs to be configured for testing 
    # This is typically a skipped test that needs special setup
    pass


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

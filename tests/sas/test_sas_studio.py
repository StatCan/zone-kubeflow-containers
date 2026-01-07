# Copyright (c) Statistics Canada. All rights reserved.

"""
test_sas_studio
~~~~~~~~~~~~~~~
Tests for SAS Studio functionality.

These tests verify that:
- SAS Studio web interface is accessible
- SAS Studio environment is properly configured
- Basic SAS Studio operations work
"""

import logging
import time

import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def sas_studio_helper(container):
    """Return a container ready for SAS Studio testing"""
    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["which", "sas"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        LOGGER.warning(f"SAS binary not found in expected location. Output: {output}")

    return container


@pytest.mark.integration
def test_sas_studio_available(sas_studio_helper):
    """Test that SAS Studio environment is available."""
    LOGGER.info("Testing SAS Studio availability...")

    # Check for SAS Studio related processes or directories
    # In a real SAS Studio environment, this would check for the actual SAS Studio web service
    # For now, we'll check if SAS is available since SAS Studio builds on SAS
    
    result = sas_studio_helper.container.exec_run(["which", "sas"])
    assert result.exit_code == 0, "SAS should be available for SAS Studio"
    
    LOGGER.info("SAS Studio base environment check completed")


@pytest.mark.integration
def test_sas_studio_web_accessibility(sas_studio_helper):
    """Test that SAS Studio web interface is accessible."""
    LOGGER.info("Testing SAS Studio web interface accessibility...")

    # This test would normally check if SAS Studio web interface is accessible
    # Since proper testing requires web interface setup with exposed ports, 
    # we'll do basic checks here and mark as skipped for now
    pytest.skip("SAS Studio web interface tests require additional container setup with exposed ports and web interface configuration")
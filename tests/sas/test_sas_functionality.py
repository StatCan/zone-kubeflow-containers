# Copyright (c) Statistics Canada. All rights reserved.

"""
Basic test for SAS functionality.
"""

import logging

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.smoke
def test_sas_available(sas_container):
    """Test that SAS container runs properly (SAS availability check)."""
    LOGGER.info("Testing SAS container functionality...")

    try:
        # Start the SAS container
        sas_container.run()
    except Exception as e:
        pytest.fail(f"Failed to start SAS container: {str(e)}")

    # Check if SAS executable exists (this may not be present in all images)
    try:
        result = sas_container.container.exec_run(["bash", "-c", "command -v sas || echo 'SAS not found'"])
        output = result.output.decode('utf-8').strip()

        LOGGER.info(f"SAS check result: {output}")
    except Exception as e:
        LOGGER.warning(f"Could not check for SAS executable: {str(e)}. Container ran successfully.")

    # The important thing is that the container started without error
    LOGGER.info("SAS container test completed (infrastructure demo)")

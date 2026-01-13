# Copyright (c) Statistics Canada. All rights reserved.

"""
Basic test to demonstrate kernel execution functionality.
"""

import logging

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.smoke
def test_basic_kernel_execution(container):
    """Test basic container functionality."""
    LOGGER.info("Testing basic container execution...")

    try:
        # Start the container
        container.run()
    except Exception as e:
        pytest.fail(f"Failed to start container: {str(e)}")

    try:
        # Execute a simple command in the container
        result = container.container.exec_run(["echo", "hello world"])
    except Exception as e:
        pytest.fail(f"Failed to execute command in container: {str(e)}")

    assert result.exit_code == 0, (
        f"Command failed with exit code {result.exit_code}. "
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8').strip()
    assert output == "hello world", f"Unexpected output: {output}"

    LOGGER.info("Basic container execution test passed")
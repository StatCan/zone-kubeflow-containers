# Copyright (c) Statistics Canada. All rights reserved.

"""
Basic test for Python functionality in jupyterlab-cpu image.
"""

import logging

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.smoke
def test_python_available(container):
    """Test that Python is available in the jupyterlab-cpu image."""
    LOGGER.info("Testing Python availability...")

    try:
        # Start the container
        container.run()

        # Execute a simple Python command
        result = container.container.exec_run(["python", "--version"])
    except Exception as e:
        pytest.fail(f"Failed to execute Python command in container: {str(e)}")

    assert result.exit_code == 0, (
        f"Python command failed with exit code {result.exit_code}. "
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8').strip()
    assert "Python" in output, f"Unexpected Python version output: {output}"

    LOGGER.info(f"Python available: {output}")
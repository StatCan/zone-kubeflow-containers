# Copyright (c) Statistics Canada. All rights reserved.

"""
Basic test for Python functionality in jupyterlab-cpu image.
"""

import logging

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.smoke
def test_python_available(jupyter_container):
    """Test that Python is available in the jupyterlab-cpu image."""
    LOGGER.info("Testing Python availability...")
    
    # Execute a simple Python command
    result = jupyter_container.container.exec_run(["python", "--version"])
    
    assert result.exit_code == 0, f"Python command failed with exit code {result.exit_code}"
    
    output = result.output.decode('utf-8').strip()
    assert "Python" in output, f"Unexpected Python version output: {output}"
    
    LOGGER.info(f"Python available: {output}")
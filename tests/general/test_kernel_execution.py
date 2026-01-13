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
    
    # Start the container
    container.run()
    
    # Execute a simple command in the container
    result = container.container.exec_run(["echo", "hello world"])
    
    assert result.exit_code == 0, f"Command failed with exit code {result.exit_code}"
    
    output = result.output.decode('utf-8').strip()
    assert output == "hello world", f"Unexpected output: {output}"
    
    LOGGER.info("Basic container execution test passed")
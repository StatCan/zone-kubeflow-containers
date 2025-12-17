# Copyright (c) Statistics Canada. All rights reserved.

"""
test_julia
~~~~~~~~~~
Basic tests for Julia functionality.

These tests verify that:
- Julia can be executed
- Basic Julia functionality works
"""

import logging

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
def test_julia(container):
    """Basic julia test"""
    LOGGER.info("Test that julia is correctly installed ...")
    running_container = container.run(
        tty=True, command=["start.sh", "bash", "-c", "sleep infinity"]
    )
    command = "julia --version"
    cmd = running_container.exec_run(command)
    output = cmd.output.decode("utf-8")
    assert cmd.exit_code == 0, f"Command {command} failed {output}"
    LOGGER.debug(output)
    LOGGER.info("Julia basic functionality test completed")
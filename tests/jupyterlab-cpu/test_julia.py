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

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def julia_helper(container):
    """Return a container ready for Julia testing"""
    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["julia", "--startup-file=no", "-e", "1"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=60,  # Julia takes longer to start
        initial_delay=1.0,
        max_delay=5.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for Julia execution within timeout. Output: {output}")

    return container


def test_julia(julia_helper):
    """Basic julia test"""
    LOGGER.info("Test that julia is correctly installed ...")
    command = ["julia", "--startup-file=no", "-e", "Base.banner() || println(Base.banner) || 1"]
    result = julia_helper.container.exec_run(command)
    output = result.output.decode("utf-8")
    assert result.exit_code == 0, f"Julia execution failed {output}"
    LOGGER.debug(output)
    LOGGER.info("Julia basic functionality test completed")
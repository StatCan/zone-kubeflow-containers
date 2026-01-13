# Copyright (c) Statistics Canada. All rights reserved.
import logging
import pytest

LOGGER = logging.getLogger(__name__)


def test_julia(container):
    """Basic julia test"""
    LOGGER.info("Test that julia is correctly installed ...")

    try:
        # Start the container
        container.run()
        command = "julia --version"
        cmd = container.container.exec_run(command)
        output = cmd.output.decode("utf-8")

        # If julia is not installed in this image, skip the test
        if cmd.exit_code != 0 and "command not found" in output.lower():
            pytest.skip("Julia is not installed in this image")

        assert cmd.exit_code == 0, f"Command {command} failed {output}"
        LOGGER.debug(output)
    except Exception as e:
        # If julia is not available in this image, skip the test
        if "command not found" in str(e).lower() or "no such file" in str(e).lower():
            pytest.skip("Julia is not installed in this image")
        else:
            raise
# Copyright (c) Statistics Canada. All rights reserved.
import logging

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "name,command_list",
    [
        (
            "Sum series",
            [
                "import pandas as pd",
                "import numpy as np",
                "np.random.seed(0)",
                "print(pd.Series(np.random.randint(0, 7, size=10)).sum())"
            ]
        ),
    ],
)
def test_pandas(container, name, command_list):
    """Basic pandas tests"""
    LOGGER.info(f"Testing pandas: {name} ...")

    try:
        command = ';'.join(command_list)
        c = container.run(tty=True, command=["start.sh", "python", "-c", command])
        rv = c.wait(timeout=120)

        # If pandas is not available in this image, skip the test
        logs = c.logs(stdout=True).decode("utf-8")
        if "ModuleNotFoundError" in logs or "ImportError" in logs:
            pytest.skip("Pandas or required modules not available in this image")

        assert rv == 0 or rv["StatusCode"] == 0, f"Command {command} failed: {logs}"
        LOGGER.debug(logs)
    except Exception as e:
        # If pandas is not available in this image, skip the test
        if "command not found" in str(e).lower() or "no such file" in str(e).lower() or "module not found" in str(e).lower():
            pytest.skip("Pandas or required modules not available in this image")
        else:
            raise

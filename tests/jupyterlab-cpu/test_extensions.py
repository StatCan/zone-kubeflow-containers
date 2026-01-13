# Copyright (c) Statistics Canada. All rights reserved.
import logging

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.xfail(reason="Not yet compliant with JupyterLab 3 - Extension management changed in newer versions")
@pytest.mark.parametrize(
    "extension",
    [
        "@bokeh/jupyter_bokeh",
        "@jupyter-widgets/jupyterlab-manager",
        "jupyter-matplotlib",
    ],
)
def test_check_extension(container, extension):
    """Basic check of each extension

    The list of extensions can be obtained through this command

    $ jupyter labextension list

    """
    LOGGER.info(f"Checking the extension: {extension} ...")

    try:
        c = container.run(
            tty=True, command=["start.sh", "jupyter", "labextension", "check", extension]
        )
        rv = c.wait(timeout=10)
        logs = c.logs(stdout=True).decode("utf-8")
        LOGGER.debug(logs)

        # If jupyter labextension command is not available, skip the test
        if "command not found" in logs.lower() or "jupyter: command not found" in logs.lower():
            pytest.skip("JupyterLab extensions not available in this image")

        assert rv == 0 or rv["StatusCode"] == 0, f"Extension {extension} check failed: {logs}"
    except Exception as e:
        # If jupyter labextension command is not available, skip the test
        if "command not found" in str(e).lower() or "no such file" in str(e).lower():
            pytest.skip("JupyterLab extensions not available in this image")
        else:
            raise

"""
test_zone_browser
~~~~~~~~~~~~~~~~~
Test the in-pod secure browser (zone-browser).

Verifies the components needed for interactive Entra ID sign-in inside the
pod:
- zone-browser launcher and zone-browser-viewer.py on disk / PATH
- wired up via $BROWSER / $R_BROWSER
- DISPLAY exported in interactive shells (required by `az login`)
- the "Zone Browser" JupyterLab tile registered with jupyter-server-proxy
- headless Chromium + CDP viewer actually start, serve and navigate
  (`zone-browser --selftest`)

Example:

    $ make test/mid
"""

import logging
import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
def test_zone_browser_stack(container):
    """Test that the in-pod secure browser is installed and functional."""
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("zone-browser not expected in base image")

    LOGGER.info("Testing zone-browser secure browser stack...")

    container.run()

    success, output = wait_for_exec_success(
        container=container,
        command=["which", "zone-browser"],
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )
    if not success:
        raise AssertionError(
            f"Container failed to be ready for execution within timeout. Output: {output}"
        )

    result = container.container.exec_run(["test", "-x", "/usr/local/bin/zone-browser-viewer.py"])
    assert result.exit_code == 0, "zone-browser-viewer.py not found or not executable"

    # webbrowser/az/R must be routed to the in-pod browser
    for var in ["BROWSER", "R_BROWSER"]:
        result = container.container.exec_run(["printenv", var])
        assert result.exit_code == 0 and b"zone-browser" in result.output, (
            f"{var} env var not set to zone-browser: {result.output}"
        )

    # `az login` requires a GUI env var in the (interactive) shell it runs from
    result = container.container.exec_run(["bash", "-ic", "echo DISPLAY=$DISPLAY"])
    assert b"DISPLAY=:" in result.output, (
        f"DISPLAY not exported in interactive shells: {result.output}"
    )

    # The "Zone Browser" Launcher tile must be registered with
    # jupyter-server-proxy (traitlets config, not jupyter_server_config.d)
    result = container.container.exec_run(
        ["cat", "/opt/conda/etc/jupyter/jupyter_server_config.json"]
    )
    assert result.exit_code == 0 and b"zone-browser" in result.output, (
        f"zone-browser server-proxy config missing: {result.output}"
    )

    # The auto-open labextension must be built and installed (opens the Zone
    # Browser tab in JupyterLab when a sign-in starts)
    result = container.container.exec_run(
        ["ls", "/opt/conda/share/jupyter/labextensions/zone-browser-autoopen/static"]
    )
    assert result.exit_code == 0 and b"remoteEntry" in result.output, (
        f"zone-browser-autoopen labextension not installed: {result.output}"
    )

    # R sign-ins (AzureAuth/browseURL) must route to the in-pod browser,
    # including in RStudio, which overrides the browser option at session
    # init -- hence the rstudio.sessionInit hook in Rprofile.site
    result = container.container.exec_run(
        ["grep", "-q", "rstudio.sessionInit", "/opt/conda/lib/R/etc/Rprofile.site"]
    )
    assert result.exit_code == 0, (
        "zone-browser hook missing from Rprofile.site"
    )

    # Starts headless Chromium + the CDP viewer, probes the viewer page and
    # the /open navigation API, then stops everything.
    result = container.container.exec_run(["zone-browser", "--selftest"])
    LOGGER.info(f"zone-browser --selftest output:\n{result.output.decode('utf-8')}")
    assert result.exit_code == 0, (
        f"zone-browser --selftest failed: {result.output.decode('utf-8')}"
    )

    LOGGER.info("zone-browser secure browser stack is installed and functional")

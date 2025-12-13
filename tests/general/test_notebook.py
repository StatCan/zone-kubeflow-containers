# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import logging

from tests.general.wait_utils import wait_for_http_response

LOGGER = logging.getLogger(__name__)


def test_server_alive(container, http_client, url="http://localhost:8888"):
    """Notebook server should eventually appear with a recognizable page."""

    # Redirect url to NB_PREFIX if it is set in the container environment
    url = "{}{}/".format(url, container.kwargs['environment']['NB_PREFIX'])

    LOGGER.info("Running test_server_alive")
    LOGGER.info("launching the container")
    container.run()

    # Wait for server to respond to HTTP requests with exponential backoff
    success = wait_for_http_response(
        http_client=http_client,
        url=url,
        expected_status=200,
        timeout=60,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Failed to connect to server at {url} within 60 seconds")

    LOGGER.info(f"accessing {url}")
    resp = http_client.get(url)
    resp.raise_for_status()
    LOGGER.debug(f"got text from url: {resp.text}")

    # Not sure why but some flavors of JupyterLab images don't hit all of these.
    # Trying to catch several different acceptable looks.
    # Also accepting RStudio
    # TODO: This general test accepts many different images.
    #       Could refactor to have specific tests that are more pointed

    # Define various possible expected texts (this catches different expected outcomes like a JupyterLab interface,
    # RStudio, etc.).  If any of these pass, the test passes
    assertion_expected_texts = [
        "<title>JupyterLab",
        "<title>Jupyter Notebook</title>",
        "<title>RStudio</title>",
        '<html lang="en" class="noVNC_loading">',  # Remote desktop
        '<html lang="fr" class="noVNC_loading">',  # Remote desktop
        '<span id="running_list_info">Currently running Jupyter processes</span>',
    ]
    assertions = [s in resp.text for s in assertion_expected_texts]

    # Log assertions to screen for easier debugging
    LOGGER.debug("Status of tests look for that indicate notebook is up:")
    for i, (text, assertion) in enumerate(zip(assertion_expected_texts, assertions)):
        LOGGER.debug(f"{i}: '{text}' in resp.text = {assertion}")

    # Provide detailed error message if all assertions fail
    error_message = (
        f"Server at {url} did not return a recognizable interface.\n"
        f"HTTP Status: {resp.status_code}\n"
        f"Expected one of the following in response:\n"
    )
    for i, text in enumerate(assertion_expected_texts):
        error_message += f"  {i+1}. '{text}'\n"
    error_message += f"\nActual response (first 500 chars):\n{resp.text[:500]}\n"
    error_message += "Try accessing the server manually to diagnose the issue."

    assert any(assertions), error_message

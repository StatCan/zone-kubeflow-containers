# Copyright (c) Statistics Canada. All rights reserved.

"""
test_health
~~~~~~~~~~~
Basic health check tests for Jupyter containers.

Validates that containers start properly and respond to HTTP requests.
"""

import logging
import os

import pytest

from tests.general.wait_utils import wait_for_http_response

LOGGER = logging.getLogger(__name__)


def validate_required_env_vars():
    """Validate that required environment variables are set."""
    required_vars = ['IMAGE_NAME']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        pytest.fail(f"Missing required environment variables: {missing_vars}. "
                   f"Set IMAGE_NAME to the container image to test.")


@pytest.mark.smoke
@pytest.mark.integration
def test_server_responds_to_requests(container, http_client, url="http://localhost:8888"):
    """Test that the server responds with valid HTTP status codes."""
    # Validate prerequisites
    validate_required_env_vars()

    LOGGER.info("Testing server HTTP responses...")

    nb_prefix = container.kwargs['environment']['NB_PREFIX']
    url_with_prefix = f"{url}{nb_prefix}/"

    try:
        container.run()
    except Exception as e:
        pytest.fail(f"Failed to start container: {str(e)}")

    # Wait for server to respond to HTTP requests
    success = wait_for_http_response(
        http_client=http_client,
        url=url_with_prefix,
        expected_status=200,
        timeout=30
    )

    if not success:
        pytest.fail(
            f"Failed to connect to server at {url_with_prefix} within 30 seconds. "
            f"Check that the container is running and accessible."
        )

    # Additional verification
    try:
        resp = http_client.get(url_with_prefix, timeout=10)
    except Exception as e:
        pytest.fail(f"Failed to make HTTP request: {str(e)}")

    assert resp.status_code == 200, (
        f"Expected status 200, got {resp.status_code}\n"
        f"URL: {url_with_prefix}\n"
        f"Response: {resp.text[:500] if resp.text else 'No response body'}"
    )
    LOGGER.info(f"Server responded with status {resp.status_code}")
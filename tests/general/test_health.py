# Copyright (c) Statistics Canada. All rights reserved.

"""
test_health
~~~~~~~~~~~
Basic health check tests for Jupyter containers.

This is a minimal test to demonstrate the test infrastructure.
"""

import logging
import time

import pytest

from tests.general.wait_utils import wait_for_http_response

LOGGER = logging.getLogger(__name__)


@pytest.mark.smoke
@pytest.mark.integration
def test_server_responds_to_requests(container, http_client, url="http://localhost:8888"):
    """Test that the server responds with valid HTTP status codes."""
    LOGGER.info("Testing server HTTP responses...")

    nb_prefix = container.kwargs['environment']['NB_PREFIX']
    url_with_prefix = f"{url}{nb_prefix}/"

    container.run()

    # Wait for server to respond to HTTP requests
    success = wait_for_http_response(
        http_client=http_client,
        url=url_with_prefix,
        expected_status=200,
        timeout=30
    )

    if not success:
        raise AssertionError(
            f"Failed to connect to server at {url_with_prefix} within 30 seconds"
        )

    # Additional verification
    resp = http_client.get(url_with_prefix, timeout=10)
    assert resp.status_code == 200, (
        f"Expected status 200, got {resp.status_code}\n"
        f"URL: {url_with_prefix}\n"
        f"Response: {resp.text[:500]}"
    )
    LOGGER.info(f"Server responded with status {resp.status_code}")
# Copyright (c) Statistics Canada. All rights reserved.

"""
wait_utils
~~~~~~~~~~
Utility functions for waiting and polling.

This is a minimal version to demonstrate the test infrastructure.
"""

import time
import logging

LOGGER = logging.getLogger(__name__)


def wait_for_http_response(
    http_client,
    url: str,
    expected_status,
    timeout: float = 60.0
) -> bool:
    """
    Wait for an HTTP endpoint to return the expected status code.

    Args:
        http_client: Requests session object
        url: URL to poll
        expected_status: Expected HTTP status code(s)
        timeout: Maximum time to wait in seconds

    Returns:
        True if expected status received within timeout, False otherwise
    """
    import requests
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            resp = http_client.get(url, timeout=5)
            if isinstance(expected_status, int):
                if resp.status_code == expected_status:
                    return True
            else:
                if resp.status_code in expected_status:
                    return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)
    
    return False
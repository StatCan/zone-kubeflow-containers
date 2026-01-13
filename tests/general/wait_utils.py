# Copyright (c) Statistics Canada. All rights reserved.

"""
wait_utils
~~~~~~~~~~
Utility functions for waiting and polling with error handling.

Robust utilities for test synchronization with proper error reporting.
"""

import time
import logging
from typing import Union, List

LOGGER = logging.getLogger(__name__)


def wait_for_http_response(
    http_client,
    url: str,
    expected_status: Union[int, List[int]],
    timeout: float = 60.0,
    initial_delay: float = 0.5,
    max_delay: float = 3.0
) -> bool:
    """
    Wait for an HTTP endpoint to return the expected status code with exponential backoff.

    Args:
        http_client: Requests session object with retry configuration
        url: URL to poll
        expected_status: Expected HTTP status code(s)
        timeout: Maximum time to wait in seconds
        initial_delay: Initial delay between polls
        max_delay: Maximum delay between polls

    Returns:
        True if expected status received within timeout, False otherwise
    """
    import requests

    start_time = time.time()
    current_delay = initial_delay

    LOGGER.debug(f"Waiting for HTTP {expected_status} response from {url}")

    while time.time() - start_time < timeout:
        try:
            # Use shorter timeout for individual requests to avoid hanging
            resp = http_client.get(url, timeout=min(10.0, max_delay))

            # Check if response status matches expected
            if isinstance(expected_status, int):
                status_match = resp.status_code == expected_status
            else:
                status_match = resp.status_code in expected_status

            if status_match:
                elapsed = time.time() - start_time
                LOGGER.debug(f"HTTP response {resp.status_code} received after {elapsed:.2f}s")
                return True

        except requests.exceptions.RequestException as e:
            # Log connection errors but continue waiting
            LOGGER.debug(f"Request failed (will retry): {str(e)}")
        except Exception as e:
            # Log unexpected errors but continue waiting
            LOGGER.warning(f"Unexpected error during HTTP check: {str(e)}")

        # Exponential backoff with max delay
        time.sleep(min(current_delay, max_delay))
        current_delay *= 1.5  # Exponential backoff

    elapsed = time.time() - start_time
    LOGGER.warning(f"Timeout waiting for HTTP {expected_status} from {url} after {elapsed:.2f}s")
    return False
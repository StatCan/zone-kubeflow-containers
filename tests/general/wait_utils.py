# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
wait_utils
~~~~~~~~~~
Utility functions for waiting and polling with exponential backoff.

These utilities provide consistent waiting mechanisms across all tests
to prevent flaky tests caused by fixed sleep times. They implement
exponential backoff with jitter to handle system load variations.
"""

import time
import logging
import random
from typing import Callable, Type, Union, Any

LOGGER = logging.getLogger(__name__)


def wait_for_condition(
    condition_func: Callable[[], bool],
    timeout: float = 30.0,
    initial_delay: float = 0.1,
    max_delay: float = 5.0,
    exponential_base: float = 1.5,
    jitter: bool = True,
    poll_interval: float = 0.5,
    description: str = "condition"
) -> bool:
    """
    Wait for a condition to become true with exponential backoff.

    Args:
        condition_func: A callable that returns True when the condition is met
        timeout: Maximum time to wait in seconds (default: 30.0)
        initial_delay: Initial delay between polls in seconds (default: 0.1)
        max_delay: Maximum delay between polls in seconds (default: 5.0)
        exponential_base: Base for exponential backoff growth (default: 1.5)
        jitter: Whether to add random jitter to delay times (default: True)
        poll_interval: Base interval for polling (default: 0.5)
        description: Description of the condition for logging purposes

    Returns:
        True if condition was met within timeout, False otherwise
    """
    start_time = time.time()
    current_delay = initial_delay

    LOGGER.debug(f"Waiting for {description} with timeout {timeout}s")

    while time.time() - start_time < timeout:
        if condition_func():
            elapsed = time.time() - start_time
            LOGGER.debug(f"{description} satisfied after {elapsed:.2f}s")
            return True

        # Calculate next delay with exponential backoff
        next_delay = min(current_delay, max_delay)
        
        # Apply jitter if enabled
        if jitter:
            jitter_factor = random.uniform(0.8, 1.2)
            next_delay *= jitter_factor
        
        # Ensure we don't exceed timeout
        remaining_time = timeout - (time.time() - start_time)
        sleep_time = min(next_delay, remaining_time)

        if sleep_time > 0:
            time.sleep(sleep_time)

        # Increase delay for next iteration using exponential backoff
        current_delay *= exponential_base

    elapsed = time.time() - start_time
    LOGGER.warning(f"Timeout waiting for {description} after {elapsed:.2f}s")
    return False


def wait_for_http_response(
    http_client,
    url: str,
    expected_status: Union[int, list] = 200,
    timeout: float = 60.0,
    initial_delay: float = 0.1,
    max_delay: float = 3.0,
    description: str = None
) -> bool:
    """
    Wait for an HTTP endpoint to return the expected status code.

    Args:
        http_client: Requests session object
        url: URL to poll
        expected_status: Expected HTTP status code(s)
        timeout: Maximum time to wait in seconds
        initial_delay: Initial delay between polls in seconds
        max_delay: Maximum delay between polls in seconds
        description: Description for logging (auto-generated if None)

    Returns:
        True if expected status received within timeout, False otherwise
    """
    if description is None:
        description = f"HTTP {expected_status} response from {url}"

    def check_http_response():
        try:
            resp = http_client.get(url, timeout=min(10.0, max_delay))  # Use shorter timeout for individual requests
            if isinstance(expected_status, int):
                return resp.status_code == expected_status
            else:
                return resp.status_code in expected_status
        except Exception:
            return False

    return wait_for_condition(
        check_http_response,
        timeout=timeout,
        initial_delay=initial_delay,
        max_delay=max_delay,
        description=description
    )


def wait_for_container_log_match(
    container,
    pattern: str,
    timeout: float = 60.0,
    initial_delay: float = 0.5,
    max_delay: float = 5.0
) -> bool:
    """
    Wait for a container to log a message containing the given pattern.

    Args:
        container: Container object with logs() method
        pattern: String pattern to search for in logs
        timeout: Maximum time to wait in seconds
        initial_delay: Initial delay between polls in seconds
        max_delay: Maximum delay between polls in seconds

    Returns:
        True if pattern found in logs within timeout, False otherwise
    """
    def check_log_contains():
        try:
            logs = container.container.logs().decode("utf-8")
            return pattern.lower() in logs.lower()
        except Exception:
            return False

    return wait_for_condition(
        check_log_contains,
        timeout=timeout,
        initial_delay=initial_delay,
        max_delay=max_delay,
        description=f"log containing '{pattern}'"
    )


def wait_for_port_open(
    container,
    port: int,
    timeout: float = 30.0,
    initial_delay: float = 0.1,
    max_delay: float = 2.0
) -> bool:
    """
    Wait for a port to be open/listening inside the container.

    Args:
        container: Container object
        port: Port number to check
        timeout: Maximum time to wait in seconds
        initial_delay: Initial delay between polls in seconds
        max_delay: Maximum delay between polls in seconds

    Returns:
        True if port is open within timeout, False otherwise
    """
    def check_port_open():
        try:
            check_port_cmd = f"netstat -tuln | grep :{port} || ss -tuln | grep :{port}"
            result = container.container.exec_run(["bash", "-c", check_port_cmd])
            return result.exit_code == 0
        except Exception:
            return False

    return wait_for_condition(
        check_port_open,
        timeout=timeout,
        initial_delay=initial_delay,
        max_delay=max_delay,
        description=f"port {port} to be open"
    )


def wait_for_exec_success(
    container,
    command: list,
    timeout: float = 30.0,
    initial_delay: float = 0.5,
    max_delay: float = 3.0
) -> tuple[bool, str]:
    """
    Wait for a command to execute successfully inside the container.

    Args:
        container: Container object
        command: Command to execute
        timeout: Maximum time to wait in seconds
        initial_delay: Initial delay between polls in seconds
        max_delay: Maximum delay between polls in seconds

    Returns:
        Tuple of (success: bool, output: str)
    """
    success_result = [None, None]  # Using list to allow modification in closure

    def check_exec_success():
        try:
            result = container.container.exec_run(command)
            success_result[0] = result.exit_code == 0
            success_result[1] = result.output.decode('utf-8')
            return success_result[0]
        except Exception as e:
            success_result[1] = str(e)
            return False

    satisfied = wait_for_condition(
        check_exec_success,
        timeout=timeout,
        initial_delay=initial_delay,
        max_delay=max_delay,
        description=f"command {command} to succeed"
    )

    return satisfied, success_result[1]
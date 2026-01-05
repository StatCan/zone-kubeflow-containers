# Copyright (c) Statistics Canada. All rights reserved.

"""
test_environment
~~~~~~~~~~~~~~~~
Tests for environment variable configuration and propagation.

These tests verify that:
- Environment variables are correctly set in containers
- NB_PREFIX configuration is applied to URLs
- Custom environment variables are accessible within the container
- Path configurations work correctly
- Configuration is passed through properly
"""

import logging
import os

import pytest

from tests.general.wait_utils import wait_for_http_response

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
def test_nb_prefix_env_variable_set(container):
    """Test that NB_PREFIX environment variable is set in container."""
    LOGGER.info("Testing NB_PREFIX environment variable...")
    
    expected_prefix = container.kwargs['environment']['NB_PREFIX']
    container.run()
    
    # Check if NB_PREFIX is set in the container
    cmd = 'echo $NB_PREFIX'
    result = container.container.exec_run(['bash', '-c', cmd])
    actual_prefix = result.output.decode('utf-8').strip()
    
    assert actual_prefix == expected_prefix, (
        f"NB_PREFIX mismatch:\n"
        f"Expected: '{expected_prefix}'\n"
        f"Actual: '{actual_prefix}'"
    )
    
    LOGGER.info(f"NB_PREFIX correctly set to: {actual_prefix}")


@pytest.mark.integration
def test_nb_prefix_in_url(container, http_client, url="http://localhost:8888"):
    """Test that NB_PREFIX is correctly applied to request URLs."""
    LOGGER.info("Testing NB_PREFIX in URL...")

    nb_prefix = container.kwargs['environment']['NB_PREFIX']
    url_with_prefix = f"{url}{nb_prefix}/"

    container.run()

    # Wait for server to respond to HTTP requests with exponential backoff
    success = wait_for_http_response(
        http_client=http_client,
        url=url_with_prefix,
        expected_status=200,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(
            f"Failed to access URL with NB_PREFIX: {url_with_prefix} within 30 seconds"
        )

    # Make final verification request
    resp = http_client.get(url_with_prefix, timeout=10)

    assert resp.status_code == 200, (
        f"URL with NB_PREFIX returned {resp.status_code}\n"
        f"URL: {url_with_prefix}\n"
        f"NB_PREFIX: {nb_prefix}"
    )

    LOGGER.info(f"NB_PREFIX URL accessible: {url_with_prefix}")


@pytest.mark.integration
def test_nb_prefix_empty_string(container, http_client, url="http://localhost:8888"):
    """Test that empty NB_PREFIX works correctly."""
    LOGGER.info("Testing empty NB_PREFIX...")

    nb_prefix = container.kwargs['environment']['NB_PREFIX']

    # If NB_PREFIX is empty, URL should be clean without trailing slashes
    if nb_prefix == "":
        url_to_test = f"{url}/"

        container.run()

        # Wait for server to respond to HTTP requests with exponential backoff
        success = wait_for_http_response(
            http_client=http_client,
            url=url_to_test,
            expected_status=200,
            timeout=30,
            initial_delay=0.5,
            max_delay=3.0
        )

        if not success:
            raise AssertionError(
                f"Failed to access root URL with empty NB_PREFIX: {url_to_test} within 30 seconds"
            )

        # Make final verification request
        resp = http_client.get(url_to_test, timeout=10)

        assert resp.status_code == 200, (
            f"Root URL with empty NB_PREFIX returned {resp.status_code}\n"
            f"URL: {url_to_test}"
        )

        LOGGER.info("Empty NB_PREFIX handled correctly")
    else:
        LOGGER.info(f"Skipping empty NB_PREFIX test (NB_PREFIX='{nb_prefix}')")


@pytest.mark.integration
def test_home_directory_accessible(container):
    """Test that /home/jovyan directory exists and is accessible."""
    LOGGER.info("Testing /home/jovyan directory...")
    
    container.run()
    
    # Check if /home/jovyan exists
    cmd = 'test -d /home/jovyan && echo "exists" || echo "missing"'
    result = container.container.exec_run(['bash', '-c', cmd])
    output = result.output.decode('utf-8').strip()
    
    assert output == "exists", (
        f"/home/jovyan directory is {output}\n"
        "This directory is required for the notebook user"
    )
    
    LOGGER.info("/home/jovyan directory exists")


@pytest.mark.integration
def test_jovyan_user_exists(container):
    """Test that the jovyan user exists in the container."""
    LOGGER.info("Testing jovyan user...")
    
    container.run()
    
    # Check if jovyan user exists
    cmd = 'id jovyan > /dev/null 2>&1 && echo "exists" || echo "missing"'
    result = container.container.exec_run(['bash', '-c', cmd])
    output = result.output.decode('utf-8').strip()
    
    assert output == "exists", (
        "The 'jovyan' user does not exist in the container\n"
        "This is required for Jupyter server operation"
    )
    
    LOGGER.info("jovyan user exists")


@pytest.mark.integration
def test_python_path_accessible(container):
    """Test that Python is accessible and correct version."""
    LOGGER.info("Testing Python path and version...")
    
    container.run()
    
    # Check Python version
    cmd = 'python --version'
    result = container.container.exec_run(['bash', '-c', cmd])
    output = result.output.decode('utf-8').strip()
    
    assert result.exit_code == 0, (
        f"Failed to get Python version: {output}"
    )
    
    assert "Python 3" in output, (
        f"Expected Python 3, got: {output}"
    )
    
    LOGGER.info(f"Python available: {output}")


@pytest.mark.integration
def test_jupyter_executable_available(container):
    """Test that jupyter command is available."""
    LOGGER.info("Testing jupyter command availability...")
    
    container.run()
    
    # Check if jupyter is available
    cmd = 'jupyter --version'
    result = container.container.exec_run(['bash', '-c', cmd])
    
    assert result.exit_code == 0, (
        f"jupyter command not available\n"
        f"Output: {result.output.decode('utf-8')}"
    )
    
    output = result.output.decode('utf-8').strip()
    LOGGER.info(f"Jupyter available: {output}")


@pytest.mark.integration
def test_pip_accessible(container):
    """Test that pip package manager is accessible."""
    LOGGER.info("Testing pip availability...")
    
    container.run()
    
    # Check if pip is available
    cmd = 'pip --version'
    result = container.container.exec_run(['bash', '-c', cmd])
    
    assert result.exit_code == 0, (
        f"pip not available\n"
        f"Output: {result.output.decode('utf-8')}"
    )
    
    output = result.output.decode('utf-8').strip()
    LOGGER.info(f"pip available: {output}")


@pytest.mark.integration
def test_conda_accessible(container):
    """Test that conda is accessible (if conda-based image)."""
    LOGGER.info("Testing conda availability...")
    
    container.run()
    
    # Check if conda is available
    cmd = 'conda --version'
    result = container.container.exec_run(['bash', '-c', cmd])
    
    if result.exit_code == 0:
        output = result.output.decode('utf-8').strip()
        LOGGER.info(f"conda available: {output}")
    else:
        LOGGER.info("conda not available (non-conda-based image)")


@pytest.mark.integration
def test_locale_configuration(container):
    """Test that locale is properly configured."""
    LOGGER.info("Testing locale configuration...")
    
    container.run()
    
    # Check locale
    cmd = 'locale | head -1'
    result = container.container.exec_run(['bash', '-c', cmd])
    output = result.output.decode('utf-8').strip()
    
    # Most containers should have UTF-8 locale
    if "UTF-8" not in output and "utf8" not in output.lower():
        LOGGER.warning(f"Unexpected locale configuration: {output}")
    else:
        LOGGER.info(f"Locale properly configured: {output}")


@pytest.mark.integration
def test_timezone_accessible(container):
    """Test that timezone information is accessible."""
    LOGGER.info("Testing timezone configuration...")
    
    container.run()
    
    # Check timezone
    cmd = 'date +%Z'
    result = container.container.exec_run(['bash', '-c', cmd])
    
    assert result.exit_code == 0, "Failed to get timezone"
    
    output = result.output.decode('utf-8').strip()
    LOGGER.info(f"Timezone: {output}")


@pytest.mark.integration
def test_custom_env_variable_propagation(container):
    """Test that custom environment variables can be set and accessed."""
    LOGGER.info("Testing custom environment variable propagation...")
    
    # Set a custom env variable
    test_var_name = "TEST_CUSTOM_VAR"
    test_var_value = "test_value_12345"
    
    container.kwargs['environment'][test_var_name] = test_var_value
    container.run()
    
    # Check if the custom variable is accessible
    cmd = f'echo ${test_var_name}'
    result = container.container.exec_run(['bash', '-c', cmd])
    actual_value = result.output.decode('utf-8').strip()
    
    assert actual_value == test_var_value, (
        f"Custom environment variable mismatch:\n"
        f"Expected: '{test_var_value}'\n"
        f"Actual: '{actual_value}'"
    )
    
    LOGGER.info(f"Custom environment variable correctly propagated: {test_var_name}={test_var_value}")


@pytest.mark.integration
def test_working_directory_accessible(container):
    """Test that working directory is set correctly."""
    LOGGER.info("Testing working directory...")
    
    container.run()
    
    # Check working directory
    cmd = 'pwd'
    result = container.container.exec_run(['bash', '-c', cmd])
    cwd = result.output.decode('utf-8').strip()
    
    assert cwd, "Could not determine working directory"
    
    # Should be accessible
    cmd = f'test -d "{cwd}" && echo "accessible" || echo "inaccessible"'
    result = container.container.exec_run(['bash', '-c', cmd])
    output = result.output.decode('utf-8').strip()
    
    assert output == "accessible", f"Working directory not accessible: {cwd}"
    
    LOGGER.info(f"Working directory accessible: {cwd}")

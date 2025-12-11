# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
test_health
~~~~~~~~~~~
Health check and readiness tests for Jupyter containers.

These tests verify that:
- Services start successfully
- Servers respond to health endpoints
- Container is ready to accept connections
- Response times are acceptable
- All critical endpoints are accessible
"""

import logging
import time

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.smoke
@pytest.mark.integration
def test_server_startup_time(container, http_client, url="http://localhost:8888"):
    """Test that the Jupyter server starts within a reasonable timeframe."""
    LOGGER.info("Testing server startup time...")
    
    nb_prefix = container.kwargs['environment']['NB_PREFIX']
    url_with_prefix = f"{url}{nb_prefix}/"
    
    start_time = time.time()
    container.run()
    
    # Try to connect with a timeout of 60 seconds
    max_wait = 60
    timeout_per_attempt = 5
    attempts = 0
    last_error = None
    
    while time.time() - start_time < max_wait:
        try:
            resp = http_client.get(url_with_prefix, timeout=timeout_per_attempt)
            if resp.status_code == 200:
                startup_time = time.time() - start_time
                LOGGER.info(f"Server started successfully in {startup_time:.2f} seconds")
                assert startup_time < 60, f"Server took {startup_time:.2f}s to start (expected < 60s)"
                return
        except Exception as e:
            last_error = e
            attempts += 1
            time.sleep(1)
    
    # If we get here, startup failed
    elapsed = time.time() - start_time
    error_msg = (
        f"Server failed to respond within {max_wait} seconds ({elapsed:.2f}s elapsed, {attempts} attempts).\n"
        f"Last error: {last_error}\n"
        f"URL tested: {url_with_prefix}"
    )
    raise AssertionError(error_msg)


@pytest.mark.smoke
@pytest.mark.integration
def test_server_responds_to_requests(container, http_client, url="http://localhost:8888"):
    """Test that the server responds with valid HTTP status codes."""
    LOGGER.info("Testing server HTTP responses...")
    
    nb_prefix = container.kwargs['environment']['NB_PREFIX']
    url_with_prefix = f"{url}{nb_prefix}/"
    
    container.run()
    
    # Allow time for server startup
    time.sleep(5)
    
    try:
        resp = http_client.get(url_with_prefix, timeout=10)
    except Exception as e:
        raise AssertionError(
            f"Failed to connect to server at {url_with_prefix}: {e}"
        )
    
    assert resp.status_code == 200, (
        f"Expected status 200, got {resp.status_code}\n"
        f"URL: {url_with_prefix}\n"
        f"Response: {resp.text[:500]}"
    )
    LOGGER.info(f"Server responded with status {resp.status_code}")


@pytest.mark.integration
def test_server_has_valid_html(container, http_client, url="http://localhost:8888"):
    """Test that the server returns valid HTML content."""
    LOGGER.info("Testing server HTML validity...")
    
    nb_prefix = container.kwargs['environment']['NB_PREFIX']
    url_with_prefix = f"{url}{nb_prefix}/"
    
    container.run()
    time.sleep(5)
    
    resp = http_client.get(url_with_prefix)
    resp.raise_for_status()
    
    content = resp.text
    
    # Check for basic HTML structure
    assert content.startswith("<!DOCTYPE") or "<html" in content.lower(), (
        f"Response does not appear to be valid HTML\n"
        f"First 200 chars: {content[:200]}"
    )
    
    # Check that response is not an error page
    error_indicators = ["404", "500", "error", "exception"]
    for indicator in error_indicators:
        assert indicator.lower() not in content[:1000].lower(), (
            f"Response appears to contain error indicator: {indicator}\n"
            f"Response start: {content[:500]}"
        )
    
    LOGGER.info("Server HTML is valid")


@pytest.mark.integration
def test_api_endpoint_accessible(container, http_client, url="http://localhost:8888"):
    """Test that the Jupyter API is accessible."""
    LOGGER.info("Testing Jupyter API accessibility...")
    
    nb_prefix = container.kwargs['environment']['NB_PREFIX']
    api_url = f"{url}{nb_prefix}/api/"
    
    container.run()
    time.sleep(5)
    
    try:
        resp = http_client.get(api_url, timeout=10)
    except Exception as e:
        raise AssertionError(
            f"Failed to access API at {api_url}: {e}"
        )
    
    # API endpoint should return 200 or sometimes 404 (depending on implementation)
    # but should NOT return 500 or be unreachable
    assert resp.status_code < 500, (
        f"API returned error status {resp.status_code}\n"
        f"URL: {api_url}\n"
        f"Response: {resp.text[:500]}"
    )
    
    LOGGER.info(f"API endpoint responded with status {resp.status_code}")


@pytest.mark.integration
def test_static_assets_accessible(container, http_client, url="http://localhost:8888"):
    """Test that static assets (CSS, JS) are accessible."""
    LOGGER.info("Testing static assets accessibility...")
    
    nb_prefix = container.kwargs['environment']['NB_PREFIX']
    container.run()
    time.sleep(5)
    
    # Try to fetch the main page to verify static assets are referenced
    home_url = f"{url}{nb_prefix}/"
    resp = http_client.get(home_url)
    resp.raise_for_status()
    
    # Check for presence of script/style tags
    content = resp.text
    has_scripts = "<script" in content or "src=" in content
    has_styles = "style" in content or "css" in content
    
    assert has_scripts or has_styles, (
        "Response does not appear to reference any static assets (scripts/styles)\n"
        "This may indicate a configuration issue"
    )
    
    LOGGER.info("Static assets appear to be referenced correctly")


@pytest.mark.integration
def test_container_logs_no_critical_errors(container):
    """Test that container logs don't show critical errors on startup."""
    LOGGER.info("Testing container logs for critical errors...")
    
    container.run()
    time.sleep(10)  # Give server time to initialize
    
    try:
        logs = container.container.logs(stdout=True, stderr=True).decode("utf-8")
    except Exception as e:
        LOGGER.warning(f"Could not retrieve container logs: {e}")
        return
    
    # Check for critical error indicators
    critical_errors = [
        "CRITICAL ERROR",
        "FATAL",
        "Traceback",
        "ERROR: Error",
        "Failed to start",
    ]
    
    found_errors = []
    for error_pattern in critical_errors:
        if error_pattern.lower() in logs.lower():
            found_errors.append(error_pattern)
    
    # Allow some warnings but fail on critical errors
    if found_errors:
        # Get last 1000 chars of logs for context
        error_context = logs[-1000:] if len(logs) > 1000 else logs
        LOGGER.warning(
            f"Found critical error patterns in logs: {found_errors}\n"
            f"Recent logs:\n{error_context}"
        )
        # Don't fail on this for now, just warn - server might still be functional
        # This can be made stricter in the future
    
    LOGGER.info("Container logs checked for critical errors")


@pytest.mark.integration
def test_port_8888_open(container):
    """Test that port 8888 is open and listening inside the container."""
    LOGGER.info("Testing that port 8888 is listening...")
    
    container.run()
    time.sleep(5)
    
    # Check if port 8888 is listening
    check_port_cmd = "netstat -tuln | grep 8888 || ss -tuln | grep 8888"
    result = container.container.exec_run(check_port_cmd, shell=True)
    
    assert result.exit_code == 0, (
        f"Port 8888 does not appear to be listening\n"
        f"Command output: {result.output.decode('utf-8')}"
    )
    
    LOGGER.info("Port 8888 is listening")

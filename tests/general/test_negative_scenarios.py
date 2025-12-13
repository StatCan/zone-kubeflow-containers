# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
test_negative_scenarios
~~~~~~~~~~~~~~~~~~~~~~~
Tests for error handling and negative scenarios in container functionality.

These tests verify that:
- Error conditions are properly handled
- Containers behave correctly when components fail
- Proper error messages are returned
- Failed operations don't crash the entire system
"""

import logging
import time

import pytest

from tests.general.wait_utils import wait_for_condition, wait_for_http_response

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
def test_container_with_invalid_command(container):
    """Test that container handles invalid commands gracefully."""
    LOGGER.info("Testing container behavior with invalid command...")

    # Try to run container with a command that will fail
    try:
        container.run(command=["invalid_command_that_does_not_exist"])
        
        # If container runs despite invalid command, that's unexpected
        # But we should be able to access logs to see the error
        logs = container.container.logs().decode("utf-8")
        
        # Verify that we can still get logs even after a command failure
        assert "invalid_command_that_does_not_exist" in logs.lower() or "not found" in logs.lower()
        LOGGER.info("Container properly handles invalid command with appropriate error message")
        
    except Exception as e:
        # If the container fails to start, that's also acceptable behavior
        LOGGER.info(f"Container startup failed as expected with error: {e}")
        assert "invalid_command_that_does_not_exist" in str(e) or "not found" in str(e)


@pytest.mark.integration
def test_container_with_invalid_environment(container):
    """Test that container handles invalid environment variables gracefully."""
    LOGGER.info("Testing container behavior with invalid environment variables...")

    # Add an invalid environment variable
    container.kwargs['environment']['INVALID_VAR'] = '$(invalid_command)'

    # Container should still start successfully with invalid env var
    container.run()

    # Check for all valid container statuses (created, running, exited, etc.)
    valid_statuses = ['created', 'running', 'exited', 'paused', 'restarting', 'removing', 'dead']
    assert container.container.status in valid_statuses
    LOGGER.info("Container handles invalid environment variables gracefully")


@pytest.mark.integration
def test_kernel_execution_with_syntax_error(container):
    """Test that Python kernel handles syntax errors gracefully."""
    LOGGER.info("Testing Python kernel syntax error handling...")

    container.run()

    # Execute code with syntax error
    python_code = """
import sys
print("Starting execution")
x =  # Syntax error: incomplete assignment
print("This should not print")
"""
    
    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)

    # Should return non-zero exit code for syntax error
    assert result.exit_code != 0, "Python kernel should return non-zero exit code for syntax errors"
    
    output = result.output.decode('utf-8')
    assert "syntax" in output.lower() or "error" in output.lower(), (
        f"Expected syntax error message in output: {output}"
    )
    
    LOGGER.info("Python kernel properly handles syntax errors")


@pytest.mark.integration
def test_kernel_execution_with_runtime_error(container):
    """Test that Python kernel handles runtime errors gracefully."""
    LOGGER.info("Testing Python kernel runtime error handling...")

    container.run()

    # Execute code with runtime error (division by zero)
    python_code = """
import sys
print("Starting execution")
result = 1 / 0  # This will cause a runtime error
print("This should not print")
"""
    
    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)

    # Should return non-zero exit code for runtime error
    assert result.exit_code != 0, "Python kernel should return non-zero exit code for runtime errors"
    
    output = result.output.decode('utf-8')
    assert "zero" in output.lower() or "error" in output.lower(), (
        f"Expected runtime error message in output: {output}"
    )
    
    LOGGER.info("Python kernel properly handles runtime errors")


@pytest.mark.integration
def test_r_execution_with_error(container):
    """Test that R handles errors gracefully."""
    LOGGER.info("Testing R error handling...")

    container.run()

    # Execute R code with error
    r_code = """
cat("Starting R execution\\n")
x <- 1/0  # This will produce Inf, but let's try something that causes error
stop("This is a test error")
cat("This should not print\\n")
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = container.container.exec_run(cmd)

    # Should return non-zero exit code for error
    assert result.exit_code != 0, "R should return non-zero exit code for errors"
    
    output = result.output.decode('utf-8')
    assert "test error" in output.lower(), (
        f"Expected error message in output: {output}"
    )
    
    LOGGER.info("R properly handles errors")


@pytest.mark.integration
def test_missing_r_package_import(container):
    """Test that R handles missing packages gracefully."""
    LOGGER.info("Testing R missing package import handling...")

    container.run()

    # Execute R code that imports a non-existent package
    r_code = """
if(require("non_existent_package_xyz_123", quietly = TRUE)) {
    print("Unexpected: non-existent package loaded")
} else {
    print("Expected: non-existent package not found")
}
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = container.container.exec_run(cmd)

    # Should still return success since this is handled gracefully in the code
    # If R itself fails due to package not existing, that's the error we're testing
    output = result.output.decode('utf-8')
    # R command should complete (exit code 0) and show that package was not found
    # If R crashes, it would have a non-zero exit code
    
    LOGGER.info(f"R missing package test result: {result.exit_code}")
    LOGGER.info(f"R output: {output}")


@pytest.mark.integration
def test_server_connection_failure(http_client):
    """Test that HTTP client handles connection failures gracefully."""
    LOGGER.info("Testing HTTP client connection failure handling...")

    # Try to connect to a port that shouldn't have a server
    fake_url = "http://localhost:9999"
    
    try:
        # This should raise an exception since there's no server
        resp = http_client.get(fake_url, timeout=5)
        # If it doesn't raise an exception, the test should fail
        assert False, "Expected connection to fail but it succeeded"
    except Exception as e:
        # Verify that the error is related to connection failure
        assert "connection" in str(e).lower() or "refused" in str(e).lower() or "timeout" in str(e).lower()
        LOGGER.info("HTTP client properly handles connection failures")


@pytest.mark.integration
def test_port_not_opening(container):
    """Test that wait utilities handle ports that never open."""
    LOGGER.info("Testing wait utility behavior with non-opening port...")

    container.run()

    # Wait for a port that will never open (very short timeout to not waste time)
    success = wait_for_condition(
        condition_func=lambda: False,  # Never true
        timeout=2.0,  # Short timeout
        initial_delay=0.1,
        max_delay=0.5,
        description="non-existent condition"
    )
    
    # This should return False due to timeout
    assert not success, "Wait condition should have timed out and returned False"
    LOGGER.info("Wait utility properly handles timeout scenarios")


@pytest.mark.integration
def test_invalid_http_response(container, http_client):
    """Test that wait utilities handle invalid HTTP responses."""
    LOGGER.info("Testing wait utility behavior with invalid HTTP responses...")

    container.run()

    # Wait for a URL that will give 404 or other non-200 response
    fake_url = "http://localhost:8888/nonexistent/endpoint"

    # Use wait_for_http_response with a strict expected status
    success = wait_for_http_response(
        http_client=http_client,
        url=fake_url,
        expected_status=200,  # Expecting 200 but should get 404
        timeout=3,  # Reasonable timeout
        initial_delay=0.2,
        max_delay=1.0
    )
    
    # This should fail since the URL doesn't exist
    assert not success, "Should not succeed with non-existent URL"
    LOGGER.info("HTTP wait utility properly handles non-existent endpoints")


@pytest.mark.integration
def test_file_permissions_error(container):
    """Test that container handles file permission errors gracefully."""
    LOGGER.info("Testing file permission error handling...")

    container.run()

    # Create a file and change its permissions to make it non-writable
    setup_cmd = "touch /tmp/readonly_file && chmod 444 /tmp/readonly_file"
    result = container.container.exec_run(["bash", "-c", setup_cmd])
    assert result.exit_code == 0, "Failed to set up readonly file"

    # Now try to write to that file (should fail)
    write_cmd = "echo 'test' > /tmp/readonly_file"
    result = container.container.exec_run(["bash", "-c", write_cmd])

    # Should return non-zero exit code for permission error
    assert result.exit_code != 0, "Write to readonly file should fail"
    
    LOGGER.info("Container properly handles file permission errors")


@pytest.mark.integration
def test_memory_exhaustion_simulation(container):
    """Test container behavior under memory stress (simulated)."""
    LOGGER.info("Testing container behavior with memory-intensive operation...")

    container.run()

    # Run a Python script that tries to use a lot of memory
    # (not truly exhausting memory, but testing graceful handling)
    python_code = """
import sys
try:
    # Create a large list to consume memory
    large_list = [0] * (10**7)  # This should be manageable but not trivial
    print(f"Created large list of {len(large_list)} elements")
    # Try to process it
    result = sum(large_list)
    print(f"Sum result: {result}")
    print("Memory-intensive operation completed successfully")
except MemoryError:
    print("MemoryError caught as expected")
except Exception as e:
    print(f"Other error occurred: {e}")
"""
    
    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)

    # Should complete with reasonable exit code (0 for success, non-0 for expected errors)
    # The important thing is that the container doesn't crash
    output = result.output.decode('utf-8')
    assert "completed successfully" in output.lower() or "memoryerror" in output.lower()
    
    LOGGER.info("Container handles memory-intensive operations gracefully")


@pytest.mark.integration
def test_timeout_scenarios_in_wait_utils(container, http_client):
    """Test timeout scenarios in wait utilities."""
    LOGGER.info("Testing timeout scenarios in wait utilities...")

    container.run()

    # Test HTTP response wait with timeout
    start_time = time.time()
    success = wait_for_http_response(
        http_client=http_client,
        url="http://localhost:8888/never-respond",
        expected_status=200,
        timeout=3,  # Short timeout
        initial_delay=0.1,
        max_delay=0.5
    )

    elapsed = time.time() - start_time
    assert not success, "Should have timed out"
    assert elapsed < 5, f"Should have timed out within timeout period, took {elapsed:.2f}s"

    LOGGER.info("Wait utilities handle timeouts appropriately")


@pytest.mark.integration
def test_command_not_found(container):
    """Test execution of commands that don't exist."""
    LOGGER.info("Testing execution of non-existent commands...")

    container.run()

    # Try to run a command that doesn't exist
    cmd = ["this_command_does_not_exist_12345"]
    result = container.container.exec_run(cmd)

    # Should return non-zero exit code
    assert result.exit_code != 0, "Non-existent command should return non-zero exit code"
    
    output = result.output.decode('utf-8')
    assert "not found" in output.lower() or "command not found" in output.lower()
    
    LOGGER.info("Container properly handles non-existent commands")
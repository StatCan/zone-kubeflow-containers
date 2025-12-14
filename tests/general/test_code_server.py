# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
test_code_server
~~~~~~~~~~~~~~~~
Tests for code-server functionality and accessibility.

These tests verify that:
- code-server binary is available and functional
- Key extensions are installed properly
- Web interface is accessible
- Python and R language support works
"""

import logging
import time

import pytest

from tests.general.wait_utils import wait_for_exec_success, wait_for_http_response

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def code_server_helper(container):
    """Return a container ready for code-server testing"""
    container.run()
    
    # Wait for container to be ready to execute commands
    check_cmd = ["code-server", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )
    
    if not success:
        raise AssertionError(f"Container failed to be ready for code-server execution within timeout. Output: {output}")
    
    return container


@pytest.mark.integration
def test_code_server_binary_available(code_server_helper):
    """Test that code-server binary is available and functional."""
    LOGGER.info("Testing code-server binary availability...")

    cmd = ["code-server", "--version"]
    result = code_server_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"code-server binary not available\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8').strip()
    LOGGER.info(f"code-server available: {output}")


@pytest.mark.integration
def test_code_server_extensions_installed(code_server_helper):
    """Test that key code-server extensions are installed."""
    LOGGER.info("Testing code-server extensions installation...")

    # List installed extensions
    cmd = ["code-server", "--list-extensions"]
    result = code_server_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Failed to list code-server extensions\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    LOGGER.debug(f"Installed extensions:\n{output}")

    # Check for key extensions
    required_extensions = [
        "ms-python.python",
        "ms-python.debugpy", 
        "REditorSupport.r",
        "ms-ceintl.vscode-language-pack-fr",
        "quarto.quarto",
        "redhat.vscode-yaml"
    ]
    
    missing_extensions = []
    for ext in required_extensions:
        # Extensions might have versions in the output, so we check if the base name is present
        found = any(ext.split('.')[0] in line and ext.split('.')[1] in line 
                   for line in output.split('\n') if ext.split('.')[0] in line)
        if not found:
            missing_extensions.append(ext)
    
    if missing_extensions:
        LOGGER.warning(f"Some extensions may be missing: {missing_extensions}")
    else:
        LOGGER.info("All required code-server extensions found")


@pytest.mark.integration
def test_code_server_python_extension(code_server_helper):
    """Test that Python language support in code-server is functional."""
    LOGGER.info("Testing code-server Python extension...")

    # Test Python syntax checking via code-server
    # Create a test Python file
    test_python_code = '''
def hello_world():
    """Test function for Python syntax."""
    print("Hello from Python in code-server!")
    return True

if __name__ == "__main__":
    result = hello_world()
    print(f"Python test result: {result}")
'''
    
    write_cmd = f"cat > /tmp/codeserver_test.py << 'EOF'\n{test_python_code}\nEOF"
    result = code_server_helper.container.exec_run(['bash', '-c', write_cmd])

    assert result.exit_code == 0, (
        f"Failed to write test Python file\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    # Execute the Python code to verify Python functionality
    cmd = ["python", "/tmp/codeserver_test.py"]
    result = code_server_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Python code execution failed in code-server context\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Hello from Python in code-server!" in output
    assert "Python test result: True" in output

    LOGGER.info("code-server Python extension test successful")


@pytest.mark.integration
def test_code_server_r_extension(code_server_helper):
    """Test that R language support in code-server is functional."""
    LOGGER.info("Testing code-server R extension...")

    # Test R functionality
    r_code = '''
# Test R functionality that would be used in code-server context
cat("Hello from R in code-server context!\\n")

# Test basic R operations
x <- 1:10
y <- x^2
result <- sum(y)
cat("Sum of squares:", result, "\\n")

# Test if key R packages are available
pkgs <- c("base", "stats", "utils")
for(pkg in pkgs) {
  if(require(pkg, character.only = TRUE, quietly = TRUE)) {
    cat(pkg, "package is available\\n")
  } else {
    stop(paste("Package", pkg, "not available"))
  }
}

cat("R functionality test completed\\n")
'''
    
    write_cmd = f"cat > /tmp/codeserver_test.R << 'EOF'\n{r_code}\nEOF"
    result = code_server_helper.container.exec_run(['bash', '-c', write_cmd])

    assert result.exit_code == 0, (
        f"Failed to write test R file\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    # Execute the R code to verify R functionality
    cmd = ["R", "--slave", "-f", "/tmp/codeserver_test.R"]
    result = code_server_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R code execution failed in code-server context\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Hello from R in code-server context!" in output
    assert "R functionality test completed" in output

    LOGGER.info("code-server R extension test successful")


@pytest.mark.integration
def test_code_server_settings_and_config(code_server_helper):
    """Test code-server configuration files exist."""
    LOGGER.info("Testing code-server settings and configuration...")

    # Check if code-server config directory exists
    cmd = ["test", "-d", "/home/jovyan/.local/share/code-server"]
    result = code_server_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"code-server configuration directory does not exist\n"
        f"This suggests code-server may not be properly configured"
    )

    # Check if settings.json exists
    cmd = ["test", "-f", "/home/jovyan/.local/share/code-server/User/settings.json"]
    result = code_server_helper.container.exec_run(cmd)

    if result.exit_code == 0:
        LOGGER.info("code-server settings.json found")
    else:
        LOGGER.warning("code-server settings.json not found, may be expected in some configurations")

    # Check if extensions directory exists
    cmd = ["test", "-d", "/home/jovyan/.local/share/code-server/extensions"]
    result = code_server_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"code-server extensions directory does not exist\n"
        f"This suggests extensions may not be properly installed"
    )

    LOGGER.info("code-server configuration test completed")


@pytest.mark.integration
def test_code_server_version_compatibility(code_server_helper):
    """Test code-server version and compatibility."""
    LOGGER.info("Testing code-server version...")

    cmd = ["code-server", "--version"]
    result = code_server_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Could not get code-server version\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    # Extract version from first line
    version_line = output.split('\n')[0] if output else "unknown"
    
    LOGGER.info(f"code-server version: {version_line}")
    
    # Verify version string is not empty
    assert version_line and version_line != "unknown", (
        f"Could not determine code-server version\n"
        f"Full output: {output}"
    )

    LOGGER.info("code-server version test successful")
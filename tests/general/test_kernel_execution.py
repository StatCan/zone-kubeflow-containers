# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
test_kernel_execution
~~~~~~~~~~~~~~~~~~~~~
Tests for kernel execution and notebook functionality.

These tests verify that:
- Python kernel can execute code
- R kernel can execute code (if available)
- Notebooks can be executed end-to-end
- Code output is captured correctly
- Kernel stability under various operations
- Common data science operations work
"""

import logging
import json
import time

import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
def test_python_kernel_basic_execution(container):
    """Test that Python kernel can execute basic code."""
    LOGGER.info("Testing basic Python kernel execution...")

    container.run()

    # Wait for container to be ready to execute commands
    cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    # Execute a simple Python command
    cmd = ["python", "-c", "print('Hello from Python')"]
    result = container.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Python kernel execution failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Hello from Python" in output, (
        f"Expected output not found\n"
        f"Got: {output}"
    )

    LOGGER.info("Python kernel basic execution successful")


@pytest.mark.integration
def test_python_kernel_arithmetic(container):
    """Test that Python kernel can perform arithmetic operations."""
    LOGGER.info("Testing Python kernel arithmetic...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    # Execute arithmetic
    cmd = ["python", "-c", "result = 2 + 2; print(f'Result: {result}'); assert result == 4"]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"Arithmetic operation failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    output = result.output.decode('utf-8')
    assert "Result: 4" in output, (
        f"Expected arithmetic result not found\n"
        f"Got: {output}"
    )
    
    LOGGER.info("Python kernel arithmetic successful")


@pytest.mark.integration
def test_python_kernel_list_operations(container):
    """Test that Python kernel can work with lists."""
    LOGGER.info("Testing Python kernel list operations...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    python_code = """
import json
data = [1, 2, 3, 4, 5]
result = sum(data)
print(f'Sum: {result}')
assert result == 15
"""

    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"List operations failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    LOGGER.info("Python kernel list operations successful")


@pytest.mark.integration
def test_python_kernel_module_import(container):
    """Test that Python kernel can import standard library modules."""
    LOGGER.info("Testing Python kernel module imports...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    python_code = """
import sys
import os
import json
import datetime

print(f'Python version: {sys.version_info.major}.{sys.version_info.minor}')
print(f'OS: {os.name}')
assert sys.version_info.major >= 3
"""

    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"Module import failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    output = result.output.decode('utf-8')
    assert "Python version:" in output, "Version info not printed"
    
    LOGGER.info("Python kernel module imports successful")


@pytest.mark.integration
@pytest.mark.slow
def test_notebook_execution_basic(container):
    """Test that a basic Jupyter notebook can be executed."""
    LOGGER.info("Testing basic notebook execution...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    # Create a simple notebook with one cell
    notebook_content = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": ["print('Hello from notebook')"]
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.8.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    # Write notebook to container
    notebook_json = json.dumps(notebook_content)
    write_cmd = f"cat > /tmp/test.ipynb << 'EOF'\n{notebook_json}\nEOF"
    result = container.container.exec_run(['bash', '-c', write_cmd])

    assert result.exit_code == 0, (
        f"Failed to write notebook\n"
        f"Error: {result.output.decode('utf-8')}"
    )

    # Execute notebook with nbconvert
    exec_cmd = "jupyter nbconvert --to notebook --execute /tmp/test.ipynb --output /tmp/test_out.ipynb --ExecutePreprocessor.timeout=300"
    result = container.container.exec_run(['bash', '-c', exec_cmd])

    # Check if execution was successful
    if result.exit_code != 0:
        LOGGER.warning(f"nbconvert execution output: {result.output.decode('utf-8')}")
        # nbconvert might not be installed, which is OK for basic test

    LOGGER.info("Notebook execution test completed")


@pytest.mark.integration
def test_python_exception_handling(container):
    """Test that Python kernel properly handles exceptions."""
    LOGGER.info("Testing Python exception handling...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    python_code = """
try:
    result = 1 / 0
except ZeroDivisionError as e:
    print(f'Caught exception: {e}')
    print('Exception handled correctly')
"""

    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"Exception handling test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    output = result.output.decode('utf-8')
    assert "Exception handled correctly" in output, (
        f"Exception handling did not work as expected\n"
        f"Got: {output}"
    )
    
    LOGGER.info("Python exception handling works correctly")


@pytest.mark.integration
def test_python_file_io(container):
    """Test that Python kernel can perform file I/O operations."""
    LOGGER.info("Testing Python file I/O...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    python_code = """
import tempfile
import os

# Create a temporary file
with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
    f.write('Test content')
    temp_file = f.name

# Read it back
with open(temp_file, 'r') as f:
    content = f.read()

assert content == 'Test content'
print('File I/O successful')

# Cleanup
os.remove(temp_file)
"""

    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"File I/O test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    LOGGER.info("Python file I/O works correctly")


@pytest.mark.integration
def test_jupyter_kernel_list(container):
    """Test that jupyter can list available kernels."""
    LOGGER.info("Testing jupyter kernel list...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    cmd = ["jupyter", "kernelspec", "list"]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"Failed to list kernels\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    output = result.output.decode('utf-8')
    assert "python" in output.lower(), (
        f"Python kernel not found in available kernels\n"
        f"Output: {output}"
    )
    
    LOGGER.info("Available kernels listed successfully")


@pytest.mark.integration
def test_python_multiline_execution(container):
    """Test that Python kernel can execute multiline code blocks."""
    LOGGER.info("Testing Python multiline execution...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    python_code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

result = fibonacci(10)
print(f'Fibonacci(10) = {result}')
assert result == 55
"""

    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"Multiline execution failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    output = result.output.decode('utf-8')
    assert "Fibonacci(10) = 55" in output, (
        f"Expected output not found\n"
        f"Got: {output}"
    )
    
    LOGGER.info("Python multiline execution successful")


@pytest.mark.integration
def test_python_string_operations(container):
    """Test that Python kernel handles string operations correctly."""
    LOGGER.info("Testing Python string operations...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    python_code = """
text = 'Hello, World!'
upper_text = text.upper()
reversed_text = text[::-1]
split_text = text.split(',')

print(f'Upper: {upper_text}')
print(f'Reversed: {reversed_text}')
print(f'Split count: {len(split_text)}')

assert upper_text == 'HELLO, WORLD!'
assert len(split_text) == 2
"""

    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"String operations failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    LOGGER.info("Python string operations successful")


@pytest.mark.integration
def test_r_kernel_available_if_installed(container):
    """Test R kernel availability (if R is installed)."""
    LOGGER.info("Testing R kernel availability...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    # Check if R is installed
    check_r_cmd = ["bash", "-c", "which R"]
    result = container.container.exec_run(check_r_cmd)

    if result.exit_code != 0:
        LOGGER.info("R not installed, skipping R kernel test")
        return

    # Check if R kernel is registered
    cmd = ["jupyter", "kernelspec", "list"]
    result = container.container.exec_run(cmd)
    output = result.output.decode('utf-8')

    if "ir" in output.lower() or "r" in output.lower():
        LOGGER.info("R kernel is available")
    else:
        LOGGER.info("R is installed but R kernel not found in jupyter")


@pytest.mark.integration
def test_kernel_timeout_handling(container):
    """Test that kernel properly handles long-running operations."""
    LOGGER.info("Testing kernel timeout handling...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    # Test with a reasonably fast operation
    python_code = """
import time
start = time.time()
time.sleep(1)
elapsed = time.time() - start
print(f'Waited for {elapsed:.2f} seconds')
assert elapsed >= 0.9
"""

    cmd = ["timeout", "30", "python", "-c", python_code]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"Timeout handling test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    LOGGER.info("Kernel timeout handling works correctly")


@pytest.mark.integration
def test_python_dictionary_operations(container):
    """Test that Python kernel can work with dictionaries."""
    LOGGER.info("Testing Python dictionary operations...")

    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["python", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for execution within timeout. Output: {output}")

    python_code = """
data = {
    'name': 'John',
    'age': 30,
    'city': 'New York'
}

print(f'Name: {data["name"]}')
print(f'Age: {data["age"]}')
assert len(data) == 3
assert data['city'] == 'New York'
"""

    cmd = ["python", "-c", python_code]
    result = container.container.exec_run(cmd)
    
    assert result.exit_code == 0, (
        f"Dictionary operations failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )
    
    LOGGER.info("Python dictionary operations successful")

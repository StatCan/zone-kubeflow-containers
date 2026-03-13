"""
test_python_path
~~~~~~~~~~~~~~~~
Test that Python defaults to conda Python (/opt/conda/bin/python)
"""

import logging
import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
def test_python_path_priority(container):
    """Test that python command resolves to conda Python by default"""
    LOGGER.info("Testing Python path priority...")

    # Start the container
    container.run(
        tty=True,
        command=['start.sh', 'bash', '-c', 'sleep infinity']
    )

    # Test 1: Check which python is used by default
    result = container.container.exec_run(["which", "python"])
    if result.exit_code == 0:
        python_path = result.output.decode("utf-8").strip()
        LOGGER.info(f"'which python' returns: {python_path}")
        # Should prefer conda python
        assert "/opt/conda/bin/python" in python_path or python_path == "/opt/conda/bin/python", \
            f"Expected /opt/conda/bin/python, got: {python_path}"

    # Test 2: Check which python3 is used by default
    result = container.container.exec_run(["which", "python3"])
    if result.exit_code == 0:
        python3_path = result.output.decode("utf-8").strip()
        LOGGER.info(f"'which python3' returns: {python3_path}")
        # Should prefer conda python3
        assert "/opt/conda/bin/python3" in python3_path or python3_path == "/opt/conda/bin/python3", \
            f"Expected /opt/conda/bin/python3, got: {python3_path}"

    # Test 3: Check Python executable path from within Python
    result = container.container.exec_run([
        "python", "-c", "import sys; print(sys.executable)"
    ])
    if result.exit_code == 0:
        sys_executable = result.output.decode("utf-8").strip()
        LOGGER.info(f"sys.executable returns: {sys_executable}")
        assert "/opt/conda/bin/python" in sys_executable or sys_executable == "/opt/conda/bin/python", \
            f"Expected /opt/conda/bin/python, got: {sys_executable}"

    # Test 4: Check PATH environment variable has conda first
    result = container.container.exec_run(["bash", "-c", "echo $PATH"])
    if result.exit_code == 0:
        path_env = result.output.decode("utf-8").strip()
        LOGGER.info(f"PATH environment: {path_env}")
        # /opt/conda/bin should appear before /usr/bin in PATH
        conda_pos = path_env.find("/opt/conda/bin")
        usr_bin_pos = path_env.find("/usr/bin")
        if conda_pos != -1 and usr_bin_pos != -1:
            assert conda_pos < usr_bin_pos, \
                f"/opt/conda/bin should come before /usr/bin in PATH. PATH={path_env}"

    LOGGER.info("Python path priority test passed successfully")


@pytest.mark.integration
def test_python_imports_work(container):
    """Test that basic Python imports work correctly"""
    LOGGER.info("Testing Python imports...")

    # Start the container
    container.run(
        tty=True,
        command=['start.sh', 'bash', '-c', 'sleep infinity']
    )

    # Test basic import
    result = container.container.exec_run([
        "python", "-c", "import sys; print('Python', sys.version)"
    ])
    assert result.exit_code == 0, f"Python import failed: {result.output.decode('utf-8')}"

    # Test conda-specific packages
    result = container.container.exec_run([
        "python", "-c", "import conda; print('Conda version:', conda.__version__)"
    ])
    # This may fail if conda package is not installed, which is ok
    if result.exit_code != 0:
        LOGGER.warning("Conda package not available for import test")
    else:
        LOGGER.info(f"Conda import successful: {result.output.decode('utf-8')}")

    LOGGER.info("Python imports test passed successfully")

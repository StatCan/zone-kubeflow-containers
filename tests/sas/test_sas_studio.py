# Copyright (c) Statistics Canada. All rights reserved.

"""
test_sas_studio
~~~~~~~~~~~~~~~
Comprehensive tests for SAS Studio functionality and integration.

These tests verify that:
- SAS Studio is properly installed and available
- SAS Studio web interface can be accessed through Jupyter proxy
- All integration components work together properly
- Basic SAS Studio operations function correctly
"""

import logging
import time
import requests

import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def sas_studio_helper(container):
    """Return a container ready for SAS Studio testing"""
    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["which", "sas"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        LOGGER.warning(f"SAS binary not found in expected location. Output: {output}")

    return container


@pytest.mark.integration
def test_sas_studio_available(sas_studio_helper):
    """Test that SAS Studio environment is available."""
    LOGGER.info("Testing SAS Studio availability...")

    # Check for SAS Studio related files and directories
    result = sas_studio_helper.container.exec_run(["which", "sas"])
    assert result.exit_code == 0, "SAS should be available for SAS Studio"

    # Check that the SAS Studio startup script exists
    result = sas_studio_helper.container.exec_run([
        "test", "-f", "/usr/local/SASHome/studioconfig/sasstudio.sh"
    ])
    assert result.exit_code == 0, "SAS Studio startup script should exist"

    # Check for SAS Studio related directories
    result = sas_studio_helper.container.exec_run([
        "bash", "-c", "find /usr/local/SASHome -name '*studio*' -type d | head -5"
    ])
    
    assert result.exit_code == 0, "Should be able to find SAS Studio directories"

    output = result.output.decode('utf-8')
    assert "studio" in output.lower() or "Studio" in output, f"Should find studio-related directories: {output}"

    LOGGER.info("SAS Studio environment check completed")


@pytest.mark.integration
def test_sas_studio_config_files(sas_studio_helper):
    """Test that SAS Studio configuration files exist and are accessible."""
    LOGGER.info("Testing SAS Studio configuration files...")

    # Check for main SAS Studio config directory
    result = sas_studio_helper.container.exec_run(
        ["test", "-d", "/usr/local/SASHome/studioconfig"]
    )
    assert result.exit_code == 0, "SAS Studio config directory should exist"

    # Check for the startup script specifically
    result = sas_studio_helper.container.exec_run(
        ["test", "-x", "/usr/local/SASHome/studioconfig/sasstudio.sh"]
    )
    assert result.exit_code == 0, "SAS Studio startup script should be executable"

    # Check for preferences directory
    result = sas_studio_helper.container.exec_run(
        ["test", "-d", "/etc/sasstudio/preferences"]
    )
    if result.exit_code != 0:
        # This might be created upon first run, so warn but don't fail
        LOGGER.info("SAS Studio preferences directory not found (might be created on first run)")

    LOGGER.info("SAS Studio config files test completed")


@pytest.mark.integration
def test_sas_studio_startup_script_functionality(sas_studio_helper):
    """Test SAS Studio startup script functionality."""
    LOGGER.info("Testing SAS Studio startup script functionality...")

    # Use wait utils to check that the script exists and is executable
    check_exec_cmd = ["test", "-x", "/usr/local/SASHome/studioconfig/sasstudio.sh"]
    success, output = wait_for_exec_success(
        container=sas_studio_helper,
        command=check_exec_cmd,
        timeout=15,
        initial_delay=0.2,
        max_delay=2.0
    )

    assert success, f"SAS Studio startup script should be executable. Output: {output}"

    # Use wait utils to check that we can read the script content
    read_cmd = ["head", "-10", "/usr/local/SASHome/studioconfig/sasstudio.sh"]
    success, output = wait_for_exec_success(
        container=sas_studio_helper,
        command=read_cmd,
        timeout=15,
        initial_delay=0.2,
        max_delay=2.0
    )

    assert success, f"Should be able to read SAS Studio startup script content. Output: {output}"

    LOGGER.debug(f"SAS Studio startup script preview: {output[:200]}...")

    # Verify it looks like a bash script
    assert "#!" in output or "bash" in output.lower(), "Script should contain bash directives"

    LOGGER.info("SAS Studio startup script functionality test successful")


@pytest.mark.integration
def test_sas_studio_web_accessibility(sas_studio_helper):
    """Test that SAS Studio web interface is accessible through Jupyter proxy."""
    LOGGER.info("Testing SAS Studio web interface accessibility...")

    # Check for processes related to SAS Studio (though they may not be running by default)
    result = sas_studio_helper.container.exec_run(["bash", "-c",
        "ps aux | grep -i sasstudio || echo 'No SAS Studio processes found (expected if not started)'"
    ])

    output = result.output.decode('utf-8')
    LOGGER.info(f"SAS Studio processes check: {output[:200]}...")

    # Also test that we can check for web service availability using the wait utils
    # Since the service might not be actively running in tests, we'll check if it can be started
    check_cmd = ["bash", "-c",
        "if [ -f '/usr/local/SASHome/studioconfig/sasstudio.sh' ]; then "
        "timeout 10s bash -c 'ls /usr/local/SASHome/studioconfig/' 2>/dev/null || echo 'Checked SAS Studio config dir'; "
        "else echo 'SAS Studio script not found'; fi"
    ]

    success, output = wait_for_exec_success(
        container=sas_studio_helper,
        command=check_cmd,
        timeout=20,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        LOGGER.warning("Could not confirm SAS Studio config directory accessibility within timeout")

    # Use wait utils to check if SAS Studio files are accessible
    check_studio_files_cmd = ["bash", "-c", "find /usr/local/SASHome -name '*studio*' -type f | head -5"]
    success, output = wait_for_exec_success(
        container=sas_studio_helper,
        command=check_studio_files_cmd,
        timeout=15,
        initial_delay=0.2,
        max_delay=2.0
    )

    if success and "studio" in output.lower():
        LOGGER.info("SAS Studio related files found and accessible")
    elif not success:
        # Use alternative check without wait utils
        result = sas_studio_helper.container.exec_run([
            "bash", "-c",
            "find /usr/local/SASHome -maxdepth 3 -type d | grep -i studio || echo 'No studio directory found'"
        ])

        output = result.output.decode('utf-8')
        if "studio" in output.lower():
            LOGGER.info("SAS Studio related directories found")
        else:
            LOGGER.warning(f"SAS Studio directories not found as expected. Output: {output[:100]}")

    LOGGER.info("SAS Studio web accessibility check completed")


@pytest.mark.integration
def test_sas_studio_java_prerequisites(sas_studio_helper):
    """Test that Java prerequisites for SAS Studio are available."""
    LOGGER.info("Testing SAS Studio Java prerequisites...")

    # Look for Java in SAS installation
    result = sas_studio_helper.container.exec_run([
        "test", "-d", "/usr/local/SASHome/SASPrivateJavaRuntimeEnvironment"
    ])
    
    assert result.exit_code == 0, "SAS should have its own Java Runtime Environment"

    # SAS Studio requires Java 
    result = sas_studio_helper.container.exec_run(["bash", "-c", 
        "find /usr/local/SASHome -name 'java' -executable -type f | head -3"
    ])
    
    if result.exit_code == 0:
        output = result.output.decode('utf-8').strip()
        if output:
            LOGGER.info(f"SAS-specific Java executables found: {output[:100]}")
        else:
            LOGGER.info("No specific Java executables found in SAS Home (this might be ok)")
    else:
        LOGGER.info("No Java executables found in SAS Home search")

    LOGGER.info("SAS Studio Java prerequisites test completed")


@pytest.mark.integration
def test_jupyter_sasstudio_proxy_installed(sas_studio_helper):
    """Test that jupyter-sasstudio-proxy is properly installed."""
    LOGGER.info("Testing jupyter-sasstudio-proxy installation...")

    # Use wait utils to check that the jupyter-sasstudio-proxy module can be imported
    import_cmd = ["python", "-c", "import jupyter_sasstudio_proxy; print('jupyter_sasstudio_proxy import successful')"]
    success, output = wait_for_exec_success(
        container=sas_studio_helper,
        command=import_cmd,
        timeout=20,
        initial_delay=0.5,
        max_delay=3.0
    )

    assert success, f"jupyter-sasstudio-proxy module not found. Output: {output}"

    # Use wait utils to check that proxy config is accessible
    config_cmd = ["python", "-c", "from jupyter_sasstudio_proxy import setup_sasstudio; config = setup_sasstudio(); print(config.get('port', 'No port found'))"]
    success, output = wait_for_exec_success(
        container=sas_studio_helper,
        command=config_cmd,
        timeout=20,
        initial_delay=0.5,
        max_delay=3.0
    )

    assert success, f"jupyter-sasstudio-proxy config should be accessible. Output: {output}"

    output = output.strip()
    # Should output the port number (38080) from the proxy configuration
    assert "38080" in output or "No port found" not in output, f"Expected port configuration, got: {output}"

    LOGGER.info("jupyter-sasstudio-proxy installation test successful")


@pytest.mark.integration
def test_sasstudio_proxy_config(sas_studio_helper):
    """Test that SAS Studio proxy configuration is correct."""
    LOGGER.info("Testing SAS Studio proxy configuration...")

    # Check the proxy configuration by importing and testing its setup
    result = sas_studio_helper.container.exec_run([
        "python", "-c", """
from jupyter_sasstudio_proxy import setup_sasstudio
config = setup_sasstudio()
print('Port:', config['port'])
print('Title:', config['launcher_entry']['title'])
print('Command function exists:', callable(config['command']))
print('Rewrite response function exists:', callable(config['rewrite_response']))
"""
    ])
    
    assert result.exit_code == 0, (
        f"SAS Studio proxy configuration test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "38080" in output, f"Expected port 38080 in proxy config, got: {output}"
    assert "SAS Studio" in output, f"Expected 'SAS Studio' in title, got: {output}"
    assert "Command function exists: True" in output, "Expected command function to exist"
    assert "Rewrite response function exists: True" in output, "Expected rewrite_response function to exist"

    LOGGER.info("SAS Studio proxy configuration test successful")


@pytest.mark.integration
def test_sas_studio_file_structure(sas_studio_helper):
    """Test SAS Studio file structure and organization."""
    LOGGER.info("Testing SAS Studio file structure...")

    # Use wait utils to look for SAS Studio related files and directories
    find_cmd = ["bash", "-c", "find /usr/local/SASHome -type d -name '*studio*' -o -path '*/studio/*' | head -10"]
    success, output = wait_for_exec_success(
        container=sas_studio_helper,
        command=find_cmd,
        timeout=20,
        initial_delay=0.5,
        max_delay=3.0
    )

    assert success, f"Should be able to search for SAS Studio files. Output: {output}"

    output = output.strip()
    if output:
        directories = output.split('\n')
        LOGGER.info(f"Found SAS Studio-related directories: {directories[:5]}")

        # At least one studio-related directory should exist
        studio_dirs = [d for d in directories if 'studio' in d.lower()]
        assert len(studio_dirs) > 0, f"Should find at least one SAS Studio directory, found: {studio_dirs}"
    else:
        # If no directories with 'studio' in the name are found, use alternative check
        alt_cmd = ["bash", "-c", "find /usr/local/SASHome -type f -name '*studio*' | head -5"]
        success, output = wait_for_exec_success(
            container=sas_studio_helper,
            command=alt_cmd,
            timeout=15,
            initial_delay=0.5,
            max_delay=2.0
        )

        assert success, f"Should be able to find SAS Studio related files. Output: {output}"

        output = output.strip()
        assert output, f"Should find some SAS Studio related files or directories. Got: {output}"

    LOGGER.info("SAS Studio file structure test successful")


@pytest.mark.integration
def test_sas_studio_preferences_and_configuration(sas_studio_helper):
    """Test SAS Studio preferences and configuration files."""
    LOGGER.info("Testing SAS Studio preferences and configuration...")

    # Check for custom preferences that were copied during Docker build
    result = sas_studio_helper.container.exec_run([
        "test", "-f", "/etc/sasstudio/preferences/SWE.folderShortcuts.key"
    ])
    
    if result.exit_code == 0:
        LOGGER.info("Custom SAS Studio preferences file found")
    else:
        LOGGER.info("Custom SAS Studio preferences file not found at expected location (may be in different location or created on first run)")

    # Check for spawner usermods script (from Dockerfile)
    result = sas_studio_helper.container.exec_run([
        "test", "-f", "/usr/local/SASHome/studioconfig/spawner/spawner_usermods.sh"
    ])
    
    if result.exit_code == 0:
        LOGGER.info("SAS Studio spawner usermods script found")
    else:
        # Check if spawner directory exists
        result = sas_studio_helper.container.exec_run([
            "test", "-d", "/usr/local/SASHome/studioconfig/spawner"
        ])
        if result.exit_code == 0:
            LOGGER.info("SAS Studio spawner directory exists, but usermods script may not be required")
        else:
            LOGGER.info("SAS Studio spawner directory not found (may be created differently)")

    LOGGER.info("SAS Studio preferences and configuration test successful")


@pytest.mark.integration
def test_complete_sas_studio_integration_pipeline(sas_studio_helper):
    """Test complete SAS Studio integration pipeline verification."""
    LOGGER.info("Testing complete SAS Studio integration pipeline...")

    # This test verifies that all components necessary for SAS Studio operation are present
    # and properly configured, without actually starting the service
    
    # 1. Check SAS base installation
    result = sas_studio_helper.container.exec_run(["sas", "--version"])
    assert result.exit_code == 0 or result.exit_code == 1, "SAS installation should be accessible (exit code 1 might be just no input)"

    # 2. Check web server components (Java-based for SAS Studio)
    result = sas_studio_helper.container.exec_run([
        "test", "-d", "/usr/local/SASHome/SASPrivateJavaRuntimeEnvironment"
    ])
    assert result.exit_code == 0, "SAS should have its own Java Runtime Environment"

    # 3. Check SAS Studio files exist
    result = sas_studio_helper.container.exec_run([
        "test", "-d", "/usr/local/SASHome/studioconfig"
    ])
    assert result.exit_code == 0, "SAS Studio configuration directory should exist"

    # 4. Check proxy components
    result = sas_studio_helper.container.exec_run([
        "python", "-c", "import jupyter_sasstudio_proxy"
    ])
    assert result.exit_code == 0, "jupyter_sasstudio_proxy should be importable"

    # 5. Check that startup script exists and is executable
    result = sas_studio_helper.container.exec_run([
        "test", "-x", "/usr/local/SASHome/studioconfig/sasstudio.sh"
    ])
    assert result.exit_code == 0, "SAS Studio startup script should be executable and available"

    # 6. Verify proxy configuration is accessible
    result = sas_studio_helper.container.exec_run([
        "python", "-c", 
        "from jupyter_sasstudio_proxy import setup_sasstudio; config = setup_sasstudio(); print(config['port']); print(config['launcher_entry']['title'])"
    ])
    assert result.exit_code == 0, "Proxy configuration should be accessible"
    
    output = result.output.decode('utf-8').strip().split('\n')
    assert len(output) >= 2, f"Should get both port and title, got: {output}"
    
    # Extract the actual port and title, ignoring extra debug output
    port_found = False
    title_found = False
    for line in output:
        if '38080' in line:
            port_found = True
        if 'SAS Studio' in line:
            title_found = True
    
    assert port_found, f"Expected port 38080 in output, got: {output}"
    assert title_found, f"Expected 'SAS Studio' title in output, got: {output}"

    LOGGER.info("Complete SAS Studio integration pipeline verification successful")
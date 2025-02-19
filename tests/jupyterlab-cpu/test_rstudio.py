import logging
import subprocess
import pytest

LOGGER = logging.getLogger(__name__)

@pytest.mark.parametrize("command,expected_keyword,description", [
    (
        "rstudio-server version",
        "rstudio-server",
        "Test that the rstudio-server version command outputs valid version information."
    ),
])
def test_rstudio_server_version(command, expected_keyword, description):
    """Test that rstudio-server version runs successfully and outputs the expected text."""
    LOGGER.info(description)
    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
    )
    # Assert that the command succeeded.
    assert result.returncode == 0, (
        f"Command '{command}' failed with exit code {result.returncode}. "
        f"Error output: {result.stderr}"
    )
    LOGGER.debug(result.stdout)
    # Check that the expected keyword is in the output.
    assert expected_keyword in result.stdout, (
        f"Expected keyword '{expected_keyword}' not found in output: {result.stdout}"
    )

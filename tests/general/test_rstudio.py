import logging
import pytest

LOGGER = logging.getLogger(__name__)

EXPECTED = "2024.12.0+467 (Kousa Dogwood) for Ubuntu Jammy"

def test_rstudio(container):
    """Test that RStudio server is available and responds with expected version."""
    # Skip this test if RStudio is not installed in the image
    try:
        # Start the container
        container.run()

        # Execute RStudio server version command
        result = container.container.exec_run(["rstudio-server", "version"])

        # If command is not found, skip the test
        if result.exit_code != 0 and "command not found" in result.output.decode("utf-8").lower():
            pytest.skip("RStudio server not installed in this image")

        # Check if the expected version is present
        output = result.output.decode("utf-8")
        LOGGER.info(f"RStudio version: {output}")
        assert EXPECTED in output

    except Exception as e:
        # If RStudio is not available in this image, skip the test
        if "command not found" in str(e).lower() or "no such file" in str(e).lower():
            pytest.skip("RStudio server not installed in this image")
        else:
            raise
 

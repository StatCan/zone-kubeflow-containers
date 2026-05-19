import logging
import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)

@pytest.mark.integration
def test_parquet_functionality(container):
    """Test that parquet file read/write works correctly."""
    
    The test is skipped for base images since parquet support is only
    expected in mid/jupyterlab images.
    """
    # Only run this test on images that have parquet support
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("Parquet functionality not expected in base image")
    
    LOGGER.info("Testing parquet functionality...")

    container.run()

    # Ensure container is ready for execution
    success, output = wait_for_exec_success(
        container=container,
        command=["python3", "--version"],
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )

    if not success:
        raise AssertionError(
            f"Container failed to be ready for execution within timeout. Output: {output}"
        )
    
    # Define the internal Python script
    # We use a single variable to keep the Python code clean
    test_script = (
        "import pandas as pd\n"
        "import pyarrow as pa\n"
        "import pyarrow.parquet as pq\n"
        "import tempfile\n"
        "import os\n"
        "\n"
        "df = pd.DataFrame({\n"
        "    'column1': [1, 2, 3, 4],\n"
        "    'column2': ['A', 'B', 'C', 'D'],\n"
        "    'column3': [1.1, 2.2, 3.3, 4.4]\n"
        "})\n"
        "\n"
        "with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:\n"
        "    temp_filename = tmp.name\n"
        "\n"
        "try:\n"
        "    df.to_parquet(temp_filename)\n"
        "    df_read = pd.read_parquet(temp_filename)\n"
        "    assert df.equals(df_read), 'Original and read DataFrames are not equal!'\n"
        "    table = pq.read_table(temp_filename)\n"
        "    print('SUCCESS: Parquet functionality working correctly')\n"
        "finally:\n"
        "    if os.path.exists(temp_filename): os.unlink(temp_filename)"
    )
    
    # Execute via heredoc to prevent shell quoting issues
    # cat << 'EOF' ensures that the content is treated as a literal string
    command = [
        "sh", "-c",
        f"cat << 'EOF' > /tmp/test_parquet_probe.py\n{test_script}\nEOF\npython3 /tmp/test_parquet_probe.py"
    ]
    
    result = container.container.exec_run(command)
    output = result.output.decode('utf-8')
    
    if result.exit_code != 0:
        LOGGER.error(f"Parquet functionality test failed: {output}")
        assert False, f"Parquet functionality test failed with exit code {result.exit_code}: {output}"
    
    if "SUCCESS: Parquet functionality working correctly" not in output:
        LOGGER.error(f"Unexpected output from parquet test: {output}")
        assert False, f"Parquet functionality test did not return expected success message: {output}"
    
    LOGGER.info("Parquet functionality test passed successfully")

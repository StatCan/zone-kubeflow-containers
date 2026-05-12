import logging
import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)

@pytest.mark.integration
def test_parquet_functionality(container):
    """Test that parquet file read/write works correctly."""
    
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("Parquet functionality not expected in base image")
    
    LOGGER.info("Testing parquet functionality...")

    container.run()

    # Verify container is ready
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
    
    # Define script with proper escaping or use a heredoc approach
    # We use a single string and write it to a file inside the container
    test_script_content = (
        "import pandas as pd\n"
        "import pyarrow as pa\n"
        "import pyarrow.parquet as pq\n"
        "import tempfile\n"
        "import os\n"
        "df = pd.DataFrame({\n"
        "    'col1': [1, 2, 3],\n"
        "    'col2': ['A', 'B', 'C']\n"
        "})\n"
        "with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:\n"
        "    fname = tmp.name\n"
        "try:\n"
        "    df.to_parquet(fname)\n"
        "    df_read = pd.read_parquet(fname)\n"
        "    assert df.equals(df_read), 'DF mismatch'\n"
        "    pq.read_table(fname)\n"
        "    print('SUCCESS_MARKER')\n"
        "finally:\n"
        "    if os.path.exists(fname): os.unlink(fname)"
    )

    # Use a heredoc to avoid quote escaping hell in the shell command
    command = [
        "sh", "-c",
        f"cat << 'EOF' > /tmp/test_pq.py\n{test_script_content}\nEOF\npython3 /tmp/test_pq.py"
    ]
    
    result = container.container.exec_run(command)
    output = result.output.decode('utf-8')
    
    if result.exit_code != 0:
        LOGGER.error(f"Parquet functionality test failed with exit code {result.exit_code}: {output}")
        assert False, f"Script execution failed: {output}"
    
    if "SUCCESS_MARKER" not in output:
        LOGGER.error(f"Unexpected output: {output}")
        assert False, "Parquet test finished but success marker was missing."
    
    LOGGER.info("Parquet functionality test passed successfully")

"""
test_parquet
~~~~~~~~~~~~
Test that parquet file read/write functionality works correctly.

This test verifies that the mid/jupyterlab images can:
- Create a pandas DataFrame
- Write it to a parquet file
- Read the parquet file back
- Verify data integrity after round-trip

The test uses both pandas and pyarrow directly to ensure
the underlying parquet libraries are properly configured.

Example:

    $ make test/mid

    # [...]
    # test/mid/test_parquet.py::test_parquet_functionality
    # ---------------------------------------------------------------------------------------------- live log call ----------------------------------------------------------------------------------------------
    # 2026-03-17 10:00:00 [    INFO] Testing parquet functionality... (test_parquet.py:22)
    # 2026-03-17 10:00:05 [    INFO] Parquet functionality test passed successfully (test_parquet.py:75)
"""

import logging
import pytest

LOGGER = logging.getLogger(__name__)

@pytest.mark.integration
def test_parquet_functionality(container):
    """Test that parquet file read/write works correctly.
    
    This test creates a DataFrame, writes it to parquet, reads it back,
    and verifies data integrity. It tests both pandas and pyarrow interfaces.
    
    The test is skipped for base images since parquet support is only
    expected in mid/jupyterlab images.
    """
    # Only run this test on images that have parquet support
    # After refactoring, parquet is in jupyterlab (and mid if it inherits it)
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("Parquet functionality not expected in base image")
    
    LOGGER.info("Testing parquet functionality...")
    
    # Create a simple Python script to test parquet functionality
    test_script = '''
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import tempfile
import os

# Create a simple DataFrame
df = pd.DataFrame({
    'column1': [1, 2, 3, 4],
    'column2': ['A', 'B', 'C', 'D'],
    'column3': [1.1, 2.2, 3.3, 4.4]
})

# Create a temporary file
with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
    temp_filename = tmp.name

try:
    # Write DataFrame to parquet
    df.to_parquet(temp_filename)
    
    # Read the parquet file back
    df_read = pd.read_parquet(temp_filename)
    
    # Verify the data is the same
    assert df.equals(df_read), "Original and read DataFrames are not equal!"
    
    # Test with PyArrow directly
    table = pq.read_table(temp_filename)
    
    print("SUCCESS: Parquet functionality working correctly")
    
finally:
    # Clean up the temporary file
    if os.path.exists(temp_filename):
        os.unlink(temp_filename)
'''
    
    # Write the test script to the container and execute it
    result = container.container.exec_run(["sh", "-c", f"python3 -c \"{test_script}\""])
    
    if result.exit_code != 0:
        LOGGER.error(f"Parquet functionality test failed: {result.output.decode('utf-8')}")
        assert False, f"Parquet functionality test failed: {result.output.decode('utf-8')}"
    
    output = result.output.decode('utf-8')
    if "SUCCESS: Parquet functionality working correctly" not in output:
        LOGGER.error(f"Unexpected output from parquet test: {output}")
        assert False, f"Parquet functionality test did not return expected success message: {output}"
    
    LOGGER.info("Parquet functionality test passed successfully")
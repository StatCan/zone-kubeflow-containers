"""
test_parquet
~~~~~~~~~~~~
Test that parquet functionality works in the mid image.
"""

import logging
import pytest

LOGGER = logging.getLogger(__name__)

@pytest.mark.integration
def test_parquet_functionality(container):
    """Test that parquet functionality works properly in the container."""
    # Only run this test on the mid image or images that should have parquet support
    image_name = container.image_name.lower()
    if 'base' in image_name or 'jupyterlab' in image_name:
        pytest.skip("Parquet functionality not expected in base/jupyterlab images")
    
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
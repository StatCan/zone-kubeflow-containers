#!/usr/bin/env python3
"""
Simple test script to verify parquet functionality is working
"""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import tempfile
import os

def test_parquet_functionality():
    """Test that parquet functionality is working properly"""
    print("Testing parquet functionality...")
    
    # Create a simple DataFrame
    df = pd.DataFrame({
        'column1': [1, 2, 3, 4],
        'column2': ['A', 'B', 'C', 'D'],
        'column3': [1.1, 2.2, 3.3, 4.4]
    })
    
    print("Created sample DataFrame:")
    print(df)
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
        temp_filename = tmp.name
    
    try:
        # Write DataFrame to parquet
        df.to_parquet(temp_filename)
        print(f"Successfully wrote DataFrame to {temp_filename}")
        
        # Read the parquet file back
        df_read = pd.read_parquet(temp_filename)
        print("Successfully read DataFrame from parquet:")
        print(df_read)
        
        # Verify the data is the same
        assert df.equals(df_read), "Original and read DataFrames are not equal!"
        print("✓ Data integrity verified!")
        
        # Test with PyArrow directly
        table = pq.read_table(temp_filename)
        print("Successfully read with PyArrow:")
        print(table)
        
        print("\n✓ All parquet functionality tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Parquet functionality test failed: {e}")
        return False
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)

if __name__ == "__main__":
    test_parquet_functionality()
# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
test_python_data_science
~~~~~~~~~~~~~~~~~~~~~~~~
Tests for Python data science packages functionality.

These tests verify that:
- Key Python data science packages are installed and functional
- Common data science workflows work properly
- Pandas, NumPy, Matplotlib, etc. are working correctly
"""

import logging
import json
import time

import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def python_ds_helper(container):
    """Return a container ready for Python data science package testing"""
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
        raise AssertionError(f"Container failed to be ready for Python execution within timeout. Output: {output}")
    
    return container


@pytest.mark.integration
def test_pandas_functionality(python_ds_helper):
    """Test that pandas is working correctly."""
    LOGGER.info("Testing pandas functionality...")

    python_code = '''
import pandas as pd
import numpy as np

# Create a sample DataFrame
df = pd.DataFrame({
    "A": [1, 2, 3, 4, 5],
    "B": ["a", "b", "c", "d", "e"],
    "C": [1.1, 2.2, 3.3, 4.4, 5.5]
})

print("DataFrame created successfully")
print(df.head())

# Test basic operations
result = df["A"].sum()
assert result == 15, f"Expected sum 15, got {result}"

# Test groupby operation
df["group"] = ["X", "Y", "X", "Y", "X"]
grouped = df.groupby("group")["A"].sum()
print("Groupby result:", grouped.to_dict())

print("pandas functionality test successful")
'''

    cmd = ["python", "-c", python_code]
    result = python_ds_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Pandas functionality test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "pandas functionality test successful" in output

    LOGGER.info("pandas functionality test successful")


@pytest.mark.integration
def test_numpy_functionality(python_ds_helper):
    """Test that NumPy is working correctly."""
    LOGGER.info("Testing NumPy functionality...")

    python_code = '''
import numpy as np

# Create arrays and test operations
arr1 = np.array([1, 2, 3, 4, 5])
arr2 = np.array([6, 7, 8, 9, 10])

# Test basic operations
sum_result = arr1 + arr2
assert np.array_equal(sum_result, np.array([7, 9, 11, 13, 15])), f"Sum failed: {sum_result}"

# Test matrix operations
matrix1 = np.array([[1, 2], [3, 4]])
matrix2 = np.array([[5, 6], [7, 8]])
matrix_result = np.dot(matrix1, matrix2)
expected_matrix = np.array([[19, 22], [43, 50]])
assert np.array_equal(matrix_result, expected_matrix), f"Matrix multiplication failed"

# Test statistics
data = np.random.randn(100)
mean_val = np.mean(data)
std_val = np.std(data)
print(f"Random data stats - Mean: {mean_val:.3f}, Std: {std_val:.3f}")

print("NumPy functionality test successful")
'''

    cmd = ["python", "-c", python_code]
    result = python_ds_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"NumPy functionality test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "NumPy functionality test successful" in output

    LOGGER.info("NumPy functionality test successful")


@pytest.mark.integration
def test_matplotlib_functionality(python_ds_helper):
    """Test that matplotlib is working correctly (without display)."""
    LOGGER.info("Testing matplotlib functionality...")

    python_code = '''
import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import io

# Test basic plotting functionality
x = np.linspace(0, 10, 100)
y = np.sin(x)

# Create a figure
fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(x, y, label="sin(x)")
ax.set_xlabel("x")
ax.set_ylabel("sin(x)")
ax.set_title("Sine Wave")
ax.legend()

# Save to bytes buffer instead of file to avoid display issues
buf = io.BytesIO()
plt.savefig(buf, format="png")
buf.seek(0)
print(f"Plot created and saved as PNG, size: {len(buf.getvalue())} bytes")

# Close the plot to free memory
plt.close()

# Test additional matplotlib features
from matplotlib import cm
import matplotlib.patches as mpatches

# Create a simple colormap test
fig2, ax2 = plt.subplots()
gradient = np.linspace(0, 1, 256).reshape(1, -1)
ax2.imshow(gradient, aspect="auto", cmap=cm.viridis)
ax2.set_xlim(0, 256)
ax2.set_yticks([])  # Hide y-axis ticks
ax2.set_title("Viridis Colormap")

buf2 = io.BytesIO()
plt.savefig(buf2, format="png", bbox_inches="tight")
buf2.seek(0)
print(f"Colormap plot created, size: {len(buf2.getvalue())} bytes")

plt.close(fig2)

print("matplotlib functionality test successful")
'''

    cmd = ["python", "-c", python_code]
    result = python_ds_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"matplotlib functionality test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "matplotlib functionality test successful" in output

    LOGGER.info("matplotlib functionality test successful")


@pytest.mark.integration
def test_scikit_learn_functionality(python_ds_helper):
    """Test that scikit-learn is working correctly."""
    LOGGER.info("Testing scikit-learn functionality...")

    python_code = '''
import numpy as np
from sklearn import datasets
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# Load iris dataset
iris = datasets.load_iris()
X, y = iris.data, iris.target

print(f"Dataset loaded - Shape: {X.shape}, Classes: {len(np.unique(y))}")

# Split the dataset
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

# Create and train a model
clf = RandomForestClassifier(n_estimators=10, random_state=42)
clf.fit(X_train, y_train)

# Make predictions
y_pred = clf.predict(X_test)

# Check accuracy (should be reasonably high for this simple dataset)
accuracy = accuracy_score(y_test, y_pred)
print(f"Model accuracy: {accuracy:.3f}")

# The accuracy should be > 0.8 for the iris dataset
assert accuracy > 0.8, f"Expected accuracy > 0.8, got {accuracy}"

print("scikit-learn functionality test successful")
'''

    cmd = ["python", "-c", python_code]
    result = python_ds_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"scikit-learn functionality test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "scikit-learn functionality test successful" in output

    LOGGER.info("scikit-learn functionality test successful")


@pytest.mark.integration
def test_jupyter_and_notebook_packages(python_ds_helper):
    """Test that Jupyter-related packages are working."""
    LOGGER.info("Testing Jupyter and notebook packages...")

    python_code = '''
import sys

# Test core Jupyter packages
try:
    import jupyter_core
    print(f"Jupyter: {jupyter_core.__version__}")
except ImportError:
    print("Jupyter not available")

try:
    import notebook
    print(f"Notebook: {notebook.__version__}")
except ImportError:
    print("Notebook not available")

try:
    import jupyterlab
    print(f"JupyterLab: {jupyterlab.__version__}")
except ImportError:
    print("JupyterLab not available")

# Test IPython functionality
try:
    import IPython
    print(f"IPython: {IPython.__version__}")
    
    # Basic IPython functionality
    from IPython.core.interactiveshell import InteractiveShell
    shell = InteractiveShell.instance()
    result = shell.run_cell("2 + 2")
    assert result.result == 4, f"IPython simple calculation failed: {result.result}"
    print("IPython basic functionality working")
except ImportError:
    print("IPython not available")

# Test widgets
try:
    import ipywidgets
    print(f"ipywidgets: {ipywidgets.__version__}")
    
    # Basic widget functionality
    import ipywidgets as widgets
    slider = widgets.IntSlider(value=7, min=0, max=10, step=1)
    print("ipywidgets basic functionality working")
except ImportError:
    print("ipywidgets not available")

print("Jupyter packages test successful")
'''

    cmd = ["python", "-c", python_code]
    result = python_ds_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Jupyter packages test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Jupyter packages test successful" in output

    LOGGER.info("Jupyter packages test successful")


@pytest.mark.integration
def test_dash_functionality(python_ds_helper):
    """Test that Dash is working correctly."""
    LOGGER.info("Testing Dash functionality...")

    python_code = '''
try:
    import dash
    from dash import html, dcc
    import plotly.graph_objs as go
    
    print(f"Dash version: {dash.__version__}")
    
    # Create a simple Dash app structure (without running it)
    app = dash.Dash(__name__)
    
    app.layout = html.Div([
        html.H1("Test Dashboard"),
        dcc.Graph(
            id="test-graph",
            figure={
                "data": [
                    go.Scatter(
                        x=[1, 2, 3, 4],
                        y=[10, 11, 12, 13],
                        name="Trace 1"
                    )
                ],
                "layout": go.Layout(title="Test Plot")
            }
        )
    ])
    
    print("Dash app structure created successfully")
    
    # Test basic serialization
    import json
    layout_json = app.layout.to_plotly_json()
    assert "props" in layout_json or "type" in layout_json, "Layout serialization failed"
    
    print("Dash functionality test successful")
    
except ImportError:
    print("Dash not available or import failed")
    # Don't fail the test if Dash is not available since it's optional
    print("Dash functionality test completed (optional package)")
'''

    cmd = ["python", "-c", python_code]
    result = python_ds_helper.container.exec_run(cmd)

    # Since Dash may be optional, we'll handle this gracefully
    output = result.output.decode('utf-8')
    if "not available or import failed" in output:
        LOGGER.info("Dash not available (expected in some configurations)")
    else:
        assert result.exit_code == 0, (
            f"Dash functionality test failed\n"
            f"Output: {output}"
        )
        assert "Dash functionality test successful" in output
        LOGGER.info("Dash functionality test successful")


@pytest.mark.integration
def test_common_data_science_stack(python_ds_helper):
    """Test a common data science stack integration."""
    LOGGER.info("Testing common data science stack integration...")

    python_code = '''
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import io

# Create sample data
np.random.seed(42)
X = np.random.randn(100, 1)
y = 2 * X.flatten() + 1 + np.random.randn(100) * 0.5

# Create a DataFrame
df = pd.DataFrame({"x": X.flatten(), "y": y})

# Perform train/test split
X_train, X_test, y_train, y_test = train_test_split(df[["x"]], df["y"], test_size=0.2, random_state=42)

# Train a model
model = LinearRegression()
model.fit(X_train, y_train)

# Make predictions
y_pred = model.predict(X_test)

# Calculate metrics
mse = mean_squared_error(y_test, y_pred)
print(f"Mean Squared Error: {mse:.3f}")

# Create a visualization
fig, ax = plt.subplots()
ax.scatter(X_test, y_test, label="Actual", alpha=0.7)
ax.scatter(X_test, y_pred, label="Predicted", alpha=0.7)
ax.set_xlabel("X")
ax.set_ylabel("y")
ax.set_title("Actual vs Predicted")
ax.legend()

# Save to buffer
buf = io.BytesIO()
plt.savefig(buf, format="png")
buf.seek(0)
print(f"Visualization created, size: {len(buf.getvalue())} bytes")
plt.close()

# Test that model parameters are reasonable
k = model.coef_[0]
b = model.intercept_
print(f"Linear model: y = {k:.2f}x + {b:.2f}")

# For our generated data (y = 2x + 1 + noise), expect k ~ 2 and b ~ 1
assert abs(k - 2) < 1, f"Slope should be close to 2, got {k}"
assert abs(b - 1) < 1, f"Intercept should be close to 1, got {b}"

print("Data science stack integration test successful")
'''

    cmd = ["python", "-c", python_code]
    result = python_ds_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Data science stack integration test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Data science stack integration test successful" in output

    LOGGER.info("Data science stack integration test successful")

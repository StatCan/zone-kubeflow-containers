# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

"""
test_python_data_science
~~~~~~~~~~~~~~~~~~~~~~~~
Tests for Python data science packages and their integration.

This module tests that the core Python data science stack works properly:
- pandas, numpy, matplotlib, scipy, scikit-learn, etc.
- Integration between packages
- Common workflows and use cases
"""

import logging

import pytest

LOGGER = logging.getLogger(__name__)


@pytest.mark.smoke
def test_python_available(jupyter_container):
    """Test that Python is available in the jupyterlab-cpu image."""
    LOGGER.info("Testing Python availability...")
    
    # Execute a simple Python command
    result = jupyter_container.container.exec_run(["python", "--version"])
    
    assert result.exit_code == 0, f"Python command failed with exit code {result.exit_code}"
    
    output = result.output.decode('utf-8').strip()
    assert "Python" in output, f"Unexpected Python version output: {output}"
    
    LOGGER.info(f"Python available: {output}")


@pytest.mark.smoke
def test_basic_data_science_packages(jupyter_container):
    """Test that basic data science packages can be imported."""
    LOGGER.info("Testing basic data science package imports...")
    
    jupyter_container.run()
    
    # Test that core packages can be imported
    packages_to_test = [
        "import pandas as pd",
        "import numpy as np", 
        "import matplotlib.pyplot as plt",
        "import scipy.stats",
        "from sklearn.linear_model import LinearRegression",
        "import seaborn as sns"
    ]
    
    for package_import in packages_to_test:
        result = jupyter_container.container.exec_run([
            "python", "-c", package_import
        ])
        
        assert result.exit_code == 0, (
            f"Failed to import {package_import.split()[1]}: {result.output.decode('utf-8')}"
        )
    
    LOGGER.info("All basic data science packages imported successfully")


@pytest.mark.integration
def test_pandas_numpy_integration(jupyter_container):
    """Test pandas and numpy integration."""
    LOGGER.info("Testing pandas and numpy integration...")
    
    jupyter_container.run()
    
    python_code = '''
import pandas as pd
import numpy as np

# Create a DataFrame with numpy arrays
data = {
    'values': np.random.randn(100),
    'categories': np.random.choice(['A', 'B', 'C'], 100),
    'indices': np.arange(100)
}

df = pd.DataFrame(data)

# Perform operations
summary = df.describe()
grouped_means = df.groupby('categories')['values'].mean()

print(f"DataFrame shape: {df.shape}")
print(f"Number of categories: {len(grouped_means)}")
print(f"Mean of values: {df['values'].mean():.3f}")

# Test that operations work as expected
assert df.shape[0] == 100, f"Expected 100 rows, got {df.shape[0]}"
assert len(df.columns) == 3, f"Expected 3 columns, got {len(df.columns)}"
'''
    
    result = jupyter_container.container.exec_run([
        "python", "-c", python_code
    ])
    
    assert result.exit_code == 0, f"Pandas-numpy integration test failed: {result.output.decode('utf-8')}"
    
    LOGGER.info("pandas-numpy integration test passed")


@pytest.mark.integration
def test_matplotlib_plotting(jupyter_container):
    """Test matplotlib plotting functionality."""
    LOGGER.info("Testing matplotlib plotting...")
    
    jupyter_container.run()
    
    python_code = '''
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import io

# Create sample data
x = np.linspace(0, 10, 100)
y = np.sin(x)

# Create a plot
fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(x, y, label='sin(x)')
ax.set_xlabel('x')
ax.set_ylabel('sin(x)')
ax.set_title('Sine Wave')
ax.legend()
ax.grid(True)

# Save to BytesIO to test plotting functionality
buf = io.BytesIO()
fig.savefig(buf, format='png')
buf.seek(0)

print(f"Plot created successfully with {len(buf.getvalue())} bytes")

# Clean up
plt.close(fig)
'''
    
    result = jupyter_container.container.exec_run([
        "python", "-c", python_code
    ])
    
    assert result.exit_code == 0, f"Matplotlib plotting test failed: {result.output.decode('utf-8')}"
    
    LOGGER.info("matplotlib plotting test passed")


@pytest.mark.integration
def test_scipy_statistics(jupyter_container):
    """Test scipy statistical functionality."""
    LOGGER.info("Testing scipy statistics...")
    
    jupyter_container.run()
    
    python_code = '''
from scipy import stats
import numpy as np

# Generate sample data
data = np.random.normal(loc=50, scale=10, size=1000)

# Perform statistical analysis
mean = np.mean(data)
std = np.std(data)
median = np.median(data)

# Perform a t-test
t_stat, p_value = stats.ttest_1samp(data, 50)

print(f"Sample mean: {mean:.2f}, std: {std:.2f}, median: {median:.2f}")
print(f"T-test vs 50: t-statistic={t_stat:.2f}, p-value={p_value:.2f}")

# Test that results are reasonable
assert abs(mean - 50) < 2, f"Mean {mean} too far from expected 50"
assert 8 < std < 12, f"Std {std} not in expected range [8, 12]"
'''
    
    result = jupyter_container.container.exec_run([
        "python", "-c", python_code
    ])
    
    assert result.exit_code == 0, f"SciPy statistics test failed: {result.output.decode('utf-8')}"
    
    LOGGER.info("scipy statistics test passed")


@pytest.mark.integration
def test_sklearn_machine_learning(jupyter_container):
    """Test sklearn machine learning functionality."""
    LOGGER.info("Testing sklearn machine learning...")
    
    jupyter_container.run()
    
    python_code = '''
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import numpy as np

# Create sample dataset
X, y = make_classification(
    n_samples=1000, 
    n_features=10, 
    n_informative=8, 
    n_redundant=2, 
    random_state=42
)

# Split the data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train a model
clf = RandomForestClassifier(n_estimators=10, random_state=42)
clf.fit(X_train, y_train)

# Make predictions
y_pred = clf.predict(X_test)

# Calculate accuracy
accuracy = accuracy_score(y_test, y_pred)
print(f"Model trained successfully with accuracy: {accuracy:.3f}")

# Test that accuracy is reasonable
assert accuracy > 0.7, f"Accuracy {accuracy} too low"
'''
    
    result = jupyter_container.container.exec_run([
        "python", "-c", python_code
    ])
    
    assert result.exit_code == 0, f"Sklearn ML test failed: {result.output.decode('utf-8')}"
    
    LOGGER.info("sklearn machine learning test passed")


@pytest.mark.integration
def test_seaborn_visualization(jupyter_container):
    """Test seaborn visualization functionality."""
    LOGGER.info("Testing seaborn visualization...")
    
    jupyter_container.run()
    
    python_code = '''
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import seaborn as sns
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io

# Create sample dataset
np.random.seed(42)
data = pd.DataFrame({
    'x': np.random.randn(100),
    'y': np.random.randn(100),
    'category': np.random.choice(['A', 'B', 'C'], 100)
})

# Create a scatter plot
fig, ax = plt.subplots(figsize=(8, 6))
sns.scatterplot(data=data, x='x', y='y', hue='category', ax=ax)
ax.set_title('Seaborn Scatter Plot')

# Save to BytesIO to test functionality
buf = io.BytesIO()
fig.savefig(buf, format='png')
buf.seek(0)

print(f"Seaborn plot created successfully with {len(buf.getvalue())} bytes")

# Clean up
plt.close(fig)
'''
    
    result = jupyter_container.container.exec_run([
        "python", "-c", python_code
    ])
    
    assert result.exit_code == 0, f"Seaborn visualization test failed: {result.output.decode('utf-8')}"
    
    LOGGER.info("seaborn visualization test passed")


@pytest.mark.integration
def test_complete_data_science_workflow(jupyter_container):
    """Test a complete data science workflow combining multiple packages."""
    LOGGER.info("Testing complete data science workflow...")
    
    jupyter_container.run()
    
    python_code = '''
import pandas as pd
import numpy as np
from scipy import stats
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io

# Create synthetic dataset
np.random.seed(42)
n_samples = 500

# Generate correlated data
X = np.random.randn(n_samples, 3)
true_coef = [2.5, -1.3, 0.8]
y = (X[:, 0] * true_coef[0] + 
     X[:, 1] * true_coef[1] + 
     X[:, 2] * true_coef[2] + 
     np.random.randn(n_samples) * 0.5)

# Create DataFrame
df = pd.DataFrame({
    'feature1': X[:, 0],
    'feature2': X[:, 1], 
    'feature3': X[:, 2],
    'target': y
})

print(f"Dataset created with shape: {df.shape}")

# Basic statistics
correlations = df.corr()['target'].drop('target')
print(f"Feature correlations with target: {correlations.values}")

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    df[['feature1', 'feature2', 'feature3']], df['target'], 
    test_size=0.2, random_state=42
)

# Fit model
model = LinearRegression()
model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)

# Metrics
mse = mean_squared_error(y_test, y_pred)
r2 = model.score(X_test, y_test)

print(f"Model performance - MSE: {mse:.3f}, R²: {r2:.3f}")

# Statistical test on residuals
residuals = y_test - y_pred
ks_stat, p_value = stats.kstest(residuals, 'norm')

print(f"Residuals KS test - statistic: {ks_stat:.3f}, p-value: {p_value:.3f}")

# Test that everything worked reasonably
assert r2 > 0.5, f"Model R² {r2} too low"
assert mse < 1.0, f"MSE {mse} too high"
'''
    
    result = jupyter_container.container.exec_run([
        "python", "-c", python_code
    ])
    
    assert result.exit_code == 0, f"Complete workflow test failed: {result.output.decode('utf-8')}"
    
    LOGGER.info("Complete data science workflow test passed")
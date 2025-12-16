# Testing Guide

This directory contains the test suite for Zone Kubeflow Containers. Tests verify container functionality, package compatibility, and system configuration.

## Quick Start

### Run All Tests Locally
```bash
# Set up dev environment (first time only)
make install-python-dev-venv

# Run all tests
make test
```

### Run Specific Test Sets
```bash
# Fast tests only (skip slow and integration tests)
make test-fast

# Smoke tests only (critical path tests)
make test-smoke

# Tests with coverage report
make test-coverage

# Tests for specific image
make test/jupyterlab-cpu
make test/base
```

## Test Structure

### Test Directories
- **`general/`** — Infrastructure and core functionality tests that run on all images
  - `test_health.py` — Health checks and readiness tests
  - `test_environment.py` — Environment variables and configuration
  - `test_kernel_execution.py` — Kernel execution and notebook functionality
  - `test_notebook.py` — Jupyter server startup
  - `test_packages.py` — Package import verification
  - `test_code_server.py` — VS Code server functionality
  - `test_rstudio.py` — RStudio server functionality
  - `test_kubeflow_integration.py` — Kubeflow platform integration
- **`jupyterlab-cpu/`** — Data science package tests for jupyterlab-cpu image
  - `test_python_data_science.py` — Python data science stack (pandas, numpy, matplotlib, etc.)
  - `test_r_functionality.py` — R language and packages functionality
  - `test_julia.py` — Julia language and packages functionality
  - `test_extensions.py` — JupyterLab extension checks
- **`sas/`** — SAS-specific tests for sas image
  - `test_sas_functionality.py` — SAS language and saspy integration functionality
  - `test_sas_studio.py` — SAS Studio environment and functionality

## Test Markers

Tests are tagged with markers for selective execution:

| Marker | Purpose | Example |
|--------|---------|---------|
| `@pytest.mark.smoke` | Critical path tests | Server startup, health checks |
| `@pytest.mark.integration` | Tests requiring Docker | Container execution, kernel tests |
| `@pytest.mark.slow` | Long-running tests | Notebook execution, complex operations |
| `@pytest.mark.xfail` | Expected to fail | Known issues or WIP features |
| `@pytest.mark.info` | Information/diagnostic tests | Package lists, version info |

### Running Tests by Marker
```bash
# Run smoke tests only
pytest -m smoke

# Run all except slow tests
pytest -m "not slow"

# Run integration tests only
pytest -m integration

# Run tests that are both smoke and integration
pytest -m "smoke and integration"
```

## Writing New Tests

### Test Fixtures
All tests have access to these fixtures from `conftest.py`:

- **`container`** — A TrackedContainer instance for the test image
- **`http_client`** — A requests Session with retry logic
- **`docker_client`** — A Docker client instance
- **`image_name`** — The image being tested (from `IMAGE_NAME` env var)
- **`nb_prefix`** — The notebook prefix (from `NB_PREFIX` env var)

### Example Test
```python
@pytest.mark.integration
@pytest.mark.smoke
def test_something_important(container, http_client):
    """Test that something important works."""
    container.run()
    
    resp = http_client.get("http://localhost:8888/")
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}\n"
        f"Response: {resp.text[:500]}"
    )
```

### Key Practices
- Add appropriate markers (`@pytest.mark.smoke`, `@pytest.mark.integration`, etc.)
- Include detailed error messages in assertions
- Use `time.sleep()` when waiting for container initialization
- Clean up resources (fixtures handle this automatically)
- Log important information with `LOGGER.info()`

## Running Tests in CI/CD

Tests automatically run on:
- **Pull Requests** — Against all modified images
- **Pushes to beta/master** — Against all images in the build matrix
- **GitHub Actions** — Uses `make test/<image>` for each image

The CI/CD workflow:
1. Builds Docker image
2. Runs `make test/<image>` to execute all tests
3. Scans for vulnerabilities
4. Reports results

## Troubleshooting

### Port Already in Use
```bash
# Check what's using port 8888
netstat -ano | findstr :8888  # Windows
lsof -i :8888  # macOS/Linux

# Or update the port in conftest.py or test parameters
```

### Container Won't Start
- Check Docker is running: `docker ps`
- Check image exists: `docker images | grep <image-name>`
- Check logs: `docker logs <container-id>`

### Import Errors in Tests
```bash
# Reinstall dev dependencies
make install-python-dev-venv
```

## Coverage Reports

Generate a coverage report:
```bash
make test-coverage
```

This creates:
- Terminal report with percentages
- HTML report in `htmlcov/index.html`

View the HTML report:
```bash
# Windows
start htmlcov/index.html

# macOS
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html
```

## Adding Image-Specific Tests

To add tests for a specific image:

1. Create a directory: `tests/<image-name>/`
2. Add test files: `tests/<image-name>/test_*.py`
3. Run with: `make test/<image-name>`

Example:
```bash
mkdir tests/my-image
touch tests/my-image/test_my_feature.py
make test/my-image
```

## Known Issues

- JupyterLab extension tests marked as `@pytest.mark.xfail` (see `test_extensions.py`)
- pytables import test excluded due to known compatibility issues
- Some R tests may be skipped if R kernel not installed
- SAS functionality tests may be skipped if SAS is not available in the image

## References

- [pytest Documentation](https://docs.pytest.org/)
- [Docker Python SDK](https://docker-py.readthedocs.io/)
- [Jupyter Testing](https://github.com/jupyter/docker-stacks/tree/master/tests)

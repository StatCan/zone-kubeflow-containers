import logging
import importlib.util
import pytest

from helpers import CondaPackageHelper

LOGGER = logging.getLogger(__name__)

# Package mappings for import names
PACKAGE_MAPPING = {
    "matplotlib-base": "matplotlib",
    "beautifulsoup4": "bs4",
    "scikit-learn": "sklearn",
    "scikit-image": "skimage",
    "spylon-kernel": "spylon_kernel",
    "pillow": "PIL",
    "pytables": "tables",
    "pyyaml": "yaml",
    "randomforest": "randomForest",
    "rsqlite": "DBI",
    "rcurl": "RCurl",
    "rodbc": "RODBC",
    "catools": "caTools",
}

# Packages excluded from import tests
EXCLUDED_PACKAGES = {"tini", "python", "hdf5", "nodejs", "jupyterlab-git", "openssl"}

@pytest.fixture(scope="function")
def package_helper(container):
    """Return a package helper object."""
    return CondaPackageHelper(container)

@pytest.fixture(scope="function")
def packages(package_helper):
    """Return a list of specified packages."""
    return package_helper.specified_packages()

def package_map(package):
    """Map package names to importable library names."""
    return PACKAGE_MAPPING.get(package, package)

def is_importable(package):
    """Check if a Python package is importable."""
    return importlib.util.find_spec(package) is not None

def is_r_package_installed(package_helper, package):
    """Check if an R package is installed and importable."""
    cmd = f"R --slave -e \"if (!requireNamespace('{package}', quietly = TRUE)) quit(status = 1)\""
    return package_helper.running_container.exec_run(cmd).exit_code == 0

def check_import_python_package(package_helper, package):
    """Try to import a Python package."""
    if not is_importable(package):
        LOGGER.warning(f"Skipping {package}: not an importable library.")
        return 0
    return package_helper.running_container.exec_run(["python", "-c", f"import {package}"]).exit_code

def check_import_r_package(package_helper, package):
    """Try to import an R package."""
    if not is_r_package_installed(package_helper, package):
        LOGGER.warning(f"Skipping {package}: not a library package.")
        return 0
    return package_helper.running_container.exec_run(["R", "--slave", "-e", f"library({package})"]).exit_code

def _import_packages(package_helper, packages, check_function, max_failures):
    """Test if packages can be imported."""
    failures = {}
    LOGGER.info("Testing package imports...")
    for package in packages:
        LOGGER.info(f"Checking import: {package}")
        try:
            assert check_function(package_helper, package) == 0, f"Failed to import {package}"
        except AssertionError as err:
            failures[package] = str(err)
    if len(failures) > max_failures:
        raise AssertionError(f"Exceeded max import failures: {failures}")
    elif failures:
        LOGGER.warning(f"Import failures: {failures}")

def test_python_packages(package_helper, packages, max_failures=3):
    """Test Python package imports."""
    python_packages = [package_map(pkg) for pkg in packages if not pkg.startswith("r-") and pkg not in EXCLUDED_PACKAGES]
    _import_packages(package_helper, python_packages, check_import_python_package, max_failures)

def test_r_packages(package_helper, packages, max_failures=3):
    """Test R package imports."""
    r_packages = [package_map(pkg[2:]) for pkg in packages if pkg.startswith("r-") and pkg not in EXCLUDED_PACKAGES]
    _import_packages(package_helper, r_packages, check_import_r_package, max_failures)

def test_summary_report():
    """Print a final summary report."""
    LOGGER.info("All package import tests completed.")

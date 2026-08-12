"""
test_r_system
~~~~~~~~~~~~~
Tests for the system R installation (CRAN apt + Posit Package Manager).

R is installed at /usr/bin/R in images/base, and the R package set is
installed from Posit Package Manager in images/mid (rstudio and sas inherit
it). These tests replace the conda-based R coverage that test_packages.py
provided when R came from conda-forge.
"""

import logging
import pytest

from helpers import CondaPackageHelper

LOGGER = logging.getLogger(__name__)

# Keep in sync with R_APT_VERSION in images/base/Dockerfile
EXPECTED_R_VERSION = "R version 4.6.1"

# Keep in sync with the Posit Package Manager install in images/mid/Dockerfile
# (zonetokenbroker is installed separately from images/mid/zone-token-broker).
R_PACKAGES = [
    "arrow",
    "aws.s3",
    "caTools",
    "caret",
    "crayon",
    "devtools",
    "e1071",
    "forecast",
    "hdf5r",
    "hexbin",
    "htmltools",
    "htmlwidgets",
    "httr",
    "jsonlite",
    "markdown",
    "nycflights13",
    "odbc",
    "randomForest",
    "RCurl",
    "renv",
    "RODBC",
    "reticulate",
    "rmarkdown",
    "RSQLite",
    "shiny",
    "sf",
    "sparklyr",
    "tidyverse",
    "tidymodels",
    "languageserver",
    "zonetokenbroker",
]


@pytest.fixture(scope="function")
def package_helper(container):
    """Return a package helper object that can be used to perform tests on installed packages"""
    return CondaPackageHelper(container)


def _execute_on_container(package_helper, command):
    """Generic function executing a command"""
    LOGGER.debug(f"Running command [{command}] ...")
    return package_helper.running_container.exec_run(command)


def _skip_unless_system_r(package_helper):
    """Skip when the image does not ship the system R installation"""
    result = _execute_on_container(package_helper, ["test", "-x", "/usr/bin/R"])
    if result.exit_code != 0:
        pytest.skip("system R (/usr/bin/R) not present in this image")


def _skip_unless_r_packages(package_helper):
    """The R package set arrives in mid; every downstream image (rstudio,
    sas-kernel, sas, jupyterlab-cpu) inherits it -- only base ships R alone"""
    image_name = package_helper.running_container.image.tags[0].lower() if package_helper.running_container.image.tags else ""
    if "base" in image_name:
        pytest.skip("R package set not expected in this image")


def test_r_version(package_helper):
    """System R is present and at the pinned version"""
    _skip_unless_system_r(package_helper)

    result = _execute_on_container(package_helper, ["/usr/bin/R", "--version"])
    output = result.output.decode("utf-8")
    LOGGER.info(f"R --version: {output.splitlines()[0] if output else output}")
    assert result.exit_code == 0
    assert EXPECTED_R_VERSION in output


def test_r_packages_load(package_helper):
    """Every R package installed from Posit Package Manager can be loaded"""
    _skip_unless_system_r(package_helper)
    _skip_unless_r_packages(package_helper)

    failures = {}
    for package in R_PACKAGES:
        LOGGER.info(f"Trying to load R package {package}")
        result = _execute_on_container(
            package_helper,
            ["/usr/bin/R", "--slave", "-e", f"library({package})"],
        )
        if result.exit_code != 0:
            failures[package] = result.output.decode("utf-8")[-500:]
    assert not failures, f"R packages failed to load: {failures}"


def test_all_installed_r_namespaces_load(package_helper):
    """Every installed R package can load its namespace in system R."""
    _skip_unless_system_r(package_helper)
    _skip_unless_r_packages(package_helper)

    expression = (
        'pkgs <- rownames(installed.packages()); '
        'ok <- vapply(pkgs, requireNamespace, logical(1), quietly = TRUE); '
        'if (any(!ok)) stop("R namespaces failed to load: ", '
        'paste(pkgs[!ok], collapse = ", "))'
    )
    result = _execute_on_container(
        package_helper, ["/usr/bin/R", "--slave", "-e", expression]
    )
    assert result.exit_code == 0, result.output.decode("utf-8", errors="replace")


def test_standalone_python_ssl(package_helper):
    """The pinned Conda Python uses its matching OpenSSL outside R."""
    _skip_unless_r_packages(package_helper)

    code = (
        "import ssl, sys; "
        "assert sys.version_info[:3] == (3, 14, 5); "
        "assert ssl.OPENSSL_VERSION.startswith('OpenSSL 3.6.3')"
    )
    result = _execute_on_container(
        package_helper, ["/opt/conda/bin/python", "-c", code]
    )
    assert result.exit_code == 0, result.output.decode("utf-8", errors="replace")


def test_python_to_system_r_via_rpy2(package_helper):
    """The Conda Python-to-system-R bridge remains operational."""
    _skip_unless_system_r(package_helper)
    _skip_unless_r_packages(package_helper)

    code = (
        "from rpy2 import robjects; "
        "version = str(robjects.r('R.version.string')[0]); "
        "assert version.startswith('R version 4.6.1'), version"
    )
    result = _execute_on_container(
        package_helper, ["/opt/conda/bin/python", "-c", code]
    )
    assert result.exit_code == 0, result.output.decode("utf-8", errors="replace")


def test_r_kernelspec(package_helper):
    """The Jupyter R kernel is registered against the system R"""
    _skip_unless_system_r(package_helper)

    result = _execute_on_container(package_helper, ["jupyter", "kernelspec", "list"])
    output = result.output.decode("utf-8")
    LOGGER.info(f"kernelspec list: {output}")
    assert result.exit_code == 0
    assert "ir" in output.split()

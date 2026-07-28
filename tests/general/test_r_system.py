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
    "e1071",
    "hdf5r",
    "httr",
    "jsonlite",
    "markdown",
    "odbc",
    "renv",
    "RODBC",
    "sf",
    "sparklyr",
    "tidyverse",
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
    """The R package set is installed in mid; base and jupyterlab-cpu only ship R itself"""
    image_name = package_helper.running_container.image.tags[0].lower() if package_helper.running_container.image.tags else ""
    if "base" in image_name or "jupyterlab" in image_name:
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


def test_r_kernelspec(package_helper):
    """The Jupyter R kernel is registered against the system R"""
    _skip_unless_system_r(package_helper)

    result = _execute_on_container(package_helper, ["jupyter", "kernelspec", "list"])
    output = result.output.decode("utf-8")
    LOGGER.info(f"kernelspec list: {output}")
    assert result.exit_code == 0
    assert "ir" in output.split()

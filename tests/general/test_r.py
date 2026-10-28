"""
test_r
~~~~~~
Tests for the R installation: r-base from conda-forge with the R package set
installed from Posit Package Manager (images/mid).

R packages no longer show up in the conda history, so test_packages.py's
conda-driven R checks no longer cover them; these tests do instead.
"""

import logging
import pytest

from helpers import CondaPackageHelper

LOGGER = logging.getLogger(__name__)

# Keep in sync with the r-base pin in images/mid/Dockerfile
EXPECTED_R_VERSION = "R version 4.6.1"

# Keep in sync with the Posit Package Manager install in images/mid/Dockerfile
# (zonetokenbroker is installed separately from images/mid/zone-token-broker).
R_PACKAGES = [
    "arrow",
    "aws.s3",
    "caret",
    "caTools",
    "crayon",
    "devtools",
    "e1071",
    "forecast",
    "hdf5r",
    "hexbin",
    "htmltools",
    "htmlwidgets",
    "httr",
    "IRkernel",
    "jsonlite",
    "languageserver",
    "markdown",
    "nycflights13",
    "odbc",
    "randomForest",
    "RCurl",
    "renv",
    "rmarkdown",
    "RODBC",
    "RSQLite",
    "sf",
    "shiny",
    "sparklyr",
    "tidymodels",
    "tidyverse",
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


def _skip_unless_mid_or_later(package_helper):
    """R 4.6 and its package set arrive in mid; every downstream image
    (rstudio, sas-kernel, sas, jupyterlab-cpu) inherits them"""
    image_name = package_helper.running_container.image.tags[0].lower() if package_helper.running_container.image.tags else ""
    if "base" in image_name:
        pytest.skip("R package set not expected in this image")


def test_r_version(package_helper):
    """R is present and at the pinned version"""
    _skip_unless_mid_or_later(package_helper)

    result = _execute_on_container(package_helper, ["R", "--version"])
    output = result.output.decode("utf-8")
    LOGGER.info(f"R --version: {output.splitlines()[0] if output else output}")
    assert result.exit_code == 0
    assert EXPECTED_R_VERSION in output


def test_r_packages_load(package_helper):
    """Every R package installed from Posit Package Manager can be loaded"""
    _skip_unless_mid_or_later(package_helper)

    failures = {}
    for package in R_PACKAGES:
        LOGGER.info(f"Trying to load R package {package}")
        result = _execute_on_container(
            package_helper,
            ["R", "--slave", "-e", f"library({package})"],
        )
        if result.exit_code != 0:
            failures[package] = result.output.decode("utf-8")[-500:]
    assert not failures, f"R packages failed to load: {failures}"


def test_r_kernelspec(package_helper):
    """The Jupyter R kernel is registered"""
    _skip_unless_mid_or_later(package_helper)

    result = _execute_on_container(package_helper, ["jupyter", "kernelspec", "list"])
    output = result.output.decode("utf-8")
    LOGGER.info(f"kernelspec list: {output}")
    assert result.exit_code == 0
    assert "ir" in output.split()


# TEMPORARY: remove with images/mid/s6/cont-init.d/03-fix-user-rprofile.
# The ~/.Rprofile that notebooks created before R 4.6.1 still carry
# (images/mid/.Rprofile from #224), plus a user customization.
OLD_RPROFILE = r'''home_dir <- Sys.getenv("HOME")
package_dir <- paste0(home_dir, "/R/", "r-packages-", R.Version()$major, ".", R.Version()$minor)
dir.create(package_dir, recursive = T, showWarnings = F)

# Include any existing older R package directories for seamless upgrade
all_r_package_dirs <- list.files(paste0(home_dir, "/R/"), pattern = "^r-packages-[0-9]+\\.[0-9]+$", full.names = TRUE, include.dirs = TRUE)
existing_r_package_dirs <- all_r_package_dirs[file.info(all_r_package_dirs)$isdir]

# Set library paths with current directory first, then any existing older directories
.libPaths(c(package_dir, existing_r_package_dirs[existing_r_package_dirs != package_dir]))

# Clean up
rm(home_dir)
rm(package_dir)
rm(all_r_package_dirs)
rm(existing_r_package_dirs)

# using wget because https://github.com/StatCan/aaw-kubeflow-containers/issues/569
# https://stackoverflow.com/questions/70559397/r-internet-routines-cannot-be-loaded-when-starting-from-rstudio
options(download.file.method="wget")
options(width = 123)
'''


def test_old_user_rprofile_is_fixed(package_helper):
    """The startup script strips the wget override and the older-library
    block from an existing ~/.Rprofile and keeps the user's own settings"""
    _skip_unless_mid_or_later(package_helper)

    # r-packages-4.5 matches the old block's pattern, so it would be added to
    # .libPaths() if the block survived.
    script = f"""export HOME="$(mktemp -d)"
mkdir -p "$HOME/R/r-packages-4.5"
cat > "$HOME/.Rprofile" <<'EOF'
{OLD_RPROFILE}EOF
bash /etc/cont-init.d/03-fix-user-rprofile
Rscript -e 'cat(sum(grepl("r-packages-", .libPaths())), identical(getOption("download.file.method"), "wget"), getOption("width"))'
"""
    result = _execute_on_container(package_helper, ["bash", "-c", script])
    output = result.output.decode("utf-8").strip()
    LOGGER.info(f"Rprofile migration: {output}")
    assert result.exit_code == 0, output
    assert output.splitlines()[-1] == "1 FALSE 123", output

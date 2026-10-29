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
from tests.general.wait_utils import wait_for_exec_success

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


def _wait_for_startup(container):
    """02-start-custom writes the user library setup into Rprofile.site at boot"""
    ready, output = wait_for_exec_success(
        container=container,
        command=["grep", "-q", "r-packages-", "/opt/conda/lib/R/etc/Rprofile.site"],
        timeout=120,
    )
    assert ready, f"Rprofile.site was not configured at startup: {output}"


def test_user_library_without_user_rprofile(container, package_helper):
    """install.packages() targets ~/R/r-packages-<version> on the workspace volume
    even when ~/.Rprofile does not run: here a project .Rprofile replaces it, as
    renv projects do. Otherwise it falls back to /opt/conda/lib/R/library, which
    is lost on restart."""
    _skip_unless_mid_or_later(package_helper)
    _wait_for_startup(container)

    script = """mkdir -p /tmp/project && echo 'options(width = 123)' > /tmp/project/.Rprofile
cd /tmp/project && Rscript -e 'cat(.libPaths()[1], getOption("width"))'
"""
    result = _execute_on_container(package_helper, ["bash", "-c", script])
    output = result.output.decode("utf-8").strip()
    LOGGER.info(f"user library: {output}")
    assert result.exit_code == 0, output
    r_version = EXPECTED_R_VERSION.split()[-1]
    assert output.splitlines()[-1] == f"/home/jovyan/R/r-packages-{r_version} 123", output


def test_wget_downloads_send_r_user_agent(container, package_helper):
    """Older ~/.Rprofile files force download.file.method = "wget". Posit Package
    Manager only serves binary packages to clients that send R's user agent."""
    _skip_unless_mid_or_later(package_helper)
    _wait_for_startup(container)

    script = """cat > /tmp/echo_ua.py <<'EOF'
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = self.headers.get("User-Agent", "").encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
HTTPServer(("127.0.0.1", 18904), Handler).serve_forever()
EOF
python3 /tmp/echo_ua.py &
SERVER_PID=$!
trap 'kill $SERVER_PID' EXIT
for _ in $(seq 1 20); do
  Rscript -e 'options(download.file.method = "wget"); download.file("http://127.0.0.1:18904/", "/tmp/ua.txt", quiet = TRUE)' 2>/dev/null && break
  sleep 0.5
done
cat /tmp/ua.txt
"""
    result = _execute_on_container(package_helper, ["bash", "-c", script])
    output = result.output.decode("utf-8").strip()
    LOGGER.info(f"wget user agent: {output}")
    r_version = EXPECTED_R_VERSION.split()[-1]
    assert output.splitlines()[-1].startswith(f"R/{r_version} "), output

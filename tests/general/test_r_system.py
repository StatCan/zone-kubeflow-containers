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
from tests.general.wait_utils import wait_for_condition

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
        'errors <- vapply(pkgs, function(pkg) tryCatch({ '
        'loadNamespace(pkg); "" }, '
        'error = function(e) conditionMessage(e)), character(1)); '
        'failed <- nzchar(errors); '
        'if (any(failed)) stop("R namespaces failed to load:\n", '
        'paste(paste0(pkgs[failed], ": ", errors[failed]), collapse = "\n"))'
    )
    result = _execute_on_container(
        package_helper, ["/usr/bin/R", "--slave", "-e", expression]
    )
    assert result.exit_code == 0, result.output.decode("utf-8", errors="replace")


def test_runtime_r_repositories_are_usable(package_helper):
    """Startup configures a usable HTTPS CRAN repo without placeholders."""
    _skip_unless_system_r(package_helper)
    _skip_unless_r_packages(package_helper)

    expression = r'''
repos <- getOption("repos")
cran <- unname(repos["CRAN"])
valid <- (
  length(cran) == 1L &&
  !is.na(cran) &&
  nzchar(cran) &&
  grepl("^https://", cran) &&
  !any(is.na(repos)) &&
  !any(unname(repos) == "@CRAN@") &&
  tryCatch({ contrib.url(repos); TRUE }, error = function(e) FALSE)
)
if (!isTRUE(valid)) {
  stop("invalid runtime R repository configuration", call. = FALSE)
}
'''.strip()
    def repositories_are_ready():
        result = _execute_on_container(
            package_helper, ["/usr/bin/R", "--slave", "-e", expression]
        )
        return result.exit_code == 0

    assert wait_for_condition(
        repositories_are_ready,
        timeout=30,
        initial_delay=0.5,
        max_delay=3,
        description="runtime R repository configuration",
    ), "runtime R repository configuration did not become valid"


def test_system_r_sparklyr_local_spark(package_helper):
    """System R can drive the installed PySpark 4.2 runtime with sparklyr."""
    _skip_unless_system_r(package_helper)
    _skip_unless_r_packages(package_helper)

    expression = r'''
suppressPackageStartupMessages(library(sparklyr))

run_sparklyr_smoke <- function() {
  spark_home <- Sys.getenv("SPARK_HOME")
  stopifnot(
    identical(
      normalizePath(spark_home),
      "/opt/conda/lib/python3.14/site-packages/pyspark"
    ),
    file.exists(file.path(spark_home, "bin", "spark-submit"))
  )

  install_dir <- tempfile("sparklyr-install-")
  dir.create(install_dir)
  old_options <- options(spark.install.dir = install_dir)
  on.exit(options(old_options), add = TRUE)
  on.exit(unlink(install_dir, recursive = TRUE), add = TRUE)

  install_info <- suppressWarnings(
    sparklyr::spark_install_find(version = "4.2.0", latest = FALSE)
  )
  stopifnot(
    file.symlink(spark_home, install_info$sparkVersionDir),
    identical(normalizePath(install_info$sparkVersionDir), spark_home)
  )

  config <- sparklyr::spark_config()
  config$`sparklyr.cores.local` <- 1
  config$`sparklyr.shell.driver-memory` <- "1g"
  config$`spark.ui.enabled` <- FALSE
  config$`spark.sql.shuffle.partitions` <- 1
  Sys.setenv(SPARK_LOCAL_IP = "127.0.0.1")

  connection <- NULL
  on.exit({
    if (!is.null(connection)) sparklyr::spark_disconnect(connection)
  }, add = TRUE)
  connection <- sparklyr::spark_connect(
    master = "local",
    version = "4.2.0",
    spark_home = spark_home,
    config = config
  )

  stopifnot(
    identical(as.character(sparklyr::spark_version(connection)), "4.2.0"),
    sparklyr::sdf_nrow(sparklyr::sdf_len(connection, 5L)) == 5L
  )
}

run_sparklyr_smoke()
cat("SYSTEM_R_SPARKLYR_4_2_OK\\n")
'''.strip()
    result = _execute_on_container(
        package_helper, ["/usr/bin/R", "--slave", "-e", expression]
    )
    output = result.output.decode("utf-8", errors="replace")
    LOGGER.info(f"system R sparklyr smoke: {output[-1000:]}")
    assert result.exit_code == 0, output[-3000:]
    assert "SYSTEM_R_SPARKLYR_4_2_OK" in output


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


def _skip_unless_reticulate_overlay(package_helper):
    """Skip when the image does not ship the audited reticulate overlay"""
    result = _execute_on_container(
        package_helper, ["test", "-e", "/opt/reticulate-compat/.audit-passed"]
    )
    if result.exit_code != 0:
        pytest.skip("reticulate compatibility overlay not present in this image")


def test_system_r_reticulate_uses_conda_python_with_overlay(package_helper):
    """Plain system-R sessions embed Conda Python through the audited overlay.

    Rprofile.site (images/mid) provides RETICULATE_PYTHON_FALLBACK so a bare
    library(reticulate) resolves the image's Conda interpreter (instead of an
    unreachable uv-managed environment), and the in-interpreter .pth hook
    activates /opt/reticulate-compat because the process runs under R. This
    covers terminal R/Rscript, the Jupyter IR kernel, and R in VSCode
    terminals -- not only the RStudio rsession wrapper.
    """
    _skip_unless_system_r(package_helper)
    _skip_unless_r_packages(package_helper)
    _skip_unless_reticulate_overlay(package_helper)

    expression = r'''
suppressPackageStartupMessages(library(reticulate))

stopifnot(identical(Sys.getenv("RETICULATE_PYTHON_FALLBACK"), "/opt/conda/bin/python"))

cfg <- py_config()
stopifnot(dirname(normalizePath(cfg$python)) == "/opt/conda/bin")

sys <- import("sys")
overlay_paths <- c(
  "/opt/reticulate-compat/lib/python3.14/lib-dynload",
  "/opt/reticulate-compat/lib/python3.14/site-packages"
)
stopifnot(all(overlay_paths %in% sys$path))

os <- import("os")
underscore_ssl <- import("_ssl")
stopifnot(startsWith(
  os$path$realpath(underscore_ssl$`__file__`),
  "/opt/reticulate-compat/"
))

ssl <- import("ssl")
stopifnot(grepl("^OpenSSL 3\\.0\\.", ssl$OPENSSL_VERSION))

hashlib <- import("hashlib")
digest <- hashlib$sha256(charToRaw("system-r-reticulate"))$hexdigest()
stopifnot(nchar(digest) == 64L)

np <- import("numpy")
stopifnot(np$arange(5L)$sum() == 10)

pa <- import("pyarrow")
stopifnot(startsWith(
  os$path$realpath(pa$`__file__`),
  "/opt/reticulate-compat/"
))
tbl <- pa$table(list(a = c(1, 2, 3)))
stopifnot(tbl$num_rows == 3L)

maps <- readLines("/proc/self/maps")
stopifnot(
  !any(grepl("/opt/conda/lib/libssl", maps, fixed = TRUE)),
  !any(grepl("/opt/conda/lib/libcrypto", maps, fixed = TRUE))
)

cat("SYSTEM_R_RETICULATE_OK\n")
'''.strip()
    result = _execute_on_container(
        package_helper, ["/usr/bin/Rscript", "-e", expression]
    )
    output = result.output.decode("utf-8", errors="replace")
    LOGGER.info(f"system R reticulate smoke: {output[-1000:]}")
    assert result.exit_code == 0, output[-3000:]
    assert "SYSTEM_R_RETICULATE_OK" in output


def test_system_r_reticulate_env_overrides_win(package_helper):
    """Explicit interpreter configuration outranks the Rprofile.site default.

    RETICULATE_PYTHON_FALLBACK is reticulate's weakest hint, so every
    explicit mechanism (RETICULATE_PYTHON here as representative) wins, and a
    pre-set fallback is never clobbered. Overlay activation is coupled to the
    interpreter itself: explicitly selecting the default Conda Python still
    engages the overlay, while the R session's environment is never polluted
    for foreign interpreters.
    """
    _skip_unless_system_r(package_helper)
    _skip_unless_r_packages(package_helper)
    _skip_unless_reticulate_overlay(package_helper)

    cases = [
        # A custom interpreter wins over the fallback, and the R session env
        # carries no overlay a foreign interpreter could pick up.
        (
            ["RETICULATE_PYTHON=/custom/python"],
            'stopifnot(identical(Sys.getenv("RETICULATE_PYTHON"), "/custom/python"), '
            'identical(Sys.getenv("PYTHONPATH"), ""))',
        ),
        # A pre-set fallback is preserved.
        (
            ["RETICULATE_PYTHON_FALLBACK=/custom/python"],
            'stopifnot(identical(Sys.getenv("RETICULATE_PYTHON_FALLBACK"), "/custom/python"))',
        ),
        # Explicitly selecting the default Conda interpreter (not via the
        # fallback) still activates the overlay: it is bound to the
        # interpreter, not to how the interpreter was chosen.
        (
            ["RETICULATE_PYTHON=/opt/conda/bin/python"],
            'suppressPackageStartupMessages(library(reticulate)); '
            'os <- import("os"); '
            'underscore_ssl <- import("_ssl"); '
            'stopifnot(startsWith(os$path$realpath(underscore_ssl$`__file__`), '
            '"/opt/reticulate-compat/"))',
        ),
    ]
    for env_settings, expression in cases:
        result = _execute_on_container(
            package_helper,
            ["/usr/bin/env", *env_settings, "/usr/bin/Rscript", "-e", expression],
        )
        output = result.output.decode("utf-8", errors="replace")
        assert result.exit_code == 0, f"env={env_settings}: {output}"


def test_reticulate_overlay_hook_scopes_to_r_processes(package_helper):
    """The .pth hook applies the overlay only to Conda Python under R.

    zone_reticulate_compat activates on R_HOME (exported by every R process,
    so reticulate-embedded and R-spawned Pythons are covered), stays inert
    for standalone Python, and honours the ZONE_RETICULATE_COMPAT=0 opt-out.
    """
    _skip_unless_r_packages(package_helper)
    _skip_unless_reticulate_overlay(package_helper)

    overlay_probe = (
        "import sys; "
        "print(any(p.startswith('/opt/reticulate-compat') for p in sys.path))"
    )
    cases = [
        # Standalone Python: overlay must stay out of sys.path.
        (["-u", "R_HOME"], "False"),
        # Under an R process: overlay paths precede the Conda ones.
        (["R_HOME=/usr/lib/R"], "True"),
        # Explicit opt-out wins even under R.
        (["R_HOME=/usr/lib/R", "ZONE_RETICULATE_COMPAT=0"], "False"),
    ]
    for env_settings, expected in cases:
        result = _execute_on_container(
            package_helper,
            ["/usr/bin/env", *env_settings, "/opt/conda/bin/python", "-c", overlay_probe],
        )
        output = result.output.decode("utf-8", errors="replace")
        assert result.exit_code == 0, f"env={env_settings}: {output}"
        assert output.strip().splitlines()[-1] == expected, f"env={env_settings}: {output}"

    # With the overlay active, its system-OpenSSL _ssl must be importable in
    # a fresh (not R-embedded) Conda Python too: the rebuilt module's
    # OPENSSL_3.0.0 symbol requirements are satisfied by whichever OpenSSL 3
    # the loader resolves.
    ssl_probe = (
        "import os, ssl, _ssl; "
        "assert os.path.realpath(_ssl.__file__).startswith('/opt/reticulate-compat/'), _ssl.__file__; "
        "ssl.create_default_context(); "
        "print('OVERLAY_SSL_OK')"
    )
    result = _execute_on_container(
        package_helper,
        ["/usr/bin/env", "R_HOME=/usr/lib/R", "/opt/conda/bin/python", "-c", ssl_probe],
    )
    output = result.output.decode("utf-8", errors="replace")
    assert result.exit_code == 0, output
    assert "OVERLAY_SSL_OK" in output


def test_r_kernel_executes_system_r(package_helper):
    """The registered Jupyter R kernel launches and executes system R 4.6.1."""
    _skip_unless_system_r(package_helper)

    kernel_test = r'''
import os
import subprocess
import time

from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

expected_argv_tail = [
    "--slave",
    "-e",
    "IRkernel::main()",
    "--args",
    "{connection_file}",
]
spec = KernelSpecManager().get_kernel_spec("ir")
assert os.path.isabs(spec.argv[0]), spec.argv
assert spec.argv[1:] == expected_argv_tail, spec.argv
assert spec.display_name == "R 4.6.1", spec.display_name
assert spec.language == "R", spec.language

r_home_command = ["--slave", "-e", "cat(normalizePath(R.home()))"]
kernel_r_home = subprocess.check_output(
    [spec.argv[0], *r_home_command], text=True
).strip()
system_r_home = subprocess.check_output(
    ["/usr/bin/R", *r_home_command], text=True
).strip()
assert kernel_r_home == system_r_home, (spec.argv[0], kernel_r_home, system_r_home)

manager = KernelManager(kernel_name="ir")
client = None
started = False
try:
    manager.start_kernel()
    started = True
    client = manager.client()
    client.start_channels()
    client.wait_for_ready(timeout=60)
    message_id = client.execute(
        'stopifnot(as.character(getRversion()) == "4.6.1"); '
        'cat("IRKERNEL_R_4_6_1_OK\\n")'
    )

    stream_output = []
    deadline = time.monotonic() + 60
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, "timed out waiting for the R kernel to become idle"
        message = client.get_iopub_msg(timeout=remaining)
        if message.get("parent_header", {}).get("msg_id") != message_id:
            continue
        message_type = message["header"]["msg_type"]
        if message_type == "stream":
            stream_output.append(message["content"]["text"])
        elif message_type == "error":
            traceback = "\n".join(message["content"].get("traceback", []))
            raise AssertionError(traceback or repr(message["content"]))
        elif message_type == "status" and message["content"]["execution_state"] == "idle":
            break

    output = "".join(stream_output)
    assert "IRKERNEL_R_4_6_1_OK" in output, output
    print("IRKERNEL_EXECUTION_OK")
finally:
    if client is not None:
        client.stop_channels()
    if started:
        manager.shutdown_kernel(now=True)
'''.strip()
    result = _execute_on_container(
        package_helper, ["/opt/conda/bin/python", "-c", kernel_test]
    )
    output = result.output.decode("utf-8", errors="replace")
    LOGGER.info(f"system R kernel smoke: {output[-1000:]}")
    assert result.exit_code == 0, output[-3000:]
    assert "IRKERNEL_EXECUTION_OK" in output

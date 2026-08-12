import logging
import pytest

from helpers import CondaPackageHelper

LOGGER = logging.getLogger(__name__)

# Expected RStudio version string for validation.
# Keep in sync with RSTUDIO_VERSION in images/rstudio/Dockerfile (the "+" build
# separator here corresponds to the "-" in the .deb version). Matched as a
# substring so the release codename does not need to be tracked.
EXPECTED = "2026.04.0+526"

@pytest.fixture(scope="function")
def package_helper(container):
    """Return a package helper object that can be used to perform tests on installed packages"""
    # Create and return a helper for package operations on the test container
    return CondaPackageHelper(container)

def _execute_on_container(package_helper, command):
    """Generic function executing a command"""
    LOGGER.debug(f"Running command [{command}] ...")
    # Execute command on running container and return result
    return package_helper.running_container.exec_run(command)


def _skip_if_no_rstudio(package_helper):
    # Extract container image name and check if RStudio is expected to be installed
    image_name = package_helper.running_container.image.tags[0].lower() if package_helper.running_container.image.tags else ""
    # Skip test for base and mid images that don't include RStudio
    if 'base' in image_name or 'mid' in image_name:
        pytest.skip("RStudio not available in this image, skipping RStudio test")


def _select_system_r(package_helper):
    result = _execute_on_container(
        package_helper,
        [
            "bash",
            "-lc",
            'mkdir -p "$HOME/.local/share/rstudio" && '
            'printf "system\\n" > "$HOME/.local/share/rstudio/active_conda_env"',
        ],
    )
    assert result.exit_code == 0, result.output.decode("utf-8", errors="replace")


def test_system_r_rsession_reticulate_openssl(package_helper):
    _skip_if_no_rstudio(package_helper)
    _select_system_r(package_helper)

    script = r'''
stopifnot(as.character(getRversion()) == "4.6.1")
suppressPackageStartupMessages({
  library(gert)
  library(curl)
  library(openssl)
  library(reticulate)
})

libgit2 <- gert::libgit2_config()
stopifnot(
  length(libgit2$version) == 1L,
  nzchar(as.character(libgit2$version)),
  libgit2$version >= package_version("1.7.0")
)

curl_config <- curl::curl_version()
stopifnot(
  length(curl_config$version) == 1L,
  nzchar(curl_config$version),
  length(curl_config$ssl_version) == 1L,
  nzchar(curl_config$ssl_version),
  grepl("OpenSSL", curl_config$ssl_version, fixed = TRUE)
)

digest <- openssl::sha256(charToRaw("rstudio-openssl-compatibility"))
stopifnot(identical(
  unclass(as.character(digest)),
  "3d9fc8c3a1b7ee6a0b817bf0fea558bfd732230d3ea19cd3da8633694178f24e"
))
cat("RSESSION_NATIVE_R_OK\\n")

cfg <- py_config()
stopifnot(dirname(normalizePath(cfg$python)) == "/opt/conda/bin")
py_run_string(
  "import ssl, sys; "
  "assert sys.version_info[:3] == (3, 14, 5); "
  "assert ssl.OPENSSL_VERSION.startswith('OpenSSL 3.6.3')"
)
maps <- readLines("/proc/self/maps")
for (soname in c("libssl.so.3", "libcrypto.so.3")) {
  hits <- maps[grepl(paste0("/", soname), maps, fixed = TRUE)]
  stopifnot(
    length(hits) > 0,
    all(grepl("/opt/conda/lib/", hits, fixed = TRUE))
  )
}
cat("RSESSION_RETICULATE_OK\\n")
quit(save = "no", status = 0)
'''.strip()

    result = package_helper.running_container.exec_run(
        [
            "/opt/jupyter-custom-rstudio-proxy/rsession.sh",
            f"--run-script={script}",
        ],
        environment={"LD_LIBRARY_PATH": "/usr/lib/R/lib"},
    )
    output = result.output.decode("utf-8", errors="replace")

    assert result.exit_code == 0, output
    assert "RSESSION_NATIVE_R_OK" in output
    assert "RSESSION_RETICULATE_OK" in output


def test_conda_r_rsession_activation_environment(package_helper):
    _skip_if_no_rstudio(package_helper)

    setup = _execute_on_container(
        package_helper,
        [
            "bash",
            "-lc",
            'set -euo pipefail; '
            'prefix="$(mktemp -d "$HOME/rstudio-conda-smoke.XXXXXX")"; '
            'mkdir -p "$prefix/bin" "$prefix/conda-meta" '
            '"$prefix/lib/R/library" "$HOME/.local/share/rstudio"; '
            'touch "$prefix/conda-meta/history"; '
            'ln -s /usr/bin/R "$prefix/bin/R"; '
            'ln -s /opt/conda/bin/python "$prefix/bin/python"; '
            'printf "%s\\n" "$prefix" '
            '> "$HOME/.local/share/rstudio/active_conda_env"; '
            'printf "%s" "$prefix"',
        ],
    )
    assert setup.exit_code == 0, setup.output.decode("utf-8", errors="replace")
    conda_prefix = setup.output.decode("utf-8", errors="replace")

    script = r'''
prefix <- Sys.getenv("CONDA_PREFIX")
expected <- Sys.getenv("EXPECTED_CONDA_PREFIX")
stopifnot(
  nzchar(prefix),
  identical(normalizePath(prefix), normalizePath(expected)),
  identical(Sys.getenv("RETICULATE_PYTHON"), file.path(prefix, "bin", "python")),
  identical(Sys.getenv("R_LIBS_USER"), file.path(prefix, "lib", "R", "library")),
  identical(Sys.getenv("R_LIBS_SITE"), file.path(prefix, "lib", "R", "library")),
  identical(unname(Sys.which("R")), file.path(prefix, "bin", "R"))
)
cat("RSESSION_CONDA_R_ENV_OK\\n")
quit(save = "no", status = 0)
'''.strip()

    result = package_helper.running_container.exec_run(
        [
            "/opt/jupyter-custom-rstudio-proxy/rsession.sh",
            f"--run-script={script}",
        ],
        environment={
            "EXPECTED_CONDA_PREFIX": conda_prefix,
            "LD_LIBRARY_PATH": "/usr/lib/R/lib",
        },
    )
    output = result.output.decode("utf-8", errors="replace")

    assert result.exit_code == 0, output
    assert f"Activated Conda env: {conda_prefix}" in output
    assert "RSESSION_CONDA_R_ENV_OK" in output


def test_system_r_rsession_fails_without_conda_openssl_pair(package_helper):
    _skip_if_no_rstudio(package_helper)
    _select_system_r(package_helper)

    libssl = "/opt/conda/lib/libssl.so.3"
    hidden_libssl = f"{libssl}.test-hidden"
    move = package_helper.running_container.exec_run(
        ["mv", libssl, hidden_libssl], user="root"
    )
    assert move.exit_code == 0, move.output.decode("utf-8", errors="replace")

    try:
        result = package_helper.running_container.exec_run(
            [
                "/opt/jupyter-custom-rstudio-proxy/rsession.sh",
                '--run-script=quit(save = "no", status = 0)',
            ],
            environment={"LD_LIBRARY_PATH": "/usr/lib/R/lib"},
        )
        output = result.output.decode("utf-8", errors="replace")
        assert result.exit_code != 0, output
        assert f"Required Conda OpenSSL library is not readable: {libssl}" in output
    finally:
        restore = package_helper.running_container.exec_run(
            ["mv", hidden_libssl, libssl], user="root"
        )
        assert restore.exit_code == 0, restore.output.decode(
            "utf-8", errors="replace"
        )


def test_rstudio(package_helper):
    # Skip this test for images that don't have rstudio-server
    _skip_if_no_rstudio(package_helper)
    
    # Attempt to start RStudio server
    result = _execute_on_container(package_helper, ["rstudio-server", "start"])
    LOGGER.info(f"starting up rstudio: {result}")
    if result.exit_code != 0:
        # If rstudio-server command is not found, skip the test
        if "executable file not found" in result.output.decode("utf-8"):
            pytest.skip("rstudio-server not found in PATH, skipping RStudio test")
    
    # Verify that RStudio server started successfully
    assert(result.exit_code==0)

    # Verify RStudio version matches expected version
    result = _execute_on_container(package_helper, ["rstudio-server", "version"])
    LOGGER.info(f"rstudio version: {result}")
    assert(EXPECTED in result.output.decode("utf-8"))


def test_custom_rstudio_proxy(package_helper):
    _skip_if_no_rstudio(package_helper)

    # Verify custom RStudio proxy module can be imported
    result = _execute_on_container(package_helper, ["python", "-c", "import jupyter_custom_rstudio_proxy"])
    assert result.exit_code == 0, result.output.decode("utf-8")

    # Verify RStudio conda helper script exists and is executable
    result = _execute_on_container(package_helper, ["test", "-x", "/usr/local/bin/rstudio-use-current-conda"])
    assert result.exit_code == 0, "rstudio-use-current-conda helper is missing or not executable"
 

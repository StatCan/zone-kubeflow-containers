import json
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


def _r_environment(package_helper, r_executable):
    expression = (
        'paths <- c(R_HOME = R.home(), R_SHARE_DIR = R.home("share"), '
        'R_INCLUDE_DIR = R.home("include"), R_DOC_DIR = R.home("doc")); '
        'cat(paste("RSESSION_R_ENV", names(paths), paths, sep = "\\t"), '
        'sep = "\\n")'
    )
    result = _execute_on_container(
        package_helper,
        [r_executable, "--vanilla", "--slave", "-e", expression],
    )
    output = result.output.decode("utf-8", errors="replace")
    assert result.exit_code == 0, output

    expected_names = {"R_HOME", "R_SHARE_DIR", "R_INCLUDE_DIR", "R_DOC_DIR"}
    environment = {}
    for line in output.splitlines():
        if not line.startswith("RSESSION_R_ENV\t"):
            continue
        _, name, value = line.split("\t", 2)
        assert name in expected_names, output
        assert name not in environment, output
        assert value, output
        environment[name] = value

    assert environment.keys() == expected_names, output
    return environment


def _write_rsession_script(package_helper, script):
    result = package_helper.running_container.exec_run(
        [
            "bash",
            "-c",
            'set -euo pipefail; '
            'script_path="$(mktemp "${HOME}/rstudio-rsession-test.XXXXXX.R")"; '
            'printf "%s" "$RSESSION_TEST_SCRIPT_CONTENT" > "$script_path"; '
            'chmod 0600 "$script_path"; '
            'printf "%s" "$script_path"',
        ],
        environment={"RSESSION_TEST_SCRIPT_CONTENT": script},
    )
    output = result.output.decode("utf-8", errors="replace")
    assert result.exit_code == 0, output
    assert output.startswith("/") and "\n" not in output, output
    return output


def test_system_r_rsession_reticulate_openssl(package_helper):
    _skip_if_no_rstudio(package_helper)
    _select_system_r(package_helper)
    r_environment = _r_environment(package_helper, "/usr/bin/R")

    script = r'''
cat("RSESSION_SCRIPT_ENTERED\\n")
stopifnot(as.character(getRversion()) == "4.6.1")
suppressPackageStartupMessages({
  library(arrow)
  library(hdf5r)
  library(gert)
  library(curl)
  library(openssl)
  library(reticulate)
})

check_native_r <- function(stage) {
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

  arrow_table <- arrow::Table$create(values = c(2L, 4L, 6L))
  stopifnot(identical(
    as.integer(as.data.frame(arrow_table)$values),
    c(2L, 4L, 6L)
  ))

  h5_path <- tempfile("rstudio-reticulate-r-", fileext = ".h5")
  h5_file <- hdf5r::H5File$new(h5_path, mode = "w")
  h5_file[["values"]] <- c(3L, 6L, 9L)
  h5_values <- as.integer(h5_file[["values"]][])
  h5_file$close_all()
  unlink(h5_path)
  stopifnot(identical(h5_values, c(3L, 6L, 9L)))

  cat(paste0("RSESSION_NATIVE_R_", stage, "_PYTHON_OK\\n"))
}

check_native_r("BEFORE")

cfg <- py_config()
stopifnot(dirname(normalizePath(cfg$python)) == "/opt/conda/bin")
compat_paths <- strsplit(Sys.getenv("PYTHONPATH"), ":", fixed = TRUE)[[1]]
stopifnot(identical(
  compat_paths[1:2],
  c(
    "/opt/reticulate-compat/lib/python3.14/lib-dynload",
    "/opt/reticulate-compat/lib/python3.14/site-packages"
  )
))

python_code <- paste(c(
  'import hashlib',
  'import importlib',
  'import importlib.metadata',
  'import os',
  'import ssl',
  'import sys',
  'import tempfile',
  'import uuid',
  'import cryptography',
  'import duckdb',
  'import h5py',
  'import numpy as np',
  'import pandas as pd',
  'import pyarrow as pa',
  'import pyarrow.parquet as pq',
  'import requests',
  'import rpy2.robjects as ro',
  'import scipy.linalg',
  'import sklearn.preprocessing',
  'import tables',
  'import zmq',
  'import zstandard',
  'from cryptography.hazmat.primitives.ciphers.aead import AESGCM',
  'import _hashlib',
  'import _ssl',
  'assert sys.version_info[:3] == (3, 14, 5)',
  'assert ssl.OPENSSL_VERSION.startswith("OpenSSL 3.0.")',
  'assert hashlib.sha256(b"rstudio-reticulate-overlay").hexdigest() == "7cecc4efd759f150d257e7baa8c46ce27a93f9aef32224e5b077df66af4d4621"',
  'overlay = "/opt/reticulate-compat/"',
  'overlay_modules = (_ssl, _hashlib, cryptography, h5py, pa, tables, zmq, zstandard)',
  'for module in overlay_modules:',
  '    location = os.path.realpath(module.__file__)',
  '    assert location.startswith(overlay), (module.__name__, location)',
  'key = bytes(range(16))',
  'nonce = bytes(range(12))',
  'ciphertext = AESGCM(key).encrypt(nonce, b"reticulate", b"rstudio")',
  'assert AESGCM(key).decrypt(nonce, ciphertext, b"rstudio") == b"reticulate"',
  'payload = b"system-r-reticulate-zstandard" * 8',
  'compressed = zstandard.ZstdCompressor(level=3).compress(payload)',
  'assert zstandard.ZstdDecompressor().decompress(compressed) == payload',
  'assert importlib.metadata.version("rpy2") == "3.6.7"',
  'assert ro.r("sum(c(2L,4L,6L))")[0] == 12',
  'assert np.array([1, 2, 3], dtype=np.int64).sum() == 6',
  'assert pd.DataFrame({"value": [1, 2, 3]})["value"].sum() == 6',
  'assert scipy.linalg.det(np.eye(2)) == 1.0',
  'assert sklearn.preprocessing.StandardScaler().fit_transform([[1.0], [3.0]]).shape == (2, 1)',
  'prepared = requests.Request("GET", "https://example.invalid/compatibility").prepare()',
  'assert prepared.url == "https://example.invalid/compatibility"',
  'connection = duckdb.connect(":memory:")',
  'assert connection.execute("select sum(i) from range(4) t(i)").fetchone()[0] == 6',
  'connection.close()',
  'for module_name in ("adlfs", "azure.identity", "banff", "banffprocessor", "dvc", "dvc_azure", "kubeflow.training", "pyodbc", "pyspark", "s3fs", "zone_token_broker"):',
  '    module = importlib.import_module(module_name)',
  '    location = getattr(module, "__file__", None)',
  '    namespace_paths = list(getattr(module, "__path__", ()))',
  '    assert location or namespace_paths, module_name',
  'with tempfile.TemporaryDirectory(prefix="rstudio-reticulate-python-") as directory:',
  '    parquet_path = os.path.join(directory, "values.parquet")',
  '    parquet_table = pa.table({"value": [2, 4, 6]})',
  '    pq.write_table(parquet_table, parquet_path)',
  '    assert pq.read_table(parquet_path)["value"].to_pylist() == [2, 4, 6]',
  '    h5py_path = os.path.join(directory, "h5py.h5")',
  '    with h5py.File(h5py_path, "w") as handle:',
  '        handle.create_dataset("value", data=np.array([3, 6, 9]))',
  '    with h5py.File(h5py_path, "r") as handle:',
  '        assert handle["value"][:].tolist() == [3, 6, 9]',
  '    tables_path = os.path.join(directory, "tables.h5")',
  '    with tables.open_file(tables_path, mode="w") as handle:',
  '        values = handle.create_array("/", "value", obj=np.array([5, 10, 15]))',
  '        assert values[:].tolist() == [5, 10, 15]',
  'context = zmq.Context()',
  'left = context.socket(zmq.PAIR)',
  'right = context.socket(zmq.PAIR)',
  'endpoint = "inproc://rstudio-reticulate-" + uuid.uuid4().hex',
  'left.bind(endpoint)',
  'right.connect(endpoint)',
  'right.send(b"reticulate-zmq")',
  'assert left.recv() == b"reticulate-zmq"',
  'left.close(0)',
  'right.close(0)',
  'context.term()'
), collapse = "\n")
py_run_string(python_code)

maps <- readLines("/proc/self/maps")
for (soname in c("libssl.so.3", "libcrypto.so.3")) {
  hits <- maps[grepl(paste0("/", soname), maps, fixed = TRUE)]
  stopifnot(
    length(hits) > 0,
    !any(grepl("/opt/conda/", hits, fixed = TRUE)),
    all(
      grepl("/usr/lib/x86_64-linux-gnu/", hits, fixed = TRUE) |
      grepl("/lib/x86_64-linux-gnu/", hits, fixed = TRUE)
    )
  )
}

cat("RSESSION_PYTHON_OVERLAY_OK\\n")
check_native_r("AFTER")
cat("RSESSION_RETICULATE_OVERLAY_OK\\n")
quit(save = "no", status = 0)
'''.strip()

    script_path = _write_rsession_script(package_helper, script)
    try:
        result = package_helper.running_container.exec_run(
            [
                "/opt/jupyter-custom-rstudio-proxy/rsession.sh",
                "--log-stderr=1",
                (
                    "--run-script=source("
                    'Sys.getenv("RSESSION_TEST_SCRIPT_PATH"), echo = FALSE)'
                ),
            ],
            environment={
                **r_environment,
                "LD_LIBRARY_PATH": "/usr/lib/R/lib",
                "RSESSION_TEST_SCRIPT_PATH": script_path,
            },
        )
        output = result.output.decode("utf-8", errors="replace")
    finally:
        cleanup = package_helper.running_container.exec_run(
            ["rm", "-f", "--", script_path]
        )

    assert cleanup.exit_code == 0, cleanup.output.decode(
        "utf-8", errors="replace"
    )

    assert result.exit_code == 0, output
    assert "RSESSION_SCRIPT_ENTERED" in output
    assert "RSESSION_NATIVE_R_BEFORE_PYTHON_OK" in output
    assert "RSESSION_PYTHON_OVERLAY_OK" in output
    assert "RSESSION_NATIVE_R_AFTER_PYTHON_OK" in output
    assert "RSESSION_RETICULATE_OVERLAY_OK" in output


def test_standalone_conda_python_ignores_reticulate_overlay(package_helper):
    _skip_if_no_rstudio(package_helper)

    code = r'''
import gc
import importlib.metadata
import os
import ssl
import sys

import _hashlib
import _ssl
import cryptography
import h5py
import libmambapy
import pyarrow
import rattler
import tables
import zmq
import zstandard

assert sys.version_info[:3] == (3, 14, 5)
assert ssl.OPENSSL_VERSION.startswith("OpenSSL 3.6.3")
assert "/opt/reticulate-compat" not in os.environ.get("PYTHONPATH", "")
assert libmambapy.__version__ == importlib.metadata.version("libmambapy")
context = libmambapy.Context()
virtual_packages = libmambapy.get_virtual_packages(context)
assert {str(package) for package in virtual_packages} == {"__unix", "__linux", "__glibc", "__archspec"}
spec = libmambapy.specs.MatchSpec.parse("python >=3.14")
assert str(spec) == "python>=3.14", str(spec)
del spec, virtual_packages, context
gc.collect()
for module in (
    _ssl,
    _hashlib,
    cryptography,
    h5py,
    pyarrow,
    rattler,
    tables,
    zmq,
    zstandard,
    libmambapy,
):
    location = os.path.realpath(module.__file__)
    assert location.startswith("/opt/conda/"), (module.__name__, location)
    assert not location.startswith("/opt/reticulate-compat/"), location
print("LIBMAMBAPY_VERSION=" + libmambapy.__version__)
'''.strip()
    result = _execute_on_container(
        package_helper,
        ["/opt/conda/bin/python", "-I", "-c", code],
    )
    standalone_output = result.output.decode("utf-8", errors="replace")
    assert result.exit_code == 0, standalone_output
    version_lines = [
        line.removeprefix("LIBMAMBAPY_VERSION=")
        for line in standalone_output.splitlines()
        if line.startswith("LIBMAMBAPY_VERSION=")
    ]
    assert len(version_lines) == 1 and version_lines[0], standalone_output
    libmambapy_version = version_lines[0]

    mamba = _execute_on_container(
        package_helper,
        ["/opt/conda/bin/mamba", "info", "--json"],
    )
    mamba_output = mamba.output.decode("utf-8", errors="replace").strip()
    assert mamba.exit_code == 0, mamba_output
    mamba_info = json.loads(mamba_output)
    assert mamba_info.get("mamba version") == libmambapy_version, mamba_info
    assert mamba_info.get("libmamba version") == libmambapy_version, mamba_info


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
    r_environment = _r_environment(package_helper, f"{conda_prefix}/bin/R")

    script = r'''
cat("RSESSION_SCRIPT_ENTERED\\n")
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
            "--log-stderr=1",
            f"--run-script={script}",
        ],
        environment={
            **r_environment,
            "EXPECTED_CONDA_PREFIX": conda_prefix,
            "LD_LIBRARY_PATH": "/usr/lib/R/lib",
        },
    )
    output = result.output.decode("utf-8", errors="replace")

    assert result.exit_code == 0, output
    assert "RSESSION_SCRIPT_ENTERED" in output
    assert f"Activated Conda env: {conda_prefix}" in output
    assert "RSESSION_CONDA_R_ENV_OK" in output


@pytest.mark.parametrize(
    "required_path",
    [
        "/opt/reticulate-compat/.audit-passed",
        (
            "/opt/reticulate-compat/lib/python3.14/lib-dynload/"
            "_ssl.cpython-314-x86_64-linux-gnu.so"
        ),
        (
            "/opt/reticulate-compat/lib/python3.14/lib-dynload/"
            "_hashlib.cpython-314-x86_64-linux-gnu.so"
        ),
    ],
)
def test_system_r_rsession_fails_without_reticulate_compat_path(
    package_helper, required_path
):
    _skip_if_no_rstudio(package_helper)
    _select_system_r(package_helper)
    r_environment = _r_environment(package_helper, "/usr/bin/R")

    hidden_path = f"{required_path}.test-hidden"
    move = package_helper.running_container.exec_run(
        ["mv", required_path, hidden_path], user="root"
    )
    assert move.exit_code == 0, move.output.decode("utf-8", errors="replace")

    try:
        result = package_helper.running_container.exec_run(
            [
                "/opt/jupyter-custom-rstudio-proxy/rsession.sh",
                "--log-stderr=1",
                '--run-script=quit(save = "no", status = 0)',
            ],
            environment={
                **r_environment,
                "LD_LIBRARY_PATH": "/usr/lib/R/lib",
            },
        )
        output = result.output.decode("utf-8", errors="replace")
        assert result.exit_code != 0, output
        assert (
            f"Required reticulate compatibility path is not readable: "
            f"{required_path}"
        ) in output
    finally:
        restore = package_helper.running_container.exec_run(
            ["mv", hidden_path, required_path], user="root"
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
 

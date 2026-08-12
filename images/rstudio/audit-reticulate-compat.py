#!/usr/bin/env python3
"""Fail closed when the system-R reticulate compatibility overlay drifts."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys


PYTHON_VERSION = "3.14"
PYTHON_ABI = "cpython-314-x86_64-linux-gnu"
EXPECTED_VERSIONS = {
    "cryptography": "50.0.0",
    "h5py": "3.16.0",
    "py-rattler": "0.25.0",
    "pyarrow": "25.0.0",
    "pyzmq": "27.1.0",
    "tables": "3.11.1",
    "zstandard": "0.25.0",
}
EXPECTED_CONDA_OPENSSL_ROOTS = {
    "_hashlib",
    "_ssl",
    "cryptography",
    "h5py",
    "libmambapy",
    "pyarrow",
    "rattler",
    "rpy2",
    "tables",
    "zmq",
}
STANDALONE_ONLY_ROOTS = {"libmambapy"}
SYSTEM_R_PROVIDED_ROOTS = {"rpy2"}
OVERLAID_OPENSSL_ROOTS = EXPECTED_CONDA_OPENSSL_ROOTS - (
    STANDALONE_ONLY_ROOTS | SYSTEM_R_PROVIDED_ROOTS
)


def fail(message: str) -> None:
    raise SystemExit(f"reticulate compatibility audit failed: {message}")


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def distribution_versions(site_packages: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in importlib.metadata.distributions(path=[str(site_packages)]):
        name = distribution.metadata.get("Name")
        if name:
            versions[canonical_name(name)] = distribution.version
    return versions


def is_loadable_elf(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("rb") as stream:
            header = stream.read(18)
    except OSError:
        return False
    if len(header) != 18 or header[:4] != b"\x7fELF":
        return False
    byte_order = {1: "little", 2: "big"}.get(header[5])
    if byte_order is None:
        return False
    elf_type = int.from_bytes(header[16:18], byteorder=byte_order)
    return elf_type in {2, 3}  # ET_EXEC or ET_DYN; ldd cannot inspect ET_REL.


def elf_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if is_loadable_elf(path))


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        fail(f"{' '.join(command)} exited {result.returncode}:\n{result.stdout}")
    return result.stdout


def ldd(path: Path, *, library_path: str | None) -> str:
    environment = os.environ.copy()
    if library_path is None:
        environment.pop("LD_LIBRARY_PATH", None)
    else:
        environment["LD_LIBRARY_PATH"] = library_path
    return run(["/usr/bin/ldd", str(path)], env=environment)


def ldd_targets(output: str) -> dict[str, Path]:
    """Return SONAME-to-canonical-target mappings from ldd output."""
    targets: dict[str, Path] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "not found" in line:
            continue
        if "=>" in line:
            soname, target = (part.strip() for part in line.split("=>", 1))
            target = target.split(" (", 1)[0].strip()
        else:
            target = line.split(" (", 1)[0].strip()
            if not target.startswith("/"):
                continue
            soname = Path(target).name
        if target.startswith("/"):
            targets[soname] = Path(target).resolve(strict=False)
    return targets


def conda_root(path: Path, python_root: Path) -> str:
    relative = path.relative_to(python_root)
    if relative.parts[0] == "lib-dynload":
        return path.name.split(".", 1)[0]
    if relative.parts[0] != "site-packages" or len(relative.parts) < 2:
        return relative.parts[0]
    first = relative.parts[1]
    if first.startswith("_cffi_backend"):
        return "cryptography"
    if first.startswith("_rinterface_cffi_api"):
        return "rpy2"
    return first.removesuffix(".libs").split(".", 1)[0]


def audit_versions(conda_site: Path, overlay_site: Path) -> None:
    conda_versions = distribution_versions(conda_site)
    overlay_versions = distribution_versions(overlay_site)
    for name, expected in EXPECTED_VERSIONS.items():
        canonical = canonical_name(name)
        conda_version = conda_versions.get(canonical)
        overlay_version = overlay_versions.get(canonical)
        if conda_version != expected:
            fail(
                f"Conda {name} version is {conda_version!r}, expected {expected!r}"
            )
        if overlay_version != conda_version:
            fail(
                f"overlay {name} version is {overlay_version!r}, "
                f"Conda has {conda_version!r}"
            )


def audit_abi_modules(overlay_dynload: Path) -> tuple[Path, Path]:
    expected = []
    for module in ("_ssl", "_hashlib"):
        matches = sorted(overlay_dynload.glob(f"{module}.*.so"))
        expected_name = f"{module}.{PYTHON_ABI}.so"
        if [path.name for path in matches] != [expected_name]:
            fail(
                f"expected exactly {expected_name}, found "
                f"{[path.name for path in matches]}"
            )
        expected.append(matches[0])
    return expected[0], expected[1]


def audit_conda_graph(conda_prefix: Path, conda_python_root: Path) -> None:
    roots: set[str] = set()
    conda_library_path = str(conda_prefix / "lib")
    conda_openssl = {
        (conda_prefix / "lib" / soname).resolve(strict=False)
        for soname in ("libssl.so.3", "libcrypto.so.3")
    }
    for path in elf_files(conda_python_root):
        targets = set(
            ldd_targets(ldd(path, library_path=conda_library_path)).values()
        )
        if targets & conda_openssl:
            roots.add(conda_root(path, conda_python_root))

    if roots != EXPECTED_CONDA_OPENSSL_ROOTS:
        fail(
            "Conda OpenSSL dependency roots changed: "
            f"found {sorted(roots)}, expected {sorted(EXPECTED_CONDA_OPENSSL_ROOTS)}"
        )
    coverage = (
        OVERLAID_OPENSSL_ROOTS
        | STANDALONE_ONLY_ROOTS
        | SYSTEM_R_PROVIDED_ROOTS
    )
    if coverage != EXPECTED_CONDA_OPENSSL_ROOTS:
        fail(
            "compatibility coverage does not equal the audited roots: "
            f"covered {sorted(coverage)}, expected "
            f"{sorted(EXPECTED_CONDA_OPENSSL_ROOTS)}"
        )


def audit_overlay_graph(
    overlay_root: Path, ssl_module: Path, hashlib_module: Path, conda_prefix: Path
) -> None:
    conda_prefix = conda_prefix.resolve(strict=False)
    system_openssl = {
        Path("/usr/lib/x86_64-linux-gnu/libssl.so.3").resolve(strict=False),
        Path("/usr/lib/x86_64-linux-gnu/libcrypto.so.3").resolve(strict=False),
    }
    for path in elf_files(overlay_root):
        dependencies = ldd(path, library_path=None)
        if "not found" in dependencies:
            fail(f"unresolved dependency for {path}:\n{dependencies}")
        targets = ldd_targets(dependencies)
        conda_targets = [
            target
            for target in targets.values()
            if target == conda_prefix or conda_prefix in target.parents
        ]
        if conda_targets:
            fail(f"{path} resolves a dependency through {conda_prefix}:\n{dependencies}")

        openssl_targets = {
            target
            for soname, target in targets.items()
            if soname in {"libssl.so.3", "libcrypto.so.3"}
        }
        if path in (ssl_module, hashlib_module):
            if not openssl_targets:
                fail(f"{path.name} did not resolve system OpenSSL")
            if not openssl_targets <= system_openssl:
                fail(
                    f"{path.name} did not resolve only Ubuntu OpenSSL: "
                    f"{sorted(map(str, openssl_targets))}"
                )
        elif openssl_targets:
            fail(
                f"wheel ELF {path} unexpectedly resolves OpenSSL: "
                f"{sorted(map(str, openssl_targets))}"
            )

    for module in (ssl_module, hashlib_module):
        version_info = run(["/usr/bin/readelf", "--version-info", str(module)])
        versions = set(re.findall(r"OPENSSL_[0-9.]+", version_info))
        if versions != {"OPENSSL_3.0.0"}:
            fail(f"{module.name} requires OpenSSL symbol versions {sorted(versions)}")


def audit_imports(conda_python: Path, overlay_python_root: Path) -> None:
    code = r'''
import importlib
import os
import sys

overlay = sys.argv[1]
sys.path.insert(0, overlay + "/site-packages")
sys.path.insert(0, overlay + "/lib-dynload")
ssl = importlib.import_module("ssl")
importlib.import_module("hashlib")
modules = [
    importlib.import_module("_ssl"),
    importlib.import_module("_hashlib"),
    importlib.import_module("cryptography"),
    importlib.import_module("h5py"),
    importlib.import_module("pyarrow"),
    importlib.import_module("rattler"),
    importlib.import_module("tables"),
    importlib.import_module("zmq"),
    importlib.import_module("zstandard"),
]
for module in modules:
    location = getattr(module, "__file__", "")
    if not location.startswith(overlay + "/"):
        raise SystemExit(f"{module.__name__} escaped overlay: {location}")
if not ssl.OPENSSL_VERSION.startswith("OpenSSL 3.0."):
    raise SystemExit(f"unexpected embedded OpenSSL: {ssl.OPENSSL_VERSION}")
rinterface = importlib.import_module("_rinterface_cffi_api")
if not os.path.realpath(rinterface.__file__).startswith(sys.prefix + "/"):
    raise SystemExit(f"rpy2 CFFI module escaped Conda: {rinterface.__file__}")
'''
    system_libraries = [
        Path("/usr/lib/x86_64-linux-gnu/libcrypto.so.3"),
        Path("/usr/lib/x86_64-linux-gnu/libssl.so.3"),
    ]
    missing = [str(path) for path in system_libraries if not path.is_file()]
    if missing:
        fail(f"Ubuntu OpenSSL audit inputs are missing: {missing}")
    environment = os.environ.copy()
    environment["LD_PRELOAD"] = ":".join(str(path) for path in system_libraries)
    environment["R_HOME"] = "/usr/lib/R"
    environment["LD_LIBRARY_PATH"] = "/usr/lib/R/lib"
    run(
        [str(conda_python), "-I", "-c", code, str(overlay_python_root)],
        env=environment,
    )


def audit_standalone_package_manager(conda_prefix: Path) -> None:
    code = r'''
import gc
import importlib.metadata
import libmambapy

if libmambapy.__version__ != importlib.metadata.version("libmambapy"):
    raise SystemExit("libmambapy runtime and distribution versions differ")
context = libmambapy.Context()
virtual_packages = libmambapy.get_virtual_packages(context)
if {str(package) for package in virtual_packages} != {
    "__unix", "__linux", "__glibc", "__archspec"
}:
    raise SystemExit(f"unexpected virtual packages: {virtual_packages}")
spec = libmambapy.specs.MatchSpec.parse("python >=3.14")
if str(spec) != "python>=3.14":
    raise SystemExit(f"unexpected libmambapy spec: {spec}")
del spec, virtual_packages, context
gc.collect()
'''
    environment = os.environ.copy()
    for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONPATH"):
        environment.pop(name, None)
    run(
        [str(conda_prefix / "bin" / "python"), "-I", "-c", code],
        env=environment,
    )
    try:
        mamba_info = json.loads(
            run([str(conda_prefix / "bin" / "mamba"), "info", "--json"], env=environment)
        )
    except json.JSONDecodeError as error:
        fail(f"mamba info --json returned invalid JSON: {error}")
    expected_version = importlib.metadata.version("libmambapy")
    for key in ("mamba version", "libmamba version"):
        if mamba_info.get(key) != expected_version:
            fail(
                f"mamba info {key!r} is {mamba_info.get(key)!r}, "
                f"expected {expected_version!r}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conda-prefix", type=Path, required=True)
    parser.add_argument("--overlay-root", type=Path, required=True)
    args = parser.parse_args()

    conda_prefix = args.conda_prefix.resolve()
    overlay_root = args.overlay_root.resolve()
    conda_python_root = conda_prefix / "lib" / f"python{PYTHON_VERSION}"
    conda_site = conda_python_root / "site-packages"
    overlay_python_root = overlay_root / "lib" / f"python{PYTHON_VERSION}"
    overlay_site = overlay_python_root / "site-packages"
    overlay_dynload = overlay_python_root / "lib-dynload"

    audit_versions(conda_site, overlay_site)
    ssl_module, hashlib_module = audit_abi_modules(overlay_dynload)
    audit_conda_graph(conda_prefix, conda_python_root)
    audit_overlay_graph(overlay_root, ssl_module, hashlib_module, conda_prefix)
    audit_imports(conda_prefix / "bin" / "python", overlay_python_root)
    audit_standalone_package_manager(conda_prefix)
    print(
        "reticulate compatibility audit passed; the overlay and system R cover "
        "the embedded surface, and standalone Conda covers package-manager internals"
    )


if __name__ == "__main__":
    main()

# R 4.6 and Python 3.14 Reticulate Compatibility Design

## Goal and scope

PR #292 (`feat/python-3.14`, base `beta`) remains the canonical pull request
for system R 4.6.1, Conda Python 3.14.5, restored R package parity, and the
mixed-runtime compatibility correction. The result must preserve standalone
system R, standalone `/opt/conda` Python, RStudio, Jupyter kernels, reticulate,
rpy2, and user-selected Conda-R environments.

The compatibility overlay is RStudio-specific and is built in
`images/rstudio/Dockerfile`. Base, mid, and Jupyter images retain their
standalone Conda Python runtime unchanged.

RStudio's system-R process is the failing boundary and the only behavior this
design changes. Terminal and VSCode sessions that invoke reticulate without
setting `RETICULATE_PYTHON` continue to use their pre-existing
reticulate/uv interpreter auto-discovery behavior; changing or guaranteeing
that behavior is out of scope. Standalone Python and language-bridge checks
are non-regression controls, not an expansion of the incident boundary.

## Evidence that rejected the preload design

System RStudio loads Ubuntu OpenSSL 3.0 before reticulate embeds
`/opt/conda/bin/python`. Conda Python 3.14.5's `_ssl` requires newer Conda
OpenSSL symbols, so loading its unmodified extension into that process fails.

The first proposed correction preloaded Conda
`libcrypto.so.3`/`libssl.so.3` process-wide. Exact CI falsified that design.
At head `a07bccb88950eb8114b2d5ae26cc74905a325a59`, GitHub Actions run
`31598508807` reached the R banner and then the real system-R
`rsession --run-script` probe exited with status 139 before
`RSESSION_SCRIPT_ENTERED`. The same failure propagated through RStudio-bearing
downstream test jobs. The no-preload synthetic Conda-R control and the
fail-closed wrapper probe did not show that crash. A process-wide Conda
OpenSSL pair therefore is not a safe compatibility boundary for native
RStudio and R packages and must not be restored.

## Compatibility-overlay architecture

The RStudio image builds only CPython 3.14.5's `_ssl` and `_hashlib` extension
modules from the checksum-pinned CPython source, using Ubuntu's system
OpenSSL headers and libraries. The exact ABI artifacts are installed under:

- `/opt/reticulate-compat/lib/python3.14/lib-dynload`

Hash-pinned, self-contained manylinux wheels are installed under:

- `/opt/reticulate-compat/lib/python3.14/site-packages`

The overlay distributions are `cryptography 50.0.0`, `h5py 3.16.0`,
`pyarrow 25.0.0`, `py-rattler 0.25.0`, `pyzmq 27.1.0`, `tables 3.11.1`,
and `zstandard 0.25.0`. Each overlay version must exactly match the
corresponding installed Conda distribution, so a future package upgrade fails
the image build instead of leaving a stale RStudio-only runtime.

Only the `system` branch of
`images/rstudio/customRStu/rsession.sh` selects the overlay. It retains
`RETICULATE_PYTHON=/opt/conda/bin/python`, prepends the two overlay directories
to `PYTHONPATH`, and validates the build-audit sentinel plus the exact CPython
ABI module filenames before launching `rsession`. It does not set
`LD_PRELOAD`, preload either OpenSSL implementation, or add `/opt/conda/lib` to
the loader path.

`libmambapy` belongs to Conda's package-manager implementation rather than the
declared embedded-reticulate application surface. It remains installed and is
validated with standalone Conda Python and the `mamba` CLI, but it is not
imported into the system-R RStudio process.

The non-system Conda-R branch remains unchanged: it activates the selected
environment and preserves its `RETICULATE_PYTHON`, `R_LIBS_USER`,
`R_LIBS_SITE`, and loader behavior.

## Audited dependency closure and fail-closed gates

The final installed Python ELF graph has ten normalized roots that reach
Conda OpenSSL:

- Overlay: `_ssl`, `_hashlib`, `cryptography`, `h5py`, `pyarrow`, `rattler`,
  `tables`, and `zmq`.
- Standalone-only package manager: `libmambapy`.
- System-R provided: `rpy2` (normalizing `_rinterface_cffi_api*`).

`rattler` retains a self-contained overlay wheel to close the audited ELF
graph, but is not treated as a declared embedded application entrypoint.

The build-time audit follows transitive `ldd` resolution, canonicalizes
resolved paths, rejects unresolved or Conda-resolved overlay dependencies,
and fails if the discovered root set or its coverage classification changes.
It also verifies:

- exact CPython 3.14 ABI filenames for `_ssl` and `_hashlib`;
- only `OPENSSL_3.0.0` requirements from the rebuilt modules;
- exact overlay-to-Conda distribution version parity;
- system-only OpenSSL resolution for the rebuilt modules;
- no unexpected OpenSSL dependency from a wheel ELF;
- embedded import and offline operation with Ubuntu crypto and SSL resident;
- standalone `libmambapy` operations and exact-version parity with
  `mamba info --json`; and
- a sentinel written only after the complete audit succeeds.

The isolated build-audit subprocess preloads Ubuntu OpenSSL only to emulate
the libraries already resident in system R; that preload is not installed in
or inherited by the runtime wrapper.

`zstandard` is included because broad embedded-runtime testing exposed a
separate native zstd API collision even though it is not one of the ten
OpenSSL-reaching roots.

## Runtime verification

The regression uses the real wrapper and RStudio `rsession` process. It loads
native R `arrow`, `hdf5r`, `gert`, `curl`, and `openssl` before and after
embedding Python, performs deterministic offline R operations, and exercises
the overlay across SSL, hashing, cryptography, Arrow/Parquet, HDF5, PyTables,
ZMQ, zstandard, rpy2, representative scientific operations, and declared
user/application entrypoints. `/proc/self/maps` must contain only Ubuntu
OpenSSL for the relevant SONAMEs.

Separate controls prove standalone `/opt/conda/bin/python` still uses Conda
OpenSSL 3.6.3 and Conda package files, exercise `libmambapy`, and require the
standalone `mamba` and `libmamba` versions to match it exactly. They also prove
that a selected
non-system Conda-R environment retains its existing activation contract. These
controls detect collateral regressions; they do not change terminal or VSCode
interpreter selection. Missing the overlay sentinel or either rebuilt ABI
module makes the system branch fail closed before R starts.

## Evidence boundary

The exit-139 result above is hosted evidence for the rejected preload design.
The final no-preload overlay image has built successfully for `linux/amd64`,
in addition to passing static syntax, collection, ELF, wheel, source, and
fail-closed checks. A full system-R `Rscript`/reticulate surrogate passed the
native-R-before, embedded-Python, system-only OpenSSL map, and
native-R-after workloads on that exact image. This local surrogate does not
prove the RStudio process seam: `rsession` does not complete reliably under
the local amd64-on-arm64 Rosetta environment, so the hosted native-amd64
`rsession` test is authoritative. No exact-head hosted CI result exists for
the overlay yet. Compatibility must not be declared complete until the real
RStudio session and full hosted PR matrix are green at the pushed head.

## Addendum (2026-08-17): overlay promoted to images/mid

Beta testing showed the RStudio-only boundary above was too narrow. The
published `mid` image is user-facing, and R sessions outside RStudio --
terminal `R`/`Rscript`, the Jupyter IR kernel, and R in VSCode terminals --
embed Conda Python through reticulate with no overlay and no configured
interpreter, reproducing exactly the OpenSSL failure this design corrects
("the link between Python libraries and R is broken"). This supersedes the
earlier scope statements that the overlay is RStudio-specific and that
terminal/VSCode reticulate auto-discovery is out of scope.

The overlay build is unchanged (same CPython modules, pinned wheels, audit,
and sentinel) but now runs in `images/mid/Dockerfile`, after the final pip
installs of that image, so `/opt/reticulate-compat` is inherited by every
downstream image. Wiring splits into two independent halves:

1. Interpreter default. `/etc/R/Renviron.site` sets
   `RETICULATE_PYTHON_FALLBACK=${RETICULATE_PYTHON_FALLBACK-/opt/conda/bin/python}`
   (the guarded form keeps a pre-set value). An `Rprofile.site`
   `Sys.setenv()` block was tried first and withdrawn: RStudio's rsession is
   already multithreaded when R sources the site profile, and glibc
   `setenv()` there races concurrent `getenv()` from rsession's worker
   threads -- observed as `corrupted double-linked list` aborts in the
   embedded Python on the env-heavy sas images (an exact-content rebuild of
   the parent branch passed the same matrix, isolating the trigger to this
   block). Renviron entries are applied during early R engine
   initialisation, the same path the s6 startup script already uses safely. The fallback is reticulate's weakest hint: `RETICULATE_PYTHON`,
   `RETICULATE_PYTHON_ENV`, `use_python()`/`use_virtualenv()`, `VIRTUAL_ENV`,
   and project-local environments all outrank it, but it still outranks the
   ephemeral uv-managed environment, which is unreachable in-cluster. A hard
   `RETICULATE_PYTHON` default (and Renviron-style `${VAR-...}` defaults)
   were rejected in review: they override supported selection mechanisms and
   cannot keep the overlay coupled to the interpreter.

2. Overlay activation. A `.pth` hook inside the Conda interpreter's
   site-packages (`zone_reticulate_compat.py`) prepends the overlay to
   `sys.path` at `site` time, only when the process runs under R (`R_HOME`
   set, exported by every R front end and rsession) and the audit sentinel
   exists; `ZONE_RETICULATE_COMPAT=0` opts out. Because the hook lives in
   the cp314 interpreter itself, a foreign interpreter selected through any
   mechanism can never receive the cp314-specific modules, and the default
   interpreter cannot lose them -- the coupling is structural rather than
   environmental.

`rsession.sh` is unchanged; its fail-closed `RETICULATE_PYTHON`/`PYTHONPATH`
exports remain authoritative in RStudio, and the hook tolerates the
resulting `sys.path` duplicates. Conda-R environments read their own site
profile and are unaffected. Standalone `/opt/conda` Python without `R_HOME`
is byte-for-byte unaffected; a Conda Python spawned *from* an R session
(inheriting `R_HOME`) receives the overlay, which is import-compatible by
construction (the rebuilt modules require only `OPENSSL_3.0.0` symbol
versions, satisfied by both Ubuntu and Conda OpenSSL 3, and overlay wheel
versions are audit-pinned to the Conda ones). Known unchanged gap: a venv
derived from the Conda interpreter skips base site-packages, so under system
R it still fails on Conda `_ssl` exactly as in the RStudio-only design.

The same beta round showed the pinned VSCode Python tooling predates the
3.14 interpreter: `ms-python.python 2025.4.0` mis-drives the 3.14 PyREPL
("Run Python File" pastes the shell command into the REPL, producing
`SyntaxError`), and `ms-python.debugpy 2025.4.0` bundles a debugpy without
3.14 support. Both pins move to 3.14-capable releases (2026.4.0 / 2026.6.0),
which still target VS Code >=1.95 and therefore run on the shipped
code-server 4.99.4 without a code-server upgrade.

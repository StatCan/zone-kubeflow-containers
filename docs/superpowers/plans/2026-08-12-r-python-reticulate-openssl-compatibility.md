# R/Python Reticulate Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve system R 4.6.1 and Conda Python 3.14.5 while making the
real system-R RStudio session safely embed the declared Python application
surface.

**Architecture:** Build an RStudio-only CPython/wheel compatibility overlay
against Ubuntu OpenSSL and select it through `PYTHONPATH` only in the system-R
wrapper branch without a process-wide preload. A transitive ELF audit and
real-session tests fail closed on dependency drift. The previously
implemented process-wide Conda OpenSSL preload is rejected by exact CI exit
139 evidence and must not be restored.

**Tech Stack:** Docker, Bash, CPython 3.14.5, R 4.6.1, reticulate, rpy2,
OpenSSL 3, manylinux wheels, pytest, GitHub Actions.

## Global constraints

- Keep PR #292 (`feat/python-3.14`, base `beta`) canonical; do not merge as
  part of this plan.
- Preserve standalone `/opt/conda` Python 3.14.5 with Conda OpenSSL 3.6.3.
- Preserve the non-system Conda-R activation branch byte-for-byte.
- Never preload Conda `libcrypto.so.3` or `libssl.so.3`, add
  `/opt/conda/lib` globally, replace system libraries, or create global
  symlinks.
- Scope the overlay to the system-R RStudio branch and do not set
  `LD_PRELOAD` there.
- Treat RStudio as the failing boundary. Terminal and VSCode reticulate calls
  without `RETICULATE_PYTHON` retain their pre-existing reticulate/uv
  interpreter auto-discovery behavior and are out of scope.
- Treat standalone Python and language-bridge checks as non-regression
  controls, not new interpreter-selection guarantees.
- Preserve the restored R package list, Spark 4.2.0, Java 21, Banff, kernels,
  and downstream image behavior.
- Treat local static checks, a local image build, and hosted exact-head CI as
  separate evidence gates.

---

### Task 1: Preserve R package parity and capture the failing seam

**Files:**

- Modify: `images/mid/Dockerfile`
- Modify: `tests/general/test_r_system.py`
- Modify: `tests/general/test_rstudio.py`

**Interfaces:**

- Consumes: the PPM transaction and the real
  `/opt/jupyter-custom-rstudio-proxy/rsession.sh --run-script` seam.
- Produces: explicit package parity, broad namespace diagnostics, and runtime
  probes that enter the selected R environment.

- [x] Restore the inherited direct R package list and explicit `reticulate` in
  the existing single PPM transaction.
- [x] Add `libgit2-dev`, justified by the exact PPM `gert` binary's
  `NEEDED libgit2.so.1.7` dependency.
- [x] Make the all-installed namespace sweep report each complete loader error.
- [x] Supply `R_HOME`, `R_SHARE_DIR`, `R_INCLUDE_DIR`, and `R_DOC_DIR` to
  direct `rsession` probes, matching the environment normally injected by
  rserver.
- [x] Record the original red seam in run `31587754558`, job `94092102590`.
- [x] Record the preload falsification at head
  `a07bccb88950eb8114b2d5ae26cc74905a325a59`, run `31598508807`: the real
  system-R session exited 139 after the R banner and before the first script
  marker, while the no-preload Conda-R control did not reproduce the crash.

### Task 2: Build and audit the RStudio compatibility overlay

**Files:**

- Create: `images/rstudio/reticulate-compat-requirements.txt`
- Create: `images/rstudio/audit-reticulate-compat.py`
  (both later moved to `images/mid/` when the overlay was promoted image-wide;
  see the design addendum)
- Modify: `images/rstudio/Dockerfile`

**Interfaces:**

- Consumes: exact CPython 3.14.5 source, Ubuntu OpenSSL development files, and
  the final inherited `/opt/conda` Python graph.
- Produces: `/opt/reticulate-compat`, exact ABI modules, hash-pinned wheels,
  and `.audit-passed` only after every drift gate succeeds.

- [x] Download CPython 3.14.5 from python.org and validate SHA-256
  `7e32597b99e5d9a39abed35de4693fa169df3e5850d4c334337ffd6a19a36db6`.
- [x] Configure with `/usr/bin/pkg-config`, `--with-openssl=/usr`,
  `--with-openssl-rpath=no`, and `--without-ensurepip`; build `sharedmods`.
- [x] Install the exact
  `_ssl.cpython-314-x86_64-linux-gnu.so` and
  `_hashlib.cpython-314-x86_64-linux-gnu.so` artifacts from `Modules/`.
- [x] Install hash-pinned, no-dependency wheels for `cryptography 50.0.0`,
  `h5py 3.16.0`, `pyarrow 25.0.0`, `py-rattler 0.25.0`, `pyzmq 27.1.0`,
  `tables 3.11.1`, and `zstandard 0.25.0`.
- [x] Require every overlay distribution version to equal its installed
  Conda counterpart.
- [x] Traverse canonicalized transitive ELF resolution and require this exact
  ten-root closure:
  `_ssl`, `_hashlib`, `cryptography`, `h5py`, `pyarrow`, `rattler`,
  `tables`, `zmq`, `libmambapy`, and `rpy2`.
- [x] Classify the first eight roots as overlay-covered, `libmambapy` as a
  standalone-only package-manager root, and `rpy2` as system-R-provided;
  require the coverage union to equal the discovered set. Retain `rattler`'s
  overlay wheel as audited graph closure rather than a declared application
  entrypoint.
- [x] Reject ET_REL inputs to `ldd`, unresolved dependencies, any Conda target
  from overlay ELF, unexpected wheel OpenSSL resolution, ABI-name drift, and
  OpenSSL symbol versions other than `OPENSSL_3.0.0` in the rebuilt modules.
- [x] Run an embedded import simulation with Ubuntu crypto and SSL resident,
  plus standalone `libmambapy` operations and exact `mamba info --json`
  version parity, before writing `.audit-passed`.
- [x] Complete the local `linux/amd64` RStudio image build and retain its exact
  terminal output as evidence. This proves image construction only; it does
  not substitute for real-session execution.

### Task 3: Select the overlay only for system-R RStudio

**Files:**

- Modify: `images/rstudio/customRStu/rsession.sh`
- Modify: `tests/general/test_rstudio.py`

**Interfaces:**

- Consumes: the overlay sentinel, exact ABI module paths, and the selected
  RStudio environment state file.
- Produces: one compatible system-R process and independent standalone and
  Conda-R controls.

- [x] Retain `RETICULATE_PYTHON=/opt/conda/bin/python` in the system branch.
- [x] Validate `.audit-passed` and both exact ABI modules; fail before launching
  R if any is unavailable.
- [x] Prepend the overlay `lib-dynload` and `site-packages` directories to
  `PYTHONPATH`.
- [x] Leave `LD_PRELOAD` untouched; package-manager internals are standalone
  only.
- [x] Exercise native R Arrow, HDF5, libgit2, curl, and OpenSSL before and
  after the embedded Python workload.
- [x] Exercise deterministic offline Python operations across SSL/hashlib,
  cryptography, Arrow/Parquet, h5py, PyTables, ZMQ, zstandard, rpy2,
  representative scientific libraries, and declared user/application
  entrypoints.
- [x] Require `/proc/self/maps` to show only Ubuntu OpenSSL for the relevant
  SONAMEs.
- [x] Preserve a standalone `/opt/conda/bin/python -I` control that requires
  Conda OpenSSL 3.6.3 and Conda module paths, exercises `libmambapy`, and checks
  exact `mamba`/`libmamba` version parity through `mamba info --json`. This is a
  non-regression control, not a change to terminal or VSCode reticulate
  discovery.
- [x] Preserve the synthetic non-system Conda-R activation control.
- [x] Cover fail-closed behavior for the sentinel and both exact ABI modules.

### Task 4: Validate and publish exact-head evidence

**Files:**

- Modify only for proven findings: files named in Tasks 1-3
- Remote metadata after validation: PR #292 title and body

**Interfaces:**

- Consumes: the reviewed worktree and successful local image build.
- Produces: an exact pushed head with a terminal full image matrix.

- [x] Run local static gates. The current Bash, Python compilation, and
  `git diff --check` results are green; retain the earlier collection result
  rather than invoking the repository's container-mutating pytest fixtures
  around user services:

  ```bash
  bash -n images/rstudio/customRStu/rsession.sh
  python3 -m py_compile \
    images/mid/audit-reticulate-compat.py \
    tests/general/test_rstudio.py \
    tests/general/test_r_system.py
  python3 -m pytest --collect-only \
    tests/general/test_rstudio.py \
    tests/general/test_r_system.py
  git diff --check
  ```

- [x] Review the complete diff and confirm no executable instruction or code
  path reintroduces the Conda OpenSSL preload.
- [x] Run the full system-R `Rscript`/reticulate surrogate against the final
  locally built `linux/amd64` image and require native R before/after,
  embedded Python operations, and system-only OpenSSL maps.
- [ ] Obtain the authoritative corrected system-R `rsession` result from
  hosted native-amd64 CI. Local `rsession` does not complete reliably under
  amd64-on-arm64 Rosetta and is not accepted as a substitute.
- [ ] Commit the overlay only after the local build and review are green.
- [ ] Fetch and verify the live remote head, then push normally without force.
- [ ] Watch every build/test/downstream job for the exact pushed SHA. Require
  the real RStudio session, standalone controls, namespace sweep, Spark,
  kernels, notebooks, and all downstream images to pass.
- [ ] Update PR #292 metadata with the exact SHA and terminal hosted results.
  Keep base `beta`; do not merge.
- [ ] If any job fails, inspect its exact log, make the smallest in-scope
  correction, rerun local gates, review, push with a refreshed lease, and
  watch the replacement run. Never infer success from a prior head.

## Current evidence boundary

The rejected design has exact hosted exit-139 evidence. The final no-preload
overlay has a green local `linux/amd64` image build plus source, wheel, ELF,
syntax, collection, fail-closed, standalone Conda, and full mixed-runtime
`Rscript` surrogate evidence. The corrected real RStudio session still needs
the hosted native-amd64 result because local `rsession` is unreliable under
Rosetta, and hosted CI for the overlay has not run. Task 4 is therefore
intentionally incomplete.

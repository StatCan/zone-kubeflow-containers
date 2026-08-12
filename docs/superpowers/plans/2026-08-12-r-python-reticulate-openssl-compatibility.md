# R/Python Reticulate OpenSSL Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PR #292 the single R 4.6.1/Python 3.14.5 upgrade PR, restore the former inherited R package surface, and make the real RStudio system-R session use Conda OpenSSL safely when reticulate embeds Conda Python.

**Architecture:** Keep system R and Conda Python as separate runtimes, but preload only Conda's coherent `libcrypto.so.3`/`libssl.so.3` pair in the system-R `rsession` wrapper before the OpenSSL-linked RStudio binary starts. Restore packages lost when the base moved from `datascience-notebook` to `scipy-notebook`, make reticulate explicit, and validate the real hidden `rsession --run-script` seam plus standalone/bridge/package behavior.

**Tech Stack:** Bash, Docker, R 4.6.1, reticulate, Python 3.14.5, rpy2, OpenSSL 3.6.3, pytest, GitHub Actions, Azure Container Registry.

## Global Constraints

- PR #292 (`feat/python-3.14`, base `beta`) is the only remote branch/PR to update; do not merge or close PR #288 or #290.
- Preserve system R 4.6.1 from CRAN apt, PPM, Conda Python 3.14.5, Spark 4.2.0, Java 21, Banff artifacts, Jupyter kernels, RStudio launch behavior, and user-selected Conda-R behavior.
- Scope loader changes only to the `system` branch of `images/rstudio/customRStu/rsession.sh`.
- Preload exactly `/opt/conda/lib/libcrypto.so.3` and `/opt/conda/lib/libssl.so.3`; never add all of `/opt/conda/lib`, replace `/usr/lib` files, create global symlinks, or downgrade OpenSSL.
- Fail closed with an actionable wrapper error if either Conda OpenSSL library is unreadable.
- Restore the former upstream direct R packages `caret`, `crayon`, `devtools`, `forecast`, `hexbin`, `htmltools`, `htmlwidgets`, `nycflights13`, `randomForest`, `RCurl`, `rmarkdown`, `RSQLite`, `shiny`, and `tidymodels`; explicitly install `reticulate`.
- Test the exact PR head. Do not claim compatibility from static checks when the rebuilt private images have not run.
- Preserve the unrelated dirty root checkout; perform all work in `/private/tmp/zone-reticulate-spec-dec228b.Bu4JrP`.

---

### Task 1: Add red-capable runtime and package-parity regressions

**Files:**
- Modify: `tests/general/test_rstudio.py`
- Modify: `tests/general/test_r_system.py`

**Interfaces:**
- Consumes: existing `CondaPackageHelper`, the system-R state file at `$HOME/.local/share/rstudio/active_conda_env`, and RStudio's hidden `--run-script=<R code>` mode.
- Produces: exact regression tests that Task 2 must make green, including the marker `RSESSION_RETICULATE_OK` and the expanded `R_PACKAGES` contract.

- [ ] **Step 1: Add the real RStudio-session regression and fail-closed regression**

Add these helpers and tests to `tests/general/test_rstudio.py`:

```python
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
suppressPackageStartupMessages(library(reticulate))
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
    assert "RSESSION_RETICULATE_OK" in output


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
```

- [ ] **Step 2: Expand the system-R package contract and add both language-bridge checks**

Extend `R_PACKAGES` in `tests/general/test_r_system.py` with the following exact names:

```python
    "caret",
    "crayon",
    "devtools",
    "forecast",
    "hexbin",
    "htmltools",
    "htmlwidgets",
    "nycflights13",
    "randomForest",
    "RCurl",
    "reticulate",
    "rmarkdown",
    "RSQLite",
    "shiny",
    "tidymodels",
```

Add these runtime tests:

```python
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
```

- [ ] **Step 3: Run local syntax/collection checks**

Run:

```bash
python3 -m py_compile tests/general/test_rstudio.py tests/general/test_r_system.py
python3 -m pytest --collect-only tests/general/test_rstudio.py tests/general/test_r_system.py
```

Expected: Python compilation and pytest collection succeed. Docker cleanup may log an unavailable-daemon warning after collection, but collection itself must exit zero.

- [ ] **Step 4: Commit the red-capable tests**

```bash
git add tests/general/test_rstudio.py tests/general/test_r_system.py
git commit -m "test: cover R Python runtime compatibility"
```

- [ ] **Step 5: Review Task 1**

Generate the task review package from the Task 1 starting commit through the test commit. Require a clean spec-compliance and test-quality review before Task 2.

### Task 2: Restore package parity and scope the OpenSSL pair to system rsession

**Files:**
- Modify: `images/mid/Dockerfile`
- Modify: `images/rstudio/customRStu/rsession.sh`

**Interfaces:**
- Consumes: the exact `R_PACKAGES`, error text, loader paths, and `RSESSION_RETICULATE_OK` contract from Task 1.
- Produces: an image with the former direct R package surface restored and a system-only RStudio wrapper that exports a coherent targeted `LD_PRELOAD`.

- [ ] **Step 1: Restore the lost inherited R packages and make reticulate explicit**

In the existing PPM `pkgs <- c(...)` vector in `images/mid/Dockerfile`, add these exact packages without changing the repository, installer, or completeness check:

```r
'caret', 'crayon', 'devtools', 'forecast', 'hexbin', 'htmltools',
'htmlwidgets', 'nycflights13', 'randomForest', 'RCurl', 'reticulate',
'rmarkdown', 'RSQLite', 'shiny', 'tidymodels'
```

Keep the entire list in the existing single PPM installation transaction so `missing <- setdiff(...)` remains authoritative.

- [ ] **Step 2: Commit package parity before changing the loader**

```bash
git add images/mid/Dockerfile
git commit -m "fix: preserve R package parity"
```

- [ ] **Step 3: Push the red-capable head and observe the exact loader regression**

Re-read the remote head and use a normal fast-forward push so concurrent remote work causes rejection rather than overwrite:

```bash
git fetch origin feat/python-3.14
git merge-base --is-ancestor origin/feat/python-3.14 HEAD
git push origin HEAD:feat/python-3.14
gh pr checks 292 --repo StatCan/zone-kubeflow-containers --watch --interval 30
```

Expected: the restored `reticulate` package allows the real RStudio test to reach Python initialization, then `test_system_r_rsession_reticulate_openssl` goes red with the observed `OPENSSL_3.3.0 not found` loader failure. `test_system_r_rsession_fails_without_conda_openssl_pair` is also red because the wrapper does not yet validate the pair. Record the exact failing run and output before changing `rsession.sh`.

- [ ] **Step 4: Add the minimal fail-closed system-rsession preload**

Replace only the `system` branch in `images/rstudio/customRStu/rsession.sh` with:

```bash
if [ "$CONDA_ENV" = "system" ]; then
  log "Using system R ($(/usr/bin/R --version | head -n 1))"
  export RETICULATE_PYTHON="/opt/conda/bin/python"

  CONDA_LIBCRYPTO="/opt/conda/lib/libcrypto.so.3"
  CONDA_LIBSSL="/opt/conda/lib/libssl.so.3"
  for library in "$CONDA_LIBCRYPTO" "$CONDA_LIBSSL"; do
    if [ ! -r "$library" ]; then
      log "ERROR: Required Conda OpenSSL library is not readable: $library"
      exit 1
    fi
  done

  export LD_PRELOAD="${CONDA_LIBCRYPTO}:${CONDA_LIBSSL}${LD_PRELOAD:+:${LD_PRELOAD}}"
  log "RETICULATE_PYTHON=${RETICULATE_PYTHON}"
  log "LD_PRELOAD=${LD_PRELOAD}"
  exec /usr/lib/rstudio-server/bin/rsession "$@"
fi
```

Do not alter the later Conda-environment branch.

- [ ] **Step 5: Run focused static tests**

Run:

```bash
bash -n images/rstudio/customRStu/rsession.sh
python3 -m py_compile tests/general/test_rstudio.py tests/general/test_r_system.py
python3 -m pytest --collect-only tests/general/test_rstudio.py tests/general/test_r_system.py
git diff --check
```

Expected: all commands exit zero.

- [ ] **Step 6: Commit the implementation**

```bash
git add images/rstudio/customRStu/rsession.sh
git commit -m "fix: preserve R Python runtime compatibility"
```

- [ ] **Step 7: Review Task 2**

Generate the task review package from the Task 2 starting commit through the implementation commit. Require a clean spec-compliance and code-quality review, including confirmation that the non-system Conda-R branch is byte-for-byte unchanged.

### Task 3: Validate, publish, and make PR #292 canonical

**Files:**
- Modify if required by findings: only files already named in Tasks 1-2
- Remote metadata: PR #292 title and body

**Interfaces:**
- Consumes: reviewed commits from Tasks 1-2.
- Produces: one exact pushed PR head with green full image checks and a combined R/Python description.

- [ ] **Step 1: Run the broad local checks available without Docker**

```bash
bash -n images/rstudio/customRStu/rsession.sh
python3 -m py_compile tests/general/*.py tests/mid/*.py tests/jupyterlab-cpu/*.py
python3 -m pytest --collect-only tests/general tests/mid tests/jupyterlab-cpu
git diff --check origin/beta...HEAD
```

Expected: every command exits zero; an unavailable Docker daemon may be logged during pytest fixture cleanup but must not turn collection red.

- [ ] **Step 2: Run the whole-branch review**

Generate a review package from `git merge-base origin/beta HEAD` through `HEAD`. The reviewer must check the combined R/Python upgrade, loader safety, restored package parity, test validity, workflow coverage, secret safety, and absence of changes outside the approved surface. Resolve every Critical or Important finding with a focused fix commit and re-review.

- [ ] **Step 3: Push the reviewed implementation with a live head lease**

```bash
git fetch origin feat/python-3.14 beta
git merge-base --is-ancestor origin/feat/python-3.14 HEAD
git push origin HEAD:feat/python-3.14
```

Expected: only `origin/feat/python-3.14` advances to the reviewed local head.

- [ ] **Step 4: Watch every GitHub check to a terminal result**

```bash
gh pr checks 292 --repo StatCan/zone-kubeflow-containers --watch --interval 30
gh pr view 292 --repo StatCan/zone-kubeflow-containers \
  --json headRefOid,baseRefName,mergeable,mergeStateStatus,statusCheckRollup
```

Expected: build and full tests pass for base, mid, rstudio, sas-kernel, jupyterlab-cpu, and sas at the exact pushed SHA, including the declared Python import sweep, all installed R namespace sweep, explicit R package loads, standalone SSL, real RStudio reticulate, rpy2, Banff, SparkSession, kernels, notebooks, and image health tests.

- [ ] **Step 5: Update PR #292 metadata with exact-head evidence**

Set the title to:

```text
feat: upgrade R 4.6 and Python 3.14 with runtime compatibility
```

Write a body that identifies #292 as the combined canonical PR, explains the system-R/Conda-Python OpenSSL collision and targeted preload, lists restored legacy R packages, calls out Spark 4/Java 21/Banff changes already in the branch, and includes the exact pushed SHA and completed check evidence from Step 4. Remove the stale instruction to merge #288 and #290 first. Keep base `beta`; do not merge the PR.

- [ ] **Step 6: Fix any CI regression on the same PR**

For a failing check, inspect the exact failed log with `gh run view <run-id> --log-failed`, make the smallest in-scope correction, rerun focused static checks, obtain task review for the fix, push with a refreshed head lease, and watch the replacement run. Stop only when the full exact-head matrix is green or an external blocker is proven.

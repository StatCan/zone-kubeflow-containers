# R 4.6 and Python 3.14 Reticulate/OpenSSL Compatibility Design

## Goal and canonical pull request

PR #292 (`feat/python-3.14`) is the sole canonical pull request for the R 4.6.1, Python 3.14.5, and reticulate/OpenSSL compatibility work. Its branch already contains the complete #288 and #290 ancestry. The implementation will update #292 only; it will not split the fix, merge or close #288/#290, or duplicate their changes elsewhere.

The result must preserve the existing user experience: system R 4.6.1 and Posit Package Manager, Conda Python 3.14.5, standalone R and Python, RStudio, Jupyter kernels, user-created Conda environments, reticulate from R to Python, and rpy2 from Python to R. Moving from the upstream `datascience-notebook` image to `scipy-notebook` must not remove the R packages users previously received from that inherited layer.

## Root cause

Commit `02b462ca89f7cef38b2d3a64c77590e63be739c2` moved R to the system installation while retaining `/opt/conda/bin/python` for reticulate. In the system-R path, `start_rstudio_server.sh` selects `/usr/bin/R` and `/usr/lib/R/lib`; `rsession.sh` then exports `RETICULATE_PYTHON=/opt/conda/bin/python` without making Conda's OpenSSL libraries resident before RStudio starts.

RStudio Server 2026.04.0+526 links `libssl.so.3` and `libcrypto.so.3`, so `rsession` loads Ubuntu's OpenSSL 3.0 libraries first. Reticulate later loads the Conda Python `_ssl` extension. The dynamic loader reuses the already-loaded libraries with the same SONAME, but Python 3.14.5's `_ssl.so` requires `OPENSSL_3.3.0`. Ubuntu's library does not export that symbol version; Conda OpenSSL 3.6.3 does. This produces the observed error even though standalone Conda Python succeeds.

The Python chain entered in `77e0a32d6efc0ecfff3bb3beaf4ed1c532894e1c` and was pinned to Python 3.14.5 in `dec228b9ee2c27b90cab6418f21b8b37180e9eda`. It exposed the mixed-runtime flaw; choosing the wrong interpreter is not the cause because reticulate reports `/opt/conda/bin/python`.

## Implementation design

Only the `system` branch of `images/rstudio/customRStu/rsession.sh` will preload the coherent Conda OpenSSL pair before executing the real RStudio `rsession` binary:

- `/opt/conda/lib/libcrypto.so.3`
- `/opt/conda/lib/libssl.so.3`

The wrapper will validate that both files exist and are readable. If either is unavailable, it will log a precise error and exit before launching a partially configured session. It must not silently fall back to the incompatible system pair.

The preload is deliberately process-scoped and limited to these two libraries. The implementation must not add all of `/opt/conda/lib` to the system-R loader path, replace files under `/usr/lib`, add global symlinks, or downgrade OpenSSL. Broad Conda library precedence already caused an unrelated ncurses collision in PR #239 and would expose RStudio and system R packages to unnecessary ABI risk.

The existing Conda-R branch remains unchanged: when a user explicitly selects a Conda environment that contains R, the current activation, `R_LIBS_USER`, `R_LIBS_SITE`, interpreter selection, and loader behavior continue to apply.

The system-R PPM installation will explicitly preserve the former upstream `datascience-notebook` R package surface in addition to this repository's existing package list. The restored direct packages are `caret`, `crayon`, `devtools`, `forecast`, `hexbin`, `htmltools`, `htmlwidgets`, `nycflights13`, `randomForest`, `RCurl`, `rmarkdown`, `RSQLite`, `shiny`, and `tidymodels`; `e1071`, `IRkernel`, `RODBC`, `tidyverse`, and rpy2 are already handled elsewhere in the new image. `reticulate` will become an explicit system-R package because the image's R-to-Python contract must not depend on a user's persisted personal library or a coincidental transitive dependency.

## Compatibility and failure behavior

The two preloaded libraries must come from the same `/opt/conda/lib` prefix. Conda OpenSSL 3.6.3 provides both RStudio's required `OPENSSL_3.0.0` symbols and Python's required `OPENSSL_3.3.0` symbols. Tests must prove the actual running session mapped the intended Conda libraries rather than inferring success from version strings alone.

Other than restoring that lost inherited R package surface and making `reticulate` explicit, no package list, interpreter-selection rule, R repository configuration, Jupyter kernel registration, Spark/Java version, Banff artifact, or user-visible launcher workflow is changed by this fix.

## Verification design

The regression must exercise the real RStudio wrapper/`rsession` boundary, not only a plain `Rscript` process. It will assert:

1. The system-R session selects `/usr/bin/R` and reticulate selects `/opt/conda/bin/python` 3.14.5.
2. `reticulate::py_run_string("import ssl")` succeeds and reports the expected Conda OpenSSL runtime.
3. `/proc/self/maps` or equivalent process evidence shows the Conda `libcrypto.so.3` and `libssl.so.3`, with no system copies of those SONAMEs resident in the session.
4. Missing either member of the required pair makes the wrapper fail closed with an actionable error.
5. The non-system Conda-R branch retains its existing environment activation behavior.

Broader compatibility validation will cover:

- standalone `/opt/conda/bin/python`, including `ssl` and the existing declared Conda/Python import sweep;
- system `/usr/bin/R`, including every package in the explicit PPM package list, the restored former upstream package list, `reticulate`, and `zonetokenbroker`;
- R-to-Python operation through reticulate;
- Python-to-R operation through rpy2;
- RStudio startup, version, custom proxy, and a live session using the wrapper;
- registered Python and R Jupyter kernels;
- the existing Banff, SparkSession, notebook, package, and image health tests;
- the complete existing CI matrix for base, mid, rstudio, sas-kernel, jupyterlab-cpu, and sas images.

CI success is evidence for the rebuilt PR head only. The PR must not be presented as fixed until the exact-head image tests pass; if a private-image runtime limitation remains, it must be reported explicitly rather than inferred from static checks.

## Pull request handoff

After implementation and exact-head validation, PR #292's title and description will be updated to describe the combined R 4.6.1, Python 3.14.5, and reticulate/OpenSSL compatibility change and its broader test evidence. The PR will remain targeted at `beta`. No merge is part of this work unless separately authorized.

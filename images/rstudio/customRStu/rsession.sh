#!/usr/bin/env bash

set -euo pipefail

log() {
  echo "[rstudio-rsession $(date -Iseconds)] $*"
}

RSTUDIO_STATE_DIR="${HOME}/.local/share/rstudio"
RSTUDIO_CONDA_ENV_FILE="${RSTUDIO_STATE_DIR}/active_conda_env"
CONDA_SH="/opt/conda/etc/profile.d/conda.sh"

log "HOME=${HOME}"
log "USER=${USER:-}"
log "env_file=${RSTUDIO_CONDA_ENV_FILE}"
log "conda_sh=${CONDA_SH}"

if [ ! -r "$RSTUDIO_CONDA_ENV_FILE" ]; then
  log "ERROR: Missing RStudio Conda env state: $RSTUDIO_CONDA_ENV_FILE"
  exit 1
fi

if [ ! -r "$CONDA_SH" ]; then
  log "ERROR: Missing Conda initialization script: $CONDA_SH"
  exit 1
fi

# load conda env from persistent state
CONDA_ENV="$(tr -d '\r' < "$RSTUDIO_CONDA_ENV_FILE")"
log "Loaded target Conda env: ${CONDA_ENV}"

# "system" means no Conda env provides R: run the image's system R (/usr/bin/R)
# directly. Library paths come from Rprofile.site and the user's ~/.Rprofile.
if [ "$CONDA_ENV" = "system" ]; then
  log "Using system R ($(/usr/bin/R --version | head -n 1))"
  export RETICULATE_PYTHON="/opt/conda/bin/python"

  RETICULATE_COMPAT_ROOT="/opt/reticulate-compat"
  RETICULATE_COMPAT_PYTHON="${RETICULATE_COMPAT_ROOT}/lib/python3.14"
  RETICULATE_COMPAT_DYNLOAD="${RETICULATE_COMPAT_PYTHON}/lib-dynload"
  RETICULATE_COMPAT_SITE="${RETICULATE_COMPAT_PYTHON}/site-packages"
  RETICULATE_COMPAT_SSL="${RETICULATE_COMPAT_DYNLOAD}/_ssl.cpython-314-x86_64-linux-gnu.so"
  RETICULATE_COMPAT_HASHLIB="${RETICULATE_COMPAT_DYNLOAD}/_hashlib.cpython-314-x86_64-linux-gnu.so"

  for required_path in \
    "${RETICULATE_COMPAT_ROOT}/.audit-passed" \
    "$RETICULATE_COMPAT_SSL" \
    "$RETICULATE_COMPAT_HASHLIB"; do
    if [ ! -r "$required_path" ]; then
      log "ERROR: Required reticulate compatibility path is not readable: $required_path"
      exit 1
    fi
  done

  export PYTHONPATH="${RETICULATE_COMPAT_DYNLOAD}:${RETICULATE_COMPAT_SITE}${PYTHONPATH:+:${PYTHONPATH}}"
  log "RETICULATE_PYTHON=${RETICULATE_PYTHON}"
  log "RETICULATE_COMPAT_PYTHON=${RETICULATE_COMPAT_PYTHON}"
  exec /usr/lib/rstudio-server/bin/rsession "$@"
fi

if [ ! -x "$CONDA_ENV/bin/R" ]; then
  log "ERROR: Invalid RStudio Conda env: $CONDA_ENV"
  exit 1
fi

# RStudio launches rsession in a non-interactive shell, so source conda.sh instead of relying on shell startup files.
# shellcheck disable=SC1091
. "$CONDA_SH"
conda activate "$CONDA_ENV"
log "Activated Conda env: ${CONDA_PREFIX}"
log "which R => $(which R)"
log "R version => $("$CONDA_PREFIX/bin/R" --version | head -n 1)"

export RETICULATE_PYTHON="${CONDA_PREFIX}/bin/python"
# R libPath Isolation
export R_LIBS_USER="$CONDA_PREFIX/lib/R/library"
export R_LIBS_SITE="$CONDA_PREFIX/lib/R/library"
log "RETICULATE_PYTHON=${RETICULATE_PYTHON}"
log "R_LIBS_USER=${R_LIBS_USER}"
log "R_LIBS_SITE=${R_LIBS_SITE}"

exec /usr/lib/rstudio-server/bin/rsession "$@"

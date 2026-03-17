#!/usr/bin/env bash

set -euo pipefail

RSTUDIO_STATE_DIR="${HOME}/.local/share/rstudio"
RSTUDIO_CONDA_ENV_FILE="${RSTUDIO_STATE_DIR}/active_conda_env"
CONDA_SH="/opt/conda/etc/profile.d/conda.sh"

if [ ! -r "$RSTUDIO_CONDA_ENV_FILE" ]; then
  echo "Missing RStudio Conda env state: $RSTUDIO_CONDA_ENV_FILE" >&2
  exit 1
fi

if [ ! -r "$CONDA_SH" ]; then
  echo "Missing Conda initialization script: $CONDA_SH" >&2
  exit 1
fi

# load conda env from persistent state
CONDA_ENV="$(tr -d '\r' < "$RSTUDIO_CONDA_ENV_FILE")"
echo "## CONDA ENV is >>>"
echo "${CONDA_ENV}"

if [ ! -x "$CONDA_ENV/bin/R" ]; then
  echo "Invalid RStudio Conda env: $CONDA_ENV" >&2
  exit 1
fi

# RStudio launches rsession in a non-interactive shell, so source conda.sh instead of relying on shell startup files.
# shellcheck disable=SC1091
. "$CONDA_SH"
conda activate "$CONDA_ENV"

export RETICULATE_PYTHON="${CONDA_PREFIX}/bin/python"
# R libPath Isolation
export R_LIBS_USER="$CONDA_PREFIX/lib/R/library"
export R_LIBS_SITE="$CONDA_PREFIX/lib/R/library"

exec /usr/lib/rstudio-server/bin/rsession "$@"

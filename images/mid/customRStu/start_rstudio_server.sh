#!/usr/bin/env bash

set -euo pipefail

##############################################
# USAGE: ./start_rstudio_server.sh <PORT>
#   e.g. ./start_rstudio_server.sh 8787
##############################################

CWD="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
echo "cwd=$CWD"
USER="${NB_USER}"
RSTUDIO_STATE_DIR="${HOME}/.local/share/rstudio"
RSTUDIO_CONDA_ENV_FILE="${RSTUDIO_STATE_DIR}/active_conda_env"

resolve_conda_env() {
  local candidate="${1:-}"

  if [ -n "$candidate" ] && [ -x "$candidate/bin/R" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  return 1
}

mkdir -p "$RSTUDIO_STATE_DIR"

TARGET_CONDA_ENV=""
# The Jupyter server usually starts in base, so prefer the last env the user selected in an interactive shell.
if [ -r "$RSTUDIO_CONDA_ENV_FILE" ]; then
  TARGET_CONDA_ENV="$(tr -d '\r' < "$RSTUDIO_CONDA_ENV_FILE")"
fi

if ! TARGET_CONDA_ENV="$(resolve_conda_env "$TARGET_CONDA_ENV")"; then
  TARGET_CONDA_ENV="$(resolve_conda_env "${CONDA_PREFIX:-/opt/conda}")"
fi

printf '%s\n' "$TARGET_CONDA_ENV" > "$RSTUDIO_CONDA_ENV_FILE"
echo "## RStudio target env is >>"
echo "$TARGET_CONDA_ENV"

# set a user-specific secure cookie key
COOKIE_KEY_PATH="/tmp/rstudio-server/${USER}_secure-cookie-key"
rm -f "$COOKIE_KEY_PATH"
mkdir -p "$(dirname "$COOKIE_KEY_PATH")"

python3 -c 'import uuid; print(uuid.uuid4())' > "$COOKIE_KEY_PATH"
chmod 600 "$COOKIE_KEY_PATH"
export RETICULATE_PYTHON="${TARGET_CONDA_ENV}/bin/python"

# Use user-specific database.conf in home directory instead of /opt
DB_CONF_PATH="${HOME}/.rstudio/database.conf"
sed -i "s|directory=.*|directory=/tmp/rstudio-server/${USER}_database|" "$DB_CONF_PATH"

# Jupyter server-proxy serves the launcher under the fixed /rstudio route.
BASE_PATH="${NB_PREFIX}/rstudio"

# Pin R and the loader path to the same target env before rsession starts.
/usr/lib/rstudio-server/bin/rserver   --server-daemonize=0 \
  --auth-none=1 \
  --www-port="$1" \
  --www-root-path="${BASE_PATH}" \
  --www-frame-origin=none \
  --www-verify-user-agent=0 \
  --www-enable-origin-check=1 \
  --www-same-site=lax \
  --secure-cookie-key-file="$COOKIE_KEY_PATH" \
  --server-pid-file="/tmp/rstudio-server/${USER}_rstudio-server.pid" \
  --server-data-dir="/tmp/rstudio-server/${USER}_rstudio-server" \
  --rsession-which-r="${TARGET_CONDA_ENV}/bin/R" \
  --rsession-ld-library-path="${TARGET_CONDA_ENV}/lib" \
  --rsession-path="$CWD/rsession.sh" \
  --server-user "$USER" \
  --database-config-file "$DB_CONF_PATH" \
  --auth-timeout-minutes=10080

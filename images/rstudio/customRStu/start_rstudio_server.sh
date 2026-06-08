#!/usr/bin/env bash

set -euo pipefail

log() {
  echo "[rstudio-start $(date -Iseconds)] $*"
}

##############################################
# USAGE: ./start_rstudio_server.sh <PORT>
#   e.g. ./start_rstudio_server.sh 8787
##############################################

CWD="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
export USER="${NB_USER}"
RSTUDIO_STATE_DIR="${HOME}/.local/share/rstudio"
RSTUDIO_CONDA_ENV_FILE="${RSTUDIO_STATE_DIR}/active_conda_env"
RSTUDIO_RUNTIME_DIR="/tmp/rstudio-server"
RSTUDIO_DATA_DIR="${RSTUDIO_RUNTIME_DIR}/${USER}_rstudio-server"
RSTUDIO_CONFIG_DIR="${HOME}/.config/rstudio"
RSTUDIO_SERVER_CONFIG_DIR="${HOME}/.rstudio"
DB_CONF_PATH="${RSTUDIO_SERVER_CONFIG_DIR}/database.conf"
DB_CONF_TEMPLATE="${CWD}/database.conf"

log "cwd=${CWD}"
log "USER=${USER}"
log "HOME=${HOME}"
log "NB_PREFIX=${NB_PREFIX:-}"
log "CONDA_PREFIX=${CONDA_PREFIX:-}"
log "state_dir=${RSTUDIO_STATE_DIR}"
log "runtime_dir=${RSTUDIO_RUNTIME_DIR}"

resolve_conda_env() {
  local candidate="${1:-}"

  if [ -n "$candidate" ] && [ -x "$candidate/bin/R" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  return 1
}

mkdir -p "$RSTUDIO_STATE_DIR"
mkdir -p "$RSTUDIO_RUNTIME_DIR"
mkdir -p "$RSTUDIO_SERVER_CONFIG_DIR"
mkdir -p "$RSTUDIO_CONFIG_DIR" || true

if [ ! -w "$RSTUDIO_CONFIG_DIR" ]; then
  log "WARNING: ${RSTUDIO_CONFIG_DIR} is not writable"
else
  log "${RSTUDIO_CONFIG_DIR} is writable"
fi

TARGET_CONDA_ENV=""
# The Jupyter server usually starts in base, so prefer the last env the user selected in an interactive shell.
if [ -r "$RSTUDIO_CONDA_ENV_FILE" ]; then
  TARGET_CONDA_ENV="$(tr -d '\r' < "$RSTUDIO_CONDA_ENV_FILE")"
  log "Loaded saved env from ${RSTUDIO_CONDA_ENV_FILE}: ${TARGET_CONDA_ENV}"
fi

if ! TARGET_CONDA_ENV="$(resolve_conda_env "$TARGET_CONDA_ENV")"; then
  log "Saved env invalid or missing, falling back to CONDA_PREFIX/default"
  TARGET_CONDA_ENV="$(resolve_conda_env "${CONDA_PREFIX:-/opt/conda}")"
fi

printf '%s\n' "$TARGET_CONDA_ENV" > "$RSTUDIO_CONDA_ENV_FILE"
log "Selected target env: ${TARGET_CONDA_ENV}"
log "Persisted target env to ${RSTUDIO_CONDA_ENV_FILE}"

# set a user-specific secure cookie key
COOKIE_KEY_PATH="${RSTUDIO_RUNTIME_DIR}/${USER}_secure-cookie-key"
rm -f "$COOKIE_KEY_PATH"
mkdir -p "$(dirname "$COOKIE_KEY_PATH")"

python3 -c 'import uuid; print(uuid.uuid4())' > "$COOKIE_KEY_PATH"
chmod 600 "$COOKIE_KEY_PATH"
export RETICULATE_PYTHON="${TARGET_CONDA_ENV}/bin/python"
log "COOKIE_KEY_PATH=${COOKIE_KEY_PATH}"
log "RETICULATE_PYTHON=${RETICULATE_PYTHON}"

if [ ! -f "$DB_CONF_PATH" ]; then
  log "database.conf missing at ${DB_CONF_PATH}; restoring from ${DB_CONF_TEMPLATE}"
  cp "$DB_CONF_TEMPLATE" "$DB_CONF_PATH"
fi

sed -i "s|directory=.*|directory=${RSTUDIO_RUNTIME_DIR}/${USER}_database|" "$DB_CONF_PATH"
log "Using database.conf at ${DB_CONF_PATH}"
log "database.conf contents:"
sed 's/^/[rstudio-start database] /' "$DB_CONF_PATH"

# Jupyter server-proxy serves the launcher under the fixed /rstudio route.
BASE_PATH="${NB_PREFIX}/rstudio"
log "BASE_PATH=${BASE_PATH}"

# Clear stale runtime state from a previously terminated RStudio server.
rm -rf "$RSTUDIO_DATA_DIR"
log "Cleared stale runtime state ${RSTUDIO_DATA_DIR})"

# Pin R and the loader path to the target env selected before launch.
log "Launching rserver with R=${TARGET_CONDA_ENV}/bin/R"
log "Launching rserver with LD_LIBRARY_PATH=${TARGET_CONDA_ENV}/lib"
/usr/lib/rstudio-server/bin/rserver   --server-daemonize=0 \
  --auth-none=1 \
  --www-port="$1" \
  --www-root-path="${BASE_PATH}" \
  --www-frame-origin=none \
  --www-verify-user-agent=0 \
  --www-enable-origin-check=1 \
  --www-same-site=lax \
  --secure-cookie-key-file="$COOKIE_KEY_PATH" \
  --server-data-dir="$RSTUDIO_DATA_DIR" \
  --rsession-which-r="${TARGET_CONDA_ENV}/bin/R" \
  --rsession-ld-library-path="${TARGET_CONDA_ENV}/lib" \
  --rsession-path="$CWD/rsession.sh" \
  --server-user "$USER" \
  --database-config-file "$DB_CONF_PATH" \
  --auth-timeout-minutes=10080 &

# Exit logging
RSTUDIO_PID=$!
log "rserver pid=${RSTUDIO_PID}"
set +e
wait "$RSTUDIO_PID"
RSTUDIO_EXIT_CODE=$?
set -e
log "RStudio server exited with status ${RSTUDIO_EXIT_CODE}"

rm -rf "$RSTUDIO_DATA_DIR"
log "Removed runtime state after exit"

exit "$RSTUDIO_EXIT_CODE"

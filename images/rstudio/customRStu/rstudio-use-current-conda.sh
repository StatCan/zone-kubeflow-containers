#!/usr/bin/env bash

set -euo pipefail

log() {
  echo "[rstudio-switch $(date -Iseconds)] $*"
}

USER_NAME="${NB_USER:-$(id -un)}"
HOME_DIR="${HOME:-/home/${USER_NAME}}"
STATE_DIR="${HOME_DIR}/.local/share/rstudio"
STATE_FILE="${STATE_DIR}/active_conda_env"
RUNTIME_DIR="/tmp/rstudio-server"
DATA_DIR="${RUNTIME_DIR}/${USER_NAME}_rstudio-server"
COOKIE_KEY="${RUNTIME_DIR}/${USER_NAME}_secure-cookie-key"
RSERVER_PATTERN="/usr/lib/rstudio-server/bin/rserver"
RSESSION_PATTERN="/usr/lib/rstudio-server/bin/rsession"
DB_DIR="${RUNTIME_DIR}/${USER_NAME}_database"

TARGET_CONDA_ENV="${CONDA_PREFIX:-/opt/conda}"
if [ ! -x "${TARGET_CONDA_ENV}/bin/R" ]; then
  log "ERROR: Current CONDA_PREFIX does not contain R: ${TARGET_CONDA_ENV}"
  exit 1
fi

log "USER_NAME=${USER_NAME}"
log "HOME_DIR=${HOME_DIR}"
log "STATE_FILE=${STATE_FILE}"
log "TARGET_CONDA_ENV=${TARGET_CONDA_ENV}"
log "Current R => $("${TARGET_CONDA_ENV}/bin/R" --version | head -n 1)"

mkdir -p "$STATE_DIR"
printf '%s\n' "$TARGET_CONDA_ENV" > "$STATE_FILE"
log "Saved RStudio env: $TARGET_CONDA_ENV"

stop_matching_processes() {
  local process_pattern="$1"
  local process_label="$2"
  local pids remaining

  pids="$(pgrep -u "$USER_NAME" -f "$process_pattern" || true)"
  if [ -z "$pids" ]; then
    log "No ${process_label} found for pattern ${process_pattern}"
    return 0
  fi

  log "Stopping ${process_label}: $(echo "$pids" | tr '\n' ' ')"
  pkill -u "$USER_NAME" -f "$process_pattern" || true

  sleep 1
  remaining="$(pgrep -u "$USER_NAME" -f "$process_pattern" || true)"
  if [ -n "$remaining" ]; then
    log "Force killing ${process_label}: $(echo "$remaining" | tr '\n' ' ')"
    pkill -9 -u "$USER_NAME" -f "$process_pattern" || true
  fi
}

# Stop child sessions before stopping the server process that launched them.
stop_matching_processes "$RSESSION_PATTERN" "RStudio sessions"
stop_matching_processes "$RSERVER_PATTERN" "RStudio server"

rm -f "$COOKIE_KEY"
rm -rf "$DATA_DIR" "$DB_DIR"
log "Removed runtime state: $COOKIE_KEY $DATA_DIR $DB_DIR"

log "RStudio is ready to relaunch from the tile."

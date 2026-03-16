#!/usr/bin/env bash

##############################################
# USAGE: ./start_rstudio_server.sh <PORT>
#   e.g. ./start_rstudio_server.sh 8787
##############################################

CWD="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
echo "cwd=$CWD"
export USER="${NB_USER}"
# set a user-specific secure cookie key
COOKIE_KEY_PATH="/tmp/rstudio-server/${USER}_secure-cookie-key"
rm -f "$COOKIE_KEY_PATH"
mkdir -p "$(dirname "$COOKIE_KEY_PATH")"

# Rserver >= version 1.3 requires the --auth-revocation-list-dir parameter
# Try to determine version, but fail gracefully - modern versions support revocation list
RSERVER_VERSION=$(/usr/lib/rstudio-server/bin/rserver --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
if [ -z "$RSERVER_VERSION" ]; then
  # If version detection fails, assume modern version supports revocation list
  REVOCATION_LIST_DIR="/tmp/rstudio-server/${USER}_revocation-list-dir"
  mkdir -p "$REVOCATION_LIST_DIR"
  REVOCATION_LIST_PAR="--auth-revocation-list-dir=$REVOCATION_LIST_DIR"
elif [ "$(echo "$RSERVER_VERSION" | cut -d. -f1)" -ge 1 ] && [ "$(echo "$RSERVER_VERSION" | cut -d. -f2)" -ge 3 ];
then
  REVOCATION_LIST_DIR="/tmp/rstudio-server/${USER}_revocation-list-dir"
  mkdir -p "$REVOCATION_LIST_DIR"
  REVOCATION_LIST_PAR="--auth-revocation-list-dir=$REVOCATION_LIST_DIR"
else
  REVOCATION_LIST_PAR=""
fi

python -c 'import uuid; print(uuid.uuid4())' > "$COOKIE_KEY_PATH"
chmod 600 "$COOKIE_KEY_PATH"

# store the currently activated conda environment in a file to be read by rsession.sh
CONDA_ENV_PATH="/tmp/rstudio-server/${USER}_current_env"
rm -f "$CONDA_ENV_PATH"
echo "## Current env is >>"
echo "$CONDA_PREFIX"
echo "$CONDA_PREFIX" > "$CONDA_ENV_PATH"

export RETICULATE_PYTHON="${CONDA_PREFIX}/bin/python"
# Prefer id -un (more robust), and EXPORT it

# Use user-specific database.conf in home directory instead of /opt
DB_CONF_PATH="${HOME}/.rstudio/database.conf"
sed -i "s|directory=.*|directory=/tmp/rstudio-server/${USER}_database|" "$DB_CONF_PATH"

# Jupyter server-proxy serves the launcher under the fixed /rstudio route.
BASE_PATH="${NB_PREFIX}/rstudio"

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
  --rsession-which-r="$(which R)" \
  --rsession-ld-library-path="${CONDA_PREFIX}/lib" \
  --rsession-path="$CWD/rsession.sh" \
  --server-user "$USER" \
  --database-config-file "$DB_CONF_PATH" \
  --auth-timeout-minutes=10080 \
  $REVOCATION_LIST_PAR

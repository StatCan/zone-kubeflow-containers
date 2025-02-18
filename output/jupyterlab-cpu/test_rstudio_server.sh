#!/bin/bash

set -e

if ! rstudio-server version; then
  echo "Error: rstudio-server is not installed or not functioning properly." >&2
  exit 1
fi

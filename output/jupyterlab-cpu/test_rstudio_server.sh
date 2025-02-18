#!/bin/bash

set -e

echo "Stopping rstudio-server..."
rstudio-server stop || true # Allow the script to continue if the server is not running.

echo "Checking rstudio-server status..."
rstudio-server status
rstudio-server verify-installation
rstudio-server version

echo "Restarting rstudio-server..."
rstudio-server start 

#!/bin/bash

set -e

echo "Stopping rstudio-server..."
sudo rstudio-server stop || true # Allow the script to continue if the server is not running.

echo "Checking rstudio-server status..."
sudo rstudio-server status
sudo rstudio-server verify-installation
sudo rstudio-server version

echo "Restarting rstudio-server..."
sudo rstudio-server start 

#!/usr/bin/env bash

# load conda env from file
CONDA_ENV=`cat /tmp/rstudio-server/${USER}_current_env`
echo "## CONDA ENV is >>>"
echo ${CONDA_ENV}

# Sanity
conda init
conda activate ${CONDA_ENV}

export RETICULATE_PYTHON=$CONDA_PREFIX/bin/python
# R libPath Isolation
export R_LIBS_USER="$CONDA_PREFIX/lib/R/library"
export R_LIBS_SITE="$CONDA_PREFIX/lib/R/library"


exec /usr/lib/rstudio-server/bin/rsession "$@"

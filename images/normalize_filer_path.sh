#! /bin/env bash
#
# File: normalize_filer_path.sh
#
# Author: Marcello Barisonzi <marcello.barisonzi@statcan.gc.ca>
#
# Purpose: Convert UNC path to Zone path
#
# Usage: 
# 1. edit the FILER_ROOT variable to the UNC root of your filer (e.g. \\<SERVER_NAME>\<BASE_FOLDER>)
# 2. edit the LOCAL_FILER_PATH to the filer folder on the Zone (e.g. `"/home/jovyan/filers/fldXfilersvm"`)
# 3. source this file: . normalize_filer_path.sh
# 4. run the command: nfp "<UNC_path>" (please remember the double quotes!)
# 5. if you want to test that the folder exists, run nfp "<UNC_path>" test

FILER_ROOT=""
LOCAL_FILER_PATH=""

function nfp() {

  echo "<=============================" 
  echo "Root filer folder: $FILER_ROOT" 
  echo "Input path: $1"
  echo

  # must double slashes for root filer
  norm_root=$(echo ${FILER_ROOT} | sed "s|\\\\|\\\\\\\\|g")

  #echo $norm_root

  norm_path=$(echo $1 | sed -e "s|${norm_root}|${LOCAL_FILER_PATH}|" -e  "s|\\\\|/|g")

  echo "=============================>" 
  echo "Normalized path: ${norm_path}"

  if [ "test" == "$2" ]
    then
        echo "Test:"
        ls -la ${norm_path}
  fi
}
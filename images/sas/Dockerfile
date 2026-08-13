#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=sas_kernel
FROM $BASE_IMAGE

USER root

# Jupyter SASStudio Proxy
COPY jupyter-sasstudio-proxy/ /opt/jupyter-sasstudio-proxy/
# --no-user: mid ships /opt/conda/pip.conf with [install] user = true. HOME is
# /home/jovyan even while building as root, so without it this build-time install
# would land in the image's /home/jovyan/.local -- which the workspace PVC hides
# at runtime, making the package vanish in production but not in `docker run`.
RUN pip install --no-user /opt/jupyter-sasstudio-proxy/

# Adds default workspace shortcut to sasstudio
COPY SWE.folderShortcuts.key /etc/sasstudio/preferences/SWE.folderShortcuts.key

# Enable X command on SAS Studio
COPY spawner_usermods.sh /usr/local/SASHome/studioconfig/spawner/

USER $NB_USER
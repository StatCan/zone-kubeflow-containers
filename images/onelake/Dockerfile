#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=base
FROM $BASE_IMAGE

USER root

# OneLake helper module and SDK for accessing Microsoft Fabric OneLake storage.
COPY onelake_utils.py /tmp/onelake_utils.py
COPY --chmod=755 onelake-configure.py /usr/local/bin/onelake-configure

RUN pip install --no-cache-dir \
        'azure-storage-file-datalake' \
        'azure-identity' \
    && python -c "from pathlib import Path; import shutil, sysconfig; dest = Path(sysconfig.get_paths()['purelib']) / 'onelake_utils.py'; shutil.copyfile('/tmp/onelake_utils.py', dest)" \
    && rm -f /tmp/onelake_utils.py \
    && fix-permissions "${CONDA_DIR}" \
    && fix-permissions "/home/${NB_USER}"

# Install blobfuse2 for OneLake FUSE filesystem mount.
# Configure the Microsoft repo explicitly so this layer does not depend on base-image apt state.
RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc -o /tmp/microsoft.asc \
    && gpg --batch --yes --dearmor -o /etc/apt/keyrings/microsoft.gpg /tmp/microsoft.asc \
    && chmod 0644 /etc/apt/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/prod jammy main" > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends fuse3 blobfuse2 \
    && (grep -qxF "user_allow_other" /etc/fuse.conf || echo "user_allow_other" >> /etc/fuse.conf) \
    && apt-get clean \
    && rm -f /tmp/microsoft.asc \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=${NB_USER}:${NB_GID} --chmod=755 s6/ /etc

USER $NB_USER

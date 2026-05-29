#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=base
FROM $BASE_IMAGE

USER root

COPY *.py /tmp/onelake/
COPY --chmod=755 onelake /usr/local/bin/onelake
COPY jupyter_server_config.d/onelake.json /tmp/onelake-jupyter-config.json
COPY onelake-r /tmp/onelake-r

RUN set -eux; \
    pip install --no-cache-dir \
        'azure-storage-file-datalake' \
        'jupyter-fs[fsspec]==1.1.2' \
        'requests'; \
    purelib="$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"; \
    install -d "$purelib"; \
    cp /tmp/onelake/*.py "$purelib/"; \
    printf '%s\n' 'import onelake_register' > "$purelib/onelake_fsspec_register.pth"; \
    R CMD INSTALL /tmp/onelake-r; \
    install -d -m 0755 /etc/jupyter/jupyter_server_config.d; \
    cp /tmp/onelake-jupyter-config.json /etc/jupyter/jupyter_server_config.d/onelake.json; \
    install -d -o "${NB_USER}" -g "${NB_GID}" -m 2775 "/home/${NB_USER}/.local/share/jupyter"; \
    rm -rf /tmp/onelake /tmp/onelake-jupyter-config.json /tmp/onelake-r; \
    fix-permissions "${CONDA_DIR}"; \
    fix-permissions "/home/${NB_USER}"

USER $NB_USER

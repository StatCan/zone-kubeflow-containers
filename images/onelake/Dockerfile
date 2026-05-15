#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=base
FROM $BASE_IMAGE

USER root

COPY onelake_utils.py /tmp/onelake_utils.py
COPY onelake_cli.py /tmp/onelake_cli.py
COPY onelake_fsspec.py /tmp/onelake_fsspec.py
COPY onelake_sitecustomize.py /tmp/onelake_sitecustomize.py
COPY --chmod=755 onelake /usr/local/bin/onelake
COPY jupyter_server_config.d/onelake.json /tmp/onelake-jupyter-config.json

RUN pip install --no-cache-dir \
        'azure-storage-file-datalake' \
        'jupyter-fs[fsspec]==1.1.2' \
        'requests' \
    && python -c "from pathlib import Path; import shutil, sysconfig; purelib = Path(sysconfig.get_paths()['purelib']); [shutil.copyfile(f'/tmp/{name}', purelib / name) for name in ('onelake_utils.py', 'onelake_cli.py', 'onelake_fsspec.py', 'onelake_sitecustomize.py')]; (purelib / 'onelake_fsspec_register.pth').write_text('import onelake_sitecustomize\\n')" \
    && install -d -m 0755 /etc/jupyter/jupyter_server_config.d \
    && cp /tmp/onelake-jupyter-config.json /etc/jupyter/jupyter_server_config.d/onelake.json \
    && install -d -o "${NB_USER}" -g "${NB_GID}" -m 2775 "/home/${NB_USER}/.local/share/jupyter" \
    && rm -f /tmp/onelake_utils.py /tmp/onelake_cli.py /tmp/onelake_fsspec.py /tmp/onelake_sitecustomize.py /tmp/onelake-jupyter-config.json \
    && fix-permissions "${CONDA_DIR}" \
    && fix-permissions "/home/${NB_USER}"

USER $NB_USER

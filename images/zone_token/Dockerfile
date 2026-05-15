#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=base
FROM $BASE_IMAGE

USER root

COPY zonetokenbroker.py /tmp/zonetokenbroker.py
COPY zone_token_cli.py /tmp/zone_token_cli.py
COPY --chmod=755 zone-token /usr/local/bin/zone-token
COPY zonetokenbroker-r /tmp/zonetokenbroker-r

RUN pip install --no-cache-dir \
        'requests' \
    && python -c "from pathlib import Path; import shutil, sysconfig; purelib = Path(sysconfig.get_paths()['purelib']); [shutil.copyfile(f'/tmp/{name}', purelib / name) for name in ('zonetokenbroker.py', 'zone_token_cli.py')]" \
    && R CMD INSTALL /tmp/zonetokenbroker-r \
    && rm -rf /tmp/zonetokenbroker.py /tmp/zone_token_cli.py /tmp/zonetokenbroker-r \
    && fix-permissions "${CONDA_DIR}" \
    && fix-permissions "/home/${NB_USER}"

USER $NB_USER

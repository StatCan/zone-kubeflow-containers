#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
# Otto: the mid image plus the `otto` coding assistant CLI.
# Kept as its own image so the agent can be piloted as an opt-in notebook
# flavour without touching the images every other notebook inherits from;
# folding it into mid later is this COPY/RUN block verbatim.
ARG BASE_IMAGE=mid
FROM $BASE_IMAGE

USER root

# `otto` in every terminal (broker-authenticated Azure OpenAI, no API
# keys). The wheel under /opt/otto/dist serves user-created venvs.
# /etc/otto is where the platform's model catalogue lands in prod
# (ConfigMap via PodDefault, see deploy/); the example documents the shape
# without activating anything.
COPY otto /opt/otto
COPY deploy/config-platform.toml.example /etc/otto/config.toml.example
RUN set -eux; \
    pip install --no-cache-dir --no-build-isolation /opt/otto; \
    pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /opt/otto/dist /opt/otto; \
    fix-permissions "${CONDA_DIR}"; \
    fix-permissions /opt/otto

USER $NB_USER

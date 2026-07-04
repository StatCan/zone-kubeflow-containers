#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
# Zone Agent: the mid image plus the `zone-agent` coding assistant CLI.
# Kept as its own image so the agent can be piloted as an opt-in notebook
# flavour without touching the images every other notebook inherits from;
# folding it into mid later is this COPY/RUN block verbatim.
ARG BASE_IMAGE=mid
FROM $BASE_IMAGE

USER root

# `zone-agent` in every terminal (broker-authenticated Azure OpenAI, no API
# keys). The wheel under /opt/zone-agent/dist serves user-created venvs.
# /etc/zone-agent is where the platform's model catalogue lands in prod
# (ConfigMap via PodDefault, see deploy/); the example documents the shape
# without activating anything.
COPY zone-agent /opt/zone-agent
COPY deploy/config-platform.toml.example /etc/zone-agent/config.toml.example
RUN set -eux; \
    pip install --no-cache-dir --no-build-isolation /opt/zone-agent; \
    pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /opt/zone-agent/dist /opt/zone-agent; \
    fix-permissions "${CONDA_DIR}"; \
    fix-permissions /opt/zone-agent

USER $NB_USER

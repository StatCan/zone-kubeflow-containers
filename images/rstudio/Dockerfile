#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=mid
FROM $BASE_IMAGE

USER root

# Install RStudio Server and keep the temporary CRAN apt source scoped to this
# layer.
ARG RSTUDIO_VERSION=2025.09.1-401
ARG RSTUDIO_SHA256=9a6b1ccf05a62e13bb7cab26b9ef5ba01445b58abb4a9f2c9868855e33613f1b
RUN apt-get update \
    && wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg \
    && echo "deb [signed-by=/etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg] https://cloud.r-project.org/bin/linux/ubuntu jammy-cran40/" > /etc/apt/sources.list.d/cran-r.list \
    && apt-get update \
    && curl --silent -L --fail "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/rstudio-server-${RSTUDIO_VERSION}-amd64.deb" > /tmp/rstudio.deb \
    && echo "${RSTUDIO_SHA256} /tmp/rstudio.deb" | sha256sum -c - \
    && apt-get install --no-install-recommends -y /tmp/rstudio.deb \
    && rm /tmp/rstudio.deb \
    && rm -f /etc/apt/sources.list.d/cran-r.list /etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Harden rstudio-server and route sessions through the selected Conda env.
COPY rsession.conf /etc/rstudio/

# Jupyter RStudio Proxy
COPY customRStu/ /opt/jupyter-custom-rstudio-proxy/
RUN chmod 755 /opt/jupyter-custom-rstudio-proxy/start_rstudio_server.sh \
    && chmod 755 /opt/jupyter-custom-rstudio-proxy/rsession.sh \
    && chmod 755 /opt/jupyter-custom-rstudio-proxy/rstudio-use-current-conda.sh \
    && pip install --no-cache-dir /opt/jupyter-custom-rstudio-proxy/ \
    && fix-permissions $CONDA_DIR

# Terminal helper to save the current Conda env and stop any running RStudio
# processes before relaunching from the Jupyter tile.
COPY --chmod=755 customRStu/rstudio-use-current-conda.sh /usr/local/bin/rstudio-use-current-conda

ENV PATH=$PATH:/usr/lib/rstudio-server/bin

USER $NB_USER

# Seed first-boot home defaults
RUN install -d -m 0775 \
    "${HOME_TMP}/.config/rstudio" \
    "${HOME_TMP}/.local/share/rstudio" \
    "${HOME_TMP}/.rstudio"

COPY --chown=${NB_USER}:${NB_GID} rstudio-prefs.json ${HOME_TMP}/.config/rstudio/rstudio-prefs.json
COPY --chown=${NB_USER}:${NB_GID} customRStu/database.conf ${HOME_TMP}/.rstudio/database.conf

RUN chmod -R g=u \
    "${HOME_TMP}/.config/rstudio" \
    "${HOME_TMP}/.local/share/rstudio" \
    "${HOME_TMP}/.rstudio"

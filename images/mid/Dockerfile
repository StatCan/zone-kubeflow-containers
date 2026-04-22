#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=base
FROM $BASE_IMAGE

USER root

# installs vscode server, python & conda packages, jupyter tooling, RStudio, and pixi

# Install vscode
ARG VSCODE_VERSION=4.99.4
ARG VSCODE_SHA=74c107b33643ed11223263b86431530fbc9c9f7c8202997579a6f0c41b4cb102
ARG VSCODE_URL=https://github.com/coder/code-server/releases/download/v${VSCODE_VERSION}/code-server_${VSCODE_VERSION}_amd64.deb

ENV CS_DISABLE_FILE_DOWNLOADS=1 \
    CS_DEFAULT_HOME=$HOME/.local/share/code-server \
    SERVICE_URL=https://extensions.coder.com/api

# Install code-server and supporting system packages.
RUN wget -q "${VSCODE_URL}" -O ./vscode.deb \
    && echo "${VSCODE_SHA}  ./vscode.deb" | sha256sum -c - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nginx build-essential gdb sqlite3 openmpi-bin libopenmpi-dev \
    && dpkg -i ./vscode.deb \
    && rm ./vscode.deb \
    && rm -f /etc/apt/sources.list.d/vscode.list \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=${NB_USER}:${NB_GID} vscode-overrides.json ${HOME_TMP}/.local/share/code-server/Machine/settings.json
# Fix for VSCode extensions and CORS
# Languagepacks.json needs to exist for code-server to recognize the languagepack
# Sets the default workspace for vscode
COPY --chown=${NB_USER}:${NB_GID} languagepacks.json coder.json ${HOME_TMP}/.local/share/code-server/

# Install Python dependencies, language tooling, and Jupyter server integration.
# Keep package manager cleanup in the same layer as the install work.
RUN mamba install --quiet --yes -c conda-forge \
        'sqlite>=3.45' \
        'pillow' \
        'pyyaml' \
        'joblib==1.2.0' \
        's3fs' \
        'fire' \
        'mkl' \
        'graphviz' \
        'nodejs' \
        'pkg-config' \
        'jupyterlab' \
        'dash' \
        'plotly' \
        'ipywidgets' \
        'markupsafe' \
        'ipympl' \
        'pexpect==4.9.0' \
        'jupyter-resource-usage' \
        'jupyter-server-proxy==4.2.0' \
        'jupyterlab-language-pack-fr-fr' \
        'jupyterlab_execute_time' \
        'nb_conda_kernels' \
        'jupyterlab-lsp' \
        'jupyter-lsp' \
        'python-lsp-server' \
        'r-arrow' \
        'r-aws.s3' \
        'r-base=4.5.1' \
        'r-catools' \
        'r-e1071' \
        'r-hdf5r' \
        'r-markdown' \
        'r-odbc' \
        'r-renv' \
        'r-rodbc' \
        'r-sf' \
        'r-sparklyr' \
        'r-tidyverse' \
        'duckdb' \
        'duckdb-cli' \
        'python-duckdb' \
    && pip install --no-cache-dir \
        'kubeflow-training' \
        'git+https://github.com/betatim/vscode-binder' \
        'jupyter-rsession-proxy==2.2.0' \
        'pyspark[ml]==3.5.5' \
    && /opt/conda/bin/R --silent --slave --no-save --no-restore -e 'install.packages("languageserver", repos="https://cran.r-project.org/")' \
    && jupyter server extension enable --sys-prefix --py jupyter_server_proxy \
    && jupyter lab build --dev-build=False --minimize=False \
    && jupyter lab clean \
    && npm i -g \
        'bash-language-server' \
        'dockerfile-language-server-nodejs' \
        'javascript-typescript-langserver' \
        'unified-language-server' \
        'yaml-language-server' \
    && clean-layer.sh \
    && rm -rf /root/.cache /root/.npm \
    && fix-permissions $CONDA_DIR

# Install DuckDB extensions for parquet visualizer (air-gapped support)
COPY --chown=${NB_USER}:${NB_GID} .duckdbrc ${HOME_TMP}/.duckdbrc

# Solarized Theme and Cell Execution Time
COPY jupyterlab-overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json

# install rstudio-server
ARG RSTUDIO_VERSION=2025.09.1-401
ARG SHA256=9a6b1ccf05a62e13bb7cab26b9ef5ba01445b58abb4a9f2c9868855e33613f1b
RUN apt-get update \
    && wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg \
    && echo "deb [signed-by=/etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg] https://cloud.r-project.org/bin/linux/ubuntu jammy-cran40/" > /etc/apt/sources.list.d/cran-r.list \
    && apt-get update \
    && curl --silent -L --fail "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/rstudio-server-${RSTUDIO_VERSION}-amd64.deb" > /tmp/rstudio.deb \
    && echo "${SHA256} /tmp/rstudio.deb" | sha256sum -c - \
    && apt-get install --no-install-recommends -y /tmp/rstudio.deb \
    && rm /tmp/rstudio.deb \
    && rm -f /etc/apt/sources.list.d/cran-r.list /etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Harden rstudio-server - copy config files
# See: https://github.com/rstudio/rstudio/issues/14060 for rsession-ld-library-path
COPY rserver.conf rsession.conf /etc/rstudio/

COPY --chown=${NB_USER}:${NB_GID} rstudio-prefs.json ${HOME_TMP}/.config/rstudio/rstudio-prefs.json

ENV PATH=$PATH:/usr/lib/rstudio-server/bin \
    SPARK_HOME="/opt/conda/lib/python3.13/site-packages/pyspark" \
    R_ZIPCMD="zip"

# Configure container startup
COPY pip.conf /etc/pip.conf
COPY --chmod=755 keep-alive.sh /usr/local/bin/

# SSL Certs
# https://jirab.statcan.ca/browse/ZONE-274?focusedId=3674862&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-3674862
COPY --from=k8scc01covidacr.azurecr.io/publiccerts:latest /home/certs/ /opt/conda/ssl/certs
RUN echo >> /opt/conda/ssl/cacert.pem \
    && cd /opt/conda/ssl/certs/ \
    && for file in *.crt; do (echo "# ${file}"; cat "${file}"; echo) >> /opt/conda/ssl/cacert.pem; done

ENV REQUESTS_CA_BUNDLE=/opt/conda/ssl/cacert.pem

# s6 - copy scripts
COPY --chown=${NB_USER}:${NB_GID} --chmod=755 s6/ /etc

USER $NB_USER

# Build the first-boot home skeleton as jovyan so user-writable content is created
# from the same context that will later consume it on mounted storage.
RUN install -d -m 0775 \
    "${HOME_TMP}/.cache" \
    "${HOME_TMP}/.cache/pip" \
    "${HOME_TMP}/.config/rstudio" \
    "${HOME_TMP}/.config/pip" \
    "${HOME_TMP}/.gnupg" \
    "${HOME_TMP}/.ipython" \
    "${HOME_TMP}/.jupyter" \
    "${HOME_TMP}/.local/bin" \
    "${HOME_TMP}/.local/share/rstudio" \
    "${HOME_TMP}/.local/share/code-server/Machine" \
    "${HOME_TMP}/.local/share/code-server/User" \
    "${HOME_TMP}/.rstudio" \
    "${HOME_TMP}/workspace/.vscode" \
    "${HOME_TMP}/workspace/data" \
    "${HOME_TMP}/workspace/repositories" \
    && export HOME="${HOME_TMP}" \
    && wget -q https://github.com/microsoft/vscode-cpptools/releases/download/v1.20.5/cpptools-linux.vsix -O "${HOME_TMP}/cpptools-linux.vsix" \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension ms-python.python@2025.4.0 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension ms-python.debugpy@2025.4.0 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension Posit.air-vscode@0.22.0 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension ms-ceintl.vscode-language-pack-fr@1.99.0 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension adamviola.parquet-explorer@1.2.1 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension lucien-martijn.parquet-visualizer@0.31.1 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension redhat.vscode-yaml@1.15.0 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension ms-vscode.azurecli@0.6.0 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension mblode.pretty-formatter@0.2.1 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension "${HOME_TMP}/cpptools-linux.vsix" \
    && rm -f "${HOME_TMP}/cpptools-linux.vsix" \
    && wget -qO- https://pixi.sh/install.sh | sh \
    && DUCK_BIN="/opt/conda/bin/duckdb" \
    && DUCK_VER="$($DUCK_BIN --version | cut -d' ' -f1)" \
    && ABI_VER="v$(echo "$DUCK_VER" | sed 's/^v//' | cut -d'.' -f1-2).0" \
    && mkdir -p "${HOME_TMP}/.duckdb/extensions/${ABI_VER}/linux_amd64/" \
    && $DUCK_BIN -c "INSTALL spatial; INSTALL httpfs; INSTALL icu; INSTALL avro; INSTALL parquet;"

ENV EXTENSIONS_GALLERY='{"serviceUrl":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/api","itemUrl":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/item","resourceUrlTemplate":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/files/{publisher}/{name}/{version}/{path}"}'

# Seed first-boot home defaults without cloning large runtime-managed directories.
RUN set -eu \
    && for entry in "${HOME}"/* "${HOME}"/.[!.]* "${HOME}"/..?*; do \
        [ -e "${entry}" ] || continue; \
        case "$(basename "${entry}")" in \
            .cache|.conda|.duckdb|.duckdbrc|.gnupg|.julia|.local|.mamba|.npm|.pixi|workspace) continue ;; \
        esac; \
        cp -r --update=none "${entry}" "${HOME_TMP}/"; \
    done \
    && git config --file "${HOME_TMP}/.gitconfig" credential.credentialStore gpg \
    && git config --file "${HOME_TMP}/.gitconfig" credential.helper manager \
    && { \
        printf 'export GPG_TTY=$(tty)\n'; \
        printf 'eval "$(pixi completion --shell bash)"\n'; \
    } >> "${HOME_TMP}/.bashrc"

# Copy over various files that should be restored into HOME on first boot.
COPY --chown=${NB_USER}:${NB_GID} .Rprofile .profile .condarc connect-to-filer.md ${HOME_TMP}/
COPY --chown=${NB_USER}:${NB_GID} gpg-agent.conf ${HOME_TMP}/.gnupg/gpg-agent.conf

# Set Python interpreter path for VSCode
COPY --chown=${NB_USER}:${NB_GID} vscode_settings.json ${HOME_TMP}/workspace/.vscode/settings.json

# Python default user settings for VSCode
COPY --chown=${NB_USER}:${NB_GID} vscode_user_settings.json ${HOME_TMP}/.local/share/code-server/User/settings.json

# add rm wrapper
# https://jirab.statcan.ca/browse/ZPS-40
COPY --chown=${NB_USER}:${NB_GID} --chmod=775 rm ${HOME_TMP}/.local/bin/rm

RUN install -d -m 2775 "${HOME}/.cache" "${HOME_TMP}/.cache" \
    && chmod -R g=u "${HOME_TMP}" \
    && chmod 700 "${HOME_TMP}/.gnupg" \
    && chmod 2775 "${HOME}/.cache" "${HOME_TMP}/.cache"

EXPOSE 8888

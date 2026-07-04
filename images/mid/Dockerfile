#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=base
FROM $BASE_IMAGE

USER root

# installs vscode server, Python/R packages, Jupyter tooling, language servers, and pixi

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
        'r-httr' \
        'r-jsonlite' \
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
        'pyspark[ml]==3.5.5' \
        'banff' \
        'banffprocessor' \
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

# Zone AuthService delegated-token helper — Python module + R wrapper.
# Provides `import zone_token_broker` in Python and `library(zonetokenbroker)`
# in R for any downstream consumer (OneLake DFS, Fabric REST, etc.) that needs
# to call the in-cluster AuthService getPassthroughToken endpoint.
# Installed here in mid, after the mamba install, so it targets the final conda
# env: the Python site-packages and the pinned r-base=4.5.1 R library. httr is
# provided by conda-forge (r-httr, in the mamba list above).
COPY zone-token-broker /tmp/zone-token-broker
RUN set -eux; \
    pip install --no-cache-dir 'requests'; \
    purelib="$(/opt/conda/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"; \
    install -d "$purelib"; \
    install -m 0644 /tmp/zone-token-broker/zone_token_broker.py "$purelib/zone_token_broker.py"; \
    /opt/conda/bin/R CMD INSTALL /tmp/zone-token-broker/zone-token-broker-r; \
    rm -rf /tmp/zone-token-broker; \
    fix-permissions "${CONDA_DIR}"

# Install DuckDB extensions for parquet visualizer (air-gapped support)
COPY --chown=${NB_USER}:${NB_GID} .duckdbrc ${HOME_TMP}/.duckdbrc

# Solarized Theme and Cell Execution Time
COPY jupyterlab-overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json

ENV SPARK_HOME="/opt/conda/lib/python3.13/site-packages/pyspark" \
    R_ZIPCMD="zip"

# Configure container startup
COPY pip.conf /etc/pip.conf
COPY --chmod=755 keep-alive.sh /usr/local/bin/

# SSL Certs
# https://jirab.statcan.ca/browse/ZONE-274?focusedId=3674862&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-3674862
# Added cert from: https://jirab.statcan.ca/browse/ZONE-349
COPY --from=k8scc01covidacr.azurecr.io/publiccerts:stcthn /home/certs/ /opt/conda/ssl/certs
RUN echo >> /opt/conda/ssl/cacert.pem \
    && cd /opt/conda/ssl/certs/ \
    && for file in *.crt; do (echo "# ${file}"; cat "${file}"; echo) >> /opt/conda/ssl/cacert.pem; done

ENV REQUESTS_CA_BUNDLE=/opt/conda/ssl/cacert.pem

# Ensure the image home stays owned by jovyan:user before we drop privileges.
RUN install -d -o "${NB_USER}" -g "${NB_GID}" -m 2775 "${HOME}/.cache" \
    && fix-permissions "/home/${NB_USER}"

# s6 - copy scripts
COPY --chown=${NB_USER}:${NB_GID} --chmod=755 s6/ /etc

USER $NB_USER

# Build the first-boot home skeleton as jovyan so user-writable content is created
# from the same context that will later consume it on mounted storage.
RUN install -d -m 0775 \
    "${HOME_TMP}/.cache" \
    "${HOME_TMP}/.cache/pip" \
    "${HOME_TMP}/.config/pip" \
    "${HOME_TMP}/.gnupg" \
    "${HOME_TMP}/.ipython" \
    "${HOME_TMP}/.jupyter" \
    "${HOME_TMP}/.local/bin" \
    "${HOME_TMP}/.local/share/code-server/Machine" \
    "${HOME_TMP}/.local/share/code-server/User" \
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

RUN install -d -m 2775 "${HOME_TMP}/.cache" \
    && chmod -R g=u "${HOME_TMP}" \
    && chmod 700 "${HOME_TMP}/.gnupg" \
    && chmod 2775 "${HOME_TMP}/.cache"

# ---- Zone Browser: in-pod sign-in without the device-code grant -----------
# Kept as the LAST layers on purpose: everything above cache-hits from the
# registry, so builds only create and export these layers. When this block
# sat mid-file it invalidated every layer below it and the resulting
# full-image export exhausted the CI runner's disk (runner shutdown during
# "exporting layers").
#
# A headless Chromium runs inside the pod, so `az login`, azure-identity and
# R AzureAuth use their default interactive (authorization-code) flow --
# MSAL's localhost redirect server and the browser share the pod's network
# namespace, and sign-in traffic egresses from the StatCan network, never
# the user's device. The browser appears as a tab INSIDE JupyterLab:
# zone-browser-viewer.py streams Chromium's screen over the Chrome DevTools
# Protocol through jupyter-server-proxy (no X server, no VNC), and the
# prebuilt zone-browser-autoopen labextension (~25 KB static JS, see
# zone-browser/README.md to rebuild) opens the tab automatically when a
# sign-in starts. Ubuntu's chromium package is a snap stub, so the
# Playwright Chromium build is installed under /opt/ms-playwright; the
# playwright pip package is only a downloader and is removed afterwards.
# BROWSER/R_BROWSER route Python's webbrowser module and R's browseURL()
# to the in-pod browser automatically.
USER root

COPY --chmod=755 zone-browser/zone-browser /usr/local/bin/zone-browser
COPY --chmod=755 zone-browser/zone-browser-viewer.py /usr/local/bin/zone-browser-viewer.py
COPY zone-browser/labextension/dist-labext /opt/conda/share/jupyter/labextensions/zone-browser-autoopen
COPY zone-browser/zone-browser-serverproxy.json /tmp/zone-browser-serverproxy.json
COPY --chown=${NB_USER}:${NB_GID} --chmod=664 azure-sign-in.md ${HOME_TMP}/azure-sign-in.md
ENV BROWSER=/usr/local/bin/zone-browser \
    R_BROWSER=/usr/local/bin/zone-browser
# The ServerProxy traitlets must live in jupyter_server_config.json (the
# jupyter_server_config.d/ directory only handles extension enablement).
# Merge rather than overwrite in case the base image ships its own config.
RUN python -c "\
import json, os; \
path = '/opt/conda/etc/jupyter/jupyter_server_config.json'; \
os.makedirs(os.path.dirname(path), exist_ok=True); \
cfg = json.load(open(path)) if os.path.exists(path) else {}; \
add = json.load(open('/tmp/zone-browser-serverproxy.json')); \
cfg.setdefault('ServerProxy', {}).setdefault('servers', {}).update(add['ServerProxy']['servers']); \
json.dump(cfg, open(path, 'w'), indent=2)" \
    && rm /tmp/zone-browser-serverproxy.json \
    && apt-get update \
    # Explicit headless-Chromium runtime deps instead of `playwright install
    # --with-deps`, which drags in ~800 MB (a mesa/LLVM upgrade, xvfb, CJK
    # font packs) that headless rendering never uses -- the resulting layer
    # starved CI runners of memory during image export. Most of these are
    # already in the image; listing them keeps the set explicit and cheap.
    && apt-get install -y --no-install-recommends \
        libnss3-tools \
        at-spi2-common libatk1.0-0t64 libatk-bridge2.0-0t64 libatspi2.0-0t64 \
        libasound2t64 libcairo2 libcups2t64 libdbus-1-3 libdrm2 libgbm1 \
        libglib2.0-0t64 libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 \
        libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 \
        libxrandr2 fonts-liberation fonts-noto-color-emoji \
    && pip install --no-cache-dir 'playwright==1.61.0' \
    && PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright playwright install chromium \
    && pip uninstall --yes playwright \
    && chmod -R a+rX /opt/ms-playwright \
    && fix-permissions /opt/conda/share/jupyter/labextensions/zone-browser-autoopen \
    # `az login` refuses interactive auth on Linux unless a GUI env var is
    # set; no X server exists -- the value only satisfies that check, the
    # browser itself is headless and driven over the DevTools Protocol.
    && echo 'export DISPLAY="${DISPLAY:-:20}"' >> /etc/bash.bashrc \
    && echo 'export DISPLAY="${DISPLAY:-:20}"' >> /etc/zsh/zshrc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.cache /root/.npm

USER $NB_USER

EXPOSE 8888

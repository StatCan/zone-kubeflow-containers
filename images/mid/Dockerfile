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

# Internal wheels installed from file in the pip step below (GitHub CI cannot
# reach StatCan Artifactory/GitLab); kept in the image so users can install
# them into their own environments too. See vendor/README.md.
COPY vendor/ /opt/vendor/

# System libraries required by the R packages installed further below (union
# of Posit Package Manager's sysreqs for that package set on Ubuntu 24.04,
# minus what images/base already installs). -dev variants so source installs
# of related CRAN packages also work for users.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        gdal-bin \
        libabsl-dev \
        libgdal-dev \
        libgeos-dev \
        libgit2-dev \
        libhdf5-dev \
        libicu-dev \
        libproj-dev \
        libsqlite3-dev \
        libudunits2-dev \
        libuv1-dev \
        libwebp-dev \
        libx11-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies, language tooling, and Jupyter server integration.
# Keep package manager cleanup in the same layer as the install work.
# NOTE: R is deliberately absent here -- the interpreter comes from CRAN's apt
# repository (images/base) and R packages from Posit Package Manager (below),
# so R upgrades no longer wait on conda-forge's r-* migration cycle.
RUN mamba install --quiet --yes -c conda-forge \
        'sqlite>=3.45' \
        'pillow' \
        'pyyaml' \
        # banff dependency: PyPI publishes no cp314 wheels inside banff's
        # nanoarrow<0.9 pin, but conda-forge ships py314 builds of 0.8.0
        'nanoarrow' \
        'joblib==1.5.3' \
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
        'jupyter-server-proxy==4.5.0' \
        'jupyterlab-language-pack-fr-fr' \
        'jupyterlab_execute_time' \
        'nb_conda_kernels' \
        'jupyterlab-lsp' \
        'jupyter-lsp' \
        'python-lsp-server' \
        'duckdb' \
        'duckdb-cli' \
        'python-duckdb' \
    && pip install --no-cache-dir \
        'kubeflow-training' \
        'git+https://github.com/betatim/vscode-binder' \
        # PySpark 4.x is required on Python 3.14 (3.5.x supports <=3.11).
        # NOTE: Spark major-version jump -- also affects r-sparklyr users.
        'pyspark[ml]==4.2.0' \
        # banff + banffprocessor: vendored internal wheels (see
        # vendor/README.md); their public PyPI releases pin pyarrow<19,
        # unsatisfiable on Python 3.14. banffprocessor requires banff>=3.2.0,
        # satisfied by the wheel alongside it.
        /opt/vendor/banff-*.whl \
        /opt/vendor/banffprocessor-*.whl \
        # Python<->R bridge; previously shipped by the datascience-notebook
        # base via conda, now built here against the system R.
        'rpy2' \
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

# R packages as prebuilt Linux binaries from Posit Package Manager -- the same
# set that previously came from conda-forge. Installed into the system R's
# site library; install.packages() does not fail on error, so verify the full
# set landed before the layer is accepted.
ARG PPM_CRAN_URL=https://packagemanager.posit.co/cran/__linux__/noble/latest
RUN Rscript -e "options(HTTPUserAgent = sprintf('R/%s R (%s)', getRversion(), paste(getRversion(), R.version['platform'], R.version['arch'], R.version['os']))); \
                pkgs <- c('arrow', 'aws.s3', 'caret', 'caTools', 'crayon', 'devtools', 'e1071', \
                          'forecast', 'hdf5r', 'hexbin', 'htmltools', 'htmlwidgets', 'httr', \
                          'jsonlite', 'languageserver', 'markdown', 'nycflights13', 'odbc', \
                          'randomForest', 'RCurl', 'renv', 'reticulate', 'rmarkdown', 'RODBC', \
                          'RSQLite', 'sf', 'shiny', 'sparklyr', 'tidymodels', 'tidyverse'); \
                install.packages(pkgs, repos = '${PPM_CRAN_URL}', Ncpus = parallel::detectCores()); \
                missing <- setdiff(pkgs, rownames(installed.packages())); \
                if (length(missing) > 0) stop('failed to install: ', paste(missing, collapse = ', '))" \
    && rm -rf /tmp/downloaded_packages /tmp/Rtmp*

# Zone AuthService delegated-token helper — Python package + R wrapper.
# Provides `import zone_token_broker` in Python and `library(zonetokenbroker)`
# in R for any downstream consumer (OneLake DFS, Fabric REST, etc.) that needs
# to call the in-cluster AuthService getPassthroughToken endpoint.
# Installed here in mid, after the mamba install, so it targets the final conda
# env and leaves source/wheel artifacts under /opt/zone-token-broker for
# user-created Python and R environments. httr is provided by the Posit
# Package Manager install above.
# adlfs provides the fsspec adapter for pandas/read_csv("az://...") workflows
# that pass zone_token_broker.async_credential(...).
COPY zone-token-broker /opt/zone-token-broker
RUN set -eux; \
    pip install --no-cache-dir 'adlfs==2026.5.0'; \
    pip install --no-cache-dir --no-build-isolation '/opt/zone-token-broker[zone-dvc]'; \
    pip wheel --no-cache-dir --no-deps --no-build-isolation --wheel-dir /opt/zone-token-broker/dist /opt/zone-token-broker; \
    /usr/bin/R CMD INSTALL /opt/zone-token-broker/zone-token-broker-r; \
    fix-permissions "${CONDA_DIR}"; \
    fix-permissions /opt/zone-token-broker

# System R loads Ubuntu OpenSSL before reticulate embeds Conda Python. Build
# just CPython's OpenSSL extension modules against that already-loaded ABI,
# shadow the declared user-facing wheels whose Conda ELF graphs reach Conda
# OpenSSL, and retain py-rattler's self-contained wheel for audit closure.
# Built here in mid (rather than images/rstudio) so every R entry point in
# the published images -- terminal R/Rscript, the Jupyter IR kernel, R in
# VSCode terminals, and RStudio downstream -- shares one overlay. Standalone
# /opt/conda Python is unchanged: the overlay is selected only through the
# R-session environment (Renviron.site below and the rsession wrapper in
# images/rstudio), never for Python started outside R.
ARG CPYTHON_VERSION=3.14.5
ARG CPYTHON_SHA256=7e32597b99e5d9a39abed35de4693fa169df3e5850d4c334337ffd6a19a36db6
COPY reticulate-compat-requirements.txt audit-reticulate-compat.py /opt/reticulate-compat-build/
RUN set -eux; \
    build_dir="$(mktemp -d /tmp/reticulate-cpython.XXXXXX)"; \
    source_archive="${build_dir}/Python-${CPYTHON_VERSION}.tar.xz"; \
    curl --fail --location --silent --show-error \
      "https://www.python.org/ftp/python/${CPYTHON_VERSION}/Python-${CPYTHON_VERSION}.tar.xz" \
      --output "${source_archive}"; \
    echo "${CPYTHON_SHA256}  ${source_archive}" | sha256sum -c -; \
    tar --extract --file "${source_archive}" --directory "${build_dir}"; \
    cd "${build_dir}/Python-${CPYTHON_VERSION}"; \
    PKG_CONFIG=/usr/bin/pkg-config ./configure \
      --with-openssl=/usr \
      --with-openssl-rpath=no \
      --without-ensurepip; \
    make -j"$(nproc)" sharedmods; \
    compat_python="/opt/reticulate-compat/lib/python3.14"; \
    compat_dynload="${compat_python}/lib-dynload"; \
    compat_site="${compat_python}/site-packages"; \
    install -d -m 0755 "${compat_dynload}" "${compat_site}"; \
    test -f Modules/_ssl.cpython-314-x86_64-linux-gnu.so; \
    test -f Modules/_hashlib.cpython-314-x86_64-linux-gnu.so; \
    install -m 0644 \
      Modules/_ssl.cpython-314-x86_64-linux-gnu.so \
      "${compat_dynload}/_ssl.cpython-314-x86_64-linux-gnu.so"; \
    install -m 0644 \
      Modules/_hashlib.cpython-314-x86_64-linux-gnu.so \
      "${compat_dynload}/_hashlib.cpython-314-x86_64-linux-gnu.so"; \
    /opt/conda/bin/python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      --no-deps \
      --only-binary=:all: \
      --require-hashes \
      --target "${compat_site}" \
      --requirement /opt/reticulate-compat-build/reticulate-compat-requirements.txt; \
    /opt/conda/bin/python /opt/reticulate-compat-build/audit-reticulate-compat.py \
      --conda-prefix /opt/conda \
      --overlay-root /opt/reticulate-compat; \
    touch /opt/reticulate-compat/.audit-passed; \
    chmod -R a+rX /opt/reticulate-compat; \
    cd /; \
    rm -rf "${build_dir}" /opt/reticulate-compat-build

# Give every system-R session (terminal R/Rscript, Jupyter IR kernel, R in
# VSCode terminals) the same reticulate contract the RStudio rsession wrapper
# provides: embed the image's Conda Python deterministically instead of
# letting reticulate auto-provision an interpreter (uv is unreachable
# in-cluster), and put the OpenSSL-compatible overlay ahead of the Conda
# native modules that cannot load next to Ubuntu OpenSSL. The ${VAR-...}
# guards keep any value already present in the environment -- a user's
# explicit RETICULATE_PYTHON/PYTHONPATH, or the rsession wrapper's own
# fail-closed exports -- authoritative over these defaults. Conda-R
# environments read their own Renviron.site and are unaffected.
RUN printf '%s\n' \
    '# Reticulate defaults for system-R sessions; see images/mid/Dockerfile.' \
    'RETICULATE_PYTHON=${RETICULATE_PYTHON-/opt/conda/bin/python}' \
    'PYTHONPATH=${PYTHONPATH-/opt/reticulate-compat/lib/python3.14/lib-dynload:/opt/reticulate-compat/lib/python3.14/site-packages}' \
    >> /etc/R/Renviron.site

# App Service managed-identity emulation: azure-identity and MSAL (so
# `az login --identity` too) detect these env vars and speak the 2019-08-01
# protocol to the zone-msi-shim s6 service, which exchanges the requested
# resource for a user-delegated token via zone_token_broker. IDENTITY_HEADER
# is a static value on purpose: the shim binds loopback inside a single-user
# pod, so the header only exists to satisfy the protocol, not to gate access.
ENV IDENTITY_ENDPOINT=http://127.0.0.1:8901/msi/token \
    IDENTITY_HEADER=zone

# Install DuckDB extensions for parquet visualizer (air-gapped support)
COPY --chown=${NB_USER}:${NB_GID} .duckdbrc ${HOME_TMP}/.duckdbrc

# Solarized Theme and Cell Execution Time
COPY jupyterlab-overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json

# Python version: tracks the CI-built scipy-notebook chain (Python 3.14 --
# see the upstream-scipy job in .github/workflows/docker.yaml). banff comes
# from the vendored internal 3.2.x wheel; public PyPI banff/banffprocessor
# pins (pyarrow<19) cannot be satisfied on 3.14.
ENV SPARK_HOME="/opt/conda/lib/python3.14/site-packages/pyspark" \
    R_ZIPCMD="zip"

# Configure container startup
COPY pip.conf /etc/pip.conf
COPY --chmod=755 keep-alive.sh /usr/local/bin/

# SSL Certs
# https://jirab.statcan.ca/browse/ZONE-274?focusedId=3674862&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-3674862
# Added cert from: https://jirab.statcan.ca/browse/ZONE-349
COPY --from=stcthezoneacr.azurecr.io/publiccerts:stcthn /home/certs/ /opt/conda/ssl/certs
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
    # ms-python/debugpy releases that support Python 3.14: 2025.4.0 predates
    # the 3.14 interpreter and mis-drives its new REPL ("Run Python File"
    # pastes the shell command into the PyREPL -> SyntaxError), and its
    # bundled debugpy has no 3.14 support. Both still target VS Code >=1.95,
    # within this code-server (1.99).
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension ms-python.python@2026.4.0 \
    && CS_DEFAULT_HOME="${HOME_TMP}/.local/share/code-server" code-server --install-extension ms-python.debugpy@2026.6.0 \
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
COPY --chown=${NB_USER}:${NB_GID} .Rprofile .profile .condarc connect-to-filer.md azure-sign-in.md ${HOME_TMP}/
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

EXPOSE 8888

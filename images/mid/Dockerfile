#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=base
FROM $BASE_IMAGE

USER root

# installs vscode server, python & conda packages and jupyter lab extensions.
# also installs r-studio and pixi

# Using JupyterLab 3.0 inherited docker-stacks base image. A few extensions we used to install and don't support
# this version of Jupyterlab and/or are not OL-compliant so they have been removed until new compatible versions are available:
# jupyterlab-kale
# jupyterlab-variableinspector
# jupyterlab-archive
# jupyterlab-spellchecker
# jupyterlab-spreadsheet

# Install vscode
ARG VSCODE_VERSION=4.99.4
ARG VSCODE_SHA=74c107b33643ed11223263b86431530fbc9c9f7c8202997579a6f0c41b4cb102
ARG VSCODE_URL=https://github.com/coder/code-server/releases/download/v${VSCODE_VERSION}/code-server_${VSCODE_VERSION}_amd64.deb

ENV CS_DISABLE_FILE_DOWNLOADS=1
ENV CS_DEFAULT_HOME=$HOME/.local/share/code-server
ENV SERVICE_URL=https://extensions.coder.com/api

RUN wget -q "${VSCODE_URL}" -O ./vscode.deb \
    && echo "${VSCODE_SHA}  ./vscode.deb" | sha256sum -c - \
    && wget -q https://github.com/microsoft/vscode-cpptools/releases/download/v1.20.5/cpptools-linux.vsix \
    && apt-get update \
    && apt-get install -y --no-install-recommends nginx build-essential gdb sqlite3 openmpi-bin libopenmpi-dev \
    && dpkg -i ./vscode.deb \
    && rm ./vscode.deb \
    && rm -f /etc/apt/sources.list.d/vscode.list \
    && mkdir -p $CS_DEFAULT_HOME/Machine \
    && \
    code-server --install-extension ms-python.python@2025.4.0 && \
    code-server --install-extension ms-python.debugpy@2025.4.0 && \
    code-server --install-extension REditorSupport.r@2.8.4 && \
    code-server --install-extension ms-ceintl.vscode-language-pack-fr@1.99.0 && \
    code-server --install-extension quarto.quarto@1.113.0 && \
    code-server --install-extension adamviola.parquet-explorer@1.2.1 && \
    code-server --install-extension lucien-martijn.parquet-visualizer@0.31.1 && \
    code-server --install-extension redhat.vscode-yaml@1.15.0 && \
    code-server --install-extension ms-vscode.azurecli@0.6.0 && \
    code-server --install-extension mblode.pretty-formatter@0.2.1 && \
    code-server --install-extension cpptools-linux.vsix \
    && rm cpptools-linux.vsix \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && fix-permissions $CS_DEFAULT_HOME

ENV EXTENSIONS_GALLERY='{"serviceUrl":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/api","itemUrl":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/item","resourceUrlTemplate":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/files/{publisher}/{name}/{version}/{path}"}'
COPY vscode-overrides.json $CS_DEFAULT_HOME/Machine/settings.json
COPY languagepacks.json coder.json $CS_DEFAULT_HOME/

# Install Python dependencies and tools
RUN mamba install --quiet --yes -c conda-forge \
    'duckdb=1.4.3' \
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
    && pip install --no-cache-dir \
    'kubeflow-training' \
    'git+https://github.com/betatim/vscode-binder' \
    'jupyter-rsession-proxy==2.2.0' \
    'pyspark[ml]==3.5.5' \
    && jupyter server extension enable --py jupyter_server_proxy \
    && jupyter labextension enable \
    '@jupyterlab/translation-extension' \
    '@jupyterlab/server-proxy' \
    'nbdime-jupyterlab' \
    && jupyter lab build \
    && jupyter lab clean \
    && clean-layer.sh \
    && rm -rf /home/$NB_USER/.cache/yarn \
    && rm -rf /home/$NB_USER/.node-gyp \
    && fix-permissions $CONDA_DIR \
    && fix-permissions /home/$NB_USER

# ---- DuckDB spatial extension (air gapped) ----
ENV DUCKDB_EXTENSION_DIRECTORY=/opt/duckdb/extensions
RUN mkdir -p /opt/duckdb/extensions/v1.4.3/linux_amd64
COPY duckdb_extensions/v1.4.3/linux_amd64/spatial.duckdb_extension.gz \
     /opt/duckdb/extensions/v1.4.3/linux_amd64/

# Install python, R, Julia and other useful language servers
RUN julia -e 'using Pkg; Pkg.add("LanguageServer")' \
    && /opt/conda/bin/R --silent --slave --no-save --no-restore -e 'install.packages("languageserver", repos="https://cran.r-project.org/")' \
    && mamba install -c conda-forge --quiet --yes 'python-lsp-server' \
    && npm i -g \
    'bash-language-server'  \
    'dockerfile-language-server-nodejs' \
    'javascript-typescript-langserver' \
    'unified-language-server' \
    'yaml-language-server' \
    && npm cache clean --force \
    && rm -rf /root/.npm \
    && clean-layer.sh \ 
    && fix-permissions $CONDA_DIR \
    && fix-permissions /home/$NB_USER

USER $NB_USER

# Disable DuckDB autoinstall in air gapped env
RUN mkdir -p ${HOME}/.duckdb \
    && echo "SET extension_directory='/opt/duckdb/extensions';" >> ${HOME}/.duckdbrc \
    && echo "SET autoinstall_extensions=false;" >> ${HOME}/.duckdbrc \
    && echo "SET autoload_extensions=true;" >> ${HOME}/.duckdbrc

# Setup default user env
RUN mkdir -p ${HOME}/workspace \
    && mkdir -p ${HOME}/workspace/repositories \
    && mkdir -p ${HOME}/workspace/data \
    && mkdir -p ${HOME}/workspace/.vscode \
    && mkdir -p ${HOME}/.local/share/code-server/User \
    && git config --global credential.credentialStore gpg \
    && git config --global credential.helper manager \
    && echo "export GPG_TTY=\$(tty)" >> ${HOME}/.bashrc \
    && mkdir -p ${HOME}/.gnupg \
    && chmod 700 "${HOME}/.gnupg"

EXPOSE 8888

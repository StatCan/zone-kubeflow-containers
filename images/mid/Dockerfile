#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=base
FROM $BASE_IMAGE

USER root

# installs vscode server, python & conda packages and jupyter lab extensions.
# also installs r-studio and pixi

# Install vscode
ARG VSCODE_VERSION=4.99.4
ARG VSCODE_SHA=74c107b33643ed11223263b86431530fbc9c9f7c8202997579a6f0c41b4cb102
ARG VSCODE_URL=https://github.com/coder/code-server/releases/download/v${VSCODE_VERSION}/code-server_${VSCODE_VERSION}_amd64.deb

ENV CS_DISABLE_FILE_DOWNLOADS=1
ENV CS_DEFAULT_HOME=$HOME/.local/share/code-server
ENV SERVICE_URL=https://extensions.coder.com/api

# System operations and cleanup
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
    # Manage extensions - FIXED: Removed failing @v1.1.3 and updated Parquet viewer
    code-server --install-extension ms-python.python@2025.4.0 && \
    code-server --install-extension ms-python.debugpy@2025.4.0 && \
    code-server --install-extension REditorSupport.r@2.8.4 && \
    code-server --install-extension ms-ceintl.vscode-language-pack-fr@1.99.0 && \
    code-server --install-extension quarto.quarto@1.113.0 && \
    code-server --install-extension dvirtz.parquet-viewer && \
    code-server --install-extension redhat.vscode-yaml@1.15.0 && \
    code-server --install-extension ms-vscode.azurecli@0.6.0 && \
    code-server --install-extension mblode.pretty-formatter@0.2.1 && \
    code-server --install-extension cweijan.vscode-mysql-client2 && \
    code-server --install-extension cpptools-linux.vsix \
    && rm cpptools-linux.vsix \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && fix-permissions $CS_DEFAULT_HOME

ENV EXTENSIONS_GALLERY='{"serviceUrl":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/api","itemUrl":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/item","resourceUrlTemplate":"https://code-marketplace.thezone-prod-cc-00.cloudnative.cloud.statcan.ca/files/{publisher}/{name}/{version}/{path}"}'
COPY vscode-overrides.json $CS_DEFAULT_HOME/Machine/settings.json
COPY languagepacks.json coder.json $CS_DEFAULT_HOME/

# Combined conda and pip installations with cleanup
RUN mamba install --quiet --yes -c conda-forge \
    'duckdb' \
    'python-duckdb' \
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
    && jupyter lab clean \
    && clean-layer.sh \
    && rm -rf /home/$NB_USER/.cache/yarn \
    && rm -rf /home/$NB_USER/.node-gyp \
    && fix-permissions $CONDA_DIR \
    && fix-permissions /home/$NB_USER

# DuckDB Extension Pre-install
USER root
RUN DUCK_VER=$(duckdb --version | cut -d' ' -f1) && \
    ABI_VER=v$(echo $DUCK_VER | cut -d'.' -f1-2).0 && \
    mkdir -p /home/$NB_USER/.duckdb/extensions/${ABI_VER}/linux_amd64/ && \
    EXT_URL="http://extensions.duckdb.org/v${DUCK_VER}/linux_amd64" && \
    wget -q "${EXT_URL}/spatial.duckdb_extension.gz" -O /tmp/spatial.gz && \
    wget -q "${EXT_URL}/httpfs.duckdb_extension.gz" -O /tmp/httpfs.gz && \
    wget -q "${EXT_URL}/icu.duckdb_extension.gz" -O /tmp/icu.gz && \
    gunzip /tmp/*.gz && \
    mv /tmp/*.duckdb_extension /home/$NB_USER/.duckdb/extensions/${ABI_VER}/linux_amd64/ && \
    chown -R $NB_USER:$NB_GID /home/$NB_USER/.duckdb && \
    fix-permissions /home/$NB_USER/.duckdb

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

COPY jupyterlab-overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json

# install rstudio-server
ARG RSTUDIO_VERSION=2025.09.1-401
ARG SHA256=9a6b1ccf05a62e13bb7cab26b9ef5ba01445b58abb4a9f2c9868855e33613f1b
RUN apt-get update \
    && apt install -y --no-install-recommends software-properties-common dirmngr gdebi-core \
    && wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | sudo tee -a /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc \
    && add-apt-repository "deb https://cloud.r-project.org/bin/linux/ubuntu $(lsb_release -cs)-cran40/" \
    && apt-get update && apt-get -y dist-upgrade \
    && curl --silent -L  --fail "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/rstudio-server-${RSTUDIO_VERSION}-amd64.deb" > /tmp/rstudio.deb \
    && echo "${SHA256} /tmp/rstudio.deb" | sha256sum -c - \
    && apt-get install --no-install-recommends -y /tmp/rstudio.deb \
    && rm /tmp/rstudio.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY rserver.conf rsession.conf /etc/rstudio/
RUN mkdir -p ${HOME}/.config/rstudio
COPY --chown=${NB_USER}:${NB_GID} rstudio-prefs.json ${HOME}/.config/rstudio/rstudio-prefs.json

ENV PATH=$PATH:/usr/lib/rstudio-server/bin
ENV SPARK_HOME="/opt/conda/lib/python3.13/site-packages/pyspark"
ENV R_ZIPCMD="zip"

# install pixi 
RUN wget -qO- https://pixi.sh/install.sh | sh \
    && echo "eval \"\$(pixi completion --shell bash)\"" >> ~/.bashrc

COPY --chown=${NB_USER}:${NB_GID} pip.conf /etc/pip.conf
COPY --chown=${NB_USER}:${NB_GID} .Rprofile .profile .condarc connect-to-filer.md ${HOME}/
COPY --chmod=755 keep-alive.sh /usr/local/bin/

# SSL Certs setup
COPY --from=k8scc01covidacr.azurecr.io/publiccerts:latest /home/certs/ /opt/conda/ssl/certs
RUN echo >> /opt/conda/ssl/cacert.pem && \
    cd /opt/conda/ssl/certs/ && \
    for file in *.crt; do (echo "# ${file}"; cat "${file}"; echo) >> /opt/conda/ssl/cacert.pem; done
ENV REQUESTS_CA_BUNDLE=/opt/conda/ssl/cacert.pem

USER $NB_USER

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

COPY --chown=${NB_USER}:${NB_GID} gpg-agent.conf ${HOME}/.gnupg/gpg-agent.conf
COPY --chown=${NB_USER}:${NB_GID} vscode_settings.json ${HOME}/workspace/.vscode/settings.json
COPY --chown=${NB_USER}:${NB_GID} vscode_user_settings.json ${HOME}/.local/share/code-server/User/settings.json
COPY --chown=${NB_USER}:${NB_GID} --chmod=775 rm ${HOME}/.local/bin/rm
COPY --chown=${NB_USER}:${NB_GID} --chmod=755 s6/ /etc

RUN cp -p -r -T "${HOME}" "${HOME_TMP}" \
    && chmod -R g=u "${HOME_TMP}"

EXPOSE 8888

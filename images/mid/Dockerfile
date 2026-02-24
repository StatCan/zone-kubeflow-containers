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
    # Manage extensions
    code-server --install-extension ms-python.python@2025.4.0 && \
    code-server --install-extension ms-python.debugpy@2025.4.0 && \
    code-server --install-extension REditorSupport.r@2.8.4 && \
    code-server --install-extension ms-ceintl.vscode-language-pack-fr@1.99.0 && \
    code-server --install-extension quarto.quarto@1.113.0 && \
    code-server --install-extension adamviola.parquet-explorer@1.2.1 && \
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
# Fix for VSCode extensions and CORS
# Languagepacks.json needs to exist for code-server to recognize the languagepack
# Sets the default workspace for vscode
COPY languagepacks.json coder.json $CS_DEFAULT_HOME/

# Install Python dependencies and tools
# https://github.com/StatCan/aaw-kubeflow-containers/issues/293
# https://stackoverflow.com/questions/68824450/error-configuration-failed-for-package-ragg
# need to add mamba install pkg-config so R can find freetype related packages
# Combined conda and pip installations with cleanup
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

# OneLake SDK for accessing Microsoft Fabric OneLake (ADLS Gen2) storage
RUN pip install --no-cache-dir \
    'azure-storage-file-datalake' \
    'azure-identity' \
    && fix-permissions $CONDA_DIR \
    && fix-permissions /home/$NB_USER

# OneLake helper module for accessing Microsoft Fabric OneLake storage
COPY onelake_utils.py /opt/conda/lib/python3.13/site-packages/onelake_utils.py

# Solarized Theme and Cell Execution Time
COPY jupyterlab-overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json

# install rstudio-server
ARG RSTUDIO_VERSION=2025.09.1-401
ARG SHA256=9a6b1ccf05a62e13bb7cab26b9ef5ba01445b58abb4a9f2c9868855e33613f1b
# RStudio installation with cleanup
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

# Harden rstudio-server - copy config files
# See: https://github.com/rstudio/rstudio/issues/14060 for rsession-ld-library-path
COPY rserver.conf rsession.conf /etc/rstudio/

# Disables .RData settings
RUN mkdir -p ${HOME}/.config/rstudio
COPY --chown=${NB_USER}:${NB_GID} rstudio-prefs.json ${HOME}/.config/rstudio/rstudio-prefs.json

ENV PATH=$PATH:/usr/lib/rstudio-server/bin

ENV SPARK_HOME="/opt/conda/lib/python3.13/site-packages/pyspark"
ENV R_ZIPCMD="zip"

# install pixi package manager and enable autocomplete

RUN wget -qO- https://pixi.sh/install.sh | sh \
    && echo "eval \"\$(pixi completion --shell bash)\"" >> ~/.bashrc

# Configure container startup

# Copy over pip config
COPY --chown=${NB_USER}:${NB_GID} pip.conf /etc/pip.conf

#Copy over various files
COPY --chown=${NB_USER}:${NB_GID} .Rprofile .profile .condarc connect-to-filer.md ${HOME}/

COPY --chmod=755 keep-alive.sh /usr/local/bin/

# SSL Certs
# https://jirab.statcan.ca/browse/ZONE-274?focusedId=3674862&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-3674862
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
    # Step up Git Credential Manager
    && git config --global credential.credentialStore gpg \
    && git config --global credential.helper manager \
    && echo "export GPG_TTY=\$(tty)" >> ${HOME}/.bashrc \
    # Create and set the gpg settings during first boot
    && mkdir -p ${HOME}/.gnupg \
    && chmod 700 "${HOME}/.gnupg"

COPY --chown=${NB_USER}:${NB_GID} gpg-agent.conf ${HOME}/.gnupg/gpg-agent.conf

# Set Python interpreter path for VSCode
COPY --chown=${NB_USER}:${NB_GID} vscode_settings.json ${HOME}/workspace/.vscode/settings.json

# Python default user settings for VSCode
COPY --chown=${NB_USER}:${NB_GID} vscode_user_settings.json ${HOME}/.local/share/code-server/User/settings.json

# add rm wrapper
# https://jirab.statcan.ca/browse/ZPS-40
COPY --chown=${NB_USER}:${NB_GID} --chmod=775 rm ${HOME}/.local/bin/rm

# s6 - copy scripts
COPY --chown=${NB_USER}:${NB_GID} --chmod=755 s6/ /etc

# s6 - 01-copy-tmp-home
# NOTE: the contents of $HOME_TMP are copied to $HOME at runtime
#       this is a workaround because a PVC will be mounted at $HOME
#       and the contents of $HOME will be hidden
RUN cp -p -r -T "${HOME}" "${HOME_TMP}" \
    # give group same access as user (needed for OpenShift)
    && chmod -R g=u "${HOME_TMP}"

EXPOSE 8888

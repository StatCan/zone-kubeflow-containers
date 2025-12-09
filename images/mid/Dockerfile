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
    'r-base=4.4.1' \
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

# OpenM install
# Install OpenM++ MPI
ARG OMPP_VERSION="1.17.5"
# IMPORTANT: Don't forget to update the version number in the openmpp.desktop file!!
ARG OMPP_PKG_DATE="20241021"
# Sha needs to be manually generated.
ARG SHA256ompp=79c4bf6e09c9c51f33986251f1f44279f29d4fe669b6e8f7d7597a406d24b5a9
# OpenM++ environment settings
ENV OMPP_INSTALL_DIR=/opt/openmpp/${OMPP_VERSION}

COPY jupyter-ompp-proxy/ /opt/jupyter-ompp-proxy/

# OpenM++ expects sqlite to be installed (not just libsqlite)
# Customize and rebuild omp-ui for jupyter-ompp-proxy install
# issue with making a relative publicPath https://github.com/quasarframework/quasar/issues/8513
ARG NODE_OPTIONS=--openssl-legacy-provider
RUN wget -q https://github.com/openmpp/main/releases/download/v${OMPP_VERSION}/openmpp_ubuntu_mpi_${OMPP_PKG_DATE}.tar.gz -O /tmp/ompp.tar.gz \
    && echo "${SHA256ompp} /tmp/ompp.tar.gz" | sha256sum -c - \
    && mkdir -p ${OMPP_INSTALL_DIR} \
    && tar -xf /tmp/ompp.tar.gz -C ${OMPP_INSTALL_DIR} --strip-components=1 \
    && rm -f /tmp/ompp.tar.gz \
    # Customize and rebuild omp-ui for jupyter-ompp-proxy install
    # issue with making a relative publicPath https://github.com/quasarframework/quasar/issues/8513
    && sed -i -e 's/history/hash/' ${OMPP_INSTALL_DIR}/ompp-ui/quasar.config.js \
    && sed -i -e "s/OMS_URL:.*''/OMS_URL: '.'/" ${OMPP_INSTALL_DIR}/ompp-ui/quasar.config.js \
    && npm install --prefix ${OMPP_INSTALL_DIR}/ompp-ui @babel/traverse@7.23.2 \
    && npm run build --prefix ${OMPP_INSTALL_DIR}/ompp-ui \
    && rm -r ${OMPP_INSTALL_DIR}/html \
    && mv ${OMPP_INSTALL_DIR}/ompp-ui/dist/spa ${OMPP_INSTALL_DIR}/html \
    && rm -rf ${OMPP_INSTALL_DIR}/ompp-ui \
    && npm cache clean --force \
    && rm -rf /root/.npm \
    && fix-permissions ${OMPP_INSTALL_DIR}

# Solarized Theme and Cell Execution Time
COPY jupyterlab-overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json

# install rstudio-server
ARG RSTUDIO_VERSION=2024.12.0-467
ARG SHA256=1493188cdabcc1047db27d1bd0e46947e39562cbd831158c7812f88d80e742b3
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

# Harden rstudio-server
RUN mkdir -p /etc/rstudio \
    && echo "www-frame-origin=none" >> /etc/rstudio/rserver.conf \
    && echo "www-enable-origin-check=1" >> /etc/rstudio/rserver.conf \
    && echo "www-same-site=lax" >> /etc/rstudio/rserver.conf \
    && echo "auth-timeout-minutes=10080" >> /etc/rstudio/rserver.conf  \
    && echo "restrict-directory-view=1" >> /etc/rstudio/rsession.conf \
    # Sets the default working dir
    && echo "session-default-working-dir=/home/jovyan/workspace" >> /etc/rstudio/rsession.conf \
    && echo "session-default-new-project-dir=/home/jovyan/workspace" >> /etc/rstudio/rsession.conf \
    # https://github.com/rstudio/rstudio/issues/14060
    && echo "rsession-ld-library-path=/opt/conda/lib" >> /etc/rstudio/rserver.conf 

# Disables .RData settings
RUN mkdir -p ${HOME}/.config/rstudio \
    && echo $'{\n\t"save_workspace": "never",\n\t"load_workspace": false\n}' > ${HOME}/.config/rstudio/rstudio-prefs.json

ENV PATH=$PATH:/usr/lib/rstudio-server/bin

ENV SPARK_HOME="/opt/conda/lib/python3.13/site-packages/pyspark"

# install pixi package manager and enable autocomplete

RUN wget -qO- https://pixi.sh/install.sh | sh \
    && echo "eval \"\$(pixi completion --shell bash)\"" >> ~/.bashrc

# Configure container startup

# Copy over pip config
COPY --chown=${NB_USER}:${NB_GID} pip.conf /etc/pip.conf

#Copy over various files
COPY --chown=${NB_USER}:${NB_GID} .Rprofile .profile .condarc connect-to-filer.md ${HOME}/

COPY --chmod=755 keep-alive.sh start-oms.sh restart-oms.sh /usr/local/bin/

# SSL Certs
COPY certs/ /opt/conda/ssl/certs
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
    && echo -e "default-cache-ttl 604800 \nmax-cache-ttl 604800 \n" > "${HOME}/.gnupg/gpg-agent.conf" \
    && chmod 700 "${HOME}/.gnupg"

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

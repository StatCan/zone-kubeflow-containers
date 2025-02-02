
###############################
###  .tmp/cpu.Dockerfile
###############################


###############################
###  docker-bits/0_cpu.Dockerfile
###############################

# Docker-stacks version tags (eg: `r-4.0.3`) are LIVE images that are frequently updated.  To avoid unexpected
# image updates, pin to the docker-stacks git commit SHA tag.
# It can be obtained by running `docker inspect repo/imagename:tag@digest` or from
# https://github.com/jupyter/docker-stacks/wiki

ARG BASE_VERSION=2024-06-17

FROM k8scc01covidacr.azurecr.io/sas4c:0.0.3 as SASHome
FROM quay.io/jupyter/datascience-notebook:$BASE_VERSION
# using  Ubuntu 22.04 Jammy

USER root

ENV PATH="/home/jovyan/.local/bin/:${PATH}"

COPY clean-layer.sh /usr/bin/clean-layer.sh

RUN apt-get update --yes \
    && apt-get install --yes language-pack-fr \
    && apt-get upgrade --yes libwebp7 \
    && rm -rf /var/lib/apt/lists/* \
    && chmod +x /usr/bin/clean-layer.sh

###############################
###  docker-bits/3_Kubeflow.Dockerfile
###############################

USER root
COPY suspend-server.sh /usr/local/bin

# https://github.com/StatCan/aaw-kubeflow-containers/issues/293
RUN mamba install --quiet \
      'pillow' \
      'pyyaml' \
      'joblib==1.2.0' \
      # s3 file system tool forked by Zach, ~4 years old, to be upgraded
      's3fs' \ 
      'fire==0.5.0' \
      'graphviz' && \
      pip install 'kubeflow-training' && \
      clean-layer.sh && \
      fix-permissions $CONDA_DIR && \
      fix-permissions /home/$NB_USER && \
      chmod +x /usr/local/bin/suspend-server.sh

###############################
###  docker-bits/4_CLI.Dockerfile
###############################

USER root

# Add helpers for shell initialization
COPY shell_helpers.sh /tmp/shell_helpers.sh

# Dependencies
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
      'byobu' \
      'pass' \
      'htop' \
      'jq' \
      'openssl' \
      'ranger' \
      'tig' \
      'tmux' \
      'tree' \
      'vim' \
      'zip' \
      'zsh' \
      'dos2unix' \
      # installs necessary tool for kerberos authentication setup
      'krb5-user' \
      # these are required by some r packages, adding these here so they get
      # installed into all images.
      'libfreetype6-dev' \
      'libpng-dev' \
      'libtiff5-dev' \
      'libjpeg-dev' \
      'libtiff-dev' \
      'libfreetype-dev' \
      'libfreetype6' && \
    rm -rf /var/lib/apt/lists/*


ARG KUBECTL_VERSION=v1.29.10
ARG KUBECTL_URL=https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl

ARG AZCLI_URL=https://aka.ms/InstallAzureCLIDeb

ARG OH_MY_ZSH_URL=https://raw.githubusercontent.com/loket/oh-my-zsh/feature/batch-mode/tools/install.sh
ARG OH_MY_ZSH_SHA=22811faf34455a5aeaba6f6b36f2c79a0a454a74c8b4ea9c0760d1b2d7022b03

ARG TRINO_URL=https://repo1.maven.org/maven2/io/trino/trino-cli/410/trino-cli-410-executable.jar
ARG TRINO_SHA=f32c257b9cfc38e15e8c0b01292ae1f11bda2b23b5ce1b75332e108ca7bf2e9b

ARG ARGO_CLI_VERSION=v3.5.12
ARG ARGO_CLI_URL=https://github.com/argoproj/argo-workflows/releases/download/${ARGO_CLI_VERSION}/argo-linux-amd64.gz
ARG ARGO_CLI_CHECKSUM_URL=https://github.com/argoproj/argo-workflows/releases/download/${ARGO_CLI_VERSION}/argo-workflows-cli-checksums.txt

RUN \
  # OpenJDK-8
    apt-get update && \
    apt-get install -y openjdk-8-jre && \
    apt-get clean && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER \
  && \
    # kubectl
    curl -LO "${KUBECTL_URL}" \
    && curl -LO "${KUBECTL_URL}.sha256" \
    && echo "$(cat kubectl.sha256) kubectl" | sha256sum -c - \
    && chmod +x ./kubectl \
    && sudo mv ./kubectl /usr/local/bin/kubectl \
  && \
    # AzureCLI - installation script from Azure
    curl -sLO "${AZCLI_URL}" \
    && bash InstallAzureCLIDeb \
    && rm InstallAzureCLIDeb \
    && echo "azcli: ok" \
  && \
    # zsh
    wget -q "${OH_MY_ZSH_URL}" -O /tmp/oh-my-zsh-install.sh \
    && echo "${OH_MY_ZSH_SHA} /tmp/oh-my-zsh-install.sh" | sha256sum -c \
    && echo "oh-my-zsh: ok" \
  && \
    # trino cli
    wget -q "${TRINO_URL}" -O /tmp/trino-original \
    && echo ${TRINO_SHA} /tmp/trino-original | sha256sum -c \
    && echo "trinocli: ok" \
    && chmod +x /tmp/trino-original \
    && sudo mv /tmp/trino-original /usr/local/bin/trino-original \
  && \
    # argo cli
    curl -sLO  ${ARGO_CLI_URL}\
    && curl -LO ${ARGO_CLI_CHECKSUM_URL} \
    && grep argo-linux-amd64.gz argo-workflows-cli-checksums.txt | sha256sum -c - \
    && gunzip argo-linux-amd64.gz \
    && chmod +x argo-linux-amd64 \
    && sudo mv ./argo-linux-amd64 /usr/local/bin/argo \
    && argo version

ARG GIT_CRED_MANAGER_VERSION=2.5.1
ARG GIT_CRED_MANAGER_URL=https://github.com/git-ecosystem/git-credential-manager/releases/download/v${GIT_CRED_MANAGER_VERSION}/gcm-linux_amd64.${GIT_CRED_MANAGER_VERSION}.deb
ARG GIT_CRED_MANAGER_SHA=03c7b174a6f90e1ae860980ba5fda4490f04e5b9aaa802e2d469e72ec5dae6a4

RUN wget -q "${GIT_CRED_MANAGER_URL}" -O ./gcm.deb \
  && echo "${GIT_CRED_MANAGER_SHA}  ./gcm.deb" | sha256sum -c - \
  && dpkg -i ./gcm.deb \
  && rm ./gcm.deb

# add script for kerberos keytab creation
COPY ktutil-keytab.sh /usr/local/bin/ktutil-keytab
RUN chmod +x /usr/local/bin/ktutil-keytab

###############################
###  docker-bits/5_DB-Drivers.Dockerfile
###############################

USER root

# ODBC drivers
# Add the signature to trust the Microsoft repo
RUN curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc && \
    # Add repo to apt sources
    curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update && \
    # Install the driver
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    # optional: for bcp and sqlcmd
    ACCEPT_EULA=Y apt-get install -y mssql-tools18 && \
    # installing unixODBC
    apt-get install -y unixodbc unixodbc-dev && \
    # libaio1 needed for Oracle Instant Client
    apt-get install -y libaio1 && \
    pip install --no-cache-dir --quiet pyodbc && \
    rm -rf /var/lib/apt/lists/* && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

RUN echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> ~/.bashrc && \
    source ~/.bashrc

# installing Oracle Instant Client
RUN curl -O https://download.oracle.com/otn_software/linux/instantclient/2350000/instantclient-basic-linux.x64-23.5.0.24.07.zip && \
    unzip instantclient-basic-linux.x64-23.5.0.24.07.zip -d /opt/oracle/ && \
    echo /opt/oracle/instantclient_23_5 > /etc/ld.so.conf.d/oracle-instantclient.conf && \
    ldconfig

ENV PATH /opt/oracle/instantclient_23_5:${PATH}

# installing Oracle ODBC driver
RUN curl -O https://download.oracle.com/otn_software/linux/instantclient/2350000/instantclient-odbc-linux.x64-23.5.0.24.07.zip && \
    unzip -oj instantclient-odbc-linux.x64-23.5.0.24.07.zip -d /opt/oracle/instantclient_23_5 && \
    /opt/oracle/instantclient_23_5/odbc_update_ini.sh / /opt/oracle/instantclient_23_5

# add relevent files needed for oracle
COPY dbConnection/LINUX_CLIENT_WALLET /opt/oracle/instantclient_23_5/LINUX_CLIENT_WALLET
COPY dbConnection/*.ora /opt/oracle/instantclient_23_5/network/admin/
#give users permissions to edit the alias file
RUN chmod a+w /opt/oracle/instantclient_23_5/network/admin
RUN chown $NB_UID:$NB_GID /opt/oracle/instantclient_23_5/network/admin/tnsnames.ora

###############################
###  docker-bits/6_rstudio-server.Dockerfile
###############################

# install rstudio-server
ARG RSTUDIO_VERSION=2024.04.2-764
ARG SHA256=d8ffb8e5c2dadb1c74df037c291a5585e595d978b3aec48a4a94a970e04a947d
RUN apt-get update && \
    apt install -y --no-install-recommends software-properties-common dirmngr gdebi-core && \
    wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | sudo tee -a /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc && \
    add-apt-repository "deb https://cloud.r-project.org/bin/linux/ubuntu jammy-cran40/" && \
    apt install -y --no-install-recommends r-base r-base-core r-recommended r-base-dev && \
    apt-get update && apt-get -y dist-upgrade

RUN curl --silent -L  --fail "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/rstudio-server-${RSTUDIO_VERSION}-amd64.deb" > /tmp/rstudio.deb && \
    echo "${SHA256} /tmp/rstudio.deb" | sha256sum -c - && \
    apt-get install --no-install-recommends -y /tmp/rstudio.deb && \
    rm /tmp/rstudio.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

###############################
###  docker-bits/6_rstudio.Dockerfile
###############################

# Harden rstudio-server
RUN mkdir -p /etc/rstudio && \
    echo "www-frame-origin=none" >> /etc/rstudio/rserver.conf && \
    echo "www-enable-origin-check=1" >> /etc/rstudio/rserver.conf && \
    echo "www-same-site=lax" >> /etc/rstudio/rserver.conf && \
    echo "restrict-directory-view=1" >> /etc/rstudio/rsession.conf && \
    # Sets the default working dir
    echo "session-default-working-dir=/home/jovyan/workspace" >> /etc/rstudio/rsession.conf && \
    echo "session-default-new-project-dir=/home/jovyan/workspace" >> /etc/rstudio/rsession.conf && \
    # https://github.com/rstudio/rstudio/issues/14060
    echo "rsession-ld-library-path=/opt/conda/lib" >> /etc/rstudio/rserver.conf 

ENV PATH=$PATH:/usr/lib/rstudio-server/bin

ENV SPARK_HOME="/opt/conda/lib/python3.11/site-packages/pyspark"

# Install some default R packages
# rpy2 is installed by upstream, I don't know if anyone uses it.
# ryp2 was causing problems with R 4.4.1, so I removed it from the 
# mamba install. rpy2 is reinstalled with pip below.
# when we next upgrade R, let's try to restore rpy2 to its original state
# which means just remove mamba remove rpy2 and remove pip install rpy2
RUN mamba remove rpy2 && \
    mamba install --quiet --yes \
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
    && \
    pip install rpy2 && \
    clean-layer.sh && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

RUN python3 -m pip install \
    'jupyter-rsession-proxy==2.2.0' \
    'jupyter-server-proxy==4.2.0' && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

# If using the docker bit in other Dockerfiles, this must get written over in a later layer
ENV DEFAULT_JUPYTER_URL="/rstudio"
ENV GIT_EXAMPLE_NOTEBOOKS=https://gitlab.k8s.cloud.statcan.ca/business-transformation/aaw/aaw-contrib-r-notebooks.git

###############################
###  docker-bits/6_jupyterlab.Dockerfile
###############################

# installs vscode server, python & conda packages and jupyter lab extensions.

# Using JupyterLab 3.0 inherited docker-stacks base image. A few extensions we used to install and don't support
# this version of Jupyterlab and/or are not OL-compliant so they have been removed until new compatible versions are available:
    # jupyterlab-kale
    # jupyterlab-variableinspector
    # jupyterlab-archive
    # jupyterlab-spellchecker
    # jupyterlab-spreadsheet

# Install vscode
ARG VSCODE_VERSION=4.93.1
ARG VSCODE_SHA=9307ad9dacf30a3de76a26d0d455150d17798cf0394ccf5a4f3705ff20c945d8
ARG VSCODE_URL=https://github.com/coder/code-server/releases/download/v${VSCODE_VERSION}/code-server_${VSCODE_VERSION}_amd64.deb
USER root

ENV CS_DISABLE_FILE_DOWNLOADS=1
ENV CS_TEMP_HOME=/etc/share/code-server
ENV CS_DEFAULT_HOME=$HOME/.local/share/code-server
ENV SERVICE_URL=https://extensions.coder.com/api

RUN wget -q "${VSCODE_URL}" -O ./vscode.deb \
    && echo "${VSCODE_SHA}  ./vscode.deb" | sha256sum -c - \
    && wget -q https://github.com/microsoft/vscode-cpptools/releases/download/v1.20.5/cpptools-linux.vsix \
    && apt-get update \
    && apt-get install -y nginx build-essential gdb \
    && dpkg -i ./vscode.deb \
    && rm ./vscode.deb \
    && rm -f /etc/apt/sources.list.d/vscode.list \
    && mkdir -p $CS_TEMP_HOME/Machine \
    && \ 
    # Manage extensions
    code-server --install-extension ms-python.python@2024.8.1 && \
    code-server --install-extension ms-python.debugpy@2024.8.0 && \
    code-server --install-extension REditorSupport.r@2.8.4 && \
    code-server --install-extension ms-ceintl.vscode-language-pack-fr@1.91.0 && \
    code-server --install-extension quarto.quarto@1.113.0 && \
    code-server --install-extension dvirtz.parquet-viewer@2.9.0 && \
    code-server --install-extension redhat.vscode-yaml@1.15.0 && \
    code-server --install-extension ms-vscode.azurecli@0.6.0 && \
    code-server --install-extension mblode.pretty-formatter@0.2.1 && \
    code-server --install-extension cpptools-linux.vsix && \
    mv $CS_DEFAULT_HOME/* $CS_TEMP_HOME && \
    fix-permissions $CS_TEMP_HOME

ENV EXTENSIONS_GALLERY='{"serviceUrl":"https://code-marketplace.das-prod-cc-00.cloudnative.cloud.statcan.ca/api","itemUrl":"https://code-marketplace.das-prod-cc-00.cloudnative.cloud.statcan.ca/item","resourceUrlTemplate":"https://code-marketplace.das-prod-cc-00.cloudnative.cloud.statcan.ca/files/{publisher}/{name}/{version}/{path}"}'
COPY vscode-overrides.json $CS_TEMP_HOME/Machine/settings.json
# Fix for VSCode extensions and CORS
# Languagepacks.json needs to exist for code-server to recognize the languagepack
COPY languagepacks.json $CS_TEMP_HOME/

# Sets the default workspace for vscode
COPY coder.json $CS_TEMP_HOME/

RUN pip install \
    'git+https://github.com/betatim/vscode-binder' && \
    # jupyter_contrib_nbextensions likes to be installed with pip
    mamba install --quiet --yes -c conda-forge \
    # https://stackoverflow.com/questions/68824450/error-configuration-failed-for-package-ragg
    # need to add mamba install pkg-config so R can find freetype related packages
    'pkg-config' \
    'jupyterlab' \
    'jupyter_contrib_nbextensions' \ 
    'dash' \
    'plotly' \
    'ipywidgets' \
    'markupsafe' \
    'pyspark' \
    'ipympl' \
    'pexpect==4.9.0' \
    'jupyter-resource-usage' \
    'jupyter-server-proxy==4.2.0' \
    'jupyterlab-language-pack-fr-fr' \
    'jupyterlab_execute_time' \
    'nb_conda_kernels' \
    'jupyterlab-lsp' \
    'jupyter-lsp'  && \
    jupyter server extension enable --py jupyter_server_proxy && \
    jupyter nbextension enable codefolding/main --sys-prefix && \
    jupyter labextension enable \
      '@jupyterlab/translation-extension' \
      '@jupyterlab/server-proxy' \
      'nbdime-jupyterlab' \
    && \
    jupyter lab build && \
    jupyter lab clean && \
  clean-layer.sh && \
  rm -rf /home/$NB_USER/.cache/yarn && \
  rm -rf /home/$NB_USER/.node-gyp && \
  fix-permissions $CONDA_DIR && \
  fix-permissions /home/$NB_USER

# Update and pin packages
# See https://github.com/StatCan/aaw-kubeflow-containers/issues/293

# Install python, R, Julia and other useful language servers
RUN julia -e 'using Pkg; Pkg.add("LanguageServer")' && \
    /opt/conda/bin/R --silent --slave --no-save --no-restore -e 'install.packages("languageserver", repos="https://cran.r-project.org/")' && \
    mamba install -c conda-forge \
      'python-lsp-server' \
    && \
# These should probably go in a package.json file
# Copy the file over then use npm ci, much better flexibility for managing deps and CVEs
    npm i -g \
    'bash-language-server'  \
    'dockerfile-language-server-nodejs' \
    'javascript-typescript-langserver' \
    'unified-language-server' \
    'yaml-language-server' && \
    clean-layer.sh && \ 
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

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
RUN apt-get update --yes \
    && apt-get install --yes sqlite3 openmpi-bin libopenmpi-dev\
    && wget -q https://github.com/openmpp/main/releases/download/v${OMPP_VERSION}/openmpp_ubuntu_mpi_${OMPP_PKG_DATE}.tar.gz -O /tmp/ompp.tar.gz \
    && echo "${SHA256ompp} /tmp/ompp.tar.gz" | sha256sum -c - \
    && mkdir -p ${OMPP_INSTALL_DIR} \
    && tar -xf /tmp/ompp.tar.gz -C ${OMPP_INSTALL_DIR} --strip-components=1\
    && rm -f /tmp/ompp.tar.gz \
# Customize and rebuild omp-ui for jupyter-ompp-proxy install
# issue with making a relative publicPath https://github.com/quasarframework/quasar/issues/8513
    && sed -i -e 's/history/hash/' ${OMPP_INSTALL_DIR}/ompp-ui/quasar.config.js \
    && sed -i -e "s/OMS_URL:.*''/OMS_URL: '.'/" ${OMPP_INSTALL_DIR}/ompp-ui/quasar.config.js \
    && npm install --prefix ${OMPP_INSTALL_DIR}/ompp-ui @babel/traverse@7.23.2\
    && npm run build --prefix ${OMPP_INSTALL_DIR}/ompp-ui \
    && rm -r ${OMPP_INSTALL_DIR}/html \
    && mv ${OMPP_INSTALL_DIR}/ompp-ui/dist/spa ${OMPP_INSTALL_DIR}/html \
    && fix-permissions ${OMPP_INSTALL_DIR} \
    && pip install /opt/jupyter-ompp-proxy/

# MinIO Client install
COPY --from=minio/mc:RELEASE.2024-11-17T19-35-25Z /bin/mc /usr/local/bin/mc

# Solarized Theme and Cell Execution Time
COPY jupyterlab-overrides.json /opt/conda/share/jupyter/lab/settings/overrides.json

ENV DEFAULT_JUPYTER_URL=/lab
ENV GIT_EXAMPLE_NOTEBOOKS=https://gitlab.k8s.cloud.statcan.ca/business-transformation/aaw/aaw-contrib-jupyter-notebooks

###############################
###  docker-bits/6_sas.Dockerfile
###############################

# SAS

# Install Quarto
ARG QUARTO_VERSION=1.5.57
ARG QUARTO_URL=https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz
ARG QUARTO_CHECKSUM_URL=https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-checksums.txt

RUN wget -q ${QUARTO_URL} -O /tmp/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz && \
    wget -q ${QUARTO_CHECKSUM_URL} -O /tmp/quarto-${QUARTO_VERSION}-checksums.txt && \
    grep "quarto-${QUARTO_VERSION}-linux-amd64.tar.gz" /tmp/quarto-${QUARTO_VERSION}-checksums.txt | sed "s|quarto-${QUARTO_VERSION}-linux-amd64.tar.gz|/tmp/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz|" | sha256sum -c - && \
    tar -xzvf /tmp/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz -C /tmp/ && \
    chmod +x /tmp/quarto-${QUARTO_VERSION} && \
    ln -s /tmp/quarto-${QUARTO_VERSION}/bin/quarto /usr/bin/quarto && \
    # Install lmodern, required by LaTeX so Quarto can produce PDFs
    apt-get update && sudo apt-get install lmodern -y && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1002 sasstaff && \
    usermod -a -G sasstaff jovyan && \
    echo "jovyan:jovyan" | chpasswd

COPY --from=SASHome /usr/local/SASHome /usr/local/SASHome

COPY --from=minio/mc:RELEASE.2024-11-17T19-35-25Z /bin/mc /usr/local/bin/mc

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/local/SASHome/SASFoundation/9.4/bin/sas_en /usr/local/bin/sas && \
    chmod -R 0775 /usr/local/SASHome/studioconfig

WORKDIR /home/jovyan

ENV PATH=$PATH:/usr/local/SASHome/SASFoundation/9.4/bin

ENV PATH=$PATH:/usr/local/SASHome/SASPrivateJavaRuntimeEnvironment/9.4/jre/bin

RUN /usr/local/SASHome/SASFoundation/9.4/utilities/bin/setuid.sh

ENV SAS_HADOOP_JAR_PATH=/opt/hadoop

EXPOSE 8561 8591 38080

# SASPY

ENV SASPY_VERSION="5.4.0"

RUN pip install sas_kernel

# TODO: make Python version ENV var.
COPY sascfg.py /opt/conda/lib/python3.11/site-packages/saspy/sascfg.py

RUN jupyter nbextension install --py sas_kernel.showSASLog && \
    jupyter nbextension enable sas_kernel.showSASLog --py && \
    jupyter nbextension install --py sas_kernel.theme && \
    jupyter nbextension enable sas_kernel.theme --py && \
    jupyter nbextension list

# Must be set in deepest image
ENV DEFAULT_JUPYTER_URL=/lab 

# SAS GConfid

COPY G-CONFID107003ELNX6494M7/ /usr/local/SASHome/gensys/G-CONFID107003ELNX6494M7/
COPY sasv9_local.cfg /usr/local/SASHome/SASFoundation/9.4/

###############################
###  docker-bits/7_remove_vulnerabilities.Dockerfile
###############################

# Remove libpdfbox-java due to CVE-2019-0228. See https://github.com/StatCan/aaw-kubeflow-containers/issues/249#issuecomment-834808115 for details.
# Issue opened https://github.com/jupyter/docker-stacks/issues/1299.
# This line of code should be removed once a solution or better alternative is found.
USER root
RUN apt-get update --yes \
    && dpkg -r --force-depends libpdfbox-java \
    && rm -rf /var/lib/apt/lists/*

# Forcibly upgrade packages to patch vulnerabilities
# See https://github.com/StatCan/aaw-private/issues/58#issuecomment-1471863092 for more details.
RUN pip3 --no-cache-dir install --quiet \
      'wheel==0.40.0' \
      'setuptools==67.6.0' \
      'pyjwt==2.6.0' \
      'oauthlib==3.2.2' \
      'mpmath==1.3.0' \
      'lxml==4.9.2' \
      'pyarrow==14.0.1' \
      'cryptography==41.0.6' \
      && fix-permissions $CONDA_DIR && \
      fix-permissions /home/$NB_USER

USER $NB_USER

###############################
###  docker-bits/8_platform.Dockerfile
###############################

USER root

# Install AMD AOCL
ARG AOCL_VERSION=4.0
ENV AOCL_PATH=/opt/amd/aocl/${AOCL_VERSION}
ARG AOCL_SHA256=8a249e727beb8005639b4887074e1ea75020267ed1ac25520876a7ad21d0f4f6
RUN cd ${RESOURCES_PATH} && \
    wget --quiet https://download.amd.com/developer/eula/aocl/aocl-4-0/aocl-linux-aocc-${AOCL_VERSION}.tar.gz -O /tmp/aocl-linux-aocc-${AOCL_VERSION}.tar && \
    echo "${AOCL_SHA256} /tmp/aocl-linux-aocc-${AOCL_VERSION}.tar" | sha256sum -c - && \
    tar xf /tmp/aocl-linux-aocc-${AOCL_VERSION}.tar -C ./ && \
    cd ./aocl-linux-aocc-${AOCL_VERSION} && \
    /bin/bash ./install.sh -t /opt/amd/aocl && \
    cp setenv_aocl.sh ${AOCL_PATH} &&\
    rm /tmp/aocl-linux-aocc-${AOCL_VERSION}.tar

# Install AMD AOCC
ARG AOCC_VERSION=4.0.0
ARG AOCC_SHA256=2729ec524cbc927618e479994330eeb72df5947e90cfcc49434009eee29bf7d4
RUN cd ${RESOURCES_PATH} && \
   wget --quiet https://download.amd.com/developer/eula/aocc-compiler/aocc-compiler-${AOCC_VERSION}.tar -O /tmp/aocc-compiler-${AOCC_VERSION}.tar && \
   echo "${AOCC_SHA256} /tmp/aocc-compiler-${AOCC_VERSION}.tar" | sha256sum -c - && \
   tar xf /tmp/aocc-compiler-${AOCC_VERSION}.tar -C ./ && \
   cd ./aocc-compiler-${AOCC_VERSION} && \
   /bin/bash ./install.sh && \
   rm /tmp/aocc-compiler-${AOCC_VERSION}.tar

###############################
###  docker-bits/∞_CMD.Dockerfile
###############################

# Configure container startup

USER root
WORKDIR /home/$NB_USER
EXPOSE 8888
COPY start-custom.sh start-oms.sh restart-oms.sh /usr/local/bin/
COPY trino-wrapper.sh /usr/local/bin/trino

RUN chmod +x /usr/local/bin/start-oms.sh && \
    chmod +x /usr/local/bin/restart-oms.sh

# Add --user to all pip install calls and point pip to Artifactory repository
COPY pip.conf /tmp/pip.conf
RUN cat /tmp/pip.conf >> /etc/pip.conf && rm /tmp/pip.conf

# Point R to Artifactory repository
#COPY Rprofile.site /tmp/Rprofile.site
#RUN cat /tmp/Rprofile.site >> /opt/conda/lib/R/etc/Rprofile.site && rm /tmp/Rprofile.site

# Add .Rprofile to /tmp so we can install it in start-custom.sh
COPY .Rprofile /tmp/.Rprofile

# Copy over Instructions to Home directory
ADD connect-to-filer.md /home/$NB_USER/connect-to-filer.md

# Point conda to Artifactory repository
RUN conda config --remove channels conda-forge --system

USER $NB_USER
ENTRYPOINT ["tini", "--"]
CMD ["start-custom.sh"]

USER root

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
    'nodejs' \
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

# install rstudio-server
ARG RSTUDIO_VERSION=2024.04.2-764
ARG SHA256=d8ffb8e5c2dadb1c74df037c291a5585e595d978b3aec48a4a94a970e04a947d
RUN apt-get update && \
    apt install -y --no-install-recommends software-properties-common dirmngr gdebi-core && \
    wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | sudo tee -a /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc && \
    add-apt-repository "deb https://cloud.r-project.org/bin/linux/ubuntu $(lsb_release -cs)-cran40/" && \
    apt install -y --no-install-recommends r-base r-base-core r-recommended r-base-dev && \
    apt-get update && apt-get -y dist-upgrade

RUN curl --silent -L  --fail "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/rstudio-server-${RSTUDIO_VERSION}-amd64.deb" > /tmp/rstudio.deb && \
    echo "${SHA256} /tmp/rstudio.deb" | sha256sum -c - && \
    apt-get install --no-install-recommends -y /tmp/rstudio.deb && \
    rm /tmp/rstudio.deb && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

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
RUN mamba install --quiet --yes \
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

COPY --from=k8scc01covidacr.azurecr.io/sas4c:0.0.3 /usr/local/SASHome /usr/local/SASHome
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

# Remove libpdfbox-java due to CVE-2019-0228. See https://github.com/StatCan/aaw-kubeflow-containers/issues/249#issuecomment-834808115 for details.
# Issue opened https://github.com/jupyter/docker-stacks/issues/1299.
# This line of code should be removed once a solution or better alternative is found.
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
      'lxml==5.3.1' \
      'pyarrow==14.0.1' \
      'cryptography==41.0.6' \
      && fix-permissions $CONDA_DIR && \
      fix-permissions /home/$NB_USER

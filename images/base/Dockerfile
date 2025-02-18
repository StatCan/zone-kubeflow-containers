USER root

ENV PATH="/home/jovyan/.local/bin/:${PATH}"

COPY clean-layer.sh /usr/bin/clean-layer.sh

RUN apt-get update --yes \
    && apt-get install --yes language-pack-fr \
    && apt-get upgrade --yes libwebp7 \
    && rm -rf /var/lib/apt/lists/* \
    && chmod +x /usr/bin/clean-layer.sh

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

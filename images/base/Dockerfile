USER root

ENV PATH="/home/jovyan/.local/bin/:${PATH}"

# Define all versioned URLs in one place
ARG KUBECTL_VERSION=v1.29.10
ARG KUBECTL_URL=https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl
ARG AZCLI_URL=https://aka.ms/InstallAzureCLIDeb
ARG OH_MY_ZSH_URL=https://raw.githubusercontent.com/loket/oh-my-zsh/feature/batch-mode/tools/install.sh
ARG OH_MY_ZSH_SHA=22811faf34455a5aeaba6f6b36f2c79a0a454a74c8b4ea9c0760d1b2d7022b03
ARG ARGO_CLI_VERSION=v3.5.12
ARG ARGO_CLI_URL=https://github.com/argoproj/argo-workflows/releases/download/${ARGO_CLI_VERSION}/argo-linux-amd64.gz
ARG ARGO_CLI_CHECKSUM_URL=https://github.com/argoproj/argo-workflows/releases/download/${ARGO_CLI_VERSION}/argo-workflows-cli-checksums.txt
ARG GIT_CRED_MANAGER_VERSION=2.5.1
ARG GIT_CRED_MANAGER_URL=https://github.com/git-ecosystem/git-credential-manager/releases/download/v${GIT_CRED_MANAGER_VERSION}/gcm-linux_amd64.${GIT_CRED_MANAGER_VERSION}.deb
ARG GIT_CRED_MANAGER_SHA=03c7b174a6f90e1ae860980ba5fda4490f04e5b9aaa802e2d469e72ec5dae6a4

COPY clean-layer.sh /usr/bin/clean-layer.sh

# System updates and installations
RUN apt-get update --yes \
    && apt-get install --yes --no-install-recommends \
        language-pack-fr \
        byobu \
        pass \
        htop \
        jq \
        openssl \
        ranger \
        tig \
        tmux \
        tree \
        vim \
        zip \
        zsh \
        dos2unix \
        krb5-user \
        libfreetype6-dev \
        libpng-dev \
        libtiff5-dev \
        libjpeg-dev \
        libtiff-dev \
        libfreetype-dev \
        libfreetype6 \
         # Use headless Java to save space
        openjdk-8-jre-headless \
    && apt-get upgrade --yes libwebp7 \
    && rm -rf /var/lib/apt/lists/* \
    && chmod +x /usr/bin/clean-layer.sh

COPY suspend-server.sh /usr/local/bin
COPY adjust-server-resources.py /usr/local/bin

# Install Python dependencies and tools
RUN mamba install --quiet \
      'pillow' \
      'pyyaml' \
      'joblib==1.2.0' \
      's3fs' \ 
      'fire==0.5.0' \
      'graphviz' \
    && pip install --no-cache-dir 'kubeflow-training' \
    && clean-layer.sh \
    && chmod +x /usr/local/bin/suspend-server.sh \
    && chmod +x /usr/local/bin/adjust-server-resources.py \
    && fix-permissions $CONDA_DIR \
    && fix-permissions /home/$NB_USER

# Add helpers for shell initialization
COPY shell_helpers.sh /tmp/shell_helpers.sh

# Combined tool installations with cleanup
RUN \
    # kubectl
    curl -LO "${KUBECTL_URL}" \
    && curl -LO "${KUBECTL_URL}.sha256" \
    && echo "$(cat kubectl.sha256) kubectl" | sha256sum -c - \
    && chmod +x ./kubectl \
    && mv ./kubectl /usr/local/bin/kubectl \
    && rm kubectl.sha256 \
    && \
    # AzureCLI
    curl -sLO "${AZCLI_URL}" \
    && bash InstallAzureCLIDeb \
    && rm InstallAzureCLIDeb \
    && \
    # zsh
    wget -q "${OH_MY_ZSH_URL}" -O /tmp/oh-my-zsh-install.sh \
    && echo "${OH_MY_ZSH_SHA} /tmp/oh-my-zsh-install.sh" | sha256sum -c \
    && \
    # argo cli
    curl -sLO "${ARGO_CLI_URL}" \
    && curl -LO "${ARGO_CLI_CHECKSUM_URL}" \
    && grep argo-linux-amd64.gz argo-workflows-cli-checksums.txt | sha256sum -c - \
    && gunzip argo-linux-amd64.gz \
    && chmod +x argo-linux-amd64 \
    && mv ./argo-linux-amd64 /usr/local/bin/argo \
    && rm argo-workflows-cli-checksums.txt \
    && \
    # git credential manager
    wget -q "${GIT_CRED_MANAGER_URL}" -O ./gcm.deb \
    && echo "${GIT_CRED_MANAGER_SHA} ./gcm.deb" | sha256sum -c - \
    && dpkg -i ./gcm.deb \
    && rm ./gcm.deb

# add script for kerberos keytab creation
COPY ktutil-keytab.sh /usr/local/bin/ktutil-keytab
RUN chmod +x /usr/local/bin/ktutil-keytab

# ODBC drivers and Oracle client in one layer
RUN \
    # Microsoft ODBC drivers
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg \
    && echo "deb [arch=amd64] https://packages.microsoft.com/ubuntu/22.04/prod jammy main" > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql18 \
        mssql-tools18 \
        unixodbc \
        unixodbc-dev \
        libaio1t64 \
    && ln -s /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1 \
    && pip install --no-cache-dir --quiet pyodbc \
    && echo 'export PATH="$PATH:/opt/mssql-tools18/bin"' >> /etc/skel/.bashrc \
    && \
    # Oracle Instant Client
    curl -O https://download.oracle.com/otn_software/linux/instantclient/2350000/instantclient-basic-linux.x64-23.5.0.24.07.zip \
    && unzip -q instantclient-basic-linux.x64-23.5.0.24.07.zip -d /opt/oracle/ \
    && echo /opt/oracle/instantclient_23_5 > /etc/ld.so.conf.d/oracle-instantclient.conf \
    && ldconfig \
    && \
    # Oracle ODBC driver
    curl -O https://download.oracle.com/otn_software/linux/instantclient/2350000/instantclient-odbc-linux.x64-23.5.0.24.07.zip \
    && unzip -q -oj instantclient-odbc-linux.x64-23.5.0.24.07.zip -d /opt/oracle/instantclient_23_5 \
    && /opt/oracle/instantclient_23_5/odbc_update_ini.sh / /opt/oracle/instantclient_23_5 \
    && \
    # Cleanup
    rm -f *.zip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && fix-permissions $CONDA_DIR \
    && fix-permissions /home/$NB_USER

# Oracle configuration
COPY dbConnection/LINUX_CLIENT_WALLET /opt/oracle/instantclient_23_5/LINUX_CLIENT_WALLET
COPY dbConnection/*.ora /opt/oracle/instantclient_23_5/network/admin/
RUN chmod a+w /opt/oracle/instantclient_23_5/network/admin \
    && chown $NB_UID:$NB_GID /opt/oracle/instantclient_23_5/network/admin/tnsnames.ora

# Oracle environment variables
ENV NLS_LANG="AMERICAN_AMERICA.WE8MSWIN1252"
ENV LD_LIBRARY_PATH="/opt/oracle/instantclient_23_5"
ENV TNS_ADMIN="/opt/oracle/instantclient_23_5/network/admin"
ENV PATH="/opt/oracle/instantclient_23_5:/opt/mssql-tools18/bin:${PATH}"

# Final cleanup
RUN rm -rf /tmp/* /var/tmp/* \
    && find / -depth -name '*.pyc' -exec rm -rf '{}' + \
    && find / -depth -name '__pycache__' -exec rm -rfv '{}' + \
    && conda clean -afy \
    && fix-permissions $CONDA_DIR \
    && fix-permissions /home/$NB_USER
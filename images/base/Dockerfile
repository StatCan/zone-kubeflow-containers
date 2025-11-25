#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=quay.io/jupyter/datascience-notebook
FROM $BASE_IMAGE

USER root

ENV PATH="/home/jovyan/.local/bin/:${PATH}"

# we copy the contents of $HOME_TMP to $HOME on startup
# this is to work around the fact that a PVC will be mounted to $HOME
# but we still want to have some default files in $HOME
# see `s6/cont-init.d/01-copy-tmp-home`
ENV HOME_TMP=/tmp_home/$NB_USER

# s6-overlay only gives 5 seconds by default, which is too small for slow PVC storage backends
# when running `/etc/cont-inid.d/01-copy-tmp-home` (note, this is in milliseconds)
ENV S6_CMD_WAIT_FOR_SERVICES_MAXTIME=300000

# s6-overlay does not fail by default if the `/etc/cont-init.d/` or `/etc/services.d/` scripts fail
# this is not the desired behavior, so we set it to fail
ENV S6_BEHAVIOUR_IF_STAGE2_FAILS=2

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
ARG S6_VERSION=v3.2.1.0
ARG S6_ARCH="x86_64"

# create temp home
RUN mkdir -pv ${HOME_TMP} \
    # in the interest of backwards compatibility we have the 'users' group owns the home directory
    # we also set the SGID bit so that new files and directories are created with the 'users' group
 && chmod 2775 ${HOME_TMP} \
 && chown -R ${NB_USER}:${USERS_GID} ${HOME_TMP}

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
        # installs necessary tool for kerberos authentication setup
        krb5-user \
        # these are required by some r packages, adding these here so they get installed into all images.
        libfreetype6-dev \
        libpng-dev \
        libtiff5-dev \
        libjpeg-dev \
        libtiff-dev \
        libfreetype-dev \
        libfreetype6 \
        # Some common system dependencies
        libcairo2-dev \
        libpango1.0-dev \
        libgdk-pixbuf2.0-dev \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        libfontconfig1-dev \
        libpq-dev \
        zlib1g-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        # Use headless Java to save space
        openjdk-8-jre-headless \
    && apt-get upgrade --yes libwebp7 \
    && rm -rf /var/lib/apt/lists/*

# adds utility scripts
# add script for kerberos keytab creation
COPY --chmod=755 suspend-server.sh keep-alive.sh adjust-server-resources.py ktutil-keytab /usr/local/bin/

# add clean-layer script
COPY --chmod=755 clean-layer.sh /usr/bin/clean-layer.sh

# Combined tool installations with cleanup
RUN \
    # S6 Overlay
    curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/${S6_VERSION}/s6-overlay-noarch.tar.xz" -o /tmp/s6-overlay-noarch.tar.xz \
    && curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/${S6_VERSION}/s6-overlay-noarch.tar.xz.sha256" -o /tmp/s6-overlay-noarch.tar.xz.sha256 \
    && echo "$(cat /tmp/s6-overlay-noarch.tar.xz.sha256 | awk '{ print $1; }')  /tmp/s6-overlay-noarch.tar.xz" | sha256sum -c - \
    && curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/${S6_VERSION}/s6-overlay-${S6_ARCH}.tar.xz" -o /tmp/s6-overlay-${S6_ARCH}.tar.xz \
    && curl -fsSL "https://github.com/just-containers/s6-overlay/releases/download/${S6_VERSION}/s6-overlay-${S6_ARCH}.tar.xz.sha256" -o /tmp/s6-overlay-${S6_ARCH}.tar.xz.sha256 \
    && echo "$(cat /tmp/s6-overlay-${S6_ARCH}.tar.xz.sha256 | awk '{ print $1; }')  /tmp/s6-overlay-${S6_ARCH}.tar.xz" | sha256sum -c - \
    && tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz \
    && tar -C / -Jxpf /tmp/s6-overlay-${S6_ARCH}.tar.xz \
    && rm /tmp/s6-overlay-noarch.tar.xz  \
        /tmp/s6-overlay-noarch.tar.xz.sha256 \
        /tmp/s6-overlay-${S6_ARCH}.tar.xz \
        /tmp/s6-overlay-${S6_ARCH}.tar.xz.sha256 \
    && chmod 0775 /run \
    && \
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

# Add helpers for shell initialization
# TODO: removing this for now as it was causing issues when opening terminal in vscode. Debug and fix where needed.
# COPY shell_helpers.sh /tmp/shell_helpers.sh

# Configure the shell
RUN sh /tmp/oh-my-zsh-install.sh --unattended --skip-chsh \
    && conda init bash \
    && conda init zsh \
    # && cat /tmp/shell_helpers.sh >> ${HOME}/.bashrc \
    # && cat /tmp/shell_helpers.sh >> ${HOME}/.zshrc \
    && touch ${HOME}/.zsh-installed \
    && touch ${HOME}/.hushlogin

ENV VISUAL="/usr/bin/nano"
ENV EDITOR=${VISUAL}

# ODBC drivers and Oracle client in one layer
RUN \
    # Microsoft ODBC drivers, add the signature to trust the Microsoft repo
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /etc/apt/trusted.gpg.d/microsoft.gpg \
    && echo "deb [arch=amd64] https://packages.microsoft.com/ubuntu/22.04/prod jammy main" > /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    # Install the driver
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
        msodbcsql18 \
        # optional: for bcp and sqlcmd
        mssql-tools18 \
        unixodbc \
        # installing unixODBC
        unixodbc-dev \
        # libaio1 needed for Oracle Instant Client
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
ENV NLS_LANG="AMERICAN_AMERICA.WE8MSWIN1252"
ENV LD_LIBRARY_PATH="/opt/oracle/instantclient_23_5"
ENV TNS_ADMIN="${LD_LIBRARY_PATH}/network/admin"
ENV PATH="${LD_LIBRARY_PATH}:/opt/mssql-tools18/bin:${PATH}"

# Dockerfile GIST: https://gist.github.com/mathis-marcotte/13a32c27ba9a7252864cb644a5029f06
# gets the linux client wallet and the tnsnames.ora file for Oracle DB connections
COPY --from=k8scc01covidacr.azurecr.io/oracletns:latest /azcopy/dbConnection/ ${LD_LIBRARY_PATH}/
COPY dbConnection/sqlnet.ora ${TNS_ADMIN}/sqlnet.ora

# give users permissions to edit the alias file
RUN chmod a+w ${TNS_ADMIN} \
    && chown $NB_UID:$NB_GID ${TNS_ADMIN}/tnsnames.ora

# increase stack soft limit to fix Oracle connection error ORA-24550 signo=11
# value taken from https://docs.oracle.com/en/database/oracle/oracle-database/26/ladbi/checking-resource-limits-for-oracle-software-installation-users.html
RUN echo "ulimit -Ss 10240" >> ${HOME}/.bashrc

# Final cleanup
RUN rm -rf /tmp/* /var/tmp/* \
    && find / -depth -name '*.pyc' -exec rm -rf '{}' + \
    && find / -depth -name '__pycache__' -exec rm -rfv '{}' + \
    && conda clean -afy \
    && fix-permissions $CONDA_DIR \
    && fix-permissions /home/$NB_USER

# s6 - copy scripts
COPY --chown=${NB_USER}:${NB_GID} --chmod=755 s6/ /etc

USER $NB_UID

ENTRYPOINT ["/init"]

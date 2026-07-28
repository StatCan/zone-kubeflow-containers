#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
# scipy-notebook rather than datascience-notebook: R now comes from CRAN's apt
# repository below (Julia is dropped deliberately), so the conda R/Julia stack
# the datascience image adds on top of scipy is no longer wanted.
ARG BASE_IMAGE=quay.io/jupyter/scipy-notebook
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
ARG KUBECTL_VERSION=v1.34.5
ARG KUBECTL_URL=https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl
ARG AZCLI_URL=https://aka.ms/InstallAzureCLIDeb
ARG OH_MY_ZSH_URL=https://raw.githubusercontent.com/loket/oh-my-zsh/feature/batch-mode/tools/install.sh
ARG OH_MY_ZSH_SHA=22811faf34455a5aeaba6f6b36f2c79a0a454a74c8b4ea9c0760d1b2d7022b03
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
        pinentry-tty \
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
        # zone-466: ROI.plugin.glpk package depends on Rglpk, which requires the system-level GNU Linear Programming Kit (GLPK)
        libglpk-dev \
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
        smbclient \
    && apt-get upgrade --yes libwebp7 \
    && rm -rf /var/lib/apt/lists/*

# System R from CRAN's Ubuntu repository, replacing the conda-forge R stack
# that previously came with the datascience-notebook base image. Keeping the
# interpreter out of conda decouples Zone R upgrades from conda-forge's r-*
# rebuild cycle: R package binaries come from Posit Package Manager instead
# (see images/mid), which publishes builds for new R versions immediately.
# R_APT_VERSION is the CRAN apt package revision for Ubuntu 24.04 (noble).
ARG R_APT_VERSION=4.6.1-1.2404.1
# Public PPM used at build time; in-cluster, s6 startup appends the internal
# Artifactory PPM remote for the running R version (see images/mid/s6).
ARG PPM_CRAN_URL=https://packagemanager.posit.co/cran/__linux__/noble/latest
RUN wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg \
    && . /etc/os-release \
    && echo "deb [signed-by=/etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg] https://cloud.r-project.org/bin/linux/ubuntu ${VERSION_CODENAME}-cran40/" > /etc/apt/sources.list.d/cran-r.list \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
        "r-base-core=${R_APT_VERSION}" \
        "r-base-dev=${R_APT_VERSION}" \
        "r-recommended=${R_APT_VERSION}" \
        # used by the s6 startup script to derive the PPM mirror name
        lsb-release \
        # pbdZMQ (IRkernel) links the system zeromq
        libzmq3-dev \
    && rm -f /etc/apt/sources.list.d/cran-r.list /etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    # Site-wide default repo: PPM serves prebuilt Linux binaries, but only
    # when the client advertises its R version in the HTTP user agent -- set
    # it explicitly (Posit-documented form); without it PPM falls back to
    # source tarballs and installs turn into compiles.
    && printf '%s\n' \
        'local({' \
        '  r <- getOption("repos")' \
        "  r[\"CRAN\"] <- \"${PPM_CRAN_URL}\"" \
        '  options(repos = r)' \
        '})' \
        'options(HTTPUserAgent = sprintf("R/%s R (%s)", getRversion(), paste(getRversion(), R.version["platform"], R.version["arch"], R.version["os"])))' \
        >> /etc/R/Rprofile.site \
    # R source installs must find the system .pc files: conda ships its own
    # pkg-config earlier in PATH whose default search path hides them.
    && printf '%s\n' \
        'PKG_CONFIG_PATH=/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/lib/pkgconfig:/usr/share/pkgconfig' \
        > /etc/R/Renviron.site \
    # s6 startup appends cluster-specific repos/env as the notebook user
    && chown ${NB_USER}:${NB_GID} /etc/R/Rprofile.site /etc/R/Renviron.site \
    # Jupyter R kernel against system R, registered into conda's Jupyter
    && Rscript -e "install.packages('IRkernel', repos = '${PPM_CRAN_URL}'); stopifnot('IRkernel' %in% rownames(installed.packages()))" \
    && Rscript -e "IRkernel::installspec(user = FALSE, prefix = '/opt/conda', name = 'ir', displayname = paste('R', getRversion()))" \
    && rm -rf /tmp/downloaded_packages /tmp/Rtmp*

# adds utility scripts
# add script for kerberos keytab creation
COPY --chmod=755 suspend-server.sh adjust-server-resources.py ktutil-keytab /usr/local/bin/

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

# Wrapper for nano to prevent segfault caused by ncurses library mismatch.
# At runtime, conda activation sets LD_LIBRARY_PATH to include /opt/conda/lib,
# which contains an incompatible ncurses. The wrapper strips LD_LIBRARY_PATH
# so the system nano loads the correct system ncurses.
# Placed in /usr/local/bin/ which takes precedence over /usr/bin/ in PATH.
RUN printf '#!/bin/sh\nexec env -u LD_LIBRARY_PATH /usr/bin/nano "$@"\n' > /usr/local/bin/nano \
    && chmod +x /usr/local/bin/nano

ENV VISUAL="/usr/local/bin/nano"
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
# NOTE: LD_LIBRARY_PATH is required for SAS Oracle connections (sasor12 uses dlopen).
# ldconfig alone is not sufficient for SAS. The nano wrapper (above) handles the
# ncurses conflict this causes by stripping LD_LIBRARY_PATH for nano specifically.
ENV NLS_LANG="AMERICAN_AMERICA.WE8MSWIN1252"
ENV LD_LIBRARY_PATH="/opt/oracle/instantclient_23_5"
ENV TNS_ADMIN="${LD_LIBRARY_PATH}/network/admin"
ENV PATH="${LD_LIBRARY_PATH}:/opt/mssql-tools18/bin:${PATH}"

# Dockerfile GIST: https://gist.github.com/mathis-marcotte/13a32c27ba9a7252864cb644a5029f06
# gets the linux client wallet and the tnsnames.ora file for Oracle DB connections
COPY --from=stcthezoneacr.azurecr.io/oracletns:latest /azcopy/dbConnection/ ${LD_LIBRARY_PATH}/
COPY dbConnection/sqlnet.ora ${TNS_ADMIN}/sqlnet.ora

# give users permissions to edit the alias file
RUN chmod a+w ${TNS_ADMIN} \
    && chown $NB_UID:$NB_GID ${TNS_ADMIN}/tnsnames.ora

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

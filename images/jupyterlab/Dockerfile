#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=sas_kernel
FROM $BASE_IMAGE

USER root

# Install VSCode extensions
# Override EXTENSIONS_GALLERY from base image to use public marketplace during build
ARG SERVICE_URL=https://extensions.coder.com/api
ENV CS_DEFAULT_HOME=$HOME/.local/share/code-server
RUN unset EXTENSIONS_GALLERY && \
    mkdir -p $CS_DEFAULT_HOME/Machine && \
    code-server --install-extension Posit.air-vscode@0.22.0 && \
    code-server --install-extension Orta.vscode-jest@6.4.4 && \
    code-server --install-extension ms-ceintl.vscode-language-pack-fr@1.99.0 && \
    code-server --install-extension adamviola.parquet-explorer@1.2.1 && \
    code-server --install-extension lucien-martijn.parquet-visualizer@0.31.1 && \
    wget -q https://github.com/microsoft/vscode-cpptools/releases/download/v1.20.5/cpptools-linux.vsix && \
    code-server --install-extension cpptools-linux.vsix && \
    rm cpptools-linux.vsix && \
    fix-permissions $CS_DEFAULT_HOME

# Install DuckDB and parquet support
RUN mamba install --quiet --yes -c conda-forge \
    'duckdb' \
    'duckdb-cli' \
    'python-duckdb' \
    && \
    # Install DuckDB extensions for parquet visualizer (air-gapped support)
    DUCK_BIN="/opt/conda/bin/duckdb" && \
    DUCK_VER=$($DUCK_BIN --version | cut -d' ' -f1) && \
    ABI_VER=v$(echo $DUCK_VER | cut -d'.' -f1-2).0 && \
    mkdir -p /home/$NB_USER/.duckdb/extensions/${ABI_VER}/linux_amd64/ && \
    $DUCK_BIN -c "INSTALL spatial; INSTALL httpfs; INSTALL icu; INSTALL avro; INSTALL parquet;" && \
    echo "SET extension_directory='/home/$NB_USER/.duckdb/extensions';" > /home/$NB_USER/.duckdbrc && \
    echo "SET allow_unsigned_extensions=true;" >> /home/$NB_USER/.duckdbrc && \
    chown -R $NB_USER:$NB_GID /home/$NB_USER/.duckdb /home/$NB_USER/.duckdbrc

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

# Install Jest testing framework
RUN npm install -g jest@29.7.0 && \
    npm cache clean --force && \
    rm -rf /root/.npm && \
    fix-permissions $CONDA_DIR

USER $NB_USER

# Update HOME_TMP to include DuckDB config (created after mid's HOME_TMP copy)
USER root
RUN cp -p -r -T "${HOME}" "${HOME_TMP}" \
    && chmod -R g=u "${HOME_TMP}"
USER $NB_USER
   

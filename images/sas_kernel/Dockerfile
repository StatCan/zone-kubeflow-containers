#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=mid
FROM $BASE_IMAGE

USER root

# SAS
# Install Quarto
ENV QUARTO_VERSION=1.8.1
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
    rm -rf /tmp/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz && \
    rm -rf /tmp/quarto-${QUARTO_VERSION}-checksums.txt && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1002 sasstaff && \
    usermod -a -G sasstaff jovyan && \
    echo "jovyan:jovyan" | chpasswd

# Dockerfile GIST: https://gist.github.com/Jose-Matsuda/c66dbf758620e4ae6bbd811a7b6471f1 
COPY --chown=jovyan:sasstaff --from=k8scc01covidacr.azurecr.io/sasinstallation:v1 /usr/local/SASHome /usr/local/SASHome

RUN ln -s /usr/local/SASHome/SASFoundation/9.4/bin/sas_en /usr/local/bin/sas 

# MinIO Client install
COPY --from=minio/mc:RELEASE.2025-04-16T18-13-26Z /bin/mc /usr/local/bin/mc

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/jovyan

ENV PATH=$PATH:/usr/local/SASHome/SASFoundation/9.4/bin
ENV PATH=$PATH:/usr/local/SASHome/SASPrivateJavaRuntimeEnvironment/9.4/jre/bin

# setuid.sh is not working as intended, seemingly cannot find the file so we do this instead.
#RUN /usr/local/SASHome/SASFoundation/9.4/utilities/bin/setuid.sh
RUN chown root /usr/local/SASHome/SASFoundation/9.4/utilities/bin/elssrv && \
    chown root /usr/local/SASHome/SASFoundation/9.4/utilities/bin/sasauth && \
    chown root /usr/local/SASHome/SASFoundation/9.4/utilities/bin/sasperm && \
    chmod 4755 /usr/local/SASHome/SASFoundation/9.4/utilities/bin/elssrv && \
    chmod 4755 /usr/local/SASHome/SASFoundation/9.4/utilities/bin/sasauth && \
    chmod 4755 /usr/local/SASHome/SASFoundation/9.4/utilities/bin/sasperm

ENV SAS_HADOOP_JAR_PATH=/opt/hadoop

EXPOSE 8561 8591 38080

# SASPY
ENV SASPY_VERSION="5.4.0"

RUN pip install sas_kernel

COPY sascfg.py /tmp/sascfg.py
RUN PYTHON_VERSION=$(python3 -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')") \
    && cp /tmp/sascfg.py /opt/conda/lib/$PYTHON_VERSION/site-packages/saspy/sascfg.py \
    && rm /tmp/sascfg.py

# SAS GConfid

COPY G-CONFID107003ELNX6494M7/ /usr/local/SASHome/gensys/G-CONFID107003ELNX6494M7/
COPY BANFF_2.08.002/ /usr/local/SASHome/gensys/BANFF_2.08.002/
COPY sasv9_local.cfg /usr/local/SASHome/SASFoundation/9.4/

# Remove libpdfbox-java due to CVE-2019-0228. See https://github.com/StatCan/aaw-kubeflow-containers/issues/249#issuecomment-834808115 for details.
# Issue opened https://github.com/jupyter/docker-stacks/issues/1299.
# This line of code should be removed once a solution or better alternative is found.
RUN apt-get update --yes \
    && dpkg -r --force-depends libpdfbox-java \
    && rm -rf /var/lib/apt/lists/*

USER $NB_USER

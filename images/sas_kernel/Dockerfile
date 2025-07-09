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
    rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1002 sasstaff && \
    usermod -a -G sasstaff jovyan && \
    echo "jovyan:jovyan" | chpasswd

COPY --from=k8scc01covidacr.azurecr.io/sas4c:0.0.3 /usr/local/SASHome /usr/local/SASHome
# MinIO Client install
COPY --from=minio/mc:RELEASE.2025-04-16T18-13-26Z /bin/mc /usr/local/bin/mc

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

COPY sascfg.py /tmp/sascfg.py
RUN PYTHON_VERSION=$(python3 -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')") \
    && cp /tmp/sascfg.py /opt/conda/lib/$PYTHON_VERSION/site-packages/saspy/sascfg.py \
    && rm /tmp/sascfg.py

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
    
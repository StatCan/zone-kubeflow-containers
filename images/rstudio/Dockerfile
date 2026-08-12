#
# NOTE: Use the docker-bake.hcl file to build this image correctly.
#
ARG BASE_IMAGE=mid
FROM $BASE_IMAGE

USER root

# Install RStudio Server and keep the temporary CRAN apt source scoped to this
# layer.
ARG RSTUDIO_VERSION=2026.04.0-526
ARG RSTUDIO_SHA256=9618cb9478d85ae7a606a773a73f6ea4221d3d69dfc0aba8358ce87c924a353a
RUN apt-get update \
    && wget -qO- https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg \
    && echo "deb [signed-by=/etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg] https://cloud.r-project.org/bin/linux/ubuntu jammy-cran40/" > /etc/apt/sources.list.d/cran-r.list \
    && apt-get update \
    && curl --silent -L --fail "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/rstudio-server-${RSTUDIO_VERSION}-amd64.deb" > /tmp/rstudio.deb \
    && echo "${RSTUDIO_SHA256} /tmp/rstudio.deb" | sha256sum -c - \
    && apt-get install --no-install-recommends -y /tmp/rstudio.deb \
    && rm /tmp/rstudio.deb \
    && rm -f /etc/apt/sources.list.d/cran-r.list /etc/apt/trusted.gpg.d/cran_ubuntu_key.gpg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# System R loads Ubuntu OpenSSL before reticulate embeds Conda Python. Build
# just CPython's OpenSSL extension modules against that already-loaded ABI,
# shadow the declared user-facing wheels whose Conda ELF graphs reach Conda
# OpenSSL, and retain py-rattler's self-contained wheel for audit closure.
# Standalone /opt/conda Python is unchanged because the overlay is selected
# only by the system-R rsession wrapper below.
ARG CPYTHON_VERSION=3.14.5
ARG CPYTHON_SHA256=7e32597b99e5d9a39abed35de4693fa169df3e5850d4c334337ffd6a19a36db6
COPY reticulate-compat-requirements.txt audit-reticulate-compat.py /opt/reticulate-compat-build/
RUN set -eux; \
    build_dir="$(mktemp -d /tmp/reticulate-cpython.XXXXXX)"; \
    source_archive="${build_dir}/Python-${CPYTHON_VERSION}.tar.xz"; \
    curl --fail --location --silent --show-error \
      "https://www.python.org/ftp/python/${CPYTHON_VERSION}/Python-${CPYTHON_VERSION}.tar.xz" \
      --output "${source_archive}"; \
    echo "${CPYTHON_SHA256}  ${source_archive}" | sha256sum -c -; \
    tar --extract --file "${source_archive}" --directory "${build_dir}"; \
    cd "${build_dir}/Python-${CPYTHON_VERSION}"; \
    PKG_CONFIG=/usr/bin/pkg-config ./configure \
      --with-openssl=/usr \
      --with-openssl-rpath=no \
      --without-ensurepip; \
    make -j"$(nproc)" sharedmods; \
    compat_python="/opt/reticulate-compat/lib/python3.14"; \
    compat_dynload="${compat_python}/lib-dynload"; \
    compat_site="${compat_python}/site-packages"; \
    install -d -m 0755 "${compat_dynload}" "${compat_site}"; \
    test -f Modules/_ssl.cpython-314-x86_64-linux-gnu.so; \
    test -f Modules/_hashlib.cpython-314-x86_64-linux-gnu.so; \
    install -m 0644 \
      Modules/_ssl.cpython-314-x86_64-linux-gnu.so \
      "${compat_dynload}/_ssl.cpython-314-x86_64-linux-gnu.so"; \
    install -m 0644 \
      Modules/_hashlib.cpython-314-x86_64-linux-gnu.so \
      "${compat_dynload}/_hashlib.cpython-314-x86_64-linux-gnu.so"; \
    /opt/conda/bin/python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      --no-deps \
      --only-binary=:all: \
      --require-hashes \
      --target "${compat_site}" \
      --requirement /opt/reticulate-compat-build/reticulate-compat-requirements.txt; \
    /opt/conda/bin/python /opt/reticulate-compat-build/audit-reticulate-compat.py \
      --conda-prefix /opt/conda \
      --overlay-root /opt/reticulate-compat; \
    touch /opt/reticulate-compat/.audit-passed; \
    chmod -R a+rX /opt/reticulate-compat; \
    cd /; \
    rm -rf "${build_dir}" /opt/reticulate-compat-build

# Harden rstudio-server and route sessions through the selected Conda env.
COPY rsession.conf /etc/rstudio/

# System-wide preference defaults. Applied to every user, including existing
# ones -- unlike the per-user rstudio-prefs.json further below, which is only
# seeded into a fresh HOME (01-copy-tmp-home uses `cp --update=none`).
# Selecting the "none" assistant/chat provider stops Posit Assistant from
# initialising, and assistant_show_messages=false suppresses its message box.
COPY rstudio-prefs-system.json /etc/rstudio/rstudio-prefs.json

# Jupyter RStudio Proxy
COPY customRStu/ /opt/jupyter-custom-rstudio-proxy/
RUN chmod 755 /opt/jupyter-custom-rstudio-proxy/start_rstudio_server.sh \
    && chmod 755 /opt/jupyter-custom-rstudio-proxy/rsession.sh \
    && chmod 755 /opt/jupyter-custom-rstudio-proxy/rstudio-use-current-conda.sh \
    && pip install --no-cache-dir /opt/jupyter-custom-rstudio-proxy/ \
    && fix-permissions $CONDA_DIR

# Terminal helper to save the current Conda env and stop any running RStudio
# processes before relaunching from the Jupyter tile.
COPY --chmod=755 customRStu/rstudio-use-current-conda.sh /usr/local/bin/rstudio-use-current-conda

ENV PATH=$PATH:/usr/lib/rstudio-server/bin

# RStudio 2026.04 ships Posit Assistant, which fetches
# https://cdn.posit.co/posit-ai/manifest.json at session startup -- unreachable
# in-cluster, so every session opens with an error popup.
#
# NOTE: neither env var fixes this on 2026.04.0+526. Unpacking the shipped
# .deb shows no RSTUDIO_DISABLE_POSIT_* string anywhere in the package:
# RSTUDIO_DISABLE_POSIT_ASSISTANT is the real switch (rstudio/rstudio#17234,
# and the only spelling in RStudio's source) but it landed after this build,
# and RSTUDIO_DISABLE_POSIT_AI has never existed. The system prefs above are
# what actually disable the feature here; this is kept only so a future
# RStudio bump picks it up automatically.
ENV RSTUDIO_DISABLE_POSIT_ASSISTANT=1

USER $NB_USER

# Seed first-boot home defaults
RUN install -d -m 0775 \
    "${HOME_TMP}/.config/rstudio" \
    "${HOME_TMP}/.local/share/rstudio" \
    "${HOME_TMP}/.rstudio"

COPY --chown=${NB_USER}:${NB_GID} rstudio-prefs.json ${HOME_TMP}/.config/rstudio/rstudio-prefs.json
COPY --chown=${NB_USER}:${NB_GID} customRStu/database.conf ${HOME_TMP}/.rstudio/database.conf

RUN chmod -R g=u \
    "${HOME_TMP}/.config/rstudio" \
    "${HOME_TMP}/.local/share/rstudio" \
    "${HOME_TMP}/.rstudio"

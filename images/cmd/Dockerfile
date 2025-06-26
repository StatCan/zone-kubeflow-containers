USER root

# Configure container startup

WORKDIR /home/$NB_USER
EXPOSE 8888
COPY start-custom.sh start-oms.sh restart-oms.sh /usr/local/bin/

RUN chmod +x /usr/local/bin/start-oms.sh && \
    chmod +x /usr/local/bin/start-custom.sh && \
    chmod +x /usr/local/bin/restart-oms.sh

# Add --user to all pip install calls and point pip to Artifactory repository
COPY pip.conf /tmp/pip.conf
RUN cat /tmp/pip.conf >> /etc/pip.conf && rm /tmp/pip.conf

# Add .Rprofile to /tmp so we can install it in start-custom.sh
COPY .Rprofile /tmp/.Rprofile

# Copy over Instructions to Home directory
ADD connect-to-filer.md /home/$NB_USER/connect-to-filer.md

# Point conda to Artifactory repository
RUN conda config --remove channels conda-forge --system

ENV TESTING="abcd-defg-hijk-elemeno-moredata"

ENV TESTING_SECOND="abcd-defg-hijk-elemeno-moredata"

USER $NB_USER
ENTRYPOINT ["tini", "--"]
CMD ["start-custom.sh"]

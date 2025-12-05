#! /bin/bash

# Script used to generate the .crt files for the given host
HOST=stc-ndm-new-qa-wc2.statcan.gc.ca
#HOST=stc-ndm-prod-wc.statcan.gc.ca

openssl s_client -showcerts -connect "${HOST}":443 < /dev/null |
   awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/{ if(/BEGIN CERTIFICATE/){a++}; out="cert"a".pem"; print >out}'
for cert in *.pem; do 
        newname=$(openssl x509 -noout -subject -in $cert | sed -nE 's/.*CN ?= ?(.*)/\1/; s/[ ,.*]/_/g; s/__/_/g; s/_-_/-/; s/^_//g;p' | tr '[:upper:]' '[:lower:]').crt
        echo "${newname}"; mv "${cert}" "${newname}" 
done
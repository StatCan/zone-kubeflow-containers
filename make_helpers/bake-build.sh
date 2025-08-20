#!/bin/bash

# Builds the desired image using bake, setting the needed parameters to override the bake file values
# Inputs: 
#   BASE_IMAGE (The base parent image for the image to build)
#   REPO (The location where our images live)
#   TAGS (Any desired tags on the final image, expects a space seperated list of values)
#   IMAGE_NAME (The name of the bake target to build)
#   DARGS (Any additional parameters to set to the bake command)

ARGS=()
# if there is a base image given, set that as the value for the BASE_IMAGE arg in the docker bake
[ ! -z "${BASE_IMAGE}" ] && ARGS+=("--set ${IMAGE_NAME}.args.BASE_IMAGE=${BASE_IMAGE}")

TAG_LIST=()
if [ ! -z "${TAGS}" ]; then
    TAG_LIST=($TAGS)
    # for each tag given, prefix the tag with the bake value to override the tags from the bake file
    TAG_LIST=( "${TAG_LIST[@]/#/--set ${IMAGE_NAME}.tags=${REPO}/${IMAGE_NAME}:}" )
    
    # concats the list of tag overrides to the bake parameters list
    ARGS+=( "${TAG_LIST[@]}" )
fi

docker buildx bake ${IMAGE_NAME} ${DARGS} ${ARGS[@]}
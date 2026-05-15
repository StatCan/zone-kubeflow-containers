#!/bin/bash

# Returns branch name, regardless of whether run locally or on github runner

if [[ $GITHUB_ACTIONS == "true" ]] ; then

	BRANCH_PATTERN="^refs/heads/(.*)"

	if [[ -n "${GITHUB_HEAD_REF:-}" ]]; then
		BRANCH_NAME=${GITHUB_HEAD_REF}
	elif [[ -n "${GITHUB_REF_NAME:-}" && "${GITHUB_REF_TYPE:-}" == "branch" ]]; then
		BRANCH_NAME=${GITHUB_REF_NAME}
	elif [[ $GITHUB_REF =~ $BRANCH_PATTERN ]]; then
		BRANCH_NAME=${BASH_REMATCH[1]}
	else
		BRANCH_NAME=""
	fi

else
	BRANCH_NAME=`git rev-parse --abbrev-ref HEAD`
fi

# The value is used as a Docker tag throughout the build pipeline.
# Docker tags cannot contain branch separators like "/".
BRANCH_NAME=$(sed -E 's/[^A-Za-z0-9_.-]+/-/g; s/^[.-]+//; s/[.-]+$//' <<<"$BRANCH_NAME")
BRANCH_NAME=${BRANCH_NAME:0:128}

echo ${BRANCH_NAME:-branch}

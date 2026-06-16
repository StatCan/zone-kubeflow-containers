#!/bin/bash

# Returns branch name, regardless of whether run locally or on github runner

if [[ $GITHUB_ACTIONS == "true" ]] ; then

	BRANCH_PATTERN="^refs/heads/(.*)"
	PR_PATTERN="^refs/pull/([0-9]+)/"

	if [[ $GITHUB_REF =~ $BRANCH_PATTERN ]]; then
		BRANCH_NAME=${BASH_REMATCH[1]}
	elif [[ $GITHUB_REF =~ $PR_PATTERN ]]; then
		PR_NUMBER=${BASH_REMATCH[1]}
		# If not specified, assume PR comes from StatCan/zone-kubeflow-containers
		OWNER=${OWNER:-StatCan}
	    REPOSITORY=${REPOSITORY:-zone-kubeflow-containers}
	    BRANCH_NAME=$(curl -s -H "Accept: application/vnd.github.v3+json" https://api.github.com/repos/$OWNER/$REPOSITORY/pulls/$PR_NUMBER | jq '.head.ref')
	    # Remove leading/trailing quotes
	    BRANCH_NAME=$(sed -e 's/^"//' -e 's/"$//' <<<"$BRANCH_NAME")
	else
		BRANCH_NAME=""
	fi

else
	BRANCH_NAME=`git rev-parse --abbrev-ref HEAD`
fi

# This value is used as a Docker tag throughout the build pipeline, and Docker
# tags cannot contain "/", so sanitize branch names like "feat/foo" -> "feat-foo".
BRANCH_NAME=$(sed -E 's/[^A-Za-z0-9_.-]+/-/g; s/^[.-]+//; s/[.-]+$//' <<<"$BRANCH_NAME")
echo ${BRANCH_NAME:-branch}

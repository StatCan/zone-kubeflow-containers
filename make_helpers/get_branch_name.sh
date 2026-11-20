#!/bin/bash

# Returns branch name, regardless of whether run locally or on github runner

if [[ $GITHUB_ACTIONS == "true" ]]; then
    case "$GITHUB_REF" in
        refs/heads/*) BRANCH_NAME=${GITHUB_REF#refs/heads/} ;;
        refs/pull/*) BRANCH_NAME=$GITHUB_HEAD_REF ;;
        *) BRANCH_NAME="" ;;
    esac
else
    BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
fi

# This value is used as a Docker tag throughout the build pipeline, and Docker
# tags cannot contain "/", so sanitize branch names like "feat/foo" -> "feat-foo".
BRANCH_NAME=$(sed -E 's/[^A-Za-z0-9_.-]+/-/g; s/^[.-]+//; s/[.-]+$//' <<<"$BRANCH_NAME")
echo ${BRANCH_NAME:-branch}

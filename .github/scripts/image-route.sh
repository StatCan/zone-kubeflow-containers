#!/usr/bin/env bash
set -eu
export LC_ALL=C

case "$GITHUB_EVENT_NAME:$GITHUB_REF" in
    push:refs/heads/master)
        suffix=''
        aliases='master v2 latest'
        ;;
    push:refs/heads/beta)
        suffix='-beta'
        aliases='latest'
        ;;
    pull_request:*|push:refs/heads/*)
        suffix='-branch'
        branch=${GITHUB_HEAD_REF:-${GITHUB_REF#refs/heads/}}
        if [[ $branch =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$ ]]; then
            aliases=$branch
        else
            # Keep slash-containing, long, or non-ASCII names distinct after sanitizing.
            slug=$(printf '%s' "$branch" | sed -E 's/[^a-zA-Z0-9_.-]+/-/g; s/^[.-]+//')
            hash=$(printf '%s' "$branch" | sha256sum)
            slug=${slug:-branch}
            aliases="${slug:0:115}-${hash:0:12}"
        fi
        ;;
    *) exit 1 ;;
esac

printf 'repository-suffix=%s\n' "$suffix"
printf 'tags=%s %s %s\n' "$aliases" "$(git rev-parse --short "$GITHUB_SHA")" "$GITHUB_SHA"

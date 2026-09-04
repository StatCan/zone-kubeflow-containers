#!/usr/bin/env python3
"""Validate that upstream base-image rebuilds propagate to downstream images."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY_ROOT / ".github/workflows/docker.yaml"


def validate_upstream_propagation() -> None:
    workflow = WORKFLOW.read_text()

    assert workflow.count('- "docker-bake.hcl"') == 2
    assert "is-diff: ${{ steps.upstream-diff.outputs.is-diff }}" in workflow
    assert (
        'parent-image-is-diff: "${{ needs.upstream-datascience.outputs.is-diff }}"'
        in workflow
    )
    assert "DOCKER_STACKS_REF|PYTHON_VERSION" in workflow
    assert '"${IMAGE_EXISTS}" != "true"' in workflow
    assert '"${DEFINITION_CHANGED}" == "true"' in workflow


if __name__ == "__main__":
    validate_upstream_propagation()

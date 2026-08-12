#!/usr/bin/env python3
"""Validate build propagation and first-start R repository configuration."""

import re
from pathlib import Path
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY_ROOT / ".github/workflows/docker.yaml"
STARTUP_SCRIPT = REPOSITORY_ROOT / "images/mid/s6/cont-init.d/02-start-custom"


def validate_upstream_scipy_propagation() -> None:
    workflow = WORKFLOW.read_text()

    assert workflow.count('- "docker-bake.hcl"') == 2
    assert "is-diff: ${{ steps.upstream-diff.outputs.is-diff }}" in workflow
    assert (
        'parent-image-is-diff: "${{ needs.upstream-scipy.outputs.is-diff }}"'
        in workflow
    )
    assert "DOCKER_STACKS_REF|PYTHON_VERSION" in workflow
    assert '"${IMAGE_EXISTS}" != "true"' in workflow
    assert '"${DEFINITION_CHANGED}" == "true"' in workflow


def validate_r_repositories() -> None:
    startup = STARTUP_SCRIPT.read_text()
    match = re.search(
        r"cat >> /etc/R/Rprofile\.site << EOF\n(?P<profile>.*?)\nEOF",
        startup,
        flags=re.DOTALL,
    )
    assert match is not None

    profile = match.group("profile")
    rendered = profile.replace(
        "$PPM_URL",
        "https://dummy.invalid/artifactory/zone-r-ppm-bin-noble-4.6-remote",
    ).replace(
        "$CRAN_LOCAL_URL",
        "https://dummy.invalid/artifactory/cran-local",
    )

    assert "@CRAN@" not in rendered
    assert 'r["ppm"]' not in rendered

    repositories = dict(re.findall(r'r\["([^"]+)"\] <- "([^"]+)"', rendered))
    assert set(repositories) == {"CRAN", "cran-local"}
    for repository in repositories.values():
        parsed = urlparse(repository)
        assert parsed.scheme == "https"
        assert parsed.hostname == "dummy.invalid"
        assert parsed.path.startswith("/artifactory/")


if __name__ == "__main__":
    validate_upstream_scipy_propagation()
    validate_r_repositories()

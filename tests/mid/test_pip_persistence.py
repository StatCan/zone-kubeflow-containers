"""
test_pip_persistence
~~~~~~~~~~~~~~~~~~~~
Test that `pip install` survives a notebook server restart (ZONE-543).

02-start-custom sets `[install] user = true` in /opt/conda/pip.conf, pip's site
scope, which only the base conda env reads. A bare `pip install` there lands in
~/.local on the workspace volume instead of the container layer, while venvs
keep installing into themselves. The jupyter service runs `python -s -P` so a
broken user package cannot stop the server from starting.

The tests build a throwaway wheel in the container and install it with
--no-index, so no network is needed.

Example:

    $ make test/mid
"""

import logging
import uuid

import pytest

from tests.general.wait_utils import wait_for_http_response

LOGGER = logging.getLogger(__name__)

PYTHON = "/opt/conda/bin/python"

BUILD_WHEEL = f"""
set -e
mkdir -p /tmp/z543/z543pkg
echo 'VERSION = "1.0"' > /tmp/z543/z543pkg/__init__.py
cat > /tmp/z543/pyproject.toml <<'EOF'
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
[project]
name = "z543pkg"
version = "1.0"
EOF
{PYTHON} -m pip wheel -q --no-deps --no-build-isolation -w /tmp/z543-wheels /tmp/z543
"""


@pytest.fixture()
def workspace(docker_client, container):
    """A docker volume standing in for a notebook server's workspace PVC."""
    volume = docker_client.volumes.create(name=f"zone543-{uuid.uuid4().hex[:8]}")
    yield {volume.name: {"bind": "/home/jovyan", "mode": "rw"}}
    # Docker will not remove a volume that a container still uses, and the
    # container fixture tears down after this one.
    container.remove()
    container.container = None
    volume.remove(force=True)


def _start_jupyter(container, http_client, nb_prefix, **kwargs):
    """Boot the image normally (s6 runs 02-start-custom) and wait for JupyterLab."""
    container.run(**kwargs)
    ready = wait_for_http_response(
        http_client=http_client,
        url=f"http://localhost:8888{nb_prefix}/api/status",
        expected_status=200,
        timeout=120,
        initial_delay=0.5,
        max_delay=3.0,
    )
    if not ready:
        logs = container.container.logs().decode("utf-8")
        raise AssertionError(f"JupyterLab did not start. Container logs (tail):\n{logs[-2000:]}")


def _exec(container, script):
    result = container.container.exec_run(["/bin/bash", "-c", script], user="jovyan", workdir="/tmp")
    output = result.output.decode("utf-8")
    assert result.exit_code == 0, output
    return output


@pytest.mark.integration
@pytest.mark.slow
def test_pip_install_persists_across_restarts(container, http_client, nb_prefix, workspace):
    """A bare `pip install` lands on the workspace volume and survives a restart.

    Kubeflow mounts one workspace PVC at /home/jovyan per notebook server, so
    packages are shared by that server's kernels and terminals, not across servers.
    """
    _start_jupyter(container, http_client, nb_prefix, volumes=workspace)
    output = _exec(container, BUILD_WHEEL + f"""
{PYTHON} -m pip install -q --no-index --no-deps /tmp/z543-wheels/z543pkg-*.whl
{PYTHON} -c 'import z543pkg; print("BASE:" + z543pkg.__file__)'
{PYTHON} -m venv /tmp/z543venv
/tmp/z543venv/bin/python -m pip install -q --no-index --no-deps /tmp/z543-wheels/z543pkg-*.whl
/tmp/z543venv/bin/python -c 'import z543pkg; print("VENV:" + z543pkg.__file__)'
""")
    assert "BASE:/home/jovyan/.local/lib/python" in output, output
    # A global (/etc/pip.conf) `user = true` fails here with "Can not perform a
    # '--user' install"; that is why it was removed in #422.
    assert "VENV:/tmp/z543venv/lib/python" in output, output

    # Restart on the same volume, as a pod restart does.
    container.remove()
    _start_jupyter(container, http_client, nb_prefix, volumes=workspace)
    output = _exec(container, f"{PYTHON} -c 'import z543pkg; print(\"FOUND:\" + z543pkg.__file__)'")
    assert "FOUND:/home/jovyan/.local/lib/python" in output, output


@pytest.mark.integration
@pytest.mark.slow
def test_jupyter_starts_with_a_broken_user_site(container, http_client, nb_prefix, workspace):
    """A user who breaks their own packages must not lock themselves out.

    Plants a traitlets (imported by jupyter_server) that raises, both in the user
    site directory, which -s hides, and in $HOME, which `-m` would put on sys.path
    without -P. Without either flag the server never comes up.
    """
    container.run(entrypoint=["/bin/bash", "-c", "sleep infinity"], ports={}, volumes=workspace)
    _exec(container, f"""
set -e
US=$({PYTHON} -c 'import site; print(site.getusersitepackages())')
mkdir -p "$US"
echo 'raise RuntimeError("broken user-site traitlets")' > "$US/traitlets.py"
echo 'raise RuntimeError("broken traitlets in HOME")' > /home/jovyan/traitlets.py
""")
    container.remove()

    _start_jupyter(container, http_client, nb_prefix, volumes=workspace)

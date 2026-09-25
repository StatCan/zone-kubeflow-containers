# Copyright (c) Statistics Canada. All rights reserved.

"""
test_pip_persistence
~~~~~~~~~~~~~~~~~~~~
Tests for persistent user pip installs (https://jirab.statcan.ca/browse/ZONE-543).

The image ships /opt/conda/pip.conf (pip's *site* scope) with ``[install] user =
true``, so a bare ``pip install`` in the base conda environment writes to
``~/.local/lib/pythonX.Y/site-packages`` -- on the workspace volume -- instead of
into the container layer under /opt/conda, where it is lost on restart.

The JupyterLab service is launched as ``python -s -m jupyterlab`` so that the
server process never reads that directory and cannot be broken by a package the
user installed. ``-s`` is not inherited by child processes, so kernels and
terminals still see everything the user installed.

These tests deliberately avoid the network: they build a throwaway wheel inside
the container and install it with ``--no-index``.

Example:

    $ make bake/mid
    $ make test/mid
"""

import logging
import uuid

import pytest

from tests.general.wait_utils import wait_for_http_response

LOGGER = logging.getLogger(__name__)

PYTHON = "/opt/conda/bin/python"

# Builds a wheel for a trivial package so the install exercises the real pip
# code path without reaching Artifactory.
BUILD_WHEEL = f"""
set -e
rm -rf /tmp/z543 /tmp/z543-wheels
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
{PYTHON} -m pip wheel --no-deps --no-build-isolation -q -w /tmp/z543-wheels /tmp/z543
"""

# Makes the user site directory poisonous: traitlets is imported by
# jupyter_server, and .pth files execute at interpreter start.
POISON_USER_SITE = f"""
set -e
US=$({PYTHON} -c 'import site; print(site.getusersitepackages())')
mkdir -p "$US"
echo 'raise RuntimeError("user broke traitlets")' > "$US/traitlets.py"
printf 'import sys; sys.stderr.write("POISONED\\n")\\n' > "$US/zzz_poison.pth"
"""

# The service does `cd "${HOME}"` before exec'ing, and `python -m` prepends the
# working directory to sys.path. A stray file in the home directory is therefore
# a second, independent route to the same lock-out that -s closes -- and one an
# ordinary user hits by accident, not by installing anything at all.
POISON_HOME_CWD = """
set -e
echo 'raise RuntimeError("user shadowed traitlets from $HOME")' > /home/jovyan/traitlets.py
"""


def _shell(container, script, **kwargs):
    """Start the image with a plain shell instead of s6 and run `script` in it.

    Returns (exit_code, output). Used for the checks that do not need a running
    JupyterLab server, so they cost a `docker run` rather than a full boot.
    """
    container.run(
        entrypoint=["/bin/bash", "-c", "sleep infinity"],
        ports={},
        **kwargs,
    )
    result = container.container.exec_run(
        ["/bin/bash", "-c", script], user="jovyan", workdir="/tmp"
    )
    return result.exit_code, result.output.decode("utf-8")


@pytest.fixture()
def workspace_volumes(docker_client, container):
    """Two named volumes standing in for two notebook servers' workspace PVCs.

    Kubeflow mounts a workspace PVC at /home/jovyan, one per Notebook, so two
    servers are isolated exactly as two volumes are here.
    """
    names = [f"zone543-{uuid.uuid4().hex[:8]}" for _ in range(2)]
    volumes = [docker_client.volumes.create(name=n) for n in names]
    yield names

    # Docker refuses to remove a volume any container still references, and the
    # container fixture tears down after this one, so drop the container here and
    # clear the reference so its own teardown becomes a no-op.
    container.remove()
    container.container = None
    for volume in volumes:
        try:
            volume.remove(force=True)
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            LOGGER.warning(f"Failed to remove volume {volume.name}: {exc}")


def _mount(name):
    return {name: {"bind": "/home/jovyan", "mode": "rw"}}


@pytest.mark.smoke
@pytest.mark.integration
def test_site_scoped_pip_config_is_shipped(container):
    """The `user = true` default must be at site scope, not global scope.

    Global scope (/etc/pip.conf) applies inside virtual environments too, where
    a user install is impossible -- that is what made the 2021 attempt at this
    (commit 44fd3c5, reverted by c59377c) break `pip install` in a venv.
    """
    exit_code, output = _shell(container, f"{PYTHON} -m pip config debug")

    assert exit_code == 0, f"pip config debug failed:\n{output}"
    assert "/opt/conda/pip.conf, exists: True" in output, (
        f"site-scoped pip config missing from the image:\n{output}"
    )
    assert "install.user: true" in output, (
        f"site-scoped pip config does not set install.user:\n{output}"
    )
    global_section = output.split("site:")[0]
    assert "install.user" not in global_section, (
        f"the user install default must not be set at global scope:\n{output}"
    )


@pytest.mark.integration
def test_bare_pip_install_lands_on_the_workspace_volume(container):
    """A plain `pip install` writes under $HOME, not into the container layer."""
    exit_code, output = _shell(
        container,
        BUILD_WHEEL
        + f"""
{PYTHON} -m pip install -q --no-index --no-deps /tmp/z543-wheels/z543pkg-*.whl
{PYTHON} -c 'import z543pkg; print("LANDED:" + z543pkg.__file__)'
""",
    )

    assert exit_code == 0, f"install failed:\n{output}"
    assert "LANDED:/home/jovyan/.local/lib/python" in output, (
        f"pip install did not land in the user site directory:\n{output}"
    )


@pytest.mark.integration
def test_pip_install_inside_a_venv_is_unaffected(container):
    """A venv must keep working: site scope is invisible once sys.prefix moves.

    This is the regression that forced the 2022 revert (commit ed7999f) of the
    forced-virtualenv work; a global `user = true` makes pip fail here with
    "Can not perform a '--user' install".
    """
    exit_code, output = _shell(
        container,
        BUILD_WHEEL
        + f"""
{PYTHON} -m venv /tmp/z543venv
/tmp/z543venv/bin/python -m pip install -q --no-index --no-deps /tmp/z543-wheels/z543pkg-*.whl
/tmp/z543venv/bin/python -c 'import z543pkg; print("VENV:" + z543pkg.__file__)'
""",
    )

    assert exit_code == 0, f"venv install failed:\n{output}"
    assert "Can not perform a '--user' install" not in output, (
        f"site-scoped config leaked into the venv:\n{output}"
    )
    assert "VENV:/tmp/z543venv/lib/python" in output, (
        f"venv install did not stay inside the venv:\n{output}"
    )


@pytest.mark.integration
def test_no_user_restores_the_previous_behaviour(container):
    """`--no-user` is the documented escape hatch and must still work."""
    exit_code, output = _shell(
        container,
        BUILD_WHEEL
        + f"""
{PYTHON} -m pip install -q --no-index --no-deps --no-user /tmp/z543-wheels/z543pkg-*.whl
{PYTHON} -c 'import z543pkg; print("LANDED:" + z543pkg.__file__)'
""",
    )

    assert exit_code == 0, f"--no-user install failed:\n{output}"
    assert "LANDED:/opt/conda/lib/python" in output, (
        f"--no-user did not install into the base environment:\n{output}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_package_persists_on_one_server_and_is_absent_on_another(
    container, workspace_volumes
):
    """Install on server A, then check a restarted A and a separate server B.

    The isolation unit is the Kubeflow Notebook (one workspace PVC mounted at
    /home/jovyan per notebook server), not a notebook file or a kernel.
    """
    server_a, server_b = workspace_volumes

    exit_code, output = _shell(
        container,
        BUILD_WHEEL
        + f"{PYTHON} -m pip install -q --no-index --no-deps /tmp/z543-wheels/z543pkg-*.whl",
        volumes=_mount(server_a),
    )
    assert exit_code == 0, f"install on server A failed:\n{output}"
    container.remove()

    check = f'{PYTHON} -c \'import z543pkg; print("FOUND:" + z543pkg.__file__)\''

    # Server A, new container, same volume: the package survived the restart.
    exit_code, output = _shell(container, check, volumes=_mount(server_a))
    assert exit_code == 0, f"package did not survive a restart of server A:\n{output}"
    assert "FOUND:/home/jovyan/.local/lib/python" in output, output
    container.remove()

    # Server B, different volume: the package is not there.
    exit_code, output = _shell(container, check, volumes=_mount(server_b))
    assert exit_code != 0, (
        f"package installed on server A leaked into server B:\n{output}"
    )
    assert "ModuleNotFoundError" in output, output


@pytest.mark.integration
def test_image_default_packages_still_import(container, workspace_volumes):
    """User packages layer on top of the image; they never replace it.

    The base environment is left in place rather than copied into $HOME, so the
    ~20 GB of preinstalled software stays exactly one shared copy on disk.
    """
    server_a, _ = workspace_volumes
    modules = (
        "pandas",
        "numpy",
        "pyarrow",
        "jupyterlab",
        "jupyter_server",
        "traitlets",
        "ipykernel",
    )
    script = (
        BUILD_WHEEL
        + f"{PYTHON} -m pip install -q --no-index --no-deps /tmp/z543-wheels/z543pkg-*.whl\n"
        + f"{PYTHON} -c 'import "
        + ", ".join(modules)
        + "; print(\"IMPORTS_OK:\" + pandas.__file__)'"
    )

    exit_code, output = _shell(container, script, volumes=_mount(server_a))

    assert exit_code == 0, f"image default packages stopped importing:\n{output}"
    assert "IMPORTS_OK:/opt/conda/lib/python" in output, (
        f"image defaults are no longer served from the base environment:\n{output}"
    )


@pytest.mark.integration
def test_user_jupyter_data_dir_is_still_searched_by_the_server(container):
    """`-s` hides ~/.local from imports, not from Jupyter's data path.

    Prebuilt (federated) JupyterLab extensions are discovered from
    ~/.local/share/jupyter/labextensions on the filesystem, so a plain
    `pip install` of one still reaches the server. Only *server* extensions,
    which the server has to import, need `--no-user`.
    """
    exit_code, output = _shell(
        container,
        f"{PYTHON} -s -c 'from jupyter_core.paths import jupyter_path; "
        'print("PATHS:" + ":".join(jupyter_path()))\'',
    )

    assert exit_code == 0, output
    assert "PATHS:/home/jovyan/.local/share/jupyter" in output, (
        f"the user data directory dropped off the server's search path:\n{output}"
    )


@pytest.mark.integration
def test_kernels_see_user_packages_but_the_server_does_not(container):
    """`-s` must protect the server without hiding packages from kernels.

    Kernels are fresh child processes (`/opt/conda/bin/python -m
    ipykernel_launcher`), and `-s` is not inherited, unlike PYTHONNOUSERSITE=1
    which would also blind them.
    """
    exit_code, output = _shell(
        container,
        BUILD_WHEEL
        + f"""
{PYTHON} -m pip install -q --no-index --no-deps /tmp/z543-wheels/z543pkg-*.whl
{PYTHON} -s -c 'import z543pkg' 2>/dev/null && echo SERVER_SEES:YES || echo SERVER_SEES:NO
{PYTHON} -s -c 'import subprocess, sys
r = subprocess.run([sys.executable, "-c", "import z543pkg"])
print("KERNEL_SEES:" + ("YES" if r.returncode == 0 else "NO"))'
""",
    )

    assert exit_code == 0, output
    assert "SERVER_SEES:NO" in output, (
        f"the server process can still import user packages:\n{output}"
    )
    assert "KERNEL_SEES:YES" in output, (
        f"kernels can no longer import user packages:\n{output}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_boot_configures_the_artifactory_index_in_the_user_scope(
    container, http_client, url="http://localhost:8888"
):
    """The boot script's `pip config set` must not get captured by the site file.

    `pip config set` writes to the user file only while no site file exists and
    switches to the site file as soon as one does. The site file is root-owned,
    so 02-start-custom needs an explicit `--user`; without it the write fails
    with EACCES and the server never learns the Artifactory index-url.
    """
    nb_prefix = container.kwargs["environment"]["NB_PREFIX"]
    container.run()

    responsive = wait_for_http_response(
        http_client=http_client,
        url=f"{url}{nb_prefix}/api/status",
        expected_status=200,
        timeout=120,
        initial_delay=0.5,
        max_delay=3.0,
    )
    assert responsive, "JupyterLab did not come up"

    logs = container.container.logs(stdout=True, stderr=True).decode("utf-8")
    assert "Unable to save configuration" not in logs, (
        f"the boot-time pip config write failed:\n{logs[-2000:]}"
    )

    result = container.container.exec_run(
        [PYTHON, "-m", "pip", "config", "debug"], user="jovyan"
    )
    output = result.output.decode("utf-8")
    # Split on the section header, not on "user:" -- that also matches the
    # "install.user: true" line inside the site section.
    site_section, _, user_section = output.partition("\nuser:\n")
    assert "install.user: true" in site_section, (
        f"boot clobbered the site-scoped user install default:\n{output}"
    )
    assert "global.index-url" in user_section, (
        f"boot did not configure the index-url in the user scope:\n{output}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_jupyter_starts_with_a_broken_user_site(
    container, http_client, workspace_volumes, url="http://localhost:8888"
):
    """A user who breaks their own site-packages must not lock themselves out.

    Before this change the same volume left the pod unreachable: `jupyter lab`
    imported the poisoned traitlets and exited, with no way in to remove it.
    """
    server_a, _ = workspace_volumes

    exit_code, output = _shell(
        container, POISON_USER_SITE, volumes=_mount(server_a)
    )
    assert exit_code == 0, f"failed to set up the poisoned user site:\n{output}"
    container.remove()

    nb_prefix = container.kwargs["environment"]["NB_PREFIX"]
    container.run(volumes=_mount(server_a))

    responsive = wait_for_http_response(
        http_client=http_client,
        url=f"{url}{nb_prefix}/api/status",
        expected_status=200,
        timeout=120,
        initial_delay=0.5,
        max_delay=3.0,
    )

    if not responsive:
        logs = container.container.logs(stdout=True, stderr=True).decode("utf-8")
        raise AssertionError(
            "JupyterLab did not start with a broken user site directory.\n"
            f"Container logs (tail):\n{logs[-2000:]}"
        )

    LOGGER.info("JupyterLab started despite a poisoned user site directory")


@pytest.mark.integration
@pytest.mark.slow
def test_jupyter_starts_with_a_module_shadowed_from_the_home_directory(
    container, http_client, workspace_volumes, url="http://localhost:8888"
):
    """A stray .py file in $HOME must not take the server down either.

    Regression test for the -P flag. The service runs `python -m` from $HOME, so
    without -P the working directory is sys.path[0] and `~/traitlets.py` is
    imported in preference to the real module -- no pip install required, and
    the pod is unreachable. -s alone does not close this.
    """
    server_a, _ = workspace_volumes

    exit_code, output = _shell(
        container, POISON_HOME_CWD, volumes=_mount(server_a)
    )
    assert exit_code == 0, f"failed to plant the shadowing module:\n{output}"
    container.remove()

    nb_prefix = container.kwargs["environment"]["NB_PREFIX"]
    container.run(volumes=_mount(server_a))

    responsive = wait_for_http_response(
        http_client=http_client,
        url=f"{url}{nb_prefix}/api/status",
        expected_status=200,
        timeout=120,
        initial_delay=0.5,
        max_delay=3.0,
    )

    if not responsive:
        logs = container.container.logs(stdout=True, stderr=True).decode("utf-8")
        raise AssertionError(
            "JupyterLab did not start with a module shadowed from $HOME.\n"
            f"Container logs (tail):\n{logs[-2000:]}"
        )

    LOGGER.info("JupyterLab started despite a shadowing module in $HOME")

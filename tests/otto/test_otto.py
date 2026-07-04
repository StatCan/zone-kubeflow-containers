"""
test_otto
~~~~~~~~~~~~~~~
Test the otto coding assistant CLI (otto image).

Static checks only — no model calls, so no Azure resources are needed:
the CLI entry point, the package modules, session persistence, the edit
tool's exact-match contract, output truncation, and the approval default
for non-interactive runs.

Example:

    $ make test/otto
"""

import logging

import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


def _wait_ready(container):
    container.run()
    success, output = wait_for_exec_success(
        container=container,
        command=["which", "otto"],
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0,
    )
    if not success:
        raise AssertionError(
            f"Container failed to be ready for execution within timeout. Output: {output}"
        )


def _run_python(container, code):
    result = container.container.exec_run(["python", "-c", code])
    assert result.exit_code == 0, result.output.decode("utf-8")
    return result.output.decode("utf-8")


@pytest.mark.smoke
def test_otto_installed(container):
    """The CLI is on PATH, the package imports, and the wheel is shipped."""
    _wait_ready(container)

    result = container.container.exec_run(["otto", "--version"])
    assert result.exit_code == 0 and b"otto" in result.output, (
        f"otto --version failed: {result.output}"
    )

    _run_python(
        container,
        "import otto, otto.agent, otto.cli, otto.config, otto.notebooks, "
        "otto.prompt, otto.session, otto.storage, otto.tools",
    )

    # Wheel for user-created venvs (same convention as zone-token-broker)
    result = container.container.exec_run(
        ["bash", "-c", "ls /opt/otto/dist/otto-*.whl"]
    )
    assert result.exit_code == 0, f"otto wheel missing: {result.output}"

    # Fails fast, with guidance, when no deployment is configured
    result = container.container.exec_run(
        ["env", "-u", "OTTO_DEPLOYMENT", "otto", "hello"]
    )
    assert result.exit_code == 2 and b"OTTO_DEPLOYMENT" in result.output, (
        f"missing-deployment handling broken: {result.output}"
    )


def test_otto_behaviour(container):
    """Session persistence, edit contract, truncation, approval default."""
    _wait_ready(container)

    # Sessions: append/load round trip, rewrite (compaction), latest, listing
    _run_python(
        container,
        """
import otto.session as s
sid = s.new_id()
s.append(sid, {"role": "user", "content": "hello world"})
s.append(sid, {"role": "assistant", "content": "hi"})
assert [m["content"] for m in s.load(sid)] == ["hello world", "hi"]
s.rewrite(sid, [{"role": "user", "content": "summary"}])
assert [m["content"] for m in s.load(sid)] == ["summary"]
assert s.latest() == sid
assert any(row[0] == sid for row in s.listing())
""",
    )

    # edit_file: unique exact match only; ambiguous or absent text is refused
    _run_python(
        container,
        """
import otto.tools as t
path = "/tmp/otto_edit_test.txt"
t.write_file(path, "aaa\\nbbb\\naaa\\n")
assert t.edit_file(path, "zzz", "x").startswith("error: old_string not found")
assert "matches 2 times" in t.edit_file(path, "aaa", "x")
assert t.edit_file(path, "bbb", "BBB").startswith("Edited")
assert t.read_file(path) == "aaa\\nBBB\\naaa"
""",
    )

    # Output truncation and safe dispatch of model-supplied calls
    _run_python(
        container,
        """
import otto.tools as t
long = t.run("bash", {"command": "yes x | head -c 100000"})
assert len(long) < t.MAX_OUTPUT_CHARS + 100 and "[output truncated" in long
assert t.run("no_such_tool", {}).startswith("error: unknown tool")
assert t.run("read_file", {"path": "/no/such/file"}).startswith("error:")
assert "[exit code 3]" in t.run("bash", {"command": "exit 3"})
""",
    )

    # Mutations are denied by default when there is no TTY to ask on
    _run_python(
        container,
        """
from otto.cli import _make_approver
assert _make_approver(False)("bash", {"command": "true"}) is False
assert _make_approver(True)("bash", {"command": "true"}) is True
""",
    )

    # Notebook tools: create, edit, read round trip (nbformat ships in the image)
    _run_python(
        container,
        """
import otto.tools as t
path = "/tmp/otto_nb_test.ipynb"
assert "1 cells now" in t.run("edit_notebook", {"path": path, "op": "append", "source": "x = 1"})
assert "2 cells now" in t.run("edit_notebook", {"path": path, "op": "append", "source": "# notes", "cell_type": "markdown"})
assert "replace at cell 0" in t.run("edit_notebook", {"path": path, "op": "replace", "index": 0, "source": "x = 2"})
out = t.run("read_notebook", {"path": path})
assert "[cell 0: code]" in out and "x = 2" in out and "# notes" in out
assert t.run("edit_notebook", {"path": path, "op": "replace", "index": 9, "source": "y"}).startswith("error: index")
assert t.run("read_notebook", {"path": "/tmp/no_such.ipynb"}).startswith("error:")
""",
    )

    # Storage tools: registered, approval-gated, URL contract enforced offline
    _run_python(
        container,
        """
import otto.tools as t
names = {d["function"]["name"] for d in t.DEFINITIONS}
assert {"read_notebook", "edit_notebook", "azure_ls", "azure_download", "azure_upload"} <= names
assert {"azure_download", "azure_upload", "edit_notebook"} <= t.MUTATING
assert "read_notebook" not in t.MUTATING and "azure_ls" not in t.MUTATING
assert t.run("azure_ls", {"url": "https://wrong"}).startswith("error:")
assert t.run("azure_upload", {"src": "/no/such", "url": "az://c@a.dfs.core.windows.net/x"}).startswith("error:")
""",
    )

    # Prod configuration layer: profiles resolve with layered precedence,
    # env fallback still works, and the shipped example config parses
    _run_python(
        container,
        """
import os, tomllib
import otto.config as c

with open("/etc/otto/config.toml.example", "rb") as fh:
    example = tomllib.load(fh)
assert example["default_model"] in example["models"]

os.environ["HOME"] = "/tmp/cfg-test"
os.makedirs("/tmp/cfg-test/.otto", exist_ok=True)
with open("/tmp/cfg-test/.otto/config.toml", "w") as fh:
    fh.write(chr(10).join([
        'default_model = "t"',
        "[models.t]",
        'endpoint = "https://x.openai.azure.com"',
        'deployment = "d"',
    ]))
m = c.resolve()
assert m.name == "t" and m.auth == "broker" and m.provider == "azure-openai"
assert c.resolve(deployment="other").deployment == "other"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://env.openai.azure.com"
os.environ["OTTO_DEPLOYMENT"] = "envdep"
os.environ["AZURE_OPENAI_API_KEY"] = "k"
assert c.resolve("not-configured").auth == "api-key"
""",
    )

"""
test_zone_agent
~~~~~~~~~~~~~~~
Test the zone-agent coding assistant CLI (zone-agent image).

Static checks only — no model calls, so no Azure resources are needed:
the CLI entry point, the package modules, session persistence, the edit
tool's exact-match contract, output truncation, and the approval default
for non-interactive runs.

Example:

    $ make test/zone-agent
"""

import logging

import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


def _wait_ready(container):
    container.run()
    success, output = wait_for_exec_success(
        container=container,
        command=["which", "zone-agent"],
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
def test_zone_agent_installed(container):
    """The CLI is on PATH, the package imports, and the wheel is shipped."""
    _wait_ready(container)

    result = container.container.exec_run(["zone-agent", "--version"])
    assert result.exit_code == 0 and b"zone-agent" in result.output, (
        f"zone-agent --version failed: {result.output}"
    )

    _run_python(
        container,
        "import zone_agent, zone_agent.agent, zone_agent.cli, "
        "zone_agent.prompt, zone_agent.session, zone_agent.tools",
    )

    # Wheel for user-created venvs (same convention as zone-token-broker)
    result = container.container.exec_run(
        ["bash", "-c", "ls /opt/zone-agent/dist/zone_agent-*.whl"]
    )
    assert result.exit_code == 0, f"zone-agent wheel missing: {result.output}"

    # Fails fast, with guidance, when no deployment is configured
    result = container.container.exec_run(
        ["env", "-u", "ZONE_AGENT_DEPLOYMENT", "zone-agent", "hello"]
    )
    assert result.exit_code == 2 and b"ZONE_AGENT_DEPLOYMENT" in result.output, (
        f"missing-deployment handling broken: {result.output}"
    )


def test_zone_agent_behaviour(container):
    """Session persistence, edit contract, truncation, approval default."""
    _wait_ready(container)

    # Sessions: append/load round trip, rewrite (compaction), latest, listing
    _run_python(
        container,
        """
import zone_agent.session as s
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
import zone_agent.tools as t
path = "/tmp/zone_agent_edit_test.txt"
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
import zone_agent.tools as t
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
from zone_agent.cli import _make_approver
assert _make_approver(False)("bash", {"command": "true"}) is False
assert _make_approver(True)("bash", {"command": "true"}) is True
""",
    )

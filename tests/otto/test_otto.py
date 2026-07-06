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
        "otto.prompt, otto.session, otto.storage, otto.tools, otto.ui",
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
import otto.ui as u
from otto.cli import _make_approver
view = u.UI()
assert _make_approver(False, view)("bash", {"command": "true"}) is False
assert _make_approver(True, view)("bash", {"command": "true"}) is True
""",
    )

    # Terminal presentation: plain when piped, styled + streamed when pretty
    _run_python(
        container,
        """
import io
import otto.ui as u

# Without a TTY nothing decorative is emitted (pipes stay machine-readable)
plain = u.UI(out=io.StringIO())
assert plain.pretty is False and plain.color is False
assert plain.paint(u.ACCENT, "x") == "x"
plain.tool_call("bash", {"command": "ls"})
plain.banner("0", "m", "/")
assert plain.out.getvalue() == ""

# Pretty mode: markdown streams with styling, fed in awkward chunks
out = io.StringIO()
view = u.UI(out=out, pretty=True)
view.begin_turn()
for chunk in ("Use ", "`x`", " now\\n", "- a bullet\\n", "```", "py\\ncode\\n``", "`\\ntail"):
    view.stream_feed(chunk)
assert view.stream_close() is True
text = out.getvalue()
assert "\\033[36mx\\033[0m" in text          # inline code styled
assert "\\033[38;5;208m\\u2022\\033[0m a bullet" in text  # bullet swapped
assert "\\u2502" in text and "code" in text  # fenced code gets a gutter
assert text.rstrip("\\n").endswith("tail")   # unterminated tail flushed

# Tool traces: call line, result preview with exit-code and size hints
out = io.StringIO()
view = u.UI(out=out, pretty=True)
view.tool_call("bash", {"command": "python x.py"})
view.tool_result("bash", {}, "boom\\n[exit code 2]")
view.tool_result("bash", {}, "Denied by user.")
text = out.getvalue()
assert "bash" in text and "python x.py" in text
assert "exit 2" in text and "denied" in text
assert u.describe_call("azure_upload", {"src": "a", "url": "b"}) == "a b"
""",
    )

    # Streaming assembly: text deltas and fragmented tool calls, offline
    _run_python(
        container,
        """
import types
import otto.agent as a
import otto.config as c

def chunk(content=None, calls=None, usage=None):
    delta = types.SimpleNamespace(content=content, tool_calls=calls)
    choice = types.SimpleNamespace(delta=delta)
    return types.SimpleNamespace(choices=[choice] if (content or calls) else [], usage=usage)

def call_delta(index, id=None, name=None, arguments=None):
    fn = types.SimpleNamespace(name=name, arguments=arguments)
    return types.SimpleNamespace(index=index, id=id, function=fn)

chunks = [
    chunk(content="hel"), chunk(content="lo"),
    chunk(calls=[call_delta(0, id="c1", name="bash", arguments='{"comm')]),
    chunk(calls=[call_delta(0, arguments='and": "ls"}')]),
    chunk(usage=types.SimpleNamespace(total_tokens=10, prompt_tokens=7)),
]

class FakeCompletions:
    def create(self, **options):
        assert options.get("stream") is True
        return iter(chunks)

deltas = []
mc = c.ModelConfig("t", "https://x.openai.azure.com", "d")
bot = a.Agent(mc, "test", [], approve=lambda n, g: False, on_delta=deltas.append)
bot._client = types.SimpleNamespace(
    chat=types.SimpleNamespace(completions=FakeCompletions())
)
reply = bot._create([{"role": "user", "content": "hi"}], stream=True)
assert "".join(deltas) == "hello" and reply.content == "hello"
assert reply.tool_calls[0].id == "c1"
assert reply.tool_calls[0].function.arguments == '{"command": "ls"}'
assert bot.total_tokens == 10 and bot._prompt_tokens == 7
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

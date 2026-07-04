"""Local tools the agent can call: file access, search, and shell.

Every tool returns a string that is fed back to the model as the tool
result. Errors are returned as strings too, so the model can adapt instead
of crashing the session. Output is capped to protect the context window.
"""

import os
import pathlib
import subprocess

MAX_OUTPUT_CHARS = 16000
BASH_TIMEOUT_SECONDS = 120

# Tools that modify state and therefore require user approval.
MUTATING = frozenset({"write_file", "edit_file", "bash"})

DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a text file. Returns the whole file, or a slice when "
                "offset/limit are given (useful for large files)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (~ allowed)."},
                    "offset": {"type": "integer", "description": "1-based line to start from."},
                    "limit": {"type": "integer", "description": "Maximum number of lines to return."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List a directory's entries; directories get a trailing slash.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: current directory)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": (
                "Search file contents recursively with a regular expression "
                "(grep -rn; binary files and .git are skipped). Returns "
                "path:line:match lines."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "grep -E regular expression."},
                    "path": {"type": "string", "description": "File or directory to search (default: current directory)."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content. Parent directories are created.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (~ allowed)."},
                    "content": {"type": "string", "description": "Full file content."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace one exact occurrence of old_string with new_string in "
                "a file. old_string must match the file contents exactly and "
                "uniquely; include surrounding lines to disambiguate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (~ allowed)."},
                    "old_string": {"type": "string", "description": "Exact text to replace."},
                    "new_string": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Run a shell command and return its output and exit code. Each "
                "call is a fresh shell in the directory otto was started "
                "from; chain with && if you need cd or environment changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to run."},
                    "timeout": {"type": "integer", "description": "Seconds before the command is killed (default 120)."},
                },
                "required": ["command"],
            },
        },
    },
]


def _resolve(path):
    return pathlib.Path(path).expanduser()


def _clip(text):
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    dropped = len(text) - MAX_OUTPUT_CHARS
    return text[:MAX_OUTPUT_CHARS] + "\n[output truncated: %d more characters]" % dropped


def read_file(path, offset=None, limit=None):
    lines = _resolve(path).read_text(errors="replace").splitlines()
    start = max((offset or 1) - 1, 0)
    end = start + limit if limit else len(lines)
    body = "\n".join(lines[start:end])
    return _clip(body) if body else "(empty)"


def list_dir(path="."):
    target = _resolve(path)
    entries = [
        entry + ("/" if (target / entry).is_dir() else "")
        for entry in sorted(os.listdir(target))
    ]
    return _clip("\n".join(entries)) if entries else "(empty directory)"


def grep(pattern, path="."):
    result = subprocess.run(
        ["grep", "-rnIE", "--exclude-dir=.git", "-e", pattern, str(_resolve(path))],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 1:
        return "(no matches)"
    if result.returncode > 1:
        return "grep error: %s" % result.stderr.strip()
    return _clip(result.stdout)


def write_file(path, content):
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return "Wrote %d bytes to %s" % (len(content.encode()), target)


def edit_file(path, old_string, new_string):
    target = _resolve(path)
    text = target.read_text()
    count = text.count(old_string)
    if count == 0:
        return "error: old_string not found in %s" % target
    if count > 1:
        return (
            "error: old_string matches %d times in %s; include more "
            "surrounding context so it is unique" % (count, target)
        )
    target.write_text(text.replace(old_string, new_string, 1))
    return "Edited %s" % target


def bash(command, timeout=None):
    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout or BASH_TIMEOUT_SECONDS,
    )
    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + "[stderr]\n" + result.stderr
    output = output.strip() or "(no output)"
    if result.returncode:
        output += "\n[exit code %d]" % result.returncode
    return _clip(output)


_HANDLERS = {
    "read_file": read_file,
    "list_dir": list_dir,
    "grep": grep,
    "write_file": write_file,
    "edit_file": edit_file,
    "bash": bash,
}


def run(name, arguments):
    """Execute tool `name` with dict `arguments`; always returns a string.

    The model is an untrusted caller: bad tool names, bad argument shapes,
    missing files and timeouts all come back as error strings it can react
    to, never as exceptions.
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        return "error: unknown tool %s" % name
    try:
        return handler(**arguments)
    except subprocess.TimeoutExpired:
        return "error: %s timed out" % name
    except TypeError as error:
        return "error: bad arguments for %s: %s" % (name, error)
    except Exception as error:  # noqa: BLE001 -- boundary with model-supplied input
        return "error: %s" % error


# Notebook and Azure storage tools plug into the same registry and the same
# approval gate.
from otto import notebooks, storage  # noqa: E402  (registry composition)

DEFINITIONS = DEFINITIONS + notebooks.DEFINITIONS + storage.DEFINITIONS
MUTATING = MUTATING | notebooks.MUTATING | storage.MUTATING
_HANDLERS.update(notebooks.HANDLERS)
_HANDLERS.update(storage.HANDLERS)

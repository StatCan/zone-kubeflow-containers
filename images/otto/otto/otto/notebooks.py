"""Notebook tools: read and edit .ipynb files through nbformat.

Reading renders cells with their outputs (including error tracebacks), so
the agent can answer "why did my cell fail" from what the user actually
sees. Editing operates on whole cells; running a notebook is done through
the bash tool (`jupyter execute --inplace`), which keeps execution behind
the approval gate.
"""

import pathlib
import re

MAX_OUTPUT_CHARS = 16000
MAX_CELL_OUTPUT_CHARS = 1500

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_notebook",
            "description": (
                "Read a Jupyter notebook (.ipynb): cells with their indexes, "
                "sources, and outputs including error tracebacks. Use this "
                "instead of read_file for notebooks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Notebook path (~ allowed)."},
                    "include_outputs": {
                        "type": "boolean",
                        "description": "Include cell outputs (default true).",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_notebook",
            "description": (
                "Edit a Jupyter notebook by whole cells: append a cell, "
                "insert one at an index, replace or delete the cell at an "
                "index. append creates the notebook if it does not exist."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Notebook path (~ allowed)."},
                    "op": {
                        "type": "string",
                        "enum": ["append", "insert", "replace", "delete"],
                        "description": "The edit operation.",
                    },
                    "index": {
                        "type": "integer",
                        "description": "Cell index (required for insert/replace/delete).",
                    },
                    "source": {
                        "type": "string",
                        "description": "Cell source (required for append/insert/replace).",
                    },
                    "cell_type": {
                        "type": "string",
                        "enum": ["code", "markdown"],
                        "description": "Cell type for new cells (default code).",
                    },
                },
                "required": ["path", "op"],
            },
        },
    },
]


def _render_output(output):
    if output.output_type == "stream":
        return output.get("text", "")
    if output.output_type in ("execute_result", "display_data"):
        data = output.get("data", {})
        if "text/plain" in data:
            return data["text/plain"]
        return "<%s>" % ", ".join(sorted(data))
    if output.output_type == "error":
        trace = _ANSI.sub("", "\n".join(output.get("traceback", [])))
        lines = trace.splitlines()
        if len(lines) > 12:
            trace = "\n".join(lines[:4] + ["..."] + lines[-7:])
        return "%s: %s\n%s" % (output.get("ename", "Error"), output.get("evalue", ""), trace)
    return "<%s>" % output.output_type


def read_notebook(path, include_outputs=True):
    import nbformat

    nb = nbformat.read(str(pathlib.Path(path).expanduser()), as_version=4)
    chunks = []
    for index, cell in enumerate(nb.cells):
        chunks.append("[cell %d: %s]\n%s" % (index, cell.cell_type, cell.source))
        if include_outputs and cell.cell_type == "code":
            for output in cell.get("outputs", []):
                text = _render_output(output).rstrip()
                if len(text) > MAX_CELL_OUTPUT_CHARS:
                    text = text[:MAX_CELL_OUTPUT_CHARS] + " …"
                if text:
                    chunks.append("  [output]\n%s" % text)
    body = "\n\n".join(chunks) or "(empty notebook)"
    if len(body) > MAX_OUTPUT_CHARS:
        body = body[:MAX_OUTPUT_CHARS] + "\n[output truncated; read cells individually]"
    return body


def edit_notebook(path, op, index=None, source=None, cell_type="code"):
    import nbformat

    target = pathlib.Path(path).expanduser()
    if target.exists():
        nb = nbformat.read(str(target), as_version=4)
    elif op == "append":
        nb = nbformat.v4.new_notebook()
    else:
        return "error: %s does not exist (op=append creates it)" % target

    if op in ("append", "insert", "replace") and source is None:
        return "error: op=%s requires source" % op
    if op in ("insert", "replace", "delete"):
        if index is None:
            return "error: op=%s requires index" % op
        if not 0 <= index < len(nb.cells) + (1 if op == "insert" else 0):
            return "error: index %d out of range (%d cells)" % (index, len(nb.cells))

    if op in ("append", "insert", "replace"):
        make = nbformat.v4.new_markdown_cell if cell_type == "markdown" else nbformat.v4.new_code_cell
        cell = make(source)
    if op == "append":
        nb.cells.append(cell)
    elif op == "insert":
        nb.cells.insert(index, cell)
    elif op == "replace":
        nb.cells[index] = cell
    elif op == "delete":
        del nb.cells[index]

    target.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, str(target))
    where = "" if op == "append" else " at cell %d" % (index or 0)
    return "%s%s in %s (%d cells now)" % (op, where, target, len(nb.cells))


HANDLERS = {"read_notebook": read_notebook, "edit_notebook": edit_notebook}
MUTATING = frozenset({"edit_notebook"})

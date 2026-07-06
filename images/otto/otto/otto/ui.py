"""Terminal presentation: theme, spinner, streamed markdown, tool traces.

Pure stdlib. Everything degrades automatically: without a TTY the output
is plain text (pipes stay machine-readable and get no traces or spinners),
and NO_COLOR keeps the layout but drops the color.

Layout of one agent turn:

    ❯ fix the failing test

    I'll look at the test first.

    ● bash python -m pytest -x
      ⎿ exit 1 · FAILED test_report.py::test_totals

    The bug is ...
"""

import os
import re
import shutil
import sys
import threading
import time

# One accent, used sparingly; everything else is default/dim/bold so the
# scheme follows the user's own terminal palette in light and dark themes.
ACCENT = "38;5;208"  # amber
BOLD = "1"
DIM = "2"
CODE = "36"  # inline `code`
ERR = "31"
WARN = "33"

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_ANSI = re.compile(r"\033\[[0-9;]*m")
_INLINE = re.compile(r"\*\*|`")
_HR = re.compile(r"(-{3,}|_{3,}|\*{3,})\s*$")
_NUMBERED = re.compile(r"(\d{1,3}[.)]) (.*)$")

# Argument keys shown (in this order) on a tool-call line.
_MAIN_ARGS = ("command", "pattern", "path", "src", "url", "dest", "op", "index")


def _width():
    return shutil.get_terminal_size((100, 24)).columns


def describe_call(name, arguments):
    """The one-line argument summary shown next to a tool name."""
    parts = [str(arguments[key]) for key in _MAIN_ARGS if key in arguments]
    if name == "write_file":
        parts.append("(%d bytes)" % len(arguments.get("content", "").encode()))
    if not parts:
        parts = ["%s=%r" % item for item in sorted(arguments.items())]
    return " ".join(parts).replace("\n", " ⏎ ")


def result_preview(name, result):
    """First meaningful line of a tool result, with a size hint."""
    lines = [line for line in result.splitlines() if line.strip()]
    if not lines:
        return "done", "dim"
    kind = "dim"
    head = lines[0]
    if result.startswith("error:"):
        kind = "err"
    elif name == "bash":
        code = re.search(r"\[exit code (\d+)\]\s*$", result)
        if code:
            kind = "err"
            head = "exit %s · %s" % (code.group(1), head)
        else:
            head = "exit 0 · %s" % head
    if len(head) > _width() - 8:
        head = head[: _width() - 9] + "…"
    if len(lines) > 1:
        head += " (+%d lines)" % (len(lines) - 1)
    return head, kind


class _Spinner(threading.Thread):
    """`⠋ thinking… 3s` on the current line until halted."""

    def __init__(self, view, label):
        super().__init__(daemon=True)
        self.view = view
        self.label = label
        self._halt = threading.Event()

    def run(self):
        start = time.time()
        frame = 0
        while not self._halt.wait(0.08):
            text = "\r\033[2K" + self.view.paint(
                ACCENT, SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]
            ) + self.view.paint(DIM, " %s… %ds" % (self.label, time.time() - start))
            self.view.out.write(text)
            self.view.out.flush()
            frame += 1
        self.view.out.write("\r\033[2K")
        self.view.out.flush()

    def halt(self):
        self._halt.set()
        self.join()


class UI:
    """All terminal output for the CLI goes through one of these."""

    def __init__(self, out=None, pretty=None):
        self.out = out or sys.stdout
        self.pretty = self.out.isatty() if pretty is None else pretty
        self.color = self.pretty and not os.environ.get("NO_COLOR")
        self.readline = False  # set by the CLI when readline is loaded
        self.libedit = False  # BSD libedit mishandles \001/\002 prompt guards
        self._spinner = None
        self._last = None  # "text" | "tool", for blank-line rhythm
        self._reset_stream()

    def _reset_stream(self):
        self._pending = ""
        self._mode = "start"  # start | prose | line
        self._line = ""
        self._in_code = False
        self._streamed = False
        self._mid_line = False

    # -- painting ----------------------------------------------------------

    def paint(self, code, text):
        if not self.color or not text:
            return text
        return "\033[%sm%s\033[0m" % (code, text)

    def prompt(self):
        """The REPL input prompt; escapes guarded when readline is active."""
        if self.libedit:
            return "\n❯ "
        text = self.paint(ACCENT, "❯") + " "
        if self.readline:
            text = _ANSI.sub(lambda m: "\001" + m.group(0) + "\002", text)
        return "\n" + text

    def _emit(self, text):
        self.unspin()
        self.out.write(text)
        self.out.flush()

    def _gap(self, kind):
        """One blank line between the prompt, text blocks, and tool blocks."""
        if self._last != kind:
            self._emit("\n")
        self._last = kind

    # -- spinner -----------------------------------------------------------

    def spin(self, label):
        if not self.pretty:
            return
        self.unspin()
        self._spinner = _Spinner(self, label)
        self._spinner.start()

    def unspin(self):
        spinner, self._spinner = self._spinner, None
        if spinner:
            spinner.halt()

    # -- one agent turn ------------------------------------------------------

    def begin_turn(self):
        self._last = None
        self._reset_stream()

    def stream_feed(self, text):
        """Model output as it arrives. Prose streams immediately; lines that
        start with a markdown marker are buffered to end-of-line and rendered
        whole; unterminated `code`/**bold** spans are held briefly."""
        self._streamed = True
        self._pending += text
        while self._pending:
            if self._mode == "line":
                cut = self._pending.find("\n")
                if cut < 0:
                    self._line += self._pending
                    self._pending = ""
                    break
                self._line += self._pending[:cut]
                self._pending = self._pending[cut + 1:]
                self._write_text(self._render_line(self._line) + "\n")
                self._line, self._mode = "", "start"
            elif self._mode == "start":
                first = self._pending[0]
                if self._in_code or first in "#-*>`|0123456789":
                    self._mode = "line"
                elif first == "\n":
                    self._write_text("\n")
                    self._pending = self._pending[1:]
                else:
                    self._mode = "prose"
            else:  # prose
                cut = self._pending.find("\n")
                if cut < 0:
                    emitted, self._pending = self._prose(self._pending, final=False)
                    if emitted:
                        self._write_text(emitted)
                    break
                emitted, _ = self._prose(self._pending[:cut], final=True)
                self._write_text(emitted + "\n")
                self._pending = self._pending[cut + 1:]
                self._mode = "start"

    def stream_close(self):
        """Flush the stream; True if this turn's text was already shown."""
        tail = self._line + self._pending
        if tail:
            if self._mode == "line":
                self._write_text(self._render_line(tail) + "\n")
            else:
                self._write_text(self._prose(tail, final=True)[0] + "\n")
        elif self._mid_line:
            self._emit("\n")
        streamed = self._streamed
        self._reset_stream()
        return streamed

    def say(self, text):
        """A complete message (non-streamed path), same rendering."""
        if not self.pretty:
            print("\n" + text if self._last else text)
            self._last = "text"
            return
        self.stream_feed(text.rstrip("\n") + "\n")
        self.stream_close()

    def _write_text(self, rendered):
        self._gap("text")
        self._emit(rendered)
        self._last = "text"
        self._mid_line = not rendered.endswith("\n")

    # -- markdown ------------------------------------------------------------

    def _render_line(self, line):
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        if stripped.startswith("```"):
            self._in_code = not self._in_code
            return self.paint(DIM, line)
        if self._in_code:
            return self.paint(DIM, "│ ") + line
        if re.match(r"#{1,6} ", stripped):
            return indent + self.paint(BOLD, stripped.lstrip("#").strip())
        if _HR.match(stripped):
            return self.paint(DIM, "─" * min(_width(), 40))
        if stripped.startswith("> "):
            return indent + self.paint(DIM, "▏ " + stripped[2:])
        if stripped[:2] in ("- ", "* "):
            return indent + self.paint(ACCENT, "•") + " " + self._prose(stripped[2:], final=True)[0]
        numbered = _NUMBERED.match(stripped)
        if numbered:
            return (
                indent
                + self.paint(ACCENT, numbered.group(1))
                + " "
                + self._prose(numbered.group(2), final=True)[0]
            )
        return self._prose(line, final=True)[0]

    def _prose(self, text, final):
        """Style `code` and **bold** spans; hold an unterminated span (and a
        trailing '*' that may become '**') until more text arrives."""
        if not final and text.endswith("*") and not text.endswith("**"):
            emitted, tail = self._prose(text[:-1], final=False)
            return emitted, tail + "*"
        out, pos = [], 0
        while pos < len(text):
            match = _INLINE.search(text, pos)
            if not match:
                break
            marker = match.group(0)
            close = text.find(marker, match.end())
            if close < 0:
                if not final and len(text) - match.start() < 160:
                    out.append(text[pos:match.start()])
                    return "".join(out), text[match.start():]
                break
            out.append(text[pos:match.start()])
            style = BOLD if marker == "**" else CODE
            out.append(self.paint(style, text[match.end():close]))
            pos = close + len(marker)
        out.append(text[pos:])
        return "".join(out), ""

    # -- tool traces -----------------------------------------------------------

    def tool_call(self, name, arguments):
        if not self.pretty:
            return
        self._gap("tool")
        summary = describe_call(name, arguments)
        room = _width() - len(name) - 4
        if len(summary) > room:
            summary = summary[: max(room - 1, 10)] + "…"
        self._emit(
            self.paint(ACCENT, "●") + " " + self.paint(BOLD, name)
            + (" " + self.paint(DIM, summary) if summary else "") + "\n"
        )
        self._last = "tool"

    def tool_result(self, name, arguments, result):
        if not self.pretty:
            return
        if result == "Denied by user.":
            head, kind = "denied", "warn"
        else:
            head, kind = result_preview(name, result)
        code = {"err": ERR, "warn": WARN}.get(kind, DIM)
        self._emit("  " + self.paint(DIM, "⎿") + " " + self.paint(code, head) + "\n")
        self._last = "tool"

    def confirm(self, name, detail):
        """Approval question for a mutating tool; True only on explicit yes."""
        self.unspin()
        if detail:
            for line in detail.splitlines():
                self.out.write("  " + self.paint(DIM, "│ " + line) + "\n")
        question = (
            "  " + self.paint(WARN, "⚠") + " "
            + self.paint(BOLD, "allow %s? " % name) + self.paint(DIM, "[y/N] ")
        )
        if self.readline:
            question = _ANSI.sub(lambda m: "\001" + m.group(0) + "\002", question)
        try:
            answer = input(question)
        except EOFError:
            return False
        return answer.strip().lower() in ("y", "yes")

    # -- chrome ------------------------------------------------------------------

    def banner(self, version, model_line, cwd):
        if not self.pretty:
            return
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        self._emit(
            self.paint(ACCENT, "✳ ") + self.paint(BOLD, "otto") + " "
            + self.paint(DIM, "v" + version) + "\n"
            + "  " + self.paint(DIM, model_line) + "\n"
            + "  " + self.paint(DIM, cwd + " · /help for commands · ctrl-d to exit")
            + "\n"
        )

    def note(self, text):
        self._emit(self.paint(DIM, text) + "\n")

    def error(self, text):
        self.unspin()
        print(self.paint(ERR, "otto: %s" % text) if self.color else "otto: %s" % text,
              file=sys.stderr)

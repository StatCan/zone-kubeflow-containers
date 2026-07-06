"""Command line interface: interactive REPL, one-shot prompts, sessions.

All presentation goes through otto.ui: on a terminal the model's answer
streams live with markdown styling and every tool call is traced; piped
output stays plain (the final answer only), so `... | otto "..."` and
`otto "..." > file` remain machine-friendly.
"""

import argparse
import os
import sys

from otto import __version__, agent, config, session, ui


def _approval_detail(name, arguments):
    """What the user is approving, shown above the [y/N] question."""
    if name == "edit_file":
        return "--- old ---\n%s\n--- new ---\n%s" % (
            arguments.get("old_string", ""),
            arguments.get("new_string", ""),
        )
    if name == "write_file":
        lines = arguments.get("content", "").splitlines()
        head = "\n".join(lines[:20])
        if len(lines) > 20:
            head += "\n... (%d more lines)" % (len(lines) - 20)
        return head
    return ""


def _make_approver(auto_yes, view):
    def approve(name, arguments):
        if auto_yes:
            return True
        if not sys.stdin.isatty():
            return False
        return view.confirm(name, _approval_detail(name, arguments))

    return approve


COMMANDS = (
    ("/help", "show this help"),
    ("/cost", "tokens used this session"),
    ("/compact", "summarize the conversation now to free context"),
    ("exit", "quit (ctrl-d works too)"),
)


def _show_help(view):
    for name, blurb in COMMANDS:
        view.note("  %s  %s" % (view.paint(ui.ACCENT, "%-8s" % name), blurb))


def _finish_turn(bot, view, reply):
    """Render whatever the stream did not already show, then compact."""
    streamed = view.stream_close()
    if reply == "[interrupted]":
        view.note("— interrupted")
    elif reply and not streamed:
        view.say(reply)
    view.spin("compacting")
    compacted = bot.maybe_compact()
    view.unspin()
    if compacted:
        view.note("✦ context compacted")


def _repl(bot, view):
    name_part = bot.deployment
    if bot.model_config.name not in (bot.deployment, "environment"):
        name_part += " (%s)" % bot.model_config.name
    view.banner(
        __version__,
        "%s · %s · session %s"
        % (name_part, bot.model_config.auth, bot.session_id),
        os.getcwd(),
    )
    while True:
        try:
            text = input(view.prompt())
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            view.note("(use ctrl-d or 'exit' to quit)")
            continue
        text = text.strip()
        if not text:
            continue
        if text in ("exit", "quit"):
            break
        if text == "/help":
            _show_help(view)
            continue
        if text == "/cost":
            view.note("~{:,} tokens used this session".format(bot.total_tokens))
            continue
        if text == "/compact":
            view.spin("compacting")
            compacted = bot.maybe_compact(force=True)
            view.unspin()
            view.note("✦ context compacted" if compacted else "nothing to compact")
            continue
        view.begin_turn()
        view.spin("thinking")
        try:
            reply = bot.run_turn(text)
        except agent.AgentError as error:
            view.unspin()
            view.stream_close()
            view.error(str(error))
            continue
        finally:
            view.unspin()
        _finish_turn(bot, view, reply)
    view.note(
        "session %s saved · ~%s tokens used"
        % (bot.session_id, format(bot.total_tokens, ","))
    )
    return 0


def _read_piped_stdin():
    """Piped input, without ever blocking on an idle inherited pipe.

    A parent process can hand otto an open-but-silent stdin; a plain read()
    would hang forever. Only read when data (or EOF) is already waiting.
    """
    try:
        import select

        ready, _, _ = select.select([sys.stdin], [], [], 0.5)
        if not ready:
            return ""
        return sys.stdin.read(102400).strip()
    except (OSError, ValueError):
        return ""


def main(argv=None):
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(
        prog="otto",
        description=(
            "A coding agent for Zone notebooks. Uses your own identity via "
            "the token broker (Azure OpenAI, no API keys); sessions persist "
            "under ~/.otto."
        ),
    )
    parser.add_argument("prompt", nargs="*", help="one-shot prompt; omit for interactive mode")
    parser.add_argument(
        "-r", "--resume", nargs="?", const="latest", metavar="ID",
        help="resume a session (default: the most recent one)",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="run write/edit/bash tools without asking (required for piped use)",
    )
    parser.add_argument(
        "-m", "--model",
        help="configured model profile (see --list-models; default: platform default)",
    )
    parser.add_argument(
        "--deployment",
        help="override the deployment name (default: the model profile's, or $%s)"
        % config.DEPLOYMENT_ENV,
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="list model profiles from the platform and user config and exit",
    )
    parser.add_argument(
        "--doctor", action="store_true",
        help="check config, auth, and connectivity for the selected model and exit",
    )
    parser.add_argument("--sessions", action="store_true", help="list saved sessions and exit")
    parser.add_argument("--version", action="version", version="otto " + __version__)
    args = parser.parse_args(argv)

    if args.sessions:
        rows = session.listing()
        if not rows:
            print("No sessions yet.")
        for session_id, count, first in rows:
            print("%s  %3d messages  %s" % (session_id, count, first))
        return 0

    if args.list_models:
        rows = config.listing()
        if not rows:
            print(
                "No model profiles configured (%s, %s); the environment "
                "fallback ($%s + $%s) applies."
                % (config.PLATFORM_CONFIG, config.USER_CONFIG,
                   config.ENDPOINT_ENV, config.DEPLOYMENT_ENV)
            )
        for name, provider, deployment_name, is_default in rows:
            marker = "*" if is_default else " "
            print("%s %-24s %-14s %s" % (marker, name, provider, deployment_name))
        return 0

    view = ui.UI()

    try:
        model_config = config.resolve(model=args.model, deployment=args.deployment)
    except config.ConfigError as error:
        view.error(str(error))
        return 2

    if args.doctor:
        return config.doctor(model_config, sys.stdout)

    prompt_text = " ".join(args.prompt) if args.prompt else None
    if not sys.stdin.isatty():
        piped = _read_piped_stdin()
        if prompt_text and piped:
            prompt_text += "\n\n[piped input]\n" + piped
        elif piped:
            prompt_text = piped
        if not prompt_text:
            view.error("no prompt given and stdin is not a terminal")
            return 2
    elif not prompt_text:
        try:
            import readline  # noqa: F401  (line editing + history in input())

            view.readline = True
            view.libedit = "libedit" in (getattr(readline, "__doc__", None) or "")
        except ImportError:
            pass

    if args.resume:
        session_id = session.latest() if args.resume == "latest" else args.resume
        if session_id is None:
            view.error("no sessions to resume")
            return 2
        try:
            messages = session.load(session_id)
        except FileNotFoundError as error:
            view.error(str(error))
            return 2
    else:
        session_id, messages = session.new_id(), []

    def on_tool_result(name, arguments, result):
        view.tool_result(name, arguments, result)
        view.spin("working")

    bot = agent.Agent(
        model_config=model_config,
        session_id=session_id,
        messages=messages,
        approve=_make_approver(args.yes, view),
        on_tool=view.tool_call,
        on_tool_result=on_tool_result,
        on_delta=view.stream_feed if view.pretty else None,
        on_text=None if view.pretty else (lambda text: print("\n" + text)),
    )

    try:
        if prompt_text:
            view.begin_turn()
            view.spin("thinking")
            try:
                reply = bot.run_turn(prompt_text)
            finally:
                view.unspin()
            if view.pretty:
                _finish_turn(bot, view, reply)
            else:
                print(reply)
                bot.maybe_compact()
            return 0
        return _repl(bot, view)
    except agent.AgentError as error:
        view.unspin()
        view.error(str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())

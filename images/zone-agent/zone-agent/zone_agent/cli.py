"""Command line interface: interactive REPL, one-shot prompts, sessions."""

import argparse
import os
import sys

from zone_agent import __version__, agent, session

DEPLOYMENT_ENV = "ZONE_AGENT_DEPLOYMENT"


def _color(code, text):
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return "\033[%sm%s\033[0m" % (code, text)


def _dim(text):
    return _color("2", text)


def _bold(text):
    return _color("1", text)


def _preview(name, arguments):
    """One line describing a tool call, for the activity trace."""
    if name == "bash":
        return "bash: %s" % arguments.get("command", "")
    if name == "write_file":
        content = arguments.get("content", "")
        return "write_file: %s (%d bytes)" % (arguments.get("path", ""), len(content.encode()))
    if name == "edit_file":
        return "edit_file: %s" % arguments.get("path", "")
    shown = ", ".join("%s=%r" % item for item in sorted(arguments.items()))
    return "%s(%s)" % (name, shown)


def _approval_detail(name, arguments):
    """What the user is approving, shown under the [y/N] question."""
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


def _make_approver(auto_yes):
    def approve(name, arguments):
        if auto_yes:
            return True
        if not sys.stdin.isatty():
            return False
        detail = _approval_detail(name, arguments)
        if detail:
            print(_dim("    " + detail.replace("\n", "\n    ")))
        try:
            answer = input(_bold("    approve? [y/N] "))
        except EOFError:
            return False
        return answer.strip().lower() in ("y", "yes")

    return approve


def _repl(bot):
    print(
        _bold("zone-agent %s" % __version__)
        + _dim("  session %s · deployment %s" % (bot.session_id, bot.deployment))
    )
    print(_dim("Working in %s. Type a request, or 'exit' to quit." % os.getcwd()))
    while True:
        try:
            text = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        text = text.strip()
        if not text:
            continue
        if text in ("exit", "quit"):
            break
        try:
            reply = bot.run_turn(text)
        except agent.AgentError as error:
            print("zone-agent: %s" % error, file=sys.stderr)
            continue
        print("\n" + reply)
        if bot.maybe_compact():
            print(_dim("[context compacted]"))
    print(_dim("session %s saved · ~%d tokens used" % (bot.session_id, bot.total_tokens)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="zone-agent",
        description=(
            "A coding agent for Zone notebooks. Uses your own identity via "
            "the token broker (Azure OpenAI, no API keys); sessions persist "
            "under ~/.zone-agent."
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
        "--deployment",
        help="Azure OpenAI deployment name (default: $%s)" % DEPLOYMENT_ENV,
    )
    parser.add_argument("--sessions", action="store_true", help="list saved sessions and exit")
    parser.add_argument("--version", action="version", version="zone-agent " + __version__)
    args = parser.parse_args(argv)

    if args.sessions:
        rows = session.listing()
        if not rows:
            print("No sessions yet.")
        for session_id, count, first in rows:
            print("%s  %3d messages  %s" % (session_id, count, first))
        return 0

    deployment = args.deployment or os.environ.get(DEPLOYMENT_ENV)
    if not deployment:
        print(
            "Set %s or pass --deployment (the Azure OpenAI deployment name)." % DEPLOYMENT_ENV,
            file=sys.stderr,
        )
        return 2

    if args.resume:
        session_id = session.latest() if args.resume == "latest" else args.resume
        if session_id is None:
            print("No sessions to resume.", file=sys.stderr)
            return 2
        try:
            messages = session.load(session_id)
        except FileNotFoundError as error:
            print(error, file=sys.stderr)
            return 2
    else:
        session_id, messages = session.new_id(), []

    bot = agent.Agent(
        deployment=deployment,
        session_id=session_id,
        messages=messages,
        approve=_make_approver(args.yes),
        on_tool=lambda name, arguments: print(_dim("  · " + _preview(name, arguments))),
        on_text=lambda text: print("\n" + text),
    )

    try:
        if args.prompt:
            print(bot.run_turn(" ".join(args.prompt)))
            bot.maybe_compact()
            return 0
        return _repl(bot)
    except agent.AgentError as error:
        print("zone-agent: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

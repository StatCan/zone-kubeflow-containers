"""Command line interface: interactive REPL, one-shot prompts, sessions."""

import argparse
import os
import sys

from zone_agent import __version__, agent, config, session


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
        + _dim(
            "  session %s · %s · %s"
            % (bot.session_id, bot.model_config.name, bot.deployment)
        )
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
    parser.add_argument("--version", action="version", version="zone-agent " + __version__)
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

    try:
        model_config = config.resolve(model=args.model, deployment=args.deployment)
    except config.ConfigError as error:
        print("zone-agent: %s" % error, file=sys.stderr)
        return 2

    if args.doctor:
        return config.doctor(model_config, sys.stdout)

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
        model_config=model_config,
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

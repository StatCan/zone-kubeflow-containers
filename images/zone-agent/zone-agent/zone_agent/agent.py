"""The agent loop: Azure OpenAI tool calling against local tools.

Auth comes from zone_openai (AuthService token broker on-platform, with
its usual local-development fallbacks), so no API keys are handled here.
"""

import json
import os

from zone_agent import prompt, session, tools

DEFAULT_CONTEXT_BUDGET = 120000  # prompt tokens allowed before compaction
MAX_STEPS = 40  # model/tool rounds per user turn

COMPACT_PROMPT = (
    "Summarize this conversation so it can continue in a fresh context. "
    "Keep: the user's goal and constraints, what has been done so far, key "
    "file paths and their relevant contents, decisions made, and what "
    "remains. Reply with only the summary."
)


class AgentError(RuntimeError):
    """Raised when the model cannot be reached or configured."""


def _context_budget():
    try:
        return int(os.environ.get("ZONE_AGENT_CONTEXT_BUDGET", DEFAULT_CONTEXT_BUDGET))
    except ValueError:
        return DEFAULT_CONTEXT_BUDGET


class Agent:
    """One conversation bound to a session file.

    The CLI owns all interaction: `approve(name, arguments)` is consulted
    before any mutating tool runs, `on_tool(name, arguments)` fires before
    each tool call, and `on_text(text)` receives assistant narration that
    accompanies tool calls.
    """

    def __init__(self, deployment, session_id, messages, approve, on_tool=None, on_text=None):
        self.deployment = deployment
        self.session_id = session_id
        self.messages = messages
        self.approve = approve
        self.on_tool = on_tool or (lambda name, arguments: None)
        self.on_text = on_text or (lambda text: None)
        self.total_tokens = 0
        self._prompt_tokens = 0
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import zone_openai
            except ImportError as error:
                raise AgentError(
                    "zone_openai is required (ships with the zone-token-broker package)"
                ) from error
            try:
                self._client = zone_openai.client()
            except Exception as error:
                raise AgentError(str(error)) from error
        return self._client

    def _create(self, messages, use_tools=True):
        options = {
            "model": self.deployment,
            "messages": [{"role": "system", "content": prompt.SYSTEM}] + messages,
        }
        if use_tools:
            options["tools"] = tools.DEFINITIONS
        effort = os.environ.get("ZONE_AGENT_REASONING", "low")
        if effort and effort != "none":
            options["reasoning_effort"] = effort
        try:
            response = self._get_client().chat.completions.create(**options)
        except AgentError:
            raise
        except Exception as error:
            raise AgentError("model call failed: %s" % error) from error
        usage = getattr(response, "usage", None)
        if usage:
            self.total_tokens += usage.total_tokens or 0
            self._prompt_tokens = usage.prompt_tokens or 0
        return response.choices[0].message

    def _record(self, message):
        self.messages.append(message)
        session.append(self.session_id, message)

    def run_turn(self, user_text):
        """Process one user message and return the assistant's final text."""
        try:
            return self._loop(user_text)
        except KeyboardInterrupt:
            self._heal()
            return "[interrupted]"

    def _loop(self, user_text):
        self._record({"role": "user", "content": user_text})
        for _ in range(MAX_STEPS):
            reply = self._create(self.messages)
            entry = {"role": "assistant", "content": reply.content or ""}
            if reply.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in reply.tool_calls
                ]
            self._record(entry)
            if not reply.tool_calls:
                return reply.content or ""
            if reply.content:
                self.on_text(reply.content)
            for call in reply.tool_calls:
                self._record(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": self._run_tool(call),
                    }
                )
        notice = (
            "Stopped after %d tool rounds without finishing; say 'continue' "
            "to keep going." % MAX_STEPS
        )
        self._record({"role": "assistant", "content": notice})
        return notice

    def _run_tool(self, call):
        name = call.function.name
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except ValueError:
            return "error: tool arguments were not valid JSON"
        if not isinstance(arguments, dict):
            return "error: tool arguments must be a JSON object"
        self.on_tool(name, arguments)
        if name in tools.MUTATING and not self.approve(name, arguments):
            return "Denied by user."
        return tools.run(name, arguments)

    def _heal(self):
        """Backfill tool results if an interrupt landed mid-round.

        The API rejects a history where an assistant tool_calls message is
        not followed by a result for every call, so answer the unanswered
        ones before the next request.
        """
        pending, answered = [], set()
        for message in reversed(self.messages):
            if message.get("role") == "tool":
                answered.add(message.get("tool_call_id"))
            elif message.get("role") == "assistant":
                pending = message.get("tool_calls") or []
                break
            else:
                break
        for call in pending:
            if call["id"] not in answered:
                self._record(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": "error: interrupted by user",
                    }
                )

    def maybe_compact(self):
        """Between turns: summarize the history once it outgrows the budget.

        Returns True when the session was compacted. Token counts come from
        the API's own usage figures, so a resumed session compacts after its
        first response if it is already over budget.
        """
        if self._prompt_tokens <= _context_budget():
            return False
        reply = self._create(
            self.messages + [{"role": "user", "content": COMPACT_PROMPT}],
            use_tools=False,
        )
        summary = (reply.content or "").strip()
        if not summary:
            return False
        self.messages[:] = [
            {
                "role": "user",
                "content": "[Earlier conversation was compacted. Summary:]\n" + summary,
            }
        ]
        session.rewrite(self.session_id, self.messages)
        self._prompt_tokens = 0
        return True

"""The agent loop: Azure OpenAI tool calling against local tools.

Auth comes from zone_openai (AuthService token broker on-platform, with
its usual local-development fallbacks), so no API keys are handled here.
"""

import json
import os
import types

from otto import prompt, session, tools

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


def _project_instructions():
    """AGENTS.md in the launch directory, if the project provides one."""
    try:
        with open("AGENTS.md") as handle:
            return handle.read(8000).strip()
    except OSError:
        return ""


def _context_budget():
    try:
        return int(os.environ.get("OTTO_CONTEXT_BUDGET", DEFAULT_CONTEXT_BUDGET))
    except ValueError:
        return DEFAULT_CONTEXT_BUDGET


class Agent:
    """One conversation bound to a session file.

    The CLI owns all interaction: `approve(name, arguments)` is consulted
    before any mutating tool runs, `on_tool(name, arguments)` fires before
    each tool call, `on_tool_result(name, arguments, result)` fires after
    it, and `on_delta(text)` streams assistant text as it is generated.
    Without `on_delta`, responses are fetched whole and `on_text(text)`
    receives the narration that accompanies tool calls.
    """

    def __init__(self, model_config, session_id, messages, approve,
                 on_tool=None, on_text=None, on_delta=None, on_tool_result=None):
        self.model_config = model_config
        self.deployment = model_config.deployment
        self.session_id = session_id
        self.messages = messages
        self.approve = approve
        self.on_tool = on_tool or (lambda name, arguments: None)
        self.on_text = on_text or (lambda text: None)
        self.on_delta = on_delta
        self.on_tool_result = on_tool_result or (lambda name, arguments, result: None)
        self._system = prompt.SYSTEM
        extra = _project_instructions()
        if extra:
            self._system += "\n\nProject instructions (from AGENTS.md):\n" + extra
        self.total_tokens = 0
        self._prompt_tokens = 0
        self._client = None

    def _get_client(self):
        if self._client is None:
            from otto import config

            try:
                self._client = config.build_client(self.model_config)
            except Exception as error:
                raise AgentError(str(error)) from error
        return self._client

    def _create(self, messages, use_tools=True, stream=False):
        options = {
            "model": self.deployment,
            "messages": [{"role": "system", "content": self._system}] + messages,
        }
        if use_tools:
            options["tools"] = tools.DEFINITIONS
        effort = os.environ.get(
            "OTTO_REASONING", self.model_config.reasoning or "low"
        )
        if effort and effort != "none":
            options["reasoning_effort"] = effort
        try:
            if stream and self.on_delta is not None:
                return self._consume_stream(options)
            response = self._get_client().chat.completions.create(**options)
        except AgentError:
            raise
        except Exception as error:
            raise AgentError("model call failed: %s" % error) from error
        self._count(getattr(response, "usage", None), options["messages"])
        return response.choices[0].message

    def _count(self, usage, sent_messages):
        """Track tokens from API usage, estimating when a stream omits it
        (compaction and /cost must keep working on any provider)."""
        if usage and usage.total_tokens:
            self.total_tokens += usage.total_tokens
            self._prompt_tokens = usage.prompt_tokens or 0
        else:
            self._prompt_tokens = sum(
                len(json.dumps(m, default=str)) for m in sent_messages
            ) // 4
            self.total_tokens += self._prompt_tokens

    def _consume_stream(self, options):
        """Stream one completion, forwarding text deltas to `on_delta` and
        assembling tool calls from their argument fragments."""
        client = self._get_client()
        try:
            events = client.chat.completions.create(
                stream=True, stream_options={"include_usage": True}, **options
            )
        except Exception:
            # Some providers reject stream_options; one retry without it.
            events = client.chat.completions.create(stream=True, **options)
        content, calls, usage = [], {}, None
        for chunk in events:
            usage = getattr(chunk, "usage", None) or usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.content:
                content.append(delta.content)
                self.on_delta(delta.content)
            for call in delta.tool_calls or []:
                slot = calls.setdefault(
                    call.index, {"id": "", "name": "", "arguments": ""}
                )
                if call.id:
                    slot["id"] = call.id
                if call.function and call.function.name:
                    slot["name"] = call.function.name
                if call.function and call.function.arguments:
                    slot["arguments"] += call.function.arguments
        self._count(usage, options["messages"])
        tool_calls = [
            types.SimpleNamespace(
                id=slot["id"],
                function=types.SimpleNamespace(
                    name=slot["name"], arguments=slot["arguments"]
                ),
            )
            for _, slot in sorted(calls.items())
        ]
        return types.SimpleNamespace(
            content="".join(content), tool_calls=tool_calls or None
        )

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
            reply = self._create(self.messages, stream=True)
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
            if reply.content and self.on_delta is None:
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
            result = "Denied by user."
        else:
            result = tools.run(name, arguments)
        self.on_tool_result(name, arguments, result)
        return result

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

    def maybe_compact(self, force=False):
        """Between turns: summarize the history once it outgrows the budget.

        Returns True when the session was compacted. Token counts come from
        the API's own usage figures, so a resumed session compacts after its
        first response if it is already over budget. `force` compacts
        regardless of the budget (the /compact command).
        """
        if not self.messages:
            return False
        if not force and self._prompt_tokens <= _context_budget():
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

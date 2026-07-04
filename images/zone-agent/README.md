# Zone Agent

The `zone-agent` image is the [mid](../mid) image plus **`zone-agent`**, a
minimal coding agent CLI for the notebook terminal. It reads and edits the
files in your workspace, searches them, and runs commands — with your
approval — the way desktop coding agents do, but entirely inside your Zone
notebook and entirely on your own identity.

```
$ zone-agent
zone-agent 0.1.0  session 20260704-101500 · deployment gpt-5-mini
Working in /home/jovyan/my-project. Type a request, or 'exit' to quit.

> add a --dry-run flag to clean.py and show me the diff
  · read_file: clean.py
  · edit_file: clean.py
    approve? [y/N] y
  · bash: git diff clean.py
...
```

## How it authenticates

There are **no API keys anywhere**. The CLI builds its Azure OpenAI client
with [`zone_openai`](../mid/zone-token-broker/zone_openai.py), which gets a
delegated Entra ID token for the signed-in user from the in-cluster
AuthService token broker (scope `https://cognitiveservices.azure.com/.default`).
Calls to Azure OpenAI are made as the user, in the Zone tenant, subject to
the user's own RBAC. Outside the cluster it falls back to `az login`
credentials, so the CLI also works on a laptop for development.

## Usage

| Command | Effect |
| --- | --- |
| `zone-agent` | interactive session in the current directory |
| `zone-agent "explain tests/conftest.py"` | one-shot prompt, prints the answer and exits |
| `zone-agent -r` | resume the most recent session |
| `zone-agent -r ID` | resume a specific session |
| `zone-agent --sessions` | list saved sessions |
| `zone-agent -y ...` | skip approval prompts (scripting; use with care) |

Configuration (environment variables):

| Variable | Meaning |
| --- | --- |
| `AZURE_OPENAI_ENDPOINT` | the Azure OpenAI resource endpoint (required) |
| `ZONE_AGENT_DEPLOYMENT` | deployment (model) name, e.g. `gpt-5-mini` (required, or `--deployment`) |
| `AZURE_OPENAI_API_VERSION` | API version override (defaults to `zone_openai`'s) |
| `ZONE_AGENT_REASONING` | reasoning effort: `minimal`/`low`/`medium`/`high`, `none` omits (default `low`) |
| `ZONE_AGENT_CONTEXT_BUDGET` | prompt tokens before auto-compaction (default 120000) |
| `ZONE_AGENT_HOME` | state directory (default `~/.zone-agent`) |

## Safeguards

- **Read-only by default**: `read_file`, `list_dir` and `grep` run freely;
  `write_file`, `edit_file` and `bash` each require a `[y/N]` approval with
  a preview of the change. Non-interactive runs deny mutations unless `-y`.
- **User-scoped**: the agent holds no identity of its own; every model call
  uses the user's delegated token and every file/command action runs as the
  user inside their pod, under the pod's existing network policy.
- **Bounded**: tool output is truncated (16 KB per result), turns are capped
  at 40 tool rounds, and sessions auto-compact (the model summarizes older
  history) once the context passes the budget — memory does not grow
  unbounded.
- **Prompt-injection aware**: the system prompt instructs the agent to treat
  file contents and command output as data, never as instructions, and to
  surface any embedded instructions to the user.

## Sessions

Sessions are JSONL transcripts under `~/.zone-agent/sessions/` — the home
directory is a persistent volume, so they survive notebook restarts and
image upgrades and stay inside the user's own storage.

## Working with worktrees

The agent knows the `git worktree` workflow: ask it to try a risky change
and it will isolate the work on a branch in a separate worktree, verify it
there, and merge back only when you are happy.

## Development

The package lives in [`zone-agent/`](zone-agent/) (pure Python, stdlib +
`openai` only). A wheel is left in `/opt/zone-agent/dist` in the image for
user-created venvs. To adopt the agent in another image, copy the
`COPY`/`RUN` block from the [Dockerfile](Dockerfile) — it is deliberately
self-contained.

Tests: `make bake/zone-agent && make test/zone-agent` (static checks only —
no model calls, so no Azure resources are needed).

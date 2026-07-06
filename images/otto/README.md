# Otto

The `otto` image is the [mid](../mid) image plus **Otto** (`otto`), the
Zone coding agent for the notebook terminal. He reads and edits the files
in your workspace, searches them, works inside Jupyter notebooks (cells,
outputs, and error tracebacks), moves data to and from Azure Storage /
OneLake, and runs commands — with your approval — the way desktop coding
agents do, but entirely inside your Zone notebook and entirely on your own
identity.

```
$ otto
otto 0.3.0  session 20260704-101500 · gpt-5-mini
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

## Connecting a model

Model access is configured through **profiles** — named entries describing a
provider (`azure-openai`, `foundry`, or `foundry-models` for non-OpenAI
catalogue models), an endpoint, a deployment, and an auth mode (`broker` for
delegated per-user Entra tokens — the default, no secrets — or `api-key`
from an environment variable). Profiles merge from three layers, later wins:

1. `/etc/otto/config.toml` — the platform catalogue (in prod, a
   ConfigMap injected by a PodDefault; stubs in [`deploy/`](deploy/))
2. `~/.otto/config.toml` — your own profiles and default
3. environment variables — the zero-config path below still works as-is

```bash
otto --list-models        # what is configured, * marks the default
otto --model gpt-5        # pick a profile for this run
otto --doctor             # config → auth → one real model call
```

To point the agent at a resource yourself with no config file (or on a
laptop), copy the values from the resource's *Keys and Endpoint* page:

```bash
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
export OTTO_DEPLOYMENT="gpt-5-mini"     # your deployment name
# Entra ID (recommended): nothing else to set — broker on Zone, az login locally.
# Key-based:              export AZURE_OPENAI_API_KEY="<key from the same page>"
```

Production rollout — provisioning, RBAC, networking, and the flagged
assumptions for the platform team — is documented in
[`docs/otto-prod.md`](../../docs/otto-prod.md).

## Usage

| Command | Effect |
| --- | --- |
| `otto` | interactive session in the current directory |
| `otto "explain tests/conftest.py"` | one-shot prompt, prints the answer and exits |
| `otto -r` | resume the most recent session |
| `otto -r ID` | resume a specific session |
| `otto --sessions` | list saved sessions |
| `otto -y ...` | skip approval prompts (scripting; use with care) |
| `cat error.log \| otto "why?"` | piped input becomes context (or the whole prompt) |
| `/help` `/compact` `/cost` | inside the REPL: help, compact now, token usage |

On a terminal, answers stream live with markdown styling and every tool
call is traced (`●` call, `⎿` result) so you can watch what he does;
approvals appear inline. Piped or redirected output is plain text with the
final answer only, so `otto "..." > notes.md` and pipelines stay clean.
`NO_COLOR=1` keeps the layout but drops the color.

Configuration (environment variables):

| Variable | Meaning |
| --- | --- |
| `AZURE_OPENAI_ENDPOINT` | the Azure OpenAI resource endpoint (required) |
| `OTTO_DEPLOYMENT` | deployment (model) name, e.g. `gpt-5-mini` (required, or `--deployment`) |
| `AZURE_OPENAI_API_KEY` | optional API key; overrides Entra ID auth when set |
| `AZURE_OPENAI_API_VERSION` | API version override (defaults to `zone_openai`'s) |
| `OTTO_REASONING` | reasoning effort: `minimal`/`low`/`medium`/`high`, `none` omits (default `low`) |
| `OTTO_CONTEXT_BUDGET` | prompt tokens before auto-compaction (default 120000) |
| `OTTO_HOME` | state directory (default `~/.otto`) |

## Safeguards

- **Read-only by default**: `read_file`, `list_dir`, `grep`, `read_notebook`
  and `azure_ls` run freely; `write_file`, `edit_file`, `edit_notebook`,
  `bash`, `azure_download` and `azure_upload` each require a `[y/N]`
  approval with a preview. Non-interactive runs deny mutations unless `-y`.
  The only network-capable tools are the Azure Storage ones — approval-gated
  and running as the signed-in user, in-tenant.
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

Sessions are JSONL transcripts under `~/.otto/sessions/` — the home
directory is a persistent volume, so they survive notebook restarts and
image upgrades and stay inside the user's own storage.

## Notebooks and OneLake

Otto is notebook-native: `read_notebook` renders cells with outputs and
error tracebacks (ask him "why did cell 7 fail?"), `edit_notebook` writes
whole cells, and he runs notebooks through `jupyter execute --inplace`.
For data, `azure_ls` / `azure_download` / `azure_upload` take the full
`az://` or `abfss://` URLs you copy from the portal or Fabric — including
OneLake (`abfss://<workspace>@onelake.dfs.fabric.microsoft.com/...`) — so
"bring that OneLake file here, fix it, push it back" is one conversation.

Drop an `AGENTS.md` in your project root and Otto reads it as project
instructions at the start of every session.

## Working with worktrees

The agent knows the `git worktree` workflow: ask it to try a risky change
and it will isolate the work on a branch in a separate worktree, verify it
there, and merge back only when you are happy.

## Development

The package lives in [`otto/`](otto/) (pure Python; its only install
dependency is `openai` — the notebook and storage tools lazily use the
image's `nbformat` and `adlfs` when invoked). A wheel is left in `/opt/otto/dist` in the image for
user-created venvs. To adopt the agent in another image, copy the
`COPY`/`RUN` block from the [Dockerfile](Dockerfile) — it is deliberately
self-contained.

Tests: `make bake/otto && make test/otto` (static checks only —
no model calls, so no Azure resources are needed).

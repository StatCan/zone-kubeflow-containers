# OneLake Simplified Architecture Agent Brief

Date: 2026-05-22

This repo should stay small: one user-facing product named `onelake`, one
internal token broker client, one JupyterLab drive, one Python API, one R API,
and one CLI for scripts.

Do not add a second auth product, a Linux mount, manual bearer-token paths, or a
large framework.

## North Star

Users should be able to:

- browse OneLake from the JupyterLab `OneLake` drive;
- run `onelake` commands;
- `import onelake` in Python;
- call `ol_*` wrappers in R;
- use the signed-in user's delegated permissions;
- read, write, upload, download, and save files without learning Microsoft auth
  internals.

Everything goes through the same small Python client.

## Architecture

```text
JupyterLab OneLake drive
Python import onelake
R library(onelake)
CLI onelake
        |
        v
images/onelake/onelake.py
        |
        v
images/onelake/zone_token_broker.py
        |
        v
AuthService getPassthroughToken
        |
        v
Azure Data Lake SDK
        |
        v
OneLake DFS endpoint
```

The real token exchange belongs to AuthService. This repo only calls:

```http
GET /authservice/getPassthroughToken?scope=https://storage.azure.com/.default
```

AuthService returns a delegated user access token as raw text. The notebook
image keeps it in memory and passes it to the Azure Data Lake SDK. The notebook
persists only workspace/lakehouse config; after restart, the next command asks
AuthService for a fresh delegated token.

## Non-Goals

Do not implement:

- FUSE, BlobFuse2, `/dev/fuse`, privileged containers, or `SYS_ADMIN`.
- A real POSIX path such as `~/onelake`.
- Device-code auth or Azure CLI login.
- User-facing token commands or token packages.
- Manual bearer-token env vars or stdin token hooks.
- Service-principal or managed-identity data access for user files.
- Append, shortcut management, cron scheduling, or Delta transaction logic.
- Broad filesystem behavior such as locks, recursive delete, or atomic rename.

## Public Surface

CLI:

```bash
onelake status [--live]
onelake connect <workspace> <lakehouse>
onelake ls [path]
onelake cat <path>
onelake write <path>
onelake get <remote-path> <local-path>
onelake put <local-path> <remote-path>
```

Python:

```python
import onelake

onelake.connect("MyWorkspace", "MyLakehouse")
onelake.ls("/")
onelake.read("Files/raw/input.csv", text=True)
onelake.write("Files/processed/output.txt", "done\n")
onelake.download("Files/raw/input.csv", "/tmp/input.csv")
onelake.upload("/tmp/output.csv", "Files/processed/output.csv")
```

R:

```r
library(onelake)

ol_connect("MyWorkspace", "MyLakehouse")
ol_ls("/")
ol_read_text("Files/raw/input.csv")
ol_write_text("Files/processed/output.txt", "done\n")
ol_download("Files/raw/input.csv", "/tmp/input.csv")
ol_upload("/tmp/output.csv", "Files/processed/output.csv")
```

R wrappers shell out to the CLI. They do not duplicate token logic.

## Path Model

The user-facing root is synthetic:

```text
OneLake/
  Files/
  Tables/
```

With multiple configured workspace/lakehouse pairs, the same JupyterLab drive
generates workspace and lakehouse folders:

```text
OneLake/
  WorkspaceA/
    LakeA/
      Files/
      Tables/
  WorkspaceB/
    LakeB/
      Files/
      Tables/
```

Rules:

- `/` lists `Files` and `Tables`.
- `Files/...` maps to the lakehouse `Files` folder.
- `Tables/...` maps to the lakehouse `Tables` folder.
- A bare path defaults to `Files/...`.
- `Workspace/Lakehouse/Files/...` and `Workspace/Lakehouse/Tables/...` select
  a configured workspace/lakehouse pair.
- Workspace and lakehouse can be names or GUIDs.
- Existing shortcuts appear wherever OneLake exposes them as folders.

Writes must target a file inside `Files/` or `Tables/`. The synthetic root,
`Files`, and `Tables` are not writable targets. JupyterLab saves overwrite the
same remote files that `onelake.write` would update.

## File Map

Keep:

```text
images/onelake/Dockerfile
images/onelake/onelake
images/onelake/onelake.py
images/onelake/onelake_cli.py
images/onelake/zone_token_broker.py
images/onelake/onelake_fsspec.py
images/onelake/onelake_register.py
images/onelake/jupyter_server_config.d/onelake.json
images/onelake/onelake-r/
tests/onelake/
```

The OneLake stage stays between `base` and `mid`:

```text
base -> onelake -> mid -> rstudio -> sas-kernel -> jupyterlab-cpu/sas
```

## Module Responsibilities

`zone_token_broker.py`

- Internal only.
- Calls AuthService for the Storage scope.
- Parses raw JWT text.
- Caches tokens in memory.
- Redacts token-shaped text in errors.
- Returns an Azure SDK `AccessToken` through `credential()`.

`onelake.py`

- Loads and saves non-secret workspace/lakehouse config.
- Normalizes `/`, `Files/...`, `Tables/...`, qualified workspace/lakehouse
  paths, and bare paths.
- Creates Azure Data Lake clients per workspace.
- Provides `connect`, `status`, `ls`, `open`, `read`, `write`, `download`, and
  `upload`.

`onelake_cli.py`

- Owns only the CLI commands listed above.
- `write` reads stdin.
- `cat` writes bytes to stdout.
- `get` and `put` are explicit about direction.

`onelake_fsspec.py`

- Powers the JupyterLab drive.
- Stays thin and calls `onelake.py`.
- Shows a not-configured marker when workspace/lakehouse config is missing.
- Supports browse, open, save, upload, and download. Avoid broader filesystem
  promises in v1.

`onelake-r`

- Provides `ol_*` wrappers.
- Shells out to the `onelake` CLI.

## Security Invariants

- No persisted OneLake access tokens or refresh tokens.
- No device-code auth.
- No Azure CLI auth.
- No service-principal or managed-identity data identity for user files.
- No token printing in normal logs.
- Auth failures fail closed.
- OneLake enforces signed-in user permissions.

## Verification

Unit tests should cover:

- broker URL policy, Storage scope, token parsing, caching, and redaction;
- root, `Files`, `Tables`, and bare path normalization;
- `connect`, `status`, `ls`, `cat`, `write`, `get`, and `put`;
- R wrappers calling the CLI;
- Jupyter drive registration and not-configured marker;
- regression checks that removed auth and mount surfaces do not return.

Live pilot checks:

```bash
onelake status --live
onelake ls /
onelake ls Files/
onelake ls Tables/
onelake cat Files/example.txt
onelake write Files/example.txt < local.txt
onelake get Files/example.txt /tmp/example.txt
onelake put /tmp/example.txt Files/example-copy.txt
```

Also validate the JupyterLab `OneLake` drive and one pre-existing shortcut.

For an automated live smoke test inside a broker-connected notebook image:

```bash
export ONELAKE_WORKSPACE=<workspace-name-or-guid>
export ONELAKE_LAKEHOUSE=<lakehouse-name-or-guid>
export ONELAKE_LIVE_TEST=1
python -m pytest tests/onelake/test_onelake_live.py
```

## Reviewer Summary

A reviewer should be able to explain the system in one minute:

1. `onelake` is installed by the `images/onelake` layer.
2. Users browse the JupyterLab drive or call Python/R/CLI helpers.
3. All helpers call one Python OneLake client.
4. The client asks one internal broker client for a delegated token.
5. The broker client calls AuthService.
6. The client streams reads and writes through the ADLS-compatible OneLake API.
7. Tokens stay in memory and permissions stay user-specific.

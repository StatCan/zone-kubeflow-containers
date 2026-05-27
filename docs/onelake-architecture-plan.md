# OneLake Architecture

## Decision

Zone notebook containers expose one user-facing product: `onelake`.

The supported path is:

```text
JupyterLab OneLake drive
Python import onelake
R library(onelake)
onelake CLI
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

The notebook image does not implement Microsoft sign-in. It asks AuthService
for a delegated Storage-audience access token and uses that token in memory.
OneLake permissions remain the signed-in user's permissions. Workspace and
lakehouse settings persist; access tokens do not. After a notebook restart, the
next `onelake` command asks AuthService for a fresh delegated token.

## User Contract

Users get four entry points, all backed by the same Python client:

- JupyterLab shows a `OneLake` drive.
- Python users import `onelake`.
- R users call `ol_*` functions from `library(onelake)`.
- Script users call the `onelake` CLI.

Required CLI commands:

```bash
onelake status [--live]
onelake connect <workspace> <lakehouse>
onelake ls [path]
onelake cat <path>
onelake write <path>
onelake get <remote-path> <local-path>
onelake put <local-path> <remote-path>
```

The CLI is the future cron path. Cron support means commands running inside an
active notebook pod use the same broker-backed delegated auth path. This repo
does not add cron scheduling.

## Non-Goals

The first supported implementation does not include:

- Linux mounts, BlobFuse2, `/dev/fuse`, privileged containers, or `SYS_ADMIN`.
- Device-code auth, Azure CLI login, service principals, or managed identity as
  the user data-access identity.
- User-facing generic token commands or R token packages.
- Manual bearer-token smoke paths.
- Table transaction management or Delta commit orchestration.
- Shortcut creation, deletion, or lifecycle management.
- POSIX promises such as file locking, append semantics, or atomic multi-file
  operations.

## Auth Boundary

AuthService owns the real auth flow:

1. The notebook pod calls:

   ```http
   GET /authservice/getPassthroughToken?scope=https://storage.azure.com/.default
   ```

2. AuthService identifies the calling pod and namespace.
3. AuthService uses the namespace `oidc-authservice-token` secret to perform
   Microsoft Entra on-behalf-of exchange.
4. AuthService returns a delegated access token as raw text.
5. The notebook code keeps the token in memory and passes it to the Azure Data
   Lake SDK.

The notebook image must never persist OneLake access tokens, refresh tokens,
client secrets, service-principal credentials, or user passwords.

## Configuration

Persist only non-secret defaults:

```json
{
  "workspace": "workspace-name-or-guid",
  "lakehouse": "lakehouse-name-or-guid"
}
```

Environment:

| Variable | Purpose |
| --- | --- |
| `ONELAKE_WORKSPACE` | Optional workspace default. |
| `ONELAKE_LAKEHOUSE` | Optional lakehouse default. |
| `ONELAKE_REGION` | Region used to build the default DFS endpoint. Defaults to `canadacentral`. |
| `ONELAKE_ENDPOINT` | Full DFS endpoint override. |
| `ONELAKE_CONFIG` | Optional config file override. |
| `ONELAKE_BROKER_URL` | AuthService base URL. Defaults to the in-cluster AuthService URL. |
| `ONELAKE_BROKER_TOKEN_PATH` | AuthService token path. Defaults to `/getPassthroughToken`. |
| `ONELAKE_ALLOW_INSECURE_BROKER` | Dev-only opt-in for non-default HTTP broker URLs. |

## Path Model

The user-facing root is synthetic:

```text
OneLake/
  Files/
  Tables/
```

Rules:

- `/` lists `Files` and `Tables`.
- `Files/...` maps to the lakehouse `Files` folder.
- `Tables/...` maps to the lakehouse `Tables` folder.
- Bare paths such as `raw/file.csv` map to `Files/raw/file.csv`.
- Workspace and lakehouse may be names or GUIDs.
- Existing shortcuts appear as folders wherever OneLake exposes them.

Writes must target a file inside `Files/` or `Tables/`. The synthetic root and
managed roots themselves are not writable targets.

## Module Map

Keep the OneLake layer in `images/onelake`.

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
```

Responsibilities:

- `onelake.py`: config, path normalization, Python API, Azure Data Lake client.
- `zone_token_broker.py`: internal AuthService client and Azure SDK credential.
- `onelake_cli.py`: command surface for users and scripts.
- `onelake_fsspec.py`: thin JupyterLab drive adapter.
- `onelake_register.py`: explicit fsspec registration through a `.pth` import.
- `onelake-r`: R wrappers that shell out to the CLI.

Removed surfaces:

- Generic token CLI.
- Generic token Python helper.
- Generic token R package.
- Manual bearer-token CLI/env hooks.
- Append and `cp onelake:...` command variants.
- Historical broker-only documentation.

## JupyterLab Drive

The drive is an API-backed browser view, not a kernel mount.

Required behavior:

- Root lists `Files` and `Tables`.
- Remote folders can be browsed.
- Files can be opened, saved, uploaded, and downloaded.
- If workspace/lakehouse config is missing, the drive shows a clear marker file.

Avoid broad filesystem features until there is a real user need and a tested
OneLake behavior behind them.

## Local Staging Guidance

Use the API or CLI for normal reads and writes. For tools that expect local disk
semantics, stage data locally:

```bash
onelake get Files/raw/input.csv /tmp/input.csv
python job.py /tmp/input.csv /tmp/output.csv
onelake put /tmp/output.csv Files/processed/output.csv
```

This is the supported pattern for large files, many random reads, and tools that
expect local locking or atomic rename behavior.

## Test Expectations

Unit tests should cover:

- Broker calls AuthService with `https://storage.azure.com/.default`.
- Broker token caching and error redaction.
- `/`, `Files/...`, `Tables/...`, and bare path normalization.
- `connect`, `status`, `ls`, `cat`, `write`, `get`, and `put`.
- R `ol_*` wrappers call the CLI.
- Jupyter `OneLake` drive registration and not-configured marker.
- Regression checks that removed auth and filesystem surfaces do not reappear.

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

The same read/write path is covered by an opt-in pytest live smoke test. Run it
inside a notebook image or pod that has AuthService access:

```bash
export ONELAKE_WORKSPACE=<workspace-name-or-guid>
export ONELAKE_LAKEHOUSE=<lakehouse-name-or-guid>
export ONELAKE_LIVE_TEST=1
python -m pytest tests/onelake/test_onelake_live.py
```

Optional paths:

```bash
export ONELAKE_LIVE_TEST_PATH=Files/onelake-smoke.txt
export ONELAKE_LIVE_UPLOAD_PATH=Files/onelake-smoke-upload.txt
```

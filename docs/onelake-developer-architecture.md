# OneLake Developer Architecture

## Purpose

This branch simplifies OneLake access in Zone notebook containers to one
user-facing product named `onelake`.

Users get:

- a JupyterLab `OneLake` drive;
- an `onelake` CLI;
- a Python module named `onelake`;
- an R package named `onelake` with `ol_*` wrappers.

All user entry points call the same Python client. Token logic is internal.

## User Journey

1. A user opens a Zone notebook.
2. The notebook image contains the `images/onelake` layer.
3. The user saves the target Fabric workspace and lakehouse once:

   ```bash
   onelake connect <workspace-id-or-name> <lakehouse-id-or-name>
   ```

4. The client writes only non-secret config to `~/.onelake/config.json`.
5. The user reads, writes, downloads, uploads, or browses OneLake:

   ```bash
   onelake status --live
   onelake ls /
   onelake ls Files/
   onelake cat Files/example.txt
   echo hello | onelake write Files/example.txt
   onelake get Files/example.txt /tmp/example.txt
   onelake put /tmp/example.txt Files/example-copy.txt
   ```

6. On the first live operation, `onelake.py` asks the internal broker client for
   a token.
7. `zone_token_broker.py` calls AuthService.
8. AuthService returns a delegated Storage-audience token.
9. The Azure Data Lake SDK uses that token against the OneLake DFS endpoint.
10. OneLake evaluates the signed-in user's permissions.

Access tokens are cached in process memory only. If the notebook restarts, the
saved workspace/lakehouse config remains and the next live command asks
AuthService for a fresh delegated token.

## Architecture Flow

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
delegated Storage access token
        |
        v
Azure Data Lake SDK
        |
        v
OneLake DFS endpoint
```

## Auth Flow

The notebook image does not implement Microsoft sign-in.

For OneLake data access, the client requests this scope:

```text
https://storage.azure.com/.default
```

The broker call is:

```http
GET /authservice/getPassthroughToken?scope=https://storage.azure.com/.default
```

AuthService is responsible for:

- identifying the calling notebook pod;
- mapping it to the namespace/user session;
- reading the platform-owned `oidc-authservice-token` secret;
- performing Microsoft Entra on-behalf-of exchange;
- returning a short-lived delegated access token as raw text.

The notebook image is responsible only for calling the endpoint, parsing the raw
JWT, caching it in memory, and passing it to the Azure SDK.

## Token Persistence Model

Persisted:

```json
{
  "workspace": "workspace-id-or-name",
  "lakehouse": "lakehouse-id-or-name"
}
```

Not persisted:

- OneLake access tokens;
- refresh tokens;
- client secrets;
- service-principal credentials;
- user passwords.

This means notebook restarts are safe: the config remains, the bearer token is
gone, and the next command re-requests a delegated token from AuthService.

## Path Model

The user-facing root is synthetic:

```text
/
  Files/
  Tables/
```

Rules:

- `onelake ls /` shows the synthetic root: `Files` and `Tables`.
- `onelake ls Files/` lists the Fabric Lakehouse Files area.
- `onelake ls Tables/` lists the Fabric Lakehouse Tables area.
- A bare path such as `raw/file.csv` maps to `Files/raw/file.csv`.
- `Files/...` maps to `<lakehouse>.Lakehouse/Files/...`.
- `Tables/...` maps to `<lakehouse>.Lakehouse/Tables/...`.
- Lakehouse GUIDs are used as-is.
- Lakehouse names get `.Lakehouse` appended.

Writes must target a file inside `Files/` or `Tables/`. The synthetic root and
the managed roots themselves are not writable targets.

## Codebase Structure

```text
images/onelake/
  Dockerfile
  onelake
  onelake.py
  onelake_cli.py
  onelake_fsspec.py
  onelake_register.py
  zone_token_broker.py
  jupyter_server_config.d/onelake.json
  onelake-r/
    DESCRIPTION
    NAMESPACE
    R/onelake.R

tests/onelake/
  test_onelake.py
  test_onelake_cli.py
  test_onelake_cli_smoke.py
  test_onelake_layer.py
  test_onelake_live.py
  test_onelake_r.py
  test_zone_token_broker.py

tests/general/
  test_onelake_image.py
```

## Component Responsibilities

### `images/onelake/onelake.py`

Owns the user-facing Python API and shared backend logic.

Responsibilities:

- read and write non-secret config;
- normalize OneLake paths;
- create Azure Data Lake clients;
- list root, Files, and Tables;
- read and write files;
- download and upload local files;
- expose a simple `open()` helper for full-file reads and overwrites;
- report readiness through `status(live=False)`.

Public API:

```python
connect(workspace, lakehouse)
status(live=False)
ls(path="/")
open(path, mode="rb")
read(path, text=False)
write(path, data)
download(path, local_path)
upload(local_path, path)
```

### `images/onelake/zone_token_broker.py`

Internal only. Users should not call it directly.

Responsibilities:

- call AuthService;
- request the Storage scope;
- parse raw JWT text;
- extract `exp` from the JWT;
- cache tokens in memory until shortly before expiry;
- provide an Azure SDK `TokenCredential`;
- redact token-shaped strings in errors.

### `images/onelake/onelake_cli.py`

Owns the CLI surface.

Commands:

```bash
onelake status [--live]
onelake connect <workspace> <lakehouse>
onelake ls [path]
onelake cat <path>
onelake write <path>
onelake get <remote-path> <local-path>
onelake put <local-path> <remote-path>
```

`write` reads stdin. `cat` writes bytes to stdout. `get` and `put` are explicit
about transfer direction.

### `images/onelake/onelake_fsspec.py`

Provides the `onelake://` fsspec filesystem used by `jupyter-fs`.

Responsibilities:

- show a not-configured marker when config is missing;
- list root as `Files` and `Tables`;
- list OneLake directories;
- open/read files with range reads;
- save/write complete files;
- keep JupyterLab browsing backed by the same `onelake.py` client.

This is not a POSIX filesystem. It should stay thin.

### `images/onelake/onelake_register.py`

Registers the fsspec implementation from a `.pth` file:

```text
import onelake_register
```

This replaces implicit `sitecustomize` behavior with an explicit registration
module.

### `images/onelake/onelake-r`

Thin R package. It shells out to the CLI rather than duplicating Python SDK or
token logic.

Functions:

```r
ol_connect(workspace, lakehouse)
ol_status(live = FALSE)
ol_ls(path = "/")
ol_read_text(path)
ol_write_text(path, text)
ol_download(path, local_path)
ol_upload(local_path, path)
```

## Docker Layer

The stage remains dedicated and sits between `base` and `mid`:

```text
base -> onelake -> mid -> rstudio -> sas-kernel -> jupyterlab-cpu/sas
```

The Dockerfile:

- installs `azure-storage-file-datalake`;
- installs `jupyter-fs[fsspec]`;
- installs `requests`;
- copies OneLake Python modules into Python `purelib`;
- registers fsspec through `onelake_fsspec_register.pth`;
- installs the R `onelake` package;
- installs the Jupyter server config.

## Removed Surfaces

The simplification removes:

- `zone-token`;
- public `zonetokenbroker.py`;
- public `zonetokenbroker-r`;
- `onelake_utils.py`;
- manual bearer-token environment hooks;
- `--access-token-stdin`;
- `doctor`, `configure`, `cp onelake:...`, and `append` CLI variants;
- `docs/zone-token-broker.md`;
- `tests/zone_token/`.

These were removed to keep one user product and one auth path.

## Validation

Local focused tests:

```bash
python -m pytest tests/onelake tests/general/test_onelake_image.py
```

Expected local result without Rscript, built image, or live OneLake config:

```text
22 passed, 3 skipped
```

The command smoke test uses fake Azure/AuthService dependencies and proves:

- `connect` writes config;
- `status --live` triggers token acquisition;
- `write` stores bytes;
- `cat` reads bytes;
- `get` downloads bytes;
- `put` uploads bytes;
- one token is reused from in-memory cache.

Live test inside a broker-connected notebook:

```bash
export ONELAKE_WORKSPACE=<workspace-id-or-name>
export ONELAKE_LAKEHOUSE=<lakehouse-id-or-name>
export ONELAKE_LIVE_TEST=1
python -m pytest tests/onelake/test_onelake_live.py
```

Optional live paths:

```bash
export ONELAKE_LIVE_TEST_PATH=Files/onelake-smoke.txt
export ONELAKE_LIVE_UPLOAD_PATH=Files/onelake-smoke-upload.txt
```

## Known Boundaries

- This branch does not implement shortcut creation or management.
- This branch does not implement cron scheduling.
- This branch does not provide a Linux mount.
- This branch does not promise local filesystem semantics such as locking,
  append, or atomic multi-file operations.
- Large or tool-sensitive workflows should stage files locally with `get` and
  `put`.

## Review Checklist

- `onelake status --live` succeeds in a notebook pod.
- `onelake ls /` shows `Files` and `Tables`.
- `onelake ls Files/` shows Lakehouse file contents.
- `onelake cat Files/<existing-small-file>` prints content.
- `echo hello | onelake write Files/<test-file>` succeeds.
- `onelake get` downloads a file.
- `onelake put` uploads a file.
- Python `import onelake` works.
- R `library(onelake)` works in images with R.
- JupyterLab shows the `OneLake` drive.

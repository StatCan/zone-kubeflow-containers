# OneLake for Zone notebooks

A small helper so notebook users can browse and move OneLake files using their
own signed-in permissions, without writing Microsoft auth or Azure SDK
boilerplate. Installed in the `mid` image, so every notebook image inherits it.

## How it fits together

```text
JupyterLab "OneLake" drive   Python: import onelake   R: library(onelake)   CLI: onelake
                         \            |              /                /
                          \           |             /                /
                                  onelake.py  (one small Python client)
                                        |
                          zone_token_broker  (shared helper, installed in mid)
                                        |
                          AuthService /authservice/getPassthroughToken?scope=...
                                        |
                          Azure Data Lake SDK  ->  OneLake DFS endpoint
```

- **Auth is delegated.** Tokens come from the in-cluster AuthService via the
  shared `zone_token_broker` module — the same broker every Zone consumer uses.
  This module does **not** ship its own broker. Tokens stay in memory; only the
  workspace/lakehouse selection is persisted (`~/.onelake/config.json`).
- **One client.** `onelake.py` is the single code path. The CLI, the R wrappers,
  and the JupyterLab drive all go through it.

## Public surface

CLI (`onelake`):

```bash
onelake status [--live]
onelake connect <workspace> <lakehouse>
onelake ls [path]
onelake cat <path>
onelake write <path>          # reads stdin
onelake get <remote> <local>
onelake put <local> <remote>
```

Python (`import onelake`): `connect`, `status`, `ls`, `read`, `write`,
`download`, `upload`. Files also open directly through fsspec, e.g.
`pandas.read_csv("onelake://Files/raw/input.csv")`.

R (`library(onelake)`): `ol_connect`, `ol_status`, `ol_ls`, `ol_read_text`,
`ol_write_text`, `ol_download`, `ol_upload` — thin shells over the CLI, no
duplicated token logic.

## Path model

The user-facing root is synthetic. `Files/` and `Tables/` are the managed
roots; any other path is treated as relative to `Files/`. Writes must target a
file inside `Files/` or `Tables/`.

## Environment

All optional; `connect` is the normal way to set the workspace/lakehouse.

- `ONELAKE_WORKSPACE`, `ONELAKE_LAKEHOUSE` — override the saved selection (env
  wins over `~/.onelake/config.json`).
- `ONELAKE_REGION` (default `canadacentral`) / `ONELAKE_ENDPOINT` — the OneLake
  DFS endpoint.
- `AUTHSERVICE_BROKER_URL` — override the AuthService base URL (from the shared
  `zone_token_broker`; defaults to the in-cluster AuthService).

## Future: folder shortcuts and a click-only GUI

The JupyterLab drive (`onelake_fsspec.py` + jupyter-fs) is the first step toward
a fully graphical experience: see OneLake folders in the file browser and open,
edit, and save by clicking. The next steps build on this same client —
registering OneLake **folder shortcuts** as named drives and a richer in-notebook
browser — without changing the auth or path model below it.

## Non-goals

No FUSE/BlobFuse mounts, no device-code/Azure CLI login, no user-facing token
commands, no service-principal data access, and no Delta/transaction logic.

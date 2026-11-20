# Signing in to Azure from your workspace

You do not need to sign in to Azure from inside your workspace — you already
did. Logging into **zone.statcan.ca** is your Azure sign-in. There is no
browser pop-up, no device code, and nothing to copy-paste. Just use the
commands below.

## az CLI

One command, no browser, no device code:

```bash
az login --identity
```

That's it. `az storage`, `az cognitiveservices`, and friends work as you.

If `az login --identity` complains that you have no subscriptions, add
`--allow-no-subscriptions` (see Troubleshooting below).

## AzCopy

Run `azcopy --version` in your workspace terminal to check that AzCopy is
available. Set `AZCOPY_AUTO_LOGIN_TYPE=MSI` on the command to use your Zone
sign-in. You need write access to the destination for these upload examples.
Replace `./example.csv` with a file in your workspace or on a mounted filer.
Both examples opt out of [AzCopy usage telemetry](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10#opt-out-of-azcopy-telemetry).

Upload to Azure Blob Storage:

```bash
AZCOPY_AUTO_LOGIN_TYPE=MSI azcopy copy ./example.csv \
  'https://<account>.blob.core.windows.net/<container>/example.csv' \
  --disable-telemetry=true
```

Upload to a Fabric OneLake lakehouse:

```bash
AZCOPY_AUTO_LOGIN_TYPE=MSI azcopy copy ./example.csv \
  'https://onelake.dfs.fabric.microsoft.com/<workspace>/<lakehouse>.lakehouse/Files/example.csv' \
  --trusted-microsoft-suffixes 'fabric.microsoft.com' --disable-telemetry=true
```

To download, put the cloud URL first and the local path second. See
[Getting started with AzCopy](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10)
and [AzCopy with OneLake](https://learn.microsoft.com/en-us/fabric/onelake/onelake-azcopy).

## Python

The standard Azure SDK credentials just work — no configuration needed:

```python
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

credential = DefaultAzureCredential()
client = BlobServiceClient(
    "https://<account>.blob.core.windows.net", credential=credential
)
```

Or, if you only need a raw token:

```python
from azure.identity import ManagedIdentityCredential

credential = ManagedIdentityCredential()
token = credential.get_token("https://storage.azure.com/.default")
```

## R

R uses the built-in `zonetokenbroker` package. Ask it for a token for the
service you want, then pass that token to whatever package you're using:

```r
token <- zonetokenbroker::zone_get_token("https://storage.azure.com/.default")

# e.g. with AzureStor:
ep <- AzureStor::storage_endpoint(
  "https://<account>.dfs.core.windows.net",
  token = token
)
```

Any package or request that accepts a bearer token string works, for example
with httr:

```r
httr::GET(url, httr::add_headers(Authorization = paste("Bearer", token)))
```

Tokens are cached and refreshed for you — call `zone_get_token()` whenever
you need one; repeated calls are free.

## How it works

Your login to zone.statcan.ca **is** the Azure sign-in — by the time your
workspace opens, you are already authenticated. When a tool in your
workspace asks for an Azure token, the Zone platform mints one for you,
server-side, from that same login session. Nothing in your workspace ever
talks to a Microsoft sign-in page — no browser, no device code, no password.

## Troubleshooting

**Token errors after about a day.** Your Zone login session has expired.
Sign in to [zone.statcan.ca](https://zone.statcan.ca) again in your regular
browser, then retry the command — no need to restart your workspace.

**"Consent required" / "permission or scope not consented" errors.** The
Azure permission you're asking for hasn't been approved for the Zone yet.
Contact the platform team with the service you're trying to reach (for
example the scope from the error message) — they can approve it. This is a
one-time, platform-wide approval, not something you can fix yourself.

**`az login --identity` reports no subscriptions.** Either run
`az login --identity --allow-no-subscriptions` (fine if you only need data
services like Storage), or you don't have a role on any Azure subscription
yet — ask your project's Azure administrator for access.

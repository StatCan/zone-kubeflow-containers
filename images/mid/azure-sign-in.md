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

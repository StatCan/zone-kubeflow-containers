# Azure sign-in on the Zone: no browser, no device code

## Introduction

If you use Azure from a Zone workspace — the `az` CLI, Python's Azure SDKs,
storage from pandas or DVC, or R — signing in used to be the worst part of
your day. That's over: **your login to zone.statcan.ca is now your Azure
sign-in.** One command (`az login --identity`) or, for most libraries, no
command at all.

This page explains what changed, how to use it, and how it works.

## The problem

Azure tools inside a workspace had no good way to know who you are:

- **Device-code sign-in** (`az login --use-device-code`) — copy a code,
  open a Microsoft page, paste the code — is being retired by Cybersecurity:
  the code-entry step is phishable, because an attacker can start a login
  and trick someone else into entering the code.
- **Normal interactive sign-in** needs a browser next to the terminal.
  A workspace pod has no browser, and Microsoft's sign-in pages are not
  reachable from inside the cluster — an in-pod browser was prototyped and
  hit exactly that wall.

Meanwhile, every Zone user *already* signs in to Entra ID — with MFA,
through GC SSO — every time they open zone.statcan.ca. The fix was to stop
asking users to sign in twice.

## What we built

The Zone platform now mints Azure tokens **from the login session you
already have**. When a tool in your workspace needs an Azure token, the
platform's authentication service exchanges your zone.statcan.ca session
for a short-lived Azure token issued **as you** — server-side, with nothing
in your workspace ever contacting a Microsoft sign-in page.

A small translator inside every workspace (the *managed-identity shim*)
makes this invisible to your tools: `az` and the Azure SDKs think they are
running on an Azure machine with a built-in identity, and pick it up
automatically.

```
Desktop                          Zone cluster                          Entra ID
───────                          ────────────                         ─────────
User's browser ──── OIDC ──► zone.statcan.ca ingress
  (real Entra sign-in,             │
   MFA, GC SSO)                    ▼
                          AuthService (StatCan fork)
                            │  holds user's OIDC session
                            │
   User's notebook pod      │
  ┌────────────────────────┐│
  │ az / azure-identity /  ││
  │ any MSI-aware SDK      ││
  │      │ MSI protocol    ││
  │      ▼                 ││
  │ zone-msi-shim          ││
  │ (127.0.0.1:8901) ──────┼┼──► getPassthroughToken?scope=X
  │                        ││    (caller pod IP → namespace →
  │ R: zonetokenbroker ────┼┘     namespace owner's session)
  └────────────────────────┘            │
                                        │ on-behalf-of exchange
                                        ▼
                              Entra token endpoint ──► delegated access
                                                       token, minted as
                                                       the user
```

Key properties:

- **Always you, never a shared account.** Every token is issued as the
  individual user and limited to what that user's own Azure roles allow.
  Two users in two workspaces get two different identities, concurrently.
- **No credentials in your workspace.** There is no secret, key, or config
  file anywhere — the platform identifies your workspace and uses your
  session. Nothing to leak, nothing to rotate.
- **Nothing new leaves the cluster.** The token exchange happens
  server-side; your workspace only ever talks to the local translator and
  the in-cluster authentication service.

## How to use it

### az CLI

```bash
az login --identity
```

That's it — instant, no browser, no code to copy. Everything after login
(`az storage`, `az group list`, …) works unchanged, and tokens refresh
silently. If az reports you have no subscriptions, add
`--allow-no-subscriptions` (fine when you only need data services like
Storage).

### Python

The standard Azure SDK credentials just work, with no configuration:

```python
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

credential = DefaultAzureCredential()
client = BlobServiceClient(
    "https://<account>.blob.core.windows.net", credential=credential
)
```

Only need a raw token?

```python
from azure.identity import ManagedIdentityCredential

token = ManagedIdentityCredential().get_token("https://storage.azure.com/.default")
```

pandas (`abfs://…` paths), DVC (`zone-dvc`), and other tools built on these
credentials work out of the box.

### R

R uses the built-in `zonetokenbroker` package — ask it for a token, pass
the token to any package that accepts one:

```r
token <- zonetokenbroker::zone_get_token("https://storage.azure.com/.default")

# e.g. with AzureStor:
ep <- AzureStor::storage_endpoint(
  "https://<account>.dfs.core.windows.net",
  token = token
)

# or any request that takes a bearer token:
httr::GET(url, httr::add_headers(Authorization = paste("Bearer", token)))
```

Tokens are cached and refreshed for you — repeated calls are free.

## The result

- `az login --identity` signs you in **in about a second**, as yourself.
- Python, pandas, DVC, and R reach Azure with **zero setup**.
- The phishable device-code flow is gone, and nothing that replaced it
  stores a credential in your workspace.
- Access is governed platform-side: each Azure service is enabled by a
  one-time approval on the Zone's app registration, and anything not yet
  approved fails with a clear, named error instead of a workaround.

## Troubleshooting

- **Token errors after about a day** — your Zone session expired. Sign in
  to [zone.statcan.ca](https://zone.statcan.ca) again in your regular
  browser, then retry. No need to restart your workspace.
- **"Consent required" / AADSTS65001** — the Azure service you're calling
  hasn't been approved for the Zone yet. Contact the platform team with the
  scope named in the error; approval is a one-time platform action.
- **az reports no subscriptions** — use
  `az login --identity --allow-no-subscriptions`, or ask your project's
  Azure administrator for a role on a subscription.
- **Known limits** — tokens are always personal (no service principals);
  sessions last about 24 hours; services requiring an extra MFA step-up
  beyond your Zone login are not supported.

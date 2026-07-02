# Signing in to Azure from your workspace

Device-code authentication (`az login --use-device-code`) is being retired by
Cybersecurity. You no longer need it: your workspace includes a **secure
browser that runs inside your notebook** and appears as a tab in JupyterLab,
so the normal interactive Azure sign-in works directly — credentials are
typed into the workspace's own browser on the StatCan network, never into a
browser on your device.

## Azure CLI

1. Open a terminal and run:

   ```bash
   az login
   ```

2. A **Zone Browser** tab opens automatically beside your terminal, showing
   the Microsoft sign-in page. (If it does not appear, click the blue **+**
   (Launcher) and open the **Zone Browser** tile.)

3. Sign in (including MFA) in that tab. Your terminal finishes logging in on
   its own.

That's it — no `--use-device-code`, no wrappers, no code changes.

## Python

`DefaultAzureCredential` / `InteractiveBrowserCredential` from
`azure-identity` work the same way: when a credential needs you to sign in,
it loads the sign-in page in the Zone Browser.

```python
from azure.identity import InteractiveBrowserCredential
cred = InteractiveBrowserCredential()
token = cred.get_token("https://storage.azure.com/.default")
```

## R

`AzureAuth` / `AzureRMR` with the default `authorization_code` flow open the
Zone Browser via `browseURL()`:

```r
token <- AzureAuth::get_azure_token(
    resource = "https://storage.azure.com/",
    tenant   = "yourtenant",
    app      = "yourappid"
)
```

## Using the Zone Browser directly

The Zone Browser is a real Chromium running inside your workspace — you can
use its address bar like any browser (for example, to finish a device-code
prompt from a tool that still uses one during the transition period):

```bash
zone-browser                    # loads https://microsoft.com/devicelogin
zone-browser https://portal.azure.com
zone-browser --status           # what is running
zone-browser --stop             # shut it down now
```

It shuts itself down after 15 idle minutes and restarts automatically the
next time it is needed.

## Troubleshooting

- **`az login` says it cannot launch a browser** — run it from a terminal
  (JupyterLab or VS Code). From a notebook cell, use `!bash -ic "az login"`.
- **The Zone Browser tab shows "Disconnected"** — reload the tab.
- **Blank page** — wait a moment; the browser may still be starting.
- Logs live under `/tmp/zone-browser-$(id -u)/` if you need to report an
  issue.

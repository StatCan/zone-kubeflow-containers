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
   the GC SSO sign-in page. (If it does not appear, click the blue **+**
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

## R (including RStudio)

`AzureAuth` / `AzureRMR` with the default `authorization_code` flow open the
Zone Browser via `browseURL()` — in the R console, in a Jupyter R kernel,
and inside RStudio (where the Zone overrides RStudio's default of opening
your local browser):

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

- **You signed in but ended on a blank `localhost:<port>` "can't reach this
  page" error** — you opened the `login.microsoftonline.com` link printed by
  the Azure CLI in your **own** browser. That link only works inside the
  workspace: after sign-in it redirects to a port that exists only in your
  notebook. Go back to JupyterLab, open the **Zone Browser** tab, and sign
  in there instead.
- **`az login` says it cannot launch a browser** — run it from a terminal
  (JupyterLab or VS Code). From a notebook cell, use `!bash -ic "az login"`.
- **The Zone Browser tab shows "Disconnected"** — reload the tab.
- **Blank page** — wait a moment; the browser may still be starting.
- **Stuck on "Taking you to your organization's sign-in page"** — this page
  should normally be skipped entirely (the workspace sends sign-ins straight
  to GC SSO). If you still land on it, click the "click here" link on the
  page — the Zone Browser follows it, even when it opens in a new browser
  tab behind the scenes.
- **Signed in as the wrong account, or need to switch accounts** — the
  workspace browser keeps your sign-in session, so a new `az login` may
  sign you back in silently. Clear it first:

  ```bash
  zone-browser --stop && rm -rf /tmp/zone-browser-$(id -u)/profile
  az login
  ```
- **Blank white page on `sso1.gcsso.gc.ca/adfs/ls/wia`** — GC SSO tried
  Windows Integrated Authentication, which a notebook pod cannot do (it is
  not a domain-joined device). Ask your admins to set a user-agent that GC
  SSO does not treat as WIA-capable (the `ZONE_BROWSER_UA` environment
  variable), which makes the normal username/password page appear instead.
- **Reporting an issue** — run `zone-browser --dump` while the problem is
  on screen: it saves a screenshot, the page HTML, and the URL under
  `/tmp/zone-browser-$(id -u)/dump-*/`. Attach that folder (plus the `*.log`
  files next to it) to your ticket.

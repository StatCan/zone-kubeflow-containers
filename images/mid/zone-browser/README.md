# zone-browser — the in-pod secure browser

Replaces device-code authentication (being retired by Cybersecurity) with the
standard interactive (authorization-code) Entra ID flow, run entirely inside
the notebook pod. Users keep running plain `az login` /
`DefaultAzureCredential` / R `AzureAuth` — no wrappers, no code changes — and
the sign-in page appears **as a tab inside JupyterLab** (the "Zone Browser"
Launcher tile), right beside their terminal or notebook.

There is **no X server and no VNC**. A headless Chromium (the Playwright
build bundled under `/opt/ms-playwright`; Ubuntu's chromium is a snap stub)
runs in the pod, and `zone-browser-viewer.py` streams its screen over the
Chrome DevTools Protocol (CDP) — the same mechanism Chrome's own debugger
uses — through the notebook's authenticated jupyter-server-proxy route.

## How it works

```
JupyterLab "Zone Browser" tab (viewer page: frames on an <img>,
mouse/keyboard forwarded back)
        │  wss  {NB_PREFIX}/zone-browser/ws        (authenticated route)
jupyter-server-proxy ──► zone-browser-viewer.py    (127.0.0.1:{port})
        │  CDP websocket
Headless Chromium ── 127.0.0.1:9222 DevTools ── screencast + input
        ▲
az login (MSAL) ── http://localhost:<random> redirect, same pod netns
```

1. The image sets `BROWSER=/usr/local/bin/zone-browser` (and `R_BROWSER`), so
   Python's `webbrowser` module — used by `az`/MSAL/azure-identity — invokes
   `zone-browser` when a sign-in page must be opened. `DISPLAY=:20` is
   exported from `/etc/bash.bashrc` only because `az` refuses interactive
   auth on Linux without a GUI env var; no X server exists.
   For R, `Rprofile-zone-browser.R` (appended to `Rprofile.site` at build)
   sets `options(browser=)` to zone-browser and re-asserts it from a
   `rstudio.sessionInit` hook — RStudio otherwise replaces the option at
   session init with a handler that opens the user's local browser. This
   covers the rstudio image too, which builds FROM mid.
2. `zone-browser <url>` starts the headless Chromium if needed and points it
   at the URL — via the running viewer bridge (`POST /open`) so an open Zone
   Browser tab updates live, else via a one-shot DevTools call.
2b. The `zone-browser-autoopen` labextension (built from `labextension/` at
   image build) holds the bridge's `/events` websocket from every JupyterLab
   frontend; on the bridge's `{"type": "open"}` broadcast it opens/focuses
   the Zone Browser tab in the main area automatically. The printed banner
   therefore contains **no URL** — a clickable link would open in the user's
   local browser, which is exactly what this flow avoids. Because frontends
   hold `/events` open all session, `--serve` must stay cheap: Chromium is
   only started on demand (`zone-browser --ensure`), and the idle watchdog
   stops Chromium but leaves the bridge running.
3. The "Zone Browser" Launcher tile is a jupyter-server-proxy named server
   (`zone-browser --serve {port}`, registered in
   `/opt/conda/etc/jupyter/jupyter_server_config.json` — the traitlets must
   live there, not in `jupyter_server_config.d/`, which only handles
   extension enablement). `new_browser_tab: false` renders it inside
   JupyterLab.
4. MSAL's redirect server listens on `localhost` inside the pod; Chromium is
   in the same network namespace, so the authorization-code flow completes
   without device code. Egress to `login.microsoftonline.com` comes from the
   pod, i.e. the StatCan network. Credentials are typed into the pod's
   Chromium — the user's local browser only displays pixels.
5. An idle watchdog stops Chromium after `ZONE_BROWSER_TTL_MINUTES`
   (default 15) with no use; the viewer restarts it transparently on the next
   use (`zone-browser --ensure`).

## Security notes

- The device-code *grant* is never used — that is what Cybersecurity is
  retiring (it is phishable). Conditional Access evaluates the sign-in
  against the pod's egress IP; the interactive session never runs on the
  user's device.
- Chromium runs `--no-sandbox`: the k8s pod's seccomp profile does not allow
  the Chromium sandbox's namespace syscalls. It is headless, runs as the
  unprivileged notebook user, and is already inside the pod's isolation
  boundary.
- The DevTools port (9222) and the viewer bind to `127.0.0.1` only; the only
  external path is the authenticated jupyter-server-proxy route.
- StatCan TLS-inspection CAs from `/opt/conda/ssl/certs` are imported into
  `~/.pki/nssdb` (Chromium's trust store) on first use.
- If a Conditional Access policy requires an Intune-compliant *device* for an
  app, this flow (like any in-pod flow) presents the pod, not the user's
  managed laptop. Location/network-based policies are satisfied.

## Ops / tunables

Runtime state lives under `/tmp/zone-browser-$UID/` (pidfiles, logs, Chromium
profile — deliberately not on the home PVC). See the `zone-browser` header
for the `ZONE_BROWSER_*` env vars. Set `ZONE_EXTERNAL_URL=https://<zone
host>` (e.g. via PodDefault or the notebook controller) to make the printed
fallback link fully clickable.

**GC SSO / ADFS Windows Integrated Auth:** from inside the StatCan network,
`sso1.gcsso.gc.ca` serves its WIA endpoint (`/adfs/ls/wia`) to user agents
on its `WIASupportedUserAgents` list; the pod has no Kerberos ticket, so
the sign-in dead-ends on a blank page. The browser therefore runs BY
DEFAULT with a user agent that drops the "Chrome" token
(`Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)
ZoneBrowser/1.0 Safari/537.36` — verified to render Microsoft sign-in
pages correctly). If GC SSO still WIA-challenges that UA, set
`ZONE_BROWSER_UA` to a value confirmed with
`curl -s -o /dev/null -w '%{http_code}\n' -A "<ua>"
https://sso1.gcsso.gc.ca/adfs/ls/` (401 = WIA challenge, 200 = forms);
`ZONE_BROWSER_UA=""` restores Chromium's native user agent.

**Support bundles:** `zone-browser --dump` captures what the browser is
showing right now (screenshot + page HTML + URL) into
`/tmp/zone-browser-$UID/dump-<timestamp>/` — through the running viewer
bridge when one is attached, else via a direct one-shot DevTools call.

**Display quality:** frames are captured at 2× device scale, JPEG quality
90 (supersampled on standard-DPI monitors, native on hi-DPI).

`zone-browser --selftest` (used by `tests/mid/test_zone_browser.py`) starts
Chromium and the viewer, probes the viewer page and the `/open` navigation
API, and shuts everything down.

## Rebuilding the labextension

`labextension/dist-labext/` is the prebuilt output that the Dockerfile
installs (committed so the image build needs no node/webpack step). After
changing `labextension/lib/index.js`, rebuild it in any environment with
`jupyterlab` and node available:

```bash
cd images/mid/zone-browser/labextension
jlpm install
# builder CLI name differs across JupyterLab 4.x:
CORE_PATH="$(python -c 'import jupyterlab, os; print(os.path.join(os.path.dirname(jupyterlab.__file__), "staging"))')"
node_modules/.bin/build-labextension --core-path "$CORE_PATH" .   # or: jupyter-builder build --core-path ...
# output lands in dist-labext/ (configured in package.json); commit it
```

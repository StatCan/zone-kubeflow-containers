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
2. `zone-browser <url>` starts the headless Chromium if needed and points it
   at the URL — via the running viewer bridge (`POST /open`) so an open Zone
   Browser tab updates live, else via a one-shot DevTools call.
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

`zone-browser --selftest` (used by `tests/mid/test_zone_browser.py`) starts
Chromium and the viewer, probes the viewer page and the `/open` navigation
API, and shuts everything down.

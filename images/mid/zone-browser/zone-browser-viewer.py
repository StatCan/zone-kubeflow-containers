#!/usr/bin/env python3
"""zone-browser-viewer -- stream the in-pod headless Chromium into a
JupyterLab tab over the Chrome DevTools Protocol (CDP). No X server, no VNC.

Serves a small viewer page (screen frames on an <img>, input events forwarded
back) plus a websocket bridge to Chromium's DevTools endpoint. It is run by
jupyter-server-proxy as the "Zone Browser" Launcher tile (see
zone-browser --serve) and is reached only through Jupyter's authenticated
proxy; everything here binds to 127.0.0.1.

  zone-browser-viewer.py --serve PORT     serve viewer + bridge (foreground)
  zone-browser-viewer.py --navigate URL   one-shot: point the browser at URL

Uses tornado, which is always present in the notebook's Jupyter environment.
"""

import argparse
import asyncio
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.websocket import websocket_connect

CDP = os.environ.get("ZONE_BROWSER_CDP", "http://127.0.0.1:9222")
RUN_DIR = os.environ.get(
    "ZONE_BROWSER_RUN_DIR", f"/tmp/zone-browser-{os.getuid()}"
)
ZONE_BROWSER_BIN = os.environ.get("ZONE_BROWSER_BIN", "/usr/local/bin/zone-browser")
# ids >= this are commands issued by the bridge itself; their replies are not
# forwarded to the viewer (the viewer's own ids start at 1)
BRIDGE_ID_BASE = 1_000_000_000
TARGET_CHANGED = json.dumps({"method": "ZoneBrowser.targetChanged"})
BROWSER_GONE = json.dumps({"method": "ZoneBrowser.browserGone"})


def send_all(clients, message):
    for client in list(clients):
        try:
            client.write_message(message)
        except tornado.websocket.WebSocketClosedError:
            clients.discard(client)

_last_touch = 0.0


def touch_last_used():
    """Tell zone-browser's idle watchdog that someone is using the browser."""
    global _last_touch
    now = time.time()
    if now - _last_touch > 30:
        _last_touch = now
        try:
            pathlib.Path(RUN_DIR, "last-used").touch()
        except OSError:
            pass


def list_pages():
    with urllib.request.urlopen(f"{CDP}/json/list", timeout=5) as resp:
        return [t for t in json.load(resp) if t.get("type") == "page"]


class Upstream:
    """The single shared CDP connection to the current Chromium page target."""

    def __init__(self):
        self.conn = None
        self.target_id = None
        self.known_targets = set()
        self.clients = set()
        self.next_id = BRIDGE_ID_BASE
        self.pending = {}
        self.watch_task = None
        self.pump_task = None

    async def ensure(self):
        if self.conn is not None:
            return self.conn
        pages = []
        for attempt in range(3):
            try:
                pages = list_pages()
            except OSError:
                pages = []
            if pages:
                break
            # Chromium is not up (first use, or reaped by the idle watchdog)
            subprocess.run([ZONE_BROWSER_BIN, "--ensure"], check=False, timeout=120)
            await asyncio.sleep(1 + attempt)
        if not pages:
            raise RuntimeError("in-pod Chromium is not reachable")
        self._adopt(await self._connect(pages[0]), pages[0])
        self.known_targets = {p["id"] for p in pages}
        # an already-open viewer tab (idle-reaped browser) must re-arm its
        # screencast on the fresh target
        send_all(self.clients, TARGET_CHANGED)
        if self.watch_task is None or self.watch_task.done():
            self.watch_task = asyncio.ensure_future(self._watch_targets())
        return self.conn

    async def _connect(self, page):
        return await websocket_connect(
            page["webSocketDebuggerUrl"], max_message_size=64 * 1024 * 1024
        )

    def _adopt(self, conn, page):
        old, self.conn = self.conn, conn
        self.target_id = page["id"]
        self._fail_pending()
        self.pump_task = asyncio.ensure_future(self._pump(conn))
        if old is not None:
            old.close()

    def _fail_pending(self):
        for future in self.pending.values():
            if not future.done():
                future.set_exception(RuntimeError("browser connection closed"))
        self.pending.clear()

    async def _list_pages(self):
        # keep the blocking HTTP call off the event loop: a slow /json/list
        # must not stall the screencast and input websockets
        return await asyncio.get_event_loop().run_in_executor(None, list_pages)

    async def _watch_targets(self):
        # Sign-in pages sometimes continue in a NEW tab (window.open or
        # target="_blank" -- e.g. the "click here" fallback link on Entra's
        # "Taking you to your organization's sign-in page" interstitial).
        # Headless Chromium puts that tab in a hidden target, so the viewer
        # would keep screencasting the old, now-frozen page. Follow the
        # newest tab. The replaced page is deliberately left open: popup
        # flows hand their result back to window.opener, and when a popup
        # closes itself, _pump()'s _reattach returns the viewer to it.
        while True:
            await asyncio.sleep(2)
            if self.conn is None:
                continue
            try:
                pages = await self._list_pages()
            except Exception:
                continue  # Chromium mid-shutdown/unreachable; retry later
            fresh = [p for p in pages if p["id"] not in self.known_targets]
            if not fresh or self.conn is None:
                continue
            try:
                self._adopt(await self._connect(fresh[0]), fresh[0])
            except Exception:
                continue  # tab still initializing; retry on the next tick
            # only mark targets known once the switch succeeded, so a
            # transient connect failure is retried instead of orphaned
            self.known_targets = {p["id"] for p in pages}
            send_all(self.clients, TARGET_CHANGED)

    async def _reattach(self):
        # Our tab closed (e.g. a sign-in popup finished and closed itself)
        # while Chromium is still up: move to a surviving tab, trying the
        # tab that just died last (it may still be listed while closing).
        try:
            pages = await self._list_pages()
        except Exception:
            return False
        pages.sort(key=lambda p: p["id"] == self.target_id)
        for page in pages:
            try:
                self._adopt(await self._connect(page), page)
            except Exception:
                continue
            self.known_targets = {p["id"] for p in pages}
            return True
        return False

    async def _pump(self, conn):
        while True:
            msg = await conn.read_message()
            if msg is None:
                break
            try:
                parsed = json.loads(msg)
                mid = parsed.get("id")
            except (ValueError, AttributeError):
                parsed, mid = None, None
            if isinstance(mid, int) and mid >= BRIDGE_ID_BASE:
                future = self.pending.pop(mid, None)
                if future is not None and not future.done():
                    future.set_result(parsed)
                continue
            send_all(self.clients, msg)
        if self.conn is not conn:
            return  # superseded by a target switch
        self.conn = None
        self._fail_pending()
        if await self._reattach():
            send_all(self.clients, TARGET_CHANGED)
            return
        send_all(self.clients, BROWSER_GONE)

    async def command(self, method, params):
        conn = await self.ensure()
        self.next_id += 1
        await conn.write_message(
            json.dumps({"id": self.next_id, "method": method, "params": params})
        )

    async def request(self, method, params, timeout=20):
        """Send a CDP command and await its reply (unlike command())."""
        conn = await self.ensure()
        self.next_id += 1
        request_id = self.next_id
        future = asyncio.get_event_loop().create_future()
        self.pending[request_id] = future
        await conn.write_message(
            json.dumps({"id": request_id, "method": method, "params": params})
        )
        try:
            reply = await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(request_id, None)
        if "error" in reply:
            raise RuntimeError("%s: %s" % (method, reply["error"]))
        return reply.get("result", {})


UPSTREAM = Upstream()


class WSHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        # jupyter-server-proxy sits in front and enforces notebook auth
        return True

    async def open(self):
        # one live viewer at a time: the newest tab wins
        for client in list(UPSTREAM.clients):
            client.close(4000, "another Zone Browser tab was opened")
        UPSTREAM.clients = {self}
        try:
            await UPSTREAM.ensure()
        except Exception:
            self.close(4001, "in-pod browser unavailable")

    async def on_message(self, message):
        touch_last_used()
        try:
            conn = await UPSTREAM.ensure()
        except Exception:
            self.close(4001, "in-pod browser unavailable")
            return
        await conn.write_message(message)

    def on_close(self):
        UPSTREAM.clients.discard(self)


EVENT_CLIENTS = set()


def broadcast_open():
    """Tell every JupyterLab frontend to open (or focus) the Zone Browser tab."""
    send_all(EVENT_CLIENTS, '{"type": "open"}')


class EventsHandler(tornado.websocket.WebSocketHandler):
    """Held open by the zone-browser-autoopen labextension in each Lab tab.

    Deliberately does NOT touch the Chromium upstream: Lab frontends connect
    at startup, and the browser must only start when something needs it.
    """

    def check_origin(self, origin):
        return True

    def open(self):
        EVENT_CLIENTS.add(self)

    def on_message(self, message):
        pass

    def on_close(self):
        EVENT_CLIENTS.discard(self)


class OpenHandler(tornado.web.RequestHandler):
    """POST /open (url=...) -- used by the zone-browser CLI, e.g. az login."""

    async def post(self):
        url = self.get_body_argument("url", self.get_query_argument("url", None))
        if not url:
            raise tornado.web.HTTPError(400, "missing url")
        touch_last_used()
        broadcast_open()
        await UPSTREAM.command("Page.navigate", {"url": url})
        self.write("ok")


def _write_dump(screenshot_b64, html, url):
    import base64
    import time

    directory = os.path.join(RUN_DIR, "dump-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "page.png"), "wb") as handle:
        handle.write(base64.b64decode(screenshot_b64 or ""))
    with open(os.path.join(directory, "page.html"), "w", errors="replace") as handle:
        handle.write(html or "")
    with open(os.path.join(directory, "url.txt"), "w") as handle:
        handle.write((url or "") + "\n")
    return directory


DUMP_COMMANDS = (
    ("Page.captureScreenshot", {"format": "png"}),
    ("Runtime.evaluate",
     {"expression": "document.documentElement.outerHTML", "returnByValue": True}),
    ("Runtime.evaluate", {"expression": "location.href", "returnByValue": True}),
)


def _dump_results(shot, html, url):
    return _write_dump(
        shot.get("data", ""),
        (html.get("result") or {}).get("value", ""),
        (url.get("result") or {}).get("value", ""),
    )


class DumpHandler(tornado.web.RequestHandler):
    """POST /dump -- support bundle of whatever the browser shows right now."""

    async def post(self):
        replies = [
            await UPSTREAM.request(method, params) for method, params in DUMP_COMMANDS
        ]
        self.write("dumped: " + _dump_results(*replies))


class HealthHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("ok")


class RootHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.write(VIEWER_HTML)


VIEWER_HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Zone Browser</title>
<style>
  html, body { margin: 0; height: 100%; }
  body { display: flex; flex-direction: column; background: #202124;
         font: 13px system-ui, sans-serif; color: #e8eaed; }
  #bar { display: flex; align-items: center; gap: 8px; padding: 6px 10px;
         background: #35363a; flex: none; }
  #bar button { background: none; border: none; color: #e8eaed; font-size: 15px;
                cursor: pointer; padding: 2px 6px; border-radius: 4px; }
  #bar button:hover { background: #5f6368; }
  #urlwrap { flex: 1; display: flex; align-items: center; gap: 6px;
             background: #202124; border: 1px solid #5f6368; border-radius: 14px;
             padding: 3px 12px; }
  #lock { color: #8ab4f8; font-size: 12px; }
  #url { flex: 1; background: none; border: none; outline: none;
         color: #e8eaed; font: 13px system-ui, sans-serif; }
  #badge { flex: none; font-size: 11px; color: #9aa0a6; }
  #view { flex: 1; position: relative; overflow: hidden; background: #000;
          outline: none; }
  #screen { position: absolute; inset: 0; width: 100%; height: 100%;
            user-select: none; -webkit-user-drag: none; }
  #msg { position: absolute; inset: 0; display: flex; align-items: center;
         justify-content: center; color: #9aa0a6; background: #202124; }
  #wia { position: absolute; top: 16px; left: 50%; transform: translateX(-50%);
         display: none; max-width: 560px; background: #35363a; color: #e8eaed;
         border: 1px solid #5f6368; border-radius: 8px; padding: 14px 16px;
         box-shadow: 0 4px 16px rgba(0,0,0,.4); font-size: 13px;
         line-height: 1.5; z-index: 5; }
  #wia button { margin: 10px 8px 0 0; padding: 5px 12px; border-radius: 4px;
                border: 1px solid #5f6368; background: #8ab4f8; color: #202124;
                font: inherit; cursor: pointer; }
  #wia button.quiet { background: none; color: #e8eaed; }
</style>
</head>
<body>
<div id="bar">
  <button id="back" title="Back">&#8592;</button>
  <button id="reload" title="Reload">&#8635;</button>
  <div id="urlwrap"><span id="lock">&#128274;</span>
    <input id="url" spellcheck="false" autocomplete="off"></div>
  <span id="badge">secure browser &mdash; runs inside your workspace</span>
</div>
<div id="view" tabindex="0">
  <img id="screen" draggable="false" alt="">
  <div id="msg">Starting the in-workspace browser&hellip;</div>
  <div id="wia">
    <strong>This sign-in page needs Windows authentication.</strong><br>
    GC SSO tried a silent Windows (Kerberos) sign-in, which a notebook
    workspace cannot complete &mdash; that is why the page below is blank.
    <br>
    <button id="wia-try">Try the standard sign-in page</button>
    <button id="wia-close" class="quiet">Dismiss</button><br>
    If that also fails, ask your administrator to set
    <code>ZONE_BROWSER_UA</code> (see azure-sign-in.md in your home folder).
  </div>
</div>
<script>
(function () {
  "use strict";
  var view = document.getElementById("view");
  var screen = document.getElementById("screen");
  var msg = document.getElementById("msg");
  var urlBox = document.getElementById("url");
  var lock = document.getElementById("lock");

  var base = location.pathname.replace(/[^/]*$/, "");
  var proto = location.protocol === "https:" ? "wss://" : "ws://";
  var ws = new WebSocket(proto + location.host + base + "ws");

  var nextId = 1;
  var pending = {};
  function send(method, params, cb) {
    if (ws.readyState !== 1) {
      // a click on a dead connection must not die silently -- but never
      // clobber a more specific message (e.g. "view moved to a newer tab")
      if (ws.readyState > 1 && msg.style.display === "none") {
        msg.textContent = "Disconnected. Reload this tab to reconnect.";
        msg.style.display = "flex";
      }
      return;
    }
    var id = nextId++;
    if (cb) pending[id] = cb;
    ws.send(JSON.stringify({ id: id, method: method, params: params || {} }));
  }

  var W = 0, H = 0;
  function fit() {
    var r = view.getBoundingClientRect();
    var w = Math.max(320, Math.floor(r.width));
    var h = Math.max(240, Math.floor(r.height));
    if (w === W && h === H) return;
    W = w; H = h;
    // Always render and capture at 2x: on standard-DPI monitors the frame
    // is downscaled in the tab (supersampled, crisp text); on retina it is
    // native. 1x capture reads as blurry/"fake".
    var dpr = 2;
    send("Emulation.setDeviceMetricsOverride",
         { width: W, height: H, deviceScaleFactor: dpr, mobile: false });
    send("Page.stopScreencast");
    send("Page.startScreencast",
         { format: "jpeg", quality: 90,
           maxWidth: Math.floor(W * dpr), maxHeight: Math.floor(H * dpr) });
  }
  var fitTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(fitTimer);
    fitTimer = setTimeout(fit, 150);
  });

  var wiaBox = document.getElementById("wia");
  var wiaUrl = "";
  function checkWia(u) {
    // ADFS served its Windows-Integrated-Auth endpoint, which dead-ends in
    // a pod (no Kerberos): explain the blank page and offer the forms
    // endpoint (same URL without /wia) as a one-click recovery attempt.
    if (u.indexOf("/adfs/ls/wia") !== -1) {
      wiaUrl = u;
      wiaBox.style.display = "block";
    } else {
      wiaBox.style.display = "none";
    }
  }
  document.getElementById("wia-try").addEventListener("click", function () {
    if (wiaUrl) send("Page.navigate",
                     { url: wiaUrl.replace("/adfs/ls/wia", "/adfs/ls/") });
    wiaBox.style.display = "none";
    view.focus();
  });
  document.getElementById("wia-close").addEventListener("click", function () {
    wiaBox.style.display = "none";
    view.focus();
  });

  function setUrl(u) {
    if (document.activeElement !== urlBox) urlBox.value = u;
    lock.innerHTML = /^https:/.test(u) ? "&#128274;" : "&#9888;&#65039;";
    checkWia(u);
  }

  function refreshUrl() {
    send("Page.getNavigationHistory", {}, function (res) {
      if (res && res.entries && res.entries[res.currentIndex])
        setUrl(res.entries[res.currentIndex].url);
    });
  }

  function rearm() {
    // (re)subscribe events and restart the screencast -- used at open and
    // whenever the bridge moves to another browser tab
    send("Page.enable");
    W = 0; H = 0;
    fit();
    refreshUrl();
  }

  ws.onopen = function () {
    rearm();
    // the CLI may have navigated just before this viewer attached
    setTimeout(refreshUrl, 1500);
    setTimeout(refreshUrl, 4000);
    view.focus();
  };

  ws.onmessage = function (ev) {
    var m;
    try { m = JSON.parse(ev.data); } catch (e) { return; }
    if (m.id && pending[m.id]) {
      var cb = pending[m.id];
      delete pending[m.id];
      cb(m.result);
      return;
    }
    if (m.method === "Page.screencastFrame") {
      screen.src = "data:image/jpeg;base64," + m.params.data;
      msg.style.display = "none";
      send("Page.screencastFrameAck", { sessionId: m.params.sessionId });
    } else if (m.method === "Page.frameNavigated") {
      if (!m.params.frame.parentId) setUrl(m.params.frame.url);
    } else if (m.method === "Page.loadEventFired" ||
               m.method === "Page.navigatedWithinDocument") {
      refreshUrl();
    } else if (m.method === "Page.javascriptDialogOpening") {
      send("Page.handleJavaScriptDialog", { accept: true });
    } else if (m.method === "ZoneBrowser.targetChanged") {
      // the sign-in continued in a new browser tab and the bridge followed
      // it (or reattached after a restart): re-arm on the new page
      rearm();
    } else if (m.method === "ZoneBrowser.browserGone") {
      wiaBox.style.display = "none";
      msg.textContent = "The in-workspace browser stopped (idle timeout). " +
                        "Run az login again, or reload this tab.";
      msg.style.display = "flex";
    }
  };

  ws.onclose = function (ev) {
    msg.textContent = (ev.code === 4000)
      ? "This view moved to a newer Zone Browser tab."
      : "Disconnected. Reload this tab to reconnect.";
    msg.style.display = "flex";
  };

  function mods(e) {
    return (e.altKey ? 1 : 0) | (e.ctrlKey ? 2 : 0) |
           (e.metaKey ? 4 : 0) | (e.shiftKey ? 8 : 0);
  }
  function pos(e) {
    var r = screen.getBoundingClientRect();
    return { x: Math.max(0, Math.round(e.clientX - r.left)),
             y: Math.max(0, Math.round(e.clientY - r.top)) };
  }
  var BUTTONS = ["left", "middle", "right", "back", "forward"];
  function mouse(type, e, extra) {
    var p = pos(e);
    var ev = { type: type, x: p.x, y: p.y, modifiers: mods(e),
               button: BUTTONS[e.button] || "none", buttons: e.buttons,
               clickCount: type === "mousePressed" ? (e.detail || 1) : 0 };
    if (extra) for (var k in extra) ev[k] = extra[k];
    send("Input.dispatchMouseEvent", ev);
  }
  view.addEventListener("mousedown", function (e) {
    view.focus(); e.preventDefault(); mouse("mousePressed", e);
  });
  view.addEventListener("mouseup", function (e) {
    e.preventDefault(); mouse("mouseReleased", e);
  });
  view.addEventListener("mousemove", function (e) { mouse("mouseMoved", e); });
  view.addEventListener("wheel", function (e) {
    e.preventDefault();
    mouse("mouseWheel", e, { deltaX: -e.deltaX, deltaY: -e.deltaY,
                             button: "none", clickCount: 0 });
  }, { passive: false });
  view.addEventListener("contextmenu", function (e) { e.preventDefault(); });

  function key(type, e) {
    var ev = { type: type, modifiers: mods(e), code: e.code, key: e.key,
               windowsVirtualKeyCode: e.keyCode, nativeVirtualKeyCode: e.keyCode,
               autoRepeat: !!e.repeat, isKeypad: e.location === 3,
               location: e.location };
    if (type === "keyDown") {
      if (e.key.length === 1) { ev.text = e.key; ev.unmodifiedText = e.key; }
      else if (e.key === "Enter") { ev.text = "\r"; ev.unmodifiedText = "\r"; }
    }
    return ev;
  }
  view.addEventListener("keydown", function (e) {
    e.preventDefault();
    var typing = (e.key.length === 1 || e.key === "Enter") &&
                 !e.ctrlKey && !e.metaKey && !e.altKey;
    send("Input.dispatchKeyEvent", key(typing ? "keyDown" : "rawKeyDown", e));
  });
  view.addEventListener("keyup", function (e) {
    e.preventDefault();
    send("Input.dispatchKeyEvent", key("keyUp", e));
  });
  document.addEventListener("paste", function (e) {
    if (document.activeElement !== view) return;
    var text = e.clipboardData.getData("text");
    if (text) send("Input.insertText", { text: text });
    e.preventDefault();
  });

  urlBox.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    var u = urlBox.value.trim();
    if (!u) return;
    if (!/^[a-z]+:\/\//i.test(u)) u = "https://" + u;
    send("Page.navigate", { url: u });
    view.focus();
  });
  document.getElementById("reload").addEventListener("click", function () {
    send("Page.reload", {}); view.focus();
  });
  document.getElementById("back").addEventListener("click", function () {
    send("Page.getNavigationHistory", {}, function (res) {
      if (res && res.currentIndex > 0)
        send("Page.navigateToHistoryEntry",
             { entryId: res.entries[res.currentIndex - 1].id });
    });
    view.focus();
  });
})();
</script>
</body>
</html>
"""


def dump_oneshot():
    """--dump without a running bridge: talk to the page target directly."""
    pages = list_pages()
    if not pages:
        raise SystemExit("zone-browser-viewer: no page target (is Chromium running?)")

    async def go():
        conn = await websocket_connect(
            pages[0]["webSocketDebuggerUrl"], max_message_size=64 * 1024 * 1024
        )
        for request_id, (method, params) in enumerate(DUMP_COMMANDS, start=1):
            await conn.write_message(
                json.dumps({"id": request_id, "method": method, "params": params})
            )
        replies = {}
        while len(replies) < len(DUMP_COMMANDS):
            msg = await conn.read_message()
            if msg is None:
                raise SystemExit("zone-browser-viewer: browser connection closed")
            data = json.loads(msg)
            if data.get("id") in range(1, len(DUMP_COMMANDS) + 1):
                replies[data["id"]] = data.get("result", {})
        conn.close()
        return [replies[i] for i in range(1, len(DUMP_COMMANDS) + 1)]

    print("dumped: " + _dump_results(*asyncio.run(go())))


def navigate_oneshot(url):
    """Point the browser at url without a running bridge (single use)."""
    pages = list_pages()
    if not pages:
        req = urllib.request.Request(
            f"{CDP}/json/new?{urllib.parse.urlencode({'url': url})}", method="PUT"
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        return

    async def go():
        conn = await websocket_connect(pages[0]["webSocketDebuggerUrl"])
        await conn.write_message(
            json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}})
        )
        await conn.read_message()
        conn.close()

    asyncio.run(go())


def serve(port):
    app = tornado.web.Application(
        [
            (r"/", RootHandler),
            (r"/index\.html", RootHandler),
            (r"/ws", WSHandler),
            (r"/events", EventsHandler),
            (r"/open", OpenHandler),
            (r"/dump", DumpHandler),
            (r"/healthz", HealthHandler),
        ],
        websocket_max_message_size=64 * 1024 * 1024,
    )
    app.listen(port, address="127.0.0.1")
    tornado.ioloop.IOLoop.current().start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--serve", type=int, metavar="PORT")
    group.add_argument("--navigate", metavar="URL")
    group.add_argument("--dump", action="store_true")
    args = parser.parse_args()
    if args.navigate:
        navigate_oneshot(args.navigate)
    elif args.dump:
        dump_oneshot()
    else:
        serve(args.serve)


if __name__ == "__main__":
    sys.exit(main())

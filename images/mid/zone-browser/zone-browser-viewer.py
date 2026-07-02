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
    """The single shared CDP connection to the Chromium page target."""

    def __init__(self):
        self.conn = None
        self.clients = set()
        self.next_id = BRIDGE_ID_BASE

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
        self.conn = await websocket_connect(
            pages[0]["webSocketDebuggerUrl"], max_message_size=64 * 1024 * 1024
        )
        asyncio.ensure_future(self._pump())
        return self.conn

    async def _pump(self):
        conn = self.conn
        while True:
            msg = await conn.read_message()
            if msg is None:
                break
            try:
                mid = json.loads(msg).get("id")
            except (ValueError, AttributeError):
                mid = None
            if isinstance(mid, int) and mid >= BRIDGE_ID_BASE:
                continue
            for client in list(self.clients):
                try:
                    client.write_message(msg)
                except tornado.websocket.WebSocketClosedError:
                    self.clients.discard(client)
        self.conn = None
        for client in list(self.clients):
            try:
                client.write_message(json.dumps({"method": "ZoneBrowser.browserGone"}))
            except tornado.websocket.WebSocketClosedError:
                pass

    async def command(self, method, params):
        conn = await self.ensure()
        self.next_id += 1
        await conn.write_message(
            json.dumps({"id": self.next_id, "method": method, "params": params})
        )


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


class OpenHandler(tornado.web.RequestHandler):
    """POST /open (url=...) -- used by the zone-browser CLI, e.g. az login."""

    async def post(self):
        url = self.get_body_argument("url", self.get_query_argument("url", None))
        if not url:
            raise tornado.web.HTTPError(400, "missing url")
        touch_last_used()
        await UPSTREAM.command("Page.navigate", {"url": url})
        self.write("ok")


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
    if (ws.readyState !== 1) return;
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
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    send("Emulation.setDeviceMetricsOverride",
         { width: W, height: H, deviceScaleFactor: dpr, mobile: false });
    send("Page.stopScreencast");
    send("Page.startScreencast",
         { format: "jpeg", quality: 80,
           maxWidth: Math.floor(W * dpr), maxHeight: Math.floor(H * dpr) });
  }
  var fitTimer = null;
  window.addEventListener("resize", function () {
    clearTimeout(fitTimer);
    fitTimer = setTimeout(fit, 150);
  });

  function setUrl(u) {
    if (document.activeElement !== urlBox) urlBox.value = u;
    lock.innerHTML = /^https:/.test(u) ? "&#128274;" : "&#9888;&#65039;";
  }

  ws.onopen = function () {
    send("Page.enable");
    send("Page.getNavigationHistory", {}, function (res) {
      if (res && res.entries && res.entries[res.currentIndex])
        setUrl(res.entries[res.currentIndex].url);
    });
    fit();
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
    } else if (m.method === "Page.javascriptDialogOpening") {
      send("Page.handleJavaScriptDialog", { accept: true });
    } else if (m.method === "ZoneBrowser.browserGone") {
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
            (r"/open", OpenHandler),
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
    args = parser.parse_args()
    if args.navigate:
        navigate_oneshot(args.navigate)
    else:
        serve(args.serve)


if __name__ == "__main__":
    sys.exit(main())

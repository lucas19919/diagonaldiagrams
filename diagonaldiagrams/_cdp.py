"""One headless Edge or Chrome kept open over DevTools, for drawing many frames (DESIGN 21.2.1).

A browser launch costs 1-2 s, more on a busy machine. Filming draws a hundred frames that differ
only in a small layer, so the browser starts once, loads the figure once in each of a few windows,
and each frame swaps the layer and takes a screenshot. The windows work at the same time. The
browser is driven over the DevTools protocol, through the small WebSocket client below (standard
library only, D1). Anything that goes wrong raises OSError, and the caller falls back to one
launch per sheet (export._raster_svg).
"""
import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _mask(data, key):
    n = len(data)
    return (int.from_bytes(data, "big") ^ int.from_bytes((key * (n // 4 + 1))[:n], "big")).to_bytes(n, "big")


class _WebSocket:
    """A client WebSocket (RFC 6455): text messages, masked as a client must, no extensions."""

    def __init__(self, url, timeout):
        u = urllib.parse.urlsplit(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.file = self.sock.makefile("rb")
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = []
        while True:
            line = self.file.readline()
            if not line:
                raise OSError("DevTools closed the connection during the handshake")
            if line in (b"\r\n", b"\n"):
                break
            head.append(line.decode("latin-1").strip().lower())
        accept = base64.b64encode(hashlib.sha1((key + _GUID).encode()).digest()).decode().lower()
        if not head or head[0].split()[1:2] != ["101"] or f"sec-websocket-accept: {accept}" not in head:
            raise OSError(f"DevTools refused the WebSocket: {head[0] if head else 'no answer'}")

    def _frame(self, op, data):
        n = len(data)
        head = bytes([0x80 | op]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + n.to_bytes(2, "big") if n < 65536
                                       else bytes([0x80 | 127]) + n.to_bytes(8, "big"))
        key = os.urandom(4)
        self.sock.sendall(head + key + _mask(data, key))

    def send(self, text):
        self._frame(1, text.encode("utf-8"))

    def _read(self, n):
        data = self.file.read(n)
        if len(data) != n:
            raise OSError("DevTools closed the connection")
        return data

    def recv(self):
        parts = []
        while True:
            b0, b1 = self._read(2)
            op, n = b0 & 15, b1 & 127
            if n >= 126:
                n = int.from_bytes(self._read(2 if n == 126 else 8), "big")
            key = self._read(4) if b1 & 0x80 else None
            data = self._read(n)
            if key:
                data = _mask(data, key)
            if op == 8:
                raise OSError("DevTools closed the connection")
            if op == 9:
                self._frame(10, data)
            if op in (0, 1, 2):
                parts.append(data)
                if b0 & 0x80:
                    return b"".join(parts).decode("utf-8")

    def close(self):
        for f in (self.file.close, self.sock.close):
            try:
                f()
            except OSError:
                pass


class Browser:
    """A headless browser with `pages` windows of w x h, open until close(). pages holds each
    window's session id, for calls()."""

    def __init__(self, path, w, h, pages=1, timeout=30):
        self.timeout, self.next_id, self.proc, self.drain, self.ws, self.pages = timeout, 0, None, None, None, []
        self.profile = tempfile.mkdtemp(prefix="dd-devtools-")
        try:
            try:
                self._start(path, w, h, max(1, pages))
            except OSError as e:
                from .export import _sandbox_refused
                if self.proc is None or self.proc.poll() is None or not _sandbox_refused(str(e)):
                    raise
                self.close()  # it never started: once more without the sandbox, in a fresh profile
                self.proc = self.drain = None
                self.profile = tempfile.mkdtemp(prefix="dd-devtools-")
                self._start(path, w, h, max(1, pages), ["--no-sandbox"])
        except BaseException:
            self.close()
            raise

    def _start(self, path, w, h, pages, flags=()):
        cmd = [path, "--headless=new", "--disable-gpu", *flags, "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", "--mute-audio", "--remote-debugging-port=0", f"--user-data-dir={self.profile}",
               f"--window-size={w},{h}", "about:blank"]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        found, lines = [], []

        def drain():  # read stderr to its end, so the browser never blocks on a full pipe
            for raw in self.proc.stderr:
                line = raw.decode("utf-8", "replace").strip()
                if not found and line.startswith("DevTools listening on ws://"):
                    found.append(line.split(" on ", 1)[1])
                elif len(lines) < 20:
                    lines.append(line)
        self.drain = threading.Thread(target=drain, daemon=True)
        self.drain.start()
        deadline = time.time() + self.timeout
        while not found:
            if self.proc.poll() is not None:
                raise OSError(f"{os.path.basename(path)} exited ({self.proc.returncode}): {' / '.join(lines[-2:])}")
            if time.time() > deadline:
                raise OSError(f"{os.path.basename(path)} did not open DevTools in {self.timeout} s")
            time.sleep(0.02)
        self.ws = _WebSocket(found[0], self.timeout)
        # a window of its own for each page: a background tab is never painted, so it never screenshots
        made = self.calls([(None, "Target.createTarget", {"url": "about:blank", "newWindow": True, "width": w, "height": h})] * pages)
        self.pages = [r["sessionId"] for r in self.calls([(None, "Target.attachToTarget", {"targetId": m["targetId"], "flatten": True})
                                                          for m in made])]

    def calls(self, cmds, until=None, meanwhile=None):
        """[(session or None for the browser, method, params)], sent together; their results, in
        order. With until, also waits for that event from each of their sessions. meanwhile()
        runs once the commands are sent, while the browser works on them."""
        ids, waiting = {}, set()
        for session, method, params in cmds:
            self.next_id += 1
            ids[self.next_id] = (len(ids), method)
            msg = {"id": self.next_id, "method": method, "params": params or {}}
            if session:
                msg["sessionId"] = session
                if until:
                    waiting.add(session)
            self.ws.send(json.dumps(msg))
        if meanwhile:
            meanwhile()
        out = [None] * len(cmds)
        left = len(cmds)
        while left or waiting:
            m = json.loads(self.ws.recv())
            if m.get("id") in ids:
                k, method = ids.pop(m["id"])
                if "error" in m:
                    raise OSError(f"DevTools {method}: {m['error'].get('message', m['error'])}")
                out[k], left = m.get("result", {}), left - 1
            elif until and m.get("method") == until:
                waiting.discard(m.get("sessionId"))
        return out

    def everywhere(self, method, params=None, until=None):
        return self.calls([(p, method, params) for p in self.pages], until=until)

    def load(self, html, w, h):
        """Shows the page in every window, at w x h CSS pixels of one device pixel each, with its fonts loaded."""
        page = os.path.join(self.profile, "page.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(html)
        self.everywhere("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False})
        self.everywhere("Page.enable")
        self.everywhere("Page.navigate", {"url": "file:///" + os.path.abspath(page).replace("\\", "/")}, until="Page.loadEventFired")
        self.everywhere("Page.disable")
        self.run([(p, "document.fonts.ready.then(() => true)") for p in self.pages])

    def run(self, scripts):
        """[(page, JavaScript)], run together; their values."""
        out = self.calls([(p, "Runtime.evaluate", {"expression": js, "awaitPromise": True, "returnByValue": True}) for p, js in scripts])
        for r in out:
            if "exceptionDetails" in r:
                raise OSError(f"the page threw: {r['exceptionDetails'].get('text', '')}")
        return [r.get("result", {}).get("value") for r in out]

    def shots(self, pages, w, h, meanwhile=None):
        """A PNG of each page's top-left w x h pixels."""
        clip = {"x": 0, "y": 0, "width": w, "height": h, "scale": 1}
        out = self.calls([(p, "Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True, "clip": clip}) for p in pages],
                         meanwhile=meanwhile)
        if not all(r.get("data") for r in out):
            raise OSError("DevTools returned an empty screenshot")
        return [base64.b64decode(r["data"]) for r in out]

    def close(self):
        if self.ws:
            try:
                self.calls([(None, "Browser.close", None)])
            except (OSError, ValueError):
                pass
            self.ws.close()
        if self.proc:
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(10)
            if self.drain:
                self.drain.join(2)
            self.proc.stderr.close()
        for _ in range(10):  # the browser's children can hold the profile for a moment
            shutil.rmtree(self.profile, ignore_errors=True)
            if not os.path.exists(self.profile):
                break
            time.sleep(0.2)

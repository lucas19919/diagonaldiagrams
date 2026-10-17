"""Motion from meaning (motion.py, gif.py, web/motion.js; DESIGN 21.2.1).
Run: py -3 -m unittest discover tests/unit"""
import copy
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import gif, motion  # noqa: E402
from diagonaldiagrams.diagrams import render_arch  # noqa: E402
from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.mermaid import load_spec  # noqa: E402
from diagonaldiagrams.story import build  # noqa: E402
from diagonaldiagrams.style.styler import Styler  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKOUT = os.path.join(HERE, "examples", "checkout_platform.json")
PATH = "web -> gw -> orders -> pay -> stripe"


def checkout(block, kind="arch", spec=None):
    spec = spec or load_spec(CHECKOUT, "arch")
    svg, _, _ = render_arch(spec)
    return motion.resolve(motion.read(block), spec, kind, Styler(spec, "arch"), svg) + (svg,)


class Read(unittest.TestCase):
    def test_a_bad_block_is_an_error_with_a_fix(self):
        cases = [{"trace": "a -> b"}, [{"trace": "a -> b", "flow": "edge"}], [{"move": "a -> b"}], [{"trace": "a -> b", "speeed": 3}],
                 [{"trace": "a -> b", "speed": 0}], [{"trace": "a -> b", "speed": "fast"}], [{"trace": "a -> b", "packet": "star"}],
                 [{"trace": "web"}], [{"trace": ["web", ""]}], [{"flow": ""}], [{"flow": "edge", "hold": 2}], "web -> gw"]
        for block in cases[1:]:
            with self.assertRaises(SpecError, msg=block) as e:
                motion.read(block, "view 'v'")
            self.assertEqual(e.exception.code, "bad-motion")
            self.assertTrue(e.exception.fix)
            self.assertIn("view 'v'", e.exception.msg)
        self.assertEqual(motion.read(cases[0])[0]["path"], ["a", "b"])  # one object is a list of one

    def test_defaults_and_both_path_forms(self):
        a, b = motion.read([{"trace": "web -> gw → orders"}, {"trace": ["web", "gw", "orders"], "speed": 100, "packet": "dash"}])
        self.assertEqual(a["path"], b["path"])
        self.assertEqual((a["speed"], a["hold"], a["packet"], a["color"]), (320.0, 1.2, "dot", "accent"))
        self.assertEqual((b["speed"], b["packet"]), (100.0, "dash"))
        f = motion.read([{"flow": "edge[async]", "gap": 30}])[0]
        self.assertEqual((f["speed"], f["gap"], f["color"]), (60.0, 30.0, "link"))


class Resolve(unittest.TestCase):
    def test_the_trace_follows_the_drawn_arrows(self):
        s, warn, svg = checkout([{"trace": PATH}])
        self.assertEqual(warn, [])
        hops = s["traces"][0]["hops"]
        self.assertEqual([h["edge"] for h in hops], ["web->gw:calls", "gw->orders:checkout", "orders->pay:charge", "pay->stripe:card"])
        drawn = {a["id"]: a["pts"] for a in motion.arrows(svg)}
        for h in hops:
            self.assertEqual(h["pts"], drawn[h["edge"]])  # the route as drawn, corners and all
            self.assertTrue(h["head"])
        self.assertGreater(len(hops[0]["pts"]), 4)  # rounded corners are flattened, not cut

    def test_a_hop_may_run_against_an_arrow(self):
        s, _, svg = checkout([{"trace": "gw -> web"}])
        hop = s["traces"][0]["hops"][0]
        drawn = {a["id"]: a["pts"] for a in motion.arrows(svg)}
        self.assertEqual(hop["pts"], drawn["web->gw:calls"][::-1])
        self.assertFalse(hop["head"])  # the arrowhead stays at the arrow's own end

    def test_unknown_boxes_missing_arrows_and_other_kinds_are_errors(self):
        with self.assertRaises(SpecError) as e:
            checkout([{"trace": "web -> gw -> order"}])
        self.assertIn("did you mean 'orders'", e.exception.msg)
        with self.assertRaises(SpecError) as e:
            checkout([{"trace": "web -> gw -> pay"}])
        self.assertIn("no arrow joins gw and pay (hop 2", e.exception.msg)
        self.assertIn("orders", e.exception.fix)  # it lists where gw's arrows go
        with self.assertRaises(SpecError):
            checkout([{"trace": PATH}], kind="seq")
        with self.assertRaises(SpecError):
            checkout([{"trace": PATH, "color": "not-a-token"}])

    def test_warnings_for_an_empty_flow_and_a_doubled_hop(self):
        _, warn, _ = checkout([{"flow": "edge[from=stripe]"}])
        self.assertIn("matches no arrows", warn[0]["msg"])
        spec = {"nodes": [{"id": "a", "name": "A", "layer": 0}, {"id": "b", "name": "B", "layer": 1}],
                "edges": [{"from": "a", "to": "b", "label": "x"}, {"from": "a", "to": "b", "label": "y"}]}
        s, warn, _ = checkout([{"trace": "a -> b"}], spec=spec)
        self.assertIn("2 arrows join a and b", warn[0]["msg"])
        self.assertEqual(s["traces"][0]["hops"][0]["edge"], "a->b:x")


class Timing(unittest.TestCase):
    def setUp(self):
        self.s = checkout([{"trace": PATH}, {"flow": "edge[async]"}])[0]

    def test_hops_take_their_length_over_speed_and_rest_between(self):
        tr = self.s["traces"][0]
        hops = tr["hops"]
        self.assertAlmostEqual(hops[0]["a"], motion.LEAD)
        for h in hops:
            want = max(motion.MIN_HOP, h["cum"][-1] / 320.0)
            self.assertAlmostEqual(h["b"] - h["a"], want, places=3)
        for h0, h1 in zip(hops, hops[1:]):
            self.assertAlmostEqual(h1["a"] - h0["b"], motion.DWELL, places=3)
        self.assertEqual(tr["end"], hops[-1]["b"])
        self.assertAlmostEqual(self.s["loop"], tr["end"] + 1.2 + motion.FADE + motion.REST, places=3)
        self.assertEqual([p["t"] for p in tr["pulses"]], [0.0] + [h["b"] for h in hops])

    def test_traces_play_one_after_another_and_flows_alone_loop_in_three_seconds(self):
        s = checkout([{"trace": "web -> gw"}, {"trace": "gw -> orders"}])[0]
        a, b = s["traces"]
        self.assertEqual(b["t0"], a["dur"])
        self.assertAlmostEqual(s["loop"], a["dur"] + b["dur"], places=3)
        self.assertEqual(checkout([{"flow": "edge[async]"}])[0]["loop"], motion.FLOW_LOOP)

    def test_the_loop_has_no_seam(self):
        s = self.s
        for f in s["flows"]:
            turns = f["v"] * s["loop"] / f["gap"]
            self.assertAlmostEqual(turns, round(turns), places=4)  # a whole number of gaps per loop
        self.assertEqual(motion.at(s, 0.0), motion.at(s, s["loop"]))
        self.assertEqual(motion.at(s, 0.25), motion.at(s, s["loop"] + 0.25))

    def test_the_packet_rides_the_route_and_the_still_moment_has_none(self):
        s = self.s
        hop = s["traces"][0]["hops"][1]
        shapes = motion.at(s, (hop["a"] + hop["b"]) / 2)
        packet = [a for tag, a in shapes if tag == "circle" and a["r"] == motion.PACKET_R][0]
        self.assertLess(_distance((packet["cx"], packet["cy"]), hop["pts"]), 0.01)
        still = motion.at(s, s["still"])
        self.assertFalse([a for tag, a in still if tag == "circle" and a["r"] == motion.PACKET_R])
        lit = [a for tag, a in still if tag == "path" and a["stroke-width"] == motion.LIT_W]
        self.assertEqual(len(lit), 4)  # every hop lit, at full strength
        self.assertTrue(all(a["opacity"] == 1 for a in lit))

    def test_frame_timing(self):
        n, ts, delays = motion.times(5.5419, 20)
        self.assertEqual(n, 111)
        self.assertEqual(ts[0], 0)
        self.assertLess(ts[-1], 5.5419)  # frame n would be frame 0 again
        steps = [b - a for a, b in zip(ts, ts[1:])]
        self.assertLess(max(steps) - min(steps), 1e-9)
        self.assertEqual(sum(delays), 554)  # the rounding is spread: the loop keeps its length
        self.assertEqual(set(delays), {4, 5})  # 4.99 hundredths a frame: now and then a 4
        self.assertEqual(set(motion.times(1.0, 50)[2]), {2})
        self.assertEqual(sum(motion.times(2.343, 30)[2]), 234)
        for fps in (0, 51):
            with self.assertRaises(SpecError):
                motion.times(3, fps)

    def test_frames_are_the_figure_plus_a_layer_and_never_change_it(self):
        s, _, svg = checkout([{"trace": PATH}])
        one, two = motion.frame(svg, s, 1.5), motion.frame(svg, s, 1.5)
        self.assertEqual(one, two)
        i = svg.rindex("</svg>")
        self.assertTrue(one.startswith(svg[:i] + '<g data-motion="" aria-hidden="true"'))
        self.assertTrue(one.endswith(svg[i:]))


def _distance(p, pts):
    best = 1e9
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((p[0] - x0) * dx + (p[1] - y0) * dy) / L2))
        best = min(best, math.hypot(p[0] - x0 - t * dx, p[1] - y0 - t * dy))
    return best


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Parity(unittest.TestCase):
    def test_the_page_draws_what_the_exporter_draws(self):
        s = checkout([{"trace": PATH, "packet": "dash"}, {"trace": "stripe -> pay"}, {"flow": "edge[async]"}])[0]
        ts = [k * s["loop"] / 37 for k in range(37)]
        js = os.path.join(HERE, "diagonaldiagrams", "web", "motion.js")
        prog = ("const fs=require('fs');eval(fs.readFileSync(process.argv[1],'utf8'));"
                "const a=JSON.parse(fs.readFileSync(0,'utf8'));"
                "process.stdout.write(JSON.stringify(a.ts.map(t=>ddMotion.at(a.s,t))))")
        p = subprocess.run(["node", "-e", prog, js], input=json.dumps({"s": s, "ts": ts}), capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        for t, theirs in zip(ts, json.loads(p.stdout)):
            ours = motion.at(s, t)
            self.assertEqual([tag for tag, _ in ours], [tag for tag, _ in theirs], t)
            for (_, a), (_, b) in zip(ours, theirs):
                self.assertEqual(list(a), list(b))
                for k in a:
                    if isinstance(a[k], (int, float)):
                        self.assertAlmostEqual(a[k], b[k], places=6, msg=(t, k))
                    elif k in ("d", "points"):
                        self.assertEqual(_nums(a[k]), _nums(b[k]))
                    else:
                        self.assertEqual(a[k], b[k])


def _nums(text):
    import re
    return [round(float(v), 1) for v in re.findall(r"-?\d+\.?\d*", text)]


class Story(unittest.TestCase):
    def test_motion_rides_on_the_frames_and_leaves_them_as_they_were(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(HERE, "examples", "story_checkout.json")
            with open(path, encoding="utf-8") as f:
                story = json.load(f)
            still = copy.deepcopy(story)
            for v in still["views"]:
                v.pop("motion", None)
            still["figure"]["spec"] = CHECKOUT
            plain = os.path.join(d, "still.json")
            with open(plain, "w", encoding="utf-8") as f:
                json.dump(still, f)
            moving = build(path, os.path.join(d, "moving.html"))
            calm = build(plain, os.path.join(d, "still.html"))
            self.assertTrue(moving["ok"], moving)
            self.assertEqual(moving["views"][1]["motion"], {"loop": 5.5419, "traces": 1, "flows": 5})
            self.assertNotIn("motion", calm["views"][1])
            pages = []
            for name in ("moving.html", "still.html"):
                with open(os.path.join(d, name), encoding="utf-8") as f:
                    page = f.read()
                pages.append(json.loads(page.split('id="dd-story">', 1)[1].split("</script>", 1)[0]))
            self.assertEqual([f["svg"] for f in pages[0]["frames"]], [f["svg"] for f in pages[1]["frames"]])
            self.assertNotIn("data-motion", pages[0]["frames"][1]["svg"])
            self.assertIn("motion", pages[0]["frames"][1])
            with self.assertRaises(SpecError):  # nothing moves in the first view
                build(path, os.path.join(d, "x.html"), gif=os.path.join(d, "x.gif"), view="platform")


# ---- the GIF and PNG coders -------------------------------------------------------------------

def _png(path, w, h, rows, bpp=3, filters=(0, 1, 2, 3, 4)):
    """A PNG whose rows use each filter type in turn (rows: bytes of w * bpp)."""
    out, prior = bytearray(), bytes(w * bpp)
    for r, row in enumerate(rows):
        ft = filters[r % len(filters)]
        line = bytearray(len(row))
        for i in range(len(row)):
            a = row[i - bpp] if i >= bpp else 0
            b = prior[i]
            c = prior[i - bpp] if i >= bpp else 0
            pred = (0, a, b, (a + b) // 2, _paeth(a, b, c))[ft]
            line[i] = (row[i] - pred) & 255
        out += bytes([ft]) + line
        prior = row

    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2 if bpp == 3 else 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes(out))) + chunk(b"IEND", b""))


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def _lzw_decode(data, mcs):
    clear, eoi = 1 << mcs, (1 << mcs) + 1
    acc, pos, total = int.from_bytes(data, "little"), 0, len(data) * 8
    size, nxt, table, prev, out = mcs + 1, eoi + 1, {i: [i] for i in range(clear)}, None, []
    while pos + size <= total:
        code = (acc >> pos) & ((1 << size) - 1)
        pos += size
        if code == clear:
            size, nxt, table, prev = mcs + 1, eoi + 1, {i: [i] for i in range(clear)}, None
            continue
        if code == eoi:
            return out
        if prev is None:
            entry = table[code]
        elif code in table:
            entry = table[code]
        elif code == nxt:
            entry = prev + [prev[0]]
        else:
            raise ValueError(f"code {code} before it exists")
        out += entry
        if prev is not None and nxt < 4096:
            table[nxt] = prev + [entry[0]]
            nxt += 1
            if nxt == (1 << size) and size < 12:
                size += 1
        prev = entry
    raise ValueError("no end code")


def _gif_decode(data):
    """(w, h, loop, [(delay, [rgb per pixel])]): a plain GIF reader, written apart from gif.py."""
    assert data[:6] == b"GIF89a"
    w, h, packed = struct.unpack("<HHB", data[6:11])
    pos, pal = 13, None
    if packed & 0x80:
        n = 3 * (2 << (packed & 7))
        pal, pos = data[pos:pos + n], pos + n
    canvas, frames, loop, gce = [0] * (w * h), [], None, None

    def blocks(pos):
        out = []
        while data[pos]:
            out.append(data[pos + 1:pos + 1 + data[pos]])
            pos += 1 + data[pos]
        return out, pos + 1
    while True:
        b = data[pos]
        pos += 1
        if b == 0x3B:
            return w, h, loop, frames
        if b == 0x21:
            label = data[pos]
            got, pos = blocks(pos + 1)
            if label == 0xF9:
                p = got[0]
                gce = {"transparent": p[3] if p[0] & 1 else None, "delay": p[1] | p[2] << 8, "disposal": (p[0] >> 2) & 7}
            elif label == 0xFF and got[0] == b"NETSCAPE2.0":
                loop = got[1][1] | got[1][2] << 8
        elif b == 0x2C:
            x, y, iw, ih, ip = struct.unpack("<HHHHB", data[pos:pos + 9])
            mcs = data[pos + 9]
            got, pos = blocks(pos + 10)
            idx = _lzw_decode(b"".join(got), mcs)
            assert len(idx) == iw * ih and gce["disposal"] == 1
            for j in range(ih):
                for i in range(iw):
                    v = idx[j * iw + i]
                    if v != gce["transparent"]:
                        canvas[(y + j) * w + x + i] = v
            frames.append((gce["delay"], [tuple(pal[3 * v:3 * v + 3]) for v in canvas]))
        else:
            raise ValueError(f"block {b:#x}")


def _frame(w, h, dot, color=(235, 108, 54)):
    rows = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            on = dot and abs(x - dot[0]) <= 1 and abs(y - dot[1]) <= 1
            row += bytes(color if on else ((245, 245, 245) if x < w // 2 else (46, 90, 168)))
        rows.append(bytes(row))
    return gif.Frame(w, h, rows, None, None)


class Coders(unittest.TestCase):
    def test_png_rows_decode_under_every_filter(self):
        with tempfile.TemporaryDirectory() as d:
            w, h = 23, 11
            for bpp in (3, 4):
                rows = [bytes((x * 37 + y * 11 + c * 5) % 256 for x in range(w) for c in range(bpp)) for y in range(h)]
                path = os.path.join(d, f"t{bpp}.png")
                _png(path, w, h, rows, bpp)
                f = gif.read_png(path)
                rgb = [bytes(v for i, v in enumerate(r) if i % bpp < 3) for r in rows]
                self.assertEqual(f.rows, rgb)

    def test_a_sheet_decodes_each_frame_against_the_one_above(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = _frame(30, 12, (5, 5)), _frame(30, 12, (9, 5))
            path = os.path.join(d, "sheet.png")
            _png(path, 30, 36, a.rows + b.rows + b.rows)
            sheet = gif.read_png(path, period=12)
            one, two, three = gif.split(sheet, 12)
            self.assertEqual((one.rows, two.rows, three.rows), (a.rows, b.rows, b.rows))
            self.assertTrue(all(x is y for x, y in zip(two.rows, three.rows)))  # matched rows are reused, not decoded again
            again = gif.read_png(path, like=sheet, period=12)
            self.assertEqual(again.rows, sheet.rows)
            gif.write_png(path, one)
            self.assertEqual(gif.read_png(path).rows, a.rows)
            with open(path, "rb") as f:  # a screenshot arrives as bytes, not a file
                self.assertEqual(gif.read_png(f.read(), like=two, period=12).rows, a.rows)

    def test_the_gif_holds_every_frame_with_its_delay_and_loops(self):
        frames = [_frame(40, 30, (8, 10)), _frame(40, 30, (12, 10)), _frame(40, 30, (12, 10)), _frame(40, 30, None)]
        data, n = gif.encode(frames, [5, 6, 7, 8])
        self.assertEqual(n, 3)  # the repeated frame adds its delay to the one before
        w, h, loop, got = _gif_decode(data)
        self.assertEqual((w, h, loop), (40, 30, 0))
        self.assertEqual([dl for dl, _ in got], [5, 13, 8])
        for (_, px), f in zip(got, (frames[0], frames[1], frames[3])):
            want = [tuple(r[3 * x:3 * x + 3]) for r in f.rows for x in range(f.w)]
            self.assertEqual(px, want)

    def test_lzw_survives_a_full_table(self):
        seed, rows = 7, []
        for y in range(120):
            row = bytearray()
            for x in range(200):
                seed = (seed * 1103515245 + 12345) % 2 ** 31
                k = seed % 180
                row += bytes((k, (k * 7) % 256, (k * 13) % 256))
            rows.append(bytes(row))
        f = gif.Frame(200, 120, rows, None, None)
        data, _ = gif.encode([f], [10])
        _, _, _, got = _gif_decode(data)
        self.assertEqual(got[0][1], [tuple(r[3 * x:3 * x + 3]) for r in rows for x in range(200)])

    def test_frames_stack_into_one_sheet(self):
        s, _, svg = checkout([{"trace": PATH}])
        both = motion.sheet([motion.frame(svg, s, 0.5), motion.frame(svg, s, 1.0)], 1054, 869)
        self.assertTrue(both.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1054 1738" width="1054">'))
        self.assertEqual(both.count('x="0" y="869" height="869">'), 1)


# ---- filming: one browser kept open, or a launch per sheet ------------------------------------

def _serve_websocket(script):
    """A one-connection WebSocket server on localhost: (port, thread, log). script(conn, recv, send)
    plays the server's side; recv returns (opcode, payload, masked), send(op, data, fin)."""
    import base64
    import hashlib
    import socket
    import threading
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    log = {}

    def run():
        conn, _ = srv.accept()
        f = conn.makefile("rb")
        head = []
        while True:
            line = f.readline().decode().strip()
            if not line:
                break
            head.append(line)
        key = next(h.split(":", 1)[1].strip() for h in head if h.lower().startswith("sec-websocket-key:"))
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        conn.sendall(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                     f"Sec-WebSocket-Accept: {accept}\r\n\r\n".encode())
        log["head"] = head

        def recv():
            b0, b1 = f.read(2)
            n = b1 & 127
            if n >= 126:
                n = int.from_bytes(f.read(2 if n == 126 else 8), "big")
            mask = f.read(4) if b1 & 0x80 else b""
            data = f.read(n)
            if mask:
                data = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
            return b0 & 15, data, bool(mask)

        def send(op, data, fin=True):
            n = len(data)
            size = bytes([n]) if n < 126 else bytes([126]) + n.to_bytes(2, "big") if n < 65536 else bytes([127]) + n.to_bytes(8, "big")
            conn.sendall(bytes([(0x80 if fin else 0) | op]) + size + data)
        try:
            script(conn, recv, send, log)
        finally:
            conn.close()
            srv.close()
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv.getsockname()[1], t, log


class Filming(unittest.TestCase):
    def test_the_websocket_client_masks_frames_and_reads_every_length(self):
        from diagonaldiagrams import _cdp
        texts = ["hi", "é" * 70, "x" * 126, "y" * 70000]  # 7-bit, 7-bit in UTF-8 bytes, 16-bit and 64-bit lengths

        def script(conn, recv, send, log):
            log["masked"], log["pong"] = [], None
            for k in range(len(texts)):
                op, data, masked = recv()
                log["masked"].append(masked)
                if k == 1:  # a ping before the answer, which the client must answer
                    send(9, b"are you there")
                    log["pong"] = recv()
                if k == 2:  # an answer in two fragments
                    send(1, data[:50], fin=False)
                    send(0, data[50:])
                else:
                    send(1, data)
            send(8, b"")
        port, t, log = _serve_websocket(script)
        ws = _cdp._WebSocket(f"ws://127.0.0.1:{port}/devtools/browser/x", 10)
        try:
            for text in texts:
                ws.send(text)
                self.assertEqual(ws.recv(), text)
            with self.assertRaises(OSError):  # the server closed it
                ws.recv()
        finally:
            ws.close()
        t.join(10)
        self.assertEqual(log["masked"], [True] * 4)  # a client masks every frame
        self.assertEqual(log["pong"], (10, b"are you there", True))
        self.assertIn("GET /devtools/browser/x HTTP/1.1", log["head"])

    def test_film_takes_the_open_browser_and_falls_back_to_a_launch_per_sheet(self):
        from unittest import mock
        from diagonaldiagrams import export
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 6" width="8"></svg>'
        s = {"loop": 1.0, "still": 0.0, "paper": "#fff", "flows": [], "traces": []}
        frames = [_frame(8, 6, (k + 1, 2)) for k in range(4)]
        sheets = []

        def raster(text, dest, kind, width, scale=2):
            sheets.append(text)
            _png(dest, 8, 24, [r for f in frames for r in f.rows], filters=(0,))
            return "browser", ""
        with tempfile.TemporaryDirectory() as d, mock.patch.object(export, "_browser", return_value="msedge"), \
                mock.patch.object(export, "_raster_svg", raster), mock.patch.object(motion, "_cairo", return_value=False):
            with mock.patch.object(motion, "_shoot", return_value=frames) as shoot:
                out = motion.film(svg, s, fps=4, gif=os.path.join(d, "a.gif"))
            self.assertEqual((out["raster"], out["frames"], out["gif_frames"], sheets), ("devtools", 4, 4, []))
            self.assertEqual(shoot.call_args.args[3], [0.0, 0.25, 0.5, 0.75])  # the frames' times
            with mock.patch.object(motion, "_shoot", side_effect=OSError("DevTools refused the WebSocket")):
                out = motion.film(svg, s, fps=4, gif=os.path.join(d, "b.gif"))
            self.assertEqual((out["raster"], out["sheets"], out["gif_frames"], len(sheets)), ("browser", 1, 4, 1))
            self.assertIn("refused", out["devtools_error"])
            with open(os.path.join(d, "a.gif"), "rb") as a, open(os.path.join(d, "b.gif"), "rb") as b:
                self.assertEqual(a.read(), b.read())  # the same frames make the same file either way

    def test_one_open_browser_draws_each_frame_as_a_launch_of_its_own_would(self):
        from diagonaldiagrams import export
        browser = export._browser()
        if not browser:
            self.skipTest("no Edge or Chrome on this machine")
        s, _, svg = checkout([{"trace": PATH}, {"flow": "edge[async]"}])
        ts = [0.6, 1.9, 2.4]
        got = motion._shoot(browser, svg, s, ts, None, 1054, 869, pages=2)
        self.assertEqual([(f.w, f.h) for f in got], [(1054, 869)] * 3)
        self.assertGreater(sum(a != b for a, b in zip(got[0].rows, got[1].rows)), 20)  # the packet moved
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "alone.png")
            how, why = export._raster_svg(motion.frame(svg, s, ts[1]), path, "png", 1054, scale=1)
            self.assertEqual(how, "browser", why)
            alone = gif.read_png(path)
        differ = sum(a != b for ra, rb in zip(alone.rows, got[1].rows) if ra != rb
                     for a, b in zip(_px(ra), _px(rb)))
        self.assertLess(differ, 200)  # antialiasing at most: 1054 x 869 is 915,926 pixels


def _px(row):
    return [row[i:i + 3] for i in range(0, len(row), 3)]


if __name__ == "__main__":
    unittest.main()

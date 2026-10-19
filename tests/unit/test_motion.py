"""Motion from meaning (motion.py, web/motion.js; DESIGN 21.2.1).
Run: py -3 -m unittest discover tests/unit"""
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import motion  # noqa: E402
from diagonaldiagrams.diagrams import render_arch  # noqa: E402
from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.mermaid import load_spec  # noqa: E402
from diagonaldiagrams.story import build  # noqa: E402
from diagonaldiagrams.style.styler import Styler  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKOUT = os.path.join(HERE, "examples", "checkout_platform.json")
PATH = "web -> gw -> orders -> pay -> stripe"
SVG_G = "{http://www.w3.org/2000/svg}g"


def _rasterizes():
    """cairosvg, Edge or Chrome: what the PNG export path draws with."""
    try:
        import cairosvg  # noqa: F401
        return True
    except (ImportError, OSError):
        from diagonaldiagrams.export import _browser
        return _browser() is not None


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
        n, ts = motion.times(5.5419, 20)
        self.assertEqual(n, 111)
        self.assertEqual(ts[0], 0)
        self.assertLess(ts[-1], 5.5419)  # frame n would be frame 0 again
        steps = [b - a for a, b in zip(ts, ts[1:])]
        self.assertLess(max(steps) - min(steps), 1e-9)
        self.assertEqual(motion.times(1.0, 50)[0], 50)
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
            self.assertEqual(moving["views"][1]["motion"], {"loop": 4.9494, "traces": 1, "flows": 5})  # follows the routes' lengths
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


# ---- export: an animated SVG in pure Python, a GIF or a video through ffmpeg ---------------------

class Export(unittest.TestCase):
    def test_the_animated_svg_shows_each_frame_once_a_loop(self):
        s, _, svg = checkout([{"trace": PATH}, {"flow": "edge[async]"}])
        out = motion.animated(svg, s, fps=10)
        n, ts = motion.times(s["loop"], 10)
        i = svg.rindex("</svg>")
        self.assertTrue(out.startswith(svg[:i]) and out.endswith(svg[i:]))  # the figure, untouched
        root = ET.fromstring(out)
        frames = [g for g in root.iter(SVG_G) if "data-frame" in g.attrib]
        self.assertEqual(len(frames), n)
        delays = [float(re.search(r"animation-delay:([\d.]+)s", g.get("style")).group(1)) for g in frames]
        self.assertEqual(delays, [round(t, 4) for t in ts])
        self.assertIn("@keyframes dd-frame{0%{visibility:visible}" + motion._s(100.0 / n) + "%", out)
        self.assertIn(f"animation:dd-frame {motion._s(s['loop'])}s step-end infinite", out)
        for t in (ts[0], ts[3], ts[-1]):  # each frame is the layer the page draws at its time
            self.assertIn(f'<g data-frame="" style="animation-delay:{motion._s(t)}s">' + motion.layer(motion.at(s, t)) + "</g>", out)
        self.assertIn('<g data-still="">' + motion.layer(motion.at(s, s["still"])) + "</g>", out)
        still = [g for g in root.iter(SVG_G) if "data-still" in g.attrib]
        self.assertEqual(len(still), 1)  # reduced motion: the path lit, no packets
        self.assertIn("prefers-reduced-motion:reduce", out)

    def test_a_camera_crops_the_figure_and_moves_the_layers_with_it(self):
        s, _, svg = checkout([{"trace": PATH}])
        out = motion.animated(svg, s, fps=5, camera=[100, 50, 400, 300])
        self.assertIn('viewBox="0 0 400 300"', out[:out.index(">", out.index("<svg")) + 1])
        self.assertIn('<g transform="translate(-100,-50)"><g data-still="">', out)
        ET.fromstring(out)

    def test_without_ffmpeg_nothing_is_filmed_and_the_result_says_so(self):
        s, _, svg = checkout([{"trace": PATH}])
        which = shutil.which
        try:
            shutil.which = lambda name, *a, **k: None if name == "ffmpeg" else which(name, *a, **k)
            out = motion.film(svg, s, fps=5, gif="never.gif")
        finally:
            shutil.which = which
        self.assertIn("ffmpeg", out["error"])
        self.assertIn("--svg", out["fix"])
        self.assertFalse(os.path.exists("never.gif"))

    @unittest.skipUnless(shutil.which("ffmpeg") and _rasterizes(), "needs ffmpeg, and cairosvg, Edge or Chrome")
    def test_ffmpeg_films_every_frame_of_the_loop(self):
        s, _, svg = checkout([{"trace": PATH}])
        n, _ = motion.times(s["loop"], 4)
        with tempfile.TemporaryDirectory() as d:
            out = motion.film(svg, s, fps=4, gif=os.path.join(d, "x.gif"), video=os.path.join(d, "x.mp4"))
            self.assertNotIn("gif_error", out)
            self.assertNotIn("video_error", out)
            with open(out["gif"], "rb") as f:
                head = f.read()
            self.assertTrue(head.startswith(b"GIF89a"))
            self.assertIn(b"NETSCAPE2.0", head)  # it loops
            if shutil.which("ffprobe"):
                for path in (out["gif"], out["video"]):
                    p = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                        "stream=nb_read_frames", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=60)
                    self.assertEqual(int(p.stdout.strip()), n, path)


if __name__ == "__main__":
    unittest.main()

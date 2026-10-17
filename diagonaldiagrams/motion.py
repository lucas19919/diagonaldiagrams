"""Motion from meaning (DESIGN 21.2.1): a view says what moves, and the engine works out how.

    "motion": [{"trace": "web -> gw -> orders -> pay"},   # a packet runs the path; arrows light up
               {"flow": "edge[async]"}]                    # dots run along those arrows, without end

read() checks a motion block; resolve() turns it into a schedule against a drawn figure (each
arrow's route as a polyline, each event's start and end); at() is the motion layer at a time t.
The page evaluates the same schedule with web/motion.js, the same arithmetic, so the HTML and the
exported frames agree. frame() is the figure plus that layer; times() is the frame timing of a
seamless loop; film() rasterizes the frames, a sheet at a time, and writes a GIF (gif.py) or,
through ffmpeg, a video.
"""
import math
import os
import re
import xml.etree.ElementTree as ET

from .errors import SpecError

VERBS = {"trace": ("speed", "hold", "packet", "color"), "flow": ("speed", "gap", "color")}
DEFAULTS = {"trace": {"speed": 320.0, "hold": 1.2, "packet": "dot", "color": "accent"},
            "flow": {"speed": 60.0, "gap": 24.0, "color": "link"}}
LIMITS = {"speed": (10.0, 5000.0), "hold": (0.0, 30.0), "gap": (6.0, 400.0)}
PACKETS = ("dot", "dash")
KINDS = ("flow", "arch", "schema")

LEAD = 0.25       # s: the first box pulses before the packet leaves
MIN_HOP = 0.45    # s: the shortest hop, so a short arrow still reads
DWELL = 0.2       # s: the packet rests in a box between hops
FADE = 0.5        # s: the lit path fades out
REST = 0.35       # s: nothing lit before the loop starts again
PULSE = 0.7       # s: a box's ring when the packet reaches it
FLOW_LOOP = 3.0   # s: the loop when only flows move
TIP = 12.0        # px: flow dots stop short of the arrowhead
RAMP = 10.0       # px: flow dots fade in and out over this much route
DOT_R, HALO_R, PACKET_R, DASH = 2.6, 10.0, 4.6, 22.0
LIT_W, GLOW_W, GLOW = 2.8, 9.0, 0.16


def _where(where, k):
    return f"{where} motion[{k}]"


def _number(value, name, at):
    lo, hi = LIMITS[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise SpecError(f"{at}: {name} is {value!r}", f"{name} is a number from {lo:g} to {hi:g}", "bad-motion")
    return float(value)


def read(block, where="view"):
    """The motion block, checked and with its defaults: [{"verb": "trace", "trace": ..., options}]."""
    if block is None:
        return []
    if isinstance(block, dict):
        block = [block]
    if not isinstance(block, list):
        raise SpecError(f"{where}: motion should be a list", 'write "motion": [{"trace": "a -> b -> c"}, {"flow": "edge[async]"}]',
                        "bad-motion")
    out = []
    for k, item in enumerate(block):
        at = _where(where, k)
        verbs = [v for v in VERBS if isinstance(item, dict) and v in item]
        if len(verbs) != 1:
            raise SpecError(f"{at}: say one of {', '.join(VERBS)}",
                            '{"trace": "web -> api -> db"} runs a packet along a path; {"flow": "edge[async]"} runs dots along arrows',
                            "bad-motion")
        verb = verbs[0]
        extra = [key for key in item if key != verb and key not in VERBS[verb]]
        if extra:
            raise SpecError(f"{at}: {verb} does not take {', '.join(extra)}", f"a {verb} takes: {', '.join(VERBS[verb])}", "bad-motion")
        one = dict(DEFAULTS[verb], verb=verb)
        for key in VERBS[verb]:
            if key in item:
                one[key] = _number(item[key], key, at) if key in LIMITS else item[key]
        if verb == "trace":
            one["path"] = _path(item["trace"], at)
        else:
            if not isinstance(item["flow"], str) or not item["flow"].strip():
                raise SpecError(f"{at}: flow names no arrows", 'a flow is a selector of arrows: "edge[async]", "edge[from=bus]"', "bad-motion")
            one["flow"] = item["flow"]
        if one.get("packet") not in PACKETS + (None,):
            raise SpecError(f"{at}: packet is {one['packet']!r}", f"a packet is one of: {', '.join(PACKETS)}", "bad-motion")
        if not isinstance(one["color"], str) or not one["color"].strip():
            raise SpecError(f"{at}: color is {one['color']!r}", "a color is a theme token (accent, link, ink) or a color (#d1495b)", "bad-motion")
        out.append(one)
    return out


def _path(value, at):
    """["web", "gw", "orders"] from "web -> gw -> orders" (or the list itself)."""
    ids = [str(v).strip() for v in value] if isinstance(value, list) else re.split(r"\s*(?:->|→)\s*", str(value).strip())
    if len(ids) < 2 or not all(ids):
        raise SpecError(f"{at}: a trace is a path of two boxes or more", 'write "trace": "web -> api -> db" (box ids, joined by ->)',
                        "bad-motion")
    return ids


# ---- routes ---------------------------------------------------------------------------------

_CMD = re.compile(r"[MmLlHhVvQqCcAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def flatten(d, steps=4):
    """A path's points, with each curve cut into short lines: what a packet runs along."""
    toks = _CMD.findall(d or "")
    pts, k, cmd, x, y, sx, sy = [], 0, "M", 0.0, 0.0, 0.0, 0.0
    need = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "C": 6, "A": 7, "Z": 0}

    def num(i):
        return float(toks[i])
    while k < len(toks):
        if toks[k].isalpha():
            cmd = toks[k]
            k += 1
            if cmd in "Zz":
                if pts and (x, y) != (sx, sy):
                    pts.append((sx, sy))
                x, y = sx, sy
                continue
        up, rel = cmd.upper(), cmd.islower()
        n = need[up]
        if k + n > len(toks) or any(toks[i].isalpha() for i in range(k, k + n)):
            break
        v = [num(i) for i in range(k, k + n)]
        k += n
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if up == "H":
            x = v[0] + (x if rel else 0.0)
            pts.append((x, y))
        elif up == "V":
            y = v[0] + (y if rel else 0.0)
            pts.append((x, y))
        elif up in "ML":
            x, y = v[0] + ox, v[1] + oy
            if up == "M":
                sx, sy = x, y
                cmd = "l" if rel else "L"  # more pairs after M are lines
            pts.append((x, y))
        elif up == "Q":
            cx, cy, ex, ey = v[0] + ox, v[1] + oy, v[2] + ox, v[3] + oy
            for i in range(1, steps + 1):
                t = i / steps
                pts.append(((1 - t) ** 2 * x + 2 * (1 - t) * t * cx + t * t * ex, (1 - t) ** 2 * y + 2 * (1 - t) * t * cy + t * t * ey))
            x, y = ex, ey
        elif up == "C":
            c1x, c1y, c2x, c2y, ex, ey = v[0] + ox, v[1] + oy, v[2] + ox, v[3] + oy, v[4] + ox, v[5] + oy
            for i in range(1, 2 * steps + 1):
                t = i / (2 * steps)
                a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
                pts.append((a * x + b * c1x + c * c2x + e * ex, a * y + b * c1y + c * c2y + e * ey))
            x, y = ex, ey
        else:  # an arc: its end (arcs are rare on arrows; the chord is close enough for a packet)
            x, y = v[5] + ox, v[6] + oy
            pts.append((x, y))
    out = []
    for p in pts:
        p = (round(p[0], 2), round(p[1], 2))
        if not out or p != out[-1]:
            out.append(p)
    return [list(p) for p in out]


def _cum(pts):
    out = [0.0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        out.append(out[-1] + math.sqrt(dx * dx + dy * dy))
    return [round(c, 3) for c in out]


def arrows(svg):
    """[{"id", "from", "to", "stroke", "pts"}] for every arrow drawn, in document order."""
    root = ET.fromstring(svg)
    out = []
    for el in root.iter():
        if str(el.tag).split("}")[-1] == "path" and el.get("data-from") is not None and el.get("data-to") is not None:
            pts = flatten(el.get("d"))
            if len(pts) >= 2:
                out.append({"id": el.get("data-id"), "from": el.get("data-from"), "to": el.get("data-to"),
                            "stroke": el.get("stroke"), "pts": pts})
    return out


# ---- schedule -------------------------------------------------------------------------------

def _color(sty, value, at):
    v = str(value).strip()
    token = sty.token(v) if re.fullmatch(r"[a-z][\w-]*", v) else None
    if token:
        return token
    if re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})|rgba?\([\d.,\s%]+\)", v):
        return v
    raise SpecError(f"{at}: color {v!r} is not a theme token or a color", "use a token (accent, link, ink, muted) or a color (#d1495b)",
                    "bad-motion")


def _near(word, words):
    import difflib
    hit = difflib.get_close_matches(word, list(words), n=1, cutoff=0.6)
    return f" (did you mean '{hit[0]}'?)" if hit else ""


def resolve(items, spec, kind, sty, svg, where="view"):
    """(schedule, warnings): the motion block worked out against the figure as drawn."""
    from .outline import read_figure
    from .story import match
    if not items:
        return None, []
    if kind not in KINDS:
        raise SpecError(f"{where}: motion draws on {', '.join(KINDS)} figures for now, not {kind}",
                        "drop the motion block for this figure", "bad-motion")
    drawn = arrows(svg)
    boxes = read_figure(svg)["nodes"]
    warnings, traces, flows, clock = [], [], [], 0.0
    paper = sty.token("paper") or "#ffffff"
    for k, it in enumerate(items):
        at = _where(where, k)
        color = _color(sty, it["color"], at)
        if it["verb"] == "flow":
            try:
                ids = match(sty, it["flow"])["edges"]
            except SpecError as e:
                raise SpecError(f"{at} flow: {e.msg}", e.fix, "bad-selector")
            hit = [a for a in drawn if a["id"] in ids]
            if not hit:
                warnings.append({"msg": f"{at}: flow {it['flow']!r} matches no arrows",
                                 "fix": "name arrows as dim does: edge[async], edge[from=bus], edge[to=db]"})
            for a in hit:
                flows.append({"edge": a["id"], "pts": a["pts"], "cum": _cum(a["pts"]), "v": it["speed"],
                              "gap": it["gap"], "color": color})
            continue
        path = it["path"]
        for i in path:
            if i not in boxes:
                raise SpecError(f"{at}: the trace names '{i}', which is not a box here{_near(i, boxes)}",
                                "a trace is box ids joined by ->; the figure's ids are its spec's ids", "bad-motion")
        hops, pulses, t = [], [], LEAD
        pulses.append(_pulse(0.0, boxes[path[0]]))
        for h, (a, b) in enumerate(zip(path, path[1:])):
            fwd = [e for e in drawn if e["from"] == a and e["to"] == b]
            back = [e for e in drawn if e["from"] == b and e["to"] == a]
            pick = fwd or back
            if not pick:
                leaving = sorted({e["to"] for e in drawn if e["from"] == a} | {e["from"] for e in drawn if e["to"] == a})
                raise SpecError(f"{at}: no arrow joins {a} and {b} (hop {h + 1} of the trace)",
                                f"arrows join {a} to: {', '.join(leaving) or 'nothing'}", "bad-motion")
            if len(pick) > 1:
                warnings.append({"msg": f"{at}: {len(pick)} arrows join {a} and {b}; the trace takes {pick[0]['id']}",
                                 "fix": "fine as it is; the packet runs along the first"})
            e = pick[0]
            pts = e["pts"] if fwd else [list(p) for p in reversed(e["pts"])]
            cum = _cum(pts)
            dur = max(MIN_HOP, cum[-1] / it["speed"])
            hops.append({"edge": e["id"], "pts": pts, "cum": cum, "a": round(t, 4), "b": round(t + dur, 4), "head": bool(fwd)})
            pulses.append(_pulse(t + dur, boxes[b]))
            t += dur + (DWELL if h < len(path) - 2 else 0.0)
        end = hops[-1]["b"]
        dur = end + it["hold"] + FADE + REST
        traces.append({"t0": round(clock, 4), "dur": round(dur, 4), "end": end, "hold": it["hold"], "color": color,
                       "packet": it["packet"], "hops": hops, "pulses": pulses})
        clock += dur
    loop = round(clock, 4) if traces else FLOW_LOOP
    for f in flows:  # a whole number of gaps per loop: the loop ends where it began
        f["v"] = round(max(1, round(f["v"] * loop / f["gap"])) * f["gap"] / loop, 6)
    still = traces[0]["t0"] + traces[0]["end"] + min(PULSE, traces[0]["hold"]) if traces else 0.0
    return {"loop": loop, "still": round(still, 4), "paper": paper, "flows": flows, "traces": traces}, warnings


def _pulse(t, box):
    return {"t": round(t, 4), "box": [box["x"], box["y"], box["w"], box["h"]], "shape": "diamond" if box["shape"] == "diamond" else "rect"}


# ---- the layer at a time t (web/motion.js does the same arithmetic) -------------------------

def _clamp(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def _ease(p):
    return p * p * (3 - 2 * p)


def _point(pts, cum, s):
    if s <= 0:
        return pts[0][0], pts[0][1]
    for i in range(1, len(pts)):
        if cum[i] >= s:
            seg = cum[i] - cum[i - 1]
            f = (s - cum[i - 1]) / seg if seg > 0 else 1.0
            return pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f
    return pts[-1][0], pts[-1][1]


def _between(pts, cum, s0, s1):
    """The route's points from s0 to s1."""
    out = [_point(pts, cum, s0)]
    for i in range(1, len(pts)):
        if s0 < cum[i] < s1:
            out.append((pts[i][0], pts[i][1]))
    out.append(_point(pts, cum, s1))
    return out


def _n(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _d(line):
    return "M" + " L".join(f"{_n(x)},{_n(y)}" for x, y in line)


def _head(pts):
    """The lit arrowhead: the size and place of the drawn one (marker 12 x 9, tip at the end)."""
    x1, y1 = pts[-1]
    for x0, y0 in reversed(pts[:-1]):
        dx, dy = x1 - x0, y1 - y0
        L = math.sqrt(dx * dx + dy * dy)
        if L > 0.5:
            break
    else:
        return None
    ux, uy = dx / L, dy / L
    bx, by = x1 - ux * 11.5, y1 - uy * 11.5
    return " ".join(f"{_n(x)},{_n(y)}" for x, y in ((x1 + ux * 1.4, y1 + uy * 1.4), (bx - uy * 5, by + ux * 5), (bx + uy * 5, by - ux * 5)))


def at(s, t):
    """The motion layer at time t: [(tag, {attribute: value})], bottom to top."""
    loop = s["loop"]
    t = ((t % loop) + loop) % loop
    dots, glows, cores, heads, rings, packets = [], [], [], [], [], []
    for f in s["flows"]:
        pts, cum, gap = f["pts"], f["cum"], f["gap"]
        end = cum[-1] - TIP
        x = (f["v"] * t) % gap
        while x <= end:
            op = min(1.0, x / RAMP, (end - x) / RAMP)
            if op > 0.01:
                px, py = _point(pts, cum, x)
                dots.append(("circle", {"cx": px, "cy": py, "r": DOT_R, "fill": f["color"], "opacity": op}))
            x += gap
    for tr in s["traces"]:
        u = t - tr["t0"]
        if u < 0 or u >= tr["dur"]:
            continue
        c = tr["color"]
        fade = 1.0 - _clamp((u - tr["end"] - tr["hold"]) / FADE)
        for h in tr["hops"]:
            if u < h["a"] or fade <= 0:
                break
            pts, cum = h["pts"], h["cum"]
            moving = u < h["b"]
            pos = cum[-1] * _ease((u - h["a"]) / (h["b"] - h["a"])) if moving else cum[-1]
            d = _d(_between(pts, cum, 0, pos))
            line = {"d": d, "fill": "none", "stroke": c, "stroke-linecap": "round", "stroke-linejoin": "round"}
            glows.append(("path", dict(line, **{"stroke-width": GLOW_W, "opacity": GLOW * fade})))
            cores.append(("path", dict(line, **{"stroke-width": LIT_W, "opacity": fade})))
            if not moving and h["head"]:
                head = _head(pts)
                if head:
                    heads.append(("polygon", {"points": head, "fill": c, "opacity": fade}))
            if moving:
                px, py = _point(pts, cum, pos)
                if tr["packet"] == "dash":
                    tail = _d(_between(pts, cum, max(0.0, pos - DASH), pos))
                    packets.append(("path", {"d": tail, "fill": "none", "stroke": c, "stroke-linecap": "round", "stroke-width": 12, "opacity": 0.22}))
                    packets.append(("path", {"d": tail, "fill": "none", "stroke": c, "stroke-linecap": "round", "stroke-width": 5}))
                else:
                    packets.append(("circle", {"cx": px, "cy": py, "r": HALO_R, "fill": c, "opacity": 0.22}))
                    packets.append(("circle", {"cx": px, "cy": py, "r": PACKET_R, "fill": c, "stroke": s["paper"], "stroke-width": 1.6}))
        for p in tr["pulses"]:
            w = (u - p["t"]) / PULSE
            if 0 <= w < 1:
                op = w / 0.15 if w < 0.15 else (1 - w) / 0.85
                g = 3 + 6 * w
                x, y, bw, bh = p["box"]
                if p["shape"] == "diamond":
                    cx, cy = x + bw / 2, y + bh / 2
                    pts = ((cx, y - g), (x + bw + g, cy), (cx, y + bh + g), (x - g, cy))
                    rings.append(("polygon", {"points": " ".join(f"{_n(a)},{_n(b)}" for a, b in pts), "fill": "none", "stroke": c,
                                              "stroke-width": 2, "opacity": op}))
                else:
                    rings.append(("rect", {"x": x - g, "y": y - g, "width": bw + 2 * g, "height": bh + 2 * g, "rx": 8 + g,
                                           "fill": "none", "stroke": c, "stroke-width": 2, "opacity": op}))
    return dots + glows + cores + heads + rings + packets


def layer(shapes):
    """The shapes as SVG markup, in a group the figure's readers skip."""
    from ._text import esc
    parts = ['<g data-motion="" aria-hidden="true" pointer-events="none">']
    for tag, attrs in shapes:
        parts.append(f"<{tag} " + " ".join(f'{k}="{_n(v) if isinstance(v, (int, float)) else esc(str(v))}"' for k, v in attrs.items()) + "/>")
    parts.append("</g>")
    return "".join(parts)


def frame(svg, s, t):
    """The figure at time t: its SVG with the motion layer on top."""
    i = svg.rindex("</svg>")
    return svg[:i] + layer(at(s, t)) + "\n" + svg[i:]


def times(loop, fps):
    """(n, [t_k], [delay_k in hundredths of a second]) for a loop at about fps frames a second.
    Frame n would be frame 0 again, so the loop has no seam; the delays add up to the loop."""
    if not 1 <= fps <= 50:
        raise SpecError(f"fps is {fps}", "fps is from 1 to 50 (a GIF counts in hundredths of a second)", "bad-motion")
    n = max(2, int(round(loop * fps)))
    ts = [loop * k / n for k in range(n)]
    delays = [int(round(100 * loop * (k + 1) / n)) - int(round(100 * loop * k / n)) for k in range(n)]
    return n, ts, delays


# ---- export ---------------------------------------------------------------------------------

def _crop(svg, box):
    """The figure cut to the camera's box [x, y, w, h], as a drawing of its own (0 0 w h)."""
    x, y, w, h = box
    head_end = svg.index(">", svg.index("<svg")) + 1
    head = re.sub(r'viewBox="[^"]*"', f'viewBox="0 0 {_n(w)} {_n(h)}"', svg[:head_end])
    head = re.sub(r'width="[^"]*"', f'width="{_n(w)}"', head, count=1)
    i = svg.rindex("</svg>")
    return head + f'<g transform="translate({_n(-x)},{_n(-y)})">' + svg[head_end:i] + "</g>" + svg[i:]


SHEET = 7800  # px: the tallest sheet of frames one raster call draws


def sheet(svgs, w, h):
    """Several frames stacked top to bottom in one drawing, so one raster call draws them all."""
    tiles = []
    for j, body in enumerate(svgs):
        end = body.index(">", body.index("<svg")) + 1
        tiles.append(body[:end - 1] + f' x="0" y="{j * h}" height="{h}">' + body[end:])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h * len(svgs)}" width="{w}">'
            + "".join(tiles) + "</svg>")


def film(svg, s, fps=20, gif=None, video=None, camera=None, workers=4, keep=None):
    """Draws the loop through the PNG export path, a sheet of frames per raster call, then writes the
    GIF and/or the video. Returns what it wrote: {"frames", "fps", "loop", "gif", "gif_bytes", ...}."""
    import shutil
    import subprocess
    import tempfile
    from concurrent.futures import ThreadPoolExecutor
    from . import gif as giff
    from .export import _raster_svg
    n, ts, delays = times(s["loop"], fps)
    if camera:  # whole pixels, so the frames tile exactly
        x, y, w, h = camera
        camera = [x, y, math.ceil(w), math.ceil(h)]
    first = _crop(svg, camera) if camera else svg
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', first)
    if not m:
        raise SpecError("the figure has no viewBox to film", "draw it again; every renderer writes one", "no-raster")
    W, H = int(round(float(m.group(1)))), int(round(float(m.group(2))))
    per = max(1, min(16, SHEET // max(1, H)))
    groups = [list(range(k, min(n, k + per))) for k in range(0, n, per)]
    folder = keep or tempfile.mkdtemp(prefix="dd-motion-")
    os.makedirs(folder, exist_ok=True)

    def body(k):
        out = frame(svg, s, ts[k])
        return _crop(out, camera) if camera else out

    def one(g):
        svgs = [body(k) for k in groups[g]]
        if keep:
            for k, text in zip(groups[g], svgs):
                with open(os.path.join(folder, f"f{k:04d}.svg"), "w", encoding="utf-8") as fh:
                    fh.write(text)
        return _raster_svg(sheet(svgs, W, H), os.path.join(folder, f"sheet{g:03d}.png"), "png", W, scale=1)
    try:
        with ThreadPoolExecutor(max(1, workers)) as pool:
            done = list(pool.map(one, range(len(groups))))
        bad = [why for how, why in done if not how]
        if bad:
            raise SpecError(f"a frame did not rasterize: {bad[0]}", "filming needs cairosvg, Edge or Chrome on this machine",
                            "no-raster")
        frames, prev = [], None
        for g in range(len(groups)):
            part = giff.read_png(os.path.join(folder, f"sheet{g:03d}.png"), like=prev, period=H)
            if prev is not None:
                prev.px = prev.filtered = None
            prev = part
            frames += giff.split(part, H)[:len(groups[g])]
        out = {"frames": n, "fps": fps, "loop": s["loop"], "size": [W, H], "raster": done[0][0], "sheets": len(groups)}
        if gif:
            size, written = giff.write(gif, frames, delays)
            out.update(gif=gif, gif_bytes=size, gif_frames=written)
        if video:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                out["video_error"] = "ffmpeg is not on the PATH (the GIF needs nothing else)"
            else:
                for k, f in enumerate(frames):
                    giff.write_png(os.path.join(folder, f"f{k:04d}.png"), f)
                codec = (["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32"] if video.lower().endswith(".webm")
                         else ["-c:v", "libx264", "-crf", "18", "-movflags", "+faststart"])
                cmd = [ffmpeg, "-y", "-loglevel", "error", "-framerate", f"{n / s['loop']:.6f}", "-i", os.path.join(folder, "f%04d.png"),
                       "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-pix_fmt", "yuv420p", *codec, os.path.abspath(video)]
                p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=600)
                if p.returncode == 0 and os.path.isfile(video):
                    out.update(video=video, video_bytes=os.path.getsize(video))
                else:
                    out["video_error"] = (p.stderr or p.stdout or f"ffmpeg exit {p.returncode}").strip()[-300:]
        return out
    finally:
        if not keep:
            shutil.rmtree(folder, ignore_errors=True)

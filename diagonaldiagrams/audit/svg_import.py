"""Any SVG as a display list, for the audit: texts with their measured boxes, shapes, arrows,
group frames, named nodes and decision outlines.

It reads what other tools write too (Mermaid, D2, hand-written SVG): stylesheet rules, nested
transforms, tspan lines placed in em, relative path commands.
"""
import re

from .._text import _text_w
from ..displaylist import DisplayList, Item
from ..geom import IDENTITY, affine, apply, compose, xbox

SKIP = ("defs", "marker", "clipPath", "mask", "symbol", "pattern", "title", "desc", "style")
KEEP = ("font-size", "font-weight", "text-anchor", "dominant-baseline", "opacity", "visibility", "display", "letter-spacing")
NEED = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}


def num(v, d=0.0):
    try:
        return float(str(v).replace("px", "").replace(",", " ").split()[0])
    except (TypeError, ValueError, IndexError):
        return d


def stylesheet(root):
    """CSS rules from <style> blocks. Each rule's last compound selector (tag, .class, #id) is
    kept with the text properties above, sorted so a more specific rule applies later."""
    css = []
    for st_el in (e for e in root.iter() if str(e.tag).split("}")[-1] == "style"):
        body = re.sub(r"/\*.*?\*/", "", "".join(st_el.itertext()), flags=re.S)
        body = re.sub(r"@[\w-]+[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", body)  # @font-face, @media
        for sels, decls in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
            props = {}
            for d in decls.split(";"):
                if ":" in d:
                    name, val = d.split(":", 1)
                    if name.strip().lower() in KEEP:
                        props[name.strip().lower()] = val.replace("!important", "").strip()
            if not props:
                continue
            for sel in sels.split(","):
                last = re.split(r"[\s>+~]+", sel.strip())[-1] if sel.strip() else ""
                m_sel = re.fullmatch(r"([\w*-]*)((?:[.#][\w-]+)*)(?::[\w-]+(?:\([^)]*\))?)*", last)
                if not m_sel:
                    continue
                parts = re.findall(r"([.#])([\w-]+)", m_sel.group(2))
                classes = {v for p, v in parts if p == "."}
                ids = {v for p, v in parts if p == "#"}
                tag = "" if m_sel.group(1) in ("", "*") else m_sel.group(1)
                css.append(((len(ids), len(classes), 1 if tag else 0, len(css)), tag, classes, ids, props))
    css.sort(key=lambda r: r[0])
    return css


def css_for(css, el, tag):
    cls = set((el.get("class") or "").split())
    out = {}
    for _, t, classes, ids, props in css:
        if (not t or t == tag) and classes <= cls and (not ids or el.get("id") in ids):
            out.update(props)
    return out


def path_pts(d):
    """A path's points, absolute; None marks where a subpath starts. A curve keeps only its end
    point: corners are small."""
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d or "")
    pts, cur, start, cmd, i = [], (0.0, 0.0), (0.0, 0.0), None, 0
    while i < len(toks):
        tk = toks[i]
        if tk.isalpha():
            cmd, i = tk, i + 1
            if cmd in "Zz":
                cur = start
                pts.append(cur)
            continue
        if cmd is None or cmd in "Zz":
            break
        u, n = cmd.upper(), NEED[cmd.upper()]
        vals = [float(v) for v in toks[i:i + n]]
        if len(vals) < n:
            break
        i += n
        rel = cmd.islower()
        if u == "H":
            x, y = (cur[0] + vals[0] if rel else vals[0]), cur[1]
        elif u == "V":
            x, y = cur[0], (cur[1] + vals[0] if rel else vals[0])
        else:
            x, y = (cur[0] + vals[-2], cur[1] + vals[-1]) if rel else (vals[-2], vals[-1])
        cur = (x, y)
        if u == "M":
            start = cur
            pts.append(None)
            cmd = "l" if rel else "L"
        pts.append(cur)
    return pts


def text_items(el, st, m, z):
    """One item per line of a <text>: each positioned <tspan> starts a line."""
    fs = num(st.get("font-size", 12), 12)
    bold = str(st.get("font-weight", "")) in ("600", "700", "800", "900", "bold")
    cx, cy = num(el.get("x")), num(el.get("y"))
    lines = [[el.text or "", cx, cy]]

    def length(v):  # "12", "12px", or "1.1em" (a font height, as Mermaid writes line positions)
        v = str(v)
        return num(v.replace("em", "").replace("px", "")) * (fs if "em" in v else 1)
    for sp in el:
        if str(sp.tag).split("}")[-1] != "tspan":
            continue
        moved = any(sp.get(k) is not None for k in ("x", "y", "dy"))
        if sp.get("x") is not None:
            cx = length(sp.get("x"))
        if sp.get("y") is not None:
            cy = length(sp.get("y"))
        if sp.get("dy") is not None:
            cy += length(sp.get("dy"))
        body = "".join(sp.itertext())
        if moved:
            lines.append([body, cx, cy])
        else:
            lines[-1][0] += body
        lines[-1][0] += sp.tail or ""
    anc = st.get("text-anchor", "start")
    db = st.get("dominant-baseline", "")
    out = []
    for s, x, y in lines:
        s = s.strip()
        if not s:
            continue
        w = _text_w(s, fs, bold)
        ls = str(st.get("letter-spacing") or "0")
        w += len(s) * num(ls.replace("em", "")) * (fs if "em" in ls else 1)
        x0 = x - w / 2 if anc == "middle" else (x - w if anc == "end" else x)
        if db in ("middle", "central"):
            y0, y1 = y - fs * 0.5, y + fs * 0.5
        elif db in ("hanging", "text-before-edge"):
            y0, y1 = y, y + fs
        else:
            y0, y1 = y - fs * 0.72, y + fs * 0.2
        z[0] += 1
        out.append(Item("text", z=z[0], box=xbox(m, x0, y0, x0 + w, y1), text=s, size=fs, newline="\n" in s))
    return out


def svg_import(root, width, height):
    """The display list of a parsed SVG (an ElementTree root) with a width x height canvas."""
    dl = DisplayList(width, height)
    css = stylesheet(root)
    seen, centers, z = set(), [], [0]

    def walk(el, st, m):
        tag = str(el.tag).split("}")[-1]
        if tag in SKIP:
            return
        st = dict(st, **{k: el.get(k) for k in KEEP if el.get(k) is not None})
        if css:
            st.update(css_for(css, el, tag))  # stylesheet rules beat presentation attributes
        style = el.get("style") or ""
        for k in KEEP:
            hit = re.search(rf"(?:^|;)\s*{k}\s*:\s*([^;]+)", style)
            if hit:
                st[k] = hit.group(1).strip()
        if st.get("display") == "none" or st.get("visibility") == "hidden" or num(st.get("opacity", 1), 1) <= 0:
            return
        if el.get("transform"):
            m = compose(m, affine(el.get("transform")))
        if tag == "text":
            for item in text_items(el, st, m, z):
                dl.add(item)
            return
        if tag in ("path", "line", "polyline") and (el.get("marker-end") or el.get("marker-start") or "marker" in style):
            if tag == "path":
                raw = path_pts(el.get("d"))
            elif tag == "line":
                raw = [(num(el.get("x1")), num(el.get("y1"))), (num(el.get("x2")), num(el.get("y2")))]
            else:
                v = [float(p) for p in re.findall(r"-?\d*\.?\d+", el.get("points", ""))]
                raw = list(zip(v[0::2], v[1::2]))
            pts = [None if q is None else apply(m, q) for q in raw]
            real = [q for q in pts if q is not None]
            if len(real) >= 2:
                z[0] += 1
                dl.add(Item("arrow", z=z[0], pts=pts, ends=(real[0], real[-1])))
        box, item = None, None
        if tag == "rect":
            x, y, w, h = (num(el.get(k)) for k in ("x", "y", "width", "height"))
            box = xbox(m, x, y, x + w, y + h)
            item = Item("shape", box=box, tag=tag)
            if el.get("data-group") is not None:
                item.group = el.get("data-group")
                item.members = frozenset((el.get("data-members") or "").split(","))
            if el.get("data-node") is not None:
                item.node = el.get("data-node")
        elif tag == "polygon":
            v = [float(p) for p in re.findall(r"-?\d*\.?\d+", el.get("points", ""))]
            if len(v) == 8:  # a diamond: test the rectangle inside it, not its bounding box
                b = xbox(m, min(v[0::2]), min(v[1::2]), max(v[0::2]), max(v[1::2]))
                cx, cy, qw, qh = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, (b[2] - b[0]) / 4, (b[3] - b[1]) / 4
                box = (cx - qw, cy - qh, cx + qw, cy + qh)
                item = Item("shape", box=box, tag=tag)
                if (el.get("fill") or "") != "none" and (cx, cy) not in centers:
                    centers.append((cx, cy))
                    item.diamond = (cx, cy, 2 * qw, 2 * qh)
        if item is not None:
            bw, bh = box[2] - box[0], box[3] - box[1]
            filled = (el.get("fill") or "black") != "none" or el.get("stroke")
            big = width and height and bw * bh > 0.5 * width * height
            key = tuple(round(c, 1) for c in box)
            if filled and bw >= 10 and bh >= 10 and not big and key not in seen:
                seen.add(key)
                z[0] += 1
                item.z, item.obstacle = z[0], True
            dl.add(item)
        for c in el:
            walk(c, st, m)

    walk(root, {}, IDENTITY)
    return dl

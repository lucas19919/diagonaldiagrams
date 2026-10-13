"""The audit: reads a finished SVG and reports what an agent cannot see in it."""
import json, os
from ._text import _text_w


def _affine(tf):
    """SVG transform list -> matrix (a, b, c, d, e, f)."""
    import math, re

    def mul(m, n):
        a1, b1, c1, d1, e1, f1 = m
        a2, b2, c2, d2, e2, f2 = n
        return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
                a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, raw in re.findall(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)", tf or ""):
        v = [float(x) for x in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", raw)]
        if not v:
            continue
        if name == "matrix" and len(v) == 6:
            n = tuple(v)
        elif name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            n = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                n = mul(mul((1, 0, 0, 1, v[1], v[2]), n), (1, 0, 0, 1, -v[1], -v[2]))
        else:
            continue
        m = mul(m, n)
    return m


def _xbox(m, x0, y0, x1, y1):
    pts = [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def _svg_geometry(root, W, H, stats=None):
    """Collisions an agent cannot see in its own output: label on label, label off the
    canvas, label wider than its box, box on box. Returns error dicts with a fix."""
    import re

    def num(v, d=0.0):
        try:
            return float(str(v).replace("px", "").replace(",", " ").split()[0])
        except (TypeError, ValueError, IndexError):
            return d
    texts, shapes, arrows, seen, z = [], [], [], set(), [0]
    frames, named = [], []  # group frames (data-group) and node boxes (data-node)
    diamonds = []  # (cx, cy, half width, half height): arrows are tested against the real shape
    keep = ("font-size", "font-weight", "text-anchor", "dominant-baseline", "opacity", "visibility", "display", "letter-spacing")
    need = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    # CSS rules from <style> blocks (Mermaid, hand-written SVG): each rule's last compound selector
    # (tag, .class, #id) is matched, in specificity order, for the properties above.
    css = []
    for k, st_el in enumerate(e for e in root.iter() if str(e.tag).split("}")[-1] == "style"):
        body = re.sub(r"/\*.*?\*/", "", "".join(st_el.itertext()), flags=re.S)
        body = re.sub(r"@[\w-]+[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", body)  # @font-face, @media
        for sels, decls in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
            props = {}
            for d in decls.split(";"):
                if ":" in d:
                    name, val = d.split(":", 1)
                    if name.strip().lower() in keep:
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

    def css_for(el, tag):
        cls = set((el.get("class") or "").split())
        out = {}
        for _, t, classes, ids, props in css:
            if (not t or t == tag) and classes <= cls and (not ids or el.get("id") in ids):
                out.update(props)
        return out

    def path_pts(d):
        # Absolute and relative commands. A curve keeps only its end point: corners are small.
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
            u, n = cmd.upper(), need[cmd.upper()]
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

    def walk(el, st, m):
        tag = str(el.tag).split("}")[-1]
        if tag in ("defs", "marker", "clipPath", "mask", "symbol", "pattern", "title", "desc", "style"):
            return
        st = dict(st, **{k: el.get(k) for k in keep if el.get(k) is not None})
        if css:
            st.update(css_for(el, tag))  # stylesheet rules beat presentation attributes
        style = el.get("style") or ""
        for k in keep:
            hit = re.search(rf"(?:^|;)\s*{k}\s*:\s*([^;]+)", style)
            if hit:
                st[k] = hit.group(1).strip()
        if st.get("display") == "none" or st.get("visibility") == "hidden" or num(st.get("opacity", 1), 1) <= 0:
            return
        if el.get("transform"):
            n = _affine(el.get("transform"))
            a1, b1, c1, d1, e1, f1 = m
            a2, b2, c2, d2, e2, f2 = n
            m = (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
                 a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)
        if tag == "text":
            fs = num(st.get("font-size", 12), 12)
            bold = str(st.get("font-weight", "")) in ("600", "700", "800", "900", "bold")
            cx, cy = num(el.get("x")), num(el.get("y"))
            lines = [[el.text or "", cx, cy]]

            def length(v):  # "12", "12px", or "1.1em" (a font height, as Mermaid writes line positions)
                v = str(v)
                return num(v.replace("em", "").replace("px", "")) * (fs if "em" in v else 1)
            for sp in el:  # each positioned <tspan> is its own line
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
                texts.append({"s": s, "fs": fs, "box": _xbox(m, x0, y0, x0 + w, y1), "nl": "\n" in s, "z": z[0]})
            return
        if tag in ("path", "line", "polyline") and (el.get("marker-end") or el.get("marker-start") or "marker" in style):
            if tag == "path":
                raw = path_pts(el.get("d"))
            elif tag == "line":
                raw = [(num(el.get("x1")), num(el.get("y1"))), (num(el.get("x2")), num(el.get("y2")))]
            else:
                v = [float(p) for p in re.findall(r"-?\d*\.?\d+", el.get("points", ""))]
                raw = list(zip(v[0::2], v[1::2]))
            pts = [None if q is None else (m[0] * q[0] + m[2] * q[1] + m[4], m[1] * q[0] + m[3] * q[1] + m[5]) for q in raw]
            real = [q for q in pts if q is not None]
            if len(real) >= 2:
                z[0] += 1
                arrows.append({"pts": pts, "ends": (real[0], real[-1]), "z": z[0]})
        box = None
        if tag == "rect":
            x, y, w, h = (num(el.get(k)) for k in ("x", "y", "width", "height"))
            box = _xbox(m, x, y, x + w, y + h)
            if el.get("data-group") is not None:
                frames.append((box, el.get("data-group"), set((el.get("data-members") or "").split(","))))
            if el.get("data-node") is not None:
                named.append((box, el.get("data-node")))
        elif tag == "polygon":
            v = [float(p) for p in re.findall(r"-?\d*\.?\d+", el.get("points", ""))]
            if len(v) == 8:  # a diamond: test the rectangle inside it, not its bounding box
                b = _xbox(m, min(v[0::2]), min(v[1::2]), max(v[0::2]), max(v[1::2]))
                cx, cy, qw, qh = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, (b[2] - b[0]) / 4, (b[3] - b[1]) / 4
                box = (cx - qw, cy - qh, cx + qw, cy + qh)
                if (el.get("fill") or "") != "none" and (cx, cy) not in [(d[0], d[1]) for d in diamonds]:
                    diamonds.append((cx, cy, 2 * qw, 2 * qh))
        if box:
            bw, bh = box[2] - box[0], box[3] - box[1]
            filled = (el.get("fill") or "black") != "none" or el.get("stroke")
            big = W and H and bw * bh > 0.5 * W * H
            key = tuple(round(c, 1) for c in box)
            if filled and bw >= 10 and bh >= 10 and not big and key not in seen:
                seen.add(key)
                z[0] += 1
                shapes.append({"box": box, "tag": tag, "z": z[0]})
        for c in el:
            walk(c, st, m)

    walk(root, {}, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))

    def inter(a, b):
        return max(0.0, min(a[2], b[2]) - max(a[0], b[0])), max(0.0, min(a[3], b[3]) - max(a[1], b[1]))

    def inside(a, b, tol=1.0):
        return a[0] - tol <= b[0] and a[1] - tol <= b[1] and a[2] + tol >= b[2] and a[3] + tol >= b[3]

    def at(b):
        return [round((b[0] + b[2]) / 2), round((b[1] + b[3]) / 2)]

    def near(xs, ys=None, cell=64.0):
        # Candidate pairs from a grid, so a chart with thousands of marks stays fast.
        # With one list, pairs come once (i < j); with two, every (i, j) that may touch.
        lim = max(W, H, 1000.0) + 1000.0

        def cells(b):
            x0, y0 = max(-lim, b[0]), max(-lim, b[1])
            x1, y1 = min(lim, b[2]), min(lim, b[3])
            return [(gx, gy) for gx in range(int(x0 // cell), int(x1 // cell) + 1)
                    for gy in range(int(y0 // cell), int(y1 // cell) + 1)]
        grid = {}
        for j, b in enumerate(xs if ys is None else ys):
            for c in cells(b):
                grid.setdefault(c, []).append(j)
        done = set()
        for i, a in enumerate(xs):
            for c in cells(a):
                for j in grid.get(c, ()):
                    if (ys is None and j <= i) or (i, j) in done:
                        continue
                    done.add((i, j))
                    yield i, j
    issues = []
    if len(texts) > 1500:
        # Past this nobody reads the labels, and pairwise checks would take minutes.
        return [{"code": "dense", "msg": f"{len(texts)} labels on one figure",
                 "fix": "aggregate to top-N + Other, facet, or pass --no-audit", "at": [0, 0]}]
    if len(shapes) > 4000:
        shapes = []
    tb = [t["box"] for t in texts]
    sb = [sh["box"] for sh in shapes]
    for t in texts:
        b = t["box"]
        if t["nl"]:
            issues.append({"code": "newline", "msg": f"label '{t['s'][:30]}' has a line break; SVG draws it on one line",
                           "fix": "split it: name for the headline, sub for the detail", "at": at(b)})
        if W and H and (b[0] < -4 or b[2] > W + 4 or b[1] < -4 or b[3] > H + 4):
            issues.append({"code": "clip", "msg": f"label '{t['s'][:30]}' runs off the canvas",
                           "fix": "shorten it", "at": at(b)})
    for i, j in near(tb):
        if True:
            a, b = texts[i], texts[j]
            if a["s"] == b["s"] and abs(a["box"][0] - b["box"][0]) < 1 and abs(a["box"][1] - b["box"][1]) < 1:
                continue  # a halo drawn under its own label
            iw, ih = inter(a["box"], b["box"])
            short = min(a["box"][2] - a["box"][0], b["box"][2] - b["box"][0])
            if iw > max(3.0, 0.15 * short) and ih > 0.4 * min(a["fs"], b["fs"]):
                issues.append({"code": "collide", "msg": f"labels collide: '{a['s'][:24]}' and '{b['s'][:24]}'",
                               "fix": "shorten one, or move it (rank, lane, --note-at)", "at": at(a["box"])})
    for i, j in near(sb):
        if True:
            a, b = shapes[i]["box"], shapes[j]["box"]
            iw, ih = inter(a, b)
            if iw > 4 and ih > 4 and not inside(a, b) and not inside(b, a):
                issues.append({"code": "overlap", "msg": f"boxes overlap at {at((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))}",
                               "fix": "give them different rank or lane, or fewer items per row", "at": at(a)})
    import math

    def crosses(p, q, b):
        # Liang-Barsky: does segment p-q run more than 2px inside box b?
        dx, dy = q[0] - p[0], q[1] - p[1]
        t0, t1 = 0.0, 1.0
        for pk, qk in ((-dx, p[0] - b[0]), (dx, b[2] - p[0]), (-dy, p[1] - b[1]), (dy, b[3] - p[1])):
            if pk == 0:
                if qk < 0:
                    return False
                continue
            r = qk / pk
            if pk < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return False
        return (t1 - t0) * math.hypot(dx, dy) > 2
    # A group frame holds whole boxes. A node holding only its own tag pill is still a node.
    holders = {i for i, j in near(sb, sb)
               if i != j and inside(sb[i], sb[j]) and not inside(sb[j], sb[i]) and sb[j][3] - sb[j][1] >= 24}

    # A pill behind an arrow label masks the arrow on purpose: a short shape around one line of text.
    holders |= {i for i, j in near(sb, tb)
                if inside(sb[i], tb[j], tol=4) and sb[i][3] - sb[i][1] <= 2.5 * (tb[j][3] - tb[j][1])}
    for ar in arrows:
        segs = [(ar["pts"][k], ar["pts"][k + 1]) for k in range(len(ar["pts"]) - 1)
                if ar["pts"][k] is not None and ar["pts"][k + 1] is not None]
        if not segs:
            continue
        # the arrow's bounding box: anything outside it cannot be crossed, so skip it cheaply
        ax0 = min(min(p[0], q[0]) for p, q in segs)
        ay0 = min(min(p[1], q[1]) for p, q in segs)
        ax1 = max(max(p[0], q[0]) for p, q in segs)
        ay1 = max(max(p[1], q[1]) for p, q in segs)

        def apart(b):
            return b[2] < ax0 or b[0] > ax1 or b[3] < ay0 or b[1] > ay1
        for i, sh in enumerate(shapes):
            b = sh["box"]
            if apart(b):
                continue
            if i in holders or any(b[0] - 6 <= e[0] <= b[2] + 6 and b[1] - 6 <= e[1] <= b[3] + 6 for e in ar["ends"]):
                continue  # a group frame, or the box this arrow leaves or enters
            core = (b[0] + 3, b[1] + 3, b[2] - 3, b[3] - 3)
            if core[2] > core[0] and core[3] > core[1] and any(crosses(p, q, core) for p, q in segs):
                issues.append({"code": "through", "msg": f"an arrow runs through the box at {at(b)}",
                               "fix": "move one node to another lane or rank so the arrow goes around it", "at": at(b)})
        for cx, cy, hw, hh in diamonds:
            if apart((cx - hw, cy - hh, cx + hw, cy + hh)):
                continue
            if any(abs(e[0] - cx) <= hw + 6 and abs(e[1] - cy) <= hh + 6 for e in ar["ends"]):
                continue  # the decision this arrow leaves or enters
            hit = False
            for p, q in segs:
                if max(p[0], q[0]) < cx - hw or min(p[0], q[0]) > cx + hw or max(p[1], q[1]) < cy - hh or min(p[1], q[1]) > cy + hh:
                    continue
                n = max(1, int(math.hypot(q[0] - p[0], q[1] - p[1]) // 4))
                if any(abs(p[0] + (q[0] - p[0]) * k / n - cx) / hw + abs(p[1] + (q[1] - p[1]) * k / n - cy) / hh < 0.9
                       for k in range(n + 1)):
                    hit = True
                    break
            if hit:
                issues.append({"code": "through", "msg": f"an arrow runs through the decision at {[round(cx), round(cy)]}",
                               "fix": "move one node to another lane or rank so the arrow goes around it", "at": [round(cx), round(cy)]})
        for t in texts:
            if t["z"] > ar["z"] or apart(t["box"]):
                continue  # the label is painted over the arrow, on purpose, or is nowhere near it
            b = t["box"]
            h = b[3] - b[1]
            core = (b[0] + 1, b[1] + 0.2 * h, b[2] - 1, b[3] - 0.2 * h)
            if core[2] > core[0] and any(crosses(p, q, core) for p, q in segs):
                issues.append({"code": "strike", "msg": f"an arrow is drawn across the label '{t['s'][:24]}'",
                               "fix": "move the node or the label off the arrow's path", "at": at(b)})
    # Two arrows on one line, or ending within 12px of each other on it, read as one arrow
    # that forks: nobody can tell where each goes.
    runs = []
    for k, ar in enumerate(arrows[:300]):
        p = ar["pts"]
        for a, b in zip(p, p[1:]):
            if a is None or b is None:
                continue
            if abs(a[1] - b[1]) < 0.5 and abs(a[0] - b[0]) > 12:
                runs.append((k, "h", round(a[1], 1), min(a[0], b[0]), max(a[0], b[0])))
            elif abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) > 12:
                runs.append((k, "v", round(a[0], 1), min(a[1], b[1]), max(a[1], b[1])))
    shared = set()
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            ka, da, ca, la, ha = runs[i]
            kb, db, cb, lb, hb = runs[j]
            sa, ea = arrows[ka]["ends"]
            sb, eb = arrows[kb]["ends"]
            joint = math.hypot(sa[0] - sb[0], sa[1] - sb[1]) < 3 or math.hypot(ea[0] - eb[0], ea[1] - eb[1]) < 3
            if ka != kb and not joint and da == db and abs(ca - cb) < 2 and min(ha, hb) - max(la, lb) > -12 and (ka, kb) not in shared:
                shared.add((ka, kb))
                mid = (max(la, lb) + min(ha, hb)) / 2
                where = [round(mid), round(ca)] if da == "h" else [round(ca), round(mid)]
                issues.append({"code": "shared", "msg": f"two arrows run on one line at {where}",
                               "fix": "reorder the row or move one node so the arrows take separate paths", "at": where})
    for t in texts:
        b = t["box"]
        mx, my = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        for cx, cy, hw, hh in diamonds:
            if abs(mx - cx) / hw + abs(my - cy) / hh <= 1:
                continue  # the decision's own question
            # measured with the label's background pill, which is what covers the outline
            corners = [(b[0] - 7, b[1] - 2), (b[2] + 7, b[1] - 2), (b[0] - 7, b[3] + 2), (b[2] + 7, b[3] + 2)]
            if any(abs(x - cx) / hw + abs(y - cy) / hh < 1.0 for x, y in corners):
                issues.append({"code": "collide", "msg": f"label '{t['s'][:24]}' sits on the edge of a decision",
                               "fix": "move the label or the node so the decision shows whole", "at": [round(mx), round(my)]})
    for fb, gid, members in frames:
        for nb, nid in named:
            cx, cy = (nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2
            if nid not in members and fb[0] < cx < fb[2] and fb[1] < cy < fb[3]:
                issues.append({"code": "intrude", "msg": f"node '{nid}' sits inside group '{gid}' but is not in it",
                               "fix": "move it to another row or lane, or add it to the group", "at": [round(cx), round(cy)]})
        # a frame's border runs across a line of text (a subtitle above it, a label at its edge)
        for t in texts:
            b = t["box"]
            across_h = b[0] < fb[2] and fb[0] < b[2] and any(b[1] + 1 < y < b[3] - 1 for y in (fb[1], fb[3]))
            across_v = b[1] < fb[3] and fb[1] < b[3] and any(b[0] + 1 < x < b[2] - 1 for x in (fb[0], fb[2]))
            if across_h or across_v:
                mx, my = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                issues.append({"code": "collide", "msg": f"the frame of group '{gid}' runs through '{t['s'][:24]}'",
                               "fix": "move the text or the group's members so the frame clears it", "at": [round(mx), round(my)]})
    rects = [s["box"] for s in shapes if s["tag"] == "rect"]
    hosts = {}
    for i, j in near(tb, rects):
        b, r = tb[i], rects[j]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
            if i not in hosts or (r[2] - r[0]) * (r[3] - r[1]) < (hosts[i][2] - hosts[i][0]) * (hosts[i][3] - hosts[i][1]):
                hosts[i] = r
    for i, r in sorted(hosts.items()):
        t, b = texts[i], tb[i]
        # a background drawn to the text's own size (Mermaid's arrow labels) is not a box to fit in
        tight = (r[3] - r[1]) <= 1.8 * (b[3] - b[1]) and (r[2] - r[0]) <= (b[2] - b[0]) + 2 * t["fs"]
        if not tight:
            if b[0] < r[0] + 2 or b[2] > r[2] - 2:  # a label keeps 2px clear of its box edge
                issues.append({"code": "spill", "msg": f"label '{t['s'][:30]}' fills or overflows its box",
                               "fix": "2-4 words for a name; put detail in sub", "at": at(b)})
    if stats is not None:
        # For layout repair: how many arrow segments cross, and how much arrow there is.
        hs = [r for r in runs if r[1] == "h"]
        vs = [r for r in runs if r[1] == "v"]
        stats["crossings"] = sum(1 for kh, _, y, x0, x1 in hs for kv, _, x, y0, y1 in vs
                                 if kh != kv and x0 + 1 < x < x1 - 1 and y0 + 1 < y < y1 - 1)
        stats["wire"] = sum(r[4] - r[3] for r in runs)
    out, dedup = [], set()
    for it in issues:
        k = (it["code"], it["msg"])
        if k not in dedup:
            dedup.add(k)
            out.append(it)
    return out


def do_audit(args):
    rep = _audit_file(args.target)
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1


def _audit_file(p):
    """Every check `audit` runs, as a report dict. Render calls it after drawing."""
    import re, xml.etree.ElementTree as ET
    errors, warnings = [], []
    if not os.path.isfile(p):
        return {"ok": False, "errors": [{"msg": f"no file {p}", "fix": "render first; audit takes the .svg or .html it wrote"}], "warnings": []}
    raw = open(p, encoding="utf-8", errors="replace").read()
    # the outermost <svg> first (D2 nests one svg in another), then the first whole one (an HTML page)
    a, b = raw.find("<svg"), raw.rfind("</svg>")
    m = re.search(r"<svg[\s\S]*?</svg>", raw)
    root, err = None, None
    for svg in ([raw[a:b + 6]] if a >= 0 and b > a else []) + ([m.group(0)] if m else [raw]):
        try:
            root = ET.fromstring(svg)
            break
        except ET.ParseError as e:
            err = err or e
    if root is None:
        return {"ok": False, "errors": [{"msg": f"malformed SVG: {err}"}], "warnings": []}
    W = H = 0
    vb = root.get("viewBox", "").split()
    if len(vb) == 4:
        W, H = float(vb[2]), float(vb[3])
    def _tagged(name):
        return [el for el in root.iter() if str(el.tag).split("}")[-1] == name]
    texts = _tagged("text")
    if not any(t.get("font-size") == "24" for t in texts) and not _tagged("title"):
        warnings.append({"msg": "no <title>: screen readers and docs see an unnamed figure", "fix": "add <title> as the first child of <svg>"})
    if not _tagged("desc"):
        warnings.append({"msg": "no <desc>: add one-sentence content summary"})
    if re.search(r"font-family='[^\"\]]", svg):
        errors.append({"msg": "unquoted font-family attribute", "fix": 'wrap families: font-family="\'Inter\',sans-serif"'})
    if sum(1 for t in texts if t.get("font-size") == "24") > 1:
        warnings.append({"msg": "2+ hero titles inside one figure", "fix": "title once (page XOR figure)"})
    neg = [t.text for t in texts if (t.text or "").strip().startswith("-") and re.fullmatch(r"-\d[\d.,k]*", (t.text or "").strip())]
    if neg:
        warnings.append({"msg": f"negative ticks {neg}", "fix": "verify intended; ratio data floors at 0"})
    circles = len(_tagged("circle"))
    if circles > 400:
        warnings.append({"msg": f"{circles} points over render budget", "fix": "aggregate/facet"})
    for t in texts:
        try:
            x = float(t.get("x", "0").split()[0])
            if (x < -4 or (W and x > W + 4)) and t.get("text-anchor") != "middle":
                warnings.append({"msg": f"text '{(t.text or '')[:20]}' near canvas edge x={x}", "fix": "check clipping"})
                break
        except ValueError:
            pass
    dup = [t.text for t in texts if t.text]
    from collections import Counter
    for txt, c in Counter(dup).items():
        if c > 3 and len(txt) > 8:
            warnings.append({"msg": f"'{txt[:30]}' repeated {c}x", "fix": "dedupe title/caption/source"})
            break
    for it in _svg_geometry(root, W, H):
        (warnings if it["code"] == "newline" else errors).append(it)
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "stats": {"texts": len(texts), "points": circles, "canvas": [W, H]}}

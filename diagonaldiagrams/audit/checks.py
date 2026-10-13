"""The audit's checks: collisions an agent cannot see in its own output.

Each check reads the display list and appends issues ({code, msg, fix, at}). CHECKS runs in order,
and that order is the order issues are reported in. docs/DESIGN.md section 9.6 describes each one.
"""
import math
from types import SimpleNamespace

from ..geom import center, inside, near_pairs, overlap, path_crosses
from ..registry import Registry

CHECKS = Registry("check")  # name -> function(view, issues), with the codes it reports; run in order
WARNINGS = {"newline", "min-size", "colors"}  # codes that warn; every other code is an error


def check(name, *codes):
    return CHECKS.add(name, codes=codes)


def arrow_runs(arrows):
    """Axis-aligned arrow runs longer than 12 px: (arrow index, "h"|"v", line, low, high).
    Only the first 300 arrows: past that the pairwise checks would take too long."""
    runs = []
    for k, ar in enumerate(arrows[:300]):
        p = ar.pts
        for a, b in zip(p, p[1:]):
            if a is None or b is None:
                continue
            if abs(a[1] - b[1]) < 0.5 and abs(a[0] - b[0]) > 12:
                runs.append((k, "h", round(a[1], 1), min(a[0], b[0]), max(a[0], b[0])))
            elif abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) > 12:
                runs.append((k, "v", round(a[0], 1), min(a[1], b[1]), max(a[1], b[1])))
    return runs


@check("text lines", "newline", "clip")
def text_lines(v, issues):
    for t in v.texts:
        b = t.box
        if t.newline:
            issues.append({"code": "newline", "msg": f"label '{t.text[:30]}' has a line break; SVG draws it on one line",
                           "fix": "split it: name for the headline, sub for the detail", "at": center(b)})
        if v.W and v.H and (b[0] < -4 or b[2] > v.W + 4 or b[1] < -4 or b[3] > v.H + 4):
            issues.append({"code": "clip", "msg": f"label '{t.text[:30]}' runs off the canvas",
                           "fix": "shorten it", "at": center(b)})


@check("labels on labels", "collide")
def text_collide(v, issues):
    for i, j in v.near(v.tb):
        a, b = v.texts[i], v.texts[j]
        if a.text == b.text and abs(a.box[0] - b.box[0]) < 1 and abs(a.box[1] - b.box[1]) < 1:
            continue  # a halo drawn under its own label
        iw, ih = overlap(a.box, b.box)
        short = min(a.box[2] - a.box[0], b.box[2] - b.box[0])
        if iw > max(3.0, 0.15 * short) and ih > 0.4 * min(a.size, b.size):
            issues.append({"code": "collide", "msg": f"labels collide: '{a.text[:24]}' and '{b.text[:24]}'",
                           "fix": "shorten one, or move it (rank, lane, --note-at)", "at": center(a.box)})


@check("boxes on boxes", "overlap")
def shape_overlap(v, issues):
    for i, j in v.near(v.sb):
        a, b = v.sb[i], v.sb[j]
        iw, ih = overlap(a, b)
        if iw > 4 and ih > 4 and not inside(a, b) and not inside(b, a):
            issues.append({"code": "overlap", "msg": f"boxes overlap at {center((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))}",
                           "fix": "give them different rank or lane, or fewer items per row", "at": center(a)})


@check("arrows through boxes and labels", "through", "strike")
def arrow_paths(v, issues):
    sb, tb = v.sb, v.tb
    # A group frame holds whole boxes. A node holding only its own tag pill is still a node.
    holders = {i for i, j in v.near(sb, sb)
               if i != j and inside(sb[i], sb[j]) and not inside(sb[j], sb[i]) and sb[j][3] - sb[j][1] >= 24}
    # A pill behind an arrow label masks the arrow on purpose: a short shape around one line of text.
    holders |= {i for i, j in v.near(sb, tb)
                if inside(sb[i], tb[j], tol=4) and sb[i][3] - sb[i][1] <= 2.5 * (tb[j][3] - tb[j][1])}
    for ar in v.arrows:
        segs = [(ar.pts[k], ar.pts[k + 1]) for k in range(len(ar.pts) - 1)
                if ar.pts[k] is not None and ar.pts[k + 1] is not None]
        if not segs:
            continue
        # the arrow's bounding box: anything outside it cannot be crossed, so skip it cheaply
        ax0 = min(min(p[0], q[0]) for p, q in segs)
        ay0 = min(min(p[1], q[1]) for p, q in segs)
        ax1 = max(max(p[0], q[0]) for p, q in segs)
        ay1 = max(max(p[1], q[1]) for p, q in segs)

        def apart(b):
            return b[2] < ax0 or b[0] > ax1 or b[3] < ay0 or b[1] > ay1
        for i, b in enumerate(sb):
            if apart(b):
                continue
            if i in holders or any(b[0] - 6 <= e[0] <= b[2] + 6 and b[1] - 6 <= e[1] <= b[3] + 6 for e in ar.ends):
                continue  # a group frame, or the box this arrow leaves or enters
            core = (b[0] + 3, b[1] + 3, b[2] - 3, b[3] - 3)
            if core[2] > core[0] and core[3] > core[1] and path_crosses(segs, core):
                issues.append({"code": "through", "msg": f"an arrow runs through the box at {center(b)}",
                               "fix": "move one node to another lane or rank so the arrow goes around it", "at": center(b)})
        for cx, cy, hw, hh in v.diamonds:
            if apart((cx - hw, cy - hh, cx + hw, cy + hh)):
                continue
            if any(abs(e[0] - cx) <= hw + 6 and abs(e[1] - cy) <= hh + 6 for e in ar.ends):
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
        for cx, cy, rx, ry in v.ellipses:
            if apart((cx - rx, cy - ry, cx + rx, cy + ry)):
                continue
            if any(((e[0] - cx) / (rx + 6)) ** 2 + ((e[1] - cy) / (ry + 6)) ** 2 <= 1 for e in ar.ends):
                continue  # the circle this arrow leaves or enters
            hit = False
            for p, q in segs:
                n = max(1, int(math.hypot(q[0] - p[0], q[1] - p[1]) // 4))
                if any(((p[0] + (q[0] - p[0]) * k / n - cx) / rx) ** 2 + ((p[1] + (q[1] - p[1]) * k / n - cy) / ry) ** 2 < 0.81
                       for k in range(n + 1)):
                    hit = True
                    break
            if hit:
                issues.append({"code": "through", "msg": f"an arrow runs through the circle at {[round(cx), round(cy)]}",
                               "fix": "move one node so the arrow goes around it", "at": [round(cx), round(cy)]})
        for t in v.texts:
            if t.z > ar.z or apart(t.box):
                continue  # the label is painted over the arrow, on purpose, or is nowhere near it
            b = t.box
            h = b[3] - b[1]
            core = (b[0] + 1, b[1] + 0.2 * h, b[2] - 1, b[3] - 0.2 * h)
            if core[2] > core[0] and path_crosses(segs, core):
                issues.append({"code": "strike", "msg": f"an arrow is drawn across the label '{t.text[:24]}'",
                               "fix": "move the node or the label off the arrow's path", "at": center(b)})


@check("arrows on one line", "shared")
def shared_runs(v, issues):
    # Two arrows on one line, or ending within 12px of each other on it, read as one arrow
    # that forks: nobody can tell where each goes.
    runs = v.runs
    shared = set()
    # only runs in the same direction within 2px of each other can share a line: find those pairs
    # through a sort, then look at them in the order a full pairwise scan would
    order = sorted(range(len(runs)), key=lambda k: (runs[k][1], runs[k][2]))
    pairs = []
    for x, i in enumerate(order):
        for j in order[x + 1:]:
            if runs[j][1] != runs[i][1] or runs[j][2] - runs[i][2] >= 2:
                break
            pairs.append((min(i, j), max(i, j)))
    for i, j in sorted(pairs):
        ka, da, ca, la, ha = runs[i]
        kb, db, cb, lb, hb = runs[j]
        sa, ea = v.arrows[ka].ends
        sb, eb = v.arrows[kb].ends
        joint = math.hypot(sa[0] - sb[0], sa[1] - sb[1]) < 3 or math.hypot(ea[0] - eb[0], ea[1] - eb[1]) < 3
        if ka != kb and not joint and da == db and abs(ca - cb) < 2 and min(ha, hb) - max(la, lb) > -12 and (ka, kb) not in shared:
            shared.add((ka, kb))
            mid = (max(la, lb) + min(ha, hb)) / 2
            where = [round(mid), round(ca)] if da == "h" else [round(ca), round(mid)]
            issues.append({"code": "shared", "msg": f"two arrows run on one line at {where}",
                           "fix": "reorder the row or move one node so the arrows take separate paths", "at": where})


@check("labels on decision outlines", "collide")
def diamond_labels(v, issues):
    for t in v.texts:
        b = t.box
        mx, my = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        for cx, cy, hw, hh in v.diamonds:
            if abs(mx - cx) / hw + abs(my - cy) / hh <= 1:
                continue  # the decision's own question
            # measured with the label's background pill, which is what covers the outline
            corners = [(b[0] - 7, b[1] - 2), (b[2] + 7, b[1] - 2), (b[0] - 7, b[3] + 2), (b[2] + 7, b[3] + 2)]
            if any(abs(x - cx) / hw + abs(y - cy) / hh < 1.0 for x, y in corners):
                issues.append({"code": "collide", "msg": f"label '{t.text[:24]}' sits on the edge of a decision",
                               "fix": "move the label or the node so the decision shows whole", "at": [round(mx), round(my)]})


@check("group frames", "intrude", "collide")
def group_frames(v, issues):
    for fr in v.frames:
        fb, gid, members = fr.box, fr.group, fr.members
        for nd in v.named:
            nb, nid = nd.box, nd.node
            cx, cy = (nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2
            if nid not in members and fb[0] < cx < fb[2] and fb[1] < cy < fb[3]:
                issues.append({"code": "intrude", "msg": f"node '{nid}' sits inside group '{gid}' but is not in it",
                               "fix": "move it to another row or lane, or add it to the group", "at": [round(cx), round(cy)]})
        # a frame's border runs across a line of text (a subtitle above it, a label at its edge)
        for t in v.texts:
            b = t.box
            across_h = b[0] < fb[2] and fb[0] < b[2] and any(b[1] + 1 < y < b[3] - 1 for y in (fb[1], fb[3]))
            across_v = b[1] < fb[3] and fb[1] < b[3] and any(b[0] + 1 < x < b[2] - 1 for x in (fb[0], fb[2]))
            if across_h or across_v:
                mx, my = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                issues.append({"code": "collide", "msg": f"the frame of group '{gid}' runs through '{t.text[:24]}'",
                               "fix": "move the text or the group's members so the frame clears it", "at": [round(mx), round(my)]})


def _under(v, t):
    """The paint under a text: the last solid fill painted before it whose shape holds its middle,
    as (color, opacity), or the figure's own background."""
    cx, cy = (t.box[0] + t.box[2]) / 2, (t.box[1] + t.box[3]) / 2
    under = None
    for it in v.items:
        if it is t:
            break
        if it.kind == "shape" and it.fill and it.box and it.box[0] <= cx <= it.box[2] and it.box[1] <= cy <= it.box[3]:
            paint = str(it.fill[0]).strip().lower()
            if paint not in ("none", "transparent") and not paint.startswith("url("):
                under = it
    return under.fill if under is not None else ("#ffffff", 1.0)


@check("text contrast", "contrast")
def text_contrast(v, issues):
    # WCAG AA: 4.5:1, or 3:1 for large text (18.66 px, or 14 px bold). Judged where a stylesheet chose
    # the color; the default themes' own shortfalls are known bug B25.
    from ..style.parse import Color, color, contrast
    for t in v.texts:
        if not t.color_from:
            continue
        try:
            fg = color(t.color)
            bg_color, alpha = _under(v, t)
            bg = color(bg_color)
        except Exception:
            continue
        if alpha < 1:
            bg = Color(bg.r, bg.g, bg.b, bg.a * alpha)
        ratio = contrast(fg, bg)
        need = 3.0 if t.size >= 18.66 or (t.size >= 14 and t.bold) else 4.5
        if ratio < need:
            mx, my = (t.box[0] + t.box[2]) / 2, (t.box[1] + t.box[3]) / 2
            issues.append({"code": "contrast",
                           "msg": f"'{t.text[:24]}' is {t.color} on {bg_color}: {ratio:.1f}:1, under the {need:g}:1 "
                                  f"WCAG AA asks for; the color comes from {t.color_from}",
                           "fix": "darken the text or lighten what is under it, in that rule", "at": [round(mx), round(my)]})


@check("text size", "min-size")
def min_size(v, issues):
    for t in v.texts:
        if t.size_from and t.size < 9:
            issues.append({"code": "min-size", "msg": f"'{t.text[:24]}' is {t.size:g} px, under 9 px; the size comes from "
                                                       f"{t.size_from}", "fix": "use 9 px or more", "at": [round(t.box[0]), round(t.box[1])]})


@check("colors", "colors")
def too_many_colors(v, issues):
    # More than 8 distinct node colors stop meaning anything: nobody tells the ninth apart.
    from ..style.parse import color
    import colorsys
    seen = []
    for it in v.named:
        paint = str((it.fill or ("none",))[0]).strip().lower()
        if paint in seen or paint in ("none", "transparent") or paint.startswith("url("):
            continue
        try:
            c = color(paint)
        except Exception:
            continue
        if colorsys.rgb_to_hls(c.r / 255, c.g / 255, c.b / 255)[2] >= 0.2:  # greys and whites carry no meaning
            seen.append(paint)
    if len(seen) > 8:
        issues.append({"code": "colors", "msg": f"{len(seen)} distinct node colors: past 8 a reader can't keep them apart",
                       "fix": "group values into 8 or fewer, or encode the rest another way (border, shape, label)",
                       "at": [0, 0]})


@check("labels in their boxes", "spill")
def spill(v, issues):
    rects = [s.box for s in v.shapes if s.tag == "rect"]
    hosts = {}
    for i, j in v.near(v.tb, rects):
        b, r = v.tb[i], rects[j]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
            if i not in hosts or (r[2] - r[0]) * (r[3] - r[1]) < (hosts[i][2] - hosts[i][0]) * (hosts[i][3] - hosts[i][1]):
                hosts[i] = r
    for i, r in sorted(hosts.items()):
        t, b = v.texts[i], v.tb[i]
        # a background drawn to the text's own size (Mermaid's arrow labels) is not a box to fit in
        tight = (r[3] - r[1]) <= 1.8 * (b[3] - b[1]) and (r[2] - r[0]) <= (b[2] - b[0]) + 2 * t.size
        if not tight:
            if b[0] < r[0] + 2 or b[2] > r[2] - 2 or b[1] < r[1] or b[3] > r[3]:  # 2px clear at the sides, inside at top and bottom
                issues.append({"code": "spill", "msg": f"label '{t.text[:30]}' fills or overflows its box",
                               "fix": "2-4 words for a name; put detail in sub", "at": center(b)})


def run_checks(dl, stats=None):
    """Every check over a display list, as issues without duplicates. stats, if given, gets
    the arrows' crossings and total run length (the layout repair loops' cost)."""
    texts = dl.texts
    if len(texts) > 1500:
        # Past this nobody reads the labels, and pairwise checks would take minutes.
        return [{"code": "dense", "msg": f"{len(texts)} labels on one figure",
                 "fix": "aggregate to top-N + Other, facet, or pass --no-audit", "at": [0, 0]}]
    shapes = dl.shapes
    if len(shapes) > 4000:
        shapes = []
    arrows = dl.arrows
    v = SimpleNamespace(W=dl.width, H=dl.height, texts=texts, shapes=shapes, arrows=arrows, items=dl.items,
                        frames=dl.frames, named=dl.named, diamonds=dl.diamonds, ellipses=dl.ellipses,
                        tb=[t.box for t in texts], sb=[s.box for s in shapes], runs=arrow_runs(arrows),
                        near=lambda xs, ys=None: near_pairs(xs, ys, dl.width, dl.height))
    issues = []
    for _, fn, _ in CHECKS.items():
        fn(v, issues)
    if stats is not None:
        hs = [r for r in v.runs if r[1] == "h"]
        vs = [r for r in v.runs if r[1] == "v"]
        stats["crossings"] = sum(1 for kh, _, y, x0, x1 in hs for kv, _, x, y0, y1 in vs
                                 if kh != kv and x0 + 1 < x < x1 - 1 and y0 + 1 < y < y1 - 1)
        stats["wire"] = sum(r[4] - r[3] for r in v.runs)
    out, seen = [], set()
    for it in issues:
        k = (it["code"], it["msg"])
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out

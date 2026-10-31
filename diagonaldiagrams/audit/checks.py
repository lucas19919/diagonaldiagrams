"""The audit's checks: collisions an agent cannot see in its own output.

Each check reads the display list and appends issues ({code, msg, fix, at}). CHECKS runs in order,
and that order is the order issues are reported in.
"""
import math
from types import SimpleNamespace

from ..geom import center, inside, length_inside, near_pairs, overlap
from ..registry import Registry

CHECKS = Registry("check")  # name -> function(view, issues), with the codes it reports; run in order
WARNINGS = {"newline", "min-size", "colors", "truncated", "font-fallback", "shaping"}  # codes that warn; others are errors


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


def _crosses(spans, b):
    """geom.path_crosses(segments, b) for segments given with their bounding boxes, (p, q, x0, y0,
    x1, y1): one lying wholly apart from b runs exactly 0 px inside it, so it is not measured."""
    total = 0.0
    for p, q, x0, y0, x1, y1 in spans:
        if x1 < b[0] or x0 > b[2] or y1 < b[1] or y0 > b[3]:
            continue
        total += length_inside(p, q, b)
        if total > 2:
            return True
    return False


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
        # each segment with its bounding box, and the arrow's: anything outside it cannot be crossed,
        # so skip it cheaply
        spans = [(p, q, min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])) for p, q in segs]
        ax0 = min(s[2] for s in spans)
        ay0 = min(s[3] for s in spans)
        ax1 = max(s[4] for s in spans)
        ay1 = max(s[5] for s in spans)

        def apart(b):
            return b[2] < ax0 or b[0] > ax1 or b[3] < ay0 or b[1] > ay1
        for i, b in enumerate(sb):
            if b[2] < ax0 or b[0] > ax1 or b[3] < ay0 or b[1] > ay1:
                continue
            if i in holders or any(b[0] - 6 <= e[0] <= b[2] + 6 and b[1] - 6 <= e[1] <= b[3] + 6 for e in ar.ends):
                continue  # a group frame, or the box this arrow leaves or enters
            core = (b[0] + 3, b[1] + 3, b[2] - 3, b[3] - 3)
            if core[2] > core[0] and core[3] > core[1] and _crosses(spans, core):
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
            b = t.box
            if t.z > ar.z or b[2] < ax0 or b[0] > ax1 or b[3] < ay0 or b[1] > ay1:
                continue  # the label is painted over the arrow, on purpose, or is nowhere near it
            h = b[3] - b[1]
            core = (b[0] + 1, b[1] + 0.2 * h, b[2] - 1, b[3] - 0.2 * h)
            if core[2] > core[0] and _crosses(spans, core):
                issues.append({"code": "strike", "msg": f"an arrow is drawn across the label '{t.text[:24]}'",
                               "fix": "move the node or the label off the arrow's path", "at": center(b)})


@check("arrows on one line", "shared")
def shared_runs(v, issues):
    # Two arrows on one line, or ending within 12px of each other on it, read as one arrow
    # that forks: nobody can tell where each goes. Arrows that leave or arrive at one point and
    # split (a trunk) are drawn so on purpose, unless two leaving together both carry a label: then
    # the labels sit on the one bar they share, each far from its own line.
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
        if v.arrows[ka].label and v.arrows[kb].label and math.hypot(sa[0] - sb[0], sa[1] - sb[1]) < 3:
            joint = False  # a labelled trunk
        # one arrow ends where the other begins (through a junction dot) and they only meet end to
        # end: that is one path, drawn on purpose
        chained = ((math.hypot(ea[0] - sb[0], ea[1] - sb[1]) < 10 or math.hypot(eb[0] - sa[0], eb[1] - sa[1]) < 10)
                   and min(ha, hb) - max(la, lb) <= 0)
        if ka != kb and not joint and not chained and da == db and abs(ca - cb) < 2 and min(ha, hb) - max(la, lb) > -12 and (ka, kb) not in shared:
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
            if hw > 0 and hh > 0 and (b[2] + 8 < cx - hw or b[0] - 8 > cx + hw or b[3] + 3 < cy - hh or b[1] - 3 > cy + hh):
                continue  # the pill (7 px beside the text, 2 above and below) is over a pixel clear of it
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


def _layers(v):
    """The solid fills in paint order, read once per figure: (position in v.items, box, Color or
    None when the fill can't be read, opacity); and each text's position."""
    from ..style.parse import color
    layers, at, seen = [], {}, {}
    for k, it in enumerate(v.items):
        if it.kind == "text":
            at[id(it)] = k
        elif it.kind in ("shape", "face") and it.fill and it.box:
            paint = str(it.fill[0]).strip().lower()
            if paint in ("none", "transparent") or paint.startswith("url("):
                continue
            if paint not in seen:
                try:
                    seen[paint] = color(paint)
                except Exception:
                    seen[paint] = None
            layers.append((k, it.box, seen[paint], it.fill[1], it.pts if it.kind == "face" else None))
    return layers, at


def _under(t, layers, at):
    """The paint under a text's middle: every solid fill painted before it whose shape holds that
    point, laid in paint order over a white page, so a translucent fill is read over what it covers.
    Returns (Color, words for the message), or None when a fill can't be read."""
    from ..style.parse import Color
    cx, cy = (t.box[0] + t.box[2]) / 2, (t.box[1] + t.box[3]) / 2
    bg, words = Color(255, 255, 255), "#ffffff"
    mine = at[id(t)]
    from ..geom import in_convex
    for k, b, c, opacity, outline in layers:
        if k > mine:
            break
        if b[0] <= cx <= b[2] and b[1] <= cy <= b[3] and (outline is None or in_convex((cx, cy), outline)):
            if c is None:
                return None
            a = c.a * opacity
            if a >= 1:
                bg, words = c, c.css
            elif a > 0:
                bg = Color(c.r * a + bg.r * (1 - a), c.g * a + bg.g * (1 - a), c.b * a + bg.b * (1 - a))
                words = f"{c.css} at {a:.2g} over {words.split(' over ')[-1]}"
    return bg, words


@check("text contrast", "contrast")
def text_contrast(v, issues):
    # WCAG AA: 4.5:1, or 3:1 for large text (18.66 px, or 14 px bold). Judged where a stylesheet chose
    # the color, and everywhere on a figure whose defaults pass (data-legibility="all": flow, arch, seq
    # and schema). The chart kinds' defaults still fall short, so there only styled text is judged.
    from ..style.parse import color, contrast
    layers = None
    for t in v.texts:
        if not (t.color_from or v.every):
            continue
        try:
            fg = color(t.color)
        except Exception:
            continue
        if layers is None:
            layers = _layers(v)
        under = _under(t, *layers)
        if under is None:
            continue
        bg, bg_color = under
        ratio = contrast(fg, bg)
        need = 3.0 if t.size >= 18.66 or (t.size >= 14 and t.bold) else 4.5
        if ratio < need:
            mx, my = (t.box[0] + t.box[2]) / 2, (t.box[1] + t.box[3]) / 2
            where = f"the color comes from {t.color_from}" if t.color_from else "the color is the theme's default"
            issues.append({"code": "contrast",
                           "msg": f"'{t.text[:24]}' is {t.color} on {bg_color}: {ratio:.1f}:1, under the {need:g}:1 "
                                  f"WCAG AA asks for; {where}",
                           "fix": ("darken the text or lighten what is under it, in that rule" if t.color_from else
                                   "set a darker color for it in a stylesheet; a default that fails is a bug"),
                           "at": [round(mx), round(my)]})


@check("text size", "min-size")
def min_size(v, issues):
    for t in v.texts:
        if (t.size_from or v.every) and t.size < 9:
            where = f"the size comes from {t.size_from}" if t.size_from else "the size is the preset's default"
            issues.append({"code": "min-size", "msg": f"'{t.text[:24]}' is {t.size:g} px, under 9 px; {where}",
                           "fix": "use 9 px or more", "at": [round(t.box[0]), round(t.box[1])]})


@check("fonts found", "font-fallback")
def font_fallback(v, issues):
    # One warning per font a stylesheet named that this machine doesn't have.
    seen = set()
    for t in v.texts:
        if t.font_fallback and t.font_fallback not in seen:
            seen.add(t.font_fallback)
            issues.append({"code": "font-fallback",
                           "msg": f"the font '{t.font_fallback}' isn't installed here, so text was measured by the built-in "
                                  "estimate and may not fit where it is shown",
                           "fix": "install it, or name its file in the stylesheet's \"fonts\" or with --font PATH",
                           "at": [round(t.box[0]), round(t.box[1])]})


@check("shaped scripts", "shaping")
def shaping(v, issues):
    # One warning per script whose letters join or reorder: their widths here are estimates.
    seen = set()
    for t in v.texts:
        for script in (t.shaping or "").split(", "):
            if script and script not in seen:
                seen.add(script)
                issues.append({"code": "shaping",
                               "msg": f"{script} text needs shaping, which this engine doesn't do, so its widths are estimates",
                               "fix": "check that the labels fit; a HarfBuzz shaper can be added as a toolkit (P13)",
                               "at": [round(t.box[0]), round(t.box[1])]})


@check("cut text", "truncated")
def truncated(v, issues):
    # Text that ends in an ellipsis lost words the reader can't get back: say where, once per text.
    for t in v.texts:
        if t.text.endswith(("...", "…")) and len(t.text) > 3:
            issues.append({"code": "truncated", "msg": f"'{t.text[:32]}' was cut short",
                           "fix": "let it wrap: make the box wider or the text shorter, or drop overflow: ellipsis",
                           "at": [round(t.box[0]), round(t.box[1])]})


@check("colors", "colors")
def too_many_colors(v, issues):
    # More than 8 distinct node colors stop meaning anything: nobody tells the ninth apart.
    from ..style.parse import color
    if len({str((it.fill or ("none",))[0]).strip().lower() for it in v.named} - {"none", "transparent"}) <= 8:
        return  # 8 fills or fewer: never too many, whatever their saturation (and colorsys stays unloaded)
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


def _holders(tops):
    """The solids others stand on (a slab under its blocks): ground, not an obstacle to an arrow."""
    out = set()
    for s, a in tops.items():
        for r, b in tops.items():
            if r != s and abs(b[2] - a[5]) < .5 and b[0] >= a[0] - .5 and b[3] <= a[3] + .5 and b[1] >= a[1] - .5 \
                    and b[4] <= a[4] + .5:
                out.add(s)
                break
    return out


@check("depth", "hidden", "spill", "through", "overlap")
def depth(v, issues):
    """A projected 3D figure (iso.py): faces are their own outlines, painted in depth order, so what
    is painted later hides what is under it. Reads data-solid, data-box3 and data-face back."""
    faces = v.faces
    if not faces:
        return
    from ..geom import in_convex, length_in_convex
    at = {id(it): k for k, it in enumerate(v.items)}
    last, tops = {}, {}  # solid -> where its last face is painted; solid -> its box, from its top face
    for f in faces:
        last[f.solid] = at[id(f)]
        if f.box3:
            tops[f.solid] = f.box3
    top_face = {f.solid: f for f in faces if f.box3}
    for ar in v.arrows:
        if ar.solid:
            last[ar.solid] = at[id(ar)]
    for t in v.texts:
        mine = last.get(t.on, at[id(t)]) if t.on else at[id(t)]
        c = center(t.box)
        cover = next((f for f in faces if f.solid != t.on and at[id(f)] > mine and in_convex(c, f.pts)), None)
        if cover is not None:
            issues.append({"code": "hidden", "msg": f"'{t.text[:24]}' is hidden behind '{cover.solid}'",
                           "fix": ("stand the linked items in one column (col), so the link and its label drop straight down"
                                   if str(t.on).startswith("link:") else
                                   "give the layers more room, or move the item to a column nothing stands in front of"),
                           "at": c})
            continue
        top = top_face.get(t.on)
        if top is not None:
            x0, y0, x1, y1 = t.box
            if not all(in_convex(p, top.pts, tol=1) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
                issues.append({"code": "spill", "msg": f"label '{t.text[:30]}' runs off the top of '{t.on}'",
                               "fix": "2-4 words for a name; put detail in sub", "at": c})
    ground = _holders(tops)
    for ar in v.arrows:
        segs = [(ar.pts[k], ar.pts[k + 1]) for k in range(len(ar.pts) - 1)
                if ar.pts[k] is not None and ar.pts[k + 1] is not None]
        if not segs:
            continue
        mine = at[id(ar)]
        touch = {f.solid for f in faces if any(in_convex(e, f.pts, tol=3) for e in ar.ends)}
        behind, over = {}, {}
        for f in faces:
            if f.solid == ar.solid:
                continue
            run = sum(length_in_convex(p, q, f.pts) for p, q in segs)
            if run <= 0:
                continue
            if at[id(f)] > mine:
                behind[f.solid] = behind.get(f.solid, 0) + run
            elif f.solid not in touch and f.solid not in ground:
                over[f.solid] = over.get(f.solid, 0) + run
        name = f"the arrow {ar.attach['from']['node']} -> {ar.attach['to']['node']}" if ar.attach else "an arrow"
        for s, run in behind.items():
            if run > 4:
                issues.append({"code": "hidden", "msg": f"{name} runs behind '{s}' for {run:.0f} px",
                               "fix": "link items in neighbouring layers only", "at": center(ar.box or segs[0][0] + segs[-1][1])})
        for s, run in over.items():
            if run > 4:
                issues.append({"code": "through", "msg": f"{name} crosses '{s}'",
                               "fix": "stand the two linked items in one column (col), so the link drops straight down",
                               "at": [round(c) for c in segs[0][0]]})
    solids = sorted(tops.items())
    for i, (s, a) in enumerate(solids):
        for r, b in solids[i + 1:]:
            if all(min(a[k + 3], b[k + 3]) - max(a[k], b[k]) > .5 for k in range(3)):
                issues.append({"code": "overlap", "msg": f"'{s}' and '{r}' run into each other",
                               "fix": "give them different columns or layers", "at": [0, 0]})


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
    v = SimpleNamespace(W=dl.width, H=dl.height, texts=texts, shapes=shapes, arrows=arrows, items=dl.items, faces=dl.faces,
                        every=dl.legibility == "all",
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

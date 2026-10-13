"""SVG building blocks: markers, boxes, diamonds, ports, arrow routing, frames, labels, ticks, icons."""
from ._text import _text_w, _wrap, _wrap_px, esc
from ._theme import FONT, MONO, SANS, SERIF


def render_pincallout(t, px, py, text, above=True, top=None):
    """In-plot journal callout: masked italic label + leader dot on the point."""
    lines = _wrap(text, 26, 2)
    w = max([len(l) for l in lines] + [4]) * 6.8 + 16
    h = 12 + 15 * len(lines)
    ty = py - 12 - h if above else py + 12
    if top is not None:
        ty = max(ty, top)
    yo = py + (-4 if above else 4)
    s = [f'<line x1="{px:.1f}" y1="{yo:.1f}" x2="{px:.1f}" y2="{(ty + h) if above else ty:.1f}" stroke="{t["soft"]}" stroke-width="1"/>',
         f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{t["accent"]}"/>',
         f'<rect x="{px - w/2:.1f}" y="{ty:.1f}" width="{w:.1f}" height="{h:.1f}" rx="3" fill="{t["card"]}" stroke="{t["rule"]}" stroke-width="1"/>']
    for j, ln in enumerate(lines):
        s.append(f'<text x="{px:.1f}" y="{ty + 16 + j*15:.1f}" font-size="11.5" font-style="italic" font-family="{SERIF}" fill="{t["ink"]}" text-anchor="middle">{esc(ln)}</text>')
    return "\n".join(s)


def render_noterail(t, notes, rail_x, top, lh=92):
    """Right-rail editorial callouts: italic serif note + thin leader to (ax, ay).
    notes = [(ax, ay, text)]. Caller widens canvas by 200 when notes exist."""
    s = []
    for i, (ax, ay, text) in enumerate(notes):
        ry = top + 14 + i * lh
        tx = rail_x + 14
        s.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{tx:.1f}" y2="{ry:.1f}" stroke="{t["soft"]}" stroke-width="1"/>')
        s.append(f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="2.5" fill="{t["accent"]}"/>')
        for j, ln in enumerate(_wrap(text)):
            s.append(f'<text x="{tx:.1f}" y="{ry + 4 + j * 16:.1f}" font-size="13" font-style="italic" font-family="{SERIF}" fill="{t["ink"]}">{esc(ln)}</text>')
    return "\n".join(s)


def figure_heading(t, title, subtitle, x=28):
    """Title and subtitle drawn on the figure. Returns (svg bits, block height)."""
    bits, y = [], 8
    if title:
        y += 18
        bits.append(
            f'<text x="{x}" y="{y}" font-size="18" font-weight="600" font-family="{FONT}" fill="{t["ink"]}">{esc(title)}</text>')
    if subtitle:
        y += 18
        bits.append(
            f'<text x="{x}" y="{y}" font-size="13" font-family="{FONT}" fill="{t["muted"]}">{esc(subtitle)}</text>')
    return bits, ((y + 16) if bits else 8)


def markers(t):
    def one(mid, fill):
        # userSpaceOnUse keeps the head a fixed size, so direction stays readable on a thin stroke
        return (f'<marker id="{mid}" markerWidth="12" markerHeight="9" refX="11" refY="4.5" '
                f'orient="auto" markerUnits="userSpaceOnUse">'
                f'<polygon points="0 0,12 4.5,0 9" fill="{fill}"/></marker>')
    return "<defs>" + one("a", t["muted"]) + one("aa", t["accent"]) + one("al", t["link"]) + one("ar", t["soft"]) + "</defs>"


def elbow(x1, y1, x2, y2, r=8):
    """Rounded orthogonal path between (x1,y1)->(x2,y2)."""
    if x1 == x2 or y1 == y2:
        return f"M{x1},{y1} L{x2},{y2}"
    mx = x2 if abs(x2 - x1) < 60 else (x1 + x2) / 2
    # horizontal then vertical with rounded corner
    sx = 1 if x2 > mx else -1
    sy = 1 if y2 > y1 else -1
    return (f"M{x1},{y1} L{mx - sx*r},{y1} Q{mx},{y1} {mx},{y1 + sy*r} L{mx},{y2 - sy*r} "
            f"Q{mx},{y2} {mx + sx*r},{y2} L{x2},{y2}")


def axis_ticks(vmin, vmax, n=5):
    """Nice ticks with one spare step above vmax so a bar and its label stay inside the plot."""
    ticks = nice_ticks(vmin, vmax, n=n)
    if len(ticks) < 2:
        step = (vmax - vmin) or 1
        return [round(vmin, 10), round(vmin + step, 10)]
    if vmax >= ticks[-1] - 1e-9:
        step = ticks[-1] - ticks[-2] or 1
        ticks = list(ticks) + [round(ticks[-1] + step, 10)]
    return ticks


def bar_path(x, y, w, h, rx, cap="top"):
    """Bar path. The end on the baseline is square; only the free end is rounded.
    cap is 'top' or 'bottom' (vertical) or 'right' or 'left' (horizontal)."""
    if w <= 0 or h <= 0:
        return ""
    rx = 0 if rx <= 0 else min(float(rx), w / 2.0, h / 2.0)
    if rx <= 0.01:
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"'
    x2, y2 = x + w, y + h
    if cap == "top":
        d = (f"M{x:.1f},{y2:.1f} L{x:.1f},{y+rx:.1f} Q{x:.1f},{y:.1f} {x+rx:.1f},{y:.1f} "
             f"L{x2-rx:.1f},{y:.1f} Q{x2:.1f},{y:.1f} {x2:.1f},{y+rx:.1f} L{x2:.1f},{y2:.1f} Z")
    elif cap == "bottom":
        d = (f"M{x:.1f},{y:.1f} L{x:.1f},{y2-rx:.1f} Q{x:.1f},{y2:.1f} {x+rx:.1f},{y2:.1f} "
             f"L{x2-rx:.1f},{y2:.1f} Q{x2:.1f},{y2:.1f} {x2:.1f},{y2-rx:.1f} L{x2:.1f},{y:.1f} Z")
    elif cap == "left":
        d = (f"M{x2:.1f},{y:.1f} L{x+rx:.1f},{y:.1f} Q{x:.1f},{y:.1f} {x:.1f},{y+rx:.1f} "
             f"L{x:.1f},{y2-rx:.1f} Q{x:.1f},{y2:.1f} {x+rx:.1f},{y2:.1f} L{x2:.1f},{y2:.1f} Z")
    else:
        d = (f"M{x:.1f},{y:.1f} L{x2-rx:.1f},{y:.1f} Q{x2:.1f},{y:.1f} {x2:.1f},{y+rx:.1f} "
             f"L{x2:.1f},{y2-rx:.1f} Q{x2:.1f},{y2:.1f} {x2-rx:.1f},{y2:.1f} L{x:.1f},{y2:.1f} Z")
    return f'<path d="{d}"'


_SIDE = {"n": (0.0, -1.0), "s": (0.0, 1.0), "e": (1.0, 0.0), "w": (-1.0, 0.0)}


def _node_box(node):
    sh = (node or {}).get("shape", "rect")
    if sh == "dot":
        return sh, 4.0, 4.0
    if sh == "diamond":
        return sh, 80.0, float(node.get("_h", 64)) / 2.0
    return "box", 80.0, float((node or {}).get("_h", BOX_H)) / 2.0


def node_side(cx, cy, node, tx, ty):
    """Side of the node that faces (tx, ty)."""
    sh, hw, hh = _node_box(node)
    if sh == "dot":
        return "s"
    dx, dy = tx - cx, ty - cy
    if abs(dx) <= hw and abs(dy) > abs(dx):
        return "s" if dy > 0 else "n"
    if abs(dy) <= hh and abs(dx) >= abs(dy):
        return "e" if dx > 0 else "w"
    if abs(dx) >= abs(dy):
        return "e" if dx >= 0 else "w"
    return "s" if dy >= 0 else "n"


def port_on(cx, cy, node, side, along=0.0):
    """Point on a side. along slides it so two arrows do not share one pixel.
    A lone diamond exit stays on the vertex (along 0)."""
    sh, hw, hh = _node_box(node)
    if sh == "dot":
        return cx, cy
    vx, vy = _SIDE[side]
    tx, ty = -vy, vx
    lim = 12.0 if sh == "diamond" else max(8.0, (hh if side in ("e", "w") else hw) - 10.0)
    along = max(-lim, min(lim, along))
    return cx + vx * hw + tx * along, cy + vy * hh + ty * along


def node_port(cx, cy, node, tx, ty):
    """Center of the side facing (tx, ty). Diamond vertices and box edge-centers, never the node interior."""
    side = node_side(cx, cy, node, tx, ty)
    x, y = port_on(cx, cy, node, side, 0.0)
    return x, y, side


def _slots(n, lo, hi):
    """n positions inside [lo, hi], centered, at most 22px apart."""
    if n <= 1:
        return [(lo + hi) / 2.0]
    span = hi - lo
    gap = min(22.0, span / (n - 1))
    width = gap * (n - 1)
    start = (lo + hi) / 2.0 - width / 2.0
    return [start + i * gap for i in range(n)]


def assign_ports(pos, edges, layered=False, fixed=None, trunk=False):
    """Spread arrows along a side. Outgoing and incoming on the same side get opposite halves,
    so a return arrow does not leave from the pixel it arrived on."""
    sides = []
    buckets = {}
    for i, e in enumerate(edges):
        if e.get("from") not in pos or e.get("to") not in pos:
            sides.append(None)
            continue
        x1, y1, n1 = pos[e["from"]]
        x2, y2, n2 = pos[e["to"]]
        if fixed and i in fixed:
            s1, s2 = fixed[i]
        elif layered and abs(y2 - y1) > 1:
            # between rows: out the bottom, sideways in the gap, in the top. Never along a row.
            s1, s2 = ("s", "n") if y2 > y1 else ("n", "s")
        else:
            s1 = node_side(x1, y1, n1, x2, y2)
            s2 = node_side(x2, y2, n2, x1, y1)
        sides.append((s1, s2))
        # port_on slides along the side's tangent, which runs right-to-left on "s" and
        # bottom-to-top on "w". Flip the key there, so the leftmost target gets the leftmost port.
        k_out = (y2 if s1 in ("e", "w") else x2) * (-1 if s1 in ("s", "w") else 1)
        k_in = (y1 if s2 in ("e", "w") else x1) * (-1 if s2 in ("s", "w") else 1)
        buckets.setdefault((e["from"], s1), []).append((i, "out", k_out))
        buckets.setdefault((e["to"], s2), []).append((i, "in", k_in))
    along = {}
    for (nid, side), items in buckets.items():
        sh, hw, hh = _node_box(pos[nid][2])
        lim = 0.0 if sh in ("diamond", "dot") else max(8.0, (hh if side in ("e", "w") else hw) - 10.0)
        outs = sorted((it for it in items if it[1] == "out"), key=lambda t: t[2])
        ins = sorted((it for it in items if it[1] == "in"), key=lambda t: t[2])
        if sh == "diamond" and len(items) > 1:
            ordered = outs + ins
            for (ei, role, _), v in zip(ordered, _slots(len(ordered), -10.0, 10.0)):
                along[(ei, role)] = v
            continue
        if trunk and sh == "box" and side in ("n", "s") and len(items) >= 2 and len({it[1] for it in items}) == 1:
            for ei, role, _ in items:  # one port: the arrows split (or merge) in the gap, like a tree
                along[(ei, role)] = 0.0
            continue
        if layered and len(items) == 1 and side in ("n", "s") and lim >= 8:
            # A lone port leans toward the far end of its arrow, so an exit and an entry
            # stacked in one column never land on the same x and read as one line.
            ei, role, _ = items[0]
            other = edges[ei]["to"] if role == "out" else edges[ei]["from"]
            dx = pos[other][0] - pos[nid][0]
            lean = 0.0 if abs(dx) < 1 else (12.0 if dx > 0 else -12.0)
            along[(ei, role)] = -lean if side == "s" else lean
            continue
        if outs and ins and lim >= 8:
            for (ei, role, _), v in zip(outs, _slots(len(outs), -lim, -6.0)):
                along[(ei, role)] = v
            for (ei, role, _), v in zip(ins, _slots(len(ins), 6.0, lim)):
                along[(ei, role)] = v
        else:
            group = outs + ins
            vals = [0.0] * len(group) if lim < 1 else _slots(len(group), -lim, lim)
            for (ei, role, _), v in zip(group, vals):
                along[(ei, role)] = v
    out = {}
    for i, e in enumerate(edges):
        if sides[i] is None:
            continue
        s1, s2 = sides[i]
        x1, y1, n1 = pos[e["from"]]
        x2, y2, n2 = pos[e["to"]]
        ax, ay = port_on(x1, y1, n1, s1, along.get((i, "out"), 0.0))
        bx, by = port_on(x2, y2, n2, s2, along.get((i, "in"), 0.0))
        out[i] = (ax, ay, s1, bx, by, s2)
    return out


def _tail(x, y, side, col):
    """Dot on the outgoing stub so the start of the arrow is not only an arrowhead at the far end."""
    vx, vy = _SIDE.get(side, (0.0, 1.0))
    return f'<circle cx="{x + vx * 7:.1f}" cy="{y + vy * 7:.1f}" r="2.7" fill="{col}"/>'


def _round_poly(pts, r=8):
    clean = []
    for p in pts:
        if not clean or abs(p[0] - clean[-1][0]) > 0.4 or abs(p[1] - clean[-1][1]) > 0.4:
            clean.append((float(p[0]), float(p[1])))
    pruned = []
    for i, p in enumerate(clean):
        if 0 < i < len(clean) - 1:
            x0, y0 = pruned[-1]
            x1, y1 = p
            x2, y2 = clean[i + 1]
            if (abs(x0 - x1) < 0.4 and abs(x1 - x2) < 0.4) or (abs(y0 - y1) < 0.4 and abs(y1 - y2) < 0.4):
                continue
        pruned.append(p)
    if len(pruned) < 2:
        return ""
    if len(pruned) == 2:
        (x1, y1), (x2, y2) = pruned
        return f"M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}"
    d = [f"M{pruned[0][0]:.1f},{pruned[0][1]:.1f}"]
    for i in range(1, len(pruned) - 1):
        x0, y0 = pruned[i - 1]
        x1, y1 = pruned[i]
        x2, y2 = pruned[i + 1]
        l1 = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1.0
        l2 = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1.0
        rr = min(r, l1 / 2.0, l2 / 2.0)
        ax, ay = x1 - (x1 - x0) / l1 * rr, y1 - (y1 - y0) / l1 * rr
        bx, by = x1 + (x2 - x1) / l2 * rr, y1 + (y2 - y1) / l2 * rr
        d.append(f"L{ax:.1f},{ay:.1f} Q{x1:.1f},{y1:.1f} {bx:.1f},{by:.1f}")
    d.append(f"L{pruned[-1][0]:.1f},{pruned[-1][1]:.1f}")
    return " ".join(d)


def route_edge(x1, y1, side1, x2, y2, side2, r=8, stub=16, nudge=0, track=0):
    """Leave one side-center, arrive at the other. Returns path, label x/y, label-is-vertical,
    and the corner points. nudge shifts a sideways corridor so a return arrow does not sit on
    the outbound one."""
    vx, vy = _SIDE[side1]
    ux, uy = _SIDE[side2]
    ax, ay = x1 + vx * stub, y1 + vy * stub
    bx, by = x2 + ux * stub, y2 + uy * stub
    pts = [(x1, y1), (ax, ay)]
    leave_h = side1 in ("e", "w")
    enter_h = side2 in ("e", "w")
    if leave_h and enter_h:
        if side1 == side2 and abs(ay - by) >= 0.5:
            # both ends on the same side (a loop going back): run outside both boxes, not between them
            mx = min(ax, bx) if side1 == "w" else max(ax, bx)
            pts += [(mx, ay), (mx, by)]
        elif abs(ay - by) >= 0.5:
            lo, hi = sorted((ax, bx))
            mx = min(max((ax + bx) / 2.0 + nudge, lo + 8), hi - 8)
            pts += [(mx, ay), (mx, by)]
        pts.append((bx, by))
    elif (not leave_h) and (not enter_h):
        if abs(ax - bx) >= 0.5:
            my = (ay + by) / 2.0 + track  # track: its own height in a shared gap
            pts += [(ax, my), (bx, my)]
        pts.append((bx, by))
    elif leave_h and not enter_h:
        pts += [(x2, ay), (bx, by)]
    else:
        pts += [(ax, y2), (bx, by)]
    pts.append((x2, y2))
    best, mx, my, vert = 0.0, (x1 + x2) / 2.0, (y1 + y2) / 2.0, False
    for (px, py), (qx, qy) in zip(pts, pts[1:]):
        length = abs(qx - px) + abs(qy - py)
        if length > best:
            best = length
            mx, my = (px + qx) / 2.0, (py + qy) / 2.0
            vert = abs(qy - py) > abs(qx - px)
    return _round_poly(pts, r), mx, my, vert, pts


def edge_ends(pos, src_id, dst_id):
    x1, y1, n1 = pos[src_id]
    x2, y2, n2 = pos[dst_id]
    px, py, s1 = node_port(x1, y1, n1, x2, y2)
    qx, qy, s2 = node_port(x2, y2, n2, x1, y1)
    return px, py, s1, qx, qy, s2


def corner_rx(corners):
    return {"sharp": 0, "rounded": 10, "editorial": 6}.get(corners, 6)


def _groups_of(spec, ids):
    """Groups from spec["groups"] ({id, name, nodes}, or members for nodes) and from each node's "group" field."""
    out, seen = [], {}
    for g in spec.get("groups") or []:
        if isinstance(g, dict) and g.get("id") is not None:
            seen[g["id"]] = {"id": g["id"], "name": g.get("name", g["id"]), "tag": g.get("tag", ""),
                             "members": [m for m in g.get("nodes") or g.get("members") or [] if m in ids]}
            out.append(seen[g["id"]])
    for n in spec.get("nodes") or []:
        gid = n.get("group") if isinstance(n, dict) else None
        if gid is None:
            continue
        if gid not in seen:
            seen[gid] = {"id": gid, "name": str(gid), "tag": "", "members": []}
            out.append(seen[gid])
        if n.get("id") in ids and n["id"] not in seen[gid]["members"]:
            seen[gid]["members"].append(n["id"])
    return [g for g in out if g["members"]]


GROUP_PAD, GROUP_HEAD = 16, 24


def _seg_boxes(pts):
    return [(min(p[0], q[0]) - 1, min(p[1], q[1]) - 1, max(p[0], q[0]) + 1, max(p[1], q[1]) + 1)
            for p, q in zip(pts or [], (pts or [])[1:])]


def _below_heading(pos, groups, head_h):
    """Moves every node down when a frame's top band would cross the title or subtitle."""
    tops = [pos[m][1] - pos[m][2]["_h"] / 2 for g in groups for m in g["members"] if m in pos]
    dy = (head_h + 6) - (min(tops) - GROUP_HEAD) if tops else 0
    return {k: (x, y + dy, n) for k, (x, y, n) in pos.items()} if dy > 0 else pos


def _frame_box(g, pos):
    """The frame around a group's members, as (x0, y0, x1, y1), or None if none is placed."""
    boxes = []
    for m in g["members"]:
        if m in pos:
            cx, cy, n = pos[m]
            sh, hw, hh = _node_box(n)
            boxes.append((cx - hw, cy - hh, cx + hw, cy + hh))
    if not boxes:
        return None
    return (min(b[0] for b in boxes) - GROUP_PAD, min(b[1] for b in boxes) - GROUP_HEAD,
            max(b[2] for b in boxes) + GROUP_PAD, max(b[3] for b in boxes) + GROUP_PAD - 4)


def _frame_edges(groups, pos):
    """Thin strips along each frame's border, so arrow labels sit inside or outside a frame, not on it."""
    out = []
    for g in groups:
        f = _frame_box(g, pos)
        if f:
            x0, y0, x1, y1 = f
            out += [(x0, y0 - 1, x1, y0 + 1), (x0, y1 - 1, x1, y1 + 1), (x0 - 1, y0, x0 + 1, y1), (x1 - 1, y0, x1 + 1, y1)]
    return out


def group_frames(t, groups, pos, avoid=()):
    """A frame behind each group's members. Its name goes in the top corner (left, else right)
    that no arrow crosses; avoid holds the arrows' segment boxes."""
    parts = []
    for g in groups:
        f = _frame_box(g, pos)
        if not f:
            continue
        x0, y0, x1, y1 = f
        members = ",".join(esc(m) for m in g["members"])
        parts.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="10" '
                     f'fill="{t["rule"]}" fill-opacity=".35" stroke="{t["muted"]}" stroke-opacity=".55" '
                     f'stroke-dasharray="4,3" data-group="{esc(g["id"])}" data-name="{esc(g["name"])}" data-members="{members}"/>')
        label = ((g["tag"] + "  " if g.get("tag") else "") + str(g["name"])).upper()
        lw = _text_w(label, 10, True) + 0.4 * len(label)

        def hits(lx):
            b = (lx - 8, y0 + 3, lx + lw + 8, y0 + 19)  # keep clear of arrows, not just off them
            return sum(1 for a in avoid if b[0] < a[2] and a[0] < b[2] and b[1] < a[3] and a[1] < b[3])
        # left corner if it is clear, else the nearest clear spot along the top band, else the least crossed
        spots = [x0 + 10] + [x0 + 10 + 8 * k for k in range(1, int(max(0, x1 - 20 - lw - x0) // 8) + 1)]
        lx = min(spots, key=lambda v: (hits(v), v - x0))
        parts.append(f'<text x="{lx:.1f}" y="{y0 + 15:.1f}" font-size="10" font-weight="600" '
                     f'font-family="{FONT}" fill="{t["muted"]}" letter-spacing=".04em">{esc(label)}</text>')
    return parts


BOX_W, BOX_H = 160, 56


def _box_lines(name, sub="", w=BOX_W):
    return _wrap_px(name, w - 16, 12, True, 3), (_wrap_px(sub, w - 16, 9, False, 2) if sub else [])


def _box_h(name, sub="", tag="", w=BOX_W):
    """Height a box needs for its wrapped name and sub. One line each fits the classic 56."""
    nl, sl = _box_lines(name, sub, w)
    block = 15 * len(nl) + (12 * len(sl) + 2 if sl else 0)
    return max(BOX_H, block + (30 if tag else 18))


# Line glyphs on a 16x16 grid, drawn with the box's stroke. Generic shapes, no brand marks.
ICONS = {
    "user": "M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2.5 14c.8-2.8 3-4 5.5-4s4.7 1.2 5.5 4",
    "database": "M3 4c0-1.1 2.2-2 5-2s5 .9 5 2-2.2 2-5 2-5-.9-5-2zM3 4v8c0 1.1 2.2 2 5 2s5-.9 5-2V4M3 8c0 1.1 2.2 2 5 2s5-.9 5-2",
    "server": "M2.5 2.5h11v4h-11zM2.5 9.5h11v4h-11zM5 4.5h1M5 11.5h1",
    "cloud": "M4.5 12.5h7a3 3 0 0 0 .4-6A4 4 0 0 0 4.3 7a2.8 2.8 0 0 0 .2 5.5z",
    "queue": "M2 4.5h12M2 8h12M2 11.5h12M11.5 2.5l2.5 2-2.5 2",
    "lock": "M4.5 7V5a3.5 3.5 0 0 1 7 0v2M3 7h10v7H3z",
    "globe": "M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM1.5 8h13M8 1.5c2 2 2.5 4 2.5 6.5S10 12.5 8 14.5M8 1.5C6 3.5 5.5 5.5 5.5 8s.5 4.5 2.5 6.5",
    "mobile": "M5 1.5h6v13H5zM7.5 12.5h1",
    "web": "M1.5 3h13v10h-13zM1.5 6h13M3.5 4.5h1",
    "mail": "M1.5 3.5h13v9h-13zM1.5 4l6.5 5 6.5-5",
    "gear": "M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4",
    "key": "M5.5 10.5a3 3 0 1 1 2.1-.9L14 3.2M11.5 5.5l2 2",
    "bot": "M3 6h10v7H3zM8 3v3M6 9.5h1M9 9.5h1M7 2.5h2",
    "file": "M4 1.5h5.5L12 4v10.5H4zM9.5 1.5V4H12",
    "chart": "M2.5 13.5h11M4.5 11V8M8 11V4.5M11.5 11V6.5",
    "shield": "M8 1.5l5.5 2v4c0 3.5-2.4 6-5.5 7-3.1-1-5.5-3.5-5.5-7v-4z",
    "bolt": "M9 1.5L3.5 9H8l-1 5.5L12.5 7H8z",
}


# Mermaid writers reach for Font Awesome names; these map onto the glyphs above
_FA_ICONS = {"user": "user", "users": "user", "person": "user", "database": "database", "db": "database",
             "server": "server", "cloud": "cloud", "lock": "lock", "globe": "globe", "mobile": "mobile",
             "phone": "mobile", "desktop": "web", "laptop": "web", "browser": "web", "envelope": "mail",
             "cog": "gear", "gear": "gear", "key": "key", "robot": "bot", "file": "file", "chart-bar": "chart",
             "shield": "shield", "bolt": "bolt", "list": "queue", "inbox": "queue"}


def node_box(t, x, y, w, h, name, sub="", tag="", focal=False, corners="editorial", nid=None, icon=None):
    fill = t["accent_tint"] if focal else t["card"]
    stroke = t["accent"] if focal else t["ink"]
    rx = corner_rx(corners)
    cx = x + w / 2
    mark = f' data-node="{esc(nid)}" data-label="{esc(name)}"' if nid is not None else ""
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{t["paper"]}"/>',
         f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"{mark}/>']
    if tag:
        s.append(f'<rect x="{x+8}" y="{y+6}" width="{max(28,len(tag)*7)}" height="12" rx="2" fill="none" stroke="{stroke}" stroke-opacity=".4" stroke-width=".8"/>')
        s.append(f'<text x="{x+8+max(28,len(tag)*7)/2}" y="{y+15}" font-size="8" font-family="{FONT}" fill="{stroke}" text-anchor="middle">{esc(tag)}</text>')
    if icon in ICONS:
        s.append(f'<path d="{ICONS[icon]}" transform="translate({x + w - 24},{y + 5})" fill="none" stroke="{stroke}" '
                 f'stroke-opacity=".75" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>')
    # the wrapped name and sub, centered in the space below the tag and icon
    nl, sl = _box_lines(name, sub, w)
    block = 15 * len(nl) + (12 * len(sl) + 2 if sl else 0)
    top = y + (20 if tag or icon in ICONS else 8)
    base = top + max(0.0, (y + h - 8 - top - block) / 2.0) + 11
    for i, line in enumerate(nl):
        s.append(f'<text x="{cx}" y="{base + 15 * i:.1f}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle">{esc(line)}</text>')
    for i, line in enumerate(sl):
        s.append(f'<text x="{cx}" y="{base + 15 * len(nl) + 2 + 12 * i:.1f}" font-size="9" font-family="{MONO}" fill="{t["muted"]}" text-anchor="middle">{esc(line)}</text>')
    return "\n".join(s)


def _diamond_lines(name):
    return _wrap_px(name, 100, 12, True, 3)


def _diamond_h(name):
    return {1: 64, 2: 84}.get(len(_diamond_lines(name)), 104)


def diamond(t, cx, cy, w, h, name, focal=False, nid=None):
    stroke = t["accent"] if focal else t["ink"]
    fill = t["accent_tint"] if focal else t["card"]
    pts = f"{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}"
    lines = _diamond_lines(name)
    y0 = cy + 4 - 7.5 * (len(lines) - 1)
    text = "".join(f'<text x="{cx}" y="{y0 + 15 * i:.1f}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle">{esc(line)}</text>'
                   for i, line in enumerate(lines))
    return (f'<polygon points="{pts}" fill="{t["paper"]}"/>'
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}"'
            + (f' data-node="{esc(nid)}" data-label="{esc(name)}" data-cx="{cx}" data-cy="{cy}"' if nid is not None else "")
            + '/>' + text)


def _pill_w(text):
    return max(40, int(len(text) * 6.4 + 12))


def arrow_label(t, mx, ay, text, vertical=False, flip=False):
    """Label sitting off the shaft, on the paper, so it does not cut the arrow.
    flip puts it on the other side: left of a vertical shaft, below a horizontal one."""
    x0, y0, _, _ = _label_box(mx, ay, text, vertical, flip)
    w = _pill_w(text)
    return (f'<rect x="{x0}" y="{y0}" width="{w}" height="16" rx="2" fill="{t["paper"]}"/>'
            f'<text x="{x0 + w / 2}" y="{y0 + 12}" font-size="10" font-family="{MONO}" fill="{t["muted"]}" text-anchor="middle">{esc(text)}</text>')


def _label_box(mx, ay, text, vertical=False, flip=False):
    w = _pill_w(text)
    if vertical:
        x0 = mx - 8 - w if flip else mx + 8
        return (x0, ay - 9, x0 + w, ay + 7)
    y0 = ay + 8 if flip else ay - 24
    return (mx - w / 2, y0, mx + w / 2, y0 + 16)


def _place_label(mx, my, vertical, text, pts, avoid, soft=()):
    """The first spot along the route where the label's pill clears everything. Tries the
    default, then each segment's middle, on both sides and both orientations. If none is
    clear: never on a hard obstacle (a box or a label), then the fewest soft ones (other arrows)."""
    cands = [(mx, my, vertical, False), (mx, my, vertical, True)]
    for at in (0.5, 0.3, 0.7):  # each segment's middle first, then either side of it
        for (px, py), (qx, qy) in zip(pts or [], (pts or [])[1:]):
            seg_v = abs(qy - py) > abs(qx - px)
            for v in (seg_v, not seg_v):
                for flip in (False, True):
                    cands.append((px + (qx - px) * at, py + (qy - py) * at, v, flip))

    def hits(b, boxes):
        return sum(1 for a in boxes if b[0] < a[2] + 2 and a[0] - 2 < b[2] and b[1] < a[3] + 2 and a[1] - 2 < b[3])
    scored = []
    for k, c in enumerate(cands):
        b = _label_box(c[0], c[1], text, c[2], c[3])
        cost = (hits(b, avoid), hits(b, soft), k)
        if cost[:2] == (0, 0):
            return c
        scored.append((cost, c))
    return min(scored)[1]


def nice_ticks(vmin, vmax, n=5):
    """Pretty tick positions (Heckbert nice numbers)."""
    import math
    if vmin == vmax:
        vmax = vmin + 1
    span = vmax - vmin
    step0 = span / n
    mag = 10 ** math.floor(math.log10(step0))
    for m in (1, 2, 2.5, 5, 10):
        if step0 / mag <= m:
            step = m * mag
            break
    lo = math.floor(vmin / step) * step
    ticks, v = [], lo
    while v <= vmax + 1e-9 and len(ticks) < 12:
        ticks.append(round(v, 10))
        v += step
    if ticks and ticks[-1] < vmax - 1e-9 and len(ticks) < 12:
        ticks.append(round(ticks[-1] + step, 10))  # axis must cover the data
    return ticks


def fmt_value(v):
    """One value as a reader says it: 1,816, 20k, 12.5k, 3.4M. Ticks keep fmt_tick, which never rounds."""
    if abs(v) >= 9999.5:
        for div, unit in ((1e3, "k"), (1e6, "M"), (1e9, "B")):
            txt = f"{v / div:.3g}"
            if "e" not in txt and abs(float(txt)) < 1000:
                return txt + unit
        return f"{v / 1e9:,.0f}B"
    return f"{v:,.0f}" if abs(v) >= 100 or v == int(v) else f"{v:.3g}"


def fmt_tick(v):
    if v == int(v) and abs(v) < 10000:
        return str(int(v))
    if abs(v) >= 1000:
        return f"{v/1000:g}k"
    return f"{v:g}"

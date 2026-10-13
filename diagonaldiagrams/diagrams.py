"""flow, arch, seq and schema: placement, routing and the repair loops."""
import json
from ._draw import (
    BOX_H, BOX_W, GROUP_PAD, _below_heading, _box_h, _diamond_h, _frame_edges, _groups_of, _label_box,
    _pill_w, _place_label, _seg_boxes, _tail, arrow_label, assign_ports, corner_rx, diamond, elbow,
    figure_heading, group_frames, markers, node_box, render_noterail, route_edge,
)
from ._text import esc
from ._theme import FONT, MONO, SANS, THEME
from .audit import _svg_geometry


def _group_columns(layers, groups, gof, edges=()):
    """Columns for a layered view with groups. Each group owns a band of columns in the rows it
    spans and its members stack inside it; other nodes take free columns outside every band that
    covers their row. Returns {node id: column} (a column may be fractional, to center a short row)."""
    keys = sorted(layers)
    rows = [layers[k] for k in keys]
    bands = []
    for k in range(len(groups)):
        hit = [r for r, row in enumerate(rows) if any(gof.get(n["id"]) == k for n in row)]
        if not hit:
            continue
        width = max(sum(1 for n in rows[r] if gof.get(n["id"]) == k) for r in hit)
        first = max(next(i for i, n in enumerate(rows[r]) if gof.get(n["id"]) == k) for r in hit)
        mean = sum(next(i for i, n in enumerate(rows[r]) if gof.get(n["id"]) == k) / max(1, len(rows[r])) for r in hit) / len(hit)
        bands.append({"k": k, "lo": min(hit), "hi": max(hit), "w": width, "first": first, "mean": mean})
    start = {}
    for b in sorted(bands, key=lambda b: (b["mean"], b["k"])):
        s0 = b["first"]
        for o in bands:
            if o["k"] in start and not (o["hi"] < b["lo"] or o["lo"] > b["hi"]):
                s0 = max(s0, start[o["k"]] + o["w"])
        start[b["k"]] = s0
    by_k = {b["k"]: b for b in bands}
    col = {}
    for r, row in enumerate(rows):
        live = [(start[b["k"]], start[b["k"]] + b["w"]) for b in bands if b["lo"] <= r <= b["hi"]]
        ptr, seen = 0, {}
        for n in row:
            k = gof.get(n["id"])
            if k is not None and k in start:
                members = [m for m in row if gof.get(m["id"]) == k]
                i = seen.setdefault(k, 0)
                seen[k] += 1
                col[n["id"]] = start[k] + i + (by_k[k]["w"] - len(members)) / 2.0
                ptr = max(ptr, start[k] + by_k[k]["w"])
            else:
                c = ptr
                while any(lo <= c < hi for lo, hi in live):
                    c += 1
                col[n["id"]] = c
                ptr = c + 1
    # Nodes outside groups move toward the mean column of their neighbours (a barycenter pass),
    # keeping their order within the row and clear of the bands that cover the row.
    nbr = {}
    for e in edges or ():
        a, b = e.get("from"), e.get("to")
        if a in col and b in col:
            nbr.setdefault(a, []).append(b)
            nbr.setdefault(b, []).append(a)
    for _ in range(4):
        for r, row in enumerate(rows):
            live = [(start[b["k"]], start[b["k"]] + b["w"]) for b in bands if b["lo"] <= r <= b["hi"]]
            taken = {round(col[n["id"]] * 2) for n in row if gof.get(n["id"]) in start}
            free_nodes = [n for n in row if gof.get(n["id"]) not in start]
            want = {n["id"]: (sum(col[m] for m in nbr[n["id"]]) / len(nbr[n["id"]]) if nbr.get(n["id"]) else col[n["id"]])
                    for n in free_nodes}
            last = -1e9
            for n in sorted(free_nodes, key=lambda n: (want[n["id"]], row.index(n))):
                c = max(round(want[n["id"]]), int(last) + 1)
                while any(lo <= c < hi for lo, hi in live) or round(c * 2) in taken:
                    c += 1
                col[n["id"]] = c
                last = c
    lo = min(col.values(), default=0)
    return {k: v - lo for k, v in col.items()}


def auto_ranks(nodes, edges):
    """Longest-path layering (Sugiyama layer assignment). Loops are broken first: a depth-first
    walk from the start nodes (no incoming arrow, else the first in the spec) marks each arrow
    that returns to a node still on the walk as a back edge. Ranking ignores back edges, so a
    loop's start stays on top and its return arrow is drawn going back up. Pure stdlib."""
    ids = [n["id"] for n in nodes]
    succ = {i: [] for i in ids}
    indeg = {i: 0 for i in ids}
    for e in edges:
        a, b = e.get("from"), e.get("to")
        if a in succ and b in succ and a != b:
            succ[a].append(b)
            indeg[b] += 1
    back, state = set(), {}
    for root in [i for i in ids if indeg[i] == 0] + ids:
        if root in state:
            continue
        state[root] = 1
        stack = [(root, iter(succ[root]))]
        while stack:
            v, it = stack[-1]
            w = next(it, None)
            if w is None:
                state[v] = 2
                stack.pop()
            elif state.get(w) == 1:
                back.add((v, w))
            elif w not in state:
                state[w] = 1
                stack.append((w, iter(succ[w])))
    preds = {i: [] for i in ids}
    for v in ids:
        for w in succ[v]:
            if (v, w) not in back:
                preds[w].append(v)
    rank = {}
    for nid in ids:  # the graph is acyclic now; an explicit stack avoids deep recursion
        stack = [nid]
        while stack:
            v = stack[-1]
            if v in rank:
                stack.pop()
                continue
            todo = [p for p in preds[v] if p not in rank]
            if todo:
                stack.extend(todo)
            else:
                rank[v] = max((rank[p] + 1 for p in preds[v]), default=0)
                stack.pop()
    return rank


def _render_flow_once(spec, corners="editorial", auto=False, theme=None):
    t = theme or THEME
    nodes = [dict(n) for n in spec["nodes"]]  # [{id,shape,name,tag?,sub?,focal?}]
    for n in nodes:
        n.setdefault("name", n.get("id", ""))
        sh = n.get("shape", "rect")
        n["_h"] = 8 if sh == "dot" else (_diamond_h(n["name"]) if sh == "diamond" else _box_h(n["name"], n.get("sub", ""), n.get("tag", "") or n.get("icon", "")))
    edges = spec.get("edges", [])  # [{from,to,label?,focal?}]
    _notes = (spec.get("notes", []) or [])[:2]
    head_bits, head_h = figure_heading(t, spec.get("title") or "", spec.get("sub") or "", x=30)
    W, col_w, top, gap_y = (720 + (200 if _notes else 0)), 200, max(90, head_h + 20), 120
    if auto or not any("rank" in n for n in nodes):
        computed = auto_ranks(nodes, edges)
        ranks = {n["id"]: computed.get(n["id"], 0) for n in nodes}
    else:
        ranks = {}
    pos = {}
    # rank = explicit, else list order, else longest-path; shared ranks fan out
    # across x unless explicit 'lane' (-1 left|0 center|1 right) is given
    by_rank = {}
    for i, n in enumerate(nodes):
        rk = n.get("rank", ranks.get(n["id"], i))
        by_rank.setdefault(rk, []).append(n)
    maxrk = max(by_rank) if by_rank else 0
    # A row of tall (wrapped) boxes pushes the rows below it down; classic rows keep their pitch.
    tall = {rk: max(n["_h"] for n in g) for rk, g in by_rank.items()}
    extra, acc, prev = {}, 0.0, None
    for rk in sorted(by_rank):
        if prev is not None:
            # push down only when the rows would leave less than 56px clear between them
            acc += max(0.0, (tall[prev] + tall[rk]) / 2.0 + 56 - (rk - prev) * gap_y)
        extra[rk], prev = acc, rk

    def row_y(rk):
        return top + rk * gap_y + 30 + extra.get(rk, 0.0)
    placed = {}  # id -> cx, filled rank by rank for barycenter ordering
    for rk in sorted(by_rank):
        group = by_rank[rk]
        if len(group) > 1 and not any("lane" in g for g in group):
            # barycenter heuristic: order by mean predecessor x (fewer crossings)
            def _bary(n):
                xs = [placed[e["from"]] for e in edges
                      if e.get("to") == n["id"] and e["from"] in placed]
                return sum(xs) / len(xs) if xs else len(placed)
            for j, n in enumerate(sorted(group, key=_bary)):
                cx = W / 2 + (j - (len(group) - 1) / 2) * 200
                pos[n["id"]] = (cx, row_y(rk), n)
                placed[n["id"]] = cx
        else:
            # Some nodes carry a lane. The rest take the free lane nearest their parents,
            # so they do not stack on the center lane under a long edge.
            taken = {n["lane"] for n in group if "lane" in n}
            given = {}

            def _parent_x(n):
                xs = [placed[e["from"]] for e in edges if e.get("to") == n["id"] and e.get("from") in placed]
                return sum(xs) / len(xs) if xs else W / 2
            for n in sorted((g for g in group if "lane" not in g and len(group) > 1), key=_parent_x):
                px = _parent_x(n)
                free = [ln for ln in range(-4, 5) if ln not in taken]
                ln = min(free, key=lambda v: (abs(W / 2 + v * (col_w + 40) - px), abs(v)))
                taken.add(ln)
                given[n["id"]] = ln
            for n in group:
                lane = n.get("lane", given.get(n["id"], 0))
                cx = W / 2 + lane * (col_w + 40)
                pos[n["id"]] = (cx, row_y(rk), n)
                placed[n["id"]] = cx
    # Two boxes in one row never share a spot (a lane on some nodes and not others did that).
    # Push them apart, then shift and widen the canvas to fit.
    for rk, group in by_rank.items():
        row = sorted((pos[n["id"]][0], k, n["id"]) for k, n in enumerate(group))
        for k in range(1, len(row)):
            if row[k][0] < row[k - 1][0] + 200:
                row[k] = (row[k - 1][0] + 200, row[k][1], row[k][2])
        for cx, _, nid in row:
            pos[nid] = (cx, pos[nid][1], pos[nid][2])
    if pos:
        shift = max(0, 110 - min(cx for cx, _, _ in pos.values()))
        if shift:
            pos = {k: (cx + shift, cy, n) for k, (cx, cy, n) in pos.items()}
        W = max(W, int(max(cx for cx, _, _ in pos.values()) + 110 + (200 if _notes else 0)))
    pos = _below_heading(pos, _groups_of(spec, set(pos)), head_h)
    low = max((cy + n["_h"] / 2 - BOX_H / 2 for _, cy, n in pos.values()), default=top)
    if _notes:
        low = max(low, top + 14 + max(0, len(_notes) - 1) * 92 + 52)
    H = int(low + 112)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(spec.get("title","flow"))}</title>',
             f'<desc>{esc(spec.get("sub", spec.get("title", "flow")))}</desc>',
             f'<rect width="{W}" height="{H}" fill="{t["paper"]}"/>', markers(t)]
    parts.extend(head_bits)
    frame_at, seg_boxes = len(parts), []
    node_boxes = [(cx - 80, cy - n["_h"] / 2, cx + 80, cy + n["_h"] / 2) for cx, cy, n in pos.values()]
    frame_edges = _frame_edges(_groups_of(spec, set(pos)), pos)
    label_boxes = []
    for nid, (cx, cy, n) in pos.items():
        sh = n.get("shape", "rect")
        h = n["_h"]
        if sh == "diamond":
            parts.append(diamond(t, cx, cy, 160, h, n["name"], n.get("focal", False), nid))
        elif sh == "oval":
            # both rects: the paper underlay and the visible box
            parts.append(node_box(t, cx-80, cy-h/2, 160, h, n["name"], n.get("sub",""), n.get("tag",""), n.get("focal",False), corners, nid, n.get("icon")).replace(f'rx="{corner_rx(corners)}"','rx="20"', 2))
        elif sh == "dot":
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{t["ink"]}"/>')
        else:
            parts.append(node_box(t, cx-80, cy-h/2, 160, h, n["name"], n.get("sub",""), n.get("tag",""), n.get("focal",False), corners, nid, n.get("icon")))
    # edges after nodes. Ports are spread so an input and an output do not share a point.
    # An arrow going back up (a loop) leaves and enters on the outer side and runs up the outside,
    # instead of climbing through the boxes between its ends.
    fixed = {}
    row_ys = sorted({round(cy, 1) for _, cy, _ in pos.values()})
    for i, e in enumerate(edges):
        a, b = pos.get(e.get("from")), pos.get(e.get("to"))
        if a and b and b[1] < a[1] - 1 and a[2].get("shape") != "dot" and b[2].get("shape") != "dot":
            side = "w" if (a[0] + b[0]) / 2 <= W / 2 else "e"
            fixed[i] = (side, side)
        elif (a and b and b[1] > a[1] + 1 and a[2].get("shape") not in ("diamond", "dot") and b[2].get("shape") != "dot"
              and not any(a[1] + 1 < y < b[1] - 1 for y in row_ys)):
            fixed[i] = ("s", "n")  # to the next row: out the bottom, in the top. Longer arrows go round the side.
    ports = assign_ports(pos, edges, fixed=fixed, trunk=True)
    tracks = _gap_tracks(ports, room=30, net_by_source=True)
    for i, e in enumerate(edges):
        if i not in ports:
            continue
        x1, y1, s1, x2, y2, s2 = ports[i]
        col = t["accent"] if e.get("focal") else t["muted"]
        mid = "aa" if e.get("focal") else "a"
        nudge = label_dy = 0
        if s1 in ("e", "w") and s2 in ("e", "w") and y1 > y2 + 24:
            nudge = -20 if x1 <= x2 else 20
            label_dy = -34
        d, lx, ly, vertical, pts = route_edge(x1, y1, s1, x2, y2, s2, nudge=nudge, track=tracks.get(i, 0))
        if not d:
            continue
        dash = ' stroke-dasharray="5,4"' if e.get("async") else ""
        ends = f' data-from="{esc(e.get("from"))}" data-to="{esc(e.get("to"))}" data-label="{esc(e.get("label", ""))}"'
        parts.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.8"{dash} marker-end="url(#{mid})"{ends}/>')
        parts.append(_tail(x1, y1, s1, col))
        seg_boxes += _seg_boxes(pts)
        if e.get("label"):
            text = e["label"].upper()
            lx, ly, vertical, flip = _place_label(lx, ly + label_dy, vertical, text, pts,
                                                  node_boxes + label_boxes + frame_edges)
            parts.append(arrow_label(t, lx, ly, text, vertical=vertical, flip=flip))
            label_boxes.append(_label_box(lx, ly, text, vertical, flip))
    parts[frame_at:frame_at] = group_frames(t, _groups_of(spec, set(pos)), pos, seg_boxes)
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in pos:
                cx, cy, _n = pos[nt["at"]]
                rail.append((cx + 80, cy, nt["text"]))
        parts.append(render_noterail(t, rail, W - 186, top))
    # legend strip
    ly = H - 40
    parts.append(f'<line x1="30" y1="{ly-8}" x2="{W-30}" y2="{ly-8}" stroke="{t["rule"]}" stroke-width=".8"/>')
    parts.append(f'<text x="30" y="{ly+8}" font-size="11" font-family="{FONT}" fill="{t["muted"]}">box = step, diamond = decision, rounded = start or end</text>')
    parts.append("</svg>")
    return "\n".join(parts), W, H, {nid: (cx, cy) for nid, (cx, cy, _n) in pos.items()}


def render_flow(spec, corners="editorial", auto=False, theme=None):
    """Draw a flow. If an arrow runs through a box, move a node the spec left free to
    another lane and draw again. A node with its own lane is never moved. A move must lower
    the layout cost (problems, crossings, arrow length), not just the problem count."""
    def draw(sp):
        svg, w, h, placed = _render_flow_once(sp, corners, auto, theme)
        out, found, c = _layout_cost((svg, w, h))
        return out, placed, found, c
    out, pos, bad, cost = draw(spec)
    if not bad:
        return out
    work = json.loads(json.dumps(spec))
    free = {n["id"] for n in work.get("nodes", []) if "lane" not in n}
    # one move fixes one spot or a few, so a big flow with many problems gets more moves
    for _ in range(min(16, max(4, len(bad)))):
        blockers = []
        for it in bad:
            x, y = it["at"]
            for nid, (cx, cy) in pos.items():
                if nid in free and nid not in blockers and abs(cx - x) <= 80 and abs(cy - y) <= 32:
                    blockers.append(nid)
        best = None
        # the nodes at the problem first; if moving them does not help, any free node
        for nid in blockers + [n for n in pos if n in free and n not in blockers]:
            for lane in (-1, 1, -2, 2):
                trial = json.loads(json.dumps(work))
                for n in trial["nodes"]:
                    if n.get("id") == nid:
                        n["lane"] = lane
                o, p, b, c = draw(trial)
                if c < cost and (best is None or c < best[4]):
                    best = (nid, trial, (o, p), b, c)
            if best:
                break
        if not best:
            break
        nid, work, (out, pos), bad, cost = best
        free.discard(nid)
        if not bad:
            break
    return out


def render_arch(spec, corners="editorial", theme=None):
    """Draw an architecture view. If the audit finds a problem (an arrow through a box, two
    arrows on one line, a label collision), try other orders within each row (layers never
    change). Keep the order with the lowest cost: a problem counts as four crossings, and
    arrow length breaks ties, so one fix is never bought with a tangle of new crossings."""
    out, bad, cost = _layout_cost(_render_arch_once(spec, corners, theme))
    if not bad or not isinstance(spec.get("nodes"), list):
        return out
    work = json.loads(json.dumps(spec))
    for _ in range(6):
        improved = False
        rows = {}
        for k, n in enumerate(work["nodes"]):
            rows.setdefault(n.get("layer", 0), []).append(k)
        for idx in rows.values():
            for a in range(len(idx)):
                for b in range(a + 1, len(idx)):
                    trial = json.loads(json.dumps(work))
                    ns = trial["nodes"]
                    ns[idx[a]], ns[idx[b]] = ns[idx[b]], ns[idx[a]]
                    o, found, c = _layout_cost(_render_arch_once(trial, corners, theme))
                    if c < cost:
                        work, out, bad, cost, improved = trial, o, found, c, True
        if not improved:
            break
    return out


def _layout_cost(out):
    """(drawing, audit problems, cost) for the layout repair loops."""
    import xml.etree.ElementTree as ET
    stats = {"crossings": 0, "wire": 0.0}
    try:
        found = _svg_geometry(ET.fromstring(out[0]), out[1], out[2], stats)
    except ET.ParseError:
        found = []
    bad = [i for i in found if i["code"] in ("through", "strike", "overlap", "collide", "shared", "intrude")]
    return out, bad, 4 * len(bad) + stats["crossings"] + stats["wire"] / 400.0


def _gap_tracks(ports, room=None, net_by_source=False):
    """Arrows that cross the same gap between rows each get a track (a turn height), so two
    arrows never run on one line. Greedy interval colouring over their sideways spans.
    net_by_source: arrows leaving one port share a track (a trunk that splits, like a tree).
    room caps the spread when the gap is tight. Returns {edge index: vertical offset}."""
    tracks, by_gap = {}, {}
    for i, (x1, y1, s1, x2, y2, s2) in ports.items():
        if s1 in ("n", "s") and s2 in ("n", "s") and abs(x1 - x2) >= 0.5:
            by_gap.setdefault((round(min(y1, y2)), round(max(y1, y2))), []).append((min(x1, x2), max(x1, x2), i, x1, x2))
    for spans in by_gap.values():
        if net_by_source:
            # one span per source port: its arrows ride one trunk
            nets = {}
            for lo, hi, i, sx, dx in spans:
                key = (round(sx, 1), round(ports[i][1], 1))
                n0 = nets.setdefault(key, [lo, hi, [], sx, dx])
                n0[0], n0[1] = min(n0[0], lo), max(n0[1], hi)
                n0[2].append(i)
            members = {n[2][0]: n[2] for n in nets.values()}
            spans = [(n[0], n[1], n[2][0], n[3], n[4]) for n in nets.values()]
        else:
            members = {i: [i] for _, _, i, _, _ in spans}
        # An arrow that leaves at the x where another arrives must turn above it, or the
        # two run down one line. Place those first, then the rest by their left end.
        above = {i: set() for _, _, i, _, _ in spans}
        for _, _, a, sa, _ in spans:
            for _, _, b, _, db in spans:
                if a != b and abs(sa - db) < 14:
                    above[b].add(a)
        order, placed_ids = [], set()
        pending = sorted(spans)
        while pending:
            ready = [x for x in pending if above[x[2]] <= placed_ids] or pending[:1]
            x = ready[0]
            pending.remove(x)
            order.append(x)
            placed_ids.add(x[2])
        used, k_of = [], {}  # per track: the spans already on it
        for lo, hi, i, _, _ in order:
            floor = max((k_of[a] + 1 for a in above[i] if a in k_of), default=0)
            k = next((k for k in range(floor, len(used))
                      if all(hi + 14 < a or lo - 14 > b for a, b in used[k])), None)
            if k is None:
                while len(used) < floor:
                    used.append([])
                used.append([])
                k = len(used) - 1
            used[k].append((lo, hi))
            k_of[i] = k
        n = len(used)
        step = 14.0 if room is None or n < 2 else min(14.0, room / (n - 1))
        for _, _, i, _, _ in spans:
            for m in members[i]:
                tracks[m] = (k_of[i] - (n - 1) / 2.0) * step
    return tracks


def _render_arch_once(spec, corners="editorial", theme=None):
    t = theme or THEME
    nodes = [dict(n) for n in spec["nodes"]]; edges = spec.get("edges", [])
    for n in nodes:
        n.setdefault("name", n.get("id", ""))
        n["_h"] = _box_h(n["name"], n.get("sub", ""), n.get("tag", "") or n.get("icon", ""))
    _notes = (spec.get("notes", []) or [])[:2]
    head_bits, head_h = figure_heading(t, spec.get("title") or "", spec.get("sub") or "", x=30)
    # simple layered: group by 'layer' (0 top..n), spread across width
    from collections import defaultdict
    layers = defaultdict(list)
    for n in nodes:
        layers[n.get("layer", 0)].append(n)
    groups = _groups_of(spec, {n["id"] for n in nodes})
    if groups:
        # members of one group sit side by side; the row otherwise keeps the spec's order
        gof = {m: k for k, g in enumerate(groups) for m in g["members"]}
        for key, row in layers.items():
            first = {}
            for j, n in enumerate(row):
                first.setdefault(gof.get(n["id"], ("solo", j)), j)
            layers[key] = sorted(row, key=lambda n, r=row: (first[gof.get(n["id"], ("solo", r.index(n)))], r.index(n)))
    max_n = max((len(row) for row in layers.values()), default=1)
    # A box is 160 wide. A row wider than four overlaps on a 760 canvas.
    # A spec with the count cap off gets a wider pitch so the labels fit.
    pitch = 220 if spec.get("budget", True) is False or len(nodes) > 9 else 188
    W = max(760, pitch * (max_n + 1)) + (200 if _notes else 0)
    cols = None
    if groups:
        # with groups, rows share one column grid so a group's frame holds only its members
        pitch = max(pitch, 210)
        cols = _group_columns(layers, groups, gof, edges)
        span = max(cols.values()) + 1 if cols else 1
        # a labelled arrow between neighbours in a row needs room for its label between the boxes,
        # and past a frame border when it leaves a frame
        lay = {n["id"]: n.get("layer", 0) for n in nodes}
        for e in edges:
            a, b = e.get("from"), e.get("to")
            if (e.get("label") and a in cols and b in cols and lay.get(a) == lay.get(b)
                    and abs(cols[a] - cols[b]) == 1):
                borders = ((a in gof) + (b in gof)) if gof.get(a) != gof.get(b) else 0
                pitch = max(pitch, int(BOX_W + borders * GROUP_PAD + _pill_w(e["label"].upper()) + 16))
        W = max(760, int(span * pitch + 2 * 50)) + (200 if _notes else 0)
    pos = {}
    top, gap_y = max(100, head_h + 24), 156
    acc, prev_h = 0.0, None
    for li, key in enumerate(sorted(layers)):
        row = layers[key]
        row_h = max(n["_h"] for n in row)
        if prev_h is not None:
            acc += max(0.0, (prev_h + row_h) / 2.0 + 100 - gap_y)  # keep 100px clear for the arrows' tracks
        prev_h = row_h
        for j, n in enumerate(row):
            x = (50 + (cols[n["id"]] + 0.5) * pitch) if cols else (W / (len(row)+1)) * (j+1)
            y = top + li * gap_y + acc
            pos[n["id"]] = (x, y, n)
    pos = _below_heading(pos, groups, head_h)
    low = max((y + n["_h"] / 2 - BOX_H / 2 for _, y, n in pos.values()), default=top)
    if _notes:
        low = max(low, top + 14 + max(0, len(_notes) - 1) * 92 + 52)
    H = int(low + 112)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(spec.get("title","arch"))}</title>',
             f'<desc>{esc(spec.get("sub", spec.get("title", "arch")))}</desc>',
             f'<rect width="{W}" height="{H}" fill="{t["paper"]}"/>', markers(t)]
    parts.extend(head_bits)
    frame_at = len(parts)
    for nid,(x,y,n) in pos.items():
        parts.append(node_box(t, x-80, y-n["_h"]/2, 160, n["_h"], n["name"], n.get("sub",""), n.get("tag",""), n.get("focal",False), corners, nid, n.get("icon")))
    node_boxes = [(x - 80, y - n["_h"] / 2, x + 80, y + n["_h"] / 2) for x, y, n in pos.values()]
    frame_edges = _frame_edges(groups, pos)
    label_boxes = []
    ports = assign_ports(pos, edges, layered=True)
    tracks = _gap_tracks(ports)
    routes = []
    for i, e in enumerate(edges):
        if i not in ports:
            continue
        x1, y1, s1, x2, y2, s2 = ports[i]
        col = t["link"] if e.get("proto","").startswith("http") else (t["accent"] if e.get("focal") else t["muted"])
        dash = ' stroke-dasharray="5,4"' if e.get("async") else ""
        mid = "al" if e.get("proto", "").startswith("http") else ("aa" if e.get("focal") else "a")
        d, lx, ly, vertical, pts = route_edge(x1, y1, s1, x2, y2, s2, track=tracks.get(i, 0))
        if not d:
            continue
        ends = f' data-from="{esc(e.get("from"))}" data-to="{esc(e.get("to"))}" data-label="{esc(e.get("label", ""))}"'
        parts.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.8"{dash} marker-end="url(#{mid})"{ends}/>')
        parts.append(_tail(x1, y1, s1, col))
        segs = [(min(p[0], q[0]) - 1, min(p[1], q[1]) - 1, max(p[0], q[0]) + 1, max(p[1], q[1]) + 1)
                for p, q in zip(pts, pts[1:])]
        routes.append((e, lx, ly, vertical, pts, segs))
    parts[frame_at:frame_at] = group_frames(t, groups, pos, [b for r in routes for b in r[5]])
    # Labels go last, once every arrow is routed: each one keeps clear of the boxes,
    # the labels already placed, and every other arrow.
    for k, (e, lx, ly, vertical, pts, _segs) in enumerate(routes):
        if e.get("label"):
            text = e["label"].upper()
            others = [b for j, r in enumerate(routes) if j != k for b in r[5]]
            lx, ly, vertical, flip = _place_label(lx, ly, vertical, text, pts, node_boxes + label_boxes + frame_edges, others)
            parts.append(arrow_label(t, lx, ly, text, vertical=vertical, flip=flip))
            label_boxes.append(_label_box(lx, ly, text, vertical, flip))
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in pos:
                x, y, _n = pos[nt["at"]]
                rail.append((x + 80, y, nt["text"]))
        parts.append(render_noterail(t, rail, W - 186, top))
    ly = H - 40
    parts.append(f'<line x1="30" y1="{ly-8}" x2="{W-30}" y2="{ly-8}" stroke="{t["rule"]}" stroke-width=".8"/>')
    parts.append(f'<text x="30" y="{ly+8}" font-size="11" font-family="{FONT}" fill="{t["muted"]}">blue = HTTP call, dashed = sent in the background, coral = highlighted</text>')
    parts.append("</svg>")
    return "\n".join(parts), W, H


def render_seq(spec, corners="editorial", theme=None):
    t = theme or THEME
    actors = spec.get("actors", [])
    messages = spec.get("messages", [])
    n_act = max(1, len(actors))
    margin_x = 70
    _notes = (spec.get("notes", []) or [])[:2]
    head_bits, head_h = figure_heading(t, spec.get("title") or "", spec.get("sub") or "", x=30)
    longest = 48
    for m in messages:
        if m.get("from") == m.get("to"):
            continue
        lbl = m.get("label") or ""
        if m.get("proto"):
            lbl = f"[{m['proto'].upper()}] {lbl}"
        longest = max(longest, _pill_w(lbl.upper()))
    pitch = max(180, longest + 36)
    W = margin_x * 2 + max(0, n_act - 1) * pitch + 140 + (200 if _notes else 0)
    pos = {}
    for i, a in enumerate(actors):
        cx = margin_x + 70 + i * pitch
        pos[a["id"]] = (cx, a)
    top = max(90, head_h + 16)
    msg_gap = 52
    msg_start = top + 86  # the first message's label sits clear of the actor boxes
    H = msg_start + len(messages) * msg_gap + 80
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(spec.get("title","sequence"))}</title>',
             f'<desc>{esc(spec.get("sub", spec.get("title", "sequence")))}</desc>',
             f'<rect width="{W}" height="{H}" fill="{t["paper"]}"/>', markers(t)]
    parts.extend(head_bits)
    # Lifelines
    for aid, (cx, a) in pos.items():
        parts.append(f'<line x1="{cx:.1f}" y1="{top+52}" x2="{cx:.1f}" y2="{H-50}" stroke="{t["rule"]}" stroke-width="1.2" stroke-dasharray="4,4"/>')
    # Messages
    for i, m in enumerate(messages):
        f_id = m.get("from")
        t_id = m.get("to")
        if f_id not in pos or t_id not in pos:
            continue
        x1, _ = pos[f_id]
        x2, _ = pos[t_id]
        my = msg_start + i * msg_gap
        focal = m.get("focal", False)
        is_http = m.get("proto", "").startswith("http")
        col = t["accent"] if focal else (t["link"] if is_http else t["muted"])
        mid = "aa" if focal else ("al" if is_http else "a")
        dash = ' stroke-dasharray="4,4"' if (m.get("reply") or m.get("async")) else ''
        # read back by the outline: who sends what to whom, in order
        dash += (f' data-msg="{esc(m.get("label", ""))}" data-msg-from="{esc(pos[f_id][1].get("name", f_id))}"'
                 f' data-msg-to="{esc(pos[t_id][1].get("name", t_id))}"')
        if f_id == t_id:
            # Self-call loop
            lw = 32
            parts.append(f'<path d="M{x1:.1f},{my} L{x1+lw:.1f},{my} L{x1+lw:.1f},{my+20} L{x1+4:.1f},{my+20}" fill="none" stroke="{col}" stroke-width="1.5"{dash} marker-end="url(#{mid})"/>')
            if m.get("label"):
                parts.append(arrow_label(t, x1 + lw + max(20, len(m["label"])*3.5), my + 10, m["label"].upper()))
        else:
            direction = 1 if x2 >= x1 else -1
            x_from = x1 + direction * 8
            x_to = x2 - direction * 8
            parts.append(f'<line x1="{x_from:.1f}" y1="{my}" x2="{x_to:.1f}" y2="{my}" stroke="{col}" stroke-width="1.6"{dash} marker-end="url(#{mid})"/>')
            if m.get("label"):
                lbl = m["label"]
                if m.get("proto"):
                    lbl = f"[{m['proto'].upper()}] {lbl}"
                parts.append(arrow_label(t, (x1 + x2) / 2, my, lbl.upper()))
    # Actor boxes at top
    for aid, (cx, a) in pos.items():
        bw, bh = 140, 52
        bx, by = cx - bw / 2, top
        parts.append(node_box(t, bx, by, bw, bh, a.get("name", aid), a.get("sub", ""), a.get("tag", ""), a.get("focal", False), corners, aid))
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in pos:
                cx, _a = pos[nt["at"]]
                rail.append((cx + 70, top + 26, nt["text"]))
        parts.append(render_noterail(t, rail, W - 186, top))
    # Legend
    ly = H - 28
    parts.append(f'<line x1="30" y1="{ly-10}" x2="{W-30}" y2="{ly-10}" stroke="{t["rule"]}" stroke-width=".8"/>')
    parts.append(f'<text x="30" y="{ly+4}" font-size="11" font-family="{FONT}" fill="{t["muted"]}">solid = call, dashed = reply or event, blue = HTTP, coral = highlighted</text>')
    parts.append("</svg>")
    return "\n".join(parts), W, H


def render_schema(spec, corners="editorial", theme=None):
    """Draw tables and relations. If the audit finds a problem, try other table orders and keep
    the one with the lowest layout cost (problems, crossings, length), as render_arch does."""
    out, bad, cost = _layout_cost(_render_schema_once(spec, corners, theme))
    tables = spec.get("tables") if isinstance(spec, dict) else None
    if not bad or not isinstance(tables, list) or any("x" in tb for tb in tables if isinstance(tb, dict)):
        return out
    work = json.loads(json.dumps(spec))
    for _ in range(4):
        improved = False
        n = len(work["tables"])
        for a in range(n):
            for b in range(a + 1, n):
                trial = json.loads(json.dumps(work))
                trial["tables"][a], trial["tables"][b] = trial["tables"][b], trial["tables"][a]
                o, found, c = _layout_cost(_render_schema_once(trial, corners, theme))
                if c < cost:
                    work, out, bad, cost, improved = trial, o, found, c, True
        if not improved or not bad:
            break
    return out


def _render_schema_once(spec, corners="editorial", theme=None):
    t = theme or THEME
    tables = spec.get("tables", [])
    relations = spec.get("relations", [])
    head_bits, head_h = figure_heading(t, spec.get("title") or "", spec.get("sub") or "", x=30)
    base_y = max(90, head_h + 16)
    rx = corner_rx(corners)
    tbl_w, row_h = 240, 24
    # the gap between columns fits the widest relation label, so labels never sit on a table
    widest = max((_pill_w(str(r.get("label", "")).upper()) for r in relations if r.get("label")), default=0)
    col_gap, row_gap = min(170, max(70, widest + 36)), 60
    max_cols = 3 if len(tables) >= 3 else max(1, len(tables))
    # a row is as tall as its tallest table, so a long table never runs into the row below
    tallest = {}
    for i, tbl in enumerate(tables):
        if not ("x" in tbl and "y" in tbl):
            r = i // max_cols
            tallest[r] = max(tallest.get(r, 0), 44 + len(tbl.get("columns", [])) * row_h + 12)
    row_top, acc = {}, base_y
    for r in range(max(tallest, default=-1) + 1):
        row_top[r] = acc
        acc += max(260, tallest.get(r, 0)) + row_gap
    table_boxes = {}
    for i, tbl in enumerate(tables):
        cols = tbl.get("columns", [])
        h = 44 + len(cols) * row_h + 12
        if "x" in tbl and "y" in tbl:
            x, y = tbl["x"], tbl["y"]
        else:
            grid_c = i % max_cols
            grid_r = i // max_cols
            x = 60 + grid_c * (tbl_w + col_gap)
            y = row_top[grid_r]
        col_y_map = {}
        for c_idx, c in enumerate(cols):
            col_y_map[c["name"]] = y + 44 + c_idx * row_h + row_h / 2
        table_boxes[tbl["id"]] = {"x": x, "y": y, "w": tbl_w, "h": h, "col_y_map": col_y_map, "tbl": tbl}
    max_x = max((b["x"] + b["w"] for b in table_boxes.values()), default=760)
    max_y = max((b["y"] + b["h"] for b in table_boxes.values()), default=400)
    _notes = (spec.get("notes", []) or [])[:2]
    if _notes:
        max_y = max(max_y, 110 + 14 + max(0, len(_notes) - 1) * 92 + 52)
    W = max(780, int(max_x + 60)) + (200 if _notes else 0)
    H = int(max_y + 72)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(spec.get("title","schema"))}</title>',
             f'<desc>{esc(spec.get("sub", spec.get("title", "schema")))}</desc>',
             f'<rect width="{W}" height="{H}" fill="{t["paper"]}"/>', markers(t)]
    parts.extend(head_bits)
    # Relations (rendered behind table cards)
    rel_labels = []
    for rel in relations:
        from_id, to_id = rel.get("from"), rel.get("to")
        if from_id not in table_boxes or to_id not in table_boxes:
            continue
        b1, b2 = table_boxes[from_id], table_boxes[to_id]
        from_col, to_col = rel.get("from_col"), rel.get("to_col")
        y1 = b1["col_y_map"].get(from_col, b1["y"] + b1["h"] / 2)
        y2 = b2["col_y_map"].get(to_col, b2["y"] + b2["h"] / 2)
        if b1["x"] + b1["w"] <= b2["x"]:
            x1, x2 = b1["x"] + b1["w"], b2["x"] - 6
        elif b2["x"] + b2["w"] <= b1["x"]:
            x1, x2 = b1["x"], b2["x"] + b2["w"] + 6
        else:
            x1, x2 = b1["x"] + b1["w"] / 2, b2["x"] + b2["w"] / 2
        focal = rel.get("focal", False)
        col = t["accent"] if focal else t["link"]
        mid = "aa" if focal else "al"
        parts.append(f'<path d="{elbow(x1, y1, x2, y2)}" fill="none" stroke="{col}" stroke-width="1.4" marker-end="url(#{mid})"/>')
        if rel.get("label"):
            if x1 == x2 or y1 == y2:
                pts = [(x1, y1), (x2, y2)]
            else:
                ex = x2 if abs(x2 - x1) < 60 else (x1 + x2) / 2
                pts = [(x1, y1), (ex, y1), (ex, y2), (x2, y2)]
            text = rel["label"].upper()
            boxes = [(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]) for b in table_boxes.values()]
            lx, ly, vert, flip = _place_label((x1 + x2) / 2, (y1 + y2) / 2, False, text, pts, boxes + rel_labels)
            parts.append(arrow_label(t, lx, ly, text, vertical=vert, flip=flip))
            rel_labels.append(_label_box(lx, ly, text, vert, flip))
    # Table cards
    for tid, b in table_boxes.items():
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        tbl = b["tbl"]
        focal = tbl.get("focal", False)
        stroke = t["accent"] if focal else t["ink"]
        fill_head = t["accent_tint"] if focal else "rgba(45,49,66,0.06)"
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{t["card"]}" stroke="{stroke}" stroke-width="1.2"/>')
        parts.append(f'<path d="M{x},{y+36} L{x},{y+rx} Q{x},{y} {x+rx},{y} L{x+w-rx},{y} Q{x+w},{y} {x+w},{y+rx} L{x+w},{y+36} Z" fill="{fill_head}"/>')
        parts.append(f'<line x1="{x}" y1="{y+36}" x2="{x+w}" y2="{y+36}" stroke="{t["rule"]}" stroke-width="1"/>')
        parts.append(f'<text x="{x+12}" y="{y+23}" font-size="13" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" data-role="table">{esc(tbl.get("name", tid))}</text>')
        tag = tbl.get("tag", "")
        if tag:
            tw = max(32, len(tag) * 7 + 8)
            parts.append(f'<rect x="{x+w-tw-10}" y="{y+12}" width="{tw}" height="14" rx="2" fill="none" stroke="{stroke}" stroke-opacity=".5" stroke-width=".8"/>')
            parts.append(f'<text x="{x+w-tw/2-10}" y="{y+22}" font-size="8" font-family="{MONO}" fill="{stroke}" text-anchor="middle">{esc(tag)}</text>')
        for c_idx, c in enumerate(tbl.get("columns", [])):
            cy = y + 44 + c_idx * row_h
            if c_idx > 0:
                parts.append(f'<line x1="{x+6}" y1="{cy}" x2="{x+w-6}" y2="{cy}" stroke="{t["rule"]}" stroke-width="0.5"/>')
            badge_x = x + 10
            if c.get("pk"):
                parts.append(f'<rect x="{badge_x}" y="{cy+4}" width="20" height="12" rx="2" fill="{t["accent"]}" fill-opacity=".15"/>')
                parts.append(f'<text x="{badge_x+10}" y="{cy+13}" font-size="7" font-weight="600" font-family="{MONO}" fill="{t["accent"]}" text-anchor="middle">PK</text>')
            elif c.get("fk"):
                parts.append(f'<rect x="{badge_x}" y="{cy+4}" width="20" height="12" rx="2" fill="{t["link"]}" fill-opacity=".15"/>')
                parts.append(f'<text x="{badge_x+10}" y="{cy+13}" font-size="7" font-weight="600" font-family="{MONO}" fill="{t["link"]}" text-anchor="middle">FK</text>')
            name_x = badge_x + (25 if (c.get("pk") or c.get("fk")) else 0)
            parts.append(f'<text x="{name_x}" y="{cy+15}" font-size="11" font-family="{MONO}" fill="{t["ink"]}">{esc(c["name"])}</text>')
            parts.append(f'<text x="{x+w-12}" y="{cy+15}" font-size="10" font-family="{MONO}" fill="{t["soft"]}" text-anchor="end">{esc(c.get("type",""))}</text>')
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in table_boxes:
                b = table_boxes[nt["at"]]
                rail.append((b["x"] + b["w"], b["y"] + 18, nt["text"]))
        parts.append(render_noterail(t, rail, W - 186, 110))
    ly = H - 28
    parts.append(f'<line x1="30" y1="{ly-10}" x2="{W-30}" y2="{ly-10}" stroke="{t["rule"]}" stroke-width=".8"/>')
    parts.append(f'<text x="30" y="{ly+4}" font-size="11" font-family="{FONT}" fill="{t["muted"]}">PK = primary key, FK = foreign key, blue = relation, coral = highlighted</text>')
    parts.append("</svg>")
    return "\n".join(parts), W, H

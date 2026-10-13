"""flow, arch, seq and schema: placement, routing and the repair loops."""
import json
from . import paint
from ._draw import (
    BOX_H, BOX_W, GROUP_PAD, _below_heading, _box_h, _diamond_h, _frame_edges, _groups_of, _label_box,
    _pill_w, _place_label, _seg_boxes, assign_ports, corner_rx, elbow, route_edge,
)
from ._theme import THEME
from .audit import _svg_geometry
from .scene.ids import edge_ids
from .style.styler import Styler


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


def _render_flow_once(spec, corners="editorial", auto=False, theme=None, styler=None):
    t = theme or THEME
    sty = styler or Styler(spec, "flow", t, corners)
    nodes = [dict(n) for n in spec["nodes"]]  # [{id,shape,name,tag?,sub?,focal?}]
    for n in nodes:
        n.setdefault("name", n.get("id", ""))
        st = sty.node(n.get("id"))
        n["shape"] = st["computed"].get("shape") or n.get("shape", "rect")  # a rule may set it
        sh = n["shape"]
        n["_h"] = 8 if sh == "dot" else (_diamond_h(n["name"], st) if sh == "diamond" else
                                         _box_h(n["name"], n.get("sub", ""), n.get("tag", "") or n.get("icon", ""), st=st))
    edges = spec.get("edges", [])  # [{from,to,label?,focal?}]
    _notes = (spec.get("notes", []) or [])[:2]
    head_els, head_h = paint.heading(t, spec.get("title") or "", spec.get("sub") or "", x=30, st=sty.figure(), eyebrow=spec.get("figure"))
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
    extra = _bottom(t, sty, spec, W)
    H += extra
    dr = paint.Drawing(W, H, spec.get("title", "flow"), spec.get("sub", spec.get("title", "flow")), kind="flow diagram")
    dr.add(paint.paper(t, W, H, sty.figure()["paper"]), paint.marker_defs(t), *head_els)
    frame_at, seg_boxes = len(dr.items), []
    node_boxes = [(cx - 80, cy - n["_h"] / 2, cx + 80, cy + n["_h"] / 2) for cx, cy, n in pos.values()]
    frame_edges = _frame_edges(_groups_of(spec, set(pos)), pos)
    label_boxes = []
    for nid, (cx, cy, n) in pos.items():
        painter = paint.SHAPES.get(n.get("shape", "rect")) or paint.SHAPES.get("rect")  # unknown: a box, as v1 draws it
        dr.add(*painter(t, nid, n, cx, cy, 160, n["_h"], corners, st=sty.node(nid)))
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
    eids = edge_ids(edges)
    for i, e in enumerate(edges):
        if i not in ports:
            continue
        x1, y1, s1, x2, y2, s2 = ports[i]
        es = sty.edge(eids[i])
        col = es["stroke"]
        mid = sty.marker(col)
        nudge = label_dy = 0
        if s1 in ("e", "w") and s2 in ("e", "w") and y1 > y2 + 24:
            nudge = -20 if x1 <= x2 else 20
            label_dy = -34
        d, lx, ly, vertical, pts = route_edge(x1, y1, s1, x2, y2, s2, nudge=nudge, track=tracks.get(i, 0))
        if not d:
            continue
        owner = eids[i]
        path = paint.edge_path(d, col, mid, owner, False,
                               {"data-from": e.get("from"), "data-to": e.get("to"), "data-label": e.get("label", ""),
                                "data-id": owner}, width=es["stroke-width"], dash=es["dasharray"])
        path.a11y = {"name": _edge_name(pos, e), "kind": "arrow"}
        path.attach = {"from": {"node": e.get("from"), "port": s1}, "to": {"node": e.get("to"), "port": s2}}
        dr.add(path,
               paint.tail(x1, y1, s1, col, owner))
        seg_boxes += _seg_boxes(pts)
        if e.get("label"):
            text = paint.transformed(e["label"], es["label"])
            lx, ly, vertical, flip = _place_label(lx, ly + label_dy, vertical, text, pts,
                                                  node_boxes + label_boxes + frame_edges)
            dr.add(*paint.arrow_label(t, lx, ly, text, vertical=vertical, flip=flip, owner=owner, st=es["label"],
                                      pill=es["paper"]))
            label_boxes.append(_label_box(lx, ly, text, vertical, flip))
    _more_markers(dr, sty)
    dr.insert(frame_at, paint.group_frames(t, _groups_of(spec, set(pos)), pos, seg_boxes, style_of=sty.group))
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in pos:
                cx, cy, _n = pos[nt["at"]]
                rail.append((cx + 80, cy, nt["text"]))
        dr.add(*paint.note_rail(t, rail, W - 186, top, st=sty.figure()["note"]))
    shapes = {n["shape"] for _, _, n in pos.values()}
    _legend(dr, t, sty, W, H, extra, 48, 32, _phrases((bool(shapes - {"diamond", "oval", "dot"}), "box = step"),
                                                   ("diamond" in shapes, "diamond = decision"),
                                                   ("oval" in shapes, "rounded = start or end")), spec)
    return dr, W, H, {nid: (cx, cy) for nid, (cx, cy, _n) in pos.items()}


def render_flow(spec, corners="editorial", auto=False, theme=None, sheets=(), embed=False):
    """Draw a flow. If an arrow runs through a box, move a node the spec left free to
    another lane and draw again. A node with its own lane is never moved. A move must lower
    the layout cost (problems, crossings, arrow length), not just the problem count."""
    sty = Styler(spec, "flow", theme or THEME, corners, sheets)  # styles don't depend on the lanes the loop moves

    def draw(sp):
        dr, w, h, placed = _render_flow_once(sp, corners, auto, theme, sty)
        out, found, c = _layout_cost((dr, w, h))
        return out, placed, found, c
    out, pos, bad, cost = draw(spec)
    if not bad:
        return _as_svg(out, sty, embed)
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
    return _as_svg(out, sty, embed)


def render_arch(spec, corners="editorial", theme=None, sheets=(), embed=False):
    """Draw an architecture view. If the audit finds a problem (an arrow through a box, two
    arrows on one line, a label collision), try other orders within each row (layers never
    change). Keep the order with the lowest cost: a problem counts as four crossings, and
    arrow length breaks ties, so one fix is never bought with a tangle of new crossings."""
    sty = Styler(spec, "arch", theme or THEME, corners, sheets)  # shared by the drafts: they only reorder rows
    out, bad, cost = _layout_cost(_render_arch_once(spec, corners, theme, sty))
    if not bad or not isinstance(spec.get("nodes"), list):
        return _as_svg(out, sty, embed)
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
                    o, found, c = _layout_cost(_render_arch_once(trial, corners, theme, sty))
                    if c < cost:
                        work, out, bad, cost, improved = trial, o, found, c, True
        if not improved:
            break
    return _as_svg(out, sty, embed)


def _layout_cost(out):
    """(draft, audit problems, cost) for the layout repair loops. A draft is (Drawing, W, H): the
    audit reads the drawing's element tree, so no draft is written out as SVG and parsed back
    (D5). _as_svg() writes the one that wins."""
    stats = {"crossings": 0, "wire": 0.0}
    found = _svg_geometry(out[0].etree(), out[1], out[2], stats)
    bad = [i for i in found if i["code"] in ("through", "strike", "overlap", "collide", "shared", "intrude")]
    return out, bad, 4 * len(bad) + stats["crossings"] + stats["wire"] / 400.0


def _edge_name(pos, e, label=None):
    """An arrow as a reader hears it: "Tests to Deploy: pass"."""
    def name(nid):
        return str(pos[nid][2].get("name", nid)) if nid in pos else str(nid)
    text = e.get("label", "") if label is None else label
    return f"{name(e.get('from'))} to {name(e.get('to'))}" + (f": {text}" if text else "")


def _more_markers(dr, sty):
    """Arrowheads for the stroke colors the styles chose beyond the four default ones."""
    if sty.extra_markers:
        defs = next(e for e in dr.items if e.role == "figure.defs")
        known = {c.attrs.get("id") for c in defs.children}
        paint.add_markers(defs, {c: m for c, m in sty.extra_markers.items() if m not in known})


def _bottom(t, sty, spec, W):
    """How much the canvas grows at the bottom: legend rows for encodings and rule legends, then the
    caption (B17), if there is one."""
    rows = paint.legend_height(t, sty.legend_entries(), W - 60)
    lines = paint.caption_lines(spec.get("caption") or "", W - 60, sty.figure()["caption"])
    return rows + ((sty.figure()["caption"]["font-size"] + 4) * len(lines) + 8 if lines else 0)


def _legend(dr, t, sty, W, H, extra, rule_off, text_off, sentence, spec=None):
    """The bottom of the figure: the preset's sentence (only what the figure shows), the swatch rows
    for encodings and rule legends, then the caption, which together grew the canvas by `extra`.
    The rule sits rule_off and the sentence text_off above where the bottom was."""
    cap = sty.figure()["caption"]
    lines = paint.caption_lines((spec or {}).get("caption") or "", W - 60, cap)
    cap_h = (cap["font-size"] + 4) * len(lines) + 8 if lines else 0
    rows = extra - cap_h
    if sentence or extra:
        els = paint.legend_line(t, W, H - rule_off - extra, H - text_off - extra, sentence, st=sty.figure()["legend"])
        dr.add(*(els if sentence else els[:1]))
    if rows:
        dr.add(*paint.legend_rows(t, sty.legend_entries(), 30, H - text_off - extra + paint.LEGEND_ROW, W - 60)[0])
    if lines:
        dr.add(*paint.caption(t, lines, 30, H - text_off - extra + rows + cap["font-size"] + 10, cap))


def _phrases(*pairs):
    """The legend sentence: each (shown, phrase) whose part the figure has."""
    return ", ".join(p for shown, p in pairs if shown)


def _first(items, test):
    return next((x for x in items if test(x)), None)


def _fonts(dr, sty, embed):
    """--embed-fonts: the fonts the figure measured with, embedded in a <style>. A font whose license
    forbids embedding is only referenced, and its family is marked for the audit's warning."""
    style, refused = sty.embed(embed)
    if style is not None:
        dr.insert(1, [style])
    if refused:
        dr.items[0].attrs["data-font-restricted"] = ", ".join(refused)


def _as_svg(out, sty=None, embed=False):
    """A draft from the repair loops as the (svg, W, H) the callers take, its fonts embedded if asked."""
    if sty is not None:
        _fonts(out[0], sty, embed)
    return (out[0].svg(),) + tuple(out[1:])


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


def _render_arch_once(spec, corners="editorial", theme=None, styler=None):
    t = theme or THEME
    sty = styler or Styler(spec, "arch", t, corners)
    nodes = [dict(n) for n in spec["nodes"]]; edges = spec.get("edges", [])
    for n in nodes:
        n.setdefault("name", n.get("id", ""))
        n["_h"] = _box_h(n["name"], n.get("sub", ""), n.get("tag", "") or n.get("icon", ""), st=sty.node(n["id"]))
    _notes = (spec.get("notes", []) or [])[:2]
    head_els, head_h = paint.heading(t, spec.get("title") or "", spec.get("sub") or "", x=30, st=sty.figure(), eyebrow=spec.get("figure"))
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
    extra = _bottom(t, sty, spec, W)
    H += extra
    dr = paint.Drawing(W, H, spec.get("title", "arch"), spec.get("sub", spec.get("title", "arch")), kind="architecture diagram")
    dr.add(paint.paper(t, W, H, sty.figure()["paper"]), paint.marker_defs(t), *head_els)
    frame_at = len(dr.items)
    for nid, (x, y, n) in pos.items():
        dr.add(*paint.SHAPES.get("rect")(t, nid, n, x, y, 160, n["_h"], corners, st=sty.node(nid)))
    node_boxes = [(x - 80, y - n["_h"] / 2, x + 80, y + n["_h"] / 2) for x, y, n in pos.values()]
    frame_edges = _frame_edges(groups, pos)
    label_boxes = []
    ports = assign_ports(pos, edges, layered=True)
    tracks = _gap_tracks(ports)
    routes = []
    eids = edge_ids(edges)
    for i, e in enumerate(edges):
        if i not in ports:
            continue
        x1, y1, s1, x2, y2, s2 = ports[i]
        es = sty.edge(eids[i])
        col = es["stroke"]
        mid = sty.marker(col)
        d, lx, ly, vertical, pts = route_edge(x1, y1, s1, x2, y2, s2, track=tracks.get(i, 0))
        if not d:
            continue
        owner = eids[i]
        path = paint.edge_path(d, col, mid, owner, False,
                               {"data-from": e.get("from"), "data-to": e.get("to"), "data-label": e.get("label", ""),
                                "data-id": owner}, width=es["stroke-width"], dash=es["dasharray"])
        path.a11y = {"name": _edge_name(pos, e), "kind": "arrow"}
        path.attach = {"from": {"node": e.get("from"), "port": s1}, "to": {"node": e.get("to"), "port": s2}}
        dr.add(path,
               paint.tail(x1, y1, s1, col, owner))
        segs = [(min(p[0], q[0]) - 1, min(p[1], q[1]) - 1, max(p[0], q[0]) + 1, max(p[1], q[1]) + 1)
                for p, q in zip(pts, pts[1:])]
        routes.append((e, lx, ly, vertical, pts, segs, owner, es))
    _more_markers(dr, sty)
    dr.insert(frame_at, paint.group_frames(t, groups, pos, [b for r in routes for b in r[5]], style_of=sty.group))
    # Labels go last, once every arrow is routed: each one keeps clear of the boxes,
    # the labels already placed, and every other arrow.
    for k, (e, lx, ly, vertical, pts, _segs, owner, es) in enumerate(routes):
        if e.get("label"):
            text = paint.transformed(e["label"], es["label"])
            others = [b for j, r in enumerate(routes) if j != k for b in r[5]]
            lx, ly, vertical, flip = _place_label(lx, ly, vertical, text, pts, node_boxes + label_boxes + frame_edges, others)
            dr.add(*paint.arrow_label(t, lx, ly, text, vertical=vertical, flip=flip, owner=owner, st=es["label"],
                                      pill=es["paper"]))
            label_boxes.append(_label_box(lx, ly, text, vertical, flip))
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in pos:
                x, y, _n = pos[nt["at"]]
                rail.append((x + 80, y, nt["text"]))
        dr.add(*paint.note_rail(t, rail, W - 186, top, st=sty.figure()["note"]))
    http = _first(range(len(edges)), lambda i: str(edges[i].get("proto", "")).startswith("http"))
    focal_node = _first(nodes, lambda n: n.get("focal"))
    focal_edge = _first(range(len(edges)), lambda i: edges[i].get("focal"))
    hi = sty.node(focal_node["id"])["stroke"] if focal_node else (sty.edge(eids[focal_edge])["stroke"] if focal_edge is not None else None)
    _legend(dr, t, sty, W, H, extra, 48, 32, _phrases(
        (http is not None, f"{paint.color_word(sty.edge(eids[http])['stroke'])} = HTTP call" if http is not None else ""),
        (any(e.get("async") for e in edges), "dashed = sent in the background"),
        (hi is not None, f"{paint.color_word(hi)} = highlighted" if hi else "")), spec)
    return dr, W, H


def render_seq(spec, corners="editorial", theme=None, sheets=(), embed=False):
    t = theme or THEME
    sty = Styler(spec, "seq", t, corners, sheets)
    actors = spec.get("actors", [])
    messages = spec.get("messages", [])
    n_act = max(1, len(actors))
    margin_x = 70
    _notes = (spec.get("notes", []) or [])[:2]
    head_els, head_h = paint.heading(t, spec.get("title") or "", spec.get("sub") or "", x=30, st=sty.figure(), eyebrow=spec.get("figure"))
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
    bh = 52  # actor boxes share one height, grown when a name, styled or long, needs it
    for a in actors:
        nl_, sl_, lab_, sb_ = paint.box_text(a.get("name", a.get("id", "")), a.get("sub", ""), 140, sty.node(a.get("id")))
        block = lab_["pitch"] * len(nl_) + (sb_["pitch"] * len(sl_) + 2 if sl_ else 0)
        bh = max(bh, (20 if a.get("tag") else 8) + block + 3)
    msg_gap = 52
    msg_start = top + bh + 34  # the first message's label sits clear of the actor boxes
    H = msg_start + len(messages) * msg_gap + 80
    extra = _bottom(t, sty, spec, W)
    H += extra
    dr = paint.Drawing(W, H, spec.get("title", "sequence"), spec.get("sub", spec.get("title", "sequence")),
                       kind="sequence diagram")
    dr.add(paint.paper(t, W, H, sty.figure()["paper"]), paint.marker_defs(t), *head_els)
    # Lifelines
    for aid, (cx, a) in pos.items():
        dr.add(paint.el("line", owner=aid, role="actor.lifeline", x1=cx, y1=top + bh, x2=cx, y2=H - 50, stroke=t["rule"],
                        stroke_width=1.2, stroke_dasharray="4,4"))
    # Messages
    mids = edge_ids(messages)
    for i, m in enumerate(messages):
        f_id = m.get("from")
        t_id = m.get("to")
        if f_id not in pos or t_id not in pos:
            continue
        x1, _ = pos[f_id]
        x2, _ = pos[t_id]
        my = msg_start + i * msg_gap
        es = sty.edge(mids[i])
        col = es["stroke"]
        mid = sty.marker(col)
        owner = mids[i]
        # read back by the outline: who sends what to whom, in order
        look = {"stroke-dasharray": ",".join(paint.fmt(v) for v in es["dasharray"]) if es["dasharray"] else None,
                "data-msg": m.get("label", ""), "data-msg-from": pos[f_id][1].get("name", f_id),
                "data-msg-to": pos[t_id][1].get("name", t_id), "marker-end": f"url(#{mid})", "data-id": owner}
        said = {"name": f"{i + 1}. {pos[f_id][1].get('name', f_id)} to {pos[t_id][1].get('name', t_id)}"
                        + (f": {m['label']}" if m.get("label") else ""), "kind": "message"}
        if f_id == t_id:
            # Self-call loop
            lw = 32
            dr.add(paint.el("path", owner=owner, role="message.path", a11y=said,
                            d=f"M{x1},{my} L{x1 + lw},{my} L{x1 + lw},{my + 20} L{x1 + 4},{my + 20}",
                            fill="none", stroke=col, stroke_width=es["stroke-width"] * 1.5 / 1.6,  # a loop draws a touch finer
                            **{k.replace("-", "_"): v for k, v in look.items()}))
            if m.get("label"):
                dr.add(*paint.arrow_label(t, x1 + lw + max(20, len(m["label"]) * 3.5), my + 10,
                                          paint.transformed(m["label"], es["label"]), owner=owner, st=es["label"],
                                          pill=es["paper"]))
        else:
            direction = 1 if x2 >= x1 else -1
            x_from = x1 + direction * 8
            x_to = x2 - direction * 8
            dr.add(paint.el("line", owner=owner, role="message.path", a11y=said, x1=x_from, y1=my, x2=x_to, y2=my, stroke=col,
                            stroke_width=es["stroke-width"], **{k.replace("-", "_"): v for k, v in look.items()}))
            if m.get("label"):
                lbl = m["label"]
                if m.get("proto"):
                    lbl = f"[{m['proto'].upper()}] {lbl}"
                dr.add(*paint.arrow_label(t, (x1 + x2) / 2, my, paint.transformed(lbl, es["label"]), owner=owner,
                                          st=es["label"], pill=es["paper"]))
    _more_markers(dr, sty)
    # Actor boxes at top
    for aid, (cx, a) in pos.items():
        bw = 140
        bx, by = cx - bw / 2, top
        dr.add(*paint.named(paint.node_box(t, bx, by, bw, bh, a.get("name", aid), a.get("sub", ""), a.get("tag", ""),
                                           a.get("focal", False), corners, aid, st=sty.node(aid)), "actor",
                            paint.node_name(a, aid)))
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in pos:
                cx, _a = pos[nt["at"]]
                rail.append((cx + 70, top + 26, nt["text"]))
        dr.add(*paint.note_rail(t, rail, W - 186, top, st=sty.figure()["note"]))
    http = _first(range(len(messages)), lambda i: str(messages[i].get("proto", "")).startswith("http"))
    focal_actor = _first(actors, lambda a: a.get("focal"))
    focal_msg = _first(range(len(messages)), lambda i: messages[i].get("focal"))
    hi = sty.node(focal_actor["id"])["stroke"] if focal_actor else (sty.edge(mids[focal_msg])["stroke"] if focal_msg is not None else None)
    _legend(dr, t, sty, W, H, extra, 38, 24, _phrases(
        (any(not (m.get("reply") or m.get("async")) for m in messages), "solid = call"),
        (any(m.get("reply") or m.get("async") for m in messages), "dashed = reply or event"),
        (http is not None, f"{paint.color_word(sty.edge(mids[http])['stroke'])} = HTTP" if http is not None else ""),
        (hi is not None, f"{paint.color_word(hi)} = highlighted" if hi else "")), spec)
    _fonts(dr, sty, embed)
    return dr.svg(), W, H


def render_schema(spec, corners="editorial", theme=None, sheets=(), embed=False):
    """Draw tables and relations. If the audit finds a problem, try other table orders and keep
    the one with the lowest layout cost (problems, crossings, length), as render_arch does."""
    sty = Styler(spec, "schema", theme or THEME, corners, sheets)  # shared by the drafts: they only reorder tables
    out, bad, cost = _layout_cost(_render_schema_once(spec, corners, theme, sty))
    tables = spec.get("tables") if isinstance(spec, dict) else None
    if not bad or not isinstance(tables, list) or any("x" in tb for tb in tables if isinstance(tb, dict)):
        return _as_svg(out, sty, embed)
    work = json.loads(json.dumps(spec))
    for _ in range(4):
        improved = False
        n = len(work["tables"])
        for a in range(n):
            for b in range(a + 1, n):
                trial = json.loads(json.dumps(work))
                trial["tables"][a], trial["tables"][b] = trial["tables"][b], trial["tables"][a]
                o, found, c = _layout_cost(_render_schema_once(trial, corners, theme, sty))
                if c < cost:
                    work, out, bad, cost, improved = trial, o, found, c, True
        if not improved or not bad:
            break
    return _as_svg(out, sty, embed)


def _render_schema_once(spec, corners="editorial", theme=None, styler=None):
    t = theme or THEME
    sty = styler or Styler(spec, "schema", t, corners)
    tables = spec.get("tables", [])
    relations = spec.get("relations", [])
    head_els, head_h = paint.heading(t, spec.get("title") or "", spec.get("sub") or "", x=30, st=sty.figure(), eyebrow=spec.get("figure"))
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
    extra = _bottom(t, sty, spec, W)
    H += extra
    dr = paint.Drawing(W, H, spec.get("title", "schema"), spec.get("sub", spec.get("title", "schema")),
                       kind="database schema")
    dr.add(paint.paper(t, W, H, sty.figure()["paper"]), paint.marker_defs(t), *head_els)
    # Relations (rendered behind table cards)
    rel_labels = []
    rids = edge_ids(relations)
    for k, rel in enumerate(relations):
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
        es = sty.edge(rids[k])
        col = es["stroke"]
        mid = sty.marker(col)
        owner = rids[k]
        names = {tid: {"name": b["tbl"].get("name", tid)} for tid, b in table_boxes.items()}
        dr.add(paint.el("path", owner=owner, role="edge.path", d=elbow(x1, y1, x2, y2), fill="none", stroke=col,
                        stroke_width=es["stroke-width"],
                        stroke_dasharray=",".join(paint.fmt(v) for v in es["dasharray"]) if es["dasharray"] else None,
                        marker_end=f"url(#{mid})", data_from=from_id, data_to=to_id,
                        data_label=rel.get("label", ""), data_id=owner,
                        a11y={"name": _edge_name({k: (0, 0, v) for k, v in names.items()}, rel), "kind": "relation"},
                        attach={"from": {"node": from_id, "port": from_col}, "to": {"node": to_id, "port": to_col}}))
        if rel.get("label"):
            if x1 == x2 or y1 == y2:
                pts = [(x1, y1), (x2, y2)]
            else:
                ex = x2 if abs(x2 - x1) < 60 else (x1 + x2) / 2
                pts = [(x1, y1), (ex, y1), (ex, y2), (x2, y2)]
            text = paint.transformed(rel["label"], es["label"])
            boxes = [(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]) for b in table_boxes.values()]
            lx, ly, vert, flip = _place_label((x1 + x2) / 2, (y1 + y2) / 2, False, text, pts, boxes + rel_labels)
            dr.add(*paint.arrow_label(t, lx, ly, text, vertical=vert, flip=flip, owner=owner, st=es["label"],
                                      pill=es["paper"]))
            rel_labels.append(_label_box(lx, ly, text, vert, flip))
    _more_markers(dr, sty)
    # Table cards
    for tid, b in table_boxes.items():
        dr.add(*paint.table_card(t, b["x"], b["y"], b["w"], b["h"], rx, tid, b["tbl"], row_h, st=sty.table(tid)))
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in table_boxes:
                b = table_boxes[nt["at"]]
                rail.append((b["x"] + b["w"], b["y"] + 18, nt["text"]))
        dr.add(*paint.note_rail(t, rail, W - 186, 110, st=sty.figure()["note"]))
    cols = [c for tb in tables for c in tb.get("columns", [])]
    focal_tbl = _first(tables, lambda tb: tb.get("focal"))
    focal_rel = _first(range(len(relations)), lambda i: relations[i].get("focal"))
    hi = sty.node(focal_tbl["id"])["stroke"] if focal_tbl else (sty.edge(rids[focal_rel])["stroke"] if focal_rel is not None else None)
    _legend(dr, t, sty, W, H, extra, 38, 24, _phrases(
        (any(c.get("pk") for c in cols), "PK = primary key"),
        (any(c.get("fk") for c in cols), "FK = foreign key"),
        (bool(relations), f"{paint.color_word(sty.edge(rids[0])['stroke'])} = relation" if relations else ""),
        (hi is not None, f"{paint.color_word(hi)} = highlighted" if hi else "")), spec)
    return dr, W, H

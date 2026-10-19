"""flow, arch, seq and schema: each preset's look over the layout kernels (layout/).

flow, arch and schema place their boxes with the layered layout and draw its routes as they are: no
draft is audited and redrawn. `engine="v1"` (`--layout-engine v1`) draws with the v1 rows and repair
loops (legacy.py) until P8.
"""
from . import paint
from ._draw import _bold, _groups_of, _round_poly, _seg_boxes, corner_rx
from ._theme import THEME
from .route.labels import GAP, label_box, place_label
from .scene.ids import edge_ids
from .style.styler import Styler

ENGINES = ("v2", "v1")
MARGIN = 30  # between the canvas edge and the nearest box or frame


def render_flow(spec, corners="editorial", auto=False, theme=None, sheets=(), embed=False, engine=None, prev=None,
                info=None):
    """Draw a flow: steps in layers top to bottom, decisions branching sideways, loops climbing back
    up the side. auto ranks every node, ignoring the spec's ranks. prev: {node id: x} from the drawing
    before an edit, so the boxes the edit leaves alone stay near their places. info, if a dict, gets the
    layout's layers (_layered), which the page's edit mode moves boxes between."""
    if engine == "v1":
        from .legacy import render_flow as v1
        return v1(spec, corners, auto, theme, sheets, embed)
    t = theme or THEME
    sty = Styler(spec, "flow", t, corners, sheets)
    nodes = []
    for n in spec["nodes"]:
        n = dict(n)
        n.setdefault("name", n.get("id", ""))
        st = sty.node(n.get("id"))
        n["shape"] = st["computed"].get("shape") or n.get("shape", "rect")
        sh = n["shape"]
        if str(n.get("tag", "")).strip().lower() in SAID_BY_SHAPE.get(sh, ()):
            n["tag"] = ""  # STEP on a box, END on a rounded box: the shape and the legend say it already
        if sh == "dot":
            n["_w"] = n["_h"] = 8
        elif sh == "diamond":
            n["_w"], n["_h"], n["_room"] = paint.diamond_size(n["name"], st)
        else:
            n["_w"], n["_h"], n["_pad"] = paint.box_size(n["name"], n.get("sub", ""), n.get("tag", ""), n.get("icon"), st)
        if auto:
            n.pop("rank", None)
        nodes.append(n)
    _even_widths(nodes, sty)
    shapes = {n["shape"] for n in nodes}
    sentence = _phrases((bool(shapes - {"diamond", "oval", "dot"}), "box = step"), ("diamond" in shapes, "diamond = decision"),
                        ("oval" in shapes, "rounded = start or end"))
    min_w = _min_width(spec, t, sty, sentence)
    dr, W, H, extra = _layered(spec, "flow", nodes, t, sty, corners, {"trunk": True, "straight": True, "rank_gap": 48.0, "min_width": min_w - 2 * MARGIN,
                                                                      "prev": prev}, min_w, "flow diagram", info=info,
                               legend=bool(sentence))
    _legend(dr, t, sty, W, H, extra, LEGEND_RULE, LEGEND_TEXT, sentence, spec)
    return _as_svg((dr, W, H), sty, embed)


def _even_widths(nodes, sty, spread=4 / 3):
    """Boxes whose fitted widths are close (the widest at most `spread` times the narrowest) all take the
    widest, so a figure of similar names reads as a grid. Each keeps where its text wraps. A box whose
    style sets its width keeps that width."""
    boxes = [n for n in nodes if "_pad" in n and not sty.node(n["id"])["computed"].get("width")]
    if len(boxes) < 2:
        return
    widest = max(n["_w"] for n in boxes)
    if widest > spread * min(n["_w"] for n in boxes):
        return
    for n in boxes:
        n["_pad"] = (widest - (n["_w"] - 2 * n["_pad"])) / 2.0
        n["_w"] = widest


# tags a flow leaves out: the box's shape, and the legend under it, already say what they say
SAID_BY_SHAPE = {"rect": ("step", "process"), "oval": ("start", "end", "begin", "stop"), "diamond": ("decision",)}
LEGEND_RULE, LEGEND_TEXT = 40, 22  # how far above the bottom the legend's rule and its sentence sit


def _min_width(spec, t, sty, sentence, floor=240, rows_up_to=660):
    """The least width of a figure: what its title, subtitle, eyebrow and legend sentence need, each on
    one line beside the margins, and its legend's swatches on one row if that row is at most rows_up_to
    wide. A figure is otherwise only as wide as what it draws."""
    from .text.measure import width
    fig = sty.figure()
    need = floor - 2 * MARGIN
    row = sum(w for w, _ in paint._legend_items(sty.legend_entries(), t))
    if row <= rows_up_to:
        need = max(need, row)
    for text, st in ((spec.get("title"), fig["title"]), (spec.get("sub"), fig["sub"]), (spec.get("figure"), fig["eyebrow"]),
                     (sentence, fig["legend"])):
        if text:
            text = paint.transformed(str(text), st)
            need = max(need, width(text, st["font-size"], _bold(st), "", st.get("font")) * 1.04)
    return int(need + 2 * MARGIN + 0.999)


def _label_w(text, st):
    """An arrow label's pill: the text as its style measures it, and 4 px either side."""
    from .text.measure import width
    return float(int(width(text, st["font-size"], _bold(st), "", st.get("font")) + 8.999))


def render_arch(spec, corners="editorial", theme=None, sheets=(), embed=False, engine=None, prev=None, info=None):
    """Draw an architecture view: one row per layer, calls running down between rows, calls within a
    row running straight between neighbors, groups framed."""
    if engine == "v1":
        from .legacy import render_arch as v1
        return v1(spec, corners, theme, sheets, embed)
    t = theme or THEME
    sty = Styler(spec, "arch", t, corners, sheets)
    nodes = []
    layered = any("layer" in n or "rank" in n for n in spec["nodes"])
    for n in spec["nodes"]:
        n = dict(n)
        n.setdefault("name", n.get("id", ""))
        n["shape"] = "rect"
        n["_w"], n["_h"], n["_pad"] = paint.box_size(n["name"], n.get("sub", ""), n.get("tag", ""), n.get("icon"),
                                                     sty.node(n["id"]))
        if layered:
            n["rank"] = n.get("layer", n.get("rank", 0))
        nodes.append(n)
    _even_widths(nodes, sty)
    edges = spec.get("edges", [])
    eids = edge_ids(edges)
    http = _first(range(len(edges)), lambda i: str(edges[i].get("proto", "")).startswith("http"))
    focal_node = _first(nodes, lambda n: n.get("focal"))
    focal_edge = _first(range(len(edges)), lambda i: edges[i].get("focal"))
    hi = sty.node(focal_node["id"])["stroke"] if focal_node else (sty.edge(eids[focal_edge])["stroke"] if focal_edge is not None else None)
    sentence = _phrases(
        (http is not None, f"{paint.color_word(sty.edge(eids[http])['stroke'])} = HTTP call" if http is not None else ""),
        (any(e.get("async") for e in edges), "dashed = sent in the background"),
        (hi is not None, f"{paint.color_word(hi)} = highlighted" if hi else ""))
    min_w = _min_width(spec, t, sty, sentence)
    dr, W, H, extra = _layered(spec, "arch", nodes, t, sty, corners, {"rank_gap": 64.0, "back": "ports", "balance": True, "min_width": min_w - 2 * MARGIN,
                                                                      "prev": prev}, min_w, "architecture diagram", info=info,
                               legend=bool(sentence))
    _legend(dr, t, sty, W, H, extra, LEGEND_RULE, LEGEND_TEXT, sentence, spec)
    return _as_svg((dr, W, H), sty, embed)


def _layered(spec, kind, nodes, t, sty, corners, options, min_w, label, edges=None, pins=None, paint_node=None,
             tails=True, attach=None, a11y_kind="arrow", info=None, legend=True):
    """Lays out and paints a flow, arch or schema figure, all but its legend: (Drawing, W, H, legend
    rows). edges: the spec's edges unless given; pins: {edge index: (from_at, to_at)}, ends kept at an
    offset along their sides (a schema's column rows); paint_node(nid, node, cx, cy): its elements,
    else the node's shape; attach(edge, route): the ends' attachment for exports and the audit. legend: a
    sentence goes under the figure. An arrow gets a dot where it leaves its box only when its style asks
    (marker-start: circle)."""
    from .layout import layered
    edges = spec.get("edges", []) if edges is None else edges
    eids = edge_ids(edges)
    ids = {n["id"] for n in nodes}
    groups = _groups_of(spec, ids)
    head_els, head_h = paint.heading(t, spec.get("title") or "", spec.get("sub") or "", x=30, st=sty.figure(),
                                     eyebrow=spec.get("figure"))
    flat_room, label_w = {}, {}
    for i, e in enumerate(edges):  # a labelled arrow between neighbors in a layer needs room for its label
        if e.get("label") and e.get("from") in ids and e.get("to") in ids:
            ls = sty.edge(eids[i])["label"]
            label_w[eids[i]] = _label_w(paint.transformed(e["label"], ls), ls)
            flat_room[(e["from"], e["to"])] = label_w[eids[i]] + 24
    lnodes = []
    for n in nodes:
        d = {"id": n["id"], "w": n["_w"], "h": n["_h"], "shape": n["shape"]}
        for k in ("rank", "lane", "order"):
            if isinstance(n.get(k), (int, float)) and not isinstance(n.get(k), bool):
                d[k] = n[k]
        lnodes.append(d)
    # constraints from edits (scene/patch.py): same-rank shares a layer; order is kept within one,
    # for the nodes that carry no order or lane of their own
    cons = [c for c in spec.get("constraints") or [] if isinstance(c, dict)]
    same = [[i for i in c["same-rank"] if i in ids] for c in cons if isinstance(c.get("same-rank"), list)]
    by = {d["id"]: d for d in lnodes}
    for c in cons:
        if isinstance(c.get("order"), list):
            for k, i in enumerate(i for i in c["order"] if i in by):
                if "order" not in by[i] and "lane" not in by[i]:
                    by[i]["order"] = k
    ledges = []
    for i, e in enumerate(edges):
        if e.get("from") in ids and e.get("to") in ids:
            le = {"id": eids[i], "from": e.get("from"), "to": e.get("to")}
            for key, at in zip(("from_at", "to_at"), (pins or {}).get(i, (None, None))):
                if at is not None:
                    le[key] = at
            ledges.append(le)
    res = layered.layout(lnodes, ledges, [{"id": g["id"], "members": g["members"]} for g in groups],
                         dict(options, flat_room=flat_room, aspect=_aspect(spec), labels=label_w, margin=MARGIN,
                              same_rank=[s for s in same if len(s) > 1]))
    top = max(MARGIN, head_h + 12)
    if info is not None:  # for the page and the verdict: each layer's boxes in order, and whether layers run across
        info["layers"] = [[it for it in layer if it in ids] for layer in res.layers]
        info["layers"] = [layer for layer in info["layers"] if layer]
        info["across"] = str(options.get("direction", "TB")).upper() in ("LR", "RL")
        if res.wrapped:  # where the columns break: a layer that starts above the one before it begins one
            k = 0 if info["across"] else 1
            start = [min(res.pos[i][k] for i in layer) for layer in info["layers"]]
            breaks = [j for j in range(1, len(start)) if start[j] < start[j - 1]]
            info["columns"] = [(lo + 1, hi) for lo, hi in zip([0] + breaks, breaks + [len(start)])]
    notes = (spec.get("notes", []) or [])[:2]
    cw, ch = res.size
    W = max(min_w, int(cw + 2 * MARGIN + 0.999))
    ox, oy = (W - cw) / 2.0, float(top)
    by_id = {n["id"]: n for n in nodes}
    pos = {nid: (x + ox, y + oy, by_id[nid]) for nid, (x, y) in res.pos.items()}
    frames = {g: (b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy) for g, b in res.frames.items()}
    routes = dict(res.routes)
    for r in routes.values():
        r.points = [(x + ox, y + oy) for x, y in r.points]
    low = oy + ch
    if notes:
        low = max(low, top + 14 + max(0, len(notes) - 1) * 92 + 52)
        W += 200
    H = int(low + (64 if legend else MARGIN))
    extra = _bottom(t, sty, spec, W)
    H += extra
    dr = paint.Drawing(W, H, spec.get("title", kind), spec.get("sub", spec.get("title", kind)), kind=label,
                       legible=True)
    dr.add(paint.paper(t, W, H, sty.figure()["paper"]), paint.marker_defs(t), *head_els)
    frame_at = len(dr.items)
    for nid, (cx, cy, n) in pos.items():
        if paint_node:
            dr.add(*paint_node(nid, n, cx, cy))
            continue
        painter = paint.SHAPES.get(n.get("shape", "rect")) or paint.SHAPES.get("rect")  # unknown: a box, as v1 draws it
        dr.add(*painter(t, nid, n, cx, cy, n["_w"], n["_h"], corners, st=sty.node(nid)))
    node_boxes = [(cx - n["_w"] / 2, cy - n["_h"] / 2, cx + n["_w"] / 2, cy + n["_h"] / 2) for cx, cy, n in pos.values()]
    strips = []
    for x0, y0, x1, y1 in frames.values():  # labels sit inside or outside a frame, not on its border
        strips += [(x0, y0 - 1, x1, y0 + 1), (x0, y1 - 1, x1, y1 + 1), (x0 - 1, y0, x0 + 1, y1), (x1 - 1, y0, x1 + 1, y1)]
        strips.append((x0, y0, x1, y0 + 20))  # the title band
    edges_by_id = {eids[i]: (i, e) for i, e in enumerate(edges)}
    drawn = []
    for eid, r in routes.items():
        i, e = edges_by_id[eid]
        es = sty.edge(eid)
        col = es["stroke"]
        mid = sty.marker(col)
        pts = r.points
        d = _round_poly(pts, 8)
        if not d:
            continue
        path = paint.edge_path(d, col, mid, eid, False,
                               {"data-from": e.get("from"), "data-to": e.get("to"), "data-label": e.get("label", ""),
                                "data-id": eid}, width=es["stroke-width"], dash=es["dasharray"])
        path.a11y = {"name": _edge_name(pos, e), "kind": a11y_kind}
        path.attach = attach(e, r) if attach else {"from": {"node": e.get("from"), "port": r.sides[0]},
                                                     "to": {"node": e.get("to"), "port": r.sides[1]}}
        dr.add(path)
        if tails and e.get("from") != e.get("to") and es["computed"].get("marker-start") == "circle":
            dr.add(paint.tail(pts[0][0], pts[0][1], r.sides[0], col, eid))
        drawn.append((e, eid, es, pts, _seg_boxes(pts)))
    _more_markers(dr, sty)
    dr.insert(frame_at, paint.group_frames(t, groups, pos, [b for x in drawn for b in x[4]], style_of=sty.group,
                                           boxes=frames))
    # labels last, once every arrow is down: each keeps clear of boxes, frames, the labels placed and
    # the canvas edge, and of other arrows where it can
    canvas = [(-40, 0, 0, H), (W, 0, W + 40, H), (0, -40, W, 0), (0, oy + ch + 22, W, H)]
    label_boxes = []
    for k, (e, eid, es, pts, segs) in enumerate(drawn):
        if not e.get("label"):
            continue
        text = paint.transformed(e["label"], es["label"])
        mx, my, vert = _longest(pts, frames.values())
        others = [b for x in drawn for b in x[4]]  # its own arrow too: a label never sits on it
        w = _label_w(text, es["label"])
        lx, ly, vert, flip = place_label(mx, my, vert, text, pts, node_boxes + label_boxes + strips + canvas, others, w, GAP)
        box = label_box(lx, ly, text, vert, flip, w, GAP)
        dr.add(*paint.arrow_label(t, lx, ly, text, vertical=vert, flip=flip, owner=eid, st=es["label"],
                                  pill=_ground(box, es["paper"], frames, sty), w=w, gap=GAP))
        label_boxes.append(box)
    if notes:
        rail = []
        for nt in notes:
            if nt.get("at") in pos:
                cx, cy, n = pos[nt["at"]]
                rail.append((cx + n["_w"] / 2, cy, nt["text"]))
        dr.add(*paint.note_rail(t, rail, W - 186, top, st=sty.figure()["note"]))
    _owned_opacity(dr, sty)
    return dr, W, H, extra


def _ground(box, paper, frames, sty):
    """The color under a label's pill: the paper, seen through every frame the pill sits in, so the pill
    masks the arrows it crosses without showing as a patch."""
    from .style.parse import Color, color
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    inside = [(g, b) for g, b in frames.items() if b[0] < cx < b[2] and b[1] < cy < b[3]]
    if not inside:
        return paper
    try:
        out = color(paper)
        for g, _ in sorted(inside, key=lambda gb: -(gb[1][2] - gb[1][0]) * (gb[1][3] - gb[1][1])):  # outermost first
            f = color(sty.group(g)["fill"])
            a = f.a * 0.35  # paint.group_frames draws the fill at this opacity
            out = Color(round(out.r + (f.r - out.r) * a), round(out.g + (f.g - out.g) * a), round(out.b + (f.b - out.b) * a))
        return out.css
    except Exception:
        return paper


def _owned_opacity(dr, sty):
    """A node's, edge's or frame's opacity reaches every part it owns (its underlay, text, badges,
    icon, arrowhead tail, label pill), not only the outline the shape painter gives it, so a view can
    dim or hide an element whole (story.py). An element that sets its own opacity keeps it."""
    v = sty.views
    memo = {}

    def opacity(owner):
        if owner not in memo:
            c = (sty.node(owner) if owner in v["nodes"] else sty.edge(owner) if owner in v["edges"]
                 else sty.group(owner) if owner in v["groups"] else {}).get("computed") or {}
            o = c.get("opacity")
            memo[owner] = o if isinstance(o, (int, float)) and not isinstance(o, bool) and o != 1 else None
        return memo[owner]

    def walk(items):
        for e in items:
            o = opacity(e.owner) if e.owner else None
            if o is not None:
                e.attrs.setdefault("opacity", o)
            else:
                walk(e.children)
    walk(dr.items)


ASPECT = 4 / 3  # a layered figure much taller than this wraps into columns (layout/wrap.py)


def _aspect(spec):
    """The target width / height: the spec's size.aspect ("16:9", 1.6), else ASPECT."""
    size = spec.get("size") if isinstance(spec.get("size"), dict) else {}
    a = size.get("aspect")
    try:
        if isinstance(a, str) and ":" in a:
            w, h = a.split(":", 1)
            return float(w) / float(h)
        if a is not None:
            return float(a)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return ASPECT


def _longest(pts, frames=()):
    """A label's first spot: the middle of the longest stretch of the route that no frame border
    crosses, and whether that stretch runs up and down (route.labels)."""
    from .route.labels import longest_segment
    return longest_segment(pts, frames)



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


def render_seq(spec, corners="editorial", theme=None, sheets=(), embed=False):
    """Draw a sequence: actors across the top, messages down their lifelines in order (layout/sequence)."""
    from .layout import sequence
    t = theme or THEME
    sty = Styler(spec, "seq", t, corners, sheets)
    actors = spec.get("actors", [])
    messages = spec.get("messages", [])
    _notes = (spec.get("notes", []) or [])[:2]
    head_els, head_h = paint.heading(t, spec.get("title") or "", spec.get("sub") or "", x=30, st=sty.figure(), eyebrow=spec.get("figure"))

    mids = edge_ids(messages)

    def text_of(m):
        lbl = m.get("label") or ""
        return f"[{m['proto'].upper()}] {lbl}" if m.get("proto") else lbl

    def label_w(i, m):
        return _label_w(paint.transformed(text_of(m), sty.edge(mids[i])["label"]), sty.edge(mids[i])["label"])

    # actor boxes share one size: the widest and tallest any actor's text needs
    sizes = [paint.box_size(a.get("name", a.get("id", "")), a.get("sub", ""), a.get("tag", ""), None, sty.node(a.get("id")))
             for a in actors]
    bw = max([s_[0] for s_ in sizes] or [140])
    sizes = {a["id"]: paint.box_size(a.get("name", a.get("id", "")), a.get("sub", ""), a.get("tag", ""), None,
                                     dict(sty.node(a.get("id")), computed={"width": bw})) for a in actors}
    hs = [sizes[a["id"]][1] for a in actors]
    http = _first(range(len(messages)), lambda i: str(messages[i].get("proto", "")).startswith("http"))
    focal_actor = _first(actors, lambda a: a.get("focal"))
    focal_msg = _first(range(len(messages)), lambda i: messages[i].get("focal"))
    hi = sty.node(focal_actor["id"])["stroke"] if focal_actor else (sty.edge(mids[focal_msg])["stroke"] if focal_msg is not None else None)
    sentence = _phrases(
        (any(not (m.get("reply") or m.get("async")) for m in messages), "solid = call"),
        (any(m.get("reply") or m.get("async") for m in messages), "dashed = reply or event"),
        (http is not None, f"{paint.color_word(sty.edge(mids[http])['stroke'])} = HTTP" if http is not None else ""),
        (hi is not None, f"{paint.color_word(hi)} = highlighted" if hi else ""))
    res = sequence.layout([{"id": a["id"], "w": bw, "h": h_} for a, h_ in zip(actors, hs)],
                          [{"from": m.get("from"), "to": m.get("to"), "label_w": label_w(i, m)} for i, m in enumerate(messages)],
                          {"top": max(MARGIN, head_h + 12), "margin": MARGIN, "pitch": bw + 48, "label_pad": 32, "box_h": MIN_ACTOR_H,
                           "gap": 32, "step": 44, "bottom": 0})
    pos = {a["id"]: (res.x[a["id"]], a) for a in actors}
    top, bh = res.top, res.box_h
    end = (res.y[-1] if messages else top + bh) + 24  # where the lifelines stop: just past the last message
    reach = [pos[m["from"]][0] + LOOP_W + GAP + label_w(i, m) for i, m in enumerate(messages)
             if m.get("from") == m.get("to") and m.get("from") in pos and m.get("label")]
    W = max([res.size[0], _min_width(spec, t, sty, sentence)] + [int(x + MARGIN + 0.999) for x in reach])
    H = end + (56 if sentence else MARGIN)
    W += 200 if _notes else 0
    extra = _bottom(t, sty, spec, W)
    H += extra
    dr = paint.Drawing(W, H, spec.get("title", "sequence"), spec.get("sub", spec.get("title", "sequence")),
                       kind="sequence diagram", legible=True)
    dr.add(paint.paper(t, W, H, sty.figure()["paper"]), paint.marker_defs(t), *head_els)
    # Lifelines
    for aid, (cx, a) in pos.items():
        dr.add(paint.el("line", owner=aid, role="actor.lifeline", x1=cx, y1=top + bh, x2=cx, y2=end, stroke=t["line"],
                        stroke_opacity=".6", stroke_width=1, stroke_dasharray="3,4"))
    # Messages
    for i, m in enumerate(messages):
        f_id = m.get("from")
        t_id = m.get("to")
        if f_id not in pos or t_id not in pos:
            continue
        x1, _ = pos[f_id]
        x2, _ = pos[t_id]
        my = res.y[i]
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
            lw = LOOP_W
            dr.add(paint.el("path", owner=owner, role="message.path", a11y=said,
                            d=f"M{x1},{my} L{x1 + lw},{my} L{x1 + lw},{my + 20} L{x1 + 4},{my + 20}",
                            fill="none", stroke=col, stroke_width=es["stroke-width"] * 1.5 / 1.6,  # a loop draws a touch finer
                            **{k.replace("-", "_"): v for k, v in look.items()}))
            if m.get("label"):
                dr.add(*paint.arrow_label(t, x1 + lw, my + 10, paint.transformed(m["label"], es["label"]), vertical=True,
                                          owner=owner, st=es["label"], pill=es["paper"], w=label_w(i, m), gap=GAP))
        else:
            direction = 1 if x2 >= x1 else -1
            x_from = x1 + direction * 1.5  # from the lifeline, the arrowhead's tip on the other one
            x_to = x2 - direction * 1
            dr.add(paint.el("line", owner=owner, role="message.path", a11y=said, x1=x_from, y1=my, x2=x_to, y2=my, stroke=col,
                            stroke_width=es["stroke-width"], **{k.replace("-", "_"): v for k, v in look.items()}))
            if m.get("label"):
                dr.add(*paint.arrow_label(t, (x1 + x2) / 2, my, paint.transformed(text_of(m), es["label"]), owner=owner,
                                          st=es["label"], pill=es["paper"], w=label_w(i, m), gap=GAP))
    _more_markers(dr, sty)
    # Actor boxes at top
    for aid, (cx, a) in pos.items():
        bx, by = cx - bw / 2, top
        dr.add(*paint.named(paint.node_box(t, bx, by, bw, bh, a.get("name", aid), a.get("sub", ""), a.get("tag", ""),
                                           a.get("focal", False), corners, aid, st=sty.node(aid), pad=sizes[aid][2]), "actor",
                            paint.node_name(a, aid)))
    if _notes:
        rail = []
        for nt in _notes:
            if nt.get("at") in pos:
                cx, _a = pos[nt["at"]]
                rail.append((cx + bw / 2, top + bh / 2, nt["text"]))
        dr.add(*paint.note_rail(t, rail, W - 186, top, st=sty.figure()["note"]))
    _legend(dr, t, sty, W, H, extra, LEGEND_RULE, LEGEND_TEXT, sentence, spec)
    _owned_opacity(dr, sty)
    _fonts(dr, sty, embed)
    return dr.svg(), W, H


LOOP_W, MIN_ACTOR_H = 32, 40  # how far a self-call's loop stands out; an actor box's least height


TABLE_W, ROW_H = 240, 24  # a table card's width and the pitch of its column rows (paint.table_card)


def render_schema(spec, corners="editorial", theme=None, sheets=(), embed=False, engine=None, info=None):
    """Draw tables and their relations: tables in columns left to right, each relation running from
    a column row of one table to a column row of the other, laid out once by the layered layout.
    Tables pinned with x and y keep their places, which the v1 path draws."""
    tables = spec.get("tables", [])
    if engine == "v1" or any(isinstance(tb, dict) and "x" in tb and "y" in tb for tb in tables):
        from .legacy import render_schema as v1
        return v1(spec, corners, theme, sheets, embed)
    t = theme or THEME
    sty = Styler(spec, "schema", t, corners, sheets)
    rx = corner_rx(corners)
    nodes, rows = [], {}
    for tb in tables:
        cols = tb.get("columns", [])
        h = 44 + len(cols) * ROW_H + 12
        nodes.append({"id": tb["id"], "name": tb.get("name", tb["id"]), "shape": "rect", "_w": TABLE_W, "_h": h, "tbl": tb,
                      **{k: tb[k] for k in ("rank", "order", "lane") if k in tb}})  # a column and a place in it, from edits
        rows[tb["id"]] = {c["name"]: 44 + k * ROW_H + ROW_H / 2 - h / 2 for k, c in enumerate(cols)}
    relations = spec.get("relations", [])
    rids = edge_ids(relations)
    pins = {i: (rows.get(r.get("from"), {}).get(r.get("from_col")), rows.get(r.get("to"), {}).get(r.get("to_col")))
            for i, r in enumerate(relations)}
    # the gap between columns fits the widest relation label
    widest = max((_label_w(paint.transformed(str(r["label"]), sty.edge(rids[i])["label"]), sty.edge(rids[i])["label"])
                  for i, r in enumerate(relations) if r.get("label")), default=0)
    options = {"direction": "LR", "back": "ports", "rank_gap": float(min(170, max(70, widest + 36)))}

    def card(nid, n, cx, cy):
        return paint.table_card(t, cx - n["_w"] / 2, cy - n["_h"] / 2, n["_w"], n["_h"], rx, nid, n["tbl"], ROW_H,
                                st=sty.table(nid))

    def attach(e, r):
        return {"from": {"node": e.get("from"), "port": e.get("from_col")}, "to": {"node": e.get("to"), "port": e.get("to_col")}}
    cols = [c for tb in tables for c in tb.get("columns", [])]
    focal_tbl = _first(tables, lambda tb: tb.get("focal"))
    focal_rel = _first(range(len(relations)), lambda i: relations[i].get("focal"))
    hi = sty.node(focal_tbl["id"])["stroke"] if focal_tbl else (sty.edge(rids[focal_rel])["stroke"] if focal_rel is not None else None)
    sentence = _phrases(
        (any(c.get("pk") for c in cols), "PK = primary key"),
        (any(c.get("fk") for c in cols), "FK = foreign key"),
        (bool(relations), f"{paint.color_word(sty.edge(rids[0])['stroke'])} = relation" if relations else ""),
        (hi is not None, f"{paint.color_word(hi)} = highlighted" if hi else ""))
    min_w = _min_width(spec, t, sty, sentence)
    dr, W, H, extra = _layered(spec, "schema", nodes, t, sty, corners, dict(options, min_width=min_w - 2 * MARGIN), min_w,
                               "database schema", edges=relations, pins=pins, paint_node=card, tails=False, attach=attach,
                               a11y_kind="relation", info=info, legend=bool(sentence))
    _legend(dr, t, sty, W, H, extra, LEGEND_RULE, LEGEND_TEXT, sentence, spec)
    return _as_svg((dr, W, H), sty, embed)

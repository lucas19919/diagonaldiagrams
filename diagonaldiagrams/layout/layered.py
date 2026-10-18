"""The layered layout (DESIGN 7.2, PLAN P4.2): flowcharts, architecture, state machines, DAGs.

    result = layout(nodes, edges, groups, options)

- nodes: [{"id", "w", "h", "shape"?, "rank"?, "lane"?, "order"?}]. rank pins a layer; lane and order
  keep a relative order within one.
- edges: [{"id", "from", "to", "from_at"?, "to_at"?}]. from_at and to_at pin an end on the top or
  bottom side (left or right across): its offset along the side from the node's middle, as a
  table's column row is (schema).
- groups: [{"id", "members": [node ids], "parent"?}].
- options: DEFAULTS, plus "same_rank": [[node ids that share a layer]] (from edits), "prev" ({node
  id: x} from the drawing before an edit, so the rest stays put), "aspect", "flat_room" and
  "min_width". Sizes are in pixels, direction TB (top to bottom), LR, BT or RL.
- options for pinned nodes (DESIGN 4.6), read in TB only: "pins" ({node id: x} in prev's frame: the
  node's middle stands there), "wall" (in prev's frame, the least x a box's left edge may take before
  the first cut: the canvas's margin), "anchor" ({node id: x on the canvas}: where the renderer puts
  the pinned nodes, which sets the canvas's edges), "row_y" ({node id: y}: its layer's middle stands
  at least that low, as Result.bands gives it) and "cuts" (the layers to wrap after, as Result.cuts
  gives them; [] for none).

The steps: break cycles (back_edges), rank (ranks), add a dummy wherever an arrow passes a layer and
a left and a right border wherever a group spans one (Layering), order the layers for few crossings
(order), place them across (bk.coordinates), then route: every arrow leaves and enters at ports
spread along a side, runs straight through its dummies, and turns in the gaps between layers on a
track of its own (channels). The gaps are made as tall as their tracks need, so nothing is moved
afterwards and nothing is drawn twice: the layout is right by construction, with no repair loop.

Arrows that go back up (B19, B23) leave and enter on the side and climb through their own dummies;
arrows within a layer run straight between neighbors or over the top. Groups are frames that hold
their members and nothing else (B20).
"""
from . import bk, channels, order as ordering
from .order import Layering
from .rank import back_edges, ranks

DEFAULTS = {
    "direction": "TB",
    "node_gap": 40.0,      # between two nodes in a layer
    "edge_gap": 18.0,      # between two arrows passing a layer
    "side_gap": 32.0,      # between a node and an arrow passing it
    "rank_gap": 64.0,      # least space between two layers
    "track": 14.0,         # between two tracks in a gap
    "stub": 16.0,          # an arrow's straight start before its first turn
    "group_pad": 16.0,     # inside a frame, around its members
    "group_head": 24.0,    # a frame's title band
    "group_gap": 24.0,     # outside a frame
    "slot": 22.0,          # most space between two ports on one side
    "trunk": False,        # arrows leaving one side share one port and split in the gap (flow)
    "simplex": True,
    "loop": 22.0,          # how far a self-loop stands out
    "back": "side",        # arrows going back up: "side" loops (flow) or "ports", top to bottom (arch)
    "wrap_layers": 12,     # fewer layers than this never wrap
    "balance": False,      # center each node over what it calls, after Brandes-Köpf (arch)
    "straight": False,     # the main path runs straight down: each node over its longest branch (flow)
}
_FLIP = {"n": "w", "s": "e", "w": "n", "e": "s"}


class Route:
    __slots__ = ("id", "points", "sides", "back", "flat", "nodes")

    def __init__(self, eid, points, sides, back=False, flat=False, nodes=None):
        self.id, self.points, self.sides, self.back, self.flat, self.nodes = eid, points, sides, back, flat, nodes

    def to_dict(self):
        return {"id": self.id, "points": [[round(x, 2), round(y, 2)] for x, y in self.points], "sides": list(self.sides)}


class Result:
    __slots__ = ("pos", "size", "routes", "frames", "layers", "crossings", "issues", "rank", "wrapped", "blocked",
                 "bands", "cuts", "flat")

    def __init__(self):
        self.pos, self.size, self.routes, self.frames = {}, (0.0, 0.0), {}, {}
        self.layers, self.crossings, self.issues, self.rank = [], 0, [], {}
        self.wrapped = False
        self.blocked = {}  # pinned node -> what kept it from its x ("pin", "edge", "layout"; bk.hold)
        self.bands = []  # each layer's middle y, before wrap and before the frame is moved to the canvas
        self.flat = {}  # each node's x, before wrap and label room and before the frame is moved
        self.cuts = []  # the layers wrap cut after


def _shape(n):
    sh = n.get("shape") or "rect"
    return sh if sh in ("diamond", "dot") else "box"


def layout(nodes, edges, groups=(), options=None):
    o = dict(DEFAULTS, **(options or {}))
    direction = str(o["direction"]).upper()
    across = direction in ("LR", "RL")
    res = Result()
    if not nodes:
        return res
    info = {}
    for k, n in enumerate(nodes):
        w, h = float(n["w"]), float(n["h"])
        if across:
            w, h = h, w
        info[n["id"]] = {"w": w, "h": h, "shape": _shape(n), "k": k, "node": n}
    ids = [n["id"] for n in nodes]
    E = [e for e in edges if e.get("from") in info and e.get("to") in info]
    loops = [e for e in E if e["from"] == e["to"]]
    E = [e for e in E if e["from"] != e["to"]]

    # groups: innermost group of each node, the tree, and what each group holds
    gparent, gof = {}, {}
    for g in groups or ():
        gparent[g["id"]] = g.get("parent") if g.get("parent") in {x["id"] for x in groups} else None
    for g in groups or ():
        for m in g.get("members") or ():
            if m in info and m not in gof:
                gof[m] = g["id"]

    def chain(g):
        out = []
        while g is not None:
            out.append(g)
            g = gparent.get(g)
        return out  # innermost first

    # 1. ranks. A same-rank group (from an edit) shares the rank of its pinned member if it has one;
    # else it is one node while ranks are worked out, as Graphviz's rank=same is
    fixed = {}
    for n in nodes:
        r = n.get("rank")
        if isinstance(r, (int, float)) and not isinstance(r, bool):
            fixed[n["id"]] = r
    head = {}

    def find(i):
        while head.get(i, i) != i:
            i = head[i]
        return i
    for grp in o.get("same_rank") or ():
        grp = [i for i in grp if i in info]
        r = next((fixed[i] for i in grp if i in fixed), None)
        for i in grp[1:]:
            if r is not None:
                fixed[i] = fixed.setdefault(grp[0], r)
            elif find(i) != find(grp[0]):
                head[find(i)] = find(grp[0])
    if fixed and len(fixed) == len(ids):
        rank = ranks(ids, [], fixed)
    else:
        heads = [i for i in ids if find(i) == i]
        live = [(u, v) for u, v in ((find(e["from"]), find(e["to"])) for e in E) if u != v]
        back = back_edges(heads, live)
        oriented = [((v, u) if k in back else (u, v)) + (1, 1) for k, (u, v) in enumerate(live)]
        merged = ranks(heads, oriented, {find(i): r for i, r in fixed.items()}, simplex=o["simplex"])
        rank = {i: merged[find(i)] for i in ids}
    res.rank = rank
    nl = max(rank.values()) + 1

    # 2. the layering: nodes, dummies, group borders
    L = Layering()
    for nid in sorted(ids, key=lambda i: (rank[i], info[i]["k"])):
        L.add(nid, rank[nid], "node", gof.get(nid))
        hint = info[nid]["node"].get("lane")
        if hint is None:
            hint = info[nid]["node"].get("order")
        if isinstance(hint, (int, float)) and not isinstance(hint, bool):
            L.hint[nid] = float(hint)
    span = {}
    for nid in ids:
        for g in chain(gof.get(nid)):
            lo, hi = span.get(g, (rank[nid], rank[nid]))
            span[g] = (min(lo, rank[nid]), max(hi, rank[nid]))
    first_k = {}
    for nid in ids:
        for g in chain(gof.get(nid)):
            first_k.setdefault(g, info[nid]["k"])
    forced_up = {}
    for g in sorted(span, key=lambda g: first_k[g]):
        L.parent[g] = gparent.get(g)
        L.span[g] = span[g]
        L.rank[g] = first_k[g]
        lo, hi = span[g]
        for r in range(lo, hi + 1):
            L.add(("L", g, r), r, "left", g)
            L.add(("R", g, r), r, "right", g)
            if r > lo:
                L.link(("L", g, r - 1), ("L", g, r))
                L.link(("R", g, r - 1), ("R", g, r))
                forced_up[("L", g, r)] = ("L", g, r - 1)
                forced_up[("R", g, r)] = ("R", g, r - 1)

    def lca(a, b):
        ca = chain(gof.get(a))
        cb = set(chain(gof.get(b)))
        return next((g for g in ca if g in cb), None)

    kinds = []  # per edge: ("down"|"back"|"flat", top node, bottom node, [dummies top to bottom])
    for e in E:
        a, b = e["from"], e["to"]
        if rank[a] == rank[b]:
            kinds.append(("flat", a, b, []))
            continue
        top, bot = (a, b) if rank[a] < rank[b] else (b, a)
        owner = lca(a, b)
        ds = []
        for r in range(rank[top] + 1, rank[bot]):
            d = ("D", e["id"], r)
            L.add(d, r, "dummy", owner)
            ds.append(d)
        if top == a or o["back"] == "ports":
            seq = [top] + ds + [bot]
        else:  # a back edge leaves and arrives beside its nodes: a port item at each end
            pin, pout = ("P", e["id"], "in"), ("P", e["id"], "out")
            L.add(pin, rank[top], "port", gof.get(top))
            L.add(pout, rank[bot], "port", gof.get(bot))
            L.attach[pin], L.attach[pout] = top, bot
            seq = [pin] + ds + [pout]
        for x, y in zip(seq, seq[1:]):
            L.link(x, y)
        kinds.append(("down" if top == a else "back", top, bot, ds))

    # 3. order: start from the spec's order, dummies under the node they hang from
    key = {}
    for nid in ids:
        key[nid] = float(info[nid]["k"])
    for kind, top, bot, ds in kinds:
        for d in ds:
            key[d] = key[top] + 0.5
    for pt, nid in L.attach.items():
        key[pt] = key[nid] + 0.25
    for r in range(len(L.layers)):
        ordering._sort_layer(L, r, key, {it: [it] for it in L.layers[r]})
    res.crossings = ordering.order(L)

    # 4. across: separations, then Brandes-Köpf
    flat_room = o.get("flat_room") or {}
    width = {}
    loop_nodes = {e["from"] for e in loops}
    for it in L.kind:
        k = L.kind[it]
        if k == "node":
            extra = (2 * o["loop"] + 2 * flat_room.get((it, it), 0.0)) if it in loop_nodes else 0.0
            width[it] = info[it]["w"] + extra
        else:
            width[it] = 0.0

    def gap(a, b):
        ka, kb = L.kind[a], L.kind[b]
        # layers are sorted as a tree: after a frame's left border comes its contents or its right border
        if ka == "left":
            return 2 * o["group_pad"] if kb == "right" and L.owner[b] == L.owner[a] else o["group_pad"]
        if kb == "right":
            return o["group_pad"]
        if ka == "right" or kb == "left":
            return o["group_gap"]  # outside a frame
        if ka == "port" and kb == "node" and L.attach[a] == b or kb == "port" and ka == "node" and L.attach[b] == a:
            return o["stub"]  # a back edge's turn, just beside its node
        if ka == "port" and kb == "port" and L.attach[a] == L.attach[b]:
            return o["track"]
        lines = ("dummy", "port")
        if ka in lines and kb in lines:
            return o["edge_gap"]
        if ka in lines or kb in lines:
            return o["side_gap"]
        room = max(flat_room.get((a, b), 0.0), flat_room.get((b, a), 0.0))  # a labelled arrow between them
        return max(o["node_gap"], room)

    # a decision's branches stand beyond its side vertices, so each can leave by one
    spread = {}
    for nid in ids:
        if info[nid]["shape"] == "diamond":
            kids = [w for w in dict.fromkeys(L.down.get(nid, ())) if L.kind.get(w) in ("node", "dummy")]
            for i in range(len(kids)):
                for j in range(i + 1, len(kids)):
                    key = frozenset((kids[i], kids[j]))
                    spread[key] = max(spread.get(key, 0.0), info[nid]["w"] + o["node_gap"])

    # a labelled arrow within a layer whose ends have frame borders or other arrows' lines between
    # them (a back edge's port item, a long arrow's dummy): the room it needs goes on one pair of the
    # items between, on top of their own gaps
    extra = {}
    for (a, b), room in flat_room.items():
        if a not in L.layer_of or b not in L.layer_of or L.layer_of[a] != L.layer_of[b]:
            continue
        layer = L.layers[L.layer_of[a]]
        i, j = sorted((layer.index(a), layer.index(b)))
        mid = layer[i:j + 1]
        if j - i < 2 or any(L.kind[x] not in ("left", "right", "port", "dummy") for x in mid[1:-1]):
            continue
        # the label sits between two borders, never across one: the widest stretch between borders
        # alone must hold it. It may cross a line: a back edge's climb stops short of the arrow on one
        # side, so the label sits on the other, and a long arrow passes under the label's pill
        stretches = [[]]
        for xy in zip(mid, mid[1:]):
            stretches[-1].append(xy)
            if L.kind[xy[1]] in ("left", "right"):
                stretches.append([])
        widest = max((s for s in stretches if s), key=lambda s: sum(gap(*xy) for xy in s))
        have = sum(gap(*xy) for xy in widest)
        key = max(widest, key=lambda xy: gap(*xy))
        if room > have:
            extra[key] = max(extra.get(key, 0.0), room - have)

    def sep(a, b):
        return max(width[a] / 2.0 + width[b] / 2.0 + gap(a, b) + extra.get((a, b), 0.0),
                   spread.get(frozenset((a, b)), 0.0))

    def inner(u, v):
        ku, kv = L.kind[u], L.kind[v]
        lines = ("dummy", "port")
        return (ku in lines and kv in lines) or (ku in ("left", "right") and kv == ku and L.owner[u] == L.owner[v])
    straight = None
    if o.get("straight"):  # flow: each node over the child that continues its longest path (bk.spine)
        climb = set(L.attach) | {d for kind, top, bot, ds in kinds if kind == "back" for d in ds}
        straight = bk.spine(L.layers, [(top, ds, bot) for kind, top, bot, ds in kinds if kind == "down"], L.up,
                            lambda u, v: inner(u, v) and u not in climb and v not in climb, forced_up)
    prev = o.get("prev") if direction == "TB" else None  # an earlier drawing's x per node: stay near it
    xs = bk.coordinates(L.layers, L.up, L.down, width, sep, L.kind, inner, forced_up,
                        {k: float(v) for k, v in prev.items() if k in info} if prev else None, straight)
    if o.get("balance"):  # arch: each node over what it calls (bk.balance)
        xs = bk.balance(L.layers, L.up, L.down, L.kind, xs, sep)
    # 4b. pinned nodes go to their x, pushing what stands in their way (DESIGN 4.6); after the
    # balance, so a pin's x holds exactly
    pins = {k: float(v) for k, v in (o.get("pins") or {}).items() if k in info} if direction == "TB" else {}
    if pins:
        targets, walls = _pin_targets(pins, prev or {}, xs, ids, o.get("wall"), o.get("cuts") or [], nl)
        lines = [(u, v) for u in L.kind if L.kind[u] in ("dummy", "port")
                 for v in L.down[u] if L.kind[v] in ("dummy", "port")]  # an arrow's items, which a push keeps in line
        xs, res.blocked = bk.hold(L.layers, xs, sep, width, forced_up, targets, walls, lines)
    res.flat = {i: xs[i] for i in ids}
    # 5. ports, routes and the gaps' tracks
    order_of = {it: k for layer in L.layers for k, it in enumerate(layer)}
    band_h = [max((info[it]["h"] for it in layer if L.kind[it] == "node"), default=0.0) for layer in L.layers]
    plan = _Plan(o, info, xs, rank, L, order_of)
    for (kind, top, bot, ds), e in zip(kinds, E):
        plan.edge(e, kind, top, bot, ds)
    for e in loops:
        plan.loop(e)
    plan.ports()
    tracks = plan.tracks(nl)

    # 6. heights: a gap is as tall as its tracks and the frames' bands around it need
    head_at, pad_at = _frame_depths(span, gparent)
    low = {}  # a layer whose middle must stand at least this low (row_y): the gap above it grows
    for i, v in (o.get("row_y") or {}).items():
        if i in rank:
            low[rank[i]] = max(low.get(rank[i], v), float(v))
    y, band_top = 0.0, []
    gap_h = {}
    for g in range(-1, nl):
        n = tracks.get(g, 0)
        pads = pad_at.get(g, 0) * o["group_pad"]
        heads = head_at.get(g + 1, 0) * o["group_head"]
        if g in (-1, nl - 1):
            mid = (n + 1) * o["track"] + o["stub"] if n else 0.0
        else:
            mid = max(o["rank_gap"], (n + 1) * o["track"] + 2 * o["stub"] if n else 0.0)
        if g + 1 in low:
            mid += max(0.0, low[g + 1] - (y + pads + mid + heads + band_h[g + 1] / 2.0))
        gap_h[g] = (pads, mid, heads)
        y += pads + mid + heads
        if g + 1 < nl:
            band_top.append(y)
            y += band_h[g + 1]
    H = y
    res.layers = [list(x) for x in L.layers]
    cy = {r: band_top[r] + band_h[r] / 2.0 for r in range(nl)}
    res.bands = [cy[r] for r in range(nl)]
    track_y = {}
    for g in range(-1, nl):
        pads, mid, heads = gap_h[g]
        start = (band_top[g] + band_h[g]) if g >= 0 else 0.0
        n = tracks.get(g, 0)
        top = start + pads
        for t in range(n):
            track_y[(g, t)] = top + mid / 2.0 + (t - (n - 1) / 2.0) * o["track"]
    for nid in ids:
        res.pos[nid] = (xs[nid], cy[rank[nid]])
    for g, (lo, hi) in span.items():
        x0 = min(xs[("L", g, r)] for r in range(lo, hi + 1))
        x1 = max(xs[("R", g, r)] for r in range(lo, hi + 1))
        y0 = band_top[lo] - _depth(g, lo, span, gparent, "head") * o["group_head"]
        y1 = band_top[hi] + band_h[hi] + _depth(g, hi, span, gparent, "pad") * o["group_pad"]
        res.frames[g] = (x0, y0, x1, y1)
    for r in plan.build(res.pos, band_top, band_h, track_y):
        res.routes[r.id] = r

    # 6b. a tall strip folds into columns near the target aspect (wrap.py)
    if o.get("aspect"):
        from .wrap import wrap
        target = float(o["aspect"])
        res.cuts = wrap(res.pos, rank, info, res.frames, span, res.routes, band_top, band_h,
                        {r: n * o["group_pad"] for r, n in pad_at.items()},
                        {r: n * o["group_head"] for r, n in head_at.items()}, o, 1.0 / target if across else target,
                        min_width=o.get("min_width", 0.0), cuts=o.get("cuts"))
    wrapped = res.wrapped = bool(res.cuts)

    # 6c. a label with no clear spot beside its arrow gets a strip of room there (room.py)
    room_x = []
    if o.get("labels") and direction == "TB":
        from .room import make_room
        reach = {i: info[i]["w"] / 2.0 + o["loop"] + flat_room[(i, i)] for i in loop_nodes if (i, i) in flat_room}
        left = None
        anchor = {k: float(v) for k, v in (o.get("anchor") or {}).items() if k in res.pos}
        if anchor:  # a pinned figure's canvas begins where its pins put it, as the renderer will place it
            keep = [p for p in anchor if p not in res.blocked] or list(anchor)
            left = sum(res.pos[p][0] - anchor[p] for p in keep) / len(keep)
        room_x = make_room(res.pos, info, res.frames, res.routes, o["labels"], reach, o.get("min_width", 0.0),
                           o.get("margin", 0.0), left)

    # 7. into the canvas's frame of reference, and turned for LR, BT, RL
    pts = [p for r in res.routes.values() for p in r.points]
    boxes = [(x - info[i]["w"] / 2, y - info[i]["h"] / 2, x + info[i]["w"] / 2, y + info[i]["h"] / 2)
             for i, (x, y) in res.pos.items()]
    boxes += list(res.frames.values())
    extra_x = [res.pos[i][0] + info[i]["w"] / 2.0 + o["loop"] + flat_room[(i, i)]
               for i in loop_nodes if (i, i) in flat_room and i in res.pos]
    x_lo = min([b[0] for b in boxes] + [p[0] for p in pts] + room_x)
    x_hi = max([b[2] for b in boxes] + [p[0] for p in pts] + extra_x + room_x)
    y_lo = min([b[1] for b in boxes] + [p[1] for p in pts] + [0.0])
    y_hi = max([b[3] for b in boxes] + [p[1] for p in pts] + ([] if wrapped else [H]))

    def tf(x, y):
        x, y = x - x_lo, y - y_lo
        if direction == "BT":
            y = (y_hi - y_lo) - y
        elif across:
            x, y = y, x
        return x, y
    res.pos = {i: tf(*p) for i, p in res.pos.items()}
    res.frames = {g: _tbox(tf, b) for g, b in res.frames.items()}
    for r in res.routes.values():
        r.points = [tf(*p) for p in r.points]
        r.sides = tuple(_turn(s, direction) for s in r.sides)
    w, h = x_hi - x_lo, y_hi - y_lo
    res.size = (h, w) if across else (w, h)
    if direction == "RL":
        W = res.size[0]
        res.pos = {i: (W - x, y) for i, (x, y) in res.pos.items()}
        res.frames = {g: (W - b[2], b[1], W - b[0], b[3]) for g, b in res.frames.items()}
        for r in res.routes.values():
            r.points = [(W - x, y) for x, y in r.points]
            r.sides = tuple({"e": "w", "w": "e"}.get(s, s) for s in r.sides)
    return res


def _pin_targets(pins, prev, xs, ids, wall, cuts, nl):
    """([(node, x)], walls) for bk.hold: each pin in BK's frame. prev's frame is read off the other
    boxes, which keep their earlier places as nearly as BK allows (one shift for them all); with no
    earlier places at all, BK's frame is the pins' own. walls: per layer, the wall in BK's frame for
    the layers before the first cut (wrap sets the later columns right of them), else None."""
    seen = [float(prev[i]) - xs[i] for i in ids if i not in pins and i in prev]
    shift = sum(seen) / len(seen) if seen else 0.0  # BK's x + shift: prev's frame
    out = [(p, pins[p] - shift) for p in ids if p in pins]
    first = min(cuts) if cuts else nl
    walls = [wall - shift if wall is not None and seen and r <= first else None for r in range(nl)]
    return out, walls


def _turn(side, direction):
    if direction in ("LR", "RL"):
        return _FLIP[side]
    if direction == "BT":
        return {"n": "s", "s": "n"}.get(side, side)
    return side


def _tbox(tf, b):
    a, c = tf(b[0], b[1]), tf(b[2], b[3])
    return (min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1]))


def _depth(g, r, span, parent, what):
    """How many frames, g and the ones inside it, start (head) or end (pad) at layer r along g's
    deepest chain: g's band sits that many bands out."""
    kids = [c for c, p in parent.items() if p == g and c in span]
    at = 0 if what == "head" else 1
    deeper = [_depth(c, r, span, parent, what) for c in kids if span[c][at] == r]
    return 1 + max(deeper, default=0)


def _frame_depths(span, parent):
    """gap -> how many title bands sit at its bottom (frames starting at the layer below), and how many
    paddings at its top (frames ending at the layer above)."""
    head, pad = {}, {}
    for g, (lo, hi) in span.items():
        head[lo - 1] = max(head.get(lo - 1, 0), _depth(g, lo, span, parent, "head"))
        pad[hi] = max(pad.get(hi, 0), _depth(g, hi, span, parent, "pad"))
    return {k + 1: v for k, v in head.items()}, pad


class _Plan:
    """Ports and routes in the top-to-bottom frame: what each arrow does, then where."""

    def __init__(self, o, info, xs, rank, L, order_of):
        self.o, self.info, self.xs, self.rank, self.L, self.order_of = o, info, xs, rank, L, order_of
        self.items = []  # (edge, kind, [(node, side, role, key)], spec)
        self.slots = {}  # (node, side) -> [(edge id, role, key)]
        self.offset = {}  # (edge id, role) -> offset along the side
        self.stub = {}  # (edge id, role) -> how far a side port's arrow runs out before it turns
        self.peer = {}  # (edge id, role) -> ("x", fixed x of the next point) or ("node", the other end)
        self.runs = {}  # gap -> [Run]
        self.paths = []
        self.pins = {}  # (edge id, role) -> offset an end keeps on its side (edge from_at, to_at)

    def _x(self, it):
        return self.xs[it]

    def _side_port(self, nid, toward_x):
        return "w" if toward_x < self._x(nid) else "e"

    def _down_side(self, nid, nxt_x):
        """The side a downward arrow leaves by: the bottom, or a decision's side vertex when its
        next point lies clearly to that side."""
        inf = self.info[nid]
        if inf["shape"] == "diamond":
            dx = nxt_x - self._x(nid)
            if abs(dx) > inf["w"] / 2.0:  # beyond the vertex: leave by it
                return "w" if dx < 0 else "e"
        return "s"

    def edge(self, e, kind, top, bot, ds):
        eid = e["id"]
        for role, key in (("out", "from_at"), ("in", "to_at")):
            if isinstance(e.get(key), (int, float)) and not isinstance(e.get(key), bool):
                self.pins[(eid, role)] = float(e[key])
        if kind == "flat":
            a, b = e["from"], e["to"]
            between = [it for it in self.L.layers[self.rank[a]]
                       if self.L.kind[it] == "node" and min(self.order_of[a], self.order_of[b]) < self.order_of[it]
                       < max(self.order_of[a], self.order_of[b])]
            if not between:
                s1 = "e" if self._x(b) > self._x(a) else "w"
                s2 = "w" if s1 == "e" else "e"
                self._slot(a, s1, eid, "out", 0.0)
                self._slot(b, s2, eid, "in", 0.0)
                self.paths.append((eid, "flat", a, b, [], (s1, s2)))
            else:
                self._slot(a, "n", eid, "out", self._x(b))
                self._slot(b, "n", eid, "in", self._x(a))
                self.paths.append((eid, "over", a, b, [], ("n", "n")))
            return
        if kind == "down":
            nxt = self._x(ds[0]) if ds else self._x(bot)
            prv = self._x(ds[-1]) if ds else self._x(top)
            s1 = self._down_side(top, nxt)
            self._slot(top, s1, eid, "out", nxt if s1 in ("n", "s") else 1000.0 + abs(nxt - self._x(top)))
            self._slot(bot, "n", eid, "in", prv)
            self.peer[(eid, "out")] = ("x", nxt) if ds else ("node", bot)
            self.peer[(eid, "in")] = ("x", prv) if ds else ("node", top)
            self.paths.append((eid, "down", top, bot, ds, (s1, "n")))
            return
        if self.o["back"] == "ports":  # out the top of the lower node, into the bottom of the upper one
            nxt = self._x(ds[-1]) if ds else self._x(top)
            prv = self._x(ds[0]) if ds else self._x(bot)
            self._slot(bot, "n", eid, "out", nxt)
            self._slot(top, "s", eid, "in", prv)
            self.peer[(eid, "out")] = ("x", nxt) if ds else ("node", top)
            self.peer[(eid, "in")] = ("x", prv) if ds else ("node", bot)
            self.paths.append((eid, "rise", bot, top, ds, ("n", "s")))
            return
        # back: the arrow leaves the lower node (bot) beside it, climbs, and arrives beside the upper one
        pout, pin = ("P", eid, "out"), ("P", eid, "in")
        s1 = self._side_port(bot, self._x(pout))
        s2 = self._side_port(top, self._x(pin))
        # the key says where on the side an arrow goes (ports() reads its range) and, within that, in
        # what order; the distance is capped so a port item far out on a wide figure stays in its range
        self._slot(bot, s1, eid, "out", -2000.0 + min(999.0, abs(self._x(pout) - self._x(bot))))  # climbs: the top of the side
        self._slot(top, s2, eid, "in", 2000.0 - min(999.0, abs(self._x(pin) - self._x(top))))  # arrives from below: the bottom
        self.paths.append((eid, "back", bot, top, ds, (s1, s2)))

    def _center(self):
        xs = [self.xs[n] for n in self.info]
        return (min(xs) + max(xs)) / 2.0

    def loop(self, e):
        self.paths.append((e["id"], "loop", e["from"], e["from"], [], ("e", "e")))

    def _slot(self, nid, side, eid, role, key):
        self.slots.setdefault((nid, side), []).append((eid, role, key))

    def ports(self):
        """Spreads the arrows on each side: sorted by where they go, outs and ins apart, a trunk when
        every arrow on a side goes the same way (o["trunk"]), a lone port leaning toward its far end."""
        o = self.o
        lone = []
        for (nid, side), items in self.slots.items():
            inf = self.info[nid]
            along = inf["w"] if side in ("n", "s") else inf["h"]
            if inf["shape"] == "dot":
                lim = 4.0 if side in ("w", "e") and len(items) > 1 else 0.0  # its side arrows apart, just
            elif inf["shape"] == "diamond":
                lim = 10.0
            else:
                lim = max(0.0, along / 2.0 - 10.0)
            outs = sorted((it for it in items if it[1] == "out"), key=lambda t: t[2])
            ins = sorted((it for it in items if it[1] == "in"), key=lambda t: t[2])
            if side in ("w", "e"):  # climbing arrows on top, arriving ones at the bottom
                group = sorted(items, key=lambda t: t[2])
                flats = sorted((t for t in group if -500 < t[2] < 500), key=lambda t: str(t[0]))
                if flats and lim:  # arrows within a layer at the middle, so both their ends are level
                    half = 4.0 * (len(flats) - 1)
                    for (eid, role, _), v in zip(flats, _slots(len(flats), -half, half, 8.0)):
                        self.offset[(eid, role)] = v
                    ups = [t for t in group if t[2] <= -500]
                    downs = [t for t in group if t[2] >= 500]
                    reach = inf["h"] / 2.0 - 4.0  # still on the side
                    for seq, lo, hi in ((ups, -lim, -half - 10.0), (downs, half + 10.0, lim)):
                        need = 8.0 * (len(seq) - 1)
                        if inf["shape"] != "dot" and hi - lo < need:  # no room past the middle ones: further along
                            lo, hi = (max(-reach, hi - need), hi) if hi < 0 else (lo, min(reach, lo + need))
                        for (eid, role, _), v in zip(seq, _slots(len(seq), lo, hi, o["slot"]) if seq else []):
                            self.offset[(eid, role)] = v
                else:
                    vals = _slots(len(group), -lim, lim, o["slot"]) if lim else [0.0] * len(group)
                    for (eid, role, _), v in zip(group, vals):
                        self.offset[(eid, role)] = v
                # each one turns at its own distance from the side: the innermost turn goes to the
                # arrow that runs up from the top, or down (or in) from the bottom, so none cross
                ups = [t for t in group if t[2] < -1000]
                downs = [t for t in reversed(group) if t[2] > 500]
                for seq in (ups, downs):
                    for k, (eid, role, _) in enumerate(seq):
                        self.stub[(eid, role)] = o["stub"] + k * o["track"]
                continue
            if lim == 0.0 or (o["trunk"] and inf["shape"] == "box" and len(items) >= 2 and len({it[1] for it in items}) == 1):
                for eid, role, _ in items:
                    self.offset[(eid, role)] = 0.0
                continue
            if inf["shape"] == "diamond":
                group = outs + ins
                for (eid, role, _), v in zip(group, _slots(len(group), -lim, lim, o["slot"])):
                    self.offset[(eid, role)] = v
                continue
            if len(items) == 1:
                lone.append((nid, side, items[0], lim))
                continue
            if outs and ins:
                mo = sum(t[2] for t in outs) / len(outs)
                mi = sum(t[2] for t in ins) / len(ins)
                # a tie (two boxes calling each other) is broken by the arrows' ids, the same at both ends
                key_o = (round(mo, 3), min(str(t[0]) for t in outs))
                key_i = (round(mi, 3), min(str(t[0]) for t in ins))
                left, right = (outs, ins) if key_o <= key_i else (ins, outs)
                # packed from the middle out, so two boxes of different widths stacked on one center
                # put their ends at the same x and the arrows between them run straight
                for (eid, role, _), v in zip(left, [-x for x in reversed(_inward(len(left), 12.0, lim, o["slot"]))]):
                    self.offset[(eid, role)] = v
                for (eid, role, _), v in zip(right, _inward(len(right), 12.0, lim, o["slot"])):
                    self.offset[(eid, role)] = v
            else:
                group = outs + ins
                for (eid, role, _), v in zip(group, _slots(len(group), -lim, lim, o["slot"])):
                    self.offset[(eid, role)] = v

        self._lone(lone)
        for nid, inf in self.info.items():  # a dot used from both sides: its two sides' arrows not in line
            if inf["shape"] == "dot" and (nid, "w") in self.slots and (nid, "e") in self.slots:
                for side, dy in (("w", -3.0), ("e", 3.0)):
                    for eid, role, _ in self.slots[(nid, side)]:
                        self.offset[(eid, role)] = max(-4.0, min(4.0, self.offset.get((eid, role), 0.0) + dy))
        for (nid, side), items in self.slots.items():  # a pinned end stays where it was put
            if side in ("n", "s"):
                for eid, role, _ in items:
                    if (eid, role) in self.pins:
                        self.offset[(eid, role)] = self.pins[(eid, role)]

    def _lone(self, lone):
        """A side with one arrow: in line with its next point when that falls within the side, so
        the arrow runs straight; else leaning toward its far end, so an exit and an entry stacked in
        one column never land on the same x. Two lone ends of one arrow meet at a shared x."""
        at = {(nid, side): (it, lim) for nid, side, it, lim in lone}
        for nid, side, (eid, role, k), lim in lone:
            if (eid, role) in self.offset:
                continue
            cx = self._x(nid)
            peer = self.peer.get((eid, role))
            want = None
            if peer and peer[0] == "x":
                want = peer[1]
            elif peer and peer[0] == "node":
                other = peer[1]
                oside = "n" if role == "out" else "s"
                if self.info[other]["shape"] == "diamond" or side not in ("n", "s"):
                    oside = None
                hit = at.get((other, oside)) if oside else None
                if hit and hit[0][0] == eid:  # both ends alone: meet in the overlap of the two sides
                    ox, olim = self._x(other), hit[1]
                    lo, hi = max(cx - lim, ox - olim), min(cx + lim, ox + olim)
                    if lo <= hi:
                        x = min(max((cx + ox) / 2.0, lo), hi)
                        self.offset[(eid, role)] = x - cx
                        self.offset[(eid, "in" if role == "out" else "out")] = x - ox
                        continue
                want = self._x(other)
            dx = (want if want is not None else k) - cx
            if abs(dx) <= lim and peer and peer[0] == "x":
                self.offset[(eid, role)] = dx
            else:
                self.offset[(eid, role)] = 0.0 if abs(dx) < 30 else (12.0 if dx > 0 else -12.0)

    def port(self, nid, side, eid, role):
        """(x, y) of an arrow's end on a side, before the layers have their heights: y is relative to
        the node's center."""
        inf = self.info[nid]
        x = self._x(nid)
        off = self.offset.get((eid, role), 0.0)
        hw, hh = inf["w"] / 2.0, inf["h"] / 2.0
        if inf["shape"] == "dot":
            if side in ("w", "e"):
                return x + (hw if side == "e" else -hw), off
            return x, {"n": -hh, "s": hh}.get(side, 0.0)
        if inf["shape"] == "diamond":
            if side in ("n", "s"):
                dy = hh - abs(off) * hh / hw
                return x + off, (-dy if side == "n" else dy)
            dx = hw - abs(off) * hw / hh
            return x + (dx if side == "e" else -dx), off
        if side == "n":
            return x + off, -hh
        if side == "s":
            return x + off, hh
        return x + (hw if side == "e" else -hw), off

    def tracks(self, nl):
        """Builds every arrow's runs in the gaps and gives them tracks. Returns {gap: track count}."""
        self._legs()
        while self.crowded and self._bottom():
            self._legs()
        for k in range(4):
            if k:
                self._legs()
            if not self._separate():
                break
        self._doglegs()
        out = {}
        for g, runs in self.runs.items():
            out[g] = channels.assign(runs, self.o["track"])
        return out

    def _bottom(self):
        """A decision side whose exits step out so far that one turns down inside the box beside it
        (three exits on one side, a box node_gap away): its exit with the nearest target leaves by the
        bottom vertex instead, and the ports are spread again. Returns True when one moved."""
        moved = False
        for nid, side in dict.fromkeys(self.crowded):
            exits = [t for t in self.slots.get((nid, side), ()) if t[1] == "out" and t[2] >= 1000]
            if not exits:
                continue
            eid, role, key = min(exits, key=lambda t: (t[2], str(t[0])))
            self.slots[(nid, side)].remove((eid, role, key))
            for n, (pid, kind, a, b, ds, sides) in enumerate(self.paths):
                if pid == eid and kind == "down" and a == nid:
                    self._slot(nid, "s", eid, "out", self._x(ds[0]) if ds else self._x(b))
                    self.paths[n] = (pid, kind, a, b, ds, ("s", sides[1]))
                    break
            moved = True
        if moved:
            self.offset, self.stub = {}, {}
            self.ports()
        return moved

    def _into_box(self, nid, x0, x1):
        """True when a sideways run from x0 to x1 at nid's middle comes within 6 px of a box of its
        layer, or into it."""
        lo, hi = min(x0, x1), max(x0, x1)
        for it in self.L.layers[self.rank[nid]]:
            if it != nid and self.L.kind[it] == "node":
                w = self.info[it]["w"] / 2.0 + 6.0
                if self._x(it) - w < hi and lo < self._x(it) + w:
                    return True
        return False

    def _across_port(self, nid, x0, x1, y):
        """True when a sideways run from x0 to x1 at y (from nid's middle) passes another node's back
        edge where it runs out sideways to its port item, at much the same y: the two share a line."""
        lo, hi = min(x0, x1), max(x0, x1)
        for it in self.L.layers[self.rank[nid]]:
            if self.L.kind[it] != "port" or self.L.attach[it] == nid:
                continue
            n2, (_, eid, role) = self.L.attach[it], it
            a, b = sorted((self._x(it), self._x(n2)))
            side = self._side_port(n2, self._x(it))
            if a < hi and lo < b and abs(self.port(n2, side, eid, role)[1] - y) < channels.NEAR:
                return True
        return False

    def _separate(self):
        """An arrow coming down into a gap at x and another leaving it downward at the same x would
        share that line whatever their tracks: slide a lone port aside (toward its own run) so they
        don't. Returns True when a port moved."""
        moved = False
        for g, runs in self.runs.items():
            tops = [(x, r, i) for r in runs for i, (x, d) in enumerate(r.ends) if d == "top"]
            bots = [(x, r, i) for r in runs for i, (x, d) in enumerate(r.ends) if d == "bottom"]
            for xt, rt, it in tops:
                for xb, rb, ib in bots:
                    if rt is rb or abs(xt - xb) >= channels.NEAR:
                        continue
                    for r, i, other in ((rb, ib, xt), (rt, it, xb)):
                        m = self.movable.get((id(r), i))
                        if m and self._slide(m, r, i, other):
                            moved = True
                            break
        return moved

    def _doglegs(self):
        """Two runs that trade columns in a gap (long arrows crossing between their dummies): one of
        them takes a dogleg, a low track, a jog just past the other run's span, then a high track, so
        it passes above the other at one end and below it at the other. Three or more passing their
        columns round (channels.ring) are untied the same way, one dogleg at a time."""
        for g, runs in list(self.runs.items()):
            done = set()
            for a in list(runs):
                for b in list(runs):
                    if a is b or id(a) in done or id(b) in done or not channels.trading(a, b):
                        continue
                    r = b if len(b.ends) == 2 else a if len(a.ends) == 2 else None
                    if r is None:
                        continue
                    other = a if r is b else b
                    self._dogleg(g, runs, r, other.lo, other.hi)
                    done.update((id(a), id(b)))
            for _ in range(len(runs)):
                rs = channels.ring(runs)
                r = next((q for q in rs if len(q.ends) == 2), None) if rs else None
                if r is None:
                    break
                self._dogleg(g, runs, r, min(q.lo for q in rs if q is not r), max(q.hi for q in rs if q is not r))

    def _dogleg(self, g, runs, r, lo, hi):
        """Splits run r of gap g in two, joined by a jog just past lo..hi on the side of its top end."""
        top = next(x for x, d in r.ends if d == "top")
        bot = next(x for x, d in r.ends if d == "bottom")
        sign = 1.0 if top >= bot else -1.0
        taken = [x for q in runs for x, _ in q.ends] + self.passes.get(g, [])
        xd = (hi if sign > 0 else lo) + sign * channels.NEAR
        while any(abs(xd - x) < channels.NEAR for x in taken):
            xd += sign * channels.NEAR
        high = channels.Run(r.key + ("high",) if isinstance(r.key, tuple) else (r.key, "high"),
                            [(top, "top"), (xd, "mid")])
        low = channels.Run(r.key + ("low",) if isinstance(r.key, tuple) else (r.key, "low"),
                           [(xd, "mid"), (bot, "bottom")])
        high.above.append(low)
        runs.remove(r)
        runs += [high, low]
        self._rewire(r, top, bot, xd, high, low)

    def _rewire(self, r, top, bot, xd, high, low):
        """Points an arrow's legs at the two halves of its dogleg, in the order the arrow runs."""
        for n, (eid, kind, a, b, legs, sides) in enumerate(self.legs):
            idx = [k for k, leg in enumerate(legs) if leg[0] == "run" and leg[2] is r]
            if len(idx) != 2:
                continue
            k0, k1 = idx
            g = legs[k0][1]
            first_x = legs[k0][3]
            if abs(first_x - top) < 0.01:  # coming down: high half first
                new = [("run", g, high, top), ("run", g, high, xd), ("run", g, low, xd), ("run", g, low, bot)]
            else:  # climbing: low half first
                new = [("run", g, low, bot), ("run", g, low, xd), ("run", g, high, xd), ("run", g, high, top)]
            self.legs[n] = (eid, kind, a, b, legs[:k0] + new + legs[k1 + 1:], sides)
            return

    def _slide(self, m, run, i, other):
        eid, role, nid, side = m
        inf = self.info[nid]
        if inf["shape"] == "dot" or (eid, role) in self.pins:
            return False
        lim = 10.0 if inf["shape"] == "diamond" else max(0.0, (inf["w"] if side in ("n", "s") else inf["h"]) / 2.0 - 10.0)
        cx = self._x(nid)
        x = run.ends[i][0]
        rest = [e[0] for k, e in enumerate(run.ends) if k != i]
        toward = (sum(rest) / len(rest) - x) if rest else 1.0
        off = self.offset.get((eid, role), 0.0)
        sibs = [self.offset.get((e2, r2), 0.0) for e2, r2, _ in self.slots.get((nid, side), ()) if (e2, r2) != (eid, role)]
        step = channels.NEAR + 2.0
        cands = []
        for k in (1, 2, 3):
            for sign in ((1.0 if toward >= 0 else -1.0), (-1.0 if toward >= 0 else 1.0)):
                new = (other - cx) + sign * k * step
                if -lim <= new <= lim and all(abs(new - o2) >= 10.0 for o2 in sibs) and abs(new - off) > 0.01:
                    cands.append((abs(new - off), k, new))
        if not cands:
            return False
        self.offset[(eid, role)] = min(cands)[2]
        return True

    def _legs(self):
        self.legs = []  # per path: list of ("pt", x, ylocal, node) | ("run", gap, Run, x)
        self.runs = {}
        self.passes = {}  # gap -> x of arrows that cross it straight, with no run there
        self.movable = {}  # (id(run), end index) -> (edge, role, node, side): an end that is a lone port
        self.crowded = []  # (decision, side) whose exits turn down too close to a box beside it
        trunks = {}
        turns = {}  # (node, side) -> where its side exits turn down
        # sideways runs at a layer's middle, out of a side vertex and then down: layer -> [(lo, hi,
        # node)]. Every side exit's stub is in from the start, so a long run from another node of the
        # layer keeps off it, whichever comes first: two runs on one line read as one arrow that forks
        level = {}
        for eid, kind, a, b, ds, (s1, s2) in self.paths:
            if kind == "down" and s1 in ("w", "e"):
                x0 = self.port(a, s1, eid, "out")[0]
                x1 = x0 + (-1.0 if s1 == "w" else 1.0) * self.stub.get((eid, "out"), self.o["stub"])
                level.setdefault(self.rank[a], []).append((min(x0, x1), max(x0, x1), a))
        for eid, kind, a, b, ds, (s1, s2) in self.paths:
            legs = []
            st = self.o["stub"]
            if kind == "loop":
                self.legs.append((eid, kind, a, b, legs, (s1, s2)))
                continue
            if kind == "flat":
                p, q = self.port(a, s1, eid, "out"), self.port(b, s2, eid, "in")
                legs += [("pt", p[0], p[1], a), ("pt", q[0], q[1], b)]
                self.legs.append((eid, kind, a, b, legs, (s1, s2)))
                continue
            if kind == "over":
                g = self.rank[a] - 1
                p, q = self.port(a, "n", eid, "out"), self.port(b, "n", eid, "in")
                run = self._run(g, (eid, "over"), [(p[0], "bottom"), (q[0], "bottom")])
                self.movable[(id(run), 0)] = (eid, "out", a, "n")
                self.movable[(id(run), 1)] = (eid, "in", b, "n")
                legs += [("pt", p[0], p[1], a), ("run", g, run, p[0]), ("run", g, run, q[0]), ("pt", q[0], q[1], b)]
                self.legs.append((eid, kind, a, b, legs, (s1, s2)))
                continue
            if kind == "down":
                p = self.port(a, s1, eid, "out")
                q = self.port(b, "n", eid, "in")
                legs.append(("pt", p[0], p[1], a))
                x = p[0]
                if s1 in ("w", "e"):  # a decision's side vertex: out sideways, then down
                    nxt = self._x(ds[0]) if ds else q[0]
                    clear = self._clear(a, x, nxt)
                    out_st = self.stub.get((eid, "out"), st)
                    # every line through this layer (any node's back-edge port items, long arrows'
                    # dummies) and the turns already beside this node: a turn down near one shares its line
                    taken = [self._x(it) for it in self.L.layers[self.rank[a]] if self.L.kind[it] in ("port", "dummy")]
                    taken += turns.get((a, s1), [])
                    spans = level.setdefault(self.rank[a], [])
                    lo, hi = min(x, nxt), max(x, nxt)
                    free = not any(n2 != a and lo - channels.NEAR < h2 and l2 - channels.NEAR < hi for l2, h2, n2 in spans)
                    if clear and free and not any(abs(nxt - t) < channels.NEAR for t in taken):
                        x = nxt
                    else:  # turn just outside, clear of the other turns beside this node
                        sign = -1.0 if s1 == "w" else 1.0
                        x = x + sign * out_st
                        while any(abs(x - t) < channels.NEAR for t in taken):
                            x += sign * self.o["track"]
                        if self._into_box(a, p[0], x) or self._across_port(a, p[0], x, p[1]):
                            self.crowded.append((a, s1))
                    spans.append((min(p[0], x), max(p[0], x), a))
                    turns.setdefault((a, s1), []).append(x)
                    legs.append(("pt", x, p[1], a))
                g = self.rank[a]
                cols = [self._x(d) for d in ds] + [q[0]]
                tkey = (a, s1, round(p[0], 1)) if self.o["trunk"] and self.offset.get((eid, "out")) == 0.0 and s1 == "s" else None
                for k, cx in enumerate(cols):
                    if abs(cx - x) >= 0.5:
                        ends = [(x, "top"), (cx, "bottom")]
                        if k == 0 and tkey is not None:
                            run = trunks.get((g, tkey))
                            if run is None:
                                run = trunks[(g, tkey)] = self._run(g, ("trunk",) + tkey, [(x, "top")])
                            run.ends.append((cx, "bottom"))
                            run.lo, run.hi = min(run.lo, cx), max(run.hi, cx)
                        else:
                            run = self._run(g, (eid, k), ends)
                            if k == 0 and s1 == "s":
                                self.movable[(id(run), 0)] = (eid, "out", a, "s")
                        if k == len(cols) - 1:
                            self.movable[(id(run), len(run.ends) - 1)] = (eid, "in", b, "n")
                        legs += [("run", g, run, x), ("run", g, run, cx)]
                    else:
                        self.passes.setdefault(g, []).append(x)
                    x = cx
                    g += 1
                legs.append(("pt", q[0], q[1], b))
                self.legs.append((eid, kind, a, b, legs, (s1, s2)))
                continue
            if kind == "rise":  # from the top of the lower node a, up through its dummies, into b's bottom
                p = self.port(a, "n", eid, "out")
                q = self.port(b, "s", eid, "in")
                legs.append(("pt", p[0], p[1], a))
                g = self.rank[a] - 1
                cols = [self._x(d) for d in reversed(ds)] + [q[0]]
                x = p[0]
                for k, cx in enumerate(cols):
                    if abs(cx - x) >= 0.5:
                        run = self._run(g, (eid, "r", k), [(x, "bottom"), (cx, "top")])
                        if k == 0:
                            self.movable[(id(run), 0)] = (eid, "out", a, "n")
                        if k == len(cols) - 1:
                            self.movable[(id(run), 1)] = (eid, "in", b, "s")
                        legs += [("run", g, run, x), ("run", g, run, cx)]
                    else:
                        self.passes.setdefault(g, []).append(x)
                    x = cx
                    g -= 1
                legs.append(("pt", q[0], q[1], b))
                self.legs.append((eid, kind, a, b, legs, (s1, s2)))
                continue
            # back: from the lower node a up to the upper node b, turning at their port items
            p = self.port(a, s1, eid, "out")
            q = self.port(b, s2, eid, "in")
            xa, xb = self._x(("P", eid, "out")), self._x(("P", eid, "in"))
            legs += [("pt", p[0], p[1], a), ("pt", xa, p[1], a)]
            g = self.rank[a] - 1
            cols = [self._x(d) for d in reversed(ds)] + [xb]
            x = xa
            for k, cx in enumerate(cols):
                if abs(cx - x) >= 0.5:
                    run = self._run(g, (eid, "b", k), [(x, "bottom"), (cx, "top")])
                    legs += [("run", g, run, x), ("run", g, run, cx)]
                else:
                    self.passes.setdefault(g, []).append(x)
                x = cx
                g -= 1
            legs += [("pt", xb, q[1], b), ("pt", q[0], q[1], b)]
            self.legs.append((eid, kind, a, b, legs, (s1, s2)))

    def _lone_side(self, nid, side):
        return len(self.slots.get((nid, side), ())) == 1

    def _clear(self, nid, x0, x1):
        """True when nothing of nid's layer stands between x0 and x1 at its middle: no node, and no
        back edge's short run from its node out to its port item."""
        lo, hi = min(x0, x1), max(x0, x1)
        for it in self.L.layers[self.rank[nid]]:
            if it != nid and self.L.kind[it] == "node":
                w = self.info[it]["w"] / 2.0 + 8
                if self._x(it) + w > lo and self._x(it) - w < hi:
                    return False
            elif self.L.kind[it] == "port" and self.L.attach[it] != nid:
                n2 = self.L.attach[it]
                a, b = sorted((self._x(it), self._x(n2)))
                if b + 8 > lo and a - 8 < hi:
                    return False
            elif self.L.kind[it] == "dummy" and abs(self._x(it) - x1) < channels.NEAR:
                return False  # a long arrow passes right where this one would turn down
        return True

    def _run(self, g, key, ends):
        run = channels.Run(key, list(ends))
        self.runs.setdefault(g, []).append(run)
        return run

    def build(self, pos, band_top, band_h, track_y):
        out = []
        for eid, kind, a, b, legs, sides in self.legs:
            if kind == "loop":
                x, y = pos[a]
                inf = self.info[a]
                r = x + inf["w"] / 2.0
                lp = self.o["loop"]
                pts = [(r, y - 8), (r + lp, y - 8), (r + lp, y + 8), (r, y + 8)]
                out.append(Route(eid, pts, sides, nodes=(a, b)))
                continue
            pts = []
            for leg in legs:
                if leg[0] == "pt":
                    _, x, dy, nid = leg
                    pts.append((x, pos[nid][1] + dy))
                else:
                    _, g, run, x = leg
                    pts.append((x, track_y[(g, run.track)]))
            out.append(Route(eid, _clean(pts), sides, back=kind in ("back", "rise"), flat=kind in ("flat", "over"),
                             nodes=(a, b)))
        return out


def _clean(pts):
    """Drops repeated points and the middle of three in a line."""
    out = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 0.01 and abs(p[1] - out[-1][1]) < 0.01:
            continue
        out.append(p)
    k = 1
    while k < len(out) - 1:
        (x0, y0), (x1, y1), (x2, y2) = out[k - 1], out[k], out[k + 1]
        if (abs(x0 - x1) < 0.01 and abs(x1 - x2) < 0.01) or (abs(y0 - y1) < 0.01 and abs(y1 - y2) < 0.01):
            del out[k]
        else:
            k += 1
    return out


def _inward(n, near, far, most=22.0):
    """n positions from near outward toward far, at most `most` apart (all within [near, far])."""
    near = min(near, far)
    gap = most if n <= 1 else min(most, (far - near) / (n - 1))
    return [near + i * gap for i in range(n)]


def _slots(n, lo, hi, most=22.0):
    """n positions inside [lo, hi], centered, at most `most` apart."""
    if n <= 1:
        return [(lo + hi) / 2.0]
    gap = min(most, (hi - lo) / (n - 1))
    start = (lo + hi) / 2.0 - gap * (n - 1) / 2.0
    return [start + i * gap for i in range(n)]

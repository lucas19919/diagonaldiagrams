"""Isometric figures: the 3D toolkit, and the layer stack drawn with it.

The toolkit is what paint.py's projection stage was left open for. Iso is a projection (true
isometric: x runs down to the right, y down to the left, z straight up) that also knows the solids
it draws, so it orders their faces itself: a face's middle says little about what hides it. A
block's side is nearer than the middle of the plate it stands on, yet the plate goes first, so
Iso.order sorts whole boxes by the axis that keeps them apart. box_faces gives a box's three
visible faces as Elements with pts3d, and Drawing.svg() projects them.

Every face carries data-solid (its box's key), and the top face its box as data-box3, so the audit
reads depth back from the SVG: what hides what, what a label stands on, what an arrow runs behind.

The figure: `iso` draws layers, top first, as slabs stacked with room between them. Each holds
its items in rows as blocks with their names on top, and links are arrows between blocks, passing
any slab between them through a port. Every face and link is drawn first, in depth order, then
every text, so the projection stage reorders only faces among faces. Its look is the iso preset
(style/presets/iso.json): a layer is a group, an item a node, a link an edge, so stylesheets
select them as they do any diagram's.
"""
import heapq
import math

from . import paint
from .geom import clip_convex as clip
from .errors import SpecError
from .text.markup import plain

COS, SIN = math.cos(math.pi / 6), 0.5
EPS = 1e-6


class Iso:
    """True isometric: (x, y, z) -> (x, y, depth) on the page, the origin at (ox, oy); larger depth
    is farther. solids: key -> (x0, y0, z0, x1, y1, z1), the boxes whose faces carry data-solid=key;
    order() sorts by them, and a face whose key is unknown counts as a box around its own points."""

    def __init__(self, ox=0.0, oy=0.0):
        self.ox, self.oy, self.solids = ox, oy, {}

    def __call__(self, x, y, z):
        return self.ox + (x - y) * COS, self.oy + (x + y) * SIN - z, -(x + y + z)

    def flat(self, x, y, z):
        return self.ox + (x - y) * COS, self.oy + (x + y) * SIN - z

    def corners(self, box):
        x0, y0, z0, x1, y1, z1 = box
        return [self.flat(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]

    def outline(self, box):
        """The box's silhouette on the page, a convex polygon."""
        return hull(self.corners(box))

    def order(self, faces):
        """The faces back to front: whole solids in an order where nothing is drawn over what hides
        it, each solid's faces in the order given (a box's visible faces never overlap)."""
        groups, keys = {}, []
        for e in faces:
            k = e.attrs.get("data-solid") or id(e)
            if k not in groups:
                groups[k] = []
                keys.append(k)
            groups[k].append(e)
        boxes = [self.solids.get(k) or _bounds(groups[k]) for k in keys]
        rects = [_rect(self.corners(b)) for b in boxes]
        n = len(keys)
        after, need = [[] for _ in range(n)], [0] * n
        for i in range(n):
            for j in range(i + 1, n):
                if not _meet(rects[i], rects[j]):
                    continue
                w = behind(boxes[i], boxes[j])
                if w == 1:
                    after[i].append(j)
                    need[j] += 1
                elif w == -1:
                    after[j].append(i)
                    need[i] += 1
        near = [sum(b[a] + b[a + 3] for a in range(3)) for b in boxes]  # x + y + z of the middle, twice: larger is nearer
        heap = [(near[i], i) for i in range(n) if not need[i]]
        heapq.heapify(heap)
        out, done = [], set()
        while len(out) < n:
            if not heap:  # solids that cross each other: the farthest goes first
                i = min((k for k in range(n) if k not in done), key=lambda k: (near[k], k))
                heapq.heappush(heap, (near[i], i))
            _, i = heapq.heappop(heap)
            if i in done:
                continue
            done.add(i)
            out.append(i)
            for j in after[i]:
                need[j] -= 1
                if need[j] == 0 and j not in done:
                    heapq.heappush(heap, (near[j], j))
        return [e for i in out for e in groups[keys[i]]]


def behind(a, b):
    """1 if box a is behind box b (b may hide it), -1 if b is behind a, 0 if that can't be told:
    they cross, or they are apart along axes that disagree, and then neither hides the other.
    The viewer looks from +x, +y, +z, so along each axis the lower box is the farther."""
    votes = set()
    for k in range(3):
        if a[k + 3] <= b[k] + EPS:
            votes.add(1)
        elif b[k + 3] <= a[k] + EPS:
            votes.add(-1)
    return votes.pop() if len(votes) == 1 else 0


def _bounds(faces):
    pts = [p for e in faces for p in (e.pts3d or [])]
    return tuple(min(p[k] for p in pts) for k in range(3)) + tuple(max(p[k] for p in pts) for k in range(3))


def _rect(pts):
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def _meet(a, b):
    return a[0] < b[2] - EPS and b[0] < a[2] - EPS and a[1] < b[3] - EPS and b[1] < a[3] - EPS


def hull(points):
    """The convex hull of 2D points, counterclockwise as the page draws it (y down)."""
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def box_faces(box, key, fills, stroke, width, owner="", top=None, a11y=None):
    """A box's three visible faces, top first: Elements with pts3d, for the projection stage.
    fills: (top, front-left, front-right). top: more attributes for the top face, which also gets
    the box as data-box3 and the accessible name."""
    x0, y0, z0, x1, y1, z1 = box
    corners = {"top": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
               "left": [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)],
               "right": [(x1, y0, z1), (x1, y1, z1), (x1, y1, z0), (x1, y0, z0)]}
    out = []
    for (side, pts), fill in zip(corners.items(), fills):
        extra = dict(top or {}, data_box3=" ".join(paint.fmt(round(v, 2)) for v in box)) if side == "top" else {}
        e = paint.el("polygon", owner=owner, role="solid." + side, a11y=a11y if side == "top" else None,
                     fill=fill, stroke=stroke, stroke_width=width, stroke_linejoin="round", data_solid=key, **extra)
        e.pts3d = pts
        out.append(e)
    return out


def mix(a, b, p):
    """Color a moved p of the way to b, as #rrggbb (opaque: the audit reads faces as solid paint)."""
    from .style.parse import color
    ca, cb = color(a), color(b)
    r, g, bl = (u + (v - u) * p for u, v in ((ca.r, cb.r), (ca.g, cb.g), (ca.b, cb.b)))
    return f"#{int(r + .5):02x}{int(g + .5):02x}{int(bl + .5):02x}"


# ---------------------------------------------------------------------------------------------------
# The layer stack

LAYERS, FOCAL = 8, 2  # layers, highlighted items
WRAP, WIDE, MOST = 6, 12, 24  # a layer's row wraps past this many items; a layer warns past WIDE, and stops past MOST
PX, PY, GAP = 26, 22, 26  # a slab's room beside its blocks (x) and before and after them (y); between blocks
THICK, RISE = 12, 20  # a slab's thickness, a block's height
NAME_W, NARROW_W = 118, 96  # a block's name wraps past this width; in a narrow place, past the second


def _w(text, st):
    from .text.measure import width
    return width(paint.transformed(text, st), st["font-size"], paint._bold(st), "", st.get("font"))


def _wrap(text, st, room, lines=2):
    """Words in lines no wider than room, at most `lines` of them; the last keeps what is left."""
    words, out, cur = str(text).split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and _w(trial, st) > room and len(out) < lines - 1:
            out.append(cur)
            cur = w
        else:
            cur = trial
    return out + ([cur] if cur else [])


def _name(x):
    return str(x.get("name") if x.get("name") not in (None, "") else x.get("id", ""))


def _whole(item, key):
    c = item.get(key)
    return c if isinstance(c, int) and not isinstance(c, bool) and 0 <= c < 8 else None


def _layers(spec):
    return [dict(layer, id=str(layer.get("id", f"layer{i + 1}")), items=list(layer.get("items") or []))
            for i, layer in enumerate(spec["layers"])]


def grid(layers, links, wrap=WRAP):
    """Where each item stands on the grid every slab shares. Returns ({id: (row, col)}, columns,
    rows over all layers, each layer's rows); row 0 is the front row. An item stands where its "row"
    and "col" say; otherwise on the diagonal of what it links to in a layer above, because blocks with
    the same row + col line up on the page and their link drops straight down, in the backmost row
    that allows, where no block of its own layer stands in the link's way. The rest take what is left
    from where they would stand filling the rows from the back, in spec order. A link that passes a
    layer keeps its cell there free, adding a column if the layer has no other room."""
    fixed = [_whole(it, "col") for layer in layers for it in layer["items"] if _whole(it, "col") is not None]
    most = max([min(len(layer["items"]), wrap) for layer in layers] + [1] + [c + 1 for c in fixed])
    while True:
        cell, rows, tight = _place(layers, links, wrap, most)
        if not tight or most >= 8:
            return cell, most, max(rows), rows
        most += 1


def _place(layers, links, wrap, most):
    near = {}
    for ln in links:
        a, b = str(ln["from"]), str(ln["to"])
        near.setdefault(a, []).append(b)
        near.setdefault(b, []).append(a)
    where = {str(it["id"]): i for i, layer in enumerate(layers) for it in layer["items"]}
    cell, rows, kept, tight = {}, [], {}, False  # kept: layer index -> the cells links pass through
    for i, layer in enumerate(layers):
        items = layer["items"]
        ids = [str(it["id"]) for it in items]
        k = max([math.ceil(len(items) / wrap), 1] + [_whole(it, "row") + 1 for it in items if _whole(it, "row") is not None])
        rows.append(k)
        cells = [(r, c) for r in range(k) for c in range(most)]
        mine = {}
        for it in items:
            c = _whole(it, "col")
            if c is not None or _whole(it, "row") is not None:
                r = _whole(it, "row")
                mine[str(it["id"])] = (k - 1 if r is None else r, c if c is not None else 0)
        free = [x for x in cells if x not in mine.values()]
        open_ = [x for x in free if x not in kept.get(i, ())]
        if len(open_) >= len(ids) - len(mine):
            free = open_
        else:
            tight = True
        want = {}
        for n, iid in enumerate(ids):
            if iid in mine:
                continue
            above = [sum(cell[o]) for o in near.get(iid, []) if o in cell]  # only the layers above are placed yet
            row_len = min(wrap, len(ids) - n // wrap * wrap)
            at = (k - 1 - n // wrap, (most - row_len) // 2 + n % wrap)
            want[iid] = (0, sum(above) / len(above), 0) if above else (1, at[1], at[0])
        for iid in sorted(want, key=lambda j: (want[j][:2], ids.index(j))):
            linked, d, r0 = want[iid]
            if linked == 0:
                x = min(free, key=lambda x: (abs(x[0] + x[1] - d), -x[0], x[1]))
            else:
                x = min(free, key=lambda x: (abs(x[1] - d) + abs(x[0] - r0) * 2, x[1]))
            free.remove(x)
            cell[iid] = x
        cell.update(mine)
        for ln in links:
            a, b = str(ln["from"]), str(ln["to"])
            for p, q in ((a, b), (b, a)):
                if p in cell and where[p] == i and where.get(q, i) > i + 1:
                    for j in range(i + 1, where[q]):
                        kept.setdefault(j, set()).add(cell[p])
    return cell, rows, tight


def _adapted(spec):
    """The stack as an arch spec, so the style system selects its parts as it does any diagram's:
    items are nodes, layers their groups, links edges."""
    layers = _layers(spec)
    pick = lambda d, keys: {k: d[k] for k in keys if k in d}  # noqa: E731
    return {**pick(spec, ("title", "sub", "style")),
            "nodes": [dict(pick(it, ("id", "name", "sub", "tag", "focal", "style", "class", "classes")), id=str(it["id"]), layer=i)
                      for i, layer in enumerate(layers) for it in layer["items"]],
            "edges": [dict(pick(ln, ("id", "label", "proto", "async", "focal", "style", "class", "classes")),
                           **{"from": str(ln["from"]), "to": str(ln["to"])}) for ln in spec.get("links") or []],
            "groups": [dict(pick(layer, ("id", "name", "style", "class", "classes")),
                            members=[str(it["id"]) for it in layer["items"]]) for layer in layers if layer["items"]]}


def styler(spec, theme=None, sheets=()):
    from .style.styler import Styler

    class IsoStyler(Styler):
        @staticmethod
        def _scene(spec, kind):
            return Styler._scene(_adapted(spec), "arch")
    return IsoStyler(spec, "iso", theme, sheets=sheets)


def check(spec):
    """What `validate` says about an iso spec: (errors, warnings), each with its fix."""
    errors, warnings = [], []

    def err(msg, fix):
        errors.append({"msg": msg, "fix": fix})
    if not isinstance(spec, dict):
        err("an iso spec is a JSON object", 'write {"title": "...", "layers": [{"id": "app", "name": "Apps", "items": [...]}]}')
        return errors, warnings
    layers = spec.get("layers")
    if not isinstance(layers, list) or not layers:
        err("iso needs a layers list", 'add "layers": [{"id": "app", "name": "Apps", "items": [{"id": "web", "name": "Web"}]}], top layer first')
        return errors, warnings
    budget = spec.get("budget", True) is not False
    if len(layers) > LAYERS:
        err(f"{len(layers)} layers; a stack reads up to {LAYERS}", "merge layers, or split the stack into two figures")
    wrap = spec.get("columns")
    if wrap is not None and (not isinstance(wrap, int) or isinstance(wrap, bool) or not 1 <= wrap <= 8):
        err(f"columns {wrap!r} is not a width", "columns is a whole number from 1 to 8: how many items a row holds before it wraps")
    where, ids = {}, set()
    focal = 0
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            err(f"layer {i + 1} is not an object", 'write it as {"id": "app", "name": "Apps", "items": [...]}')
            continue
        lid = layer.get("id", f"layer{i + 1}")
        if str(lid) in ids:
            err(f"the id '{lid}' is used twice", "give every layer and item its own id")
        ids.add(str(lid))
        items = layer.get("items") or []
        if not isinstance(items, list):
            err(f"layer '{lid}': items is not a list", 'write "items": [{"id": "web", "name": "Web"}]')
            continue
        if len(items) > MOST:
            err(f"layer '{lid}' has {len(items)} items; a layer holds up to {MOST}", "group items, or give them a layer of their own")
        elif len(items) > WIDE and budget:
            warnings.append({"msg": f"layer '{lid}' has {len(items)} items, past {WIDE}: the figure gets large",
                             "fix": "group some items, or set budget false"})
        taken = {}
        for item in items:
            if not isinstance(item, dict) or item.get("id") in (None, ""):
                err(f"layer '{lid}' has an item without an id", 'write each item as {"id": "web", "name": "Web"}')
                continue
            iid = str(item["id"])
            for key, what in (("col", "column"), ("row", "row")):
                if item.get(key) is not None and _whole(item, key) is None:
                    err(f"item '{iid}': {key} {item[key]!r} is not a {what}", f"{key} is a whole number from 0 to 7")
            if item.get("col") is not None or item.get("row") is not None:
                at = (_whole(item, "row"), _whole(item, "col"))
                if at in taken:
                    err(f"items '{taken[at]}' and '{iid}' both stand in the same place on layer '{lid}'",
                        "give each item in a layer its own row and col, or leave them out")
                taken[at] = iid
            if iid in ids:
                err(f"the id '{iid}' is used twice", "give every layer and item its own id")
            ids.add(iid)
            where[iid] = i
            focal += bool(item.get("focal"))
    if focal > FOCAL:
        warnings.append({"msg": f"{focal} items are highlighted; past {FOCAL} the accent stops pointing at anything",
                         "fix": "keep focal on one or two items"})
    names = {i: _name(layer) for i, layer in enumerate(layers) if isinstance(layer, dict)}  # by position, as `where` is
    joined = []
    for k, ln in enumerate(spec.get("links") or []):
        if not isinstance(ln, dict):
            err(f"link {k + 1} is not an object", 'write it as {"from": "web", "to": "api"}')
            continue
        a, b = str(ln.get("from")), str(ln.get("to"))
        missing = [x for x in (a, b) if x not in where]
        if missing:
            err(f"link {a} -> {b}: no item '{missing[0]}'", "links join items; check the ids")
        elif where[a] == where[b]:
            err(f"link {a} -> {b} joins two items in the same layer ({names[where[a]]})",
                "a stack links layers; draw links within a layer as an arch diagram")
        else:
            joined.append((a, b))
    if errors:
        return errors, warnings
    # a link that passes a layer goes through its slab, so nothing may stand where it does
    all_layers = _layers(spec)
    cell, _, _, _ = grid(all_layers, spec.get("links") or [], wrap or WRAP)
    for a, b in joined:
        up, down = (a, b) if where[a] < where[b] else (b, a)
        for k in range(where[up] + 1, where[down]):
            f = (k - where[up]) / (where[down] - where[up])
            r, c = (u + (d - u) * f for u, d in zip(cell[up], cell[down]))
            for it in all_layers[k]["items"]:
                x = cell[str(it["id"])]
                if abs(x[0] - r) < .5 and abs(x[1] - c) < .5:  # half a cell: past it, the link is in the gap beside the block
                    err(f"link {a} -> {b} runs through '{it['id']}' on layer '{all_layers[k]['id']}'",
                        f"give '{it['id']}' another col, or set col on {up} and {down} so the link passes beside it")
    from .style.styler import check_styles
    errors.extend(check_styles(_adapted(spec), "arch"))
    return errors, warnings


def _size(spec, layers, links, sty, wrap, name_w):
    """A figure's measurements at this wrap and name width: everything the width depends on."""
    text = {}
    for layer in layers:
        for item in layer["items"]:
            iid = str(item["id"])
            s = sty.node(iid)
            text[iid] = (_wrap(plain(_name(item)), s["label"], name_w), plain(str(item.get("sub") or "")))
    widths = [40]
    tall = [15]
    for iid, (nl, sub) in text.items():
        s = sty.node(iid)
        widths += [_w(ln, s["label"]) for ln in nl] + ([_w(sub, s["sub"])] if sub else [])
        tall.append(_block_h(s, nl, sub))
    # a square block's top is a rhombus: the text block fits across its middle with room to spare
    a = max(68, math.ceil((max(widths) / 2 + 8) / COS + max(tall) + 8))
    cell, most, R, rows = grid(layers, links, wrap)
    LW, LD = 2 * PX + most * a + (most - 1) * GAP, R * a + (R - 1) * GAP + 2 * PY
    left = 0
    for layer in layers:
        g = sty.group(layer["id"])
        left = max(left, _w(plain(_name(layer)), g["title"]),
                   _w(plain(str(layer.get("sub") or "")), _layer_sub(sty, layer)) if layer.get("sub") else 0)
    x_left = 30 + (left + 18 if left else 0)
    return {"text": text, "a": a, "cell": cell, "R": R, "rows": rows, "LW": LW, "LD": LD, "x_left": x_left,
            "W": x_left + (LW + LD) * COS + 30}


def _pitch(s):
    return round(s["font-size"] * 1.25)


def _block_h(s, nl, sub):
    return _pitch(s["label"]) * len(nl) + (_pitch(s["sub"]) + 1 if sub else 0)


def _layer_sub(sty, layer):
    return sty._text(sty.view("group", layer["id"]), "sub")


def render(spec, theme=None, info=None, sheets=(), embed=False):
    """Draw a layer stack. Returns (svg, W, H); info, if given, gets the drawing (the audit and the
    outline read it in memory) and, when the figure is wider than where it goes allows, over."""
    from ._theme import THEME
    from .diagrams import _bottom, _fit, _fonts, _legend, _more_markers, _owned_opacity, LEGEND_RULE, LEGEND_TEXT
    from .style.parse import color
    errors, _ = check(spec)
    if errors:
        raise SpecError(errors[0]["msg"], errors[0]["fix"])
    t = theme or THEME
    sty = styler(spec, t, sheets)
    layers = _layers(spec)
    links = list(spec.get("links") or [])
    L = len(layers)
    limit = _fit(spec)[1]

    # where it goes decides the shape: the fewest rows that fit, or the narrowest it can be
    wrap = spec.get("columns") or WRAP
    plan = _size(spec, layers, links, sty, wrap, NARROW_W if limit else NAME_W)
    if limit and not spec.get("columns"):
        for w in range(min(wrap, max(len(layer["items"]) for layer in layers)), 0, -1):
            trial = _size(spec, layers, links, sty, w, NARROW_W)
            if trial["W"] < plan["W"] or plan["W"] > limit >= trial["W"]:
                plan = trial
            if plan["W"] <= limit:
                break
    text, a, cell, R, rows, LW, LD, x_left = (plan[k] for k in ("text", "a", "cell", "R", "rows", "LW", "LD", "x_left"))

    def row_y(r):
        return LD - PY - a - r * (a + GAP)
    # each slab sits as low under the one above as its own back row allows: a block's whole top clears it
    z_top = [THICK] * L
    for i in range(L - 2, -1, -1):
        z_top[i] = z_top[i + 1] + (LD - row_y(rows[i + 1] - 1) + THICK + RISE + 16 + (28 if links else 0))

    fig = sty.figure()
    head, head_h = paint.heading(t, spec.get("title") or "", spec.get("sub") or "", x=30, st=fig, eyebrow=spec.get("figure"))
    top = max(30, head_h + 12)
    iso = Iso(ox=x_left + LD * COS, oy=top + z_top[0])  # the top slab's back corner is the highest point
    W = math.ceil(max(iso.ox + LW * COS + 30, _w(spec.get("title") or "", fig["title"]) + 60))
    if limit and info is not None and W > limit:
        info["over"] = (W, limit)
    bottom = iso.oy + (LW + LD) * SIN
    ids = edge_ids(links)
    focal = any(item.get("focal") for layer in layers for item in layer["items"]) or any(ln.get("focal") for ln in links)
    sentence = ", ".join(p for shown, p in ((links, "arrows = links between layers"),
                                             (any(ln.get("async") for ln in links), "dashed = async"),
                                             (focal, f"{paint.color_word(sty.token('accent'))} = highlighted")) if shown)
    extra = _bottom(t, sty, spec, W)
    H = math.ceil(bottom + (56 if sentence else 30) + extra)

    dr = paint.Drawing(W, H, spec.get("title") or "layer stack", spec.get("sub") or spec.get("title") or "layer stack",
                       projection=iso, kind="layer stack diagram", legible=True)
    dr.add(paint.paper(t, W, H, fig["paper"]), paint.marker_defs(t), *head)

    # light from above: tops lightest, the left sides darker, the right sides darker still. On a dark
    # theme the ink is light, so the sides darken toward black instead.
    p = color(fig["paper"])
    shade = "#000000" if (.2126 * p.r + .7152 * p.g + .0722 * p.b) / 255 < .5 else sty.token("ink")
    spots, texts = {}, []  # item id -> (layer index, center x, y); the texts, drawn after every face
    for i, layer in enumerate(layers):
        zt = z_top[i]
        slab = (0, 0, zt - THICK, LW, LD, zt)
        iso.solids[layer["id"]] = slab
        g = sty.group(layer["id"])
        names = [_name(item) for item in layer["items"]]
        said = plain(_name(layer)) + (": " + ", ".join(plain(n) for n in names) if names else "")
        dr.add(*box_faces(slab, layer["id"], (g["fill"], mix(g["fill"], shade, .10), mix(g["fill"], shade, .18)), g["stroke"],
                          g["computed"].get("stroke-width") or 1, owner=layer["id"],
                          top={"data_label": plain(_name(layer)), "data_rank": i}, a11y={"name": said, "kind": "layer"}))
        for item in layer["items"]:
            iid = str(item["id"])
            s = sty.node(iid)
            r, c = cell[iid]
            x, y = PX + c * (a + GAP), row_y(r)
            box = (x, y, zt, x + a, y + a, zt + RISE)
            iso.solids[iid] = box
            name = plain(_name(item))
            sides = (.13, .27, s["stroke"]) if item.get("focal") else (.08, .16, shade)
            dr.add(*box_faces(box, iid, (s["fill"], mix(s["fill"], sides[2], sides[0]), mix(s["fill"], sides[2], sides[1])),
                              s["stroke"], s["stroke-width"], owner=iid, top={"data_label": name, "data_layer": layer["id"]},
                              a11y={"name": name + (f", {plain(str(item['sub']))}" if item.get("sub") else "") +
                                    f", in {plain(_name(layer))}", "kind": "block"}))
            spots[iid] = (i, x + a / 2, y + a / 2)
            cx, cy = iso.flat(x + a / 2, y + a / 2, zt + RISE)
            nl, sub = text[iid]
            ty = cy - _block_h(s, nl, sub) / 2
            for ln in nl:
                texts.append(_on(paint.text_el(paint.transformed(ln, s["label"]), s["label"], iid, "node.label", round(cx, 1),
                                               paint._baseline(ty, _pitch(s["label"]), s["label"]["font-size"])), iid))
                ty += _pitch(s["label"])
            if sub:
                texts.append(_on(paint.text_el(paint.transformed(sub, s["sub"]), s["sub"], iid, "node.sub", round(cx, 1),
                                               paint._baseline(ty + 1, _pitch(s["sub"]), s["sub"]["font-size"])), iid))
        # the layer's name, level with the slab's left corner
        vx, vy = iso.flat(0, LD, zt)
        mid = vy + THICK / 2
        lsub = plain(str(layer.get("sub") or ""))
        ss = _layer_sub(sty, layer)
        block_h = g["title"]["font-size"] + 3 + (ss["font-size"] + 3 if lsub else 0)
        y0 = mid - block_h / 2
        texts.append(paint.el("line", owner=layer["id"], role="layer.leader", x1=round(vx - 12, 1), y1=round(mid, 1),
                              x2=round(vx - 3, 1), y2=round(mid, 1), stroke=g["stroke"], stroke_width=1))
        texts.append(paint.text_el(paint.transformed(plain(_name(layer)), g["title"]), g["title"], layer["id"], "layer.label",
                                   round(vx - 18, 1), round(y0 + g["title"]["font-size"] - 1, 1), anchor="end"))
        if lsub:
            texts.append(paint.text_el(paint.transformed(lsub, ss), ss, layer["id"], "layer.sub", round(vx - 18, 1),
                                       round(y0 + block_h - 3, 1), anchor="end"))

    # links: from under the upper block down to the top of the lower one, toward its back corner so the
    # arrowhead keeps clear of its name. A slab in the way is passed through a port, so the link is drawn
    # a piece per gap. A slab hides where a piece leaves it, so that part is cut off; what is left lies
    # between two slabs, and is sorted with the faces.
    for k, ln in enumerate(links):
        a_id, b_id = str(ln["from"]), str(ln["to"])
        (ia, xa, ya), (ib, xb, yb) = spots[a_id], spots[b_id]
        (xu, yu, iu), (xd, yd, idn) = ((xa, ya, ia), (xb, yb, ib)) if ia < ib else ((xb, yb, ib), (xa, ya, ia))
        start = (xu, yu, z_top[iu] - THICK)
        land = (xd - .35 * a, yd - .35 * a, z_top[idn] + RISE)

        def along(z):
            f = (start[2] - z) / (start[2] - land[2])
            return tuple(u + (v - u) * f for u, v in zip(start, land))
        pieces, cur, above = [], start, iu
        for j in range(iu + 1, idn):
            hole = along(z_top[j])
            pieces.append((cur, hole, above))
            r = 8
            port = paint.el("polygon", owner=layers[j]["id"], role="solid.port", fill=sty.group(layers[j]["id"])["stroke"],
                            stroke="none", data_solid=layers[j]["id"])
            port.pts3d = [(hole[0] - r, hole[1], hole[2]), (hole[0], hole[1] - r, hole[2]),
                          (hole[0] + r, hole[1], hole[2]), (hole[0], hole[1] + r, hole[2])]
            dr.add(port)
            cur, above = along(z_top[j] - THICK), j
        pieces.append((cur, land, above))
        seen = []
        for u, v, j in pieces:
            cut = clip(iso.flat(*u), iso.flat(*v), iso.outline(iso.solids[layers[j]["id"]]))
            t0 = cut[1] if cut else 0.0
            if t0 < 1:
                seen.append((tuple(s_ + (e_ - s_) * t0 for s_, e_ in zip(u, v)), v))
        if not seen:
            continue
        eid = ids[k]
        es = sty.edge(eid)
        key = "link:" + eid
        head_at = seen[-1] if ia < ib else seen[0]  # the arrowhead is at `to`
        for n, piece in enumerate(seen):
            pts = list(piece) if ia < ib else list(reversed(piece))  # from `from` to `to`
            arrow = piece is head_at
            pkey = key if arrow else f"{key}~{n}"
            iso.solids[pkey] = tuple(min(q[d] for q in pts) for d in range(3)) + tuple(max(q[d] for q in pts) for d in range(3))
            look = dict(owner=eid, role="edge.path", fill="none", stroke=es["stroke"], stroke_width=es["stroke-width"],
                        stroke_dasharray=",".join(paint.fmt(v) for v in es["dasharray"]) if es["dasharray"] else None,
                        data_solid=pkey)
            if arrow:
                e = paint.el("path", marker_end=f"url(#{sty.marker(es['stroke'])})", data_id=eid, data_from=a_id, data_to=b_id,
                             data_label=ln.get("label") or None,
                             a11y={"name": f"{plain(_name(_find(layers, a_id)))} to {plain(_name(_find(layers, b_id)))}" +
                                   (f": {plain(str(ln['label']))}" if ln.get("label") else ""), "kind": "link"},
                             attach={"from": {"node": a_id}, "to": {"node": b_id}}, **look)
            else:
                e = paint.el("path", data_link=key, **look)
            e.pts3d = pts
            dr.add(e)
        if ln.get("label"):  # beside the part that shows, on its right
            (sx, sy), (ex, ey) = iso.flat(*head_at[0]), iso.flat(*head_at[1])
            label = paint.transformed(str(ln["label"]), es["label"])
            w = paint._pill_w(label)
            x0, y0 = max(sx, ex) + 6, (sy + ey) / 2 - 8
            texts.append(_on(paint.el("rect", owner=eid, role="edge.label.pill", x=round(x0, 1), y=round(y0, 1),
                                      width=w, height=16, rx=2, fill=es["paper"]), key))
            texts.append(_on(paint.text_el(label, es["label"], eid, "edge.label", round(x0 + w / 2, 1), round(y0 + 12, 1)), key))
    dr.add(*texts)
    _more_markers(dr, sty)
    _legend(dr, t, sty, W, H, extra, LEGEND_RULE, LEGEND_TEXT, sentence, spec)
    _owned_opacity(dr, sty)
    _fonts(dr, sty, embed)
    svg = dr.svg()
    if info is not None:
        info["drawing"] = dr
    return svg, W, H


def edge_ids(links):
    from .scene.ids import edge_ids as ids
    return ids(links)


def _on(e, key):
    """Mark a text as standing on a solid's top (a block's name) or beside a link (its label), for the audit."""
    e.attrs["data-face"] = key
    return e


def _find(layers, iid):
    return next(item for layer in layers for item in layer["items"] if str(item["id"]) == iid)

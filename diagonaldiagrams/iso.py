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
its items in a row as blocks with their names on top, and links are arrows between the blocks of
neighbouring layers. Every face and link is drawn first, in depth order, then every text, so the
projection stage reorders only faces among faces.
"""
import heapq
import math

from . import paint
from .geom import clip_convex as clip
from .errors import SpecError
from ._theme import FONT, MONO, SANS
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

LAYERS, ITEMS, FOCAL = 8, 6, 2  # layers, items per layer, highlighted items
PX, PY, GAP = 26, 22, 26  # a slab's room beside its row of blocks (x) and before and after it (y); between blocks
THICK, RISE = 12, 20  # a slab's thickness, a block's height
NAME_W = 118  # a block's name wraps past this width


def _styles(t):
    return {"name": {"font-size": 12, "font-weight": 600, "font-family": SANS, "color": t["ink"]},
            "sub": {"font-size": 9, "font-family": MONO, "color": t["muted"]},
            "layer": {"font-size": 13, "font-weight": 600, "font-family": SANS, "color": t["ink"]},
            "layer_sub": {"font-size": 11, "font-family": FONT, "color": t["muted"]},
            "link": {"font-size": 10, "font-family": MONO, "color": t["muted"]},
            "caption": {"font-size": 12, "font-family": FONT, "color": t["muted"]}}


def _w(text, st):
    from .text.measure import width
    return width(text, st["font-size"], (st.get("font-weight") or 400) >= 600)


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


def _col(item):
    c = item.get("col")
    return c if isinstance(c, int) and not isinstance(c, bool) and 0 <= c < 8 else None


def columns(layers, links):
    """Each item's column in the grid every slab shares, and how many columns there are. An item
    stands in its "col" where the spec gives one; otherwise under the items it links to in the layer
    above, as near as the free columns allow, so most links drop straight down; the rest take what
    is left from where centering their layer would put them, in spec order."""
    fixed = [_col(it) for layer in layers for it in layer["items"] if _col(it) is not None]
    most = max([len(layer["items"]) for layer in layers] + [1] + [c + 1 for c in fixed])
    near = {}
    for ln in links:
        a, b = str(ln["from"]), str(ln["to"])
        near.setdefault(a, []).append(b)
        near.setdefault(b, []).append(a)
    col = {}
    for layer in layers:
        items = [str(it["id"]) for it in layer["items"]]
        mine = {str(it["id"]): _col(it) for it in layer["items"] if _col(it) is not None}
        free = [c for c in range(most) if c not in mine.values()]
        start = (most - len(items)) // 2
        want = {}
        for k, iid in enumerate(items):
            if iid not in mine:
                above = [col[o] for o in near.get(iid, []) if o in col]  # only the layers above are placed yet
                want[iid] = (0, sum(above) / len(above)) if above else (1, start + k)
        for iid in sorted(want, key=lambda j: (want[j], items.index(j))):
            c = min(free, key=lambda c: (abs(c - want[iid][1]), c))
            free.remove(c)
            col[iid] = c
        col.update(mine)
    return col, most


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
        if len(items) > 8:
            err(f"layer '{lid}' has {len(items)} items; a row holds up to 8", "group items, or give them a layer of their own")
        elif len(items) > ITEMS and budget:
            warnings.append({"msg": f"layer '{lid}' has {len(items)} items, past {ITEMS}: the figure gets wide",
                             "fix": "group some items, or set budget false"})
        taken = {}
        for item in items:
            if not isinstance(item, dict) or item.get("id") in (None, ""):
                err(f"layer '{lid}' has an item without an id", 'write each item as {"id": "web", "name": "Web"}')
                continue
            iid = str(item["id"])
            if item.get("col") is not None:
                if _col(item) is None:
                    err(f"item '{iid}': col {item['col']!r} is not a column", "col is a whole number from 0 (the left) to 7")
                elif _col(item) in taken:
                    err(f"items '{taken[_col(item)]}' and '{iid}' both stand in col {_col(item)} of layer '{lid}'",
                        "give each item in a layer its own col, or leave col out")
                else:
                    taken[_col(item)] = iid
            if iid in ids:
                err(f"the id '{iid}' is used twice", "give every layer and item its own id")
            ids.add(iid)
            where[iid] = i
            focal += bool(item.get("focal"))
    if focal > FOCAL:
        warnings.append({"msg": f"{focal} items are highlighted; past {FOCAL} the accent stops pointing at anything",
                         "fix": "keep focal on one or two items"})
    names = {i: _name(layer) for i, layer in enumerate(layers) if isinstance(layer, dict)}  # by position, as `where` is
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
        elif abs(where[a] - where[b]) > 1:
            gap = ", ".join(names[j] for j in range(min(where[a], where[b]) + 1, max(where[a], where[b])))
            err(f"link {a} -> {b} skips a layer ({gap}), which would hide it",
                "link through an item in the layer between, or move one of the items")
    return errors, warnings


def render(spec, theme=None, info=None):
    """Draw a layer stack. Returns (svg, W, H); info, if given, gets the drawing (the audit and the
    outline read it in memory)."""
    from ._theme import THEME
    errors, _ = check(spec)
    if errors:
        raise SpecError(errors[0]["msg"], errors[0]["fix"])
    t = theme or THEME
    st = _styles(t)
    layers = [dict(layer, id=str(layer.get("id", f"layer{i + 1}")), items=list(layer.get("items") or []))
              for i, layer in enumerate(spec["layers"])]
    L = len(layers)

    # a block's text: its name in up to two lines, its sub in one
    text = {}
    for layer in layers:
        for item in layer["items"]:
            nl = _wrap(plain(_name(item)), st["name"], NAME_W)
            sub = plain(str(item.get("sub") or ""))
            text[str(item["id"])] = (nl, sub)
    tw = max([_w(ln, st["name"]) for nl, _ in text.values() for ln in nl] +
             [_w(sub, st["sub"]) for _, sub in text.values() if sub] + [40])
    tall = max([15 * len(nl) + (12 if sub else 0) for nl, sub in text.values()] + [15])
    # a square block's top is a rhombus: the text block fits across its middle with room to spare
    a = max(68, math.ceil((tw / 2 + 8) / COS + tall + 8))
    links = list(spec.get("links") or [])
    col, most = columns(layers, links)
    LW = 2 * PX + most * a + (most - 1) * GAP
    LD = a + 2 * PY
    pitch = a + PY + THICK + RISE + 16 + (28 if links else 0)  # a block's whole top clears the slab above, and a link shows
    z_top = [(L - 1 - i) * pitch + THICK for i in range(L)]  # each slab's top face

    # the layer names, left of each slab's left corner
    left_w = 0
    for layer in layers:
        left_w = max(left_w, _w(plain(_name(layer)), st["layer"]),
                     _w(plain(str(layer.get("sub") or "")), st["layer_sub"]) if layer.get("sub") else 0)
    margin = 30
    head, head_h = paint.heading(t, spec.get("title") or "", spec.get("sub") or "", x=margin, eyebrow=spec.get("figure"))
    top = max(margin, head_h + 12)
    x_left = margin + (left_w + 18 if left_w else 0)
    iso = Iso(ox=x_left + LD * COS, oy=top + z_top[0])  # the top slab's back corner is the highest point
    W = math.ceil(max(iso.ox + LW * COS + margin, _w(spec.get("title") or "", {"font-size": 18, "font-weight": 600}) + 2 * margin))
    bottom = iso.oy + (LW + LD) * SIN
    focal = any(item.get("focal") for layer in layers for item in layer["items"]) or any(ln.get("focal") for ln in links)
    sentence = ", ".join(p for shown, p in ((links, "arrows = links between layers"),
                                             (any(ln.get("async") for ln in links), "dashed = async"),
                                             (focal, f"{paint.color_word(t['accent'])} = highlighted")) if shown)
    cap = st["caption"]
    cap_lines = paint.caption_lines(spec.get("caption") or "", W - 2 * margin, cap)
    H = math.ceil(bottom + (56 if sentence else margin) + ((cap["font-size"] + 4) * len(cap_lines) + 8 if cap_lines else 0))

    dr = paint.Drawing(W, H, spec.get("title") or "layer stack", spec.get("sub") or spec.get("title") or "layer stack",
                       projection=iso, kind="layer stack diagram", legible=True)
    dr.add(paint.paper(t, W, H), paint.marker_defs(t), *head)

    # light from above: tops lightest, the left sides darker, the right sides darker still. On a dark
    # theme the ink is light, so the sides darken toward black instead.
    from .style.parse import color
    p = color(t["paper"])
    shade = "#000000" if (.2126 * p.r + .7152 * p.g + .0722 * p.b) / 255 < .5 else t["ink"]
    plate_top = mix(t["paper"], t["ink"], .06)
    plate = (plate_top, mix(plate_top, shade, .10), mix(plate_top, shade, .18))
    plate_line = mix(t["paper"], t["ink"], .32)
    block = (t["card"], mix(t["card"], shade, .08), mix(t["card"], shade, .16))
    hot_top = mix(t["card"], t["accent"], .10)
    hot = (hot_top, mix(t["card"], t["accent"], .22), mix(t["card"], t["accent"], .34))
    spots, texts = {}, []  # item id -> (layer index, center x, y, top z); the texts, drawn after every face
    for i, layer in enumerate(layers):
        zt = z_top[i]
        slab = (0, 0, zt - THICK, LW, LD, zt)
        iso.solids[layer["id"]] = slab
        names = [_name(item) for item in layer["items"]]
        said = plain(_name(layer)) + (": " + ", ".join(plain(n) for n in names) if names else "")
        dr.add(*box_faces(slab, layer["id"], plate, plate_line, 1, owner=layer["id"],
                          top={"data_label": plain(_name(layer)), "data_rank": i}, a11y={"name": said, "kind": "layer"}))
        for item in layer["items"]:
            iid = str(item["id"])
            x = PX + col[iid] * (a + GAP)
            box = (x, PY, zt, x + a, PY + a, zt + RISE)
            iso.solids[iid] = box
            hi = bool(item.get("focal"))
            name = plain(_name(item))
            dr.add(*box_faces(box, iid, hot if hi else block, t["accent"] if hi else t["ink"], 1.6 if hi else 1.2, owner=iid,
                              top={"data_label": name, "data_layer": layer["id"]},
                              a11y={"name": name + (f", {plain(str(item['sub']))}" if item.get("sub") else "") +
                                    f", in {plain(_name(layer))}", "kind": "block"}))
            spots[iid] = (i, x + a / 2, PY + a / 2, zt + RISE)
            cx, cy = iso.flat(x + a / 2, PY + a / 2, zt + RISE)
            nl, sub = text[iid]
            pitch_n = 15
            y = cy - (pitch_n * len(nl) + (12 if sub else 0)) / 2
            for ln in nl:
                texts.append(_on(paint.text_el(ln, st["name"], iid, "node.label", round(cx, 1), round(y + 11, 1)), iid))
                y += pitch_n
            if sub:
                texts.append(_on(paint.text_el(sub, st["sub"], iid, "node.sub", round(cx, 1), round(y + 9, 1)), iid))
        # the layer's name, level with the slab's left corner
        vx, vy = iso.flat(0, LD, zt)
        mid = vy + THICK / 2
        lsub = plain(str(layer.get("sub") or ""))
        block_h = 16 + (14 if lsub else 0)
        y0 = mid - block_h / 2
        texts.append(paint.el("line", owner=layer["id"], role="layer.leader", x1=round(vx - 12, 1), y1=round(mid, 1),
                              x2=round(vx - 3, 1), y2=round(mid, 1), stroke=plate_line, stroke_width=1))
        texts.append(paint.text_el(plain(_name(layer)), st["layer"], layer["id"], "layer.label", round(vx - 18, 1),
                                   round(y0 + 12, 1), anchor="end"))
        if lsub:
            texts.append(paint.text_el(lsub, st["layer_sub"], layer["id"], "layer.sub", round(vx - 18, 1),
                                       round(y0 + 27, 1), anchor="end"))

    # links: from under the upper block down to the top of the lower one, toward its back corner so the
    # arrowhead keeps clear of its name. The upper slab hides where a link leaves, so that part is cut
    # off; what is left lies between two slabs, above every block it passes, and is sorted with the faces.
    from .scene.ids import EdgeIds
    name_of = EdgeIds()
    for ln in links:
        a_id, b_id = str(ln["from"]), str(ln["to"])
        (ia, xa, ya, _), (ib, xb, yb, _) = spots[a_id], spots[b_id]
        (xu, yu, iu), (xd, yd, idn) = ((xa, ya, ia), (xb, yb, ib)) if ia < ib else ((xb, yb, ib), (xa, ya, ia))
        start = (xu, yu, z_top[iu] - THICK)
        land = (xd - .35 * a, yd - .35 * a, z_top[idn] + RISE)
        cut = clip(iso.flat(*start), iso.flat(*land), iso.outline(iso.solids[layers[iu]["id"]]))
        t0 = cut[1] if cut else 0.0
        seen = tuple(s + (e - s) * t0 for s, e in zip(start, land))
        pts = [seen, land] if ia < ib else [land, seen]  # from `from` to `to`: the arrowhead is at `to`
        eid = name_of(a_id, b_id, ln.get("label") or "", ln.get("id"))
        key = "link:" + eid
        iso.solids[key] = tuple(min(p[k] for p in pts) for k in range(3)) + tuple(max(p[k] for p in pts) for k in range(3))
        hot_link = bool(ln.get("focal"))
        e = paint.el("path", owner=eid, role="edge.path", fill="none", stroke=t["accent"] if hot_link else t["muted"],
                     stroke_width=1.6, stroke_dasharray="5,4" if ln.get("async") else None,
                     marker_end="url(#aa)" if hot_link else "url(#a)", data_solid=key, data_id=eid,
                     data_from=a_id, data_to=b_id, data_label=ln.get("label") or None,
                     a11y={"name": f"{plain(_name(_find(layers, a_id)))} to {plain(_name(_find(layers, b_id)))}" +
                           (f": {plain(str(ln['label']))}" if ln.get("label") else ""), "kind": "link"},
                     attach={"from": {"node": a_id}, "to": {"node": b_id}})
        e.pts3d = pts
        dr.add(e)
        if ln.get("label"):  # beside the part that shows, on its right
            (sx, sy), (ex, ey) = iso.flat(*seen), iso.flat(*land)
            label = paint.transformed(str(ln["label"]), st["link"])
            w = paint._pill_w(label)
            x0, y0 = max(sx, ex) + 6, (sy + ey) / 2 - 8
            texts.append(_on(paint.el("rect", owner=eid, role="edge.label.pill", x=round(x0, 1), y=round(y0, 1),
                                      width=w, height=16, rx=2, fill=t["paper"]), key))
            texts.append(_on(paint.text_el(label, st["link"], eid, "edge.label", round(x0 + w / 2, 1), round(y0 + 12, 1)), key))
    dr.add(*texts)
    if sentence:
        dr.add(*paint.legend_line(t, W, bottom + 16, bottom + 34, sentence))
    if cap_lines:
        dr.add(*paint.caption(t, cap_lines, margin, bottom + (56 if sentence else margin) + cap["font-size"], cap))
    svg = dr.svg()
    if info is not None:
        info["drawing"] = dr
    return svg, W, H


def _on(e, key):
    """Mark a text as standing on a solid's top (a block's name) or beside a link (its label), for the audit."""
    e.attrs["data-face"] = key
    return e


def _find(layers, iid):
    return next(item for layer in layers for item in layer["items"] if str(item["id"]) == iid)

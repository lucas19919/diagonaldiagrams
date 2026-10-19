"""Painting: the elements a figure draws, and the one place their SVG text is written.

A Drawing is an ordered list of Elements (paint order). Each Element is one SVG element with its
attributes (unescaped values), its text, and what it is for: `owner` names the scene element it
belongs to (a node id, an edge "from->to", a group id; "" for the figure) and `role` says which
part of it this is (node.shape, node.label, edge.path, group.frame, ...). Outlines, exports and the
audit read owners and roles instead of guessing them back from the SVG.

Drawing.svg() writes every figure the same way: one top-level element per line, attributes in the
order given, numbers with at most two decimals (trailing zeros dropped), text escaped once.

Before writing, a drawing passes through the projection stage (DESIGN 13), which is the identity
in 2D. An element may carry 3D corner points (pts3d); with a projection set, those faces get their
2D outline and depth from it and are painted back to front. The core never sets one: the 3D toolkit
(P7) does, without core edits.

Accessibility (DESIGN 22.3): the parts a reader navigates (nodes, arrows, messages, tables, groups)
carry a11y = {"name", "kind"}. A drawing with a `kind` ("flow diagram") is written as a WAI-ARIA
graphics document: those parts become role="graphics-symbol" with an aria-label, and everything
else a part owns (its texts, pills, tails) is aria-hidden, so nothing is read twice. An edge
also carries attach: the node and port at each end, written as data-from-port and data-to-port.
"""
import re

from ._draw import ICONS, _bold, _box_lines, _diamond_h, _diamond_lines, _frame_box, _label_box, _pill_w, box_text, corner_rx, diamond_text
from . import deco
from .text.markup import plain
from .registry import Registry
from ._text import _text_w, _wrap
from ._theme import FONT, MONO, SANS, SERIF

_NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
GEOMETRY = ("d", "points", "transform", "viewBox")  # strings whose numbers are written canonically


def fmt(v):
    """A number as SVG text: at most two decimals, no trailing zeros, no "-0"."""
    if type(v) is int:  # the common case, and what the general path would give
        return str(v)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _numbers(s):
    return _NUM.sub(lambda m: fmt(float(m.group(0))), s)


def _attr(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _text(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_DECOR = {"figure.paper", "legend.rule", "note.leader", "note.dot"}  # drawn, but nothing to read


class Element:
    """One SVG element. depth and pts3d are the 3D hooks: a face's 3D corners, and its distance from
    the viewer once projected (0 in 2D). a11y names a part a reader navigates; attach says what an
    edge joins: {"from": {"node", "port"}, "to": {...}}."""
    __slots__ = ("tag", "attrs", "text", "children", "owner", "role", "depth", "pts3d", "a11y", "attach")

    def __init__(self, tag, attrs=None, text=None, children=None, owner="", role="", depth=0.0, pts3d=None,
                 a11y=None, attach=None):
        self.tag, self.attrs, self.text, self.children = tag, attrs if attrs is not None else {}, text, children or []
        self.owner, self.role, self.depth, self.pts3d = owner, role, depth, pts3d
        self.a11y, self.attach = a11y, attach

    def __repr__(self):
        return f"Element({self.tag!r}, owner={self.owner!r}, role={self.role!r})"

    def values(self, aria=False):
        """Attribute values as the SVG text will hold them (numbers canonical, not yet escaped).
        aria: this element sits in a graphics document, so it gets its ARIA attributes too."""
        out = {k: (fmt(v) if isinstance(v, (int, float)) else (_numbers(v) if k in GEOMETRY else str(v)))
               for k, v in self.attrs.items() if v is not None}
        if self.attach:
            for end in ("from", "to"):
                port = self.attach.get(end, {}).get("port")
                if port is not None:
                    out[f"data-{end}-port"] = str(port)
        if aria:
            if self.a11y:
                out["role"] = "graphics-symbol"
                out["aria-roledescription"] = self.a11y["kind"]
                out["aria-label"] = self.a11y["name"]
            elif self.owner or self.role in _DECOR:
                out["aria-hidden"] = "true"
        return out

    def etree(self, aria=False):
        """This element as an ElementTree element, equal to what parsing svg() would give."""
        import xml.etree.ElementTree as ET
        node = ET.Element(self.tag, self.values(aria))
        node.text = self.text or None
        node.extend(c.etree() for c in self.children)
        return node

    def svg(self, aria=False):
        parts = [f' {k}="{_attr(v)}"' for k, v in self.values(aria).items()]
        head = f"<{self.tag}{''.join(parts)}"
        if self.text is None and not self.children:
            return head + "/>"
        return head + ">" + _text(self.text or "") + "".join(c.svg() for c in self.children) + f"</{self.tag}>"


_ATTR_NAMES = {}  # stroke_width -> stroke-width, worked out once per name


def _attr_name(k):
    name = _ATTR_NAMES.get(k)
    if name is None:
        name = _ATTR_NAMES[k] = k.rstrip("_").replace("_", "-")
    return name


def el(tag, text=None, owner="", role="", children=None, a11y=None, attach=None, **attrs):
    """An Element; attribute names are written with dashes (stroke_width -> stroke-width), and a
    trailing underscore is dropped (in_ -> in, for names Python keeps to itself)."""
    return Element(tag, {_ATTR_NAMES.get(k) or _attr_name(k): v for k, v in attrs.items()}, text, children or [], owner, role,
                   a11y=a11y, attach=attach)


def project(items, projection=None):
    """The projection stage: the identity when projection is None. A projection is a callable
    (x, y, z) -> (x, y, depth), larger depth farther away. Each element with pts3d (a polygon face)
    gets its points and a data-depth from it; the faces are then reordered back to front among the
    places they hold in the paint order, so everything 2D (paper, labels) stays where it was."""
    if projection is None:
        return items
    slots = [k for k, e in enumerate(items) if e.pts3d]
    for k in slots:
        e = items[k]
        flat = [projection(*p) for p in e.pts3d]
        e.depth = sum(d for _, _, d in flat) / len(flat)
        e.attrs["points"] = " ".join(f"{fmt(x)},{fmt(y)}" for x, y, _ in flat)
        e.attrs["data-depth"] = e.depth
    out = list(items)
    for k, e in zip(slots, sorted((items[k] for k in slots), key=lambda e: -e.depth)):  # stable for ties
        out[k] = e
    return out


class Drawing:
    """A figure being painted: its size, its accessible title and description, the elements in
    paint order, the projection (None in 2D), and its kind ("flow diagram"), which makes it a
    navigable graphics document rather than a single image (None: role="img", as charts are).
    legible: its default colors and sizes pass the legibility checks (B25), so it writes
    data-legibility="all" and the audit judges every text, not only those a stylesheet styled."""
    __slots__ = ("width", "height", "title", "desc", "items", "projection", "kind", "legible")

    def __init__(self, width, height, title="", desc="", items=None, projection=None, kind=None, legible=False):
        self.width, self.height, self.title, self.desc = width, height, title, desc
        self.items, self.projection, self.kind, self.legible = list(items or []), projection, kind, legible

    def _items(self):
        """The elements to write: after the projection stage, with the definitions decorations
        brought (gradients, filters, patterns) moved into the figure's <defs>, once each."""
        items = project(self.items, self.projection)
        holders = [e for e in items if e.role == "deco.defs"]
        defs = next((e for e in items if e.role == "figure.defs"), None)
        if not holders or defs is None:
            return items  # no figure <defs>: they stay inline, which SVG allows
        known = {c.attrs.get("id") for c in defs.children}
        for h in holders:
            for c in h.children:
                if c.attrs.get("id") not in known:
                    defs.children.append(c)
                    known.add(c.attrs.get("id"))
        return [e for e in items if e.role != "deco.defs"]

    def _root(self):
        role = (f'role="graphics-document" aria-roledescription="{_attr(self.kind)}"' if self.kind else 'role="img"')
        return role + (' data-legibility="all"' if self.legible else "")

    def add(self, *elements):
        self.items.extend(elements)

    def insert(self, index, elements):
        self.items[index:index] = list(elements)

    def etree(self):
        """The drawing as an element tree, for the audit (D5: nothing re-parses its own SVG). It holds
        what svg() would write, after the projection stage."""
        import xml.etree.ElementTree as ET
        root = ET.Element("svg", {"viewBox": f"0 0 {fmt(self.width)} {fmt(self.height)}", "width": fmt(self.width)})
        if self.legible:
            root.set("data-legibility", "all")
        ET.SubElement(root, "title").text = self.title or None
        ET.SubElement(root, "desc").text = self.desc or None
        root.extend(e.etree(bool(self.kind)) for e in self._items())
        return root

    def svg(self):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" {self._root()} viewBox="0 0 {fmt(self.width)} {fmt(self.height)}" '
                f'width="{fmt(self.width)}">')
        lines = [head, f"<title>{_text(self.title)}</title>", f"<desc>{_text(self.desc)}</desc>"]
        lines += [e.svg(bool(self.kind)) for e in self._items()]
        lines.append("</svg>")
        return "\n".join(lines)


# ---------- painters: the parts flow, arch, seq and schema draw ----------

# A node shape: painter(theme, node id, node, cx, cy, w, h, corners, st=computed style) -> elements. A shape may paint
# several elements (a 3D solid paints one per face). Flow looks a node's "shape" up here.
SHAPES = Registry("shape")

def paper(t, W, H, fill=None):
    return el("rect", role="figure.paper", width=W, height=H, fill=fill or t["paper"])


def _head(mid, fill):
    """An arrowhead 10 by 7, its back notched a little, its tip just past the end of the line."""
    return el("marker", id=mid, markerWidth=10, markerHeight=7, refX=9, refY=3.5, orient="auto",
              markerUnits="userSpaceOnUse", children=[el("polygon", points="0 0,10 3.5,0 7,2 3.5", fill=fill)])


def marker_defs(t):
    """Arrowheads: muted, accent (focal), link (HTTP) and soft. A fixed size on any stroke."""
    return el("defs", role="figure.defs", children=[_head("a", t["muted"]), _head("aa", t["accent"]),
                                                    _head("al", t["link"]), _head("ar", t["soft"])])


def heading(t, title, subtitle, x=28, st=None, eyebrow=None):
    """Title and subtitle drawn on the figure, under an optional eyebrow (the figure label, "Fig. 3").
    Returns (elements, block height). st is the figure's computed style (Styler.figure); a bigger
    title takes more room."""
    ts = (st or {}).get("title") or {"font-size": 18, "font-weight": 600, "font-family": FONT, "color": t["ink"]}
    ss = (st or {}).get("sub") or {"font-size": 13, "font-family": FONT, "color": t["muted"]}
    out, y = [], 8
    if eyebrow:
        es = (st or {}).get("eyebrow") or {"font-size": 10, "font-weight": 600, "font-family": FONT, "color": t["muted"],
                                           "text-transform": "uppercase"}
        y += round(es["font-size"]) + 2
        e = text_el(transformed(eyebrow, es), es, "", "figure.eyebrow", x, y, anchor=None)
        e.attrs.setdefault("letter-spacing", ".08em")
        out.append(e)
    if title:
        y += round(ts["font-size"])
        out.append(text_el(transformed(title, ts), ts, "", "figure.title", x, y, anchor=None))
    if subtitle:
        y += max(18, round(ss["font-size"] * 1.4))
        out.append(text_el(transformed(subtitle, ss), ss, "", "figure.subtitle", x, y, anchor=None))
    return out, ((y + 16) if out else 8)


PAD_X, PAD_Y, MIN_H = 14, 10, 40  # a fitted box: room beside and above its text, and its least height
ICON_ROOM = 22  # beside the text, on both sides, when a box has an icon in its top corner
SNAP = 16  # fitted widths are a multiple of this, so boxes with similar names come out the same width


def _line_w(runs, st):
    """A line of (text, kind) runs measured in its text style."""
    from .text.measure import width
    return sum(width(transformed(text, st), st["font-size"], _bold(st), kind, st.get("font")) for text, kind in runs)


def tag_w(tag, st):
    """A tag's width: uppercase text with its letter spacing."""
    from .text.measure import width
    text = transformed(tag, st)
    return width(text, st["font-size"], True, "", st.get("font")) + float(st.get("letter-spacing") or 0) * len(text)


def tag_pitch(st):
    return round(st["font-size"] * 1.5)


def box_size(name, sub="", tag="", icon=None, st=None):
    """A box fitted to its text (w, h, side padding): the name wraps at the style's max-width, then as narrow
    as it can without taking another line, so its lines come out even. The box is as wide as its longest
    line (or tag) plus padding, in steps of SNAP, no narrower than min-width. A word too long for max-width
    widens the box rather than break. A style that sets width keeps it. The side padding returned is what
    node_box needs to wrap the text the same way."""
    c = (st or {}).get("computed") or {}
    pad = PAD_X + (ICON_ROOM if icon in ICONS else 0)
    hi = float(c.get("max-width") or 176)
    lo = min(float(c.get("min-width") or 0), hi)
    fixed = c.get("width")
    if not fixed:
        _, _, lab, sb = box_text(name, sub, hi, st, pad)
        word = max([_line_w([(wd, "")], lab) for wd in plain(name).split()] +
                   [_line_w([(wd, "")], sb) for wd in plain(sub or "").split()] + [0])
        hi = max(hi, min(2 * hi, -(-(word + 2 * pad + 1) // SNAP) * SNAP))
    w = float(fixed) if fixed else hi
    nl, sl, lab, sb = box_text(name, sub, w, st, pad)
    if not fixed:
        room = w - 2 * pad
        wraps = all((x.get("overflow") or "wrap") == "wrap" for x in (lab, sb))  # text cut to max-lines can't balance
        if wraps and (len(nl) > 1 or len(sl) > 1):  # balanced lines: the narrowest room that keeps as many
            short, room = 0, int(room)
            while room - short > 1:
                mid = (short + room) // 2
                a, b, _, _ = box_text(name, sub, mid + 2 * pad, st, pad)
                if len(a) == len(nl) and len(b) == len(sl):
                    room = mid
                else:
                    short = mid
            nl, sl, lab, sb = box_text(name, sub, room + 2 * pad, st, pad)
        need = max([_line_w(line, lab) for line in nl] + [_line_w(line, sb) for line in sl] +
                   ([tag_w(tag, st["tag"])] if tag else []))
        w = max(lo, min(hi, -(-(need + 2 * pad) // SNAP) * SNAP))
        pad = (w - room) / 2.0  # node_box wraps at w less this on each side: at room
    block = lab["pitch"] * len(nl) + (sb["pitch"] * len(sl) + 2 if sl else 0) + (tag_pitch(st["tag"]) if tag else 0)
    h = max(MIN_H, 2 * -(-(block + 2 * PAD_Y) // 2))
    return w, h, pad


DIAMOND_ROOM = 128  # where a fitted decision's question wraps


def diamond_size(name, st=None):
    """A decision fitted to its question (w, h, room): as tall as v1 drew it, and as wide as the
    rhombus must be for the text block to sit inside it, in steps of SNAP, from 112 to 192."""
    lines, lab = diamond_text(name, st, DIAMOND_ROOM)
    h = _diamond_h(name, st, DIAMOND_ROOM)
    a = max(_line_w(line, lab) for line in lines) / 2.0 + 6
    b = lab["pitch"] * len(lines) / 2.0 + 3
    half = a / max(0.2, 1 - b / (h / 2.0))
    return max(112, min(192, -(-2 * half // SNAP) * SNAP)), h, DIAMOND_ROOM


def node_box(t, x, y, w, h, name, sub="", tag="", focal=False, corners="editorial", nid=None, icon=None, rx=None,
             st=None, shape="rect", pad=None):
    """A node: paper underlay, the box, an optional icon in its top corner, then its text centered as one
    block: the tag above the name in small capitals, the wrapped name, the sub. st is the node's computed
    style (style.Styler.node); without it, the theme's v1 look. pad: the room beside the text, which sets
    where the name wraps (box_size gives it); v1 boxes keep 8 and their tag pill in the corner."""
    st = st or legacy_node_style(t, focal, corners)
    stroke = st["stroke"]
    radii = st.get("radii") if rx is None else rx
    rx = st["radius"] if rx is None else rx
    cx = x + w / 2
    own = nid or ""
    if radii is not None and deco.uniform(radii) is None:  # a radius per corner: the box is a path
        d = deco.rounded_rect(x, y, w, h, radii)
        out = [el("path", owner=own, role="node.underlay", d=d, fill=st["paper"]),
               el("path", owner=own, role="node.shape", d=d, fill=st["fill"], stroke=stroke,
                  stroke_width=st.get("stroke-width"), data_node=nid, data_label=plain(name) if nid is not None else None)]
        rx = radii
    else:
        out = [el("rect", owner=own, role="node.underlay", x=x, y=y, width=w, height=h, rx=rx, fill=st["paper"]),
               el("rect", owner=own, role="node.shape", x=x, y=y, width=w, height=h, rx=rx, fill=st["fill"],
                  stroke=stroke, stroke_width=st.get("stroke-width"), data_node=nid,
                  data_label=plain(name) if nid is not None else None)]
    out += deco.decorate(out[1], out[0], st, lambda fill: el(out[1].tag, owner=own, role="node.pattern",
                                                         **{k: v for k, v in out[1].attrs.items()
                                                            if k in ("x", "y", "width", "height", "rx", "d")}, fill=fill))
    out += _sides(out[1], lambda: deco.rect_sides(x, y, w, h, rx), st, shape, own)
    if pad is not None:
        return out + _box_body(x, y, w, h, name, sub, tag, icon, stroke, own, st, pad)
    if tag:
        tw = max(28, len(tag) * 7)
        tg = st["tag"]
        out.append(el("rect", owner=own, role="node.tag", x=x + 8, y=y + 6, width=tw, height=12, rx=2, fill="none",
                      stroke=stroke, stroke_opacity=".4", stroke_width=".8"))
        out.append(el("text", transformed(tag, tg), owner=own, role="node.tag", x=x + 8 + tw / 2, y=y + 15,
                      font_size=tg["font-size"], font_family=tg["font-family"], fill=tg.get("color") or stroke,
                      text_anchor="middle"))
    if icon in ICONS:
        out.append(el("path", owner=own, role="node.icon", d=ICONS[icon], transform=f"translate({x + w - 24},{y + 5})",
                      fill="none", stroke=stroke, stroke_opacity=".75", stroke_width=1.3, stroke_linecap="round",
                      stroke_linejoin="round"))
    # the wrapped name and sub, centered in the space below the tag and icon
    nl, sl, lab_box, sb_box = box_text(name, sub, w, st)
    block = lab_box["pitch"] * len(nl) + (sb_box["pitch"] * len(sl) + 2 if sl else 0)
    top = y + (20 if tag or icon in ICONS else 8)
    base = top + max(0.0, (y + h - 8 - top - block) / 2.0) + lab_box["font-size"] - 1
    lab = dict(st["label"], **{"font-size": lab_box["font-size"]})
    sb = dict(st["sub"], **{"font-size": sb_box["font-size"]})
    for i, line in enumerate(nl):
        out.append(runs_el(line, lab, own, "node.label", cx, round(base + lab_box["pitch"] * i, 1)))
    for i, line in enumerate(sl):
        out.append(runs_el(line, sb, own, "node.sub", cx,
                           round(base + lab_box["pitch"] * len(nl) + 2 + sb_box["pitch"] * i, 1)))
    return out


def _baseline(top, pitch, size):
    """Where a line of text sits in its pitch: its capitals centered."""
    return round(top + pitch / 2.0 + size * 0.36, 1)


def _box_body(x, y, w, h, name, sub, tag, icon, stroke, own, st, pad):
    """A fitted box's icon and text: the tag, name and sub as one block, centered both ways."""
    out = []
    cx = x + w / 2
    if icon in ICONS:
        out.append(el("path", owner=own, role="node.icon", d=ICONS[icon], transform=f"translate({x + w - 22},{y + 6})",
                      fill="none", stroke=stroke, stroke_opacity=".75", stroke_width=1.3, stroke_linecap="round",
                      stroke_linejoin="round"))
    nl, sl, lab_box, sb_box = box_text(name, sub, w, st, pad)
    tg = st["tag"]
    tp = tag_pitch(tg) if tag else 0
    block = tp + lab_box["pitch"] * len(nl) + (sb_box["pitch"] * len(sl) + 2 if sl else 0)
    top = y + (h - block) / 2.0
    if tag:
        e = text_el(transformed(tag, tg), tg, own, "node.tag", cx, _baseline(top - 1, tp, tg["font-size"]))
        out.append(e)
        top += tp
    lab = dict(st["label"], **{"font-size": lab_box["font-size"]})
    sb = dict(st["sub"], **{"font-size": sb_box["font-size"]})
    for i, line in enumerate(nl):
        out.append(runs_el(line, lab, own, "node.label", cx, _baseline(top, lab_box["pitch"], lab_box["font-size"])))
        top += lab_box["pitch"]
    top += 2
    for i, line in enumerate(sl):
        out.append(runs_el(line, sb, own, "node.sub", cx, _baseline(top, sb_box["pitch"], sb_box["font-size"])))
        top += sb_box["pitch"]
    return out


def diamond(t, cx, cy, w, h, name, focal=False, nid=None, st=None, room=100):
    """A decision: paper underlay, the rhombus, and the question inside, wrapped at room."""
    st = st or legacy_node_style(t, focal)
    pts = f"{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}"
    own = nid or ""
    out = [el("polygon", owner=own, role="node.underlay", points=pts, fill=st["paper"]),
           el("polygon", owner=own, role="node.shape", points=pts, fill=st["fill"], stroke=st["stroke"],
              stroke_width=st.get("stroke-width"), data_node=nid, data_label=plain(name) if nid is not None else None,
              data_cx=cx if nid is not None else None, data_cy=cy if nid is not None else None)]
    out += deco.decorate(out[1], out[0], st, lambda fill: el("polygon", owner=own, role="node.pattern", points=pts, fill=fill))
    out += _sides(out[1], lambda: deco.diamond_sides(cx, cy, w, h), st, "diamond", own)
    lines, lab_box = diamond_text(name, st, room)
    y0 = cy + lab_box["font-size"] / 3 - lab_box["pitch"] / 2 * (len(lines) - 1)
    lab = dict(st["label"], **{"font-size": lab_box["font-size"]})
    for i, line in enumerate(lines):
        out.append(runs_el(line, lab, own, "node.label", cx, round(y0 + lab_box["pitch"] * i, 1)))
    return out
def dot(t, cx, cy, nid=None, st=None):
    """A merge point."""
    fill = st["fill"] if st else t["ink"]
    return [el("circle", owner=nid or "", role="node.shape", cx=cx, cy=cy, r=4, fill=fill)]
def edge_path(d, color, marker, owner="", dashed=False, attrs=None, width=1.8, dash=None):
    """An arrow's line; attrs are its data-* attributes (from, to, label). dash is a dash list from
    the style (stroke-dasharray); dashed alone draws v1's 5,4."""
    pattern = ",".join(fmt(v) for v in dash) if dash else ("5,4" if dashed else None)
    return el("path", owner=owner, role="edge.path", d=d, fill="none", stroke=color, stroke_width=width,
              stroke_dasharray=pattern, marker_end=f"url(#{marker})", **(attrs or {}))
def tail(x, y, side, color, owner=""):
    """The small dot where an arrow leaves its box."""
    vx, vy = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}[side]
    return el("circle", owner=owner, role="edge.tail", cx=x + vx * 7, cy=y + vy * 7, r=2.7, fill=color)


def arrow_label(t, mx, ay, text, vertical=False, flip=False, owner="", st=None, pill=None, w=None, gap=None):
    """A label off the shaft, on a paper pill, so it does not cut the arrow. st is the edge's
    ::label style; text arrives already transformed (the placement measured it). w and gap: the pill's
    width and its distance from the arrow (route.labels), when the label hugs its arrow; else v1's."""
    st = st or {"font-size": 10, "font-family": MONO, "color": t["muted"]}
    if w is None:
        x0, y0, _, _ = _label_box(mx, ay, text, vertical, flip)
        w = _pill_w(text)
    else:
        from .route.labels import label_box
        x0, y0, _, _ = label_box(mx, ay, text, vertical, flip, w, gap)
    return [el("rect", owner=owner, role="edge.label.pill", x=x0, y=y0, width=w, height=16, rx=2, fill=pill or t["paper"]),
            el("text", text, owner=owner, role="edge.label", x=x0 + w / 2, y=y0 + 12, data_shaping=_shaping(text),
               font_size=st["font-size"],
               font_family=st["font-family"], font_weight=st.get("font-weight"), fill=st["color"], text_anchor="middle")]



def _sides(shape_el, geometry, st, shape, owner):
    """Border sides (DESIGN 5.5): when a style sets any border-*, the outline is drawn side by side and
    the shape itself keeps only its fill. geometry() gives each side's path, worked out only then."""
    sides = deco.declared(st.get("computed") or {}, shape)
    if not sides:
        return []
    out = deco.borders(geometry(), sides, shape_el.attrs.get("stroke"), st.get("stroke-width"), st["paper"], owner)
    shape_el.attrs["stroke"] = "none"
    shape_el.attrs["stroke-width"] = None
    return out


def legacy_node_style(t, focal=False, corners="editorial"):
    """A node's style from a v1 theme dict alone: what the painters drew before stylesheets."""
    return {"fill": t["accent_tint"] if focal else t["card"], "stroke": t["accent"] if focal else t["ink"],
            "stroke-width": None, "radius": corner_rx(corners), "paper": t["paper"],
            "label": {"font-family": SANS, "font-size": 12, "font-weight": 600, "color": t["ink"]},
            "sub": {"font-family": MONO, "font-size": 9, "color": t["muted"]},
            "tag": {"font-family": FONT, "font-size": 8, "color": None}}


def transformed(text, st):
    """Text with the style's text-transform applied."""
    mode = (st or {}).get("text-transform")
    if mode == "uppercase":
        return str(text).upper()
    if mode == "lowercase":
        return str(text).lower()
    if mode == "capitalize":
        return " ".join(w[:1].upper() + w[1:] for w in str(text).split(" "))
    return text


CODE_FONT = "ui-monospace, 'Cascadia Code', Consolas, monospace"


def runs_el(runs, st, owner, role, x, y, anchor="middle"):
    """A line of (text, kind) runs: plain text as one text element, markup as tspans in it."""
    if len(runs) == 1 and runs[0][1] == "":
        return text_el(transformed(runs[0][0], st), st, owner, role, x, y, anchor)
    e = text_el(None, st, owner, role, x, y, anchor)
    e.children = [el("tspan", transformed(t, st), font_weight="700" if k == "b" else None,
                     font_style="italic" if k == "i" else None, font_family=CODE_FONT if k == "m" else None)
                  for t, k in runs]
    return e


def _shaping(text):
    """The scripts in a text whose widths are estimates without a shaper, for the audit, or None."""
    if not text or max(map(ord, str(text))) < 0x0600:
        return None
    from .text.shaper import shape
    scripts = shape(text)["scripts"]
    return ", ".join(scripts) if scripts else None


def text_el(text, st, owner, role, x, y, anchor="middle"):
    """A text element in a computed text style: size, weight, family, then style and spacing if set."""
    return el("text", text, owner=owner, role=role, x=x, y=y, data_shaping=_shaping(text),
              font_size=st["font-size"], font_weight=st.get("font-weight"),
              font_family=st["font-family"], font_style=st.get("font-style"), letter_spacing=st.get("letter-spacing"),
              fill=st["color"], text_anchor=anchor, data_color_from=st.get("color-from"),
              data_size_from=st.get("font-size-from"), data_font_fallback=st.get("font-fallback"))


def add_markers(defs, colors):
    """Arrowheads for stroke colors the default four don't cover: {color: id}, into the defs element."""
    for color, mid in colors.items():
        defs.children.append(_head(mid, color))


def named(els, kind, name, role="node.shape"):
    """Give the part's main element (by role) its accessible name, and return the elements."""
    for e in els:
        if e.role == role:
            e.a11y = {"name": name, "kind": kind}
            break
    return els


def node_name(n, nid=None):
    """A node as a reader hears it: its name, then its sub-label."""
    name = plain(n.get("name", nid if nid is not None else n.get("id", "")))
    return name + (f", {n['sub']}" if n.get("sub") else "")


@SHAPES.add("rect")
def _rect(t, nid, n, cx, cy, w, h, corners="editorial", rx=None, kind="box", st=None, shape="rect"):
    return named(node_box(t, cx - w / 2, cy - h / 2, w, h, n["name"], n.get("sub", ""), n.get("tag", ""),
                          n.get("focal", False), corners, nid, n.get("icon"), rx=rx, st=st, shape=shape,
                          pad=n.get("_pad")), kind,
                 node_name(n, nid))


@SHAPES.add("oval")
def _oval(t, nid, n, cx, cy, w, h, corners="editorial", st=None):
    return _rect(t, nid, n, cx, cy, w, h, corners, rx=None if st else 20, kind="start or end", st=st, shape="oval")


@SHAPES.add("diamond")
def _diamond(t, nid, n, cx, cy, w, h, corners="editorial", st=None):
    return named(diamond(t, cx, cy, w, h, n["name"], n.get("focal", False), nid, st=st, room=n.get("_room", 100)), "decision",
                 node_name(n, nid))


@SHAPES.add("dot")
def _dot(t, nid, n, cx, cy, w, h, corners="editorial", st=None):
    return named(dot(t, cx, cy, nid, st=st), "merge point", node_name(n, nid))

def table_card(t, x, y, w, h, rx, tid, tbl, row_h, st=None):
    """A table: card, tinted header with the name and an optional tag, then one row per column
    with a PK or FK badge, the column name and its type. st: the table's computed style."""
    focal = tbl.get("focal", False)
    st = st or {"fill": t["card"], "stroke": t["accent"] if focal else t["ink"], "stroke-width": 1.2, "radius": rx,
                "header": t["accent_tint"] if focal else "rgba(45,49,66,0.06)",
                "label": {"font-family": SANS, "font-size": 13, "font-weight": 600, "color": t["ink"]},
                "tag": {"font-family": MONO, "font-size": 8, "color": None}}
    stroke = st["stroke"]
    rx = st["radius"] if st.get("radius") is not None else rx
    fill_head = st["header"]
    cols = ", ".join(str(c.get("name", "")) + (" (primary key)" if c.get("pk") else " (foreign key)" if c.get("fk") else "")
                     for c in tbl.get("columns", []))
    out = [el("rect", owner=tid, role="table.card", x=x, y=y, width=w, height=h, rx=rx, fill=st["fill"], stroke=stroke,
              stroke_width=st["stroke-width"], data_node=tid, data_label=tbl.get("name", tid),
              a11y={"name": f"{tbl.get('name', tid)}" + (f": {cols}" if cols else ""), "kind": "table"}),
           el("path", owner=tid, role="table.header",
              d=f"M{x},{y + 36} L{x},{y + rx} Q{x},{y} {x + rx},{y} L{x + w - rx},{y} Q{x + w},{y} {x + w},{y + rx} L{x + w},{y + 36} Z",
              fill=fill_head),
           el("line", owner=tid, role="table.rule", x1=x, y1=y + 36, x2=x + w, y2=y + 36, stroke=t["rule"], stroke_width=1),
           el("text", transformed(tbl.get("name", tid), st["label"]), owner=tid, role="table.name", x=x + 12, y=y + 23,
              font_size=st["label"]["font-size"], font_weight=st["label"].get("font-weight"),
              font_family=st["label"]["font-family"], fill=st["label"]["color"], data_role="table",
              data_color_from=st["label"].get("color-from"), data_size_from=st["label"].get("font-size-from"),
              data_font_fallback=st["label"].get("font-fallback"))]
    paper = el("rect", owner=tid, role="node.underlay", x=x, y=y, width=w, height=h, rx=rx, fill=st.get("paper") or t["paper"])
    decor = deco.decorate(out[0], paper, st, lambda fill: el("rect", owner=tid, role="node.pattern", x=x, y=y, width=w,
                                                            height=h, rx=rx, fill=fill))
    card = 0
    if paper.attrs.get("filter"):  # a shadow needs something under the card to cast it
        out.insert(0, paper)
        card = 1
    after = card + 3  # the card, its header band, and the rule under the header
    out[after:after] = decor + _sides(out[card], lambda: deco.rect_sides(x, y, w, h, rx), st, "table", tid)
    ink, soft = on_fill(t["ink"], st["fill"], t), on_fill(t["soft"], st["fill"], t)  # the rows' text, on the card
    tag = tbl.get("tag", "")
    if tag:  # in small capitals at the header's right end
        tg = dict(st["tag"], color=st["tag"].get("color") or t["muted"])
        out.append(text_el(transformed(tag, tg), tg, tid, "table.tag", x + w - 12, y + 22, anchor="end"))
    for c_idx, c in enumerate(tbl.get("columns", [])):
        cy = y + 44 + c_idx * row_h
        own = f'{tid}.{c.get("name", c_idx)}'
        if c_idx > 0:
            out.append(el("line", owner=own, role="column.rule", x1=x + 6, y1=cy, x2=x + w - 6, y2=cy, stroke=t["rule"],
                          stroke_width=0.5))
        badge_x = x + 10
        for key, color in (("pk", t["accent"]), ("fk", t["link"])):
            if c.get(key) and (key == "pk" or not c.get("pk")):
                out.append(el("rect", owner=own, role="column.badge", x=badge_x, y=cy + 5, width=22, height=14, rx=3, fill=color,
                              fill_opacity=".15"))
                out.append(el("text", key.upper(), owner=own, role="column.badge", x=badge_x + 11, y=cy + 15.2, font_size=9,
                              font_weight=700, font_family=MONO, fill=readable_on_tint(color, st["fill"]),
                              text_anchor="middle"))
                break
        name_x = badge_x + (28 if (c.get("pk") or c.get("fk")) else 0)
        out.append(el("text", c["name"], owner=own, role="column.name", x=name_x, y=cy + 15, font_size=11, font_family=MONO,
                      fill=ink))
        out.append(el("text", c.get("type", ""), owner=own, role="column.type", x=x + w - 12, y=cy + 15, font_size=10,
                      font_family=MONO, fill=soft, text_anchor="end"))
    return out


def on_fill(fg, fill, t):
    """A theme text color that reads on fill (a stylesheet's or a scale's): fg if it meets WCAG AA,
    else ink, paper, black or white (style.parse.readable). A fill it can't read keeps fg."""
    from .style.parse import color, readable
    try:
        fg_c, bg = color(fg), color(fill)
    except Exception:
        return fg
    pick = readable(fg_c, bg, color(t["ink"]), color(t["paper"]))
    return fg if pick is fg_c else pick.css


def readable_on_tint(fg, card, alpha=0.15):
    """fg, darkened or lightened until it reads at WCAG AA (4.5:1) on a badge of fg at alpha over card."""
    import colorsys
    from .style.parse import Color, color, contrast
    try:
        c, base = color(fg), color(card)
    except Exception:
        return fg
    bg = Color(round(base.r + (c.r - base.r) * alpha), round(base.g + (c.g - base.g) * alpha),
               round(base.b + (c.b - base.b) * alpha))
    h, light, sat = colorsys.rgb_to_hls(c.r / 255, c.g / 255, c.b / 255)
    step = -0.02 if colorsys.rgb_to_hls(bg.r / 255, bg.g / 255, bg.b / 255)[1] > 0.5 else 0.02
    while contrast(c, bg) < 4.5 and 0.0 < light < 1.0:
        light = min(1.0, max(0.0, light + step))
        r, g, b = colorsys.hls_to_rgb(h, light, sat)
        c = Color(round(r * 255), round(g * 255), round(b * 255))
    return c.css


def frame_title(g, ts):
    """(text, width) of a group's title as its frame draws it, ts its title style."""
    label = transformed((g["tag"] + "  " if g.get("tag") else "") + str(g["name"]), ts)
    return label, _text_w(label, ts["font-size"], True) + 0.4 * len(label)


def group_frames(t, groups, pos, avoid=(), style_of=None, boxes=None):
    """A frame behind each group's members. Its name goes in the top corner (left, else right)
    that no arrow crosses; avoid holds the arrows' segment boxes. style_of(gid) gives a group's
    computed style (Styler.group). boxes: {group id: (x0, y0, x1, y1)} when a layout placed the
    frames; otherwise each frame is drawn around its members."""
    out = []
    for g in groups:
        gs = style_of(g["id"]) if style_of else {
            "fill": t["rule"], "stroke": t["muted"], "dasharray": [4, 3], "radius": 10,
            "title": {"font-size": 10, "font-weight": 600, "font-family": FONT, "color": t["muted"],
                      "text-transform": "uppercase"}}
        f = boxes.get(g["id"]) if boxes is not None else _frame_box(g, pos)
        if not f:
            continue
        x0, y0, x1, y1 = f
        names = ", ".join(str(pos[m][2].get("name", m)) if m in pos else str(m) for m in g["members"])
        out.append(el("rect", owner=g["id"], role="group.frame", x=x0, y=y0, width=x1 - x0, height=y1 - y0, rx=gs["radius"],
                      fill=gs["fill"], fill_opacity=".35", stroke=gs["stroke"], stroke_opacity=".55",
                      stroke_dasharray=",".join(fmt(v) for v in gs["dasharray"]) if gs["dasharray"] else None,
                      data_group=g["id"], data_name=g["name"], data_members=",".join(g["members"]),
                      a11y={"name": f"{g['name']}: {names}", "kind": "group"}))
        ts = gs["title"]
        label, lw = frame_title(g, ts)

        def hits(lx):
            b = (lx - 8, y0 + 3, lx + lw + 8, y0 + 19)  # keep clear of arrows, not just off them
            return sum(1 for a in avoid if b[0] < a[2] and a[0] < b[2] and b[1] < a[3] and a[1] < b[3])
        # left corner if it is clear, else the nearest clear spot along the top band, else the least crossed
        spots = [x0 + 10] + [x0 + 10 + 8 * k for k in range(1, int(max(0, x1 - 20 - lw - x0) // 8) + 1)]
        lx = min(spots, key=lambda v: (hits(v), v - x0))
        out.append(el("text", label, owner=g["id"], role="group.title", x=lx, y=y0 + 15, font_size=ts["font-size"],
                      font_weight=ts.get("font-weight"), font_family=ts["font-family"], fill=ts["color"],
                      letter_spacing=ts.get("letter-spacing") if ts.get("letter-spacing") is not None else ".04em"))
    return out


def note_rail(t, notes, rail_x, top, lh=92, st=None):
    """Right-rail notes: an italic note and a thin leader to (ax, ay). notes = [(ax, ay, text)]. st is
    the annotation style (Styler.figure()["note"])."""
    st = st or {"font-size": 13, "font-style": "italic", "font-family": SERIF, "color": t["ink"], "stroke": t["soft"],
                "fill": t["accent"]}
    out = []
    for i, (ax, ay, text) in enumerate(notes):
        ry = top + 14 + i * lh
        tx = rail_x + 14
        out.append(el("line", role="note.leader", x1=ax, y1=ay, x2=tx, y2=ry, stroke=st["stroke"], stroke_width=1))
        out.append(el("circle", role="note.dot", cx=ax, cy=ay, r=2.5, fill=st["fill"]))
        for j, ln in enumerate(_wrap(text)):
            out.append(el("text", transformed(ln, st), role="note.text", x=tx, y=ry + 4 + j * 16, font_size=st["font-size"],
                          font_style=st.get("font-style"), font_weight=st.get("font-weight"), font_family=st["font-family"],
                          fill=st["color"]))
    return out


# the words today's legends use for the default themes' colors; any other color is named by its hue
COLOR_WORDS = {"#eb6c36": "coral", "#f08a59": "coral", "#2e5aa8": "blue", "#6a95d8": "blue"}


def color_word(css):
    """A color as a legend names it: "coral", "blue", or, for any other color, its hue."""
    import colorsys
    if css in COLOR_WORDS:
        return COLOR_WORDS[css]
    try:
        from .style.parse import color
        c = color(css)
    except Exception:
        return "colored"
    h, light, sat = colorsys.rgb_to_hls(c.r / 255, c.g / 255, c.b / 255)
    if sat < 0.15 or light < 0.08 or light > 0.95:
        return "black" if light < 0.15 else "dark grey" if light < 0.4 else "grey" if light < 0.75 else "light grey"
    hue = h * 360
    for top, word in ((15, "red"), (40, "orange"), (65, "yellow"), (170, "green"), (200, "teal"), (255, "blue"),
                      (290, "purple"), (335, "pink"), (361, "red")):
        if hue < top:
            return word
    return "colored"


LEGEND_ROW = 18


def _legend_items(entries, t):
    """(width, painter) per legend item; painter(x, y) gives its elements at that spot."""
    muted, soft = t["muted"], t["soft"]
    items = []
    for e in entries:
        if e["type"] == "rule":
            look, text = e["look"], e["text"]

            def swatch(x, y, look=look, text=text):
                if "border" in look:
                    bar = {"top": (0, 0, 14, 3), "bottom": (0, 7, 14, 3), "left": (0, 0, 3, 10), "right": (11, 0, 3, 10)}
                    bx, by, bw, bh = bar.get(look["side"], (0, 0, 14, 3))
                    marks = [el("rect", role="legend.swatch", x=x, y=y - 9, width=14, height=10, fill="none",
                                stroke=soft, stroke_width=0.8),
                             el("rect", role="legend.swatch", x=x + bx, y=y - 9 + by, width=bw, height=bh, fill=look["border"])]
                else:
                    marks = [el("rect", role="legend.swatch", x=x, y=y - 9, width=14, height=10, rx=2,
                                fill=look.get("fill") or "none", stroke=look.get("stroke") or soft, stroke_width=0.8)]
                return marks + [el("text", text, role="legend.text", x=x + 20, y=y, font_size=11, font_family=FONT,
                                   fill=muted)]
            items.append((20 + _text_w(text, 11) + 18, swatch))
        else:
            label = f"{e['field']}:"
            width = _text_w(label, 11) + 8
            parts = [(0, lambda x, y, label=label: [el("text", label, role="legend.text", x=x, y=y, font_size=11,
                                                            font_family=FONT, fill=muted)])]
            for text, value in e["steps"]:
                offset = width

                def step(x, y, text=text, value=value):
                    if hasattr(value, "css"):
                        mark = el("rect", role="legend.swatch", x=x, y=y - 9, width=12, height=10, rx=2, fill=value.css,
                                  stroke=soft, stroke_width=0.5)
                    else:
                        mark = el("line", role="legend.swatch", x1=x, y1=y - 4, x2=x + 12, y2=y - 4, stroke=muted,
                                  stroke_width=round(float(value), 2))
                    return [mark, el("text", text, role="legend.text", x=x + 16, y=y, font_size=11, font_family=FONT,
                                     fill=muted)]
                parts.append((offset, step))
                width += 16 + _text_w(text, 11) + 10

            def scale(x, y, parts=parts):
                return [e2 for off, fn in parts for e2 in fn(x + off, y)]
            items.append((width + 14, scale))
    return items


def legend_rows(t, entries, x, y, max_w):
    """The legend beyond the sentence: swatches for rules with a legend text and for encodings.
    Returns (elements, height); wraps to more rows when one would run past max_w."""
    out, cx, cy, rows = [], x, y, 1 if entries else 0
    for width, paint_item in _legend_items(entries, t):
        if cx > x and cx + width > x + max_w:
            cx, cy, rows = x, cy + LEGEND_ROW, rows + 1
        out += paint_item(cx, cy)
        cx += width
    return out, rows * LEGEND_ROW


def legend_height(t, entries, max_w):
    return legend_rows(t, entries, 0, 0, max_w)[1]


def caption_lines(text, width, st):
    """A caption wrapped to the figure's width at its style's size: nothing is cut."""
    from ._text import _wrap_px
    return _wrap_px(text, width, st["font-size"], False, 10 ** 6) if text else []


def caption(t, lines, x, y, st):
    """The caption under the figure, one text element per line."""
    return [el("text", transformed(ln, st), role="figure.caption", x=x, y=round(y + k * (st["font-size"] + 4), 1),
               font_size=st["font-size"], font_style=st.get("font-style"), font_family=st["font-family"], fill=st["color"])
            for k, ln in enumerate(lines)]


def legend_line(t, W, rule_y, text_y, text, st=None):
    """The rule and one-line key at the bottom of a diagram. st is the legend style."""
    st = st or {"font-size": 11, "font-family": FONT, "color": t["muted"], "stroke": t["rule"]}
    return [el("line", role="legend.rule", x1=30, y1=rule_y, x2=W - 30, y2=rule_y, stroke=st["stroke"], stroke_width=".8"),
            text_el(transformed(text, st), st, "", "legend.text", 30, text_y, anchor=None)]

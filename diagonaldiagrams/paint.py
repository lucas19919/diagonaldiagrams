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
"""
import re

from ._draw import ICONS, _box_lines, _diamond_lines, _frame_box, _label_box, _pill_w, corner_rx
from ._text import _text_w, _wrap
from ._theme import FONT, MONO, SANS, SERIF

_NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
GEOMETRY = ("d", "points", "transform", "viewBox")  # strings whose numbers are written canonically


def fmt(v):
    """A number as SVG text: at most two decimals, no trailing zeros, no "-0"."""
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


class Element:
    """One SVG element. depth and pts3d are the 3D hooks: a face's 3D corners, and its distance from
    the viewer once projected (0 in 2D)."""
    __slots__ = ("tag", "attrs", "text", "children", "owner", "role", "depth", "pts3d")

    def __init__(self, tag, attrs=None, text=None, children=None, owner="", role="", depth=0.0, pts3d=None):
        self.tag, self.attrs, self.text, self.children = tag, attrs if attrs is not None else {}, text, children or []
        self.owner, self.role, self.depth, self.pts3d = owner, role, depth, pts3d

    def __repr__(self):
        return f"Element({self.tag!r}, owner={self.owner!r}, role={self.role!r})"

    def values(self):
        """Attribute values as the SVG text will hold them (numbers canonical, not yet escaped)."""
        return {k: (fmt(v) if isinstance(v, (int, float)) else (_numbers(v) if k in GEOMETRY else str(v)))
                for k, v in self.attrs.items() if v is not None}

    def etree(self):
        """This element as an ElementTree element, equal to what parsing svg() would give."""
        import xml.etree.ElementTree as ET
        node = ET.Element(self.tag, self.values())
        node.text = self.text or None
        node.extend(c.etree() for c in self.children)
        return node

    def svg(self):
        parts = [f' {k}="{_attr(v)}"' for k, v in self.values().items()]
        head = f"<{self.tag}{''.join(parts)}"
        if self.text is None and not self.children:
            return head + "/>"
        return head + ">" + _text(self.text or "") + "".join(c.svg() for c in self.children) + f"</{self.tag}>"


def el(tag, text=None, owner="", role="", children=None, **attrs):
    """An Element; attribute names are written with dashes (stroke_width -> stroke-width)."""
    return Element(tag, {k.replace("_", "-"): v for k, v in attrs.items()}, text, children or [], owner, role)


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
    paint order, and the projection (None in 2D)."""
    __slots__ = ("width", "height", "title", "desc", "items", "projection")

    def __init__(self, width, height, title="", desc="", items=None, projection=None):
        self.width, self.height, self.title, self.desc = width, height, title, desc
        self.items, self.projection = list(items or []), projection

    def add(self, *elements):
        self.items.extend(elements)

    def insert(self, index, elements):
        self.items[index:index] = list(elements)

    def etree(self):
        """The drawing as an element tree, for the audit (D5: nothing re-parses its own SVG). It holds
        what svg() would write, after the projection stage."""
        import xml.etree.ElementTree as ET
        root = ET.Element("svg", {"viewBox": f"0 0 {fmt(self.width)} {fmt(self.height)}", "width": fmt(self.width)})
        ET.SubElement(root, "title").text = self.title or None
        ET.SubElement(root, "desc").text = self.desc or None
        root.extend(e.etree() for e in project(self.items, self.projection))
        return root

    def svg(self):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {fmt(self.width)} {fmt(self.height)}" '
                f'width="{fmt(self.width)}">')
        lines = [head, f"<title>{_text(self.title)}</title>", f"<desc>{_text(self.desc)}</desc>"]
        lines += [e.svg() for e in project(self.items, self.projection)]
        lines.append("</svg>")
        return "\n".join(lines)


# ---------- painters: the parts flow, arch, seq and schema draw ----------

def paper(t, W, H):
    return el("rect", role="figure.paper", width=W, height=H, fill=t["paper"])


def marker_defs(t):
    """Arrowheads: muted, accent (focal), link (HTTP) and soft. A fixed size on any stroke."""
    def one(mid, fill):
        return el("marker", id=mid, markerWidth=12, markerHeight=9, refX=11, refY=4.5, orient="auto",
                  markerUnits="userSpaceOnUse", children=[el("polygon", points="0 0,12 4.5,0 9", fill=fill)])
    return el("defs", role="figure.defs", children=[one("a", t["muted"]), one("aa", t["accent"]),
                                                    one("al", t["link"]), one("ar", t["soft"])])


def heading(t, title, subtitle, x=28):
    """Title and subtitle drawn on the figure. Returns (elements, block height)."""
    out, y = [], 8
    if title:
        y += 18
        out.append(el("text", title, role="figure.title", x=x, y=y, font_size=18, font_weight=600,
                      font_family=FONT, fill=t["ink"]))
    if subtitle:
        y += 18
        out.append(el("text", subtitle, role="figure.subtitle", x=x, y=y, font_size=13, font_family=FONT,
                      fill=t["muted"]))
    return out, ((y + 16) if out else 8)


def node_box(t, x, y, w, h, name, sub="", tag="", focal=False, corners="editorial", nid=None, icon=None, rx=None):
    """A node: paper underlay, the box, an optional tag pill and icon, then the wrapped name and sub."""
    fill = t["accent_tint"] if focal else t["card"]
    stroke = t["accent"] if focal else t["ink"]
    rx = corner_rx(corners) if rx is None else rx
    cx = x + w / 2
    own = nid or ""
    out = [el("rect", owner=own, role="node.underlay", x=x, y=y, width=w, height=h, rx=rx, fill=t["paper"]),
           el("rect", owner=own, role="node.shape", x=x, y=y, width=w, height=h, rx=rx, fill=fill, stroke=stroke,
              data_node=nid, data_label=name if nid is not None else None)]
    if tag:
        tw = max(28, len(tag) * 7)
        out.append(el("rect", owner=own, role="node.tag", x=x + 8, y=y + 6, width=tw, height=12, rx=2, fill="none",
                      stroke=stroke, stroke_opacity=".4", stroke_width=".8"))
        out.append(el("text", tag, owner=own, role="node.tag", x=x + 8 + tw / 2, y=y + 15, font_size=8, font_family=FONT,
                      fill=stroke, text_anchor="middle"))
    if icon in ICONS:
        out.append(el("path", owner=own, role="node.icon", d=ICONS[icon], transform=f"translate({x + w - 24},{y + 5})",
                      fill="none", stroke=stroke, stroke_opacity=".75", stroke_width=1.3, stroke_linecap="round",
                      stroke_linejoin="round"))
    # the wrapped name and sub, centered in the space below the tag and icon
    nl, sl = _box_lines(name, sub, w)
    block = 15 * len(nl) + (12 * len(sl) + 2 if sl else 0)
    top = y + (20 if tag or icon in ICONS else 8)
    base = top + max(0.0, (y + h - 8 - top - block) / 2.0) + 11
    for i, line in enumerate(nl):
        out.append(el("text", line, owner=own, role="node.label", x=cx, y=round(base + 15 * i, 1), font_size=12,
                      font_weight=600, font_family=SANS, fill=t["ink"], text_anchor="middle"))
    for i, line in enumerate(sl):
        out.append(el("text", line, owner=own, role="node.sub", x=cx, y=round(base + 15 * len(nl) + 2 + 12 * i, 1),
                      font_size=9, font_family=MONO, fill=t["muted"], text_anchor="middle"))
    return out


def diamond(t, cx, cy, w, h, name, focal=False, nid=None):
    """A decision: paper underlay, the rhombus, and the wrapped question inside."""
    stroke = t["accent"] if focal else t["ink"]
    fill = t["accent_tint"] if focal else t["card"]
    pts = f"{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}"
    own = nid or ""
    out = [el("polygon", owner=own, role="node.underlay", points=pts, fill=t["paper"]),
           el("polygon", owner=own, role="node.shape", points=pts, fill=fill, stroke=stroke,
              data_node=nid, data_label=name if nid is not None else None,
              data_cx=cx if nid is not None else None, data_cy=cy if nid is not None else None)]
    lines = _diamond_lines(name)
    y0 = cy + 4 - 7.5 * (len(lines) - 1)
    for i, line in enumerate(lines):
        out.append(el("text", line, owner=own, role="node.label", x=cx, y=round(y0 + 15 * i, 1), font_size=12,
                      font_weight=600, font_family=SANS, fill=t["ink"], text_anchor="middle"))
    return out


def dot(t, cx, cy, nid=None):
    """A merge point."""
    return [el("circle", owner=nid or "", role="node.shape", cx=cx, cy=cy, r=4, fill=t["ink"])]


def edge_path(d, color, marker, owner="", dashed=False, attrs=None):
    """An arrow's line; attrs are its data-* attributes (from, to, label)."""
    return el("path", owner=owner, role="edge.path", d=d, fill="none", stroke=color, stroke_width=1.8,
              stroke_dasharray="5,4" if dashed else None, marker_end=f"url(#{marker})", **(attrs or {}))


def tail(x, y, side, color, owner=""):
    """The small dot where an arrow leaves its box."""
    vx, vy = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}[side]
    return el("circle", owner=owner, role="edge.tail", cx=x + vx * 7, cy=y + vy * 7, r=2.7, fill=color)


def arrow_label(t, mx, ay, text, vertical=False, flip=False, owner=""):
    """A label off the shaft, on a paper pill, so it does not cut the arrow."""
    x0, y0, _, _ = _label_box(mx, ay, text, vertical, flip)
    w = _pill_w(text)
    return [el("rect", owner=owner, role="edge.label.pill", x=x0, y=y0, width=w, height=16, rx=2, fill=t["paper"]),
            el("text", text, owner=owner, role="edge.label", x=x0 + w / 2, y=y0 + 12, font_size=10, font_family=MONO,
               fill=t["muted"], text_anchor="middle")]


def table_card(t, x, y, w, h, rx, tid, tbl, row_h):
    """A table: card, tinted header with the name and an optional tag, then one row per column
    with a PK or FK badge, the column name and its type."""
    focal = tbl.get("focal", False)
    stroke = t["accent"] if focal else t["ink"]
    fill_head = t["accent_tint"] if focal else "rgba(45,49,66,0.06)"
    out = [el("rect", owner=tid, role="table.card", x=x, y=y, width=w, height=h, rx=rx, fill=t["card"], stroke=stroke,
              stroke_width=1.2, data_node=tid, data_label=tbl.get("name", tid)),
           el("path", owner=tid, role="table.header",
              d=f"M{x},{y + 36} L{x},{y + rx} Q{x},{y} {x + rx},{y} L{x + w - rx},{y} Q{x + w},{y} {x + w},{y + rx} L{x + w},{y + 36} Z",
              fill=fill_head),
           el("line", owner=tid, role="table.rule", x1=x, y1=y + 36, x2=x + w, y2=y + 36, stroke=t["rule"], stroke_width=1),
           el("text", tbl.get("name", tid), owner=tid, role="table.name", x=x + 12, y=y + 23, font_size=13, font_weight=600,
              font_family=SANS, fill=t["ink"], data_role="table")]
    tag = tbl.get("tag", "")
    if tag:
        tw = max(32, len(tag) * 7 + 8)
        out.append(el("rect", owner=tid, role="table.tag", x=x + w - tw - 10, y=y + 12, width=tw, height=14, rx=2, fill="none",
                      stroke=stroke, stroke_opacity=".5", stroke_width=".8"))
        out.append(el("text", tag, owner=tid, role="table.tag", x=x + w - tw / 2 - 10, y=y + 22, font_size=8, font_family=MONO,
                      fill=stroke, text_anchor="middle"))
    for c_idx, c in enumerate(tbl.get("columns", [])):
        cy = y + 44 + c_idx * row_h
        own = f'{tid}.{c.get("name", c_idx)}'
        if c_idx > 0:
            out.append(el("line", owner=own, role="column.rule", x1=x + 6, y1=cy, x2=x + w - 6, y2=cy, stroke=t["rule"],
                          stroke_width=0.5))
        badge_x = x + 10
        for key, color in (("pk", t["accent"]), ("fk", t["link"])):
            if c.get(key) and (key == "pk" or not c.get("pk")):
                out.append(el("rect", owner=own, role="column.badge", x=badge_x, y=cy + 4, width=20, height=12, rx=2, fill=color,
                              fill_opacity=".15"))
                out.append(el("text", key.upper(), owner=own, role="column.badge", x=badge_x + 10, y=cy + 13, font_size=7,
                              font_weight=600, font_family=MONO, fill=color, text_anchor="middle"))
                break
        name_x = badge_x + (25 if (c.get("pk") or c.get("fk")) else 0)
        out.append(el("text", c["name"], owner=own, role="column.name", x=name_x, y=cy + 15, font_size=11, font_family=MONO,
                      fill=t["ink"]))
        out.append(el("text", c.get("type", ""), owner=own, role="column.type", x=x + w - 12, y=cy + 15, font_size=10,
                      font_family=MONO, fill=t["soft"], text_anchor="end"))
    return out


def group_frames(t, groups, pos, avoid=()):
    """A frame behind each group's members. Its name goes in the top corner (left, else right)
    that no arrow crosses; avoid holds the arrows' segment boxes."""
    out = []
    for g in groups:
        f = _frame_box(g, pos)
        if not f:
            continue
        x0, y0, x1, y1 = f
        out.append(el("rect", owner=g["id"], role="group.frame", x=x0, y=y0, width=x1 - x0, height=y1 - y0, rx=10,
                      fill=t["rule"], fill_opacity=".35", stroke=t["muted"], stroke_opacity=".55", stroke_dasharray="4,3",
                      data_group=g["id"], data_name=g["name"], data_members=",".join(g["members"])))
        label = ((g["tag"] + "  " if g.get("tag") else "") + str(g["name"])).upper()
        lw = _text_w(label, 10, True) + 0.4 * len(label)

        def hits(lx):
            b = (lx - 8, y0 + 3, lx + lw + 8, y0 + 19)  # keep clear of arrows, not just off them
            return sum(1 for a in avoid if b[0] < a[2] and a[0] < b[2] and b[1] < a[3] and a[1] < b[3])
        # left corner if it is clear, else the nearest clear spot along the top band, else the least crossed
        spots = [x0 + 10] + [x0 + 10 + 8 * k for k in range(1, int(max(0, x1 - 20 - lw - x0) // 8) + 1)]
        lx = min(spots, key=lambda v: (hits(v), v - x0))
        out.append(el("text", label, owner=g["id"], role="group.title", x=lx, y=y0 + 15, font_size=10, font_weight=600,
                      font_family=FONT, fill=t["muted"], letter_spacing=".04em"))
    return out


def note_rail(t, notes, rail_x, top, lh=92):
    """Right-rail notes: an italic note and a thin leader to (ax, ay). notes = [(ax, ay, text)]."""
    out = []
    for i, (ax, ay, text) in enumerate(notes):
        ry = top + 14 + i * lh
        tx = rail_x + 14
        out.append(el("line", role="note.leader", x1=ax, y1=ay, x2=tx, y2=ry, stroke=t["soft"], stroke_width=1))
        out.append(el("circle", role="note.dot", cx=ax, cy=ay, r=2.5, fill=t["accent"]))
        for j, ln in enumerate(_wrap(text)):
            out.append(el("text", ln, role="note.text", x=tx, y=ry + 4 + j * 16, font_size=13, font_style="italic",
                          font_family=SERIF, fill=t["ink"]))
    return out


def legend_line(t, W, rule_y, text_y, text):
    """The rule and one-line key at the bottom of a diagram."""
    return [el("line", role="legend.rule", x1=30, y1=rule_y, x2=W - 30, y2=rule_y, stroke=t["rule"], stroke_width=".8"),
            el("text", text, role="legend.text", x=30, y=text_y, font_size=11, font_family=FONT, fill=t["muted"])]

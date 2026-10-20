"""Named sides and border decorations.

Each shape splits its outline into named sides. A rectangle (and so a rounded box, an oval or a
table card) has top, right, bottom and left; a side's stroke ends at the middle of each corner
arc next to it, so rounded corners stay round. A diamond has top-left, top-right, bottom-right and
bottom-left, and the generic sides name two of them each (its top is its two upper edges), so a
rule like `node { border-top: 3px solid accent }` reads the same on every shape.

borders(...) decides how a node's outline is painted. With no border-* declared, the shape keeps
its single stroke, as before. Otherwise every side is drawn on its own: a declared side with its
width, style and color, an undeclared one with the shape's stroke, and a `none` side not at all.
"""
from .errors import SpecError

K = 1 - 2 ** -0.5  # how far a corner arc's midpoint sits in from the corner, per unit of radius
RECT = ("top", "right", "bottom", "left")
DIAMOND = ("top-left", "top-right", "bottom-right", "bottom-left")
SIDES = {"rect": RECT, "diamond": DIAMOND}
GENERIC = {"diamond": {"top": ("top-left", "top-right"), "right": ("top-right", "bottom-right"),
                       "bottom": ("bottom-right", "bottom-left"), "left": ("bottom-left", "top-left")}}
ALL = RECT + DIAMOND


def _num(v):
    return f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def rect_sides(x, y, w, h, radii):
    """{side: path d} for a rectangle with corner radii (top-left, top-right, bottom-right, bottom-left)."""
    if not isinstance(radii, (tuple, list)):
        radii = (radii or 0,) * 4
    tl, tr, br, bl = (min(float(r or 0), w / 2, h / 2) for r in radii)
    n = _num

    def arc(r, ex, ey):
        return f" A{n(r)},{n(r)} 0 0 1 {n(ex)},{n(ey)}" if r > 0 else f" L{n(ex)},{n(ey)}"
    return {
        "top": f"M{n(x + tl * K)},{n(y + tl * K)}" + arc(tl, x + tl, y) + f" L{n(x + w - tr)},{n(y)}"
               + arc(tr, x + w - tr * K, y + tr * K),
        "right": f"M{n(x + w - tr * K)},{n(y + tr * K)}" + arc(tr, x + w, y + tr) + f" L{n(x + w)},{n(y + h - br)}"
                 + arc(br, x + w - br * K, y + h - br * K),
        "bottom": f"M{n(x + w - br * K)},{n(y + h - br * K)}" + arc(br, x + w - br, y + h) + f" L{n(x + bl)},{n(y + h)}"
                  + arc(bl, x + bl * K, y + h - bl * K),
        "left": f"M{n(x + bl * K)},{n(y + h - bl * K)}" + arc(bl, x, y + h - bl) + f" L{n(x)},{n(y + tl)}"
                + arc(tl, x + tl * K, y + tl * K),
    }


def rounded_rect(x, y, w, h, radii):
    """A rectangle with its own radius at each corner (top-left, top-right, bottom-right, bottom-left)
    as a closed path: the four sides joined."""
    sides = rect_sides(x, y, w, h, radii)
    d = sides["top"]
    for side in ("right", "bottom", "left"):
        d += " " + sides[side].split(" ", 1)[1]  # each side starts where the last one stopped
    return d + " Z"


def uniform(radii):
    """The one radius, if all four corners share it, else None."""
    if not isinstance(radii, (tuple, list)):
        return radii
    return radii[0] if len(set(radii)) == 1 else None


def diamond_sides(cx, cy, w, h):
    top, right, bottom, left = (cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)
    n = _num

    def line(a, b):
        return f"M{n(a[0])},{n(a[1])} L{n(b[0])},{n(b[1])}"
    return {"top-left": line(left, top), "top-right": line(top, right), "bottom-right": line(right, bottom),
            "bottom-left": line(bottom, left)}


def declared(computed, shape):
    """{side: border} for the border-* properties a node's style sets, in the shape's own side names.
    A side the shape doesn't have is an error that lists the ones it does."""
    kind = "diamond" if shape == "diamond" else "rect"
    own, generic = SIDES[kind], GENERIC.get(kind, {})
    out = {}
    for side in ("top", "right", "bottom", "left") + DIAMOND:  # generic first, so a named side wins
        b = computed.get(f"border-{side}")
        if b is None:
            continue
        if side in own:
            out[side] = b
        elif side in generic:
            for s in generic[side]:
                out.setdefault(s, b)
        else:
            article = "an" if shape[:1] in "aeiou" else "a"
            raise SpecError(f"{article} {shape} has no side '{side}'", f"its sides are: {', '.join(own)}", "unknown-side")
    return out


def borders(sides_d, sides, stroke, width, paper, owner, role="node.border"):
    """Elements for the sides of an outline drawn one by one. sides_d is {side: path d}; sides holds
    the declared borders; the rest take the shape's stroke and width."""
    from .paint import el
    out = []
    for side, d in sides_d.items():
        b = sides.get(side)
        if b is None:
            b = {"width": width if width is not None else 1.0, "style": "solid", "color": stroke}
        w = b.get("width") or 0.0
        color = b["color"].css if hasattr(b.get("color"), "css") else (b.get("color") or stroke)
        if w <= 0 or b.get("style") == "none" or color in (None, "none"):
            continue
        style = b.get("style", "solid")
        dash = {"dashed": f"{_num(3 * w)},{_num(2 * w)}", "dotted": f"0,{_num(2 * w)}"}.get(style)
        out.append(el("path", owner=owner, role=role, d=d, fill="none", stroke=color, stroke_width=w,
                      stroke_dasharray=dash, stroke_linecap="round" if style == "dotted" else None))
        if style == "double":  # a paper line down the middle leaves two
            out.append(el("path", owner=owner, role=role, d=d, fill="none", stroke=paper, stroke_width=w / 3))
    return out


# ---------- paint decorations: gradient, shadow, glow, pattern ----------

def _key(obj):
    import zlib
    return format(zlib.crc32(repr(obj).encode("utf-8")) & 0xFFFFFF, "06x")


def _color(c):
    """(opaque color text, alpha): SVG wants a translucent paint as a color plus an opacity, or the
    alpha would count twice."""
    if hasattr(c, "a") and c.a < 1:
        from .style.parse import Color
        return Color(c.r, c.g, c.b, 1.0).computed(), round(c.a, 3)
    return (c.css if hasattr(c, "css") else c), 1.0


def gradient_def(g):
    """A linear-gradient value as (id, <linearGradient>). The angle is CSS's: 0deg points up."""
    import math
    from .paint import el
    a = math.radians(g["angle"])
    dx, dy = math.sin(a) / 2, -math.cos(a) / 2
    stops = [el("stop", offset=round(at, 4), stop_color=_color(c)[0], stop_opacity=_color(c)[1] if _color(c)[1] < 1 else None)
             for at, c in g["stops"]]
    gid = "gr-" + _key((g["angle"], [(at, _color(c)[0]) for at, c in g["stops"]]))
    return gid, el("linearGradient", id=gid, x1=round(0.5 - dx, 4), y1=round(0.5 - dy, 4), x2=round(0.5 + dx, 4),
                   y2=round(0.5 + dy, 4), children=stops)


def shadow_def(shadows):
    """Outer box-shadows as (id, <filter>), or None when there are none. Inset shadows are skipped."""
    from .paint import el
    outer = [s for s in shadows or [] if not s.get("inset")]
    if not outer:
        return None
    sid = "sh-" + _key([(s["x"], s["y"], s["blur"], _color(s["color"])[0]) for s in outer])
    parts, merge = [], []
    for k, s in enumerate(outer):
        color, alpha = _color(s["color"])
        parts += [el("feGaussianBlur", in_="SourceAlpha", stdDeviation=s["blur"] / 2, result=f"b{k}"),
                  el("feOffset", in_=f"b{k}", dx=s["x"], dy=s["y"], result=f"o{k}"),
                  el("feFlood", flood_color=color, flood_opacity=alpha if alpha < 1 else None),
                  el("feComposite", in2=f"o{k}", operator="in", result=f"s{k}")]
        merge.append(el("feMergeNode", in_=f"s{k}"))
    merge.append(el("feMergeNode", in_="SourceGraphic"))
    return sid, el("filter", id=sid, x="-50%", y="-50%", width="200%", height="200%",
                   children=parts + [el("feMerge", children=merge)])


def glow_def(color):
    """A glow in a color as (id, <filter>): a soft halo of the shape's own outline."""
    from .paint import el
    css, alpha = _color(color)
    gid = "gl-" + _key(css)
    return gid, el("filter", id=gid, x="-50%", y="-50%", width="200%", height="200%", children=[
        el("feGaussianBlur", in_="SourceAlpha", stdDeviation=4, result="b"),
        el("feFlood", flood_color=css, flood_opacity=alpha if alpha < 1 else None),
        el("feComposite", in2="b", operator="in", result="g"),
        el("feMerge", children=[el("feMergeNode", in_="g"), el("feMergeNode", in_="SourceGraphic")])])


def pattern_def(kind, color):
    """hatch, dots or grid as (id, <pattern>), drawn in a color at low opacity."""
    from .paint import el
    pid = f"pt-{kind}-" + _key(color)
    marks = {"hatch": [el("line", x1=0, y1=0, x2=0, y2=8, stroke=color, stroke_width=1.2, stroke_opacity=".35")],
             "dots": [el("circle", cx=4, cy=4, r=1.1, fill=color, fill_opacity=".4")],
             "grid": [el("path", d="M8,0 L0,0 L0,8", fill="none", stroke=color, stroke_width=0.8, stroke_opacity=".3")]}[kind]
    return pid, el("pattern", id=pid, width=8, height=8, patternUnits="userSpaceOnUse",
                   patternTransform="rotate(45)" if kind == "hatch" else None, children=marks)


def decorate(shape_el, underlay_el, st, overlay):
    """Apply a node's paint decorations in place and return what goes with them: a defs holder the
    drawing hoists, and a pattern overlay. overlay(fill) makes a copy of the outline with that fill."""
    from .paint import el
    c = st.get("computed") or {}
    defs, extra = [], []
    fill = shape_el.attrs.get("fill")
    if isinstance(fill, dict) and fill.get("type") == "linear":
        gid, g = gradient_def(fill)
        defs.append(g)
        shape_el.attrs["fill"] = f"url(#{gid})"
    shadow = shadow_def(c.get("box-shadow"))
    if shadow:
        defs.append(shadow[1])
        underlay_el.attrs["filter"] = f"url(#{shadow[0]})"
    if c.get("glow") is not None:
        gid, g = glow_def(c["glow"])
        defs.append(g)
        shape_el.attrs["filter"] = f"url(#{gid})"
    if c.get("opacity") is not None:
        shape_el.attrs["opacity"] = c["opacity"]
    if c.get("pattern") not in (None, "none"):
        stroke = shape_el.attrs.get("stroke")
        pid, p = pattern_def(c["pattern"], stroke if stroke not in (None, "none") else st.get("stroke") or "#000")
        defs.append(p)
        extra.append(overlay(f"url(#{pid})"))
    if defs:
        extra.insert(0, el("defs", role="deco.defs", children=defs))
    return extra

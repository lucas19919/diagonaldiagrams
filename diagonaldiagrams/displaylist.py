"""The display list: everything a figure paints, in paint order, with what each item is.

The audit's checks read a display list, never SVG text. Today the audit builds one from a finished
SVG (audit.svg_import); the renderers will build theirs directly, so
the same checks see exactly what was drawn.
"""


class Item:
    """One painted thing as the checks see it. Item(kind, **fields); unset fields take the defaults
    below, which live on the class, so making an item stores only what it sets (the audit makes
    tens of thousands per figure). Not a dataclass: importing dataclasses costs 25-40 ms."""
    FIELDS = (
        ("z", 0),                   # paint order among texts, arrows and obstacle shapes
        ("box", None),              # (x0, y0, x1, y1), absolute
        ("text", ""),               # text: one line
        ("size", 0.0),              # text: font size
        ("newline", False),         # text: holds a literal line break SVG will not honor
        ("tag", ""),                # shape: the element it came from (rect, polygon, ...)
        ("obstacle", False),        # shape: arrows and other shapes must keep off it
        ("pts", None),              # arrow: corner points, None where a subpath starts
        ("ends", None),             # arrow: first and last point
        ("group", None),            # a group frame around `members`
        ("members", frozenset()),
        ("node", None),             # a named node's box
        ("diamond", None),          # (cx, cy, width, height) of a decision's outline
        ("ellipse", None),          # (cx, cy, rx, ry): a circle or ellipse arrows must go around
        ("depth", 0.0),             # distance from the viewer once projected; 0 in 2D
        ("a11y", None),             # a part a reader navigates: {"name", "kind", "order"}
        ("attach", None),           # arrow: {"from": {"node", "port"}, "to": {...}} when the SVG says
        ("color", None),            # text: its fill
        ("bold", False),            # text: weight 600 or more
        ("color_from", None),       # text: the stylesheet rule that chose its color, when one did
        ("size_from", None),        # text: the rule that chose its size
        ("font_fallback", None),    # text: a named font that wasn't found, so it was measured by estimate
        ("shaping", None),          # text: scripts whose widths need a shaper this engine lacks
        ("fill", None),             # shape: (color, opacity), what text over it is read against
        ("solid", None),            # face, arrow: the 3D solid it belongs to (data-solid)
        ("box3", None),             # face: its solid's box (x0, y0, z0, x1, y1, z1), on the top face (data-box3)
        ("on", None),               # text: the solid it stands on, or the link it names (data-face)
    )
    NAMES = frozenset(name for name, _ in FIELDS)

    def __init__(self, kind, **fields):
        self.kind = kind  # "text", "shape", "arrow" or "face" (a projected 3D face: pts is its outline)
        if fields:
            if not fields.keys() <= self.NAMES:
                raise TypeError(f"Item has no field {sorted(fields.keys() - self.NAMES)[0]!r}")
            self.__dict__.update(fields)

    def __repr__(self):
        shown = ", ".join(f"{n}={getattr(self, n)!r}" for n, d in self.FIELDS if getattr(self, n) != d)
        return f"Item({self.kind!r}{', ' + shown if shown else ''})"


for _name, _default in Item.FIELDS:  # the defaults, on the class
    setattr(Item, _name, _default)


class DisplayList:
    """legibility: "all" when the figure's renderer says its default colors and sizes pass (the
    root's data-legibility), so the contrast and size checks judge every text; None judges only
    text a stylesheet styled."""
    __slots__ = ("width", "height", "items", "legibility")

    def __init__(self, width=0.0, height=0.0, items=None, legibility=None):
        self.width, self.height, self.items, self.legibility = width, height, list(items or []), legibility

    def add(self, item):
        self.items.append(item)
        return item

    @property
    def texts(self):
        return [i for i in self.items if i.kind == "text"]

    @property
    def shapes(self):
        return [i for i in self.items if i.kind == "shape" and i.obstacle]

    @property
    def arrows(self):
        return [i for i in self.items if i.kind == "arrow"]

    @property
    def faces(self):
        return [i for i in self.items if i.kind == "face"]

    @property
    def frames(self):
        return [i for i in self.items if i.group is not None]

    @property
    def named(self):
        return [i for i in self.items if i.node is not None]

    @property
    def diamonds(self):
        return [i.diamond for i in self.items if i.diamond]

    @property
    def ellipses(self):
        return [i.ellipse for i in self.items if i.ellipse]

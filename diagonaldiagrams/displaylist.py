"""The display list: everything a figure paints, in paint order, with what each item is.

The audit's checks read a display list, never SVG text. Today the audit builds one from a finished
SVG (audit.svg_import); the renderers will build theirs directly (docs/DESIGN.md, section 8.3), so
the same checks see exactly what was drawn.
"""


class Item:
    """One painted thing as the checks see it. Item(kind, **fields); unset fields take the defaults
    below. Plain slots rather than a dataclass: importing dataclasses costs 25-40 ms per process."""
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
        ("depth", 0.0),             # distance from the viewer once projected (DESIGN 13); 0 in 2D
        ("a11y", None),             # a part a reader navigates: {"name", "kind", "order"} (DESIGN 22.3)
        ("attach", None),           # arrow: {"from": {"node", "port"}, "to": {...}} when the SVG says
    )
    __slots__ = ("kind",) + tuple(name for name, _ in FIELDS)

    def __init__(self, kind, **fields):
        self.kind = kind  # "text", "shape" or "arrow"
        for name, default in self.FIELDS:
            setattr(self, name, fields.pop(name, default))
        if fields:
            raise TypeError(f"Item has no field {next(iter(fields))!r}")

    def __repr__(self):
        shown = ", ".join(f"{n}={getattr(self, n)!r}" for n, d in self.FIELDS if getattr(self, n) != d)
        return f"Item({self.kind!r}{', ' + shown if shown else ''})"


class DisplayList:
    __slots__ = ("width", "height", "items")

    def __init__(self, width=0.0, height=0.0, items=None):
        self.width, self.height, self.items = width, height, list(items or [])

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

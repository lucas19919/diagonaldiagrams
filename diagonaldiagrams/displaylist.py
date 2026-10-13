"""The display list: everything a figure paints, in paint order, with what each item is.

The audit's checks read a display list, never SVG text. Today the audit builds one from a finished
SVG (audit.svg_import); the renderers will build theirs directly (docs/DESIGN.md, section 8.3), so
the same checks see exactly what was drawn.
"""
from dataclasses import dataclass, field


@dataclass
class Item:
    kind: str                     # "text", "shape" or "arrow"
    z: int = 0                    # paint order among texts, arrows and obstacle shapes
    box: tuple = None             # (x0, y0, x1, y1), absolute
    text: str = ""                # text: one line
    size: float = 0.0             # text: font size
    newline: bool = False         # text: holds a literal line break SVG will not honor
    tag: str = ""                 # shape: the element it came from (rect, polygon, ...)
    obstacle: bool = False        # shape: arrows and other shapes must keep off it
    pts: list = None              # arrow: corner points, None where a subpath starts
    ends: tuple = None            # arrow: first and last point
    group: str = None             # a group frame around `members`
    members: frozenset = frozenset()
    node: str = None              # a named node's box
    diamond: tuple = None         # (cx, cy, width, height) of a decision's outline
    ellipse: tuple = None         # (cx, cy, rx, ry): a circle or ellipse arrows must go around


@dataclass
class DisplayList:
    width: float = 0.0
    height: float = 0.0
    items: list = field(default_factory=list)

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

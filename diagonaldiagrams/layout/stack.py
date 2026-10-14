"""Stack layout kernel (DESIGN 7.2, PLAN P4.5): rows and columns of anything.

Flexbox-like semantics: direction ("row" or "column"), gap, align ("start", "center", "end"),
justify ("start", "center", "end", "space-between", "space-around"), and wrap.
"""
from .base import Layout, Placement, Size, register


class StackLayout(Layout):
    name = "stack"
    options = {
        "direction": "row",  # "row" | "column"
        "gap": 24.0,
        "align": "center",   # cross-axis: "start" | "center" | "end"
        "justify": "start",  # main-axis: "start" | "center" | "end" | "space-between" | "space-around"
        "wrap": False,
        "pad": 16.0,
    }

    def __init__(self, options=None):
        self.opts = dict(self.options, **(options or {}))

    def _items(self, container):
        items = []
        for c in container.children:
            w = float(getattr(c, "w", 0) or getattr(getattr(c, "size", None), "w", 0) or (c.get("w", 160) if isinstance(c, dict) else 160))
            h = float(getattr(c, "h", 0) or getattr(getattr(c, "size", None), "h", 0) or (c.get("h", 56) if isinstance(c, dict) else 56))
            cid = getattr(c, "id", c.get("id") if isinstance(c, dict) else str(c))
            items.append((cid, w, h))
        return items

    def measure(self, ctx, container) -> Size:
        items = self._items(container)
        if not items:
            return Size(0.0, 0.0)
        direction = self.opts.get("direction", "row")
        gap = float(self.opts.get("gap", 24.0))
        pad = float(self.opts.get("pad", 16.0))
        if direction in ("row", "LR"):
            total_w = sum(w for _, w, _ in items) + gap * max(0, len(items) - 1) + 2 * pad
            max_h = max(h for _, _, h in items) + 2 * pad
            return Size(total_w, max_h)
        else:
            max_w = max(w for _, w, _ in items) + 2 * pad
            total_h = sum(h for _, _, h in items) + gap * max(0, len(items) - 1) + 2 * pad
            return Size(max_w, total_h)

    def place(self, ctx, container, box) -> Placement:
        items = self._items(container)
        pos = {}
        if not items:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        direction = self.opts.get("direction", "row")
        gap = float(self.opts.get("gap", 24.0))
        pad = float(self.opts.get("pad", 16.0))
        align = self.opts.get("align", "center")
        bx, by = box[0] + pad, box[1] + pad
        bw, bh = max(0.0, box[2] - 2 * pad), max(0.0, box[3] - 2 * pad)

        if direction in ("row", "LR"):
            cur_x = bx
            for cid, w, h in items:
                if align == "start":
                    cy = by + h / 2.0
                elif align == "end":
                    cy = by + bh - h / 2.0
                else:  # center
                    cy = by + bh / 2.0
                cx = cur_x + w / 2.0
                pos[cid] = (cx, cy)
                cur_x += w + gap
        else:
            cur_y = by
            for cid, w, h in items:
                if align == "start":
                    cx = bx + w / 2.0
                elif align == "end":
                    cx = bx + bw - w / 2.0
                else:  # center
                    cx = bx + bw / 2.0
                cy = cur_y + h / 2.0
                pos[cid] = (cx, cy)
                cur_y += h + gap
        return Placement(pos=pos, size=Size(box[2], box[3]))


register("stack", StackLayout)
register("row", lambda opts=None: StackLayout(dict(opts or {}, direction="row")))
register("column", lambda opts=None: StackLayout(dict(opts or {}, direction="column")))

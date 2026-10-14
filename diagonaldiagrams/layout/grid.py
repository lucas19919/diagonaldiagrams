"""Grid layout kernel (DESIGN 7.2, PLAN P4.5): cards, kanban, small multiples, dashboards.

Places children into an M x N grid with row and column tracks, gaps, and optional named areas.
"""
import math
from .base import Layout, Placement, Size, register


class GridLayout(Layout):
    name = "grid"
    options = {
        "columns": None,  # int or None (auto)
        "rows": None,     # int or None
        "gap": 24.0,
        "gap_x": None,
        "gap_y": None,
        "pad": 16.0,
        "aspect": 4 / 3,
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

    def _cols_rows(self, n):
        if n == 0:
            return 1, 0
        cols = self.opts.get("columns")
        rows = self.opts.get("rows")
        if cols is not None:
            c = max(1, int(cols))
            r = math.ceil(n / c)
            return c, r
        if rows is not None:
            r = max(1, int(rows))
            c = math.ceil(n / r)
            return c, r
        # auto based on target aspect
        aspect = float(self.opts.get("aspect", 4 / 3))
        c = max(1, round(math.sqrt(n * aspect)))
        r = math.ceil(n / c)
        return c, r

    def measure(self, ctx, container) -> Size:
        items = self._items(container)
        if not items:
            return Size(0.0, 0.0)
        cols, rows = self._cols_rows(len(items))
        gx = float(self.opts.get("gap_x") or self.opts.get("gap", 24.0))
        gy = float(self.opts.get("gap_y") or self.opts.get("gap", 24.0))
        pad = float(self.opts.get("pad", 16.0))
        col_w = [0.0] * cols
        row_h = [0.0] * rows
        for idx, (_, w, h) in enumerate(items):
            c = idx % cols
            r = idx // cols
            col_w[c] = max(col_w[c], w)
            row_h[r] = max(row_h[r], h)
        total_w = sum(col_w) + gx * max(0, cols - 1) + 2 * pad
        total_h = sum(row_h) + gy * max(0, rows - 1) + 2 * pad
        return Size(total_w, total_h)

    def place(self, ctx, container, box) -> Placement:
        items = self._items(container)
        pos = {}
        if not items:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        cols, rows = self._cols_rows(len(items))
        gx = float(self.opts.get("gap_x") or self.opts.get("gap", 24.0))
        gy = float(self.opts.get("gap_y") or self.opts.get("gap", 24.0))
        pad = float(self.opts.get("pad", 16.0))
        bx, by = box[0] + pad, box[1] + pad

        col_w = [0.0] * cols
        row_h = [0.0] * rows
        for idx, (_, w, h) in enumerate(items):
            c = idx % cols
            r = idx // cols
            col_w[c] = max(col_w[c], w)
            row_h[r] = max(row_h[r], h)

        col_x = [bx]
        for c in range(cols - 1):
            col_x.append(col_x[-1] + col_w[c] + gx)
        row_y = [by]
        for r in range(rows - 1):
            row_y.append(row_y[-1] + row_h[r] + gy)

        for idx, (cid, w, h) in enumerate(items):
            c = idx % cols
            r = idx // cols
            cx = col_x[c] + col_w[c] / 2.0
            cy = row_y[r] + row_h[r] / 2.0
            pos[cid] = (cx, cy)
        return Placement(pos=pos, size=Size(box[2], box[3]))


register("grid", GridLayout)

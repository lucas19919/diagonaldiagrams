"""Manual / pinned layout kernel (DESIGN 7.2, PLAN P4.5): exact coordinates with overlap checking.

Positions items at their explicit pin coordinates (x, y) and verifies no boxes collide.
"""
from .base import Layout, Placement, Size, register


class ManualLayout(Layout):
    name = "manual"
    options = {
        "pad": 24.0,
    }

    def __init__(self, options=None):
        self.opts = dict(self.options, **(options or {}))

    def _items(self, container):
        items = []
        for c in container.children:
            w = float(getattr(c, "w", 0) or getattr(getattr(c, "size", None), "w", 0) or (c.get("w", 160) if isinstance(c, dict) else 160))
            h = float(getattr(c, "h", 0) or getattr(getattr(c, "size", None), "h", 0) or (c.get("h", 56) if isinstance(c, dict) else 56))
            cid = getattr(c, "id", c.get("id") if isinstance(c, dict) else str(c))
            pin = getattr(c, "pin", None) or (c.get("pin") if isinstance(c, dict) else None)
            px = float(pin.get("x", 0)) if isinstance(pin, dict) else 0.0
            py = float(pin.get("y", 0)) if isinstance(pin, dict) else 0.0
            items.append((cid, w, h, px, py))
        return items

    def measure(self, ctx, container) -> Size:
        items = self._items(container)
        if not items:
            return Size(0.0, 0.0)
        pad = float(self.opts.get("pad", 24.0))
        max_x = max(px + w / 2.0 for _, w, _, px, _ in items)
        min_x = min(px - w / 2.0 for _, w, _, px, _ in items)
        max_y = max(py + h / 2.0 for _, _, h, _, py in items)
        min_y = min(py - h / 2.0 for _, _, h, _, py in items)
        return Size(max(0.0, max_x - min_x) + 2 * pad, max(0.0, max_y - min_y) + 2 * pad)

    def place(self, ctx, container, box) -> Placement:
        items = self._items(container)
        pos = {}
        issues = []
        if not items:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        pad = float(self.opts.get("pad", 24.0))
        min_x = min(px - w / 2.0 for _, w, _, px, _ in items)
        min_y = min(py - h / 2.0 for _, _, h, _, py in items)
        bx, by = box[0] + pad, box[1] + pad

        boxes = []
        for cid, w, h, px, py in items:
            cx = px - min_x + bx + w / 2.0
            cy = py - min_y + by + h / 2.0
            pos[cid] = (cx, cy)
            boxes.append((cid, cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0))

        # Check for overlaps
        for i in range(len(boxes)):
            id1, x1, y1, x2, y2 = boxes[i]
            for j in range(i + 1, len(boxes)):
                id2, u1, v1, u2, v2 = boxes[j]
                if not (x2 <= u1 or u2 <= x1 or y2 <= v1 or v2 <= y1):
                    issues.append({
                        "code": "overlap",
                        "msg": f"pinned nodes '{id1}' and '{id2}' overlap",
                        "fix": f"adjust pin coordinates of '{id1}' or '{id2}'",
                        "at": ((x1 + u2) / 2.0, (y1 + v2) / 2.0),
                    })
        return Placement(pos=pos, size=Size(box[2], box[3]), issues=issues)


register("manual", ManualLayout)

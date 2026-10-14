"""Timeaxis / timeline layout kernel (DESIGN 7.2, PLAN P4.5): Gantt charts, timelines, journeys.

Places events and intervals along a continuous time scale partitioned into lanes.
"""
from .base import Layout, Placement, Size, register


class TimeaxisLayout(Layout):
    name = "timeaxis"
    options = {
        "lane_h": 48.0,
        "lane_gap": 16.0,
        "pad": 32.0,
        "scale": 1.0,  # pixels per unit time (or auto)
        "time_span": None,
    }

    def __init__(self, options=None):
        self.opts = dict(self.options, **(options or {}))

    def _items(self, container):
        items = []
        for c in container.children:
            cid = getattr(c, "id", c.get("id") if isinstance(c, dict) else str(c))
            lane = getattr(c, "lane", c.get("lane", 0) if isinstance(c, dict) else 0)
            data = getattr(c, "data", c.get("data", {}) if isinstance(c, dict) else {})
            start = data.get("start", 0.0) if isinstance(data, dict) else 0.0
            end = data.get("end", start + 100.0) if isinstance(data, dict) else start + 100.0
            try:
                start = float(start)
                end = float(end)
            except (ValueError, TypeError):
                start, end = 0.0, 100.0
            w = max(40.0, end - start)
            h = float(getattr(c, "h", 0) or getattr(getattr(c, "size", None), "h", 0) or (c.get("h", 36) if isinstance(c, dict) else 36))
            items.append((cid, lane, start, end, w, h))
        return items

    def measure(self, ctx, container) -> Size:
        items = self._items(container)
        if not items:
            return Size(0.0, 0.0)
        lane_h = float(self.opts.get("lane_h", 48.0))
        lane_gap = float(self.opts.get("lane_gap", 16.0))
        pad = float(self.opts.get("pad", 32.0))
        min_start = min(st for _, _, st, _, _, _ in items)
        max_end = max(en for _, _, _, en, _, _ in items)
        lanes = sorted(set(l for _, l, _, _, _, _ in items))
        total_w = (max_end - min_start) + 2 * pad
        total_h = len(lanes) * (lane_h + lane_gap) + 2 * pad
        return Size(total_w, total_h)

    def place(self, ctx, container, box) -> Placement:
        items = self._items(container)
        pos = {}
        if not items:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        lane_h = float(self.opts.get("lane_h", 48.0))
        lane_gap = float(self.opts.get("lane_gap", 16.0))
        pad = float(self.opts.get("pad", 32.0))
        min_start = min(st for _, _, st, _, _, _ in items)
        lanes = sorted(set(l for _, l, _, _, _, _ in items))
        lane_idx = {l: i for i, l in enumerate(lanes)}
        bx, by = box[0] + pad, box[1] + pad

        for cid, lane, start, end, w, h in items:
            cx = bx + (start - min_start) + w / 2.0
            l_i = lane_idx.get(lane, 0)
            cy = by + l_i * (lane_h + lane_gap) + lane_h / 2.0
            pos[cid] = (cx, cy)
        return Placement(pos=pos, size=Size(box[2], box[3]))


register("timeaxis", TimeaxisLayout)
register("timeline", TimeaxisLayout)

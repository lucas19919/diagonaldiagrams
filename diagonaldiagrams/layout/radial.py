"""Radial layout kernel (DESIGN 7.2, PLAN P4.5): flywheels, hub-and-spoke, cyclic architectures.

Even angular spacing around a central hub or concentric rings.
"""
import math
from .base import Layout, Placement, Size, register


class RadialLayout(Layout):
    name = "radial"
    options = {
        "hub": None,         # id of central node (or auto)
        "radius": None,      # distance from center (auto if None)
        "start_angle": -math.pi / 2,  # 12 o'clock
        "pad": 32.0,
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

    def _hub_and_spokes(self, items):
        if not items:
            return None, []
        hub_id = self.opts.get("hub")
        if hub_id:
            hub = next((it for it in items if it[0] == hub_id), items[0])
            spokes = [it for it in items if it[0] != hub_id]
        else:
            hub = items[0]
            spokes = items[1:]
        return hub, spokes

    def measure(self, ctx, container) -> Size:
        items = self._items(container)
        if not items:
            return Size(0.0, 0.0)
        hub, spokes = self._hub_and_spokes(items)
        pad = float(self.opts.get("pad", 32.0))
        max_sw = max((w for _, w, _ in spokes), default=120)
        max_sh = max((h for _, _, h in spokes), default=50)
        hw = hub[1] if hub else 120
        hh = hub[2] if hub else 50
        r = float(self.opts.get("radius") or max(140.0, len(spokes) * max(max_sw, max_sh) / math.pi + max(hw, hh) / 2))
        total_d = 2 * (r + max(max_sw, max_sh) / 2.0 + pad)
        return Size(total_d, total_d)

    def place(self, ctx, container, box) -> Placement:
        items = self._items(container)
        pos = {}
        if not items:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        hub, spokes = self._hub_and_spokes(items)
        pad = float(self.opts.get("pad", 32.0))
        max_sw = max((w for _, w, _ in spokes), default=120)
        max_sh = max((h for _, _, h in spokes), default=50)
        hw = hub[1] if hub else 120
        hh = hub[2] if hub else 50
        r = float(self.opts.get("radius") or max(140.0, len(spokes) * max(max_sw, max_sh) / math.pi + max(hw, hh) / 2))
        cx = box[0] + box[2] / 2.0
        cy = box[1] + box[3] / 2.0
        if hub:
            pos[hub[0]] = (cx, cy)
        start = float(self.opts.get("start_angle", -math.pi / 2))
        n = len(spokes)
        for i, (sid, w, h) in enumerate(spokes):
            theta = start + 2 * math.pi * i / n
            sx = cx + r * math.cos(theta)
            sy = cy + r * math.sin(theta)
            pos[sid] = (sx, sy)
        return Placement(pos=pos, size=Size(box[2], box[3]))


register("radial", RadialLayout)

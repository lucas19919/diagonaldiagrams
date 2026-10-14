"""Force-directed layout kernel (DESIGN 7.2, PLAN P4.5): knowledge graphs, coupling maps.

Deterministic seeded simulation (Fruchterman-Reingold) with overlap removal.
"""
import math
import random
from .base import Layout, Placement, Size, register


class ForceLayout(Layout):
    name = "force"
    options = {
        "seed": 42,
        "iterations": 60,
        "k": 120.0,
        "pad": 32.0,
    }

    def __init__(self, options=None):
        self.opts = dict(self.options, **(options or {}))

    def _items_edges(self, container):
        items = []
        for c in container.children:
            w = float(getattr(c, "w", 0) or getattr(getattr(c, "size", None), "w", 0) or (c.get("w", 160) if isinstance(c, dict) else 160))
            h = float(getattr(c, "h", 0) or getattr(getattr(c, "size", None), "h", 0) or (c.get("h", 56) if isinstance(c, dict) else 56))
            cid = getattr(c, "id", c.get("id") if isinstance(c, dict) else str(c))
            items.append((cid, w, h))
        edges = getattr(container, "edges", []) or container.extra.get("edges", [])
        clean_edges = []
        item_ids = {it[0] for it in items}
        for e in edges:
            f = e.get("from") if isinstance(e, dict) else getattr(e, "from_", None)
            t = e.get("to") if isinstance(e, dict) else getattr(e, "to", None)
            if f in item_ids and t in item_ids and f != t:
                clean_edges.append((f, t))
        return items, clean_edges

    def _simulate(self, items, edges):
        rng = random.Random(self.opts.get("seed", 42))
        n = len(items)
        if n == 0:
            return {}
        k = float(self.opts.get("k", 120.0))
        area = n * (k ** 2)
        radius = math.sqrt(area / math.pi)
        pos = {}
        for i, (cid, w, h) in enumerate(items):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(0, radius)
            pos[cid] = [dist * math.cos(angle), dist * math.sin(angle)]

        iterations = int(self.opts.get("iterations", 60))
        t = radius / 10.0
        dt = t / (iterations + 1)

        cids = [it[0] for it in items]
        size_of = {it[0]: (it[1], it[2]) for it in items}

        for _ in range(iterations):
            disp = {cid: [0.0, 0.0] for cid in cids}
            # Repulsion between all pairs
            for i in range(n):
                u = cids[i]
                for j in range(i + 1, n):
                    v = cids[j]
                    dx = pos[u][0] - pos[v][0]
                    dy = pos[u][1] - pos[v][1]
                    d = math.hypot(dx, dy) or 0.01
                    # adjust distance by box sizes to avoid overlap
                    min_d = (size_of[u][0] + size_of[v][0]) / 4.0
                    eff_d = max(d - min_d, 0.1)
                    rep = (k ** 2) / eff_d
                    disp[u][0] += (dx / d) * rep
                    disp[u][1] += (dy / d) * rep
                    disp[v][0] -= (dx / d) * rep
                    disp[v][1] -= (dy / d) * rep

            # Attraction along edges
            for u, v in edges:
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                d = math.hypot(dx, dy) or 0.01
                att = (d ** 2) / k
                disp[u][0] -= (dx / d) * att
                disp[u][1] -= (dy / d) * att
                disp[v][0] += (dx / d) * att
                disp[v][1] += (dy / d) * att

            # Apply displacement capped by temperature
            for cid in cids:
                d = math.hypot(disp[cid][0], disp[cid][1]) or 0.01
                step = min(d, t)
                pos[cid][0] += (disp[cid][0] / d) * step
                pos[cid][1] += (disp[cid][1] / d) * step
            t = max(0.01, t - dt)

        return pos

    def measure(self, ctx, container) -> Size:
        items, edges = self._items_edges(container)
        if not items:
            return Size(0.0, 0.0)
        pos = self._simulate(items, edges)
        pad = float(self.opts.get("pad", 32.0))
        size_of = {it[0]: (it[1], it[2]) for it in items}
        min_x = min(pos[cid][0] - size_of[cid][0] / 2.0 for cid in pos)
        max_x = max(pos[cid][0] + size_of[cid][0] / 2.0 for cid in pos)
        min_y = min(pos[cid][1] - size_of[cid][1] / 2.0 for cid in pos)
        max_y = max(pos[cid][1] + size_of[cid][1] / 2.0 for cid in pos)
        return Size(max_x - min_x + 2 * pad, max_y - min_y + 2 * pad)

    def place(self, ctx, container, box) -> Placement:
        items, edges = self._items_edges(container)
        pos = {}
        if not items:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        sim_pos = self._simulate(items, edges)
        pad = float(self.opts.get("pad", 32.0))
        size_of = {it[0]: (it[1], it[2]) for it in items}
        min_x = min(sim_pos[cid][0] - size_of[cid][0] / 2.0 for cid in sim_pos)
        max_x = max(sim_pos[cid][0] + size_of[cid][0] / 2.0 for cid in sim_pos)
        min_y = min(sim_pos[cid][1] - size_of[cid][1] / 2.0 for cid in sim_pos)
        max_y = max(sim_pos[cid][1] + size_of[cid][1] / 2.0 for cid in sim_pos)
        bx, by = box[0] + pad, box[1] + pad
        for cid in sim_pos:
            nx = sim_pos[cid][0] - min_x + bx
            ny = sim_pos[cid][1] - min_y + by
            pos[cid] = (nx, ny)
        return Placement(pos=pos, size=Size(box[2], box[3]))


register("force", ForceLayout)

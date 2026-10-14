"""Sequence diagram layout kernel (DESIGN 7.2, PLAN P4.5): lifelines, messages, activations, fragments.

Places actors along horizontal pitches and messages down vertical time axis.
"""
from .base import Layout, Placement, Size, register


class SequenceLayout(Layout):
    name = "sequence"
    options = {
        "pitch": 180.0,
        "msg_gap": 52.0,
        "box_h": 52.0,
        "pad": 40.0,
        "margin_x": 70.0,
    }

    def __init__(self, options=None):
        self.opts = dict(self.options, **(options or {}))

    def _actors_messages(self, container):
        actors = []
        for c in container.children:
            cid = getattr(c, "id", c.get("id") if isinstance(c, dict) else str(c))
            name = getattr(c, "name", c.get("name", cid) if isinstance(c, dict) else cid)
            actors.append((cid, name))
        messages = getattr(container, "edges", []) or container.extra.get("messages", [])
        fragments = container.extra.get("fragments", [])
        return actors, messages, fragments

    def measure(self, ctx, container) -> Size:
        actors, messages, _ = self._actors_messages(container)
        n = max(1, len(actors))
        pitch = float(self.opts.get("pitch", 180.0))
        margin_x = float(self.opts.get("margin_x", 70.0))
        msg_gap = float(self.opts.get("msg_gap", 52.0))
        box_h = float(self.opts.get("box_h", 52.0))
        w = margin_x * 2 + max(0, n - 1) * pitch + 140.0
        h = box_h + 34.0 + len(messages) * msg_gap + 120.0
        return Size(w, h)

    def place(self, ctx, container, box) -> Placement:
        actors, messages, fragments = self._actors_messages(container)
        pos = {}
        routes = {}
        frames = {}
        if not actors:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        n = max(1, len(actors))
        pitch = float(self.opts.get("pitch", 180.0))
        margin_x = float(self.opts.get("margin_x", 70.0))
        msg_gap = float(self.opts.get("msg_gap", 52.0))
        box_h = float(self.opts.get("box_h", 52.0))
        bx, by = box[0], box[1]

        # Actor positions
        for i, (aid, _) in enumerate(actors):
            cx = bx + margin_x + 70.0 + i * pitch
            cy = by + box_h / 2.0 + 20.0
            pos[aid] = (cx, cy)

        # Message routes
        msg_start = by + box_h + 54.0
        for i, m in enumerate(messages):
            fid = m.get("from") if isinstance(m, dict) else getattr(m, "from_", None)
            tid = m.get("to") if isinstance(m, dict) else getattr(m, "to", None)
            mid = m.get("id") if isinstance(m, dict) else getattr(m, "id", f"msg_{i}")
            if fid in pos and tid in pos:
                x1, _ = pos[fid]
                x2, _ = pos[tid]
                my = msg_start + i * msg_gap
                if fid == tid:
                    # self-message
                    pts = [(x1, my - 8), (x1 + 36, my - 8), (x1 + 36, my + 12), (x1, my + 12)]
                else:
                    pts = [(x1, my), (x2, my)]
                routes[mid] = {"id": mid, "points": pts, "from": fid, "to": tid}

        # Fragments (loop, alt, opt)
        for i, frag in enumerate(fragments):
            kind = frag.get("type", "loop")
            m_start = int(frag.get("start", 0))
            m_end = int(frag.get("end", len(messages) - 1))
            targets = frag.get("actors", [a[0] for a in actors])
            t_xs = [pos[aid][0] for aid in targets if aid in pos]
            if t_xs:
                fx0 = min(t_xs) - 40.0
                fx1 = max(t_xs) + 40.0
                fy0 = msg_start + m_start * msg_gap - 20.0
                fy1 = msg_start + m_end * msg_gap + 20.0
                frames[f"frag_{i}_{kind}"] = (fx0, fy0, fx1, fy1)

        return Placement(pos=pos, size=Size(box[2], box[3]), routes=routes, frames=frames)


register("sequence", SequenceLayout)
register("seq", SequenceLayout)

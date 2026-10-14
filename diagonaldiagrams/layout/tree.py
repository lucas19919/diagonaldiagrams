"""Tree layout kernel (DESIGN 7.2, PLAN P4.5): org charts, decision trees, taxonomies.

Linear-time tidy tree layout (Buchheim, Jünger, Leipert 2002; Walker 1990).
"""
from .base import Layout, Placement, Size, register


class _Node:
    __slots__ = ("id", "w", "h", "children", "parent", "x", "y", "prelim", "mod", "thread", "ancestor", "change", "shift", "number")

    def __init__(self, id, w, h, parent=None, number=0):
        self.id = id
        self.w, self.h = float(w), float(h)
        self.children = []
        self.parent = parent
        self.x, self.y = 0.0, 0.0
        self.prelim, self.mod = 0.0, 0.0
        self.thread = None
        self.ancestor = self
        self.change, self.shift = 0.0, 0.0
        self.number = number


class TreeLayout(Layout):
    name = "tree"
    options = {
        "direction": "TB",
        "node_gap": 32.0,
        "level_gap": 64.0,
        "pad": 24.0,
    }

    def __init__(self, options=None):
        self.opts = dict(self.options, **(options or {}))

    def _build_tree(self, container):
        items = {}
        for c in container.children:
            w = float(getattr(c, "w", 0) or getattr(getattr(c, "size", None), "w", 0) or (c.get("w", 160) if isinstance(c, dict) else 160))
            h = float(getattr(c, "h", 0) or getattr(getattr(c, "size", None), "h", 0) or (c.get("h", 56) if isinstance(c, dict) else 56))
            cid = getattr(c, "id", c.get("id") if isinstance(c, dict) else str(c))
            items[cid] = _Node(cid, w, h)
        edges = getattr(container, "edges", []) or container.extra.get("edges", [])
        parent_of = {}
        for e in edges:
            f = e.get("from") if isinstance(e, dict) else getattr(e, "from_", None)
            t = e.get("to") if isinstance(e, dict) else getattr(e, "to", None)
            if f in items and t in items and t not in parent_of:
                parent_of[t] = f
        # root has in-degree 0
        roots = [n for cid, n in items.items() if cid not in parent_of]
        if not roots and items:
            roots = [next(iter(items.values()))]
        for cid, n in items.items():
            pid = parent_of.get(cid)
            if pid and pid in items:
                p = items[pid]
                n.parent = p
                n.number = len(p.children)
                p.children.append(n)
        return roots, items

    def _buchheim(self, root, node_gap, level_gap):
        def first_walk(v, dist=node_gap):
            if not v.children:
                w = v.parent.children[v.number - 1] if v.number > 0 else None
                v.prelim = (w.prelim + dist + (w.w + v.w) / 2.0) if w else 0.0
            else:
                default_ancestor = v.children[0]
                for w in v.children:
                    first_walk(w, dist)
                    default_ancestor = apportion(w, default_ancestor, dist)
                execute_shifts(v)
                midpoint = (v.children[0].prelim + v.children[-1].prelim) / 2.0
                w = v.parent.children[v.number - 1] if (v.parent and v.number > 0) else None
                if w:
                    v.prelim = w.prelim + dist + (w.w + v.w) / 2.0
                    v.mod = v.prelim - midpoint
                else:
                    v.prelim = midpoint

        def apportion(v, default_ancestor, dist):
            w = v.parent.children[v.number - 1] if v.number > 0 else None
            if w:
                vir = vor = v
                vil = w
                vol = v.parent.children[0]
                sir, sor = vir.mod, vor.mod
                sil, sol = vil.mod, vol.mod
                while next_right(vil) and next_left(vir):
                    vil = next_right(vil)
                    vir = next_left(vir)
                    vol = next_left(vol)
                    vor = next_right(vor)
                    vor.ancestor = v
                    shift = (vil.prelim + sil) - (vir.prelim + sir) + dist + (vil.w + vir.w) / 2.0
                    if shift > 0:
                        anc = ancestor(vil, v, default_ancestor)
                        move_subtree(anc, v, shift)
                        sir += shift
                        sor += shift
                    sil += vil.mod
                    sir += vir.mod
                    sol += vol.mod
                    sor += vor.mod
                if next_right(vil) and not next_right(vor):
                    vor.thread = next_right(vil)
                    vor.mod += sil - sor
                if next_left(vir) and not next_left(vol):
                    vol.thread = next_left(vir)
                    vol.mod += sir - sol
                    default_ancestor = v
            return default_ancestor

        def next_right(v):
            return v.children[-1] if v.children else v.thread

        def next_left(v):
            return v.children[0] if v.children else v.thread

        def move_subtree(wl, wr, shift):
            subtrees = wr.number - wl.number
            if subtrees > 0:
                wr.change -= shift / subtrees
                wr.shift += shift
                wl.change += shift / subtrees
                wr.prelim += shift
                wr.mod += shift

        def execute_shifts(v):
            shift = change = 0.0
            for w in reversed(v.children):
                w.prelim += shift
                w.mod += shift
                change += w.change
                shift += w.shift + change

        def ancestor(vil, v, default_ancestor):
            return vil.ancestor if (v.parent and vil.ancestor in v.parent.children) else default_ancestor

        def second_walk(v, m=0.0, depth=0):
            v.x = v.prelim + m
            v.y = depth * (level_gap + v.h)
            for w in v.children:
                second_walk(w, m + v.mod, depth + 1)

        first_walk(root)
        second_walk(root, -root.prelim)

    def measure(self, ctx, container) -> Size:
        roots, items = self._build_tree(container)
        if not items:
            return Size(0.0, 0.0)
        gap = float(self.opts.get("node_gap", 32.0))
        lgap = float(self.opts.get("level_gap", 64.0))
        pad = float(self.opts.get("pad", 24.0))
        for r in roots:
            self._buchheim(r, gap, lgap)
        min_x = min(n.x - n.w / 2.0 for n in items.values())
        max_x = max(n.x + n.w / 2.0 for n in items.values())
        min_y = min(n.y - n.h / 2.0 for n in items.values())
        max_y = max(n.y + n.h / 2.0 for n in items.values())
        w = max_x - min_x + 2 * pad
        h = max_y - min_y + 2 * pad
        dirn = self.opts.get("direction", "TB")
        return Size(h, w) if dirn in ("LR", "RL") else Size(w, h)

    def place(self, ctx, container, box) -> Placement:
        roots, items = self._build_tree(container)
        pos = {}
        if not items:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        gap = float(self.opts.get("node_gap", 32.0))
        lgap = float(self.opts.get("level_gap", 64.0))
        pad = float(self.opts.get("pad", 24.0))
        for r in roots:
            self._buchheim(r, gap, lgap)
        min_x = min(n.x - n.w / 2.0 for n in items.values())
        max_x = max(n.x + n.w / 2.0 for n in items.values())
        min_y = min(n.y - n.h / 2.0 for n in items.values())
        max_y = max(n.y + n.h / 2.0 for n in items.values())
        dirn = self.opts.get("direction", "TB")
        bx, by = box[0] + pad, box[1] + pad
        for cid, n in items.items():
            nx = n.x - min_x + bx + n.w / 2.0
            ny = n.y - min_y + by + n.h / 2.0
            if dirn == "LR":
                pos[cid] = (ny, nx)
            elif dirn == "BT":
                pos[cid] = (nx, box[3] - ny)
            else:
                pos[cid] = (nx, ny)
        return Placement(pos=pos, size=Size(box[2], box[3]))


register("tree", TreeLayout)

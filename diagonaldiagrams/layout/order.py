"""The order of each layer (DESIGN 7.2): few crossings, groups kept whole.

A layer holds nodes, dummies (the points where a long arrow passes a layer) and, for each group that
spans the layer, a left and a right border item with the group's contents between them. Sorting is
done per level of the group tree, so a group's members stay contiguous, and sibling groups keep one
order in every layer, so frames never cross. Within a level, items sort by the barycenter of their
neighbors in the layer just fixed; a node's `lane` or `order` hint is kept as a relative order.

order() runs down and up sweeps, then transposes neighbors that cross less swapped, and keeps the
best layering seen (ties keep the earlier one, so the spec's own order wins when it is as good).
"""


class Layering:
    """Items in layers, with what sorting needs to know about them.

    layers: [[item]] in order. kind: item -> "node" | "dummy" | "left" | "right" (group borders).
    owner: item -> the group it sits in (None at the top level); a border's owner is its group.
    parent: group -> parent group or None. span: group -> (first layer, last layer).
    up, down: item -> neighbor items one layer up or down (repeats allowed: one per arrow).
    hint: item -> sort key that must stay increasing among items of one level (lane, order).
    rank: group -> its place among its siblings.
    attach: port item -> its node: a port sorts with its node, on the side its neighbors pull it to.
    """
    __slots__ = ("layers", "kind", "owner", "parent", "span", "up", "down", "hint", "rank", "layer_of", "attach",
                 "held")

    def __init__(self):
        self.layers, self.kind, self.owner, self.parent, self.span = [], {}, {}, {}, {}
        self.up, self.down, self.hint, self.rank, self.layer_of = {}, {}, {}, {}, {}
        self.attach = {}  # port item -> the node it sits beside (where a back edge leaves or arrives)
        self.held = {}  # port item -> True to keep it left of its node, False right (set by _flip_ports)

    def add(self, item, layer, kind, owner=None):
        while len(self.layers) <= layer:
            self.layers.append([])
        self.layers[layer].append(item)
        self.kind[item], self.owner[item], self.layer_of[item] = kind, owner, layer
        self.up.setdefault(item, [])
        self.down.setdefault(item, [])

    def link(self, a, b):
        """An arrow segment from a (one layer up) to b."""
        self.down[a].append(b)
        self.up[b].append(a)


def _count(upper, lower, down):
    """Crossings between two adjacent layers: inversions among the segments, by an accumulator tree."""
    pos = {v: k for k, v in enumerate(lower)}
    south = []
    for u in upper:
        south.extend(sorted(pos[w] for w in down[u] if w in pos))
    if len(south) < 2:
        return 0
    first = 1
    while first < len(lower):
        first *= 2
    tree = [0] * (2 * first)
    first -= 1
    total = 0
    for p in south:
        i = p + first
        tree[i] += 1
        while i > 0:
            if i % 2:
                total += tree[i + 1]
            i = (i - 1) // 2
            tree[i] += 1
    return total


def crossings(L):
    return sum(_count(L.layers[r], L.layers[r + 1], L.down) for r in range(len(L.layers) - 1))


def _level_children(L, layer):
    """For one layer: group -> its direct contents in current order (items and child groups), plus
    the top level under None."""
    kids = {None: []}
    for it in layer:
        k = L.kind[it]
        g = L.owner[it]
        if it in L.attach:
            continue  # sorted with its node
        if k == "left":
            kids.setdefault(g, [])
            kids.setdefault(L.parent.get(g), []).append(("group", g))
        elif k != "right":
            kids.setdefault(g, []).append(("item", it))
    return kids


def _hint_start(L, r):
    """Layer r with its hinted items in hint order, frames kept whole. At each level of the frame
    tree the entries that carry a hint (an item its own, a lone frame the least of its items') trade
    places until their hints increase; the others keep theirs. Port items stay beside their nodes."""
    layer = L.layers[r]
    if not any(L.hint.get(it) is not None for it in layer):
        return
    kids = _level_children(L, layer)
    here = {v: k for k, v in enumerate(layer)}
    ports = {}
    for it in layer:
        if it in L.attach:
            ports.setdefault(L.attach[it], []).append(it)

    def build(g):
        entries, frames = [], []
        for kind, x in kids.get(g, []):
            if kind == "item":
                ps = ports.get(x, [])
                entries.append(([p for p in ps if here[p] < here[x]] + [x] + [p for p in ps if here[p] > here[x]],
                                L.hint.get(x)))
            else:
                frames.append(len(entries))
                entries.append(build(x))
        if len(frames) > 1:  # sibling frames keep their own order (_constrain); hints place a lone frame only
            for k in frames:
                entries[k] = (entries[k][0], None)
        idx = [k for k, (_, h) in enumerate(entries) if h is not None]
        for k, e in zip(idx, sorted((entries[k] for k in idx), key=lambda e: e[1])):
            entries[k] = e
        flat = [it for items, _ in entries for it in items]
        if g is not None:
            lb = ("L", g, r) if ("L", g, r) in L.kind else next(it for it in layer if L.kind[it] == "left" and L.owner[it] == g)
            rb = ("R", g, r) if ("R", g, r) in L.kind else next(it for it in layer if L.kind[it] == "right" and L.owner[it] == g)
            flat = [lb] + flat + [rb]
        hints = [h for _, h in entries if h is not None]
        return flat, (min(hints) if hints else None)
    flat, _ = build(None)
    if sorted(map(str, flat)) == sorted(map(str, layer)):
        L.layers[r] = flat


def _sort_layer(L, r, pos, nbrs):
    """Sorts layer r by the barycenter of each item's neighbors (nbrs: up or down) at positions pos."""
    layer = L.layers[r]
    if len(layer) <= 1:
        return
    kids = _level_children(L, layer)
    here = {v: k for k, v in enumerate(layer)}
    ports = {}
    if L.attach:
        for it in layer:
            if it in L.attach:
                ports.setdefault(L.attach[it], []).append(it)

    def solve(g):
        """(ordered items of group g with its borders, barycenter sum, neighbor count)."""
        entries = []
        for kind, x in kids.get(g, []):
            if kind == "item":
                ns = [pos[n] for n in nbrs[x] if n in pos]
                items = [x]
                if x in ports:  # its ports: on the side their neighbors lie, the furthest outermost
                    mine = sum(ns) / len(ns) if ns else None
                    left, right = [], []
                    for pt in ports[x]:
                        ps = [pos[n] for n in nbrs[pt] if n in pos]
                        b = sum(ps) / len(ps) if ps else None
                        outer = here[x] < len(layer) / 2.0  # a tie goes to the outside of the layer
                        if pt in L.held:
                            side_left = L.held[pt]
                        elif b is None:
                            side_left = here[pt] < here[x]
                        elif mine is None or abs(b - mine) < 1e-9:
                            side_left = outer
                        else:
                            side_left = b < mine
                        (left if side_left else right).append((b if b is not None else here[pt], pt))
                    items = [pt for _, pt in sorted(left)] + [x] + [pt for _, pt in sorted(right)]
                    if not ns:
                        ns = [b for b, _ in left + right]
                entries.append({"items": items, "sum": float(sum(ns)), "n": len(ns), "at": here[x],
                                "hint": L.hint.get(x), "group": None})
            else:
                items, s, n = solve(x)
                hints = [L.hint[i] for i in items if L.hint.get(i) is not None]  # a lone frame keeps its place among hinted items
                entries.append({"items": items, "sum": s, "n": n, "at": here[items[0]], "hint": min(hints) if hints else None,
                                "group": x})
        if len(entries) <= 1:
            flat = [it for e in entries for it in e["items"]]
        else:
            for e in entries:
                e["bc"] = e["sum"] / e["n"] if e["n"] else None
            frames = [e for e in entries if e["group"] is not None]
            if len(frames) > 1:  # sibling frames keep their rank order, which their hints could contradict
                for e in frames:
                    e["hint"] = None
            bound = bool(frames) or any(e["hint"] is not None for e in entries)  # else _constrain and _repair do nothing
            if bound:
                _constrain(entries, L)
            sortable = sorted((e for e in entries if e["bc"] is not None), key=lambda e: (e["bc"], e["at"]))
            fixed = [e for e in entries if e["bc"] is None]
            if not fixed:
                out = sortable
            else:
                out = list(sortable)
                rank_of = {id(e): k for k, e in enumerate(entries)}
                for e in fixed:  # an item with no neighbors keeps its place among its level
                    out.insert(min(rank_of[id(e)], len(out)), e)
            if bound:
                _repair(out, L)
            flat = [it for e in out for it in e["items"]]
        if g is not None:
            lb = ("L", g, r) if ("L", g, r) in L.kind else next(it for it in layer if L.kind[it] == "left" and L.owner[it] == g)
            rb = ("R", g, r) if ("R", g, r) in L.kind else next(it for it in layer if L.kind[it] == "right" and L.owner[it] == g)
            flat = [lb] + flat + [rb]
        return flat, sum(e["sum"] for e in entries), sum(e["n"] for e in entries)

    L.layers[r] = solve(None)[0]


def _constrain(entries, L):
    """Keeps sibling groups in their rank order and hinted items in hint order: their barycenters
    are made increasing in that order, so the sort can't swap them."""
    for key in (lambda e: L.rank.get(e["group"]) if e["group"] is not None else None,
                lambda e: e["hint"]):
        chain = sorted((e for e in entries if key(e) is not None), key=lambda e: (key(e), e["at"]))
        last = None
        for e in chain:
            if e["bc"] is None:
                e["bc"] = float(e["at"]) if last is None else max(float(e["at"]), last + 1e-6)
            if last is not None and e["bc"] <= last:
                e["bc"] = last + 1e-6
            last = e["bc"]


def _repair(out, L):
    """After the unsortable entries were put back, make the constrained ones increasing again by
    swapping out-of-order pairs (a few at most)."""
    for key in (lambda e: L.rank.get(e["group"]) if e["group"] is not None else None, lambda e: e["hint"]):
        idx = [k for k, e in enumerate(out) if key(e) is not None]
        vals = sorted((out[k] for k in idx), key=lambda e: (key(e), e["at"]))
        for k, e in zip(idx, vals):
            out[k] = e


def _transpose(L, r, frozen):
    """Swaps neighbors in layer r (same level, both plain items) when that crosses less."""
    layer = L.layers[r]
    if len(layer) < 2:
        return False
    swappable = False
    for k in range(len(layer) - 1):
        a, b = layer[k], layer[k + 1]
        if (L.kind[a] in ("node", "dummy") and L.kind[b] in ("node", "dummy") and L.owner[a] == L.owner[b]
                and a not in frozen and b not in frozen
                and not (L.hint.get(a) is not None and L.hint.get(b) is not None)):
            swappable = True
            break
    if not swappable:
        return False
    up_pos = {v: k for k, v in enumerate(L.layers[r - 1])} if r > 0 else {}
    dn_pos = {v: k for k, v in enumerate(L.layers[r + 1])} if r + 1 < len(L.layers) else {}
    up_nbrs = {it: [up_pos[x] for x in L.up[it] if x in up_pos] for it in layer}
    dn_nbrs = {it: [dn_pos[x] for x in L.down[it] if x in dn_pos] for it in layer}

    def c(a, b):
        n = 0
        pa, pb = up_nbrs[a], up_nbrs[b]
        for x in pa:
            for y in pb:
                if x > y:
                    n += 1
        pa, pb = dn_nbrs[a], dn_nbrs[b]
        for x in pa:
            for y in pb:
                if x > y:
                    n += 1
        return n
    improved = False
    for k in range(len(layer) - 1):
        a, b = layer[k], layer[k + 1]
        if (L.kind[a] not in ("node", "dummy") or L.kind[b] not in ("node", "dummy") or L.owner[a] != L.owner[b]
                or a in frozen or b in frozen):
            continue
        if L.hint.get(a) is not None and L.hint.get(b) is not None:
            continue
        if c(b, a) < c(a, b):
            layer[k], layer[k + 1] = b, a
            improved = True
    return improved


def order(L, iterations=24, patience=4, flips=True):
    """Orders L.layers in place for few crossings. Returns the crossing count."""
    if len(L.layers) < 2:
        return 0
    for r in range(len(L.layers)):  # hinted items start in hint order: a start that crosses nothing skips the sweeps
        _hint_start(L, r)
    best = [list(x) for x in L.layers]
    best_c = crossings(L)
    frozen = {it for it, h in L.hint.items() if h is not None} | set(L.attach.values()) | set(L.attach)
    stale = 0
    for i in range(iterations):
        if best_c == 0:
            break
        if i % 2 == 0:
            for r in range(1, len(L.layers)):
                _sort_layer(L, r, {v: k for k, v in enumerate(L.layers[r - 1])}, L.up)
        else:
            for r in range(len(L.layers) - 2, -1, -1):
                _sort_layer(L, r, {v: k for k, v in enumerate(L.layers[r + 1])}, L.down)
        for _ in range(4):
            if not any([_transpose(L, r, frozen) for r in range(len(L.layers))]):  # a list: every layer, each time
                break
        c = crossings(L)
        if c < best_c:
            best, best_c, stale = [list(x) for x in L.layers], c, 0
        else:
            stale += 1
            if stale >= patience:
                break
    L.layers = best
    if flips and best_c and L.attach:
        best_c = _flip_ports(L, best_c)
    return best_c


def _flip_ports(L, best_c, most=30):
    """A port on one side of its node, with the arrow's dummies following, can cross less than the
    sweeps found: try each port on the other side, re-sweep briefly, keep what crosses less."""
    chain_of = {}
    for it in L.kind:
        if isinstance(it, tuple) and len(it) == 3:
            chain_of.setdefault(it[1], []).append(it)
    for pt in list(L.attach)[:most]:
        if best_c == 0:
            break
        eid = pt[1]
        mine_list = chain_of.get(eid, [])
        if not mine_list:
            continue
        mine = set(mine_list)
        chain_layers = [L.layer_of[it] for it in mine_list]
        lo, hi = min(chain_layers), max(chain_layers)
        if not _chain_crosses(L, eid, mine, lo, hi):  # its arrow crosses nothing: no side can do better
            continue
        saved = [list(x) for x in L.layers]
        layer = L.layers[L.layer_of[pt]]
        nid = L.attach[pt]
        side_left = layer.index(pt) > layer.index(nid)
        layer.remove(pt)
        k = layer.index(nid)
        layer.insert(k if side_left else k + 1, pt)
        L.held[pt] = side_left
        frozen = {it for it, h in L.hint.items() if h is not None} | set(L.attach.values()) | set(L.attach)
        for i in range(4):
            if i % 2 == 0:
                for r in range(lo + 1, hi + 1):
                    _sort_layer(L, r, {v: k for k, v in enumerate(L.layers[r - 1])}, L.up)
            else:
                for r in range(hi - 1, lo - 1, -1):
                    _sort_layer(L, r, {v: k for k, v in enumerate(L.layers[r + 1])}, L.down)
            for _ in range(2):
                if not any([_transpose(L, r, frozen) for r in range(lo, hi + 1)]):
                    break
        aff = range(max(0, lo - 1), min(len(L.layers) - 1, hi + 1))
        old_cross = sum(_count(saved[r], saved[r + 1], L.down) for r in aff)
        new_cross = sum(_count(L.layers[r], L.layers[r + 1], L.down) for r in aff)
        c = best_c - old_cross + new_cross
        if c < best_c:
            best_c = c
        else:
            L.layers = saved
            del L.held[pt]
    return best_c


def _chain_crosses(L, eid, mine=None, lo=0, hi=None):
    """Whether any segment of arrow eid's chain (its ports and dummies) crosses another segment."""
    if mine is None:
        mine = {it for it in L.kind if isinstance(it, tuple) and len(it) == 3 and it[1] == eid}
    if hi is None:
        hi = len(L.layers) - 1
    for r in range(max(0, lo - 1), min(len(L.layers) - 1, hi + 1)):
        upper, lower = L.layers[r], L.layers[r + 1]
        if not any(it in mine for it in upper) and not any(it in mine for it in lower):
            continue
        pos = {v: k for k, v in enumerate(lower)}
        segs = [(k, pos[w], u in mine or w in mine) for k, u in enumerate(upper) for w in L.down[u] if w in pos]
        for a in segs:
            if a[2] and any((a[0] - b[0]) * (a[1] - b[1]) < 0 for b in segs if not b[2]):
                return True
    return False

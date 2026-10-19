"""Horizontal coordinates for an ordered layering: Brandes and Köpf (2001), as dagre builds it.

Four alignments (up/down x left/right) each line items up with a median neighbor, preferring to keep
long arrows straight (an inner segment between two dummies wins over a crossing segment), then pack
the aligned blocks as tight as their separation allows. The result is the median of the four, aligned
to the narrowest. Group borders are forced into one block per side, so every frame is a rectangle.

If the median breaks a separation (it can, with items of different widths), the mean of the four is
used instead: each of them is valid and the constraints are linear, so their mean is valid too.

Given where items stood in an earlier drawing (prev), any weighted mean of the four is valid for the
same reason, so the one closest to the earlier places is taken instead: an edit then moves the rest
of the figure as little as the four allow (PLAN P4.9).

A flow's main path (spine) is forced the way borders are, so all four keep it straight. On an edit
the four without it join the mix, since a path that flips sides would otherwise move every box.
"""
import math

INF = float("inf")


def _type1(layers, up, inner):
    """Segments that cross an inner segment (dummy to dummy): those may not be aligned."""
    conflicts = set()
    for r in range(1, len(layers)):
        prev, layer = layers[r - 1], layers[r]
        ppos = {v: k for k, v in enumerate(prev)}
        k0, scan = 0, 0
        last = layer[-1] if layer else None
        for i, v in enumerate(layer):
            w = next((u for u in up[v] if inner(u, v)), None)
            k1 = ppos[w] if w is not None else len(prev)
            if w is not None or v == last:
                for s in layer[scan:i + 1]:
                    for u in up[s]:
                        p = ppos.get(u)
                        if p is not None and (p < k0 or k1 < p) and not inner(u, s):
                            conflicts.add((u, s))
                scan, k0 = i + 1, k1
    return conflicts


def _align(layers, nbrs, conflicts, forced):
    """BK's vertical alignment over layers in the given order (nbrs: the neighbors in the layer
    before). forced: item -> the neighbor it must align with."""
    root = {v: v for layer in layers for v in layer}
    align = dict(root)
    pos = {v: k for layer in layers for k, v in enumerate(layer)}
    for layer in layers:
        bound, lim = [INF] * len(layer), INF  # an alignment may not pass a forced one further right
        for i in range(len(layer) - 1, -1, -1):
            bound[i] = lim
            f = forced.get(layer[i])
            if f is not None:
                lim = min(lim, pos[f])
        prev = -1
        for i, v in enumerate(layer):
            f = forced.get(v)
            if f is not None:
                if prev < pos[f]:
                    align[f] = v
                    align[v] = root[v] = root[f]
                    prev = pos[f]
                continue
            ws = sorted(set(nbrs[v]), key=pos.get)
            if not ws:
                continue
            mp = (len(ws) - 1) / 2.0
            for m in range(int(math.floor(mp)), int(math.ceil(mp)) + 1):
                w = ws[m]
                if (align[v] == v and prev < pos[w] < bound[i]
                        and (w, v) not in conflicts and (v, w) not in conflicts):
                    align[w] = v
                    align[v] = root[v] = root[w]
                    prev = pos[w]
    return root, align


def _compact(layers, root, align, sep, kind, reverse):
    """Places blocks: as far left as separation allows, then each moved right into unused space."""
    edges = {}  # (block a, block b) -> least distance, a to the left of b
    for layer in layers:
        for u, v in zip(layer, layer[1:]):
            s = sep(v, u) if reverse else sep(u, v)
            key = (root[u], root[v])
            if s > edges.get(key, -INF):
                edges[key] = s
    blocks = list(dict.fromkeys(root[v] for layer in layers for v in layer))
    ins = {b: [] for b in blocks}
    outs = {b: [] for b in blocks}
    for (a, b), s in edges.items():
        outs[a].append((b, s))
        ins[b].append((a, s))
    indeg = {b: len(ins[b]) for b in blocks}
    topo = [b for b in blocks if indeg[b] == 0]
    for b in topo:
        for c, _ in outs[b]:
            indeg[c] -= 1
            if indeg[c] == 0:
                topo.append(c)
    if len(topo) != len(blocks):
        return None  # not a DAG: an alignment crossed another
    xs = {}
    for b in topo:
        xs[b] = max((xs[a] + s for a, s in ins[b]), default=0.0)
    keep = "left" if reverse else "right"  # a group's far border stays put, or the frame would widen
    for b in reversed(topo):
        if outs[b] and kind.get(b) != keep:
            xs[b] = max(xs[b], min(xs[c] - s for c, s in outs[b]))
    return {v: xs[root[v]] for layer in layers for v in layer}


def valid(layers, xs, sep, forced_up):
    """True when xs keeps every separation and holds every forced_up chain (group borders) in line."""
    return _valid(layers, xs, sep, [(a, b) for b, a in forced_up.items()])


def _valid(layers, xs, sep, chains):
    for layer in layers:
        for u, v in zip(layer, layer[1:]):
            if xs[v] - xs[u] < sep(u, v) - 0.01:
                return False
    return all(abs(xs[a] - xs[b]) < 0.01 for a, b in chains)


def _nearest(vals, prev, steps=4):
    """The weighted mean of the alignments vals that lies closest to prev, after the best shift of
    the whole drawing; weights in 1/steps. None when fewer than two items have an earlier place."""
    keys = [v for v in vals[0] if prev and v in prev]
    if len(keys) < 2:
        return None
    best = None
    n = len(vals)

    def weights(k, left):
        if k == n - 1:
            yield (left,)
            return
        for w in range(left + 1):
            for rest in weights(k + 1, left - w):
                yield (w,) + rest
    for ws in weights(0, steps):
        xs = [sum(w * xs_[v] for w, xs_ in zip(ws, vals)) / steps for v in keys]
        t = sum(prev[v] - x for v, x in zip(keys, xs)) / len(keys)
        cost = sum((x + t - prev[v]) ** 2 for v, x in zip(keys, xs))
        if best is None or cost < best[0] - 1e-6:
            best = (cost, ws)
    ws = best[1]
    return {v: sum(w * xs_[v] for w, xs_ in zip(ws, vals)) / steps for v in vals[0]}


def _four(layers, up, down, sep, kind, conflicts, forced_up):
    """The four alignments, packed: {"ul"|"ur"|"dl"|"dr": {item: x}}, each that packed cleanly."""
    forced_down = {b: a for a, b in forced_up.items()}
    xss = {}
    for vert in ("u", "d"):
        lays = layers if vert == "u" else layers[::-1]
        nbrs, forced = (up, forced_up) if vert == "u" else (down, forced_down)
        for horiz in ("l", "r"):
            ls = lays if horiz == "l" else [layer[::-1] for layer in lays]
            root, align = _align(ls, nbrs, conflicts, forced)
            xs = _compact(ls, root, align, sep, kind, horiz == "r")
            if xs is None:
                continue
            if horiz == "r":
                xs = {v: -x for v, x in xs.items()}
            xss[vert + horiz] = xs
    return xss


def coordinates(layers, up, down, width, sep, kind, inner, forced_up, prev=None, straight=None):
    """{item: x of its center}. layers in order; up/down: neighbors; width: item -> width; sep(a, b):
    least distance between the centers of a and b when a is directly left of b; kind: item -> kind
    ("left"/"right" mark group borders); inner(u, v): u-v is an inner segment; forced_up: item -> the
    item above it that it must align with (group border chains); prev: item -> its x in an earlier
    drawing, in any frame (a shift of the whole drawing costs nothing); straight: more pairs like
    forced_up that all four alignments keep (a flow's main path, spine()). With prev as well, the four
    alignments without them are mixed in too, so an edit may bend the path rather than move the figure."""
    if not any(layers):
        return {}
    conflicts = _type1(layers, up, inner)
    xss = _four(layers, up, down, sep, kind, conflicts, {**forced_up, **straight} if straight else forced_up)
    loose = _four(layers, up, down, sep, kind, conflicts, forced_up) if straight and prev else {}
    if not xss:
        xss, loose = loose or _four(layers, up, down, sep, kind, conflicts, forced_up), {}
    if not xss:
        x, out = 0.0, {}
        for layer in layers:  # nothing aligned cleanly: pack each layer from the left
            x = 0.0
            for k, v in enumerate(layer):
                x = x + sep(layer[k - 1], v) if k else 0.0
                out[v] = x
        return out

    def span(xs):
        return max(x + width[v] / 2 for v, x in xs.items()) - min(x - width[v] / 2 for v, x in xs.items())
    smallest = min(xss.values(), key=span)
    lo, hi = min(smallest.values()), max(smallest.values())

    def to_smallest(key, xs):
        delta = lo - min(xs.values()) if key[1] == "l" else hi - max(xs.values())
        return {v: x + delta for v, x in xs.items()}
    for key, xs in list(xss.items()):
        if xs is not smallest:
            xss[key] = to_smallest(key, xs)
    vals = list(xss.values())
    items = list(vals[0])
    chains = [(a, b) for b, a in forced_up.items()]
    near = _nearest(vals + [to_smallest(key, xs) for key, xs in loose.items()], prev)
    if near is not None and _valid(layers, near, sep, chains):
        return near
    if len(vals) == 4:
        out = {}
        for v in items:
            s = sorted(xs[v] for xs in vals)
            out[v] = (s[1] + s[2]) / 2.0
        if _valid(layers, out, sep, chains):
            return out
    out = {v: sum(xs[v] for xs in vals) / len(vals) for v in items}
    if _valid(layers, out, sep, chains):
        return out
    return smallest

def _isotonic(vals, weights):
    """Nondecreasing values closest to vals in weighted squares (pool adjacent violators)."""
    blocks = []  # [weighted sum, weight, count]
    for v, w in zip(vals, weights):
        blocks.append([v * w, w, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            a = blocks.pop()
            blocks[-1] = [blocks[-1][0] + a[0], blocks[-1][1] + a[1], blocks[-1][2] + a[2]]
    out = []
    for total, w, n in blocks:
        out += [total / w] * n
    return out


def balance(layers, up, down, kind, xs, sep):
    """Centers each node over what it calls and each sink under what calls it, as far as its layer
    allows (an architecture's look: a gateway over its services, not over the median one).

    Bottom-up, a node with neighbors in the layer below moves to the middle of their span; top-down, a
    node with none there moves to the middle of its neighbors above. Each layer is solved whole: the
    positions closest to those targets that keep every separation (an isotonic regression, so nodes
    that want one spot share it evenly). Dummies, ports and frame borders stay where they are, so long
    arrows stay straight and frames stay rectangles. Returns new {item: x}."""
    xs = dict(xs)
    fixed, loose = 1e9, 1e-3

    def solve(layer, nbrs, only_free):
        if not layer:
            return
        offs, vals, ws, o = [], [], [], 0.0
        for k, v in enumerate(layer):
            if k:
                o += sep(layer[k - 1], v)
            offs.append(o)
            ns = [xs[u] for u in nbrs.get(v, ()) if u in xs]
            if kind.get(v) != "node":
                t, w = xs[v], fixed
            elif ns and not (only_free and down.get(v)):
                t, w = (min(ns) + max(ns)) / 2.0, 1.0
            else:
                t, w = xs[v], loose
            vals.append(t - o)
            ws.append(w)
        for v, y, o in zip(layer, _isotonic(vals, ws), offs):
            xs[v] = y + o
    for layer in reversed(layers[:-1]):
        solve(layer, down, False)
    for layer in layers[1:]:
        solve(layer, up, True)
    return xs


def spine(layers, paths, up, hold, forced_up):
    """A flow's main path, to run straight down: each node over the child that continues the longest
    path below it, and each child under the parent with the longest path above it (lengths in boxes,
    so a long arrow that skips steps loses to the steps). A tie picks no one, so a decision whose
    branches are equally long stays centered over them. paths: (top node, [dummies top to bottom],
    bottom node) per arrow going down. An arrow is left to the alignments when its line would cross
    a frame border, a segment hold(u, v) keeps straight, or an arrow kept before it (longest paths
    first). Returns new forced_up pairs: item -> the item above it that it must align with."""
    pos = {v: k for layer in layers for k, v in enumerate(layer)}
    layer_of = {v: r for r, layer in enumerate(layers) for v in layer}
    kids, parents = {}, {}
    for p in paths:
        kids.setdefault(p[0], {}).setdefault(p[2], p)  # the first arrow between two boxes
        parents.setdefault(p[2], {}).setdefault(p[0], p)
    nodes = sorted(set(kids) | set(parents), key=lambda v: (layer_of[v], pos[v]))
    below, above = {}, {}
    for v in reversed(nodes):
        below[v] = 1 + max((below[c] for c in kids.get(v, ())), default=0)
    for v in nodes:
        above[v] = 1 + max((above[p] for p in parents.get(v, ())), default=0)

    def best(cands, score):
        top = max((score[c] for c in cands), default=None)
        win = [c for c in cands if score[c] == top]
        return win[0] if len(win) == 1 else None
    child = {v: best(list(kids.get(v, ())), below) for v in nodes}
    picked = []
    for v in nodes:
        p = best([p for p in parents.get(v, ()) if child[p] == v], above)
        if p is not None:
            picked.append(kids[p][v])
    picked.sort(key=lambda p: (-(above[p[0]] + below[p[2]]), layer_of[p[0]], pos[p[0]]))
    held = {}  # layer r -> [(position above, position below)] of the segments from r to r + 1 held
    for b, a in forced_up.items():
        held.setdefault(layer_of[a], []).append((pos[a], pos[b]))
    for r in range(len(layers) - 1):
        for v in layers[r + 1]:
            for u in up.get(v, ()):
                if hold(u, v):
                    held.setdefault(r, []).append((pos[u], pos[v]))
    out = {}
    for top, ds, bot in picked:
        seq = [top] + list(ds) + [bot]
        segs = [(layer_of[a], pos[a], pos[b]) for a, b in zip(seq, seq[1:])]
        if any((a - x) * (b - y) < 0 for r, a, b in segs for x, y in held.get(r, ())):
            continue
        for r, a, b in segs:
            held.setdefault(r, []).append((a, b))
        for a, b in zip(seq, seq[1:]):
            out[b] = a
    return out

"""Horizontal coordinates for an ordered layering: Brandes and Köpf (2001), as dagre builds it.

Four alignments (up/down x left/right) each line items up with a median neighbor, preferring to keep
long arrows straight (an inner segment between two dummies wins over a crossing segment), then pack
the aligned blocks as tight as their separation allows. The result is the median of the four, aligned
to the narrowest. Group borders are forced into one block per side, so every frame is a rectangle.

If the median breaks a separation (it can, with items of different widths), the mean of the four is
used instead: each of them is valid and the constraints are linear, so their mean is valid too.
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


def _valid(layers, xs, sep, chains):
    for layer in layers:
        for u, v in zip(layer, layer[1:]):
            if xs[v] - xs[u] < sep(u, v) - 0.01:
                return False
    return all(abs(xs[a] - xs[b]) < 0.01 for a, b in chains)


def coordinates(layers, up, down, width, sep, kind, inner, forced_up):
    """{item: x of its center}. layers in order; up/down: neighbors; width: item -> width; sep(a, b):
    least distance between the centers of a and b when a is directly left of b; kind: item -> kind
    ("left"/"right" mark group borders); inner(u, v): u-v is an inner segment; forced_up: item -> the
    item above it that it must align with (group border chains)."""
    if not any(layers):
        return {}
    forced_down = {b: a for a, b in forced_up.items()}
    conflicts = _type1(layers, up, inner)
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
    for key, xs in list(xss.items()):
        if xs is smallest:
            continue
        delta = lo - min(xs.values()) if key[1] == "l" else hi - max(xs.values())
        xss[key] = {v: x + delta for v, x in xs.items()}
    vals = list(xss.values())
    items = list(vals[0])
    chains = [(a, b) for b, a in forced_up.items()]
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

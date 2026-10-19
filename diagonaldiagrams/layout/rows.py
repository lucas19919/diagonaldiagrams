"""Rows for a layer too wide for where the figure goes (a fit's max_width: DESIGN 7.3, layered.layout()).

In a narrow docs column a layer of eight services side by side shrinks the whole figure. spread()
deals such a layer's boxes over rows of their own, stacked in columns one box under another, the
arrows down to a column's lower boxes running beside it like the teeth of a comb.
"""


def spread(rank, ids, info, E, unit_of, o):
    """(rank, first, stack): ranks with layers dealt over rows of their own, the layers below moving
    down to make room; for each node of a layer so dealt, the rank of the layer's first row; and for
    each box dealt under another, that box, which bk keeps it in line with.

    How far it goes is o["more_rows"], one step a try (layered.layout()). From 0 to 2, each layer too
    wide for o["max_width"] on its own is dealt over as many rows as its width needs, plus that many.
    It goes in units: one top frame's members in it, one node, or the nodes an edit keeps in one
    layer. Units an arrow within the layer joins stay together while they fit, and a unit too wide
    goes in node by node. The units, in the spec's order, are dealt in turn, so each column holds the
    next few units one under another, and the arrows down to its lower boxes run beside it
    (layered._layout keys their dummies to the boxes they go to). At 3 each too-wide layer, and at 4
    every layer, puts one box in a row, an arrow within the layer running down from its source."""
    most, gap, pad, step = o["max_width"], o["node_gap"], 2 * o["group_pad"], o["more_rows"]
    layers = {}
    for i in ids:
        layers.setdefault(rank[i], []).append(i)

    def width(u, framed):
        return sum(info[i]["w"] for i in u) + gap * (len(u) - 1) + (pad if framed else 0)

    def downward(layer, r):  # one a row: an arrow's source above its target, else the spec's order
        left = sorted(layer, key=lambda i: info[i]["k"])
        into = {i: {e["from"] for e in E if e["to"] == i and e["from"] != i and rank[e["from"]] == r} for i in left}
        out = []
        while left:
            i = next((i for i in left if not into[i] - set(out)), left[0])
            left.remove(i)
            out.append(i)
        return [[i] for i in out]
    out, first, stack, shift = {}, {}, {}, 0
    for r in sorted(layers):
        units, framed, home = {}, {}, {}
        for i in sorted(layers[r], key=lambda i: info[i]["k"]):
            k = unit_of(i)
            units.setdefault(k, []).append(i)
            framed[k] = not (isinstance(k, tuple) and k[0] == "node")
            home[i] = k
        for e in E:  # an arrow within the layer: its two ends' units as one, if that fits
            ka, kb = home.get(e["from"]), home.get(e["to"])
            if ka is None or kb is None or ka == kb or rank[e["from"]] != r or rank[e["to"]] != r:
                continue
            both = sorted(units[ka] + units[kb], key=lambda i: info[i]["k"])
            if width(both, framed[ka] or framed[kb]) <= most:
                units[ka], framed[ka] = both, framed[ka] or framed[kb]
                del units[kb]
                for i in both:
                    home[i] = ka
        todo = []
        for k, u in sorted(units.items(), key=lambda ku: min(info[i]["k"] for i in ku[1])):
            if width(u, framed[k]) > most and len(u) > 1:
                todo += [([i], framed[k]) for i in u]  # its frame spans the rows its members go to
            else:
                todo.append((u, framed[k]))
        need = sum(width(u, f) for u, f in todo) + gap * (len(todo) - 1)
        need += sum(max(0.0, room - gap) for (a, b), room in (o.get("flat_room") or {}).items()  # labels between
                    if a != b and rank.get(a) == r and rank.get(b) == r)
        rows = [layers[r]]
        if len(layers[r]) > 1 and (step >= 4 or (step == 3 and need > most)):
            rows = downward(layers[r], r)
            stack.update((a[0], b[0]) for a, b in zip(rows[1:], rows))
        elif need > most and len(todo) > 1:
            n = min(len(todo), int(-(-need // most)) + step)
            rows = [[] for _ in range(n)]
            for j, (u, _) in enumerate(todo):
                rows[j % n] += u
                if j % n:  # under the unit before it, in its column
                    stack[u[0]] = todo[j - 1][0][0]
        for j, row in enumerate(rows):
            for i in row:
                out[i] = r + shift + j
                if len(rows) > 1:
                    first[i] = r + shift
        shift += len(rows) - 1
    return out, first, stack

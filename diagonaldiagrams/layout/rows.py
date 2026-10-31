"""Rows for a layer too wide for where the figure goes (a fit's max_width; see layered.layout()).

In a narrow docs column a layer of eight services side by side shrinks the whole figure. spread()
deals such a layer's boxes over rows of their own, stacked in columns one box under another, the
arrows down to a column's lower boxes running beside it like the teeth of a comb.
"""


def spread(rank, ids, info, E, unit_of, o):
    """(rank, first, stack): ranks with layers dealt over rows of their own, the layers below moving
    down to make room; for each node of a layer so dealt, the rank of the layer's first row; and for
    each box dealt under another, that box, which bk keeps it in line with.

    How far it goes is o["more_rows"], one step a try (layered.layout()). At -1 the units go side by
    side in as few rows as fit (_pack), no box kept under another. From 0 to 2, each layer too
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
        if step < 0 and need > most and len(todo) > 1:
            rows = _pack(todo, r, rank, ids, E, unit_of, width, o)
        elif len(layers[r]) > 1 and (step >= 4 or (step == 3 and need > most)):
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


def _pack(todo, r, rank, ids, E, unit_of, width, o):
    """A too-wide layer's units side by side in as few rows as fit (o["more_rows"] -1), so a frame that
    fits stays whole and its boxes stand side by side under what calls them. A frame begun in a layer
    above goes in the first row and one that goes on below in the last, so neither spans an empty row.
    The rest go in turn, those with no arrow on down first: each in the first row with room for it and
    for the lanes passing each row, the arrows from above down to the rows below it and from the rows
    above it on down, so the arrows out of the lower rows stay short."""
    most, gap = o["max_width"], o["node_gap"]
    above = {unit_of(i) for i in ids if rank[i] < r}
    below = {unit_of(i) for i in ids if rank[i] > r}
    into = [sum(1 for e in E if e["to"] in u and rank[e["from"]] < r) for u, _ in todo]
    onto = [sum(1 for e in E if e["from"] in u and rank[e["to"]] > r) for u, _ in todo]
    head = [k for k, (u, _) in enumerate(todo) if unit_of(u[0]) in above]
    tail = [k for k, (u, _) in enumerate(todo) if unit_of(u[0]) in below and k not in head]
    rest = [k for k in range(len(todo)) if k not in head and k not in tail]
    rest.sort(key=lambda k: onto[k] > 0)

    def lanes(n):  # n arrows passing a row: a gap each, and room beside the boxes
        return n * o["edge_gap"] + 2 * o["side_gap"] - gap if n else 0.0

    def fits(rows):
        for j, row in enumerate(rows):
            n = sum(into[k] for row2 in rows[j + 1:] for k in row2) + sum(onto[k] for row2 in rows[:j] for k in row2)
            if sum(width(*todo[k]) for k in row) + gap * (len(row) - 1) + lanes(n) > most:
                return False
        return True
    rows = [[]]
    for k in head + rest:
        j = next((j for j in range(len(rows)) if not rows[j]
                  or fits(rows[:j] + [rows[j] + [k]] + rows[j + 1:])), None)
        if j is None:
            rows.append([])
            j = len(rows) - 1
        rows[j].append(k)
    for k in tail:
        if rows[-1] and not fits(rows[:-1] + [rows[-1] + [k]]):
            rows.append([])
        rows[-1].append(k)
    return [[i for k in sorted(row) for i in todo[k][0]] for row in rows if row]

"""Room for the arrows' labels (PLAN B29).

The layout keeps room for a label between two neighbors in a layer (flat_room), but nothing for a label
beside an arrow that climbs between layers. Inside a frame the border can stand 16 px from the arrow;
beside a back edge's climb the boxes of the column stand 32 px away. So once the routes are drawn (and
wrapped), make_room places every label as diagrams.py will: route.labels, with the same obstacles (boxes,
frame borders, the canvas edge, the labels placed before it, and the arrows as soft obstacles).

A label that finds no spot clear of the hard obstacles gets room at its first spot. A strip of empty
space opens between the label and what blocks it: everything past the strip moves over, and a frame it
crosses widens. When only the canvas edge blocks it, the figure reaches further instead. A strip never
cuts a box or a label, and it only widens what it crosses, so arrows stay off boxes and off each other's
lines. A figure whose labels all fit draws exactly as before.

Everything here is in the layered layout's top-to-bottom frame, after wrap and before any turn.
"""
from ..route.labels import GAP, first_spot, label_box, place_label

TITLE = 20.0  # a frame's title band, which diagrams.py keeps labels out of
FAR = 1e9


def _hits(b, boxes):
    return [a for a in boxes if b[0] < a[2] + 2 and a[0] - 2 < b[2] and b[1] < a[3] + 2 and a[1] - 2 < b[3]]


def _boxes(pos, info):
    return [(x - info[n]["w"] / 2.0, y - info[n]["h"] / 2.0, x + info[n]["w"] / 2.0, y + info[n]["h"] / 2.0)
            for n, (x, y) in pos.items()]


def _strips(frames):
    out = []
    for x0, y0, x1, y1 in frames.values():
        out += [(x0, y0 - 1, x1, y0 + 1), (x0, y1 - 1, x1, y1 + 1), (x0 - 1, y0, x0 + 1, y1), (x1 - 1, y0, x1 + 1, y1),
                (x0, y0, x1, y0 + TITLE)]
    return out


def _segs(routes):
    return [(min(p[0], q[0]) - 1, min(p[1], q[1]) - 1, max(p[0], q[0]) + 1, max(p[1], q[1]) + 1)
            for r in routes.values() for p, q in zip(r.points, r.points[1:])]


def _canvas(pos, info, frames, routes, reach, extra, min_width, margin):
    """The canvas edges, as diagrams.py sets them: the figure's extent plus the margin, centered in the
    least width."""
    boxes = _boxes(pos, info) + list(frames.values())
    xs = [p[0] for r in routes.values() for p in r.points] + list(extra)
    lo = min([b[0] for b in boxes] + xs)
    hi = max([b[2] for b in boxes] + xs + [pos[n][0] + d for n, d in reach.items() if n in pos])
    W = max(min_width + 2 * margin, int(hi - lo + 2 * margin + 0.999))
    left = lo - (W - (hi - lo)) / 2.0
    return [(left - 40, -FAR, left, FAR), (left + W, -FAR, left + W + 40, FAR)]


def make_room(pos, info, frames, routes, widths, reach=None, min_width=0.0, margin=0.0):
    """Opens room for labels, in place: pos {node: (x, y)}, frames {group: box}, routes (their points).
    widths: {edge id: pill width}. reach: {node: how far past its center the figure reaches} (a self-loop
    and its label). Returns the x of points the figure's extent must take in."""
    reach = reach or {}
    extra, placed = [], []
    fixed = soft = canvas = None
    for eid, r in routes.items():
        if eid not in widths or len(r.points) < 2:
            continue
        w = widths[eid]
        for attempt in range(3):  # a strip, then perhaps the canvas
            if fixed is None:
                fixed = _boxes(pos, info) + _strips(frames)
                soft = _segs(routes)
                canvas = _canvas(pos, info, frames, routes, reach, extra, min_width, margin)
            avoid = fixed + placed + canvas
            mx, my, vert = first_spot(r.points, list(frames.values()), r.tooth)
            c = place_label(mx, my, vert, None, r.points, avoid, soft, w, GAP)
            box = label_box(c[0], c[1], None, c[2], c[3], w, GAP)
            if attempt == 2 or not _hits(box, avoid):
                break
            if not _open(mx, my, vert, w, fixed + placed, canvas, soft, pos, info, frames, routes, placed, extra, margin):
                break
            fixed = None
        placed.append(box)
    return extra


def _open(mx, my, vert, w, solid, canvas, soft, pos, info, frames, routes, placed, extra, margin):
    """Room for a label at its first spot (mx, my), on the side where it crosses fewer arrows, else the
    narrower strip. Returns True when something moved."""
    best = None
    for flip in (False, True):
        b = label_box(mx, my, None, vert, flip, w, GAP)
        block = _hits(b, solid)
        edge = _hits(b, canvas)
        if all(a[0] > mx for a in block + edge):  # all on the right: push them right
            if block:
                stop = min(a[0] for a in block)
                cut = _free(mx, stop, pos, info, placed)
                d = b[2] + 2.5 - stop
            else:
                cut, d = None, b[2] + 2.5 - edge[0][0]
        elif all(a[2] < mx for a in block + edge):  # all on the left: push the label's side right
            if block:
                stop = max(a[2] for a in block)
                cut = _free(stop, mx, pos, info, placed)
                d = stop + 2.5 - b[0]
            else:
                cut, d = None, edge[0][2] + 2.5 - b[0]
        else:
            continue
        if block and cut is None:
            continue
        cost = (len(_hits(b, soft)), d)
        if best is None or cost[0] < best[0][0] or cost[0] == best[0][0] and d < best[0][1] - 0.01:
            best = (cost, cut, bool(block), b)
    if best is None:
        return False
    (_, d), cut, strip, b = best
    if strip:
        _shift(cut, d, pos, frames, routes, placed, extra)
    elif b[2] > mx:  # only the canvas: the figure reaches past the label
        extra.append(b[2] + 2.5 - margin)
    else:
        extra.append(b[0] - 2.5 + margin)
    return True


def _free(lo, hi, pos, info, placed):
    """An x strictly between lo and hi that cuts no box and no label, or None."""
    spans = [(x - info[n]["w"] / 2.0, x + info[n]["w"] / 2.0) for n, (x, y) in pos.items()]
    spans += [(b[0], b[2]) for b in placed]
    x = lo + 0.5
    while x < hi:
        inside = [e for s, e in spans if s <= x <= e]
        if not inside:
            return x
        x = max(inside) + 0.5
    return None


def _shift(cut, d, pos, frames, routes, placed, extra):
    """Opens a strip d wide at x = cut: everything past it moves right."""
    def f(x):
        return x + d if x > cut else x
    for n, (x, y) in list(pos.items()):
        pos[n] = (f(x), y)
    for g, (x0, y0, x1, y1) in list(frames.items()):
        frames[g] = (f(x0), y0, f(x1), y1)
    for r in routes.values():
        r.points = [(f(x), y) for x, y in r.points]
    placed[:] = [(f(b[0]), b[1], f(b[2]), b[3]) for b in placed]
    extra[:] = [f(x) for x in extra]

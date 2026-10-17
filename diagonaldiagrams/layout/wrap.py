"""Wrapping a tall layered layout into columns (DESIGN 7.3, PLAN P4.2 and P4.8).

A 40-step flow drawn in one column is a 4000 px strip. wrap() cuts the layers into chunks of about
equal height and sets the chunks side by side, so the figure lands near the target aspect ratio.
Cuts fall only between layers that no group frame spans. An arrow that crosses a cut leaves its chunk
at the bottom, runs along a corridor under it, climbs the gap between the chunks, crosses over the top
of the next chunk and drops into its target (an arrow going back up does the same in reverse). Every
arrow in a corridor has a track and a column of its own, ordered so they don't cross one another.

Everything here is in the layered layout's top-to-bottom frame, before it is turned for LR, BT or RL.
"""
import math


def _choose(heights, cuttable, width_of, target, most=8):
    """(cuts, aspect): the layer indices after which to cut, for the column count whose aspect ratio
    lands nearest the target. heights: per layer, the height it adds (its band and the gap above)."""
    total = sum(heights)
    if total <= 0:
        return [], 0.0
    best = None
    for k in range(1, min(most, len(heights)) + 1):
        cuts, acc, want = [], 0.0, total / k
        for r, h in enumerate(heights[:-1]):
            acc += h
            if len(cuts) < k - 1 and r in cuttable and acc >= want * (len(cuts) + 1) - heights[r + 1] / 2.0:
                cuts.append(r)
        if len(cuts) != k - 1:
            continue
        bounds = [-1] + cuts + [len(heights) - 1]
        hs = [sum(heights[bounds[i] + 1:bounds[i + 1] + 1]) for i in range(len(bounds) - 1)]
        ws = [width_of(bounds[i] + 1, bounds[i + 1]) for i in range(len(bounds) - 1)]
        aspect = sum(ws) / max(hs)
        score = abs(math.log(aspect / target))
        if best is None or score < best[0] - 1e-9:
            best = (score, cuts, aspect)
    return (best[1], best[2]) if best else ([], 0.0)


def wrap(pos, rank, info, frames, span, routes, band_top, band_h, pads_below, heads_above, o, target, min_width=0.0,
         cuts=None):
    """Wraps in place: pos {node: (x, y)}, frames {group: box}, routes (Route, points changed). Returns
    the layers it cut after ([] when it did not wrap). band_top/band_h: per layer; pads_below[r] and
    heads_above[r]: the frame bands just below layer r and just above it. cuts: the cuts to make, from
    an earlier layout of the same figure ([] for none); one a frame now spans moves to the nearest
    layer it can fall after."""
    nl = len(band_top)
    track, stub, side = o["track"], o["stub"], o["side_gap"]
    cuttable = {r for r in range(nl - 1) if not any(lo <= r < hi for lo, hi in span.values())}
    if cuts:
        cuts = sorted({min(cuttable, key=lambda r: (abs(r - c), r)) for c in cuts}) if cuttable else None
    given = cuts is not None
    if given and not cuts:
        return []
    if not given and (nl < o.get("wrap_layers", 12) or target is None):
        return []
    gap_top = [band_top[r] + band_h[r] + pads_below.get(r, 0.0) for r in range(nl)]  # where a chunk ends

    def start(r):  # where the chunk beginning at layer r begins: the gap above it, tracks and all
        return gap_top[r - 1] if r > 0 else min(0.0, min((b[1] for b in frames.values()), default=0.0))
    ends = [gap_top[r] for r in range(nl)]
    heights = [ends[r] - start(r) for r in range(nl)]

    def x_extent(lo, hi):
        xs = []
        for nid, (x, y) in pos.items():
            if lo <= rank[nid] <= hi:
                w = info[nid]["w"] / 2.0
                xs += [x - w, x + w]
        for g, (a, b) in span.items():
            if lo <= a and b <= hi:
                xs += [frames[g][0], frames[g][2]]
        for r in routes.values():
            ra, rb = rank[r.nodes[0]], rank[r.nodes[1]]
            if lo <= ra <= hi and lo <= rb <= hi:
                xs += [p[0] for p in r.points]
        return (min(xs), max(xs)) if xs else (0.0, 0.0)

    def width_of(lo, hi):
        a, b = x_extent(lo, hi)
        return b - a + 2 * side
    if not given:
        natural = max(width_of(0, nl - 1), min_width) / (ends[-1] - start(0))
        if natural >= target * 0.4:  # not much taller than wanted: one column reads better
            return []
        cuts, _ = _choose(heights, cuttable, width_of, target)
        if not cuts:
            return []
    bounds = [-1] + cuts + [nl - 1]
    chunks = [(bounds[i] + 1, bounds[i + 1]) for i in range(len(bounds) - 1)]

    def chunk_of_rank(r):
        return next(i for i, (lo, hi) in enumerate(chunks) if lo <= r <= hi)

    # which arrows cross each cut, and where they leave and enter
    crossing = {c: [] for c in range(len(cuts))}
    split = {}
    for eid, r in routes.items():
        ca, cb = chunk_of_rank(rank[r.nodes[0]]), chunk_of_rank(rank[r.nodes[1]])
        if ca == cb:
            continue
        pieces = _split(r.points, cuts, chunks, gap_top, band_top, heads_above)
        if pieces is None:
            return []
        split[eid] = pieces
        for c, x_in, x_out, up in pieces["cuts"]:
            crossing[c].append((eid, x_in, x_out, up))

    def content_top(i, lo, hi):
        """The top of what chunk i shows: its boxes and frames, the routes inside it, and where the
        arrows crossing into it arrive."""
        ys = [pos[n][1] - info[n]["h"] / 2.0 - heads_above.get(rank[n], 0.0) for n in pos if lo <= rank[n] <= hi]
        ys += [frames[g][1] for g, (a, b) in span.items() if lo <= a and b <= hi]
        for eid, r in routes.items():
            if eid in split:
                ys += [y for part in split[eid]["parts"] if part["chunk"] == i for _, y in part["points"]]
            elif lo <= rank[r.nodes[0]] <= hi:
                ys += [y for _, y in r.points]
        return min(ys) if ys else start(lo)

    # chunk offsets: side by side, tops aligned below the highest top corridor
    lanes = {c: len(v) for c, v in crossing.items()}
    top_band = max((n * track + stub for n in lanes.values() if n), default=0.0)
    dx, dy, right = [], [], None
    extents = []
    for i, (lo, hi) in enumerate(chunks):  # what a chunk spans: its own content and the arrows passing it
        a, b = x_extent(lo, hi)
        xs = [x for pieces in split.values() for part in pieces["parts"] if part["chunk"] == i for x, _ in part["points"]]
        extents.append((min([a] + xs), max([b] + xs)))
    for i, (lo, hi) in enumerate(chunks):
        a, b = extents[i]
        if right is None:
            dx.append(-a)
        else:
            corridor = lanes.get(i - 1, 0) * track + 2 * side
            dx.append(right + corridor - a)
        right = b + dx[-1]
        dy.append(top_band - content_top(i, lo, hi))
    for nid, (x, y) in list(pos.items()):
        i = chunk_of_rank(rank[nid])
        pos[nid] = (x + dx[i], y + dy[i])
    for g, (a, b) in span.items():
        i = chunk_of_rank(a)
        x0, y0, x1, y1 = frames[g]
        frames[g] = (x0 + dx[i], y0 + dy[i], x1 + dx[i], y1 + dy[i])
    bottoms = []
    for i, (lo, hi) in enumerate(chunks):
        bottoms.append(ends[hi] + dy[i])
    for eid, r in routes.items():
        if eid in split:
            continue
        i = chunk_of_rank(rank[r.nodes[0]])
        r.points = [(x + dx[i], y + dy[i]) for x, y in r.points]
        bottoms[i] = max([bottoms[i]] + [y for _, y in r.points])

    # corridors: below chunk c, up between c and c+1, over the top of c+1
    lane_of = {}
    for c, items in crossing.items():
        for k, (eid, x_in, x_out, up) in enumerate(sorted(items, key=lambda t: -t[1])):
            lane_of[(eid, c)] = k
    for eid, pieces in split.items():
        pts = []
        for n, part in enumerate(pieces["parts"]):
            i = part["chunk"]
            seg = [(x + dx[i], y + dy[i]) for x, y in part["points"]]
            if n:
                c, x_in, x_out, up = pieces["cuts"][n - 1]
                k, n_c = lane_of[(eid, c)], lanes[c]
                yb = max(bottoms[c], ends[chunks[c][1]] + dy[c]) + stub + k * track
                xc = extents[c][1] + dx[c] + side + k * track
                yt = top_band - stub - (n_c - 1 - k) * track
                xi, xo = x_in + dx[c], x_out + dx[c + 1]
                way = [(xi, yb), (xc, yb), (xc, yt), (xo, yt)]
                pts += way[::-1] if up else way
            pts += seg
        routes[eid].points = _clean(pts)
    return list(cuts)


def _split(points, cuts, chunks, gap_top, band_top, heads_above):
    """Cuts a route at each cut it crosses: {"parts": [{"chunk", "points"}], "cuts": [(cut, x_in,
    x_out, up)], "up"}. x_in is where it leaves (or enters) the earlier chunk, x_out the later one."""
    exit_y = {c: gap_top[cuts[c]] for c in range(len(cuts))}
    entry_y = {c: band_top[cuts[c] + 1] - heads_above.get(cuts[c] + 1, 0.0) for c in range(len(cuts))}

    def region(y):
        for c in range(len(cuts)):
            if y <= exit_y[c] + 0.01:
                return ("chunk", c)
            if y < entry_y[c] - 0.01:
                return ("cut", c)
        return ("chunk", len(cuts))
    up = points[0][1] > points[-1][1]
    pts = points if not up else points[::-1]  # walk top to bottom
    parts, crosses = [{"chunk": region(pts[0][1])[1], "points": [pts[0]]}], []
    for p, q in zip(pts, pts[1:]):
        rp, rq = region(p[1]), region(q[1])
        if rp == rq:
            if rp[0] == "chunk":
                parts[-1]["points"].append(q)
            continue
        # leaving a chunk downward: the crossing of its exit line
        if rp[0] == "chunk" and (rq[0] == "cut" or rq[1] > rp[1]):
            if abs(p[0] - q[0]) > 0.5:
                return None  # sideways across a cut line: not a shape this router makes
            parts[-1]["points"].append((p[0], exit_y[rp[1]]))
            crosses.append([rp[1], p[0], None])
        if (rp[0] == "cut" or rp[1] < rq[1]) and rq[0] == "chunk":
            if abs(p[0] - q[0]) > 0.5:
                return None
            c = rq[1] - 1
            if not crosses or crosses[-1][2] is not None:
                return None
            crosses[-1][2] = q[0]
            parts.append({"chunk": rq[1], "points": [(q[0], entry_y[c]), q]})
    if any(c[2] is None for c in crosses):
        return None
    if up:
        parts = [{"chunk": pt["chunk"], "points": pt["points"][::-1]} for pt in parts[::-1]]
        crosses = crosses[::-1]
    return {"parts": parts, "cuts": [(c, x_in, x_out, up) for c, x_in, x_out in crosses], "up": up}


def _clean(pts):
    out = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 0.01 and abs(p[1] - out[-1][1]) < 0.01:
            continue
        out.append(p)
    k = 1
    while k < len(out) - 1:
        (x0, y0), (x1, y1), (x2, y2) = out[k - 1], out[k], out[k + 1]
        if (abs(x0 - x1) < 0.01 and abs(x1 - x2) < 0.01) or (abs(y0 - y1) < 0.01 and abs(y1 - y2) < 0.01):
            del out[k]
        else:
            k += 1
    return out

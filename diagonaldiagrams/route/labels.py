"""Edge label placement (DESIGN 8, PLAN P4.4).

Finds the first clear spot along an edge's route where the paper-colored label pill clears
boxes, group frames, canvas borders and already-placed labels (hard obstacles), while minimizing
crossings with other arrow segments (soft obstacles).
"""


def pill_width(text):
    return max(40, int(len(text) * 6.4 + 12))


GAP = 4  # between an arrow and its label's pill, where the label hugs its arrow (flow, arch, schema, seq)


def label_box(mx, ay, text, vertical=False, flip=False, w=None, gap=8):
    """The label's pill as (x0, y0, x1, y1), gap away from the arrow; w, when given, is its width (the
    layout knows widths, not texts)."""
    w = pill_width(text) if w is None else w
    if vertical:
        x0 = mx - gap - w if flip else mx + gap
        return (x0, ay - 9, x0 + w, ay + 7)
    y0 = ay + gap if flip else ay - gap - 16
    return (mx - w / 2, y0, mx + w / 2, y0 + 16)


def longest_segment(pts, frames=()):
    """A label's first spot: the middle of the longest stretch of the route that no frame border
    crosses, and whether that stretch runs up and down."""
    if not pts:
        return 0.0, 0.0, False
    best, mx, my, vert = -1.0, pts[0][0], pts[0][1], False
    for (px, py), (qx, qy) in zip(pts, pts[1:]):
        v = abs(qy - py) > abs(qx - px)
        a, b = (py, qy) if v else (px, qx)
        lo, hi = min(a, b), max(a, b)
        cuts = [lo, hi]
        for x0, y0, x1, y1 in frames:  # where the segment crosses a frame's border
            if v and x0 < px < x1:
                cuts += [y for y in (y0, y1) if lo < y < hi]
            elif not v and y0 < py < y1:
                cuts += [x for x in (x0, x1) if lo < x < hi]
        cuts.sort()
        for c0, c1 in zip(cuts, cuts[1:]):
            if c1 - c0 > best:
                best = c1 - c0
                m = (c0 + c1) / 2.0
                mx, my, vert = (px, m, True) if v else (m, py, False)
    return mx, my, vert


def place_label(mx, my, vertical, text, pts, avoid, soft=(), w=None, gap=8):
    """The first spot along the route where the label's pill clears everything. Tries the
    default, then each segment's middle, on both sides and both orientations. If none is
    clear: never on a hard obstacle (a box or a label), then the fewest soft ones (other arrows).
    w: the pill's width, in place of measuring text; gap: between the arrow and the pill."""
    cands = [(mx, my, vertical, False), (mx, my, vertical, True)]
    for at in (0.5, 0.3, 0.7):  # each segment's middle first, then either side of it
        for (px, py), (qx, qy) in zip(pts or [], (pts or [])[1:]):
            seg_v = abs(qy - py) > abs(qx - px)
            for v in (seg_v, not seg_v):
                for flip in (False, True):
                    cands.append((px + (qx - px) * at, py + (qy - py) * at, v, flip))

    def hits(b, boxes):
        return sum(1 for a in boxes if b[0] < a[2] + 2 and a[0] - 2 < b[2] and b[1] < a[3] + 2 and a[1] - 2 < b[3])

    scored = []
    for k, c in enumerate(cands):
        b = label_box(c[0], c[1], text, c[2], c[3], w, gap)
        cost = (hits(b, avoid), hits(b, soft), k)
        if cost[:2] == (0, 0):
            return c
        scored.append((cost, c))
    return min(scored)[1]


class LabelPlacer:
    """Manages placement of labels across a diagram, tracking obstacles."""

    def __init__(self, hard_obstacles=(), soft_obstacles=(), frames=()):
        self.hard = list(hard_obstacles)
        self.soft = list(soft_obstacles)
        self.frames = list(frames)
        self.placed = []

    def place(self, text, pts, default_pos=None):
        """Places a label for an edge and records its pill box as a hard obstacle."""
        if default_pos is None:
            mx, my, vert = longest_segment(pts, self.frames)
        else:
            mx, my, vert = default_pos
        lx, ly, vert, flip = place_label(mx, my, vert, text, pts, self.hard + self.placed, self.soft)
        box = label_box(lx, ly, text, vert, flip)
        self.placed.append(box)
        return lx, ly, vert, flip

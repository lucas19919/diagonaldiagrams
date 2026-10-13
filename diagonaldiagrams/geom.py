"""Plane geometry shared by layout and audit: transforms, boxes, segment clipping, nearby pairs.

A box is (x0, y0, x1, y1) with x0 <= x1 and y0 <= y1. A transform is the SVG matrix
(a, b, c, d, e, f), mapping (x, y) to (a*x + c*y + e, b*x + d*y + f).
"""
import math
import re

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def compose(m, n):
    """The transform that applies n, then m."""
    a1, b1, c1, d1, e1, f1 = m
    a2, b2, c2, d2, e2, f2 = n
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def affine(tf):
    """An SVG transform list (matrix, translate, scale, rotate; skew is ignored) as one matrix."""
    m = IDENTITY
    for name, raw in re.findall(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)", tf or ""):
        v = [float(x) for x in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", raw)]
        if not v:
            continue
        if name == "matrix" and len(v) == 6:
            n = tuple(v)
        elif name == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            n = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                n = compose(compose((1, 0, 0, 1, v[1], v[2]), n), (1, 0, 0, 1, -v[1], -v[2]))
        else:
            continue
        m = compose(m, n)
    return m


def apply(m, p):
    """A point through a transform."""
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def xbox(m, x0, y0, x1, y1):
    """The axis-aligned box around a transformed box."""
    pts = [apply(m, q) for q in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def overlap(a, b):
    """Width and height of the intersection of two boxes (0 when they do not meet)."""
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])), max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def inside(a, b, tol=1.0):
    """Box b lies inside box a, within tol."""
    return a[0] - tol <= b[0] and a[1] - tol <= b[1] and a[2] + tol >= b[2] and a[3] + tol >= b[3]


def center(b):
    """A box's center, rounded to whole pixels (where an issue is reported)."""
    return [round((b[0] + b[2]) / 2), round((b[1] + b[3]) / 2)]


def crosses(p, q, b):
    """Does segment p-q run more than 2 px inside box b? (Liang-Barsky clipping.)"""
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, p[0] - b[0]), (dx, b[2] - p[0]), (-dy, p[1] - b[1]), (dy, b[3] - p[1])):
        if pk == 0:
            if qk < 0:
                return False
            continue
        r = qk / pk
        if pk < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return False
    return (t1 - t0) * math.hypot(dx, dy) > 2


def near_pairs(xs, ys=None, width=0.0, height=0.0, cell=64.0):
    """Index pairs of boxes that may touch, from a grid, so thousands of boxes stay fast.
    With one list, each pair comes once (i < j); with two, every (i, j) that may touch."""
    lim = max(width, height, 1000.0) + 1000.0

    def cells(b):
        x0, y0 = max(-lim, b[0]), max(-lim, b[1])
        x1, y1 = min(lim, b[2]), min(lim, b[3])
        return [(gx, gy) for gx in range(int(x0 // cell), int(x1 // cell) + 1)
                for gy in range(int(y0 // cell), int(y1 // cell) + 1)]
    grid = {}
    for j, b in enumerate(xs if ys is None else ys):
        for c in cells(b):
            grid.setdefault(c, []).append(j)
    done = set()
    for i, a in enumerate(xs):
        for c in cells(a):
            for j in grid.get(c, ()):
                if (ys is None and j <= i) or (i, j) in done:
                    continue
                done.add((i, j))
                yield i, j

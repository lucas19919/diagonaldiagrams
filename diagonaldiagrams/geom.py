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
    """An SVG transform list (matrix, translate, scale, rotate, skewX, skewY) as one matrix."""
    m = IDENTITY
    for name, raw in re.findall(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)", tf or ""):
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
        elif name == "skewX":
            n = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            n = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
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


def arc_points(p0, rx, ry, phi, large, sweep, p1, steps=8):
    """Points along an SVG elliptical arc from p0 to p1 (endpoint parameters), p1 included."""
    if rx == 0 or ry == 0 or p0 == p1:
        return [p1]
    rx, ry = abs(rx), abs(ry)
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = c * dx + s * dy, -s * dx + c * dy
    lam = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    k = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        k = -k
    cx1, cy1 = k * rx * y1 / ry, -k * ry * x1 / rx
    cx, cy = c * cx1 - s * cy1 + (p0[0] + p1[0]) / 2, s * cx1 + c * cy1 + (p0[1] + p1[1]) / 2
    t0 = math.atan2((y1 - cy1) / ry, (x1 - cx1) / rx)
    t1 = math.atan2((-y1 - cy1) / ry, (-x1 - cx1) / rx)
    dt = t1 - t0
    if sweep and dt < 0:
        dt += 2 * math.pi
    elif not sweep and dt > 0:
        dt -= 2 * math.pi
    out = []
    for i in range(1, steps + 1):
        t = t0 + dt * i / steps
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        out.append((c * ex - s * ey + cx, s * ex + c * ey + cy))
    out[-1] = p1
    return out


def bezier_points(p0, controls, p1, steps=8):
    """Points along a quadratic (one control) or cubic (two controls) Bezier, p1 included."""
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        if len(controls) == 1:
            (qx, qy), = controls
            out.append((u * u * p0[0] + 2 * u * t * qx + t * t * p1[0], u * u * p0[1] + 2 * u * t * qy + t * t * p1[1]))
        else:
            (ax, ay), (bx, by) = controls
            out.append((u ** 3 * p0[0] + 3 * u * u * t * ax + 3 * u * t * t * bx + t ** 3 * p1[0],
                        u ** 3 * p0[1] + 3 * u * u * t * ay + 3 * u * t * t * by + t ** 3 * p1[1]))
    out[-1] = p1
    return out


def overlap(a, b):
    """Width and height of the intersection of two boxes (0 when they do not meet)."""
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])), max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def inside(a, b, tol=1.0):
    """Box b lies inside box a, within tol."""
    return a[0] - tol <= b[0] and a[1] - tol <= b[1] and a[2] + tol >= b[2] and a[3] + tol >= b[3]


def center(b):
    """A box's center, rounded to whole pixels (where an issue is reported)."""
    return [round((b[0] + b[2]) / 2), round((b[1] + b[3]) / 2)]


def length_inside(p, q, b):
    """How much of segment p-q lies inside box b (Liang-Barsky clipping)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, p[0] - b[0]), (dx, b[2] - p[0]), (-dy, p[1] - b[1]), (dy, b[3] - p[1])):
        if pk == 0:
            if qk < 0:
                return 0.0
            continue
        r = qk / pk
        if pk < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return 0.0
    return (t1 - t0) * math.hypot(dx, dy)


def clip_convex(p, q, poly):
    """The part of segment p-q inside a convex polygon, as (t0, t1) along it, or None."""
    t0, t1 = 0.0, 1.0
    cx = sum(v[0] for v in poly) / len(poly)
    cy = sum(v[1] for v in poly) / len(poly)
    for a, b in zip(poly, poly[1:] + poly[:1]):
        def side(x, y):
            return (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
        s = 1 if side(cx, cy) >= 0 else -1
        f0, f1 = s * side(*p), s * side(*q)
        if f0 < 0 and f1 < 0:
            return None
        if f0 < 0 or f1 < 0:
            t = f0 / (f0 - f1)
            if f0 < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
    return (t0, t1) if t0 < t1 else None


def length_in_convex(p, q, poly):
    """How much of segment p-q lies inside a convex polygon."""
    cut = clip_convex(p, q, poly)
    return (cut[1] - cut[0]) * math.hypot(q[0] - p[0], q[1] - p[1]) if cut else 0.0


def in_convex(pt, poly, tol=0.0):
    """Is the point inside a convex polygon, or within tol of it?"""
    cx = sum(v[0] for v in poly) / len(poly)
    cy = sum(v[1] for v in poly) / len(poly)
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        n = math.hypot(ex, ey)
        if n == 0:
            continue
        side = (ex * (pt[1] - a[1]) - ey * (pt[0] - a[0])) / n  # signed distance from the edge's line
        inner = ex * (cy - a[1]) - ey * (cx - a[0])
        if (side if inner >= 0 else -side) < -tol:
            return False
    return True


def crosses(p, q, b):
    """Does segment p-q run more than 2 px inside box b?"""
    return length_inside(p, q, b) > 2


def path_crosses(segs, b):
    """Does a path (its segments) run more than 2 px inside box b in all? A curve is many short
    segments, so the length inside is summed rather than asked of each one."""
    total = 0.0
    for p, q in segs:
        total += length_inside(p, q, b)
        if total > 2:
            return True
    return False


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

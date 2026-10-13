"""The `chart <kind>` renderers."""
from ..errors import SpecError
from .._draw import arrow_label, axis_ticks, fmt_tick, markers, nice_ticks
from .._text import esc
from .._theme import FONT, _hit, series_palette
from ..charts._base import (
    _annulus, _axes, _begin, _cap, _cat_labels, _col, _domain, _done, _dot, _draw_links, _f, _fig_open,
    _floats, _focals, _foot, _groups, _heat_color, _hh, _layers_of, _leaf_pos, _legend, _linked, _need,
    _ninv, _open_budget, _ordered, _paint_boxes, _parse_date, _partition, _quartiles, _ramp, _short,
    _tree_from, _tree_index, _when, _with_ids,
)
from ..geo import _clip_poly, _map_finish, _map_stage


def _c_bubble(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("y", opt["y"]), ("size", opt["size"])])
    gc = _col(rows, opt["group"], "group")
    pts = []
    for r in rows:
        try:
            pts.append((r, _f(r, c["x"]), _f(r, c["y"]), _f(r, c["size"])))
        except (TypeError, ValueError):
            continue
    if not pts:
        raise SpecError("bubble needs numeric x, y, and size")
    _cap(None, len(pts), 400, "points", opt["unbounded"])
    names = _ordered(str(r.get(gc) or "") for r, *_ in pts) if gc else [""]
    _cap(None, len(names), 8, "groups", opt["unbounded"])
    pal = series_palette(opt["t"])
    color = {name: (opt["t"]["link"] if len(names) == 1 else pal[i % len(pal)]) for i, name in enumerate(names)}
    xs = [p[1] for p in pts]
    ys = [p[2] for p in pts]
    ss = [max(0.0, p[3]) for p in pts]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 320, bottom=78 if gc else 56)
    xt, yt = nice_ticks(*_domain(xs, floor0=min(xs) >= 0)), nice_ticks(*_domain(ys, floor0=min(ys) >= 0))
    X, Y = _axes(parts, t, ox, oy, pw, ph, xt, yt, opt["grid"])
    smax = max(ss) or 1
    for r, x, y, s in pts:
        name = str(r.get(gc) or "") if gc else ""
        hit = _hit(opt["highlights"], name, r.get(c["x"]))
        rad = 5 + 16 * (max(s, 0) / smax) ** 0.5
        _dot(parts, t, X(x), Y(y), rad, color[name], opt["markers"], hit)
    if gc and len(names) > 1:
        _legend(parts, t, [(color[n], n or "series") for n in names], ox, H - 36)
    return _done(parts, opt, W, H, len(pts))


def _c_beeswarm(spec, rows, opt):
    import math
    c = _need(rows, [("cat", opt["x"] or opt["label"]), ("val", opt["val"] or opt["y"])])
    packed = []
    for r, v in _floats(rows, c["val"]):
        packed.append((str(r.get(c["cat"]) or ""), v))
    _cap(None, len(packed), 300, "dots", opt["unbounded"])
    cats = _ordered(p[0] for p in packed)
    vals = [p[1] for p in packed]
    rotate = len(cats) > 6
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 320, bottom=78 if rotate else 56)
    yt = nice_ticks(*_domain(vals))
    span = (yt[-1] - yt[0]) or 1
    slot = pw / max(len(cats), 1)

    def Y(v):
        return oy + ph - (v - yt[0]) / span * ph

    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    centers = []
    for i, cat in enumerate(cats):
        cx = ox + (i + 0.5) * slot
        centers.append(cx)
        here = [(v, Y(v)) for name, v in packed if name == cat]
        placed = []
        for v, y in here:
            x, sign, step = cx, 1, 0
            for _try in range(30):
                if not any(math.hypot(x - px, y - py) < 11 for px, py in placed):
                    break
                step += 1
                x = cx + (step // 2 + 1) * 6 * (1 if step % 2 else -1)
            x = min(ox + pw - 8, max(ox + 8, x))
            placed.append((x, y))
            _dot(parts, t, x, y, 4.5, t["link"], opt["markers"], _hit(opt["highlights"], cat))
    _cat_labels(parts, t, cats, centers, oy + ph + 16, rotate)
    return _done(parts, opt, W, H, len(packed))


def _c_step(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("y", opt["y"])])
    gc = _col(rows, opt["group"], "group")
    series = {}
    for r in rows:
        try:
            series.setdefault(str(r.get(gc) or "") if gc else "", []).append((_f(r, c["x"]), _f(r, c["y"])))
        except (TypeError, ValueError):
            continue
    if not series:
        raise SpecError("step needs numeric x and y")
    names = _ordered(series)
    _cap(None, len(names), 6, "series", opt["unbounded"])
    pal = series_palette(opt["t"])
    xs = [p[0] for pts in series.values() for p in pts]
    ys = [p[1] for pts in series.values() for p in pts]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=72 if len(names) > 1 else 52)
    X, Y = _axes(parts, t, ox, oy, pw, ph, nice_ticks(*_domain(xs)), nice_ticks(*_domain(ys)), opt["grid"])
    for i, name in enumerate(names):
        pts = sorted(series[name])
        col = t["link"] if len(names) == 1 else pal[i % len(pal)]
        d = [f"M {X(pts[0][0]):.1f} {Y(pts[0][1]):.1f}"]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            d.append(f"H {X(x1):.1f} V {Y(y1):.1f}")
        parts.append(f'<path d="{" ".join(d)}" fill="none" stroke="{col}" stroke-width="1.8"/>')
        if opt["markers"] or _hit(opt["highlights"], name):
            for x, y in pts:
                _dot(parts, t, X(x), Y(y), 3.2, col, opt["markers"], _hit(opt["highlights"], name, x))
    if len(names) > 1:
        _legend(parts, t, [(pal[i % len(pal)], n or "series") for i, n in enumerate(names)], ox, H - 34)
    return _done(parts, opt, W, H, sum(len(v) for v in series.values()))


def _c_slope(spec, rows, opt):
    c = _need(rows, [("cat", opt["label"] or opt["x"]), ("a", opt["a"]), ("b", opt["b"])])
    items = []
    for r in rows:
        try:
            items.append((str(r.get(c["cat"]) or ""), _f(r, c["a"]), _f(r, c["b"])))
        except (TypeError, ValueError):
            continue
    if not items:
        raise SpecError("slope needs cat, a, and b")
    _cap(None, len(items), 16, "lines", opt["unbounded"])
    vals = [v for _, a, b in items for v in (a, b)]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(280, 36 + len(items) * 8), ox=120, right=130)
    lo, hi = _domain(vals, floor0=min(vals) >= 0)
    yt = nice_ticks(lo, hi)
    span = (yt[-1] - yt[0]) or 1

    def Y(v):
        return oy + ph - (v - yt[0]) / span * ph

    x1, x2 = ox + 10, ox + pw - 10
    for lab, anchor, x in (("A", "end", x1 - 8), ("B", "start", x2 + 8)):
        parts.append(
            f'<text x="{x}" y="{oy - 6}" font-size="11" font-family="{FONT}" fill="{t["muted"]}" text-anchor="{anchor}">{lab}</text>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{x1}" y1="{y:.1f}" x2="{x2}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
    pal = series_palette(t)
    for i, (name, a, b) in enumerate(items):
        col = t["accent"] if _hit(opt["highlights"], name) else (t["link"] if len(items) == 1 else pal[i % len(pal)])
        parts.append(
            f'<line x1="{x1}" y1="{Y(a):.1f}" x2="{x2}" y2="{Y(b):.1f}" stroke="{col}" stroke-width="1.6"/>')
        if opt["markers"] or _hit(opt["highlights"], name):
            _dot(parts, t, x1, Y(a), 3.4, col, True, False)
            _dot(parts, t, x2, Y(b), 3.4, col, True, False)
        parts.append(
            f'<text x="{x1 - 10}" y="{Y(a) + 3:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(_short(name, 16))}</text>')
        if opt["markers"]:
            parts.append(
                f'<text x="{x2 + 10}" y="{Y(b) + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}">{fmt_tick(b)}</text>')
    return _done(parts, opt, W, H, len(items))


def _c_bump(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("name", opt["label"]), ("rank", opt["y"] or opt["val"])])
    series = {}
    order = []
    for r in rows:
        try:
            name = str(r.get(c["name"]) or "")
            series.setdefault(name, []).append((str(r.get(c["x"]) or ""), _f(r, c["rank"])))
            if str(r.get(c["x"]) or "") not in order:
                order.append(str(r.get(c["x"]) or ""))
        except (TypeError, ValueError):
            continue
    if not series:
        raise SpecError("bump needs x, name, and rank")
    _cap(None, len(series), 8, "names", opt["unbounded"])
    ranks = [p[1] for pts in series.values() for p in pts]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=72)
    top, bot = min(ranks), max(ranks)
    span = (bot - top) or 1

    def Y(v):
        return oy + (v - top) / span * ph

    xs = [ox + (i + 0.5) * pw / max(len(order), 1) for i in range(len(order))]
    pal = series_palette(t)
    names = list(series)
    for i, name in enumerate(names):
        col = t["accent"] if _hit(opt["highlights"], name) else pal[i % len(pal)]
        pts = sorted(series[name], key=lambda p: order.index(p[0]) if p[0] in order else 0)
        d = " ".join(f'{"M" if j == 0 else "L"} {xs[order.index(x)]:.1f} {Y(rk):.1f}' for j, (x, rk) in enumerate(pts) if x in order)
        if d:
            parts.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.7"/>')
        if opt["markers"] or _hit(opt["highlights"], name):
            for x, rk in pts:
                if x in order:
                    _dot(parts, t, xs[order.index(x)], Y(rk), 3.5, col, True, _hit(opt["highlights"], name))
    _cat_labels(parts, t, order, xs, oy + ph + 18, len(order) > 6)
    _legend(parts, t, [(pal[i % len(pal)], n) for i, n in enumerate(names)], ox, H - 34)
    return _done(parts, opt, W, H, len(series))


def _c_ridgeline(spec, rows, opt):
    import math
    c = _need(rows, [("group", opt["group"]), ("val", opt["val"] or opt["y"])])
    groups = _groups(rows, c["group"])
    names = _ordered(groups)
    _cap(None, len(names), 8, "groups", opt["unbounded"])
    vals = []
    for name in names:
        vals.extend(v for _, v in _floats(groups[name], c["val"]))
    lo, hi = min(vals), max(vals)
    if lo == hi:
        hi = lo + 1
    k = max(5, min(16, int(math.ceil(math.log2(max(len(vals), 2)) + 1))))
    edges = [lo + (hi - lo) * i / k for i in range(k + 1)]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(280, 36 * len(names) + 40))
    band = ph / max(len(names), 1)
    pal = series_palette(t)
    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for i, name in enumerate(names):
        counts = [0] * k
        for _, v in _floats(groups[name], c["val"]):
            idx = min(k - 1, int((v - lo) / (hi - lo) * k))
            counts[idx] += 1
        peak = max(counts) or 1
        base = oy + (i + 1) * band - 8
        col = t["accent"] if _hit(opt["highlights"], name) else pal[i % len(pal)]
        d = [f"M {ox:.1f} {base:.1f}"]
        for j, count in enumerate(counts):
            x0 = ox + j * pw / k
            x1 = ox + (j + 1) * pw / k
            y = base - (count / peak) * (band - 16)
            d.append(f"L {x0:.1f} {y:.1f} L {x1:.1f} {y:.1f}")
        d.append(f"L {ox + pw:.1f} {base:.1f} Z")
        parts.append(f'<path d="{" ".join(d)}" fill="{col}" fill-opacity="0.35" stroke="{col}" stroke-width="1.2"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{base:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(_short(name, 14))}</text>')
    parts.append(
        f'<text x="{ox}" y="{oy + ph + 16}" font-size="10" font-family="{FONT}" fill="{t["muted"]}">{fmt_tick(lo)}</text>')
    parts.append(
        f'<text x="{ox + pw}" y="{oy + ph + 16}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(hi)}</text>')
    return _done(parts, opt, W, H, len(vals), "value along the ridge")


def _c_stack(spec, rows, opt):
    c = _need(rows, [("cat", opt["x"] or opt["label"]), ("group", opt["group"]), ("val", opt["val"] or opt["y"])])
    cats, groups = [], []
    cell = {}
    for r in rows:
        try:
            cat, grp, val = str(r.get(c["cat"]) or ""), str(r.get(c["group"]) or ""), _f(r, c["val"])
        except (TypeError, ValueError):
            continue
        if cat not in cats:
            cats.append(cat)
        if grp not in groups:
            groups.append(grp)
        cell[(cat, grp)] = cell.get((cat, grp), 0) + val
    if not cats:
        raise SpecError("stack needs cat, group, and val")
    _cap(None, len(cats), 12, "categories", opt["unbounded"])
    _cap(None, len(groups), 8, "groups", opt["unbounded"])
    totals = []
    for cat in cats:
        pos = sum(v for g in groups for v in [cell.get((cat, g), 0)] if v > 0)
        neg = sum(v for g in groups for v in [cell.get((cat, g), 0)] if v < 0)
        totals.extend((pos, neg))
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=78)
    yt = axis_ticks(*_domain(totals, floor0=min(totals) >= 0))
    span = (yt[-1] - yt[0]) or 1

    def Y(v):
        return oy + ph - (v - yt[0]) / span * ph

    slot = pw / len(cats)
    bw = min(46, slot * 0.62)
    pal = series_palette(t)
    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{Y(0):.1f}" x2="{ox + pw}" y2="{Y(0):.1f}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    centers = []
    for i, cat in enumerate(cats):
        cx = ox + (i + 0.5) * slot
        centers.append(cx)
        pos = neg = 0.0
        hit = _hit(opt["highlights"], cat)
        for j, grp in enumerate(groups):
            val = cell.get((cat, grp), 0)
            if val == 0:
                continue
            y0 = pos if val > 0 else neg
            y1 = y0 + val
            if val > 0:
                pos = y1
            else:
                neg = y1
            top, bot = Y(max(y0, y1)), Y(min(y0, y1))
            col = t["accent"] if hit else pal[j % len(pal)]
            parts.append(
                f'<rect x="{cx - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(1, bot - top):.1f}" fill="{col}"/>')
    _cat_labels(parts, t, cats, centers, oy + ph + 16, len(cats) > 6)
    _legend(parts, t, [(pal[i % len(pal)], g) for i, g in enumerate(groups)], ox, H - 34)
    return _done(parts, opt, W, H, len(cats))


def _c_dumbbell(spec, rows, opt):
    c = _need(rows, [("cat", opt["label"] or opt["x"]), ("a", opt["a"] or opt["lo"]), ("b", opt["b"] or opt["hi"])])
    items = []
    for r in rows:
        try:
            items.append((str(r.get(c["cat"]) or ""), _f(r, c["a"]), _f(r, c["b"])))
        except (TypeError, ValueError):
            continue
    if not items:
        raise SpecError("dumbbell needs cat, a, and b")
    _cap(None, len(items), 16, "rows", opt["unbounded"])
    vals = [v for _, a, b in items for v in (a, b)]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(240, len(items) * 32), ox=130, right=36)
    xt = nice_ticks(*_domain(vals))
    span = (xt[-1] - xt[0]) or 1

    def X(v):
        return ox + (v - xt[0]) / span * pw

    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in xt:
        x = X(v)
        if opt["grid"]:
            parts.append(f'<line x1="{x:.1f}" y1="{oy}" x2="{x:.1f}" y2="{oy + ph}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{oy + ph + 16}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{fmt_tick(v)}</text>')
    for i, (name, a, b) in enumerate(items):
        y = oy + (i + 0.5) * ph / len(items)
        hit = _hit(opt["highlights"], name)
        col = t["accent"] if hit else t["link"]
        parts.append(f'<line x1="{X(a):.1f}" y1="{y:.1f}" x2="{X(b):.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="1.6"/>')
        _dot(parts, t, X(a), y, 4.5, t["muted"], opt["markers"] or hit, False)
        _dot(parts, t, X(b), y, 4.5, col, opt["markers"] or hit, hit)
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(_short(name, 16))}</text>')
    return _done(parts, opt, W, H, len(items))


def _c_waterfall(spec, rows, opt):
    c = _need(rows, [("cat", opt["x"] or opt["label"]), ("val", opt["val"] or opt["y"])])
    items = []
    for r in rows:
        try:
            items.append((str(r.get(c["cat"]) or ""), _f(r, c["val"])))
        except (TypeError, ValueError):
            continue
    if not items:
        raise SpecError("waterfall needs cat and val")
    _cap(None, len(items), 16, "steps", opt["unbounded"])
    running = 0.0
    spans = []
    for name, val in items:
        if name.strip().lower() in ("total", "net", "end"):
            spans.append((name, 0.0, val, "total"))
            running = val
        else:
            spans.append((name, running, running + val, "up" if val >= 0 else "down"))
            running += val
    bounds = [v for _, a, b, _ in spans for v in (a, b)]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=78)
    yt = axis_ticks(*_domain(bounds))
    span = (yt[-1] - yt[0]) or 1

    def Y(v):
        return oy + ph - (v - yt[0]) / span * ph

    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    zero = Y(0)
    parts.append(f'<line x1="{ox}" y1="{zero:.1f}" x2="{ox + pw}" y2="{zero:.1f}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    slot = pw / len(spans)
    bw = min(42, slot * 0.62)
    prev = None
    centers = []
    for i, (name, a, b, kind) in enumerate(spans):
        cx = ox + (i + 0.5) * slot
        centers.append(cx)
        top, bot = Y(max(a, b)), Y(min(a, b))
        col = t["ink"] if kind == "total" else (t["link"] if kind == "up" else t["accent"])
        if _hit(opt["highlights"], name):
            col = t["accent"]
        parts.append(
            f'<rect x="{cx - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(1, bot - top):.1f}" fill="{col}"/>')
        if prev is not None and kind != "total":
            parts.append(
                f'<line x1="{prev:.1f}" y1="{Y(a):.1f}" x2="{cx - bw / 2:.1f}" y2="{Y(a):.1f}" stroke="{t["soft"]}" stroke-dasharray="3 3"/>')
        prev = cx + bw / 2
        if opt["markers"]:
            parts.append(
                f'<text x="{cx:.1f}" y="{top - 4:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{fmt_tick(b - a if kind != "total" else b)}</text>')
    _cat_labels(parts, t, [s[0] for s in spans], centers, oy + ph + 16, len(spans) > 6)
    return _done(parts, opt, W, H, len(spans))


def _hist_edges(vals):
    import math
    lo, hi = min(vals), max(vals)
    if lo == hi:
        hi = lo + 1
    k = int(math.ceil(math.log2(len(vals)) + 1))
    k = max(5, min(20, k))
    step = (hi - lo) / k
    return [lo + i * step for i in range(k + 1)], k


def _c_histogram(spec, rows, opt):
    c = _need(rows, [("val", opt["val"] or opt["y"] or opt["x"])])
    vals = [v for _, v in _floats(rows, c["val"])]
    _cap(None, len(vals), 400, "values", opt["unbounded"])
    edges, k = _hist_edges(vals)
    counts = [0] * k
    span = edges[-1] - edges[0]
    for v in vals:
        counts[min(k - 1, int((v - edges[0]) / span * k))] += 1
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300)
    yt = axis_ticks(0, max(counts))
    yspan = (yt[-1] - yt[0]) or 1

    def Y(v):
        return oy + ph - (v - yt[0]) / yspan * ph

    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    bw = pw / k
    for i, count in enumerate(counts):
        top = Y(count)
        parts.append(
            f'<rect x="{ox + i * bw + 1:.1f}" y="{top:.1f}" width="{bw - 2:.1f}" height="{max(0, oy + ph - top):.1f}" fill="{t["link"]}"/>')
    for i in (0, k // 2, k):
        x = ox + i * bw
        parts.append(
            f'<text x="{x:.1f}" y="{oy + ph + 16}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{fmt_tick(edges[i])}</text>')
    return _done(parts, opt, W, H, len(vals), f"{k} bins")


def _box_stats(vals):
    q1, med, q3 = _quartiles(vals)
    iqr = q3 - q1
    lo_f, hi_f = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = [v for v in vals if lo_f <= v <= hi_f]
    whisk_lo = min(inside) if inside else q1
    whisk_hi = max(inside) if inside else q3
    outliers = [v for v in vals if v < lo_f or v > hi_f]
    return q1, med, q3, whisk_lo, whisk_hi, outliers


def _c_box(spec, rows, opt):
    c = _need(rows, [("group", opt["group"] or opt["x"]), ("val", opt["val"] or opt["y"])])
    groups = _groups(rows, c["group"])
    names = _ordered(groups)
    _cap(None, len(names), 8, "groups", opt["unbounded"])
    stats = []
    allv = []
    for name in names:
        vals = [v for _, v in _floats(groups[name], c["val"])]
        allv.extend(vals)
        stats.append((name, vals, _box_stats(vals)))
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=70)
    yt = nice_ticks(*_domain(allv))
    span = (yt[-1] - yt[0]) or 1

    def Y(v):
        return oy + ph - (v - yt[0]) / span * ph

    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    slot = pw / len(names)
    centers = []
    for i, (name, vals, (q1, med, q3, wlo, whi, outs)) in enumerate(stats):
        cx = ox + (i + 0.5) * slot
        centers.append(cx)
        bw = min(36, slot * 0.45)
        hit = _hit(opt["highlights"], name)
        col = t["accent"] if hit else t["link"]
        parts.append(f'<line x1="{cx:.1f}" y1="{Y(wlo):.1f}" x2="{cx:.1f}" y2="{Y(whi):.1f}" stroke="{col}" stroke-width="1.2"/>')
        parts.append(f'<line x1="{cx - 8:.1f}" y1="{Y(wlo):.1f}" x2="{cx + 8:.1f}" y2="{Y(wlo):.1f}" stroke="{col}"/>')
        parts.append(f'<line x1="{cx - 8:.1f}" y1="{Y(whi):.1f}" x2="{cx + 8:.1f}" y2="{Y(whi):.1f}" stroke="{col}"/>')
        top, bot = Y(q3), Y(q1)
        parts.append(
            f'<rect x="{cx - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(1, bot - top):.1f}" fill="{t["card"]}" stroke="{col}" stroke-width="1.4"/>')
        parts.append(f'<line x1="{cx - bw / 2:.1f}" y1="{Y(med):.1f}" x2="{cx + bw / 2:.1f}" y2="{Y(med):.1f}" stroke="{col}" stroke-width="1.6"/>')
        if opt["markers"]:
            for v in outs:
                _dot(parts, t, cx, Y(v), 2.8, col, True, False)
    _cat_labels(parts, t, names, centers, oy + ph + 16, len(names) > 6)
    return _done(parts, opt, W, H, sum(len(s[1]) for s in stats))


def _c_violin(spec, rows, opt):
    import math
    c = _need(rows, [("group", opt["group"] or opt["x"]), ("val", opt["val"] or opt["y"])])
    groups = _groups(rows, c["group"])
    names = _ordered(groups)
    _cap(None, len(names), 8, "groups", opt["unbounded"])
    series = []
    allv = []
    for name in names:
        vals = [v for _, v in _floats(groups[name], c["val"])]
        _cap(None, len(vals), 400, "values", opt["unbounded"])
        allv.extend(vals)
        series.append((name, vals, _box_stats(vals)))
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=70)
    yt = nice_ticks(*_domain(allv))
    span = (yt[-1] - yt[0]) or 1

    def Y(v):
        return oy + ph - (v - yt[0]) / span * ph

    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    slot = pw / len(names)
    half = min(28, slot * 0.38)
    centers = []
    for i, (name, vals, (q1, med, q3, wlo, whi, _)) in enumerate(series):
        cx = ox + (i + 0.5) * slot
        centers.append(cx)
        n = len(vals)
        sd = (sum((v - (sum(vals) / n)) ** 2 for v in vals) / n) ** 0.5 or 1
        bw = 1.06 * sd * n ** (-0.2)
        grid = [min(vals) + (max(vals) - min(vals)) * j / 31 for j in range(32)]
        if grid[0] == grid[-1]:
            grid = [grid[0] - 1, grid[0] + 1]
        dens = []
        for x in grid:
            s = sum(math.exp(-0.5 * ((x - v) / bw) ** 2) for v in vals)
            dens.append(s)
        peak = max(dens) or 1
        col = t["accent"] if _hit(opt["highlights"], name) else t["link"]
        right = [f"{cx + half * d / peak:.1f},{Y(x):.1f}" for x, d in zip(grid, dens)]
        left = [f"{cx - half * d / peak:.1f},{Y(x):.1f}" for x, d in zip(reversed(grid), reversed(dens))]
        parts.append(f'<polygon points="{" ".join(right + left)}" fill="{col}" fill-opacity="0.22" stroke="{col}" stroke-width="1.2"/>')
        parts.append(f'<line x1="{cx:.1f}" y1="{Y(wlo):.1f}" x2="{cx:.1f}" y2="{Y(whi):.1f}" stroke="{t["ink"]}" stroke-width="1.2"/>')
        parts.append(
            f'<rect x="{cx - 5:.1f}" y="{Y(q3):.1f}" width="10" height="{max(1, Y(q1) - Y(q3)):.1f}" fill="{t["card"]}" stroke="{t["ink"]}"/>')
        parts.append(f'<line x1="{cx - 5:.1f}" y1="{Y(med):.1f}" x2="{cx + 5:.1f}" y2="{Y(med):.1f}" stroke="{t["ink"]}"/>')
    _cat_labels(parts, t, names, centers, oy + ph + 16, len(names) > 6)
    return _done(parts, opt, W, H, sum(len(s[1]) for s in series))


def _c_strip(spec, rows, opt):
    c = _need(rows, [("group", opt["group"] or opt["x"]), ("val", opt["val"] or opt["y"])])
    groups = _groups(rows, c["group"])
    names = _ordered(groups)
    _cap(None, len(names), 8, "groups", opt["unbounded"])
    allv = []
    series = []
    for name in names:
        vals = [v for _, v in _floats(groups[name], c["val"])]
        _cap(None, len(vals), 400, "dots", opt["unbounded"])
        allv.extend(vals)
        series.append((name, vals))
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=70)
    yt = nice_ticks(*_domain(allv))
    span = (yt[-1] - yt[0]) or 1

    def Y(v):
        return oy + ph - (v - yt[0]) / span * ph

    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    slot = pw / len(names)
    centers = []
    for i, (name, vals) in enumerate(series):
        cx = ox + (i + 0.5) * slot
        centers.append(cx)
        hit = _hit(opt["highlights"], name)
        for j, v in enumerate(vals):
            jitter = ((j * 17) % 11) - 5
            _dot(parts, t, cx + jitter, Y(v), 3.4, t["link"], opt["markers"], hit)
    _cat_labels(parts, t, names, centers, oy + ph + 16, len(names) > 6)
    return _done(parts, opt, W, H, sum(len(s[1]) for s in series))


def _shares(rows, cat, val):
    items = []
    for r in rows:
        try:
            items.append((str(r.get(cat) or ""), _f(r, val)))
        except (TypeError, ValueError):
            continue
    items = [(n, v) for n, v in items if v > 0]
    if not items:
        raise SpecError("need a positive value")
    return items


def _c_pie(spec, rows, opt, hole=0):
    import math
    c = _need(rows, [("cat", opt["label"] or opt["x"]), ("val", opt["val"] or opt["y"])])
    items = _shares(rows, c["cat"], c["val"])
    _cap(None, len(items), 8, "slices", opt["unbounded"])
    total = sum(v for _, v in items) or 1
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 340, ox=40, right=40, bottom=36)
    cx, cy, r = W / 2 - 70, oy + ph / 2, min(pw, ph) * 0.38
    pal = series_palette(t)
    ang = -math.pi / 2
    for i, (name, val) in enumerate(items):
        span = val / total * math.tau
        col = t["accent"] if _hit(opt["highlights"], name) else pal[i % len(pal)]
        a1 = ang + span
        if span >= math.tau - 1e-3:
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{col}"/>')
        else:
            large = 1 if span > math.pi else 0
            x0, y0 = cx + r * math.cos(ang), cy + r * math.sin(ang)
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            parts.append(
                f'<path d="M {cx:.1f} {cy:.1f} L {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {x1:.1f} {y1:.1f} Z" fill="{col}"/>')
        mid = ang + span / 2
        lx, ly = cx + (r + 18) * math.cos(mid), cy + (r + 18) * math.sin(mid)
        anchor = "start" if math.cos(mid) >= 0 else "end"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="{anchor}">{esc(_short(name, 14))} {val / total * 100:.0f}%</text>')
        ang = a1
    if hole:
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * 0.58:.1f}" fill="{t["paper"]}"/>')
    return _done(parts, opt, W, H, len(items))


def _c_donut(spec, rows, opt):
    return _c_pie(spec, rows, opt, hole=1)


def _c_waffle(spec, rows, opt):
    c = _need(rows, [("cat", opt["label"] or opt["x"]), ("val", opt["val"] or opt["y"])])
    items = _shares(rows, c["cat"], c["val"])
    _cap(None, len(items), 8, "shares", opt["unbounded"])
    total = sum(v for _, v in items) or 1
    cells = [max(0, int(round(v / total * 100))) for _, v in items]
    drift = 100 - sum(cells)
    cells[max(range(len(cells)), key=lambda i: items[i][1])] += drift
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 320, bottom=70)
    size, gap = 22, 4
    pal = series_palette(t)
    painted = []
    for i, ncell in enumerate(cells):
        painted.extend([i] * max(0, ncell))
    painted = painted[:100]
    x0 = ox + 20
    y0 = oy + 10
    for i, owner in enumerate(painted):
        col = pal[owner % len(pal)]
        if _hit(opt["highlights"], items[owner][0]):
            col = t["accent"]
        gx, gy = i % 10, i // 10
        parts.append(
            f'<rect x="{x0 + gx * (size + gap):.1f}" y="{y0 + gy * (size + gap):.1f}" width="{size}" height="{size}" rx="2" fill="{col}"/>')
    _legend(parts, t, [(pal[i % len(pal)], f"{name} {cells[i]}") for i, (name, _) in enumerate(items)], ox, H - 34)
    return _done(parts, opt, W, H, 100, "100 cells")


def _csv_tree(rows, opt):
    c = _need(rows, [("name", opt["label"]), ("val", opt["val"] or opt["y"])])
    parent = _col(rows, opt["parent"], "parent")
    nodes = []
    for r in rows:
        name = str(r.get(c["name"]) or "")
        if not name:
            continue
        try:
            val = float(r[c["val"]]) if r.get(c["val"]) not in ("", None) else 0
        except (TypeError, ValueError):
            val = 0
        nodes.append({"name": name, "parent": str(r.get(parent) or "") if parent else "", "val": val})
    roots = _tree_index(nodes)
    if not roots:
        raise SpecError("tree needs a name column")
    return roots


def _c_treemap(spec, rows, opt):
    roots = _csv_tree(rows, opt) if spec is None else _tree_from(spec.get("nodes") or [])
    if not roots:
        raise SpecError("treemap needs nodes")
    n = sum(1 for _ in _walk_tree(roots))
    _cap(spec, n, 40, "nodes", opt["unbounded"])
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 360, ox=36, right=36)
    pal = series_palette(t)
    rects = _partition([(node, node["val"]) for node in roots], ox, oy, pw, ph, True)
    for i, (node, x, y, w, h) in enumerate(rects):
        _paint_tree_rect(parts, t, node, x, y, w, h, pal[i % len(pal)], opt)
    return _done(parts, opt, W, H, n)


def _walk_tree(roots):
    stack = list(roots)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node["children"])


def _paint_tree_rect(parts, t, node, x, y, w, h, col, opt):
    kids = [(c, c["val"]) for c in node["children"]]
    hit = _hit(opt["highlights"], node["name"])
    fill = t["accent"] if hit else col
    if kids and w > 28 and h > 28:
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" fill="{t["paper"]}" stroke="{t["card"]}"/>')
        if h > 18:
            parts.append(
                f'<text x="{x + 6:.1f}" y="{y + 14:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(node["name"], 18))}</text>')
        inner = _partition(kids, x + 2, y + 18, max(0, w - 4), max(0, h - 20), False)
        for child, cx, cy, cw, ch in inner:
            _paint_tree_rect(parts, t, child, cx, cy, cw, ch, col, opt)
        return
    parts.append(
        f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" width="{max(w - 2, 0):.1f}" height="{max(h - 2, 0):.1f}" fill="{fill}" fill-opacity="0.82" stroke="{t["paper"]}"/>')
    if w > 46 and h > 22:
        parts.append(
            f'<text x="{x + 6:.1f}" y="{y + 16:.1f}" font-size="11" font-family="{FONT}" fill="{t["card"]}">{esc(_short(node["name"], int(w / 7)))}</text>')
        if opt["markers"] and h > 34:
            parts.append(
                f'<text x="{x + 6:.1f}" y="{y + 30:.1f}" font-size="10" font-family="{FONT}" fill="{t["card"]}">{fmt_tick(node["val"])}</text>')


def _c_icicle(spec, rows, opt):
    roots = _csv_tree(rows, opt) if spec is None else _tree_from(spec.get("nodes") or [])
    n = sum(1 for _ in _walk_tree(roots))
    _cap(spec, n, 40, "nodes", opt["unbounded"])
    depth = _depth(roots)
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(280, depth * 56), ox=28, right=28)
    band = ph / max(depth, 1)
    pal = series_palette(t)

    def walk(node, x, y, w, d, color):
        hit = _hit(opt["highlights"], node["name"])
        parts.append(
            f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" width="{max(w - 2, 0):.1f}" height="{max(band - 2, 0):.1f}" fill="{t["accent"] if hit else color}" fill-opacity="0.85" stroke="{t["paper"]}"/>')
        if w > 48:
            parts.append(
                f'<text x="{x + 6:.1f}" y="{y + band / 2 + 4:.1f}" font-size="11" font-family="{FONT}" fill="{t["card"]}">{esc(_short(node["name"], int(w / 7)))}</text>')
        kids = node["children"]
        if not kids:
            return
        total = sum(c["val"] for c in kids) or 1
        acc = x
        for i, child in enumerate(kids):
            cw = w * child["val"] / total
            walk(child, acc, y + band, cw, d + 1, pal[(d + 1 + i) % len(pal)])
            acc += cw

    total = sum(r["val"] for r in roots) or 1
    acc = ox
    for i, root in enumerate(roots):
        w = pw * root["val"] / total
        walk(root, acc, oy, w, 0, pal[i % len(pal)])
        acc += w
    return _done(parts, opt, W, H, n)


def _depth(roots):
    best = 1

    def walk(node, d):
        nonlocal best
        best = max(best, d)
        for child in node["children"]:
            walk(child, d + 1)
    for root in roots:
        walk(root, 1)
    return best


def _c_sunburst(spec, rows, opt):
    import math
    roots = _csv_tree(rows, opt) if spec is None else _tree_from(spec.get("nodes") or [])
    n = sum(1 for _ in _walk_tree(roots))
    _cap(spec, n, 40, "nodes", opt["unbounded"])
    depth = _depth(roots)
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 420, ox=30, right=30, bottom=30)
    cx, cy = W / 2, oy + ph / 2 + 8
    ring = min(pw, ph) * 0.42 / max(depth, 1)
    pal = series_palette(t)

    def walk(node, a0, a1, d, color):
        if d == 0 and len(roots) == 1:
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ring * 0.85:.1f}" fill="{color}"/>')
            parts.append(
                f'<text x="{cx:.1f}" y="{cy + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["card"]}" text-anchor="middle">{esc(_short(node["name"], 12))}</text>')
        else:
            r0 = ring * (d if len(roots) == 1 else d + 0.15)
            r1 = r0 + ring * 0.92
            if a1 - a0 >= math.tau - 1e-3:
                parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r1:.1f}" fill="{color}"/>')
                parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r0:.1f}" fill="{t["paper"]}"/>')
            else:
                parts.append(f'<path d="{_annulus(cx, cy, r0, r1, a0, a1)}" fill="{color}" stroke="{t["paper"]}" stroke-width="1"/>')
            if a1 - a0 > 0.35:
                mid = (a0 + a1) / 2
                rr = (r0 + r1) / 2 if d else ring * 0.4
                parts.append(
                    f'<text x="{cx + rr * math.cos(mid):.1f}" y="{cy + rr * math.sin(mid) + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["card"]}" text-anchor="middle">{esc(_short(node["name"], 10))}</text>')
        kids = node["children"]
        if not kids:
            return
        total = sum(c["val"] for c in kids) or 1
        ang = a0
        for i, child in enumerate(kids):
            span = (a1 - a0) * child["val"] / total
            walk(child, ang, ang + span, d + 1, pal[(d + i) % len(pal)])
            ang += span

    total = sum(r["val"] for r in roots) or 1
    ang = -math.pi / 2
    for i, root in enumerate(roots):
        span = math.tau * root["val"] / total
        walk(root, ang, ang + span, 0, pal[i % len(pal)])
        ang += span
    return _done(parts, opt, W, H, n)


def _c_heatmap(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("y", opt["y"]), ("val", opt["val"])])
    xs, ys = [], []
    cell = {}
    for r in rows:
        try:
            x, y, v = str(r.get(c["x"]) or ""), str(r.get(c["y"]) or ""), _f(r, c["val"])
        except (TypeError, ValueError):
            continue
        if x not in xs:
            xs.append(x)
        if y not in ys:
            ys.append(y)
        cell[(x, y)] = v
    if not xs or not ys:
        raise SpecError("heatmap needs x, y, and val")
    _cap(None, len(xs) * len(ys), 400, "cells", opt["unbounded"])
    vals = list(cell.values())
    lo, hi = min(vals), max(vals)
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(240, len(ys) * 36 + 20), ox=110, bottom=78)
    cw, ch = pw / len(xs), ph / len(ys)
    show = len(xs) * len(ys) <= 48 and opt["markers"]
    for iy, y in enumerate(ys):
        parts.append(
            f'<text x="{ox - 8}" y="{oy + (iy + 0.5) * ch + 3:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(_short(y, 14))}</text>')
        for ix, x in enumerate(xs):
            if (x, y) not in cell:
                continue
            v = cell[(x, y)]
            u = 0.5 if hi == lo else (v - lo) / (hi - lo)
            parts.append(
                f'<rect x="{ox + ix * cw + 1:.1f}" y="{oy + iy * ch + 1:.1f}" width="{cw - 2:.1f}" height="{ch - 2:.1f}" fill="{_heat_color(t, u)}"/>')
            if show and cw > 28 and ch > 16:
                ink = t["ink"] if u < 0.45 else t["card"]
                parts.append(
                    f'<text x="{ox + (ix + 0.5) * cw:.1f}" y="{oy + (iy + 0.5) * ch + 3:.1f}" font-size="10" font-family="{FONT}" fill="{ink}" text-anchor="middle">{fmt_tick(v)}</text>')
    _cat_labels(parts, t, xs, [ox + (i + 0.5) * cw for i in range(len(xs))], oy + ph + 16, len(xs) > 6)
    _ramp(parts, t, ox, H - 40, 140, fmt_tick(lo), fmt_tick(hi))
    return _done(parts, opt, W, H, len(cell))


def _c_calendar(spec, rows, opt):
    import datetime
    c = _need(rows, [("date", opt["x"]), ("val", opt["val"] or opt["y"])])
    pts = []
    for r in rows:
        d = _parse_date(r.get(c["date"]))
        if d is None:
            continue
        try:
            pts.append((d.date(), _f(r, c["val"])))
        except (TypeError, ValueError):
            continue
    if not pts:
        raise SpecError("calendar needs dates and values")
    pts.sort()
    end = pts[-1][0]
    start = end - datetime.timedelta(weeks=59)
    window = [p for p in pts if p[0] >= start]
    note = "" if len(window) == len(pts) else f"from {window[0][0].isoformat()}"
    vals = [v for _, v in window]
    lo, hi = min(vals), max(vals)
    by = {d: v for d, v in window}
    first = window[0][0] - datetime.timedelta(days=window[0][0].weekday())
    last = window[-1][0]
    weeks = (last - first).days // 7 + 1
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 220, ox=48, right=28, W=max(760, 70 + weeks * 16), bottom=64)
    cell = 14
    days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    for i, name in enumerate(days):
        parts.append(
            f'<text x="{ox - 4}" y="{oy + i * (cell + 3) + 11:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{name[0]}</text>')
    for d, v in by.items():
        week = (d - first).days // 7
        dow = d.weekday()
        u = 0.5 if hi == lo else (v - lo) / (hi - lo)
        parts.append(
            f'<rect x="{ox + week * (cell + 3):.1f}" y="{oy + dow * (cell + 3):.1f}" width="{cell}" height="{cell}" rx="2" fill="{_heat_color(t, u)}"/>')
    _ramp(parts, t, ox, oy + 7 * (cell + 3) + 8, 120, fmt_tick(lo), fmt_tick(hi))
    return _done(parts, opt, W, H, len(window), note)


def _c_radar(spec, rows, opt):
    import math
    c = _need(rows, [("axis", opt["x"] or opt["label"]), ("series", opt["group"]), ("val", opt["val"] or opt["y"])])
    axes, series = [], []
    cell = {}
    for r in rows:
        try:
            axis, name, val = str(r.get(c["axis"]) or ""), str(r.get(c["series"]) or ""), _f(r, c["val"])
        except (TypeError, ValueError):
            continue
        if axis not in axes:
            axes.append(axis)
        if name not in series:
            series.append(name)
        cell[(axis, name)] = val
    if len(axes) < 3:
        raise SpecError("radar needs at least 3 axes")
    _cap(None, len(axes), 8, "axes", opt["unbounded"])
    _cap(None, len(series), 4, "series", opt["unbounded"])
    vals = list(cell.values())
    lo, hi = _domain(vals)
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 380, ox=40, right=40, bottom=70)
    cx, cy = W / 2, oy + ph / 2
    radius = min(pw, ph) * 0.38
    pal = series_palette(t)
    for step in (0.25, 0.5, 0.75, 1):
        pts = []
        for i in range(len(axes)):
            ang = -math.pi / 2 + i * math.tau / len(axes)
            pts.append(f"{cx + radius * step * math.cos(ang):.1f},{cy + radius * step * math.sin(ang):.1f}")
        parts.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="{t["rule"]}"/>')
    for i, axis in enumerate(axes):
        ang = -math.pi / 2 + i * math.tau / len(axes)
        x, y = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
        parts.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        lx, ly = cx + (radius + 16) * math.cos(ang), cy + (radius + 16) * math.sin(ang)
        anchor = "middle" if abs(math.cos(ang)) < 0.3 else ("start" if math.cos(ang) > 0 else "end")
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="{anchor}">{esc(_short(axis, 14))}</text>')
    for s, name in enumerate(series):
        pts = []
        col = t["accent"] if _hit(opt["highlights"], name) else (t["link"] if len(series) == 1 else pal[s % len(pal)])
        for i, axis in enumerate(axes):
            v = cell.get((axis, name), lo)
            u = 0 if hi == lo else (v - lo) / (hi - lo)
            ang = -math.pi / 2 + i * math.tau / len(axes)
            pts.append((cx + radius * u * math.cos(ang), cy + radius * u * math.sin(ang)))
        seq = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polygon points="{seq}" fill="{col}" fill-opacity="0.16" stroke="{col}" stroke-width="1.6"/>')
        if opt["markers"] or _hit(opt["highlights"], name):
            for x, y in pts:
                _dot(parts, t, x, y, 3.2, col, True, _hit(opt["highlights"], name))
    if len(series) > 1:
        _legend(parts, t, [(pal[i % len(pal)], n) for i, n in enumerate(series)], ox, H - 34)
    return _done(parts, opt, W, H, len(cell))


def _c_polar(spec, rows, opt):
    import math
    c = _need(rows, [("cat", opt["label"] or opt["x"]), ("val", opt["val"] or opt["y"])])
    items = []
    for r in rows:
        try:
            items.append((str(r.get(c["cat"]) or ""), max(0.0, _f(r, c["val"]))))
        except (TypeError, ValueError):
            continue
    if not items:
        raise SpecError("polar needs cat and val")
    _cap(None, len(items), 24, "slices", opt["unbounded"])
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 380, ox=36, right=36)
    cx, cy = W / 2, oy + ph / 2
    radius = min(pw, ph) * 0.40
    peak = max(v for _, v in items) or 1
    for step in (0.5, 1):
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius * step:.1f}" fill="none" stroke="{t["rule"]}"/>')
    for i, (name, val) in enumerate(items):
        a0 = -math.pi / 2 + i * math.tau / len(items)
        a1 = a0 + math.tau / len(items)
        r = radius * val / peak
        col = t["accent"] if _hit(opt["highlights"], name) else t["link"]
        if a1 - a0 >= math.tau - 1e-3:
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{col}" fill-opacity="0.8"/>')
        else:
            x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            large = 1 if a1 - a0 > math.pi else 0
            parts.append(
                f'<path d="M {cx:.1f} {cy:.1f} L {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 {large} 1 {x1:.1f} {y1:.1f} Z" fill="{col}" fill-opacity="0.8" stroke="{t["paper"]}"/>')
        mid = (a0 + a1) / 2
        parts.append(
            f'<text x="{cx + (radius + 14) * math.cos(mid):.1f}" y="{cy + (radius + 14) * math.sin(mid):.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(name, 12))}</text>')
    return _done(parts, opt, W, H, len(items))


def _c_status(spec, rows, opt):
    c = _need(rows, [("row", opt["y"] or opt["label"]), ("col", opt["x"]), ("state", opt["group"] or opt["val"])])
    rs, cs = [], []
    cell = {}
    for r in rows:
        row, col, state = str(r.get(c["row"]) or ""), str(r.get(c["col"]) or ""), str(r.get(c["state"]) or "").lower()
        if row not in rs:
            rs.append(row)
        if col not in cs:
            cs.append(col)
        cell[(row, col)] = state
    _cap(None, len(rs) * max(len(cs), 1), 200, "cells", opt["unbounded"])
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(200, len(rs) * 36 + 10), ox=120, bottom=70)
    cw = pw / max(len(cs), 1)
    ch = ph / max(len(rs), 1)
    paint = {"ok": t["link"], "up": t["link"], "good": t["link"], "warn": t["accent"], "warning": t["accent"],
             "down": t["ink"], "bad": t["ink"], "fail": t["ink"], "failed": t["ink"]}
    for iy, row in enumerate(rs):
        parts.append(
            f'<text x="{ox - 8}" y="{oy + (iy + 0.5) * ch + 4:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(_short(row, 16))}</text>')
        for ix, col in enumerate(cs):
            state = cell.get((row, col), "")
            colr = paint.get(state, t["card"])
            stroke = t["accent"] if _hit(opt["highlights"], row, col, state) else t["rule"]
            parts.append(
                f'<rect x="{ox + ix * cw + 3:.1f}" y="{oy + iy * ch + 3:.1f}" width="{cw - 6:.1f}" height="{ch - 6:.1f}" rx="3" fill="{colr}" stroke="{stroke}"/>')
    _cat_labels(parts, t, cs, [ox + (i + 0.5) * cw for i in range(len(cs))], oy + ph + 16, len(cs) > 6)
    _legend(parts, t, [(t["link"], "ok"), (t["accent"], "warn"), (t["ink"], "down"), (t["card"], "other")], ox, H - 34)
    return _done(parts, opt, W, H, len(cell))


def _c_forest(spec, rows, opt):
    c = _need(rows, [("cat", opt["label"] or opt["x"]), ("est", opt["val"] or opt["y"]), ("lo", opt["lo"]), ("hi", opt["hi"])])
    items = []
    for r in rows:
        try:
            items.append((str(r.get(c["cat"]) or ""), _f(r, c["est"]), _f(r, c["lo"]), _f(r, c["hi"])))
        except (TypeError, ValueError):
            continue
    if not items:
        raise SpecError("forest needs cat, est, lo, and hi")
    _cap(None, len(items), 20, "rows", opt["unbounded"])
    vals = [v for _, e, lo, hi in items for v in (e, lo, hi)]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(220, len(items) * 28), ox=140)
    xt = nice_ticks(min(vals), max(vals) if max(vals) != min(vals) else min(vals) + 1)
    span = (xt[-1] - xt[0]) or 1

    def X(v):
        return ox + (v - xt[0]) / span * pw

    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in xt:
        x = X(v)
        if opt["grid"]:
            parts.append(f'<line x1="{x:.1f}" y1="{oy}" x2="{x:.1f}" y2="{oy + ph}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{oy + ph + 16}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{fmt_tick(v)}</text>')
    if xt[0] <= 0 <= xt[-1]:
        parts.append(f'<line x1="{X(0):.1f}" y1="{oy}" x2="{X(0):.1f}" y2="{oy + ph}" stroke="{t["soft"]}" stroke-dasharray="3 3"/>')
    for i, (name, est, lo, hi) in enumerate(items):
        y = oy + (i + 0.5) * ph / len(items)
        hit = _hit(opt["highlights"], name)
        col = t["accent"] if hit else t["link"]
        parts.append(f'<line x1="{X(lo):.1f}" y1="{y:.1f}" x2="{X(hi):.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="1.4"/>')
        parts.append(f'<line x1="{X(lo):.1f}" y1="{y - 4:.1f}" x2="{X(lo):.1f}" y2="{y + 4:.1f}" stroke="{col}"/>')
        parts.append(f'<line x1="{X(hi):.1f}" y1="{y - 4:.1f}" x2="{X(hi):.1f}" y2="{y + 4:.1f}" stroke="{col}"/>')
        _dot(parts, t, X(est), y, 4.2, col, True, hit)
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(_short(name, 18))}</text>')
    return _done(parts, opt, W, H, len(items))


def _c_qq(spec, rows, opt):
    c = _need(rows, [("val", opt["val"] or opt["y"] or opt["x"])])
    vals = sorted(v for _, v in _floats(rows, c["val"]))
    _cap(None, len(vals), 400, "points", opt["unbounded"])
    n = len(vals)
    theo = [_ninv((i + 0.5) / n) for i in range(n)]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 320)
    X, Y = _axes(parts, t, ox, oy, pw, ph, nice_ticks(min(theo), max(theo)), nice_ticks(*_domain(vals, floor0=False)), opt["grid"])
    q1, _, q3 = _quartiles(vals)
    t1, t3 = _ninv(0.25), _ninv(0.75)
    if t3 != t1:
        slope = (q3 - q1) / (t3 - t1)
        intercept = q1 - slope * t1
        x0, x1 = min(theo), max(theo)
        parts.append(
            f'<line x1="{X(x0):.1f}" y1="{Y(intercept + slope * x0):.1f}" x2="{X(x1):.1f}" y2="{Y(intercept + slope * x1):.1f}" stroke="{t["accent"]}" stroke-width="1.2"/>')
    for x, y in zip(theo, vals):
        _dot(parts, t, X(x), Y(y), 3.2, t["link"], opt["markers"], False)
    return _done(parts, opt, W, H, n, "normal quantile")


def _c_volcano(spec, rows, opt):
    import math
    c = _need(rows, [("x", opt["x"]), ("y", opt["y"])])
    lab = _col(rows, opt["label"], "label")
    pts = []
    for r in rows:
        try:
            pts.append((r, _f(r, c["x"]), _f(r, c["y"])))
        except (TypeError, ValueError):
            continue
    if not pts:
        raise SpecError("volcano needs numeric x and y")
    _cap(None, len(pts), 400, "points", opt["unbounded"])
    plotted = []
    as_p = max(p[2] for p in pts) <= 1
    for r, x, y in pts:
        py = -math.log10(max(y, 1e-300)) if as_p else y
        plotted.append((r, x, py))
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 320, bottom=56)
    xs = [p[1] for p in plotted]
    ys = [p[2] for p in plotted]
    X, Y = _axes(parts, t, ox, oy, pw, ph, nice_ticks(min(xs), max(xs) if max(xs) != min(xs) else min(xs) + 1),
                 nice_ticks(0, max(ys) if max(ys) else 1), opt["grid"])
    ranked = sorted(plotted, key=lambda p: p[2], reverse=True)
    label_ids = {id(p[0]) for p in ranked[:5]}
    for r, x, y in plotted:
        name = str(r.get(lab) or "") if lab else ""
        strong = abs(x) > 1 and y > 2
        hit = _hit(opt["highlights"], name, x) or strong
        _dot(parts, t, X(x), Y(y), 3.4, t["link"], opt["markers"], hit)
        if opt["markers"] and lab and id(r) in label_ids and name:
            parts.append(
                f'<text x="{X(x) + 6:.1f}" y="{Y(y) - 4:.1f}" font-size="10" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(name, 16))}</text>')
    note = "y is -log10 of a p-value" if as_p else ""
    return _done(parts, opt, W, H, len(plotted), note)


def _c_candle(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("open", None), ("high", None), ("low", None), ("close", None)])
    items = []
    for r in rows:
        try:
            items.append((str(r.get(c["x"]) or ""), _f(r, c["open"]), _f(r, c["high"]), _f(r, c["low"]), _f(r, c["close"])))
        except (TypeError, ValueError):
            continue
    if not items:
        raise SpecError("candle needs x, open, high, low, close")
    _cap(None, len(items), 80, "candles", opt["unbounded"])
    vals = [v for it in items for v in it[2:4]]
    rotate = len(items) > 8
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=84 if rotate else 56)
    yt = nice_ticks(*_domain(vals, floor0=min(vals) >= 0))
    span = (yt[-1] - yt[0]) or 1

    def Y(v):
        return oy + ph - (v - yt[0]) / span * ph

    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    slot = pw / len(items)
    bw = min(14, slot * 0.5)
    centers = []
    for i, (name, o, h, low, cl) in enumerate(items):
        x = ox + (i + 0.5) * slot
        centers.append(x)
        col = t["accent"] if _hit(opt["highlights"], name) or cl < o else t["link"]
        parts.append(f'<line x1="{x:.1f}" y1="{Y(h):.1f}" x2="{x:.1f}" y2="{Y(low):.1f}" stroke="{col}" stroke-width="1.2"/>')
        top, bot = Y(max(o, cl)), Y(min(o, cl))
        parts.append(
            f'<rect x="{x - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(1.2, bot - top):.1f}" fill="{col}"/>')
    _cat_labels(parts, t, [it[0] for it in items], centers, oy + ph + 16, rotate)
    return _done(parts, opt, W, H, len(items))


def _sankey_layers(links):
    """Longest-path columns. A cycle does not add another column."""
    names = []
    pred = {}
    for s, d, _v in links:
        if s not in pred:
            pred[s] = []
            names.append(s)
        if d not in pred:
            pred[d] = []
            names.append(d)
        if s not in pred[d]:
            pred[d].append(s)
    rank = {n: 0 for n in names}
    guard = len(names)
    for _ in range(guard):
        changed = False
        for n in names:
            ups = [rank[p] + 1 for p in pred[n]]
            if not ups:
                continue
            nxt = max(ups)
            if nxt >= guard or nxt == rank[n]:
                continue
            rank[n] = nxt
            changed = True
        if not changed:
            break
    layers = {}
    for n in names:
        layers.setdefault(rank[n], []).append(n)
    return [layers[k] for k in sorted(layers)]


def _sankey_balance(cols, links):
    """Reorder each column so flows that share a node stay in the same top-to-bottom order."""
    pred, succ = {}, {}
    for s, d, v in links:
        pred.setdefault(d, []).append((s, v))
        succ.setdefault(s, []).append((d, v))
    cols = [list(c) for c in cols]

    def bary(group, neigh, index):
        def key(n):
            ws = [(index[m], w) for m, w in neigh.get(n, []) if m in index]
            if not ws:
                return (index.get(n, 0), n)
            tot = sum(w for _, w in ws) or 1
            return (sum(i * w for i, w in ws) / tot, n)
        return sorted(group, key=key)

    for _ in range(6):
        index = {n: i for col in cols for i, n in enumerate(col)}
        cols = [cols[0]] + [bary(col, pred, index) for col in cols[1:]]
        index = {n: i for col in cols for i, n in enumerate(col)}
        cols = [bary(col, succ, index) for col in cols[:-1]] + [cols[-1]]
    return cols


def _c_sankey(spec, rows, opt):
    c = _need(rows, [("src", opt["x"] or opt["label"]), ("dst", opt["y"]), ("val", opt["val"])])
    links = []
    for r in rows:
        try:
            val = _f(r, c["val"])
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        links.append((str(r.get(c["src"]) or ""), str(r.get(c["dst"]) or ""), val))
    if not links:
        raise SpecError("sankey needs src, dst, and val")
    _cap(None, len(links), 40, "links", opt["unbounded"])
    out_w, in_w = {}, {}
    for s, d, v in links:
        out_w[s] = out_w.get(s, 0) + v
        in_w[d] = in_w.get(d, 0) + v
    cols = _sankey_balance(_sankey_layers(links), links)
    names = [n for col in cols for n in col]
    weight = {n: max(out_w.get(n, 0), in_w.get(n, 0)) for n in names}
    nw, gap = 12, 12
    n_cols = len(cols)
    W = max(780, 160 + n_cols * 230)
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 380, ox=132, right=132, W=W, bottom=48)
    if n_cols == 1:
        xs = [ox + pw / 2 - nw / 2]
    else:
        xs = [ox + i * (pw - nw) / (n_cols - 1) for i in range(n_cols)]

    def pads(ci):
        return (6, 6)

    ks = []
    for ci, col in enumerate(cols):
        top_pad, bot_pad = pads(ci)
        gaps = gap * max(len(col) - 1, 0)
        total = sum(weight[n] for n in col) or 1
        ks.append(max(0.0, (ph - top_pad - bot_pad - gaps) / total))
    k = min(ks) if ks else 1
    top, height = {}, {}
    for ci, col in enumerate(cols):
        top_pad, bot_pad = pads(ci)
        raw = [weight[n] * k for n in col]
        boost = sum(max(0.0, 4 - h) for h in raw)
        gaps = gap * max(len(col) - 1, 0)
        room = ph - top_pad - bot_pad - gaps
        use = [max(4.0, h) for h in raw] if sum(raw) + boost <= room + 0.1 else [max(2.0, h) for h in raw]
        extra = max(0.0, room - sum(use))
        y = oy + top_pad + extra / 2
        for n, h in zip(col, use):
            top[n] = y
            height[n] = h
            y += h + gap
    col_of = {n: ci for ci, col in enumerate(cols) for n in col}
    index = {n: i for col in cols for i, n in enumerate(col)}
    outgoing = {n: [] for n in names}
    incoming = {n: [] for n in names}
    for i, (s, d, _v) in enumerate(links):
        outgoing[s].append(i)
        incoming[d].append(i)

    def sort_out(idxs):
        return sorted(idxs, key=lambda i: (col_of[links[i][1]], index[links[i][1]], links[i][1]))

    def sort_in(idxs):
        return sorted(idxs, key=lambda i: (col_of[links[i][0]], index[links[i][0]], links[i][0]))

    src_box, dst_box = {}, {}
    for n in names:
        y = top[n]
        share = weight[n] or 1
        for i in sort_out(outgoing[n]):
            h = height[n] * (links[i][2] / share)
            src_box[i] = (y, y + h)
            y += h
        y = top[n]
        for i in sort_in(incoming[n]):
            h = height[n] * (links[i][2] / share)
            dst_box[i] = (y, y + h)
            y += h
    sources = [n for n in names if out_w.get(n, 0) > 0]
    pal = series_palette(t)
    if len(sources) <= 1:
        src_color = {n: t["link"] for n in sources}
    else:
        src_color = {n: pal[i % len(pal)] for i, n in enumerate(sources)}

    def ribbon(x1, y1a, y1b, x2, y2a, y2b):
        if y1b - y1a > 7:
            y1a, y1b = y1a + 1.2, y1b - 1.2
        if y2b - y2a > 7:
            y2a, y2b = y2a + 1.2, y2b - 1.2
        mx = (x1 + x2) / 2
        return (
            f"M {x1:.1f} {y1a:.1f} C {mx:.1f} {y1a:.1f} {mx:.1f} {y2a:.1f} {x2:.1f} {y2a:.1f} "
            f"L {x2:.1f} {y2b:.1f} C {mx:.1f} {y2b:.1f} {mx:.1f} {y1b:.1f} {x1:.1f} {y1b:.1f} Z")

    def attach(s, d):
        cs, cd = col_of[s], col_of[d]
        if cs < cd:
            return xs[cs] + nw, xs[cd]
        if cs > cd:
            return xs[cs], xs[cd] + nw
        return xs[cs] + nw, xs[cs] + nw + 48

    order = sorted(range(len(links)), key=lambda i: 1 if _hit(opt["highlights"], links[i][0], links[i][1]) else 0)
    for i in order:
        s, d, _v = links[i]
        x1, x2 = attach(s, d)
        y1a, y1b = src_box[i]
        y2a, y2b = dst_box[i]
        hit = _hit(opt["highlights"], s, d)
        colr = t["accent"] if hit else src_color.get(s, t["link"])
        parts.append(
            f'<path d="{ribbon(x1, y1a, y1b, x2, y2a, y2b)}" fill="{colr}" fill-opacity="0.9" stroke="{t["paper"]}" stroke-width="1.2"/>')
    for ci, col in enumerate(cols):
        x = xs[ci]
        for j, n in enumerate(col):
            y0, h = top[n], height[n]
            parts.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{nw}" height="{h:.1f}" fill="{t["ink"]}"/>')
            shown = esc(_short(n, 18))
            if ci == 0 or ci == n_cols - 1:
                anchor = "end" if ci == 0 else "start"
                lx = x - 10 if ci == 0 else x + nw + 10
                parts.append(
                    f'<text x="{lx:.1f}" y="{y0 + h / 2 + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="{anchor}">{shown}</text>')
                if opt["markers"] and h >= 28:
                    parts.append(
                        f'<text x="{lx:.1f}" y="{y0 + h / 2 + 18:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="{anchor}">{esc(fmt_tick(weight[n]))}</text>')
            else:
                parts.append(
                    f'<text x="{x + nw / 2:.1f}" y="{y0 + h / 2 + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle" stroke="{t["paper"]}" stroke-width="3.5" paint-order="stroke fill">{shown}</text>')
    return _done(parts, opt, W, H, len(links))


def _c_stream(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("group", opt["group"]), ("val", opt["val"] or opt["y"])])
    xs, groups, cell = [], [], {}
    for r in rows:
        try:
            x, g, v = str(r.get(c["x"]) or ""), str(r.get(c["group"]) or ""), _f(r, c["val"])
        except (TypeError, ValueError):
            continue
        if x not in xs:
            xs.append(x)
        if g not in groups:
            groups.append(g)
        cell[(x, g)] = cell.get((x, g), 0) + max(0.0, v)
    if len(xs) < 2 or not groups:
        raise SpecError("stream needs at least two x values and a group")
    _cap(None, len(groups), 8, "groups", opt["unbounded"])
    totals = [sum(cell.get((x, g), 0) for g in groups) for x in xs]
    peak = max(totals) or 1
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, bottom=72)
    pal = series_palette(t)

    def X(i):
        return ox + i * pw / (len(xs) - 1)

    def Y(v):
        return oy + ph / 2 - v / peak * (ph * 0.86)

    def smooth(pts):
        """Closed-enough cubic through a polyline. Endpoints stay put."""
        if len(pts) < 2:
            return ""
        seq = [pts[0]]
        for i in range(len(pts) - 1):
            p0 = pts[i - 1] if i else pts[i]
            p1, p2 = pts[i], pts[i + 1]
            p3 = pts[i + 2] if i + 2 < len(pts) else pts[i + 1]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
            seq.append(c1)
            seq.append(c2)
            seq.append(p2)
        head = f"M {seq[0][0]:.1f} {seq[0][1]:.1f}"
        body = []
        for i in range(1, len(seq), 3):
            a, b, c = seq[i], seq[i + 1], seq[i + 2]
            body.append(f"C {a[0]:.1f} {a[1]:.1f} {b[0]:.1f} {b[1]:.1f} {c[0]:.1f} {c[1]:.1f}")
        return head + " " + " ".join(body)

    low = [-t / 2 for t in totals]
    for gi, g in enumerate(groups):
        high = [low[i] + cell.get((xs[i], g), 0) for i in range(len(xs))]
        fwd = [(X(i), Y(low[i])) for i in range(len(xs))]
        back = [(X(i), Y(high[i])) for i in range(len(xs) - 1, -1, -1)]
        col = pal[gi % len(pal)]
        parts.append(f'<path d="{smooth(fwd)} {smooth(back).replace("M", "L", 1)} Z" fill="{col}" fill-opacity="0.82"/>')
        low = high
    _cat_labels(parts, t, xs, [X(i) for i in range(len(xs))], oy + ph + 16, len(xs) > 6)
    _legend(parts, t, [(pal[i % len(pal)], g) for i, g in enumerate(groups)], ox, H - 34)
    return _done(parts, opt, W, H, len(xs) * len(groups))


def _c_funnel(spec, rows, opt):
    c = _need(rows, [("cat", opt["label"] or opt["x"]), ("val", opt["val"] or opt["y"])])
    items = _shares(rows, c["cat"], c["val"])
    _cap(None, len(items), 8, "stages", opt["unbounded"])
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(240, len(items) * 56), ox=120, right=80)
    first = items[0][1] or 1
    band = ph / len(items)
    cx = ox + pw / 2
    prev = items[0][1]
    for i, (name, val) in enumerate(items):
        w0 = pw * (prev / first)
        w1 = pw * (val / first)
        y0 = oy + i * band
        y1 = y0 + band - 8
        col = t["accent"] if _hit(opt["highlights"], name) else t["link"]
        parts.append(
            f'<polygon points="{cx - w0 / 2:.1f},{y0:.1f} {cx + w0 / 2:.1f},{y0:.1f} {cx + w1 / 2:.1f},{y1:.1f} {cx - w1 / 2:.1f},{y1:.1f}" fill="{col}" fill-opacity="{0.9 - i * 0.08:.2f}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{(y0 + y1) / 2 + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(_short(name, 16))}</text>')
        if opt["markers"]:
            parts.append(
                f'<text x="{cx:.1f}" y="{(y0 + y1) / 2 + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["card"]}" text-anchor="middle">{val / first * 100:.0f}%</text>')
        prev = val
    return _done(parts, opt, W, H, len(items))


def _c_combo(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("bar", opt["a"] or opt["val"]), ("line", opt["b"] or opt["y"])])
    items = []
    for r in rows:
        try:
            items.append((str(r.get(c["x"]) or ""), _f(r, c["bar"]), _f(r, c["line"])))
        except (TypeError, ValueError):
            continue
    if not items:
        raise SpecError("combo needs x, bar, and line")
    _cap(None, len(items), 24, "points", opt["unbounded"])
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 300, right=72, bottom=76)
    bars = [b for _, b, _ in items]
    lines = [v for _, _, v in items]
    y0 = axis_ticks(*_domain(bars))
    y1 = nice_ticks(*_domain(lines))
    s0 = (y0[-1] - y0[0]) or 1
    s1 = (y1[-1] - y1[0]) or 1

    def Y0(v):
        return oy + ph - (v - y0[0]) / s0 * ph

    def Y1(v):
        return oy + ph - (v - y1[0]) / s1 * ph

    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox + pw}" y1="{oy}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in y0:
        y = Y0(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    for v in y1:
        parts.append(
            f'<text x="{ox + pw + 8}" y="{Y1(v) + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}">{fmt_tick(v)}</text>')
    slot = pw / len(items)
    bw = min(28, slot * 0.5)
    centers = []
    d = []
    for i, (name, bar, line) in enumerate(items):
        x = ox + (i + 0.5) * slot
        centers.append(x)
        top = Y0(max(bar, 0))
        parts.append(
            f'<rect x="{x - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(1, oy + ph - top):.1f}" fill="{t["link"]}" fill-opacity="0.85"/>')
        d.append(f'{"M" if i == 0 else "L"} {x:.1f} {Y1(line):.1f}')
    parts.append(f'<path d="{" ".join(d)}" fill="none" stroke="{t["accent"]}" stroke-width="1.8"/>')
    if opt["markers"]:
        for i, (name, bar, line) in enumerate(items):
            _dot(parts, t, centers[i], Y1(line), 3.4, t["accent"], True, _hit(opt["highlights"], name))
    _cat_labels(parts, t, [it[0] for it in items], centers, oy + ph + 16, len(items) > 6)
    _legend(parts, t, [(t["link"], "bar"), (t["accent"], "line")], ox, H - 34)
    return _done(parts, opt, W, H, len(items))


def _c_quadrant(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("y", opt["y"])])
    lab = _col(rows, opt["label"], "label")
    pts = []
    for r in rows:
        try:
            pts.append((str(r.get(lab) or "") if lab else "", _f(r, c["x"]), _f(r, c["y"])))
        except (TypeError, ValueError):
            continue
    if not pts:
        raise SpecError("quadrant needs numeric x and y")
    _cap(None, len(pts), 40, "points", opt["unbounded"])
    xs = [p[1] for p in pts]
    ys = [p[2] for p in pts]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 320, bottom=56)
    xt = nice_ticks(min(xs), max(xs) if max(xs) != min(xs) else min(xs) + 1)
    yt = nice_ticks(min(ys), max(ys) if max(ys) != min(ys) else min(ys) + 1)
    X, Y = _axes(parts, t, ox, oy, pw, ph, xt, yt, opt["grid"])

    def mid(vals, ticks):
        if min(vals) < 0 < max(vals):
            return 0.0
        return _quartiles(vals)[1]

    mx, my = mid(xs, xt), mid(ys, yt)
    parts.append(f'<line x1="{X(mx):.1f}" y1="{oy}" x2="{X(mx):.1f}" y2="{oy + ph}" stroke="{t["soft"]}" stroke-dasharray="4 3"/>')
    parts.append(f'<line x1="{ox}" y1="{Y(my):.1f}" x2="{ox + pw}" y2="{Y(my):.1f}" stroke="{t["soft"]}" stroke-dasharray="4 3"/>')
    for name, x, y in pts:
        _dot(parts, t, X(x), Y(y), 4.2, t["link"], opt["markers"], _hit(opt["highlights"], name))
        if name and (opt["markers"] or len(pts) <= 12):
            tx = min(ox + pw - 4, X(x) + 8)
            parts.append(
                f'<text x="{tx:.1f}" y="{Y(y) - 6:.1f}" font-size="10" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(name, 18))}</text>')
    return _done(parts, opt, W, H, len(pts))


def _isolines(xs, ys, grid, levels):
    segs = []
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            corners = []
            ok = True
            for dj, di in ((0, 0), (0, 1), (1, 1), (1, 0)):
                z = grid[j + dj][i + di]
                if z is None:
                    ok = False
                    break
                corners.append((xs[i + di], ys[j + dj], z))
            if not ok:
                continue
            for level in levels:
                hits = []
                for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
                    za, zb = corners[a][2], corners[b][2]
                    if (za - level) == 0 and (zb - level) == 0:
                        continue
                    if (za - level) * (zb - level) < 0:
                        t = (level - za) / (zb - za)
                        hits.append((corners[a][0] + t * (corners[b][0] - corners[a][0]),
                                     corners[a][1] + t * (corners[b][1] - corners[a][1])))
                if len(hits) >= 2:
                    segs.append((hits[0], hits[1], level))
                if len(hits) == 4:
                    segs.append((hits[2], hits[3], level))
    return segs


def _c_contour(spec, rows, opt):
    c = _need(rows, [("x", opt["x"]), ("y", opt["y"]), ("z", opt["val"])])
    pts = []
    for r in rows:
        try:
            pts.append((_f(r, c["x"]), _f(r, c["y"]), _f(r, c["z"])))
        except (TypeError, ValueError):
            continue
    if len(pts) < 4:
        raise SpecError("contour needs at least 4 x, y, z rows")
    _cap(None, len(pts), 400, "points", opt["unbounded"])
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    nx = ny = 8
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    if hi_x == lo_x:
        hi_x += 1
    if hi_y == lo_y:
        hi_y += 1
    acc = [[[] for _ in range(nx)] for _ in range(ny)]
    for x, y, z in pts:
        i = min(nx - 1, int((x - lo_x) / (hi_x - lo_x) * nx))
        j = min(ny - 1, int((y - lo_y) / (hi_y - lo_y) * ny))
        acc[j][i].append(z)
    grid = [[(sum(cell) / len(cell) if cell else None) for cell in row] for row in acc]
    known = [z for row in grid for z in row if z is not None]
    levels = []
    if known and max(known) != min(known):
        levels = [min(known) + (max(known) - min(known)) * (k + 1) / 5 for k in range(4)]
    gx = [lo_x + (hi_x - lo_x) * (i + 0.5) / nx for i in range(nx)]
    gy = [lo_y + (hi_y - lo_y) * (j + 0.5) / ny for j in range(ny)]
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 320)
    X, Y = _axes(parts, t, ox, oy, pw, ph, nice_ticks(lo_x, hi_x), nice_ticks(lo_y, hi_y), opt["grid"])
    segs = _isolines(gx, gy, grid, levels)
    pal = series_palette(t)
    for a, b, level in segs:
        u = 0 if not levels else levels.index(level) / max(len(levels) - 1, 1)
        parts.append(
            f'<line x1="{X(a[0]):.1f}" y1="{Y(a[1]):.1f}" x2="{X(b[0]):.1f}" y2="{Y(b[1]):.1f}" stroke="{_heat_color(t, u)}" stroke-width="1.6"/>')
    if opt["markers"] and len(pts) <= 80:
        for x, y, z in pts:
            _dot(parts, t, X(x), Y(y), 2.4, t["ink"], True, False)
    return _done(parts, opt, W, H, len(pts), f"{len(levels)} levels" if levels else "flat field")


def _json(spec):
    if not isinstance(spec, dict):
        raise SpecError("this chart reads a JSON spec")
    return spec


def _c_dag(spec, rows, opt):
    spec = _json(spec)
    nodes, edges = spec.get("nodes") or [], spec.get("edges") or []
    opt = dict(opt, spec=spec)
    parts, pos, W, H = _linked(opt, nodes, edges, 12, 24)
    _paint_boxes(parts, opt["t"], pos, _focals(nodes))
    _draw_links(parts, opt["t"], pos, edges)
    return _done(parts, opt, W, H, len(nodes))


def _force_pos(nodes, edges, W, top, height):
    import math
    ids = [n["id"] for n in nodes]
    pos = {}
    for i, n in enumerate(nodes):
        ang = math.tau * i / max(len(nodes), 1)
        pos[n["id"]] = [W / 2 + 150 * math.cos(ang), top + height / 2 + 100 * math.sin(ang)]
    links = [(e.get("from"), e.get("to")) for e in edges if e.get("from") in pos and e.get("to") in pos]
    for _ in range(80):
        force = {i: [0.0, 0.0] for i in ids}
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                ia, ib = ids[a], ids[b]
                dx, dy = pos[ia][0] - pos[ib][0], pos[ia][1] - pos[ib][1]
                dist = math.hypot(dx, dy) or 0.1
                f = 800.0 / (dist * dist)
                force[ia][0] += f * dx / dist
                force[ia][1] += f * dy / dist
                force[ib][0] -= f * dx / dist
                force[ib][1] -= f * dy / dist
        for a, b in links:
            dx, dy = pos[b][0] - pos[a][0], pos[b][1] - pos[a][1]
            dist = math.hypot(dx, dy) or 0.1
            f = (dist - 90) * 0.05
            force[a][0] += max(-12, min(12, f * dx / dist))
            force[a][1] += max(-12, min(12, f * dy / dist))
            force[b][0] -= max(-12, min(12, f * dx / dist))
            force[b][1] -= max(-12, min(12, f * dy / dist))
        for i in ids:
            pos[i][0] = min(W - 46, max(46, pos[i][0] + max(-12, min(12, force[i][0]))))
            pos[i][1] = min(top + height - 16, max(top + 8, pos[i][1] + max(-12, min(12, force[i][1]))))
    return pos


def _c_force(spec, rows, opt, colored=False):
    spec = _json(spec)
    nodes, edges = _with_ids(spec.get("nodes") or []), spec.get("edges") or []
    unbounded = _open_budget(spec, opt["unbounded"])
    _cap(spec, len(nodes), 40, "nodes", unbounded)
    _cap(spec, len(edges), 80, "edges", unbounded)
    if len(nodes) < 1:
        raise SpecError("need at least one node")
    hh = _hh(opt["title"], opt["sub"])
    W, top, height = 760, hh + 20, 420
    H = top + height + 40
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    t = opt["t"]
    pos = _force_pos(nodes, edges, W, top, height)
    pal = series_palette(t)
    kinds = _ordered(str(n.get("kind") or "") for n in nodes) if colored else []
    kcol = {k: pal[i % len(pal)] for i, k in enumerate(kinds)}
    by = {n["id"]: n for n in nodes}
    for e in edges:
        if e.get("from") in pos and e.get("to") in pos:
            a, b = pos[e["from"]], pos[e["to"]]
            parts.append(
                f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{t["muted"]}" stroke-width="1.2"/>')
    for n in nodes:
        x, y = pos[n["id"]]
        focal = n["id"] in _focals(nodes)
        if colored:
            fill = t["accent"] if focal else kcol.get(str(n.get("kind") or ""), t["link"])
        else:
            fill = t["accent"] if focal else t["link"]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="16" fill="{fill}" stroke="{t["card"]}" stroke-width="1.4"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 28:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n.get("name") or n["id"], 16))}</text>')
    if colored and len(kinds) > 1:
        _legend(parts, t, [(kcol[k], k or "kind") for k in kinds], 36, H - 34)
    return _done(parts, opt, W, H, len(nodes))


def _c_kg(spec, rows, opt):
    return _c_force(spec, rows, opt, colored=True)


def _c_radial(spec, rows, opt):
    import math
    from collections import defaultdict, deque
    spec = _json(spec)
    nodes, edges = _with_ids(spec.get("nodes") or []), spec.get("edges") or []
    unbounded = _open_budget(spec, opt["unbounded"])
    _cap(spec, len(nodes), 24, "nodes", unbounded)
    if not nodes:
        raise SpecError("radial needs nodes")
    adj = defaultdict(list)
    deg = defaultdict(int)
    for e in edges:
        if e.get("from") in {n["id"] for n in nodes} and e.get("to") in {n["id"] for n in nodes}:
            adj[e["from"]].append(e["to"])
            adj[e["to"]].append(e["from"])
            deg[e["from"]] += 1
            deg[e["to"]] += 1
    root = spec.get("root") or max(nodes, key=lambda n: deg[n["id"]])["id"]
    ring = {root: 0}
    q = deque([root])
    while q:
        cur = q.popleft()
        for nxt in adj[cur]:
            if nxt not in ring:
                ring[nxt] = ring[cur] + 1
                q.append(nxt)
    extra = max(ring.values(), default=0) + 1
    for n in nodes:
        ring.setdefault(n["id"], extra)
    groups = defaultdict(list)
    for n in nodes:
        groups[ring[n["id"]]].append(n)
    hh = _hh(opt["title"], opt["sub"])
    W, H = 760, hh + 500
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    t = opt["t"]
    cx, cy = W / 2, hh + 250
    pos = {}
    for depth, group in groups.items():
        rad = 0 if depth == 0 else 70 + depth * 78
        for i, n in enumerate(group):
            ang = -math.pi / 2 + math.tau * i / max(len(group), 1)
            pos[n["id"]] = (cx + rad * math.cos(ang), cy + rad * math.sin(ang), n)
    for e in edges:
        if e.get("from") in pos and e.get("to") in pos:
            a, b = pos[e["from"]], pos[e["to"]]
            parts.append(
                f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{t["muted"]}" stroke-width="1.2"/>')
    foc = _focals(nodes)
    for nid, (x, y, n) in pos.items():
        col = t["accent"] if nid in foc or nid == root else t["link"]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="15" fill="{col}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 28:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n.get("name") or nid, 14))}</text>')
    return _done(parts, opt, W, H, len(nodes))


def _draw_hierarchy(opt, roots, org=False, edge_labels=False):
    n = sum(1 for _ in _walk_tree(roots))
    cap = 12 if org else 24
    _cap(opt.get("spec"), n, cap, "nodes", opt["unbounded"])
    if not roots:
        raise SpecError("need a parent tree")
    pos, leaves = _leaf_pos(roots)
    pitch = 180 if org else 120
    gap = 100 if org else 84
    depth = _depth(roots)
    bw, bh = (156, 52) if org else (108, 36)
    margin = bw / 2 + 28
    span = (leaves - 1) * pitch
    W = max(760, int(span + margin * 2))
    top = _hh(opt["title"], opt["sub"]) + 36
    H = int(top + (depth - 1) * gap + bh + 70)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    t = opt["t"]
    origin = margin + max(0.0, (W - (span + margin * 2)) / 2)

    def at(node):
        x = origin + pos[id(node)][0] * pitch
        y = top + pos[id(node)][1] * gap
        return x, y

    def walk(node):
        x, y = at(node)
        for child in node["children"]:
            cx, cy = at(child)
            mid = y + bh + (cy - (y + bh)) / 2
            parts.append(
                f'<path d="M {x:.1f} {y + bh:.1f} V {mid:.1f} H {cx:.1f} V {cy:.1f}" fill="none" stroke="{t["muted"]}" stroke-width="1.3"/>')
            label = (child.get("raw") or {}).get("label") or ""
            if edge_labels and label:
                parts.append(
                    f'<text x="{(x + cx) / 2:.1f}" y="{mid - 4:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{esc(_short(label, 16))}</text>')
            walk(child)
        sub = (node.get("raw") or {}).get("sub") or ""
        hit = _hit(opt["highlights"], node["name"])
        fill = t["accent_tint"] if hit else t["card"]
        stroke = t["accent"] if hit else t["ink"]
        parts.append(
            f'<rect x="{x - bw / 2:.1f}" y="{y:.1f}" width="{bw}" height="{bh}" rx="2" fill="{fill}" stroke="{stroke}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + (22 if sub else bh / 2 + 4):.1f}" font-size="13" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(node["name"], 18))}</text>')
        if sub:
            parts.append(
                f'<text x="{x:.1f}" y="{y + 38:.1f}" font-size="11" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{esc(_short(sub, 22))}</text>')

    for root in roots:
        walk(root)
    return _done(parts, opt, W, H, n)


def _c_tree(spec, rows, opt):
    spec = _json(spec)
    opt = dict(opt, spec=spec)
    return _draw_hierarchy(opt, _tree_from(spec.get("nodes") or []))


def _c_dtree(spec, rows, opt):
    spec = _json(spec)
    opt = dict(opt, spec=spec)
    return _draw_hierarchy(opt, _tree_from(spec.get("nodes") or []), edge_labels=True)


def _c_org(spec, rows, opt):
    spec = _json(spec)
    opt = dict(opt, spec=spec)
    return _draw_hierarchy(opt, _tree_from(spec.get("nodes") or []), org=True)


def _c_nested(spec, rows, opt):
    spec = _json(spec)
    roots = _tree_from(spec.get("nodes") or [])
    n = sum(1 for _ in _walk_tree(roots))
    _cap(spec, n, 20, "nodes", _open_budget(spec, opt["unbounded"]))
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 400, ox=28, right=28)
    pal = series_palette(t)

    def draw(node, x, y, w, h, depth, idx):
        if depth > 4 or w < 8 or h < 8:
            return
        col = pal[idx % len(pal)]
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{t["card"]}" stroke="{col}" stroke-width="1.4"/>')
        if w > 36 and h > 16:
            parts.append(
                f'<text x="{x + 8:.1f}" y="{y + 16:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(node["name"], int(max(w / 8, 4))))}</text>')
        kids = node["children"]
        if not kids or depth == 4:
            return
        rects = _partition([(c, c["val"]) for c in kids], x + 6, y + 24, max(4, w - 12), max(4, h - 30), True)
        for i, (child, cx, cy, cw, ch) in enumerate(rects):
            draw(child, cx, cy, cw, ch, depth + 1, idx + i + 1)

    rects = _partition([(r, r["val"]) for r in roots], ox, oy, pw, ph, True)
    for i, (node, x, y, w, h) in enumerate(rects):
        draw(node, x, y, w, h, 1, i)
    return _done(parts, opt, W, H, n)


def _c_context(spec, rows, opt):
    spec = _json(spec)
    nodes, edges = _with_ids(spec.get("nodes") or []), spec.get("edges") or []
    _cap(spec, len(nodes), 9, "nodes", _open_budget(spec, opt["unbounded"]))
    people = [n for n in nodes if str(n.get("kind") or "") == "person"]
    systems = [n for n in nodes if n not in people]
    if not systems:
        systems, people = people, []
    hh = _hh(opt["title"], opt["sub"])
    W, H = 760, max(420, hh + 80 + max(len(people), len(systems), 1) * 80)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    parts.append(markers(opt["t"]))
    t = opt["t"]
    pos = {}
    for i, n in enumerate(people):
        pos[n["id"]] = (150, hh + 70 + i * 78, n)
    for i, n in enumerate(systems):
        pos[n["id"]] = (480, hh + 70 + i * 84, n)
    foc = _focals(nodes)
    for e in edges:
        if e.get("from") not in pos or e.get("to") not in pos:
            continue
        x1, y1, _ = pos[e["from"]]
        x2, y2, _ = pos[e["to"]]
        parts.append(
            f'<line x1="{x1 + 28:.1f}" y1="{y1:.1f}" x2="{x2 - 80:.1f}" y2="{y2:.1f}" stroke="{t["muted"]}" stroke-width="1.4" marker-end="url(#a)"/>')
        if e.get("label"):
            parts.append(arrow_label(t, (x1 + x2) / 2, (y1 + y2) / 2, str(e["label"]).upper()))
    for n in people:
        x, y, _ = pos[n["id"]]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="26" fill="{t["card"]}" stroke="{t["ink"]}" stroke-width="1.3"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n["name"], 10))}</text>')
    for n in systems:
        x, y, _ = pos[n["id"]]
        focal = n["id"] in foc
        _paint_one = focal
        sw = "1.6" if focal else "1.2"
        fill = t["accent_tint"] if focal else t["card"]
        stroke = t["accent"] if focal else t["ink"]
        parts.append(
            f'<rect x="{x - 80:.1f}" y="{y - 28:.1f}" width="160" height="56" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="13" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n["name"], 18))}</text>')
    return _done(parts, opt, W, H, len(nodes))


def _c_uml(spec, rows, opt):
    spec = _json(spec)
    nodes, edges = _with_ids(spec.get("nodes") or []), spec.get("edges") or []
    _cap(spec, len(nodes), 7, "classes", _open_budget(spec, opt["unbounded"]))
    rev = [{"from": e.get("to"), "to": e.get("from")} for e in edges]
    rank = _layers_of(nodes, rev)
    from collections import defaultdict
    rows_l = defaultdict(list)
    for n in nodes:
        rows_l[rank.get(n["id"], 0)].append(n)
    hh = _hh(opt["title"], opt["sub"])
    widest = max((len(v) for v in rows_l.values()), default=1)
    W = max(760, 240 * (widest + 1))
    def box_h(n):
        return 36 + 14 * min(6, len(n.get("attrs") or [])) + 14 * min(6, len(n.get("methods") or [])) + 12
    y = hh + 30
    pos = {}
    for key in sorted(rows_l):
        row = rows_l[key]
        h = max(box_h(n) for n in row)
        for j, n in enumerate(row):
            x = W * (j + 1) / (len(row) + 1)
            pos[n["id"]] = (x, y, h, n)
        y += h + 48
    H = int(y + 40)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    parts.append(markers(opt["t"]))
    t = opt["t"]
    for e in edges:
        if e.get("from") not in pos or e.get("to") not in pos:
            continue
        x1, y1, h1, _ = pos[e["from"]]
        x2, y2, h2, _ = pos[e["to"]]
        inherit = str(e.get("kind") or "") == "inherit"
        head = "none" if inherit else "url(#a)"
        parts.append(
            f'<path d="M {x1:.1f} {y1:.1f} V {(y1 + y2) / 2:.1f} H {x2:.1f} V {y2 + h2:.1f}" fill="none" stroke="{t["muted"]}" stroke-width="1.3" marker-end="{head}"/>')
        if inherit:
            parts.append(
                f'<polygon points="{x2:.1f},{y2 + h2:.1f} {x2 - 7:.1f},{y2 + h2 + 12:.1f} {x2 + 7:.1f},{y2 + h2 + 12:.1f}" fill="{t["paper"]}" stroke="{t["ink"]}"/>')
    for nid, (x, y0, h, n) in pos.items():
        w = 180
        parts.append(f'<rect x="{x - w / 2:.1f}" y="{y0:.1f}" width="{w}" height="{h}" fill="{t["card"]}" stroke="{t["ink"]}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y0 + 18:.1f}" font-size="13" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n.get("name") or nid, 20))}</text>')
        parts.append(f'<line x1="{x - w / 2:.1f}" y1="{y0 + 28:.1f}" x2="{x + w / 2:.1f}" y2="{y0 + 28:.1f}" stroke="{t["rule"]}"/>')
        yy = y0 + 44
        for attr in (n.get("attrs") or [])[:6]:
            parts.append(
                f'<text x="{x - w / 2 + 8:.1f}" y="{yy:.1f}" font-size="11" font-family="{FONT}" fill="{t["muted"]}">{esc(_short(attr, 22))}</text>')
            yy += 14
        parts.append(f'<line x1="{x - w / 2:.1f}" y1="{yy - 6:.1f}" x2="{x + w / 2:.1f}" y2="{yy - 6:.1f}" stroke="{t["rule"]}"/>')
        for method in (n.get("methods") or [])[:6]:
            parts.append(
                f'<text x="{x - w / 2 + 8:.1f}" y="{yy + 8:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(method, 22))}</text>')
            yy += 14
    return _done(parts, opt, W, H, len(nodes))


def _c_deploy(spec, rows, opt):
    spec = _json(spec)
    zones = spec.get("zones") or []
    _cap(spec, len(zones), 3, "zones", _open_budget(spec, opt["unbounded"]))
    if not zones:
        raise SpecError("deploy needs zones")
    tall = max(len(z.get("nodes") or []) for z in zones)
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(220, 70 + tall * 64), ox=28, right=28, bottom=40)
    zw = pw / len(zones)
    for i, zone in enumerate(zones):
        x = ox + i * zw
        parts.append(
            f'<rect x="{x + 6:.1f}" y="{oy:.1f}" width="{zw - 12:.1f}" height="{ph:.1f}" rx="4" fill="{t["card"]}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{x + 16:.1f}" y="{oy + 20:.1f}" font-size="13" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(zone.get("name") or zone.get("id") or "zone", 18))}</text>')
        for j, node in enumerate((zone.get("nodes") or [])[:8]):
            parts.append(
                f'<rect x="{x + 18:.1f}" y="{oy + 36 + j * 58:.1f}" width="{zw - 40:.1f}" height="46" rx="2" fill="{t["paper"]}" stroke="{t["ink"]}"/>')
            parts.append(
                f'<text x="{x + zw / 2:.1f}" y="{oy + 64 + j * 58:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(node.get("name") or node.get("id"), 16))}</text>')
    return _done(parts, opt, W, H, len(zones))


def _c_layers(spec, rows, opt):
    spec = _json(spec)
    layers = spec.get("layers") or []
    _cap(spec, len(layers), 8, "layers", _open_budget(spec, opt["unbounded"]))
    if not layers:
        raise SpecError("layers needs a layers list")
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(200, len(layers) * 58), ox=28, right=28, bottom=36)
    band = ph / len(layers)
    for i, layer in enumerate(layers):
        y = oy + i * band
        parts.append(
            f'<rect x="{ox:.1f}" y="{y + 4:.1f}" width="{pw:.1f}" height="{band - 8:.1f}" fill="{t["card"]}" stroke="{t["ink"]}"/>')
        parts.append(
            f'<text x="{ox + 16:.1f}" y="{y + band / 2 + 4:.1f}" font-size="14" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(layer.get("name") or "", 24))}</text>')
        if layer.get("sub"):
            parts.append(
                f'<text x="{ox + pw - 16:.1f}" y="{y + band / 2 + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{esc(_short(layer["sub"], 28))}</text>')
    return _done(parts, opt, W, H, len(layers))


def _c_integration(spec, rows, opt):
    spec = _json(spec)
    nodes, edges = _with_ids(spec.get("nodes") or []), spec.get("edges") or []
    _cap(spec, len(nodes), 9, "nodes", _open_budget(spec, opt["unbounded"]))
    cols = {"source": [], "core": [], "consumer": []}
    for n in nodes:
        key = str(n.get("col") or "core")
        cols[key if key in cols else "core"].append(n)
    hh = _hh(opt["title"], opt["sub"])
    tall = max(len(v) for v in cols.values())
    W, H = 820, int(hh + 80 + max(tall, 1) * 90)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    parts.append(markers(opt["t"]))
    t = opt["t"]
    xs = {"source": 170, "core": 410, "consumer": 650}
    pos = {}
    for key, group in cols.items():
        for i, n in enumerate(group):
            pos[n["id"]] = (xs[key], hh + 70 + i * 90, n)
    _paint_boxes(parts, t, pos, _focals(nodes))
    _draw_links(parts, t, pos, edges)
    for key, x in xs.items():
        parts.append(
            f'<text x="{x:.1f}" y="{hh + 28:.1f}" font-size="11" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{key}</text>')
    return _done(parts, opt, W, H, len(nodes))


def _c_current(spec, rows, opt):
    spec = _json(spec)
    nodes = _with_ids(spec.get("nodes") or [])
    _cap(spec, len(nodes), 18, "nodes", _open_budget(spec, opt["unbounded"]))
    groups = _ordered(str(n.get("group") or "Other") for n in nodes)
    hh = _hh(opt["title"], opt["sub"])
    tall = max(sum(1 for n in nodes if str(n.get("group") or "Other") == g) for g in groups) if groups else 1
    W = max(760, 200 * max(len(groups), 1) + 40)
    H = int(hh + 70 + tall * 70)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    t = opt["t"]
    for i, g in enumerate(groups):
        x = 30 + i * (W - 50) / max(len(groups), 1)
        colw = (W - 50) / max(len(groups), 1)
        parts.append(
            f'<text x="{x + 12:.1f}" y="{hh + 28:.1f}" font-size="12" font-family="{FONT}" fill="{t["muted"]}">{esc(_short(g, 18))}</text>')
        j = 0
        for n in nodes:
            if str(n.get("group") or "Other") != g:
                continue
            parts.append(
                f'<rect x="{x + 8:.1f}" y="{hh + 42 + j * 64:.1f}" width="{colw - 24:.1f}" height="50" rx="2" fill="{t["card"]}" stroke="{t["ink"]}"/>')
            parts.append(
                f'<text x="{x + colw / 2:.1f}" y="{hh + 72 + j * 64:.1f}" font-size="13" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n["name"], 16))}</text>')
            j += 1
    return _done(parts, opt, W, H, len(nodes))


def _many_card(card):
    return str(card or "1").strip().lower() in ("*", "n", "m", "many", "*") or str(card or "").endswith("*") or str(card or "").endswith("n")


def _crow(parts, t, x1, y1, x2, y2, many):
    import math
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    ex, ey = x2 - ux * 8, y2 - uy * 8
    sx, sy = ex - ux * 16, ey - uy * 16
    parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{sx:.1f}" y2="{sy:.1f}" stroke="{t["muted"]}" stroke-width="1.3"/>')
    if many:
        for s in (-1, 0, 1):
            parts.append(
                f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex + px * s * 7:.1f}" y2="{ey + py * s * 7:.1f}" stroke="{t["ink"]}" stroke-width="1.2"/>')
    else:
        parts.append(
            f'<line x1="{ex - px * 7:.1f}" y1="{ey - py * 7:.1f}" x2="{ex + px * 7:.1f}" y2="{ey + py * 7:.1f}" stroke="{t["ink"]}" stroke-width="1.4"/>')


def _c_er(spec, rows, opt):
    spec = _json(spec)
    ents = spec.get("entities") or []
    rels = spec.get("relations") or []
    _cap(spec, len(ents), 8, "entities", _open_budget(spec, opt["unbounded"]))
    if not ents:
        raise SpecError("er needs entities")
    cols = 2 if len(ents) > 3 else len(ents)
    rows_n = (len(ents) + cols - 1) // cols
    hh = _hh(opt["title"], opt["sub"])
    W = max(760, cols * 340)
    box_h = 120
    H = int(hh + 40 + rows_n * (box_h + 36))
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    t = opt["t"]
    pos = {}
    for i, ent in enumerate(ents):
        c, r = i % cols, i // cols
        x = W * (c + 1) / (cols + 1)
        y = hh + 36 + r * (box_h + 36)
        pos[ent.get("id") or ent.get("name")] = (x, y, ent)
    for rel in rels:
        if rel.get("from") not in pos or rel.get("to") not in pos:
            continue
        x1, y1, _ = pos[rel["from"]]
        x2, y2, _ = pos[rel["to"]]
        _crow(parts, t, x1 + 90, y1 + 28, x2 - 90, y2 + 28, _many_card(rel.get("to_card")))
        _crow(parts, t, x2 - 90, y2 + 40, x1 + 90, y1 + 40, _many_card(rel.get("from_card")))
    for eid, (x, y, ent) in pos.items():
        attrs = ent.get("attrs") or []
        h = 36 + 16 * min(6, len(attrs))
        parts.append(f'<rect x="{x - 90:.1f}" y="{y:.1f}" width="180" height="{h}" fill="{t["card"]}" stroke="{t["ink"]}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 18:.1f}" font-size="13" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(ent.get("name") or eid, 18))}</text>')
        for i, attr in enumerate(attrs[:6]):
            mark = "pk" if str(attr.get("key") or "").lower() == "pk" else ""
            parts.append(
                f'<text x="{x - 80:.1f}" y="{y + 38 + i * 16:.1f}" font-size="11" font-family="{FONT}" fill="{t["muted"]}">{esc(_short(attr.get("name") or "", 16))}</text>')
            if mark:
                parts.append(
                    f'<text x="{x + 70:.1f}" y="{y + 38 + i * 16:.1f}" font-size="10" font-family="{FONT}" fill="{t["accent"]}" text-anchor="end">pk</text>')
    return _done(parts, opt, W, H, len(ents))


def _c_wardley(spec, rows, opt):
    spec = _json(spec)
    nodes, edges = _with_ids(spec.get("nodes") or []), spec.get("edges") or []
    _cap(spec, len(nodes), 12, "components", _open_budget(spec, opt["unbounded"]))
    if not nodes:
        raise SpecError("wardley needs nodes with visibility and evolution")
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 360, ox=70, bottom=64)
    parts.append(f'<rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" fill="{t["card"]}" stroke="{t["rule"]}"/>')
    for frac, lab in ((0.25, "Custom"), (0.5, "Product"), (0.75, "")):
        x = ox + frac * pw
        parts.append(f'<line x1="{x:.1f}" y1="{oy}" x2="{x:.1f}" y2="{oy + ph}" stroke="{t["rule"]}"/>')
    for frac, lab in ((0.125, "Genesis"), (0.375, "Custom"), (0.625, "Product"), (0.875, "Commodity")):
        parts.append(
            f'<text x="{ox + frac * pw:.1f}" y="{oy + ph + 18:.1f}" font-size="11" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{lab}</text>')
    parts.append(
        f'<text x="{ox - 8}" y="{oy + 12:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">visible</text>')

    def px(n):
        evo = min(1.0, max(0.0, float(n.get("evolution") or 0)))
        vis = min(1.0, max(0.0, float(n.get("visibility") or 0)))
        return ox + evo * pw, oy + (1 - vis) * ph

    by = {n["id"]: n for n in nodes}
    for e in edges:
        if e.get("from") in by and e.get("to") in by:
            x1, y1 = px(by[e["from"]])
            x2, y2 = px(by[e["to"]])
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{t["muted"]}" stroke-width="1.2"/>')
    for n in nodes:
        x, y = px(n)
        hit = _hit(opt["highlights"], n["name"]) or n.get("focal")
        parts.append(
            f'<rect x="{x - 46:.1f}" y="{y - 14:.1f}" width="92" height="28" rx="2" fill="{t["accent_tint"] if hit else t["paper"]}" stroke="{t["accent"] if hit else t["ink"]}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n["name"], 14))}</text>')
    return _done(parts, opt, W, H, len(nodes))


def _c_swim(spec, rows, opt):
    spec = _json(spec)
    lanes = spec.get("lanes") or []
    nodes = _with_ids(spec.get("nodes") or [])
    edges = spec.get("edges") or []
    _cap(spec, len(nodes), 12, "nodes", _open_budget(spec, opt["unbounded"]))
    if not lanes:
        raise SpecError("swim needs lanes")
    hh = _hh(opt["title"], opt["sub"])
    lane_h = 110
    W, H = 860, int(hh + 36 + len(lanes) * lane_h + 40)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    parts.append(markers(opt["t"]))
    t = opt["t"]
    lane_y = {}
    for i, lane in enumerate(lanes):
        y = hh + 24 + i * lane_h
        lane_y[lane.get("id")] = y
        parts.append(f'<rect x="120" y="{y:.1f}" width="700" height="{lane_h - 8}" fill="{t["card"]}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="16" y="{y + lane_h / 2:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(lane.get("name") or "", 12))}</text>')
    buckets = {}
    for n in nodes:
        buckets.setdefault(n.get("lane"), []).append(n)
    pos = {}
    for lane_id, group in buckets.items():
        y = lane_y.get(lane_id, hh + 24) + lane_h / 2
        for i, n in enumerate(group):
            x = 200 + i * 180
            pos[n["id"]] = (x, y, n)
    _paint_boxes(parts, t, pos, _focals(nodes), w=140, h=48)
    _draw_links(parts, t, pos, edges)
    return _done(parts, opt, W, H, len(nodes))


def _c_state(spec, rows, opt):
    import math
    spec = _json(spec)
    nodes, edges = _with_ids(spec.get("nodes") or []), spec.get("edges") or []
    _cap(spec, len(nodes), 8, "states", _open_budget(spec, opt["unbounded"]))
    if not nodes:
        raise SpecError("state needs nodes")
    hh = _hh(opt["title"], opt["sub"])
    W = max(760, 140 + len(nodes) * 140)
    H = hh + 280
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    parts.append(markers(opt["t"]))
    t = opt["t"]
    idx = {n["id"]: i for i, n in enumerate(nodes)}
    pos = {n["id"]: (120 + i * (W - 180) / max(len(nodes) - 1, 1), hh + 150) for i, n in enumerate(nodes)}
    for e in edges:
        if e.get("from") not in pos or e.get("to") not in pos:
            continue
        x1, y1 = pos[e["from"]]
        x2, y2 = pos[e["to"]]
        back = idx[e["to"]] <= idx[e["from"]]
        if back:
            mx, my = (x1 + x2) / 2, y1 - 70
            parts.append(
                f'<path d="M {x1:.1f} {y1 - 22:.1f} Q {mx:.1f} {my:.1f} {x2:.1f} {y2 - 22:.1f}" fill="none" stroke="{t["muted"]}" stroke-width="1.4" marker-end="url(#a)"/>')
            lx, ly = mx, my
        else:
            parts.append(
                f'<line x1="{x1 + 24:.1f}" y1="{y1:.1f}" x2="{x2 - 28:.1f}" y2="{y2:.1f}" stroke="{t["muted"]}" stroke-width="1.4" marker-end="url(#a)"/>')
            lx, ly = (x1 + x2) / 2, y1 - 10
        if e.get("label"):
            parts.append(
                f'<text x="{lx:.1f}" y="{ly - 6:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(e["label"], 16))}</text>')
    for n in nodes:
        x, y = pos[n["id"]]
        hit = n["id"] in _focals(nodes)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="26" fill="{t["accent_tint"] if hit else t["card"]}" stroke="{t["accent"] if hit else t["ink"]}" stroke-width="1.4"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 46:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n["name"], 16))}</text>')
    return _done(parts, opt, W, H, len(nodes))


def _c_bpmn(spec, rows, opt):
    spec = _json(spec)
    nodes, edges = _with_ids(spec.get("nodes") or []), spec.get("edges") or []
    _cap(spec, len(nodes), 12, "nodes", _open_budget(spec, opt["unbounded"]))
    if not nodes:
        raise SpecError("bpmn needs nodes")
    rank = _layers_of(nodes, edges)
    from collections import defaultdict
    layers = defaultdict(list)
    for n in nodes:
        layers[rank.get(n["id"], 0)].append(n)
    hh = _hh(opt["title"], opt["sub"])
    widest = max(len(v) for v in layers.values())
    W = max(760, 200 * (widest + 1))
    gap = 120
    H = int(hh + 50 + max(rank.values()) * gap + 100)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    parts.append(markers(opt["t"]))
    t = opt["t"]
    pos = {}
    for key in sorted(layers):
        row = layers[key]
        for j, n in enumerate(row):
            pos[n["id"]] = (W * (j + 1) / (len(row) + 1), hh + 60 + key * gap, n)
    for e in edges:
        if e.get("from") not in pos or e.get("to") not in pos:
            continue
        x1, y1, _ = pos[e["from"]]
        x2, y2, _ = pos[e["to"]]
        if abs(y1 - y2) < 8:
            parts.append(
                f'<line x1="{x1 + 36:.1f}" y1="{y1:.1f}" x2="{x2 - 40:.1f}" y2="{y2:.1f}" stroke="{t["muted"]}" stroke-width="1.4" marker-end="url(#a)"/>')
            lx, ly = (x1 + x2) / 2, y1
        else:
            mid = (y1 + y2) / 2
            parts.append(
                f'<path d="M {x1:.1f} {y1 + 28:.1f} V {mid:.1f} H {x2:.1f} V {y2 - 32:.1f}" fill="none" stroke="{t["muted"]}" stroke-width="1.4" marker-end="url(#a)"/>')
            lx, ly = (x1 + x2) / 2, mid
        if e.get("label"):
            parts.append(
                f'<text x="{lx:.1f}" y="{ly - 6:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(e["label"], 14))}</text>')
    for n in nodes:
        x, y, _ = pos[n["id"]]
        shape = str(n.get("shape") or "task")
        if shape == "event":
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="22" fill="{t["card"]}" stroke="{t["ink"]}" stroke-width="1.3"/>')
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" fill="none" stroke="{t["ink"]}" stroke-width="1"/>')
        elif shape == "gateway":
            parts.append(
                f'<polygon points="{x:.1f},{y - 24:.1f} {x + 28:.1f},{y:.1f} {x:.1f},{y + 24:.1f} {x - 28:.1f},{y:.1f}" fill="{t["card"]}" stroke="{t["ink"]}"/>')
        else:
            parts.append(
                f'<rect x="{x - 54:.1f}" y="{y - 22:.1f}" width="108" height="44" rx="8" fill="{t["card"]}" stroke="{t["ink"]}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n["name"], 12))}</text>')
    return _done(parts, opt, W, H, len(nodes))


def _c_fishbone(spec, rows, opt):
    spec = _json(spec)
    ribs = spec.get("ribs") or []
    _cap(spec, len(ribs), 6, "ribs", _open_budget(spec, opt["unbounded"]))
    if not ribs:
        raise SpecError("fishbone needs ribs")
    problem = spec.get("problem") or opt["title"] or "Problem"
    W, H = 860, 460
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    t = opt["t"]
    y = 250
    parts.append(f'<line x1="70" y1="{y}" x2="690" y2="{y}" stroke="{t["ink"]}" stroke-width="1.6"/>')
    parts.append(f'<rect x="690" y="{y - 22}" width="140" height="44" rx="2" fill="{t["accent_tint"]}" stroke="{t["accent"]}"/>')
    parts.append(
        f'<text x="760" y="{y + 4}" font-size="13" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(problem, 16))}</text>')
    for i, rib in enumerate(ribs[:6]):
        x = 120 + i * 90
        up = i % 2 == 0
        x2, y2 = x + 80, 120 if up else 380
        parts.append(f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" stroke="{t["muted"]}" stroke-width="1.3"/>')
        parts.append(
            f'<text x="{x2 + 4}" y="{y2 + (-6 if up else 12)}" font-size="12" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(rib.get("name") or "", 14))}</text>')
        causes = rib.get("causes") or []
        for j, cause in enumerate(causes[:4]):
            u = (j + 1) / (min(len(causes), 4) + 1)
            cx, cy = x + (x2 - x) * u, y + (y2 - y) * u
            tick = 42
            parts.append(
                f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx + tick:.1f}" y2="{cy:.1f}" stroke="{t["muted"]}" stroke-width="1.1"/>')
            parts.append(
                f'<text x="{cx + tick + 6:.1f}" y="{cy + 4:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(cause, 16))}</text>')
    return _done(parts, opt, W, H, len(ribs))


def _c_flywheel(spec, rows, opt):
    import math
    spec = _json(spec)
    nodes = spec.get("nodes") or []
    _cap(spec, len(nodes), 8, "steps", _open_budget(spec, opt["unbounded"]))
    if len(nodes) < 2:
        raise SpecError("flywheel needs at least two nodes")
    hh = _hh(opt["title"], opt["sub"])
    W, H = 760, hh + 460
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    parts.append(markers(opt["t"]))
    t = opt["t"]
    cx, cy, rad = W / 2, hh + 230, 150
    pts = []
    for i, n in enumerate(nodes):
        ang = -math.pi / 2 + math.tau * i / len(nodes)
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang), ang, n))
    for i, (x, y, ang, n) in enumerate(pts):
        x2, y2, ang2, _ = pts[(i + 1) % len(pts)]
        parts.append(
            f'<path d="M {x:.1f} {y:.1f} A {rad:.1f} {rad:.1f} 0 0 1 {x2:.1f} {y2:.1f}" fill="none" stroke="{t["link"]}" stroke-width="1.6" marker-end="url(#a)"/>')
    for x, y, ang, n in pts:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="28" fill="{t["card"]}" stroke="{t["ink"]}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(n.get("name") or "", 10))}</text>')
    hub = spec.get("hub") or ""
    if hub:
        parts.append(
            f'<text x="{cx:.1f}" y="{cy + 4:.1f}" font-size="16" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(hub, 16))}</text>')
    return _done(parts, opt, W, H, len(nodes))


def _c_kanban(spec, rows, opt):
    spec = _json(spec)
    cols = spec.get("columns") or []
    if not cols:
        raise SpecError("kanban needs columns")
    _cap(spec, len(cols), 6, "columns", _open_budget(spec, opt["unbounded"]))
    tall = max(len(c.get("cards") or []) for c in cols)
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(220, 40 + tall * 58), ox=24, right=24, bottom=36)
    cw = pw / len(cols)
    for i, col in enumerate(cols):
        x = ox + i * cw
        parts.append(
            f'<text x="{x + 12:.1f}" y="{oy + 16:.1f}" font-size="13" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(col.get("name") or "", 16))}</text>')
        for j, card in enumerate(col.get("cards") or []):
            blocked = bool(card.get("blocked"))
            stroke = t["accent"] if blocked else t["ink"]
            sw = "1.6" if blocked else "1.1"
            parts.append(
                f'<rect x="{x + 8:.1f}" y="{oy + 28 + j * 56:.1f}" width="{cw - 20:.1f}" height="46" rx="2" fill="{t["card"]}" stroke="{stroke}" stroke-width="{sw}"/>')
            parts.append(
                f'<text x="{x + cw / 2:.1f}" y="{oy + 56 + j * 56:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(card.get("name") or "", 18))}</text>')
    return _done(parts, opt, W, H, len(cols))


def _c_gantt(spec, rows, opt):
    spec = _json(spec)
    tasks = spec.get("tasks") or []
    if not tasks:
        raise SpecError("gantt needs tasks")
    _cap(spec, len(tasks), 16, "tasks", _open_budget(spec, opt["unbounded"]))
    parsed = []
    dated = False
    for task in tasks:
        a, d1 = _when(task.get("start"))
        b, d2 = _when(task.get("end"))
        dated = dated or d1 or d2
        parsed.append((str(task.get("name") or ""), a, b))
    lo, hi = min(a for _, a, _ in parsed), max(b for _, _, b in parsed)
    if lo == hi:
        hi = lo + 1
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, max(200, len(parsed) * 32), ox=140)
    xt = nice_ticks(lo, hi)
    span = (xt[-1] - xt[0]) or 1

    def X(v):
        return ox + (v - xt[0]) / span * pw

    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    import datetime
    for v in xt:
        x = X(v)
        if opt["grid"]:
            parts.append(f'<line x1="{x:.1f}" y1="{oy}" x2="{x:.1f}" y2="{oy + ph}" stroke="{t["rule"]}"/>')
        label = datetime.date.fromordinal(int(v)).isoformat() if dated else fmt_tick(v)
        parts.append(
            f'<text x="{x:.1f}" y="{oy + ph + 16}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{esc(label)}</text>')
    for i, (name, a, b) in enumerate(parsed):
        y = oy + (i + 0.5) * ph / len(parsed)
        hit = _hit(opt["highlights"], name)
        parts.append(
            f'<rect x="{X(min(a, b)):.1f}" y="{y - 8:.1f}" width="{max(2, abs(X(b) - X(a))):.1f}" height="16" rx="2" fill="{t["accent"] if hit else t["link"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(_short(name, 18))}</text>')
    return _done(parts, opt, W, H, len(parsed))


def _c_timeline(spec, rows, opt):
    spec = _json(spec)
    events = spec.get("events") or []
    if not events:
        raise SpecError("timeline needs events")
    _cap(spec, len(events), 12, "events", _open_budget(spec, opt["unbounded"]))
    parsed = []
    for ev in events:
        d = _parse_date(ev.get("at"))
        parsed.append((str(ev.get("name") or ""), d, str(ev.get("at") or "")))
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 220, ox=50, right=40)
    y = oy + ph / 2
    parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["ink"]}" stroke-width="1.3"/>')
    n = len(parsed)
    for i, (name, d, raw) in enumerate(parsed):
        x = ox + (i + 0.5) * pw / n
        up = i % 2 == 0
        y2 = y - 36 if up else y + 36
        parts.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y2:.1f}" stroke="{t["muted"]}"/>')
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{t["link"]}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y2 + (-8 if up else 16):.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(name, 16))}</text>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + (18 if up else -10):.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{esc(_short(raw, 12))}</text>')
    return _done(parts, opt, W, H, n)


def _c_journey(spec, rows, opt):
    spec = _json(spec)
    stages = spec.get("stages") or []
    if not stages:
        raise SpecError("journey needs stages")
    _cap(spec, len(stages), 8, "stages", _open_budget(spec, opt["unbounded"]))
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 260, ox=50, right=40, bottom=64)
    scores = [max(0, min(5, float(s.get("score") or 0))) for s in stages]

    def Y(v):
        return oy + ph - v / 5 * ph

    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}"/>')
    for v in range(6):
        y = Y(v)
        if opt["grid"]:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{v}</text>')
    xs = [ox + (i + 0.5) * pw / len(stages) for i in range(len(stages))]
    d = " ".join(f'{"M" if i == 0 else "L"} {xs[i]:.1f} {Y(scores[i]):.1f}' for i in range(len(stages)))
    parts.append(f'<path d="{d}" fill="none" stroke="{t["link"]}" stroke-width="1.8"/>')
    for i, stage in enumerate(stages):
        _dot(parts, t, xs[i], Y(scores[i]), 5, t["link"], True, _hit(opt["highlights"], stage.get("name")))
        parts.append(
            f'<text x="{xs[i]:.1f}" y="{oy + ph + 18:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(stage.get("name") or "", 12))}</text>')
        if stage.get("note"):
            parts.append(
                f'<text x="{xs[i]:.1f}" y="{oy + ph + 34:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{esc(_short(stage["note"], 16))}</text>')
    return _done(parts, opt, W, H, len(stages), "score 0 to 5")


def _c_story(spec, rows, opt):
    spec = _json(spec)
    backbone = spec.get("backbone") or []
    releases = spec.get("releases") or []
    if not backbone and not releases:
        raise SpecError("story needs a backbone or releases")
    hh = _hh(opt["title"], opt["sub"])
    W = max(760, 80 + max(len(backbone), 1) * 140)
    H = int(hh + 80 + max(len(releases), 1) * 70 + 40)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    t = opt["t"]
    for i, name in enumerate(backbone):
        x = 40 + i * 140
        parts.append(f'<rect x="{x:.1f}" y="{hh + 16:.1f}" width="120" height="36" rx="2" fill="{t["ink"]}"/>')
        parts.append(
            f'<text x="{x + 60:.1f}" y="{hh + 39:.1f}" font-size="12" font-family="{FONT}" fill="{t["paper"]}" text-anchor="middle">{esc(_short(name, 14))}</text>')
        if i < len(backbone) - 1:
            parts.append(f'<line x1="{x + 120:.1f}" y1="{hh + 34:.1f}" x2="{x + 140:.1f}" y2="{hh + 34:.1f}" stroke="{t["muted"]}"/>')
    pal = series_palette(t)
    for i, rel in enumerate(releases):
        y = hh + 80 + i * 64
        col = pal[i % len(pal)]
        parts.append(
            f'<text x="36" y="{y + 18:.1f}" font-size="12" font-family="{FONT}" fill="{t["ink"]}">{esc(_short(rel.get("name") or "", 10))}</text>')
        for j, story in enumerate(rel.get("stories") or []):
            x = 120 + j * 130
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="116" height="32" rx="2" fill="{col}" fill-opacity="0.85"/>')
            parts.append(
                f'<text x="{x + 58:.1f}" y="{y + 21:.1f}" font-size="11" font-family="{FONT}" fill="{t["card"]}" text-anchor="middle">{esc(_short(story, 14))}</text>')
    return _done(parts, opt, W, H, len(backbone) + len(releases))


def _c_venn(spec, rows, opt):
    spec = _json(spec)
    sets = spec.get("sets") or []
    if len(sets) not in (2, 3):
        raise SpecError("venn needs 2 or 3 sets")
    overlap = spec.get("overlap")
    hh = _hh(opt["title"], opt["sub"])
    W, H = 760, hh + 420
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    t = opt["t"]
    pal = series_palette(t)
    cy = hh + 210
    if len(sets) == 2:
        centers = [(300, cy), (460, cy)]
        r = 120
    else:
        centers = [(380, cy - 50), (300, cy + 70), (460, cy + 70)]
        r = 110
    for i, (x, y) in enumerate(centers):
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{pal[i % len(pal)]}" fill-opacity="0.28" stroke="{pal[i % len(pal)]}" stroke-width="1.6"/>')
        parts.append(
            f'<text x="{x}" y="{y + (4 if len(sets) == 3 and i == 0 else -r + 28 if i == 0 or len(sets) == 2 else 8)}" font-size="14" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(sets[i].get("name") or "", 12))}</text>')
        if sets[i].get("size") is not None and opt["markers"]:
            parts.append(
                f'<text x="{x}" y="{y + 22:.1f}" font-size="12" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{esc(sets[i]["size"])}</text>')
    if len(sets) == 2 and overlap is not None:
        parts.append(
            f'<text x="380" y="{cy + 4}" font-size="14" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(overlap)}</text>')
    elif isinstance(overlap, dict):
        spots = {"ab": (340, cy + 10), "ac": (420, cy + 10), "bc": (380, cy + 78), "abc": (380, cy + 36)}
        for key, (x, y) in spots.items():
            if overlap.get(key) is not None:
                parts.append(
                    f'<text x="{x}" y="{y}" font-size="13" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(overlap[key])}</text>')
    return _done(parts, opt, W, H, len(sets))


def _polys_from(spec, opt):
    feats = []
    if isinstance(spec, dict):
        feats = spec.get("features") or ([] if spec.get("type") != "Feature" else [spec])
    key = opt.get("val") or "value"
    polys, samples = [], []
    for feat in feats:
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        try:
            val = float(props.get(key if key in props else "value") or 0)
        except (TypeError, ValueError):
            val = 0
        rings = []
        if geom.get("type") == "Polygon":
            rings = geom.get("coordinates") or []
        elif geom.get("type") == "MultiPolygon":
            rings = [p[0] for p in geom.get("coordinates") or [] if p]
        for ring in rings[:1] if geom.get("type") == "MultiPolygon" else rings[:1]:
            pts = [(c[0], c[1]) for c in ring if isinstance(c, (list, tuple)) and len(c) >= 2]
            if len(pts) >= 3:
                polys.append((pts, val, str(props.get("name") or "")))
                samples.extend(pts)
    if not samples:
        raise SpecError("choropleth needs GeoJSON polygons")
    return polys, samples


def _c_choropleth(spec, rows, opt):
    spec = _json(spec)
    polys, samples = _polys_from(spec, opt)
    _cap(spec, len(polys), 80, "polygons", _open_budget(spec, opt["unbounded"]))
    ctx = _map_stage(opt["t"], opt["title"], opt["sub"], samples)
    vals = [v for _, v, _ in polys]
    lo, hi = min(vals), max(vals)
    proj = ctx["proj"]
    for pts, val, name in polys:
        clipped = _clip_poly(pts, ctx["minlon"], ctx["minlat"], ctx["maxlon"], ctx["maxlat"])
        if len(clipped) < 3:
            continue
        u = 0.5 if hi == lo else (val - lo) / (hi - lo)
        seq = []
        for lon, lat in clipped:
            x, y = proj(lon, lat)
            seq.append(f"{x:.1f},{y:.1f}")
        ctx["parts"].append(
            f'<polygon points="{" ".join(seq)}" fill="{_heat_color(opt["t"], u)}" fill-opacity="0.82" stroke="{opt["t"]["ink"]}" stroke-width="0.6"/>')
        if name and len(polys) <= 12 and opt["markers"]:
            xs = [proj(p[0], p[1])[0] for p in pts]
            ys = [proj(p[0], p[1])[1] for p in pts]
            ctx["parts"].append(
                f'<text x="{sum(xs) / len(xs):.1f}" y="{sum(ys) / len(ys):.1f}" font-size="11" font-family="{FONT}" fill="{opt["t"]["ink"]}" text-anchor="middle">{esc(_short(name, 14))}</text>')
    ctx["after"] = []
    _ramp(ctx["after"], opt["t"], ctx["ox"], ctx["oy"] + 420 + 6, 130, fmt_tick(lo), fmt_tick(hi))
    svg, W, H = _map_finish(ctx, _foot(opt, len(polys)))
    return svg, W, H, len(polys)


def _geo_rows(rows, opt, need_val=False):
    pairs = [("lat", opt["y"]), ("lon", opt["x"])]
    if need_val:
        pairs.append(("val", opt["val"]))
    return _need(rows, pairs)


def _c_heatgeo(spec, rows, opt):
    c = _geo_rows(rows, opt, True)
    pts = []
    for r in rows:
        try:
            lat, lon, val = _f(r, c["lat"]), _f(r, c["lon"]), _f(r, c["val"])
        except (TypeError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            pts.append((lon, lat, val))
    if not pts:
        raise SpecError("heatgeo needs lat, lon, and val")
    _cap(None, len(pts), 400, "points", opt["unbounded"])
    ctx = _map_stage(opt["t"], opt["title"], opt["sub"], [(p[0], p[1]) for p in pts])
    nx = ny = 14
    bins = [[[] for _ in range(nx)] for _ in range(ny)]
    minlon, maxlon = ctx["minlon"], ctx["maxlon"]
    minlat, maxlat = ctx["minlat"], ctx["maxlat"]
    for lon, lat, val in pts:
        i = min(nx - 1, max(0, int((lon - minlon) / ((maxlon - minlon) or 1) * nx)))
        j = min(ny - 1, max(0, int((lat - minlat) / ((maxlat - minlat) or 1) * ny)))
        bins[j][i].append(val)
    flat = [sum(cell) / len(cell) for row in bins for cell in row if cell]
    lo, hi = (min(flat), max(flat)) if flat else (0, 1)
    proj = ctx["proj"]
    for j in range(ny):
        for i in range(nx):
            if not bins[j][i]:
                continue
            v = sum(bins[j][i]) / len(bins[j][i])
            u = 0.5 if hi == lo else (v - lo) / (hi - lo)
            lon0 = minlon + (maxlon - minlon) * i / nx
            lon1 = minlon + (maxlon - minlon) * (i + 1) / nx
            lat0 = minlat + (maxlat - minlat) * j / ny
            lat1 = minlat + (maxlat - minlat) * (j + 1) / ny
            x0, y0 = proj(lon0, lat1)
            x1, y1 = proj(lon1, lat0)
            ctx["parts"].append(
                f'<rect x="{min(x0, x1):.1f}" y="{min(y0, y1):.1f}" width="{abs(x1 - x0):.1f}" height="{abs(y1 - y0):.1f}" fill="{_heat_color(opt["t"], u)}" fill-opacity="0.55"/>')
    ctx["after"] = []
    _ramp(ctx["after"], opt["t"], ctx["ox"], ctx["oy"] + 426, 130, fmt_tick(lo), fmt_tick(hi))
    svg, W, H = _map_finish(ctx, _foot(opt, len(pts)))
    return svg, W, H, len(pts)


def _c_od(spec, rows, opt):
    import math
    c = _need(rows, [("lon", opt["x"]), ("lat", opt["y"]), ("lon2", opt["a"]), ("lat2", opt["b"])])
    vc = _col(rows, opt["val"], "val")
    arcs = []
    samples = []
    for r in rows:
        try:
            lon, lat = _f(r, c["lon"]), _f(r, c["lat"])
            lon2, lat2 = _f(r, c["lon2"]), _f(r, c["lat2"])
            val = _f(r, vc) if vc else 1
        except (TypeError, ValueError):
            continue
        arcs.append((lon, lat, lon2, lat2, val))
        samples.append((lon, lat))
        samples.append((lon2, lat2))
    if not arcs:
        raise SpecError("od needs lon, lat, lon2, lat2")
    _cap(None, len(arcs), 40, "arcs", opt["unbounded"])
    ctx = _map_stage(opt["t"], opt["title"], opt["sub"], samples)
    ctx["parts"].append(markers(opt["t"]))
    proj = ctx["proj"]
    peak = max(a[4] for a in arcs) or 1
    for lon, lat, lon2, lat2, val in arcs:
        x1, y1 = proj(lon, lat)
        x2, y2 = proj(lon2, lat2)
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1
        mx, my = (x1 + x2) / 2 - dy / length * min(36, length * 0.2), (y1 + y2) / 2 + dx / length * min(36, length * 0.2)
        width = 1.2 + 4.5 * (val / peak)
        ctx["parts"].append(
            f'<path d="M {x1:.1f} {y1:.1f} Q {mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}" fill="none" stroke="{opt["t"]["accent"]}" stroke-width="{width:.1f}" stroke-opacity="0.8" marker-end="url(#aa)"/>')
    svg, W, H = _map_finish(ctx, _foot(opt, len(arcs)))
    return svg, W, H, len(arcs)


def _c_cluster(spec, rows, opt):
    import math
    c = _geo_rows(rows, opt, False)
    pts = []
    for r in rows:
        try:
            lat, lon = _f(r, c["lat"]), _f(r, c["lon"])
        except (TypeError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            pts.append((lon, lat))
    if not pts:
        raise SpecError("cluster needs lat and lon")
    _cap(None, len(pts), 400, "points", opt["unbounded"])
    ctx = _map_stage(opt["t"], opt["title"], opt["sub"], pts)
    span = max(ctx["maxlon"] - ctx["minlon"], ctx["maxlat"] - ctx["minlat"]) or 1
    cell = span / 10
    buckets = {}
    for lon, lat in pts:
        key = (round(lon / cell), round(lat / cell))
        buckets.setdefault(key, []).append((lon, lat))
    peak = max(len(v) for v in buckets.values())
    proj = ctx["proj"]
    ranked = sorted(buckets.values(), key=len, reverse=True)
    for group in buckets.values():
        lon = sum(p[0] for p in group) / len(group)
        lat = sum(p[1] for p in group) / len(group)
        x, y = proj(lon, lat)
        rad = 6 + 14 * math.sqrt(len(group) / peak)
        ctx["parts"].append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{opt["t"]["link"]}" fill-opacity="0.75" stroke="{opt["t"]["card"]}"/>')
        if opt["markers"] and group in ranked[:5]:
            ctx["parts"].append(
                f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="11" font-family="{FONT}" fill="{opt["t"]["card"]}" text-anchor="middle">{len(group)}</text>')
    svg, W, H = _map_finish(ctx, _foot(opt, len(pts), f"{len(buckets)} clusters"))
    return svg, W, H, len(pts)

"""What the `chart <kind>` renderers share: metadata, column roles, axes, legends, boxes."""
import csv, json
from .._draw import _tail, arrow_label, assign_ports, figure_heading, fmt_tick, markers, route_edge
from .._text import esc
from .._theme import FONT


def _load_input(path):
    if str(path).lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return json.load(f), []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return None, list(reader)


def _pick(rows, explicit, aliases):
    cols = list(rows[0].keys()) if rows else []
    if explicit:
        if explicit not in cols:
            raise SystemExit(f"column '{explicit}' not in {cols}")
        return explicit
    low = {c.lower(): c for c in cols}
    for alias in aliases:
        if alias in low:
            return low[alias]
    return None


def _f(row, col):
    return float(row[col])


def _cap(spec, n, cap, what, unbounded=False):
    if unbounded or (isinstance(spec, dict) and spec.get("budget") is False):
        return
    if n > cap:
        raise SystemExit(f"{n} {what} > {cap}. Split the figure, or set budget false.")


def _fig_open(t, title, sub, W, H):
    head, hh = figure_heading(t, title, sub, x=28)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}">'
        f'<title>{esc(title or "chart")}</title>',
        f'<desc>{esc(sub or title or "chart")}</desc>',
        f'<rect width="{W}" height="{H}" fill="{t["paper"]}"/>',
    ]
    parts.extend(head)
    return parts, hh


def _fig_close(parts, t, W, H, foot):
    parts.append(
        f'<text x="28" y="{H - 16}" font-size="11" font-family="{FONT}" fill="{t["muted"]}">{esc(foot)}</text>')
    parts.append("</svg>")
    return "\n".join(parts), W, H


def _mix(h1, h2, u):
    u = max(0.0, min(1.0, u))

    def p(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    a, b = p(h1), p(h2)
    c = tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*c)


def _heat_color(t, u):
    u = max(0.0, min(1.0, u))
    if u < 0.5:
        return _mix("#d6dde8", t["link"], u / 0.5)
    return _mix(t["link"], t["accent"], (u - 0.5) / 0.5)


def _axes(parts, t, ox, oy, pw, ph, xt, yt, grid):
    spanx = (xt[-1] - xt[0]) or 1
    spany = (yt[-1] - yt[0]) or 1

    def X(v):
        return ox + (v - xt[0]) / spanx * pw

    def Y(v):
        return oy + ph - (v - yt[0]) / spany * ph

    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    for v in yt:
        y = Y(v)
        if grid:
            parts.append(f'<line x1="{ox}" y1="{y:.1f}" x2="{ox + pw}" y2="{y:.1f}" stroke="{t["rule"]}" stroke-width="1"/>')
        parts.append(
            f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    for v in xt:
        x = X(v)
        if grid:
            parts.append(f'<line x1="{x:.1f}" y1="{oy}" x2="{x:.1f}" y2="{oy + ph}" stroke="{t["rule"]}" stroke-width="1"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{oy + ph + 16}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{fmt_tick(v)}</text>')
    return X, Y


def _cat_axis(parts, t, labels, ox, oy, pw, ph, horizontal=False):
    n = max(1, len(labels))
    coords = []
    if horizontal:
        for i, lab in enumerate(labels):
            y = oy + (i + 0.5) * ph / n
            coords.append(y)
            parts.append(
                f'<text x="{ox - 8}" y="{y + 3:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end">{esc(lab)}</text>')
        parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    else:
        for i, lab in enumerate(labels):
            x = ox + (i + 0.5) * pw / n
            coords.append(x)
            parts.append(
                f'<text x="{x:.1f}" y="{oy + ph + 16}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(lab)}</text>')
        parts.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1"/>')
    return coords


def _tree_index(rows_or_nodes, name_key="name", parent_key="parent"):
    nodes = []
    for row in rows_or_nodes:
        if isinstance(row, dict) and name_key in row:
            nodes.append(row)
    by_name = {}
    for row in nodes:
        name = str(row.get(name_key) or row.get("id") or "")
        parent = str(row.get(parent_key) or "")
        try:
            val = float(row.get("val") or row.get("value") or 0)
        except (TypeError, ValueError):
            val = 0
        by_name[name] = {"name": name, "parent": parent, "val": val, "children": [], "raw": row}
    for node in by_name.values():
        parent = by_name.get(node["parent"])
        if parent is not None and parent is not node:
            parent["children"].append(node)
    roots = [n for n in by_name.values() if n["parent"] not in by_name or n["parent"] == ""]

    def roll(node):
        if node["children"]:
            node["val"] = sum(roll(c) for c in node["children"]) or node["val"] or 1
        elif node["val"] <= 0:
            node["val"] = 1
        return node["val"]

    for root in roots:
        roll(root)
    return roots


def _partition(items, x, y, w, h, vert=True):
    items = [(k, v) for k, v in items if v > 0]
    if not items:
        return []
    if len(items) == 1 or w < 4 or h < 4:
        return [(items[0][0], x, y, max(w, 0), max(h, 0))]
    total = sum(v for _, v in items) or 1
    half = total / 2
    acc, i = 0, 0
    while i < len(items) - 1 and acc + items[i][1] <= half:
        acc += items[i][1]
        i += 1
    if i == 0:
        i, acc = 1, items[0][1]
    left, right = items[:i], items[i:]
    if not right:
        return [(items[0][0], x, y, w, h)]
    if vert:
        lw = w * acc / total
        return _partition(left, x, y, lw, h, False) + _partition(right, x + lw, y, w - lw, h, False)
    lh = h * acc / total
    return _partition(left, x, y, w, lh, True) + _partition(right, x, y + lh, w, h - lh, True)


def _annulus(cx, cy, r0, r1, a0, a1):
    import math
    large = 1 if (a1 - a0) > math.pi else 0

    def pt(r, a):
        return cx + r * math.cos(a), cy + r * math.sin(a)

    x0, y0 = pt(r1, a0)
    x1, y1 = pt(r1, a1)
    x2, y2 = pt(r0, a1)
    x3, y3 = pt(r0, a0)
    return (f"M {x0:.1f} {y0:.1f} A {r1:.1f} {r1:.1f} 0 {large} 1 {x1:.1f} {y1:.1f} "
            f"L {x2:.1f} {y2:.1f} A {r0:.1f} {r0:.1f} 0 {large} 0 {x3:.1f} {y3:.1f} Z")


def _ninv(p):
    import math
    p = min(max(p, 1e-6), 1 - 1e-6)
    lo, hi = -8.0, 8.0
    for _ in range(48):
        mid = (lo + hi) / 2
        cdf = 0.5 * (1 + math.erf(mid / math.sqrt(2)))
        if cdf < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _layers_of(nodes, edges):
    from collections import defaultdict
    ids = [n.get("id") for n in nodes]
    indeg = {i: 0 for i in ids}
    out = defaultdict(list)
    for e in edges:
        if e.get("from") in indeg and e.get("to") in indeg:
            indeg[e["to"]] += 1
            out[e["from"]].append(e["to"])
    rank = {i: 0 for i in ids}
    ready = [i for i in ids if indeg[i] == 0] or list(ids)
    seen = set()
    while ready:
        cur = ready.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in out[cur]:
            rank[nxt] = max(rank[nxt], rank[cur] + 1)
            indeg[nxt] -= 1
            if indeg[nxt] <= 0:
                ready.append(nxt)
    for i in ids:
        if i not in seen:
            rank[i] = max(rank.values(), default=0) + 1
    return rank


def _place_layers(nodes, rank, W, top, gap_y=120):
    from collections import defaultdict
    rows = defaultdict(list)
    for n in nodes:
        rows[rank[n["id"]]].append(n)
    pos = {}
    for key in sorted(rows):
        row = rows[key]
        for j, n in enumerate(row):
            x = W * (j + 1) / (len(row) + 1)
            y = top + key * gap_y
            pos[n["id"]] = (x, y, n)
    return pos


def _draw_links(parts, t, pos, edges):
    ports = assign_ports(pos, edges)
    for i, e in enumerate(edges):
        if i not in ports:
            continue
        x1, y1, s1, x2, y2, s2 = ports[i]
        d, lx, ly, vertical, _ = route_edge(x1, y1, s1, x2, y2, s2)
        if not d:
            continue
        col = t["link"] if str(e.get("proto", "")).startswith("http") else t["muted"]
        parts.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.6" marker-end="url(#a)"/>')
        parts.append(_tail(x1, y1, s1, col))
        if e.get("label"):
            parts.append(arrow_label(t, lx, ly, str(e["label"]).upper(), vertical=vertical))


# --- chart renderers ---

_ROLE_ALIAS = {
    "x": ("x", "time", "ts", "date", "day", "at"),
    "y": ("y",),
    "val": ("val", "value", "v", "n", "count"),
    "size": ("size", "z", "r"),
    "cat": ("cat", "category", "name", "label"),
    "group": ("group", "series", "g"),
    "a": ("a", "left", "start", "before", "lo"),
    "b": ("b", "right", "end", "after", "hi"),
    "lo": ("lo", "low", "min", "lower"),
    "hi": ("hi", "high", "max", "upper"),
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c"),
    "src": ("src", "from", "source"),
    "dst": ("dst", "to", "target"),
    "lat": ("lat", "latitude"),
    "lon": ("lon", "lng", "long", "longitude"),
    "lat2": ("lat2", "latitude2", "dst_lat"),
    "lon2": ("lon2", "lng2", "longitude2", "dst_lon"),
    "rank": ("rank", "r"),
    "name": ("name", "id", "node"),
    "parent": ("parent", "pid"),
    "axis": ("axis", "dim", "criteria"),
    "series": ("series", "group", "g"),
    "row": ("row", "r"),
    "col": ("col", "column", "c"),
    "state": ("state", "status"),
    "est": ("est", "estimate", "effect", "val", "value"),
    "bar": ("bar", "bars"),
    "line": ("line", "lines"),
    "z": ("z", "val", "value"),
    "date": ("date", "day", "at"),
    "label": ("label", "name"),
}


def _hh(title, sub):
    y = 8
    if title:
        y += 18
    if sub:
        y += 18
    return (y + 16) if (title or sub) else 8


def _short(text, n=28):
    text = str(text)
    return text if len(text) <= n else text[:n - 1] + "…"


def _ordered(vals):
    out = []
    for v in vals:
        if v not in out:
            out.append(v)
    return out


def _col(rows, explicit, role):
    return _pick(rows, explicit, _ROLE_ALIAS[role])


def _need(rows, pairs):
    found = {}
    missing = []
    for role, explicit in pairs:
        col = _col(rows, explicit, role)
        found[role] = col
        if not col:
            missing.append(role)
    if missing:
        raise SystemExit("need a column for " + ", ".join(missing))
    return found


def _floats(rows, col):
    out = []
    for r in rows:
        try:
            out.append((r, _f(r, col)))
        except (TypeError, ValueError, KeyError):
            continue
    if not out:
        raise SystemExit(f"column '{col}' has no numbers")
    return out


def _foot(opt, n, extra=""):
    bit = opt.get("source") or f"n={n}"
    return (bit + (" · " + extra if extra else "")).strip()


def _begin(opt, ph, ox=78, right=44, W=760, bottom=52):
    title, sub = opt["title"], opt["sub"]
    hh = _hh(title, sub)
    oy = hh + 10
    pw = W - ox - right
    H = int(oy + ph + bottom)
    parts, _hh_real = _fig_open(opt["t"], title, sub, W, H)
    return parts, opt["t"], W, H, ox, oy, pw, ph


def _done(parts, opt, W, H, n, extra=""):
    return _fig_close(parts, opt["t"], W, H, _foot(opt, n, extra)) + (n,)


def _domain(vals, floor0=True):
    lo, hi = min(vals), max(vals)
    if floor0 and lo >= 0:
        lo = 0.0
    if lo == hi:
        hi = lo + 1.0
    return lo, hi


def _dot(parts, t, x, y, r, col, on, hit):
    if hit:
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 2.5:.1f}" fill="{t["accent"]}" stroke="{t["card"]}" stroke-width="1.2"/>')
        return
    if not on:
        return
    parts.append(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{col}" stroke="{t["card"]}" stroke-width="1"/>')


def _legend(parts, t, items, x, y, limit=680):
    cx = x
    for col, lab in items:
        lab = _short(lab, 16)
        parts.append(f'<rect x="{cx:.1f}" y="{y - 8:.1f}" width="9" height="9" fill="{col}"/>')
        parts.append(
            f'<text x="{cx + 13:.1f}" y="{y:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}">{esc(lab)}</text>')
        cx += 13 + len(str(lab)) * 6.2 + 16
        if cx > limit:
            break


def _ramp(parts, t, x, y, w, lo, hi):
    steps = 10
    for i in range(steps):
        col = _heat_color(t, i / (steps - 1))
        parts.append(
            f'<rect x="{x + i * w / steps:.1f}" y="{y:.1f}" width="{w / steps + 0.5:.1f}" height="8" fill="{col}"/>')
    parts.append(
        f'<text x="{x:.1f}" y="{y + 20:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}">{esc(lo)}</text>')
    parts.append(
        f'<text x="{x + w:.1f}" y="{y + 20:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{esc(hi)}</text>')


def _cat_labels(parts, t, labels, coords, y, rotate):
    for x, lab in zip(coords, labels):
        if rotate:
            parts.append(
                f'<text x="{x:.1f}" y="{y:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="end" transform="rotate(-32 {x:.1f} {y:.1f})">{esc(_short(lab, 18))}</text>')
        else:
            parts.append(
                f'<text x="{x:.1f}" y="{y:.1f}" font-size="11" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(_short(lab, 16))}</text>')


def _focals(nodes):
    out = []
    for n in nodes:
        if n.get("focal") and len(out) < 2:
            out.append(n.get("id"))
    return set(out)


def _with_ids(nodes):
    for i, n in enumerate(nodes):
        if not n.get("id"):
            n["id"] = str(n.get("name") or f"n{i}")
        if not n.get("name"):
            n["name"] = n["id"]
    return nodes


def _linked(opt, nodes, edges, cap_n, cap_e, gap_y=128):
    nodes = _with_ids(nodes)
    unbounded = _open_budget(opt.get("spec"), opt["unbounded"])
    _cap(opt.get("spec"), len(nodes), cap_n, "nodes", unbounded)
    _cap(opt.get("spec"), len(edges), cap_e, "edges", unbounded)
    rank = _layers_of(nodes, edges) if nodes else {}
    from collections import defaultdict
    rows = defaultdict(list)
    for n in nodes:
        rows[rank.get(n["id"], 0)].append(n)
    depth = max(rank.values()) if rank else 0
    widest = max((len(v) for v in rows.values()), default=1)
    W = max(760, 220 * (widest + 1))
    top = _hh(opt["title"], opt["sub"]) + 52
    H = int(top + max(depth, 0) * gap_y + 96)
    parts, _ = _fig_open(opt["t"], opt["title"], opt["sub"], W, H)
    parts.append(markers(opt["t"]))
    pos = _place_layers(nodes, rank, W, top, gap_y) if nodes else {}
    return parts, pos, W, H


def _paint_boxes(parts, t, pos, focals, w=160, h=56):
    for nid, (x, y, n) in pos.items():
        focal = nid in focals
        fill = t["accent_tint"] if focal else t["card"]
        stroke = t["accent"] if focal else t["ink"]
        sw = "1.5" if focal else "1.1"
        parts.append(
            f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w}" height="{h}" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        name = _short(n.get("name") or nid, 22)
        sub = n.get("sub") or ""
        parts.append(
            f'<text x="{x:.1f}" y="{y + (-2 if sub else 4):.1f}" font-size="13" font-family="{FONT}" fill="{t["ink"]}" text-anchor="middle">{esc(name)}</text>')
        if sub:
            parts.append(
                f'<text x="{x:.1f}" y="{y + 16:.1f}" font-size="11" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{esc(_short(sub, 26))}</text>')


def _open_budget(spec, unbounded):
    return bool(unbounded) or (isinstance(spec, dict) and spec.get("budget") is False)


def _quartiles(vals):
    s = sorted(vals)
    n = len(s)

    def q(p):
        if n == 1:
            return s[0]
        i = p * (n - 1)
        lo = int(i)
        hi = min(lo + 1, n - 1)
        f = i - lo
        return s[lo] * (1 - f) + s[hi] * f

    return q(0.25), q(0.5), q(0.75)


def _parse_date(text):
    import datetime
    s = str(text).strip()
    for fmt, n in (("%Y-%m-%d", 10), ("%Y/%m/%d", 10), ("%Y-%m", 7), ("%Y/%m", 7), ("%Y", 4)):
        try:
            return datetime.datetime.strptime(s[:n], fmt)
        except ValueError:
            continue
    return None


def _when(text):
    import datetime
    try:
        return float(text), False
    except (TypeError, ValueError):
        d = _parse_date(text)
        if d is None:
            raise SystemExit(f"cannot read a date or number from '{text}'")
        return d.toordinal(), True


def _tree_from(nodes):
    rows = []
    by_id = {}
    for n in nodes:
        i = str(n.get("id") or n.get("name") or "")
        by_id[i] = str(n.get("name") or i)
    for n in nodes:
        i = str(n.get("id") or n.get("name") or "")
        parent = str(n.get("parent") or "")
        rows.append({
            "name": by_id.get(i, i),
            "parent": by_id.get(parent, parent),
            "val": n.get("val", n.get("value", 0)),
            "sub": n.get("sub") or "",
            "label": n.get("label") or n.get("edge") or "",
        })
    return _tree_index(rows)


def _leaf_pos(roots):
    pos = {}
    cursor = [0]

    def walk(node, depth):
        if not node["children"]:
            pos[id(node)] = [float(cursor[0]), depth]
            cursor[0] += 1
            return
        for child in node["children"]:
            walk(child, depth + 1)
        xs = [pos[id(c)][0] for c in node["children"]]
        pos[id(node)] = [sum(xs) / len(xs), depth]
    for root in roots:
        walk(root, 0)
    return pos, max(cursor[0], 1)


def _groups(rows, col):
    from collections import defaultdict
    g = defaultdict(list)
    if not col:
        g[""] = list(rows)
        return g
    for r in rows:
        g[str(r.get(col) or "")].append(r)
    return g

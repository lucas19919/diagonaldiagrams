"""Point maps on the built-in coastline, and the map helpers the geo charts share."""
import csv, functools, json
from .errors import SpecError
from ._draw import figure_heading
from ._text import esc
from ._theme import MONO, SANS, THEME, _hit


# Coastline packed as zlib+base64 of "lon_tenth,lat_tenth ..." rings separated by ";".
# Natural Earth 110m land, simplified. Drawn under the points. Not a tiled basemap.
LAND_B64 = """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"""


@functools.lru_cache(maxsize=None)
def _land_rings():
    rings = []
    if LAND_B64:
        import base64, zlib
        raw = zlib.decompress(base64.b64decode(LAND_B64)).decode()
        for part in raw.split(";"):
            pts = []
            for pair in part.split():
                a, b = pair.split(",")
                pts.append((int(a) / 10.0, int(b) / 10.0))
            if len(pts) >= 3:
                rings.append(pts)
    return rings


def _clip_poly(ring, minx, miny, maxx, maxy):
    """Sutherland–Hodgman clip of a lon/lat ring to a box."""
    def edge(poly, inside, cross):
        if not poly:
            return []
        out, prev = [], poly[-1]
        pin = inside(prev)
        for cur in poly:
            cin = inside(cur)
            if cin:
                if not pin:
                    out.append(cross(prev, cur))
                out.append(cur)
            elif pin:
                out.append(cross(prev, cur))
            prev, pin = cur, cin
        return out

    def lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    def xclip(poly, x, keep_left):
        def inside(p):
            return p[0] <= x if keep_left else p[0] >= x
        def cross(a, b):
            dx = b[0] - a[0]
            t = 0.0 if dx == 0 else (x - a[0]) / dx
            return lerp(a, b, max(0.0, min(1.0, t)))
        return edge(poly, inside, cross)

    def yclip(poly, y, keep_low):
        def inside(p):
            return p[1] <= y if keep_low else p[1] >= y
        def cross(a, b):
            dy = b[1] - a[1]
            t = 0.0 if dy == 0 else (y - a[1]) / dy
            return lerp(a, b, max(0.0, min(1.0, t)))
        return edge(poly, inside, cross)

    ring = xclip(ring, maxx, True)
    ring = xclip(ring, minx, False)
    ring = yclip(ring, maxy, True)
    ring = yclip(ring, miny, False)
    return ring


def _map_colors(t):
    paper = t.get("paper") or ""
    dark = False
    if paper.startswith("#") and len(paper) >= 7:
        r, g, b = int(paper[1:3], 16), int(paper[3:5], 16), int(paper[5:7], 16)
        dark = 0.3 * r + 0.59 * g + 0.11 * b < 140
    if dark:
        return "#1c2838", "#3a4358", "#8b95a8"
    return "#d5e3ec", "#f4f0e8", "#8d97a8"


def _merc(lon, lat):
    import math
    lat = max(-85.0, min(85.0, float(lat)))
    x = math.radians(float(lon))
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def _load_geo(path, latcol, loncol, labelcol, valcol):
    """CSV points, or GeoJSON points / polygon rings. Returns points, rings, value label."""
    points, rings = [], []
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            cols = r.fieldnames or []
            def pick(pref, fallbacks):
                if pref and pref in cols:
                    return pref
                for c in cols:
                    if c.lower() in fallbacks:
                        return c
                return None
            lc = pick(latcol, ("lat", "latitude", "y"))
            nc = pick(loncol, ("lon", "lng", "long", "longitude", "x"))
            if not lc or not nc:
                raise SpecError(f"{path}: need lat/lon columns, got {cols}")
            lb = pick(labelcol, ("name", "city", "label"))
            vc = pick(valcol, ("value", "val", "pop", "weight"))
            for row in r:
                try:
                    item = {"lat": float(row[lc]), "lon": float(row[nc]),
                            "label": (row.get(lb) or "") if lb else "",
                            "val": float(row[vc]) if vc and row.get(vc) not in (None, "") else None}
                except (TypeError, ValueError, KeyError):
                    continue
                if not (-90 <= item["lat"] <= 90 and -180 <= item["lon"] <= 180):
                    continue
                points.append(item)
        return points, rings
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    feats = data.get("features", []) if isinstance(data, dict) else []
    for ft in feats:
        g = ft.get("geometry") or {}
        props = ft.get("properties") or {}
        label = str(props.get(labelcol) or props.get("name") or props.get("city") or "")
        raw = props.get(valcol) if valcol else props.get("value")
        try:
            val = float(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            val = None
        gt = g.get("type")
        coords = g.get("coordinates") or []
        if gt == "Point" and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                points.append({"lat": lat, "lon": lon, "label": label, "val": val})
        elif gt == "Polygon":
            if coords:
                rings.append(coords[0])
        elif gt == "MultiPolygon":
            for poly in coords:
                if poly:
                    rings.append(poly[0])
    return points, rings


def render_geo(spec_path, latcol=None, loncol=None, labelcol=None, valcol=None,
               title="Map", subtitle="", figure="Fig. 1", source="", theme=None, width=760, chrome=True,
               grid=True, markers=True, highlights=None):
    """Point map on a built-in coastline. Web Mercator. GeoJSON polygons are drawn on top.
    Stdlib only. A figure, not a tiled GIS."""
    import math
    t = theme or THEME
    points, rings = _load_geo(spec_path, latcol, loncol, labelcol, valcol)
    samples = [(p["lon"], p["lat"]) for p in points]
    for ring in rings:
        for c in ring:
            if len(c) >= 2:
                samples.append((c[0], c[1]))
    if len(samples) < 1:
        raise SpecError(f"{spec_path}: no coordinates")
    lons = [s[0] for s in samples]
    lats = [s[1] for s in samples]
    minlon, maxlon = min(lons), max(lons)
    minlat, maxlat = min(lats), max(lats)
    if maxlon - minlon < 0.4:
        mid = (minlon + maxlon) / 2
        minlon, maxlon = mid - 0.3, mid + 0.3
    if maxlat - minlat < 0.4:
        mid = (minlat + maxlat) / 2
        minlat, maxlat = mid - 0.25, mid + 0.25
    pad_x = (maxlon - minlon) * 0.08
    pad_y = (maxlat - minlat) * 0.08
    minlon -= pad_x
    maxlon += pad_x
    minlat -= pad_y
    maxlat += pad_y
    corners = [_merc(minlon, minlat), _merc(maxlon, minlat), _merc(minlon, maxlat), _merc(maxlon, maxlat)]
    minx = min(c[0] for c in corners)
    maxx = max(c[0] for c in corners)
    miny = min(c[1] for c in corners)
    maxy = max(c[1] for c in corners)
    W = width
    head_bits, head_h = figure_heading(t, title, subtitle, x=36) if chrome else ([], 12)
    ox, oy = 48, head_h
    pw, ph = W - ox - 36, 420
    H = oy + ph + 56
    sx = (maxx - minx) or 1
    sy = (maxy - miny) or 1
    # fit, preserving mercator aspect inside the panel
    aspect = sx / sy
    panel_aspect = pw / ph
    if aspect > panel_aspect:
        used_w, used_h = pw, pw / aspect
    else:
        used_h, used_w = ph, ph * aspect
    x0 = ox + (pw - used_w) / 2
    y0 = oy + (ph - used_h) / 2

    def proj(lon, lat):
        mx, my = _merc(lon, lat)
        px = x0 + (mx - minx) / sx * used_w
        py = y0 + (maxy - my) / sy * used_h
        return px, py

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(title)}</title>',
             f'<desc>{esc(subtitle or "Locations")}</desc>',
             f'<rect width="{W}" height="{H}" fill="{t["card"]}"/>']
    parts.extend(head_bits)
    water, land, coast = _map_colors(t)
    parts.append(f'<rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" fill="{water}" stroke="{t["rule"]}"/>')
    parts.append(f'<clipPath id="mapframe"><rect x="{x0:.1f}" y="{y0:.1f}" width="{used_w:.1f}" height="{used_h:.1f}"/></clipPath>')
    parts.append('<g clip-path="url(#mapframe)">')
    for ring in _land_rings():
        lons_r = [p[0] for p in ring]
        lats_r = [p[1] for p in ring]
        if max(lons_r) < minlon or min(lons_r) > maxlon or max(lats_r) < minlat or min(lats_r) > maxlat:
            continue
        clipped = _clip_poly(ring, minlon, minlat, maxlon, maxlat)
        if len(clipped) < 3:
            continue
        seq = []
        for lon, lat in clipped:
            px, py = proj(lon, lat)
            seq.append(f"{px:.1f},{py:.1f}")
        parts.append(f'<polygon points="{" ".join(seq)}" fill="{land}" stroke="{coast}" stroke-width="0.7" stroke-linejoin="round"/>')
    # graticule on nice degree steps
    span = max(maxlon - minlon, maxlat - minlat)
    step = 1
    for cand in (1, 2, 5, 10, 15, 30, 45):
        if span / cand <= 6:
            step = cand
            break
    def nice_deg(lo, hi):
        import math as _m
        a = _m.ceil(lo / step) * step
        v = a
        while v < hi - 1e-9:
            yield v
            v += step
    labels = []
    for lon in nice_deg(minlon, maxlon):
        x, _ = proj(lon, (minlat + maxlat) / 2)
        if grid:
            parts.append(f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y0+used_h:.1f}" stroke="{coast}" stroke-opacity="0.55" stroke-width="0.7"/>')
        labels.append(f'<text x="{x:.1f}" y="{y0+used_h+14:.1f}" font-size="9" font-family="{MONO}" fill="{t["soft"]}" text-anchor="middle">{lon:.0f}°</text>')
    for lat in nice_deg(minlat, maxlat):
        _, y = proj((minlon + maxlon) / 2, lat)
        if grid:
            parts.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x0+used_w:.1f}" y2="{y:.1f}" stroke="{coast}" stroke-opacity="0.55" stroke-width="0.7"/>')
        labels.append(f'<text x="{x0-6:.1f}" y="{y+3:.1f}" font-size="9" font-family="{MONO}" fill="{t["soft"]}" text-anchor="end">{lat:.0f}°</text>')
    vals = [p["val"] for p in points if p["val"] is not None]
    vmin, vmax = (min(vals), max(vals)) if vals else (0, 1)
    if vmin == vmax:
        vmax = vmin + 1
    for ring in rings:
        seq = []
        for c in ring:
            if len(c) < 2:
                continue
            px, py = proj(c[0], c[1])
            seq.append(f"{px:.1f},{py:.1f}")
        if len(seq) >= 3:
            parts.append(f'<polygon points="{" ".join(seq)}" fill="{t["accent_tint"]}" stroke="{t["ink"]}" stroke-width="1"/>')
    parts.append("</g>")
    parts.extend(labels)
    show_labels = len(points) <= 16
    for p in points:
        hit = _hit(highlights, p["label"], p["lat"], p["lon"])
        if not markers and not hit:
            continue
        px, py = proj(p["lon"], p["lat"])
        if p["val"] is None:
            r = 4.5
            col = t["accent"]
        else:
            u = (p["val"] - vmin) / (vmax - vmin)
            r = 4 + 10 * u
            col = t["link"] if u < 0.66 else t["accent"]
        if hit:
            col = t["accent"]
            r += 3
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r:.1f}" fill="{col}" fill-opacity="0.9" stroke="{t["card"]}" stroke-width="{"1.6" if hit else "1"}"/>')
        if (show_labels or hit) and p["label"]:
            parts.append(f'<text x="{px+r+4:.1f}" y="{py-r:.1f}" font-size="11" font-family="{SANS}" fill="{t["ink"]}">{esc(p["label"])}</text>')
    # scale bar from mercator metres at mid latitude
    midlat = (minlat + maxlat) / 2
    m_per_rad = 6378137 * math.cos(math.radians(midlat))
    m_per_px = m_per_rad / (used_w / sx)
    target = used_w * 0.22 * m_per_px
    nice_m = 1
    for cand in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000):
        if cand * 1000 <= target:
            nice_m = cand
    bar_px = (nice_m * 1000) / m_per_px if m_per_px else 40
    bx, by = x0 + 12, y0 + used_h - 18
    parts.append(f'<rect x="{bx-4:.1f}" y="{by-18:.1f}" width="{bar_px+12:.1f}" height="26" fill="{water}" fill-opacity="0.92"/>')
    parts.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx+bar_px:.1f}" y2="{by:.1f}" stroke="{t["ink"]}" stroke-width="2"/>')
    parts.append(f'<line x1="{bx:.1f}" y1="{by-4:.1f}" x2="{bx:.1f}" y2="{by+4:.1f}" stroke="{t["ink"]}" stroke-width="1.2"/>')
    parts.append(f'<line x1="{bx+bar_px:.1f}" y1="{by-4:.1f}" x2="{bx+bar_px:.1f}" y2="{by+4:.1f}" stroke="{t["ink"]}" stroke-width="1.2"/>')
    unit = f"{nice_m} km" if nice_m < 1000 else f"{nice_m/1000:g}k km"
    parts.append(f'<text x="{bx:.1f}" y="{by-8:.1f}" font-size="10" font-family="{MONO}" fill="{t["ink"]}">{esc(unit)}</text>')
    # north
    nx, ny = x0 + used_w - 18, y0 + 22
    parts.append(f'<line x1="{nx:.1f}" y1="{ny+16:.1f}" x2="{nx:.1f}" y2="{ny-10:.1f}" stroke="{t["ink"]}" stroke-width="1.2"/>')
    parts.append(f'<polygon points="{nx:.1f},{ny-16:.1f} {nx-4:.1f},{ny-6:.1f} {nx+4:.1f},{ny-6:.1f}" fill="{t["ink"]}"/>')
    parts.append(f'<text x="{nx+8:.1f}" y="{ny-8:.1f}" font-size="10" font-family="{MONO}" fill="{t["ink"]}">N</text>')
    note = f"n = {len(points)}"
    if rings:
        note += f" · {len(rings)} polygons"
    if source:
        note += f" · Source: {source}"
    note += " · Web Mercator"
    parts.append(f'<text x="36" y="{H-14}" font-size="10.5" font-family="{MONO}" fill="{t["soft"]}">{esc(note)}</text>')
    parts.append("</svg>")
    return "\n".join(parts), W, H, len(points)


def _map_stage(t, title, subtitle, samples, width=760):
    import math
    lons = [s[0] for s in samples]
    lats = [s[1] for s in samples]
    minlon, maxlon = min(lons), max(lons)
    minlat, maxlat = min(lats), max(lats)
    if maxlon - minlon < 0.4:
        mid = (minlon + maxlon) / 2
        minlon, maxlon = mid - 0.3, mid + 0.3
    if maxlat - minlat < 0.4:
        mid = (minlat + maxlat) / 2
        minlat, maxlat = mid - 0.25, mid + 0.25
    pad_x = (maxlon - minlon) * 0.08
    pad_y = (maxlat - minlat) * 0.08
    minlon, maxlon = minlon - pad_x, maxlon + pad_x
    minlat, maxlat = minlat - pad_y, maxlat + pad_y
    corners = [_merc(minlon, minlat), _merc(maxlon, minlat), _merc(minlon, maxlat), _merc(maxlon, maxlat)]
    minx, maxx = min(c[0] for c in corners), max(c[0] for c in corners)
    miny, maxy = min(c[1] for c in corners), max(c[1] for c in corners)
    W = width
    head, hh = figure_heading(t, title, subtitle, x=36)
    ox, oy, pw, ph = 48, hh, W - 84, 420
    H = oy + ph + 56
    sx, sy = (maxx - minx) or 1, (maxy - miny) or 1
    aspect, panel = sx / sy, pw / ph
    if aspect > panel:
        used_w, used_h = pw, pw / aspect
    else:
        used_h, used_w = ph, ph * aspect
    x0 = ox + (pw - used_w) / 2
    y0 = oy + (ph - used_h) / 2

    def proj(lon, lat):
        mx, my = _merc(lon, lat)
        return x0 + (mx - minx) / sx * used_w, y0 + (maxy - my) / sy * used_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(title or "map")}</title>',
        f'<desc>{esc(subtitle or title or "map")}</desc>',
        f'<rect width="{W}" height="{H}" fill="{t["card"]}"/>',
    ]
    parts.extend(head)
    water, land, coast = _map_colors(t)
    parts.append(f'<rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" fill="{water}" stroke="{t["rule"]}"/>')
    parts.append(f'<clipPath id="mapframe"><rect x="{x0:.1f}" y="{y0:.1f}" width="{used_w:.1f}" height="{used_h:.1f}"/></clipPath>')
    parts.append('<g clip-path="url(#mapframe)">')
    for ring in _land_rings():
        lons_r = [p[0] for p in ring]
        lats_r = [p[1] for p in ring]
        if max(lons_r) < minlon or min(lons_r) > maxlon or max(lats_r) < minlat or min(lats_r) > maxlat:
            continue
        clipped = _clip_poly(ring, minlon, minlat, maxlon, maxlat)
        if len(clipped) < 3:
            continue
        seq = []
        for lon, lat in clipped:
            px, py = proj(lon, lat)
            seq.append(f"{px:.1f},{py:.1f}")
        parts.append(f'<polygon points="{" ".join(seq)}" fill="{land}" stroke="{coast}" stroke-width="0.6"/>')
    return {"parts": parts, "proj": proj, "W": W, "H": H, "t": t, "x0": x0, "y0": y0,
            "used_w": used_w, "used_h": used_h, "ox": ox, "oy": oy, "water": water,
            "minlon": minlon, "maxlon": maxlon, "minlat": minlat, "maxlat": maxlat, "sx": sx}


def _map_finish(ctx, note):
    import math
    t, parts = ctx["t"], ctx["parts"]
    parts.append("</g>")
    parts.extend(ctx.get("after") or [])
    x0, y0, used_w, used_h, sx = ctx["x0"], ctx["y0"], ctx["used_w"], ctx["used_h"], ctx["sx"]
    midlat = (ctx["minlat"] + ctx["maxlat"]) / 2
    m_per_px = 6378137 * math.cos(math.radians(midlat)) / (used_w / sx) if used_w else 1
    target = used_w * 0.22 * m_per_px
    nice_m = 1
    for cand in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000):
        if cand * 1000 <= target:
            nice_m = cand
    bar_px = (nice_m * 1000) / m_per_px if m_per_px else 40
    bx, by = x0 + 12, y0 + used_h - 18
    parts.append(f'<rect x="{bx - 4:.1f}" y="{by - 18:.1f}" width="{bar_px + 12:.1f}" height="26" fill="{ctx["water"]}" fill-opacity="0.92"/>')
    parts.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx + bar_px:.1f}" y2="{by:.1f}" stroke="{t["ink"]}" stroke-width="2"/>')
    unit = f"{nice_m} km" if nice_m < 1000 else f"{nice_m / 1000:g}k km"
    parts.append(f'<text x="{bx:.1f}" y="{by - 8:.1f}" font-size="10" font-family="{MONO}" fill="{t["ink"]}">{esc(unit)}</text>')
    nx, ny = x0 + used_w - 18, y0 + 22
    parts.append(f'<line x1="{nx:.1f}" y1="{ny + 16:.1f}" x2="{nx:.1f}" y2="{ny - 10:.1f}" stroke="{t["ink"]}" stroke-width="1.2"/>')
    parts.append(f'<polygon points="{nx:.1f},{ny - 16:.1f} {nx - 4:.1f},{ny - 6:.1f} {nx + 4:.1f},{ny - 6:.1f}" fill="{t["ink"]}"/>')
    parts.append(f'<text x="{nx + 8:.1f}" y="{ny - 8:.1f}" font-size="10" font-family="{MONO}" fill="{t["ink"]}">N</text>')
    parts.append(f'<text x="36" y="{ctx["H"] - 14}" font-size="10.5" font-family="{MONO}" fill="{t["soft"]}">{esc(note)} · Web Mercator</text>')
    parts.append("</svg>")
    return "\n".join(parts), ctx["W"], ctx["H"]

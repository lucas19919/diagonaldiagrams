"""bar, line and scatter."""
import csv
from ._draw import (
    axis_ticks, bar_path, corner_rx, figure_heading, fmt_tick, fmt_value, nice_ticks, render_pincallout,
)
from ._text import _humanize, _text_w, _with_unit, esc
from ._theme import MONO, SANS, THEME, _assign_colors, _hit, series_palette


def render_scatter(spec_path, xcol, ycol, title, subtitle, figure, xlabel, xunit, ylabel, yunit,
                    groupcol=None, yerrcol=None, facetcol=None, source="", corners="editorial",
                    chrome=True, width=760, facet_dir="row", theme=None, notes=None,
                    grid=True, markers=True, highlights=None):
    """Scatter: title and subtitle on the figure, nice ticks, groups, error bars, facets.
    chrome=False skips the heading. grid draws the tick rules. markers draws the dots.
    highlights (category, x, or group) are drawn larger in accent.
    facet_dir=row (side-by-side) or col (stacked, for social)."""
    import math
    t = theme or THEME
    rows = []
    with open(spec_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        cols = r.fieldnames or []
        xc = xcol or cols[0]; yc = ycol or (cols[1] if len(cols) > 1 else cols[0])
        for row in r:
            try:
                d = {"x": float(row[xc]), "y": float(row[yc])}
                if groupcol and row.get(groupcol):
                    d["g"] = str(row[groupcol])
                if yerrcol and row.get(yerrcol):
                    d["ye"] = float(row[yerrcol])
                if facetcol and row.get(facetcol):
                    d["f"] = str(row[facetcol])
                rows.append(d)
            except ValueError:
                continue
    if not rows:
        raise SystemExit(f"{spec_path}: no numeric data in {xc}/{yc}")
    facets = sorted({d.get("f", "") for d in rows})
    multi = len(facets) > 1 or len(facets) == 1 and facetcol is not None
    groups = sorted({d.get("g", "") for d in rows if d.get("g")})
    _pal = series_palette(t, highlights)
    palette = _assign_colors(groups, _pal, highlights) if groups else {}
    # One scale for every facet, including the error bars, so panel B is comparable to panel A.
    xs = [d["x"] for d in rows]
    ylo = [d["y"] - d.get("ye", 0) for d in rows]
    yhi = [d["y"] + d.get("ye", 0) for d in rows]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ylo), max(yhi)
    if xmin == xmax:
        xmax = xmin + 1
    if ymin == ymax:
        ymax = ymin + 1
    padx, pady = (xmax - xmin) * 0.06, (ymax - ymin) * 0.08
    xmin -= padx
    xmax += padx
    ymin -= pady
    ymax += pady
    if min(xs) >= 0:
        xmin = max(0, xmin)
    if min(ylo) >= 0:
        ymin = max(0, ymin)
    xt = nice_ticks(xmin, xmax)
    yt = axis_ticks(ymin, ymax)

    def panel_svg(dset, panel_tag, px, py, pw, ph, show_y):
        sx = lambda v: px + (v - xt[0]) / (xt[-1] - xt[0]) * pw if len(xt) > 1 and xt[-1] != xt[0] else px + pw / 2
        sy = lambda v: (py + ph) - (v - yt[0]) / (yt[-1] - yt[0]) * ph if len(yt) > 1 and yt[-1] != yt[0] else py + ph / 2
        p = []
        # panel tag A/B
        if panel_tag:
            p.append(f'<text x="{px}" y="{py-10}" font-size="13" font-weight="600" font-family="{SANS}" fill="{t["ink"]}">{esc(panel_tag)}</text>')
        if grid:
            for v in xt:
                p.append(f'<line x1="{sx(v):.1f}" y1="{py}" x2="{sx(v):.1f}" y2="{py+ph}" stroke="{t["rule"]}" stroke-width="0.8"/>')
            for v in yt:
                p.append(f'<line x1="{px}" y1="{sy(v):.1f}" x2="{px+pw}" y2="{sy(v):.1f}" stroke="{t["rule"]}" stroke-width="0.8"/>')
        # decluttered spines: bottom + left only
        p.append(f'<line x1="{px}" y1="{py+ph}" x2="{px+pw}" y2="{py+ph}" stroke="{t["ink"]}" stroke-width="1.2"/>')
        p.append(f'<line x1="{px}" y1="{py}" x2="{px}" y2="{py+ph}" stroke="{t["ink"]}" stroke-width="1.2"/>')
        # Every point is drawn: up to 400 as dots with a tooltip, up to 5,000 as small translucent
        # dots so density shows, past that a fixed random sample of 5,000 (the footer says so).
        many = len(dset) > 400
        shown = dset if len(dset) <= 5000 else __import__("random").Random(7).sample(dset, 5000)
        # error bars first, then points
        for d in ([] if many else dset):
            if "ye" in d:
                y1 = sy(d["y"] - d["ye"]); y2 = sy(d["y"] + d["ye"])
                col = palette.get(d.get("g", ""), t["muted"])
                p.append(f'<line x1="{sx(d["x"]):.1f}" y1="{y1:.1f}" x2="{sx(d["x"]):.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="1"/>')
                p.append(f'<line x1="{sx(d["x"])-4:.1f}" y1="{y1:.1f}" x2="{sx(d["x"])+4:.1f}" y2="{y1:.1f}" stroke="{col}"/>')
                p.append(f'<line x1="{sx(d["x"])-4:.1f}" y1="{y2:.1f}" x2="{sx(d["x"])+4:.1f}" y2="{y2:.1f}" stroke="{col}"/>')
        for d in shown:
            hit = _hit(highlights, d.get("g"), d["x"], fmt_tick(d["x"]))
            if not markers and not hit:
                continue
            col = t["accent"] if hit else palette.get(d.get("g", ""), t["muted"])
            if many and not hit:
                p.append(f'<circle cx="{sx(d["x"]):.1f}" cy="{sy(d["y"]):.1f}" r="2.2" fill="{col}" fill-opacity=".35"/>')
                continue
            rad = 6.4 if hit else 4.2
            tip = (f'{d["g"]} · ' if d.get("g") else "") + f'{fmt_tick(d["x"])}, {fmt_tick(d["y"])}'
            p.append(f'<circle cx="{sx(d["x"]):.1f}" cy="{sy(d["y"]):.1f}" r="{rad}" fill="{col}" fill-opacity=".9" stroke="{t["card"]}" stroke-width="1">'
                     f'<title>{esc(tip)}</title></circle>')
        for ni, pn in enumerate(notes or []):
            try:
                nx, ny = float(pn["x"]), float(pn["y"])
            except (KeyError, TypeError, ValueError):
                continue
            if len(xt) > 1 and len(yt) > 1 and xt[0] <= nx <= xt[-1] and yt[0] <= ny <= yt[-1] \
                    and ni not in drawn_notes:
                drawn_notes.add(ni)
                p.append(render_pincallout(t, sx(nx), sy(ny), pn.get("text", ""), top=py + 4))
        # ticks
        for v in xt:
            p.append(f'<text x="{sx(v):.1f}" y="{py+ph+18}" font-size="10" font-family="{MONO}" fill="{t["soft"]}" text-anchor="middle">{esc(fmt_tick(v))}</text>')
        if show_y:
            for v in yt:
                p.append(f'<text x="{px-8}" y="{sy(v)+3:.1f}" font-size="10" font-family="{MONO}" fill="{t["soft"]}" text-anchor="end">{esc(fmt_tick(v))}</text>')
        return "\n".join(p), len(dset)

    W = width
    faceted = bool(facetcol and len(facets) > 1)
    if chrome:
        head_bits, head_h = figure_heading(t, title, subtitle, x=36)
        if faceted:
            head_h += 18
    else:
        head_bits, head_h = [], 12
    if facet_dir == "col" and faceted:
        panel_h, gap = 250, 64
        fig_h = panel_h * len(facets) + gap * (len(facets) - 1)
        fig_w = W - 72
    else:
        fig_w, fig_h = W - 72, 360
    foot_h = 96 if groups else 70
    H = head_h + fig_h + foot_h + 30
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(title)}</title>',
         f'<desc>{esc((subtitle + " " if subtitle else "") + (xlabel or "") + " vs " + (ylabel or ""))}</desc>',
         f'<rect width="{W}" height="{H}" fill="{t["card"]}"/>']
    s.extend(head_bits)
    ox, oy = 72, head_h
    drawn_notes = set()  # each pin drawn once (first panel whose domain contains it)
    if faceted and facet_dir == "col":
        for i, fv in enumerate(facets):
            dset = [d for d in rows if d.get("f") == fv]
            tag = chr(65 + i)
            label = tag if not fv or fv == tag else f"{tag} · {fv}"
            blk, _ = panel_svg(dset, label, ox, oy + i * (panel_h + gap), fig_w - 72, panel_h - 40, show_y=True)
            s.append(blk)
    elif faceted:
        gutter = 48
        pw = (fig_w - 72 - gutter * (len(facets) - 1)) / len(facets)
        for i, fv in enumerate(facets):
            dset = [d for d in rows if d.get("f") == fv]
            tag = chr(65 + i)
            label = tag if not fv or fv == tag else f"{tag} · {fv}"
            blk, _ = panel_svg(dset, label, ox + i * (pw + gutter), oy, pw, fig_h - 40, show_y=True)
            s.append(blk)
    else:
        blk, _ = panel_svg(rows, "", ox, oy, fig_w - 72, fig_h - 40, show_y=True)
        s.append(blk)
    # axis titles with units (clear of tick labels at +18)
    xlab = _with_unit(xlabel or _humanize(xc), xunit)
    ylab = _with_unit(ylabel or _humanize(yc), yunit)
    foot_top = oy + fig_h
    s.append(f'<text x="{ox + (fig_w-72)/2}" y="{foot_top+42}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle" data-role="xaxis">{esc(xlab)}</text>')
    s.append(f'<text x="20" y="{oy + fig_h/2}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle" transform="rotate(-90 20,{oy + fig_h/2})" data-role="yaxis">{esc(ylab)}</text>')
    # legend row below axis title
    if groups:
        lx, ly = ox, foot_top + 66
        for g in groups:
            s.append(f'<circle cx="{lx+6}" cy="{ly-4}" r="5" fill="{palette[g]}" stroke="{t["card"]}"/>')
            s.append(f'<text x="{lx+16}" y="{ly}" font-size="11" font-family="{SANS}" fill="{t["ink"]}" data-role="series">{esc(g)}</text>')
            lx += 16 + len(g) * 7 + 24
    # stats + source inside figure (no duplicated n)
    n = len(rows)
    note = f"n = {n}" + (" · 5,000 shown, a random sample" if n > 5000 else "")
    if len(rows) > 2:
        try:
            mx = sum(d["x"] for d in rows) / n; my = sum(d["y"] for d in rows) / n
            num = sum((d["x"] - mx) * (d["y"] - my) for d in rows)
            den = (sum((d["x"] - mx) ** 2 for d in rows) * sum((d["y"] - my) ** 2 for d in rows)) ** 0.5
            if den:
                note += f" · Pearson r = {num/den:.2f}"
        except Exception:
            pass
    src = (source or "").strip()
    if src:
        import re as _re
        src = _re.sub(r"^\s*n\s*=\s*\d+\s*[·•\-–]\s*", "", src)  # caller already gets n
        note += f" · Source: {src}" if not src.lower().startswith("source") else f" · {src}"
    s.append(f'<text x="36" y="{H-12}" font-size="10.5" font-family="{MONO}" fill="{t["soft"]}">{esc(note)}</text>')
    s.append("</svg>")
    return "\n".join(s), W, H, n


def render_bar(spec_path, catcol, valcol, title, subtitle="", figure="Fig. 1",
               groupcol=None, orientation="v", sort="none", xlabel="", ylabel="",
               unit="", source="", corners="editorial", chrome=True, width=760, theme=None, notes=None,
               grid=True, markers=True, highlights=None):
    t = theme or THEME
    rows = []
    with open(spec_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        cols = r.fieldnames or []
        cc = catcol or (cols[0] if cols else "")
        vc = valcol or (cols[1] if len(cols) > 1 else (cols[0] if cols else ""))
        for row in r:
            try:
                d = {"cat": str(row[cc]), "val": float(row[vc])}
                if groupcol and row.get(groupcol):
                    d["g"] = str(row[groupcol])
                rows.append(d)
            except (ValueError, KeyError, TypeError):
                continue
    if not rows:
        raise SystemExit(f"{spec_path}: no valid data in {cc}/{vc}")
    if sort == "asc":
        rows.sort(key=lambda d: d["val"])
    elif sort == "desc":
        rows.sort(key=lambda d: d["val"], reverse=True)
    vals = [d["val"] for d in rows]
    vmin, vmax = min(vals), max(vals)
    if vmin >= 0:
        vmin = 0
    if vmin == vmax:
        vmax = vmin + 1
    ticks = axis_ticks(vmin, vmax, n=5)
    span = (ticks[-1] - ticks[0]) or 1
    W = width
    head_bits, head_h = figure_heading(t, title, subtitle, x=36) if chrome else ([], 12)
    _bpal = series_palette(t, highlights)
    _bgroups = sorted({d.get("g", "") for d in rows if d.get("g")})
    _bmap = _assign_colors(_bgroups, _bpal, highlights)
    horizontal = orientation == "h"
    cats, buckets = [], {}
    for d in rows:
        buckets.setdefault(d["cat"], []).append(d)
        if d["cat"] not in cats:
            cats.append(d["cat"])
    # one slot per category when a group column splits it; otherwise one bar per row
    slot_members = [buckets[c] for c in cats] if _bgroups else [[d] for d in rows]
    n = len(slot_members)
    rx = corner_rx(corners)
    if horizontal:
        label_w = min(200, max(88, max(len(s[0]["cat"]) for s in slot_members) * 6.6 + 18))
        ox = label_w
        oy = head_h + 8
        row_h = 32 if n > 8 else 40
        ph = max(160, n * row_h + 16)
        pw = W - ox - 72
        H = oy + ph + 72 + (26 if _bgroups else 0)
    else:
        ox, oy = 90, head_h
        pw, ph = W - ox - 48, 340
        slot_w = pw / max(1, n)
        wide = any(len(m[0]["cat"]) * 6.4 > slot_w * 0.9 for m in slot_members)
        H = head_h + ph + (128 if wide else 100) + (46 if _bgroups else 0)  # axis title, then the legend
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(title)}</title>',
             f'<desc>{esc(subtitle or (cc + " vs " + vc))}</desc>',
             f'<rect width="{W}" height="{H}" fill="{t["card"]}"/>']
    parts.extend(head_bits)

    def _sx(v):
        return ox + (v - ticks[0]) / span * pw

    def _sy(v):
        return (oy + ph) - (v - ticks[0]) / span * ph

    zero = 0 if ticks[0] <= 0 <= ticks[-1] else ticks[0]
    if horizontal:
        for v in ticks:
            x_pos = _sx(v)
            if grid:
                parts.append(f'<line x1="{x_pos:.1f}" y1="{oy}" x2="{x_pos:.1f}" y2="{oy+ph}" stroke="{t["rule"]}" stroke-width="0.8"/>')
            parts.append(f'<text x="{x_pos:.1f}" y="{oy+ph+16}" font-size="10" font-family="{MONO}" fill="{t["soft"]}" text-anchor="middle">{esc(fmt_tick(v))}</text>')
        parts.append(f'<line x1="{ox}" y1="{oy+ph}" x2="{ox+pw}" y2="{oy+ph}" stroke="{t["ink"]}" stroke-width="1.2"/>')
        parts.append(f'<line x1="{_sx(zero):.1f}" y1="{oy}" x2="{_sx(zero):.1f}" y2="{oy+ph}" stroke="{t["ink"]}" stroke-width="1.2"/>')
        band = ph / max(1, n)
        bar_h = min(22, band * 0.62)
        for i, members in enumerate(slot_members):
            cy = oy + (i + 0.5) * band
            gap = 3
            bh = min(bar_h, (band * 0.72 - gap * (len(members) - 1)) / len(members))
            top0 = cy - (bh * len(members) + gap * (len(members) - 1)) / 2
            parts.append(f'<text x="{ox-8}" y="{cy+4:.1f}" font-size="11" font-family="{SANS}" fill="{t["ink"]}" text-anchor="end">{esc(members[0]["cat"])}</text>')
            for j, d in enumerate(members):
                by = top0 + j * (bh + gap)
                x0, x1 = _sx(zero), _sx(d["val"])
                bx, bw = (x1, x0 - x1) if d["val"] < zero else (x0, x1 - x0)
                cap = "left" if d["val"] < zero else "right"
                hit = _hit(highlights, d["cat"], d.get("g"))
                col = t["accent"] if hit else _bmap.get(d.get("g", ""), t["link"])
                grow = 2 if hit else 0
                shape = bar_path(bx, by - grow / 2, bw, bh + grow, rx, cap)
                if shape:
                    edge = f' stroke="{t["ink"]}" stroke-width="1.2"' if hit else ""
                    tip = (f'{d["g"]} · ' if d.get("g") else "") + f'{d["cat"]}: {fmt_value(d["val"])}' + (f" {unit}" if unit else "")
                    parts.append(f'{shape} fill="{col}" fill-opacity="{"0.95" if hit else "0.85"}"{edge}><title>{esc(tip)}</title></path>')
                if markers:
                    val_str = fmt_value(d["val"]) + (f" {unit}" if unit else "")
                    outside = (bx - 6) if d["val"] < zero else (bx + bw + 6)
                    if d["val"] >= zero and outside > ox + pw - 28:
                        parts.append(f'<text x="{bx+bw-4:.1f}" y="{by+bh/2+3:.1f}" font-size="10" font-family="{MONO}" fill="{t["card"]}" text-anchor="end">{esc(val_str)}</text>')
                    else:
                        anchor = "end" if d["val"] < zero else "start"
                        parts.append(f'<text x="{outside:.1f}" y="{by+bh/2+3:.1f}" font-size="10" font-family="{MONO}" fill="{t["ink"]}" text-anchor="{anchor}">{esc(val_str)}</text>')
        legend_y = oy + ph + 28
    else:
        for v in ticks:
            y_pos = _sy(v)
            if grid:
                parts.append(f'<line x1="{ox}" y1="{y_pos:.1f}" x2="{ox+pw}" y2="{y_pos:.1f}" stroke="{t["rule"]}" stroke-width="0.8"/>')
            parts.append(f'<text x="{ox-8}" y="{y_pos+3:.1f}" font-size="10" font-family="{MONO}" fill="{t["soft"]}" text-anchor="end">{esc(fmt_tick(v))}</text>')
        base_y = _sy(zero)
        parts.append(f'<line x1="{ox}" y1="{base_y:.1f}" x2="{ox+pw}" y2="{base_y:.1f}" stroke="{t["ink"]}" stroke-width="1.2"/>')
        parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy+ph}" stroke="{t["ink"]}" stroke-width="1.2"/>')
        for i, members in enumerate(slot_members):
            gap = 4
            inner = slot_w * 0.7
            bw = min(48, (inner - gap * (len(members) - 1)) / max(1, len(members)))
            origin = ox + i * slot_w + (slot_w - (bw * len(members) + gap * (len(members) - 1))) / 2
            for j, d in enumerate(members):
                bx = origin + j * (bw + gap)
                y_val = _sy(d["val"])
                y0 = base_y
                by, bh = (y_val, y0 - y_val) if d["val"] >= zero else (y0, y_val - y0)
                by = min(max(by, oy), oy + ph)
                bh = max(0.0, min(bh, oy + ph - by))
                cap = "bottom" if d["val"] < zero else "top"
                hit = _hit(highlights, d["cat"], d.get("g"))
                col = t["accent"] if hit else _bmap.get(d.get("g", ""), t["link"])
                grow = 3 if hit else 0
                shape = bar_path(bx - grow / 2, by, bw + grow, bh, rx, cap)
                if shape:
                    edge = f' stroke="{t["ink"]}" stroke-width="1.2"' if hit else ""
                    tip = (f'{d["g"]} · ' if d.get("g") else "") + f'{d["cat"]}: {fmt_value(d["val"])}' + (f" {unit}" if unit else "")
                    parts.append(f'{shape} fill="{col}" fill-opacity="{"0.95" if hit else "0.85"}"{edge}><title>{esc(tip)}</title></path>')
                if markers:
                    val_str = fmt_value(d["val"]) + (f" {unit}" if unit else "")
                    tip = by if d["val"] >= zero else by + bh
                    if d["val"] >= zero and tip < oy + 18:
                        parts.append(f'<text x="{bx+bw/2:.1f}" y="{tip+13:.1f}" font-size="10" font-family="{MONO}" fill="{t["card"]}" text-anchor="middle">{esc(val_str)}</text>')
                    else:
                        ly = tip - 6 if d["val"] >= zero else tip + 14
                        parts.append(f'<text x="{bx+bw/2:.1f}" y="{ly:.1f}" font-size="10" font-family="{MONO}" fill="{t["ink"]}" text-anchor="middle">{esc(val_str)}</text>')
            cx = ox + (i + 0.5) * slot_w
            ly = oy + ph + 18
            if wide:
                parts.append(f'<text x="{cx:.1f}" y="{ly:.1f}" font-size="10.5" font-family="{SANS}" fill="{t["ink"]}" text-anchor="end" transform="rotate(-40 {cx:.1f} {ly:.1f})">{esc(members[0]["cat"])}</text>')
            else:
                parts.append(f'<text x="{cx:.1f}" y="{ly:.1f}" font-size="10.5" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle">{esc(members[0]["cat"])}</text>')
        legend_y = oy + ph + (56 if wide else 36)
    for nt in (notes or [])[:2]:
        hit = next((d for d in rows if d["cat"] == nt.get("at")), None)
        if hit is None:
            continue
        if horizontal:
            idx = next(i for i, m in enumerate(slot_members) if m[0]["cat"] == hit["cat"])
            cy = oy + (idx + 0.5) * (ph / max(1, n))
            parts.append(render_pincallout(t, _sx(hit["val"]), cy, nt.get("text", ""), above=False, top=oy + 4))
        else:
            idx = next(i for i, m in enumerate(slot_members) if any(d["cat"] == hit["cat"] for d in m))
            cx = ox + (idx + 0.5) * (pw / max(1, n))
            parts.append(render_pincallout(t, cx, _sy(hit["val"]), nt.get("text", ""), top=oy + 4))
    # under vertical bars the axis title sits right below the categories, and the legend below it
    title_row = legend_y + 12 if (_bgroups and not horizontal and (xlabel or catcol)) else None
    if title_row is not None:
        legend_y += 26
    if _bgroups:
        lx = ox
        for g in _bgroups:
            swatch = t["accent"] if _hit(highlights, g) else _bmap[g]
            parts.append(f'<rect x="{lx}" y="{legend_y}" width="12" height="12" rx="2" fill="{swatch}"/>')
            parts.append(f'<text x="{lx+18}" y="{legend_y+10}" font-size="11" font-family="{SANS}" fill="{t["ink"]}" data-role="series">{esc(g)}</text>')
            lx += 18 + len(g) * 7 + 24
    _fx = (legend_y - (oy + ph) + 28) if horizontal else (legend_y - base_y + 22)
    if xlabel or catcol:
        xlab = xlabel or ("" if horizontal else _humanize(catcol))
        if horizontal and not xlabel:
            xlab = ""
        if xlab:
            xy = title_row if title_row is not None else oy + ph + _fx
            parts.append(f'<text x="{ox+pw/2}" y="{xy}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle" data-role="xaxis">{esc(xlab)}</text>')
    ylbl = _with_unit(ylabel or (_humanize(valcol) if horizontal else _humanize(valcol)), unit)
    if horizontal:
        if ylabel or valcol:
            # under the tick labels, clear of the source line at the foot
            parts.append(f'<text x="{ox+pw/2}" y="{oy+ph+40}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle" data-role="xaxis">{esc(ylbl)}</text>')
    elif ylabel or valcol:
        parts.append(f'<text x="22" y="{oy+ph/2}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle" transform="rotate(-90 22,{oy+ph/2})">{esc(ylbl)}</text>')
    src_note = f"{len(rows)} bars" + (f" · Source: {source}" if source else "")  # what it counts, not "n ="
    parts.append(f'<text x="36" y="{H-14}" font-size="10.5" font-family="{MONO}" fill="{t["soft"]}">{esc(src_note)}</text>')
    parts.append("</svg>")
    return "\n".join(parts), W, H, len(rows)


def _lttb(pts, n):
    """Largest-Triangle-Three-Buckets: the n points that keep a long line's shape (peaks and dips)."""
    if len(pts) <= n or n < 3:
        return pts
    out, a, every = [pts[0]], 0, (len(pts) - 2) / (n - 2)
    for i in range(n - 2):
        lo, hi = int(i * every) + 1, int((i + 1) * every) + 1
        nlo, nhi = hi, min(int((i + 2) * every) + 1, len(pts))
        ax = sum(p[0] for p in pts[nlo:nhi]) / max(1, nhi - nlo)
        ay = sum(p[1] for p in pts[nlo:nhi]) / max(1, nhi - nlo)
        px, py = pts[a]
        best = max(range(lo, hi), key=lambda j: abs((px - ax) * (pts[j][1] - py) - (px - pts[j][0]) * (ay - py)))
        out.append(pts[best])
        a = best
    out.append(pts[-1])
    return out


def render_line(spec_path, xcol, ycol, title, subtitle="", figure="Fig. 1",
                groupcol=None, xlabel="", xunit="", ylabel="", yunit="",
                source="", corners="editorial", chrome=True, width=760, theme=None, notes=None,
                grid=True, markers=True, highlights=None):
    t = theme or THEME
    rows = []
    with open(spec_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        cols = r.fieldnames or []
        xc = xcol or (cols[0] if cols else "")
        yc = ycol or (cols[1] if len(cols) > 1 else (cols[0] if cols else ""))
        for row in r:
            try:
                x_val = row[xc]
                try:
                    num_x = float(x_val)
                except ValueError:
                    num_x = None
                y_val = float(row[yc])
                d = {"x_str": x_val, "x_num": num_x, "y": y_val}
                if groupcol and row.get(groupcol):
                    d["g"] = str(row[groupcol])
                rows.append(d)
            except (ValueError, KeyError, TypeError):
                continue
    if not rows:
        raise SystemExit(f"{spec_path}: no valid data in {xc}/{yc}")
    groups = sorted({d.get("g", "default") for d in rows})
    _pal = series_palette(t, highlights)
    palette = _assign_colors(groups, _pal, highlights)
    ys = [d["y"] for d in rows]
    ymin, ymax = min(ys), max(ys)
    if min(ys) >= 0:
        ymin = 0
    if ymin == ymax:
        ymax = ymin + 1
    yt = nice_ticks(ymin, ymax, n=5)
    W = width
    head_bits, head_h = figure_heading(t, title, subtitle, x=36) if chrome else ([], 12)
    H = head_h + 360 + (80 if len(groups) > 1 else 60)
    ox, oy = 80, head_h
    multi = len(groups) > 1 and groups != ["default"]
    ends = {}
    if multi:
        for g in groups:
            last = [d for d in rows if d.get("g", "default") == g][-1]
            ends[g] = f"{g} {fmt_value(last['y'])}"
    right = max([40] + [int(_text_w(v, 11, True)) + 24 for v in ends.values()])
    if multi:
        H = head_h + 360 + 60  # the end labels name the series; no legend row below the axis
    pw, ph = W - ox - right, 320
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 {W} {H}" width="{W}"><title>{esc(title)}</title>',
             f'<desc>{esc(subtitle or (xc + " vs " + yc))}</desc>',
             f'<rect width="{W}" height="{H}" fill="{t["card"]}"/>']
    parts.extend(head_bits)
    sy = lambda v: (oy + ph) - (v - yt[0]) / (yt[-1] - yt[0]) * ph if yt[-1] != yt[0] else oy + ph / 2
    for v in yt:
        y_pos = sy(v)
        if grid:
            parts.append(f'<line x1="{ox}" y1="{y_pos:.1f}" x2="{ox+pw}" y2="{y_pos:.1f}" stroke="{t["rule"]}" stroke-width="0.8"/>')
        parts.append(f'<text x="{ox-10}" y="{y_pos+4:.1f}" font-size="10" font-family="{MONO}" fill="{t["soft"]}" text-anchor="end">{esc(fmt_tick(v))}</text>')
    is_numeric_x = all(d["x_num"] is not None for d in rows)
    if is_numeric_x:
        x_nums = [d["x_num"] for d in rows]
        xmin, xmax = min(x_nums), max(x_nums)
        if xmin == xmax: xmax = xmin + 1
        xt = nice_ticks(xmin, xmax, n=5)
        sx = lambda v: ox + (v - xt[0]) / (xt[-1] - xt[0]) * pw if xt[-1] != xt[0] else ox + pw / 2
        for v in xt:
            if grid:
                parts.append(f'<line x1="{sx(v):.1f}" y1="{oy}" x2="{sx(v):.1f}" y2="{oy+ph}" stroke="{t["rule"]}" stroke-width="0.8"/>')
            parts.append(f'<text x="{sx(v):.1f}" y="{oy+ph+18}" font-size="10" font-family="{MONO}" fill="{t["soft"]}" text-anchor="middle">{esc(fmt_tick(v))}</text>')
    else:
        x_labels = []
        for d in rows:
            if d["x_str"] not in x_labels:
                x_labels.append(d["x_str"])
        n_xl = len(x_labels)
        sx_map = {lbl: ox + (i / max(1, n_xl - 1)) * pw for i, lbl in enumerate(x_labels)}
        sx = lambda lbl: sx_map[lbl]
        for lbl in x_labels:
            xp = sx(lbl)
            if grid:
                parts.append(f'<line x1="{xp:.1f}" y1="{oy}" x2="{xp:.1f}" y2="{oy+ph}" stroke="{t["rule"]}" stroke-width="0.8"/>')
            parts.append(f'<text x="{xp:.1f}" y="{oy+ph+18}" font-size="10" font-family="{MONO}" fill="{t["soft"]}" text-anchor="middle">{esc(lbl)}</text>')
    parts.append(f'<line x1="{ox}" y1="{oy+ph}" x2="{ox+pw}" y2="{oy+ph}" stroke="{t["ink"]}" stroke-width="1.2"/>')
    parts.append(f'<line x1="{ox}" y1="{oy}" x2="{ox}" y2="{oy+ph}" stroke="{t["ink"]}" stroke-width="1.2"/>')
    end_marks = []
    for g in groups:
        g_rows = [d for d in rows if d.get("g", "default") == g]
        if not g_rows:
            continue
        pts = []
        for d in g_rows:
            xp = sx(d["x_num"]) if is_numeric_x else sx(d["x_str"])
            yp = sy(d["y"])
            pts.append((xp, yp))
        # a highlighted series is coral end to end: line, dots, and legend swatch
        col = t["accent"] if len(groups) > 1 and _hit(highlights, g) else palette[g]
        if len(groups) == 1:
            poly_pts = f"{pts[0][0]:.1f},{oy+ph} " + " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts) + f" {pts[-1][0]:.1f},{oy+ph}"
            parts.append(f'<polygon points="{poly_pts}" fill="{col}" fill-opacity="0.08"/>')
        drawn = _lttb(pts, 600)  # a long series keeps its shape at a fraction of the points
        path_d = f"M{drawn[0][0]:.1f},{drawn[0][1]:.1f} " + " ".join(f"L{p[0]:.1f},{p[1]:.1f}" for p in drawn[1:])
        parts.append(f'<path d="{path_d}" fill="none" stroke="{col}" stroke-width="2.2" stroke-linecap="round"/>')
        dense = len(pts) > 80  # past this the dots merge into a band; keep the highlighted ones
        for i, (xp, yp) in enumerate(pts):
            d = g_rows[i]
            hit = _hit(highlights, d["x_str"], d.get("g"), d["x_num"])
            if (not markers or dense) and not hit:
                continue
            mcol = t["accent"] if hit else col
            rad = 5.6 if hit else 3.5
            tip = (f"{g} · " if multi else "") + f"{d['x_str']}: {fmt_tick(d['y'])}"
            parts.append(f'<circle cx="{xp:.1f}" cy="{yp:.1f}" r="{rad}" fill="{mcol}" stroke="{t["card"]}" stroke-width="1.2">'
                         f'<title>{esc(tip)}</title></circle>')
        if multi:
            end_marks.append([yp, xp, g, col])
    for nt in (notes or [])[:2]:
        ax, best, bd = nt.get("at"), None, None
        try:
            av = float(ax)
            for d in rows:
                if d["x_num"] is None:
                    continue
                delta = abs(d["x_num"] - av)
                if bd is None or delta < bd:
                    best, bd = d, delta
        except (TypeError, ValueError):
            best = next((d for d in rows if d["x_str"] == ax), None)
        if best is None:
            continue
        xp = sx(best["x_num"]) if is_numeric_x and best["x_num"] is not None else sx(best["x_str"])
        parts.append(render_pincallout(t, xp, sy(best["y"]), nt.get("text", ""), top=oy + 4))
    end_marks.sort()
    for k in range(1, len(end_marks)):
        end_marks[k][0] = max(end_marks[k][0], end_marks[k - 1][0] + 14)
    for ly, lx, g, col in end_marks:
        parts.append(f'<text x="{ox + pw + 10:.1f}" y="{ly + 4:.1f}" font-size="11" font-weight="600" font-family="{SANS}" '
                     f'fill="{col}" data-role="series">{esc(ends[g])}</text>')
    xlab = _with_unit(xlabel or _humanize(xc), xunit)
    ylab = _with_unit(ylabel or _humanize(yc), yunit)
    parts.append(f'<text x="{ox+pw/2}" y="{oy+ph+40}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle" data-role="xaxis">{esc(xlab)}</text>')
    if multi and not end_marks:
        lx, ly = ox, oy + ph + 66
        for g in groups:
            gcol = t["accent"] if _hit(highlights, g) else palette[g]
            parts.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+16}" y2="{ly}" stroke="{gcol}" stroke-width="2.5"/>')
            parts.append(f'<circle cx="{lx+8}" cy="{ly}" r="3.5" fill="{gcol}" stroke="{t["card"]}" stroke-width="1"/>')
            parts.append(f'<text x="{lx+24}" y="{ly+4}" font-size="11" font-family="{SANS}" fill="{t["ink"]}" data-role="series">{esc(g)}</text>')
            lx += 24 + len(g) * 7 + 24
    parts.append(f'<text x="24" y="{oy+ph/2}" font-size="12" font-weight="600" font-family="{SANS}" fill="{t["ink"]}" text-anchor="middle" transform="rotate(-90 24,{oy+ph/2})" data-role="yaxis">{esc(ylab)}</text>')
    src_note = f"{len(rows)} points" + (f" · Source: {source}" if source else "")  # what it counts, not "n ="
    parts.append(f'<text x="36" y="{H-14}" font-size="10.5" font-family="{MONO}" fill="{t["soft"]}">{esc(src_note)}</text>')
    parts.append("</svg>")
    return "\n".join(parts), W, H, len(rows)

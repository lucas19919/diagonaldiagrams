"""export: redraw from a receipt as PNG, PDF, SVG, draw.io or Excalidraw."""
import html, json, os, sys
from .errors import SpecError
from ._output import LAYOUTS, _RECEIPT_PATHS, _receipt_inputs
from ._text import _text_w
from ._theme import get_theme
from ._lazy import lazy
from .registry import Registry

# An export format: writer(svg, dest, receipt, args, said) prints what it wrote. said is the
# "N items" phrase for the message. export --to looks the format up here.
OUTPUTS = Registry("output")

render_chart = lazy("diagonaldiagrams.charts.render", "render_chart")
render_arch = lazy("diagonaldiagrams.diagrams", "render_arch")
render_flow = lazy("diagonaldiagrams.diagrams", "render_flow")
render_schema = lazy("diagonaldiagrams.diagrams", "render_schema")
render_seq = lazy("diagonaldiagrams.diagrams", "render_seq")
render_geo = lazy("diagonaldiagrams.geo", "render_geo")
load_spec = lazy("diagonaldiagrams.mermaid", "load_spec")
render_bar = lazy("diagonaldiagrams.plots", "render_bar")
render_line = lazy("diagonaldiagrams.plots", "render_line")
render_scatter = lazy("diagonaldiagrams.plots", "render_scatter")


def _browser():
    import shutil
    for name in ("msedge", "microsoft-edge", "chrome", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _raster_svg(svg, dest, kind, width_hint):
    """Write a PNG or PDF of the SVG. Cairo if it imports, otherwise Edge or Chrome headless.
    Returns (how, why): how is "cairosvg" or "browser", or None with why it failed."""
    import re, shutil, subprocess, tempfile
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    w = max(1, int(round(float(m.group(1))))) if m else int(width_hint)
    h = max(1, int(round(float(m.group(2))))) if m else int(width_hint * 0.75)
    try:
        import cairosvg
        kw = {"write_to": dest, "output_width": width_hint} if kind == "png" else {"write_to": dest}
        getattr(cairosvg, f"svg2{kind}")(bytestring=svg.encode("utf-8"), **kw)
        return "cairosvg", ""
    except (ImportError, OSError):
        pass
    browser = _browser()
    if not browser:
        return None, "no Edge, Chrome, or cairosvg on this machine"
    folder = tempfile.mkdtemp(prefix="graph-raster-")
    page = os.path.join(folder, "fig.html")
    html = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;padding:0;width:{w}px;height:{h}px;overflow:hidden;background:#fff}}"
            "svg{display:block;width:100%;height:100%}</style></head><body>"
            + svg + "</body></html>")
    with open(page, "w", encoding="utf-8") as f:
        f.write(html)
    url = "file:///" + os.path.abspath(page).replace("\\", "/")
    profile = os.path.join(folder, "profile")
    dest_abs = os.path.abspath(dest)
    if kind == "pdf":
        cmd = [browser, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}",
               "--no-pdf-header-footer", f"--print-to-pdf={dest_abs}", url]
    else:
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               "--force-device-scale-factor=2", f"--user-data-dir={profile}",
               f"--window-size={w},{h}", f"--screenshot={dest_abs}", url]
    import time
    if os.path.exists(dest_abs):
        os.remove(dest_abs)
    try:
        p = subprocess.run(cmd, timeout=90, capture_output=True, text=True, errors="replace")
    except (subprocess.TimeoutExpired, OSError) as e:
        shutil.rmtree(folder, ignore_errors=True)
        return None, f"{os.path.basename(browser)} did not finish: {e}"
    # Edge and Chrome on Windows can hand the job to a running browser and exit at once.
    # The file lands a second or two later, so wait for it before the page is deleted.
    last, deadline = -1, time.time() + 30
    while time.time() < deadline:
        size = os.path.getsize(dest_abs) if os.path.isfile(dest_abs) else -1
        if size > 400 and size == last:
            break
        last = size
        time.sleep(0.4)
    shutil.rmtree(folder, ignore_errors=True)
    if os.path.isfile(dest_abs) and os.path.getsize(dest_abs) > 400:
        return "browser", ""
    tail = ((p.stderr or "") + (p.stdout or "")).strip().splitlines()[-2:]
    return None, (f"{browser} ran (exit {p.returncode}) but wrote no {kind}"
                  + (f": {' / '.join(tail)}" if tail else ""))


def _svg_model(svg):
    """Boxes, decisions, arrows, and frames of a drawn flow or arch, read back from the data-*
    attributes the renderers write. The editable exports are built from this."""
    from .outline import read_figure, svg_model
    return svg_model(read_figure(svg))


def _cell_ids(model):
    """Export ids from the figure's own ids (D15): node:ID, edge:FROM->TO:LABEL, group:ID. The same
    element keeps its cell across exports of an edited spec."""
    return ({n["id"]: f"node:{n['id']}" for n in model["nodes"]},
            [f"edge:{e['id']}" for e in model["edges"]],
            [f"group:{f['id']}" for f in model["frames"]])


def _to_drawio(model, title=""):
    """draw.io (diagrams.net) file: boxes and frames keep their place, arrows keep their bends and stay
    attached to their boxes, so dragging a box drags its arrows."""
    def a(v):
        return html.escape(str(v), quote=True)
    ids, edge_ids, frame_ids = _cell_ids(model)
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for k, f in enumerate(model["frames"]):
        cells.append(f'<mxCell id="{a(frame_ids[k])}" value="{a(f["label"].upper())}" style="rounded=1;arcSize=6;dashed=1;'
                     f'fillColor=#eeeeee;strokeColor=#888888;verticalAlign=top;align=left;spacingLeft=10;fontSize=10;'
                     f'fontStyle=1;fontColor=#4f5d75;" vertex="1" parent="1"><mxGeometry x="{f["x"]:.0f}" y="{f["y"]:.0f}" '
                     f'width="{f["w"]:.0f}" height="{f["h"]:.0f}" as="geometry"/></mxCell>')
    for n in model["nodes"]:
        shape = {"diamond": "rhombus;", "oval": "rounded=1;arcSize=40;"}.get(n["shape"], "rounded=1;arcSize=8;")
        cells.append(f'<mxCell id="{a(ids[n["id"]])}" value="{a(n["label"])}" style="{shape}whiteSpace=wrap;html=1;fillColor=#ffffff;'
                     f'strokeColor={n["stroke"]};fontStyle=1;" vertex="1" parent="1"><mxGeometry x="{n["x"]:.0f}" '
                     f'y="{n["y"]:.0f}" width="{n["w"]:.0f}" height="{n["h"]:.0f}" as="geometry"/></mxCell>')
    for k, e in enumerate(model["edges"]):
        bends = "".join(f'<mxPoint x="{x:.0f}" y="{y:.0f}"/>' for x, y in e["points"][1:-1])
        style = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeColor={e['stroke']};"
                 + ("dashed=1;" if e["dashed"] else ""))
        cells.append(f'<mxCell id="{a(edge_ids[k])}" value="{a(e["label"])}" style="{style}" edge="1" parent="1" '
                     f'source="{a(ids[e["from"]])}" target="{a(ids[e["to"]])}"><mxGeometry relative="1" as="geometry">'
                     f'<Array as="points">{bends}</Array></mxGeometry></mxCell>')
    return ('<mxfile host="diagonaldiagrams"><diagram id="d1" name="' + a(title or "Page-1") + '">'
            '<mxGraphModel grid="1" gridSize="10" guides="1" connect="1" arrows="1" page="0"><root>'
            + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>\n")


def _to_excalidraw(model):
    """Excalidraw scene: shapes with their text bound inside, arrows bound to the shapes they join."""
    import zlib
    ids, edge_ids, frame_ids = _cell_ids(model)
    els = []

    def seed(eid, salt=""):  # from the id, so an unchanged element exports unchanged
        return zlib.crc32((eid + salt).encode("utf-8")) % (2 ** 31 - 1) + 1

    def base(eid, kind, x, y, w, h, **kw):
        d = {"id": eid, "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
             "strokeColor": "#2d3142", "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 1,
             "strokeStyle": "solid", "roughness": 0, "opacity": 100, "groupIds": [], "frameId": None,
             "roundness": None, "seed": seed(eid), "version": 1, "versionNonce": seed(eid, "#nonce"),
             "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False}
        d.update(kw)
        return d

    def text(eid, label, cx, cy, size, container=None):
        w = _text_w(label, size)
        return base(eid, "text", cx - w / 2, cy - size * 0.625, w, size * 1.25, text=label, originalText=label,
                    fontSize=size, fontFamily=2, textAlign="center", verticalAlign="middle",
                    containerId=container, lineHeight=1.25)
    for k, f in enumerate(model["frames"]):
        els.append(base(frame_ids[k], "rectangle", f["x"], f["y"], f["w"], f["h"], strokeStyle="dashed",
                        backgroundColor="#eeeeee", strokeColor="#888888", roundness={"type": 3}))
        els.append(text(frame_ids[k] + ":text", f["label"].upper(), f["x"] + 12 + _text_w(f["label"].upper(), 12) / 2, f["y"] + 14, 12))
    for n in model["nodes"]:
        sid = ids[n["id"]]
        tid = sid + ":text"
        kind = {"diamond": "diamond", "oval": "rectangle"}.get(n["shape"], "rectangle")
        rnd_kw = {"roundness": {"type": 3}} if n["shape"] != "diamond" else {}
        shape = base(sid, kind, n["x"], n["y"], n["w"], n["h"], backgroundColor="#ffffff", strokeColor=n["stroke"],
                     boundElements=[{"type": "text", "id": tid}], **rnd_kw)
        els.append(shape)
        els.append(text(tid, n["label"], n["x"] + n["w"] / 2, n["y"] + n["h"] / 2, 16, sid))
    shapes = {e["id"]: e for e in els}
    for k, e in enumerate(model["edges"]):
        aid = edge_ids[k]
        x0, y0 = e["points"][0]
        pts = [[x - x0, y - y0] for x, y in e["points"]]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        els.append(base(aid, "arrow", x0, y0, max(xs) - min(xs), max(ys) - min(ys), points=pts,
                        strokeColor=e["stroke"], strokeStyle="dashed" if e["dashed"] else "solid",
                        startBinding={"elementId": ids[e["from"]], "focus": 0, "gap": 2},
                        endBinding={"elementId": ids[e["to"]], "focus": 0, "gap": 2},
                        startArrowhead=None, endArrowhead="arrow", roundness={"type": 2}, elbowed=False,
                        boundElements=[{"type": "text", "id": aid + ":text"}] if e["label"] else []))
        shapes[ids[e["from"]]]["boundElements"].append({"type": "arrow", "id": aid})
        shapes[ids[e["to"]]]["boundElements"].append({"type": "arrow", "id": aid})
        if e["label"]:
            mx, my = e["points"][len(e["points"]) // 2]
            els.append(text(aid + ":text", e["label"], mx, my, 12, aid))
    return json.dumps({"type": "excalidraw", "version": 2, "source": "diagonaldiagrams", "elements": els,
                       "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None}, "files": {}}, indent=1)


def do_export(args):
    base = args.target
    for ext in (".graph.json", ".html", ".svg"):
        if base.endswith(ext):
            base = base[: -len(ext)]
    rcpt = base + ".graph.json"
    if not os.path.exists(rcpt):
        raise SpecError(f"no receipt {rcpt} — re-render with: diagonaldiagrams scatter ... -o {base}.html")
    with open(rcpt, encoding="utf-8") as f:
        r = _receipt_inputs(json.load(f), rcpt)
    # a v2 diagram receipt holds the scene it drew, so its spec file may have moved or changed
    missing = [r[k] for k in _RECEIPT_PATHS if isinstance(r.get(k), str) and not os.path.exists(r[k])
               and not (k == "spec" and r.get("scene"))]
    if missing:
        raise SpecError(f"export: the input {missing[0]} named in {rcpt} is gone. Render again from the spec.")
    cmd, lay = r.get("cmd", "scatter"), LAYOUTS[args.layout]
    theme = get_theme(args.theme or r.get("theme") or "editorial", args.theme_file)
    if not (args.theme or args.theme_file):
        theme.update(r.get("theme_overrides") or {})  # the colors the figure was drawn with (B11)
    notes = r.get("notes") or None
    note = ""
    if cmd == "scatter":
        svg, _, _, n = render_scatter(r["csv"], r.get("x"), r.get("y"), r.get("title", "Scatter"),
                                      r.get("subtitle", ""), r.get("figure", "Fig. 1"),
                                      r.get("xlabel", ""), r.get("xunit", ""), r.get("ylabel", ""),
                                      r.get("yunit", ""), r.get("group"), r.get("yerr"), r.get("facet"),
                                      r.get("source", ""), r.get("corners", "editorial"),
                                      chrome=lay["chrome"], width=lay["width"], facet_dir=lay["facet_dir"],
                                      theme=theme, grid=r.get("grid", True), markers=r.get("markers", True),
                                      highlights=r.get("highlights") or None, notes=notes)
        unit, dest = "points", args.o or f"{base}-{args.layout}.{args.to}"
    elif cmd == "bar":
        svg, _, _, n = render_bar(r["csv"], r.get("cat"), r.get("val"), r.get("title", "Bar Chart"),
                                  r.get("subtitle", ""), r.get("figure", "Fig. 1"), r.get("group"),
                                  r.get("orientation", "v"), r.get("sort", "none"), r.get("xlabel"),
                                  r.get("ylabel"), r.get("unit", ""), r.get("source", ""),
                                  r.get("corners", "editorial"), chrome=True, theme=theme,
                                  grid=r.get("grid", True), markers=r.get("markers", True),
                                  highlights=r.get("highlights") or None, notes=notes)
        unit, dest, note = "bars", args.o or f"{base}.{args.to}", " (layouts: scatter only)"
    elif cmd == "line":
        svg, _, _, n = render_line(r["csv"], r.get("x"), r.get("y"), r.get("title", "Line Trend"),
                                   r.get("subtitle", ""), r.get("figure", "Fig. 1"), r.get("group"),
                                   r.get("xlabel"), r.get("xunit", ""), r.get("ylabel"), r.get("yunit", ""),
                                   r.get("source", ""), r.get("corners", "editorial"), chrome=True, theme=theme,
                                   grid=r.get("grid", True), markers=r.get("markers", True),
                                   highlights=r.get("highlights") or None, notes=notes)
        unit, dest, note = "points", args.o or f"{base}.{args.to}", " (layouts: scatter only)"
    elif cmd in ("flow", "arch", "seq", "schema"):
        if r.get("scene"):  # v2: the scene that was drawn
            from .inputs.v1 import scene_as_v1
            spec = scene_as_v1(dict(r["scene"], version=2), cmd)
        else:
            spec = load_spec(r["spec"], cmd)
        fn = {"flow": render_flow, "arch": render_arch, "seq": render_seq, "schema": render_schema}[cmd]
        if cmd == "flow":
            svg, _, _ = render_flow(spec, r.get("corners", "editorial"), r.get("auto", False), theme)
        else:
            svg, _, _ = fn(spec, r.get("corners", "editorial"), theme)
        key = {"flow": "nodes", "arch": "nodes", "seq": "actors", "schema": "tables"}[cmd]
        n = len(spec.get(key, []))
        unit, dest, note = "items", args.o or f"{base}.{args.to}", " (diagram: single layout)"
    elif cmd == "geo":
        svg, _, _, n = render_geo(r["src"], r.get("lat"), r.get("lon"), r.get("label"), r.get("val"),
                                  r.get("title", "Map"), r.get("subtitle", ""), r.get("figure", "Fig. 1"),
                                  r.get("source", ""), theme, chrome=True,
                                  grid=r.get("grid", True), markers=r.get("markers", True),
                                  highlights=r.get("highlights") or None)
        unit, dest, note = "places", args.o or f"{base}.{args.to}", " (map: single layout)"
    elif cmd == "chart":
        svg, _, _, n = render_chart(
            r.get("kind"), r.get("src"), title=r.get("title") or "", subtitle=r.get("subtitle") or "",
            source=r.get("source") or "", theme=theme,
            x=r.get("x"), y=r.get("y"), group=r.get("group"), size=r.get("size"),
            label=r.get("label"), parent=r.get("parent"), val=r.get("val"),
            a=r.get("a"), b=r.get("b"), lo=r.get("lo"), hi=r.get("hi"),
            grid=r.get("grid", True), markers=r.get("markers", True),
            highlights=r.get("highlights") or None, unbounded=r.get("budget") is False)
        unit, dest, note = "items", args.o or f"{base}.{args.to}", " (chart: single layout)"
    else:
        raise SpecError(f"unknown receipt cmd '{cmd}'")
    writer = OUTPUTS.get(args.to)
    if writer is None:
        raise SpecError(f"no export format '{args.to}'", f"use one of: {', '.join(OUTPUTS.names())}")
    writer(svg, dest, r, args, f"{n} {unit}{note}")


@OUTPUTS.add("svg")
def _write_svg(svg, dest, r, args, said):
    with open(dest, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {dest} ({said})")


def _editable(to):
    def write(svg, dest, r, args, said):
        model = _svg_model(svg)
        if not model["nodes"]:
            raise SpecError(f"{to} export covers figures of boxes and arrows (flow, arch, schema, Mermaid flowcharts, "
                            f"and the dag, integration and swim charts); this figure is a {r.get('cmd', 'figure')}")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(_to_drawio(model, r.get("title") or "") if to == "drawio" else _to_excalidraw(model))
        print(f"wrote {dest} ({len(model['nodes'])} boxes, {len(model['edges'])} arrows, {len(model['frames'])} frames)")
    return write


OUTPUTS.add("drawio")(_editable("drawio"))
OUTPUTS.add("excalidraw")(_editable("excalidraw"))


def _raster(svg, dest, r, args, said):
    how, why = _raster_svg(svg, dest, args.to, args.width)
    if not how:
        raise SpecError(f"{args.to} export failed: {why}. "
                        "--to svg needs nothing, and the HTML page has an Export PNG button.")
    print(f"wrote {dest} via {how} ({said})")


OUTPUTS.add("png")(_raster)
OUTPUTS.add("pdf")(_raster)

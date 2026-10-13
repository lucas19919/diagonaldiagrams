"""render_chart: dispatch, aliases, and validation for `chart <kind>`."""
import json
from .._issues import _vissue
from .._theme import THEME
from ..charts._base import _col, _load_input
from ..charts.catalog import CHART_ALIAS, _CHART_BLURB
from ..charts.kinds import (
    _c_beeswarm, _c_box, _c_bpmn, _c_bubble, _c_bump, _c_calendar, _c_candle, _c_choropleth, _c_cluster,
    _c_combo, _c_context, _c_contour, _c_current, _c_dag, _c_deploy, _c_donut, _c_dtree, _c_dumbbell, _c_er,
    _c_fishbone, _c_flywheel, _c_force, _c_forest, _c_funnel, _c_gantt, _c_heatgeo, _c_heatmap, _c_histogram,
    _c_icicle, _c_integration, _c_journey, _c_kanban, _c_kg, _c_layers, _c_nested, _c_od, _c_org, _c_pie,
    _c_polar, _c_qq, _c_quadrant, _c_radar, _c_radial, _c_ridgeline, _c_sankey, _c_slope, _c_stack, _c_state,
    _c_status, _c_step, _c_story, _c_stream, _c_strip, _c_sunburst, _c_swim, _c_timeline, _c_tree,
    _c_treemap, _c_uml, _c_venn, _c_violin, _c_volcano, _c_waffle, _c_wardley, _c_waterfall,
)
from ..charts.mathplot import _c_math, _math_compile_item, _math_from_text, _math_items
from .._lazy import lazy

render_arch = lazy("diagonaldiagrams.diagrams", "render_arch")
render_flow = lazy("diagonaldiagrams.diagrams", "render_flow")
render_seq = lazy("diagonaldiagrams.diagrams", "render_seq")
render_geo = lazy("diagonaldiagrams.geo", "render_geo")
load_spec = lazy("diagonaldiagrams.mermaid", "load_spec")
_validate_spec_dict = lazy("diagonaldiagrams.validate", "_validate_spec_dict")


_CHART_FN = {
    "bubble": _c_bubble, "beeswarm": _c_beeswarm, "step": _c_step, "slope": _c_slope,
    "bump": _c_bump, "ridgeline": _c_ridgeline, "stack": _c_stack, "dumbbell": _c_dumbbell,
    "waterfall": _c_waterfall, "histogram": _c_histogram, "box": _c_box, "violin": _c_violin,
    "strip": _c_strip, "pie": _c_pie, "donut": _c_donut, "waffle": _c_waffle,
    "treemap": _c_treemap, "icicle": _c_icicle, "sunburst": _c_sunburst, "heatmap": _c_heatmap,
    "calendar": _c_calendar, "radar": _c_radar, "polar": _c_polar, "candle": _c_candle,
    "status": _c_status, "forest": _c_forest, "qq": _c_qq, "volcano": _c_volcano,
    "sankey": _c_sankey, "stream": _c_stream, "funnel": _c_funnel, "combo": _c_combo,
    "quadrant": _c_quadrant, "contour": _c_contour, "math": _c_math, "dag": _c_dag, "force": _c_force,
    "radial": _c_radial, "tree": _c_tree, "dtree": _c_dtree, "nested": _c_nested,
    "kg": _c_kg, "context": _c_context, "uml": _c_uml, "deploy": _c_deploy,
    "layers": _c_layers, "integration": _c_integration, "current": _c_current, "er": _c_er,
    "wardley": _c_wardley, "swim": _c_swim, "state": _c_state, "bpmn": _c_bpmn,
    "fishbone": _c_fishbone, "flywheel": _c_flywheel, "kanban": _c_kanban, "gantt": _c_gantt,
    "timeline": _c_timeline, "journey": _c_journey, "story": _c_story, "org": _c_org,
    "venn": _c_venn, "choropleth": _c_choropleth, "heatgeo": _c_heatgeo, "od": _c_od,
    "cluster": _c_cluster,
}


def _render_alias(kind, path, title, subtitle, source, theme, x, y, label, val, grid, markers_on, highlights):
    base = CHART_ALIAS[kind]
    if base == "geo":
        svg, W, H, n = render_geo(path, y, x, label, val, title or "Map", subtitle, "Fig. 1", source, theme,
                                  grid=grid, markers=markers_on, highlights=highlights)
        return svg, W, H, n
    spec = load_spec(path)
    if title:
        spec["title"] = title
    if subtitle:
        spec["sub"] = subtitle
    if base == "flow":
        svg, W, H = render_flow(spec, "editorial", False, theme)
        n = len(spec.get("nodes", []))
    elif base == "arch":
        svg, W, H = render_arch(spec, "editorial", theme)
        n = len(spec.get("nodes", []))
    else:
        svg, W, H = render_seq(spec, "editorial", theme)
        n = len(spec.get("actors", []))
    return svg, W, H, n


def render_chart(kind, path, title="", subtitle="", source="", theme=None, x=None, y=None, group=None,
                 size=None, label=None, parent=None, val=None, a=None, b=None, lo=None, hi=None,
                 grid=True, markers=True, highlights=None, unbounded=False):
    """Draw one taxonomy chart. Aliases call flow, arch, seq, or geo. terrain and print refuse."""
    kind = str(kind or "").strip().lower()
    if kind not in _CHART_BLURB:
        raise SystemExit(f"unknown chart type '{kind}'. Run: py graph.py describe")
    if kind == "terrain":
        raise SystemExit("terrain is not drawn. A DEM raster is outside this library. Use contour for a z grid.")
    if kind == "print":
        raise SystemExit("print is not a separate drawing. Use geo, then export --to pdf.")
    t = theme or THEME
    if kind in CHART_ALIAS:
        return _render_alias(kind, path, title, subtitle, source, t, x, y, label, val, grid, markers, highlights)
    if kind == "math" and not str(path).lower().endswith(".json"):
        try:
            spec, rows = _math_from_text(path), []
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc))
    else:
        spec, rows = _load_input(path)
    if isinstance(spec, dict):
        title = title or spec.get("title") or kind
        subtitle = subtitle or spec.get("sub") or spec.get("subtitle") or ""
    else:
        title = title or kind
    opt = {"title": title, "sub": subtitle, "source": source, "t": t, "x": x, "y": y, "group": group,
           "size": size, "label": label, "parent": parent, "val": val, "a": a, "b": b, "lo": lo, "hi": hi,
           "grid": grid, "markers": markers, "highlights": highlights or [], "unbounded": unbounded, "spec": spec}
    if spec is None and not rows:
        raise SystemExit(f"{path}: no rows")
    return _CHART_FN[kind](spec, rows, opt)


_CSV_NEED = {
    "bubble": ("x", "y", "size"), "beeswarm": ("cat", "val"), "step": ("x", "y"),
    "slope": ("cat", "a", "b"), "bump": ("x", "name", "rank"), "ridgeline": ("group", "val"),
    "stack": ("cat", "group", "val"), "dumbbell": ("cat", "a", "b"), "waterfall": ("cat", "val"),
    "histogram": ("val",), "box": ("group", "val"), "violin": ("group", "val"), "strip": ("group", "val"),
    "pie": ("cat", "val"), "donut": ("cat", "val"), "waffle": ("cat", "val"), "funnel": ("cat", "val"),
    "treemap": ("name", "val"), "icicle": ("name", "val"), "sunburst": ("name", "val"),
    "heatmap": ("x", "y", "val"), "calendar": ("date", "val"), "radar": ("axis", "series", "val"),
    "polar": ("cat", "val"), "candle": ("x", "open", "high", "low", "close"),
    "status": ("row", "col", "state"), "forest": ("cat", "est", "lo", "hi"), "qq": ("val",),
    "volcano": ("x", "y"), "sankey": ("src", "dst", "val"), "stream": ("x", "group", "val"),
    "combo": ("x", "bar", "line"), "quadrant": ("x", "y"), "contour": ("x", "y", "z"),
    "heatgeo": ("lat", "lon", "val"), "od": ("lon", "lat", "lon2", "lat2"), "cluster": ("lat", "lon"),
}


_JSON_NEED = {
    "dag": ("nodes", "edges"), "force": ("nodes", "edges"), "radial": ("nodes",),
    "tree": ("nodes",), "dtree": ("nodes",), "nested": ("nodes",), "kg": ("nodes", "edges"),
    "context": ("nodes",), "uml": ("nodes",), "deploy": ("zones",), "layers": ("layers",),
    "integration": ("nodes",), "current": ("nodes",), "er": ("entities",), "wardley": ("nodes",),
    "swim": ("lanes", "nodes"), "state": ("nodes",), "bpmn": ("nodes",), "fishbone": ("ribs",),
    "flywheel": ("nodes",), "kanban": ("columns",), "gantt": ("tasks",), "timeline": ("events",),
    "journey": ("stages",), "story": ("releases",), "org": ("nodes",), "venn": ("sets",),
    "choropleth": ("features",),
}


_EXPLICIT_ROLE = {"x": "x", "y": "y", "group": "group"}


def _validate_math_spec(spec, errors, warnings):
    try:
        curves = [_math_compile_item(item) for item in _math_items(spec)]
    except ValueError as exc:
        _vissue(errors, warnings, "E", str(exc), "use y=f(x), (x(t), y(t)), or f(x,y)=0")
        return
    if spec.get("budget", True) is not False and len(curves) > 8:
        _vissue(errors, warnings, "E", f"{len(curves)} equations > 8", "split the figure, or set budget false")
    if sum(1 for curve in curves if curve.get("focal")) > 2:
        _vissue(errors, warnings, "E", "focal on >2 equations erases signal", "keep 1-2 focal curves")


def _validate_chart(kind, target, args, errors, warnings):
    if kind in ("terrain", "print"):
        _vissue(errors, warnings, "E", _CHART_BLURB[kind], "pick a type that draws")
        return
    if kind == "math":
        try:
            spec = load_spec(target) if str(target).lower().endswith(".json") else _math_from_text(target)
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as exc:
            _vissue(errors, warnings, "E", f"unreadable spec: {exc}", "pass JSON equations or a text file")
            return
        if not isinstance(spec, dict):
            _vissue(errors, warnings, "E", "spec is not an object", "pass a JSON object")
            return
        if getattr(args, "no_budget", False):
            spec = dict(spec, budget=False)
        _validate_math_spec(spec, errors, warnings)
        return
    base = CHART_ALIAS.get(kind)
    if base in ("flow", "arch", "seq"):
        try:
            spec = load_spec(target)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            _vissue(errors, warnings, "E", f"unreadable spec: {exc}", "pass a JSON spec")
            return
        _validate_spec_dict(spec, errors, warnings)
        return
    if base == "geo" or kind in ("heatgeo", "cluster", "od"):
        if not str(target).lower().endswith(".csv") and base == "geo":
            return
    if kind in _JSON_NEED and not str(target).lower().endswith(".csv"):
        try:
            spec = load_spec(target)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            _vissue(errors, warnings, "E", f"unreadable spec: {exc}", "pass JSON")
            return
        if not isinstance(spec, dict):
            _vissue(errors, warnings, "E", "spec is not an object", "pass a JSON object")
            return
        for key in _JSON_NEED[kind]:
            if key not in spec:
                _vissue(errors, warnings, "E", f"missing '{key}'", _CHART_BLURB.get(kind, ""))
        return
    if kind not in _CSV_NEED and kind not in ("heatgeo", "cluster", "od", "point"):
        return
    import csv as _csv
    try:
        with open(target, newline="", encoding="utf-8") as f:
            rd = _csv.DictReader(f)
            cols, body = rd.fieldnames or [], list(rd)
    except FileNotFoundError:
        _vissue(errors, warnings, "E", f"file not found: {target}", "")
        return
    if not cols:
        _vissue(errors, warnings, "E", "no header row", "add a header")
        return
    roles = _CSV_NEED.get(kind, ())
    explicit = {"x": getattr(args, "x", None), "y": getattr(args, "y", None), "group": getattr(args, "group", None)}
    # map a couple of CLI flags onto the roles this type actually uses
    role_flag = {}
    if "x" in roles:
        role_flag["x"] = explicit["x"]
    if "y" in roles:
        role_flag["y"] = explicit["y"]
    if "group" in roles:
        role_flag["group"] = explicit["group"]
    fake = [{c: "" for c in cols}]
    for role in roles:
        if not _col(fake, role_flag.get(role), role):
            _vissue(errors, warnings, "E", f"need a {role} column in {cols}", "rename the header or pass the matching flag")
    if len(body) > 400:
        warnings.append({"msg": f"n={len(body)} rows", "fix": "aggregate, or pass --no-budget at render time"})


_missing_charts = [k for k in _CHART_BLURB if k not in CHART_ALIAS and k not in ("terrain", "print") and k not in _CHART_FN]


if _missing_charts:
    raise RuntimeError("chart types without a renderer: " + ", ".join(_missing_charts))

"""validate and infer."""
import json, os
from ._draw import ICONS
from ._issues import _SPEC_KEYS, _vissue
from ._text import _wrap_px
from .charts.catalog import _CHART_BLURB
from .mermaid import load_spec
from ._lazy import lazy

_validate_chart = lazy("diagonaldiagrams.charts.render", "_validate_chart")
_validate_math_spec = lazy("diagonaldiagrams.charts.render", "_validate_math_spec")


def do_validate(args):
    vtype = getattr(args, "type", None) or "scatter"
    kind = vtype if vtype in ("flow", "arch", "seq", "schema") else None  # a diagram spec of that kind
    roles = {f: getattr(args, f, None) for f in ("size", "label", "parent", "val", "a", "b", "lo", "hi")}
    errors, warnings = _validate_target(args.target, vtype, args.x, args.y, args.group, args.facet, kind=kind,
                                        roles=roles)
    ok = not errors
    print(json.dumps({"ok": ok, "errors": errors, "warnings": warnings}, indent=2))
    return 0 if ok else 1


def _validate_target(target, vtype="scatter", x=None, y=None, group=None, facet=None, kind=None, unbounded=False,
                     roles=None):
    """Every check `validate` runs, as (errors, warnings). Render calls it before drawing.
    roles: the other column flags a chart type reads (size, label, parent, val, a, b, lo, hi)."""
    from types import SimpleNamespace
    args = SimpleNamespace(target=target, type=vtype, x=x, y=y, group=group, facet=facet, no_budget=unbounded,
                           **(roles or {}))
    errors, warnings = [], []
    if vtype in ("terrain", "print"):
        _validate_chart(vtype, target, args, errors, warnings)
        return errors, warnings
    if not os.path.isfile(target):
        return [{"msg": f"no file {target}", "fix": "check the path; write the spec or CSV first"}], []
    if vtype in _CHART_BLURB:
        _validate_chart(vtype, args.target, args, errors, warnings)
        return errors, warnings
    if args.target.endswith(".csv"):
        import csv as _csv
        try:
            with open(args.target, newline="", encoding="utf-8") as f:
                rd = _csv.DictReader(f)
                cols, rows = rd.fieldnames or [], list(rd)
        except (FileNotFoundError, UnicodeDecodeError) as e:
            return [{"msg": f"unreadable CSV {args.target}: {e}", "fix": "save it as UTF-8 with a header row"}], []
        if not cols:
            errors.append({"msg": "no header row"})
        else:
            vtype = getattr(args, "type", "scatter") or "scatter"
            if vtype == "bar":
                cat, val = args.x, args.y
                if cat and cat not in cols:
                    _vissue(errors, warnings, "E", f"category column '{cat}' not in {cols}", f"use one of {cols}")
                if val and (val not in cols or not all(_numok(r.get(val, "")) for r in rows[:50] if (r.get(val) or "") != "")):
                    _vissue(errors, warnings, "E", f"value column '{val}' missing or non-numeric", "pick a numeric column")
                if cat in (cols or []) and len({r[cat] for r in rows}) > 12:
                    warnings.append({"msg": f"{len({r[cat] for r in rows})} categories > 12", "fix": "sort top-11 + Other"})
                if len(rows) > 24:
                    warnings.append({"msg": f"{len(rows)} bars > 24", "fix": "aggregate or top-N"})
            elif vtype == "geo":
                lon, lat = args.x, args.y
                if not lon:
                    lon = next((c for c in cols if c.lower() in ("lon", "lng", "long", "longitude")), None)
                if not lat:
                    lat = next((c for c in cols if c.lower() in ("lat", "latitude")), None)
                if not lon or lon not in cols or not lat or lat not in cols:
                    _vissue(errors, warnings, "E", f"need lat and lon columns, got {cols}", "pass --x lon --y lat")
                else:
                    bad = 0
                    for row in rows:
                        try:
                            la, lo = float(row[lat]), float(row[lon])
                            if not (-90 <= la <= 90 and -180 <= lo <= 180):
                                bad += 1
                        except (TypeError, ValueError):
                            bad += 1
                    if bad:
                        _vissue(errors, warnings, "E", f"{bad} rows with bad lat/lon", "lat -90..90, lon -180..180")
                    if len(rows) > 400:
                        warnings.append({"msg": f"n={len(rows)} points", "fix": "aggregate to the area you want to show"})
            elif vtype == "line":
                if args.x and args.x not in cols:
                    _vissue(errors, warnings, "E", f"x column '{args.x}' not in {cols}", f"use one of {cols}")
                if args.y and (args.y not in cols or not all(_numok(r.get(args.y, "")) for r in rows[:50] if (r.get(args.y) or "") != "")):
                    _vissue(errors, warnings, "E", f"y column '{args.y}' missing or non-numeric", "pick a numeric column")
                if args.group and args.group in cols and len({r[args.group] for r in rows}) > 6:
                    warnings.append({"msg": f"{len({r[args.group] for r in rows})} series > 6", "fix": "keep top series"})
                if len(rows) > 400:
                    warnings.append({"msg": f"n={len(rows)} points, over budget", "fix": "downsample or facet"})
            else:
                for c in (args.x, args.y):
                    if c and c not in cols:
                        _vissue(errors, warnings, "E", f"column '{c}' not in {cols}", f"use one of {cols}")
                num = [c for c in cols if all(_numok(r.get(c, "")) for r in rows[:50] if r.get(c, "") != "")]
                if len(num) < 2:
                    _vissue(errors, warnings, "E", f"need 2 numeric cols, found {num}", "check delimiter/headers")
                if len(rows) > 400:
                    warnings.append({"msg": f"n={len(rows)}: drawn as small dots" + (", 5,000 of them sampled" if len(rows) > 5000 else ""),
                                     "fix": "aggregate or --facet split if the cloud hides the pattern"})
                for c in (args.group, args.facet):
                    if c and c in cols and len({r[c] for r in rows}) > 8:
                        warnings.append({"msg": f"'{c}' has {len({r[c] for r in rows})} distinct values", "fix": "keep top-7 + Other"})
    else:
        try:
            spec = load_spec(args.target, kind)
        except (FileNotFoundError, json.JSONDecodeError, SystemExit, ValueError) as e:
            return [{"msg": f"the JSON can't be read: {_json_where(e)}", "fix": "use double quotes, and no trailing commas or comments"}], []
        if isinstance(spec, dict) and (spec.get("equations") or spec.get("expr")) and "nodes" not in spec and "actors" not in spec:
            _validate_math_spec(spec, errors, warnings)
        else:
            _validate_spec_dict(spec, errors, warnings, kind)
            if not errors and isinstance(spec, dict):
                errors.extend(_brand(args.target, spec, kind))
    return errors, warnings


def _brand(target, spec, kind):
    """The project's brand policy (diagonaldiagrams.toml, DESIGN 22.4) checked the way render checks it."""
    from . import config
    from .errors import SpecError
    from .inputs.v1 import KINDS, detect
    try:
        cfg = config.load(target)
    except SpecError as e:
        return [{"msg": e.msg, "fix": e.fix}]
    if not (cfg.policies or cfg.palette is not None or cfg.fonts is not None):
        return []
    from .style.styler import Styler
    sheets = list(cfg.sheets) + ([{"name": "the config's fonts", "fonts": cfg.font_files}] if cfg.font_files else [])
    sheets += [dict(p, policy=True) for p in cfg.policies]
    try:
        return Styler(spec, kind if kind in KINDS else detect(spec), sheets=sheets).off_brand(cfg.palette, cfg.fonts)
    except SpecError as e:
        return [{"msg": e.msg, "fix": e.fix}]


def _json_where(e):
    if isinstance(e, json.JSONDecodeError):
        return f"line {e.lineno} column {e.colno}: {e.msg}"
    return str(e)


def _a_pin(pin):
    """Numbers x and y, and z in 3D, as a scene's pin is (scene/normalize.py)."""
    return (isinstance(pin, dict) and "x" in pin and "y" in pin and set(pin) <= {"x", "y", "z"}
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in pin.values()))


def _validate_spec_dict(spec, errors, warnings, kind=None):
    """Shared diagram-spec checks for `validate` + `doc`. Appends E/W dicts."""
    if not _structure_ok(spec, errors, warnings, kind):
        return
    if isinstance(spec, dict) and (spec.get("style") is not None or any(
            isinstance(el, dict) and "style" in el for k in ("nodes", "edges", "actors", "messages", "tables", "relations")
            for el in spec.get(k) or [])):
        from .style.styler import check_styles
        errors.extend(check_styles(spec, kind))
    if "actors" in spec or "messages" in spec:
        actors, messages = spec.get("actors", []), spec.get("messages", [])
        a_ids = [a.get("id") for a in actors]
        if len(set(a_ids)) != len(a_ids):
            _vissue(errors, warnings, "E", "duplicate actor ids", "make actor ids unique")
        if len(actors) > 6 and spec.get("budget", True) is not False:
            _vissue(errors, warnings, "W", f"{len(actors)} actors: past 6 a sequence gets hard to read", "split it into sub-sequences if it does; budget false hides this")
        if len(messages) > 16 and spec.get("budget", True) is not False:
            _vissue(errors, warnings, "W", f"{len(messages)} messages: past 16 a sequence gets hard to read", "keep the main exchange if it does; budget false hides this")
        if sum(1 for a in actors if a.get("focal")) > 2:
            _vissue(errors, warnings, "E", "focal on >2 actors erases signal", "max 2 focal actors")
        for m in messages:
            for k in ("from", "to"):
                if m.get(k) not in a_ids:
                    _vissue(errors, warnings, "E", f"a message names '{m.get(k)}', which is not an actor", f"use one of: {', '.join(map(str, a_ids))}")
    elif "tables" in spec or "relations" in spec:
        tables, relations = spec.get("tables", []), spec.get("relations", [])
        t_ids = [t.get("id") for t in tables]
        if len(set(t_ids)) != len(t_ids):
            _vissue(errors, warnings, "E", "duplicate table ids", "make table ids unique")
        if len(tables) > 6 and spec.get("budget", True) is not False:
            _vissue(errors, warnings, "W", f"{len(tables)} tables: past 6 a schema gets hard to read", "split it into views if it does; budget false hides this")
        if sum(1 for t in tables if t.get("focal")) > 2:
            _vissue(errors, warnings, "E", "focal on >2 tables erases signal", "max 2 focal tables")
        for t in tables:
            cols = t.get("columns", [])
            if len(cols) > 12:
                warnings.append({"msg": f"table '{t.get('id')}' has {len(cols)} columns (>12)", "fix": "hide non-essential columns"})
        for rel in relations:
            if rel.get("from") not in t_ids or rel.get("to") not in t_ids:
                _vissue(errors, warnings, "E", f"a relation names '{rel.get('from') if rel.get('from') not in t_ids else rel.get('to')}', which is not a table", f"use one of: {', '.join(map(str, t_ids))}")
    else:
        nodes, edges = spec.get("nodes", []), spec.get("edges", [])
        ids = [n.get("id") for n in nodes]
        if len(set(ids)) != len(ids):
            _vissue(errors, warnings, "E", "duplicate node ids", "make ids unique")
        for n in nodes:  # a pin is drawn (DESIGN 4.6), so it must be one
            pin = n.get("pin") if isinstance(n, dict) else None
            if pin is not None and not _a_pin(pin):
                errors.append({"code": "bad-value", "msg": f"node '{n.get('id')}' has pin {pin!r}; a pin is numbers x and y, "
                               "where the box's middle goes", "fix": 'write "pin": {"x": 120, "y": 80}, or drop it'})
        for e in edges:
            for k in ("from", "to"):
                if e.get(k) not in ids:
                    _vissue(errors, warnings, "E", f"an arrow {'starts at' if k == 'from' else 'goes to'} '{e.get(k)}', but there is no node with that id",
                            f"add a node with id '{e.get(k)}', or use one of: {', '.join(map(str, ids))}")
        homes = {}
        for g in spec.get("groups") or []:
            if not isinstance(g, dict) or g.get("id") is None:
                _vissue(errors, warnings, "E", f"group {g} has no id", 'write {"id": "core", "name": "Core", "nodes": ["a", "b"]}')
                continue
            members = g.get("nodes") or g.get("members") or []
            unknown = [m for m in members if m not in ids]
            members = members or [n.get("id") for n in nodes if n.get("group") == g["id"]]
            if unknown:
                _vissue(errors, warnings, "E", f"group '{g['id']}' names unknown nodes {unknown}", f"use ids from {ids}")
            if not members:
                _vissue(errors, warnings, "E", f"group '{g['id']}' lists no nodes, so no frame is drawn",
                        'list its node ids: "nodes": ["a", "b"]')
            for m in members:
                if m in homes and homes[m] != g["id"]:
                    _vissue(errors, warnings, "E", f"node '{m}' is in groups '{homes[m]}' and '{g['id']}'",
                            "a node sits in one frame; keep it in one group")
                homes.setdefault(m, g["id"])
        if spec.get("budget", True) is not False:
            if len(nodes) > 9:
                _vissue(errors, warnings, "W", f"{len(nodes)} nodes: past 9 a figure gets hard to read", "split it into overview and detail views if it does; budget false hides this")
            if len(edges) > 12:
                _vissue(errors, warnings, "W", f"{len(edges)} edges: past 12 a figure gets hard to read", "drop arrows the layout already shows if it does; budget false hides this")
        if sum(1 for n in nodes if n.get("focal")) > 2:
            _vissue(errors, warnings, "E", "focal on >2 nodes erases signal", "keep 1-2 focal, demote rest")
        from collections import Counter
        outdeg = Counter(e["from"] for e in edges if "from" in e)
        shapes = {n["id"]: n.get("shape", "rect") for n in nodes}
        for nid, deg in outdeg.items():
            if shapes.get(nid) == "diamond" and deg > 3:
                _vissue(errors, warnings, "E", f"diamond '{nid}' has {deg} exits", "nest diamonds")
        unlabeled = []
        for e in edges:
            if shapes.get(e.get("from")) == "diamond" and not e.get("label") and e.get("from") not in unlabeled:
                unlabeled.append(e.get("from"))
        for nid in unlabeled:
            warnings.append({"msg": f"unlabeled exit from diamond '{nid}'", "fix": "label Yes/No or condition"})


def _numok(v):
    import math
    try:
        return math.isfinite(float(v))
    except (ValueError, TypeError):
        return False


def _structure_ok(spec, errors, warnings, kind=None):
    """The shape every diagram renderer assumes. Run first, so a malformed spec
    gets a sentence and a fix, not a traceback."""
    if not isinstance(spec, dict):
        _vissue(errors, warnings, "E", f"the spec is a JSON {type(spec).__name__}, not an object",
                'wrap it: {"title": "...", "nodes": [...], "edges": [...]}')
        return False
    warnings.extend(spec.get("_warnings") or [])
    if spec.get("_errors"):
        errors.extend(spec["_errors"])
        return False
    have = next((k for k in ("nodes", "actors", "tables") if k in spec), None)
    want = _SPEC_KEYS.get(kind)
    if want and want not in spec:
        other = {"nodes": "flow or arch", "actors": "seq", "tables": "schema"}.get(have)
        _vissue(errors, warnings, "E", f"{kind} needs a '{want}' list" + (f"; this spec has '{have}', which is a {other} spec" if other else ""),
                f"run `describe {kind}` for the shape" + (f", or render it with {other}" if other else ""))
        return False
    lists = {"nodes": ("id", "name"), "edges": ("from", "to"), "actors": ("id",),
             "messages": ("from", "to"), "tables": ("id",), "relations": ("from", "to")}
    main = want or have
    if main and isinstance(spec.get(main), list) and not spec[main]:
        warnings.append({"msg": f"'{main}' is empty, so the figure has nothing in it",
                         "fix": f"add at least one item to '{main}' (describe {kind or 'flow'} shows one)"})
    ok = True
    for key, need in lists.items():
        if key not in spec:
            continue
        items = spec[key]
        if not isinstance(items, list):
            _vissue(errors, warnings, "E", f"'{key}' is a {type(items).__name__}, not a list", f"make '{key}' a JSON array of objects")
            ok = False
            continue
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                eg = "{" + ", ".join(f'"{k}": "..."' for k in need) + "}"
                _vissue(errors, warnings, "E", f"{key}[{i}] is {json.dumps(it)[:40]}, not an object", f"write it as {eg}")
                ok = False
                break
            miss = [k for k in need if k not in it or it[k] in (None, "")]
            if key in ("nodes", "actors", "tables") and miss == ["name"]:
                continue  # a name falls back to the id
            if miss:
                _vissue(errors, warnings, "E", f"{key}[{i}] has no '{miss[0]}'", f"every item in '{key}' needs {', '.join(need)}")
                ok = False
                break
    for i, n in enumerate(spec.get("nodes") or []):
        if not isinstance(n, dict):
            break
        for k in ("rank", "lane"):
            if k in n and (isinstance(n[k], bool) or not isinstance(n[k], (int, float))):
                _vissue(errors, warnings, "E", f"nodes[{i}] '{n.get('id')}': {k} is {json.dumps(n[k])}, not a number",
                        f"{k} is an integer" + (": -1 left, 0 center, 1 right" if k == "lane" else ": 0 is the top row"))
                ok = False
        if kind == "flow" and n.get("shape") not in (None, "oval", "rect", "diamond", "dot"):
            warnings.append({"msg": f"node '{n.get('id')}' shape '{n.get('shape')}' draws as rect",
                             "fix": "oval | rect | diamond | dot"})
        if kind in ("flow", "arch") and isinstance(n.get("name", ""), str):
            dia = kind == "flow" and n.get("shape") == "diamond"
            need = len(_wrap_px(n.get("name", ""), 100 if dia else 144, 12, True, 99))
            if need > 3:
                warnings.append({"msg": f"node '{n.get('id')}' name needs {need} lines, so its box grows taller than the rest",
                                 "fix": "shorten it" + ("; a decision is a short question" if dia else "; put detail in sub")})
        if n.get("icon") and n.get("icon") not in ICONS:
            warnings.append({"msg": f"node '{n.get('id')}' icon '{n.get('icon')}' is not built in; drawn without it",
                             "fix": "one of " + ", ".join(sorted(ICONS))})
        if kind == "flow" and n.get("shape") == "diamond" and n.get("sub"):
            warnings.append({"msg": f"diamond '{n.get('id')}' does not draw its sub",
                             "fix": "put the detail in the step before the decision"})
    return ok


def do_infer(args):
    import csv as _csv
    with open(args.target, newline="", encoding="utf-8") as f:
        rd = _csv.DictReader(f)
        cols, rows = rd.fieldnames or [], list(rd)
    numeric = [c for c in cols if rows and all(_numok(r.get(c, "")) for r in rows[:50] if (r.get(c) or "") != "")]
    cats = {}
    for c in cols:
        if c not in numeric:
            vals = sorted({r[c] for r in rows if r.get(c)})
            if 1 < len(vals) <= 12:
                cats[c] = vals
    err = next((c for c in cols if any(k in c.lower() for k in ("err", "sd", "_sd", "ci", "sem")) and c in numeric), None)
    nums = [c for c in numeric if c != err]
    if len(nums) < 2:
        print(json.dumps({"ok": False, "fix": "need 2 numeric columns", "columns": cols})); return 1
    ck = list(cats)
    group = ck[0] if ck and len(cats[ck[0]]) <= 8 else None
    facet = next((c for c in ck[1:] if len(cats[c]) <= 4), None)
    name = os.path.splitext(os.path.basename(args.target))[0].replace("_", " ")
    out = {"ok": True, "cmd": "scatter", "csv": args.target, "x": nums[0], "y": nums[1],
           "title": name.capitalize(), "subtitle": "", "figure": "Fig. 1",
           "xlabel": nums[0], "xunit": "", "ylabel": nums[1], "yunit": "",
           "group": group, "yerr": err, "facet": facet, "source": os.path.basename(args.target),
           "groups_found": {k: v for k, v in cats.items()},
           "render": f"diagonaldiagrams scatter {args.target} --x {nums[0]} --y {nums[1]}"
                     + (f" --group {group}" if group else "") + (f" --yerr {err}" if err else "")
                     + (f" --facet {facet}" if facet else "") + " -o out/inferred.html",
           "next": "edit title/subtitle/units, then validate + render"}
    print(json.dumps(out, indent=2))

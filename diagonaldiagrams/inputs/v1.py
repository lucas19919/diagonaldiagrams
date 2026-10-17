"""v1 specs and scenes, both ways (DESIGN 14.6).

from_v1() turns a flow, arch, seq or schema spec into scene JSON with that preset. to_v1() turns a
scene back into the spec today's renderers draw, which is how a v2 scene renders until the layout
kernels (P4) read scenes directly. For a v1 spec the round trip draws the same bytes; the golden
corpus checks it.

Fields only a scene has (style, class, pin, constraints, ...) are written into the v1 spec under
their scene names. Today's renderers ignore them and from_v1() reads them back, so a patch applied
to a v1 file (scene/patch.py) is kept there.
"""
from ..errors import SpecError
from ..scene.ids import EdgeIds

KINDS = ("flow", "arch", "seq", "schema")
LAYOUTS = {"flow": {"type": "layered", "ranks": "explicit-then-index"}, "arch": {"type": "layered", "ranks": "explicit"},
           "seq": "sequence", "schema": "table"}  # what each preset's v1 renderer does
EDGE_FLAGS = ("label", "proto", "async_", "reply", "focal")  # in the order v1 specs write them


def detect(spec):
    """The v1 kind a spec reads as."""
    if "actors" in spec or "messages" in spec:
        return "seq"
    if "tables" in spec or "relations" in spec:
        return "schema"
    nodes = [n for n in spec.get("nodes") or [] if isinstance(n, dict)]
    edges = [e for e in spec.get("edges") or [] if isinstance(e, dict)]
    if any("layer" in n for n in nodes) or any("proto" in e for e in edges):
        return "arch"
    return "flow"


def _items(spec, key):
    v = spec.get(key)
    return v if isinstance(v, list) else None


def from_v1(spec, kind=None):
    """Scene JSON for a v1 spec. Anything the mapping doesn't name is carried over as given, so
    normalize() reports it and to_v1() writes it back."""
    if not isinstance(spec, dict):
        return spec  # normalize() reports it
    kind = kind or detect(spec)
    if kind not in KINDS:
        raise SpecError(f"'{kind}' is not a v1 spec kind", f"use one of: {', '.join(KINDS)}", "kind")
    rest = dict(spec)
    out = {"version": 2, "preset": kind}
    for key in ("title", "sub"):
        if key in rest:
            out["subtitle" if key == "sub" else key] = rest.pop(key)
    notes = rest.pop("notes", None)
    if isinstance(notes, list) and all(isinstance(n, dict) for n in notes):
        out["annotations"] = [_note(n) for n in notes]
    elif notes is not None:
        rest["notes"] = notes
    if kind in ("flow", "arch"):
        nodes, edges = _items(rest, "nodes"), rest.pop("edges", None)
        rest.pop("nodes", None)
        if kind == "arch" and nodes is not None:
            nodes = [dict(n, layer=n.get("layer", 0)) if isinstance(n, dict) else n for n in nodes]
            rows = {}
            for n in nodes:
                if isinstance(n, dict) and "id" in n:
                    rows.setdefault(str(n["layer"]), []).append(n["id"])
            out["constraints"] = [{"order": ids} for ids in rows.values() if len(ids) > 1]
        out["layout"] = dict(LAYOUTS[kind])
    elif kind == "seq":
        nodes, edges = rest.pop("actors", None), rest.pop("messages", None)
        if isinstance(edges, list):
            edges = [dict(m, order=i) if isinstance(m, dict) else m for i, m in enumerate(edges)]
        out["layout"] = LAYOUTS[kind]
    else:
        nodes, edges = rest.pop("tables", None), rest.pop("relations", None)
        if isinstance(nodes, list):
            nodes = [_table(t) if isinstance(t, dict) else t for t in nodes]
        if isinstance(edges, list):
            edges = [_relation(r) if isinstance(r, dict) else r for r in edges]
        out["layout"] = LAYOUTS[kind]
    if nodes is not None:
        out["nodes"] = nodes
    if edges is not None:
        out["edges"] = edges
    out.update(rest)  # groups, budget, and fields only a toolkit reads
    return out


def _note(n):
    n = dict(n)
    out = {"type": "note"}
    if "at" in n:
        out["target"] = f"#{n.pop('at')}"
    if "text" in n:
        out["text"] = n.pop("text")
    out.update(n)
    return out


def _table(t):
    t = dict(t)
    cols = t.pop("columns", None)
    node = {"id": t.pop("id")} if "id" in t else {}
    node["shape"] = "table"
    if "x" in t and "y" in t:
        node["pin"] = {"x": t.pop("x"), "y": t.pop("y")}
    if cols is not None:
        node["content"] = {"table": {"columns": cols}}
        if isinstance(cols, list):
            node["ports"] = [{"id": str(c["name"])} for c in cols if isinstance(c, dict) and "name" in c]
    node.update(t)
    return node


def _relation(r):
    r = dict(r)
    for v1, v2 in (("from_col", "from-port"), ("to_col", "to-port")):
        if v1 in r:
            r[v2] = r.pop(v1)
    return r


def to_v1(scene):
    """(kind, spec, warnings): the v1 spec today's renderers draw for this scene. What they can't
    draw yet is named in the warnings, never dropped without a word."""
    kind = scene.preset
    if kind not in KINDS:
        raise SpecError(f"preset {kind!r} has no renderer yet" if kind else "the scene names no preset",
                        f'set "preset" to one of: {", ".join(KINDS)}', "preset", "preset")
    warn = []
    spec = {}
    if scene.title is not None:
        spec["title"] = scene.title
    if scene.subtitle is not None:
        spec["sub"] = scene.subtitle
    notes, other = [], []
    for a in scene.annotations:
        (notes if a.get("type") == "note" else other).append(a)
    if notes:
        spec["notes"] = [_v1_note(a) for a in notes]
    if other:
        warn.append(_not_drawn(f"{len(other)} annotation(s) of type {', '.join(sorted({str(a.get('type')) for a in other}))}",
                               "annotations"))
        spec["annotations"] = other
    if scene.budget is False:
        spec["budget"] = False
    if scene.style:
        spec["style"] = scene.style  # drawn: the renderers read their styles through the cascade (P3.8)
    if scene.caption:
        spec["caption"] = scene.caption  # drawn under the figure (B17)
    for key in ("source", "use", "size", "defs", "data", "space"):
        if getattr(scene, key):
            warn.append(_not_drawn(f"the figure's '{key}'", key))
            spec[key] = getattr(scene, key)
    if scene.layout not in (None, LAYOUTS[kind]):
        warn.append(_not_drawn(f"the layout {scene.layout!r} (the {kind} preset lays out its own way until P4)", "layout"))
        spec["layout"] = scene.layout
    if scene.legend != "auto":
        warn.append(_not_drawn("the legend setting", "legend"))
        spec["legend"] = scene.legend
    nodes = list(scene.nodes)
    order = [c["order"] for c in scene.constraints if isinstance(c.get("order"), list)]
    others = [c for c in scene.constraints if not isinstance(c.get("order"), list)]
    if kind == "arch":
        nodes = _apply_order(nodes, order)
    elif kind == "seq":  # actors stand in their list's order: an order over actors is that order
        actors = {n.id for n in nodes}
        nodes = _apply_order(nodes, [o for o in order if set(map(str, o)) <= actors])
        others += [{"order": o} for o in order if not set(map(str, o)) <= actors]
    elif order:
        others += [{"order": o} for o in order]
    # flow, arch and schema draw with the layered layout, which reads same-rank and order (diagrams._layered)
    read = ("same-rank", "order") if kind in ("flow", "arch", "schema") else ()
    unread = [c for c in others if not any(isinstance(c.get(k), list) for k in read)]
    if unread:
        warn.append(_not_drawn(f"{len(unread)} constraint(s)", "constraints"))
    if others:
        spec["constraints"] = others
    for el in [*nodes, *scene.edges, *scene.groups]:
        if (getattr(el, "pin", None) or getattr(el, "content", None)) and kind != "schema":
            warn.append(_not_drawn(f"the pin or content of '{el.id}'", f"{type(el).__name__.lower()}s.{el.id}"))
            break
    if kind in ("flow", "arch"):
        spec["nodes"] = [_v1_node(n, kind) for n in nodes]
        spec["edges"] = _v1_edges(scene.edges)
        groups = [_v1_group(g) for g in scene.groups]
        if groups:
            spec["groups"] = groups
    elif kind == "seq":
        spec["actors"] = [_v1_node(n, kind) for n in nodes]
        edges = sorted(scene.edges, key=lambda e: (e.order is None, e.order if e.order is not None else 0))
        spec["messages"] = [{k: v for k, v in m.items() if k != "order"} for m in _v1_edges(edges)]
    else:
        spec["tables"] = [_v1_table(n) for n in nodes]
        spec["relations"] = [_v1_relation(r) for r in _v1_edges(scene.edges)]
    if kind in ("seq", "schema") and scene.groups:
        warn.append(_not_drawn("groups", "groups"))
        spec["groups"] = [_v1_group(g) for g in scene.groups]
    spec.update(scene.extra)
    return kind, spec, warn


def _not_drawn(what, path):
    return {"code": "not-drawn", "msg": f"kept in the spec but not drawn yet: {what}",
            "fix": "this preset does not draw it yet; drop it if unwanted. To move a node, use a place patch (its row) instead of a pin",
            "path": path}


def _v1_note(a):
    out = {}
    target = a.get("target")
    if isinstance(target, str):
        out["at"] = target[1:] if target.startswith("#") else target
    if "text" in a:
        out["text"] = a["text"]
    out.update({k: v for k, v in a.items() if k not in ("type", "target", "text")})
    return out


def _apply_order(nodes, orders):
    """Nodes reordered so each order constraint holds among the slots its nodes already fill."""
    nodes = list(nodes)
    for ids in orders:
        ids = [str(i) for i in ids]
        slots = sorted(k for k, n in enumerate(nodes) if n.id in ids)
        by_id = {n.id: n for n in nodes}
        for slot, nid in zip(slots, [i for i in ids if i in by_id]):
            nodes[slot] = by_id[nid]
    return nodes


def _v1_node(n, kind):
    out = {"id": n.id, "name": n.name}
    if n.shape != "rect":
        out["shape"] = n.shape
    for key in ("sub", "tag", "icon"):
        if getattr(n, key):
            out[key] = getattr(n, key)
    if n.focal:
        out["focal"] = True
    if n.rank is not None:
        out["layer" if kind == "arch" else "rank"] = n.rank
    if n.lane is not None:
        out["lane"] = n.lane
    if n.order is not None:
        out["order"] = n.order
    _scene_only(out, n, ("classes", "data", "style", "content", "ports", "pin"))
    out.update(n.extra)
    return out


def _scene_only(out, el, keys):
    """Fields v1 has no name for, written under their scene names."""
    for key in keys:
        v = getattr(el, key)
        if v:
            out["class" if key == "classes" else key] = " ".join(v) if key == "classes" else v


def _v1_group(g):
    out = {"id": g.id, "name": g.name}
    if g.tag:
        out["tag"] = g.tag
    out["nodes"] = list(g.members)
    _scene_only(out, g, ("parent", "layout", "classes", "style"))
    out.update(g.extra)
    return out


def _v1_edges(edges):
    out, name = [], EdgeIds()
    for e in edges:
        d = {"from": e.from_, "to": e.to}
        if e.id != name.generated(e.from_, e.to, e.label):
            d["id"] = e.id  # only an id the renderer wouldn't give it itself
        name(e.from_, e.to, e.label, e.id)
        if e.from_port is not None:
            d["from-port"] = e.from_port
        if e.to_port is not None:
            d["to-port"] = e.to_port
        for key in EDGE_FLAGS:
            if getattr(e, key):
                d[key.rstrip("_")] = getattr(e, key)
        if e.order is not None:
            d["order"] = e.order
        _scene_only(d, e, ("labels", "classes", "data", "style", "router", "route"))
        d.update(e.extra)
        out.append(d)
    return out


def _v1_table(n):
    out = {"id": n.id, "name": n.name}
    for key in ("sub", "tag", "icon"):
        if getattr(n, key):
            out[key] = getattr(n, key)
    if n.focal:
        out["focal"] = True
    for key in ("rank", "lane", "order"):  # a column and a place in it, from edits (scene/patch.py place)
        if getattr(n, key) is not None:
            out[key] = getattr(n, key)
    if n.pin:
        out["x"], out["y"] = n.pin.get("x"), n.pin.get("y")
    table = (n.content or {}).get("table")
    if isinstance(table, dict) and "columns" in table:
        out["columns"] = table["columns"]
    _scene_only(out, n, ("classes", "data", "style"))
    out.update(n.extra)
    return out


def _v1_relation(r):
    out = dict(r)
    for v2, v1 in (("from-port", "from_col"), ("to-port", "to_col")):
        if v2 in out:
            out[v1] = out.pop(v2)
    return out


def scene_as_v1(raw, kind=None):
    """A v2 scene file, as the v1 spec the renderer for `kind` (or the scene's preset) draws. Scene
    problems come back the way load_spec reports Mermaid ones: as "_errors" and "_warnings"."""
    from ..scene import check
    scene, errors, warnings = check(raw)
    if scene is not None and not errors:
        if scene.preset is None and kind in KINDS:
            scene.preset = kind
        elif kind in KINDS and scene.preset != kind:
            errors = [{"code": "preset", "msg": f"this scene's preset is {scene.preset!r}, not {kind!r}",
                       "fix": f"draw it with the {scene.preset} command, or change its preset" if scene.preset in KINDS
                       else f'set "preset": "{kind}"', "path": "preset"}]
    if not errors:
        try:
            _, spec, more = to_v1(scene)
        except SpecError as e:
            errors = [{"code": e.code, "msg": e.msg, "fix": e.fix, "path": e.at}]
        else:
            if warnings or more:
                spec["_warnings"] = list(spec.get("_warnings") or []) + warnings + more
            return spec
    key = {"seq": "actors", "schema": "tables"}.get(kind, "nodes")
    return {key: [], "_errors": errors, "_warnings": warnings}

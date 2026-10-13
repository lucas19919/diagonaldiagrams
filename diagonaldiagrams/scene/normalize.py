"""JSON in, a checked Scene out (DESIGN 4).

Accepts the aliases v1 specs use (label for name, sub for subtitle, layer for rank, nodes for a
group's members), both forms of group membership, and numbers as ids. Every problem is collected
with the JSON path it sits at, so an agent can fix them all in one pass.

check(raw) returns (scene or None, errors, warnings). normalize(raw) returns (scene, warnings) and
raises SpecError when there is an error.
"""
from ..errors import SpecError
from .ids import EdgeIds
from .model import KEYS, Edge, Group, Node, Scene

# JSON key -> the key it stands for
ALIASES = {
    "scene": {"sub": "subtitle"},
    "node": {"label": "name", "subtitle": "sub", "layer": "rank"},
    "edge": {},
    "group": {"label": "name", "nodes": "members"},
}

# what each field holds: str, id (a string or a number), bool, int, num, dict, list, classes, any
TYPES = {
    "scene": {"version": "int", "title": "str", "subtitle": "str", "source": "str", "caption": "str", "preset": "str",
              "use": "list", "size": "dict", "style": "any", "defs": "dict", "data": "dict", "layout": "any",
              "space": "dict", "nodes": "list", "edges": "list", "groups": "list", "constraints": "list",
              "annotations": "list", "legend": "any", "budget": "bool"},
    "node": {"id": "id", "name": "str", "sub": "str", "tag": "str", "icon": "str", "shape": "str", "class": "classes",
             "data": "dict", "style": "dict", "group": "id", "content": "dict", "ports": "list", "focal": "bool",
             "rank": "int", "lane": "num", "order": "int", "pin": "dict"},
    "edge": {"id": "id", "from": "id", "to": "id", "from-port": "id", "to-port": "id", "label": "str", "labels": "list",
             "proto": "str", "async": "bool", "reply": "bool", "class": "classes", "data": "dict", "style": "dict",
             "router": "str", "route": "list", "focal": "bool", "order": "int"},
    "group": {"id": "id", "name": "str", "tag": "str", "members": "list", "parent": "id", "layout": "any",
              "class": "classes", "style": "dict"},
}
ATTR = {v: k for k, v in KEYS.items()}  # JSON key -> attribute
CONSTRAINTS = {"same-rank", "order", "above", "align", "pin", "together"}
ANNOTATIONS = {"note", "callout", "highlight", "bracket", "band", "rule"}


class _Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, code, msg, fix, path):
        self.errors.append({"code": code, "msg": msg, "fix": fix, "path": path})

    def warn(self, code, msg, fix, path):
        self.warnings.append({"code": code, "msg": msg, "fix": fix, "path": path})


def _coerce(kind, value, path, rep):
    """value as the type the field holds, or MISSING after reporting why it can't be."""
    if kind == "any":
        return value
    if kind == "str":
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    elif kind == "id":
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    elif kind == "bool":
        if isinstance(value, bool):
            return value
        if value in (0, 1) and not isinstance(value, float):
            return bool(value)
    elif kind == "int":
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
    elif kind == "num":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    elif kind == "dict":
        if isinstance(value, dict):
            return value
    elif kind == "list":
        if isinstance(value, list):
            return value
    elif kind == "classes":
        if isinstance(value, str):
            return value.split()
        if isinstance(value, list) and all(isinstance(c, str) for c in value):
            return list(value)
    want = {"str": "text", "id": "a non-empty string or an integer", "bool": "true or false", "int": "a whole number",
            "num": "a number", "dict": "an object", "list": "a list", "classes": "a string of class names"}[kind]
    rep.error("bad-value", f"{path} is {_show(value)}; it should be {want}", f"set {path} to {want}", path)
    return _MISSING


_MISSING = object()


def _show(v):
    import json
    try:
        s = json.dumps(v)
    except (TypeError, ValueError):
        s = repr(v)
    return s if len(s) <= 40 else s[:37] + "..."


def _fields(kind, raw, path, rep):
    """The known fields of one object, under their canonical JSON keys and coerced, plus the
    unknown ones kept as given."""
    aliases, types = ALIASES[kind], TYPES[kind]
    known, extra = {}, {}
    for key, value in raw.items():
        canon = aliases.get(key, key)
        if canon in types:
            if canon != key and canon in raw:
                if raw[canon] != value:
                    rep.warn("alias-conflict", f"{path} sets both '{canon}' and its alias '{key}'; '{canon}' is used",
                             f"drop '{key}'", f"{path}.{key}")
                continue
            v = _coerce(types[canon], value, f"{path}.{key}", rep)
            if v is not _MISSING:
                known[canon] = v
        else:
            extra[key] = value
            import difflib
            near = difflib.get_close_matches(key, list(types) + list(aliases), n=1, cutoff=0.8)
            if near:
                rep.warn("unknown-field", f"{path} has a field '{key}', which is kept but not read", f"did you mean '{near[0]}'?",
                         f"{path}.{key}")
    return known, extra


def _build(cls, known, extra):
    return cls(**{ATTR.get(k, k).replace("-", "_"): v for k, v in known.items()}, extra=extra)


def _objects(raw, key, rep):
    items = raw.get(key)
    if items is None:
        return []
    if not isinstance(items, list):
        return []  # _fields already reported it
    out = []
    for i, it in enumerate(items):
        if isinstance(it, dict):
            out.append((f"{key}[{i}]", it))
        else:
            rep.error("bad-value", f"{key}[{i}] is {_show(it)}, not an object", f"write it as an object with an \"id\"", f"{key}[{i}]")
    return out


def check(raw):
    """(scene or None, errors, warnings). The scene is None only when raw isn't an object."""
    rep = _Report()
    if not isinstance(raw, dict):
        rep.error("bad-value", f"the scene is a JSON {type(raw).__name__}, not an object",
                  'wrap it: {"version": 2, "nodes": [...], "edges": [...]}', "")
        return None, rep.errors, rep.warnings
    top, extra = _fields("scene", raw, "scene", rep)
    if top.get("version", 2) != 2:
        rep.error("version", f"version {top['version']} is not a scene version this engine reads", 'set "version": 2', "version")
    top.pop("version", None)
    for key in ("nodes", "edges", "groups"):
        top.pop(key, None)
    scene = _build(Scene, top, extra)

    # nodes
    for path, raw_n in _objects(raw, "nodes", rep):
        known, extra = _fields("node", raw_n, path, rep)
        if "id" not in known:
            if "name" in known and known["name"]:
                known["id"] = known["name"]
            else:
                if "id" not in raw_n:  # a bad id was reported already
                    rep.error("missing-id", f"{path} has no id", 'give it one: "id": "api"', f"{path}.id")
                continue
        node = _build(Node, known, extra)
        if "name" not in known:
            node.name = node.id
        scene.nodes.append(node)
    seen = {}
    for k, n in enumerate(scene.nodes):
        if n.id in seen:
            rep.error("duplicate-id", f"two nodes have the id '{n.id}'", "make node ids unique", f"nodes[{k}].id")
        seen.setdefault(n.id, n)
    nodes = seen

    # groups: listed members and each node's own "group" field, merged
    for path, raw_g in _objects(raw, "groups", rep):
        known, extra = _fields("group", raw_g, path, rep)
        if "id" not in known:
            if "id" not in raw_g:
                rep.error("missing-id", f"{path} has no id", 'write {"id": "core", "name": "Core", "members": ["a", "b"]}', f"{path}.id")
            continue
        group = _build(Group, known, extra)
        if "name" not in known:
            group.name = group.id
        scene.groups.append(group)
    groups = {}
    for k, g in enumerate(scene.groups):
        if g.id in groups:
            rep.error("duplicate-id", f"two groups have the id '{g.id}'", "make group ids unique", f"groups[{k}].id")
            continue
        groups[g.id] = g
        if g.id in nodes:
            rep.warn("id-clash", f"'{g.id}' is the id of a node and a group, so '#{g.id}' means the node",
                     "rename one of them", f"groups[{k}].id")
    home = {}
    for k, g in enumerate(scene.groups):
        members = []
        for j, m in enumerate(g.members):
            m = str(m) if isinstance(m, (str, int)) and not isinstance(m, bool) else m
            if m not in nodes:
                rep.error("unknown-node", f"group '{g.id}' lists '{m}', which is not a node",
                          f"use node ids, such as {', '.join(list(nodes)[:5]) or 'a node id'}", f"groups[{k}].members[{j}]")
            elif m in home and home[m] != g.id:
                rep.error("two-groups", f"node '{m}' is in groups '{home[m]}' and '{g.id}'",
                          "a node sits in one frame; keep it in one group", f"groups[{k}].members[{j}]")
            elif m not in members:
                members.append(m)
                home[m] = g.id
        g.members = members
    for k, n in enumerate(scene.nodes):
        if n.group is None:
            if n.id in home:
                n.group = home[n.id]
            continue
        if n.id in home and home[n.id] != n.group:
            rep.error("two-groups", f"node '{n.id}' says it is in group '{n.group}' but group '{home[n.id]}' lists it",
                      "keep it in one group", f"nodes[{k}].group")
            continue
        g = groups.get(n.group)
        if g is None:  # a group named only by its members, as v1 allows
            g = groups[n.group] = Group(id=n.group, name=n.group)
            scene.groups.append(g)
        if n.id not in g.members:
            g.members.append(n.id)
        home[n.id] = n.group
    for k, g in enumerate(scene.groups):
        if g.parent is not None and g.parent not in groups:
            rep.error("unknown-group", f"group '{g.id}' has parent '{g.parent}', which is not a group",
                      f"use a group id, such as {', '.join(list(groups)[:5])}", f"groups[{k}].parent")
            g.parent = None
    for k, g in enumerate(scene.groups):
        seen_up, p = {g.id}, g.parent
        while p is not None:
            if p in seen_up:
                rep.error("group-cycle", f"group '{g.id}' contains itself through its parents",
                          "remove one parent so the groups form a tree", f"groups[{k}].parent")
                g.parent = None
                break
            seen_up.add(p)
            p = groups[p].parent if p in groups else None
    parents = {g.parent for g in scene.groups}
    for k, g in enumerate(scene.groups):
        if not g.members and g.id not in parents:
            rep.warn("empty-group", f"group '{g.id}' has no members, so it draws nothing",
                     'list its node ids: "members": ["a", "b"]', f"groups[{k}]")

    # edges
    name = EdgeIds()
    for path, raw_e in _objects(raw, "edges", rep):
        known, extra = _fields("edge", raw_e, path, rep)
        ok = True
        for end in ("from", "to"):
            if end not in known:
                if end not in raw_e:
                    rep.error("missing-end", f"{path} has no '{end}'", f'name a node: "{end}": "api"', f"{path}.{end}")
                ok = False
            elif known[end] not in nodes:
                verb = "starts at" if end == "from" else "goes to"
                rep.error("unknown-node", f"an edge {verb} '{known[end]}', but there is no node with that id",
                          f"use one of: {', '.join(list(nodes)[:8])}" if nodes else "add the node first", f"{path}.{end}")
                ok = False
        if not ok:
            continue
        given = "id" in known
        edge = _build(Edge, {"id": "", **known}, extra)
        for end, port in (("from", edge.from_port), ("to", edge.to_port)):
            node = nodes[edge.from_ if end == "from" else edge.to]
            names = [p.get("id") for p in node.ports if isinstance(p, dict)]
            if port is not None and names and port not in names:
                rep.warn("unknown-port", f"an edge {end} '{node.id}' names port '{port}', which the node doesn't have",
                         f"use one of: {', '.join(map(str, names[:8]))}", f"{path}.{end}-port")
        if given and edge.id in name.taken:
            rep.error("duplicate-id", f"two edges have the id '{edge.id}'", "make edge ids unique", f"{path}.id")
        edge.id = name(edge.from_, edge.to, edge.label, edge.id if given else None)
        scene.edges.append(edge)

    # constraints and annotations: shapes checked here, meaning checked by the layout that reads them
    ids = set(nodes) | set(groups)
    for path, c in _objects(raw, "constraints", rep):
        kind = next((k for k in c if k in CONSTRAINTS), None)
        if kind is None:
            rep.warn("unknown-constraint", f"{path} is not a constraint this engine knows, so no layout reads it",
                     f"use one of: {', '.join(sorted(CONSTRAINTS))}", path)
            continue
        refs = c[kind] if isinstance(c[kind], list) else [c[kind]]
        for r in refs:
            if str(r) not in ids:
                rep.error("unknown-node", f"{path} names '{r}', which is not a node or group",
                          "use node or group ids", f"{path}.{kind}")
    scene.constraints = [c for _, c in _objects(raw, "constraints", _Report())]
    for path, a in _objects(raw, "annotations", rep):
        if a.get("type") not in ANNOTATIONS:
            rep.warn("unknown-annotation", f"{path} has type {_show(a.get('type'))}, which nothing draws",
                     f"use one of: {', '.join(sorted(ANNOTATIONS))}", f"{path}.type")
        target = a.get("target")
        if isinstance(target, str) and target.startswith("#") and target[1:] not in ids:
            rep.warn("unknown-target", f"{path} points at '{target}', which matches nothing", "point it at a node or group id",
                     f"{path}.target")
    scene.annotations = [a for _, a in _objects(raw, "annotations", _Report())]
    return scene, rep.errors, rep.warnings


def normalize(raw):
    """(scene, warnings), or SpecError for the first error with a count of the rest."""
    scene, errors, warnings = check(raw)
    if errors:
        e = errors[0]
        more = f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""
        raise SpecError(e["msg"] + more, e["fix"], e["code"], e["path"])
    return scene, warnings

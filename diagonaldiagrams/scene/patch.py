"""Patches: an edit as data (DESIGN 21.3, D12).

A patch is a list of operations. A human's drag, retype or recolor becomes one, and so can an
agent's edit; either way it lands in the spec as fields, constraints and style rules, so it survives
the next generation of the spec.

    {"op": "pin",   "id": "psp", "x": 640, "y": 210}                     "z" too, in 3D
    {"op": "order", "ids": ["auth", "api"]}                              nodes, or a sequence's messages
    {"op": "place", "id": "psp", "row": ["api", "psp", "auth"]}          a drag: its row, in order
    {"op": "style", "selector": "#psp", "set": {"fill": "#fee2e2"}}      null removes a property
    {"op": "text",  "id": "psp", "name": "Payment provider", "was": "PSP"}
    {"op": "add",   "node": {...}}   or "edge" or "group"
    {"op": "remove", "id": "psp"}
    {"op": "move-to-group", "id": "psp", "group": "external"}            null leaves every group

An operation that no longer fits the spec (its element is gone, a "was" no longer matches, the
result would not be a valid scene) is reported as a patch-conflict and skipped, never dropped
without a word. The others still apply.
"""
import copy
import re

from .ids import compact  # noqa: F401 (compact is part of the patch API)
from .normalize import check

OPS = ("pin", "order", "place", "style", "text", "add", "remove", "move-to-group")
TEXT = {"node": ("name", "sub", "tag"), "group": ("name", "tag"), "edge": ("label",)}


class _Conflict(Exception):
    def __init__(self, msg, fix):
        super().__init__(msg)
        self.msg, self.fix = msg, fix


def _find(d, eid):
    """(kind, element dict) for an id: nodes first, then groups, then edges."""
    for kind in ("node", "group", "edge"):
        for el in d.get(kind + "s") or []:
            if str(el.get("id")) == str(eid):
                return kind, el
    raise _Conflict(f"there is no element '{eid}'", "it was removed or renamed since the patch was made; "
                    "drop this operation or point it at the element's new id")


def _ids(op, key="ids"):
    ids = op.get(key)
    if not isinstance(ids, list) or not ids:
        raise _Conflict(f"'{key}' should be a list of ids", f'write "{key}": ["a", "b"]')
    return [str(i) for i in ids]


def _pin(d, op):
    kind, el = _find(d, op.get("id"))
    if kind != "node":
        raise _Conflict(f"'{op['id']}' is {'an' if kind == 'edge' else 'a'} {kind}; only nodes are pinned", "pin a node")
    pin = {k: op[k] for k in ("x", "y", "z") if k in op}
    if not ("x" in pin and "y" in pin) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in pin.values()):
        raise _Conflict("a pin needs numbers x and y, and z if the figure is 3D", 'write "x": 640, "y": 210')
    el["pin"] = pin


def _order(d, op):
    ids = _ids(op)
    kinds = {_find(d, i)[0] for i in ids}
    if "edge" in kinds:
        if kinds != {"edge"}:
            raise _Conflict("an order names nodes or edges, not both", "order the nodes and the messages in separate operations")
        if d.get("preset") != "seq":
            raise _Conflict("only a sequence's messages have an order", "order nodes, or drop this operation")
        return _order_messages(d, ids)
    cons = d.setdefault("constraints", [])
    for c in cons:
        held = c.get("order")
        if isinstance(held, list) and set(ids) <= {str(h) for h in held}:
            # the new order takes the places these ids already hold in the constraint
            slots = sorted(k for k, h in enumerate(held) if str(h) in ids)
            for slot, i in zip(slots, ids):
                held[slot] = i
            return
    cons.append({"order": ids})


def _order_messages(d, ids):
    """A sequence's messages in a new order: they take the steps they already hold, as their order
    fields, so the messages the operation doesn't name keep theirs."""
    edges = d["edges"]
    if not all(isinstance(e.get("order"), int) for e in edges if str(e.get("id")) in ids):
        steps = sorted(range(len(edges)), key=lambda k: (edges[k].get("order") is None, edges[k].get("order") or 0, k))
        for step, k in enumerate(steps):  # messages that have no step yet get the one their place in the list gives
            edges[k]["order"] = step
    by_id = {str(e.get("id")): e for e in edges}
    slots = sorted(by_id[i]["order"] for i in ids)
    for slot, i in zip(slots, ids):
        by_id[i]["order"] = slot


def _place(d, op):
    """A node dropped into a row: it shares the row with the others named, in the order named. With
    the others in one pinned rank (arch layers, ranked flows), the node takes that rank; else the
    row is a same-rank constraint, so it holds when the ranks are worked out again. The row's nodes
    take its order, and drop their lanes."""
    kind, el = _find(d, op.get("id"))
    if kind != "node":
        raise _Conflict(f"'{el['id']}' is a {kind}; place moves nodes", "place a node")
    row = _ids(op, "row")
    nid = str(el["id"])
    if nid not in row or len(set(row)) != len(row):
        raise _Conflict(f"the row should name '{nid}' once, among the nodes it now sits between",
                        f'write "row": ["a", "{nid}", "b"]')
    nodes = {}
    for i in row:
        k, other = _find(d, i)
        if k != "node":
            raise _Conflict(f"'{i}' is {'an' if k == 'edge' else 'a'} {k}, not a node", "name only nodes in a row")
        nodes[i] = other
    mates = [nodes[i] for i in row if i != nid]
    if not mates:
        raise _Conflict("a row needs another node besides the one placed", f'write "row": ["a", "{nid}"]')
    cons = [c for c in d.get("constraints") or [] if not (isinstance(c.get("same-rank"), list) and nid in map(str, c["same-rank"]))]
    ranks = {m.get("rank") for m in mates}
    if len(ranks) == 1 and None not in ranks:
        el["rank"] = ranks.pop()
    else:
        el.pop("rank", None)
        cons.append({"same-rank": row})
    d["constraints"] = cons
    for k, i in enumerate(row):  # the row's order replaces the lanes it had: the drag says where they go
        nodes[i]["order"] = k
        nodes[i].pop("lane", None)


def _style(d, op):
    sel, props = op.get("selector"), op.get("set")
    if not isinstance(sel, str) or not sel.strip() or not isinstance(props, dict):
        raise _Conflict("a style operation needs a selector and a set object", 'write "selector": "#api", "set": {"fill": "#fee2e2"}')
    m = re.fullmatch(r"#([^\s.#\[:>]+)", sel.strip())
    if m:  # one element: its own style field
        _, el = _find(d, m.group(1))
        target = el.setdefault("style", {})
    else:  # anything wider: an inline rule, so it reaches elements added later too
        target = _rules(d).setdefault(sel.strip(), {})
    for k, v in props.items():
        if v is None:
            target.pop(k, None)
        else:
            target[k] = v


def _rules(d):
    """The inline stylesheet's rules, created if the scene has none."""
    style = d.get("style")
    if style is None:
        d["style"] = style = {}
    if isinstance(style, str):
        d["style"] = style = [style, {}]
    if isinstance(style, list):
        sheet = next((s for s in reversed(style) if isinstance(s, dict)), None)
        if sheet is None:
            sheet = {}
            style.append(sheet)
        style = sheet
    return style.setdefault("rules", {})


def _text(d, op):
    kind, el = _find(d, op.get("id"))
    fields = {("name" if k == "label" and kind != "edge" else k): v for k, v in op.items()
              if k not in ("op", "id", "was")}
    unknown = [k for k in fields if k not in TEXT[kind]]
    if unknown or not fields:
        raise _Conflict(f"a {kind}'s text fields are {', '.join(TEXT[kind])}; this operation sets {', '.join(unknown) or 'none'}",
                        f"set one of: {', '.join(TEXT[kind])}")
    if all(el.get(k) == v for k, v in fields.items()):
        return  # already says so: applying a patch again after the spec was written changes nothing
    if "was" in op:
        key = next(iter(fields))
        now = el.get(key, el.get("id") if key == "name" else "")
        if now != op["was"]:
            raise _Conflict(f"'{el['id']}' {key} is now {now!r}, not {op['was']!r} as the patch expected",
                            "the spec changed since the patch was made; check the new text, then drop \"was\" to apply anyway")
    for k, v in fields.items():
        el[k] = v
    # an edge keeps the id it had: its label is part of a generated id (ids.py)


def _add(d, op):
    kinds = [k for k in ("node", "edge", "group") if k in op]
    if len(kinds) != 1 or not isinstance(op[kinds[0]], dict):
        raise _Conflict("add takes one of node, edge or group, as an object", 'write {"op": "add", "node": {"id": "cache"}}')
    kind, el = kinds[0], dict(op[kinds[0]])
    if el.get("id") is not None:
        try:
            _find(d, el["id"])
        except _Conflict:
            pass
        else:
            raise _Conflict(f"'{el['id']}' already exists", "give the new element another id, or patch the existing one")
    d.setdefault(kind + "s", []).append(el)


def _remove(d, op):
    kind, el = _find(d, op.get("id"))
    eid = str(el["id"])
    d[kind + "s"].remove(el)
    if kind == "node":
        d["edges"] = [e for e in d.get("edges") or [] if str(e.get("from")) != eid and str(e.get("to")) != eid]
        for g in d.get("groups") or []:
            g["members"] = [m for m in g.get("members") or [] if str(m) != eid]
    if kind == "group":
        for n in d.get("nodes") or []:
            if str(n.get("group")) == eid:
                n.pop("group")
        for g in d.get("groups") or []:
            if str(g.get("parent")) == eid:
                if el.get("parent") is not None:
                    g["parent"] = el["parent"]
                else:
                    g.pop("parent")
    if kind != "edge":
        cons = []
        for c in d.get("constraints") or []:
            c = {k: ([i for i in v if str(i) != eid] if isinstance(v, list) else v) for k, v in c.items()}
            if not any(str(v) == eid for v in c.values()) and all(len(v) > 1 for v in c.values() if isinstance(v, list)):
                cons.append(c)
        d["constraints"] = cons
        d["annotations"] = [a for a in d.get("annotations") or [] if a.get("target") != f"#{eid}"]


def _move(d, op):
    kind, el = _find(d, op.get("id"))
    if kind != "node":
        raise _Conflict(f"'{el['id']}' is a {kind}; move-to-group moves nodes", "move a node, or set the group's parent")
    gid = op.get("group")
    if gid is not None:
        if _find(d, gid)[0] != "group":
            raise _Conflict(f"'{gid}' is not a group", "move it into a group id, or null to leave every group")
    for g in d.get("groups") or []:
        g["members"] = [m for m in g.get("members") or [] if str(m) != str(el["id"])]
    if gid is None:
        el.pop("group", None)
    else:
        el["group"] = str(gid)


HANDLERS = {"pin": _pin, "order": _order, "place": _place, "style": _style, "text": _text, "add": _add, "remove": _remove,
            "move-to-group": _move}


def apply(scene, ops):
    """(scene, applied, conflicts): the scene with every operation that fits applied, in order.
    The scene passed in is not changed."""
    d = copy.deepcopy(scene.to_dict())  # a scene shares nested lists and dicts with the JSON it came from
    applied, conflicts = 0, []
    if isinstance(ops, dict):
        ops = ops.get("ops")
    if not isinstance(ops, list):
        return scene, 0, [_issue("patch", "a patch is a list of operations", '[{"op": "text", "id": "a", "name": "New"}]')]
    for k, op in enumerate(ops):
        path = f"patch[{k}]"
        if not isinstance(op, dict) or op.get("op") not in HANDLERS:
            got = op.get("op") if isinstance(op, dict) else op
            conflicts.append(_issue(path, f"{path} is not an operation this engine knows ({got!r})", f"use one of: {', '.join(OPS)}"))
            continue
        before = copy.deepcopy(d)
        try:
            HANDLERS[op["op"]](d, op)
        except _Conflict as c:
            conflicts.append(_issue(path, f"{op['op']}: {c.msg}", c.fix))
            d = before
            continue
        _, errors, _ = check(d)
        if errors:
            conflicts.append(_issue(path, f"{op['op']}: the result would not be a valid scene: {errors[0]['msg']}", errors[0]["fix"]))
            d = before
            continue
        applied += 1
    out, errors, _ = check(d)
    return out, applied, conflicts


def _issue(path, msg, fix):
    return {"code": "patch-conflict", "msg": msg, "fix": fix, "path": path}

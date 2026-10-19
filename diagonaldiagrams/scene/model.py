"""The scene: what a figure shows, before layout and style decide where and how.

Plain slotted records. normalize.py builds them from JSON and to_dict() writes them back, so a scene
round-trips through receipts and patches. A scene is data: nothing in it runs. Every element
has an id, and generated ids come from content, never from position.

Fields a toolkit understands but the core does not are kept in `extra` and written back as given.
"""
# attribute -> JSON key, where they differ ("from" and "async" are Python keywords)
KEYS = {"from_": "from", "async_": "async", "classes": "class", "from_port": "from-port", "to_port": "to-port"}
ALWAYS = {"id", "from_", "to"}  # written even when empty
REQUIRED = object()


class Record:
    """A slotted record. FIELDS lists (name, default); a list or dict default is made fresh for
    each record. Plain classes rather than dataclasses, which would add 25-40 ms to every import."""
    __slots__ = ()
    FIELDS = ()

    def __init__(self, **kw):
        for name, default in self.FIELDS:
            if name in kw:
                value = kw.pop(name)
            elif default is REQUIRED:
                raise TypeError(f"{type(self).__name__} needs {name!r}")
            else:
                value = default() if default in (list, dict) else default
            setattr(self, name, value)
        if kw:
            raise TypeError(f"{type(self).__name__} has no field {next(iter(kw))!r}")

    def __eq__(self, other):
        return type(self) is type(other) and all(getattr(self, n) == getattr(other, n) for n, _ in self.FIELDS)

    def __repr__(self):
        shown = ", ".join(f"{n}={getattr(self, n)!r}" for n, d in self.FIELDS
                          if n == "id" or getattr(self, n) != (d() if d in (list, dict) else d))
        return f"{type(self).__name__}({shown})"

    def to_dict(self, skip=()):
        out = {}
        for name, default in self.FIELDS:
            if name == "extra" or name in skip:
                continue
            v = getattr(self, name)
            if v == (default() if default in (list, dict) else default) and name not in ALWAYS:
                continue
            out[KEYS.get(name, name)] = " ".join(v) if name == "classes" else v
        out.update(self.extra)
        return out


def _record(name, fields, doc=""):
    return type(name, (Record,), {"__slots__": tuple(n for n, _ in fields), "FIELDS": tuple(fields), "__doc__": doc})


_NAMED = Record.to_dict


class Node(_record("Node", (
        ("id", REQUIRED), ("name", ""), ("sub", ""), ("tag", ""), ("icon", ""), ("shape", "rect"), ("classes", list),
        ("data", dict), ("style", dict), ("group", None),
        ("content", None),  # a nested container: a chart, a sub-diagram, a table, raw SVG (4.5)
        ("ports", list), ("focal", False), ("rank", None), ("lane", None), ("order", None), ("pin", None),
        ("extra", dict)))):
    """A box, decision, table or any registered shape. name defaults to id (normalize fills it in)."""
    __slots__ = ()

    def to_dict(self):
        return _NAMED(self, skip=("name",) if self.name == self.id else ())


class Edge(_record("Edge", (
        ("id", REQUIRED), ("from_", REQUIRED), ("to", REQUIRED), ("from_port", None), ("to_port", None), ("label", ""),
        ("labels", list), ("proto", ""), ("async_", False), ("reply", False), ("classes", list), ("data", dict),
        ("style", dict), ("router", None), ("route", None), ("focal", False),
        ("order", None),  # a sequence message's place in time
        ("extra", dict)))):
    """A connection between two nodes. Its id comes from content when it has none (ids.py)."""
    __slots__ = ()


class Group(_record("Group", (
        ("id", REQUIRED), ("name", ""), ("tag", ""), ("members", list), ("parent", None), ("layout", None),
        ("classes", list), ("style", dict), ("extra", dict)))):
    """A container drawn as a frame. Groups nest through parent."""
    __slots__ = ()

    def to_dict(self):
        return _NAMED(self, skip=("name",) if self.name == self.id else ())


class Scene(_record("Scene", (
        ("version", 2),
        ("title", None), ("subtitle", None),  # None: not given, so a renderer may put its own default in
        ("source", ""), ("caption", ""), ("preset", None), ("use", list), ("size", None),
        ("style", None),  # a stylesheet path, an inline stylesheet, or a list of both
        ("defs", dict), ("data", dict), ("layout", None), ("space", None), ("nodes", list), ("edges", list),
        ("groups", list), ("constraints", list), ("annotations", list), ("legend", "auto"), ("budget", True),
        ("extra", dict)))):
    """A whole figure: the root container."""
    __slots__ = ()

    def to_dict(self):
        out = {"version": self.version}
        out.update(Record.to_dict(self, skip=("version", "nodes", "edges", "groups")))
        for key in ("nodes", "edges", "groups"):
            if getattr(self, key):
                out[key] = [x.to_dict() for x in getattr(self, key)]
        order = ["version", "title", "subtitle", "source", "caption", "preset", "use", "size", "style", "defs",
                 "data", "layout", "space", "nodes", "edges", "groups", "constraints", "annotations", "legend", "budget"]
        return {k: out[k] for k in sorted(out, key=lambda k: order.index(k) if k in order else len(order))}

    def node(self, nid):
        return next((n for n in self.nodes if n.id == nid), None)

    def group(self, gid):
        return next((g for g in self.groups if g.id == gid), None)

    def element(self, eid):
        """The node, edge or group with this id (nodes first, as `#id` selectors read it)."""
        return self.node(eid) or self.group(eid) or next((e for e in self.edges if e.id == eid), None)

    def children(self, parent=None):
        """The container tree (4.5): the groups and nodes directly inside `parent`, a group id, or
        the figure itself when parent is None. Groups come first, each list in scene order."""
        return ([g for g in self.groups if g.parent == parent] +
                [n for n in self.nodes if n.group == parent])

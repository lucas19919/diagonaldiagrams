"""The scene: what a figure shows, before layout and style decide where and how (DESIGN 4).

Plain dataclasses. normalize.py builds them from JSON and to_dict() writes them back, so a scene
round-trips through receipts and patches. A scene is data (D8): nothing in it runs. Every element
has an id, and generated ids come from content, never from position (D15).

Fields a toolkit understands but the core does not are kept in `extra` and written back as given.
"""
from dataclasses import MISSING, dataclass, field, fields

# attribute -> JSON key, where they differ ("from" and "async" are Python keywords)
KEYS = {"from_": "from", "async_": "async", "classes": "class", "from_port": "from-port", "to_port": "to-port"}
ALWAYS = {"id", "from_", "to"}  # written even when empty


def _list():
    return field(default_factory=list)


def _dict():
    return field(default_factory=dict)


def _to_dict(obj, skip=()):
    out = {}
    for f in fields(obj):
        if f.name == "extra" or f.name in skip:
            continue
        v = getattr(obj, f.name)
        default = f.default_factory() if f.default_factory is not MISSING else f.default
        if v == default and f.name not in ALWAYS:
            continue
        out[KEYS.get(f.name, f.name)] = " ".join(v) if f.name == "classes" else v
    out.update(obj.extra)
    return out


@dataclass(slots=True)
class Node:
    id: str
    name: str = ""  # normalize fills in the id when a node has none
    sub: str = ""
    tag: str = ""
    icon: str = ""
    shape: str = "rect"
    classes: list = _list()
    data: dict = _dict()
    style: dict = _dict()
    group: str | None = None
    content: dict | None = None  # a nested container: a chart, a sub-diagram, a table, raw SVG (4.5)
    ports: list = _list()
    focal: bool = False
    rank: int | None = None
    lane: float | None = None
    order: int | None = None
    pin: dict | None = None
    extra: dict = _dict()

    def to_dict(self):
        return _to_dict(self, skip=("name",) if self.name == self.id else ())


@dataclass(slots=True)
class Edge:
    id: str
    from_: str
    to: str
    from_port: str | None = None
    to_port: str | None = None
    label: str = ""
    labels: list = _list()
    proto: str = ""
    async_: bool = False
    reply: bool = False
    classes: list = _list()
    data: dict = _dict()
    style: dict = _dict()
    router: str | None = None
    route: list | None = None
    focal: bool = False
    order: int | None = None  # a sequence message's place in time
    extra: dict = _dict()

    def to_dict(self):
        return _to_dict(self)


@dataclass(slots=True)
class Group:
    id: str
    name: str = ""
    tag: str = ""
    members: list = _list()
    parent: str | None = None
    layout: object = None
    classes: list = _list()
    style: dict = _dict()
    extra: dict = _dict()

    def to_dict(self):
        return _to_dict(self, skip=("name",) if self.name == self.id else ())


@dataclass(slots=True)
class Scene:
    version: int = 2
    title: str | None = None  # None: not given, so a renderer may put its own default in
    subtitle: str | None = None
    source: str = ""
    caption: str = ""
    preset: str | None = None
    use: list = _list()
    size: dict | None = None
    style: object = None  # a stylesheet path, an inline stylesheet, or a list of both
    defs: dict = _dict()
    data: dict = _dict()
    layout: object = None
    space: dict | None = None
    nodes: list = _list()
    edges: list = _list()
    groups: list = _list()
    constraints: list = _list()
    annotations: list = _list()
    legend: object = "auto"
    budget: bool = True
    extra: dict = _dict()

    def to_dict(self):
        out = {"version": self.version}
        out.update(_to_dict(self, skip=("version", "nodes", "edges", "groups")))
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

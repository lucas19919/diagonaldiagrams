"""Ids that come from content, so they stay the same across edits and renders.

The scene, the renderers, the outline and the exports all name edges through EdgeIds, so the id an
agent reads in a verdict is the id a patch, an export cell or a diff refers to.
"""


def edge_id(from_, to, label="", taken=()):
    """from->to, then :label when there is one, then #2, #3 for repeats of the same three."""
    base = f"{from_}->{to}" + (f":{label}" if label else "")
    eid, k = base, 1
    while eid in taken:
        k += 1
        eid = f"{base}#{k}"
    return eid


class EdgeIds:
    """Names a list of edges in order: an edge's own id when it has one, else edge_id()."""

    def __init__(self):
        self.taken = set()

    def __call__(self, from_, to, label="", given=None):
        eid = str(given) if given not in (None, "") else edge_id(from_, to, label or "", self.taken)
        self.taken.add(eid)
        return eid

    def generated(self, from_, to, label=""):
        """The id this edge would get without one of its own (nothing is recorded)."""
        return edge_id(from_, to, label or "", self.taken)


def edge_ids(edges, label="label"):
    """The ids of a v1 spec's edges, messages or relations, in their order: the ids the scene
    gives the same edges, so a verdict, an export and a patch all name an edge alike."""
    name = EdgeIds()
    return [name(e.get("from"), e.get("to"), e.get(label), e.get("id")) if isinstance(e, dict) else None
            for e in edges]


def compact(d):
    """A scene dict without the edge ids its edges would be given anyway (ids.py), for writing a
    spec back the way a person would write it."""
    name = EdgeIds()
    for e in d.get("edges") or []:
        gen = name.generated(e.get("from"), e.get("to"), e.get("label"))
        name(e.get("from"), e.get("to"), e.get("label"), e.get("id"))
        if e.get("id") == gen:
            e.pop("id")
    return d

"""The cascade (DESIGN 5.1): for each element, which declaration wins.

Cascade(sheets) takes stylesheets lowest priority first: core defaults, theme, toolkit sheets,
preset, files from --style or the figure's `style`, inline rules. An element's own `style` (on its
View) comes next, and a sheet marked "policy": true sits above everything. Within one sheet the more
specific selector wins, then the later rule. There is no !important.

A stylesheet is {"name", "extends": [bundled names], "tokens": {...}, "rules": {selector: {property:
value}}}; "extends" pulls in the bundled sheets (themes/*.json) first. Tokens merge in the same
order. Every selector and declaration is checked when the cascade is built, so a typo is an error
that names its sheet and rule, before anything is drawn.

computed(view, pseudo=None) gives {property: value} with values read by style.parse. Text
properties inherit from the parent view, and a pseudo-element (::label) inherits from its element.
Results are cached per element.
"""
from ..errors import SpecError
from . import parse
from .select import Selector
from .tokens import sheet as bundled_sheet

INHERITED = {"font-family", "font-size", "font-weight", "font-style", "color", "letter-spacing", "line-height",
             "text-transform", "text-align"}
SIDES = ("top", "right", "bottom", "left")


def expand(prop, raw):
    """A declaration as longhand declarations: border sets each side, background is fill, font sets
    its parts."""
    if prop == "border":
        return [(f"border-{s}", raw) for s in SIDES]
    if prop == "background":
        return [("fill", raw)]
    if prop == "font" and not isinstance(raw, dict):
        return list(parse.font(raw).items())
    return [(prop, raw)]


def _em(raw):
    return isinstance(raw, str) and raw.strip().endswith("em") and not raw.strip().endswith("rem")


class _Rule:
    __slots__ = ("selector", "decls", "rank")

    def __init__(self, selector, decls, rank):
        self.selector, self.decls, self.rank = selector, decls, rank


class Cascade:
    def __init__(self, sheets=()):
        self.sheets = []
        for s in sheets:
            self._add(s, set())
        self.tokens = {}
        for s in self.sheets:
            if not s.get("policy"):
                self.tokens.update(s.get("tokens") or {})
        for s in self.sheets:  # a policy's tokens win too
            if s.get("policy"):
                self.tokens.update(s.get("tokens") or {})
        self.rules = []
        for k, s in enumerate(self.sheets):
            layer = len(self.sheets) + 1 if s.get("policy") else k  # the element's own style ranks len(sheets)
            for order, (text, decls) in enumerate((s.get("rules") or {}).items()):
                where = f"stylesheet '{s.get('name', k)}', rule '{text}'"
                try:
                    sel = Selector(text)
                except SpecError as e:
                    raise SpecError(f"{where}: {e.msg}", e.fix, e.code) from None
                if not isinstance(decls, dict):
                    raise SpecError(f"{where}: the declarations should be an object", 'write {"stroke": "accent"}', "bad-style")
                self.rules.append(_Rule(sel, self._read(decls, where), (layer, sel.specificity, order)))
        self.rules.sort(key=lambda r: r.rank)
        self._cache = {}
        self._origins = {}  # (view, pseudo) -> {property: the layer (sheet index) that set it}

    def _add(self, s, seen):
        """A sheet and, before it, the bundled sheets it extends."""
        if isinstance(s, str):
            name = s
            if name in seen:
                return
            seen.add(name)
            s = bundled_sheet(name)
        if not isinstance(s, dict):
            raise SpecError(f"a stylesheet should be an object or a bundled name, not {type(s).__name__}",
                            'write {"tokens": {...}, "rules": {...}}', "bad-style")
        for base in s.get("extends") or []:
            self._add(base, seen)
        self.sheets.append(s)

    def _read(self, decls, where):
        """[(property, raw, value or None)]: checked now, read now unless it needs a font size."""
        out = []
        for prop, raw in decls.items():
            try:
                for p, r in expand(prop, raw):
                    if p not in parse.PROPERTIES:
                        parse.value(p, r)  # raises the did-you-mean
                    out.append((p, r, None if _em(r) else parse.value(p, r, self.tokens)))
            except SpecError as e:
                raise SpecError(f"{where}: {e.msg}", e.fix, e.code) from None
        return out

    def computed(self, view, pseudo=None):
        """The winning value of every property set for this element (and pseudo-element)."""
        key = (id(view), pseudo)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        if pseudo is not None:
            base = self.computed(view, None)
        else:
            base = self.computed(view.parent, None) if view.parent is not None else {}
        out = {p: v for p, v in base.items() if p in INHERITED}
        base_from = self._origins.get((id(view), None) if pseudo is not None else
                                      (id(view.parent), None) if view.parent is not None else None, {})
        origin = {p: base_from.get(p, -1) for p in out}
        decls = []
        for rule in self.rules:
            if rule.selector.pseudo_element == pseudo and rule.selector.matches(view):
                decls.append((rule.rank, rule.decls))
        if pseudo is None and view.style:
            decls.append(((len(self.sheets), (0, 0, 0), 0), self._read(view.style, f"the style of '{view.id}'")))
            decls.sort(key=lambda d: d[0])
        # font-size first, so em lengths read against the element's own size
        for rank, ds in decls:
            for p, raw, val in ds:
                if p == "font-size":
                    out[p] = val if val is not None else parse.length(raw, out.get("font-size", 16.0))
                    origin[p] = rank[0]
        for rank, ds in decls:
            for p, raw, val in ds:
                if p != "font-size":
                    out[p] = val if val is not None else parse.value(p, raw, self.tokens, out.get("font-size"))
                    origin[p] = rank[0]
        self._cache[key] = out
        self._origins[key] = origin
        return out

    def origin(self, view, pseudo, prop):
        """The layer that set a property for this element: the sheet's index in self.sheets, the
        number of sheets for the element's own style, more for a policy, -1 when nothing did."""
        self.computed(view, pseudo)
        return self._origins[(id(view), pseudo)].get(prop, -1)

    def token(self, name, default=None):
        return self.tokens.get(name, self.tokens.get(name.replace("_", "-"), default))


def scene_views(scene):
    """Views for a scene: {"figure": View, "nodes": {id: View}, "groups": {...}, "edges": {...}}.
    Containers follow the scene's group tree (DESIGN 4.5); edges sit in the figure."""
    from .select import View
    fig = View("figure", "figure", fields={"title": scene.title, "preset": scene.preset})
    out = {"figure": fig, "nodes": {}, "groups": {}, "edges": {}}
    indeg, outdeg = {}, {}
    for e in scene.edges:
        outdeg[e.from_] = outdeg.get(e.from_, 0) + 1
        indeg[e.to] = indeg.get(e.to, 0) + 1

    def make(parent_id, parent_view):
        kids = scene.children(parent_id)
        groups = [el for el in kids if el.__class__.__name__ == "Group"]
        nodes = [el for el in kids if el.__class__.__name__ != "Group"]
        for k, el in enumerate(groups):  # positions count among siblings of the same type
            v = View("group", el.id, el.classes, {"id": el.id, "name": el.name, "tag": el.tag}, {}, parent_view,
                     k, len(groups), style=el.style)
            out["groups"][el.id] = v
            make(el.id, v)
        for k, el in enumerate(nodes):
            fields = {"id": el.id, "name": el.name, "sub": el.sub, "tag": el.tag, "icon": el.icon, "shape": el.shape,
                      "group": el.group, "rank": el.rank, "lane": el.lane, "focal": el.focal}
            out["nodes"][el.id] = View("node", el.id, el.classes, fields, el.data, parent_view, k, len(nodes),
                                       indeg.get(el.id, 0), outdeg.get(el.id, 0), style=el.style)
    make(None, fig)
    for k, e in enumerate(scene.edges):
        fields = {"id": e.id, "from": e.from_, "to": e.to, "label": e.label, "proto": e.proto, "async": e.async_,
                  "reply": e.reply, "focal": e.focal}
        out["edges"][e.id] = View("edge", e.id, e.classes, fields, e.data, fig, k, len(scene.edges), style=e.style)
    return out

"""One diagram's computed styles (PLAN P3.8): what the painters read instead of constants.

Styler(spec, kind, theme, corners, sheets) builds the cascade for a flow, arch, seq or schema spec:
the theme (with any --theme-file overrides as tokens), the preset's stylesheet (presets/KIND.json,
which states today's look as rules, with --corners as its node radius), the spec's own `style`
sheets, and any further sheets. node(), edge() and group() read it into small dicts of painting
values; marker() names the arrowhead for a stroke color.
"""
import copy

from .cascade import Cascade, scene_views
from .select import View
from .tokens import THEME_NAMES, sheet, token_name, v1_theme

CORNER_RX = {"sharp": 0, "rounded": 10, "editorial": 6}
TEXT = ("font-family", "font-size", "font-weight", "font-style", "color", "text-transform", "letter-spacing")
MARKERS = (("muted", "a"), ("accent", "aa"), ("link", "al"), ("soft", "ar"))  # marker_defs' ids


def css(v):
    """A computed value as SVG text: a Color's text, a number or None as they are."""
    return v.css if hasattr(v, "css") else v


def spec_sheets(style):
    """A spec's `style` field as a list of stylesheets, an unnamed one called "the spec's style"."""
    sheets = [] if style is None else (style if isinstance(style, list) else [style])
    return [dict(s, name=s.get("name") or ("the spec's style" if len(sheets) == 1 else f"the spec's style {k + 1}"))
            if isinstance(s, dict) else s for k, s in enumerate(sheets)]


def check_styles(spec, kind=None):
    """Problems with a spec's stylesheets and element styles, as validate's {"msg", "fix"} errors,
    so a typo in a rule, or a border on a side a shape doesn't have, is reported with the spec's
    other errors instead of at draw time."""
    from ..deco import declared
    from ..errors import SpecError
    from ..inputs.v1 import KINDS, detect
    if not isinstance(spec, dict):
        return []
    try:
        cascade = Cascade(["editorial", *spec_sheets(spec.get("style"))])
    except SpecError as e:
        return [{"msg": e.msg, "fix": e.fix}]
    out = []
    for key in ("nodes", "edges", "groups", "actors", "messages", "tables", "relations"):
        for el in spec.get(key) or []:
            if isinstance(el, dict) and isinstance(el.get("style"), dict):
                try:
                    cascade._read(el["style"], f"the style of '{el.get('id', el.get('from', '?'))}'")
                except SpecError as e:
                    out.append({"msg": e.msg, "fix": e.fix})
    if out:
        return out
    kind = kind if kind in KINDS else detect(spec)
    try:
        sty = Styler(spec, kind)
        for key in ("nodes", "actors", "tables"):
            for el in spec.get(key) or []:
                if isinstance(el, dict) and "id" in el:
                    shape = "table" if key == "tables" else el.get("shape", "rect")
                    declared(sty.node(el["id"])["computed"], shape)
    except SpecError as e:
        out.append({"msg": e.msg, "fix": e.fix})
    return out


class Styler:
    def __init__(self, spec, kind, theme=None, corners="editorial", sheets=()):
        theme = theme or v1_theme("editorial")
        name = theme.get("_name")
        base = name if name in THEME_NAMES else "editorial"
        plain = v1_theme(base)
        overrides = {token_name(k): v for k, v in theme.items() if not k.startswith("_") and plain.get(k) != v}
        preset = copy.deepcopy(sheet(kind))
        node_rule = preset.setdefault("rules", {}).setdefault("node", {})
        node_rule.setdefault("border-radius", CORNER_RX.get(corners, 6))  # --corners, as a rule (B15)
        scene = self._scene(spec, kind)
        own = spec_sheets(scene.style) if scene is not None else []
        self.cascade = Cascade([base, {"name": "theme-file", "tokens": overrides}, preset, *own, *sheets])
        self.views = scene_views(scene) if scene is not None else {"figure": View("figure", "figure"), "nodes": {},
                                                                   "groups": {}, "edges": {}}
        self._generic = {k: View(k, parent=self.views["figure"]) for k in ("node", "edge", "group")}
        self.markers = {self.token(t): mid for t, mid in MARKERS}
        self.extra_markers = {}  # color -> id, for strokes no default marker matches

    @staticmethod
    def _scene(spec, kind):
        from ..inputs.v1 import from_v1
        from ..scene import check
        if not isinstance(spec, dict):
            return None
        scene, errors, _ = check(from_v1({k: v for k, v in spec.items() if not str(k).startswith("_")}, kind))
        return None if errors else scene

    def token(self, name):
        return css(self.cascade.token(name))

    def view(self, kind, eid):
        return self.views[kind + "s"].get(str(eid)) or self._generic[kind]

    def _text(self, v, pseudo):
        c = self.cascade.computed(v, pseudo)
        return {k: css(c.get(k)) for k in TEXT}

    def node(self, nid):
        v = self.view("node", nid)
        c = self.cascade.computed(v)
        r = c.get("border-radius")
        return {"fill": css(c.get("fill")), "stroke": css(c.get("stroke")), "stroke-width": c.get("stroke-width"),
                "radius": r[0] if isinstance(r, tuple) else r, "radii": r, "paper": self.token("paper"),
                "label": self._text(v, "label"), "sub": self._text(v, "sub"), "tag": self._text(v, "tag"),
                "computed": c}

    def table(self, tid):
        """A schema table: its card (the node), its ::header band, its name (::label) and tag."""
        v = self.view("node", tid)
        st = self.node(tid)
        st["header"] = css(self.cascade.computed(v, "header").get("fill"))
        return st

    def edge(self, eid):
        v = self.view("edge", eid)
        c = self.cascade.computed(v)
        return {"stroke": css(c.get("stroke")), "stroke-width": c.get("stroke-width"), "dasharray": c.get("stroke-dasharray"),
                "label": self._text(v, "label"), "paper": self.token("paper"), "computed": c}

    def marker(self, color):
        """The arrowhead id for a stroke color: the default ones by name, others made on demand."""
        if color in self.markers:
            return self.markers[color]
        if color not in self.extra_markers:
            self.extra_markers[color] = f"m{len(self.extra_markers) + 1}"
        return self.extra_markers[color]

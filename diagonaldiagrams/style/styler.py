"""One diagram's computed styles: what the painters read instead of constants.

Styler(spec, kind, theme, corners, sheets) builds the cascade for a flow, arch, seq or schema spec:
the theme (with any --theme-file overrides as tokens), the preset's stylesheet (presets/KIND.json,
which states today's look as rules, with --corners as its node radius), the spec's own `style`
sheets, and any further sheets. node(), edge() and group() read it into small dicts of painting
values; marker() names the arrowhead for a stroke color.
"""
from .cascade import Cascade, scene_views
from .encode import Scale, is_encoding
from .select import View
from .tokens import THEME_NAMES, sheet, token_name, v1_theme

CORNER_RX = {"sharp": 0, "rounded": 10, "editorial": 6}
TEXT = ("font-family", "font-size", "font-weight", "font-style", "color", "text-transform", "letter-spacing",
        "line-height", "max-lines", "overflow")
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


def _copied(v):
    """A stylesheet's JSON copied all the way down, as copy.deepcopy would (without loading copy)."""
    if isinstance(v, dict):
        return {k: _copied(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_copied(x) for x in v]
    return v


def _look(c):
    """The one visual a legend swatch shows for a rule: a side's border color, else the fill, else
    the stroke."""
    for side in ("top", "left", "right", "bottom", "top-left", "top-right", "bottom-right", "bottom-left"):
        b = c.get(f"border-{side}")
        if b and b.get("width") and b.get("color") is not None:
            return {"border": css(b["color"]), "side": side}
    if c.get("fill") is not None and not isinstance(c.get("fill"), dict):
        return {"fill": css(c["fill"]), "stroke": css(c.get("stroke"))}
    return {"stroke": css(c.get("stroke"))}


class Styler:
    def __init__(self, spec, kind, theme=None, corners="editorial", sheets=(), narrow=None):
        """narrow: a box's widest before its text wraps (px), for a figure bound for a narrow place
        (diagrams.FITS); it lowers the preset's max-width, under every stylesheet's own."""
        theme = theme or v1_theme("editorial")
        name = theme.get("_name")
        base = name if name in THEME_NAMES else "editorial"
        plain = v1_theme(base)
        overrides = {token_name(k): v for k, v in theme.items() if not k.startswith("_") and plain.get(k) != v}
        preset = _copied(sheet(kind))
        node_rule = preset.setdefault("rules", {}).setdefault("node", {})
        node_rule.setdefault("border-radius", CORNER_RX.get(corners, 6))  # --corners, as a rule
        if narrow and isinstance(node_rule.get("max-width"), (int, float)):
            node_rule["max-width"] = min(node_rule["max-width"], narrow)
        scene = self._scene(spec, kind)
        own = spec_sheets(scene.style) if scene is not None else []
        self.cascade = Cascade([base, {"name": "theme-file", "tokens": overrides}, preset, *own, *sheets])
        self.preset_layer = max(k for k, s in enumerate(self.cascade.sheets) if s is preset or s.get("name") == kind)
        self.views = scene_views(scene) if scene is not None else {"figure": View("figure", "figure"), "nodes": {},
                                                                   "groups": {}, "edges": {}}
        self._generic = {k: View(k, parent=self.views["figure"]) for k in ("node", "edge", "group")}
        self.markers = {self.token(t): mid for t, mid in MARKERS}
        self.extra_markers = {}  # color -> id, for strokes no default marker matches
        self._fonts = {}
        self.font_files = {}  # family -> font file, from the stylesheets' "fonts"
        for s in self.cascade.sheets:
            self.font_files.update(s.get("fonts") or {})
        self._memo = {}  # (kind, id) -> painting values: styles don't change while a render's drafts are drawn
        self._scales = {}
        self.scales = {}  # (type, property, field) -> Scale: the encodings drawn, for the legend
        self.rule_legends = {}  # legend text -> the look it names, from rules with "legend"

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

    def _text(self, v, pseudo, background=None):
        raw = self.cascade.computed(v, pseudo)
        # elements whose computed style is one shared dict (Cascade.computed) read the same text style
        # off it, unless an encoding reads their own data: worked out once, a copy handed to each
        key = ("text", id(raw), id(background))
        hit = self._memo.get(key)
        if hit is not None and hit[0] is raw and hit[1] is background:
            return dict(hit[2])
        c = self._encoded(v, raw)
        out = {k: css(c.get(k)) for k in TEXT}
        out["font"], missing = self._font(out)
        if missing:
            out["font-fallback"] = missing
        if background is not None and c.get("color") is not None and \
                self.cascade.origin(v, pseudo, "color") <= self.preset_layer:
            out["color"] = self._readable(c["color"], background)
        for prop in ("color", "font-size"):  # a stylesheet's choice is marked, so the audit can name it
            if self.cascade.origin(v, pseudo, prop) > self.preset_layer:
                out[f"{prop}-from"] = self.cascade.source(v, pseudo, prop)
        if c is raw:
            self._memo[key] = (raw, background, out)
            return dict(out)
        return out

    def _readable(self, fg, bg):
        """A default text color that stays readable when the fill under it changes (a data-driven fill,
        a dark brand color): kept if it meets WCAG AA (4.5:1), else ink or paper, whichever reads
        better, or black or white when neither of those meets it on a mid-tone fill (one of the two
        always does). A color a stylesheet chose is never changed here; the contrast check judges it."""
        from .parse import Color, color, readable
        if not isinstance(bg, Color):
            return css(fg)
        key = ("readable", css(fg), bg.css)
        if key not in self._memo:
            fg = color(fg)
            pick = readable(fg, bg, color(self.token("ink")), color(self.token("paper")))
            self._memo[key] = css(fg) if pick is fg else pick.css
        return self._memo[key]

    def _font(self, text_style):
        """(the font file measuring this text, or None; a named family that wasn't found, or None)."""
        from ..text.fonts import FontError, find
        weight = str(text_style.get("font-weight") or "400")
        weight = 700 if weight == "bold" else int(weight) if weight.isdigit() else 400
        italic = text_style.get("font-style") in ("italic", "oblique")
        key = (text_style.get("font-family"), weight, italic)
        if key not in self._fonts:
            try:
                self._fonts[key] = find(text_style.get("font-family"), weight, italic, self.font_files)
            except FontError as e:
                from ..errors import SpecError
                raise SpecError(str(e), "check the path in the stylesheet's \"fonts\"", "bad-font") from None
        return self._fonts[key]

    def off_brand(self, palette=None, fonts=None):
        """What breaks the brand policy: every rule or element style that tries to override
        a value the policy locks, and every color or font a stylesheet chose outside what the config
        allows. Values the theme and presets set are not judged: the policy controls their tokens."""
        from .parse import Color, color
        texts = ("label", "sub", "tag", "title", "header", "caption", "eyebrow")
        views = [self.views["figure"], *self.views["groups"].values(), *self.views["nodes"].values(),
                 *self.views["edges"].values()]
        allowed = None
        if palette is not None:
            allowed = []
            for c in palette:
                try:
                    allowed.append(color(c, self.cascade.tokens))
                except Exception:
                    pass
        issues, seen = [], set()
        for v in views:
            for pseudo in (None,) + texts:
                c = self.cascade.computed(v, pseudo)
                for prop, val in c.items():
                    layer = self.cascade.origin(v, pseudo, prop)
                    if layer <= self.preset_layer or layer == self.cascade.policy_layer:
                        continue
                    where = self.cascade.source(v, pseudo, prop)
                    values = [val] if isinstance(val, Color) else \
                        [val.get("color")] if isinstance(val, dict) and isinstance(val.get("color"), Color) else []
                    for cv in values:
                        if allowed is not None and cv.a > 0 and not any(cv == a for a in allowed) and (where, cv.css) not in seen:
                            seen.add((where, cv.css))
                            issues.append({"code": "off-brand", "msg": f"{where} uses {cv.css} for {prop}, which is not in "
                                                                       "the allowed palette",
                                           "fix": "use one of the palette's colors or tokens"})
                    if prop == "font-family" and fonts is not None:
                        first = str(val).split(",")[0].strip().strip("'\"").lower()
                        if first not in fonts and (where, first) not in seen:
                            seen.add((where, first))
                            issues.append({"code": "off-brand", "msg": f"{where} uses the font '{first}', which is not "
                                                                       "an allowed font",
                                           "fix": f"use one of: {', '.join(sorted(fonts))}"})
        for a in self.cascade.attempts.values():
            issues.append({"code": "off-brand", "msg": f"{a['rule']} sets {a['property']}, which {a['policy']} locks",
                           "fix": "drop the declaration: the brand policy decides it"})
        return issues

    def used_fonts(self):
        """The font files that measured some text, one per file."""
        seen = {}
        for font, _ in self._fonts.values():
            if font is not None:
                seen.setdefault((font.path, font.index), font)
        return list(seen.values())

    def embed(self, asked=False):
        """(an SVG <style> element embedding the fonts used, or None; families that forbid embedding).
        asked is --embed-fonts; the figure's font-embed property asks too. Each font file goes in whole
        (fonts are not subset), so a big one costs file size: the audit's large-font warns."""
        if not (asked or self.cascade.computed(self.views["figure"]).get("font-embed")):
            return None, []
        import base64
        from ..paint import el
        faces, refused = [], []
        for font in self.used_fonts():
            if not font.embeddable():
                refused.append(font.family)
                continue
            with open(font.path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            kind = {".otf": "font/otf", ".woff": "font/woff"}.get(font.path[-4:].lower(), "font/ttf")
            faces.append(f"@font-face {{ font-family: '{font.family}'; font-weight: {font.weight}; "
                         f"font-style: {'italic' if font.italic else 'normal'}; src: url(data:{kind};base64,{data}); }}")
        if not faces:
            return None, refused
        return el("style", "\n".join(faces), role="figure.fonts"), refused

    def _encoded(self, v, c):
        """Computed values with any {field, scale} read against this element's data,
        and its legend text noted."""
        if "legend" in c and isinstance(c["legend"], str):
            self.rule_legends.setdefault(c["legend"], (v.type, c))
        if not any(is_encoding(x) for x in c.values()):
            return c
        c = dict(c)
        for prop, enc in list(c.items()):
            if is_encoding(enc):
                scale = self._scale(v.type, prop, enc)
                c[prop] = scale(v.attr(enc["field"]))
                self.scales.setdefault((v.type, prop, enc["field"]), scale)
        return c

    def _scale(self, kind, prop, enc):
        import json
        key = (kind, prop, json.dumps(enc, sort_keys=True, default=str))
        if key not in self._scales:
            values = [v.attr(enc["field"]) for v in self.views.get(kind + "s", {}).values()]
            self._scales[key] = Scale(prop, enc, values, self.cascade.tokens)
        return self._scales[key]

    def legend_entries(self):
        """What the legend lists beyond the preset's sentence: every scale an encoding used, then every
        rule with a legend text. Reading every element's style first finds them all. Worked out once."""
        if ("legend", None) not in self._memo:
            self._memo[("legend", None)] = self._legend_entries()
        return self._memo[("legend", None)]

    def _legend_entries(self):
        for nid in list(self.views["nodes"]):
            self.node(nid)
        for eid in list(self.views["edges"]):
            self.edge(eid)
        out = []
        for (kind, prop, field), scale in self.scales.items():
            out.append({"type": "scale", "field": field, "prop": prop, "steps": scale.legend()})
        for text, (kind, c) in self.rule_legends.items():
            out.append({"type": "rule", "text": text, "kind": kind, "look": _look(c)})
        return out

    def node(self, nid):
        key = ("node", nid)
        if key not in self._memo:
            self._memo[key] = self._node(nid)
        return self._memo[key]

    def _node(self, nid):
        v = self.view("node", nid)
        c = self._encoded(v, self.cascade.computed(v))
        r = c.get("border-radius")
        fill = c.get("fill")
        return {"fill": css(fill), "stroke": css(c.get("stroke")), "stroke-width": c.get("stroke-width"),
                "radius": r[0] if isinstance(r, tuple) else r, "radii": r, "paper": self.token("paper"),
                "label": self._text(v, "label", fill), "sub": self._text(v, "sub", fill),
                "tag": self._text(v, "tag", fill), "computed": c}

    def table(self, tid):
        """A schema table: its card (the node), its ::header band, its name (::label) and tag."""
        v = self.view("node", tid)
        st = dict(self.node(tid))
        st["header"] = css(self.cascade.computed(v, "header").get("fill"))
        return st

    def figure(self):
        """The figure's own parts: paper, title and subtitle, the legend, notes (annotations)."""
        if ("figure", None) not in self._memo:
            self._memo[("figure", None)] = self._figure()
        return self._memo[("figure", None)]

    def _figure(self):
        fig = self.views["figure"]
        c = self.cascade.computed(fig)
        legend = self._part("legend")
        note = self._part("annotation")
        return {"paper": css(c.get("fill")) or self.token("paper"), "title": self._text(fig, "title"),
                "sub": self._text(fig, "sub"), "eyebrow": self._text(fig, "eyebrow"), "caption": self._text(fig, "caption"),
                "legend": dict(self._text(legend, None), stroke=css(self.cascade.computed(legend).get("stroke"))),
                "note": dict(self._text(note, None), stroke=css(self.cascade.computed(note).get("stroke")),
                             fill=css(self.cascade.computed(note).get("fill")))}

    def _part(self, kind):
        if kind not in self._generic:
            self._generic[kind] = View(kind, parent=self.views["figure"])
        return self._generic[kind]

    def group(self, gid):
        """A group's frame (fill, stroke, dash, radius) and its title text."""
        if ("group", gid) not in self._memo:
            self._memo[("group", gid)] = self._group(gid)
        return self._memo[("group", gid)]

    def _group(self, gid):
        v = self.view("group", gid)
        c = self.cascade.computed(v)
        r = c.get("border-radius")
        return {"fill": css(c.get("fill")), "stroke": css(c.get("stroke")), "dasharray": c.get("stroke-dasharray"),
                "radius": r[0] if isinstance(r, tuple) else r, "title": self._text(v, "title"), "computed": c}

    def edge(self, eid):
        key = ("edge", eid)
        if key not in self._memo:
            self._memo[key] = self._edge(eid)
        return self._memo[key]

    def _edge(self, eid):
        v = self.view("edge", eid)
        c = self._encoded(v, self.cascade.computed(v))
        return {"stroke": css(c.get("stroke")), "stroke-width": c.get("stroke-width"), "dasharray": c.get("stroke-dasharray"),
                "label": self._text(v, "label"), "paper": self.token("paper"), "computed": c}

    def marker(self, color):
        """The arrowhead id for a stroke color: the default ones by name, others made on demand."""
        if color in self.markers:
            return self.markers[color]
        if color not in self.extra_markers:
            self.extra_markers[color] = f"m{len(self.extra_markers) + 1}"
        return self.extra_markers[color]

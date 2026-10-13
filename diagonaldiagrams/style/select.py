"""Selectors (DESIGN 5.2): which elements a rule applies to.

    node                     a type: figure, node, edge, group, chart, mark, axis, legend, annotation, *
    #api  .db                an id, a class
    [team]  [team=pay]  [team!=pay]  [proto^=http]  [p99>200]  [p99<50]
                             attributes resolve against the element's fields, then its data
    group#core node          descendant (any depth)      group#core > node   child
    :focal :source :sink :first-child :last-child :nth-child(2) :not(.db)
    ::label ::sub ::tag ::icon ::title ::header ::marker-end ::marker-start

Positions (:first-child, :last-child, :nth-child) count among siblings of the same type, as CSS's
:first-of-type does: a group's nodes and its sub-groups are separate lists in a scene.

Specificity is CSS's: (ids, classes + attributes + pseudo-classes, types + pseudo-element); :not()
counts its argument. Matching reads an element view (View), not the drawing, so the same selector
works on every preset. Errors are SpecError("bad-selector") with a did-you-mean.
"""
import re

from ..errors import SpecError

TYPES = ("figure", "node", "edge", "group", "chart", "mark", "axis", "legend", "annotation", "*")
PSEUDO_CLASSES = ("focal", "source", "sink", "first-child", "last-child", "nth-child", "not")
PSEUDO_ELEMENTS = ("label", "sub", "tag", "icon", "title", "header", "marker-end", "marker-start", "caption", "eyebrow")
_TOKEN = re.compile(r"""
    (?P<ws>\s*>\s*|\s+)                       # a combinator
  | (?P<pe>::[\w-]+)                          # a pseudo-element
  | (?P<pc>:[\w-]+(?:\((?P<arg>[^()]*(?:\([^()]*\))?[^()]*)\))?)   # a pseudo-class, maybe with an argument
  | (?P<id>\#[\w-]+)
  | (?P<cls>\.[\w-]+)
  | (?P<attr>\[\s*(?P<an>[\w.-]+)\s*(?:(?P<op>!=|\^=|>=|<=|=|>|<)\s*(?P<av>"[^"]*"|'[^']*'|[^\]]*?))?\s*\])
  | (?P<type>\*|[A-Za-z][\w-]*)
""", re.X)


def _err(msg, fix, near=None):
    return SpecError(msg + (f" (did you mean '{near}'?)" if near else ""), fix, "bad-selector")


def _near(word, words):
    import difflib
    hit = difflib.get_close_matches(word, list(words), n=1, cutoff=0.7)
    return hit[0] if hit else None


class Compound:
    """One step of a selector: a type and its filters."""
    __slots__ = ("type", "ids", "classes", "attrs", "pseudos")

    def __init__(self):
        self.type, self.ids, self.classes, self.attrs, self.pseudos = None, [], [], [], []

    def specificity(self):
        a, b, c = len(self.ids), len(self.classes) + len(self.attrs), 1 if self.type not in (None, "*") else 0
        for name, arg in self.pseudos:
            if name == "not":
                na, nb, nc = arg.specificity
                a, b, c = a + na, b + nb, c + nc
            else:
                b += 1
        return a, b, c


class Selector:
    """A parsed selector: compounds joined by combinators, and an optional pseudo-element."""

    def __init__(self, text):
        self.text = text.strip()
        self.steps = []  # [(combinator before it: None, " " or ">"), Compound]
        self.pseudo_element = None
        self._parse()
        a, b, c = 0, 0, 1 if self.pseudo_element else 0
        for _, comp in self.steps:
            x, y, z = comp.specificity()
            a, b, c = a + x, b + y, c + z
        self.specificity = (a, b, c)

    def _parse(self):
        text = self.text
        if not text:
            raise _err("an empty selector", "write a type, an #id or a .class, e.g. node.db")
        pos, comp, comb = 0, Compound(), None
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m or m.end() == pos:
                raise _err(f"'{text}' has something a selector can't hold at '{text[pos:pos + 12]}'",
                           "use types, #ids, .classes, [attr=value], :pseudo-classes and ::pseudo-elements")
            pos = m.end()
            if self.pseudo_element and m.lastgroup != "ws":
                raise _err(f"'{text}': a ::pseudo-element ends a selector", "move it to the end")
            if m.group("ws") is not None:
                if pos >= len(text):
                    break
                if not (comp.type or comp.ids or comp.classes or comp.attrs or comp.pseudos):
                    if ">" in m.group("ws"):
                        raise _err(f"'{text}' starts with a combinator", "write the parent first: group > node")
                    continue
                self.steps.append((comb, comp))
                comp, comb = Compound(), ">" if ">" in m.group("ws") else " "
                continue
            kind = m.lastgroup
            if kind == "type":
                word = m.group("type").lower()
                if comp.type is not None:
                    raise _err(f"'{text}' names two types in one step", "join them with a space or >")
                if word not in TYPES:
                    raise _err(f"'{word}' is not an element type", f"use one of: {', '.join(TYPES)}", _near(word, TYPES))
                comp.type = word
            elif kind == "id":
                comp.ids.append(m.group("id")[1:])
            elif kind == "cls":
                comp.classes.append(m.group("cls")[1:])
            elif m.group("attr") is not None:
                value = m.group("av")
                if value is not None:
                    value = value.strip()
                    if value[:1] in "\"'" and value[-1:] == value[:1]:
                        value = value[1:-1]
                    if m.group("op") in (">", "<", ">=", "<=") and not _num_ok(value):
                        raise _err(f"'{text}': {m.group('op')} compares numbers, and '{value}' is not one",
                                   f"write [{m.group('an')}{m.group('op')}100]")
                comp.attrs.append((m.group("an"), m.group("op"), value))
            elif m.group("pe") is not None:
                name = m.group("pe")[2:]
                if name not in PSEUDO_ELEMENTS:
                    raise _err(f"'::{name}' is not a pseudo-element", f"use one of: {', '.join('::' + p for p in PSEUDO_ELEMENTS)}",
                               "::" + (_near(name, PSEUDO_ELEMENTS) or "") if _near(name, PSEUDO_ELEMENTS) else None)
                self.pseudo_element = name
            else:
                full = m.group("pc")[1:]
                name = full.split("(")[0]
                if name not in PSEUDO_CLASSES:
                    near = _near(name, PSEUDO_CLASSES)
                    raise _err(f"':{name}' is not a pseudo-class", f"use one of: {', '.join(':' + p for p in PSEUDO_CLASSES)}",
                               ":" + near if near else None)
                arg = m.group("arg")
                if name == "not":
                    if not arg:
                        raise _err(f"'{text}': :not() needs a selector", "write :not(.db)")
                    arg = Selector(arg)
                elif name == "nth-child":
                    if not arg or not arg.strip().isdigit() or int(arg) < 1:
                        raise _err(f"'{text}': :nth-child() takes a position from 1", "write :nth-child(2)")
                    arg = int(arg)
                elif arg is not None:
                    raise _err(f"':{name}' takes no argument", f"write :{name}")
                comp.pseudos.append((name, arg))
        if comp.type or comp.ids or comp.classes or comp.attrs or comp.pseudos:
            self.steps.append((comb, comp))
        elif self.pseudo_element and not self.steps:
            raise _err(f"'{text}': a pseudo-element needs an element", "write node::label")

    def matches(self, view):
        """Whether this selector picks the element view (pseudo-elements aside)."""
        return _match(self.steps, len(self.steps) - 1, view)

    def __repr__(self):
        return f"Selector({self.text!r})"


def _num_ok(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _match(steps, k, view):
    comb, comp = steps[k]
    if view is None or not _compound(comp, view):
        return False
    if k == 0:
        return True
    if comb == ">":
        return _match(steps, k - 1, view.parent)
    up = view.parent
    while up is not None:
        if _match(steps, k - 1, up):
            return True
        up = up.parent
    return False


def _compound(comp, v):
    if comp.type not in (None, "*") and comp.type != v.type:
        return False
    if any(i != v.id for i in comp.ids):
        return False
    if any(c not in v.classes for c in comp.classes):
        return False
    for name, op, value in comp.attrs:
        got = v.attr(name)
        if op is None:
            if got is None or got is False:
                return False
            continue
        if got is None:
            if op != "!=":
                return False
            continue
        if op in (">", "<", ">=", "<="):
            if not _num_ok(got):
                return False
            a, b = float(got), float(value)
            if not {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]:
                return False
            continue
        text = str(got).lower() if isinstance(got, bool) else str(got)
        if op == "=" and text != value or op == "!=" and text == value or op == "^=" and not text.startswith(value):
            return False
    for name, arg in comp.pseudos:
        if name == "focal" and not v.attr("focal"):
            return False
        if name == "source" and v.indegree != 0:
            return False
        if name == "sink" and v.outdegree != 0:
            return False
        if name == "first-child" and v.index != 0:
            return False
        if name == "last-child" and v.index != v.siblings - 1:
            return False
        if name == "nth-child" and v.index != arg - 1:
            return False
        if name == "not" and arg.matches(v):
            return False
    return True


class View:
    """What a selector sees of one element: its type, id, classes, fields and data, its container
    (parent view), its place among its siblings, for nodes their edge counts, and its own style
    declarations (which rank above every stylesheet but the policy)."""
    __slots__ = ("type", "id", "classes", "fields", "data", "parent", "index", "siblings", "indegree", "outdegree",
                 "style")

    def __init__(self, type, id=None, classes=(), fields=None, data=None, parent=None, index=0, siblings=1,
                 indegree=None, outdegree=None, style=None):
        self.type, self.id, self.classes = type, id, set(classes)
        self.fields, self.data, self.parent = fields or {}, data or {}, parent
        self.index, self.siblings, self.indegree, self.outdegree = index, siblings, indegree, outdegree
        self.style = style or {}

    def attr(self, name):
        """A field first, then data; dotted names reach into data (data.team works too)."""
        if name.startswith("data."):
            return self.data.get(name[5:])
        if name in self.fields and self.fields[name] not in (None, ""):
            return self.fields[name]
        return self.data.get(name)

    def __repr__(self):
        return f"View({self.type}#{self.id})"

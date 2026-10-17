"""Stories (DESIGN 21.2): one figure, several views of it, presented from one HTML page.

    {"title": "How a request moves",
     "figure": {"type": "arch", "spec": "platform.json"},   # "spec" a path or an object; Mermaid: "type": "mermaid"
     "views": [{"id": "all", "title": "The platform", "text": "...", "notes": "..."},
               {"id": "runtime", "focus": "group#runtime", "dim": "node:not(group#runtime node)", "highlight": "#agent"},
               {"id": "path", "dim": "*", "reveal": ["#web", "#gw", "#agent", "#llm"]}]}

A view draws the figure with looks of its own and points the camera at part of it:
- dim: those elements at low opacity; hide: not drawn at all;
- highlight: in the accent color with a heavier line, and never dimmed;
- reveal: elements shown one step at a time, at full strength; an arrow shows once both its ends do;
- focus: the camera frames those elements;
- motion: what moves while the view shows (motion.py, DESIGN 21.2.1): a packet tracing a path,
  dots flowing along arrows. It draws in a layer above the figure, which itself never changes.

Selectors are the stylesheet's (DESIGN 5.2); a comma lists several. Looks change color and opacity
only, so every view and reveal step (a frame) has the same layout, and moving between frames is a
change of looks and of camera, which the page animates. The engine resolves every selector and says
when one matches nothing; the page only plays the frames.
"""
import copy
import json
import os

from .errors import SpecError

DIM = 0.18          # a dimmed element's opacity
HEAVY = 2.6         # a highlighted line's width
PAD = 36            # around the focused elements
MIN_FOCUS = 280     # the narrowest the camera goes, so one box doesn't fill the page
KEYS = ("id", "title", "text", "notes", "focus", "dim", "hide", "highlight", "reveal", "motion")
KINDS = ("flow", "arch", "seq", "schema")
LISTS = {"flow": ("nodes", "edges"), "arch": ("nodes", "edges"), "seq": ("actors", "messages"), "schema": ("tables", "relations")}


def split(text):
    """A selector list: "a, b:not(.x, .y)" -> ["a", "b:not(.x, .y)"]."""
    out, depth, cur = [], 0, ""
    for ch in text:
        depth += ch in "([" and 1 or (ch in ")]" and -1 or 0)
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def match(sty, selectors):
    """{"nodes": ids, "edges": ids, "groups": ids} that a selector text (or a list of them) matches."""
    from .style.select import Selector
    texts = selectors if isinstance(selectors, list) else [selectors]
    out = {"nodes": set(), "edges": set(), "groups": set()}
    for text in texts:
        for one in split(str(text)):
            sel = Selector(one)
            for kind in out:
                for eid, view in sty.views[kind].items():
                    if sel.matches(view):
                        out[kind].add(eid)
    return out


def _empty(m):
    return not (m["nodes"] or m["edges"] or m["groups"])


def _ends(spec, kind):
    """{edge id: (from, to)} as the renderer names the edges."""
    from .scene.ids import edge_ids
    edges = spec.get(LISTS[kind][1]) or []
    return {eid: (e.get("from"), e.get("to")) for eid, e in zip(edge_ids(edges), edges)}


def frames(story, spec, kind, sty):
    """The story's frames: [{"view": index, "step": k, "steps": n, "looks": {(kind, id): style}, "focus": ids}],
    and warnings for selectors that match nothing."""
    ends = _ends(spec, kind)
    warnings, out = [], []
    for vi, view in enumerate(story["views"]):
        def sel(key, value=None):
            value = view.get(key) if value is None else value
            if value in (None, "", []):
                return {"nodes": set(), "edges": set(), "groups": set()}
            try:
                m = match(sty, value)
            except SpecError as e:
                raise SpecError(f"view '{view['id']}' {key}: {e.msg}", e.fix, "bad-selector")
            if _empty(m):
                warnings.append({"msg": f"view '{view['id']}': {key} {json.dumps(value)} matches nothing",
                                 "fix": "name boxes by #id, frames by group#id; the figure's ids are its spec's ids"})
            return m
        dim, hide, high, focus = sel("dim"), sel("hide"), sel("highlight"), sel("focus")
        reveal = [sel("reveal", r) for r in (view.get("reveal") or [])]
        steps = max(1, len(reveal))
        every = {k: set().union(*(r[k] for r in reveal)) for k in ("nodes", "edges", "groups")} if reveal else None
        for step in range(steps):
            looks = {}

            def look(k, i, **props):
                looks.setdefault((k, i), {}).update(props)
            for k, ids in dim.items():
                for i in ids:
                    look(k, i, opacity=DIM)
            for k, ids in high.items():
                for i in ids:
                    look(k, i, opacity=1, stroke="accent", **{"stroke-width": HEAVY})
            if reveal:
                shown = {k: set().union(*(r[k] for r in reveal[:step + 1])) for k in ("nodes", "edges", "groups")}
                hidden_nodes = every["nodes"] - shown["nodes"]
                for k in ("nodes", "groups"):
                    for i in every[k] - shown[k]:
                        look(k, i, opacity=0)
                    for i in shown[k]:
                        look(k, i, opacity=1)
                for eid, (a, b) in ends.items():
                    if a in hidden_nodes or b in hidden_nodes or eid in every["edges"] - shown["edges"]:
                        look("edges", eid, opacity=0)
                    elif eid in shown["edges"] or (a in shown["nodes"] and b in shown["nodes"]):
                        look("edges", eid, opacity=1)
            for k, ids in hide.items():
                for i in ids:
                    look(k, i, opacity=0)
            out.append({"view": vi, "step": step, "steps": steps, "looks": looks,
                        "focus": {k: sorted(v) for k, v in focus.items() if v}})
    return out, warnings


def looked(spec, kind, looks):
    """The spec with a frame's looks as each element's own style (which no stylesheet rule outranks)."""
    from .scene.ids import edge_ids
    s = copy.deepcopy(spec)
    nodes_key, edges_key = LISTS[kind]
    by = {("nodes", str(n.get("id"))): n for n in s.get(nodes_key) or [] if isinstance(n, dict)}
    by.update({("groups", str(g.get("id"))): g for g in s.get("groups") or [] if isinstance(g, dict)})
    edges = s.get(edges_key) or []
    by.update({("edges", eid): e for eid, e in zip(edge_ids(edges), edges)})
    for key, props in looks.items():
        el = by.get(key)
        if el is not None:
            el["style"] = dict(el.get("style") or {}, **props)
    return s


def camera(svg, focus):
    """[x, y, w, h] around the focused elements in a drawing, or None to show it whole."""
    if not focus:
        return None
    from .outline import read_figure
    fig = read_figure(svg)
    boxes = []
    for i in focus.get("nodes", []):
        n = fig["nodes"].get(i)
        if n:
            boxes.append((n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"]))
    for f in fig["frames"]:
        if f["id"] in focus.get("groups", []):
            boxes.append((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]))
    for e in fig["edges"]:
        if e["id"] in focus.get("edges", []) and e["points"]:
            xs, ys = [p[0] for p in e["points"]], [p[1] for p in e["points"]]
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
    if not boxes:
        return None
    x0, y0 = min(b[0] for b in boxes) - PAD, min(b[1] for b in boxes) - PAD
    x1, y1 = max(b[2] for b in boxes) + PAD, max(b[3] for b in boxes) + PAD
    if x1 - x0 < MIN_FOCUS:
        grow = (MIN_FOCUS - (x1 - x0)) / 2
        x0, x1 = x0 - grow, x1 + grow
    W, H = fig["size"] or (x1, y1)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    return [round(x0, 1), round(y0, 1), round(x1 - x0, 1), round(y1 - y0, 1)]


def read_story(path):
    """(story, base folder): the story file, checked. Raises SpecError with a fix."""
    try:
        with open(path, encoding="utf-8") as f:
            story = json.load(f)
    except (OSError, ValueError) as e:
        raise SpecError(f"the story can't be read: {e}", "a story is JSON: {\"figure\": {...}, \"views\": [...]}")
    if not isinstance(story, dict) or not isinstance(story.get("figure"), dict):
        raise SpecError("a story needs a figure", 'write "figure": {"type": "arch", "spec": "platform.json"}')
    views = story.get("views")
    if not isinstance(views, list) or not views or not all(isinstance(v, dict) for v in views):
        raise SpecError("a story needs views, a list of objects", 'write "views": [{"id": "all", "title": "The whole figure"}]')
    seen = set()
    for k, v in enumerate(views):
        v.setdefault("id", f"view-{k + 1}")
        if v["id"] in seen:
            raise SpecError(f"two views are called '{v['id']}'", "give each view its own id")
        seen.add(v["id"])
        if v.get("reveal") is not None and not isinstance(v["reveal"], list):
            raise SpecError(f"view '{v['id']}': reveal should be a list of selectors, one per step", 'write "reveal": ["#web", "#gw"]')
        from .motion import read
        read(v.get("motion"), f"view '{v['id']}'")
    return story, os.path.dirname(os.path.abspath(path))


SHELL = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--paper:{paper};--ink:{ink};--muted:{muted};--rule:{rule};--accent:{accent}}}
*{{box-sizing:border-box}}
html,body{{margin:0;height:100%;background:var(--paper);color:var(--ink);font-family:{font}}}
#deck{{display:grid;grid-template-rows:auto 1fr auto auto;height:100vh;max-width:1400px;margin:0 auto;padding:16px 24px}}
header{{display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap}}
#story-title{{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
#view-title{{font-size:28px;font-weight:600;margin:.2rem 0 .4rem;flex:1 1 100%}}
#stage{{min-height:0;display:flex;align-items:center;justify-content:center}}
#stage svg{{width:100%;height:100%;max-height:100%}}
#stage svg > *{{transition:opacity .45s ease,stroke .45s ease,fill .45s ease,stroke-width .45s ease}}
#view-text{{font-size:17px;line-height:1.5;max-width:70ch;margin:.6rem 0}}
nav{{display:flex;align-items:center;gap:.6rem;padding-top:.6rem;border-top:1px solid var(--rule)}}
nav button{{font:14px {font};color:var(--ink);background:#fff;border:1px solid var(--rule);padding:.35rem .8rem;cursor:pointer}}
nav button:disabled{{opacity:.35;cursor:default}}
#count{{font-size:13px;color:var(--muted);margin-left:.4rem}}
#dots{{display:flex;gap:6px;margin-left:auto}}
.dot{{width:10px;height:10px;border-radius:50%;padding:0;border:1px solid var(--muted);background:transparent}}
.dot.on{{background:var(--accent);border-color:var(--accent)}}
#notes{{display:none;margin-top:.6rem;padding:.6rem .8rem;background:rgba(45,49,66,.05);font-size:15px;white-space:pre-wrap}}
.notes-on #notes{{display:block}}
.hint{{font-size:12px;color:var(--muted)}}
#print{{display:none}}
@media (prefers-reduced-motion:reduce){{#stage svg > *{{transition:none}}}}
@media (max-width:700px){{#deck{{padding:10px 12px}}#view-title{{font-size:21px}}#view-text{{font-size:15px}}}}
@media print{{#deck{{display:none}}#print{{display:block}}.page{{page-break-after:always;padding:12px}}.page svg{{width:100%;height:auto;max-height:80vh}}}}
</style></head><body>
<div id="deck">
<header><span id="story-title">{title}</span><h1 id="view-title"></h1></header>
<div id="stage" aria-live="polite"></div>
<div><p id="view-text"></p><aside id="notes"></aside></div>
<nav><button type="button" id="prev" aria-label="Previous">&larr; Back</button><button type="button" id="next" aria-label="Next">Next &rarr;</button>
<span id="count"></span><span class="hint" id="hint">Arrows or Space to move &middot; N for notes</span><span id="dots"></span></nav>
</div>
<div id="print"></div>
<script type="application/json" id="dd-story">{data}</script>
<script>
{motion}</script>
<script>
{js}</script>
</body></html>"""


def _figure_input(story, base, out_base):
    """(command, path) for the story's figure: its spec file, or an inline spec written beside the page."""
    fig = story["figure"]
    kind = str(fig.get("type") or "")
    if kind not in KINDS + ("mermaid",):
        raise SpecError(f"the figure's type is {kind!r}", f"use one of: {', '.join(KINDS)}, mermaid")
    spec = fig.get("spec") if fig.get("spec") is not None else fig.get("path")
    if isinstance(spec, (dict, list)):
        path = out_base + ".figure.json"
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=1)
        return kind, path
    if not isinstance(spec, str):
        raise SpecError("the figure names no spec", 'write "spec": "platform.json", or the spec itself')
    path = spec if os.path.isabs(spec) else os.path.join(base, spec)
    if not os.path.isfile(path):
        raise SpecError(f"no figure spec at {path}", "paths in a story are relative to the story file")
    return kind, path


def build(story_path, out, gif=None, video=None, view=None, fps=20):
    """Draws the story: its figure (OUT.figure.svg, .html and receipt, through the usual render), then
    every frame, into OUT.html. With gif or video, also films one view's motion (the first view that
    moves, or `view`). Returns the verdict."""
    from . import api
    from ._output import FONT
    from ._theme import THEME
    from .mermaid import _mermaid_kind, load_spec
    from .style.styler import Styler
    story, base = read_story(story_path)
    out_base, ext = os.path.splitext(out)
    if ext.lower() not in (".html", ".htm", ".svg"):
        out_base = out
    kind, path = _figure_input(story, base, out_base)
    code, text, err = api.run([kind, path, "-o", out_base + ".figure.svg"])
    try:
        fig = json.loads(text.strip().splitlines()[-1])
    except (ValueError, IndexError):
        fig = {"ok": False, "errors": [{"msg": (text + err).strip()[-400:] or f"exit {code}"}]}
    if not os.path.isfile(out_base + ".figure.svg") or fig.get("stage") == "validate":
        return {"ok": False, "stage": "figure", "errors": fig.get("errors") or [{"msg": "the figure was not drawn"}],
                "next": "fix the figure's spec (the errors are its render's) and run the story again"}
    if kind == "mermaid":
        with open(path, encoding="utf-8") as f:
            kind = _mermaid_kind(f.read())
    spec = load_spec(path, kind)
    sty = Styler(spec, kind, THEME)
    plan, warnings = frames(story, spec, kind, sty)
    from .diagrams import render_arch, render_flow, render_schema, render_seq
    draw = {"flow": lambda s: render_flow(s), "arch": lambda s: render_arch(s), "seq": lambda s: render_seq(s),
            "schema": lambda s: render_schema(s)}[kind]
    from . import motion
    drawn, size, moves = [], None, {}
    for f in plan:
        svg, W, H = draw(looked(spec, kind, f["looks"]))
        size = size or [W, H]
        v = story["views"][f["view"]]
        if v.get("motion") and f["view"] not in moves:  # one schedule per view: its frames share a layout
            where = f"view '{v['id']}'"
            moves[f["view"]], said = motion.resolve(motion.read(v["motion"], where), spec, kind, sty, svg, where)
            warnings += said
        drawn.append({"view": f["view"], "step": f["step"], "steps": f["steps"], "svg": svg, "viewBox": camera(svg, f["focus"]),
                      **({"motion": moves[f["view"]]} if moves.get(f["view"]) else {})})
    views = [{k: v.get(k) for k in ("id", "title", "text", "notes")} for v in story["views"]]
    for v in story["views"]:
        extra = [k for k in v if k not in KEYS]
        if extra:
            warnings.append({"msg": f"view '{v['id']}': {', '.join(extra)} is not read", "fix": f"a view takes {', '.join(KEYS)}"})
    data = json.dumps({"title": story.get("title") or "", "size": size, "views": views, "frames": drawn},
                      ensure_ascii=False).replace("</", "<\\/")  # stays inside its script tag
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "web", "story.js"), encoding="utf-8") as fh:
        js = fh.read()
    with open(os.path.join(here, "web", "motion.js"), encoding="utf-8") as fh:
        motion_js = fh.read()
    from ._text import esc
    t = THEME
    page = SHELL.format(title=esc(story.get("title") or "Story"), paper=t["paper"], ink=t["ink"], muted=t["muted"],
                        rule=t["rule"], accent=t["accent"], font=FONT, data=data, js=js, motion=motion_js)
    html = out_base + ".html"
    with open(html, "w", encoding="utf-8") as fh:
        fh.write(page)
    verdict = {"ok": bool(fig.get("ok")), "html": html, "frames": len(drawn),
               "views": [{"id": v["id"], "title": v.get("title") or "", "steps": next(f["steps"] for f in drawn if f["view"] == i),
                          "focus": bool(drawn[[f["view"] for f in drawn].index(i)]["viewBox"]),
                          **({"motion": _moves(moves[i])} if moves.get(i) else {})} for i, v in enumerate(story["views"])],
               "figure": {k: fig[k] for k in ("svg", "ok", "errors", "warnings", "layout") if k in fig},
               **({"warnings": warnings} if warnings else {})}
    if gif or video:
        verdict["film"] = _film(story, drawn, moves, view, gif, video, fps)
    return verdict


def _moves(s):
    return {"loop": s["loop"], "traces": len(s["traces"]), "flows": len(s["flows"])}


def _film(story, drawn, moves, view, gif, video, fps):
    """One view's motion as a GIF and/or a video: the view's last frame (every reveal step shown),
    with its camera, one loop long."""
    from . import motion
    ids = [v["id"] for v in story["views"]]
    if view is not None and view not in ids:
        raise SpecError(f"no view called '{view}'", f"the views are: {', '.join(ids)}")
    vi = ids.index(view) if view is not None else next((i for i in range(len(ids)) if moves.get(i)), None)
    if vi is None or not moves.get(vi):
        raise SpecError(f"view '{ids[vi]}' has no motion" if vi is not None else "no view has motion, so there is nothing to film",
                        'give the view "motion": [{"trace": "a -> b -> c"}]')
    last = [f for f in drawn if f["view"] == vi][-1]
    out = motion.film(last["svg"], moves[vi], fps=fps, gif=gif, video=video, camera=last["viewBox"])
    return dict(out, view=ids[vi])


def do_story(args):
    try:
        out = build(args.story, args.o, gif=getattr(args, "gif", None), video=getattr(args, "video", None),
                    view=getattr(args, "view", None), fps=getattr(args, "fps", 20))
    except SpecError as e:
        out = {"ok": False, "stage": "story", "errors": [{"msg": e.msg, "fix": e.fix}]}
    print(json.dumps(out))
    return 0 if out.get("ok") else 1

"""The command line: arguments, the one-line JSON verdict, and the layout outline."""
import json, os, sys
from .errors import SpecError
from . import __version__
from ._issues import _FITS, _SPEC_KEYS
from ._output import LAYOUTS, save_receipt, write_out
from ._theme import THEMES, get_theme
from ._lazy import lazy

_audit_file = lazy("diagonaldiagrams.audit", "_audit_file")
_audit_drawn = lazy("diagonaldiagrams.audit", "_audit_drawn")
do_audit = lazy("diagonaldiagrams.audit", "do_audit")
do_describe = lazy("diagonaldiagrams.describe", "do_describe")
render_chart = lazy("diagonaldiagrams.charts.render", "render_chart")
render_arch = lazy("diagonaldiagrams.diagrams", "render_arch")
render_flow = lazy("diagonaldiagrams.diagrams", "render_flow")
render_schema = lazy("diagonaldiagrams.diagrams", "render_schema")
render_seq = lazy("diagonaldiagrams.diagrams", "render_seq")
do_doc = lazy("diagonaldiagrams.doc", "do_doc")
do_monitor = lazy("diagonaldiagrams.drift", "do_monitor")
do_sync = lazy("diagonaldiagrams.drift", "do_sync")
do_export = lazy("diagonaldiagrams.export", "do_export")
do_extract = lazy("diagonaldiagrams.extract", "do_extract")
render_geo = lazy("diagonaldiagrams.geo", "render_geo")
do_mcp = lazy("diagonaldiagrams.mcp", "do_mcp")
do_apply = lazy("diagonaldiagrams.apply", "do_apply")
do_diff = lazy("diagonaldiagrams.diff", "do_diff")
do_story = lazy("diagonaldiagrams.story", "do_story")
_mermaid_kind = lazy("diagonaldiagrams.mermaid", "_mermaid_kind")
load_spec = lazy("diagonaldiagrams.mermaid", "load_spec")
render_bar = lazy("diagonaldiagrams.plots", "render_bar")
render_line = lazy("diagonaldiagrams.plots", "render_line")
render_scatter = lazy("diagonaldiagrams.plots", "render_scatter")
_json_where = lazy("diagonaldiagrams.validate", "_json_where")
_validate_target = lazy("diagonaldiagrams.validate", "_validate_target")
do_infer = lazy("diagonaldiagrams.validate", "do_infer")
do_validate = lazy("diagonaldiagrams.validate", "do_validate")


def _cli_theme(args):
    return get_theme(getattr(args, "theme", None) or "editorial", getattr(args, "theme_file", None))


def _cli_notes(args, kind):
    texts = getattr(args, "note", None) or []
    ats = getattr(args, "note_at", None) or []
    out = []
    for i, text in enumerate(texts):
        if i >= len(ats):
            break
        at = ats[i]
        if kind == "scatter":
            bits = [b.strip() for b in str(at).split(",")]
            if len(bits) == 2:
                out.append({"x": bits[0], "y": bits[1], "text": text})
        else:
            out.append({"at": at, "text": text})
    return out or None


def _cli_sheets(a):
    """The project config's sheets, then --style files and --font, then the config's locked policy:
    the stylesheets after the spec's own. A file that can't be read, or a rule with a mistake in it,
    stops here with validate's JSON, before anything is drawn."""
    from .errors import SpecError
    from .style.cascade import Cascade
    from . import config
    try:
        cfg = config.load(a.spec if a.spec and os.path.exists(a.spec) else None)
    except SpecError as e:
        _report({"ok": False, "stage": "validate", "errors": [{"msg": e.msg, "fix": e.fix}]}, 1)
    a._config = cfg
    for key in ("theme", "corners"):  # the config's defaults, where the flag was left at its own
        if cfg.defaults.get(key) and getattr(a, key, None) == "editorial":
            setattr(a, key, cfg.defaults[key])
    sheets = list(cfg.sheets)
    if cfg.font_files:
        sheets.append({"name": "the config's fonts", "fonts": dict(cfg.font_files)})
    for path in getattr(a, "style", None) or []:
        try:
            with open(path, encoding="utf-8") as f:
                sheet = json.load(f)
        except (OSError, ValueError) as e:
            _report({"ok": False, "stage": "validate", "errors": [{
                "msg": f"--style {path} can't be read: {e}", "fix": "pass a JSON stylesheet: {\"tokens\": {...}, \"rules\": {...}}"}]}, 1)
        if isinstance(sheet, dict):
            here = os.path.dirname(os.path.abspath(path))  # a sheet's font files are found beside it
            fonts = {fam: f if os.path.isabs(f) else os.path.join(here, f) for fam, f in (sheet.get("fonts") or {}).items()}
            sheet = dict(sheet, name=sheet.get("name") or os.path.basename(path), fonts=fonts)
        sheets.append(sheet)
    if getattr(a, "font", None):
        if os.path.isfile(a.font):  # a font file: its own family name, measured from the file
            from .text.fonts import FontError, describe
            try:
                family = describe(a.font)["family"]
            except (OSError, FontError, ValueError) as e:
                _report({"ok": False, "stage": "validate", "errors": [{
                    "msg": f"--font {a.font} can't be read as a font: {e}", "fix": "pass a .ttf, .otf, .ttc or .woff file, or a family name"}]}, 1)
            sheets.append({"name": "--font", "tokens": {"font": f"'{family}', sans-serif"},
                           "fonts": {family: os.path.abspath(a.font)}})
        else:
            sheets.append({"name": "--font", "tokens": {"font": a.font}})
    sheets += [dict(p, policy=True) for p in cfg.policies]
    if sheets:
        try:
            Cascade(["editorial", *sheets])
        except SpecError as e:
            _report({"ok": False, "stage": "validate", "errors": [{"msg": e.msg, "fix": e.fix}],
                     "next": "fix the stylesheet and run the same command again; nothing was drawn"}, 1)
    return sheets


def _brand_check(a, spec, theme, sheets):
    """The brand policy: an override of a locked value, or a color or font the config
    doesn't allow, stops the render with each one named."""
    cfg = getattr(a, "_config", None)
    if cfg is None or not (cfg.policies or cfg.palette is not None or cfg.fonts is not None):
        return
    from .style.styler import Styler
    issues = Styler(spec, a.cmd, theme, a.corners, sheets).off_brand(cfg.palette, cfg.fonts)
    if issues:
        _report({"ok": False, "stage": "validate", "errors": issues,
                 "next": "the project's brand policy (diagonaldiagrams.toml) decides these; nothing was drawn"}, 1)


def _receipt(a, theme, payload, notes=None, scene=None, sheets=None):
    """Receipt v2: what export needs to draw the same figure again. On top of v1's fields:
    the theme keys --theme-file changed, the caption, chart notes, whether the audit ran, and for a
    diagram the scene that was drawn, so export doesn't depend on the spec file staying as it was."""
    base = THEMES.get(theme.get("_name"), THEMES["editorial"])
    out = {"receipt": 2, **payload}
    over = {k: v for k, v in theme.items() if not k.startswith("_") and base.get(k) != v}
    if over:
        out["theme_overrides"] = over
    if getattr(a, "caption", None) is not None:
        out["caption"] = a.caption
    if getattr(a, "figure", None) is not None and "figure" not in out:
        out["figure"] = a.figure
    if notes:
        out["notes"] = notes
    if getattr(a, "no_audit", False):
        out["audit"] = False
    if scene is not None:
        out["scene"] = scene
    if sheets:
        out["styles"] = sheets  # their content: export redraws with them even if the files move
    return out


def _drawn_scene(spec, kind):
    """The scene a diagram spec draws as, for its receipt (None if it can't be read as one)."""
    from .inputs.v1 import from_v1
    from .scene import check
    from .scene.ids import compact
    scene, errors, _ = check(from_v1({k: v for k, v in spec.items() if k not in ("_warnings", "_errors")}, kind))
    return None if errors else compact(scene.to_dict())


def _exit_with(code):
    """Command handlers return their exit code; only the command line ends the process."""
    if code:
        raise SystemExit(code)


def _report(obj, code):
    print(json.dumps(obj))
    raise SystemExit(code)


def _chart_kinds():
    """The chart taxonomy's kinds, loaded only by the commands that draw or check one."""
    from .charts.catalog import _CHART_BLURB
    return _CHART_BLURB


def _prevalidate(a):
    """Render runs validate first. A bad spec stops here with the same JSON validate prints."""
    if a.cmd in _SPEC_KEYS:
        errors, warnings = _validate_target(a.spec, "spec", kind=a.cmd)
    elif a.cmd == "bar":
        errors, warnings = _validate_target(a.csv, "bar", a.cat, a.val)
    elif a.cmd == "line":
        errors, warnings = _validate_target(a.csv, "line", a.x, a.y, a.group)
    elif a.cmd == "scatter":
        errors, warnings = _validate_target(a.csv, "scatter", a.x, a.y, a.group, a.facet)
    elif a.cmd == "geo":
        errors, warnings = _validate_target(a.src, "geo", a.lon, a.lat)
    elif a.cmd == "chart" and a.kind in _chart_kinds():
        roles = {f: getattr(a, f, None) for f in ("size", "label", "parent", "val", "a", "b", "lo", "hi")}
        errors, warnings = _validate_target(a.src, a.kind, a.x, a.y, a.group, unbounded=a.no_budget, roles=roles)
    else:
        return []
    if errors:
        _report({"ok": False, "stage": "validate", "errors": errors, "warnings": warnings,
                 "next": "fix the spec or flags and run the same command again; nothing was drawn"}, 1)
    return warnings


def _outline(svg_path, structured=False, info=None, root=None):
    """The drawn layout as text (the verdict's layout rows), and with structured=True the --outline
    object too. Lets an agent check the structure for a few dozen tokens instead of a picture.
    info: the layout's layers from the renderer, which the rows then follow. root: the figure's tree
    in memory (paint.Drawing.tree), read instead of the file."""
    from .outline import layout_rows, outline, read_figure
    try:
        fig = read_figure(root if root is not None else open(svg_path, encoding="utf-8").read())
    except (OSError, SyntaxError):  # ElementTree's ParseError is a SyntaxError
        return None, None
    info = info or {}
    layers, across = info.get("layers"), bool(info.get("across"))
    return (layout_rows(fig, layers, across, info.get("columns")),
            (outline(fig, layers, across) if structured else None))


def _finish(a, html, svg, count, unit, pre, changed=None, info=None):
    """One JSON line per render: the files, the count, the audit verdict, and what changed since the
    figure was last drawn at this path, when it was. info: the layout's layers (_outline), and a
    diagram's drawing, which the audit and the outline then read in memory instead of the file."""
    drawing = (info or {}).get("drawing")
    root = drawing.tree() if drawing is not None else None
    if getattr(a, "no_audit", False):
        rep = {"ok": True, "errors": [], "warnings": []}
    else:
        rep = _audit_drawn(drawing, root) if root is not None else _audit_file(svg)
    out = {"ok": rep["ok"], "svg": svg, "html": html, "receipt": os.path.splitext(html)[0] + ".graph.json", unit: count}
    layout, structured = _outline(svg, getattr(a, "outline", False), info, root)
    if layout:
        out["layout"] = layout
    if changed is not None:
        out["changed"] = changed
    if structured:
        out["outline"] = structured
    if rep["errors"]:
        out["errors"] = rep["errors"]
        out["next"] = ("the files are written so you can look; change the spec or flags and render again "
                       "(--no-audit accepts the figure as it is)")
    warns = list(pre or []) + rep["warnings"]
    if warns:
        out["warnings"] = warns
    _report(out, 0 if rep["ok"] else 1)


def _previous_drawing(a):
    """The SVG this figure was last drawn as at -o, or None: the files must be there and the receipt
    must name the same command and spec, so a render over some other figure is not an edit of it."""
    base, ext = os.path.splitext(a.o)
    if ext.lower() not in (".html", ".htm", ".svg"):
        base = a.o
    try:
        with open(base + ".graph.json", encoding="utf-8") as f:
            r = json.load(f)
        with open(base + ".svg", encoding="utf-8") as f:
            old = f.read()
    except (OSError, ValueError):
        return None
    spec = r.get("spec")
    if r.get("cmd") != a.cmd or not isinstance(spec, str):
        return None
    if not os.path.isabs(spec):
        spec = os.path.join(os.path.dirname(os.path.abspath(base)), spec)
    same = os.path.normcase(os.path.abspath(spec)) == os.path.normcase(os.path.abspath(a.spec))
    return old if same else None


def _previous_layers(a):
    """The layers the last drawing's page kept (diff's rows), or None."""
    from .diff import page_layers
    base, ext = os.path.splitext(a.o)
    if ext.lower() not in (".html", ".htm", ".svg"):
        base = a.o
    try:
        with open(base + ".html", encoding="utf-8") as f:
            return page_layers(f.read())
    except OSError:
        return None


def _chart_flags(p):
    p.add_argument("--grid", dest="grid", action="store_true", help="draw gridlines (default)")
    p.add_argument("--no-grid", dest="grid", action="store_false", help="drop gridlines; keep ticks")
    p.add_argument("--markers", dest="markers", action="store_true", help="point dots or bar value labels (default)")
    p.add_argument("--no-markers", dest="markers", action="store_false", help="hide point dots or bar value labels")
    p.add_argument("--highlight", action="append", default=[],
                   help="category, x value, group, or place drawn in accent (repeatable)")
    p.add_argument("--no-audit", action="store_true", help="skip the layout check after drawing")
    p.add_argument("--outline", action="store_true", help="add the structured outline to the verdict")
    p.set_defaults(grid=True, markers=True)


def _spec_to_file(a):
    """The spec as a file path. Text given with -s, or piped in with -, is saved beside the output
    as NAME.spec.mmd or NAME.spec.json, so validation, the receipt, and export all read a file."""
    if a.spec is not None and a.spec_text is not None:
        _report({"ok": False, "stage": "validate", "errors": [{"msg": "two specs given", "fix": "pass a file, or -s TEXT, not both"}]}, 1)
    if a.spec is None and a.spec_text is None:
        _report({"ok": False, "stage": "validate", "errors": [{"msg": "no spec given", "fix": "pass a file, -s TEXT, or - to read stdin"}]}, 1)
    if a.spec_text is None and a.spec != "-":
        return
    # stdin as UTF-8 bytes: a Windows console code page would garble anything past ASCII
    text = sys.stdin.buffer.read().decode("utf-8-sig", "replace") if a.spec_text is None else a.spec_text
    ext = ".json" if text.lstrip().startswith(("{", "[")) else ".mmd"
    path = os.path.splitext(a.o)[0] + ".spec" + ext
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    a.spec = path


COMMANDS = ("flow", "arch", "seq", "schema", "mermaid", "bar", "line", "geo", "doc", "monitor", "sync", "extract",
            "scatter", "chart", "export", "describe", "validate", "infer", "audit", "mcp", "apply", "diff", "story")


class _Skipped:
    """Stands in for a subcommand parser that this run does not need: every call is ignored."""

    def __getattr__(self, name):
        return lambda *a, **k: self


class _OnlyOne:
    """add_subparsers() that builds only the subcommand being run. Building all of them costs
    more than drawing a small figure; --help, --version and a mistyped command still get all."""

    def __init__(self, sub, want):
        self.sub, self.want = sub, want

    def add_parser(self, name, **kw):
        return self.sub.add_parser(name, **kw) if name == self.want else _Skipped()


RENDER = ("flow", "arch", "seq", "schema", "mermaid")
# The render commands' options as _parse() declares them: {flag: (dest, choices or None)} for one that
# takes a value, and {flag: dest} for a switch (store_true). tests/unit/test_cli_args.py holds the two
# to the same answers.
_VALUES = {"-s": ("spec_text", None), "--string": ("spec_text", None), "--spec-text": ("spec_text", None), "-o": ("o", None),
           "--corners": ("corners", ("sharp", "rounded", "editorial")), "--theme": ("theme", tuple(THEMES)),
           "--theme-file": ("theme_file", None), "--style": ("style", None),
           "--caption": ("caption", None), "--figure": ("figure", None), "--font": ("font", None),
           "--fit": ("fit", tuple(_FITS))}
_SWITCHES = {"--no-audit": "no_audit", "--outline": "outline", "--embed-fonts": "embed_fonts"}


def _quick(argv):
    """A render command's arguments read without argparse, which with the modules it loads costs a
    call more than drawing a small figure: flow, arch, seq, schema or mermaid, an optional spec, and
    the options above written out in full (--opt VALUE or --opt=VALUE). Anything else (help, --version,
    an abbreviation, a mistake, a value that starts with "-") returns None, and _parse() reads it, so
    argparse's answers and errors stay the only ones."""
    if not argv or argv[0] not in RENDER:
        return None
    from types import SimpleNamespace
    cmd = argv[0]
    a = SimpleNamespace(cmd=cmd, spec=None, spec_text=None, o=None, corners="editorial", theme="editorial", theme_file=None,
                        no_audit=False, outline=False, style=[], embed_fonts=False, caption=None, figure=None,
                        font=None, fit=None)
    switches = dict(_SWITCHES, **({"--auto": "auto"} if cmd == "flow" else {}))
    if cmd == "flow":
        a.auto = False
    spec, k = [], 1
    while k < len(argv):
        arg = argv[k]
        k += 1
        if not arg.startswith("-") or arg == "-":
            spec.append(arg)
            continue
        flag, eq, value = arg.partition("=") if arg.startswith("--") else (arg, "", "")
        if flag in switches and not eq:
            setattr(a, switches[flag], True)
            continue
        if flag not in _VALUES or (eq and not value):
            return None
        if not eq:
            if k >= len(argv) or (argv[k].startswith("-") and argv[k] != "-"):
                return None
            value, k = argv[k], k + 1
        dest, choices = _VALUES[flag]
        if choices is not None and value not in choices:
            return None
        if dest == "style":
            a.style = a.style + [value]
        else:
            setattr(a, dest, value)
    if len(spec) > 1 or a.o is None:
        return None
    a.spec = spec[0] if spec else None
    return a


def _parse():
    """The command line as argparse reads it: every command, --help, --version, and the errors."""
    import argparse
    from .charts.catalog import _CHART_BLURB
    from .describe import DESCRIBE
    ap = argparse.ArgumentParser(prog="diagonaldiagrams")
    ap.add_argument("--version", action="version", version=f"diagonaldiagrams {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    if len(sys.argv) > 1 and sys.argv[1] in COMMANDS:
        sub = _OnlyOne(sub, sys.argv[1])
    _render_parsers = {}
    for name in ("flow", "arch", "seq", "schema", "mermaid"):
        p = sub.add_parser(name)
        p.add_argument("spec", nargs="?", default=None, help="spec file path, or '-' for stdin (inline text: -s)")
        p.add_argument("-s", "--string", "--spec-text", dest="spec_text", default=None, help="inline spec or Mermaid string")
        p.add_argument("-o", required=True)
        p.add_argument("--corners", default="editorial", choices=["sharp", "rounded", "editorial"])
        p.add_argument("--theme", default="editorial", choices=sorted(THEMES))
        p.add_argument("--theme-file", default=None, help="JSON with theme key overrides")
        p.add_argument("--no-audit", action="store_true", help="skip the layout check after drawing")
        p.add_argument("--outline", action="store_true", help="add the structured outline to the verdict")
        p.add_argument("--style", action="append", default=[], metavar="FILE",
                       help="a stylesheet (JSON: tokens and rules); repeat it, later files win")
        p.add_argument("--embed-fonts", action="store_true",
                       help="embed the named fonts the figure measured with (whole files: large-font warns past 200 KB)")
        p.add_argument("--caption", default=None, help="a caption drawn under the figure")
        p.add_argument("--figure", default=None, help='the figure label drawn above the title, e.g. "Fig. 3"')
        p.add_argument("--font", default=None,
                       help="the font for the figure's text: a family name, or a .ttf/.otf/.ttc/.woff file to measure with")
        p.add_argument("--fit", default=None, choices=_FITS,
                       help="where the figure goes: slide (default; a long flow wraps into columns), page (a document "
                            "page) or column (a docs or notes column: no wrap, about 640 px wide)")
        _render_parsers[name] = p
    _render_parsers["flow"].add_argument("--auto", action="store_true",
                                         help="force longest-path layering (default when no ranks given)")
    p = sub.add_parser("bar"); p.add_argument("csv"); p.add_argument("--cat", default=None)
    p.add_argument("--val", default=None); p.add_argument("--title", default="Bar Chart")
    p.add_argument("--subtitle", default=""); p.add_argument("--figure", default="Fig. 1")
    p.add_argument("--group", default=None); p.add_argument("--orientation", default="v", choices=["v", "h"])
    p.add_argument("--sort", default="none", choices=["none", "asc", "desc"])
    p.add_argument("--xlabel", default=None); p.add_argument("--ylabel", default=None)
    p.add_argument("--unit", default=""); p.add_argument("--source", default="")
    p.add_argument("--caption", default="Categorical comparison.")
    p.add_argument("--corners", default="editorial", choices=["sharp", "rounded", "editorial"])
    p.add_argument("--theme", default="editorial", choices=sorted(THEMES))
    p.add_argument("--theme-file", default=None)
    p.add_argument("--note", action="append", default=[], help="callout text (pairs with --note-at)")
    p.add_argument("--note-at", action="append", default=[], help="callout anchor: category value")
    p.add_argument("-o", required=True)
    _chart_flags(p)
    p = sub.add_parser("line"); p.add_argument("csv"); p.add_argument("--x", default=None)
    p.add_argument("--y", default=None); p.add_argument("--title", default="Line Trend")
    p.add_argument("--subtitle", default=""); p.add_argument("--figure", default="Fig. 1")
    p.add_argument("--group", default=None); p.add_argument("--xlabel", default=None)
    p.add_argument("--xunit", default=""); p.add_argument("--ylabel", default=None)
    p.add_argument("--yunit", default=""); p.add_argument("--source", default="")
    p.add_argument("--caption", default="Trend over time or continuous variable.")
    p.add_argument("--corners", default="editorial", choices=["sharp", "rounded", "editorial"])
    p.add_argument("--theme", default="editorial", choices=sorted(THEMES))
    p.add_argument("--theme-file", default=None)
    p.add_argument("--note", action="append", default=[])
    p.add_argument("--note-at", action="append", default=[], help="callout anchor: x value")
    p.add_argument("-o", required=True)
    _chart_flags(p)
    p = sub.add_parser("geo", help="point map from CSV lat/lon, or GeoJSON points and polygons")
    p.add_argument("src"); p.add_argument("--lat", default=None); p.add_argument("--lon", default=None)
    p.add_argument("--label", default=None); p.add_argument("--val", default=None)
    p.add_argument("--title", default="Map"); p.add_argument("--subtitle", default="")
    p.add_argument("--figure", default="Fig. 1"); p.add_argument("--source", default="")
    p.add_argument("--caption", default="Locations. Dot size follows the value column when one is set.")
    p.add_argument("--theme", default="editorial", choices=sorted(THEMES))
    p.add_argument("--theme-file", default=None)
    p.add_argument("-o", required=True)
    _chart_flags(p)
    p = sub.add_parser("doc", help="compile graph specs in markdown docs to standalone SVGs")
    p.add_argument("target", help="markdown file path")
    p.add_argument("--out-dir", default=None, help="assets output directory")
    p.add_argument("--check", action="store_true", help="CI check mode: verify all specs are valid")
    p = sub.add_parser("monitor", help="detect architectural drift between code and diagrams")
    p.add_argument("--path", default=".", help="project root path")
    p.add_argument("--base", default="HEAD", help="git base ref: HEAD = working tree (local), else branch compare (CI)")
    p.add_argument("--ci", action="store_true", help="fail exit code on drift")
    p.add_argument("--map", default=None, help="mappings JSON: code globs -> spec files for semantic drift compare")
    p = sub.add_parser("sync", help="auto-fix bot: monitor -> extract -> validate -> doc -> audit (-> commit)")
    p.add_argument("--path", default=".", help="project root path")
    p.add_argument("--base", default="HEAD", help="git base ref: HEAD = working tree (local), else branch compare (CI)")
    p.add_argument("--map", default=None, help="mappings JSON (machine remediation needs this)")
    p.add_argument("--docs", nargs="*", default=[], help="markdown docs to recompile after sync")
    p.add_argument("--commit", action="store_true", help="create a local commit (never pushes)")
    p = sub.add_parser("extract", help="reverse-extract diagram specs from code (AST/DDL)")
    sub_ext = p.add_subparsers(dest="ext_type", required=True)
    p_sc = sub_ext.add_parser("schema", help="extract ER schema from SQL DDL or Python ORM models")
    p_sc.add_argument("source", help="source file (.sql, .py, .prisma)")
    p_sc.add_argument("-o", default=None, help="output .json spec file")
    p_rt = sub_ext.add_parser("routes", help="extract service/API routes from FastAPI/Flask code")
    p_rt.add_argument("source", help="source file (.py, .ts, .json)")
    p_rt.add_argument("-o", default=None, help="output .json spec file")
    p = sub.add_parser("scatter"); p.add_argument("csv"); p.add_argument("--x", default=None)
    p.add_argument("--y", default=None); p.add_argument("--title", default="Scatter")
    p.add_argument("--subtitle", default=""); p.add_argument("--figure", default="Fig. 1")
    p.add_argument("--xlabel", default=None); p.add_argument("--xunit", default="")
    p.add_argument("--ylabel", default=None); p.add_argument("--yunit", default="")
    p.add_argument("--group", default=None); p.add_argument("--yerr", default=None)
    p.add_argument("--facet", default=None); p.add_argument("--source", default="")
    p.add_argument("--caption", default="Relationship between the two variables. Points show individual observations.")
    p.add_argument("--corners", default="editorial", choices=["sharp", "rounded", "editorial"])
    p.add_argument("--theme", default="editorial", choices=sorted(THEMES))
    p.add_argument("--theme-file", default=None)
    p.add_argument("--note", action="append", default=[])
    p.add_argument("--note-at", action="append", default=[], help="callout anchor: x,y")
    p.add_argument("-o", required=True)
    _chart_flags(p)
    p = sub.add_parser("chart", help="draw one taxonomy type: diagonaldiagrams chart KIND SRC -o OUT.svg")
    p.add_argument("kind")
    p.add_argument("src")
    p.add_argument("-o", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--subtitle", default="")
    p.add_argument("--source", default="")
    p.add_argument("--x", default=None)
    p.add_argument("--y", default=None)
    p.add_argument("--group", default=None)
    p.add_argument("--size", default=None)
    p.add_argument("--label", default=None)
    p.add_argument("--parent", default=None)
    p.add_argument("--val", default=None)
    p.add_argument("--a", default=None)
    p.add_argument("--b", default=None)
    p.add_argument("--lo", default=None)
    p.add_argument("--hi", default=None)
    p.add_argument("--theme", default="editorial", choices=sorted(THEMES))
    p.add_argument("--theme-file", default=None)
    p.add_argument("--no-budget", action="store_true", help="lift the count cap for this figure")
    _chart_flags(p)
    p = sub.add_parser("export", help="render receipt to png/pdf/svg in a layout")
    p.add_argument("target", help="base path, .html or .svg (receipt .graph.json must sit beside it)")
    p.add_argument("--to", default="png", choices=["png", "pdf", "svg", "drawio", "excalidraw"])
    p.add_argument("--layout", default="figure", choices=sorted(LAYOUTS))
    p.add_argument("--width", type=int, default=1600, help="raster width px (png)")
    p.add_argument("--theme", default=None, choices=sorted(THEMES), help="override receipt theme")
    p.add_argument("--theme-file", default=None)
    p.add_argument("-o", default=None)
    p = sub.add_parser("describe", help="minimal schema+rules+example per type (agent context)")
    p.add_argument("type", nargs="?", default=None, choices=sorted(DESCRIBE))
    p = sub.add_parser("validate", help="check spec/csv BEFORE render; JSON report, exit 1 on error")
    p.add_argument("target"); p.add_argument("--x", default=None); p.add_argument("--y", default=None)
    p.add_argument("--group", default=None); p.add_argument("--facet", default=None)
    for flag in ("--size", "--label", "--parent", "--val", "--a", "--b", "--lo", "--hi"):
        p.add_argument(flag, default=None, help="a chart type's column, as in chart KIND")
    _vtypes = sorted(set(["scatter", "bar", "line", "geo", "flow", "arch", "seq", "schema", "mermaid"]) | set(_CHART_BLURB))
    p.add_argument("--type", default="scatter", choices=_vtypes,
                   help="shape to check. A chart type uses the same name as chart KIND")
    p = sub.add_parser("infer", help="propose a scatter spec from a CSV (agent starting point)")
    p.add_argument("target")
    p = sub.add_parser("audit", help="check rendered svg/html AFTER render; geometry+taste gate as JSON")
    p.add_argument("target")
    p = sub.add_parser("apply", help="write a patch (place, order, style, text, add, remove, move-to-group, pin) into a spec")
    p.add_argument("spec", help="the spec or scene to change (JSON; Mermaid or YAML with -o OUT.json)")
    p.add_argument("patch", help="a JSON list of operations, or '-' for stdin")
    p.add_argument("-o", default=None, help="write here instead of over the spec")
    p.add_argument("--type", default=None, choices=["flow", "arch", "seq", "schema"],
                   help="how to read a v1 spec (default: from its fields)")
    p = sub.add_parser("story", help="one figure, several views (focus, dim, highlight, reveal), presented in one HTML page")
    p.add_argument("story", help="the story: JSON with a figure and its views")
    p.add_argument("-o", required=True, help="the page to write (OUT.html; the figure is drawn as OUT.figure.svg)")
    p.add_argument("--svg", dest="anim", default=None, help="also write a view's motion as an animated SVG (needs nothing)")
    p.add_argument("--gif", default=None, help="also film it as a looping GIF (needs ffmpeg on the PATH)")
    p.add_argument("--video", default=None, help="also film it as .mp4 or .webm (needs ffmpeg on the PATH)")
    p.add_argument("--view", default=None, help="the view to export (default: the first view with motion)")
    p.add_argument("--fps", type=int, default=20, help="frames a second in the export (1-50, default 20)")
    p = sub.add_parser("diff", help="what changed between two drawings of a figure: JSON and sentences")
    p.add_argument("old", help="the earlier .svg or .html")
    p.add_argument("new", help="the later .svg or .html")
    p = sub.add_parser("mcp", help="MCP server over stdio (describe/validate/infer/audit/scatter/diagram/bar/line)")
    p.add_argument("--isolate", action="store_true", help="run each tool call in its own process (180 s limit)")
    return ap.parse_args()


def main():
    a = _quick(sys.argv[1:]) or _parse()
    if a.cmd == "mcp":
        _exit_with(do_mcp(a))
        return
    if a.cmd == "apply":
        _exit_with(do_apply(a))
        return
    if a.cmd == "diff":
        _exit_with(do_diff(a))
        return
    if a.cmd == "story":
        _exit_with(do_story(a))
        return
    if a.cmd == "export":
        _exit_with(do_export(a))
        return
    if a.cmd == "describe":
        _exit_with(do_describe(a))
        return
    if a.cmd == "validate":
        _exit_with(do_validate(a))
        return
    if a.cmd == "infer":
        _exit_with(do_infer(a))
        return
    if a.cmd == "audit":
        _exit_with(do_audit(a))
        return
    if a.cmd == "doc":
        _exit_with(do_doc(a))
        return
    if a.cmd == "monitor":
        _exit_with(do_monitor(a))
        return
    if a.cmd == "sync":
        _exit_with(do_sync(a))
        return
    if a.cmd == "extract":
        _exit_with(do_extract(a))
        return
    if a.cmd in ("flow", "arch", "seq", "schema", "mermaid"):
        _spec_to_file(a)
    if a.cmd == "mermaid":
        try:
            text = open(a.spec, encoding="utf-8").read()
        except OSError:
            _report({"ok": False, "stage": "validate", "errors": [{
                "msg": f"no file {a.spec}", "fix": "check the path, or pass the text with -s or on stdin with -"}]}, 1)
        kind = _mermaid_kind(text)
        if kind not in ("flow", "seq", "schema"):
            _report({"ok": False, "stage": "validate", "errors": [{
                "msg": f"Mermaid '{kind}' is not read yet" if kind else "this doesn't start with a Mermaid diagram type",
                "fix": "start with flowchart TD, sequenceDiagram, or erDiagram"}]}, 1)
        a.cmd = kind
    pre = _prevalidate(a)
    if a.cmd in ("flow", "arch", "seq", "schema"):
        sheets = _cli_sheets(a)
        spec = load_spec(a.spec, a.cmd)
        for key in ("caption", "figure"):  # drawn: the caption under the figure, the label above it
            if getattr(a, key, None):
                spec[key] = getattr(a, key)
        if getattr(a, "fit", None):  # where it goes, over the spec's own size.fit
            spec["size"] = dict(spec["size"] if isinstance(spec.get("size"), dict) else {}, fit=a.fit)
        theme = _cli_theme(a)
        _brand_check(a, spec, theme, sheets)
        embed = getattr(a, "embed_fonts", False)
        old = _previous_drawing(a)
        old_layers = _previous_layers(a) if old is not None else None
        prev = None
        if old is not None:  # an edit of this figure: the boxes the edit leaves alone stay near their places
            from .diff import middles
            try:
                prev = {k: x for k, (x, _) in middles(old).items()}
            except ValueError:  # an old file that is not a figure this engine drew
                old = None
        info = {}  # the layout's layers, for the verdict and the page (diff reads them back)
        if a.cmd == "flow":
            svg, _, _ = render_flow(spec, a.corners, getattr(a, "auto", False), theme, sheets, embed, prev=prev, info=info)
            item_cnt = len(spec.get("nodes", []))
        elif a.cmd == "arch":
            svg, _, _ = render_arch(spec, a.corners, theme, sheets, embed, prev=prev, info=info)
            item_cnt = len(spec.get("nodes", []))
        elif a.cmd == "seq":
            svg, _, _ = render_seq(spec, a.corners, theme, sheets, embed)
            item_cnt = len(spec.get("actors", []))
            info = {"layers": [[str(x.get("id")) for x in spec.get("actors", []) if isinstance(x, dict)]], "across": False}
        elif a.cmd == "schema":
            svg, _, _ = render_schema(spec, a.corners, theme, sheets, embed, info=info)
            item_cnt = len(spec.get("tables", []))
        changed = None
        if old is not None:
            from .diff import diff
            changed = diff(old, svg, old_layers, info.get("layers"))["sentences"]
        page = {"kind": a.cmd, "previous": old if changed else None, "changed": changed or [], "layers": info.get("layers")}
        o, s = write_out(svg, a.cmd, spec.get("title", a.cmd), spec.get("sub", ""),
                         f"{a.cmd} · {os.path.basename(a.spec)}", a.o,
                         caption=spec.get("sub", ""), cap_title=spec.get("title", a.cmd) + ".",
                         source="Self-contained HTML + SVG.", corners=a.corners, theme=theme, page=page)
        drawn = {"cmd": a.cmd, "spec": a.spec, "corners": a.corners, "theme": theme.get("_name"),
                 "auto": bool(getattr(a, "auto", False))}
        if getattr(a, "fit", None):
            drawn["fit"] = a.fit
        save_receipt(o, _receipt(a, theme, drawn, scene=_drawn_scene(spec, a.cmd), sheets=sheets))
        _finish(a, o, s, item_cnt, "items", pre, changed, info)
    elif a.cmd == "bar":
        theme = _cli_theme(a)
        notes = _cli_notes(a, "bar")
        svg, _, _, n = render_bar(a.csv, a.cat, a.val, a.title, a.subtitle, a.figure,
                                  a.group, a.orientation, a.sort, a.xlabel, a.ylabel,
                                  a.unit, a.source, a.corners, chrome=True, theme=theme, notes=notes,
                                  grid=a.grid, markers=a.markers, highlights=a.highlight)
        o, s = write_out(svg, "bar", a.title, a.subtitle or f"{n} items · {os.path.basename(a.csv)}",
                         f"{a.figure} · bar · {os.path.basename(a.csv)}", a.o,
                         caption=a.caption, cap_title=a.title + ".",
                         source=(a.source or os.path.basename(a.csv)), corners=a.corners, theme=theme)
        save_receipt(o, _receipt(a, theme, {"cmd": "bar", "csv": a.csv, "cat": a.cat, "val": a.val, "title": a.title,
                         "subtitle": a.subtitle, "figure": a.figure, "group": a.group,
                         "orientation": a.orientation, "sort": a.sort, "unit": a.unit,
                         "xlabel": a.xlabel, "ylabel": a.ylabel,
                         "source": a.source, "corners": a.corners, "theme": theme.get("_name"),
                         "grid": a.grid, "markers": a.markers, "highlights": a.highlight}, notes))
        _finish(a, o, s, n, "bars", pre)
    elif a.cmd == "line":
        theme = _cli_theme(a)
        notes = _cli_notes(a, "line")
        svg, _, _, n = render_line(a.csv, a.x, a.y, a.title, a.subtitle, a.figure,
                                   a.group, a.xlabel, a.xunit, a.ylabel, a.yunit,
                                   a.source, a.corners, chrome=True, theme=theme, notes=notes,
                                   grid=a.grid, markers=a.markers, highlights=a.highlight)
        o, s = write_out(svg, "line", a.title, a.subtitle or f"{n} points · {os.path.basename(a.csv)}",
                         f"{a.figure} · line · {os.path.basename(a.csv)}", a.o,
                         caption=a.caption, cap_title=a.title + ".",
                         source=(a.source or os.path.basename(a.csv)), corners=a.corners, theme=theme)
        save_receipt(o, _receipt(a, theme, {"cmd": "line", "csv": a.csv, "x": a.x, "y": a.y, "title": a.title,
                         "subtitle": a.subtitle, "figure": a.figure, "group": a.group,
                         "xlabel": a.xlabel, "xunit": a.xunit, "ylabel": a.ylabel, "yunit": a.yunit,
                         "source": a.source, "corners": a.corners, "theme": theme.get("_name"),
                         "grid": a.grid, "markers": a.markers, "highlights": a.highlight}, notes))
        _finish(a, o, s, n, "points", pre)
    elif a.cmd == "geo":
        theme = _cli_theme(a)
        svg, _, _, n = render_geo(a.src, a.lat, a.lon, a.label, a.val, a.title, a.subtitle,
                                  a.figure, a.source, theme, chrome=True,
                                  grid=a.grid, markers=a.markers, highlights=a.highlight)
        o, s = write_out(svg, "geo", a.title, a.subtitle or f"{n} places · {os.path.basename(a.src)}",
                         f"{a.figure} · geo · {os.path.basename(a.src)}", a.o,
                         caption=a.caption, cap_title=a.title + ".",
                         source=(a.source or os.path.basename(a.src)), theme=theme)
        save_receipt(o, _receipt(a, theme, {"cmd": "geo", "src": a.src, "lat": a.lat, "lon": a.lon, "label": a.label,
                         "val": a.val, "title": a.title, "subtitle": a.subtitle, "figure": a.figure,
                         "source": a.source, "theme": theme.get("_name"),
                         "grid": a.grid, "markers": a.markers, "highlights": a.highlight}))
        _finish(a, o, s, n, "places", pre)
    elif a.cmd == "chart":
        theme = _cli_theme(a)
        svg, _, _, n = render_chart(
            a.kind, a.src, title=a.title, subtitle=a.subtitle, source=a.source, theme=theme,
            x=a.x, y=a.y, group=a.group, size=a.size, label=a.label, parent=a.parent,
            val=a.val, a=a.a, b=a.b, lo=a.lo, hi=a.hi,
            grid=a.grid, markers=a.markers, highlights=a.highlight, unbounded=a.no_budget)
        shown = a.title or a.kind
        o, s = write_out(svg, "chart", shown, a.subtitle or a.kind,
                         f"chart · {a.kind}", a.o,
                         caption=a.subtitle or a.kind, cap_title=shown + ".",
                         source=(a.source or os.path.basename(a.src)), theme=theme)
        save_receipt(o, _receipt(a, theme, {"cmd": "chart", "kind": a.kind, "src": a.src, "title": a.title,
                         "subtitle": a.subtitle, "source": a.source,
                         "x": a.x, "y": a.y, "group": a.group, "size": a.size,
                         "label": a.label, "parent": a.parent, "val": a.val,
                         "a": a.a, "b": a.b, "lo": a.lo, "hi": a.hi,
                         "theme": theme.get("_name"), "grid": a.grid, "markers": a.markers,
                         "highlights": a.highlight, "budget": False if a.no_budget else True}))
        _finish(a, o, s, n, "items", pre)
    else:
        theme = _cli_theme(a)
        kw = dict(xcol=a.x, ycol=a.y, title=a.title, subtitle=a.subtitle, figure=a.figure,
                  xlabel=a.xlabel or a.x or "", xunit=a.xunit, ylabel=a.ylabel or a.y or "",
                  yunit=a.yunit, groupcol=a.group, yerrcol=a.yerr, facetcol=a.facet,
                  source=a.source, corners=a.corners, theme=theme, notes=_cli_notes(a, "scatter"),
                  grid=a.grid, markers=a.markers, highlights=a.highlight)
        svg, _, _, n = render_scatter(a.csv, chrome=True, **kw)
        o, s = write_out(svg, "scatter", a.title,
                         a.subtitle or f"{n} points · {os.path.basename(a.csv)}",
                         f"{a.figure} · scatter · {os.path.basename(a.csv)}", a.o,
                         caption=a.caption, cap_title=a.title + ".",
                         source=(a.source or os.path.basename(a.csv)),
                         corners=a.corners, theme=theme)
        save_receipt(o, _receipt(a, theme, {"cmd": "scatter", "csv": a.csv, "x": a.x, "y": a.y, "title": a.title,
                         "subtitle": a.subtitle, "figure": a.figure,
                         "xlabel": a.xlabel or a.x or "", "xunit": a.xunit,
                         "ylabel": a.ylabel or a.y or "", "yunit": a.yunit,
                         "group": a.group, "yerr": a.yerr, "facet": a.facet,
                         "source": a.source, "corners": a.corners, "theme": theme.get("_name"),
                         "grid": a.grid, "markers": a.markers, "highlights": a.highlight}, kw["notes"]))
        _finish(a, o, s, n, "points", pre)


def cli():
    """Entry point. An input the engine does not expect comes back as JSON with a fix, not a traceback."""
    try:
        main()
    except (SystemExit, KeyboardInterrupt):
        raise
    except SpecError as e:  # the input cannot be drawn as given: say why, as sys.exit(msg) did
        sys.stderr.write(f"{e.msg}\n")
        raise SystemExit(1)
    except json.JSONDecodeError as e:
        _report({"ok": False, "errors": [{"msg": f"bad JSON at {_json_where(e)}",
                                          "fix": "strict JSON: double quotes, no trailing commas, no comments"}]}, 1)
    except FileNotFoundError as e:
        _report({"ok": False, "errors": [{"msg": f"no file {e.filename}", "fix": "check the path"}]}, 1)
    except Exception as e:
        import traceback
        where = traceback.extract_tb(e.__traceback__)[-1]
        _report({"ok": False, "errors": [{
            "msg": f"diagonaldiagrams could not draw this input ({type(e).__name__}: {e}, {os.path.basename(where.filename)} line {where.lineno})",
            "fix": "run validate on the spec first; if it passes, this is a diagonaldiagrams bug worth reporting with the spec"}]}, 2)

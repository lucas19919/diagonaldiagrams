#!/usr/bin/env python3
"""Split the single-file engine into the diagonaldiagrams package (docs/PLAN.md, P1.1).

    py -3 scripts/split.py                     # reads graph.py, writes diagonaldiagrams/ and the graph.py shim
    py -3 scripts/split.py --source old.py     # split another copy (e.g. `git show REV:graph.py > old.py`)
    py -3 scripts/split.py --check             # plan only: print the modules and their imports

The split is mechanical. Each top-level statement moves to a module with its source text
unchanged (comments included); nothing is regenerated from the syntax tree. Imports come from
the symbol tables:
- a module imports the lower-level modules listed in EAGER at its top, as usual;
- a function from any other module is reached through diagonaldiagrams._lazy.lazy(), a proxy
  that imports its module on the first call, so `flow` never compiles the chart code;
- module-level code may only use EAGER modules, and data (not functions) may only come from
  EAGER modules. Either rule broken is an error that names the statement.
The eager imports must form no cycle. Unassigned statements are an error too.

This ran once, on the graph.py of commit aacac0b. From then on the package is the source and is
edited directly; the first edits after the split were _proc._self_cmd (run `-m diagonaldiagrams`
instead of a file path) and cli.main (build only the subcommand parser being run). The script
stays as the record of how each name got where it is.
"""
import argparse
import ast
import collections
import os
import symtable
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = "diagonaldiagrams"
STDLIB = {"argparse", "csv", "functools", "html", "json", "os", "sys"}

DOCS = {
    "_theme": "Themes, palettes and the font stack.",
    "_text": "Text: escaping, labels, wrapping, and the width estimate that layout and audit share.",
    "_issues": "Validation basics: one error or warning with its fix, and the list each diagram spec must have.",
    "_proc": "Running this same engine in a new process, installed or from a checkout.",
    "_draw": "SVG building blocks: markers, boxes, diamonds, ports, arrow routing, frames, labels, ticks, icons.",
    "_output": "Writing a figure: the HTML page, the SVG file, and the receipt that export redraws from.",
    "mermaid": "Mermaid input (flowchart, sequenceDiagram, erDiagram) and load_spec.",
    "audit": "The audit: reads a finished SVG and reports what an agent cannot see in it.",
    "diagrams": "flow, arch, seq and schema: placement, routing and the repair loops.",
    "plots": "bar, line and scatter.",
    "geo": "Point maps on the built-in coastline, and the map helpers the geo charts share.",
    "charts.catalog": "The `chart <kind>` types: one line each, and their aliases.",
    "charts._base": "What the `chart <kind>` renderers share: metadata, column roles, axes, legends, boxes.",
    "charts.kinds": "The `chart <kind>` renderers.",
    "charts.mathplot": "chart math: the equation language, sampling and plotting.",
    "charts.render": "render_chart: dispatch, aliases, and validation for `chart <kind>`.",
    "export": "export: redraw from a receipt as PNG, PDF, SVG, draw.io or Excalidraw.",
    "describe": "describe: the contract for every figure type.",
    "validate": "validate and infer.",
    "doc": "doc: compile fenced graph blocks in Markdown into SVGs.",
    "extract": "extract: specs from SQL DDL, Prisma, Python ORMs and web routes.",
    "drift": "monitor and sync: notice when code and its diagrams drift apart, and fix it.",
    "mcp": "The MCP server: the CLI as tools over stdio.",
    "cli": "The command line: arguments, the one-line JSON verdict, and the layout outline.",
}

# Which module each top-level statement goes to. "a..b" is every statement from a through b in
# source order. Keys starting with @ are statements without a name (see stmt_key).
ASSIGN = {
    "_theme": ["THEME..OKABE_ITO_DARK", "get_theme", "_assign_colors", "series_palette", "OKABE_ITO", "FONT", "SANS",
               "_hit"],
    "_text": ["_humanize", "_with_unit", "_wrap", "esc", "_wrap_px", "_NARROW", "_WIDE", "_text_w"],
    "_issues": ["_vissue", "_SPEC_KEYS"],
    "_proc": ["_self_cmd"],
    "_draw": ["render_pincallout", "render_noterail", "figure_heading", "markers..GROUP_PAD",
              "_seg_boxes..group_frames", "BOX_W..fmt_tick"],
    "_output": ["HTML_SHELL", "write_out", "LAYOUTS", "_RECEIPT_PATHS", "save_receipt", "_receipt_inputs"],
    "mermaid": ["_MM_KINDS..load_spec"],
    "audit": ["_affine..do_audit", "_audit_file"],
    "diagrams": ["_group_columns", "auto_ranks.._render_schema_once"],
    "plots": ["render_scatter..render_line"],
    "geo": ["LAND_B64..render_geo", "_map_stage", "_map_finish"],
    "charts.catalog": ["CHART_ALIAS", "_CHART_BLURB", "_chart_meta"],
    "charts._base": ["_load_input.._draw_links", "_ROLE_ALIAS.._groups"],
    "charts.kinds": ["_c_bubble.._c_cluster"],
    "charts.mathplot": ["_math_prep.._math_tag"],
    "charts.render": ["_CHART_FN.._validate_chart", "_missing_charts", "@missing_charts"],
    "export": ["_browser..do_export"],
    "describe": ["DESCRIBE", "@describe_update", "do_describe"],
    "validate": ["do_validate.._numok", "_structure_ok", "do_infer"],
    "doc": ["_inject_links", "do_doc"],
    "extract": ["_split_ddl..do_extract", "_merge_specs", "_spec_diff"],
    "drift": ["do_sync", "do_monitor"],
    "mcp": ["do_mcp"],
    "cli": ["_cli_theme..cli"],
    "__init__": ["__version__"],
}
DROP = {"@doc", "@import", "@yaml", "@main"}  # rewritten by hand below

# What each module may import at its top. Everything else is lazy.
EAGER = {
    "_theme": set(), "_text": set(), "_issues": set(), "_proc": set(), "_yaml": set(),
    "_draw": {"_theme", "_text"},
    "_output": {"_theme", "_text"},
    "audit": {"_theme", "_text", "_draw"},
    "mermaid": {"_theme", "_text", "_draw", "_yaml", "_issues"},
    "diagrams": {"_theme", "_text", "_draw", "_output", "audit"},
    "plots": {"_theme", "_text", "_draw", "_output"},
    "geo": {"_theme", "_text", "_draw", "_output"},
    "charts.catalog": set(),
    "charts._base": {"_theme", "_text", "_draw", "_output", "geo", "charts.catalog"},
    "charts.kinds": {"_theme", "_text", "_draw", "_output", "geo", "charts.catalog", "charts._base"},
    "charts.mathplot": {"_theme", "_text", "_draw", "_output", "charts._base"},
    "charts.render": {"_theme", "_text", "_draw", "_output", "_issues", "charts.catalog", "charts._base", "charts.kinds",
                      "charts.mathplot"},
    "export": {"_theme", "_text", "_draw", "_output"},
    "describe": {"_theme", "_text", "_draw", "_output", "charts.catalog"},
    "validate": {"_theme", "_text", "_draw", "_output", "_issues", "_yaml", "mermaid", "charts.catalog"},
    "doc": {"_text", "_yaml"},
    "extract": {"_text"},
    "drift": {"_proc"},
    "mcp": {"_proc", "_issues", "charts.catalog"},
    "cli": {"_theme", "_text", "_output", "_issues", "_yaml", "_proc", "charts.catalog", "describe"},
}

HAND = {
    "__init__.py": '''"""diagonaldiagrams: diagrams and charts an agent can draw, and check before it shows you.

The command line is diagonaldiagrams.cli.cli(); `python -m diagonaldiagrams` runs it.
"""
''',
    "__main__.py": '''"""python -m diagonaldiagrams"""
from .cli import cli

cli()
''',
    "_yaml.py": '''"""PyYAML, if it is installed. YAML specs are optional; JSON always works."""
try:
    import yaml  # optional; falls back to JSON if missing
    HAS_YAML = True
except ImportError:
    yaml = None
    HAS_YAML = False
''',
    "_lazy.py": '''"""Functions from modules that are imported on first use.

A module that needs a function from a feature module it does not import at its top (charts,
math, maps, export, the MCP server, ...) holds a proxy made here. The proxy imports the module
on its first call, so each command compiles and loads only the code it runs.
"""
import importlib


def lazy(module, name):
    """A callable that imports `module` on first use and calls its `name`."""
    def call(*args, **kwargs):
        return getattr(importlib.import_module(module), name)(*args, **kwargs)
    call.__name__ = call.__qualname__ = name
    call.lazy_target = (module, name)
    return call
''',
    "charts/__init__.py": '''"""The `chart <kind>` figures: shared parts, renderers, math plots and dispatch."""
''',
}

SHIM = '''#!/usr/bin/env python3
"""graph.py: run diagonaldiagrams from a checkout.

The engine is the diagonaldiagrams/ package next to this file. This shim keeps
`py graph.py <command> ...` working, and `import graph` (the browser playground calls
graph.cli()). Any other attribute, such as graph.render_flow, is found in the package on
first use.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagonaldiagrams import __version__  # noqa: E402
from diagonaldiagrams.cli import cli  # noqa: E402


def __getattr__(name):
    from diagonaldiagrams._names import find
    return find(name)


if __name__ == "__main__":
    cli()
'''


def stmt_key(i, node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign):
        t = node.targets[0]
        return t.id if isinstance(t, ast.Name) else t.elts[0].id
    if i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
        return "@doc"
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return "@import"
    if isinstance(node, ast.Try):
        return "@yaml"
    if isinstance(node, ast.If):
        return "@main" if "__name__" in ast.unparse(node.test) else "@missing_charts"
    if isinstance(node, ast.Expr) and "DESCRIBE.update" in ast.unparse(node):
        return "@describe_update"
    raise SystemExit(f"line {node.lineno}: no key for {ast.unparse(node)[:60]}")


def defined_names(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    out = set()
    if isinstance(node, ast.Assign):
        for t in node.targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    out.add(n.id)
    return out


def table_globals(table):
    """Global names a function or class (and everything nested in it) reads or writes."""
    names = set()
    for sym in table.get_symbols():
        if sym.is_global() or sym.is_declared_global():
            names.add(sym.get_name())
    for child in table.get_children():
        names |= table_globals(child)
    return names


def module_level_names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def rel(from_mod, to_mod):
    depth = len(from_mod.split(".")) - 1
    dots = "." * (depth + 1)
    return dots if to_mod == "__init__" else dots + to_mod


def plan(src):
    tree = ast.parse(src)
    lines = src.split("\n")
    st = symtable.symtable(src, "graph.py", "exec")
    tables = {}
    for child in st.get_children():
        tables.setdefault(child.get_name(), child)

    stmts = []
    prev_end = 0
    for i, node in enumerate(tree.body):
        first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        stmts.append({"key": stmt_key(i, node), "node": node, "start": prev_end, "first": first - 1,
                      "end": node.end_lineno, "names": defined_names(node)})
        prev_end = node.end_lineno
    order = [s["key"] for s in stmts]
    pos = {k: i for i, k in enumerate(order)}

    where = {}
    for mod, items in ASSIGN.items():
        for item in items:
            if ".." in item:
                a, b = item.split("..")
                keys = order[pos[a]:pos[b] + 1]
            else:
                keys = [item]
            for k in keys:
                if k in where:
                    raise SystemExit(f"{k} assigned to both {where[k]} and {mod}")
                where[k] = mod
    missing = [k for k in order if k not in where and k not in DROP]
    if missing:
        raise SystemExit("unassigned statements: " + ", ".join(missing))

    home = {"yaml": "_yaml", "HAS_YAML": "_yaml"}
    callable_names = set()
    for s in stmts:
        if s["key"] in DROP:
            continue
        for n in s["names"]:
            if n in home and home[n] != where[s["key"]]:
                raise SystemExit(f"{n} defined in {home[n]} and {where[s['key']]}")
            home[n] = where[s["key"]]
        if isinstance(s["node"], (ast.FunctionDef, ast.ClassDef)):
            callable_names.add(s["node"].name)

    mods = collections.OrderedDict((m, {"stmts": [], "eager": collections.defaultdict(set), "lazy": {},
                                        "stdlib": set()}) for m in ASSIGN)
    errors = []
    for s in stmts:
        if s["key"] in DROP:
            continue
        mod = where[s["key"]]
        m = mods[mod]
        m["stmts"].append(s)
        node = s["node"]
        is_def = isinstance(node, (ast.FunctionDef, ast.ClassDef))
        refs = table_globals(tables[node.name]) if is_def else module_level_names(node)
        # Decorators, default values and base classes run when the module loads, not on a call.
        at_load = set() if is_def else refs
        if is_def:
            parts = list(node.decorator_list)
            if isinstance(node, ast.FunctionDef):
                parts += node.args.defaults + [d for d in node.args.kw_defaults if d is not None]
            else:
                parts += node.bases + [k.value for k in node.keywords]
            for part in parts:
                at_load |= module_level_names(part)
            refs = refs | at_load
        for name in sorted(refs):
            if name in STDLIB:
                m["stdlib"].add(name)
                continue
            target = home.get(name)
            if target is None or target == mod:
                continue
            if target in EAGER.get(mod, set()) or target == "__init__":
                m["eager"][target].add(name)
            elif not is_def or name in at_load:
                errors.append(f"{mod}: module-level {s['key']} uses {name} from {target}, which {mod} does not import eagerly")
            elif name not in callable_names:
                errors.append(f"{mod}: {s['key']} reads data {name} from {target}; add {target} to EAGER[{mod}] or move {name}")
            else:
                m["lazy"][name] = target
    # stdlib names used at module level by the yaml block are handled in _yaml.py
    if errors:
        raise SystemExit("\n".join(errors))

    # no cycles among eager imports
    graph = {m: set(v["eager"]) - {"__init__"} for m, v in mods.items()}
    graph["_yaml"] = set()
    state = {}

    def visit(n, path):
        if state.get(n) == 1:
            raise SystemExit("eager import cycle: " + " -> ".join(path + [n]))
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in graph.get(n, ()):
            visit(d, path + [n])
        state[n] = 2
    for n in graph:
        visit(n, [])
    return mods, lines, home


def render_module(name, m, lines):
    out = []
    if name in DOCS:
        out.append(f'"""{DOCS[name]}"""')
    if m["stdlib"]:
        out.append("import " + ", ".join(sorted(m["stdlib"])))
    for target in sorted(m["eager"]):
        names = sorted(m["eager"][target])
        stmt = f"from {rel(name, target)} import "
        body = ", ".join(names)
        if len(stmt + body) <= 110:
            out.append(stmt + body)
        else:
            out.append(stmt + "(")
            row = "    "
            for n in names:
                if len(row) + len(n) + 2 > 110:
                    out.append(row.rstrip())
                    row = "    "
                row += n + ", "
            out.append(row.rstrip())
            out.append(")")
    if m["lazy"]:
        out.append(f"from {rel(name, '_lazy')} import lazy")
        out.append("")
        for n, target in sorted(m["lazy"].items(), key=lambda kv: (kv[1], kv[0])):
            out.append(f'{n} = lazy("{PKG}.{target}", "{n}")')
    head = "\n".join(out).rstrip("\n")
    body = []
    for i, s in enumerate(m["stmts"]):
        text = lines[s["start"]:s["end"]]
        while text and not text[0].strip():
            text = text[1:]
        body.append("\n".join(text).rstrip())
    sep = "\n\n\n"
    return (head + sep if head else "") + sep.join(body) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split graph.py into the diagonaldiagrams package.")
    ap.add_argument("--source", default=os.path.join(REPO, "graph.py"), help="the single-file engine")
    ap.add_argument("--out", default=os.path.join(REPO, PKG))
    ap.add_argument("--shim", default=os.path.join(REPO, "graph.py"), help="where to write the shim")
    ap.add_argument("--check", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--no-shim", action="store_true", help="do not write the shim")
    a = ap.parse_args(argv)
    with open(a.source, encoding="utf-8") as f:
        src = f.read().replace("\r\n", "\n")
    if "from diagonaldiagrams.cli import cli" in src:
        raise SystemExit(f"{a.source} is the shim; pass --source with the single-file engine")
    mods, lines, home = plan(src)
    if a.check:
        for name, m in mods.items():
            n = sum(s["end"] - s["first"] for s in m["stmts"])
            print(f"{name:16} {n:5} lines  eager: {', '.join(sorted(m['eager'])) or '-'}  lazy: {len(m['lazy'])}")
        return 0
    if os.path.exists(a.out) and os.listdir(a.out):
        raise SystemExit(f"{a.out} exists and is not empty; remove it first")
    written = []
    for name, m in mods.items():
        if name == "__init__":
            continue
        path = os.path.join(a.out, *name.split(".")) + ".py"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_module(name, m, lines))
        written.append(path)
    version = next(s for s in mods["__init__"]["stmts"])
    for rel_path, text in HAND.items():
        path = os.path.join(a.out, *rel_path.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if rel_path == "__init__.py":
            text += "\n" + "\n".join(lines[version["first"]:version["end"]]) + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        written.append(path)
    names = {n: m for n, m in home.items() if not n.startswith("@")}
    with open(os.path.join(a.out, "_names.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write('"""Where each name from the single-file graph.py lives now, for `graph.<name>` in the shim."""\n'
                "import importlib\n\nNAMES = {\n")
        for n in sorted(names):
            f.write(f'    "{n}": "{names[n]}",\n')
        f.write("}\n\n\ndef find(name):\n"
                "    if name not in NAMES:\n"
                "        raise AttributeError(f\"module 'graph' has no attribute {name!r}\")\n"
                f'    mod = NAMES[name]\n'
                f'    return getattr(importlib.import_module("{PKG}" if mod == "__init__" else "{PKG}." + mod), name)\n')
    written.append("_names.py")
    if not a.no_shim:
        with open(a.shim, "w", encoding="utf-8", newline="\n") as f:
            f.write(SHIM)
    print(f"wrote {len(written)} files into {a.out}" + ("" if a.no_shim else f"; {a.shim} is now the shim"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

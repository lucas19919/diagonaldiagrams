"""Where one diagram command spends its time: Python's start, imports, the arguments, validation,
the styles, the draw (layout, styles, the SVG text), the page, the receipt, the audit, the outline
and the verdict.

    py -3 scripts/bench_phases.py                          # this checkout, the 5/11/20/40-step flows
    py -3 scripts/bench_phases.py --repo OLD --repo .      # two checkouts, their runs interleaved
    py -3 scripts/bench_phases.py --cmd mermaid            # the same flows read as Mermaid

Every run is a fresh process, two ways: compiled (from bytecode, in a temporary PYTHONPYCACHEPREFIX
warmed first) and uncompiled (PYTHONDONTWRITEBYTECODE=1 with no cache: every module of the engine is
compiled from source on each call, as on a machine that keeps no bytecode). Each cell is the median
of the runs. Two kinds of run:

- cli: `python -m diagonaldiagrams CMD SPEC -o OUT`, timed from outside, end to end: the command an
  agent runs. "python start" is `python -c pass` in the same environment, the interpreter alone.
- phases: the same command in a process that times each step from inside (this script with
  --child). Imports are their own phase wherever they happen (a module the draw loads on first use
  counts as import, not draw), so the two modes differ only there. "args" is what main() spends
  outside the timed steps: building the parser and reading the arguments.

The flows are the golden corpus's generated processes (tests/golden/inputs/flows/flow-NN.json),
the ones the README's speed table draws. Each run writes to a new output name: a render over its
own last output is an edit, which diffs against it.
"""
import io
import sys
import time

# cli.py's steps, by the names main() calls them by (a name a checkout lacks is skipped)
STEPS = {
    "validate": ("_spec_to_file", "_mermaid_kind", "_prevalidate"),
    "styles": ("_cli_sheets", "_cli_theme", "_brand_check"),
    "load": ("load_spec",),
    "previous": ("_previous_drawing", "_previous_layers"),
    "draw": ("render_flow", "render_arch", "render_seq", "render_schema"),
    "page": ("write_out",),
    "receipt": ("_receipt", "_drawn_scene", "save_receipt"),
    "audit": ("_audit_file", "_audit_drawn"),
    "outline": ("_outline",),
    "verdict": ("_report",),
}
# inside the draw and the audit: {module: {phase: names ("Class.method" for a method)}}
INNER = {
    "diagonaldiagrams.layout.layered": {"draw.layout": ("layout",)},
    "diagonaldiagrams.style.styler": {"draw.styles": ("Styler.__init__", "Styler.node", "Styler.edge", "Styler.group",
                                                      "Styler.figure", "Styler.table", "Styler.legend_entries",
                                                      "Styler.marker", "Styler.embed")},
    "diagonaldiagrams.paint": {"draw.svg": ("Drawing.svg",), "audit.read": ("Drawing.tree",)},
    "diagonaldiagrams.audit.svg_import": {"audit.read": ("svg_import",)},
    "diagonaldiagrams.audit.checks": {"audit.checks": ("run_checks",)},
}


# ---- the child: one command, timed step by step from inside. Before its clock starts it imports
# nothing the command imports itself (io, sys and time come loaded with Python).

def child(repo, argv):
    t0 = time.perf_counter()
    clock = time.perf_counter
    acc, stack = {}, []

    def enter():
        stack.append([clock(), 0.0])

    def leave(name):
        start, inner = stack.pop()
        took = clock() - start
        acc[name] = acc.get(name, 0.0) + took - inner
        if stack:
            stack[-1][1] += took

    def timed(name, fn):
        def call(*a, **k):
            enter()
            try:
                return fn(*a, **k)
            finally:
                leave(name)
        call.__name__, call.__wrapped__ = getattr(fn, "__name__", name), fn
        return call

    def patch(mod, phases):
        for phase, names in phases.items():
            for name in names:
                owner, attr = (getattr(mod, name.split(".")[0], None), name.split(".")[1]) if "." in name else (mod, name)
                fn = getattr(owner, attr, None) if owner is not None else None
                if fn is not None:
                    setattr(owner, attr, timed(phase, fn))

    class Loader:
        """Times a module's loading (compiling it or reading its bytecode, then running it) as import."""
        def __init__(self, inner):
            self.inner = inner

        def create_module(self, spec):
            return self.inner.create_module(spec)

        def exec_module(self, module):
            enter()
            try:
                self.inner.exec_module(module)
            finally:
                leave("import")
            if module.__name__ in INNER:
                patch(module, INNER[module.__name__])

        def __getattr__(self, name):  # is_package, get_data, get_resource_reader, ...
            return getattr(self.inner, name)

    class Finder:
        def find_spec(self, name, path, target=None):
            for f in sys.meta_path:
                if f is self or not hasattr(f, "find_spec"):
                    continue
                spec = f.find_spec(name, path, target)
                if spec is not None:
                    if spec.loader is not None and hasattr(spec.loader, "exec_module"):
                        spec.loader = Loader(spec.loader)
                    return spec
            return None

    sys.meta_path.insert(0, Finder())
    sys.path.insert(0, repo)
    enter()
    import diagonaldiagrams.cli as cli
    leave("import")
    for phase, names in STEPS.items():
        for name in names:
            if callable(getattr(cli, name, None)):
                setattr(cli, name, timed(phase, getattr(cli, name)))
    out, sys.stdout = sys.stdout, io.StringIO()
    sys.argv = ["diagonaldiagrams", *argv]
    code = 0
    enter()
    try:
        cli.cli()
    except SystemExit as e:
        code = e.code or 0
    finally:
        leave("args")  # main()'s own time, outside the timed steps
        said, sys.stdout = sys.stdout.getvalue(), out
    inside = time.perf_counter() - t0
    import json
    ok = json.loads(said.strip().splitlines()[-1]).get("ok") if said.strip() else None
    print(json.dumps({"phases": {k: v * 1000.0 for k, v in acc.items()}, "inside": inside * 1000.0, "code": code, "ok": ok}))


if __name__ == "__main__" and sys.argv[1:2] == ["--child"]:
    child(sys.argv[2], sys.argv[3:])
    raise SystemExit(0)

# ---- the parent: environments, runs, medians ------------------------------------------------

import argparse  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import statistics  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SIZES = (5, 11, 20, 40)
FRESH = itertools.count()
SHAPES = {"oval": ('(["', '"])'), "diamond": ('{"', '"}')}
ORDER = ("python start", "import", "args", "validate", "styles", "load", "previous", "draw", "draw.styles", "draw.layout",
         "draw.svg", "page", "receipt", "audit", "audit.read", "audit.checks", "outline", "verdict")


def mermaid(spec):
    """A generated flow spec as Mermaid: the same boxes, shapes, arrows and labels."""
    lines = ["flowchart TD"]
    for n in spec["nodes"]:
        a, b = SHAPES.get(n.get("shape"), ('["', '"]'))
        lines.append(f"  {n['id']}{a}{n['name']}{b}")
    for e in spec["edges"]:
        label = f"|{e['label']}|" if e.get("label") else ""
        lines.append(f"  {e['from']} -->{label} {e['to']}")
    return "\n".join(lines) + "\n"


def run(cmd, env, cwd):
    t = time.perf_counter()
    p = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ms = (time.perf_counter() - t) * 1000.0
    if p.returncode not in (0, 1):  # 1: the audit found something; still a whole run
        raise SystemExit(f"failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout[-1500:]}\n{p.stderr[-1500:]}")
    return ms, p.stdout


def specs(cmd, work):
    flows = os.path.join(REPO, "tests", "golden", "inputs", "flows")
    out = {}
    for n in SIZES:
        src = os.path.join(flows, f"flow-{n:02d}.json")
        if cmd == "mermaid":
            with open(src, encoding="utf-8") as f:
                spec = json.load(f)
            src = os.path.join(work, f"flow-{n:02d}.mmd")
            with open(src, "w", encoding="utf-8", newline="\n") as f:
                f.write(mermaid(spec))
        out[n] = src
    return out


def table(res, repos, mode, sizes, cmd, runs):
    lines = [f"### {cmd}, {mode} (ms, median of {runs})", ""]
    cols = [(r, n) for n in sizes for r in repos]
    name = (lambda r: " " + (os.path.basename(r.rstrip("\\/")) or r)) if len(repos) > 1 else (lambda r: "")
    lines.append("| phase | " + " | ".join(f"{n}{name(r)}" for r, n in cols) + " |")
    lines.append("| --- |" + " ---: |" * len(cols))

    def med(r, n, get):
        return f"{statistics.median(get(x) for x in res[r][mode][n]['phases']):.1f}"
    for ph in ORDER:
        if ph == "python start":
            lines.append(f"| {ph} | " + " | ".join(f"{statistics.median(res[r][mode][n]['python']):.1f}" for r, n in cols) + " |")
        elif any(ph in x["phases"] for r, n in cols for x in res[r][mode][n]["phases"]):
            lines.append(f"| {ph} | " + " | ".join(med(r, n, lambda x: x["phases"].get(ph, 0.0)) for r, n in cols) + " |")
    lines.append("| inside, all phases | " + " | ".join(med(r, n, lambda x: x["inside"]) for r, n in cols) + " |")
    lines.append("| **CLI call, end to end** | " + " | ".join(
        f"**{statistics.median(res[r][mode][n]['cli']):.0f}**" for r, n in cols) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", action="append", default=None, help="a checkout to time (repeat to compare; default: this one)")
    ap.add_argument("--runs", type=int, default=7, help="runs per cell (default 7)")
    ap.add_argument("--sizes", type=int, nargs="*", default=list(SIZES))
    ap.add_argument("--cmd", default="flow", choices=["flow", "mermaid"])
    ap.add_argument("--modes", nargs="*", default=["compiled", "uncompiled"], choices=["compiled", "uncompiled"])
    ap.add_argument("--json", default=None, help="also write every run's numbers here")
    a = ap.parse_args()
    repos = [os.path.abspath(r) for r in (a.repo or [REPO])]
    for r in repos:
        if any("__pycache__" in d for _, d, _ in os.walk(os.path.join(r, "diagonaldiagrams"))):
            raise SystemExit(f"{r}/diagonaldiagrams holds __pycache__ folders; delete them for a true uncompiled run")
    work = tempfile.mkdtemp(prefix="bench-phases-")
    caches = {r: tempfile.mkdtemp(prefix="bench-pyc-") for r in repos}
    base = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}

    def env(mode, repo):
        return dict(base, PYTHONPYCACHEPREFIX=caches[repo]) if mode == "compiled" else dict(base, PYTHONDONTWRITEBYTECODE="1")

    def out():
        return os.path.join(work, f"o-{next(FRESH)}.html")
    paths = specs(a.cmd, work)
    sizes = [n for n in a.sizes if n in paths]
    res = {r: {m: {n: {"cli": [], "python": [], "phases": []} for n in sizes} for m in a.modes} for r in repos}
    try:
        for r in repos:  # warm the bytecode caches with every module either kind of run imports
            for n in sizes:
                for argv in ([sys.executable, "-m", "diagonaldiagrams"], [sys.executable, __file__, "--child", r]):
                    run(argv + [a.cmd, paths[n], "-o", out()], env("compiled", r), r)
        for k in range(a.runs):
            for m in a.modes:
                for r in repos:
                    e = env(m, r)
                    for n in sizes:
                        cell = res[r][m][n]
                        cell["python"].append(run([sys.executable, "-c", "pass"], e, r)[0])
                        cell["cli"].append(run([sys.executable, "-m", "diagonaldiagrams", a.cmd, paths[n], "-o", out()], e, r)[0])
                        txt = run([sys.executable, __file__, "--child", r, a.cmd, paths[n], "-o", out()], e, r)[1]
                        cell["phases"].append(json.loads(txt.strip().splitlines()[-1]))
            print(f"run {k + 1} of {a.runs} done", file=sys.stderr)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        for c in caches.values():
            shutil.rmtree(c, ignore_errors=True)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"cmd": a.cmd, "runs": a.runs, "python": sys.version.split()[0], "repos": repos, "results": res}, f)
    for m in a.modes:
        print("\n" + table(res, repos, m, sizes, a.cmd, a.runs))


if __name__ == "__main__":
    main()

"""Time one figure per tool: diagonaldiagrams, mermaid-cli (mmdc) and Pele, on the README's flows.

The flows are the golden corpus's generated processes at 5, 11, 20 and 40 steps
(tests/golden/inputs/flows/flow-NN.json). Each is written once as Mermaid (bench/speed/flow-NN.mmd),
and every tool draws that same Mermaid text. Times are medians of several runs.

    py -3 scripts/bench_speed.py                       # diagonaldiagrams only
    py -3 scripts/bench_speed.py --mmdc DIR --pele DIR --browser PATH

--mmdc and --pele are the folders npm installed them into (the ones holding node_modules/). They
are passed as paths and never imported from: this script and bench/speed/pele_time.mjs stay
outside them. --browser is the Chromium-based browser mmdc drives (it downloads none).

What is timed:
- dd draw: the Mermaid read, layout and SVG, in this process (load_spec + render_flow), modules
  already imported. Pele's render() does the same job: text in, SVG out.
- dd command: `mermaid FILE -o OUT` in this process: the draw plus the audit, the outline, the
  HTML page, the receipt and the verdict, everything one CLI call does except starting Python.
- dd CLI: a fresh `python -m diagonaldiagrams mermaid ...` process, recompiling the engine
  (PYTHONDONTWRITEBYTECODE=1 and no bytecode anywhere, as on a machine without a cache) and
  from bytecode (PYTHONPYCACHEPREFIX in a temporary folder, warmed first).
- mmdc: a fresh `mmdc -i FILE -o OUT.svg` process, as an agent calls it: Node, a headless
  browser, mermaid.js, and the SVG written.
- pele render: render(text) in one Node process, after warm-up (bench/speed/pele_time.mjs).
- pele CLI: a fresh `node pele_time.mjs --once` process that imports Pele, renders once and
  writes the SVG, the closest Pele comes to a per-call cost (Pele ships no command line).
"""
import argparse
import itertools
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FLOWS = os.path.join(REPO, "tests", "golden", "inputs", "flows")
OUT = os.path.join(REPO, "bench", "speed")
SIZES = (5, 11, 20, 40)
FRESH = itertools.count()  # a new output name per call: a render over its own last output is an edit (diff path)
SHAPES = {"oval": ('(["', '"])'), "diamond": ('{"', '"}')}


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


def write_flows():
    os.makedirs(OUT, exist_ok=True)
    paths = {}
    for n in SIZES:
        spec = json.load(open(os.path.join(FLOWS, f"flow-{n:02d}.json"), encoding="utf-8"))
        path = os.path.join(OUT, f"flow-{n:02d}.mmd")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(mermaid(spec))
        paths[n] = path
    return paths


def median_ms(fn, runs, warm=1):
    for _ in range(warm):
        fn()
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return {"median": round(statistics.median(times), 1), "min": round(min(times), 1),
            "max": round(max(times), 1), "runs": runs}


def run_ok(cmd, env=None, cwd=None):
    p = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SystemExit(f"failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    return p.stdout


def time_dd(paths, runs, work):
    sys.path.insert(0, REPO)
    import diagonaldiagrams as dd
    from diagonaldiagrams.mermaid import load_spec
    from diagonaldiagrams.diagrams import render_flow
    rows = {}
    for n, path in paths.items():
        def draw():
            render_flow(load_spec(path, "flow"))

        def command():
            out = os.path.join(work, f"dd-{n:02d}-{next(FRESH)}.html")
            code, stdout, _ = dd.run(["mermaid", path, "-o", out])
            if code != 0:
                raise SystemExit(f"diagonaldiagrams failed on {path}: {stdout[-1500:]}")
        verdict = json.loads(dd.run(["mermaid", path, "-o", os.path.join(work, f"dd-{n:02d}.html")])[1])
        rows[n] = {"draw": median_ms(draw, runs * 4, warm=3), "command": median_ms(command, runs * 2, warm=2),
                   "ok": verdict.get("ok"), "canvas": verdict.get("canvas") or verdict.get("size")}
    return rows


def time_dd_cli(paths, runs, work):
    base = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
    stale = [r for r, d, _ in os.walk(os.path.join(REPO, "diagonaldiagrams")) if "__pycache__" in d]
    if stale:
        raise SystemExit("diagonaldiagrams/ holds __pycache__ folders; delete them for a true recompiling measurement")
    cache = tempfile.mkdtemp(prefix="bench-pyc-")
    envs = {"recompiling": dict(base, PYTHONDONTWRITEBYTECODE="1"), "bytecode": dict(base, PYTHONPYCACHEPREFIX=cache)}
    rows = {}
    try:
        bare = median_ms(lambda: run_ok([sys.executable, "-c", "pass"], envs["recompiling"]), runs)
        for n, path in paths.items():
            def cli(env):
                out = os.path.join(work, f"cli-{n:02d}-{next(FRESH)}.html")
                run_ok([sys.executable, "-m", "diagonaldiagrams", "mermaid", path, "-o", out], env, REPO)
            rows[n] = {name: median_ms(lambda e=env: cli(e), runs, warm=1) for name, env in envs.items()}
    finally:
        shutil.rmtree(cache, ignore_errors=True)
    return rows, bare


def node_bin(folder, name):
    exe = os.path.join(folder, "node_modules", ".bin", name + (".cmd" if os.name == "nt" else ""))
    if not os.path.exists(exe):
        raise SystemExit(f"no {exe}: is {name} installed in {folder}?")
    return exe


def time_mmdc(paths, runs, work, folder, browser):
    cfg = os.path.join(work, "puppeteer.json")
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({"executablePath": browser, "headless": True}, f)
    exe = node_bin(folder, "mmdc")
    version = run_ok([exe, "--version"], cwd=work).strip()
    rows = {}
    for n, path in paths.items():
        out = os.path.join(work, f"mmdc-{n:02d}.svg")
        cmd = [exe, "-i", path, "-o", out, "-p", cfg, "-q"]
        rows[n] = median_ms(lambda: run_ok(cmd, cwd=work), runs, warm=1)
    return rows, version


def time_pele(paths, runs, work, folder):
    script = os.path.join(OUT, "pele_time.mjs")
    entry = os.path.join(folder, "node_modules", "pele", "dist", "pele.js")
    pkg = json.load(open(os.path.join(folder, "node_modules", "pele", "package.json"), encoding="utf-8"))
    rows = {}
    for n, path in paths.items():
        stats = json.loads(run_ok(["node", script, entry, path, str(max(200, runs * 40))], cwd=work))
        out = os.path.join(work, f"pele-{n:02d}.svg")
        once = median_ms(lambda: run_ok(["node", script, entry, path, "--once", out], cwd=work), runs, warm=1)
        rows[n] = {"render": stats, "cli": once}
    return rows, pkg["version"]


def table(res):
    sizes = [n for n in SIZES if n in res["dd"]]
    head = "| Tool, ms per figure | " + " | ".join(f"{n} steps" for n in sizes) + " |"
    lines = [head, "| --- |" + " --- |" * len(sizes)]

    def row(label, get):
        cells = []
        for n in sizes:
            try:
                cells.append(f"{get(n):g}")
            except (KeyError, TypeError):
                cells.append("–")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    row("diagonaldiagrams draw, in process", lambda n: res["dd"][n]["draw"]["median"])
    row("diagonaldiagrams command, in process", lambda n: res["dd"][n]["command"]["median"])
    if "dd_cli" in res:
        row("diagonaldiagrams CLI, recompiling", lambda n: res["dd_cli"][n]["recompiling"]["median"])
        row("diagonaldiagrams CLI, from bytecode", lambda n: res["dd_cli"][n]["bytecode"]["median"])
    if "pele" in res:
        row("Pele render(), in process", lambda n: res["pele"][n]["render"]["median"])
        row("Pele, fresh Node process", lambda n: res["pele"][n]["cli"]["median"])
    if "mmdc" in res:
        row("mermaid-cli (mmdc), per call", lambda n: res["mmdc"][n]["median"])
    return "\n".join(lines)


def combine(paths):
    """Several whole runs as one: each cell is the median of the runs' medians, which are kept in `of`."""
    runs = [json.load(open(p, encoding="utf-8")) for p in paths]
    res = {k: v for k, v in runs[0].items() if not isinstance(v, dict)}
    res["when"] = ", ".join(r["when"] for r in runs)

    def merge(parts):
        if not isinstance(parts[0], dict):  # ok, canvas: the same in every run
            return parts[0]
        if "median" in parts[0]:
            meds = [p["median"] for p in parts]
            return {"median": round(statistics.median(meds), 3), "of": meds}
        return {k: merge([p[k] for p in parts]) for k in parts[0]}
    for key in ("dd", "dd_cli", "pele", "mmdc"):
        if all(key in r for r in runs):
            res[key] = {int(n): merge([r[key][n] for r in runs]) for n in runs[0][key]}
    if all("python_bare" in r for r in runs):
        res["python_bare"] = merge([r["python_bare"] for r in runs])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combine", nargs="+", metavar="RUN.json", help="merge saved runs instead of timing")
    ap.add_argument("--runs", type=int, default=7, help="runs per process timing (in-process timings do more)")
    ap.add_argument("--mmdc", help="folder holding node_modules/@mermaid-js/mermaid-cli")
    ap.add_argument("--browser", help="Chrome or Edge for mmdc")
    ap.add_argument("--pele", help="folder holding node_modules/pele")
    ap.add_argument("--no-cli", action="store_true", help="skip the fresh-process diagonaldiagrams timings")
    ap.add_argument("--json", default=os.path.join(OUT, "latest.json"))
    a = ap.parse_args()
    if a.combine:
        res = combine(a.combine)
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, indent=1)
            f.write("\n")
        print(table(res))
        return
    paths = write_flows()
    work = tempfile.mkdtemp(prefix="bench-speed-")
    res = {"when": time.strftime("%Y-%m-%d %H:%M"), "python": platform.python_version(),
           "machine": f"{platform.platform()}, {os.cpu_count()} CPUs", "runs": a.runs}
    try:
        res["dd"] = time_dd(paths, a.runs, work)
        if not a.no_cli:
            res["dd_cli"], res["python_bare"] = time_dd_cli(paths, a.runs, work)
        if a.pele:
            res["pele"], res["pele_version"] = time_pele(paths, a.runs, work, a.pele)
        if a.mmdc:
            if not a.browser:
                raise SystemExit("--mmdc needs --browser")
            res["mmdc"], res["mmdc_version"] = time_mmdc(paths, a.runs, work, a.mmdc, a.browser)
        res["node"] = run_ok(["node", "--version"]).strip() if (a.pele or a.mmdc) else None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    with open(a.json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=1)
        f.write("\n")
    print(table(res))


if __name__ == "__main__":
    main()

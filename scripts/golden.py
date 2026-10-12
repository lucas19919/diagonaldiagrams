#!/usr/bin/env python3
"""Golden files: what the engine draws today, byte for byte (docs/PLAN.md, P0.1).

    py -3 scripts/golden.py                  # --check: render the corpus, compare, exit 1 on any change
    py -3 scripts/golden.py --update         # rewrite tests/golden/ from the current engine
    py -3 scripts/golden.py --only gen-flow-40 arch-checkout   # a subset (names or tags)
    py -3 scripts/golden.py --png            # also rasterize to bench/golden-png/ for review
    py -3 scripts/golden.py --determinism    # render twice with different hash seeds and compare

The corpus is tests/golden/corpus.json (written by tests/golden/make_inputs.py). For each entry
tests/golden/ holds NAME.svg and NAME.json: the argv, exit code, verdict JSON (output paths
removed), a hash of the HTML page, and the receipt (input paths reduced to file names).

Rendering runs in this process through graph.cli(), the same entry point the browser playground
uses, so it keeps working when graph.py becomes a shim over the package. PYTHONHASHSEED is pinned
to 0 so a set's iteration order can't change the output between runs.
"""
import argparse
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(REPO, "tests", "golden")
CORPUS = os.path.join(GOLDEN, "corpus.json")
PNG_DIR = os.path.join(REPO, "bench", "golden-png")
PATH_KEYS = ("spec", "csv", "src")  # receipt fields that hold input paths


def load_corpus(only=None):
    with open(CORPUS, encoding="utf-8") as f:
        corpus = json.load(f)
    if only:
        want = set(only)
        corpus = [c for c in corpus if c["name"] in want or want & set(c.get("tags", []))]
    return corpus


_ENGINE = None


def engine():
    """The engine module, imported once from this checkout."""
    global _ENGINE
    if _ENGINE is None:
        if REPO not in sys.path:
            sys.path.insert(0, REPO)
        import graph  # noqa: E402  (graph.py today; a shim over the package after P1)
        _ENGINE = graph
    return _ENGINE


def run_cli(argv):
    """Run one CLI command in this process. Returns (exit code, stdout, stderr)."""
    g = engine()
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_cwd = sys.argv, os.getcwd()
    sys.argv = ["graph"] + list(argv)
    os.chdir(REPO)
    code = 0
    try:
        with redirect_stdout(out), redirect_stderr(err):
            g.cli()
    except SystemExit as e:
        if isinstance(e.code, int):
            code = e.code
        elif e.code is None:
            code = 0
        else:
            code = 1
            err.write(str(e.code))
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    return code, out.getvalue(), err.getvalue()


def _path_variants(p):
    p = os.path.abspath(p)
    vs = {p, p.replace("\\", "/"), p.replace("\\", "\\\\"), p.replace("/", "\\")}
    return sorted(vs, key=len, reverse=True)


def normalizer(outdir):
    """A function that removes machine-specific paths from text."""
    subs = [(v, "<out>") for v in _path_variants(outdir)] + [(v, "<repo>") for v in _path_variants(REPO)]
    tmp = tempfile.gettempdir()
    subs += [(v, "<tmp>") for v in _path_variants(tmp)]
    pat = re.compile("|".join(re.escape(v) for v, _ in subs), re.I)
    table = {v.lower(): r for v, r in subs}

    def norm(text):
        text = text.replace("\r\n", "\n")
        text = pat.sub(lambda m: table[m.group(0).lower()], text)
        # <out>\x.svg and <out>/x.svg are the same path
        return re.sub(r"(<(?:out|repo|tmp)>)([^\s\"',;]*)", lambda m: m.group(1) + m.group(2).replace("\\\\", "/").replace("\\", "/"), text)
    return norm


def _norm_obj(obj, norm):
    if isinstance(obj, str):
        return norm(obj)
    if isinstance(obj, list):
        return [_norm_obj(v, norm) for v in obj]
    if isinstance(obj, dict):
        return {k: _norm_obj(v, norm) for k, v in obj.items()}
    return obj


def _last_json(text):
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                return None
    return None


def render(entry, outdir):
    """Render one corpus entry into outdir. Returns the raw result plus timing."""
    name = entry["name"]
    svg_path = os.path.join(outdir, name + ".svg")
    t0 = time.perf_counter()
    code, out, err = run_cli(entry["argv"] + ["-o", svg_path])
    ms = (time.perf_counter() - t0) * 1000.0

    def read(path):
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    receipt_text = read(os.path.join(outdir, name + ".graph.json"))
    return {"name": name, "argv": entry["argv"], "code": code, "stdout": out, "stderr": err,
            "verdict": _last_json(out), "svg": read(svg_path), "html": read(os.path.join(outdir, name + ".html")),
            "receipt": json.loads(receipt_text) if receipt_text else None, "ms": ms, "svg_path": svg_path}


def record(res, outdir):
    """The comparable part of a render: no timings, no machine paths."""
    norm = normalizer(outdir)
    verdict = res["verdict"]
    if verdict is not None:
        verdict = {k: v for k, v in verdict.items() if k not in ("svg", "html", "receipt")}
        verdict = _norm_obj(verdict, norm)
    receipt = res["receipt"]
    if receipt is not None:
        receipt = {k: (os.path.basename(str(v).replace("\\", "/")) if k in PATH_KEYS and v else v)
                   for k, v in receipt.items()}
        receipt = _norm_obj(receipt, norm)
    rec = {"argv": res["argv"], "exit": res["code"], "verdict": verdict, "receipt": receipt,
           "html_sha256": hashlib.sha256(norm(res["html"]).encode("utf-8")).hexdigest() if res["html"] else None}
    if verdict is None:  # not JSON: keep the text so a change in it still shows
        rec["output"] = norm((res["stdout"] + res["stderr"]).strip())[-2000:]
    return rec, (norm(res["svg"]) if res["svg"] is not None else None)


def golden_paths(name):
    return os.path.join(GOLDEN, name + ".svg"), os.path.join(GOLDEN, name + ".json")


def dump(rec, svg, name, folder):
    svg_p, json_p = os.path.join(folder, name + ".svg"), os.path.join(folder, name + ".json")
    if svg is not None:
        with open(svg_p, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
    elif os.path.exists(svg_p):
        os.remove(svg_p)
    with open(json_p, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def _read(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def compare(rec, svg, name, folder=GOLDEN):
    """Differences between a fresh render and the stored one, as short readable lines."""
    svg_p, json_p = os.path.join(folder, name + ".svg"), os.path.join(folder, name + ".json")
    old_json = _read(json_p)
    if old_json is None:
        return ["no golden file (run --update)"]
    problems = []
    new_json = json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if old_json != new_json:
        diff = list(difflib.unified_diff(old_json.splitlines(), new_json.splitlines(), "golden", "now", n=0, lineterm=""))
        problems.append("record differs:\n      " + "\n      ".join(diff[2:14]) + ("\n      ..." if len(diff) > 14 else ""))
    old_svg = _read(svg_p)
    if (old_svg is None) != (svg is None):
        problems.append("svg " + ("appeared" if old_svg is None else "disappeared"))
    elif svg is not None and old_svg != svg:
        a, b = old_svg.splitlines(), svg.splitlines()
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
        sa = a[i][:160] if i < len(a) else "<end>"
        sb = b[i][:160] if i < len(b) else "<end>"
        problems.append(f"svg differs from line {i + 1} ({len(a)} -> {len(b)} lines):\n      - {sa}\n      + {sb}")
    return problems


def rasterize(res, outdir):
    os.makedirs(PNG_DIR, exist_ok=True)
    if res["svg"] is None:
        return
    base = os.path.join(outdir, res["name"])
    run_cli(["export", base, "--to", "png", "-o", os.path.join(PNG_DIR, res["name"] + ".png")])


def determinism(only):
    """Render the corpus in two processes with different hash seeds and compare everything."""
    work = tempfile.mkdtemp(prefix="golden-det-")
    dirs = []
    for seed in ("1", "2"):
        d = os.path.join(work, "seed" + seed)
        os.makedirs(d)
        env = dict(os.environ, PYTHONHASHSEED=seed)
        args = [sys.executable, os.path.abspath(__file__), "--dump", d] + (["--only"] + only if only else [])
        subprocess.run(args, env=env, check=True)
        dirs.append(d)
    names = sorted({os.path.splitext(n)[0] for n in os.listdir(dirs[0]) if n.endswith(".json")})
    differ = []
    for name in names:
        for ext in (".svg", ".json"):
            a, b = _read(os.path.join(dirs[0], name + ext)), _read(os.path.join(dirs[1], name + ext))
            if a != b:
                differ.append(name + ext)
    shutil.rmtree(work, ignore_errors=True)
    if differ:
        print(f"NOT deterministic across hash seeds: {len(differ)} files differ")
        for d in differ:
            print("  " + d)
        return 1
    print(f"deterministic: {len(names)} figures identical across hash seeds 1 and 2")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render the golden corpus and compare it with tests/golden/.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare with tests/golden/ (default)")
    mode.add_argument("--update", action="store_true", help="rewrite tests/golden/ from the current engine")
    mode.add_argument("--determinism", action="store_true", help="compare two renders under different hash seeds")
    mode.add_argument("--dump", metavar="DIR", help=argparse.SUPPRESS)
    mode.add_argument("--list", action="store_true", help="list corpus entries")
    ap.add_argument("--only", nargs="+", metavar="NAME_OR_TAG", help="limit to these names or tags")
    ap.add_argument("--png", action="store_true", help="also rasterize every figure to bench/golden-png/")
    a = ap.parse_args(argv)

    if a.determinism:
        return determinism(a.only)
    if a.dump is None and os.environ.get("PYTHONHASHSEED") != "0":
        env = dict(os.environ, PYTHONHASHSEED="0")
        return subprocess.run([sys.executable, os.path.abspath(__file__)] + sys.argv[1:], env=env).returncode

    corpus = load_corpus(a.only)
    if a.list:
        for c in corpus:
            print(f'{c["name"]:28} {" ".join(c["tags"]):22} {" ".join(c["argv"])}')
        return 0
    if not corpus:
        print("nothing in the corpus matches --only")
        return 1

    outdir = tempfile.mkdtemp(prefix="golden-")
    changed, start = [], time.perf_counter()
    try:
        for entry in corpus:
            res = render(entry, outdir)
            rec, svg = record(res, outdir)
            if a.png:
                rasterize(res, outdir)
            if a.dump:
                dump(rec, svg, entry["name"], a.dump)
            elif a.update:
                dump(rec, svg, entry["name"], GOLDEN)
            else:
                problems = compare(rec, svg, entry["name"])
                if problems:
                    changed.append(entry["name"])
                    print(f"CHANGED {entry['name']}")
                    for p in problems:
                        print("    " + p)
    finally:
        shutil.rmtree(outdir, ignore_errors=True)
    secs = time.perf_counter() - start
    if a.dump:
        return 0
    if a.update:
        if not a.only:  # a full update also drops goldens for entries that left the corpus
            keep = {c["name"] for c in corpus}
            for n in os.listdir(GOLDEN):
                stem, ext = os.path.splitext(n)
                if ext in (".svg", ".json") and stem not in keep and n != "corpus.json":
                    os.remove(os.path.join(GOLDEN, n))
        print(f"updated {len(corpus)} golden figures in {secs:.1f}s")
        return 0
    if changed:
        print(f"\n{len(changed)} of {len(corpus)} figures changed ({secs:.1f}s). "
              "If every change is intended, run: py -3 scripts/golden.py --update --only " + " ".join(changed[:12]))
        return 1
    print(f"all {len(corpus)} golden figures match ({secs:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

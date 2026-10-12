#!/usr/bin/env python3
"""Measure the engine for the redesign scoreboard (docs/PLAN.md, P0.2).

    py -3 scripts/metrics.py                    # golden corpus + counts + startup -> bench/metrics/latest.json/.md
    py -3 scripts/metrics.py --save baseline    # write bench/metrics/baseline.json/.md (committed)
    py -3 scripts/metrics.py --fuzz 200         # also run the fuzz harness on 200 scenes
    py -3 scripts/metrics.py --quick            # skip the cold-start timings (they start ~40 processes)
    py -3 scripts/metrics.py --compare bench/metrics/baseline.json

Per figure: render time in this process, time spent in the audit, layout redraws (the repair
loops), canvas size, audit errors by code, truncated texts, arrow crossings and wire length.
Startup: how long a fresh process takes to import the engine and to render, with and without
cached bytecode (PYTHONDONTWRITEBYTECODE=1 makes every call recompile graph.py).
"""
import argparse
import collections
import functools
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import counts  # noqa: E402
import golden  # noqa: E402

OUT_DIR = os.path.join(REPO, "bench", "metrics")
HOOKED = ("_audit_file", "_svg_geometry", "_render_flow_once", "_render_arch_once", "_render_schema_once")
COLD_FIGURES = ["flow-decision", "arch-checkout-groups", "site-signups", "gen-flow-40"]
TRUNC = ("…", "...")


# ---------- in-process hooks ----------

class Hooks:
    """Counts calls and time in named engine functions, wherever the package keeps them."""

    def __init__(self):
        self.calls = collections.Counter()
        self.ms = collections.Counter()
        self.original = {}

    def install(self):
        golden.engine()
        mods = [m for n, m in list(sys.modules.items())
                if m is not None and (n == "graph" or n.startswith("diagonaldiagrams"))]
        for name in HOOKED:
            for m in mods:
                fn = getattr(m, name, None)
                if fn is None or getattr(fn, "_metrics_hook", False):
                    continue
                self.original.setdefault(name, fn)
                setattr(m, name, self._wrap(name, fn))

    def _wrap(self, name, fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                self.calls[name] += 1
                self.ms[name] += (time.perf_counter() - t0) * 1000.0
        wrapper._metrics_hook = True
        return wrapper

    def reset(self):
        self.calls.clear()
        self.ms.clear()


def _canvas(svg_text):
    m = re.search(r'viewBox="\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)', svg_text or "")
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)


def figure_metrics(res, hooks):
    v = res["verdict"] or {}
    errors = v.get("errors", []) if v.get("stage") != "validate" else []
    row = {
        "exit": res["code"],
        "ok": bool(v.get("ok")),
        "stage": v.get("stage"),
        "render_ms": round(res["ms"], 1),
        "audit_ms": round(hooks.ms["_audit_file"], 1),
        "geometry_calls": hooks.calls["_svg_geometry"],
        "geometry_ms": round(hooks.ms["_svg_geometry"], 1),
        "redraws": sum(hooks.calls[n] for n in ("_render_flow_once", "_render_arch_once", "_render_schema_once")),
        "errors": dict(collections.Counter(e.get("code") or "?" for e in errors)),
        "warnings": len(v.get("warnings", [])),
    }
    svg = res["svg"]
    if svg:
        w, h = _canvas(svg)
        row.update({"width": w, "height": h, "aspect": round(w / h, 3) if h else None})
        try:
            root = ET.fromstring(svg)
        except ET.ParseError:
            return row
        texts = ["".join(el.itertext()).strip() for el in root.iter() if str(el.tag).endswith("text")]
        row["texts"] = len(texts)
        row["truncated"] = sum(1 for t in texts if t.endswith(TRUNC))
        stats = {"crossings": 0, "wire": 0.0}
        geo = hooks.original.get("_svg_geometry")
        if geo and w and h:
            geo(root, w, h, stats)
            row["crossings"] = stats["crossings"]
            row["wire"] = round(stats["wire"], 1)
    return row


def measure_corpus(hooks):
    corpus = golden.load_corpus()
    outdir = tempfile.mkdtemp(prefix="metrics-")
    rows = {}
    try:
        for entry in corpus:
            hooks.reset()
            res = golden.render(entry, outdir)
            rows[entry["name"]] = dict(figure_metrics(res, hooks), tags=entry.get("tags", []))
    finally:
        shutil.rmtree(outdir, ignore_errors=True)
    return rows


# ---------- fresh processes ----------

def _time_cmd(cmd, env, runs=3, warm=False):
    if warm:
        subprocess.run(cmd, env=env, cwd=REPO, capture_output=True)
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        subprocess.run(cmd, env=env, cwd=REPO, capture_output=True)
        times.append((time.perf_counter() - t0) * 1000.0)
    return round(statistics.median(times), 1)


def measure_startup():
    """Median wall time of fresh processes. 'uncached' recompiles graph.py every time, as
    `py graph.py ...` always does; 'cached' imports the engine from bytecode, as an installed
    package does."""
    py = sys.executable
    base = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
    cache = tempfile.mkdtemp(prefix="metrics-pyc-")
    uncached = dict(base, PYTHONDONTWRITEBYTECODE="1")
    cached = dict(base, PYTHONPYCACHEPREFIX=cache)
    imp = f"import sys; sys.path.insert(0, {REPO!r}); import graph"
    out = {
        "python_bare_ms": _time_cmd([py, "-c", "pass"], base),
        "import_uncached_ms": _time_cmd([py, "-c", imp], uncached),
        "import_cached_ms": _time_cmd([py, "-c", imp], cached, warm=True),
        "describe_script_ms": _time_cmd([py, "graph.py", "describe", "flow"], uncached),
        "renders": {},
    }
    corpus = {c["name"]: c for c in golden.load_corpus()}
    work = tempfile.mkdtemp(prefix="metrics-cold-")
    try:
        for name in COLD_FIGURES:
            if name not in corpus:
                continue
            argv = corpus[name]["argv"] + ["-o", os.path.join(work, name + ".svg")]
            code = (f"import sys; sys.path.insert(0, {REPO!r}); sys.argv = ['graph'] + {argv!r}; "
                    "import graph; graph.cli()")
            out["renders"][name] = {
                "script_uncached_ms": _time_cmd([py, "graph.py"] + argv, uncached),
                "module_cached_ms": _time_cmd([py, "-c", code], cached, warm=True),
            }
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(cache, ignore_errors=True)
    return out


# ---------- summary ----------

def summarize(rows):
    drawn = {n: r for n, r in rows.items() if r.get("stage") != "validate"}
    times = sorted(r["render_ms"] for r in drawn.values())
    codes = collections.Counter()
    for r in drawn.values():
        codes.update(r["errors"])
    slow = sorted(drawn.items(), key=lambda kv: -kv[1]["render_ms"])[:10]
    flows = {n: {k: r.get(k) for k in ("render_ms", "redraws", "width", "height", "aspect", "ok")}
             for n, r in rows.items() if n.startswith("gen-flow-")}
    return {
        "figures": len(rows),
        "drawn": len(drawn),
        "audit_failures": sorted(n for n, r in drawn.items() if not r["ok"]),
        "render_ms_total": round(sum(times), 1),
        "render_ms_median": round(statistics.median(times), 1) if times else 0,
        "render_ms_p90": round(times[int(len(times) * 0.9) - 1], 1) if times else 0,
        "render_ms_max": round(times[-1], 1) if times else 0,
        "redraws_total": sum(r["redraws"] for r in drawn.values()),
        "audit_ms_total": round(sum(r["audit_ms"] for r in drawn.values()), 1),
        "error_codes": dict(codes.most_common()),
        "truncated_texts": sum(r.get("truncated", 0) for r in drawn.values()),
        "figures_with_truncation": sum(1 for r in drawn.values() if r.get("truncated")),
        "crossings_total": sum(r.get("crossings", 0) for r in drawn.values()),
        "wire_total": round(sum(r.get("wire", 0) for r in drawn.values()), 1),
        "slowest": [{"name": n, "render_ms": r["render_ms"], "redraws": r["redraws"]} for n, r in slow],
        "generated_flows": flows,
    }


def machine():
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()
        except OSError:
            return ""
    return {
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "commit": git("rev-parse", "--short", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpus": os.cpu_count(),
        "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE", ""),
    }


def markdown(m):
    s, c, st = m["summary"], m["counts"], m.get("startup")
    lines = [f"# Engine metrics: {m['machine']['date']} ({m['machine']['commit']}"
             f"{', dirty' if m['machine']['dirty'] else ''})", "",
             f"Python {m['machine']['python']} on {m['machine']['platform']}, {m['machine']['cpus']} CPUs.", "",
             "## Corpus", "",
             "| Measure | Value |", "| --- | --- |",
             f"| Figures (drawn) | {s['figures']} ({s['drawn']}) |",
             f"| Failing the audit | {len(s['audit_failures'])}: {', '.join(s['audit_failures']) or 'none'} |",
             f"| Render time, total / median / p90 / max | {s['render_ms_total']:.0f} / {s['render_ms_median']:.0f} / "
             f"{s['render_ms_p90']:.0f} / {s['render_ms_max']:.0f} ms |",
             f"| Layout redraws (repair loops) | {s['redraws_total']} |",
             f"| Time in the final audit | {s['audit_ms_total']:.0f} ms |",
             f"| Audit errors by code | {', '.join(f'{k} {v}' for k, v in s['error_codes'].items()) or 'none'} |",
             f"| Truncated texts | {s['truncated_texts']} in {s['figures_with_truncation']} figures |",
             f"| Arrow crossings / wire length | {s['crossings_total']} / {s['wire_total']:.0f} px |", "",
             "## Generated flows", "",
             "| Figure | Render ms | Redraws | Canvas | Aspect | Audit |", "| --- | --- | --- | --- | --- | --- |"]
    for n, f in s["generated_flows"].items():
        lines.append(f"| {n} | {f['render_ms']:.0f} | {f['redraws']} | {f['width']:.0f} × {f['height']:.0f} | "
                     f"{f['aspect']} | {'ok' if f['ok'] else 'fails'} |")
    lines += ["", "## Slowest figures", "", "| Figure | Render ms | Redraws |", "| --- | --- | --- |"]
    lines += [f"| {x['name']} | {x['render_ms']:.0f} | {x['redraws']} |" for x in s["slowest"]]
    if st:
        lines += ["", "## Startup (fresh processes, median of 3)", "",
                  "| Measure | ms |", "| --- | --- |",
                  f"| `python -c pass` | {st['python_bare_ms']:.0f} |",
                  f"| import graph, recompiling | {st['import_uncached_ms']:.0f} |",
                  f"| import graph, from bytecode | {st['import_cached_ms']:.0f} |",
                  f"| `graph.py describe flow` | {st['describe_script_ms']:.0f} |"]
        for n, r in st["renders"].items():
            lines.append(f"| render {n}: `graph.py`, recompiling / imported from bytecode | "
                         f"{r['script_uncached_ms']:.0f} / {r['module_cached_ms']:.0f} |")
    lines += ["", "## Static counts", "", counts.markdown(c)]
    fz = m.get("fuzz")
    if fz:
        lines += ["", f"## Fuzz: {fz['scenes']} scenes, {fz['failed']} failed the audit "
                  f"({(fz['failure_rate'] or 0) * 100:.1f}%), {fz['invalid']} invalid", "",
                  "| Kind | Nodes | Scenes | Failed | Rate | Median ms | Max ms |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for t in fz["by_kind_and_size"]:
            rate = f"{t['failure_rate'] * 100:.0f}%" if t["failure_rate"] is not None else "-"
            lines.append(f"| {t['kind']} | {t['nodes']} | {t['scenes']} | {t['failed']} | {rate} | "
                         f"{t['median_ms']:.0f} | {t['max_ms']:.0f} |")
        lines += ["", "Scenes per error code: " + ", ".join(f"{k} {v}" for k, v in fz["scenes_with_code"].items())]
    return "\n".join(lines) + "\n"


def compare(cur, base_path):
    with open(base_path, encoding="utf-8") as f:
        base = json.load(f)
    worse = []
    for name, r in cur["figures"].items():
        b = base["figures"].get(name)
        if b and b["render_ms"] >= 20 and r["render_ms"] > 2 * b["render_ms"]:
            worse.append(f"{name}: {b['render_ms']:.0f} -> {r['render_ms']:.0f} ms")
    s, bs = cur["summary"], base["summary"]
    print(f"render total {bs['render_ms_total']:.0f} -> {s['render_ms_total']:.0f} ms; "
          f"redraws {bs['redraws_total']} -> {s['redraws_total']}; "
          f"audit failures {len(bs['audit_failures'])} -> {len(s['audit_failures'])}; "
          f"truncated {bs['truncated_texts']} -> {s['truncated_texts']}")
    for k in ("chart_renderers", "truncation_calls", "inline_font_settings", "side_channels", "system_exits"):
        print(f"  {k}: {base['counts'].get(k)} -> {cur['counts'].get(k)}")
    if worse:
        print("more than 2x slower: " + "; ".join(worse))
    return worse


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measure the engine for the redesign scoreboard.")
    ap.add_argument("--save", metavar="NAME", help="write bench/metrics/NAME.json and .md (default: latest)")
    ap.add_argument("--quick", action="store_true", help="skip cold-start timings")
    ap.add_argument("--fuzz", type=int, default=0, metavar="N", help="also fuzz N scenes")
    ap.add_argument("--compare", metavar="JSON", help="print changes against an earlier metrics file")
    ap.add_argument("--fail-on-regression", action="store_true", help="with --compare: exit 1 if a figure got 2x slower")
    a = ap.parse_args(argv)

    if os.environ.get("PYTHONHASHSEED") != "0":  # same pinning as the golden check
        env = dict(os.environ, PYTHONHASHSEED="0")
        return subprocess.run([sys.executable, os.path.abspath(__file__)] + sys.argv[1:], env=env).returncode

    hooks = Hooks()
    hooks.install()
    t0 = time.perf_counter()
    rows = measure_corpus(hooks)
    m = {"machine": machine(), "counts": counts.count_all(), "summary": summarize(rows), "figures": rows}
    if not a.quick:
        m["startup"] = measure_startup()
    if a.fuzz:
        sys.path.insert(0, os.path.join(REPO, "tests", "fuzz"))
        import run as fuzz_run  # noqa: E402
        m["fuzz"] = fuzz_run.summarize(fuzz_run.run(a.fuzz, 0, ["flow", "arch"]))
    m["seconds"] = round(time.perf_counter() - t0, 1)

    os.makedirs(OUT_DIR, exist_ok=True)
    name = a.save or "latest"
    with open(os.path.join(OUT_DIR, name + ".json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(m, f, indent=1, sort_keys=True)
    with open(os.path.join(OUT_DIR, name + ".md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(markdown(m))
    s = m["summary"]
    print(f"{s['figures']} figures in {s['render_ms_total'] / 1000:.1f}s render time; "
          f"{len(s['audit_failures'])} fail the audit; {s['redraws_total']} redraws; "
          f"{s['truncated_texts']} truncated texts -> bench/metrics/{name}.md")
    if a.compare:
        worse = compare(m, a.compare)
        if worse and a.fail_on_regression:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Draw the quality benchmark's figures as SVG: python bench/quality/render.py

Three sets, written to bench/quality/svg/:
  A-<steps>-<run>-<tool>   the token benchmark's agent figures, copied as the agents left them
  L-<source>-<tool>        one Mermaid source (bench/quality/sources/*.mmd) drawn by all three tools
  N-<ref>-dd               our reference figures from their native specs (examples/*.json), against
                           Pele's and Mermaid's drawings of the Mermaid translation in L-ref-*

Tools: diagonaldiagrams from this checkout, Pele 1.6.0 and mermaid-cli 12 from the bench tools folder.
Each tool runs at its defaults. Every output is deleted first, so dd never takes its edit path.

A rerun of dd alone, with a fit, from another checkout, into bench/quality/runs/NAME/svg:

    py -3 bench/quality/render.py --run fit-column --fit column --dd D:/path/to/checkout

It redraws dd's figures with --fit (the agent figures from the agents' own specs) and copies Pele's and
Mermaid's from svg/, so they are the same drawings the first judging saw."""
import argparse, glob, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TOOLS = os.environ.get("BENCH_TOOLS", r"D:\Repos\diagonaldiagrams-bench-tools")
RUNS = os.environ.get("BENCH_RUNS", r"D:\Repos\diagonaldiagrams-bench-runs")
PELE = os.path.join(TOOLS, "pele", "node_modules", "pele", "dist", "pele.js")
MMDC = os.path.join(TOOLS, "mermaid-cli", "node_modules", "@mermaid-js", "mermaid-cli", "src", "cli.js")
PUPPETEER = os.path.join(TOOLS, "bin", "puppeteer.json")
OUT = os.path.join(HERE, "svg")

# reference figures with a Mermaid equivalent: (Mermaid source, dd command, native spec)
NATIVE = {
    "ref-arch-checkout-groups": ("arch", "examples/checkout_groups.json"),
    "ref-arch-agent-platform": ("arch", "examples/agent_platform.json"),
    "ref-seq-checkout": ("seq", "examples/seq_checkout.json"),
    "ref-seq-toolloop": ("seq", "examples/show_toolloop.json"),
    "ref-schema-ecommerce": ("schema", "examples/schema_ecommerce.json"),
    "ref-schema-store": ("schema", "examples/show_store.json"),
}


def dd(args, dest, checkout=REPO):
    """Run diagonaldiagrams from a checkout (this one unless given) into a fresh folder and keep the SVG."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=checkout)
    with tempfile.TemporaryDirectory(prefix="ddq-") as tmp:
        out = os.path.join(tmp, "figure.svg")
        p = subprocess.run([sys.executable, "-m", "diagonaldiagrams", *args, "-o", out], cwd=checkout, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not os.path.isfile(out):
            print(f"dd failed on {args}: {p.stdout[-400:]} {p.stderr[-400:]}")
            return {"ok": False, "out": (p.stdout + p.stderr)[-800:]}
        shutil.copyfile(out, dest)
        try:
            verdict = json.loads(p.stdout)
        except ValueError:
            verdict = {"raw": p.stdout[-800:]}
        return {"ok": True, "verdict": verdict}


def mmdc(src, dest):
    p = subprocess.run(["node", MMDC, "-p", PUPPETEER, "-q", "-i", src, "-o", dest],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not os.path.isfile(dest):
        print(f"mmdc failed on {src}: {p.stderr[-400:]}")
    return {"ok": os.path.isfile(dest), "out": (p.stdout + p.stderr)[-800:]}


def rerun(name, fit, checkout):
    """dd's figures again with --fit FIT, drawn by checkout, beside copies of the others' (module doc)."""
    folder = os.path.join(HERE, "runs", name)
    out = os.path.join(folder, "svg")
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*.svg")):
        os.remove(f)
    for f in glob.glob(os.path.join(OUT, "*.svg")):
        if not os.path.basename(f).endswith("-dd.svg"):
            shutil.copyfile(f, os.path.join(out, os.path.basename(f)))
    log, flag = {}, ["--fit", fit]
    for d in sorted(glob.glob(os.path.join(RUNS, "diagonaldiagrams-*-r*"))):
        _, steps, run = os.path.basename(d).split("-")
        with open(os.path.join(d, "figure.graph.json"), encoding="utf-8") as f:
            receipt = json.load(f)  # what the agent drew: its command and its spec, at the defaults
        log[f"A-{steps}-{run}-dd"] = dd([receipt["cmd"], os.path.join(d, receipt["spec"]), *flag],
                                        os.path.join(out, f"A-{steps}-{run}-dd.svg"), checkout)
    for src in sorted(glob.glob(os.path.join(HERE, "sources", "*.mmd"))):
        name_ = os.path.splitext(os.path.basename(src))[0]
        log[f"L-{name_}-dd"] = dd(["mermaid", src, *flag], os.path.join(out, f"L-{name_}-dd.svg"), checkout)
    for name_, (cmd, spec) in NATIVE.items():
        log[f"N-{name_}-dd"] = dd([cmd, os.path.join(checkout, spec), *flag], os.path.join(out, f"N-{name_}-dd.svg"), checkout)
    head = subprocess.run(["git", "-C", checkout, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    with open(os.path.join(folder, "render-log.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"fit": fit, "dd_commit": head, "figures": log}, f, indent=1, sort_keys=True)
    print(f"wrote {len(glob.glob(os.path.join(out, '*.svg')))} SVGs to {out} (dd at {head}, --fit {fit})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", help="a rerun of dd alone into runs/RUN (needs --fit)")
    ap.add_argument("--fit", choices=["slide", "page", "column"])
    ap.add_argument("--dd", default=REPO, help="the diagonaldiagrams checkout to draw with (default: this one)")
    a = ap.parse_args()
    if a.run:
        if not a.fit:
            ap.error("--run needs --fit")
        return rerun(a.run, a.fit, os.path.abspath(a.dd))
    os.makedirs(OUT, exist_ok=True)
    for f in glob.glob(os.path.join(OUT, "*.svg")):
        os.remove(f)
    log = {}
    # A: the agents' own figures
    for d in sorted(glob.glob(os.path.join(RUNS, "*-*-r*"))):
        tool, steps, run = os.path.basename(d).split("-")
        short = {"diagonaldiagrams": "dd", "pele": "pele", "mermaid": "mermaid"}[tool]
        shutil.copyfile(os.path.join(d, "figure.svg"), os.path.join(OUT, f"A-{steps}-{run}-{short}.svg"))
    # L: one Mermaid source, three tools
    sources = sorted(glob.glob(os.path.join(HERE, "sources", "*.mmd")))
    pele_args = []
    for src in sources:
        name = os.path.splitext(os.path.basename(src))[0]
        log[f"L-{name}-dd"] = dd(["mermaid", src], os.path.join(OUT, f"L-{name}-dd.svg"))
        log[f"L-{name}-mermaid"] = mmdc(src, os.path.join(OUT, f"L-{name}-mermaid.svg"))
        pele_args += [src, os.path.join(OUT, f"L-{name}-pele.svg")]
    p = subprocess.run(["node", os.path.join(HERE, "pele_render.mjs"), PELE, *pele_args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        print("pele:", p.stderr)
    # N: our reference figures from their native specs
    for name, (cmd, spec) in NATIVE.items():
        log[f"N-{name}-dd"] = dd([cmd, os.path.join(REPO, spec)], os.path.join(OUT, f"N-{name}-dd.svg"))
    with open(os.path.join(HERE, "render-log.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(log, f, indent=1, sort_keys=True)
    n = len(glob.glob(os.path.join(OUT, "*.svg")))
    print(f"wrote {n} SVGs to {OUT}")


if __name__ == "__main__":
    main()

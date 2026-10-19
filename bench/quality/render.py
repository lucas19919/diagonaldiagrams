"""Draw the quality benchmark's figures as SVG: python bench/quality/render.py

Three sets, written to bench/quality/svg/:
  A-<steps>-<run>-<tool>   the token benchmark's agent figures, copied as the agents left them
  L-<source>-<tool>        one Mermaid source (bench/quality/sources/*.mmd) drawn by all three tools
  N-<ref>-dd               our reference figures from their native specs (examples/*.json), against
                           Pele's and Mermaid's drawings of the Mermaid translation in L-ref-*

Tools: diagonaldiagrams from this checkout, Pele 1.6.0 and mermaid-cli 12 from the bench tools folder.
Each tool runs at its defaults. Every output is deleted first, so dd never takes its edit path."""
import glob, json, os, shutil, subprocess, sys, tempfile

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


def dd(args, dest):
    """Run diagonaldiagrams from this checkout into a fresh folder and keep the SVG."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=REPO)
    with tempfile.TemporaryDirectory(prefix="ddq-") as tmp:
        out = os.path.join(tmp, "figure.svg")
        p = subprocess.run([sys.executable, "-m", "diagonaldiagrams", *args, "-o", out], cwd=REPO, env=env,
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


def main():
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

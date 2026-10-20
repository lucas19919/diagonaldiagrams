#!/usr/bin/env python3
"""Build the GitHub Pages site in docs/: render the gallery from examples/ with the engine itself,
and build the engine's wheel into docs/wheels/ so the in-browser playground runs the same code.

    py -3 scripts/build_site.py

Every figure must pass the audit, or the build stops: the site never shows a figure the engine
would reject.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(HERE, "graph.py")
DOCS = os.path.join(HERE, "docs")
OUT = os.path.join(DOCS, "gallery")
WHEELS = os.path.join(DOCS, "wheels")

# (file name, command line after graph.py, caption)
FIGURES = [
    ("agent-platform", ["arch", "examples/agent_platform.json"], "An AI agent platform, with groups and icons."),
    ("how-it-works", ["mermaid", "examples/how_it_works.mmd"], "How a diagram gets made. Loops are drawn up the outside."),
    ("checkout", ["arch", "examples/checkout_platform.json"], "Fourteen services, and every arrow gets its own path."),
    ("checkout-grouped", ["arch", "examples/checkout_groups.json"], "The same system, grouped."),
    ("deploy", ["flow", "examples/flow_decision.json"], "A decision with a retry loop."),
    ("sequence", ["mermaid", "examples/checkout_sequence.mmd"], "A checkout request, step by step."),
    ("data-model", ["mermaid", "examples/shop_er.mmd"], "A shop's data model."),
    ("icons", ["mermaid", "examples/icons.mmd"], "Built-in icons for users, databases, queues and more."),
    ("signups", ["line", "examples/signups.csv", "--x", "month", "--y", "signups", "--group", "product",
                 "--title", "Atlas more than doubled while Beacon declined",
                 "--subtitle", "Monthly signups per product, January to June 2026",
                 "--xlabel", "Month", "--ylabel", "Signups per month"], "Each line is named at its end, so there is no legend to look up."),
]

# The benchmark charts on the page, drawn from docs/data/ by the same engine. Not in the gallery.
SOURCE = "Claude Sonnet agents, two runs per point. Counts the tokens spent on the task, not the agent's fixed instructions."
MEASURED = [
    ("bench-tools", ["line", "docs/data/bench_tools.csv", "--x", "steps", "--y", "tokens", "--group", "tool",
                     "--highlight", "diagonaldiagrams", "--title", "Tokens per flowchart",
                     "--subtitle", "diagonaldiagrams stays under 2.1k as the diagram grows; with other tools the agent keeps checking its work",
                     "--xlabel", "Steps in the flowchart", "--ylabel", "Tokens used (average of 2 runs)", "--source", SOURCE]),
    ("bench-tools-0.8", ["line", "docs/data/bench_tools_0.8.csv", "--x", "steps", "--y", "tokens", "--group", "tool",
                         "--highlight", "diagonaldiagrams", "--title", "diagonaldiagrams costs about the same at any size",
                         "--subtitle", "Tokens a fresh agent spent on one flowchart. Pele costs least; Mermaid CLI climbs with the figure.",
                         "--xlabel", "Steps in the flowchart", "--ylabel", "Tokens per flowchart, average of 2 runs",
                         "--source", SOURCE]),
    # one size as bars: Mermaid CLI on a line chart flattens the other two against the axis
    ("bench-speed", ["bar", "docs/data/bench_speed_20.csv", "--cat", "tool", "--val", "ms", "--group", "tool",
                      "--orientation", "h", "--unit", "ms", "--highlight", "diagonaldiagrams",
                      "--title", "A figure in about 150 ms, 15 times faster than Mermaid CLI",
                      "--subtitle", "One 20-step flowchart, a new process each time. Pele only draws; diagonaldiagrams also audits.",
                      "--ylabel", "Time per call",
                      "--source", "medians, 2026-10-19. 5, 11 and 40 steps rank the same (docs/data/bench_speed_call.csv)."]),
    ("bench-quality", ["bar", "docs/data/bench_quality.csv", "--cat", "figure", "--val", "clearer", "--group", "against",
                        "--orientation", "h", "--unit", "%", "--ref", "50=even",
                        "--title", "Judged clearer in 3 of 4 settings against each",
                        "--subtitle", "Share of blind judgments that picked diagonaldiagrams as the clearer figure. Past the line, it won.",
                        "--ylabel", "Judged clearer",
                        "--source", "two judges, both orders. 124 judgments a tool on a slide, 16 for column flows, 8 for each architecture row."]),
]


def render(name, args):
    """Draw one figure into docs/gallery; stop the build if it fails its audit."""
    target = os.path.join(OUT, name + ".svg")
    p = subprocess.run([sys.executable, GRAPH] + args + ["-o", target], capture_output=True, text=True, cwd=HERE)
    try:
        rep = json.loads(p.stdout)
    except ValueError:
        rep = {"ok": False, "errors": [{"msg": (p.stdout + p.stderr)[-300:]}]}
    if not rep.get("ok"):
        sys.exit(f"{name}: {rep.get('errors')}")
    for extra in (".html", ".graph.json"):
        path = os.path.join(OUT, name + extra)
        if os.path.exists(path):
            os.remove(path)
    print("ok", name)


def main():
    os.makedirs(OUT, exist_ok=True)
    shown = []
    for name, args, caption in FIGURES:
        render(name, args)
        shown.append({"file": "gallery/" + name + ".svg", "caption": caption, "source": args[1]})
    for name, args in MEASURED:
        render(name, args)
    with open(os.path.join(DOCS, "gallery.json"), "w", encoding="utf-8") as f:
        json.dump(shown, f, indent=1)
    wheel = build_wheel()
    print(f"{len(shown)} figures; the playground loads wheels/{wheel}")


def build_wheel():
    """Build the pure-Python wheel the playground unpacks into Pyodide, and name it in latest.json."""
    shutil.rmtree(WHEELS, ignore_errors=True)
    os.makedirs(WHEELS)
    cmd = [sys.executable, "-m", "pip", "wheel", HERE, "--no-deps", "-q", "-w", WHEELS]
    try:
        import setuptools  # noqa: F401  (a local setuptools builds offline)
        cmd.insert(5, "--no-build-isolation")
    except ImportError:
        pass
    subprocess.run(cmd, check=True, cwd=HERE)
    for leftover in ("build", "diagonaldiagrams.egg-info"):
        shutil.rmtree(os.path.join(HERE, leftover), ignore_errors=True)
    wheel = next(n for n in os.listdir(WHEELS) if n.endswith(".whl"))
    with open(os.path.join(WHEELS, "latest.json"), "w", encoding="utf-8") as f:
        json.dump({"wheel": wheel}, f)
    return wheel


if __name__ == "__main__":
    main()

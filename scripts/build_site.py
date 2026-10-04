#!/usr/bin/env python3
"""Build the GitHub Pages site in docs/: render the gallery from examples/ with graph.py itself,
and copy graph.py next to the page so the in-browser playground runs the same engine.

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
    shutil.copy(GRAPH, os.path.join(DOCS, "graph.py"))
    print(f"{len(shown)} figures, graph.py copied for the playground")


if __name__ == "__main__":
    main()

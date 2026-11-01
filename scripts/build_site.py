#!/usr/bin/env python3
"""Build the GitHub Pages site in docs/: render the gallery from examples/ with the engine itself.

    py -3 scripts/build_site.py

Every figure must pass the audit, or the build stops: the site never shows a figure the engine
would reject.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(HERE, "graph.py")
DOCS = os.path.join(HERE, "docs")
OUT = os.path.join(DOCS, "gallery")

# (file name, command line after graph.py, caption)
FIGURES = [
    ("three-tier", ["iso", "examples/iso_three_tier.json"], "A layer stack in isometric 3D. The audit reads depth: what hides what."),
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

TALL = {"three-tier"}  # takes a whole row of the gallery
FILMED = {"three-tier"}  # the gallery shows its film (STORIES), which keeps its heading

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


# The site's look: warm paper, near-black ink, square boxes, one coral for the path that matters.
# Charts take the colors. Diagrams also take the stylesheet (hairline strokes, a quieter title).
SITE_THEME = os.path.join(HERE, "scripts", "site_theme.json")
SITE_STYLE = os.path.join(HERE, "scripts", "site_style.json")
SHOWCASE = os.path.join(DOCS, "showcase")
STORIES = [
    ("hero", "examples/showcase/agent_platform_story.json"),
    ("nvidia", "examples/showcase/nvidia_story.json"),
    ("palantir", "examples/showcase/palantir_story.json"),
    ("falcon9", "examples/showcase/falcon9_story.json"),
    ("three-tier", "examples/showcase/three_tier_story.json"),
]


def _look(kind):
    """Flags that draw a figure in the site's look. Charts have no --style; a block has no corners."""
    if kind == "iso":
        return ["--theme-file", SITE_THEME, "--style", SITE_STYLE]
    flags = ["--theme-file", SITE_THEME, "--corners", "sharp"]
    if kind not in ("line", "bar"):
        flags += ["--style", SITE_STYLE]
    return flags


def render(name, args):
    """Draw one figure into docs/gallery; stop the build if it fails its audit."""
    target = os.path.join(OUT, name + ".svg")
    p = subprocess.run([sys.executable, GRAPH] + args + _look(args[0]) + ["-o", target],
                       capture_output=True, text=True, cwd=HERE)
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


def crop_heading(path, top=64):
    """The showcase page already says the title, in display type. Shift the frame so the print
    starts at the boxes. Coordinates stay put, so the filmed motion still lines up."""
    import re
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r'viewBox="([0-9.]+) ([0-9.]+) ([0-9.]+) ([0-9.]+)"', text)
    if not m or float(m.group(2)) >= top - 1:
        return
    w, h = float(m.group(3)), float(m.group(4))
    cropped = f'viewBox="0 {top:.0f} {w:.0f} {h - top:.0f}"'
    text = text.replace(m.group(0), cropped, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def render_story(name, rel):
    """Film one showcase story into docs/showcase, in the same look as the gallery."""
    work = os.path.join(HERE, "out", "site-stories")
    os.makedirs(work, exist_ok=True)
    os.makedirs(SHOWCASE, exist_ok=True)
    html = os.path.join(work, name + ".html")
    anim = os.path.join(SHOWCASE, name + ".svg")
    p = subprocess.run(
        [sys.executable, GRAPH, "story", rel, "-o", html, "--svg", anim] + _look("story"),
        capture_output=True, text=True, cwd=HERE)
    try:
        rep = json.loads(p.stdout)
    except ValueError:
        rep = {"ok": False, "errors": [{"msg": (p.stdout + p.stderr)[-300:]}]}
    if not rep.get("ok"):
        sys.exit(f"{name}: {rep.get('errors')}")
    if name != "hero" and name not in FILMED:
        crop_heading(anim)
    print("ok", name)


def main():
    os.makedirs(OUT, exist_ok=True)
    shown = []
    for name, args, caption in FIGURES:
        render(name, args)
        shown.append({"file": ("showcase/" if name in FILMED else "gallery/") + name + ".svg", "caption": caption, "source": args[1],
                      **({"tall": True} if name in TALL else {})})
    for name, args in MEASURED:
        render(name, args)
    for name, rel in STORIES:
        render_story(name, rel)
    with open(os.path.join(DOCS, "gallery.json"), "w", encoding="utf-8") as f:
        json.dump(shown, f, indent=1)
    print(f"{len(shown)} figures")
    publish_llms_txt()


def publish_llms_txt():
    """Serve llms.txt from the site root too. Pages only serves docs/, and the repo's relative links
    would break there, so they become absolute GitHub links."""
    import re
    base = "https://github.com/lucas19919/diagonaldiagrams/blob/master/"
    with open(os.path.join(HERE, "llms.txt"), encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"\]\((?!https?://)([^)]+)\)", lambda m: "](" + base + m.group(1) + ")", text)
    with open(os.path.join(DOCS, "llms.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    main()

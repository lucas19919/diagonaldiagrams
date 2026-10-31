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
    ("ai-stack", ["iso", "examples/showcase/ai_stack.json"], "A layer stack in isometric 3D. The audit reads depth: what hides what."),
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
]


def _look(kind):
    """Flags that draw a figure in the site's look. Charts have no --style; iso takes only the colors."""
    if kind == "iso":
        return ["--theme-file", SITE_THEME]
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
    if name != "hero":
        crop_heading(anim)
    print("ok", name)


def publish_theme():
    """The playground fetches these. They are the same files the build draws with."""
    theme = os.path.join(DOCS, "theme")
    os.makedirs(theme, exist_ok=True)
    shutil.copyfile(SITE_THEME, os.path.join(theme, "site.json"))
    shutil.copyfile(SITE_STYLE, os.path.join(theme, "site-style.json"))


def main(wheel=True):
    os.makedirs(OUT, exist_ok=True)
    shown = []
    for name, args, caption in FIGURES:
        render(name, args)
        shown.append({"file": "gallery/" + name + ".svg", "caption": caption, "source": args[1]})
    for name, args in MEASURED:
        render(name, args)
    for name, rel in STORIES:
        render_story(name, rel)
    with open(os.path.join(DOCS, "gallery.json"), "w", encoding="utf-8") as f:
        json.dump(shown, f, indent=1)
    publish_theme()
    if wheel:
        built = build_wheel()
        print(f"{len(shown)} figures; the playground loads wheels/{built}")
    else:
        print(f"{len(shown)} figures; wheel left as it was")


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
    main(wheel="--no-wheel" not in sys.argv)

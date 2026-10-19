"""Write the token benchmark's prompts: one process in prose per size, one first paragraph per tool.

The processes are the golden corpus's generated flows (tests/golden/inputs/flows/flow-NN.json),
the same ones scripts/bench_speed.py times, told as prose. Every prompt is the same task; only
the first paragraph differs: which tool, and the command that runs it.

    py -3 scripts/bench_prompts.py --tools DIR --runs DIR --browser PATH

--tools is the folder npm installed the other tools into: mermaid-cli/ and pele/, each with its
node_modules/. This script writes the commands the agents run into its bin/:
- diagonaldiagrams.cmd runs this checkout with PYTHONDONTWRITEBYTECODE=1;
- mmdc.cmd runs mermaid-cli with puppeteer.json, which points it at --browser (Edge or Chrome);
- pele.cmd runs bench/tokens/pele_render.mjs, a minimal command line around Pele's render().
--runs is where each agent gets its own empty folder. Prompts go to bench/tokens/prompts/TOOL-NN.txt
with these paths filled in, so a rerun on another machine rewrites them.
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FLOWS = os.path.join(REPO, "tests", "golden", "inputs", "flows")
OUT = os.path.join(REPO, "bench", "tokens", "prompts")
SIZES = (5, 11, 20, 40)

TOOLS = {
    "diagonaldiagrams": (
        "Use diagonaldiagrams, an SVG diagram engine for agents. Run it as `{bin}\\diagonaldiagrams.cmd` "
        "(it takes the arguments its skill describes). Its skill is {repo}\\SKILL.md."),
    "mermaid": (
        "Use Mermaid CLI (mmdc). Run it as `{bin}\\mmdc.cmd -i IN.mmd -o OUT.svg` "
        "(OUT.png also works). Its options: `{bin}\\mmdc.cmd --help`."),
    "pele": (
        "Use Pele, a Mermaid renderer for Node. Run it as `{bin}\\pele.cmd IN.mmd OUT.svg`; "
        "`{bin}\\pele.cmd IN.mmd OUT.png` also writes a PNG of the same drawing."),
}

TASK = """{tool}

Draw this process as a flowchart. It has {n} steps, counting the start and the end.

{prose}

Make the figure clean and readable, with no overlapping text. Work in {folder} and save the figure there as figure.svg. When you are done, reply with the path to figure.svg and any commands that failed.
"""


def prose(spec):
    """The flow as a paragraph: runs of steps as sentences, each check as its two ways on."""
    nodes, last = spec["nodes"], len(spec["nodes"]) - 1
    out = {}
    for e in spec["edges"]:
        out.setdefault(int(e["from"][1:]), {})[e.get("label", "")] = int(e["to"][1:])

    def step(i):
        name = nodes[i]["name"].rsplit(" (", 1)[0]
        return f"{name[0].lower()}{name[1:]} (step {i})"

    def where(i, j):
        if j == last:
            return "skip straight to the end"
        return f"go back to step {j}" if j < i else f"skip ahead to step {j}"

    words, run = ["The process starts when a request is received."], []
    for i in range(1, last):
        if nodes[i].get("shape") != "diamond":
            run.append(step(i))
            continue
        if run:
            words.append(("Then " if len(words) > 1 else "First, ") + _join(run) + ".")
            run = []
        k = nodes[i]["name"].split()[1]
        yes = out[i]["yes"]
        on = "the process is done" if yes == last else f"go on to step {yes}"
        words.append(f"Step {i} checks whether check {k} passed: if it did, {on}; if not, {where(i, out[i]['no'])}.")
    if run:
        words.append(("Then " if len(words) > 1 else "First, ") + _join(run) + ".")
        words.append("Then the process is done.")
    return " ".join(words)


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def wrappers(tools, browser):
    binary = os.path.join(tools, "bin")
    os.makedirs(binary, exist_ok=True)
    cfg = os.path.join(binary, "puppeteer.json")
    mmdc = os.path.join(tools, "mermaid-cli", "node_modules", "@mermaid-js", "mermaid-cli", "src", "cli.js")
    pele = os.path.join(tools, "pele", "node_modules", "pele", "dist", "pele.js")
    render = os.path.join(REPO, "bench", "tokens", "pele_render.mjs")
    files = {
        "puppeteer.json": [json.dumps({"executablePath": browser, "headless": True})],
        "diagonaldiagrams.cmd": ["@echo off", "setlocal", "set PYTHONDONTWRITEBYTECODE=1", f'set "PYTHONPATH={REPO}"',
                                 "py -3 -m diagonaldiagrams %*"],
        "mmdc.cmd": ["@echo off", f'node "{mmdc}" -p "{cfg}" %*'],
        "pele.cmd": ["@echo off", f'node "{render}" "{pele}" "{browser}" %*'],
    }
    for name, lines in files.items():
        with open(os.path.join(binary, name), "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")
    return binary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", required=True, help="folder holding mermaid-cli/ and pele/; bin/ is written there")
    ap.add_argument("--runs", required=True, help="folder for the agents' working folders")
    ap.add_argument("--browser", required=True, help="Edge or Chrome, for mmdc and Pele's PNG option")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    binary = wrappers(os.path.normpath(os.path.abspath(a.tools)), os.path.normpath(a.browser))
    for n in SIZES:
        spec = json.load(open(os.path.join(FLOWS, f"flow-{n:02d}.json"), encoding="utf-8"))
        for tool, first in TOOLS.items():
            folder = os.path.join(os.path.normpath(os.path.abspath(a.runs)), f"{tool}-{n:02d}-RUN")
            text = TASK.format(tool=first.format(bin=binary, repo=REPO), n=n, prose=prose(spec), folder=folder)
            with open(os.path.join(OUT, f"{tool}-{n:02d}.txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    print(open(os.path.join(OUT, "mermaid-11.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()

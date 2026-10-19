# Token benchmark

How many tokens, calls and screenshots an agent spends to draw the same flowchart with each tool.
The README's "Measured" section reports the latest run.

## Setup

Install the other tools into a folder outside the repo, then write the prompts and the commands the agents run:

```bash
cd TOOLS/mermaid-cli && PUPPETEER_SKIP_DOWNLOAD=1 npm install @mermaid-js/mermaid-cli@12.0.0
cd TOOLS/pele && npm install pele@1.6.0
py -3 scripts/bench_prompts.py --tools TOOLS --runs RUNS --browser "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
```

The committed prompts show `<repo>`, `<bench-tools>` and `<bench-runs>` where the run had this machine's folders.

`bench_prompts.py` writes `prompts/TOOL-NN.txt`, one per tool and size (5, 11, 20 and 40 steps), and `TOOLS/bin/`:

| Command | Runs |
| --- | --- |
| `diagonaldiagrams.cmd` | this checkout, with `PYTHONDONTWRITEBYTECODE=1` |
| `mmdc.cmd` | mermaid-cli with `puppeteer.json`, which points it at the system browser (no browser download) |
| `pele.cmd` | `pele_render.mjs`: Pele's `render()`, writing SVG, or PNG through the headless browser |

Pele is a library with no command line, so `pele_render.mjs` is the smallest one. Its PNG option gives
Pele agents a way to look at their figure, as mmdc's PNG output does for Mermaid agents.

## A run

Each run is a fresh Claude Sonnet agent with one prompt and nothing else from the caller. Replace `RUN` in the
prompt's folder with `r1`, `r2`, and so on, give the agent that empty folder, and name the agent
`Bench TOOL NN rK` (for example `Bench pele 20 r2`); `bench_tokens.py` finds runs by that name.

Then count, from the transcripts Claude Code keeps for subagents:

```bash
py -3 scripts/bench_tokens.py ~/.claude/projects/PROJECT/SESSION/subagents --csv runs.csv --summary docs/data/bench_tools_0.8.csv
```

The prompts are the golden corpus's generated flows (`tests/golden/inputs/flows/`) told as prose, the same
flows `scripts/bench_speed.py` times. The 0.5.0 benchmark used a different prose prompt that was not kept,
so its numbers and these are not directly comparable.

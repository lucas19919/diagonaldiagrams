# diagonaldiagrams

Diagrams and charts your agent can draw, and check before it shows you. One command takes a short spec, Mermaid, or a CSV, lays it out, draws an SVG, and audits the drawing for labels on labels, arrows through boxes, and text that spills.

**[Try it in the browser](https://lucas19919.github.io/diagonaldiagrams/)**: the real engine, running in your browser.

![An AI agent platform with framed groups and icons, drawn and audited by diagonaldiagrams](https://raw.githubusercontent.com/lucas19919/diagonaldiagrams/master/docs/gallery/agent-platform.svg)

## Install

Claude Code, as a plugin. This adds the drawing skill:

```text
/plugin marketplace add lucas19919/diagonaldiagrams
/plugin install diagonaldiagrams@diagonaldiagrams
```

Any agent, as a command. This puts `diagonaldiagrams` on PATH:

```bash
pip install git+https://github.com/lucas19919/diagonaldiagrams
```

As MCP tools (`render`, `describe`, `validate`, `audit`, `export`, `infer`):

```bash
claude mcp add --scope user diagonaldiagrams -- diagonaldiagrams mcp
```

Or clone it and run `py -3 graph.py describe` (Windows) or `python3 graph.py describe`; `graph.py` runs the `diagonaldiagrams/` package next to it. If your environment sets `PYTHONDONTWRITEBYTECODE=1`, run `python -m compileall diagonaldiagrams` once so each call starts from compiled code. Agents can follow [`.agents/skills/diagonaldiagrams-install/SKILL.md`](.agents/skills/diagonaldiagrams-install/SKILL.md) to install, and [`.agents/skills/graph-engine/SKILL.md`](.agents/skills/graph-engine/SKILL.md) to draw.

## One command

```text
diagonaldiagrams mermaid flow.mmd -o out/flow.svg
{"ok": true, "svg": "out/flow.svg", "html": "out/flow.html", "receipt": "out/flow.graph.json", "items": 9,
 "layout": ["row 1: Your agent describes the diagram", "row 2: Check the description", "row 3: Makes sense? (decision)", ...]}
```

It checks the input, draws, audits the drawing, and prints one line of JSON. `ok: false` comes with errors, each with a `fix`; change the input and run it again. `layout` describes the drawn structure, so an agent can confirm it without looking at a picture.

The audit reads the finished SVG: labels on labels, labels too wide for their box or off the canvas, boxes on boxes, arrows through a box or across a label, two arrows on one line, and nodes inside a frame they don't belong to. When it finds a problem it can fix, the layout repairs itself. It reads any SVG, so `diagonaldiagrams audit` also checks a figure an agent wrote by hand.

## Input

| Command | Input | Draws |
| --- | --- | --- |
| `mermaid` | Mermaid `flowchart`, `sequenceDiagram`, or `erDiagram` | Picks `flow`, `seq`, or `schema` |
| `flow` | JSON | A decision flow, with frames (`groups`) and icons |
| `arch` | JSON | Services and the calls between them |
| `seq` | JSON | A sequence of messages |
| `schema` | JSON | Tables and their relations |
| `bar`, `line`, `scatter` | CSV | Comparisons, trends, relationships |
| `geo` | CSV or GeoJSON | Places on a built-in coastline |
| `chart <type>` | CSV or JSON | About 60 more: sankey, gantt, heatmap, treemap, box, radar, math, ... |

`describe <type>` prints the contract for any type. Long names wrap inside their boxes. Loops are drawn back up the outside. Built-in icons (`describe icons`) cover users, databases, servers, queues, and more; in Mermaid, write `fa:fa-database`.

## Output

| File | Contents |
| --- | --- |
| `OUT.svg` | The drawing. Title and subtitle are on the figure; points and bars have hover tooltips. |
| `OUT.html` | The same figure, plus Copy SVG, Export SVG, and Export PNG. A diagram's page also has Edit. |
| `OUT.graph.json` | The receipt. `export` redraws from it. |

## Edit and draw again

A diagram's page has Edit. A person renames a box, recolors it, or moves it: within its row or into another one, a schema table into another column, a sequence's actor along the actors. In a sequence they also drag a message to another step and change its label. Everything works from the keyboard too: Tab or the arrows go from box to box (Down from an actor goes to its messages), Shift+arrows move the selected box or message, Enter renames, 1–6 pick a color, Ctrl+Z undoes. Nothing in the figure's files changes: each edit becomes a patch operation, which the page shows with Copy patch and Save patch.json.

```text
diagonaldiagrams apply deploy.json patch.json
diagonaldiagrams flow deploy.json -o out/deploy.svg
{"ok": true, ..., "changed": ["Renamed \"Review\" to \"Peer review\"", "Row 4 now reads Peer review | Fix", "4 other boxes shifted, 103 px on average"]}
```

`apply` writes the patch into the spec as fields and constraints, so the next generation of the spec keeps it. A drag becomes `{"op": "place", "id": "fix", "row": ["review", "fix"]}`: the box's row and its place in it, not pixels. Drawn again at the same path, the figure keeps the other boxes near their places, the verdict lists what `changed`, and the new page animates from the old drawing to the new one (Replay change shows it again; reduced motion turns it off). `diagonaldiagrams diff OLD NEW` prints the same list for any two drawings (two pages compare by the layout's own rows, which a wrapped figure's heights don't show). MCP has `apply` and `diff` tools.

Keep the patch. When the spec is regenerated from a changed brief, apply it again: an edit that still fits is written in again (applying twice changes nothing), and one the new spec contradicts, such as a box that is gone or a name that changed, comes back as a `patch-conflict` with a fix. `tests/unit/test_regeneration.py` checks that every edit either shows in the new drawing or is reported.

`export OUT --to png|pdf|svg|drawio|excalidraw` writes other formats. draw.io and Excalidraw exports keep boxes, frames, and the routed arrows attached to their boxes, so a person can open the figure and drag things around. PNG and PDF use cairosvg if installed, else headless Edge or Chrome.

## Stories

One figure, several views of it, presented from one HTML page:

```text
diagonaldiagrams story examples/story_platform.json -o out/story.html
{"ok": true, "html": "out/story.html", "frames": 7, "views": [{"id": "platform", ...}, {"id": "request", "steps": 4, ...}], ...}
```

A view names parts of the figure with stylesheet selectors (`#agent`, `group#runtime node`, `edge[from=agent]`) and says what to do with them: `focus` points the camera at them, `dim` and `hide` set them back, `highlight` draws them in the accent, and `reveal` shows them one step at a time. Each view has a `title`, a `text` shown under the figure, and speaker `notes`. Every view keeps the figure's layout, so the page moves between views by fading looks and gliding the camera. Arrows and Space move, N shows the notes, a link to `#request/2` opens that step, and printing gives one page per step. `describe story` has the format.

A view can also move. `"motion": [{"trace": "web -> gw -> orders -> pay"}, {"flow": "edge[async]"}]` sends a packet along that path, lighting each arrow behind it, and runs dots along the async arrows. The engine works out the timing from the drawn routes, so a few words replace a timeline. `--gif OUT.gif` films the view as a seamless loop (pure Python), and `--video OUT.mp4` does too when ffmpeg is on the PATH.

```text
diagonaldiagrams story examples/story_checkout.json -o out/checkout.html --gif out/checkout.gif
```

## Measured

diagonaldiagrams 0.8.0 against Mermaid CLI and [Pele](https://pele.run), Obsidian's open-source Mermaid renderer, on 2026-10-19. Every tool drew the same four flowcharts: 5, 11, 20 and 40 steps, with checks that loop back or skip ahead ([`tests/golden/inputs/flows/`](tests/golden/inputs/flows)).

### Speed

Milliseconds per figure. Each cell is the median of three runs, and each run is the median of 9 calls (in process, of 18 to 360 renders):

| | 5 steps | 11 steps | 20 steps | 40 steps |
| --- | --- | --- | --- | --- |
| Pele `render()`, in one Node process | 0.24 | 0.40 | 0.61 | 1.05 |
| diagonaldiagrams draw, in one Python process | 3.5 | 5.9 | 13.9 | 29.3 |
| diagonaldiagrams command, in one Python process | 13 | 26 | 41 | 65 |
| Pele, a new Node process per figure | 95 | 104 | 101 | 107 |
| diagonaldiagrams CLI, from bytecode | 208 | 235 | 242 | 276 |
| diagonaldiagrams CLI, recompiling | 396 | 401 | 428 | 430 |
| Mermaid CLI (`mmdc`), per call | 2,333 | 2,399 | 2,340 | 2,556 |

- Per call, which is what an agent waits for, diagonaldiagrams is 9 to 11 times faster than Mermaid CLI (5.5 to 6 times when it recompiles), because each `mmdc` call starts Node and a headless browser before mermaid.js draws. A Pele process is 2.2 to 2.6 times faster than a diagonaldiagrams one.
- In process, Pele draws 15 to 28 times faster than diagonaldiagrams. Pele only draws. The diagonaldiagrams command also audits the drawing and writes the outline, the HTML page, and the receipt.
- Pele's site quotes 0.05 to 0.3 ms per render, without saying for which diagrams. On these flows it took 0.24 ms at 5 steps and 1.05 ms at 40. Its figure for mermaid.js inside a page (6 to 82 ms) was not checked here: `mmdc` adds starting Node and a browser to every call.
- "Draw" is Mermaid text in, SVG out (`load_spec` and `render_flow`). "Command" is `mermaid FILE -o OUT`, the whole CLI call without starting Python. "Recompiling" is a machine with no bytecode cache (`PYTHONDONTWRITEBYTECODE=1`); `python -m compileall diagonaldiagrams` once avoids it. Starting Python itself took 37 ms.
- Run on Windows 11 with 16 CPUs, Python 3.14.2, Node 24.11.1, mermaid-cli 12.0.0 (mermaid 12.2.0) driving the system Edge, and Pele 1.6.0. Other programs kept the CPU about 45% busy. Across the three runs, per-call times varied by up to 17% (one Pele cell by 44%) and in-process times by up to 40%. `py -3 scripts/bench_speed.py` reruns it (`--help` for the Mermaid and Pele options).

### Tokens

Each run is a fresh Claude Sonnet agent given one prose task: draw this process, clean and readable, with no overlapping text, as `figure.svg`. Two runs per point.

![Tokens per flowchart for three tools: diagonaldiagrams stays between 4.4k and 6.4k, Mermaid CLI climbs from 1.8k to 15.4k, Pele stays under 2.7k until 6.3k at 40 steps](https://raw.githubusercontent.com/lucas19919/diagonaldiagrams/master/docs/gallery/bench-tools-0.8.svg)

Tokens per flowchart, mean of two runs:

| Steps | diagonaldiagrams | Mermaid CLI | Pele |
| --- | --- | --- | --- |
| 5 | 4.4k | **1.8k** | 2.6k |
| 11 | 6.0k | 2.8k | **1.7k** |
| 20 | 5.1k | 4.0k | **1.3k** |
| 40 | 6.4k | 15.4k | **6.3k** |

All eight runs per tool:

| | Tokens | Of which reading the skill | Calls | Screenshots | Time |
| --- | --- | --- | --- | --- | --- |
| diagonaldiagrams | 43.8k | 10.9k | 69 | 9 | 7 min |
| Mermaid CLI | 47.8k | – | 79 | 32 | 13 min |
| Pele | **23.9k** | – | **57** | 18 | **5 min** |

What the runs show:

- Every figure passed diagonaldiagrams' audit, which reads any SVG: no overlapping text and no arrow through a box in any of the 24.
- Pele was the cheapest: about half the tokens of the other two. Its agents, like Mermaid's, read no docs, because the model already knows Mermaid. In five of eight runs they looked at one PNG and were done.
- diagonaldiagrams costs about the same at every size: 4.4k at 5 steps, 6.4k at 40. Of that, 1.4k is reading its skill, 0.7k to 2.7k is what its commands printed (the verdict, the outline, `describe`), and in 7 of 8 runs the agent also exported a PNG and looked at it anyway. That makes it the most expensive tool at 5 to 20 steps.
- Mermaid CLI grows fastest: from 1.8k to 15.4k. At 40 steps its agents checked a figure 5,000 px tall in slices, and 62% of all its tokens were screenshots.
- What they drew differs at 20 and 40 steps. diagonaldiagrams wraps a long flow into side-by-side columns: 1,192 × 849 px at 20 steps, about 1,600 × 1,400 at 40. Mermaid CLI and Pele drew one column, 2,300 to 2,600 px tall at 20 steps and 4,700 to 5,200 at 40.

How it was run:

- Every run got the same prompt. Only the first paragraph differs: which tool, and the command that runs it. The prompts are in [`bench/tokens/prompts/`](bench/tokens/prompts), written by `scripts/bench_prompts.py`; [`bench/tokens/README.md`](bench/tokens/README.md) has the steps.
- Tools: diagonaldiagrams 0.8.0 from a checkout, with its skill as a file to read; mermaid-cli 12.0.0 driving the system Edge; Pele 1.6.0 through `bench/tokens/pele_render.mjs`, a small command line around `render()` that writes SVG, or PNG through headless Edge, so Pele agents can look as Mermaid agents can.
- Counted: the run's own tokens, meaning what the agent wrote, what came back to it, files it read, and screenshots at Claude's image rate. Left out: the harness (system prompt, tool definitions, reminders), the final report, and thinking, which transcripts hide. Time runs from a run's first transcript entry to its last. `scripts/bench_tokens.py` recounts any run from its transcript.
- Caveats. Two runs per point, and single runs differ by up to 3.5×. Twelve agents ran at once on a busy machine and shared one browser pane. All agents were Claude Sonnet.
- The earlier run, on 0.5.0 (2026-10-04), had diagonaldiagrams at 12.7k tokens and no screenshots against Mermaid CLI's 63.9k, and also measured hand-written SVG, Graphviz and D2 ([`docs/data/bench_tools.csv`](docs/data/bench_tools.csv)). It does not compare directly with this one. Its prompt was not kept, so this one is new. Its diagonaldiagrams runs, 1.3k tokens at 5 steps, cannot have included reading the 1.4k-token skill. And its agents never looked at a PNG.

## Gallery

Every figure was drawn from a file in [`examples/`](examples) and passed its own audit. Rebuild them with `py -3 scripts/build_site.py`.

![How a figure is made](https://raw.githubusercontent.com/lucas19919/diagonaldiagrams/master/docs/gallery/how-it-works.svg)

![Checkout platform with frames](https://raw.githubusercontent.com/lucas19919/diagonaldiagrams/master/docs/gallery/checkout-grouped.svg)

![Checkout request, a sequence diagram](https://raw.githubusercontent.com/lucas19919/diagonaldiagrams/master/docs/gallery/sequence.svg)

![Shop data model](https://raw.githubusercontent.com/lucas19919/diagonaldiagrams/master/docs/gallery/data-model.svg)

![Signups line chart](https://raw.githubusercontent.com/lucas19919/diagonaldiagrams/master/docs/gallery/signups.svg)

## Tests

```bash
py -3 tests_smoke.py
```

Exit 0 means every check passed.

Run these before changing how anything is drawn:

| Command | What it does |
| --- | --- |
| `py -3 scripts/golden.py` | Compares 115 figures byte for byte with `tests/golden/`. `--update` accepts a change; `--png` writes images to review. |
| `py -3 scripts/metrics.py` | Measures speed, layout redraws, audit errors and truncated text. It writes `bench/metrics/latest.md`; `--compare bench/metrics/baseline.json` shows what moved. |
| `py -3 tests/fuzz/run.py` | Renders seeded random flowcharts and architecture diagrams, and counts how many fail the audit. |
| `py -3 scripts/counts.py --md` | Counts what the redesign removes: one-off chart renderers, truncating calls, inline font settings. |

The redesign these support is described in [docs/DESIGN.md](docs/DESIGN.md), and its phases are in [docs/PLAN.md](docs/PLAN.md).

## License

[MIT](LICENSE)

<!-- mcp-name: io.github.lucas19919/diagonaldiagrams -->


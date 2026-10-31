# Architecture

How diagonaldiagrams turns a spec into a checked figure, and where each part lives. For using it,
read the [README](../README.md); for agents, [llms.txt](../llms.txt).

## The pipeline

```
input ──► scene ──► styles ──► layout ──► routes ──► paint ──► audit ──► SVG + verdict
JSON,     what it   who wins   where      arrows,    a list    what an
Mermaid,  shows     the        boxes go   ports,     of items  agent
CSV                 cascade               labels               can't see
```

Each stage takes the last one's output and returns its own. Nothing is drawn twice: the layout
is correct by construction, and the audit is a safety net, not a repair loop.

1. **Input.** `inputs/v1.py` reads the JSON specs, `mermaid.py` reads Mermaid flowchart,
   sequenceDiagram and erDiagram, `plots.py` and `charts/` read CSV. Everything becomes a
   **scene** (`scene/`): figure, nodes, edges, groups, constraints, annotations. Ids come from
   content (`scene/ids.py`), so an element keeps its id across edits and renders.
2. **Styles.** `style/` is a small CSS: tokens and themes (`tokens.py`, `themes/*.json`), values
   (`parse.py`), selectors with CSS specificity (`select.py`), the cascade (`cascade.py`), and
   data encodings (`encode.py`). `styler.py` computes each element's look once per render. The
   presets in `style/presets/` give flow, arch, seq and schema their default look.
3. **Layout.** `layout/layered.py` is a Sugiyama layout, shared by flow, arch and schema
   (schema runs it left to right):
   - `rank.py`: break cycles, then layers by longest path, compacted by network simplex;
   - `order.py`: barycenter sweeps and transposition, with groups kept whole;
   - `bk.py`: Brandes–Köpf coordinates, plus a straight main path (flow) and centered callers (arch);
   - `channels.py`: one track per sideways run of an arrow, so two arrows never share a line;
   - `wrap.py`: a tall figure folds into columns near the target aspect;
   - `rows.py` and `--fit`: a layer too wide for a column is dealt into rows;
   - `room.py`: an arrow label with no clear spot gets a strip of room.
   `layout/sequence.py` places actors and messages.
4. **Routes and labels.** `route/labels.py` places each arrow label beside the segment it names.
5. **Paint.** `paint.py` turns the layout into a **display list** (`displaylist.py`): flat,
   z-ordered items, each tagged with its owner and role. One place writes SVG text. A 3D figure
   (`iso.py`) gives its faces 3D corners; the projection stage flattens them and paints them back to
   front, ordering whole solids by the axis that keeps them apart.
6. **Audit.** `audit/` checks the finished drawing for what an agent can't see in its own
   output: text on text, arrows through boxes, text that spills, low contrast, tiny text. It reads
   the display list in memory, or any SVG from disk (`audit/svg_import.py`). A 3D figure's faces
   carry their solid (`data-solid`, `data-box3`), so it also reads depth: text hidden behind a nearer
   face, text off the face it stands on, arrows behind or across solids, solids that run into each other.
7. **Verdict.** `cli.py` prints one JSON line: `ok`, errors with a `fix` each, warnings, and the
   layout outline (`outline.py`): rows of boxes, frames and their members, a sequence's messages.
   An agent checks the structure from that instead of a screenshot.

## Outputs

- **SVG** and a self-contained **HTML page** (`_output.py`), and a **receipt** (`*.graph.json`)
  that records how to draw the figure again.
- **export** (`export.py`) redraws from the receipt as PNG or PDF (cairosvg, or headless
  Edge or Chrome), SVG, draw.io or Excalidraw.
- **story** (`story.py`, `web/story.js`): one figure as several views (focus, dim, highlight,
  reveal) in one page. A view's `motion` (`motion.py`, `web/motion.js`) traces a path or runs dots
  along arrows; `--svg` writes an animated SVG, `--gif` and `--video` film it with ffmpeg.
- **apply** (`apply.py`, `scene/patch.py`) writes a patch into a spec; **diff** (`diff.py`) says
  what changed between two drawings.
- **MCP** (`mcp.py`): the same commands as tools over stdio, in one process.

## Package map

| Path | What it holds |
| --- | --- |
| `cli.py`, `api.py`, `mcp.py` | the command line, the Python API, the MCP server |
| `diagrams.py` | flow, arch, seq and schema over the layout kernels |
| `iso.py` | the 3D toolkit (an isometric projection that orders whole solids) and the `iso` layer stack |
| `plots.py`, `charts/`, `geo.py` | bar, line, scatter, the `chart <kind>` figures, maps |
| `scene/`, `inputs/`, `mermaid.py` | the scene model and the formats that compile to it |
| `style/`, `text/`, `deco.py` | styles, text layout and fonts, borders and decorations |
| `layout/`, `route/` | where things go, and where labels go |
| `paint.py`, `_draw.py`, `displaylist.py` | painting and the display list |
| `audit/`, `outline.py`, `validate.py` | checks, the outline, spec validation |
| `export.py`, `story.py`, `motion.py`, `web/` | other outputs and the page scripts |
| `describe.py` | `describe <type>`: the contract for every figure type |

The package uses the standard library only. Optional extras: PyYAML for YAML specs, cairosvg for
PNG and PDF, ffmpeg on the PATH for GIF and video.

## Tests

```
python -m unittest discover tests/unit      # unit tests
python -m unittest discover tests/style     # seven style demos, a stylesheet each
python tests_smoke.py                        # the command-line contract (DD_ENTRY=module or installed too)
python scripts/golden.py                     # 115 reference figures, byte for byte
python scripts/golden.py --determinism       # the same bytes across hash seeds
python scripts/scene_roundtrip.py            # v1 spec -> scene -> v1 spec draws the same bytes
python tests/fuzz/run.py --n 200 --seed 5000 --strict   # random scenes must pass the audit
```

CI runs all of these on Linux and Windows, Python 3.11 to 3.13, plus the installed wheel and the
browser playground (Pyodide). `golden.py --update --only NAME` records an intended change; review
the picture first.

## Benchmarks

`bench/` holds the comparisons the README reports, with the scripts to rerun them:
`bench/speed/` (render time per call), `bench/tokens/` (an agent's tokens per figure) and
`bench/quality/` (blind pairwise judging against Pele and Mermaid).

# diagonaldiagrams 2: plan

Status: proposal, 2026-10-12. The architecture is in [DESIGN.md](DESIGN.md); this file is the order of work.

## How to read this

- **Phases.** There are fourteen phases.
  - P0–P8 build the engine.
  - P9–P11 build the post-legacy layer: pages and stories, live documents and round-trip editing, and the bridge from legacy formats.
  - P12–P13 add industry packs, scale and localization.

  Each phase ships on its own and leaves every existing command working.
- **Tasks.** Each task has an id (`P3.4`), a size and an exit check. Sizes are relative:
  - **S** = up to a day;
  - **M** = a few days;
  - **L** = one to two weeks of focused work.
- **Exit criteria.** A phase is done when its exit criteria hold in CI, not when its tasks are ticked.
- **Deletion.** Every port deletes the code it replaces in the same phase. Nothing old is left running beside its replacement, except the `--layout-engine v1` fallback, which lives from P4 to P8.

```
P0 baseline ─► P1 package ─► P1b fixes ─► P2 core seams ─┬─► P3 style + text ─┐
                                                          └─► P4 layout + route ┴─► P5 toolkits ─┬─► P6 charts ──────────┐
                                                                                                 ├─► P9 pages + stories ─┼─► P8 long tail + quality ─► P10 live + round-trip
                                                                                                 └─► P7 3D ──────────────┘                              P11 legacy bridge
                                                                                                                                                         P12 packs, P13 scale + i18n
```

- P3 and P4 can run in parallel once P2 lands.
- P6, P7 and P9 can run in parallel once P5 lands. P9 comes first, because it matters most to the post-legacy goal. P7 stays the modularity test.
- P10–P13 build on the finished engine and can run in any order.

## Releases

| Version | Contains | Headline |
| --- | --- | --- |
| 0.6.0 | P0, P1, P1b | A package; each call about 3× faster (0.5 s → under 0.2 s); known bugs fixed |
| 0.7.0 | P2, P3 | Scenes, the display list, stylesheets, real fonts, per-side borders |
| 0.8.0 | P4 | New layered layout and router; large graphs wrap; no repair loops |
| 0.9.0 | P5, P6 | Toolkits, `defs`, charts grammar, Vega-Lite input |
| 1.0.0 | P7, P8, P9 | 3D, every diagram type as a preset, quality benchmark, pages and stories |
| 1.x | P10, P11 | Live data, round-trip editing, semantic diff, legacy import |
| 2.0.0 | P12, P13 | Industry packs and notations; scale and localization; the post-legacy release |

Every release follows PUBLISHING.md. The version lives in `diagonaldiagrams/__init__.py` from P1 on, and must match `.claude-plugin/plugin.json` and `server.json` (two places).

## Scoreboard

These numbers are tracked from P0 on and updated at the end of every phase in `bench/metrics/` (`baseline.md`, then one file per phase). The baseline column is what was measured on 2026-10-12; the latest column says which phase changed it. Empty means unchanged.

| Metric | Baseline | Latest | Target | Expected to move in |
| --- | --- | --- | --- | --- |
| CLI call, end to end (render `flow_decision.json`) | 0.52 s via `graph.py`, which recompiles every call; 0.16 s importing from bytecode; Python itself starts in 0.04 s | after P2: 157 ms from bytecode, 234 ms recompiling (P1: 148–164 / 215–222). Dropping `dataclasses` took 25 ms back out of what P2's new modules added | ≤ 150 ms | P1, P2 |
| 40-step flow render (`gen-flow-40`) | 3.5 s, 225 layout redraws | after P2: 3.8 s, 225 redraws. Each draft is now audited in memory, but the more thorough audit (B12) costs about 1 ms more per draft; P1b's tree measured side by side is 10–20% faster. P2's 1 s goal moves to P4 | ≤ 100 ms, 0 redraws | P2, P4 |
| 20-step flow render (`gen-flow-20`) | 0.56 s, 89 redraws | after P2: 0.66 s, 89 redraws | ≤ 50 ms | P4 |
| 40-step flow canvas | 1180 × 3952, aspect 0.30 (a tall strip) |  | within 25% of the target aspect | P4 |
| MCP tool call | a subprocess per call that recompiles the script (about 0.4–0.5 s) | after P2: in-process; a warm render call takes 7 ms (bar) to 34 ms (arch with its repair loop), validation and audit included | ≤ 100 ms in-process (met) | P2 |
| Largest module | 10,012 lines | after P1: 2,800 (`charts/kinds.py`) | ≤ 800 lines | P1, P8 |
| `_c_*` renderers | 66 |  | 0 | P6, P8 |
| Truncation call sites (`_short`, `_wrap`) | 69 |  | 0 | P3, P6, P8 |
| Inline font settings in drawing code (`font-size=`/`font-family=` occurrences) | 342 | after P2: 310 | 0 | P3, P6, P8 |
| `SystemExit` / `sys.exit` inside engine code | 85 | after P2: 0 outside the CLI (met) | 0 outside the CLI | P2 |
| Hidden side channels (function attributes) | 4 | after P1: 0 | 0 | P1 |
| Styling surface | 9 colors + 3 corner styles |  | the property set in DESIGN 5.4 | P3 |
| Fuzz scenes failing the audit (`tests/fuzz/run.py`, 200 scenes) | 149 of 200 (74.5%). Every arch scene over 20 nodes and every flow over 40 fails; flow 5–10 nodes fails 12%. Slowest scene 61 s. |  | 0 of 1,000 | P4 |
| Golden corpus figures failing the audit | 1 of 113 drawn (`case-swim-review`, kept on purpose) | after P2: 2. The B12 audit now sees an arrow through a circle in `case-state-order`, which was always there | 0, once the swim and state presets land | P8 |
| Truncated texts in the golden corpus | 4 in 2 figures |  | 0 | P3 |
| Known bugs (table below) | 24 | after P3.1: 9 open | 0 | P1b–P8 |
| Quality win rate vs baseline (blind pairwise) | — |  | ≥ 80% | P8 |
| Layout stability: mean node movement after a one-node edit | not measured |  | ≤ 10% of the canvas diagonal | P4 |
| Human edits that survive regeneration | none survive (edits are pixels) | after P2: an edit expressed as a patch (`apply`) is written into the spec, or reported as a conflict. The edit UI that produces patches is P10 | 100% or a reported conflict | P10 |
| Tokens and minutes for an agent to produce a 10-view story from a brief | not possible |  | measured at P9, then reduced | P9, P10 |
| Legacy import fidelity (PPTX/VSDX shapes, connectors and text kept) | none |  | ≥ 95% of elements on the import corpus | P11 |

## Decisions needed before a phase starts

From DESIGN section 19. The recommended answer is the default if nobody decides.

| Question | Needed before |  | Default |
| --- | --- |  | --- |
| Python floor 3.11, or 3.10 with a JSON config | P1 (pyproject) | 3.11 |
| Release path: incremental 0.6 → 1.0, or one 2.0 | the P1 release | Incremental |
| Default font: measured system stack, or Inter with embedding | P3 | Measured system stack |
| Metric tables from open fonts only | P3 | Yes |
| Drop any chart kinds instead of porting | P6 | Drop none; `terrain` and `print` keep refusing |
| three.js from a CDN or inlined | P7 | CDN, pinned version |
| Where stories live: HTML files only, or also published pages on a host | P9 | HTML file first; host publishing as an output toolkit |
| Flat PPTX export, or PDF only for legacy recipients | P11 | PDF only, and add flat PPTX if users ask |
| Pages and stories (P9) before 3D (P7) | after P5 | Yes: P9 first, P7 in parallel when there is capacity |

---

## P0. Baseline and safety net

**Goal:** before any code moves, record what today's engine produces and how fast, so every later change is checked against it.

**Status (2026-10-12):**
- Built: the golden corpus, metrics, fuzz harness, counts and the CI workflow.
- Baseline recorded in `bench/metrics/baseline.md`.
- The CI workflow has not run yet; it needs a push. Until then, CI is verified only locally: `tests_smoke.py` passes (208/208), golden files match, and output is identical across hash seeds.

| Task | Size | Work |
| --- | --- | --- |
| P0.1 Golden corpus | M | `scripts/golden.py --check \| --update \| --png \| --determinism`. The corpus (`tests/golden/corpus.json`, written once by `tests/golden/make_inputs.py`) holds 115 figures:<ul><li>every renderable file in `examples/`, with the flags the tests use;</li><li>the site's gallery and benchmark figures;</li><li>one figure per chart kind, from the `tests_smoke.py` fixtures;</li><li>generated flows at 5, 11, 20 and 40 steps;</li><li>known-bad cases (invalid specs, figures the audit rejects).</li></ul>For each, `tests/golden/<name>.svg` and `<name>.json`: argv, exit code, verdict with its `layout` outline, HTML hash, and receipt. `--check` compares bytes. `--png` rasterizes to `bench/golden-png/` (not committed). `--determinism` renders under two hash seeds and compares. |
| P0.2 Metrics | M | `scripts/metrics.py` records, per golden figure:<ul><li>cold CLI time, both compiled and not;</li><li>in-process render and audit time;</li><li>canvas size and aspect;</li><li>audit issues by code;</li><li>truncations (texts ending in "…" or "...");</li><li>`crossings`, `wire`, and redraw count.</li></ul>Writes `bench/metrics/<date>.json` and a Markdown summary. Commits `bench/metrics/baseline.json`. |
| P0.3 Fuzz harness | M | `tests/fuzz/gen.py` makes seeded random v1 flow and arch specs: 5–60 nodes, groups, lanes, back edges, long names, every shape. It records the audit failure rate per size. The baseline goes in the metrics file. |
| P0.4 CI | S | GitHub Actions (none exists today): `tests_smoke.py` on ubuntu and windows × Python 3.11, 3.12 and 3.13; the golden check on ubuntu 3.12; metrics uploaded as an artifact. |
| P0.5 Static counts | S | `scripts/counts.py` counts `_c_*` renderers, truncation calls, inline font literals, function-attribute side channels, and the largest module's lines. Its output feeds the scoreboard. |

**Exit:**
- CI is green.
- The baseline metrics, golden files and counts are committed.
- The fuzz failure rate is known.

---

## P1. Package split, no behavior change → 0.6.0

**Goal:** the same engine as a package. Output stays byte-identical, each call gets about 3× faster (0.52 s → under 0.2 s for a typical render), and the hidden contracts are made explicit.

**Status (2026-10-13):** done on branch `p1-package`.

Exit criteria:
- **Golden files:** all 115 byte-identical.
- **Smoke tests:** pass through the shim (208/208), `python -m diagonaldiagrams`, and an installed wheel.
- **Playground:** verified in a real browser; three examples render from the wheel and pass their check. The Pyodide CI job is written but hasn't run, since CI needs a push.
- **Speed:** a flow render takes 148–164 ms with bytecode cached and 215–222 ms without.
- **Size:** the largest module is 2,800 lines; side channels are at 0.

Deviations from the tasks below:
- **`LAND_B64` stays in `geo.py`.** Compiling that 17 KB line costs about 1% of the module, so moving it gained nothing.
- **PyYAML is still imported on every call** (about 19 ms). It could be made lazy later.
- **Monitor's structured fix is `remediation_argv`,** a CLI argument list, rather than `remediation: {"cmd": ...}`.
- **The playground uses Pyodide's `unpackArchive`** instead of `micropip`, so it fetches nothing extra.

### P1.1 Mechanical split (L)

Write `scripts/split.py`, which uses `ast` to move top-level definitions by name into modules. It works out each module's imports from the free names in its functions. The split can then be rerun, reviewed, and repeated on a rebase instead of cut and pasted by hand.

The interim module map follows today's areas. The final layout in DESIGN section 15 arrives over P2–P5. Line numbers are approximate.

| Module | From `graph.py` |
| --- | --- |
| `_theme.py` | 19–111: themes, palettes, `_humanize`, `_with_unit` |
| `_text.py` | `_wrap`, `render_pincallout`, `render_noterail`, `_wrap_px`, `_box_lines`, `_box_h`, `_text_w`, `_NARROW`/`_WIDE` |
| `_html.py` | `HTML_SHELL`, `esc`, `figure_heading`, `write_out`, `save_receipt`, `_receipt_inputs` |
| `mermaid.py` | 256–647, including `load_spec` |
| `_draw.py` | 649–1289: markers, elbows, ticks, bar paths, node geometry, ports, `route_edge`, groups and frames, boxes, `ICONS`, diamond, labels, `nice_ticks`, formatters |
| `diagrams.py` | 1290–1983: `auto_ranks`, flow, arch, `_layout_cost`, `_gap_tracks`, seq, schema |
| `plots.py` | 1984–2553: scatter, bar, line, `_lttb` |
| `geo.py` | 2554–2866, with `LAND_B64` moved to `data/land.b64` and loaded on first use |
| `charts/__init__.py` | 2867–3630 and 7312–7505: chart metadata, shared helpers, `render_chart`, `_validate_chart` |
| `charts/kinds.py` | 3631–6417: the 66 `_c_*` renderers |
| `mathplot.py` | 6418–7332 |
| `export.py` | 7563–7855: raster, `_svg_model`, draw.io, Excalidraw, `do_export` |
| `describe.py` | `DESCRIBE`, `do_describe` |
| `validate.py` | 8017–8321: `do_validate`, `_validate_*`, `_structure_ok`, `do_infer` |
| `audit.py` | 8322–8857: `_affine`, `_xbox`, `_svg_geometry`, `do_audit`, `_audit_file` |
| `doc.py`, `extract.py` | 8858–9210 |
| `drift.py` | 9211–9390: `do_monitor`, `do_sync`, `_merge_specs`, `_spec_diff` |
| `mcp.py` | 9391–9547 |
| `cli.py` | 9548–10011: `main`, `cli`, `_report`, `_prevalidate`, `_outline`, `_finish`, flag helpers |

Import layers, lowest first: `_theme`, `_text` → `_draw` → `audit` → `diagrams`, `plots`, `geo`, `charts`, `mathplot` → `export`, `validate`, `describe`, `doc`, `extract` → `drift`, `mcp` → `cli`. A cycle is a split bug.

### P1.2 to P1.12

| Task | Size | Work |
| --- | --- | --- |
| P1.2 Shim | S | Repo-root `graph.py` becomes `from diagonaldiagrams.cli import cli` + `__version__` + `if __name__ == "__main__": cli()`. It is not packaged. |
| P1.3 Self-invocation | S | MCP, monitor and sync stop running `[sys.executable, __file__]` and run `[sys.executable, "-m", "diagonaldiagrams", ...]`. Still a subprocess in this phase; P2.11 moves MCP in-process. |
| P1.4 Sync contract | S | Monitor adds a structured `remediation: {"cmd": [...]}` next to `remediation_cmd`. Sync reads the structured form first and still accepts both `py graph.py extract` and `diagonaldiagrams extract` strings. |
| P1.5 Lazy imports | M | `cli.main` imports only the module for the requested command. Chart kinds, math, geo (with its coastline), extract, export and MCP load on first use. |
| P1.6 Lazy argparse | S | Build only the subparser for `argv[1]`; `--help` and unknown commands build them all. Under the profiler, building all of them took about 60 ms. |
| P1.7 Side channels | S | `route_edge` returns its points; `_render_flow_once` returns positions; `_raster_svg` returns `(ok, why)`; `_land_rings` uses `functools.cache`. |
| P1.8 Packaging | S | <ul><li>`pyproject.toml`: `packages` instead of `py-modules = ["graph"]`, package data for `data/`, entry point `diagonaldiagrams.cli:cli`, version from `diagonaldiagrams.__version__`, `requires-python >= 3.11`.</li><li>The wheel no longer installs a top-level module named `graph`.</li><li>Update PUBLISHING.md.</li></ul> |
| P1.9 Site | M | <ul><li>`build_site.py` builds the wheel into `docs/wheels/` and writes `docs/wheels/latest.json`. `.gitignore` ignores every `wheels/` folder, so add `!docs/wheels/`.</li><li>`docs/index.html` loads `micropip`, installs that wheel and calls `diagonaldiagrams.cli.cli()`.</li><li>Delete `docs/graph.py` and the copy step.</li></ul> |
| P1.10 Scripts and agent docs | S | <ul><li>Update `scripts/check_drift.py`, `.agents/skills/graph-engine/scripts/*.py` and the install skill.</li><li>Update root `SKILL.md`, the graph-engine skill and its `references/schemas.md` (regenerated from `describe`), and README.</li><li>Prefer `diagonaldiagrams …` and `python -m diagonaldiagrams …`. `py graph.py` keeps working.</li><li>Messages that say `py graph.py` say `diagonaldiagrams`.</li></ul> |
| P1.11 Tests | S | `tests_smoke.py` runs twice in CI: against the shim and against `python -m diagonaldiagrams`. Add a Pyodide smoke test that installs the wheel in headless Node and renders one figure. |
| P1.12 Compile note | S | README and the install skill note that `PYTHONDONTWRITEBYTECODE=1` disables the bytecode cache for checkouts, and give `python -m compileall diagonaldiagrams` as the fix. Installed wheels are precompiled by pip. |

**Exit:**
- Golden SVGs are byte-identical.
- `tests_smoke.py` passes against both entry points.
- Pyodide smoke passes.
- On the baseline machine, `py graph.py flow examples/flow_decision.json` (now the shim) renders in ≤ 200 ms with bytecode cached (today 0.52 s), measured by `scripts/metrics.py`.
- With `PYTHONDONTWRITEBYTECODE=1` and no bytecode, it is no slower than today's 0.52 s. Importing an uncached module compiles more slowly than running a script, so this needs small modules and lazy imports (DESIGN 16).
- No module is over 3,000 lines. `charts/kinds.py`, at about 2,800, is the largest until P6 empties it.
- Side channels: 0.

## P1b. Known-bug fixes

**Goal:** fix the bugs the inventory found that don't need the new core. Each fix is its own PR with its golden diffs reviewed.

**Status (2026-10-13):** done on branch `p1b-bugs`. All nine fixes landed in one commit; there were no golden diffs to review per fix.
- Each bug has a check in `tests_smoke.py` (`known_bugs()`). All ten checks (B2 has two) failed before the fixes and pass after them.
- All 115 golden figures are unchanged. B6 keeps the old 260 px minimum row height, so only schemas whose tables already overlapped move.
- B2 also adds `--size`, `--label`, `--parent`, `--val`, `--a`, `--b`, `--lo` and `--hi` to `validate`, so an agent can check what it will render.

| # | Bug | Fix |
| --- | --- | --- |
| B1 | A seq actor without `name` passes validation, then crashes the render | `name` defaults to `id` |
| B2 | `_validate_chart` passes only `--x/--y/--group` to its column check, so a valid `--size`, `--val`, `--label`, `--parent`, `--a`, `--b`, `--lo` or `--hi` blocks the render | Pass every role flag |
| B3 | The unlabeled-diamond warning repeats once per source node | Warn once per diamond |
| B4 | `describe` lists budgets nothing enforces (arch layers 6, schema relations 10, line 200 points per series) | Make `describe` match the code |
| B5 | Help says the positional spec may be inline text, but it is always read as a path | Fix the help; `-s` is the inline form |
| B6 | Schema rows sit a fixed 320 px apart, so tables with more than about 11 columns overlap | Row pitch = tallest table in the row + gap |
| B7 | Mermaid ER key detection is a substring match over the whole line, so comments can set `PK` | Match key tokens only |
| B8 | Mermaid drops unknown `fa:` icons silently | Warning with the known names |
| B9 | MCP `export` can't reach `drawio` or `excalidraw` | Add them to the enum |

**Exit:** each bug has a test that fails before its fix and passes after it.

The remaining bugs are fixed where their code is replaced:

| # | Bug | Fixed in |
| --- | --- | --- |
| B10 | `_layout_cost` counts an SVG parse error as zero problems | P2.6, fixed: the parse error propagates |
| B11 | Receipts drop `--caption`, `--note`, `--theme-file` overrides and `--no-audit`, so export loses them | P2.10, fixed |
| B12 | Audit blind spots: circles, ellipses and closed paths aren't obstacles; curves become chords; CSS or parent markers missed; skew ignored; 4-point polygons taken for diamonds; vertical spill unchecked | P2.5, fixed except closed paths (DESIGN 9.6) |
| B13 | `_c_*` boxes carry no `data-node`, so no outline, `intrude` or export | P2.8, fixed for dag, integration and swim (the charts that draw boxes and links) |
| B14 | The theme `_name` is "custom" only through the API; the default `THEME` has no name | P3.1, fixed |
| B15 | `--corners` is accepted but unused by line and scatter | P3.1, fixed: their note callouts take the corner radius; corners become a cascade rule in P3.3 |
| B16 | `_paint_boxes` and `_legend` truncate names at 16–26 characters | P3.6, P6.2 |
| B17 | `--figure` and `--caption` are stored and never drawn | P3.10 (diagrams), P6.6 (charts) |
| B18 | Arch width includes the note rail, so nodes can sit under it | P4.6 |
| B19 | Arch edges that go up pass straight through the rows between | P4.3 |
| B20 | Flow groups don't affect layout, so non-members land inside frames | P4.2 |
| B21 | `_gap_tracks` buckets by port y, so boxes of different heights can share a track | P4.3 |
| B22 | Routing ignores group frames | P4.3 |
| B23 | Flow back edges: the ±20 nudge has no effect on the same-side branch | P4.3 |
| B24 | `_c_swim` ports float off its 140×48 boxes because `_node_box` assumes 160×56 | P8.1 |

---

## P2. Core seams: scene, geometry, display list, output, audit → 0.7.0 (with P3)

**Goal:** the internal model from DESIGN 3, 4, 8, 9 and 10 exists. Flow, arch, seq and schema paint through it, and the audit no longer re-parses SVG. Layout algorithms are unchanged in this phase.

**Status (2026-10-13):** done on branch `p2-core`, with one exit criterion moved (the 40-step flow, below). Metrics in `bench/metrics/p2.md`.
- **Done:** P2.1, P2.2, P2.4, P2.5, P2.6, P2.8, P2.9, P2.11, P2.3, P2.15, P2.16, P2.10, P2.13, P2.14, P2.7, P2.18, P2.12 and P2.17: every P2 task.
- **P2.3:** scene JSON reads into `scene/model.py` (DESIGN 4.8). A v2 scene file (`"version": 2`) with preset `flow`, `arch`, `seq` or `schema` draws through today's renderers. This works from the command line, the API (`render(kind, scene=...)`) and MCP (`scene`). The v1 → scene → v1 round trip draws the same bytes for all 29 diagram inputs in the golden corpus and for 60 generated specs.
- **P2.15:** edges, messages and relations are named by content (`from->to:label`, then `#2`) in the scene, the SVG (`data-id`), `--outline` and the draw.io and Excalidraw cells. `tests/unit/test_identity.py` edits a spec and checks that what it didn't touch keeps its ids. 36 goldens changed by the new attributes only. Layout is not incremental yet; that is P4.
- **P2.16:** `diagonaldiagrams apply SPEC PATCH [-o OUT]` writes a patch's operations into a v1 spec or a scene (DESIGN 21.3). Each conflict is reported with its path and a fix, and the rest still apply. Unit tests cover every operation and conflict; smoke tests cover the command.
- **P2.10:** receipts gain `"receipt": 2`, theme overrides, caption, notes, `audit: false` and, for diagrams, the drawn scene, beside the v1 fields (DESIGN 10.2). Export now keeps `--theme-file` and `--note` (B11; both were lost before) and redraws a diagram after its spec file is gone. No SVG or verdict changed; 113 golden receipts gained the new fields only.
- **P2.13:** `tests/unit/test_imports.py` walks every import in the package, including imports inside functions and `lazy()` ones. It fails if the scene, geometry, text, theme or display-list modules can reach the CLI, MCP, the API or a writer, and it prints the chain.
- **P2.14:** the 3D hooks (DESIGN 13): `z` in pins, `pts3d` on painted elements, the projection stage, and `depth` on display-list items. A unit test builds a projection and a solid outside the core. Dropping `dataclasses` from the paint and display-list modules cut the renderers' import from 59 to 35 ms compiled (median of 9), about 25 ms off every CLI render.
- **P2.7:** the repair loops audit each draft from the drawing's own element tree (`Drawing.etree()`), and only the winning draft is written as SVG. Every one of the 349 drafts the corpus produces gets the same issues and stats as from its parsed SVG.
  - The audit also got faster with identical results (golden corpus and 40 fuzz figures, 79 issues):
    - inline-style regexes run only on elements with a `style` attribute;
    - shared runs are paired through a sort instead of all pairs;
    - text widths are cached.
  - A 40-step flow renders in 4.9 s in-process, down from 6.3–7.0 s.
  - This machine currently runs about 2× slower than when P1 was measured: the P1b tree itself renders the corpus in 10.3 s today, against 5.3 s then.
- **P2.18:** node `content.svg` passes through an allowlist sanitizer (DESIGN 4.5). `tests/unit/test_sanitize.py` tries scripts, handlers, outside references, `javascript:`/`data:` URLs, CSS `expression` and `@import`, entities and oversize input.
- **P2.12:** `registry.py` holds three name-to-function tables: `paint.SHAPES` (rect, oval, diamond, dot; flow and arch look shapes up there), `audit.checks.CHECKS` (in run order, with the codes each reports) and `export.OUTPUTS` (svg, drawio, excalidraw, png, pdf). `tests/unit/test_registry.py` registers a hexagon from outside the core, and flow draws it.
- **P2.17:** the four diagram types are WAI-ARIA graphics documents with named, navigable parts, and edges carry their attachment (DESIGN 22.3). 32 goldens change by the new attributes only.

Exit criteria:
- **Pixels:** every SVG change in P2 was reviewed. Each was either semantically equal (`golden.py --semantic`) or added attributes only, so nothing moved on screen.
- **Audit parity:** clean. The split audit matched the old one issue for issue except the B12 fixes. In-memory drafts match parsed ones on 349 drafts.
- **`tests_smoke.py`:** passes (238 checks), along with 60 unit tests.
- **40-step flow ≤ 1 s:** not met. It takes 3.8 s; the target moves to P4 (see below).
- **MCP render ≤ 150 ms:** met, at 7–34 ms warm.

Deviations:
- `geom.py`, `displaylist.py` and `paint.py` are single modules rather than the `geom/`, `paint/` and `emit/` packages. Geometry works on tuples, not `Point`/`Box`/`Path` classes.
- Per-corner radii and named-side extraction (P2.2) move to P3, where the style system first needs them.
- The SVG writer (P2.4) writes one element per line with numbers to 2 decimals, but no `<g>` per element yet. Owners and roles live on the in-memory elements.
- **Exit criterion not met:** "a 40-step flow in ≤ 1 s with the repair loop still on". The loop draws and audits 225 drafts, and each costs about 20 ms even after the speedups. The target moves to P4, whose layered layout is correct by construction and drops the loop (D6). The loop cannot get 5× cheaper without changing which layout it picks.

| Task | Size | Work |
| --- | --- | --- |
| P2.1 Typed errors | M | <ul><li>`errors.py` with `SpecError(code, msg, fix, at)` and `Issue`.</li><li>Replace every `raise SystemExit(...)` and `sys.exit(...)` in engine code with `SpecError`. Only the CLI exits.</li><li>The verdict JSON shapes and exit codes stay as today (DESIGN 14.1).</li></ul> |
| P2.2 Geometry | M | `geom/`:<ul><li>`Point`, `Box`, and `Path` (M L H V C Q A Z, flattened within a tolerance);</li><li>Liang–Barsky clipping, segment intersection, point in polygon;</li><li>rounded rectangles with per-corner radii;</li><li>named-side extraction.</li></ul>Unit tests per function. |
| P2.3 Scene | M | `scene/model.py` dataclasses and `scene/normalize.py`:<ul><li>aliases: `name`/`label`, `sub`/`subtitle`, `layer`/`rank`;</li><li>both group-membership forms;</li><li>id checks and the container tree.</li></ul>`inputs/v1.py` maps flow, arch, seq and schema per DESIGN 14.6. |
| P2.4 Display list and SVG writer | M | `paint/displaylist.py` and `emit/svg.py`:<ul><li>deterministic numbers (DESIGN 8.4) and one `<defs>`;</li><li>a `<g>` per element with classes and today's `data-*` attributes;</li><li>escaping in one place.</li></ul> |
| P2.5 Audit on the display list | L | <ul><li>Port every check to `audit/checks/` with the same codes and thresholds (DESIGN 9.6), plus the codeless warnings as coded checks.</li><li>`audit/svg_import.py` builds a display list from foreign SVG using today's parser.</li><li>Fix the blind spots (B12).</li><li>**Parity report:** old and new audit over the golden corpus and the foreign-SVG fixtures. Every difference is listed, and each is either fixed or marked intended.</li></ul> |
| P2.6 Paint the four main types | L | <ul><li>Flow, arch, seq and schema return positions from their existing layout code.</li><li>`paint/painter.py` draws them into a display list with the existing shapes (rect, oval, diamond, dot, table) registered in an internal shape registry.</li><li>Their f-string SVG goes away.</li></ul> |
| P2.7 Repair cost from the display list | S | `_layout_cost` reads the display list instead of re-parsing SVG (fixes B10). The repair loops stay until P4. |
| P2.8 Outline v2 | M | <ul><li>`outline.py` builds the `outline` object from the scene and display list.</li><li>`layout` rows are generated from it.</li><li>Chart outlines come from display-list roles.</li><li>`_paint_boxes` gets `data-node` so the `_c_*` diagrams get outlines now (B13).</li></ul> |
| P2.9 Exports from the display list | M | draw.io and Excalidraw models are built from the display list for new renders. `_svg_model` stays as a tolerant fallback for v1 SVGs. |
| P2.10 Receipt v2 | M | Receipts embed the normalized scene and the options listed in B11. `export` reads v1 and v2. |
| P2.11 Python API and in-process MCP | M | <ul><li>`api.render(spec_or_scene, out=None, **options) -> Result`.</li><li>The MCP server calls it in-process, with a hard ceiling on scene size.</li><li>`mcp --isolate` keeps the subprocess path.</li><li>`render` accepts a `scene` object.</li></ul> |
| P2.12 Internal registries | S | Private registries for shapes, checks and outputs. They become the public toolkit API in P5. |
| P2.13 Import rules | S | A test that fails if `scene`, `style`, `text`, `geom` or `layout` import `emit`, `cli` or `mcp`. |
| P2.14 Reserve 3D hooks | S | <ul><li>Positions carry an optional `z`.</li><li>Shapes may return several faces.</li><li>Items carry `depth`.</li><li>The pipeline has an identity projection stage.</li></ul>Nothing uses them yet; P7 must not need core edits. |
| P2.15 Stable identity | M | Element and item ids stay the same across renders (DESIGN D15). Generated ids come from content, never from position or list order. A test re-renders an edited spec and checks that unchanged elements keep their ids. |
| P2.16 Patch format | M | <ul><li>`scene/patch.py` with the operations in DESIGN 21.3: `pin`, `order`, `style`, `text`, `add`, `remove`, `move-to-group`.</li><li>`diagonaldiagrams apply SPEC PATCH`.</li><li>`patch-conflict` issues.</li></ul>The edit UI comes in P10; the format exists now so every later layer speaks it. |
| P2.17 Attachments and accessibility fields | S | Edge items carry `attach` (node and port at each end). Every item carries `a11y` (name, description, reading order). SVG output writes `role` and `aria-*` (DESIGN 22.3). |
| P2.18 Raw SVG content | S | Node `content: {"svg": ...}`, with a sanitizer (no script, event handlers, external references or `foreignObject`) and sanitizer tests. |

**Exit:**
- Flow, arch, seq and schema golden PNGs match within a small pixel-difference threshold. SVG bytes may change, and each change is reviewed.
- The audit parity report is clean.
- `tests_smoke.py` passes.
- A 40-step flow renders in ≤ 1 s, with the repair loop still on.
- An MCP render call takes ≤ 150 ms.

---

## P3. Style system and text → 0.7.0

**Goal:** the agent can set any font, color, border side, corner, shadow or data-driven style through stylesheets and selectors, on every type that paints through the display list.

**Status (2026-10-13):** in progress on branch `p3-style`.
- **P3.1:** `editorial`, `ink` and `print` are token stylesheets in `style/themes/` that extend `core.json` (type sizes, spacing, strokes, palettes). The flat theme dicts the renderers read are built from them, so the goldens are unchanged. `--theme-file` takes v1 keys (`accent_tint` or `accent-tint`) or a stylesheet's `tokens`. B14 and B15 are fixed.
- **P3.2:** `style/parse.py` reads every value form in DESIGN 5.3 (colors, tokens, `var()`, `mix()`, lengths, `border`/`border-<side>`, `border-radius`, `padding`, `box-shadow`, `font`, `linear-gradient`). It also holds the DESIGN 5.4 property table. Unknown properties and values are `bad-style` errors with a did-you-mean.
- **P3.3:** `style/select.py` parses DESIGN 5.2's selectors, with CSS specificity, and matches them against element views. Positions count among siblings of the same type, like `:first-of-type`. `style/cascade.py` resolves sheets in DESIGN 5.1's order:
  - an element's own `style` sits above every sheet except a `policy` sheet;
  - shorthands expand and text properties inherit;
  - em lengths read the element's own font size;
  - every selector and declaration is checked when the cascade is built, and an error names its sheet and rule;
  - results are cached per element.
  `scene_views` builds the views from a scene's group tree. The renderers start reading it in P3.8, which is also where `--corners` becomes a rule.
- **P3.8 (nodes and edges):** flow, arch, seq and schema paint their nodes, tables, edges, messages, relations and edge labels from the cascade.
  - `style/styler.py` builds it from the theme, the `--theme-file` tokens, the preset's stylesheet (`style/presets/*.json`) and the spec's `style`.
  - The preset sheets state today's look as rules: `node:focal`, `edge[proto^=http]` and `edge[async]`. `--corners` becomes the node radius rule.
  - A stroke color outside the four default arrowheads gets a marker of its own.
  - `validate` checks a spec's stylesheets and element styles.
  - Goldens are byte-identical. Still constants: group frames, headings, legend, notes, lifelines and table columns (next).
- **P3.4:** named sides with per-side borders, per-corner radius, gradients, shadows, glow, patterns and opacity, on rect, oval, diamond and table shapes (DESIGN 5.5). Checked by eye in headless renders and by `tests/unit/test_deco.py`. Inset shadows and `sketch` are left for later.
- **P3.10 (part 1):**
  - `--style FILE` (repeatable) and `--font FAMILY` on flow, arch, seq and schema. A bad stylesheet stops with validate's JSON.
  - MCP and API `options.style` takes a stylesheet object or a list; it is written beside the output and passed as `--style`.
  - Receipts keep the stylesheets' content, and export redraws with them.
  - `describe style` is generated from the property table, selector grammar and tokens.
  - Still to do: diagrams drawing `--caption` and `--figure` (B17).
- **P3.7:** `style/encode.py` provides linear, sequential and categorical scales.
  - Any style value can be `{field, scale}`. The domain comes from the elements' data, and an element without the field gets a neutral value.
  - Legends come from what is drawn: the preset's sentence keeps only phrases whose parts appear, and it names colors as drawn. The print theme now says "black = highlighted". 7 goldens changed by their legend text.
  - Swatch rows follow for every scale used and every rule with a `legend`, and the canvas grows only when there are any.
  - A preset's default label color stays readable on a data-driven or dark fill: it switches to ink or paper below 4.5:1. A color a stylesheet chose is never changed; the contrast check (P3.9) judges it.

| Task | Size | Work |
| --- | --- | --- |
| P3.1 Tokens and themes | M | <ul><li>`style/tokens.py`, and `editorial.json`, `ink.json` and `print.json` as stylesheets.</li><li>`--theme` and `--theme-file` map onto them, accepting `accent_tint` and `accent-tint`.</li><li>Corners become a rule (B15); theme names are always set (B14).</li></ul> |
| P3.2 Values | M | `style/parse.py`:<ul><li>colors: hex, rgb, hsl, CSS names, tokens, `var()`, `mix()`;</li><li>lengths;</li><li>shorthands: `border`, `border-<side>`, `border-radius`, `padding`, `box-shadow`, `font`;</li><li>`linear-gradient`.</li></ul>Errors carry a did-you-mean fix. |
| P3.3 Selectors and cascade | L | `style/select.py` and `style/cascade.py`:<ul><li>the selector grammar in DESIGN 5.2, including `^=` and numeric comparisons;</li><li>pseudo-classes and pseudo-elements;</li><li>specificity, and the cascade order in DESIGN 5.1.</li></ul>Computed styles are cached per element. |
| P3.4 Named sides and decorations | L | <ul><li>Every shape exposes named sides.</li><li>`border-<side>` with correct corner handling; per-corner radius.</li><li>`box-shadow`, `glow`, gradients, hatch, dot and grid patterns, dash styles.</li><li>An unknown side is an error that lists the sides the shape has.</li></ul> |
| P3.5 Fonts | L | <ul><li>`text/fonts.py`: TTF, OTF, TTC and WOFF1 reading (DESIGN 6.1), and a system font index cached in the user cache directory.</li><li>`scripts/build_metrics.py` generates `data/metrics/*.json` from the chosen open fonts.</li><li>The system stack is measured as the widest of the bundled metrics.</li><li>`font-fallback` warning; the receipt records the font hash.</li></ul> |
| P3.5b Font embedding | M | `--embed-fonts` and `font-embed: true` embed the whole font file, with a `large-font` warning. Subsetting comes in P8.4. |
| P3.6 Text layout | M | <ul><li>`text/measure.py`: word wrap, boxes that grow, `max-lines`, `overflow` modes, inline markup (`**`, `_`, `` ` ``).</li><li>Remove truncation from the four main types and the shared box painter (B16 for boxes).</li><li>`truncated` check.</li></ul> |
| P3.7 Encodings and legends | M | <ul><li>`style/encode.py` with linear, sequential and categorical scales; the full set comes in P6.1 and shares this code.</li><li>Any style value can be `{field, scale}`.</li><li>Legends come from rules with `legend`, from used scales, and from preset shape meanings when the shape is present.</li></ul> |
| P3.8 Styles replace constants | L | Every fixed size, color, font and stroke in the four main types' painting code reads the computed style. The inline-font count for those modules reaches 0. |
| P3.9 Legibility checks | M | `contrast` (WCAG AA, against the actual background; names the rule), `min-size`, `font-fallback`, `colors`, `legend`. |
| P3.10 Surface | M | <ul><li>CLI: `--style` (repeatable), `--font`, `--embed-fonts`.</li><li>MCP: options pass through, and `render` accepts `style`.</li><li>`describe style` lists properties, selectors and tokens.</li><li>Diagrams draw `--caption` and `--figure` (B17).</li></ul> |
| P3.11 Shaper extension point | M | Text measuring goes through `shaper` (DESIGN 6.1). The built-in shaper covers Latin, Greek, Cyrillic and CJK, plus bidi reordering. `shaping` warning. The HarfBuzz shaper comes in P13. |
| P3.12 Policy layer and config | M | <ul><li>`diagonaldiagrams.toml` (project) and an organization config path.</li><li>The policy stylesheet sits at the top of the cascade; allowed palettes and fonts; `off-brand` check.</li><li>Icon folders; enabled toolkits; defaults.</li><li>Font embedding checks OS/2 `fsType` and refuses restricted fonts with a warning.</li></ul> |

**Exit:** `tests/style/` holds the style demo suite. Every demo renders on flow, arch, seq and schema with no per-type code, and passes the audit:

1. A different font, measured from the file, wraps correctly.
2. A brand stylesheet changes tokens on all four types.
3. `node { border-top: 3px solid accent }` on rect, oval, diamond and table shapes.
4. `node[team=pay] { border-left: 4px solid … }`.
5. `edge.critical` and `edge[from=api]` highlighting.
6. A data-driven fill with its legend.
7. A deliberately low-contrast rule, which the `contrast` check catches and names.

Default-style golden PNGs stay within the threshold.

---

## P4. Layout and routing kernels → 0.8.0

**Goal:** layouts that are right by construction. Large graphs wrap to the target shape, and the repair loops are deleted.

| Task | Size | Work |
| --- | --- | --- |
| P4.1 Protocol and nesting | M | `layout/base.py`: bottom-up measure and top-down place over the container tree. Groups with their own layouts; node `content`. |
| P4.2 Layered | L | `layout/layered.py`:<ul><li>greedy feedback-arc-set cycle removal, keeping "a loop's start stays on top";</li><li>longest-path layers compacted by network simplex;</li><li>dummy nodes;</li><li>median/barycenter sweeps plus transposition, best of N passes;</li><li>Brandes–Köpf coordinates;</li><li>TB, LR, BT and RL; `lanes`; compound groups (B20); constraints (DESIGN 4.6);</li><li>`wrap` to the target aspect.</li></ul> |
| P4.3 Router | L | `route/`:<ul><li>ports and slots, keeping today's port rules as defaults: s→n between adjacent rows, trunks, in/out separation, diamond slots;</li><li>an orthogonal visibility graph with A* (length, bends, crossings);</li><li>channel nudging, replacing `_gap_tracks` (B21);</li><li>back edges around the outside (B19, B23);</li><li>self-loops;</li><li>group frames as routing obstacles (B22).</li></ul>Plus `straight`, `spline` and `bundled`. |
| P4.4 Labels | M | `route/labels.py`: today's candidate search (default spot, flips, 0.3/0.5/0.7 along each segment) with arch's soft obstacles, applied to every edge; paper-colored pills. |
| P4.5 Other kernels | L | `stack`, `grid`, `tree` (Buchheim), `radial`, `force` (seeded, with overlap removal), `manual`, `sequence` (lifelines, activations, `loop`/`alt`/`opt` fragments), `table`, `timeaxis`. |
| P4.6 Switch the presets | M | <ul><li>Flow, arch, seq and schema use the new kernels.</li><li>Delete `render_flow`, `render_arch` and `render_schema`'s repair loops, `_gap_tracks`, `_group_columns` and `auto_ranks`.</li><li>`--layout-engine v1` keeps the old path until P8 (B18 is fixed in the new path).</li></ul> |
| P4.7 Fuzz to zero | L | `tests/fuzz/` grows to 1,000 seeded scenes: 5–200 nodes, nested groups, lanes, constraints, every shape, long labels, back edges, self-loops. Fix until zero audit errors. Runs in CI on a fixed seed set, plus a nightly random set. |
| P4.8 Size targets | S | `size.width` and `size.aspect` drive `wrap` and spacing. Export `--layout` presets set them for every type. |
| P4.9 Incremental layout | L | Layouts accept the previous placement as a hint (read from the receipt), so a small edit moves little: ordering starts from the old order, and coordinates are pulled toward old positions. Tracked by the layout-stability metric. Needed for animated views (P9) and round-trip edits (P10). |
| P4.10 Page model | M | A figure can paginate: split across pages with off-page connectors, poster sizes, and collapse-to-level in HTML (DESIGN 22.2). |
| P4.11 Scale budgets | M | Benchmarks at 1,000 and 10,000 nodes. Layout per group, then compose, for very large graphs. An interface slot for a faster optional backend. |
| P4.12 Feedback interface | M | <ul><li>The verdict gains `metrics` (DESIGN 20.2).</li><li>`--preview png` returns a rendered image path.</li><li>`--candidates N` returns N scored layout variants with their receipts.</li></ul> |

**Exit:**
- Fuzz: 0 of 1,000 scenes with audit errors.
- 40-step flow ≤ 100 ms, within 25% of the target aspect.
- 200-node layered ≤ 1 s.
- Corpus crossings and wire ≤ baseline in total. Each figure that got worse is reviewed and accepted or fixed.
- The gallery is re-rendered and reviewed.
- No repair loop code remains outside the v1 fallback.

---

## P5. Extension system → 0.9.0

**Goal:** everything is a toolkit. A new shape, layout, check or preset needs no core edit, and agents can add shapes and presets as data.

| Task | Size | Work |
| --- | --- | --- |
| P5.1 Toolkit API | L | `toolkit.py`: `Toolkit` and registries for every extension point in DESIGN 11.1, each with an options schema, an example and docs. |
| P5.2 Built-ins as toolkits | M | Move the shapes, layouts, routers, checks and outputs into `toolkits/core`, `flow`, `arch`, `seq` and `schema`. |
| P5.3 `use`, `preset`, `defs` | L | <ul><li>Strict unit-box SVG path parser.</li><li>`defs` shapes with sides, ports and padding.</li><li>Presets with `extends`.</li><li>`defs` icons, markers and scales.</li><li>`--defs FILE`.</li></ul> |
| P5.4 Discovery | M | Lazy built-ins; the `diagonaldiagrams.toolkits` entry-point group; `--toolkit path.py`, which the MCP server honors only when given at start (DESIGN D8). |
| P5.5 Describe and schema | M | `describe` is generated from the registry. `describe <part>`, `describe --schema` (JSON Schema). Did-you-mean on every unknown name. |
| P5.6 Outside toolkit test | M | `tests/toolkits/demo/` lives outside the package. It adds a shape, a layout, a check and a preset, installs through an entry point in a temporary venv, and renders. It must need no edits under `diagonaldiagrams/`. |
| P5.7 Authoring guide | S | `docs/TOOLKITS.md`. |
| P5.8 Agent-written toolkits | M | <ul><li>`diagonaldiagrams toolkit new NAME` scaffolds a toolkit with golden and fuzz tests.</li><li>`diagonaldiagrams toolkit test NAME` runs them.</li><li>Project config enables local toolkits (DESIGN D18).</li><li>Test: an agent session adds a missing layout using only the scaffold and the docs.</li></ul> |

**Exit:**
- The demo toolkit test passes.
- A `defs` shape renders in every layout with ports, named-side borders and audit coverage.
- `describe` covers every registered part.

---

## P6. Charts toolkit → 0.9.x

**Goal:** charts are a grammar, not 30 renderers. Agents can write Vega-Lite.

| Task | Size | Work |
| --- | --- | --- |
| P6.1 Scales and formats | M | Linear, log, sqrt, time, band, point, ordinal, sequential and diverging; `nice_ticks`; formats: SI, units, dates (`Jan`, `Q1 2026`), percentages. |
| P6.2 Guides | M | Axes with titles, gridlines, wrapping legends with no truncation (B16), direct end labels generalized from today's line chart. |
| P6.3 Marks and transforms | L | Marks: point, line, area, bar/rect, arc, text, rule, tick, boxplot, errorbar. Transforms: bin, aggregate, stack, normalize, density, regression, window, fold, filter, calculate. `calculate` and `filter` use the math parser. |
| P6.4 Composition | M | `layer`, `facet`, `concat`; charts as node `content`; sparkline size; dashboard grids. |
| P6.5 Vega-Lite subset | L | `inputs/vegalite.py` covering DESIGN 12. Conformance fixtures in `tests/vegalite/` (example specs with local data). Unsupported features return an error naming the feature. |
| P6.6 Port bar, line, scatter, geo | L | <ul><li>Presets keep every flag.</li><li>Keep LTTB thinning and scatter sampling.</li><li>Export `--layout` works for all charts.</li><li>Draw caption and figure label (B17).</li></ul> |
| P6.7 Port the chart kinds | L | Delete each `_c_*` as it is ported. Kinds by group:<ul><li>**Mark presets:** bubble, beeswarm, step, slope, bump, ridgeline, stack, dumbbell, waterfall, histogram, box, violin, strip, pie, donut, waffle, polar, heatmap, calendar, radar, candle, status, forest, qq, volcano, stream, funnel, combo, quadrant, contour, math.</li><li>**`partition` layout:** treemap, icicle, sunburst.</li><li>**`sankey` layout:** sankey.</li><li>**Geo toolkit:** mercator projection, coastline, choropleth, heatgeo, od, cluster, point.</li></ul> |
| P6.8 Chart checks | S | Tick label overlap, too many series, legend needed, a negative axis on ratio data. |

**Exit:**
- Each ported kind is a preset of about 25 lines or less, with a golden file and an outline.
- The `_c_*` count for chart kinds is 0.
- Vega-Lite conformance passes.
- A chart with 10,000 points renders in ≤ 300 ms.

---

## P7. 3D toolkit → 1.0.0-rc

**Goal:** prove the modularity claim. 3D lands entirely inside `toolkits/threed/`.

| Task | Size | Work |
| --- | --- | --- |
| P7.1 Hooks check | S | Confirm the P2.14 hooks are enough. Any needed core edit is logged as a design bug and fixed in core first, in its own PR. |
| P7.2 Projections | M | Isometric, dimetric, orthographic, perspective (`azimuth`, `elevation`, `distance`, `fov`). |
| P7.3 Solids | L | Cuboid, cylinder, cone, sphere, plate, prism, `extrude` (any 2D or `defs` shape), and surfaces `z = f(x, y)` from the math toolkit. |
| P7.4 Shading | S | Lambert from `light`, mixing toward `shade-light` and `shade-dark`. |
| P7.5 Depth | M | Back-to-front by centroid with stable tie-breaks; grid order for height fields; `face-overlap` warning. |
| P7.6 Edges and labels | M | Route on the floor plane, project, add vertical segments between elevations. Labels stay flat to the viewer, are placed after projection, and get the `occluded` check. |
| P7.7 3D layouts | M | `stack3d`, `grid3d`, `scale3d`; `elevation: by-rank`. |
| P7.8 `html3d` output | M | three.js (pinned) with orbit controls, built from the same 3D scene. |
| P7.9 Presets | M | `iso-arch`, `platform-stack`, `surface`, `bar3d`, `scatter3d`. |

**Exit:**
- P7 PRs change nothing under `diagonaldiagrams/` outside `toolkits/threed/` (checked in CI by a path filter).
- Every arch gallery figure renders isometric by adding `"use": ["3d"]`, and passes the audit.
- A surface renders from a math spec.

---

## P8. Long tail, informativeness, quality → 1.0.0

| Task | Size | Work |
| --- | --- | --- |
| P8.1 Diagram presets | L | Delete each `_c_*` with its port. The swim preset fixes B24. Kinds:<ul><li>state, swim, bpmn, uml, er;</li><li>context, container and component (C4);</li><li>deploy, layers, integration, current, org, tree, dtree, nested, dag, force, kg, radial;</li><li>fishbone, flywheel, kanban, story, gantt, timeline, journey, wardley, venn.</li></ul> |
| P8.2 Mermaid | L | <ul><li>`direction`; `classDef`, `class`, `style` and `linkStyle` as style rules; nested subgraphs.</li><li>ER optionality markers; sequence notes, fragments and activations.</li><li>Map onto presets: `stateDiagram`, `classDiagram`, `gantt`, `pie`, `timeline`, `quadrantChart`, `mindmap`, `kanban`, `journey`.</li></ul> |
| P8.3 Annotations and budgets | M | All annotation types (DESIGN 4.7) on every preset. Budgets become warnings plus advice in the outline, with `--strict` to refuse. Today's refusals that tests rely on stay under `budget: true`. |
| P8.4 Polish | M | Font subsetting for embedding; the `sketch` decoration. |
| P8.5 Quality benchmark | L | `bench/quality/`: blind pairwise judging of rendered PNGs, before vs after and vs Mermaid, D2 and Graphviz on the README's 5/11/20/40-step task. A vision-model judge with human spot checks. Results go in README next to the token benchmark, which is rerun. |
| P8.6 Remove v1 paths | S | Delete `--layout-engine v1` and anything left unused. Every module ≤ 800 lines. |
| P8.7 Docs | M | README, root `SKILL.md`, the graph-engine skill and references, `describe` examples. A gallery showing style, nesting, `defs` and 3D. |

**Exit:**
- `_c_*` count is 0, truncations are 0, and inline font literals are 0.
- Quality win rate ≥ 80% against the baseline.
- Not worse than Mermaid on the 20- and 40-step tasks.
- The token benchmark is not worse than today.

---

## P9. Pages and stories → 1.0.0

**Goal:** the deck replacement. One scene, many views, presented from a single HTML file.

| Task | Size | Work |
| --- | --- | --- |
| P9.1 Page layouts | M | `page` extension point; sizes `slide`, `A4`, `letter`, `poster`, `responsive`; page-level tokens (DESIGN 21.1). |
| P9.2 Content blocks | L | `heading`, `text` (paragraphs, lists, inline markup), `figure`, `table` (formatted data), `image`, `callout`, `metric`. All are measured and audited. |
| P9.3 Page checks | S | `text-density`, `hierarchy`, `overflow` on pages. |
| P9.4 Views | L | `story` with `focus`, `show`, `hide`, `dim`, `highlight`, `reveal`, and per-view annotations and styles (DESIGN 21.2), through the `view` extension point. |
| P9.5 Transitions | M | Animate between views in HTML (positions, opacity) using stable ids and incremental layout. Respects `prefers-reduced-motion`. |
| P9.6 Presenter runtime | L | One self-contained HTML file, offline:<ul><li>keyboard and touch navigation;</li><li>speaker notes and a presenter view;</li><li>step reveals;</li><li>a print stylesheet with one page per view.</li></ul> |
| P9.7 PDF | M | One page per view, vector, fonts embedded where licenses allow. |
| P9.8 Story presets | M | Briefing, board update, architecture review, incident review, quarterly business review. Each is a preset of page layouts and view patterns. |

**Exit:**
- An agent turns a written brief and a data file into a 10-view story that passes every page check. The scoreboard records its tokens and time.
- Changing one node in the scene updates every view that shows it.
- The HTML opens offline in current Chrome, Edge, Safari and Firefox.

## P10. Live documents and round-trip editing → 1.x

| Task | Size | Work |
| --- | --- | --- |
| P10.1 Edit mode | L | The HTML output gets an edit mode: drag, resize, recolor, retext, reorder. It emits patches (P2.16) and never edits SVG directly. |
| P10.2 Applying edits | M | `apply` turns patches into constraints, rules and fields. A regeneration test: edit, regenerate from a changed brief, and check the edits survive or are reported. |
| P10.3 Data binding | L | `{{ }}` bindings in text, with formatting filters; charts and prose read the same values; provenance in the receipt; `stale-data` check. |
| P10.4 Semantic diff | M | `diagonaldiagrams diff A B`: JSON and sentences. Used in the verdict (`diff` against the previous version) and for review. |
| P10.5 History | M | Each render appends to a history next to the receipt: who or what changed what (agent, person, patch), when, from which inputs. |
| P10.6 Comments | S | Comment anchors keyed by element id, for hosts that support comments. |

**Exit:** human edits survive regeneration or are reported (scoreboard), and bound numbers in text and charts always match their source.

## P11. Legacy bridge → 1.x

| Task | Size | Work |
| --- | --- | --- |
| P11.1 PPTX import | L | Shapes, connectors (with their glue), text, tables and native charts become scenes and pages. |
| P11.2 VSDX and draw.io import | L | Shapes, connectors and containers become scenes. |
| P11.3 Notation imports | M | PlantUML, full Mermaid (after P8.2), BPMN 2.0 XML, ArchiMate exchange format. |
| P11.4 Fallback exports | M | Vector PDF (P9.7); flat PPTX only if the decision table says so. |

**Exit:** the import corpus (real decks and diagrams, collected with permission) reaches the fidelity target on the scoreboard.

## P12. Notations and industry packs → 2.0.0

Each pack is a toolkit with presets, shapes, checks and examples (DESIGN 22.6). Packs ship independently.

| Pack | Contents |
| --- | --- |
| Notations | ArchiMate, full UML and SysML, BPMN 2.0 |
| Finance and strategy | Bridge, Marimekko, football field, bullet, tornado, BCG, value chain, SWOT |
| Operations and quality | SPC control charts with limits, Pareto, value-stream map, SIPOC, FMEA |
| Clinical | Kaplan–Meier with a risk table, forest plot, CONSORT |
| Cloud and enterprise architecture | Extractors for Terraform, Kubernetes, CloudFormation, OpenAPI and dbt; icon packs from folders; drift monitoring through `sync` |
| Geo data | Country and state boundaries, US map with Alaska and Hawaii insets, as an optional package |

## P13. Scale and localization → 2.0.0

| Task | Size | Work |
| --- | --- | --- |
| P13.1 HarfBuzz shaper | M | An optional `shaping` extra behind the `shaper` extension point, plus a browser-measuring shaper. |
| P13.2 Locales | M | Number, date and currency formats per locale; mirrored right-to-left pages. |
| P13.3 Large graphs | L | Meet the DESIGN 22.2 budgets: a 10,000-node org tree and a 1,000-node architecture, paginated and drillable. |
| P13.4 Accessibility audit | M | Check WCAG 2.2 AA conformance of HTML stories and figures with assistive-technology testing; tagged PDF. |

## How each task gets done

1. **A branch per task**, named `p<phase>.<n>-<slug>`. A PR per task, small enough to review.
2. **Tests first** where behavior changes. A bug gets a failing test before its fix.
3. **The PR shows:**
   - golden diffs (SVG and PNG side by side for any changed figure);
   - metrics before and after;
   - counts.
4. **Unchanged contracts.** `tests_smoke.py` passes against both entry points in every PR.
5. **Docs move with the code.** A PR that changes agent-facing behavior updates the skills and `describe` text in the same PR.
6. **Phase review.** The scoreboard is updated, DESIGN.md is corrected wherever reality differed, and the release ships.

## First week

1. P0.4 CI and P0.5 counts (S each).
2. P0.1 golden corpus and P0.2 metrics (M each).
3. P0.3 fuzz harness (M).
4. Start P1.1: write `scripts/split.py` and run it on a branch; review the module boundaries before committing.

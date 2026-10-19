# Quality benchmark: diagonaldiagrams 0.8.0 against Pele and Mermaid

Blind pairwise judging (PLAN P8.5), 2026-10-19, on `slice-integration` (c510aef). dd is diagonaldiagrams 0.8.0;
Pele is 1.6.0 at its defaults (no host CSS, so its fallback greys); Mermaid is mermaid-cli 12.0.0 (mermaid 12.2.0)
at its defaults. 62 pairs, each judged in two placements, in both orders, by Sonnet and by Opus: **496 judgments**,
each answering two questions: which figure is clearer to read, and which looks better.

## Results

dd's win rate (wins / judgments):

| against | placement | clearer | better looking |
| --- | --- | --- | --- |
| Pele | slide | **85%** (106/124) | **98%** (121/124) |
| Pele | column | 56% (70/124) | 84% (104/124) |
| Mermaid | slide | **97%** (120/124) | **99%** (123/124) |
| Mermaid | column | 65% (81/124) | 86% (107/124) |

Flowcharts by size (the token benchmark's task; agent figures and same-source figures together, 16 judgments per cell):

| steps | vs Pele, slide clearer / looks | vs Pele, column clearer / looks | vs Mermaid, slide clearer / looks | vs Mermaid, column clearer / looks |
| --- | --- | --- | --- | --- |
| 5 | 100% / 100% | 100% / 100% | 100% / 100% | 100% / 100% |
| 11 | 81% / 100% | 100% / 100% | 88% / 94% | 100% / 100% |
| 20 | 100% / 100% | 69% / 94% | 100% / 100% | 56% / 94% |
| 40 | 100% / 100% | **19%** / 62% | 100% / 100% | **6%** / 50% |

Other diagram types, one Mermaid source drawn by each tool (clearer, slide / column):

| type | vs Pele | vs Mermaid |
| --- | --- | --- |
| arch (flowchart with subgraphs, 2 figures) | 100% / **0%** | 100% / 25% |
| sequence (3 figures) | **50% / 42%** | 100% / 92% |
| schema (erDiagram, 2 figures) | 62% / **0%** | 100% / 25% |
| ER example | 50% / **0%** | 75% / **0%** |

From dd's own native specs (our reference figures) against Pele and Mermaid drawing the Mermaid translation, dd does
better: arch 88-100% clearer in both placements, sequence 62-100%, schema 100% on slides but 25-50% in the column.
Full tables: [results.md](results.md). Every pair, unblinded, with each judge's reasons: [sheet.html](sheet.html).

**Where each wins.** The owner's guess holds: placement decides it.
- **Slides, decks, page-wide figures:** dd wins almost everything. Pele and Mermaid draw 20 and 40 steps as one strip
  (318 x 2274 and up), and fitted onto a slide their text drops to 2-6 px. dd wraps them into columns that fill the slide.
- **A narrow notes or docs column (700 px, read by scrolling):** dd loses clarity at 20 steps and up, and on every wide
  figure. Its wrapped flows (1192 x 849 at 20 steps, 1574 x 1247 at 40) and wide arch and schema figures shrink to
  4-8 px text, while Pele's and Mermaid's strips stay at their 14-16 px and the reader scrolls. dd still wins on looks
  in most cases (84-86%).
- **Looks:** dd wins 98-99% on slides and 84-86% in the column. Judges praised its restraint (thin strokes, one accent,
  aligned boxes, a title). They faulted Mermaid's heavy strokes, grey label chips and shadows, and Pele's curvy edges
  that leave diamonds off-centre.
- **Pele draws clearer sequence diagrams than dd** from the same source: larger, darker message text, an actor icon,
  and the participant row repeated at the bottom.
- The PLAN P8 exit asks for "not worse than Mermaid on the 20- and 40-step tasks". On slides dd wins 100%. In a column,
  dd is worse at 40 steps (6% clearer) and about even at 20 (56%).

Text size where each figure lands, bench flows (median px, [measure.py](measure.py); page = A4 portrait at 96 dpi):

| steps | slide: dd / Pele / Mermaid | A4 page | 700 px column |
| --- | --- | --- | --- |
| 5 | 20 / 23 / 18 | 13 / 16 / 14 | 13 / 16 / 14 |
| 20 | 14.5 / 5.7 / 4.3 | 8 / 6.8 / 5.2 | 8 / 16 / 14 |
| 40 | 8.5 / 2.8 / 2.1 | 5.3 / 3.3 / 2.5 | 5.3 / 16 / 14 |

No tool's 20- or 40-step flow is readable on an A4 page; dd's is the least bad. dd's own text is also smaller to
begin with: 13 px names and 11 px subtitles and sequence messages, against Pele's 16 and Mermaid's 14-16.

## Rerun in the column with `--fit column` (2026-10-19)

Fix 1 below is built on branch `fit-placement` (0216277): `--fit slide|page|column`. The column placement was
judged again with dd drawn at `--fit column`: no wrapping, at most 640 px wide, wide rows dealt into stacked
columns, wide schemas stacked. Pele's and Mermaid's figures, the 62 pairs, the 24 batches (same pairs, sides and
blind names as b07-b18 and b25-b36), the judge prompt and the judge models were the same as before. That makes
248 judgments; the two orders agree in 96%. Full tables: [runs/fit-column/results.md](runs/fit-column/results.md).

| against | clearer, before → after | better looking, before → after |
| --- | --- | --- |
| Pele | 56% → **68%** (84/124) | 84% → **78%** (97/124) |
| Mermaid | 65% → **77%** (95/124) | 86% → **86%** (107/124) |

Flowcharts (agent figures and same-source figures, 16 judgments a cell), clearer:

| steps | vs Pele | vs Mermaid |
| --- | --- | --- |
| 5, 11 | 100% → 100% | 100% → 100% |
| 20 | 69% → **100%** | 56% → **100%** |
| 40 | 19% → **100%** | 6% → **100%** |

dd's 20- and 40-step flows now win every column judgment on both questions. As one strip they keep their 13 px
text; wrapped, they had 5-8 px.

Other types did not gain, and arch lost:
- **Arch:** N (dd's native specs) fell from 88% and 100% clearer to 50% and 50%, and L stayed at 0% against Pele
  (25% → 0% against Mermaid). Both checkout-groups figures lost every judgment. Text is larger now (9-13 px
  against 5.5-10.5), but the narrow layouts run long wrap-around edges, put the labels far from them and take
  three screens. Judges preferred compact drawings at smaller sizes. `--fit column` should probably
  leave a wide arch figure's layers whole, since dd's own wide arch won here before.
- **Schema and ER:** about the same (L 0% → 0% against Pele, N 25% → 38%). Stacked tables keep 11 px text, but
  every loss names the ER drawing (fix 2): relation lines leave from arbitrary rows (Mermaid ER gives no columns),
  no crow's feet, and "1:N 1:N" doubled labels. Opus judges add that a single stack hides the tree's fan-out.
- **Sequence** figures are the same drawings in both runs; their verdicts moved by at most one judgment of four.

## What to fix, ranked by how often it loses

160 judgments went against dd. Each loss's reason and "dd's weakness" phrase were tagged by keyword
([cluster.py](cluster.py); every loss with its tags is in [losses.md](losses.md)), then grouped by cause; a loss counts
once per cause, but can count under several causes.

| # | Cause | Losses | of which column | Fix |
| --- | --- | --- | --- | --- |
| 1 | **Size ignores where the figure goes.** Wrapped 20- and 40-step flows and wide arch, schema and ER figures shrink to 4-8 px text in a column | 122 | 116 | Let the caller say where the figure goes: a `--fit slide\|page\|column` flag (and a Mermaid front-matter key) that sets the wrap target (`diagrams.ASPECT`, now 4:3; `layout/wrap.py` wraps past twice that height) and a maximum width. For a column: no wrap, a single tall strip like Pele's, and schema tables stacked rather than side by side. Spec files already have `size.aspect`, but Mermaid input and the CLI cannot set it. Tell agents in SKILL.md to pick the fit. |
| 2 | **ER drawing.** Plain arrowheads with "1:N" text instead of crow's feet; in `N-ref-schema-store` the two vertical relations show no arrowhead at all; "1:N 1:N" doubled labels | 55 | 45 | Draw crow's-foot and bar ends from the cardinality (Mermaid ER gives both ends); find why vertical relations lose their markers (the SVG has `marker-end` on all four); in `mermaid._mm_er`, drop the verb when it repeats the cardinality. Note: 25 of these losses cite the doubled label, which my schema translations provoked by using `"1:N"` as the relation's verb. With a normal verb ("places") dd draws "1:N places". The other 30 stand. |
| 3 | **Arrows share a trunk or merge.** arch fan-outs (agent-platform: prompt, search, execute, draw and events ride one horizontal bus with their labels lined up on it; checkout-groups: settled and card share a segment, verify and browse share a bar); in a wrapped flow, "7 no" merges into the 9→10 arrow | 29 | 28 | Give each fan-out edge its own port and lane out of the source (`layout/layered.py` `ports()`), and keep an edge from joining another's last segment into the same target. The audit's `shared` check did not flag these. |
| 4 | **Small, pale default text** even at full size: sequence message labels (11 px, muted grey), subtitles | 27 | 15 | Raise body text to 14-15 px and labels to 12-13 px with darker ink, sequence messages first (`style/presets/seq.json`, `diagram.json`). This also helps cause 1. |
| 5 | **No colour coding by node kind; Mermaid input dropped.** Judges liked green start/end, blue steps and amber decisions (the Mermaid agents' `classDef`, which dd ignores); `<br/>` second lines are flattened ("Web app React"); `[( )]` cylinders become boxes tagged DB | 25 | 23 | `mermaid._mm_text`: read `<br/>` as name + sub; add a cylinder shape (`paint.SHAPES` has rect, oval, diamond and dot only); map `classDef` fill and stroke to style rules instead of only warning; consider a soft default tint for decisions and terminals. |
| 6 | **Sequence chrome.** A "USER" tag over "User" reads as a duplicate; no actor icon; participants not repeated at the bottom | 16 | 10 | Draw an `actor` as a person icon, not a USER tag; repeat the participant row under long lifelines (Mermaid's mirrorActors). |
| 7 | Edge labels float away from their arrows or are crossed by them (ER "ordered in" struck through; "no" labels far from loop-backs) | 10 | 3 | Keep relation labels off the line in schema; pull loop labels to the edge. |
| 8 | Misaligned boxes and kinked arrows | 7 | 4 | (small; mostly 5- and 11-step agent figures) |

Found along the way, not judged:
- `L-ref-arch-agent-platform` read from Mermaid fails dd's own audit (`strike`: an arrow crosses the 'AGENT RUNTIME'
  frame label). The same figure from its native spec passes.
- `export._raster_svg` only reads a viewBox starting at `0 0`. Mermaid's start at `4 4` or `-50 -50`, so it guessed a 4:3
  page and cropped them. dd's own export only ever rasterizes dd's SVGs, so the product is unaffected;
  [raster.py](raster.py) places any viewBox.

## Method

**Figures** ([render.py](render.py), 81 SVGs in [svg/](svg)):
- **A, agent figures (16 pairs):** the token benchmark's figures as each agent left them (D:\Repos\diagonaldiagrams-bench-runs):
  dd against Pele and against Mermaid at 5, 11, 20 and 40 steps, run 1 with run 1 and run 2 with run 2. Content
  differs: each agent wrote its own labels, titles and colours.
- **L, same source (34 pairs):** 17 Mermaid sources in [sources/](sources), each drawn fresh by all three tools: the
  first run's Mermaid from the Pele and the Mermaid agents at each size (`bench-NN-a`, `bench-NN-b`), the three Mermaid
  examples, and Mermaid translations of six reference figures (two each of arch, seq and schema, written for this
  benchmark). dd against Pele and against Mermaid.
- **N, native (12 pairs):** dd drawing those six references from their native specs (examples/*.json), against Pele
  and Mermaid drawing the translation.

**Placements** ([raster.py](raster.py), drawn by headless Edge from the SVG, no raster rescaling; images in
[png/](png)):
- `slide`: a 1600 x 900 slide, the figure fitted into 1520 x 820 and centred (enlarged up to 2x).
- `column`: a 700 px column at 1.5x, the figure at its own size or shrunk to 668 px wide. Tall figures were cut into
  1050 x 1100 tiles, which the judge read top to bottom.

**Judging** ([pairs.py](pairs.py), [judge_prompt.md](judge_prompt.md)):
- Each judge was a fresh Claude Code subagent (Sonnet 5.5 or Opus 5.5) given only a folder of images under blind names
  (`p03-A-2of5.png`).
- A random side is A, and the swapped order goes to a different judge batch. Slide batches held about 21 pairs;
  column batches held about 11.
- For each pair the judge answered which figure is clearer and which looks better (no ties; slight or clear), why,
  and the main weakness of each figure.
- The key ([judgments/key.json](judgments/key.json)) never reached the judges. [tally.py](tally.py) unblinds the
  verdicts into [judgments/all.csv](judgments/all.csv) and [results.json](results.json).

**Consistency.** The two orders agree in 91% of 496 cases. dd wins 86% when shown first and 82% when shown second.
Sonnet and Opus agree within 1-3 points on clarity; Opus favours dd's looks a little more (90-92% against 77-81% in
the column).

**Caveats.**
- The judges are vision models, and they are not blind to style: dd's look is recognisable across pairs. The human
  check is [sheet.html](sheet.html), still to do.
- Pele was judged without host CSS. In Obsidian it takes the vault's theme, which would change its looks, not its layout.
- The six translations are mine, and the doubled-label caveat above applies to them.
- The committed PNGs are 256-colour copies (to keep the repo small); the judges saw the full-colour originals, which
  `raster.py` rebuilds.

## Rerun

Needs Node, Edge or Chrome, and the bench tools folder (Pele and mermaid-cli, already installed; nothing is
downloaded). `PYTHONDONTWRITEBYTECODE=1` throughout.

```bash
py -3 bench/quality/render.py
```

```bash
py -3 bench/quality/raster.py
```

```bash
py -3 bench/quality/measure.py
```

```bash
py -3 bench/quality/pairs.py JUDGE_DIR
```

Then run one judge per batch with `JUDGE_DIR/bNN/instructions.md` (written by [prompts.py](prompts.py)), then:

```bash
py -3 bench/quality/tally.py JUDGE_DIR
```

```bash
py -3 bench/quality/cluster.py
```

```bash
py -3 bench/quality/report.py
```

```bash
py -3 bench/quality/sheet.py
```

The `--fit column` rerun, with dd from a checkout of `fit-placement` (the column PNGs are not committed; raster.py
rebuilds them from runs/fit-column/svg):

```bash
py -3 bench/quality/render.py --run fit-column --fit column --dd PATH_TO_FIT_PLACEMENT_CHECKOUT
```

```bash
py -3 bench/quality/raster.py --run fit-column --context column
```

```bash
py -3 bench/quality/pairs.py JUDGE_DIR --run fit-column --context column
```

```bash
py -3 bench/quality/prompts.py JUDGE_DIR --run fit-column
```

Then one judge per batch as above, then:

```bash
py -3 bench/quality/tally.py JUDGE_DIR --run fit-column
```

```bash
py -3 bench/quality/compare.py fit-column
```

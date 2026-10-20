---
name: graph-engine
description: Draw charts, flowcharts, sequence diagrams, architecture maps, database schemas, maps, and math plots as SVG with diagonaldiagrams. One command checks the spec, draws, and audits the layout for collisions. Use for any request to chart, plot, diagram, or visualize data, logic, a codebase, or a schema.
---

# Draw with diagonaldiagrams

Run `diagonaldiagrams`, or `py -3 <path>/graph.py` (Windows) / `python3 <path>/graph.py`. Not installed:
run the `diagonaldiagrams-install` skill.

## One call

Write the input and render it in the same shell call. Flowcharts, sequence diagrams, and ER diagrams
are plain Mermaid, piped in with `-`:

```bash
diagonaldiagrams mermaid - -o flow.svg <<'EOF'
flowchart TD
  A([Ticket arrives]) --> B{Sev1?}
  B -->|yes| C[Page on-call]
  B -->|no| D[Queue it]
EOF
```

It prints one JSON line:

- `"ok": true`: done. The figure is at `svg`. `layout` lists what was drawn: each row's boxes left to
  right and each frame's members (a long flow that wraps says which rows stand in which column), a
  schema's columns of tables, a sequence's messages in order, or a chart's axes and series. Check the
  content against it.
- `"ok": false`: each error has a `fix`. Change the input and run again. Never edit the SVG.
- `warnings`: the figure is drawn; act on one only if it matters.

`"ok": true` means no text overlaps, nothing spills its box or the canvas, no boxes overlap, and no
arrow crosses a box or a label. Do not screenshot, open, or grep the SVG to check: answer from the
verdict. Each extra look costs a full round trip.

## Where it goes

Pick `--fit` for where the figure will be read, so its text stays full size there:

- `--fit column` for a README, docs page, wiki, notes app or chat: a column about 700 px wide, read by
  scrolling. A long flow stays one tall strip, a wide row splits into rows where that takes less room
  than shrinking the figure, schema tables stack, and the figure is about 640 px wide.
- `--fit slide` (the default) for a deck or a full-width screen: a long flow wraps into columns.
- `--fit page` for a printed or PDF page: a long flow wraps toward portrait.

In Mermaid, a front matter line does the same (`---`, `fit: column`, `---` above `flowchart TD`); in a
JSON spec, `"size": {"fit": "column"}`. Sequence diagrams draw the same in every fit.

## Mermaid

`([x])` start or end, `[x]` step, `{x}` decision, `[(x)]` store. `-->|label|`, `-.->` dashed,
`==>` or `:::focal` coral. `subgraph id [Name] ... end` draws a frame. `fa:fa-database` adds an icon.
An arrow back to an earlier step draws up the outside. Flows draw top-down; arrow labels draw in capitals.
`sequenceDiagram` (`participant G as Gateway`, `A->>B: call`, `B-->>A: reply`, `A-)B: event`) and
`erDiagram` (`A ||--o{ B : has`) work too. Not drawn: style and classDef colors, notes, loop or alt
blocks. A parse error names the line.

## JSON specs and data

`flow`, `arch`, `seq`, and `schema` also take a JSON spec: `diagonaldiagrams arch spec.json -o arch.svg`.
`describe <type>` prints the shape. Use `arch` for services in rows (`layer`), with blue HTTP arrows.

CSV with a header row:

| type | flags |
| --- | --- |
| `bar` | `--cat COL --val COL [--group COL --sort desc --unit ms]` |
| `line` | `--x COL --y COL [--group COL]` |
| `scatter` | `--x COL --y COL [--group COL]` |
| `geo` | `--lat COL --lon COL [--label COL]` |

All take `--title`, `--subtitle` (state the finding), `--xlabel`, `--ylabel`, and `--highlight VALUE`
(one series or bar in coral). Line charts name each series at its end; that is the legend.
`bar` and `line` take `--ref VALUE=label` for a dashed reference line (a target, or 50%); `--unit %` ends a
bar axis at 100.
`chart <type> INPUT` draws about 60 more (sankey, gantt, heatmap, treemap, pie, radar, math, ...);
`describe` lists them.

## Files

`-o PATH/NAME.svg` is the file you get (folders are created), with `NAME.html` and
`NAME.graph.json` beside it. Input given with `-` or `-s TEXT` is saved as `NAME.spec.mmd` or `NAME.spec.json`.
`export DIR/NAME --to png|pdf|drawio|excalidraw` redraws from the receipt.

## Stories

To walk someone through a figure, write a story: the figure, then views that `focus`, `dim`, `hide`,
`highlight` or `reveal` parts of it by selector, each with a `title`, `text` and `notes`.
`diagonaldiagrams story STORY.json -o out/story.html` draws every view into one page that animates
between them. `describe story` has the format; a warning means a selector matched nothing.

## Edits as patches

To move, rename or recolor boxes, write a patch: a JSON list like
`[{"op": "place", "id": "fix", "row": ["review", "fix"]}]` (`place` puts a box in a row, in that order). Write it
into the spec and draw again at the same `-o` path:

```bash
diagonaldiagrams apply SPEC.json patch.json
diagonaldiagrams flow SPEC.json -o out/x.svg
```

The verdict's `changed` lists what moved, so you can say it in a sentence; the page animates the change.
Keep edits when you regenerate the spec: `place` writes `rank`, `order` and `same-rank`, which you should
leave as they are. Keep the patch too: after regenerating, apply it again. Edits that still fit are written in
(applying twice changes nothing); a `patch-conflict` names an edit the new spec contradicts.
`diff OLD NEW` compares any two drawings.

Titles state the finding. Blue is HTTP, dashed is async, coral marks at most two focal items.

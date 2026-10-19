# graph — agent skill

Graphing library for agents: the `diagonaldiagrams` package, Python 3, standard library only.
Run `diagonaldiagrams` once installed; from a checkout, `py graph.py` takes the same arguments.
Install with the `diagonaldiagrams-install` skill, then draw with the commands below.
Same spec, same SVG.

## The loop

```
diagonaldiagrams <type> SPEC.json|DATA.csv [flags] -o out/x.svg
diagonaldiagrams mermaid - -o out/x.svg <<'EOF'      # or -s TEXT; the text is saved as out/x.spec.mmd
flowchart TD
  A[Client] --> B[Server]
EOF
```

Render validates first, draws, then audits the SVG, and prints one JSON line.
Exit 0 and `"ok": true`: done; `layout` lists what was drawn. Exit 1: read `errors`
(each has a `fix`), change the spec or flags, render again. Never hand-edit the SVG.
`--no-audit` accepts a figure the audit flags. `describe <type>` is the contract, `infer DATA.csv`
proposes a scatter spec, and `export out/x --to png --layout wide` redraws from
the receipt. `validate` and `audit` also run alone; `audit` reads any SVG.

Say where a flow, arch, schema or Mermaid figure will be read with `--fit`: `column` for a README, docs
page or notes column (no wrap, at most 640 px wide, read by scrolling), `slide` (default) for a deck,
`page` for a printed page. Mermaid front matter `fit: column` and a spec's `"size": {"fit": "column"}`
do the same.

## Recipes

```bash
# data → journal scatter (groups + error bars + facets)
diagonaldiagrams infer exp.csv
diagonaldiagrams scatter exp.csv --x dose --y expr --yerr sd --group tissue --facet cohort \
  --title 'Dose response' --subtitle 'One-sentence finding.' \
  --xlabel Dose --xunit mg --ylabel Expression --yunit 'log2 counts' \
  --source 'lab notebook 2026-10' -o out/exp.html

# data → bar / line
diagonaldiagrams bar lat.csv --cat service --val p99 --unit ms --sort desc -o out/bar.html
diagonaldiagrams line tput.csv --x ts --y rps --group service -o out/line.html

# logic → decision flowchart (PAP/DIN 66001 shapes; auto-layout default)
diagonaldiagrams validate flow.json && diagonaldiagrams flow flow.json --corners sharp -o out/f.html
# --auto forces longest-path layering even when ranks are present (barycenter uncrossing)

# runtime → sequence (lifelines, sync/async/reply)
diagonaldiagrams validate seq.json && diagonaldiagrams seq seq.json -o out/seq.html

# database → schema (tables, PK/FK, relations)
diagonaldiagrams validate schema.json && diagonaldiagrams schema schema.json -o out/schema.html

# places → point map (CSV lat/lon, or GeoJSON points and polygons) on a built-in coastline. Not map tiles.
diagonaldiagrams geo cities.csv --lat lat --lon lon --label city --val people_m -o out/geo.html

# codebase → architecture view (one C4 level per render)
diagonaldiagrams arch containers.json -o out/arch.html

# math → 2D curves from an equation. describe math prints the language.
diagonaldiagrams validate math.json --type math
diagonaldiagrams chart math math.json -o out/math.html

# the rest of the taxonomy. describe prints the columns or the JSON shape.
diagonaldiagrams describe sankey
diagonaldiagrams chart sankey flows.csv -o out/sankey.html
diagonaldiagrams chart gantt plan.json -o out/gantt.html
diagonaldiagrams chart choropleth regions.geojson -o out/regions.html
```

## Hard budgets (validate enforces, audit double-checks)

A flow or architecture spec may set `"budget": false` to lift the node and edge counts. Focal stays at two. The row widens so the boxes still sit apart. `chart` types have their own caps. `--no-budget`, or `"budget": false` on a JSON spec, lifts that cap.

| rule | limit | over → |
|---|---|---|
| nodes | 9 | split overview + detail |
| edges | 12 | drop layout-obvious arrows |
| focal (coral) | 2 | demote rest |
| diamond exits | 3 | nest diamonds |
| seq actors / messages | 6 / 16 | split sub-sequences |
| schema tables / cols shown | 6 / 12 warn | split bounded contexts |
| bar bars / categories | 24 / 12 | top-N + Other |
| scatter points | 400 rendered | aggregate / facet |
| geo points | 400 | crop to the region |
| groups / facets | 8 / 4 | top-N + Other |

## Taste (non-negotiable)

- Shape carries type (oval=start/end, rect=step, diamond=decision) — never color.
- Blue `#2e5aa8` = HTTP/API only. Dashed = async. Coral = 1–2 focal max.
- Orthogonal elbows, masked arrow labels with gap. Title and subtitle are drawn on the figure. One system font.
- The HTML page is the diagram plus Copy SVG, Export SVG, and Export PNG. Print hides that bar. `--grid`, `--markers`, `--highlight` live on the chart.
- Ratio data never shows a negative axis. Ticks are nice numbers on the grid.

## MCP

`diagonaldiagrams mcp` serves the same loop over stdio as six tools: describe, render,
validate, audit, export, infer. `render` takes `spec` (JSON object) or `data` (CSV
text) inline plus `options` (the CLI flags), so one call draws and audits a figure.

`diagonaldiagrams doc DOC.md --out-dir assets [--check]` compiles fenced
```graph:<type> blocks to SVGs (+ `--check` for CI).
`diagonaldiagrams extract schema|routes SRC -o spec.json` reverse-extracts specs from
SQL DDL / Prisma / Python ORM (SQLAlchemy, Django, SQLModel) / FastAPI-Flask routes.
`diagonaldiagrams monitor --map graph.monitor.json [--ci]` flags drift;
`diagonaldiagrams sync --map graph.monitor.json [--docs ARCH.md] [--commit]` is the
auto-fix bot (extract → validate → doc → audit → local commit, never pushes).

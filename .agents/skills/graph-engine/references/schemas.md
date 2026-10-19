# schemas.md — generated from `diagonaldiagrams describe <type>`
Source of truth: DESCRIBE in diagonaldiagrams/describe.py. Regenerate with `py -3 scripts/schemas_ref.py`; `describe` lists every other type.

## scatter
```json
{
  "input": "CSV with header row. Two numeric columns minimum.",
  "writes": "diagonaldiagrams scatter DATA.csv --x X --y Y -o OUT.svg  (+ OUT.html and the OUT.graph.json receipt beside it)",
  "required": [
    "--x",
    "--y"
  ],
  "options": {
    "--title": "finding, not description",
    "--subtitle": "one sentence takeaway",
    "--figure": "Fig. number",
    "--xlabel/--xunit/--ylabel/--yunit": "axis + unit in parens",
    "--group": "categorical col, Okabe-Ito legend",
    "--yerr": "numeric SD/CI col, capped bars",
    "--facet": "categorical col, small multiples A/B (+col layout via export --layout social)",
    "--source": "provenance, n auto-appended",
    "--caption": "kept on the receipt",
    "--corners": "sharp|rounded|editorial",
    "--grid/--no-grid": "tick rules, on by default",
    "--markers/--no-markers": "point dots, on by default",
    "--highlight": "group or x value, repeatable, drawn larger in accent"
  },
  "budgets": {
    "points_rendered": 400,
    "groups": 8,
    "facets": 4,
    "series": "focal rule: 1 accent max"
  },
  "rules": [
    "non-negative data never shows a negative axis",
    "domain includes error bars",
    "ticks are nice numbers aligned to grid",
    "title and subtitle are drawn on the figure; the HTML page and the .svg are the same drawing"
  ],
  "example": "diagonaldiagrams scatter examples/scatter_groups.csv --x dose --y expr --yerr expr_err --group tissue --facet cohort --xlabel Dose --xunit mg --ylabel Expression --yunit 'log2 counts' -o out/s.html"
}
```

## flow
```json
{
  "input": "JSON spec {title, sub, nodes[], edges[], groups[]}",
  "writes": "diagonaldiagrams flow SPEC.json -o OUT.svg",
  "size": "{\"fit\": \"slide|page|column\"}, or --fit. slide (default): a long flow wraps into columns near 4:3. page: a document page, wraps toward portrait. column: a docs or notes column, read by scrolling: no wrap, about 640 px wide (a wide layer splits into rows where that takes less room than shrinking the figure; schema tables stack)",
  "node": {
    "id": "unique",
    "shape": "oval=start/end | rect=step | diamond=decision | dot=merge",
    "name": "2-4 words",
    "tag": "optional kind, e.g. MANUAL (not STEP/START/END: the shape says it)",
    "sub": "mono sublabel",
    "rank": "row, 0 at the top (default: automatic)",
    "lane": "-1 left|0 center|1 right (default 0)",
    "focal": "bool, max 2 per diagram"
  },
  "edge": {
    "from": "id",
    "to": "id",
    "label": "ALWAYS label decision exits",
    "focal": "happy-path bool"
  },
  "rules": [
    "top-down; a decision's branches sit side by side, loops draw back up the outside",
    "diamond ≤3 exits (nest for more)",
    "orthogonal elbows only",
    "labels masked with 6px gap",
    "shape carries type, never color",
    "no ranks needed: longest-path auto-layering + barycenter uncrossing (--auto forces it)"
  ],
  "budgets": {
    "nodes": 9,
    "edges": 12,
    "focal": 2,
    "over": "a warning, not an error; split if it reads badly, or budget false hides it"
  },
  "example": "{\"title\":\"Deploy approval\",\"nodes\":[{\"id\":\"a\",\"shape\":\"oval\",\"name\":\"Push\"},{\"id\":\"d\",\"shape\":\"diamond\",\"name\":\"Risky?\",\"rank\":1,\"focal\":true}],\"edges\":[{\"from\":\"a\",\"to\":\"d\",\"label\":\"pass\"}]}"
}
```

## arch
```json
{
  "input": "JSON spec {title, sub, nodes[], edges[]}",
  "writes": "diagonaldiagrams arch SPEC.json -o OUT.svg",
  "size": "{\"fit\": \"slide|page|column\"}, or --fit. slide (default): a long flow wraps into columns near 4:3. page: a document page, wraps toward portrait. column: a docs or notes column, read by scrolling: no wrap, about 640 px wide (a wide layer splits into rows where that takes less room than shrinking the figure; schema tables stack)",
  "node": {
    "id": "unique",
    "layer": "row int (default 0)",
    "name": "service",
    "sub": "Lang:port e.g. Go:8080",
    "tag": "UI|API|SVC|STORE",
    "focal": "bool, max 2"
  },
  "edge": {
    "from": "id",
    "to": "id",
    "label": "VERB",
    "proto": "https=blue arrow",
    "async": "dashed bool",
    "focal": "bool"
  },
  "rules": [
    "blue=HTTP/API, dashed=async, coral=focal",
    "tech sublabels in mono, names in sans",
    "a wide layer spreads the canvas so boxes do not overlap",
    "set budget false to draw past 9 nodes and 12 edges; focal stays at 2"
  ],
  "budgets": {
    "nodes": 9,
    "edges": 12,
    "over": "a warning, not an error; one view per C4 level, or budget false hides it"
  }
}
```

## seq
```json
{
  "input": "JSON spec {title, sub, actors[], messages[]}",
  "writes": "diagonaldiagrams seq SPEC.json -o OUT.svg",
  "actor": {
    "id": "unique",
    "name": "label",
    "sub": "tech/mono sub",
    "tag": "USER|UI|GATEWAY|SVC|STORE",
    "focal": "bool, max 2"
  },
  "message": {
    "from": "id",
    "to": "id",
    "label": "Call name/payload",
    "proto": "https/grpc",
    "reply": "bool dashed",
    "async": "bool dashed",
    "focal": "bool"
  },
  "rules": [
    "solid=sync, dashed=reply/async, blue=http, coral=focal",
    "top-down sequence order",
    "max 6 lifelines"
  ],
  "budgets": {
    "actors": 6,
    "messages": 16,
    "focal": 2,
    "over": "a warning, not an error; split into sub-sequences, or budget false hides it"
  },
  "example": "{\"title\":\"Auth handshake\",\"actors\":[{\"id\":\"u\",\"name\":\"User\"},{\"id\":\"api\",\"name\":\"API\",\"focal\":true}],\"messages\":[{\"from\":\"u\",\"to\":\"api\",\"label\":\"login\"}]}"
}
```

## schema
```json
{
  "input": "JSON spec {title, sub, tables[], relations[]}",
  "writes": "diagonaldiagrams schema SPEC.json -o OUT.svg",
  "size": "{\"fit\": \"slide|page|column\"}, or --fit. slide (default): a long flow wraps into columns near 4:3. page: a document page, wraps toward portrait. column: a docs or notes column, read by scrolling: no wrap, about 640 px wide (a wide layer splits into rows where that takes less room than shrinking the figure; schema tables stack)",
  "table": {
    "id": "unique",
    "name": "table_name",
    "tag": "AUTH|CORE|AUDIT",
    "focal": "bool, max 2",
    "columns": [
      {
        "name": "col",
        "type": "data_type",
        "pk": "bool",
        "fk": "bool",
        "unique": "bool"
      }
    ]
  },
  "relation": {
    "from": "id",
    "from_col": "col",
    "to": "id",
    "to_col": "col",
    "label": "1:N|1:1|M:N",
    "focal": "bool"
  },
  "rules": [
    "PK coral badge, FK blue badge, columns in mono, types muted",
    "orthogonal elbow routing",
    "max 6 tables per view"
  ],
  "budgets": {
    "tables": 6,
    "columns_per_table": 12,
    "over": "a warning, not an error; split by bounded context, or budget false hides it"
  },
  "example": "{\"title\":\"Users & Teams\",\"tables\":[{\"id\":\"u\",\"name\":\"users\",\"columns\":[{\"name\":\"id\",\"type\":\"uuid\",\"pk\":true}]}],\"relations\":[]}"
}
```

## mermaid
```json
{
  "input": "Mermaid text (.mmd): flowchart/graph, sequenceDiagram, or erDiagram",
  "writes": "diagonaldiagrams mermaid DIAGRAM.mmd -o OUT.svg   (flow, seq, or schema; checked and audited like a JSON spec)",
  "flowchart": {
    "nodes": "A[step]  A(step)  A([start or end])  A((start or end))  A{decision?}  A[(store)]",
    "arrows": "A --> B   A -->|label| B   A -- label --> B   A -.-> B (dashed)   A ==> B (focal)   A & B --> C",
    "groups": "subgraph id [Title] ... end",
    "focal": "A:::focal",
    "icons": "fa:fa-user, fa:fa-database, fa:fa-server, fa:fa-cloud ... in a label draw that glyph in the box"
  },
  "sequenceDiagram": "participant A as Name | actor U as User | A->>B: call | B-->>A: reply | A-)B: async event",
  "erDiagram": "A ||--o{ B : verb | A { type name PK }",
  "fit": "where the figure goes, as --fit: a line fit: column (or slide, page) in the front matter between --- lines",
  "not drawn": "classDef/style colors, notes, loop/alt blocks, LR direction (flows draw top-down)",
  "example": "flowchart TD\n  A([Push]) --> B{Risky?}\n  B -->|yes| C[Review]\n  B -->|no| D([Ship])\n  C --> D"
}
```

## bar
```json
{
  "input": "CSV with header row. One categorical column and one numeric column.",
  "writes": "diagonaldiagrams bar DATA.csv --cat CAT --val VAL -o OUT.svg",
  "options": {
    "--cat": "category column",
    "--val": "numeric value column",
    "--group": "subgroup column",
    "--sort": "none|asc|desc",
    "--orientation": "v|h",
    "--unit": "unit string",
    "--title/--subtitle": "drawn on the figure",
    "--grid/--no-grid": "tick rules, on by default",
    "--markers/--no-markers": "value labels, on by default",
    "--highlight": "category or group, repeatable, drawn in accent"
  },
  "budgets": {
    "bars": 24,
    "categories": 12,
    "over": "sort top-N + other"
  },
  "rules": [
    "bar charts must start at zero",
    "value labels sit on the bars",
    "gridlines follow the ticks"
  ],
  "example": "diagonaldiagrams bar examples/bar_latency.csv --cat service --val p99_latency_ms --unit ms -o out/bar.html"
}
```

## line
```json
{
  "input": "CSV with header row. Continuous/temporal X column and numeric Y column.",
  "writes": "diagonaldiagrams line DATA.csv --x X --y Y -o OUT.svg",
  "options": {
    "--x": "x column (numeric or timestamp)",
    "--y": "y column (numeric)",
    "--group": "series column",
    "--xlabel/--xunit/--ylabel/--yunit": "axis labels",
    "--title/--subtitle": "drawn on the figure",
    "--grid/--no-grid": "tick rules, on by default",
    "--markers/--no-markers": "point dots, on by default",
    "--highlight": "x value or group, repeatable, drawn larger in accent"
  },
  "budgets": {
    "series": 6,
    "rows": 400,
    "over": "a warning, not an error; a series past 600 points is thinned for drawing"
  },
  "rules": [
    "non-negative data floors at 0",
    "Okabe-Ito series colors",
    "area fill only on a single series"
  ],
  "example": "diagonaldiagrams line examples/line_throughput.csv --x timestamp --y rps --group service -o out/line.html"
}
```

## geo
```json
{
  "input": "CSV with lat/lon columns, or a GeoJSON FeatureCollection of Points and Polygons.",
  "writes": "diagonaldiagrams geo DATA.csv --lat lat --lon lon --label name --val pop -o OUT.svg",
  "options": {
    "--lat/--lon": "column names (guessed from lat/lon/lng when omitted)",
    "--label": "place name",
    "--val": "numeric size",
    "--title/--subtitle": "drawn on the figure",
    "--source": "footer provenance",
    "--grid/--no-grid": "graticule lines, on by default",
    "--markers/--no-markers": "place dots, on by default",
    "--highlight": "place name, repeatable, drawn larger in accent"
  },
  "budgets": {
    "points": 400,
    "over": "crop to the region you mean"
  },
  "rules": [
    "Web Mercator figure with a built-in coastline, not a tiled basemap",
    "GeoJSON polygons are drawn on top of the coastline",
    "graticule, kilometre scale bar, north arrow",
    "dot size follows --val"
  ],
  "example": "diagonaldiagrams geo examples/geo_cities.csv --lat lat --lon lon --label city --val people_m -o out/geo.html"
}
```

## export
```json
{
  "input": "Receipt OUT.graph.json written beside every render.",
  "writes": "diagonaldiagrams export OUT --to png|pdf|svg [--layout figure|wide|slide|social] [--width 1600] [-o FILE]",
  "rules": [
    "svg works everywhere, zero deps (re-render from receipt)",
    "layouts figure/wide/slide/social apply to scatter; other types export single layout",
    "png and pdf use cairosvg when it imports, otherwise headless Edge or Chrome",
    "the HTML page has Export PNG, which saves the figure from the browser"
  ],
  "budgets": {
    "png_width_default": 1600
  },
  "example": "diagonaldiagrams export out/scatter --to svg --layout social"
}
```

## doc
```json
{
  "input": "Markdown document containing ```graph:<type> fenced blocks.",
  "writes": "diagonaldiagrams doc DOC.md [--out-dir assets] [--check]",
  "behavior": "Parses and compiles embedded diagram specs into standalone SVGs in assets/, updates doc links"
}
```

## monitor
```json
{
  "input": "Repository working tree or git history.",
  "writes": "diagonaldiagrams monitor [--base <ref>] [--ci] [--map graph.monitor.json]",
  "behavior": "Scans code changes for data models, routes, and migrations without corresponding diagram updates; outputs JSON drift report. With --map, extracts each changed file and semantically diffs against its spec (no diff = no drift, even if files changed).",
  "map_format": "{\"mappings\": [{\"code\": \"models/*.py\", \"spec\": \"docs/schema.graph.json\", \"kind\": \"schema\", \"domain\": \"database\"}]}"
}
```

## extract
```json
{
  "input": "Code source file (.sql DDL, Python ORM model, FastAPI routes).",
  "writes": "diagonaldiagrams extract schema|routes SOURCE_FILE -o SPEC.json",
  "behavior": "Reverse-extracts architecture or database schema diagram specs directly from source code using AST/token parsing"
}
```

## sync
```json
{
  "input": "Same inputs as monitor (--path, --base, --map).",
  "writes": "diagonaldiagrams sync --map graph.monitor.json [--docs ARCH.md] [--commit]",
  "behavior": "Auto-fix bot: for each mapping-backed drift entry runs extract -o spec, validates, recompiles --docs, audits emitted SVGs. Default touches only the working tree; --commit creates a LOCAL commit (never pushes). Exit 1 if anything is left undone. Heartbeat: cron `0 6 * * * cd repo && diagonaldiagrams sync --map graph.monitor.json --commit`, Windows Task Scheduler, or an Antigravity cron//goal task."
}
```

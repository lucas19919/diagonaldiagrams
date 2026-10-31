"""describe: the contract for every figure type."""
import json
from ._draw import ICONS
from .charts.catalog import _chart_meta

# where a figure goes (diagrams.FITS), for flow, arch and schema
FIT = ("{\"fit\": \"slide|page|column\"}, or --fit. slide (default): a long flow wraps into columns near 4:3. "
       "page: a document page, wraps toward portrait. column: a docs or notes column, read by scrolling: "
       "no wrap, about 640 px wide (a wide layer splits into rows where that takes less room than shrinking the figure; schema tables stack)")


DESCRIBE = {
    "scatter": {
        "input": "CSV with header row. Two numeric columns minimum.",
        "writes": "diagonaldiagrams scatter DATA.csv --x X --y Y -o OUT.svg  (+ OUT.html and the OUT.graph.json receipt beside it)",
        "required": ["--x", "--y"],
        "options": {"--title": "finding, not description", "--subtitle": "one sentence takeaway",
                    "--figure": "Fig. number", "--xlabel/--xunit/--ylabel/--yunit": "axis + unit in parens",
                    "--group": "categorical col, Okabe-Ito legend", "--yerr": "numeric SD/CI col, capped bars",
                    "--facet": "categorical col, small multiples A/B (+col layout via export --layout social)",
                    "--source": "provenance, n auto-appended", "--caption": "kept on the receipt",
                    "--corners": "sharp|rounded|editorial",
                    "--grid/--no-grid": "tick rules, on by default",
                    "--markers/--no-markers": "point dots, on by default",
                    "--highlight": "group or x value, repeatable, drawn larger in accent"},
        "budgets": {"points_rendered": 400, "groups": 8, "facets": 4, "series": "focal rule: 1 accent max"},
        "rules": ["non-negative data never shows a negative axis", "domain includes error bars",
                  "ticks are nice numbers aligned to grid",
                  "title and subtitle are drawn on the figure; the HTML page and the .svg are the same drawing"],
        "example": "diagonaldiagrams scatter examples/scatter_groups.csv --x dose --y expr --yerr expr_err --group tissue --facet cohort --xlabel Dose --xunit mg --ylabel Expression --yunit 'log2 counts' -o out/s.html",
    },
    "mermaid": {
        "input": "Mermaid text (.mmd): flowchart/graph, sequenceDiagram, or erDiagram",
        "writes": "diagonaldiagrams mermaid DIAGRAM.mmd -o OUT.svg   (flow, seq, or schema; checked and audited like a JSON spec)",
        "flowchart": {
            "nodes": "A[step]  A(step)  A([start or end])  A((start or end))  A{decision?}  A[(store)]",
            "arrows": "A --> B   A -->|label| B   A -- label --> B   A -.-> B (dashed)   A ==> B (focal)   A & B --> C",
            "groups": "subgraph id [Title] ... end",
            "focal": "A:::focal",
            "icons": "fa:fa-user, fa:fa-database, fa:fa-server, fa:fa-cloud ... in a label draw that glyph in the box",
        },
        "sequenceDiagram": "participant A as Name | actor U as User | A->>B: call | B-->>A: reply | A-)B: async event",
        "erDiagram": "A ||--o{ B : verb | A { type name PK }",
        "fit": "where the figure goes, as --fit: a line fit: column (or slide, page) in the front matter between --- lines",
        "not drawn": "classDef/style colors, notes, loop/alt blocks, LR direction (flows draw top-down)",
        "example": "flowchart TD\n  A([Push]) --> B{Risky?}\n  B -->|yes| C[Review]\n  B -->|no| D([Ship])\n  C --> D",
    },
    "icons": {"use": 'set "icon" on a flow or arch node', "names": sorted(ICONS)},
    "flow": {
        "input": "JSON spec {title, sub, nodes[], edges[], groups[]}",
        "writes": "diagonaldiagrams flow SPEC.json -o OUT.svg",
        "size": FIT,
        "node": {"id": "unique", "shape": "oval=start/end | rect=step | diamond=decision | dot=merge",
                 "name": "2-4 words", "tag": "optional kind, e.g. MANUAL (not STEP/START/END: the shape says it)", "sub": "mono sublabel", "rank": "row, 0 at the top (default: automatic)",
                 "lane": "-1 left|0 center|1 right (default 0)", "focal": "bool, max 2 per diagram"},
        "edge": {"from": "id", "to": "id", "label": "ALWAYS label decision exits", "focal": "happy-path bool"},
        "rules": ["top-down; a decision's branches sit side by side, loops draw back up the outside", "diamond ≤3 exits (nest for more)", "orthogonal elbows only",
                  "labels masked with 6px gap", "shape carries type, never color",
                  "no ranks needed: longest-path auto-layering + barycenter uncrossing (--auto forces it)"],
        "budgets": {"nodes": 9, "edges": 12, "focal": 2, "over": "a warning, not an error; split if it reads badly, or budget false hides it"},
        "example": '{"title":"Deploy approval","nodes":[{"id":"a","shape":"oval","name":"Push"},{"id":"d","shape":"diamond","name":"Risky?","rank":1,"focal":true}],"edges":[{"from":"a","to":"d","label":"pass"}]}',
    },
    "arch": {
        "input": "JSON spec {title, sub, nodes[], edges[]}",
        "writes": "diagonaldiagrams arch SPEC.json -o OUT.svg",
        "size": FIT,
        "node": {"id": "unique", "layer": "row int (default 0)", "name": "service", "sub": "Lang:port e.g. Go:8080",
                 "tag": "UI|API|SVC|STORE", "focal": "bool, max 2"},
        "edge": {"from": "id", "to": "id", "label": "VERB", "proto": "https=blue arrow", "async": "dashed bool", "focal": "bool"},
        "rules": ["blue=HTTP/API, dashed=async, coral=focal", "tech sublabels in mono, names in sans",
                  "a wide layer spreads the canvas so boxes do not overlap",
                  "set budget false to draw past 9 nodes and 12 edges; focal stays at 2"],
        "budgets": {"nodes": 9, "edges": 12, "over": "a warning, not an error; one view per C4 level, or budget false hides it"},
    },
    "seq": {
        "input": "JSON spec {title, sub, actors[], messages[]}",
        "writes": "diagonaldiagrams seq SPEC.json -o OUT.svg",
        "actor": {"id": "unique", "name": "label", "sub": "tech/mono sub", "tag": "USER|UI|GATEWAY|SVC|STORE", "focal": "bool, max 2"},
        "message": {"from": "id", "to": "id", "label": "Call name/payload", "proto": "https/grpc", "reply": "bool dashed", "async": "bool dashed", "focal": "bool"},
        "rules": ["solid=sync, dashed=reply/async, blue=http, coral=focal", "top-down sequence order", "max 6 lifelines"],
        "budgets": {"actors": 6, "messages": 16, "focal": 2, "over": "a warning, not an error; split into sub-sequences, or budget false hides it"},
        "example": '{"title":"Auth handshake","actors":[{"id":"u","name":"User"},{"id":"api","name":"API","focal":true}],"messages":[{"from":"u","to":"api","label":"login"}]}',
    },
    "schema": {
        "input": "JSON spec {title, sub, tables[], relations[]}",
        "writes": "diagonaldiagrams schema SPEC.json -o OUT.svg",
        "size": FIT,
        "table": {"id": "unique", "name": "table_name", "tag": "AUTH|CORE|AUDIT", "focal": "bool, max 2",
                  "columns": [{"name": "col", "type": "data_type", "pk": "bool", "fk": "bool", "unique": "bool"}]},
        "relation": {"from": "id", "from_col": "col", "to": "id", "to_col": "col", "label": "1:N|1:1|M:N", "focal": "bool"},
        "rules": ["PK coral badge, FK blue badge, columns in mono, types muted", "orthogonal elbow routing", "max 6 tables per view"],
        "budgets": {"tables": 6, "columns_per_table": 12, "over": "a warning, not an error; split by bounded context, or budget false hides it"},
        "example": '{"title":"Users & Teams","tables":[{"id":"u","name":"users","columns":[{"name":"id","type":"uuid","pk":true}]}],"relations":[]}',
    },
    "iso": {
        "input": "JSON spec {title, sub, layers[], links[]}: a layer stack drawn in isometric 3D",
        "writes": "diagonaldiagrams iso SPEC.json -o OUT.svg",
        "size": FIT,
        "columns": "1-8: how many items a row holds before it wraps (default 6; a fit with a max width picks one)",
        "layer": {"id": "unique", "name": "drawn left of its slab", "sub": "one short line under the name",
                  "items": "blocks standing on the slab, up to 24, wrapping into rows"},
        "item": {"id": "unique across layers and items", "name": "drawn on the block's top, wraps to 2 lines",
                 "sub": "tech/mono sub", "focal": "bool, max 2", "col": "0-7: the column it stands in (optional)",
                 "row": "0-7: its row, 0 at the front (optional)", "style": "this block's own style", "class": "for stylesheet rules"},
        "link": {"from": "item id", "to": "item id in any other layer", "label": "short",
                 "proto": "https=blue arrow", "async": "dashed bool", "focal": "bool"},
        "rules": ["layers top first; the top layer is drawn highest", "every slab shares one grid of columns",
                  "an item without col stands under the item it links to in a layer above, so links drop straight down",
                  "a link past a layer goes through a port in its slab; that cell stays free, and a block in the way is an error",
                  "stylesheets select a layer as group, an item as node, a link as edge: group#lake, node#api, edge:focal; "
                  "group::title and group::sub are a layer's name and sub",
                  "the audit reads depth: a label hidden behind a nearer face, a name running off its block's top, "
                  "a link crossing a block, and solids that run into each other are errors",
                  "validate with: diagonaldiagrams validate SPEC.json --type iso"],
        "budgets": {"layers": 8, "items_per_layer": 12, "focal": 2,
                    "over": "items past 12 warn (budget false hides it); past 24 items or 8 layers is an error"},
        "example": '{"title":"Platform","layers":[{"id":"apps","name":"Apps","items":[{"id":"web","name":"Web app"}]},'
                   '{"id":"data","name":"Data","items":[{"id":"db","name":"Postgres"}]}],"links":[{"from":"web","to":"db","label":"SQL"}]}',
    },
    "bar": {
        "input": "CSV with header row. One categorical column and one numeric column.",
        "writes": "diagonaldiagrams bar DATA.csv --cat CAT --val VAL -o OUT.svg",
        "options": {"--cat": "category column", "--val": "numeric value column", "--group": "subgroup column",
                    "--sort": "none|asc|desc", "--orientation": "v|h", "--unit": "unit string",
                    "--title/--subtitle": "drawn on the figure",
                    "--grid/--no-grid": "tick rules, on by default",
                    "--markers/--no-markers": "value labels, on by default",
                    "--highlight": "category or group, repeatable, drawn in accent",
                    "--ref": "VALUE or VALUE=label, repeatable: a dashed reference line, such as a target or 50%"},
        "budgets": {"bars": 24, "categories": 12, "over": "sort top-N + other"},
        "rules": ["bar charts must start at zero", "value labels sit on the bars", "gridlines follow the ticks",
                  "--unit % ends the axis at 100 and writes 85%"],
        "example": "diagonaldiagrams bar examples/bar_latency.csv --cat service --val p99_latency_ms --unit ms -o out/bar.html",
    },
    "line": {
        "input": "CSV with header row. Continuous/temporal X column and numeric Y column.",
        "writes": "diagonaldiagrams line DATA.csv --x X --y Y -o OUT.svg",
        "options": {"--x": "x column (numeric or timestamp)", "--y": "y column (numeric)", "--group": "series column",
                    "--xlabel/--xunit/--ylabel/--yunit": "axis labels",
                    "--title/--subtitle": "drawn on the figure",
                    "--grid/--no-grid": "tick rules, on by default",
                    "--markers/--no-markers": "point dots, on by default",
                    "--highlight": "x value or group, repeatable, drawn larger in accent",
                    "--ref": "VALUE or VALUE=label, repeatable: a dashed reference line"},
        "budgets": {"series": 6, "rows": 400, "over": "a warning, not an error; a series past 600 points is thinned for drawing"},
        "rules": ["non-negative data floors at 0", "Okabe-Ito series colors", "area fill only on a single series"],
        "example": "diagonaldiagrams line examples/line_throughput.csv --x timestamp --y rps --group service -o out/line.html",
    },
    "geo": {
        "input": "CSV with lat/lon columns, or a GeoJSON FeatureCollection of Points and Polygons.",
        "writes": "diagonaldiagrams geo DATA.csv --lat lat --lon lon --label name --val pop -o OUT.svg",
        "options": {"--lat/--lon": "column names (guessed from lat/lon/lng when omitted)",
                    "--label": "place name", "--val": "numeric size",
                    "--title/--subtitle": "drawn on the figure", "--source": "footer provenance",
                    "--grid/--no-grid": "graticule lines, on by default",
                    "--markers/--no-markers": "place dots, on by default",
                    "--highlight": "place name, repeatable, drawn larger in accent"},
        "budgets": {"points": 400, "over": "crop to the region you mean"},
        "rules": ["Web Mercator figure with a built-in coastline, not a tiled basemap",
                  "GeoJSON polygons are drawn on top of the coastline",
                  "graticule, kilometre scale bar, north arrow", "dot size follows --val"],
        "example": "diagonaldiagrams geo examples/geo_cities.csv --lat lat --lon lon --label city --val people_m -o out/geo.html",
    },
    "doc": {
        "input": "Markdown document containing ```graph:<type> fenced blocks.",
        "writes": "diagonaldiagrams doc DOC.md [--out-dir assets] [--check]",
        "behavior": "Parses and compiles embedded diagram specs into standalone SVGs in assets/, updates doc links",
    },
    "monitor": {
        "input": "Repository working tree or git history.",
        "writes": "diagonaldiagrams monitor [--base <ref>] [--ci] [--map graph.monitor.json]",
        "behavior": "Scans code changes for data models, routes, and migrations without corresponding diagram updates; outputs JSON drift report. With --map, extracts each changed file and semantically diffs against its spec (no diff = no drift, even if files changed).",
        "map_format": '{"mappings": [{"code": "models/*.py", "spec": "docs/schema.graph.json", "kind": "schema", "domain": "database"}]}',
    },
    "extract": {
        "input": "Code source file (.sql DDL, Python ORM model, FastAPI routes).",
        "writes": "diagonaldiagrams extract schema|routes SOURCE_FILE -o SPEC.json",
        "behavior": "Reverse-extracts architecture or database schema diagram specs directly from source code using AST/token parsing",
    },
    "export": {
        "input": "Receipt OUT.graph.json written beside every render.",
        "writes": "diagonaldiagrams export OUT --to png|pdf|svg [--layout figure|wide|slide|social] [--width 1600] [-o FILE]",
        "rules": ["svg works everywhere, zero deps (re-render from receipt)",
                  "layouts figure/wide/slide/social apply to scatter; other types export single layout",
                  "png and pdf use cairosvg when it imports, otherwise headless Edge or Chrome",
                  "the HTML page has Export PNG, which saves the figure from the browser"],
        "budgets": {"png_width_default": 1600},
        "example": "diagonaldiagrams export out/scatter --to svg --layout social",
    },
    "sync": {
        "input": "Same inputs as monitor (--path, --base, --map).",
        "writes": "diagonaldiagrams sync --map graph.monitor.json [--docs ARCH.md] [--commit]",
        "behavior": "Auto-fix bot: for each mapping-backed drift entry runs extract -o spec, validates, recompiles --docs, audits emitted SVGs. Default touches only the working tree; --commit creates a LOCAL commit (never pushes). Exit 1 if anything is left undone. Heartbeat: cron `0 6 * * * cd repo && diagonaldiagrams sync --map graph.monitor.json --commit`, Windows Task Scheduler, or an Antigravity cron//goal task.",
    },
}


DESCRIBE.update(_chart_meta())
DESCRIBE["story"] = {  # the command; `chart story`, a user story map, keeps its entry under "also"
    "input": "Story JSON: one figure and its views.",
    "writes": "diagonaldiagrams story STORY.json -o OUT.html [--svg OUT.svg] [--gif OUT.gif] [--video OUT.mp4] [--view ID] [--fps 20] "
              "(the figure itself is drawn as OUT.figure.svg)",
    "shape": {"title": "...", "figure": {"type": "flow|arch|seq|schema|iso|mermaid",
                                         "spec": "a path relative to the story file, or the spec itself"},
              "views": [{"id": "...", "title": "...", "text": "shown under the figure", "notes": "speaker notes (N)",
                         "focus": "selector: the camera frames it", "dim": "selector", "hide": "selector",
                         "highlight": "selector: accent color, heavier line", "reveal": ["one selector per step"],
                         "motion": [{"trace": "a -> b -> c (box ids)", "speed": "px/s, 320", "hold": "s, 1.2",
                                     "packet": "dot|dash", "color": "token or color, accent"},
                                    {"flow": "selector of arrows", "speed": "px/s, 60", "gap": "px, 24", "color": "link"}]}]},
    "rules": ["selectors are the stylesheet's (describe style): #id, group#id node, edge[from=a][to=b], :not(...); a comma lists several",
              "highlight undoes a dim; hide beats both; reveal shows each step at full strength, and an arrow once both its ends show",
              "a selector that matches nothing is a warning; every view has the same layout, so the page animates looks and camera",
              "keys: arrows, Space, Home, End; N shows the notes; a link to #view or #view/step opens it; printing gives a page per step",
              "motion (flow, arch, schema, iso): trace runs a packet along the arrows' routes and lights them; a hop may run against "
              "an arrow; flow runs dots along arrows; traces play in order and their total is the loop; P pauses",
              "--svg writes the first view with motion (or --view) as a seamless animated SVG, in pure Python; "
              "--gif and --video film it through ffmpeg"],
    "example": "diagonaldiagrams story examples/story_platform.json -o out/story.html",
    "also": {"chart story": DESCRIBE["story"]},
}


DESCRIBE["style"] = None  # built on request: it reads the style package, which most commands never load


def describe_style():
    """The style system, from the code that reads it, so this never drifts from what it accepts."""
    from .style import parse, select
    from .style.tokens import tokens

    def kind(k):
        return "|".join(k) if isinstance(k, tuple) else k
    return {
        "use": "--style FILE (repeatable; later files win) and --font FAMILY on flow, arch, seq and schema; a spec's "
               "\"style\" (one stylesheet or a list); an element's own \"style\"; options.style in MCP and the API",
        "sheet": {"name": "brand", "extends": ["editorial | ink | print"], "tokens": {"accent": "#7c3aed"},
                  "rules": {"SELECTOR": {"PROPERTY": "VALUE"}}},
        "cascade": "theme < preset < spec style < --style files < element style < policy; within one sheet the more "
                   "specific selector wins, then the later rule; text properties inherit",
        "selectors": "TYPE #id .class [attr] [attr=v] [attr!=v] [attr^=v] [attr>n] [attr<n] (fields, then data), "
                     "A B (descendant), A > B (child), :pseudo-class, ::pseudo-element",
        "types": list(select.TYPES),
        "pseudo_classes": [":" + p for p in select.PSEUDO_CLASSES],
        "pseudo_elements": ["::" + p for p in select.PSEUDO_ELEMENTS],
        "properties": {name: kind(k) for name, k in sorted(parse.PROPERTIES.items())},
        "values": {"color": "#rgb #rrggbb #rrggbbaa rgb() rgba() hsl() CSS names transparent tokens var(--token) "
                            "mix(a, b, 30%)",
                   "length": "a number (px), 12px, or 1.5em (of the element's font size), or a size token",
                   "border": "WIDTH STYLE COLOR in any order (solid dashed dotted double none), or none",
                   "padding, border-radius": "1 to 4 lengths, in CSS order",
                   "box-shadow": "X Y [BLUR [SPREAD]] COLOR [inset], comma-separated, or none",
                   "paint": "a color, or linear-gradient(ANGLE | to SIDE, COLOR [STOP%], ...)",
                   "encoding": "{\"field\": \"p99\", \"scale\": {...}}: the value comes from each element's data"},
        "sides": {"rect, oval, table": ["top", "right", "bottom", "left"],
                  "diamond": ["top-left", "top-right", "bottom-right", "bottom-left", "(top, right, bottom, left: two edges each)"]},
        "tokens": sorted(k for k, v in tokens("editorial").items() if not isinstance(v, list)),
        "palettes": sorted(k for k, v in tokens("editorial").items() if isinstance(v, list)),
        "example": {"rules": {"node": {"border-top": "3px solid accent"},
                              "node[team=pay]": {"border-left": "4px solid #e11d48"},
                              "edge.critical": {"stroke": "accent", "stroke-width": 2.5},
                              "edge::label": {"text-transform": "none"}}},
    }


def do_describe(args):
    if args.type == "style":
        print(json.dumps(describe_style(), indent=2))
        return 0
    print(json.dumps(DESCRIBE[args.type], indent=2) if args.type else json.dumps({"types": sorted(DESCRIBE)}, indent=2))

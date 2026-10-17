# diagonaldiagrams 2: design

Status: proposal, 2026-10-12. The phased work is in [PLAN.md](PLAN.md).

This document describes where the engine is going: what an agent can ask for, how the engine is built to deliver it, and what stays compatible on the way. It is written for whoever implements it, human or agent.

## 1. Goals

The north star: **an agent can render whatever it can describe.** Any structure, any arrangement, any font, any color, a border on the top edge only or the left edge only, a highlighted path, a chart inside a box, an isometric 3D view. The agent composes figures from parts. It does not pick from a menu of hard-coded types, and nobody has to build a renderer first.

Beyond that: **post-legacy.** The goal is to make slide software obsolete, not to export to it.

- **The scene is the document.** A deck, a report figure, a dashboard and a poster are views of one model, rendered for whatever medium the viewer is using.
- **Nobody edits pixels.** People and agents change intent. A human's direct edit is recorded in the spec, so it survives the next regeneration.
- **Built for models that keep getting stronger.** The engine never sets the ceiling on what a model can express.

Sections 20–22 describe this layer. The engine in sections 3–17 is its foundation.

Measured against today:

| Goal | Today | Target |
| --- | --- | --- |
| A. Informative | 68 places truncate text; diagram budgets warn past 9 nodes and chart caps refuse to draw; legends are fixed sentences; the `_c_*` charts get no outline | No truncation; size handled by layout; legends built from what is drawn; annotations and outlines on every type |
| B. Looks good | Only flow, arch, seq and schema use the house style; 66 `_c_*` renderers draw with hard-coded positions | Every type shares the same parts, tokens and router |
| C. Fast | 0.37–0.52 s per CLI call, mostly recompiling a 10k-line script (0.16 s when imported from bytecode); a 40-step flow takes 3.5 s through 225 layout redraws; 61 s for the slowest 60-node fuzz scene | ≤150 ms per call; ≤100 ms layout for 40 nodes; checks run in memory |
| D. Modular | One 10k-line file; styling is 9 colors and 3 corner choices; ~170 inline font settings | A package with one scene format, a style system, and toolkits that plug into fixed extension points |

### Non-goals

- Raster graphics, photo editing, or map tiles.
- A general-purpose vector editor. The engine places and checks; it does not offer free-form drawing beyond what `defs` and raw SVG node bodies allow.
- Full CSS. The style system uses CSS names and syntax for a defined subset (section 5.4).
- Full Vega-Lite. The charts toolkit accepts a defined subset (section 12).

## 2. Decisions

Each decision has a reason. Changing one should mean updating this list.

| # | Decision | Reason |
| --- | --- | --- |
| D1 | The core stays standard-library only. Optional extras (cairosvg) stay optional. | Installs in any agent sandbox and in Pyodide. |
| D2 | Python ≥ 3.11. | 3.9 is end-of-life, and 3.10 reaches end-of-life in October 2026. 3.11 adds `tomllib` for the project config (22.4) and is faster. Pyodide runs 3.12. |
| D3 | Borrow languages Claude already knows: CSS names and selectors for style, Vega-Lite for charts, Mermaid for quick structure, flexbox and grid ideas for arrangement. | Agents write them correctly without a `describe` round trip. |
| D4 | Three separate questions: **what** (scene), **where** (layout), **how it looks** (style). Toolkits extend any of them. A diagram type is a preset that combines them. | Lets the agent change one without touching the others, and removes per-type renderers. |
| D5 | The **display list** is the internal truth. SVG is one output format. | The audit, the outline and every exporter read the same in-memory geometry. Nothing re-parses its own SVG. |
| D6 | Layouts are correct by construction. The audit is a safety net, not a repair loop. | Removes the redraw-and-reparse loop (57 redraws at 40 steps). Fuzz tests hold layouts to zero audit errors. |
| D7 | Same input, same bytes out, on every machine. | Agents can diff output; tests can use golden files. Measurement uses bundled metrics unless a font file is named, and the receipt records which. |
| D8 | Specs are data and never execute code. Code toolkits load only from installed packages or a CLI flag. | Specs arrive from agents, MCP clients and docs. |
| D9 | Every existing command, flag, input format, JSON verdict field, `data-*` attribute and receipt keeps working. | Agents, the plugin, the MCP registry entry and the site depend on them (section 14). |
| D10 | One extension mechanism for built-in and third-party parts. Built-ins are toolkits too. | If the built-ins can be written as toolkits, so can anything else. |
| D11 | Errors are typed (`SpecError(code, msg, fix, at)`), never `SystemExit` from inside the engine. | The MCP server and Python API can run in-process and still return structured errors. |
| D12 | The spec is the source of truth. A human's direct edit becomes a spec patch (a constraint, a style rule, a text change), never a pixel change. | Edits survive regeneration. Agents can read an edit as intent ("payments was moved left of auth"). |
| D13 | The engine computes; the model judges. The engine owns measuring, solving, rendering, checking and scoring. Taste lives in presets, stylesheets and advisory checks, and all of it can be overridden. | A stronger model needs a precise substrate and a verifier, not rules. Today's "non-negotiable" taste rules in SKILL.md become defaults. |
| D14 | No capability ceiling. Budgets are advice. Every default has an override. Every level is reachable: intent (preset) → structure (scene) → geometry (pins, custom paths) → raw (SVG node bodies, code toolkits). | A weak model stays at the top level; a strong one goes as low as it needs, on the same artifact. |
| D15 | Stable identity. Elements keep their ids across edits and renders, and layout is incremental: a small change moves little. | Needed to animate between views, to keep a reader's mental map, to apply human edits, and to diff versions. |
| D16 | Self-describing and versioned. Models learn the engine at runtime from `describe` and the JSON Schema, not from training data. | New capabilities are usable the day they ship, by models trained before they existed. |
| D17 | Legacy formats are bridges. Import comes first (PPTX, VSDX, draw.io, PlantUML, Mermaid) so organizations can move their material in. Export (PDF, PNG, flat PPTX) is a fallback for people who haven't moved yet. The core never bends to a legacy format's limits. | The future medium is a link to a live document, not an attachment. |
| D18 | Agents may extend the engine with code. A toolkit written by the local agent is allowed with explicit opt-in (`--toolkit` or the project config). Specs from anywhere else stay data-only (D8). The audit, golden files and fuzz harness are how an agent tests its own toolkit. | A stronger model should be able to add a missing layout itself, safely. |

## 3. Architecture

### 3.1 Pipeline

```
 inputs ─┐  v1 JSON (flow/arch/seq/schema/chart kinds), Mermaid, CSV, GeoJSON, Vega-Lite, scene JSON
         ▼
 normalize ──► Scene (what): figure → containers → nodes, edges, groups, marks, annotations
         ▼
 cascade ────► computed style for every element and pseudo-element (how it looks)
         ▼
 measure ────► text blocks sized with real font metrics; shapes report their content boxes
         ▼
 layout ─────► positions, per container, bottom-up measure then top-down place (where)
         ▼
 route ──────► edge paths, ports, label positions
         ▼
 project ────► 2D identity, or isometric/perspective when the 3D toolkit is in use
         ▼
 paint ──────► DisplayList: flat, z-ordered items, each tagged with owner and role
         ▼
 audit ──────► issues with code, message, fix, location, and the style rule or spec field to change
         ▼
 emit ───────► SVG, HTML, PNG/PDF, draw.io, Excalidraw, receipt, outline (and three.js HTML for 3D)
```

Each stage is a function from the previous stage's output to its own, with no shared mutable state. Today's side channels (`route_edge.last_pts`, `_render_flow_once.pos`, `_raster_svg.why`, `_land_rings.cache`) become return values or explicit caches.

### 3.2 Where each goal lives

- **Informative:** encodings and legends (5.7), annotations (4.7), nesting (4.5), outline v2 (10).
- **Looks good:** tokens and stylesheets (5), measured text (6), layout kernels (7), router (8), decorations (5.5).
- **Fast:** package with lazy toolkits (15), in-memory audit (9), layouts without repair loops (D6), in-process MCP (14.3).
- **Modular:** the scene seam (4), the display list seam (8.3), toolkits and registries (11).

## 4. The scene format

A scene is JSON. Every field is optional except what a preset requires. Field names follow the existing specs where they exist (`name`, `sub`, `tag`, `from`, `to`), so v1 specs are already close to valid scenes.

### 4.1 Figure

```jsonc
{
  "version": 2,
  "title": "Checkout platform",
  "subtitle": "One sentence that states the finding.",   // alias: "sub", as in v1 specs
  "source": "service catalog, 2026-10",
  "caption": "",
  "preset": "arch",                    // optional; sets layout, style and defaults
  "use": ["c4", "3d"],                 // toolkits, in cascade order
  "size": { "width": 960, "aspect": "16:9", "max-height": 1600 },
  "style": "brand.json",               // or an inline stylesheet object, or a list of both
  "defs": { },                         // data-defined shapes, presets, icons, markers, scales (11.4)
  "data": { "lat": { "csv": "lat.csv" } },
  "layout": "layered",                 // or { "type": "layered", "direction": "right", ... }
  "space": { },                        // 3D toolkit only (13)
  "nodes": [], "edges": [], "groups": [],
  "constraints": [], "annotations": [],
  "legend": "auto",                    // "auto" | false | { "position": "bottom", "title": "..." }
  "budget": true                       // false lifts advisory size limits
}
```

### 4.2 Node

```jsonc
{
  "id": "api",
  "name": "API gateway",               // alias: "label"
  "sub": "Envoy:443",
  "tag": "edge",
  "icon": "shield",
  "shape": "rect",                     // any registered or defs shape
  "class": "svc hot",
  "data": { "team": "pay", "p99": 182 },   // free attributes for selectors and encodings
  "style": { "border-left": "4px solid #e11d48" },
  "group": "runtime",                  // membership; or list the node in a group's members
  "content": { },                      // a nested container: a chart, a sub-diagram, a table (4.5)
  "ports": [{ "id": "in", "side": "w" }],
  "focal": true,
  "rank": 2, "lane": -1, "order": 0,   // layered layout hints, as today; "layer" is an alias of "rank" (arch)
  "pin": { "x": 120, "y": 80 }         // v1 schema tables' "x"/"y" map here
}
```

Text fields accept `\n` for line breaks and a small inline markup: `**bold**`, `_italic_`, and `` `mono` ``. Everything else is literal.

### 4.3 Edge

```jsonc
{
  "id": "e1",
  "from": "api", "to": "auth",
  "from-port": "out", "to-port": "in",
  "label": "verify",
  "labels": [{ "text": "1", "at": "start" }, { "text": "N", "at": "end" }],
  "proto": "https",                    // as today: a value starting with "http" draws in the link color
  "async": false, "reply": false,      // as today: dashed
  "class": "critical",
  "data": { "rps": 1200 },
  "style": { "stroke-width": { "field": "rps", "scale": { "range": [1, 6] } } },
  "router": "orthogonal",              // orthogonal | straight | spline | registered
  "route": [[320, 140], [320, 260]],   // optional explicit waypoints; the router only connects them
  "focal": false
}
```

### 4.4 Group

```jsonc
{ "id": "runtime", "name": "Agent runtime", "members": ["agent", "memory"],
  "parent": "platform", "layout": "row", "class": "zone", "style": { } }
```

A group is a container drawn as a frame. Groups nest through `parent`. A group may set its own `layout`; members are laid out inside it and the group is placed as one block by its parent.

### 4.5 Containers and nesting

Internally every scene is a tree of containers. The figure is the root container. Groups are containers. A node with `content` holds a container. Any container can use any layout, including a chart's data space:

```jsonc
{ "id": "api", "name": "API", "content": {
    "mark": "line", "data": { "csv": "p99.csv" },
    "encoding": { "x": { "field": "t", "type": "temporal" }, "y": { "field": "ms" } },
    "size": "sparkline" } }
```

A dashboard is the root container with `"layout": "grid"` and charts or diagrams as children. Small multiples are a grid of the same chart over facets.

`content` may also be raw SVG: `{"svg": "<g>…</g>", "viewBox": "0 0 24 24"}`.
- It is sanitized: no `<script>`, no event handlers, no external references, no `foreignObject`.
- It is scaled into the node's content box.
- It is audited like any other item.

This is the lowest level of control (section 20.3).

As built in P2.18, `sanitize.py` keeps an allowlist rather than blocking known-bad parts:
- **Elements:** drawing elements only (`g`, `path`, shapes, `text`, gradients, `clipPath`, `mask`, `pattern`, `marker`, `use`, ...). No `script`, `foreignObject`, `a`, `image`, `iframe` or `style`.
- **Attributes:** presentation and geometry attributes only, never `on*` handlers.
- **References:** `href` and `url(...)` may point only within the fragment (`#id`). Any `javascript:`, `data:`, `expression(` or `@import` value is removed.
- **Refused outright:** a DOCTYPE or entity declaration, markup that is not well-formed, and anything over 200,000 characters or 5,000 elements.
- **Reporting:** normalize stores the cleaned markup and names what it removed in an `svg-sanitized` warning. Drawing content inside a node comes with the container layouts (P4); until then it is a `not-drawn` warning.

### 4.6 Constraints

Constraints guide layouts that understand them. A layout that cannot honor one reports an issue with code `constraint` instead of ignoring it.

| Constraint | Meaning |
| --- | --- |
| `{"same-rank": ["a", "b"]}` | Same layer in a layered layout. |
| `{"order": ["a", "b", "c"]}` | Fixed left-to-right (or top-to-bottom) order within a layer, row or column. |
| `{"above": ["a", "b"]}` | `a` is in an earlier layer than `b`. |
| `{"align": ["a", "b"], "axis": "x"}` | Shared center line. |
| `{"pin": "a", "x": 0, "y": 0}` | Fixed position in the container's coordinates. |
| `{"together": ["a", "b", "c"]}` | Kept contiguous without drawing a frame. |

**As built: a node's `pin` in flow and arch (layered).** The boxes of a layered figure stand in rows, so a pin there names a row and a place in it, not a free point.
- **Coordinates:** the box's middle, in the figure's coordinates, as `--outline` gives each node's `x` and `y`. (A v1 schema table's `x` and `y` are its top-left corner, as v1 drew them.)
- **The row:** `y` picks the layer whose middle is nearest in the figure drawn without its pins. In a wrapped flow, it is the nearest layer of the column that `x` falls in. The pin beats the node's own `rank`, `layer`, `lane` and `order`.
- **The place:** the row's other boxes keep their order, and the pinned box goes in where `x` falls among them. Its middle then stands at `x` exactly. What lies in its way moves over by as little as the gaps allow: boxes and arrows in its layer, a frame (which moves or widens), and an arrow that runs straight (which moves whole).
- **The rest stays put.** The other boxes keep their places from the figure drawn without pins, as nearly as the layout allows, and no row moves up. A row moves down only when new arrows need more room above it, and a row that a pinned box leaves empty stays as blank space. A wrapped flow breaks into columns where it did. The canvas grows to the right for a pin past its edge, and a pinned figure is not centered in its least width.
- **When a pin can't hold,** the render's verdict carries a `constraint` warning that names the node, where it was pinned and where it is drawn:
  - the box would cross the canvas's left edge;
  - another pinned box holds the room it needs;
  - its middle ends up more than half its height from `y`: `y` is far from every row, or its row moved down;
  - a `same-rank` or `order` constraint gives way to the pin.
- **Edits.** A `place` patch drops the node's pin, so a drag in the page still moves a pinned box (21.3).
- **Not exact points.** A box between two rows would sit on the tracks the arrows turn in, and nothing would route around it. Free placement is the `manual` layout's (7.2), with its overlap checks.

### 4.7 Annotations

Annotations target elements with selectors (5.2), so they work on every type.

| Type | Example | Draws |
| --- | --- | --- |
| `note` | `{"type": "note", "target": "#api", "text": "Rate limited"}` | A note in the side rail with a leader line (today's `notes`). |
| `callout` | `{"type": "callout", "target": "#db", "text": "Single point of failure"}` | A pinned callout next to the target. |
| `highlight` | `{"type": "highlight", "target": "edge[from=api]"}` | Adds class `highlight`; the stylesheet decides how it looks. |
| `bracket` | `{"type": "bracket", "targets": ["a", "b", "c"], "text": "Phase 1"}` | A bracket spanning the targets. |
| `band` | `{"type": "band", "axis": "x", "from": "2026-03", "to": "2026-05", "text": "Outage"}` | A shaded band in a chart. |
| `rule` | `{"type": "rule", "y": 200, "text": "SLO"}` | A reference line in a chart. |

### 4.8 Normalization

`scene/normalize.py` reads scene JSON into the model in `scene/model.py`. It collects every problem with the JSON path it sits at (`nodes[2].id`), so an agent fixes them in one pass.

- **Aliases.** `label` for `name`, `sub` for `subtitle` (figure), `subtitle` for `sub` (node), `layer` for `rank`, and a group's `nodes` for `members`. When both an alias and its field are given and they differ, the field wins with an `alias-conflict` warning.
- **Defaults.** A node's `name` defaults to its `id`, and a node with a name but no id takes the name as its id. Numbers are accepted as ids and read as strings.
- **Groups.** Membership may be listed on the group (`members`) or on the node (`group`); both are merged. A `group` naming an undeclared group creates it, as v1 does. A node in two groups, an unknown member, an unknown or cyclic `parent` are errors; an empty group is a warning.
- **Edge ids (D15).** An edge without an `id` gets one from what it connects and says: `from->to`, then `:label` when it has one, then `#2`, `#3` for repeats. Adding an edge elsewhere never renames another.
- **Unknown fields** are kept in the element's `extra` and written back, so a toolkit can read them. A name close to a known field gets an `unknown-field` warning ("did you mean 'focal'?").
- **Error codes:** `bad-value`, `missing-id`, `duplicate-id`, `missing-end`, `unknown-node`, `unknown-group`, `two-groups`, `group-cycle`, `version`, `preset`. **Warning codes:** `alias-conflict`, `unknown-field`, `id-clash`, `empty-group`, `unknown-port`, `unknown-constraint`, `unknown-annotation`, `unknown-target`, `not-drawn`.

Until the layout kernels read scenes (P4), a scene with preset `flow`, `arch`, `seq` or `schema` is drawn by turning it back into the v1 spec that preset's renderer reads (`inputs/v1.py`, `to_v1`). What that renderer can't draw yet (styles, classes, constraints other than arch row order, annotations other than notes) comes back as `not-drawn` warnings rather than being dropped silently. For every v1 spec in the golden corpus, and for generated ones, v1 → scene → v1 draws the same bytes (`scripts/scene_roundtrip.py`).

## 5. Style system

### 5.1 Stylesheets and the cascade

A stylesheet is JSON:

```jsonc
{
  "extends": ["editorial"],
  "font": "IBM Plex Sans",
  "tokens": { "accent": "#7c3aed", "paper": "#0f1117" },
  "rules": {
    "node":            { "border-top": "3px solid accent" },
    "node[team=pay]":  { "border-top": "none", "border-left": "4px solid #e11d48", "legend": "Payments team" },
    "node.db":         { "shape": "cylinder" },
    "edge.critical":   { "stroke": "accent", "stroke-width": 2.5 },
    "edge::label":     { "text-transform": "none", "font-weight": 600 },
    "group":           { "border": "1px dashed muted", "label-position": "top-left" }
  }
}
```

Order, lowest to highest priority:

1. Core defaults.
2. Theme (`editorial`, `ink`, `print`, or a file). Today's `--theme` and `--theme-file` map here.
3. Toolkit stylesheets, in `use` order.
4. Preset stylesheet.
5. Stylesheet files from `--style a.json b.json` or the figure's `style` field.
6. Inline `style.rules` in the spec.
7. An element's own `style`.
8. **Policy** (section 22.4): an organization's locked brand rules, loaded from the project config. Agents cannot override it; the `off-brand` check reports attempts.

Within one sheet, higher selector specificity wins, then later rules. There is no `!important`.

### 5.2 Selectors

A CSS subset plus graph-aware pseudo-classes:

- Types: `figure`, `node`, `edge`, `group`, `chart`, `mark`, `axis`, `legend`, `annotation`, `*`.
- `.class`, `#id`.
- Attributes: `[attr]`, `[attr=value]`, `[attr!=value]`, `[attr^=prefix]`, and numeric `[attr>n]`, `[attr<n]`. Attributes resolve against the element's fields first, then its `data`. Edges expose `from`, `to`, `proto`, `async`, `reply` and `label`, so the v1 rule "http is blue" is the stylesheet rule `edge[proto^=http] { stroke: link }`.
- Combinators: descendant (space) and child (`>`).
- Pseudo-classes: `:focal`, `:source` (no incoming edges), `:sink` (no outgoing edges), `:first-child`, `:last-child`, `:nth-child(n)`, `:not(sel)`.
- Pseudo-elements: `::label`, `::sub`, `::tag`, `::icon`, `::title` (group or figure), `::header` (table), `::marker-end`, `::marker-start`.

Unknown selectors and properties are errors with a did-you-mean fix, never silently ignored.

### 5.3 Values

- **Colors:** `#rgb`, `#rrggbb`, `#rrggbbaa`, `rgb()`, `rgba()`, `hsl()`, CSS named colors, token names (`accent`, or `var(--accent)`), and `mix(a, b, 30%)`.
- **Lengths:** plain numbers are px. `em` is relative to the element's font size.
- **Shorthands:** `border`, `border-<side>`, `border-radius` (1 to 4 values), `padding`, `box-shadow`, `font`, `linear-gradient(...)`.
- **Encodings:** any value may be `{"field": ..., "scale": ...}` (5.7).

### 5.4 Properties

| Applies to | Properties |
| --- | --- |
| Box and shape | `shape`, `width`, `height`, `min-width`, `max-width`, `padding`, `fill` (alias `background`), `stroke`, `stroke-width`, `border`, `border-top`, `border-right`, `border-bottom`, `border-left`, `border-style` (solid, dashed, dotted, double, none), `border-radius`, `box-shadow`, `opacity`, `glow`, `pattern` (hatch, dots, grid), `sketch` (hand-drawn, seeded) |
| Text | `font-family`, `font-size`, `font-weight`, `font-style`, `color`, `text-align`, `text-transform`, `letter-spacing`, `line-height`, `max-lines`, `overflow` (`wrap` by default, or `shrink`; never truncation unless `ellipsis` is asked for), `label-position` |
| Edge | `stroke`, `stroke-width`, `stroke-dasharray`, `marker-start`, `marker-end` (arrow, open, diamond, circle, crow-many, crow-one, none), `router`, `corner-radius`, `bundle` |
| Icon | `icon`, `icon-position`, `icon-color`, `icon-size` |
| Figure | `background`, `padding`, `title-align`, `legend-position` |
| 3D (toolkit) | `depth`, `elevation`, `material`, `shading` |

Toolkits register more properties through the same mechanism (11.2).

### 5.5 Decorations and named sides

Shapes expose their outline split into named sides. A rectangle has `top`, `right`, `bottom` and `left`. A cylinder has `top` (the ellipse), `left`, `right` and `bottom`. A diamond has `top-left`, `top-right`, `bottom-right` and `bottom-left`. A `defs` shape declares its own.

`border-<side>` paints only that part of the outline, following rounded corners correctly. Corner handling: a side's stroke ends at the middle of each adjacent corner arc. Asking for a side a shape doesn't have is a validation error that lists the sides it does have.

Other decorations (shadow, glow, gradient, hatch, sketch) are painters that take the outline and the computed style and return display-list items. They work on every shape.

As built in P3.4 (`deco.py`):
- **Sides:** rect, oval and table shapes have top, right, bottom and left. A diamond has top-left, top-right, bottom-right and bottom-left, and also answers to the generic sides, each naming two of its edges, so `node { border-top: ... }` reads on every shape.
- **Painting sides:** once any `border-*` is set, the outline is drawn side by side:
  - a declared side with its own width, style (solid, dashed, dotted, double) and color;
  - the rest with the shape's stroke;
  - a `none` side not at all.
  `validate` reports a side the shape doesn't have.
- **Radii:** `border-radius` takes 1 to 4 values. Unequal corners draw the box as a path, which the outline, exports and audit still read as the node.
- **Decorations:**
  - a `linear-gradient` fill;
  - outer `box-shadow` (inset shadows are not drawn yet);
  - `glow`;
  - `pattern` (hatch, dots, grid);
  - `opacity`.
  Each definition is content-hashed and moved into the figure's single `<defs>`. `sketch` is not built yet.

### 5.6 Tokens and themes

Tokens are named values. The existing 9 theme keys stay and are joined by type, spacing and palette tokens:

- **Color:** `paper`, `ink`, `muted`, `soft`, `rule`, `accent`, `accent-tint` (v1 theme files may write `accent_tint`), `link`, `card`, `shade-light`, `shade-dark`.
- **Type:** `font`, `font-mono`, `size-xs` 11, `size-s` 12, `size-m` 13, `size-l` 15, `size-xl` 20, `size-title` 22.
- **Space:** `space-1` 4 through `space-6` 48. `radius` 8, `stroke` 1.4, `stroke-strong` 1.8.
- **Palettes:** `categorical` (Okabe–Ito), `sequential`, `diverging`, and the dark variants.

Themes are stylesheets. `editorial`, `ink` and `print` ship as `themes/*.json`. A brand stylesheet is one file that restyles every preset.

### 5.7 Encodings, scales and legends

Any style value can come from data:

```jsonc
"node": { "fill": { "field": "p99", "scale": { "type": "sequential", "scheme": "heat", "domain": [0, 500] } } },
"edge": { "stroke-width": { "field": "rps", "scale": { "type": "linear", "range": [1, 6] } } }
```

Diagram styling and chart encodings use the same scale code (section 12).

Legends come from what was actually used:

- every rule with a `legend` text;
- every scale used by an encoding;
- every shape whose meaning the preset declares, but only if that shape appears.

A flowchart with no ovals no longer says "rounded = start or end". `"legend": false` turns legends off.

As built in P3.7:
- **Scales:** a scale's type is inferred when not given: numbers on a color are sequential, words are categorical, numbers on a numeric property are linear. Color ranges come from a scheme (`heat`, `blues`, `greens`, `greys`), a palette token or a list.
- **Legend:**
  - The preset's sentence names colors as drawn (`color_word`), so a brand's teal says "teal = HTTP call".
  - Swatch rows follow: each scale's low, middle and high (or each category), and each rule's `legend` text beside the look it names (a side's border, else the fill).
- **Readable text:** text whose color still comes from the theme or preset is checked against its node's fill. Below 4.5:1 it switches to ink or paper, whichever reads better. A color set by a later stylesheet or the element is left alone for the contrast check.

## 6. Text and fonts

### 6.1 Measuring

`text/fonts.py` reads TrueType and OpenType files with `struct`:

- `cmap` (formats 4 and 12), `hmtx` and `hhea` for advance widths;
- `head` for units per em;
- `OS/2` for ascent, descent, x-height and cap height;
- `kern` (format 0) when present;
- `.ttc` collections and zlib-compressed WOFF 1.

WOFF2 needs Brotli and is not supported. GPOS kerning is ignored, which errs slightly wide.

Shaping is an extension point (`shaper`, section 11.1):
- The built-in shaper handles Latin, Greek, Cyrillic and CJK, plus right-to-left reordering for Arabic and Hebrew, using the Unicode bidi classes in `unicodedata`.
- Scripts that need contextual shaping (Arabic joining, Devanagari, Thai) use an optional HarfBuzz-backed shaper (the `shaping` extra), or a browser-measuring shaper when a headless browser is available.
- Without either, the `shaping` warning says the widths are approximate.

**Font lookup:**

- **Bundled metrics:** `data/metrics/*.json` holds advance widths for a fixed set of open fonts: Inter, Selawik (metric-compatible with Segoe UI), Roboto, DejaVu Sans, Liberation Sans (metric-compatible with Arial), and a monospace font.
- **Named fonts:** a named font is looked up in the OS font directories and the user's font folders, then indexed by its `name` table. The index is cached in the user cache directory.
- **Default system stack** (`system-ui, ...`): measured as the widest of the bundled metrics. Text then fits whichever font the viewer actually has.
- **Determinism:** if a named font isn't found, the engine falls back to bundled metrics and issues a `font-fallback` warning. The receipt records the metrics used (family plus file hash).

As built in P3.5 (part 1):
- **Lookup:** a font family list is resolved left to right. A name a stylesheet maps to a file in its `"fonts"` comes first, then installed fonts by family, weight and style. A generic first family (`system-ui`, `sans-serif`, `serif`, `monospace`) stops the lookup: the default stack keeps the built-in estimate, so figures don't depend on the machine.
- **Fallback:** a named font that isn't found marks its text with `data-font-fallback`, and the audit warns once per font.

### 6.2 Layout of text

- Wrap at word boundaries. Break inside a word only if one word is wider than the box.
- Boxes grow to fit, up to `max-width`, then grow in height.
- `max-lines` caps the line count; past it the box grows instead of cutting text, unless the style asks for `ellipsis`.
- Any truncation is reported by the `truncated` check, so it is always visible.

As built in P3.6:
- **Boxes:** box text wraps at the node's computed `font-size` and weight, with a line pitch from `line-height` (presets: 1.25 for labels, 4/3 for subs).
- **Overflow:** `wrap` (the default) keeps every line and grows the box. `shrink` lowers the size in half-pixel steps to 9 px until `max-lines` fits. `ellipsis` cuts at `max-lines`.
- **Markup:** marked-up text wraps word by word with each run measured in its own style, and is drawn as tspans. An underscore is markup only at a word's edges.
- **Measuring:** widths still come from the built-in estimate; measured fonts arrive in P3.5.

### 6.3 Embedding

`font-embed: true` (or `--embed-fonts`) embeds the font file as a data URI `@font-face` in the SVG or HTML, for PNG/PDF export and for exact rendering elsewhere. Subsetting is a later improvement (PLAN P3.5b); until then the whole file is embedded and a `large-font` warning reports its size.

## 7. Layout

### 7.1 Protocol

```python
class Layout(Protocol):
    name: str
    options: Schema                       # validated; drives describe and JSON Schema
    def measure(self, ctx, container) -> Size: ...          # bottom-up: children are already measured
    def place(self, ctx, container, box) -> Placement: ...  # top-down: positions in the container's coordinates
```

A `Placement` holds child positions (x, y, and optional z for 3D), container-local ports, and any constraint issues. A layout never paints.

### 7.2 Kernels

| Layout | Use | Notes |
| --- | --- | --- |
| `layered` | Flowcharts, architecture, state machines, BPMN, swimlanes, DAGs, C4 | Sugiyama method: <ul><li>remove cycles with a greedy feedback arc set, keeping today's rule that a loop's start stays on top;</li><li>assign layers by longest path, compacted with network simplex;</li><li>add dummy nodes for long edges;</li><li>reduce crossings with median/barycenter sweeps plus transposition, several passes;</li><li>assign coordinates with Brandes–Köpf.</li></ul> Directions TB, LR, BT, RL. `lanes` partitions by an attribute. Groups are compound clusters kept contiguous. `wrap` folds long chains into columns to meet the target aspect ratio. |
| `tree` | Org charts, decision trees, file trees, dendrograms | Walker's tidy tree (Buchheim's linear-time version); radial variant. |
| `stack` | Rows and columns of anything | Flexbox semantics: `direction`, `gap`, `align`, `justify`, `wrap`. |
| `grid` | Kanban, story maps, dashboards, small multiples | `columns`, `rows`, `gap`, named `areas`. |
| `radial` | Flywheels, hub and spoke, rings | Even angular spacing; a hub in the middle. |
| `force` | Knowledge graphs, coupling maps | Deterministic seeded layout, then overlap removal. |
| `sequence` | Sequence diagrams | Lifelines, messages, activations, and `loop`/`alt`/`opt` fragments. |
| `table` | Schemas, ER diagrams, UML classes | Rows become ports, so relations attach to columns. |
| `timeaxis` | Gantt charts, timelines, journeys | Places items on a time scale. |
| `scale` | Charts | A data coordinate space with scales and axes (12). |
| `manual` | Pinned figures | Uses `pin`; checks for overlap. |

### 7.3 Size targets

`size.width` and `size.aspect` are passed to the root layout. `layered` uses them to choose `wrap` and spacing; `grid` uses them to choose columns. A 40-step flow lands in columns near the target aspect instead of one 5000 px strip.

**As built (P4, layered):** `layout/` holds the kernel.
- **Ranks (`rank.py`):** cycles are broken by v1's depth-first walk, so a loop's start stays on top. Unpinned ranks are the longest path, compacted by the network simplex for parts up to 400 nodes. Pinned ranks (flow `rank`, arch `layer`) are kept, made dense.
- **Order (`order.py`):** each layer holds nodes, dummies (a long arrow passing a layer), port items (where a back edge turns beside its node) and a left and right border for every group spanning it. Layers sort as a tree, so groups stay whole and sibling groups keep one order in every layer. Barycenter sweeps and transposition keep the best of up to 24 passes. Each port is then tried on the other side of its node.
- **Coordinates (`bk.py`):** Brandes–Köpf, with group borders forced into one block per side, so frames are rectangles that hold their members and nothing else (B20). A decision's branches stand beyond its side vertices. A labelled arrow within a layer gets room for its label between its ends. With frame borders between them, the widest stretch between two borders holds it. A back edge's port item or a long arrow's dummy between them counts in its stretch (B30).
- **Routes (`layered.py`, `channels.py`):** an arrow leaves by a port, runs straight through its dummies, and turns in the gaps between layers. Each turn has a track of its own, assigned per gap (B21). A gap is as tall as its tracks need, so nothing is moved afterwards. Back edges either climb beside their nodes through port items (flow, B19, B23) or run from the top of the lower node to the bottom of the upper one (arch, `back: "ports"`). Two arrows that would trade columns in a gap get a dogleg; three or more whose track rules form a cycle give up the loosest rule (B29). A decision side whose exits would turn down inside the box beside it sends its exit with the nearest target out of the bottom vertex. A side exit turns down clear of every port item and dummy in its layer, any node's, not only its own (B30).
- **Label room (`room.py`):** after the routes and wrap, each label is placed as the renderer will place it. A label with no spot clear of boxes, frame borders, earlier labels and the canvas edge gets a strip of empty space beside its first spot (what lies past the strip moves over; a frame it crosses widens), or a wider canvas. Like wrap, it moves things once, with no audit and no redraw. A figure whose labels fit draws as before.
- **Wrap (`wrap.py`):** a layout of 12 or more layers well under the target aspect (default 4:3, or the spec's `size.aspect`) is cut between layers no frame spans. The chunks sit side by side, joined by corridors under, between and over them.
- **Pinned ends:** an edge's `from_at` and `to_at` keep its end at that offset along the side. Schema pins each relation to its column rows.
- **Pinned nodes (4.6; `diagrams._hold_pins`, `bk.hold`):** a figure with pins is laid out twice.
  - The first layout leaves the pins out. It gives the rows the pins' `y` choose and the places the other boxes keep.
  - The second fixes every rank, puts each pinned node in its row, and orders that row by `x`. It keeps the first layout's rows at least as low as they stood (`row_y`, by growing the gap above a row), its wrap cuts (`cuts`; a cut a frame now spans moves to the nearest free layer), and its x before wrap as `prev`, as when an edit draws again (21.4). Read before wrap, a wrapped figure is still one column, so the pins are mapped into that frame through their column's offset.
  - Its Brandes–Köpf coordinates are moved once, before routing (`bk.hold`). First, whatever stands past the canvas's left margin moves right to it. Then each pinned item goes to its `x` and pushes what stands in its way, along its layer, through a frame's borders, and along an arrow that runs straight, by as little as the gaps allow. A pin already held, or the margin, stops a push. Routes, frames, wrap and label room then work from these places, so nothing is checked and moved afterwards.
  - The renderer places the drawing so the pins land on their `x`. When wrap or label room moved two pins apart, up to two more layouts correct their targets; a pin still off is reported.
- **Schema (`table` above):** the layered kernel run left to right (`direction: LR`, `back: "ports"`), so rows become ports on the tables' left and right sides. There is no separate `table` kernel.
- **Sequence (`sequence.py`):** lifelines a pitch apart that fits the widest label, one step per message. Activations and fragments are not drawn yet.
- **No repair loop:** flow, arch and schema draw once (a figure with pins is laid out twice first). The v1 path (`legacy.py`, `--layout-engine v1`) stays until P8; schema tables pinned with `x` and `y` still draw with it.
- **Not built:** the other kernels in 7.2 and the container protocol of 7.1. A first version of each, added without a caller, was deleted in P4; each is built with the renderer that first uses it.

## 8. Routing, labels, painting

### 8.1 Ports

A shape reports anchor points per side with outward normals. Edges get ports on the side facing their other end. Several edges on one side are spread into slots, as `assign_ports` does today.

### 8.2 Routers

| Router | Method |
| --- | --- |
| `orthogonal` (default) | <ul><li>Orthogonal visibility graph over obstacle boxes; A* with costs for length, bends and crossings.</li><li>Parallel segments are then nudged into separate channels, so two arrows never share a line.</li><li>Back edges run around the outside, as today.</li><li>Self-loops get a fixed loop on a free side.</li></ul> |
| `straight` | Straight segment, clipped to both outlines. |
| `spline` | Cubic curve through the layered layout's dummy nodes. |
| `bundled` | Orthogonal, with edges that share a source merged into one trunk. |

### 8.3 Display list

```python
@dataclass(slots=True)
class Item:
    id: str              # stable across renders and edits (D15): "<owner>/<role>/<n>"
    owner: str           # scene element id, "" for the figure
    role: str            # node.shape | node.border | node.text | node.icon | edge.path | edge.marker
                         # edge.label | group.frame | group.title | axis.* | mark.* | legend.*
                         # annotation.* | figure.title | decoration.*
    kind: str            # path | text | image | use
    geom: Path | TextBlock | ImageRef
    paint: Paint         # fill, stroke, width, dash, opacity, gradient, pattern, filter, markers, font
    z: int               # layer * 1000 + order
    bbox: Box
    obstacle: bool       # arrows must not cross it
    text_area: Box | None    # where its text must fit
    depth: float | None  # 3D only: painter's order
    attach: tuple | None # edges: ((node, port), (node, port)), so editors and exports keep arrows glued
    a11y: A11y | None    # accessible name, description, reading order (section 22.3)
    attrs: dict          # data-* attributes to write, e.g. data-node, data-from
```

A node's items (shape, border, text, icon) always share one `owner`. Any consumer can treat a node as one unit: an editor, an exporter, or an animation between views.

Z layers: background 0, group frames 100, edges 200, nodes 300, labels 500, annotations 600, legend 700, titles 800.

### 8.4 SVG writer

One module writes SVG. Its rules:

- Numbers use at most 2 decimals with trailing zeros trimmed, so output is deterministic.
- All text is escaped in one place.
- Gradients, patterns, markers and filters go into a single `<defs>` with stable ids.
- Each scene element becomes a `<g class="..." data-node|data-group|data-from...>`. Today's `data-*` attributes are kept exactly (14.4), so exports and the outline keep working. Class names make the HTML output stylable and hoverable.

## 9. Audit

### 9.1 Checks

A check is a registered function: `check(ctx, display_list, scene) -> list[Issue]`.

```python
@dataclass
class Issue:
    code: str            # stable identifier
    severity: str        # error | warning
    msg: str
    fix: str
    at: tuple[float, float]
    owner: str | None    # scene element
    rule: str | None     # the selector of the style rule that caused it, if any
    field: str | None    # the spec field to change, if any
```

Checks run on the display list, so they know exactly which items are nodes, labels and arrows. Circles, ellipses and curves are obstacles like any other shape.

### 9.2 Existing checks (kept, same codes)

`dense`, `newline`, `clip`, `collide`, `overlap`, `through`, `strike`, `shared`, `intrude`, `spill`. Their behavior is specified in [section 9.6](#96-existing-check-reference) so the port can be verified case by case.

### 9.3 New checks

| Code | Severity | Catches |
| --- | --- | --- |
| `contrast` | error | Text below WCAG AA (4.5:1, or 3:1 for text ≥ 18 px) against its actual background. Names the rule that set the colors. |
| `min-size` | warning | Text under 9 px. |
| `truncated` | warning | Any text that was cut. |
| `font-fallback` | warning | A named font wasn't found; bundled metrics were used. |
| `colors` | warning | More than 8 distinct categorical colors. |
| `legend` | warning | An encoding or shape meaning is used without a legend entry. |
| `decision-exits` | warning | A decision's exits are not all labeled (flow preset). |
| `constraint` | warning | A layout could not honor a constraint. |
| `occluded` | error | 3D: a label is hidden behind a face. |
| `face-overlap` | warning | 3D: two solids intersect, so back-to-front drawing may be wrong there. |
| `large-font` | warning | An embedded font adds more than 200 KB to the file. |
| `shaping` | warning | Text needs contextual shaping and no shaper for it is available, so widths are approximate. |
| `off-brand` | error | A rule or element tries to override the policy layer (22.4). |
| `text-density` | warning | A page has more words than its size allows (21.1). |
| `hierarchy` | warning | A page has no headline, or more than one. |
| `stale-data` | warning | A bound value's source is older than its allowed age (21.4). |
| `patch-conflict` | error | A saved edit no longer applies to the regenerated spec (21.3). |
| `aspect` | warning | Output is far from the requested aspect ratio. |

As built in P3.9:
- **`contrast`** compares a text's fill with the last solid fill painted under its middle, composited over the figure.
- **`min-size`** flags text under 9 px.
- **`colors`** counts distinct, non-grey node fills.
- **Attribution:** renderers mark text whose color or size a stylesheet set with `data-color-from` and `data-size-from`, holding the sheet and rule. Issues quote them. Until the default themes pass on their own (B25), only marked text is judged.

### 9.4 Foreign SVG

`audit` must keep reading any SVG. `audit/svg_import.py` turns a foreign SVG into a display list, using today's parser in `_svg_geometry`: CSS rules, transforms, tspans and path flattening. Roles are inferred: `text`, closed shapes are obstacles, and paths with markers are arrows. The same checks then run, and checks that need a role the import couldn't infer skip themselves.

### 9.5 Repair

There is no generic redraw loop. A check may attach a `hint` (for example `{"separate": ["a", "b"]}`). A layout may implement `repair(hints)`, capped at 2 iterations. Until the new `layered` kernel lands (PLAN P4), the current repair loops stay but compute their cost from the display list instead of parsing SVG.

### 9.6 Existing check reference

Today's behavior in `_svg_geometry` and `_audit_file`, which the port must reproduce on the golden corpus. All are errors except `newline`.

| Code | Geometry and thresholds today |
| --- | --- |
| `dense` | More than 1,500 text items. Returned alone; every other check is skipped. Separately, more than 4,000 shapes silently empties the shape list. |
| `newline` | A literal `\n` inside a text's content. Warning. |
| `clip` | A text box more than 4 px outside the canvas. Needs a `viewBox`. |
| `collide` | <ul><li>**Text on text:** overlap wider than `max(3, 0.15 × narrower width)` and taller than `0.4 × smaller font size`. An identical text at the same spot (a halo) is skipped.</li><li>**Label on a diamond:** a text pill (padding 7×2 px) has a corner inside the rhombus while its center is outside.</li><li>**Frame on text:** a frame border strictly crosses a text box.</li></ul> |
| `overlap` | Two shapes intersect by more than 4×4 px and neither contains the other (1 px tolerance). |
| `through` | <ul><li>**Box:** an arrow crosses a box, inset 3 px, for more than 2 px (Liang–Barsky).</li><li>**Diamond:** sampled every 4 px, a hit within 0.9 of the rhombus's normalized L1 distance.</li><li>**Skipped:** "holder" shapes (containing a shape ≥ 24 px tall, or a pill ≤ 2.5× its text), and shapes within 6 px of either arrow end (half-size + 6 for diamonds).</li></ul> |
| `strike` | An arrow crosses a text's core (inset 1 px horizontally, 20% vertically) for more than 2 px. Only texts painted before the arrow. |
| `shared` | Among the first 300 arrows: two axis-aligned runs longer than 12 px, same orientation, within 2 px, overlapping or less than 12 px apart. Skipped when the two starts or two ends are within 3 px (a trunk). |
| `intrude` | A named node's center strictly inside a frame it doesn't belong to. Diamonds are not named nodes today. |
| `spill` | The text's host is the smallest rect containing its center. Fails if the text comes within 2 px of the host's left or right edge. Tight hosts (height ≤ 1.8× text, width ≤ text + 2 × font size) are skipped. Vertical overflow is not checked. |

**Audit-level warnings without a code.** Missing `<title>` (unless a 24 px heading exists); missing `<desc>`; 2+ 24 px titles; negative tick text; more than 400 circles; the first off-canvas start-anchored text; text over 8 characters repeated more than 3 times. A single-quoted `font-family` attribute is an error. These move into the registry as checks with codes (`title`, `desc`, `double-title`, `negative-tick`, `many-points`, `edge-text`, `repeated-text`, `font-quote`), and the verdict keeps the same messages.

**Stats** (the repair loops' cost, today): `crossings` (horizontal × vertical runs of different arrows crossing strictly) and `wire` (total axis-aligned run length, first 300 arrows). `_layout_cost` is `4 × bad + crossings + wire / 400`, and a parse error counts as zero problems; that last case is a bug.

**Blind spots, and what P2.5 did about them.** These change results on purpose. On 203 figures (golden, gallery, 80 fuzz renders) the fixes add two real issues and remove none.

Fixed:
- **Circles and ellipses** stop arrows (`through ... circle`). They stay out of the box-on-box check, because bubbles and Venn sets overlap by design.
- **Curves and arcs** are followed in 8 steps each instead of reduced to chords. A path counts as crossing a box when it runs more than 2 px inside it in total. A curve is many short segments, so the length is summed, not asked of each segment.
- **Markers** set by CSS or inherited from a parent `<g>` make an arrow; `marker-end="none"` does not.
- **`skewX` and `skewY`** transforms are applied.
- **Only a rhombus is a decision.** Another quadrilateral (a Mermaid parallelogram) is an obstacle by its bounding box, unless it is translucent.
- **`spill`** also checks a label against the top and bottom of its box.

Still open:
- **Translucent shapes** (`fill-opacity` or `opacity` below 1) are never obstacles: they are drawn to be seen through.
- **Polygons with other point counts and closed paths** stay out: radar areas, pie and treemap slices, and chart areas would raise false overlaps. P2.6 removes the guess, because the renderers mark obstacles in the display list themselves.
- **`_c_*` boxes carry no `data-node`,** so `intrude` and the outline skip them (P2.8).

## 10. Outline and receipts

### 10.1 Verdict and outline

The one-line JSON verdict keeps every field it has today (`ok`, `svg`, `html`, `receipt`, the count key, `layout`, `errors`, `warnings`, `next`, `stage`). The new `outline` field is an object:

```jsonc
"outline": {
  "figure": { "size": [960, 540], "layout": "layered LR, 6 layers in 2 columns" },
  "nodes":  [{ "id": "api", "name": "API gateway", "layer": 2, "column": 1, "group": "edge" }],
  "edges":  [{ "from": "api", "to": "auth", "label": "verify", "route": "right" }],
  "groups": [{ "id": "edge", "members": 3 }],
  "charts": [{ "x": "month", "y": "signups", "series": [{ "name": "Atlas", "first": 120, "last": 310 }] }],
  "style":  { "font": "IBM Plex Sans (file)", "rules": 7, "legend": ["Payments team", "p99 ms"] }
}
```

`layout` (the list of row strings) stays for compatibility and is generated from the outline. Long lists are capped, with a count of what was left out.

### 10.2 Receipts

```jsonc
{ "version": 2, "engine": "0.8.0", "cmd": "arch",
  "scene": { },                         // the normalized scene, so export needs no input files
  "inputs": { "spec": "arch.json" },    // the original paths, relative, as today
  "options": { }, "styles": ["brand.json"], "toolkits": { "3d": "1" },
  "fonts": { "IBM Plex Sans": "sha1:..." } }
```

`export` reads v1 receipts (today's fields) and v2 receipts. Re-rendering a v2 receipt does not need the original inputs.

As built in P2.10, a v2 receipt keeps every v1 field where it was and adds new fields beside them. That way v1 readers, and the golden files, see no change in what they already read. The additions:
- `"receipt": 2`;
- `theme_overrides`: the theme keys that `--theme-file` changed;
- `caption` and `notes` (from `--caption` and `--note`/`--note-at`);
- `audit: false` after `--no-audit`;
- for flow, arch, seq and schema, `scene`: the normalized scene that was drawn.

Export draws a diagram from that scene, so it reproduces the figure even after the spec file has changed or gone. CSV inputs are still read from their files. The nested layout above (`inputs`, `options`, `styles`, `toolkits`, `fonts`) comes with the phases that add those fields (P3, P5).

## 11. Extension system

### 11.1 Extension points

| Point | Signature | Built-in examples |
| --- | --- | --- |
| `shape` | `(ctx, box, style) -> ShapeOut` (outline, named sides, text area, ports, hit polygon, faces for 3D) | rect, rounded, oval, diamond, circle, cylinder, hexagon, parallelogram, document, actor, cloud, table, dot |
| `layout` | `measure(ctx, container) -> Size`; `place(ctx, container, box) -> Placement` | section 7.2 |
| `router` | `(ctx, edge, ends, obstacles) -> Path` | orthogonal, straight, spline, bundled |
| `decoration` | `(ctx, outline, style) -> list[Item]` | per-side border, shadow, glow, gradient, hatch, sketch |
| `mark` | `(ctx, rows, encoding, scales) -> list[Item]` | point, line, area, bar, arc, text, rule, tick, rect, boxplot, errorbar |
| `transform` | `(ctx, rows, spec) -> rows` | bin, aggregate, stack, normalize, density, regression, window, fold, filter, calculate |
| `scale` | `(spec, values) -> Scale` | linear, log, sqrt, time, band, point, ordinal, sequential, diverging |
| `projection` | `(ctx, points3d) -> points2d, depth` | identity (core), isometric, dimetric, perspective (3D toolkit), mercator (geo toolkit) |
| `property` | name, syntax, inherited, initial, applies-to | section 5.4 |
| `pseudo` | `(element, ctx) -> bool` | `:source`, `:sink`, `:focal` |
| `input` | `(text, options) -> Scene`, plus a sniff function | v1 JSON, Mermaid, CSV, GeoJSON, Vega-Lite |
| `output` | `(display_list, ctx) -> bytes` | svg, html, png, pdf, drawio, excalidraw, html3d |
| `check` | `(ctx, display_list, scene) -> list[Issue]` | section 9 |
| `shaper` | `(text, font, lang, direction) -> glyph runs with advances` | built-in Latin/CJK + bidi; HarfBuzz (extra); browser |
| `view` | `(ctx, scene, view_spec) -> scene state` (focus, filter, highlight, zoom, reveal) | section 21.2 |
| `page` | `(ctx, page_spec, figures) -> page layout` | slide 16:9, A4, Letter, poster, responsive (section 21.1) |
| `preset` | data (11.4) or a function returning a scene | flow, arch, seq, schema, state, bpmn, … |

Every registered part declares an options schema and an example. Validation, `describe` and the JSON Schema export are generated from them.

### 11.2 Toolkit API

```python
from diagonaldiagrams.toolkit import Toolkit, ShapeOut

tk = Toolkit("3d", version="1", requires=["core"],
             stylesheet="style.json", docs="Isometric and perspective figures.")

@tk.shape("cuboid", options={"depth": "length = 24"}, example={"shape": "cuboid", "depth": 32})
def cuboid(ctx, box, style) -> ShapeOut:
    ...

@tk.projection("isometric", options={"angle": "number = 30"})
def isometric(ctx, points):
    ...

@tk.check("occluded", severity="error")
def occluded(ctx, dl, scene):
    ...
```

### 11.3 Discovery and loading

- **Built-in toolkits:** imported lazily, on first use, by `use`, a preset, or a type name. Core is always loaded.
- **Installed toolkits:** Python entry points in group `diagonaldiagrams.toolkits`.
- **Local toolkits:** `--toolkit ./path.py` on the CLI. The MCP server loads local toolkits only when it was started with `--toolkit`; a spec can never name a file to execute (D8).

### 11.4 Data-defined extensions (`defs`)

Agents extend the engine without code:

```jsonc
"defs": {
  "shapes": {
    "tag": { "path": "M0 0 H.85 L1 .5 L.85 1 H0 Z",
             "sides": { "top": "M0 0 H.85", "left": "M0 1 V0" },
             "padding": ".12 .2 .12 .06" }
  },
  "presets": {
    "incident": { "extends": "flow", "layout": { "type": "layered", "direction": "right" },
                  "style": { "rules": { "node.sev1": { "border-left": "4px solid #dc2626" } } } }
  },
  "icons":   { "robot": { "path": "M...", "viewBox": "0 0 24 24" } },
  "markers": { "hollow-dot": { "path": "M...", "size": 8 } },
  "scales":  { "heat": { "type": "sequential", "scheme": "heat", "domain": [0, 500] } }
}
```

- **Shapes:** paths are in a unit box (0 to 1), parsed by a strict SVG path parser, and scaled to the node. Named sides make `border-<side>` work. A `defs` shape gets ports, obstacles and checks like a built-in one.
- **Presets:** stylesheets plus layout plus defaults. `extends` builds on an existing preset.
- **Files:** a `defs` block can also live in a file passed with `--defs`, or in a toolkit's data folder.

### 11.5 Presets

A preset is data:

```jsonc
{ "name": "state", "use": ["core"],
  "layout": { "type": "layered", "direction": "right" },
  "defaults": { "node": { "shape": "circle" }, "edge": { "router": "spline" } },
  "style": { "rules": { "node:source": { "border-width": 2.5 } } },
  "legend": { "shapes": { "circle": "state" } },
  "checks": ["unreachable"],
  "fields": { "states": "nodes", "transitions": "edges" } }
```

`fields` renames input fields, so many v1 chart specs map onto a preset with no code. A preset that needs reshaping (for example kanban `columns[].cards[]` into groups and nodes) names a small adapter function in its toolkit.

### 11.6 Describe and schema

- `describe` lists toolkits, presets, shapes, layouts, routers, marks, properties and checks, all from the registry.
- `describe <name>` gives one part's options, an example and its docs.
- `describe --schema` prints a JSON Schema for the scene with every registered part. Agents and editors can validate against it.

## 12. Charts toolkit

A grammar of graphics over containers with the `scale` layout:

- **Scales:** linear, log, sqrt, time, band, point, ordinal, sequential, diverging. Nice ticks (today's `nice_ticks`). Formats: SI prefixes, units, dates such as `Jan` or `Q1 2026`, and percentages.
- **Guides:** axes, gridlines, legends, and direct end-of-line labels (today's line chart behavior, generalized).
- **Marks:** point, line, area, bar/rect, arc, text, rule, tick, boxplot, errorbar.
- **Transforms:** bin, aggregate, stack, normalize, density, regression, window (rank), fold, filter, calculate. `calculate` and `filter` use the math toolkit's expression parser; there is no `eval`.
- **Composition:** layer, facet (row and column), concat.
- **Extra layouts:** `partition` (treemap, icicle, sunburst), `sankey`, `venn` and `calendar`, for chart kinds that are not mark-and-axis.

**Vega-Lite subset.** Supported:
- `data` (`values`, `url` for a local CSV or JSON, named data);
- `mark`;
- `encoding`, including the channels `x`, `y`, `x2`, `y2`, `color`, `size`, `shape`, `opacity`, `text`, `tooltip`, `theta`, `radius`, `row`, `column`, `detail`, `order` and `strokeDash`;
- field types;
- `aggregate`, `bin`, `timeUnit`, `sort`;
- `scale`, `axis`, `legend`, `transform`, `layer`, `facet`, `concat`, `title`, `width`, `height`.

Anything else is an error naming the unsupported feature, with a fix.

Today's `bar`, `line`, `scatter`, `geo` and statistical `chart` kinds become presets over this grammar, keeping their flags.

## 13. 3D toolkit

The 3D toolkit is the test of the modularity goal. It must be buildable without editing core code, so the core reserves these hooks from the start:

- positions carry an optional `z`;
- a shape may return several faces;
- items carry `depth`;
- the pipeline has a projection stage (identity in 2D).

As reserved in P2.14:
- A node's `pin` takes an optional `z`, and so does the patch `pin` operation.
- A painted element (`paint.Element`) may carry `pts3d`, its 3D corner points. A shape painter returns a list of elements, so a solid returns one per face.
- `Drawing.projection` is a callable `(x, y, z) -> (x, y, depth)` and is `None` in 2D. `paint.project` gives each face its 2D points and a `data-depth`, then reorders the faces back to front among the places they hold in the paint order, so the paper and labels stay put.
- Display-list items carry `depth`, read back from `data-depth`.

`tests/unit/test_3d_hooks.py` builds a projection and a two-faced solid entirely outside the core, as P7 will.

**Space.** `"space": {"projection": {"type": "isometric", "azimuth": 45, "elevation": 30}, "light": "top-left", "floor": true}`. Projections: isometric, dimetric, orthographic, perspective (with `distance` and `fov`).

**Placement.** 2D layouts place on the floor plane. The `elevation` style or attribute lifts elements (`by-rank` lifts each layer). Groups become plates. 3D layouts: `stack3d` (layered plates, the classic platform-stack picture), `grid3d`, and `scale3d` (three data axes).

**Solids:** cuboid, cylinder, cone, sphere (a shaded disc), plate, prism, `extrude` (any 2D shape, including `defs` shapes), and surfaces `z = f(x, y)` using the math toolkit.

**Shading.** Lambert shading from the light direction mixes each face's color toward the `shade-light` or `shade-dark` tokens. The theme still controls the palette.

**Depth.** Faces are drawn back to front:
- by centroid depth with stable tie-breaks;
- by grid order for height-field surfaces, which is exact when viewed from above.

**Limit:** solids that intersect each other are not split. The `face-overlap` warning reports them, and the three.js output handles them properly.

**Edges and labels:**
- Edges are routed by the normal 2D router on the floor plane, then projected. Under isometric projection orthogonal elbows stay orthogonal-looking.
- Edges between elevations get vertical segments.
- Labels stay flat to the viewer, are placed after projection and are checked for occlusion.

**Outputs:** SVG as usual. `html3d` writes an HTML page with three.js (a pinned version from a CDN) and orbit controls, built from the same 3D scene.

## 14. Compatibility

### 14.1 Commands and flags

Every subcommand and flag listed by `--help` today keeps its meaning:

- render commands: `flow`, `arch`, `seq`, `schema`, `mermaid`, `bar`, `line`, `scatter`, `geo`, `chart <kind>`;
- other commands: `validate`, `audit`, `infer`, `describe`, `export`, `doc`, `extract`, `monitor`, `sync`, `mcp`.

New flags are additive: `--style`, `--defs`, `--toolkit`, `--font`, `--embed-fonts`, `--size`, `--aspect`.

### 14.2 Input formats

Each v1 format compiles to a scene through an adapter in `inputs/v1.py`, using the field mapping in section 14.6. `budget: true` keeps the old budgets as warnings plus advice, except where a test or a documented contract expects refusal. In those cases refusal stays and `--no-budget` or `"budget": false` lifts it.

### 14.3 MCP

- Same transport, protocol versions, tool names and input schemas.
- `render` also accepts a `scene` object. `export` gains `drawio` and `excalidraw`.
- Tool calls run in-process through the Python API instead of re-executing the script, which removes the 0.4–0.5 s of startup and compiling from every call.
- A hard ceiling on scene size keeps a call bounded. `mcp --isolate` keeps the old subprocess behavior.

### 14.4 SVG attributes

Kept on every relevant element:

- `data-node`, `data-label`, `data-cx`, `data-cy`;
- `data-group`, `data-name`, `data-members`;
- `data-from`, `data-to`;
- `data-msg`, `data-msg-from`, `data-msg-to`;
- `data-role`.

Added in 0.7 (P2.15): `data-id` on every drawn edge, sequence message and schema relation, carrying the id the scene gives it (4.8). Schema table cards now carry `data-node` and `data-label`, and relations carry `data-from`, `data-to` and `data-label`, as the other diagrams already did. The `--outline` edges and messages, and the draw.io and Excalidraw cells (`node:ID`, `edge:ID`, `group:ID`), use the same ids, so an element keeps its id and its export cell across edits.

`_svg_model` currently parses these with order-dependent regexes. It is replaced by building the draw.io and Excalidraw models from the display list, with a tolerant SVG fallback for v1 files.

### 14.5 Hidden contracts

- **Monitor and sync:** monitor's `remediation_cmd` string (`py graph.py extract K F -o S`) is parsed by sync with a regex. Monitor also emits a structured `remediation: {"cmd": [...]}`, and sync reads that first.
- **Single-file script:** sync, monitor and the MCP server re-run `graph.py` through `__file__`. They call the Python API instead.
- **Browser playground:** it loads one file named `graph.py`. The site build writes a pure-Python wheel to `docs/` and the playground installs it with `micropip`. `docs/graph.py` is deleted.
- **`graph.py` at the repo root:** stays as a shim (`from diagonaldiagrams.cli import cli; cli()`), so `py graph.py ...` and the install skill's checks keep working. The wheel no longer installs a top-level module named `graph`.

### 14.6 v1 field mapping

The v1 adapters produce a scene with a preset. Field names mostly carry over; behavior that was hard-coded becomes a preset rule, which an agent can then override.

**flow → preset `flow`** (layered, top to bottom)

| v1 | Scene |
| --- | --- |
| `title`, `sub`, `notes[{at, text}]` (first 2), `budget` | `title`, `subtitle`, `annotations[{type: note}]`, `budget` |
| node `id`, `name` (defaults to `id`), `sub`, `tag`, `icon`, `focal` | same |
| node `shape`: `rect`, `oval`, `diamond`, `dot`; anything else → rect with a warning | same names, registered in the flow toolkit (DIN 66001 shapes) |
| node `rank`; a rankless node gets its list index unless no node has a rank or `--auto` is set | `rank`; layout option `ranks: "explicit-then-index"` (v1) or `"auto"` (`--auto`, and the default for v2 scenes) |
| node `lane` (−4..4, 240 px pitch) | `lane`, honored by `layered` as a column hint |
| node `group`; `groups[{id, name, tag, nodes \| members}]` | groups. In v1 a group only drew a frame; in v2 it is also kept contiguous, which removes today's `intrude` failures. |
| edge `from`, `to`, `label` (drawn uppercase until 0.8.1), `focal`, `async` | same; labels keep the case the spec gives, and `edge::label { text-transform: uppercase }` in a stylesheet brings v1's look back |
| legend sentence "box = step, diamond = decision, rounded = start or end" | legend from the shapes present |
| warning: unlabeled diamond exit; error: more than 3 diamond exits | `decision-exits` check; the exit limit stays a validation error |

**arch → preset `arch`**

| v1 | Scene |
| --- | --- |
| node `layer` (default 0; gaps collapse) | `rank`, explicit |
| row order = spec order | `order` constraints per layer, generated by the adapter |
| no `shape`; every node is a box | default shape `rect` (a v2 scene may set any shape) |
| edge `proto` (starts with `http` → link color, beats focal) | `proto`, plus the rule `edge[proto^=http] { stroke: link }` |
| groups keep members side by side (`_group_columns`) | compound groups in `layered` |
| wider pitch when `budget: false` or more than 9 nodes | spacing comes from measured sizes |

**seq → preset `seq`** (`sequence` layout)

| v1 | Scene |
| --- | --- |
| `actors[{id, name, sub, tag, focal}]` | nodes in actor order. A missing `name` defaults to `id`, which fixes today's crash. |
| `messages[{from, to, label, proto, reply, async, focal}]` in list order | edges with `order` = index. `proto` is shown as the `[PROTO]` label prefix, as today. `from == to` is a self-loop. |

**schema → preset `schema`** (`table` layout)

| v1 | Scene |
| --- | --- |
| `tables[{id, name, tag, focal, x, y}]` | nodes with shape `table`; `x`/`y` become `pin` |
| `columns[{name, type, pk, fk, unique}]` | the table's rows, each a port. `unique` is now drawn, as a `UQ` badge. |
| `relations[{from, to, from_col, to_col, label, focal}]` | edges with `from-port`/`to-port` set to the column names |
| fixed 320 px row pitch | measured heights, which fixes overlapping tables with more than about 11 columns |

**Mermaid.** Today's parser keeps its syntax and emits a scene directly. Things it drops today are mapped later (PLAN P8.2):

- `direction` (today: warns and draws top-down);
- `classDef`, `class`, `style` and `linkStyle`, which map onto style rules;
- nested subgraphs, as nested groups;
- ER optionality, as crow's-foot markers;
- sequence `note`, `loop`, `alt`, `opt`, `par`, `activate`;
- the rejected diagram kinds, once a matching preset exists: `stateDiagram`, `classDiagram`, `gantt`, `pie`, `timeline`, `quadrantChart`, `mindmap`, `kanban` and `journey`.

**bar, line, scatter, geo → chart presets.** Every flag keeps its name:

| v1 flag | Becomes |
| --- | --- |
| `--cat/--val/--x/--y/--group/--yerr/--facet/--lat/--lon/--label` | encodings |
| `--sort`, `--orientation`, `--unit`, `--xunit`, `--yunit`, `--xlabel`, `--ylabel` | sort, axis and format options |
| `--highlight` | `highlight` annotations |
| `--note` + `--note-at` | `note` annotations |
| `--grid`, `--markers` | preset style switches |
| `--figure`, `--caption` | stored and drawn: the caption below the figure, the figure label as an eyebrow. Today both are stored and never drawn. |
| export `--layout figure\|wide\|slide\|social` | `size` presets, for every chart, not only scatter |
| LTTB thinning (600 points), scatter sampling (5,000) | kept as preset transforms |

**`chart <kind>` → one preset each.** Column roles and their aliases (`_ROLE_ALIAS`), the explicit flags (`--x --y --group --size --label --parent --val --a --b --lo --hi`) and caps carry over into the preset's `fields` and budget. One fix: validation will accept every flag that render accepts. Today `_validate_chart` passes only `--x`, `--y` and `--group` to its column check, so a valid `--size` or `--val` can block a render.

The full kind-by-kind list, with its target phase, is in PLAN.md (P6.7 and P8.1).

## 15. Package layout

```
diagonaldiagrams/
  __init__.py          public API: render, audit, describe, load; __version__
  __main__.py          python -m diagonaldiagrams
  api.py               render(spec | scene, out=None, **options) -> Result
  errors.py            SpecError, Issue
  scene/               model.py, normalize.py, schema.py
  style/               tokens.py, parse.py, select.py, cascade.py, encode.py, color.py, themes/*.json
  text/                fonts.py, measure.py, markup.py
  geom/                primitives.py (Point, Box, Path, intersections), outline.py (sides, corners)
  layout/              base.py, layered.py, tree.py, stack.py, grid.py, radial.py, force.py,
                       sequence.py, table.py, timeaxis.py, manual.py
  route/               ports.py, orthogonal.py, straight.py, spline.py, labels.py
  paint/               displaylist.py, painter.py, shapes/, decorations/, markers.py, icons.py
  audit/               run.py, svg_import.py, checks/
  emit/                svg.py, html.py, raster.py, drawio.py, excalidraw.py, receipt.py
  inputs/              v1.py, mermaid.py, csv.py, geojson.py, vegalite.py, extract/
  outline.py
  toolkit.py           Toolkit, registries, discovery
  toolkits/            core/, flow/, arch/, seq/, schema/, diagrams/ (state, bpmn, uml, c4, ...),
                       charts/, geo/, math/, threed/
  cli/                 main.py (lazy subcommands), commands/*.py
  mcp/                 server.py
  data/                icons.json, land.json, metrics/*.json
graph.py               repo-root shim, not packaged
tests/                 unit/, golden/, fuzz/, cli/ (today's tests_smoke.py moves here)
```

**Import rules:**

- `scene`, `style`, `text`, `geom` and `layout` never import `emit`, `cli` or `mcp`.
- Toolkits import only `diagonaldiagrams.toolkit` and the public types.
- A test enforces both rules.

## 16. Performance budgets

Measured by `scripts/metrics.py`, from compiled bytecode, on the CI runner:

| What | Budget |
| --- | --- |
| `import diagonaldiagrams` (core only) | ≤ 50 ms |
| CLI render of a typical diagram, end to end | ≤ 150 ms |
| 40-node layered layout plus routing | ≤ 100 ms |
| 200-node layered layout plus routing | ≤ 1 s |
| Chart with 10,000 points (downsampled as today) | ≤ 300 ms |
| Audit | ≤ 20% of render time |
| MCP tool call, in-process | ≤ 100 ms typical |

CI fails on a 2× regression against the stored baseline and reports smaller changes.

`PYTHONDONTWRITEBYTECODE=1` (set on the maintainer's machine) stops Python caching compiled modules. `pip install` precompiles them, so installed copies are unaffected.

A checkout needs care. Importing an uncached module compiles it more slowly than running the same file as a script: about 2 s versus about 0.4 s for today's `graph.py`. Compile time also grows faster than file size: the first half of `graph.py` compiles in 0.38 s, the whole file in 1.5 s. So the split must keep modules small and imports lazy, and `python -m compileall diagonaldiagrams` removes the cost entirely (PLAN P1 exit).

**As built (P3):** styles are worked out once per render, not once per layout draft.
- **Per render:** the `Styler` keeps each element's painting values, the legend entries and the readable-text colors for the whole render.
- **Across renders:** the cascade keeps the bundled sheets' parsed selectors and declarations, keyed by the token values.
- **By value:** text wrapping (`text.measure.wrap`) and box text layout (`box_text`) are cached, each bounded at 8,192 entries for long-running servers.
- **Lazy imports:** PyYAML loads only for YAML files, the SVG sanitizer only for inline SVG, and a box's per-side border geometry only when a style declares a side.

`bench/metrics/p3.md` has the side-by-side numbers.

## 17. Testing

- **CLI contract:** today's `tests_smoke.py` cases, moved to `tests/cli/`, run against the installed command and the `graph.py` shim. They are the compatibility gate.
- **Unit tests:** per module, in-process, with pytest as a dev-only dependency.
- **Golden files:** every example, gallery figure and preset, rendered to SVG (byte-compared) and outline JSON. PNGs are generated for human review. `scripts/golden.py --check | --update`.
- **Fuzz:** seeded random scenes (5 to 200 nodes, groups, lanes, back edges, long labels, every shape) must render with zero audit errors. The failure count is tracked from the baseline down to zero.
- **Quality:** blind pairwise comparison of rendered PNGs, before and after, and against Mermaid, D2 and Graphviz. Judged by a vision model, with human spot checks. Kept in `bench/quality/`.
- **Performance:** section 16.
- **Pyodide:** a headless smoke test that installs the wheel and renders one figure.

## 18. Risks

| Risk | Mitigation |
| --- | --- |
| The rewrite stalls halfway and leaves two engines. | Phases ship independently. Each port deletes the old path in the same phase. PLAN tracks the count of `_c_*` renderers and inline style constants down to zero. |
| Open styling produces ugly or illegible figures. | House-style defaults; legibility checks that name the rule at fault; no change unless the agent asks. |
| Font measurement differs by machine. | Bundled metrics by default; named fonts record a hash; fallback warns. |
| 3D depth sorting fails on intersecting solids. | Documented limit, `face-overlap` warning, three.js output. |
| Layered layout quality regresses on today's gallery. | Golden review per figure; crossing and bend counts tracked; old layout available behind `--layout-engine v1` until P8. |
| Scope creep in CSS and Vega-Lite support. | Defined subsets; unsupported features are explicit errors. |
| The Pyodide playground breaks. | Pyodide smoke test in CI. |
| The project turns into a document platform and never finishes the engine. | The layers are separable. P0–P8 ship the engine; each later phase is useful on its own. |
| Slide software's real hold is distribution and habit, not drawing. | A story is one self-contained HTML file that opens anywhere, with PDF as the fallback. Import (22.1) makes moving existing material cheap. |
| Raw SVG bodies, edit patches and agent-written toolkits become an attack path. | SVG is sanitized (4.5). Patches are data operations validated against the schema. Code toolkits need explicit local opt-in (D18) and never come from a spec (D8). |

## 19. Open questions

1. **Python floor:** 3.11 (D2), or 3.10 with a JSON config instead of TOML?
2. **Default font for new figures:** the measured system stack (safe everywhere), or Inter with embedding for exports?
3. **Font metric tables:** generated from fonts with open licenses only (Selawik, Liberation and Carlito stand in for proprietary fonts)?
4. **Release path:** incremental 0.6 → 1.0 releases per phase (recommended), or one 2.0 release?
5. **Types with no clear use:** drop any of today's 66 chart kinds rather than port them (for example `terrain` and `print`, which already refuse)?
6. **three.js output:** load three.js from a CDN in `html3d`, or inline it, which costs about 600 KB per file?
7. **Where stories live:** a self-contained HTML file (recommended), and also published pages on a host such as claude.ai Artifacts, where comments and shared state come from the host?
8. **Legacy export:** keep a flat PPTX export for people who haven't moved, or offer PDF only?
9. **Order after the engine:** pages and stories (P9) before 3D (P7), since they matter more to the post-legacy goal? 3D stays the modularity test either way.

## 20. Built for stronger models

### 20.1 What stays valuable as models improve

A stronger model can write SVG by hand. The engine earns its place by doing what is computation, not judgment:

| Engine job | Why a stronger model still wants it |
| --- | --- |
| Measure | Text width in a given font is arithmetic over the font's tables. A model can only estimate it. |
| Solve | A layout solver is deterministic and far cheaper than a model reasoning about coordinates. |
| Verify | An objective checker is useful at every capability level. Stronger models use it better, not less. |
| Render | One scene becomes SVG, HTML, a page, a presenter view, a phone layout and PDF. Nobody should hand-write each. |
| Remember | Stable ids, receipts and history carry state across a long collaboration between people and models. |
| Enforce | Brand policy and accessibility hold no matter which model or person made the change. |

What the engine must not do:
- encode taste as law;
- cap size or complexity;
- hide geometry from a model that wants it.

### 20.2 Feedback a model can optimize against

The verdict grows into a feedback interface:

- **`issues`**, as today, plus the rule or field that caused each one.
- **`metrics`:** crossings, bends, edge length, label displacement, whitespace balance, aspect error, ink ratio, smallest text, lowest contrast, and layout stability against the previous version.
- **`outline`** (section 10).
- **`image`** on request (`--preview png`), for models that check visually. The verdict states its token cost.
- **`diff`** against the previous version (21.4).
- **`candidates: N`:** the engine returns N scored layout variants (different orderings, directions, wraps and seeds). The model picks one or asks for more. Search, don't guess.

### 20.3 Levels of control (D14)

| Level | The model writes | Example |
| --- | --- | --- |
| Intent | A preset and content | `{"preset": "arch", "nodes": [...]}` |
| Structure | Scene, groups, constraints, styles | `same-rank`, selectors, encodings |
| Geometry | Pins, explicit routes, custom shapes | `pin`, edge `route`, `defs.shapes` |
| Raw | SVG node bodies, code toolkits | `"content": {"svg": ...}`, `--toolkit` |

Every level goes through the same measuring, audit and output, so going lower never means losing the checks.

### 20.4 Agents extending the engine (D18)

- `diagonaldiagrams toolkit new NAME` scaffolds a toolkit with tests.
- `diagonaldiagrams toolkit test NAME` runs its golden files, fuzz scenes and audit.
- The project config enables it.
- Once registered, the new part appears in `describe` and the JSON Schema for every model that uses the project.

## 21. Beyond slides: pages, stories, live documents

What slide software does, and what replaces each job here:

| Job | In slide software | Here |
| --- | --- | --- |
| Author | A person draws | An agent composes scenes and pages |
| Edit | Drag pixels; edits are lost when the content is regenerated | Change intent; direct edits become spec patches (21.3) |
| Stay consistent | The same diagram copied onto 12 slides and fixed on each | One scene, many views (21.2); change it once |
| Present | Slideshow | HTML presenter runtime (21.5) |
| Keep numbers right | Numbers pasted by hand | Values bound to their data (21.4) |
| Distribute | An attached file | A link to one self-contained HTML document; PDF as a fallback |
| Review | Comments on shapes | Semantic diffs, and comments anchored to element ids |
| Stay on brand | Templates people break | The policy layer (22.4) |

### 21.1 Pages

A page is a container with a page layout:
- **Sizes:** `slide` (16:9), `A4`, `letter`, `poster` and `responsive`.
- **Content blocks:** `heading`, `text` (paragraphs, lists, inline markup), `figure` (a scene or chart), `table` (data with formats), `image` (a local file), `callout`, and `metric` (a big number with its change and a sparkline).
- **Arrangement:** blocks are placed with `grid` and `stack`. The type scale and spacing come from tokens.
- **Checks:** `text-density`, `hierarchy` (one headline per page), `overflow`, plus contrast and minimum size.

### 21.2 Views and stories

A story is a list of views of one or more scenes:

```jsonc
"story": [
  { "id": "overview", "page": "slide", "title": "Checkout today", "figure": "platform" },
  { "id": "payments", "figure": "platform", "focus": "group#payments",
    "dim": "node:not(#payments node)", "highlight": "edge[to=psp]",
    "notes": "Speaker notes for this view." },
  { "id": "latency", "figure": "platform", "reveal": ["#api", "#auth", "#psp"],
    "annotations": [{ "type": "callout", "target": "#psp", "text": "p99 is 3 s" }] }
]
```

**What a view can do:**
- `focus`: zoom to a selection.
- `show`, `hide` and `dim`.
- `highlight`.
- `reveal`: show elements in steps.
- Its own annotations and style rules.

**Rendering:**
- Ids are stable and layout is incremental (D15), so in HTML the move from one view to the next animates positions and opacity.
- Static outputs render one page per view, and one per reveal step if asked.

**As built (stories slice, 2026-10-17).** `diagonaldiagrams story STORY.json -o OUT.html` (`story.py`, `web/story.js`):
- **One figure per story** for now: `"figure": {"type", "spec"}`, drawn first through the usual render (`OUT.figure.svg`, its receipt and verdict).
- **Views** take `focus`, `dim`, `hide`, `highlight` and `reveal` (a list, one selector per step), plus `title`, `text` and `notes`. The engine resolves each selector with the style system's matcher and warns when one matches nothing.
- **Frames.** Each view, or each reveal step, is a frame: the figure drawn again with per-element styles (opacity, accent stroke, a heavier line). Precedence is dim, then highlight, then reveal, then hide. A reveal step shows its elements at full strength, and an arrow once both its ends show. Opacity now reaches everything an element owns (its text, badges, tail and label), not only its outline.
- **Same layout in every frame.** Looks change color and opacity only, so frames have the same elements in the same places (a test checks this). The page moves between frames element by element: opacity, stroke, fill and line width fade with CSS transitions, and the camera (the viewBox, from `focus` plus padding) glides over 650 ms.
- **The page.** Arrows, Space, Page Up/Down, Home and End move; N shows the notes; `#view` or `#view/step` links open a frame; printing gives a page per frame with its camera; reduced motion turns the motion off.
- **Not yet:** several figures in one story, `show`, per-view annotations and style rules, pages and content blocks (21.1), a presenter view with a timer, PDF export.

### 21.3 Round-trip editing

HTML output has an edit mode. Dragging, resizing, recoloring, retyping and reordering produce patches:

```jsonc
[{ "op": "pin",   "id": "psp", "x": 640, "y": 210 },
 { "op": "order", "ids": ["auth", "api"] },
 { "op": "style", "selector": "#psp", "set": { "fill": "#fee2e2" } },
 { "op": "text",  "id": "psp", "name": "Payment provider" }]
```

- `diagonaldiagrams apply SPEC PATCH` writes the patches into the spec as constraints, rules and fields, so the next generation respects them.
- An agent reads a patch as intent.
- A patch that conflicts with a regenerated spec is reported (`patch-conflict`), never silently dropped.

As built in P2.16 (`scene/patch.py`):

- **Operations:**
  - `pin` sets a node's `pin`.
  - `order` rewrites the order constraint that already holds its ids, or adds one. Over a sequence's messages it moves them instead: they take the steps they held, as their `order` fields, and the messages it doesn't name keep theirs. An order that mixes nodes and edges, or orders edges outside a sequence, is a conflict.
  - `style` on `#id` merges into that element's own `style`; any other selector merges into the inline `style.rules`. A `null` value removes a property.
  - `text` sets `name`, `sub` or `tag` (`label` on an edge).
  - `add` takes `node`, `edge` or `group`.
  - `remove` also removes a node's edges, memberships, constraint mentions and notes.
  - `move-to-group` takes a group id, or `null` to leave every group.
- **Conflicts.** Each operation applies on its own:
  - one whose element is gone, whose optional `"was"` no longer matches the current text, or whose result would not be a valid scene is skipped and reported with its path (`patch[3]`) and a fix;
  - the others still apply;
  - the command exits 1 when anything conflicted, and says how many operations were written.
- **Identity.** Retexting an edge keeps its id, even though a generated id includes the label: the old id is written into the spec.
- **`place` (added for edit mode):** `{"op": "place", "id": "x", "row": ["a", "x", "b"]}` puts a node in a row, in that order. With its row-mates in one pinned rank (arch layers, ranked flows) the node takes that rank; else the op writes `{"same-rank": row}`. The row's nodes take its order as `order` and drop their `lane`, and the node drops its `pin`. A drag in the page writes this, never coordinates.
- **Files.** A v2 scene is written back as a scene, without the edge ids it would get anyway. A v1 spec stays v1, and fields only a scene has keep their scene names there (`style`, `pin`, `class`, `constraints`). The renderers draw what they can of them (styles, flow and arch pins, `same-rank` and `order`) and report the rest as `not-drawn` warnings. In particular, arch's repair loop may still reorder a row an `order` patch fixed, until the layered layout reads constraints (P4).

### 21.4 Live data and semantic diff

- **Data by reference.** Sources are named in `data`, and text binds values: `"Revenue grew {{revenue.q3 | change(revenue.q2)}}"`. Prose and charts then always agree.
- **Provenance.** Each bound number records its source and timestamp in the receipt. The `stale-data` check flags old sources.
- **No fetching.** The engine reads local data only (D8); the host or agent fetches.
- **Semantic diff.** `diagonaldiagrams diff A B` lists added, removed, moved, restyled and retexted elements, as JSON and as sentences. It serves review and agent feedback.

**As built (edit-and-animate slice, 2026-10-17).**
- **Edit mode** (`web/page.js`, on every diagram page): select a box to rename or recolor it (a step, a service, a table or an actor); move it by mouse or keyboard. In a sequence a message is a piece too, its line and its label together: drag it up or down to another step (`order` over the messages it passed), or change its label (`text` with `label`). The page gets the layout's layers (`info` from the renderer), so a move goes into a real layer at a place: a row of a flow or arch, wrapped or not; a column of a schema (`place`, with `rank` and `order` now kept for tables); the actors of a sequence (`order`, which reorders them). A drop goes into the layer of the nearest box. Keys: Tab and arrows go from box to box, Shift+arrows move, Enter or F2 renames, 1–6 color, Ctrl+Z undoes, Escape lets go; a live region says what moved. In a sequence, Down from an actor goes to its first message and Up and Down go along the steps, so Tab still goes from box to box. Edits show in place and are listed as a patch; the figure's files never change.
- **Applying.** `apply` writes the patch (21.3). The layered layout reads `same-rank` (the group is one node while ranks are worked out, as Graphviz's `rank=same` is), `order` constraints and node `order` hints. Hints now hold even when the start already crosses nothing, and a frame stays whole around its members.
- **Drawing again.** A render to a path whose receipt names the same command and spec is an edit of that figure. The layout takes the old drawing's x per box as a hint: Brandes–Köpf's four alignments are mixed (weights in quarters, plus a shift of the whole) to sit closest to the old places. On the decision flow, a reorder moves the other boxes 7% of the canvas diagonal on average, and a move up two rows 11%; the scoreboard target is 10%.
- **What changed.** `diff.py` matches boxes by `data-node` and arrows by `data-id`. Rows are the layout's layers when both pages give them, else boxes at one height; a schema's are columns, a sequence's its actors. Each new row takes the one old row that brings it the most boxes, so boxes that ride along when rows shift are "shifted", not "moved", and a box whose row merged into another is "moved". A sequence's messages match by `data-id`: added, removed, relabeled, and moved, which are the ones outside the longest run still in their old order, so the messages a move passes are not reported. The render verdict carries the sentences as `changed`.
- **The verdict's rows** are the layout's layers, which the renderer hands to the verdict as it does to the page. A wrapped flow lists its layers in reading order and says where its columns break (`wrapped into 3 columns: rows 1-6, rows 7-12, rows 13-18`), where rows by height mixed its columns. A schema adds its columns of tables under its `tables` line. `--outline` gives each node that row, or `column` in a schema.
- **Regeneration (P10.2).** A patch can be kept and applied again: `text` that already holds is not a conflict, and `place`, `style` and `order` rewrite what they wrote. After the spec is regenerated, each edit either shows in the new drawing or is a reported `patch-conflict` (`tests/unit/test_regeneration.py`).
- **Animation.** The new page holds the old drawing. On load, each box, and each message of a sequence, starts where it was and slides to its place (650 ms); boxes that are new fade in; removed ones fade out where they were; arrows, labels and frames that differ fade in after the boxes settle. Replay change runs it again; `prefers-reduced-motion` turns it off.
- **Pins (P10.1):** flow and arch draw a node's `pin` as a row and an x in it (4.6), and a `place` drops it. A pin that can't hold is a `constraint` warning in the verdict.
- **Not yet:** a drag that writes a pin (it writes a `place`); colors for messages; a page that applies its own patch.

### 21.5 Presenting and distribution

- **One self-contained HTML file per story,** working offline:
  - keyboard and touch navigation;
  - speaker notes and a presenter view;
  - step reveals;
  - a print stylesheet with one page per view.
- **PDF** for handouts, and for anyone who can't open a link.
- **Comments** anchored to element ids, where the host supports them.

## 22. Enterprise readiness

### 22.1 Legacy bridge (D17)

**Import:**
- PPTX: shapes, connectors, text and charts become scenes and pages.
- VSDX, draw.io and PlantUML.
- Full Mermaid.
- BPMN 2.0 XML and the ArchiMate exchange format.

**Export, as fallbacks:** vector PDF, PNG, and optionally flat PPTX (open question 8).

### 22.2 Scale

- **Pages:** the page model splits large figures across pages with off-page connectors, and supports poster sizes.
- **Drill-down:** HTML output collapses groups to N levels.
- **Budgets:** a 1,000-node layered layout in ≤ 5 s, and a 10,000-node org tree in ≤ 10 s (tree layout is linear time).
- **Beyond that:** the engine lays out each group, then composes them. The layout interface leaves room for an optional faster backend.

### 22.3 Accessibility

- Display-list items carry accessible names, descriptions and reading order.
- SVG gets `role` and `aria-*` attributes.
- HTML gets a data-table fallback for charts and a text outline for diagrams.
- Alt text is generated from the outline.
- The target is WCAG 2.2 AA, which covers Section 508 and the EU Accessibility Act.

As built in P2.17, for flow, arch, seq and schema (the diagrams that paint through `paint.Drawing`):
- The root is `role="graphics-document"` with an `aria-roledescription` ("flow diagram", "database schema"), following the WAI-ARIA Graphics Module.
- Nodes, arrows, messages, tables and groups are `role="graphics-symbol"`, each with a kind (`aria-roledescription`: "decision", "arrow", "table", ...) and a spoken name:
  - a node is its name and sub-label ("Review, owner:payments");
  - an arrow is "CI tests to Fix: fail";
  - a message is numbered ("1. Customer to Web: Submit Order");
  - a table lists its columns, with keys;
  - a group lists its members.
- What a part owns (its texts, pills, tails) and pure decoration are `aria-hidden`, so nothing is read twice. Headings, notes and the legend stay readable.
- Reading order is document order. Edges also carry `data-from-port`/`data-to-port` (a side, or a column for schemas).
- The display list reads both back: `Item.a11y` (name, kind, order) and `Item.attach`.
- Charts keep `role="img"` with a title and description until they paint through the drawing (P6).

### 22.4 Brand policy and project config

`diagonaldiagrams.toml` at the project root, and an organization config path, set:
- the brand stylesheet as policy (top of the cascade, 5.1);
- the allowed palette and fonts;
- icon folders (vendor icon packs the organization downloads);
- enabled toolkits;
- default size and locale.

The `off-brand` check reports deviations.

As built in P3.12:
- **Finding the config:** `diagonaldiagrams.toml` is found by walking up from the spec. `DIAGONALDIAGRAMS_ORG_CONFIG` names the organization's file, which applies on top.
- **Policy:** the policy sheet is a cascade layer above everything, element styles included, and its tokens win.
- **What `off-brand` judges:** values a stylesheet or element chose, not the theme or preset defaults, whose tokens the policy controls. It reports three things:
  - a declaration that a policy rule overrides with a different value;
  - a color outside `[palette] allowed` (tokens may be listed by name);
  - a first font family outside `[fonts] allowed`.
- **Where it runs:** `validate` and render both run it, so a violation stops before anything is drawn.

Font embedding respects the font's embedding permissions (the OS/2 `fsType` field). A restricted font is referenced, not embedded, with a warning.

### 22.5 Localization

- The `shaper` extension point (6.1).
- Locale-aware number and date formats.
- Mirrored page layouts for right-to-left languages.

### 22.6 Notations and industry packs

All built as toolkits:

| Pack | Contents |
| --- | --- |
| Notations | ArchiMate, full UML and SysML, BPMN 2.0 |
| Finance and strategy | Bridges, Marimekko, football field, bullet, tornado, BCG, value chain |
| Operations and quality | SPC control charts, Pareto, value-stream maps, SIPOC, FMEA |
| Clinical | Kaplan–Meier with a risk table, forest plots, CONSORT |
| Cloud and enterprise architecture | Extractors for Terraform, Kubernetes, CloudFormation, OpenAPI and dbt; icon packs from folders |
| Geo data | Country and state boundaries, shipped as a separate optional package |

Out of scope: live BI, CAD and BIM, map tiles, chemistry.

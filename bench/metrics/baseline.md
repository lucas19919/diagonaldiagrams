# Engine metrics: 2026-10-12 23:35 (b1612ee, dirty)

Python 3.14.2 on Windows-11-10.0.26200-SP0, 16 CPUs.

## Corpus

| Measure | Value |
| --- | --- |
| Figures (drawn) | 115 (113) |
| Failing the audit | 1: case-swim-review |
| Render time, total / median / p90 / max | 7014 / 20 / 41 / 3798 ms |
| Layout redraws (repair loops) | 353 |
| Time in the final audit | 571 ms |
| Audit errors by code | through 1, strike 1, shared 1 |
| Truncated texts | 4 in 2 figures |
| Arrow crossings / wire length | 12 / 58168 px |

## Generated flows

| Figure | Render ms | Redraws | Canvas | Aspect | Audit |
| --- | --- | --- | --- | --- | --- |
| gen-flow-05 | 18 | 1 | 720 × 712 | 1.011 | ok |
| gen-flow-11 | 52 | 9 | 720 × 1432 | 0.503 | ok |
| gen-flow-20 | 559 | 89 | 800 × 2272 | 0.352 | ok |
| gen-flow-40 | 3798 | 225 | 1180 × 3952 | 0.299 | ok |

## Slowest figures

| Figure | Render ms | Redraws |
| --- | --- | --- |
| gen-flow-40 | 3798 | 225 |
| gen-flow-20 | 559 | 89 |
| arch-agent-platform | 57 | 1 |
| arch-checkout | 56 | 1 |
| arch-checkout-groups | 56 | 1 |
| flow-decision | 55 | 1 |
| gen-flow-11 | 52 | 9 |
| chart-math-example | 50 | 0 |
| flow-canary | 47 | 1 |
| mmd-shop-er | 44 | 7 |

## Startup (fresh processes, median of 3)

| Measure | ms |
| --- | --- |
| `python -c pass` | 29 |
| import graph, recompiling | 1610 |
| import graph, from bytecode | 74 |
| `graph.py describe flow` | 280 |
| render flow-decision: `graph.py`, recompiling / imported from bytecode | 301 / 142 |
| render arch-checkout-groups: `graph.py`, recompiling / imported from bytecode | 310 / 154 |
| render site-signups: `graph.py`, recompiling / imported from bytecode | 321 / 150 |
| render gen-flow-40: `graph.py`, recompiling / imported from bytecode | 4036 / 3892 |

## Static counts

| Count | Value |
| --- | --- |
| Engine files | 1 |
| Total lines | 10012 |
| Largest module | graph.py (10012 lines) |
| `_c_*` chart renderers | 66 |
| Truncation calls (`_short`, `_wrap`) | 69 |
| Inline font settings | 342 |
| Function-attribute side channels | 4 (_land_rings.cache, _raster_svg.why, _render_flow_once.pos, route_edge.last_pts) |
| `SystemExit` / `sys.exit` in engine code | 85 |

## Fuzz: 200 scenes, 149 failed the audit (74.5%), 0 invalid

| Kind | Nodes | Scenes | Failed | Rate | Median ms | Max ms |
| --- | --- | --- | --- | --- | --- | --- |
| arch | 5-10 | 25 | 13 | 52% | 102 | 490 |
| arch | 11-20 | 25 | 23 | 92% | 656 | 2487 |
| arch | 21-40 | 25 | 25 | 100% | 4044 | 44677 |
| arch | 41-60 | 25 | 25 | 100% | 10394 | 60963 |
| flow | 5-10 | 25 | 3 | 12% | 83 | 526 |
| flow | 11-20 | 25 | 12 | 48% | 406 | 3640 |
| flow | 21-40 | 25 | 23 | 92% | 4371 | 19783 |
| flow | 41-60 | 25 | 25 | 100% | 7711 | 34353 |

Scenes per error code: shared 130, through 125, strike 110, intrude 13, overlap 4, clip 1, collide 1

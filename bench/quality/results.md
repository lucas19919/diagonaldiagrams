# Quality benchmark: full tables

496 blind judgments, each answering two questions (clearer, better looking). Cells are dd's win rate against the named tool: wins / judgments, Sonnet and Opus, both orders.

## All pairs

|  | Pele slide clearer | Pele slide looks | Pele column clearer | Pele column looks | Mermaid slide clearer | Mermaid slide looks | Mermaid column clearer | Mermaid column looks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 85% (106/124) | 98% (121/124) | 56% (70/124) | 84% (104/124) | 97% (120/124) | 99% (123/124) | 65% (81/124) | 86% (107/124) |

## By figure set

| set | Pele slide clearer | Pele slide looks | Pele column clearer | Pele column looks | Mermaid slide clearer | Mermaid slide looks | Mermaid column clearer | Mermaid column looks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agent figures | 91% (29/32) | 100% (32/32) | 72% (23/32) | 88% (28/32) | 94% (30/32) | 97% (31/32) | 59% (19/32) | 78% (25/32) |
| same Mermaid source | 84% (57/68) | 96% (65/68) | 47% (32/68) | 78% (53/68) | 99% (67/68) | 100% (68/68) | 62% (42/68) | 85% (58/68) |
| dd native spec vs the Mermaid translation | 83% (20/24) | 100% (24/24) | 62% (15/24) | 96% (23/24) | 96% (23/24) | 100% (24/24) | 83% (20/24) | 100% (24/24) |

## Flowcharts by size (agent figures and the same-source bench flows)

| size | Pele slide clearer | Pele slide looks | Pele column clearer | Pele column looks | Mermaid slide clearer | Mermaid slide looks | Mermaid column clearer | Mermaid column looks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 steps | 100% (16/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) |
| 11 steps | 81% (13/16) | 100% (16/16) | 100% (16/16) | 100% (16/16) | 88% (14/16) | 94% (15/16) | 100% (16/16) | 100% (16/16) |
| 20 steps | 100% (16/16) | 100% (16/16) | 69% (11/16) | 94% (15/16) | 100% (16/16) | 100% (16/16) | 56% (9/16) | 94% (15/16) |
| 40 steps | 100% (16/16) | 100% (16/16) | 19% (3/16) | 62% (10/16) | 100% (16/16) | 100% (16/16) | 6% (1/16) | 50% (8/16) |

### Same source only

| size | Pele slide clearer | Pele slide looks | Pele column clearer | Pele column looks | Mermaid slide clearer | Mermaid slide looks | Mermaid column clearer | Mermaid column looks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 steps | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) |
| 11 steps | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) |
| 20 steps | 100% (8/8) | 100% (8/8) | 75% (6/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 75% (6/8) | 100% (8/8) |
| 40 steps | 100% (8/8) | 100% (8/8) | 12% (1/8) | 62% (5/8) | 100% (8/8) | 100% (8/8) | 12% (1/8) | 75% (6/8) |

### Agent figures only

| size | Pele slide clearer | Pele slide looks | Pele column clearer | Pele column looks | Mermaid slide clearer | Mermaid slide looks | Mermaid column clearer | Mermaid column looks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 steps | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) |
| 11 steps | 62% (5/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 75% (6/8) | 88% (7/8) | 100% (8/8) | 100% (8/8) |
| 20 steps | 100% (8/8) | 100% (8/8) | 62% (5/8) | 88% (7/8) | 100% (8/8) | 100% (8/8) | 38% (3/8) | 88% (7/8) |
| 40 steps | 100% (8/8) | 100% (8/8) | 25% (2/8) | 62% (5/8) | 100% (8/8) | 100% (8/8) | 0% (0/8) | 25% (2/8) |

## Other diagram types, same Mermaid source

| type | Pele slide clearer | Pele slide looks | Pele column clearer | Pele column looks | Mermaid slide clearer | Mermaid slide looks | Mermaid column clearer | Mermaid column looks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flowchart (example) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) | 100% (4/4) |
| arch, subgraphs (2) | 100% (8/8) | 100% (8/8) | 0% (0/8) | 38% (3/8) | 100% (8/8) | 100% (8/8) | 25% (2/8) | 50% (4/8) |
| sequence (3) | 50% (6/12) | 92% (11/12) | 42% (5/12) | 100% (12/12) | 100% (12/12) | 100% (12/12) | 92% (11/12) | 100% (12/12) |
| schema (2) | 62% (5/8) | 88% (7/8) | 0% (0/8) | 50% (4/8) | 100% (8/8) | 100% (8/8) | 25% (2/8) | 75% (6/8) |
| ER (example) | 50% (2/4) | 75% (3/4) | 0% (0/4) | 25% (1/4) | 75% (3/4) | 100% (4/4) | 0% (0/4) | 50% (2/4) |

## Other diagram types, dd from its native spec

| type | Pele slide clearer | Pele slide looks | Pele column clearer | Pele column looks | Mermaid slide clearer | Mermaid slide looks | Mermaid column clearer | Mermaid column looks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| arch (2) | 88% (7/8) | 100% (8/8) | 88% (7/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) |
| sequence (2) | 62% (5/8) | 100% (8/8) | 75% (6/8) | 100% (8/8) | 88% (7/8) | 100% (8/8) | 100% (8/8) | 100% (8/8) |
| schema (2) | 100% (8/8) | 100% (8/8) | 25% (2/8) | 88% (7/8) | 100% (8/8) | 100% (8/8) | 50% (4/8) | 100% (8/8) |

## By judge

| judge | Pele slide clearer | Pele slide looks | Pele column clearer | Pele column looks | Mermaid slide clearer | Mermaid slide looks | Mermaid column clearer | Mermaid column looks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sonnet | 87% (54/62) | 95% (59/62) | 56% (35/62) | 77% (48/62) | 97% (60/62) | 98% (61/62) | 65% (40/62) | 81% (50/62) |
| Opus | 84% (52/62) | 100% (62/62) | 56% (35/62) | 90% (56/62) | 97% (60/62) | 100% (62/62) | 66% (41/62) | 92% (57/62) |

## Consistency

- The two orders of a pair (same judge, placement and question) agree in 91% of 496 cases.
- dd wins 86% (426/496) when shown first and 82% (406/496) when shown second.

## Text size where the figure lands

Median text size in px after fitting each figure to the placement (measure.py): slide = 1600 x 900, page = A4 portrait at 96 dpi inside 72 px margins (650 x 980, not enlarged), column = 700 px wide, scrolled. Bench flows, both sources per size.

| steps | placement | dd | Pele | Mermaid |
| --- | --- | --- | --- | --- |
| 5 | slide | 19.4–20.7 | 21.8–24.1 | 17.1–18.9 |
| 5 | page | 13.0 | 16.0 | 14.0 |
| 5 | column | 13.0 | 16.0 | 14.0 |
| 11 | slide | 9.8 | 10.6 | 7.7–7.9 |
| 11 | page | 11.8 | 12.7 | 9.2–9.4 |
| 11 | column | 13.0 | 16.0 | 14.0 |
| 20 | slide | 14.5 | 5.6–5.8 | 4.1–4.5 |
| 20 | page | 7.7–8.2 | 6.7–6.9 | 4.9–5.4 |
| 20 | column | 7.9–8.4 | 16.0 | 14.0 |
| 40 | slide | 8.5 | 2.7–2.8 | 2.0–2.2 |
| 40 | page | 5.1–5.4 | 3.3–3.4 | 2.4–2.6 |
| 40 | column | 5.2–5.5 | 16.0 | 14.0 |

## Why dd lost: themes

160 judgments went against dd. Each is tagged with every theme its reason names (cluster.py; losses.md lists them all with their tags), so a loss can count under several themes.

| theme | losses | slide | column | clearer | looks |
| --- | --- | --- | --- | --- | --- |
| Figure shrunk to fit the placement, so its text gets too small | 121 | 6 | 115 | 84 | 37 |
| Wrapped into columns: the reading order snakes, long connectors run between columns | 53 | 0 | 53 | 40 | 13 |
| ER relations: no crow's feet, cardinality only as text, some relations without arrowheads | 49 | 8 | 41 | 40 | 9 |
| Arrows share a trunk, merge or overlap | 29 | 1 | 28 | 19 | 10 |
| Wasted space: the figure is too wide or sparse for its content | 28 | 0 | 28 | 18 | 10 |
| Default text too small or too pale at full size | 27 | 12 | 15 | 25 | 2 |
| Doubled relation label (1:N 1:N) | 25 | 6 | 19 | 17 | 8 |
| Mermaid input dropped: second lines flattened, cylinders, classDef colours | 25 | 2 | 23 | 13 | 12 |
| Sequence: a USER tag over 'User' instead of an actor icon; participants not repeated at the bottom | 16 | 6 | 10 | 15 | 1 |
| Long detours: loop-backs and skips routed far around the figure | 14 | 0 | 14 | 9 | 5 |
| Edge labels float away from their arrows or are crossed by lines | 10 | 7 | 3 | 8 | 2 |
| Misaligned boxes or kinked arrows | 7 | 3 | 4 | 5 | 2 |
| Steps not numbered | 4 | 1 | 3 | 4 | 0 |
| Legend or chrome adds clutter | 3 | 0 | 3 | 3 | 0 |

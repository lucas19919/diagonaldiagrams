# fit-column: dd's win rate in the column, first run → this run

| against | clearer | better looking |
| --- | --- | --- |
| Pele | 56% (70/124) → **68% (84/124)** | 84% (104/124) → **78% (97/124)** |
| Mermaid | 65% (81/124) → **77% (95/124)** | 86% (107/124) → **86% (107/124)** |
| both | 61% (151/248) → **72% (179/248)** | 85% (211/248) → **82% (204/248)** |

Flowcharts by size (agent figures and same-source figures together):

| steps | vs Pele, clearer / looks | vs Mermaid, clearer / looks |
| --- | --- | --- |
| 5 | 100% (16/16) → **100% (16/16)** / 100% (16/16) → **100% (16/16)** | 100% (16/16) → **100% (16/16)** / 100% (16/16) → **100% (16/16)** |
| 11 | 100% (16/16) → **100% (16/16)** / 100% (16/16) → **100% (16/16)** | 100% (16/16) → **100% (16/16)** / 100% (16/16) → **100% (16/16)** |
| 20 | 69% (11/16) → **100% (16/16)** / 94% (15/16) → **100% (16/16)** | 56% (9/16) → **100% (16/16)** / 94% (15/16) → **100% (16/16)** |
| 40 | 19% (3/16) → **100% (16/16)** / 62% (10/16) → **100% (16/16)** | 6% (1/16) → **100% (16/16)** / 50% (8/16) → **100% (16/16)** |

Other types, clearer (L: one Mermaid source drawn by each tool; N: dd from its native spec):

| type | family | vs Pele | vs Mermaid |
| --- | --- | --- | --- |
| arch | L | 0% (0/8) → **0% (0/8)** | 25% (2/8) → **0% (0/8)** |
| arch | N | 88% (7/8) → **50% (4/8)** | 100% (8/8) → **50% (4/8)** |
| sequence | L | 42% (5/12) → **33% (4/12)** | 92% (11/12) → **83% (10/12)** |
| sequence | N | 75% (6/8) → **62% (5/8)** | 100% (8/8) → **100% (8/8)** |
| schema | L | 0% (0/8) → **0% (0/8)** | 25% (2/8) → **12% (1/8)** |
| schema | N | 25% (2/8) → **38% (3/8)** | 50% (4/8) → **50% (4/8)** |
| ER example | L | 0% (0/4) → **0% (0/4)** | 0% (0/4) → **0% (0/4)** |
| flow example | L | 100% (4/4) → **100% (4/4)** | 100% (4/4) → **100% (4/4)** |

| judge | clearer | better looking |
| --- | --- | --- |
| Sonnet | 60% (75/124) → **72% (89/124)** | 79% (98/124) → **79% (98/124)** |
| Opus | 61% (76/124) → **73% (90/124)** | 91% (113/124) → **85% (106/124)** |

Pairs whose clarity verdict moved (dd's wins of 4):

| pair | clearer | better looking |
| --- | --- | --- |
| A-20-r1-dd~mermaid | 0 → 4 | 3 → 4 |
| A-20-r1-dd~pele | 3 → 4 | 3 → 4 |
| A-20-r2-dd~mermaid | 3 → 4 | 4 → 4 |
| A-20-r2-dd~pele | 2 → 4 | 4 → 4 |
| A-40-r1-dd~mermaid | 0 → 4 | 0 → 4 |
| A-40-r1-dd~pele | 1 → 4 | 2 → 4 |
| A-40-r2-dd~mermaid | 0 → 4 | 2 → 4 |
| A-40-r2-dd~pele | 1 → 4 | 3 → 4 |
| L-bench-20-a-dd~mermaid | 3 → 4 | 4 → 4 |
| L-bench-20-a-dd~pele | 3 → 4 | 4 → 4 |
| L-bench-20-b-dd~mermaid | 3 → 4 | 4 → 4 |
| L-bench-20-b-dd~pele | 3 → 4 | 4 → 4 |
| L-bench-40-a-dd~mermaid | 0 → 4 | 3 → 4 |
| L-bench-40-a-dd~pele | 1 → 4 | 3 → 4 |
| L-bench-40-b-dd~mermaid | 1 → 4 | 3 → 4 |
| L-bench-40-b-dd~pele | 0 → 4 | 2 → 4 |
| L-ex-seq-checkout-dd~pele | 1 → 0 | 4 → 4 |
| L-ref-arch-checkout-groups-dd~mermaid | 2 → 0 | 4 → 0 |
| L-ref-schema-ecommerce-dd~mermaid | 2 → 1 | 4 → 4 |
| L-ref-seq-toolloop-dd~mermaid | 3 → 2 | 4 → 4 |
| N-ref-arch-checkout-groups-dd~mermaid | 4 → 0 | 4 → 2 |
| N-ref-arch-checkout-groups-dd~pele | 3 → 0 | 4 → 0 |
| N-ref-schema-ecommerce-dd~pele | 2 → 3 | 4 → 4 |
| N-ref-seq-toolloop-dd~pele | 2 → 1 | 4 → 4 |

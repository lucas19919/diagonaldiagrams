# fit-column-fanout: dd's win rate in the column, fit-column-arch → this run (pairs with 'ref-arch')

| against | clearer | better looking |
| --- | --- | --- |
| Pele | 44% (7/16) → **38% (6/16)** | 62% (10/16) → **81% (13/16)** |
| Mermaid | 62% (10/16) → **69% (11/16)** | 100% (16/16) → **100% (16/16)** |
| both | 53% (17/32) → **53% (17/32)** | 81% (26/32) → **91% (29/32)** |

Other types, clearer (L: one Mermaid source drawn by each tool; N: dd from its native spec):

| type | family | vs Pele | vs Mermaid |
| --- | --- | --- | --- |
| arch | L | 0% (0/8) → **0% (0/8)** | 38% (3/8) → **50% (4/8)** |
| arch | N | 88% (7/8) → **75% (6/8)** | 88% (7/8) → **88% (7/8)** |

| judge | clearer | better looking |
| --- | --- | --- |
| Sonnet | 56% (9/16) → **56% (9/16)** | 75% (12/16) → **81% (13/16)** |
| Opus | 50% (8/16) → **50% (8/16)** | 88% (14/16) → **100% (16/16)** |

Every pair, dd's wins of 4 (first run → fit-column-arch → this run):

| pair | clearer | better looking |
| --- | --- | --- |
| L-ref-arch-agent-platform-dd~mermaid | 0 → 1 → 4 | 0 → 4 → 4 |
| L-ref-arch-agent-platform-dd~pele | 0 → 0 → 0 | 0 → 0 → 3 |
| L-ref-arch-checkout-groups-dd~mermaid | 2 → 2 → 0 | 4 → 4 → 4 |
| L-ref-arch-checkout-groups-dd~pele | 0 → 0 → 0 | 3 → 2 → 2 |
| N-ref-arch-agent-platform-dd~mermaid | 4 → 4 → 4 | 4 → 4 → 4 |
| N-ref-arch-agent-platform-dd~pele | 4 → 4 → 4 | 4 → 4 → 4 |
| N-ref-arch-checkout-groups-dd~mermaid | 4 → 3 → 3 | 4 → 4 → 4 |
| N-ref-arch-checkout-groups-dd~pele | 3 → 3 → 2 | 4 → 4 → 4 |

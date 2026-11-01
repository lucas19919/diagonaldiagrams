# Benchmarks

The comparisons the README summarises, with the scripts to rerun them: `speed/` (render time per call), `tokens/` (an agent's tokens per figure) and `quality/` (blind pairwise judging against Pele and Mermaid CLI). The numbers below are as measured, losses included. Method: [`tokens/README.md`](tokens/README.md) and [`quality/README.md`](quality/README.md).

## Measured

diagonaldiagrams 0.8.0 against [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) and [Pele](https://pele.run), on 2026-10-19. The same four flowcharts, 5, 11, 20 and 40 steps.

## Speed

Milliseconds for one figure, a new process each time. diagonaldiagrams was remeasured the same day: median of 7 calls, from bytecode ([`speed/cli-2026-10-19.json`](speed/cli-2026-10-19.json)). Pele and Mermaid CLI are that day's earlier run, not rerun.

![Bar chart of one 20-step flowchart, a new process each time: diagonaldiagrams 152 ms, Pele 101 ms, Mermaid CLI 2,340 ms, about 15 times as long.](../docs/gallery/bench-speed.svg)

| | 5 steps | 11 steps | 20 steps | 40 steps |
| --- | ---: | ---: | ---: | ---: |
| Pele, a new process | 95 | 104 | 101 | 107 |
| diagonaldiagrams | 136 | 142 | 152 | 154 |
| Mermaid CLI | 2,333 | 2,399 | 2,340 | 2,556 |

A diagonaldiagrams call is about 1.4 times a Pele process, and about 16 times faster than Mermaid CLI. Mermaid starts Node and a browser on every call. Pele only draws. diagonaldiagrams also audits the drawing and writes the page and the receipt.

## Tokens

Each point is a fresh Claude Sonnet agent with one prose task and nothing else. Two runs. Tokens are what the agent wrote, what came back, files it read, and screenshots. The harness and thinking are left out.

![Line chart of tokens per flowchart. diagonaldiagrams stays between 4.4k and 6.4k. Mermaid CLI climbs from 1.8k to 15.4k. Pele stays under 2.7k until 6.3k at 40 steps.](../docs/gallery/bench-tools-0.8.svg)

| Steps | diagonaldiagrams | Mermaid CLI | Pele |
| --- | ---: | ---: | ---: |
| 5 | 4.4k | 1.8k | 2.6k |
| 11 | 6.0k | 2.8k | 1.7k |
| 20 | 5.1k | 4.0k | 1.3k |
| 40 | 6.4k | 15.4k | 6.3k |

All eight runs:

| | Tokens | Calls | Screenshots | Time |
| --- | ---: | ---: | ---: | ---: |
| Pele | 23.9k | 57 | 18 | 5 min |
| diagonaldiagrams | 43.8k | 69 | 9 | 7 min |
| Mermaid CLI | 47.8k | 79 | 32 | 13 min |

Pele cost the least, because the model already knows Mermaid and reads no skill. diagonaldiagrams stays about the same at every size. Of its tokens, about 1.4k a run is reading the skill. Mermaid CLI grows fastest, and at 40 steps most of its tokens are screenshots of a figure several thousand pixels tall. Every one of the 24 figures passed this audit. Two runs is a small sample: single runs differed by up to 3.5 times.

An earlier run, on 0.5.0 (2026-10-04), had different prompts and is not comparable. It is in [`docs/data/bench_tools.csv`](../docs/data/bench_tools.csv).

## Quality

Blind pairs. Two judges, both orders, two questions: which is clearer, and which looks better. The chart is the share diagonaldiagrams won on clarity; past the 50% line it won.

![Bar chart of the share of blind judgments calling diagonaldiagrams clearer, with a line at 50 percent. Against Pele: 85 percent on a slide, 100 for column flows, 75 for our architecture, 0 for architecture translated from Mermaid. Against Mermaid CLI: 97, 100, 88 and 50.](../docs/gallery/bench-quality.svg)

| | vs Pele | vs Mermaid |
| --- | ---: | ---: |
| On a slide, every figure | 85% (106/124) | 97% (120/124) |
| In a column, flows, each of 5, 11, 20, 40 steps | 100% (16/16) | 100% (16/16) |
| In a column, architecture we wrote | 75% (6/8) | 88% (7/8) |
| In a column, that architecture translated from Mermaid | 0% (0/8) | 50% (4/8) |

The column numbers are after `--fit column`, which keeps a README column near full-size text. The translated-architecture loss is one figure: the agent platform won 4 of 4 against Mermaid, and the checkout groups won none against either tool.


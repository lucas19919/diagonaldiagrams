# diagonaldiagrams

[![PyPI](https://img.shields.io/pypi/v/diagonaldiagrams)](https://pypi.org/project/diagonaldiagrams/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/lucas19919/diagonaldiagrams/blob/master/LICENSE)

diagonaldiagrams is a Python library and MCP server that lets an AI agent draw diagrams and charts as SVG, and check them for overlapping text, arrows through boxes and text that spills, before showing them.

**[Site](https://lucas19919.github.io/diagonaldiagrams/)**: filmed examples, benchmarks and a gallery.

![An architecture diagram drawn by diagonaldiagrams, with one chat request traced through an AI agent platform](https://lucas19919.github.io/diagonaldiagrams/showcase/hero.gif)

## How it works

1. **Describe.** The agent writes a short description of the figure, in Mermaid, JSON or CSV.
2. **Draw.** diagonaldiagrams lays it out and saves an SVG.
3. **Check.** It audits the drawing and prints one line of JSON: all clear, or what is wrong and how to fix it. The agent reads that line instead of a screenshot.

```text
$ diagonaldiagrams mermaid flow.mmd -o flow.svg
{"ok": true, "svg": "flow.svg", ..., "items": 3,
 "layout": ["row 1: Start", "row 2: Ready? (decision)", "row 3: Done"]}
```

When `ok` is `false`, each error comes with a `fix`.

## Install

Needs Python 3.11 or newer.

**Command line**

```bash
pip install diagonaldiagrams
```

**MCP** (Cursor, Claude Desktop and other MCP apps). Add this to the app's MCP settings; it needs [uv](https://docs.astral.sh/uv/). The server is in the [official MCP registry](https://registry.modelcontextprotocol.io) as `io.github.lucas19919/diagonaldiagrams`.

```json
{
  "mcpServers": {
    "diagonaldiagrams": { "command": "uvx", "args": ["diagonaldiagrams", "mcp"] }
  }
}
```

Claude Desktop can also open the `.mcpb` file from the [latest release](https://github.com/lucas19919/diagonaldiagrams/releases/latest).

**Claude Code**

```text
/plugin marketplace add lucas19919/diagonaldiagrams
/plugin install diagonaldiagrams@diagonaldiagrams
```

**Any other agent:** tell it `Install diagonaldiagrams from https://github.com/lucas19919/diagonaldiagrams`. It follows the [install skill](https://github.com/lucas19919/diagonaldiagrams/blob/master/.agents/skills/diagonaldiagrams-install/SKILL.md), then draws with the [drawing skill](https://github.com/lucas19919/diagonaldiagrams/blob/master/.agents/skills/graph-engine/SKILL.md). The short version for models is [`llms.txt`](https://github.com/lucas19919/diagonaldiagrams/blob/master/llms.txt).

## What it draws

| Command | Input | Draws |
| --- | --- | --- |
| `mermaid` | `flowchart`, `sequenceDiagram`, `erDiagram` | A flow, a sequence, or a schema |
| `flow`, `arch`, `seq`, `schema` | JSON | The same four, from a spec |
| `iso` | JSON | A layer stack in isometric 3D, with links between layers |
| `bar`, `line`, `scatter` | CSV | A comparison, a trend, a relationship |
| `geo` | CSV or GeoJSON | Places on a built-in coastline |
| `chart <type>` | CSV or JSON | About 60 more |

- `describe <type>` prints the spec shape for any figure type.
- `--fit column` sizes a figure for a README or docs page. `slide` is the default, and `page` is for print.
- `story` turns one figure into several views in one page, and `--gif` films it when ffmpeg is installed.
- `apply` edits a spec with a JSON patch, and `export` writes PNG, PDF, draw.io or Excalidraw files.

## How it compares

Measured on 2026-10-19 against [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) and [Pele](https://pele.run), on version 0.8.0, with the same four flowcharts of 5 to 40 steps.

- **Speed.** A 20-step flowchart takes 152 ms, about 15 times faster than Mermaid CLI (2,340 ms) and about 1.5 times slower than Pele (101 ms).
- **Tokens.** An agent used 4.4k to 6.4k tokens per figure at every size. At 5 to 20 steps Pele and Mermaid CLI used fewer (1.3k to 4.0k). At 40 steps diagonaldiagrams used 6.4k, Pele 6.3k and Mermaid CLI 15.4k. This is two runs, so treat it as a small sample.
- **Quality.** In blind pairs, diagonaldiagrams was judged clearer than Pele 85% of the time and than Mermaid CLI 97% of the time on slide-sized figures. It lost where an architecture translated from Mermaid was sized for a narrow column: 0 of 8 against Pele.

The full tables, the method and the scripts to rerun them are in [`bench/`](https://github.com/lucas19919/diagonaldiagrams/tree/master/bench).

## Develop

```bash
python -m unittest discover tests/unit   # unit tests
python tests_smoke.py                    # the command-line contract
python scripts/golden.py                 # the reference figures, byte for byte
```

How the engine is put together: [`docs/ARCHITECTURE.md`](https://github.com/lucas19919/diagonaldiagrams/blob/master/docs/ARCHITECTURE.md). How releases are made: [`PUBLISHING.md`](https://github.com/lucas19919/diagonaldiagrams/blob/master/PUBLISHING.md).

## License

MIT. See [LICENSE](https://github.com/lucas19919/diagonaldiagrams/blob/master/LICENSE).

<!-- mcp-name: io.github.lucas19919/diagonaldiagrams -->

#!/usr/bin/env python3
"""Regenerate .agents/skills/graph-engine/references/schemas.md from `describe`.

    py -3 scripts/schemas_ref.py

The reference is a snapshot of `diagonaldiagrams describe <type>` for the types an agent reaches
for most; the source of truth is DESCRIBE in diagonaldiagrams/describe.py.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from diagonaldiagrams.describe import DESCRIBE  # noqa: E402

TYPES = ["scatter", "flow", "arch", "seq", "schema", "mermaid", "bar", "line", "geo",
         "export", "doc", "monitor", "extract", "sync"]
OUT = os.path.join(REPO, ".agents", "skills", "graph-engine", "references", "schemas.md")


def main():
    parts = ["# schemas.md — generated from `diagonaldiagrams describe <type>`",
             "Source of truth: DESCRIBE in diagonaldiagrams/describe.py. Regenerate with "
             "`py -3 scripts/schemas_ref.py`; `describe` lists every other type.", ""]
    for t in TYPES:
        parts += [f"## {t}", "```json", json.dumps(DESCRIBE[t], indent=2, ensure_ascii=False), "```", ""]
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts))
    print(f"wrote {len(TYPES)} types to {os.path.relpath(OUT, REPO)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""graph.py: run diagonaldiagrams from a checkout.

The engine is the diagonaldiagrams/ package next to this file. This shim keeps
`py graph.py <command> ...` working, and `import graph` (the browser playground calls
graph.cli()).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagonaldiagrams import __version__  # noqa: E402
from diagonaldiagrams.cli import cli  # noqa: E402

if __name__ == "__main__":
    cli()

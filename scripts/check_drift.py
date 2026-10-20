#!/usr/bin/env python3
"""Architecture drift gate for git hooks or CI pipelines.
Usage:
  py scripts/check_drift.py [--ci] [--base HEAD~1]
"""
import os, subprocess, sys

GRAPH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "graph.py")


def main():
    cmd = [sys.executable, GRAPH, "monitor"] + sys.argv[1:]
    res = subprocess.run(cmd)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()

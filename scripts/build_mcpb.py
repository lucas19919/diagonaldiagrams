#!/usr/bin/env python3
"""Build dist/diagonaldiagrams-VERSION.mcpb, the one-click desktop bundle: .mcpb/manifest.json and the package, zipped.

    py -3 scripts/build_mcpb.py

The package uses the standard library only, so the bundle needs nothing but a Python on the machine.
"""
import json
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    with open(os.path.join(REPO, ".mcpb", "manifest.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    dest = os.path.join(REPO, "dist", f"diagonaldiagrams-{version}.mcpb")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(REPO, ".mcpb", "manifest.json"), "manifest.json")
        z.write(os.path.join(REPO, "LICENSE"), "LICENSE")
        for root, dirs, files in os.walk(os.path.join(REPO, "diagonaldiagrams")):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(files):
                path = os.path.join(root, name)
                z.write(path, os.path.relpath(path, REPO).replace(os.sep, "/"))
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())

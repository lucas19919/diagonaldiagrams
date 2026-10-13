#!/usr/bin/env python3
"""Compare the audit with an earlier version of it, issue for issue (docs/PLAN.md, P2.5).

    py -3 scripts/audit_parity.py OLD_AUDIT.py [--fuzz N]

OLD_AUDIT.py is an earlier diagonaldiagrams/audit.py, e.g. from `git show REV:diagonaldiagrams/audit.py`.
Both audits read the same SVGs: every golden figure, the gallery, and N fuzz scenes rendered now.
Exit 0 when every issue list (codes, messages, places, order) and the arrow stats agree.
"""
import argparse
import glob
import importlib.util
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "tests", "fuzz"))


def load_old(path):
    spec = importlib.util.spec_from_file_location("diagonaldiagrams._audit_parity_old", path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "diagonaldiagrams"
    spec.loader.exec_module(mod)
    return mod


def canvas(root):
    vb = root.get("viewBox", "").split()
    return (float(vb[2]), float(vb[3])) if len(vb) == 4 else (0, 0)


def fuzz_svgs(n, work):
    import gen
    import golden
    out = []
    for i in range(n):
        kind = ("flow", "arch")[i % 2]
        size = (6, 14, 24, 36)[(i // 2) % 4]
        spec = gen.make(kind, 1000 + i, size)
        path = os.path.join(work, f"{kind}-{i}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f)
        svg = os.path.join(work, f"{kind}-{i}.svg")
        golden.run_cli([kind, path, "-o", svg, "--no-audit"])
        if os.path.exists(svg):
            out.append(svg)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("--fuzz", type=int, default=80)
    a = ap.parse_args()
    import diagonaldiagrams.audit as new
    old = load_old(a.old)
    work = tempfile.mkdtemp(prefix="parity-")
    files = sorted(glob.glob(os.path.join(REPO, "tests", "golden", "*.svg")))
    files += sorted(glob.glob(os.path.join(REPO, "docs", "gallery", "*.svg")))
    files += fuzz_svgs(a.fuzz, work)
    differ, issues = [], 0
    for f in files:
        root = ET.parse(f).getroot()
        W, H = canvas(root)
        s_old, s_new = {"crossings": 0, "wire": 0.0}, {"crossings": 0, "wire": 0.0}
        i_old = old._svg_geometry(root, W, H, s_old)
        i_new = new._svg_geometry(root, W, H, s_new)
        issues += len(i_new)
        if i_old != i_new or s_old != s_new:
            differ.append((os.path.relpath(f, REPO) if f.startswith(REPO) else os.path.basename(f), len(i_old), len(i_new)))
        r_old, r_new = old._audit_file(f), new._audit_file(f)
        if r_old != r_new:
            differ.append((os.path.basename(f) + " (_audit_file)", len(r_old.get("errors", [])), len(r_new.get("errors", []))))
    if differ:
        print(f"{len(differ)} of {len(files)} figures differ:")
        for name, n_old, n_new in differ[:20]:
            print(f"  {name}: {n_old} issues before, {n_new} now")
        return 1
    print(f"parity: {len(files)} figures, {issues} issues, identical in order, text and stats")
    return 0


if __name__ == "__main__":
    sys.exit(main())

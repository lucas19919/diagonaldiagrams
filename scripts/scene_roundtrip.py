#!/usr/bin/env python3
"""v1 spec -> scene -> v1 spec draws the same bytes (docs/PLAN.md, P2.3).

    py -3 scripts/scene_roundtrip.py            # the golden corpus's flow, arch, seq, schema and Mermaid inputs
    py -3 scripts/scene_roundtrip.py --fuzz 200 # also that many generated specs, against their direct render

Each input goes through inputs.v1.from_v1, scene.normalize and inputs.v1.to_v1, is drawn with the
same flags, and its SVG is compared with the golden file (or, for fuzz specs, with the original
spec drawn the same way). Exit 1 on any difference or normalize error.
"""
import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)
import golden  # noqa: E402

KINDS = ("flow", "arch", "seq", "schema")


def round_trip(spec, kind):
    from diagonaldiagrams.inputs.v1 import from_v1, to_v1
    from diagonaldiagrams.scene import check
    scene, errors, _ = check(from_v1(spec, kind))
    if errors:
        return None, errors
    _, back, _ = to_v1(scene)
    return back, []


def draw(argv, spec_path, outdir, name):
    entry = {"name": name, "argv": [argv[0], spec_path] + argv[2:]}
    return golden.render(entry, outdir)["svg"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fuzz", type=int, default=0, help="also round-trip this many generated specs")
    args = ap.parse_args(argv)
    from diagonaldiagrams.mermaid import load_spec
    out = tempfile.mkdtemp(prefix="dd-roundtrip-")
    bad, n = [], 0
    for e in golden.load_corpus():
        cmd = e["argv"][0]
        if cmd not in KINDS + ("mermaid",):
            continue
        spec = load_spec(os.path.join(REPO, e["argv"][1]))
        kind = cmd
        if cmd == "mermaid":
            from diagonaldiagrams.inputs.v1 import detect
            kind = detect(spec)
        back, errors = round_trip(spec, kind)
        n += 1
        with open(os.path.join(golden.GOLDEN, e["name"] + ".json"), encoding="utf-8") as f:
            refused = json.load(f)["exit"] != 0
        if errors or refused:
            if not (errors and refused):  # a spec v1 refuses, the scene must refuse too, and only those
                bad.append((e["name"], f"normalize: {errors[0]['msg']}" if errors else "v1 refuses it; the scene doesn't"))
            continue
        path = os.path.join(out, e["name"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(back, f)
        svg = draw([kind] + e["argv"][1:], path, out, e["name"])
        with open(os.path.join(golden.GOLDEN, e["name"] + ".svg"), encoding="utf-8", newline="") as f:
            want = f.read()
        if (svg or "").replace("\r\n", "\n") != want.replace("\r\n", "\n"):
            bad.append((e["name"], "svg differs"))
    if args.fuzz:
        sys.path.insert(0, os.path.join(REPO, "tests", "fuzz"))
        import gen
        for i in range(args.fuzz):
            kind = ("flow", "arch")[i % 2]
            spec = gen.make(kind, i, 4 + i % 9)  # up to 12 nodes keeps the redraw loops short
            src = os.path.join(out, f"fuzz{i}.json")
            with open(src, "w", encoding="utf-8") as f:
                json.dump(spec, f)
            back, errors = round_trip(spec, kind)
            n += 1
            if errors:
                bad.append((f"fuzz{i}", f"normalize: {errors[0]['msg']}"))
                continue
            path = os.path.join(out, f"fuzz{i}-back.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(back, f)
            if draw([kind, ""], src, out, f"fuzz{i}") != draw([kind, ""], path, out, f"fuzz{i}-back"):
                bad.append((f"fuzz{i}", "svg differs"))
    for name, why in bad:
        print(f"  {name}: {why}")
    print(f"{n - len(bad)} of {n} specs draw the same after v1 -> scene -> v1")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

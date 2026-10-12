#!/usr/bin/env python3
"""Fuzz the layout: render seeded random flow and arch specs, count audit failures (docs/PLAN.md, P0.3).

    py -3 tests/fuzz/run.py                       # 200 scenes, summary on stdout
    py -3 tests/fuzz/run.py --n 1000 --out f.json # write the full result
    py -3 tests/fuzz/run.py --keep out/fuzz       # also save each failing spec and its SVG
    py -3 tests/fuzz/run.py --one flow 17 33      # render one scene (kind, seed, nodes) and print it
    py -3 tests/fuzz/run.py --strict              # exit 1 if any scene fails (P4.7 turns this on in CI)

Scene i uses seed BASE+i; kinds alternate and sizes cycle through the buckets, so the same
arguments always render the same scenes. A failure is a render whose audit reports errors.
A spec that fails validation is a generator bug and is counted apart.
"""
import argparse
import collections
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import gen  # noqa: E402
import golden  # noqa: E402

BUCKETS = [(5, 10), (11, 20), (21, 40), (41, 60)]


def scenes(n, base, kinds):
    for i in range(n):
        kind = kinds[i % len(kinds)]
        lo, hi = BUCKETS[(i // len(kinds)) % len(BUCKETS)]
        seed = base + i
        size = lo + (seed * 7919) % (hi - lo + 1)
        yield kind, seed, size, f"{lo}-{hi}"


def render_one(kind, seed, size, work):
    spec = gen.make(kind, seed, size)
    path = os.path.join(work, f"{kind}-{seed}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    svg = os.path.join(work, f"{kind}-{seed}.svg")
    t0 = time.perf_counter()
    code, out, err = golden.run_cli([kind, path, "-o", svg])
    ms = (time.perf_counter() - t0) * 1000.0
    verdict = golden._last_json(out) or {}
    return spec, path, svg, ms, verdict, (out + err)


def run(n, base, kinds, keep=None):
    work = tempfile.mkdtemp(prefix="fuzz-")
    rows = []
    try:
        for kind, seed, size, bucket in scenes(n, base, kinds):
            spec, path, svg, ms, verdict, raw = render_one(kind, seed, size, work)
            invalid = verdict.get("stage") == "validate" or not verdict
            codes = sorted(e.get("code") or "?" for e in verdict.get("errors", [])) if not invalid else []
            row = {"kind": kind, "seed": seed, "nodes": size, "bucket": bucket, "ms": round(ms, 1),
                   "ok": bool(verdict.get("ok")), "invalid": invalid, "codes": codes}
            if invalid:
                row["detail"] = (verdict.get("errors") or [{"msg": raw[-300:]}])[:3]
            rows.append(row)
            if keep and not row["ok"]:
                os.makedirs(keep, exist_ok=True)
                shutil.copy(path, os.path.join(keep, os.path.basename(path)))
                if os.path.exists(svg):
                    shutil.copy(svg, os.path.join(keep, os.path.basename(svg)))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return rows


def summarize(rows):
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["kind"], r["bucket"])].append(r)
    table = []
    for (kind, bucket), rs in sorted(by.items(), key=lambda kv: (kv[0][0], int(kv[0][1].split("-")[0]))):
        valid = [r for r in rs if not r["invalid"]]
        failed = [r for r in valid if not r["ok"]]
        ms = sorted(r["ms"] for r in valid) or [0]
        table.append({"kind": kind, "nodes": bucket, "scenes": len(rs), "invalid": len(rs) - len(valid),
                      "failed": len(failed), "failure_rate": round(len(failed) / len(valid), 3) if valid else None,
                      "median_ms": ms[len(ms) // 2], "max_ms": ms[-1]})
    valid = [r for r in rows if not r["invalid"]]
    codes = collections.Counter(c for r in valid for c in set(r["codes"]))
    failed = [r for r in valid if not r["ok"]]
    return {
        "scenes": len(rows),
        "invalid": len(rows) - len(valid),
        "failed": len(failed),
        "failure_rate": round(len(failed) / len(valid), 3) if valid else None,
        "scenes_with_code": dict(codes.most_common()),
        "by_kind_and_size": table,
        "failing": [f'{r["kind"]} {r["seed"]} {r["nodes"]}' for r in failed],
        "invalid_examples": [r for r in rows if r["invalid"]][:5],
    }


def print_summary(s):
    print(f'{s["scenes"]} scenes: {s["failed"]} failed the audit ({(s["failure_rate"] or 0) * 100:.1f}%), '
          f'{s["invalid"]} invalid')
    print(f'{"kind":6} {"nodes":>6} {"scenes":>7} {"failed":>7} {"rate":>6} {"median ms":>10} {"max ms":>8}')
    for t in s["by_kind_and_size"]:
        rate = f'{t["failure_rate"] * 100:.0f}%' if t["failure_rate"] is not None else "-"
        print(f'{t["kind"]:6} {t["nodes"]:>6} {t["scenes"]:>7} {t["failed"]:>7} {rate:>6} '
              f'{t["median_ms"]:>10.0f} {t["max_ms"]:>8.0f}')
    if s["scenes_with_code"]:
        print("scenes per error code: " + ", ".join(f"{k} {v}" for k, v in s["scenes_with_code"].items()))
    if s["invalid_examples"]:
        print("INVALID (generator bug): " + json.dumps(s["invalid_examples"][0])[:400])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render seeded random specs and count audit failures.")
    ap.add_argument("--n", type=int, default=200, help="number of scenes (default 200)")
    ap.add_argument("--seed", type=int, default=0, help="first seed (default 0)")
    ap.add_argument("--kinds", nargs="+", default=["flow", "arch"], choices=sorted(gen.KINDS))
    ap.add_argument("--out", help="write rows and summary as JSON")
    ap.add_argument("--keep", help="save failing specs and SVGs here")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any scene fails or is invalid")
    ap.add_argument("--one", nargs=3, metavar=("KIND", "SEED", "NODES"), help="render one scene and print it")
    a = ap.parse_args(argv)

    if a.one:
        kind, seed, size = a.one[0], int(a.one[1]), int(a.one[2])
        work = a.keep or tempfile.mkdtemp(prefix="fuzz-one-")
        os.makedirs(work, exist_ok=True)
        spec, path, svg, ms, verdict, raw = render_one(kind, seed, size, work)
        print(json.dumps({"spec": path, "svg": svg, "ms": round(ms), "verdict": verdict}, indent=1)[:4000])
        return 0

    t0 = time.perf_counter()
    rows = run(a.n, a.seed, a.kinds, a.keep)
    s = summarize(rows)
    s["seconds"] = round(time.perf_counter() - t0, 1)
    print_summary(s)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"summary": s, "rows": rows}, f, indent=1)
    if a.strict and (s["failed"] or s["invalid"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

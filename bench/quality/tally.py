"""Tally the blind judgments: python bench/quality/tally.py [JUDGE_DIR]

Copies each batch's verdicts.json from JUDGE_DIR into judgments/bNN.json (when given), unblinds them
with judgments/key.json, and writes judgments/all.csv (one row per judgment and question) and
results.json (win rates for dd by opponent, family, size, placement and judge; order agreement).
With --run RUN (a rerun: render.py and pairs.py --run), all of it is under runs/RUN instead."""
import csv, glob, json, os, shutil, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
JD = os.path.join(HERE, "judgments")
SIZE_NAMES = {"05": "5 steps", "11": "11 steps", "20": "20 steps", "40": "40 steps"}


def load():
    if len(sys.argv) > 1:
        for f in glob.glob(os.path.join(sys.argv[1], "b*", "verdicts.json")):
            shutil.copyfile(f, os.path.join(JD, os.path.basename(os.path.dirname(f)) + ".json"))
    with open(os.path.join(JD, "key.json"), encoding="utf-8") as f:
        key = json.load(f)
    rows = []
    for bid, b in sorted(key["batches"].items()):
        path = os.path.join(JD, bid + ".json")
        if not os.path.isfile(path):
            print("missing", bid)
            continue
        with open(path, encoding="utf-8") as f:
            verdicts = {v["pair"]: v for v in json.load(f)}
        for it in b["items"]:
            v = verdicts.get(f"p{it['n']:02d}")
            if not v:
                print("missing", bid, it["n"])
                continue
            p = key["pairs"][it["pair"]]
            tool = {"A": it["A"].rsplit("-", 1)[1], "B": it["B"].rsplit("-", 1)[1]}
            dd_side = "A" if tool["A"] == "dd" else "B"
            other_side = "B" if dd_side == "A" else "A"
            for q in ("clearer", "looks"):
                pick = str(v.get(q, "")).strip().upper()[:1]
                rows.append({"batch": bid, "model": b["model"], "context": b["context"], "pair": it["pair"],
                             "family": p["family"], "size": p["size"], "opponent": tool[other_side],
                             "dd_first": dd_side == "A", "question": q, "dd_won": pick == dd_side,
                             "margin": v.get(f"{q}_margin", ""), "why": v.get(f"{q}_why", ""),
                             "weak_dd": v.get(f"weak_{dd_side}", ""), "weak_other": v.get(f"weak_{other_side}", "")})
    return key, rows


def rate(rs):
    n = len(rs)
    return {"n": n, "dd_wins": sum(r["dd_won"] for r in rs), "rate": round(sum(r["dd_won"] for r in rs) / n, 3) if n else None}


def group(rows, *keys):
    g = defaultdict(list)
    for r in rows:
        g[tuple(r[k] for k in keys)].append(r)
    return {"|".join(map(str, k)): rate(v) for k, v in sorted(g.items())}


def main():
    global JD
    root = HERE
    if "--run" in sys.argv:
        i = sys.argv.index("--run")
        root = os.path.join(HERE, "runs", sys.argv[i + 1])
        del sys.argv[i:i + 2]
        JD = os.path.join(root, "judgments")
    key, rows = load()
    with open(os.path.join(JD, "all.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # order agreement: the same pair, judge, placement and question, seen in both orders
    by = defaultdict(list)
    for r in rows:
        by[(r["pair"], r["model"], r["context"], r["question"])].append(r["dd_won"])
    both = [v for v in by.values() if len(v) == 2]
    res = {
        "judgments": len(rows) // 2,
        "overall": group(rows, "question"),
        "by_opponent": group(rows, "opponent", "question"),
        "by_opponent_context": group(rows, "opponent", "context", "question"),
        "by_family_opponent_context": group(rows, "family", "opponent", "context", "question"),
        "by_size": group([r for r in rows if r["family"] in ("A", "L")], "family", "size", "opponent", "context", "question"),
        "by_model": group(rows, "model", "opponent", "question"),
        "by_dd_first": group(rows, "dd_first", "question"),
        "order_agreement": round(sum(a == b for a, b in both) / len(both), 3) if both else None,
        "by_pair": group(rows, "pair", "context", "question"),
    }
    with open(os.path.join(root, "results.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, indent=1)
    for k in ("overall", "by_opponent", "by_opponent_context"):
        print(k, json.dumps(res[k], indent=1))
    print("order agreement", res["order_agreement"], "of", len(both))


if __name__ == "__main__":
    main()

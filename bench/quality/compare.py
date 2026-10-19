"""A rerun's win rates beside the first run's: python bench/quality/compare.py RUN [CONTEXT]

Reads judgments/all.csv (the first run) and runs/RUN/judgments/all.csv (tally.py --run RUN), keeps one
placement (default column), and writes runs/RUN/results.md: dd's wins before and after, by opponent,
for flowcharts by size, for the other types, by judge model, and for every pair whose verdict moved.

--base BASE compares with runs/BASE instead of the first run (adding a column for the first run);
--only WORD keeps the pairs whose id contains WORD, in both (a rerun of some pairs, pairs.py --only):

    py -3 bench/quality/compare.py fit-column-arch --base fit-column --only ref-arch"""
import csv, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TYPES = {"arch": "arch", "seq": "sequence", "schema": "schema", "er": "ER example", "flow": "flow example"}


def rows(path, context):
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r["context"] == context]


def tally(rs, *keys):
    out = defaultdict(lambda: [0, 0])
    for r in rs:
        k = tuple(r[x] for x in keys)
        out[k][0] += r["dd_won"] == "True"
        out[k][1] += 1
    return out


def cell(t, k):
    won, n = t.get(k, (0, 0))
    return f"{round(100 * won / n)}% ({won}/{n})" if n else "-"


def both(old, new, k):
    return f"{cell(old, k)} → **{cell(new, k)}**"


def main():
    args, flags = [], {}
    it = iter(sys.argv[1:])
    for a in it:
        if a in ("--base", "--only"):
            flags[a] = next(it)
        else:
            args.append(a)
    run, context = args[0], (args[1] if len(args) > 1 else "column")
    base, only = flags.get("--base"), flags.get("--only")
    keep = lambda rs: [r for r in rs if not only or only in r["pair"]]
    first = keep(rows(os.path.join(HERE, "judgments", "all.csv"), context))
    old = keep(rows(os.path.join(HERE, "runs", base, "judgments", "all.csv"), context)) if base else first
    new = keep(rows(os.path.join(HERE, "runs", run, "judgments", "all.csv"), context))
    out = [f"# {run}: dd's win rate in the {context}, {base or 'first run'} → this run"
           + (f" (pairs with '{only}')" if only else ""), ""]

    t0, t1 = tally(old, "opponent", "question"), tally(new, "opponent", "question")
    out += ["| against | clearer | better looking |", "| --- | --- | --- |"]
    for opp in ("pele", "mermaid"):
        out.append(f"| {opp.capitalize()} | {both(t0, t1, (opp, 'clearer'))} | {both(t0, t1, (opp, 'looks'))} |")
    t0, t1 = tally(old, "question"), tally(new, "question")
    out += [f"| both | {both(t0, t1, ('clearer',))} | {both(t0, t1, ('looks',))} |", ""]

    flows = lambda rs: [r for r in rs if r["family"] in ("A", "L") and r["size"] in ("05", "11", "20", "40")]
    if flows(new):
        out += ["Flowcharts by size (agent figures and same-source figures together):", "",
                "| steps | vs Pele, clearer / looks | vs Mermaid, clearer / looks |", "| --- | --- | --- |"]
        t0, t1 = tally(flows(old), "size", "opponent", "question"), tally(flows(new), "size", "opponent", "question")
        for s in ("05", "11", "20", "40"):
            out.append(f"| {int(s)} | " + " | ".join(f"{both(t0, t1, (s, o, 'clearer'))} / {both(t0, t1, (s, o, 'looks'))}"
                                                   for o in ("pele", "mermaid")) + " |")
        out.append("")
    out += ["Other types, clearer (L: one Mermaid source drawn by each tool; N: dd from its native spec):", "",
            "| type | family | vs Pele | vs Mermaid |", "| --- | --- | --- | --- |"]
    other = lambda rs: [r for r in rs if r["size"] in TYPES]
    t0, t1 = tally(other(old), "size", "family", "opponent", "question"), tally(other(new), "size", "family", "opponent", "question")
    for s in TYPES:
        for fam in ("L", "N"):
            if (s, fam, "pele", "clearer") in t0 or (s, fam, "pele", "clearer") in t1:
                out.append(f"| {TYPES[s]} | {fam} | {both(t0, t1, (s, fam, 'pele', 'clearer'))} | "
                           f"{both(t0, t1, (s, fam, 'mermaid', 'clearer'))} |")
    out += ["", "| judge | clearer | better looking |", "| --- | --- | --- |"]
    t0, t1 = tally(old, "model", "question"), tally(new, "model", "question")
    for m in ("sonnet", "opus"):
        out.append(f"| {m.capitalize()} | {both(t0, t1, (m, 'clearer'))} | {both(t0, t1, (m, 'looks'))} |")

    if only:  # few pairs: each one, first run, base and this run
        tf = tally(first, "pair", "question")
        head = "first run → " + (f"{base} → " if base else "") + "this run"
        out += ["", f"Every pair, dd's wins of 4 ({head}):", "", "| pair | clearer | better looking |",
                "| --- | --- | --- |"]
        t0, t1 = tally(old, "pair", "question"), tally(new, "pair", "question")
        for (pair, q) in sorted(k for k in t1 if k[1] == "clearer"):
            seq = lambda q: " → ".join(str(t.get((pair, q), (0, 0))[0]) for t in ([tf, t0, t1] if base else [tf, t1]))
            out.append(f"| {pair} | {seq('clearer')} | {seq('looks')} |")
    else:
        out += ["", "Pairs whose clarity verdict moved (dd's wins of 4):", "", "| pair | clearer | better looking |",
                "| --- | --- | --- |"]
        t0, t1 = tally(old, "pair", "question"), tally(new, "pair", "question")
        for (pair, q) in sorted(k for k in t1 if k[1] == "clearer"):
            if t0.get((pair, q), (0, 0))[0] != t1[(pair, q)][0]:
                a, b = t0.get((pair, q), (0, 0))[0], t1[(pair, q)][0]
                la, lb = t0.get((pair, "looks"), (0, 0))[0], t1.get((pair, "looks"), (0, 0))[0]
                out.append(f"| {pair} | {a} → {b} | {la} → {lb} |")
    text = "\n".join(out) + "\n"
    with open(os.path.join(HERE, "runs", run, "results.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

"""Write results.md, the full tables: python bench/quality/report.py (after tally.py and cluster.py)

Every cell is dd's win rate: wins / judgments, over both judges and both orders."""
import csv, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OPP = (("pele", "Pele"), ("mermaid", "Mermaid"))
CTX = (("slide", "slide"), ("column", "column"))
Q = (("clearer", "clearer"), ("looks", "looks"))
SIZES = (("05", "5 steps"), ("11", "11 steps"), ("20", "20 steps"), ("40", "40 steps"))
KINDS = (("flow", "flowchart (example)"), ("arch", "arch, subgraphs (2)"), ("seq", "sequence (3)"),
         ("schema", "schema (2)"), ("er", "ER (example)"))


def cell(rs):
    if not rs:
        return "–"
    w = sum(r["dd_won"] == "True" for r in rs)
    return f"{round(100 * w / len(rs))}% ({w}/{len(rs)})"


def table(rows, label, keys, filt):
    head = [label] + [f"{on} {cn} {qn}" for _, on in OPP for _, cn in CTX for _, qn in Q]
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * len(head)) + " |"]
    for k, name in keys:
        cells = []
        for o, _ in OPP:
            for c, _ in CTX:
                for q, _ in Q:
                    cells.append(cell([r for r in rows if filt(r, k) and r["opponent"] == o and r["context"] == c
                                       and r["question"] == q]))
        out.append("| " + " | ".join([name] + cells) + " |")
    return "\n".join(out)


def main():
    rows = list(csv.DictReader(open(os.path.join(HERE, "judgments", "all.csv"), encoding="utf-8")))
    res = json.load(open(os.path.join(HERE, "results.json"), encoding="utf-8"))
    cl = json.load(open(os.path.join(HERE, "clusters.json"), encoding="utf-8"))
    meas = json.load(open(os.path.join(HERE, "measure.json"), encoding="utf-8"))
    md = ["# Quality benchmark: full tables", "",
          f"{res['judgments']} blind judgments, each answering two questions (clearer, better looking). "
          "Cells are dd's win rate against the named tool: wins / judgments, Sonnet and Opus, both orders.", ""]
    md += ["## All pairs", "", table(rows, "", [("all", "all")], lambda r, k: True), ""]
    fams = [("A", "agent figures"), ("L", "same Mermaid source"), ("N", "dd native spec vs the Mermaid translation")]
    md += ["## By figure set", "", table(rows, "set", fams, lambda r, k: r["family"] == k), ""]
    md += ["## Flowcharts by size (agent figures and the same-source bench flows)", "",
           table(rows, "size", SIZES, lambda r, k: r["size"] == k), "",
           "### Same source only", "", table(rows, "size", SIZES, lambda r, k: r["size"] == k and r["family"] == "L"), "",
           "### Agent figures only", "", table(rows, "size", SIZES, lambda r, k: r["size"] == k and r["family"] == "A"), ""]
    md += ["## Other diagram types, same Mermaid source", "",
           table(rows, "type", KINDS, lambda r, k: r["size"] == k and r["family"] == "L"), "",
           "## Other diagram types, dd from its native spec", "",
           table(rows, "type", [("arch", "arch (2)"), ("seq", "sequence (2)"), ("schema", "schema (2)")],
                 lambda r, k: r["size"] == k and r["family"] == "N"), ""]
    md += ["## By judge", "", table(rows, "judge", [("sonnet", "Sonnet"), ("opus", "Opus")], lambda r, k: r["model"] == k), ""]
    by = defaultdict(list)
    for r in rows:
        by[(r["pair"], r["model"], r["context"], r["question"])].append(r["dd_won"])
    both = [v for v in by.values() if len(v) == 2]
    first = [r for r in rows if r["dd_first"] == "True"]
    second = [r for r in rows if r["dd_first"] == "False"]
    md += ["## Consistency", "",
           f"- The two orders of a pair (same judge, placement and question) agree in {res['order_agreement']:.0%} "
           f"of {len(both)} cases.",
           f"- dd wins {cell(first)} when shown first and {cell(second)} when shown second.", ""]
    md += ["## Text size where the figure lands", "",
           "Median text size in px after fitting each figure to the placement (measure.py): slide = 1600 x 900, "
           "page = A4 portrait at 96 dpi inside 72 px margins (650 x 980, not enlarged), column = 700 px wide, "
           "scrolled. Bench flows, both sources per size.", "",
           "| steps | placement | dd | Pele | Mermaid |", "| --- | --- | --- | --- | --- |"]
    for s, name in SIZES:
        for c in ("slide", "page", "column"):
            vals = []
            for t in ("dd", "pele", "mermaid"):
                v = [meas[f"L-bench-{s}-{x}-{t}"][c]["median"] for x in "ab"]
                vals.append(f"{min(v)}" if min(v) == max(v) else f"{min(v)}–{max(v)}")
            md.append(f"| {s.lstrip('0')} | {c} | " + " | ".join(vals) + " |")
    md += ["", "## Why dd lost: themes", "",
           f"{cl['losses']} judgments went against dd. Each is tagged with every theme its reason names (cluster.py; "
           "losses.md lists them all with their tags), so a loss can count under several themes.", "",
           "| theme | losses | slide | column | clearer | looks |", "| --- | --- | --- | --- | --- | --- |"]
    for t in cl["themes"]:
        md.append(f"| {t['name']} | {t['losses']} | {t['slide']} | {t['column']} | {t['clearer']} | {t['looks']} |")
    with open(os.path.join(HERE, "results.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md) + "\n")
    print("wrote results.md")


if __name__ == "__main__":
    main()

"""Cluster why dd lost: python bench/quality/cluster.py

Reads judgments/all.csv. Every judgment dd lost (per question) is tagged with the themes its reason
and its "dd's weakness" phrase name; the keyword rules below were written after reading all of
them, and losses.md lists each loss with its tags so the coding can be checked by eye.
"Shrunk" and "small default text" are told apart by the figure's scale in that placement
(measure.json): below 0.75 the reader sees the figure shrunk to fit."""
import csv, json, os, re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

THEMES = [  # (key, name, where to look: "both" = the reason and dd's weakness, "weak" = dd's weakness only, regex)
    ("wrap", "Wrapped into columns: the reading order snakes, long connectors run between columns", "both",
     r"(?:two|three|four|3|4|several|multiple|snaking|wrapped)[- ]columns?|columns? (?:layout|wrap)|wrap|snak|"
     r"cross-column|between columns|across columns|column-to-column|reading order|jump"),
    ("text", "Text too small or too pale to read", "both",
     r"small|tiny|microscopic|minuscule|specks|illegib|unreadable|hard to read|barely (?:read|legible)|\bpx\b|pale|faint|"
     r"light(?:er)?[- ]gr[ae]y|low[- ]contrast|squint|zoom|thumbnail"),
    ("trunk", "Arrows share a trunk, merge or overlap", "both",
     r"trunk|\bbus\b|shar(?:e|es|ed|ing) (?:a |one |the same )?(?:segment|line|path|lane|route|vertical|horizontal)|merg|bundl|"
     r"run together|runs? on top of|overlap(?:ping)? (?:dashed |solid )?(?:edges|lines|arrows|connectors)|edges overlap|lines overlap|"
     r"converg|tangle|spaghetti|crowd"),
    ("label", "Edge labels float away from their arrows or are crossed by lines", "both",
     r"float|far from|away from (?:the|its) (?:edge|line|arrow|loop|connector)|long way from|struck|strike|runs? through|"
     r"passes through|crossed by|cuts? through (?:the |a )?label|collid|detached"),
    ("detour", "Long detours: loop-backs and skips routed far around the figure", "both",
     r"detour|long (?:loop|edges?|connectors?|returns?|lines?|routes?|wires?|wrap-around)|far out|wrap-?around|"
     r"around the (?:outside|edge)|lengthy"),
    ("space", "Wasted space: the figure is too wide or sparse for its content", "both",
     r"wasted|empty|white ?space|sparse|too wide|very wide|wide (?:figure|layout|strip)|spread out|lot of space|dead space"),
    ("kink", "Misaligned boxes or kinked arrows", "both",
     r"kink|misalign|offset|jog|dog-?leg|off-cent|stagger|uneven"),
    ("er", "ER relations: no crow's feet, cardinality only as text, some relations without arrowheads", "both",
     r"crow|cardinality|no arrowheads?|bare (?:lines|arrows)|plain (?:lines|arrows|arrowheads)|inconsistent (?:arrows|connectors)"),
    ("lost", "Mermaid input dropped: second lines flattened, cylinders, classDef colours", "both",
     r"cylinder|database shape|one line|single line|run[- ]on|flatten|class ?def|colou?r[- ]?cod|colou?red (?:start|steps|shapes|nodes)|"
     r"(?:blue|green|amber|yellow) (?:steps|diamonds|decisions|start)|monochrome|all (?:grey|gray)|start/(?:step|decision)"),
    ("dup", "Doubled relation label (1:N 1:N)", "both", r"1:N 1:N|doubled|duplicat"),
    ("actor", "Sequence: a USER tag over 'User' instead of an actor icon; participants not repeated at the bottom", "both",
     r"USER\b|actor (?:icon|figure|row|mark)|stick|marks? (?:the )?User|repeat\w* (?:the )?(?:participants|actors|header)|"
     r"participants (?:repeat|at the bottom)|header row at the bottom|at the bottom"),
    ("legend", "Legend or chrome adds clutter", "weak", r"legend|box = step|caption"),
    ("numbers", "Steps not numbered", "weak",
     r"unnumbered|no step numbers|not numbered|numbers? (?:every|all|the|each) (?:\w+ )?steps?|numbered (?:steps|labels|single)|step numbers"),
]

# Root causes for the fix list: a loss counts once per cause, however many of its themes point there.
CAUSES = [
    ("size", "The figure's size ignores where it goes: wide or wrapped figures shrink in a page or column",
     ("shrunk", "wrap", "space", "detour")),
    ("er", "ER drawing: plain arrowheads and '1:N' text instead of crow's feet, missing arrowheads, doubled labels",
     ("er", "dup")),
    ("text", "Small, pale default text (sequence messages, subtitles) even at full size", ("text",)),
    ("trunk", "Arrows that share a trunk or merge (arch fan-outs, wrapped flows)", ("trunk",)),
    ("lost", "No colour coding by node kind; Mermaid input dropped (<br/> second lines, cylinders, classDef colours)", ("lost",)),
    ("actor", "Sequence chrome: USER tag instead of an actor icon, no participant row at the bottom", ("actor",)),
    ("label", "Edge labels float away from their arrows or are crossed by them", ("label",)),
    ("kink", "Misaligned boxes and kinked arrows", ("kink",)),
    ("other", "Other: legend clutter, unnumbered steps, nothing matched", ("legend", "numbers", "other")),
]


def main():
    rows = list(csv.DictReader(open(os.path.join(HERE, "judgments", "all.csv"), encoding="utf-8")))
    meas = json.load(open(os.path.join(HERE, "measure.json"), encoding="utf-8"))
    pairs = json.load(open(os.path.join(HERE, "judgments", "key.json"), encoding="utf-8"))["pairs"]
    losses = [r for r in rows if r["dd_won"] == "False"]
    count, causes = defaultdict(Counter), defaultdict(Counter)
    lines = ["# dd's losses, tagged", "", "Each judgment dd lost, with the themes cluster.py found in it.", ""]
    for r in losses:
        both = f"{r['why']} || {r['weak_dd']}"
        tags = [k for k, _, where, rx in THEMES if re.search(rx, both if where == "both" else r["weak_dd"], re.I)]
        dd_fig = pairs[r["pair"]]["figs"][0]
        if "text" in tags:
            tags[tags.index("text")] = "shrunk" if meas[dd_fig][r["context"]]["scale"] < 0.75 else "text"
        if not tags:
            tags = ["other"]
        for key, _, members in CAUSES:
            if any(t in members for t in tags):
                causes[key][r["context"]] += 1
                causes[key]["all"] += 1
                causes[key][r["question"]] += 1
        for t in tags:
            count[t][r["context"]] += 1
            count[t]["all"] += 1
            count[t][r["question"]] += 1
        lines.append(f"- **{r['pair']}** ({r['context']}, {r['question']}, {r['model']}, {r['margin']}): "
                     f"`{' '.join(tags)}`. {r['why']} *dd's weakness: {r['weak_dd']}*")
    names = {k: n for k, n, _, _ in THEMES}
    names.update(shrunk="Figure shrunk to fit the placement, so its text gets too small",
                 text="Default text too small or too pale at full size", other="(no theme matched)")
    order = sorted(count, key=lambda t: -count[t]["all"])
    summary = [{"theme": t, "name": names[t], "losses": count[t]["all"], "slide": count[t]["slide"],
                "column": count[t]["column"], "clearer": count[t]["clearer"], "looks": count[t]["looks"]} for t in order]
    with open(os.path.join(HERE, "clusters.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"losses": len(losses), "themes": summary,
                   "causes": [{"cause": k, "name": n, "losses": causes[k]["all"], "slide": causes[k]["slide"],
                               "column": causes[k]["column"], "clearer": causes[k]["clearer"], "looks": causes[k]["looks"]}
                              for k, n, _ in sorted(CAUSES, key=lambda c: -causes[c[0]]["all"])]}, f, indent=1)
    with open(os.path.join(HERE, "losses.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(losses)} losses")
    for s in summary:
        print(f"{s['losses']:4d}  slide {s['slide']:3d}  column {s['column']:3d}  clearer {s['clearer']:3d}  looks {s['looks']:3d}  {s['name']}")
    print("causes:")
    for k, n, _ in sorted(CAUSES, key=lambda c: -causes[c[0]]["all"]):
        c = causes[k]
        print(f"{c['all']:4d}  slide {c['slide']:3d}  column {c['column']:3d}  clearer {c['clearer']:3d}  looks {c['looks']:3d}  {n}")


if __name__ == "__main__":
    main()

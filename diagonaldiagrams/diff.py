"""What changed between two drawings of one figure, matched by the ids both carry (DESIGN 21.4).

    diff(old_svg, new_svg) -> {"nodes": {...}, "edges": {...}, "shifted": {...}, "sentences": [...]}

Nodes match by data-node and edges by data-id, so the ids must be stable (D15): a render after an
edit keeps them. Rows are the verdict's rows (outline.layout_rows): boxes whose middles sit within
30 px of each other. A schema's layers are columns, so there they are columns, and a sequence's one
row is its actors. Each old row is matched to the new row that holds most of its boxes, so a
box that only rides along when rows shift is not reported as moved to another row.
"""
import re
import xml.etree.ElementTree as ET

from .outline import read_figure

NEAR = 2.0  # a box whose middle moved less than this did not move
ROW = 30.0  # outline.layout_rows' row tolerance


def svg_of(text):
    """The figure's <svg> element as text: the whole file, or the first one in an HTML page."""
    m = re.search(r"<svg[\s\S]*?</svg>", text)
    return m.group(0) if m else text


def middles(svg):
    """{node id: (x, y)} of each box's middle in a drawing (an SVG or an HTML page)."""
    try:
        return _middles(read_figure(svg_of(svg)))
    except ET.ParseError as e:
        raise ValueError(str(e))


def _middles(fig):
    out = {}
    for n in fig["nodes"].values():
        if n["shape"] == "diamond" and n.get("cx") is not None and n.get("cy") is not None:
            out[n["id"]] = (n["cx"], n["cy"])
        else:
            out[n["id"]] = (n["x"] + n["w"] / 2, n["y"] + n["h"] / 2)
    return out


def _rows(mid, across=False):
    """[[node ids left to right], ...] top to bottom; across: [[ids top to bottom], ...] left to right."""
    rows = []
    for nid, (x, y) in sorted(mid.items(), key=lambda kv: (kv[1][0], kv[1][1]) if across else (kv[1][1], kv[1][0])):
        a, b = (y, x) if across else (x, y)
        if rows and abs(rows[-1][0] - b) < ROW:
            rows[-1][1].append((a, nid))
        else:
            rows.append([b, [(a, nid)]])
    return [[nid for _, nid in sorted(r[1])] for r in rows]


def _kind(svg):
    """What the drawing calls itself (aria-roledescription): "database schema", "sequence diagram", ..."""
    m = re.search(r'<svg[^>]*aria-roledescription="([^"]*)"', svg)
    return m.group(1) if m else ""


def _fills(svg):
    root = ET.fromstring(svg)
    return {el.get("data-node"): el.get("fill") for el in root.iter() if el.get("data-node") is not None and el.get("data-label") is not None}


def _q(s):
    return f'"{s}"'


def page_layers(text):
    """The layout's layers a diagram page keeps for its edit mode, or None (an SVG, or no page)."""
    import json
    m = re.search(r'<script type="application/json" id="dd-page">(.*?)</script>', text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1)).get("layers") or None
    except ValueError:
        return None


def diff(old, new, old_layers=None, new_layers=None):
    """old_layers, new_layers: the layouts' layers, when known (the pages keep them). Rows then are
    layers, which a wrapped layout's heights don't show: its columns share heights."""
    old, new = svg_of(old), svg_of(new)
    a, b = read_figure(old), read_figure(new)
    am, bm = _middles(a), _middles(b)
    name = {**{k: v["label"] for k, v in a["nodes"].items()}, **{k: v["label"] for k, v in b["nodes"].items()}}
    added = [k for k in b["nodes"] if k not in a["nodes"]]
    removed = [k for k in a["nodes"] if k not in b["nodes"]]
    both = [k for k in b["nodes"] if k in a["nodes"]]
    renamed = [{"id": k, "was": a["nodes"][k]["label"], "now": b["nodes"][k]["label"]}
               for k in both if a["nodes"][k]["label"] != b["nodes"][k]["label"]]
    af, bf = _fills(old), _fills(new)
    recolored = [{"id": k, "was": af.get(k), "now": bf.get(k)} for k in both if af.get(k) != bf.get(k)]

    kind = _kind(new)
    across = kind == "database schema"
    word = "column" if across else "row"
    if old_layers and new_layers:
        arows = [[i for i in layer if i in am] for layer in old_layers]
        brows = [[i for i in layer if i in bm] for layer in new_layers]
        arows, brows = [r for r in arows if r], [r for r in brows if r]
        arows += [[i] for i in am if not any(i in r for r in arows)]  # a box the layers miss: a row of its own
        brows += [[i] for i in bm if not any(i in r for r in brows)]
        key = (lambda i, m: m[i][1]) if across else (lambda i, m: m[i][0])
        arows = [sorted(r, key=lambda i: key(i, am)) for r in arows]
        brows = [sorted(r, key=lambda i: key(i, bm)) for r in brows]
    else:
        arows, brows = _rows(am, across), _rows(bm, across)
    a_row = {nid: i for i, r in enumerate(arows) for nid in r}
    b_row = {nid: i for i, r in enumerate(brows) for nid in r}
    # each old row goes where most of its boxes went, and each new row takes one old row: the one that
    # brings it the most boxes, a tie going to the nearer index. A row whose boxes joined another
    # row is matched to none, so its boxes moved.
    votes = []
    for i, r in enumerate(arows):
        count = {}
        for nid in r:
            if nid in b_row:
                count[b_row[nid]] = count.get(b_row[nid], 0) + 1
        votes += [(c, -abs(j - i), i, j) for j, c in count.items()]
    match, taken = {}, set()
    for c, _, i, j in sorted(votes, reverse=True):
        if i not in match and j not in taken:
            match[i] = j
            taken.add(j)
    reordered, swapped = [], set()  # swapped: boxes that changed places in their row
    for i, r in enumerate(arows):
        j = match.get(i)
        if j is None:
            continue
        before = [n for n in r if n in b_row and b_row[n] == j]
        after = [n for n in brows[j] if n in before]
        if before != after:
            reordered.append({"row": j + 1, "was": before, "now": after})
            swapped.update(n for k, n in enumerate(after) if before[k] != n)

    moved, shifted = [], []
    for k in both:
        dx, dy = bm[k][0] - am[k][0], bm[k][1] - am[k][1]
        if abs(dx) < NEAR and abs(dy) < NEAR:
            continue
        rec = {"id": k, "dx": round(dx, 1), "dy": round(dy, 1)}
        if match.get(a_row[k]) != b_row[k]:
            rec["row"] = [a_row[k] + 1, b_row[k] + 1]
            moved.append(rec)
        elif k in swapped:
            moved.append(rec)
        else:
            shifted.append(rec)
    ae = {e["id"]: e for e in a["edges"]}
    be = {e["id"]: e for e in b["edges"]}
    e_added = [k for k in be if k not in ae]
    e_removed = [k for k in ae if k not in be]
    relabeled = [{"id": k, "was": ae[k]["label"], "now": be[k]["label"]} for k in be if k in ae and ae[k]["label"] != be[k]["label"]]

    def arrow(e):
        return f"{_q(name.get(e['from'], e['from']))} to {_q(name.get(e['to'], e['to']))}"
    says = []
    says += [f"Added {_q(name[k])}" for k in added]
    says += [f"Removed {_q(name[k])}" for k in removed]
    says += [f"Renamed {_q(r['was'])} to {_q(r['now'])}" for r in renamed]
    says += [f"Moved {_q(name[m['id']])} from {word} {m['row'][0]} to {word} {m['row'][1]}" for m in moved if "row" in m]
    if kind == "sequence diagram":
        says += ["The actors now read " + " | ".join(name[n] for n in r["now"]) for r in reordered]
    else:
        says += [f"{word.capitalize()} {r['row']} now reads " + " | ".join(name[n] for n in r["now"]) for r in reordered]
    says += [f"Recolored {_q(name[r['id']])}" for r in recolored]
    says += [f"Added an arrow from {arrow(be[k])}" for k in e_added]
    says += [f"Removed the arrow from {arrow(ae[k])}" for k in e_removed]
    says += [f"The arrow from {arrow(be[r['id']])} now reads {_q(r['now'])}" for r in relabeled]
    if shifted:
        mean = sum((s["dx"] ** 2 + s["dy"] ** 2) ** 0.5 for s in shifted) / len(shifted)
        says.append(f"{len(shifted)} other box{'es' if len(shifted) > 1 else ''} shifted, {mean:.0f} px on average")
    diag = 0.0
    if b["size"]:
        diag = (b["size"][0] ** 2 + b["size"][1] ** 2) ** 0.5
    return {
        "nodes": {"added": added, "removed": removed, "renamed": renamed, "moved": moved, "reordered": reordered,
                  "recolored": recolored},
        "edges": {"added": e_added, "removed": e_removed, "relabeled": relabeled},
        # layout stability (PLAN scoreboard): how far the boxes the edit did not move went, against the canvas
        "shifted": {"count": len(shifted), "boxes": shifted,
                    "mean_of_diagonal": round(sum((s["dx"] ** 2 + s["dy"] ** 2) ** 0.5 for s in shifted) / len(both) / diag, 4)
                    if both and diag else 0.0},
        "sentences": says,
    }


def do_diff(args):
    """diagonaldiagrams diff OLD NEW: prints the JSON; exit 0 either way, 1 when a file can't be read."""
    import json
    try:
        old = open(args.old, encoding="utf-8").read()
        new = open(args.new, encoding="utf-8").read()
        out = diff(old, new, page_layers(old), page_layers(new))  # two pages: their layers are the rows
    except (OSError, ET.ParseError) as e:
        print(json.dumps({"ok": False, "errors": [{"msg": f"can't read the figures: {e}",
                                                   "fix": "pass two .svg or .html files that diagonaldiagrams drew"}]}))
        return 1
    print(json.dumps(dict({"ok": True}, **out), indent=2))
    return 0

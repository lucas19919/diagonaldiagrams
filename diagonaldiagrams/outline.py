"""What a finished figure shows, read back from its SVG: for the verdict and the editable exports.

Every renderer marks what it draws with data-* attributes (data-node, data-from, data-group,
data-msg, data-role). read_figure() parses them once; layout_rows() is the compact outline in every
render verdict, outline() the structured one behind --outline, and svg_model() what the draw.io and
Excalidraw exports are built from.
"""
import re
import xml.etree.ElementTree as ET

ROLES = (("xaxis", "x axis"), ("yaxis", "y axis"), ("series", "series"), ("table", "tables"))
CAP = 60  # nodes or edges listed in the structured outline before "more"


def _num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _path_points(d):
    """A path's corner points: M and L points, and the end of each Q corner (its control point is
    the corner itself, rounded off)."""
    pts = []
    for cmd, a, b, c, e in re.findall(r"([MLQ])\s*([-\d.]+),([-\d.]+)(?:\s+([-\d.]+),([-\d.]+))?", d or ""):
        pts.append((float(c), float(e)) if cmd == "Q" and c else (float(a), float(b)))
    return pts


def read_figure(svg):
    """The marked parts of a figure, in document order. svg is the SVG text (an HTML page works too
    if it is passed already cut down to its <svg>)."""
    root = ET.fromstring(svg)
    vb = (root.get("viewBox") or "").split()
    fig = {"size": [_num(vb[2]), _num(vb[3])] if len(vb) == 4 else None, "nodes": {}, "edges": [], "frames": [],
           "actors": [], "messages": [], "roles": {}}
    for el in root.iter():
        tag = str(el.tag).split("}")[-1]
        get = el.get
        role = get("data-role")
        if role:
            fig["roles"].setdefault(role, []).append((el.text or ""))
        if get("data-msg") is not None:
            fig["messages"].append({"label": get("data-msg"), "from": get("data-msg-from"), "to": get("data-msg-to")})
        if get("data-node") is not None and get("data-label") is not None:
            nid, label = get("data-node"), get("data-label")
            fig["actors"].append(label)
            if tag == "rect":
                x, y, w, h = (_num(get(k)) for k in ("x", "y", "width", "height"))
                fig["nodes"][nid] = {"id": nid, "label": label, "x": x, "y": y, "w": w, "h": h,
                                     "shape": "oval" if _num(get("rx")) >= 20 else "rect", "stroke": get("stroke")}
            elif tag == "polygon":
                v = [float(p) for p in re.findall(r"-?\d*\.?\d+", get("points") or "")]
                xs, ys = v[0::2], v[1::2]
                if xs:
                    fig["nodes"][nid] = {"id": nid, "label": label, "x": min(xs), "y": min(ys), "w": max(xs) - min(xs),
                                         "h": max(ys) - min(ys), "shape": "diamond", "stroke": get("stroke"),
                                         "cx": _num(get("data-cx"), None), "cy": _num(get("data-cy"), None)}
        if tag == "path" and get("data-from") is not None and get("data-to") is not None:
            fig["edges"].append({"from": get("data-from"), "to": get("data-to"), "label": get("data-label") or "",
                                 "dashed": get("stroke-dasharray") is not None, "stroke": get("stroke"),
                                 "points": _path_points(get("d"))})
        if tag == "rect" and get("data-group") is not None:
            fig["frames"].append({"id": get("data-group"), "label": get("data-name") or "",
                                  "x": _num(get("x")), "y": _num(get("y")), "w": _num(get("width")), "h": _num(get("height")),
                                  "members": [m for m in (get("data-members") or "").split(",") if m]})
    return fig


def layout_rows(fig):
    """The compact outline every render verdict carries: chart axes and series, a sequence's
    messages in order, or a diagram's rows of boxes left to right and each frame's members."""
    if fig["roles"]:
        out = []
        for role, name in ROLES:
            vals = list(dict.fromkeys(fig["roles"].get(role, [])))
            if vals:
                out.append(f"{name}: " + ", ".join(vals))
        return out or None
    if fig["messages"]:
        return (["actors: " + " | ".join(fig["actors"])] +
                [f"{k}. {m['from']} -> {m['to']}" + (f": {m['label']}" if m["label"] else "")
                 for k, m in enumerate(fig["messages"], 1)])
    boxes, label = [], {}
    for n in fig["nodes"].values():
        label[n["id"]] = n["label"]
        if n["shape"] == "diamond":
            if n.get("cx") is not None and n.get("cy") is not None:
                boxes.append((n["cy"], n["cx"], n["label"] + " (decision)"))
        else:
            boxes.append((n["y"] + n["h"] / 2, n["x"] + n["w"] / 2, n["label"]))
    if not boxes:
        return None
    rows = []
    for cy, cx, name in sorted(boxes):
        if rows and abs(rows[-1][0] - cy) < 30:
            rows[-1][1].append((cx, name))
        else:
            rows.append([cy, [(cx, name)]])
    out = [f"row {k + 1}: " + " | ".join(n for _, n in sorted(r[1])) for k, r in enumerate(rows)]
    for f in fig["frames"]:
        out.append(f"frame {f['label']}: " + ", ".join(label.get(m, m) for m in f["members"]))
    return out


def outline(fig):
    """The structured outline (--outline): nodes with their row and position, edges with labels,
    groups with members, sequence messages, chart axes and series. Long lists are capped."""
    out = {"size": fig["size"]}
    nodes = list(fig["nodes"].values())
    if nodes and not fig["messages"]:
        centers = sorted({round(n["y"] + n["h"] / 2) for n in nodes})
        rows, row_of = [], {}
        for c in centers:
            if not rows or c - rows[-1] >= 30:
                rows.append(c)
            row_of[c] = len(rows)
        group_of = {m: f["id"] for f in fig["frames"] for m in f["members"]}
        out["nodes"] = [{"id": n["id"], "name": n["label"], "shape": n["shape"],
                         "row": row_of[round(n["y"] + n["h"] / 2)],
                         "x": round(n["x"] + n["w"] / 2), "y": round(n["y"] + n["h"] / 2),
                         **({"group": group_of[n["id"]]} if n["id"] in group_of else {})} for n in nodes[:CAP]]
    if fig["edges"]:
        out["edges"] = [{"from": e["from"], "to": e["to"], **({"label": e["label"]} if e["label"] else {}),
                         **({"dashed": True} if e["dashed"] else {})} for e in fig["edges"][:CAP]]
    if fig["frames"]:
        out["groups"] = [{"id": f["id"], "name": f["label"], "members": f["members"]} for f in fig["frames"]]
    if fig["messages"]:
        out["actors"] = fig["actors"]
        out["messages"] = fig["messages"][:CAP]
    for role, name in ROLES:
        if fig["roles"].get(role):
            out[name.replace(" ", "_")] = list(dict.fromkeys(fig["roles"][role]))
    more = {k: n - CAP for k, n in (("nodes", len(nodes)), ("edges", len(fig["edges"])), ("messages", len(fig["messages"])))
            if n > CAP}
    if more:
        out["more"] = more
    return out


def svg_model(fig):
    """Boxes, decisions, arrows and frames of a drawn flow or arch: the editable exports' input."""
    nodes = fig["nodes"]
    model_nodes = [{k: v for k, v in n.items() if k not in ("cx", "cy")} for n in nodes.values()]
    return {"nodes": model_nodes, "edges": [e for e in fig["edges"] if e["from"] in nodes and e["to"] in nodes],
            "frames": [{k: v for k, v in f.items() if k != "members"} for f in fig["frames"]]}

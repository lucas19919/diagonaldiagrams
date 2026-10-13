"""Mermaid input (flowchart, sequenceDiagram, erDiagram) and load_spec."""
import json, sys
from .errors import SpecError
from ._draw import _FA_ICONS


# ---------- Mermaid input ----------
# Agents already write Mermaid. These read flowchart/graph, sequenceDiagram, and erDiagram text
# into the same specs the JSON route uses, so layout, audit, and repair apply unchanged.

_MM_KINDS = {"flowchart": "flow", "graph": "flow", "sequencediagram": "seq", "erdiagram": "schema"}


def _split_mermaid_semicolons(line):
    chunks, cur = [], []
    in_q, bracket_depth = None, 0
    for ch in line:
        if ch in ('"', "'") and not in_q:
            in_q = ch
            cur.append(ch)
        elif ch == in_q:
            in_q = None
            cur.append(ch)
        elif not in_q:
            if ch in ('[', '(', '{'):
                bracket_depth += 1
                cur.append(ch)
            elif ch in (']', ')', '}'):
                bracket_depth = max(0, bracket_depth - 1)
                cur.append(ch)
            elif ch == ';' and bracket_depth == 0:
                chunk = "".join(cur).strip()
                if chunk:
                    chunks.append(chunk)
                cur = []
            else:
                cur.append(ch)
        else:
            cur.append(ch)
    chunk = "".join(cur).strip()
    if chunk:
        chunks.append(chunk)
    return chunks


def _mermaid_lines(text):
    """(title, [(line number, stripped line)]): front matter title pulled out, comments dropped."""
    raw = str(text).replace("\r\n", "\n").split("\n")
    title, start = "", 0
    if raw and raw[0].strip() == "---":
        for j in range(1, len(raw)):
            if raw[j].strip() == "---":
                for fm in raw[1:j]:
                    if fm.strip().lower().startswith("title:"):
                        title = fm.split(":", 1)[1].strip().strip("\"'")
                start = j + 1
                break
    out = []
    for k in range(start, len(raw)):
        s = raw[k].strip()
        if not s or s.startswith("%%"):
            continue
        # a ; ends a statement too, so "flowchart TD; A --> B" works on one line
        for c in (_split_mermaid_semicolons(s) if ";" in s else [s]):
            if not c.startswith("%%"):
                out.append((k + 1, c))  # the line number in the file, front matter included
    return title, out


def _mermaid_kind(text):
    """'flow', 'seq', or 'schema' for Mermaid text we read; the Mermaid keyword for one we do not;
    None when the text is not Mermaid at all."""
    _, lines = _mermaid_lines(text)
    if not lines:
        return None
    head = lines[0][1].split()[0].lower().rstrip(":;")
    if head in _MM_KINDS:
        return _MM_KINDS[head]
    known = ("pie", "classdiagram", "statediagram", "statediagram-v2", "gantt", "journey", "gitgraph",
             "mindmap", "timeline", "quadrantchart", "xychart-beta", "sankey-beta", "block-beta",
             "architecture-beta", "requirementdiagram", "c4context", "kanban", "packet-beta", "radar-beta")
    return head if head in known else None


def _mm_text(s):
    """A Mermaid label as plain text: quotes, <br>, markdown marks, and entity codes removed."""
    import re
    s = str(s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'`":
        s = s[1:-1]
    s = re.sub(r"<br\s*/?>|\\n", " ", s, flags=re.I)
    s = s.replace("**", "").replace("`", "").replace("#quot;", '"').replace("#amp;", "&")
    return " ".join(s.split())


# (open, close, shape, tag); longer openers first so "([" is not read as "("
_MM_SHAPES = [("(((", ")))", "oval", ""), ("([", "])", "oval", ""), ("((", "))", "oval", ""),
              ("[(", ")]", "rect", "DB"), ("[[", "]]", "rect", ""), ("{{", "}}", "rect", ""),
              ("[/", "/]", "rect", ""), ("[\\", "\\]", "rect", ""), ("[/", "\\]", "rect", ""),
              ("[\\", "/]", "rect", ""), ("[", "]", "rect", ""), ("(", ")", "rect", ""),
              ("{", "}", "diamond", ""), (">", "]", "rect", "")]


def _mm_flow(lines, title):
    import re
    nodes, order, edges, groups, stack = {}, [], [], {}, []
    errors, warnings = [], []
    id_re = re.compile(r"[^\W][\w.]*", re.U)
    simple = re.compile(r"(<)?(-{2,}>|-{3,}|-\.+->|-\.+-|={2,}>|={3,}|-{2,}[xo]|~~~)(?:\|([^|]*)\|)?")
    texty = re.compile(r"(--|-\.|==)\s+(.+?)\s+(-{2,}>|-{3,}|\.-+>|\.-+|={2,}>|={3,}|-{2,}[xo])")

    def node_at(s, i, ln):
        m = id_re.match(s, i)
        if not m:
            return None, i
        nid, i = m.group(0), m.end()
        name, shape, tag = None, None, ""
        for op, cl, sh, tg in _MM_SHAPES:
            if s.startswith(op, i):
                j = i + len(op)
                if j < len(s) and s[j] == '"':
                    q = s.find('"', j + 1)
                    k = s.find(cl, q + 1) if q >= 0 else -1
                else:
                    k = s.find(cl, j)
                if k < 0:
                    errors.append({"msg": f"line {ln}: '{op}' opened after '{nid}' is never closed", "fix": f"close it with '{cl}'"})
                    return None, len(s)
                name, shape, tag, i = _mm_text(s[j:k]), sh, tg, k + len(cl)
                break
        focal = False
        cm = re.match(r":::([\w-]+)", s[i:])
        if cm:
            focal = cm.group(1).lower() in ("focal", "accent", "highlight", "primary")
            i += cm.end()
        if nid not in nodes:
            nodes[nid] = {"id": nid, "name": nid}
            order.append(nid)
        n = nodes[nid]
        if name is not None:
            fa = re.search(r"fa[srb]?:fa-([\w-]+)", name)
            if fa:
                name = _mm_text(name.replace(fa.group(0), ""))
                if _FA_ICONS.get(fa.group(1)):
                    n["icon"] = _FA_ICONS[fa.group(1)]
                elif not any(f"fa-{fa.group(1)};" in w["msg"] for w in warnings):
                    warnings.append({"msg": f"line {ln}: no built-in icon for fa-{fa.group(1)}; drawn without one",
                                     "fix": "use one of: " + ", ".join(sorted(_FA_ICONS))})
            n["name"] = name or nid
        if shape and shape != "rect":
            n["shape"] = shape
        if tag:
            n["tag"] = tag
        if focal:
            n["focal"] = True
        if stack and "group" not in n:
            n["group"] = stack[-1]
        return nid, i

    def group_at(s, i, ln):
        ids = []
        while True:
            while i < len(s) and s[i] == " ":
                i += 1
            nid, i = node_at(s, i, ln)
            if nid is None:
                return ids, i
            ids.append(nid)
            m = re.match(r"\s*&\s*", s[i:])
            if not m:
                return ids, i
            i += m.end()

    for ln, line in lines[1:]:
        low = line.lower()
        if low.startswith("subgraph"):
            rest = line[8:].strip()
            m = re.match(r'([^\s\["]+)\s*\[\s*(.*?)\s*\]$', rest)
            gid, name = (m.group(1), _mm_text(m.group(2))) if m else (_mm_text(rest) or f"group{len(groups) + 1}", _mm_text(rest))
            gid = gid if re.fullmatch(r"[\w.-]+", gid) else re.sub(r"\W+", "_", gid).strip("_") or f"group{len(groups) + 1}"
            if stack:
                warnings.append({"msg": f"line {ln}: nested subgraph '{name}' is drawn beside its parent, not inside it",
                                 "fix": "flatten the nesting if the frame matters"})
            groups.setdefault(gid, {"id": gid, "name": name or gid})
            stack.append(gid)
            continue
        if low == "end":
            if stack:
                stack.pop()
            continue
        if re.match(r"(classdef|class|style|linkstyle|click|direction|acctitle|accdescr)\b", low):
            continue
        for stmt in [p.strip() for p in line.split(";") if p.strip()]:
            before = len(errors)
            prev, i = group_at(stmt, 0, ln)
            if not prev:
                if len(errors) > before:
                    continue
                errors.append({"msg": f"line {ln}: cannot read '{stmt[:40]}'",
                               "fix": "write 'A[Label] --> B{Question?}' style lines"})
                continue
            while True:
                rest = stmt[i:].lstrip()
                if not rest:
                    break
                off = len(stmt) - len(rest)
                m = simple.match(rest)
                label, arrow = "", None
                if m:
                    arrow, label = m.group(2), _mm_text(m.group(3) or "")
                else:
                    m = texty.match(rest)
                    if m:
                        arrow, label = m.group(1) + m.group(3), _mm_text(m.group(2))
                if not m:
                    errors.append({"msg": f"line {ln}: cannot read '{rest[:30]}' after '{prev[-1]}'",
                                   "fix": "join nodes with -->, ---, -.->, or ==>; labels go in -->|label|"})
                    break
                nxt, i = group_at(stmt, off + m.end(), ln)
                if not nxt:
                    errors.append({"msg": f"line {ln}: arrow from '{prev[-1]}' has no target", "fix": "add the node after the arrow"})
                    break
                for a in prev:
                    for b in nxt:
                        e = {"from": a, "to": b}
                        if label:
                            e["label"] = label
                        if "." in arrow:
                            e["async"] = True
                        if "=" in arrow:
                            e["focal"] = True
                        edges.append(e)
                prev = nxt
    # An arrow to a subgraph's id lands on that group's first member, not on a stray box.
    firsts = {}
    for nid in order:
        g = nodes[nid].get("group")
        if g and g not in firsts:
            firsts[g] = nid
    for gid in groups:
        if gid in nodes and gid in firsts and nodes[gid].get("name") == gid and not nodes[gid].get("group"):
            for e in edges:
                for k in ("from", "to"):
                    if e[k] == gid:
                        e[k] = firsts[gid]
            order.remove(gid)
            del nodes[gid]
    spec = {"title": title, "nodes": [nodes[n] for n in order], "edges": edges,
            "groups": [g for g in groups.values()]}
    spec["budget"] = False  # drawn as written: the author chose its size
    return spec, errors, warnings


def _mm_seq(lines, title):
    import re
    actors, aid, messages, errors, warnings = [], {}, [], [], []
    msg = re.compile(r"^(.+?)\s*(-->>|->>|--\)|-\)|--x|-x|-->|->)\s*([+-])?\s*(.+?)\s*:\s*(.*)$")

    def actor(name, label=None, kind=None):
        name = name.strip()
        if name not in aid:
            aid[name] = len(actors)
            actors.append({"id": name, "name": _mm_text(label) if label else name})
        elif label:
            actors[aid[name]]["name"] = _mm_text(label)
        if kind == "actor":
            actors[aid[name]]["tag"] = "USER"
    skipped = 0
    for ln, line in lines[1:]:
        low = line.lower()
        m = re.match(r"^(participant|actor)\s+(.+?)(?:\s+as\s+(.+))?$", line, re.I)
        if m:
            actor(m.group(2), m.group(3), m.group(1).lower())
            continue
        if low.startswith("title"):
            title = line[5:].strip(" :")
            continue
        m = msg.match(line)
        if m:
            a, arrow, _, b, text = m.groups()
            actor(a)
            actor(b)
            item = {"from": a.strip(), "to": b.strip(), "label": _mm_text(text)}
            if arrow in ("-->>", "-->", "--x"):
                item["reply"] = True
            if ")" in arrow:
                item["async"] = True
            messages.append(item)
            continue
        if re.match(r"(note|loop|alt|else|opt|par|and|critical|option|break|rect|end|activate|deactivate|"
                    r"autonumber|box|create|destroy|links?|properties|details)\b", low):
            skipped += 1
            continue
        errors.append({"msg": f"line {ln}: cannot read '{line[:40]}'", "fix": "write 'A->>B: message' lines"})
    if skipped:
        warnings.append({"msg": f"{skipped} notes, blocks, or activations are not drawn",
                         "fix": "put what matters in the message labels"})
    spec = {"title": title, "actors": actors, "messages": messages}
    spec["budget"] = False  # drawn as written: the author chose its size
    return spec, errors, warnings


def _mm_er(lines, title):
    import re
    tables, order, rels, errors, warnings = {}, [], [], [], []
    rel = re.compile(r"^([\w-]+)\s*(\|o|\|\||\}o|\}\|)(--|\.\.)(o\||\|\||o\{|\|\{)\s*([\w-]+)\s*:\s*(.*)$")

    def table(name):
        if name not in tables:
            tables[name] = {"id": name, "name": name, "columns": []}
            order.append(name)
        return tables[name]
    cur = None
    for ln, line in lines[1:]:
        if cur is not None:
            if line.startswith("}"):
                cur = None
                continue
            parts = line.split('"', 1)[0].split()  # a quoted comment is not part of the keys
            if len(parts) >= 2:
                keys = set(re.split(r"[\s,]+", " ".join(parts[2:]).upper()))
                col = {"name": parts[1], "type": parts[0]}
                if "PK" in keys:
                    col["pk"] = True
                if "FK" in keys:
                    col["fk"] = True
                if "UK" in keys:
                    col["unique"] = True
                cur["columns"].append(col)
            continue
        m = re.match(r"^([\w-]+)\s*\{\s*$", line)
        if m:
            cur = table(m.group(1))
            continue
        m = rel.match(line)
        if m:
            a, left, _, right, b, verb = m.groups()
            table(a)
            table(b)
            many_l, many_r = "}" in left, "{" in right
            card = {(False, True): "1:N", (True, False): "N:1", (True, True): "M:N"}.get((many_l, many_r), "1:1")
            verb = _mm_text(verb)
            rels.append({"from": a, "to": b, "label": f"{card} {verb}".strip()})
            continue
        if re.match(r"^[\w-]+$", line):
            table(line)
            continue
        errors.append({"msg": f"line {ln}: cannot read '{line[:40]}'", "fix": "write 'A ||--o{ B : label' or 'A { type name PK }'"})
    spec = {"title": title, "tables": [tables[n] for n in order], "relations": rels}
    spec["budget"] = False  # drawn as written: the author chose its size
    return spec, errors, warnings


def _mermaid_spec(text):
    """Mermaid text as a spec dict. Parse problems ride along in _errors and _warnings."""
    title, lines = _mermaid_lines(text)
    kind = _mermaid_kind(text)
    if kind not in ("flow", "seq", "schema"):
        name = lines[0][1].split()[0] if lines else "(empty)"
        return {"_kind": None, "_errors": [{"msg": f"Mermaid '{name}' is not read yet",
                                             "fix": "flowchart, graph, sequenceDiagram, and erDiagram are; or use describe for a JSON type"}]}
    if kind == "flow":
        head = lines[0][1].split()
        if len(head) > 1 and head[1].upper() in ("LR", "RL", "BT"):
            pre = [{"msg": f"direction {head[1].upper()} is drawn top-down", "fix": "this engine lays flows out top to bottom"}]
        else:
            pre = []
        spec, errors, warnings = _mm_flow(lines, title)
        warnings = pre + warnings
    elif kind == "seq":
        spec, errors, warnings = _mm_seq(lines, title)
    else:
        spec, errors, warnings = _mm_er(lines, title)
    spec["_kind"] = kind
    main = {"flow": "nodes", "seq": "messages", "schema": "tables"}[kind]
    if not errors and not spec.get(main):
        errors = [{"msg": f"this {lines[0][1].split()[0]} has no {'messages' if kind == 'seq' else main} yet",
                   "fix": {"flow": "add a line like 'A[Start] --> B[Next]'", "seq": "add a line like 'A->>B: hello'",
                           "schema": "add a line like 'A ||--o{ B : has'"}[kind]}]
    if errors:
        spec["_errors"] = errors
    if warnings:
        spec["_warnings"] = warnings
    return spec


def _yaml():
    """(PyYAML is installed, the module): imported only for a YAML file, as it takes 30 ms to load."""
    from ._yaml import HAS_YAML, yaml
    return HAS_YAML, yaml


def load_spec(path, kind=None):
    """The spec in a file: JSON, YAML or Mermaid. A v2 scene ("version": 2) comes back as the v1
    spec the renderer for `kind`, or for the scene's preset, draws."""
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    if path.lower().endswith((".mmd", ".mermaid")) or _mermaid_kind(txt):
        return _mermaid_spec(txt)
    if path.endswith(".json"):
        spec = json.loads(txt)
    elif path.endswith((".yaml", ".yml")) and _yaml()[0]:
        spec = _yaml()[1].safe_load(txt)
    else:
        # minimal fallback: JSON in .yaml also works
        try:
            spec = json.loads(txt)
        except Exception:
            raise SpecError(f"{path}: need PyYAML for YAML (pip install pyyaml) or use JSON")
    if isinstance(spec, dict) and spec.get("version") == 2:
        from .inputs.v1 import scene_as_v1
        return scene_as_v1(spec, kind)
    return spec

"""extract: specs from SQL DDL, Prisma, Python ORMs and web routes."""
import json, os
from .errors import SpecError


def _split_ddl(body):
    """Split a CREATE TABLE body on commas at paren-depth 0 (DECIMAL(10,2) safe).
    Handles packed single-line and one-column-per-line DDL alike."""
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def do_extract(args):
    import re, ast
    src = args.source
    if not os.path.exists(src):
        raise SpecError(f"source file not found: {src}")
    with open(src, encoding="utf-8") as f:
        code = f.read()
    if args.o:
        parent = os.path.dirname(os.path.abspath(args.o))
        os.makedirs(parent, exist_ok=True)
    if args.ext_type == "schema":
        tables, relations = [], []
        if src.endswith(".sql"):
            tbl_matches = re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)\s*\(([\s\S]*?)\);", code, re.IGNORECASE)
            for tm in tbl_matches:
                tname = tm.group(1)
                body = tm.group(2)
                cols = []
                for line in _split_ddl(body):
                    line = line.strip()
                    if not line or line.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "CONSTRAINT", "INDEX", "UNIQUE")):
                        fk_m = re.search(r"FOREIGN\s+KEY\s*\(([a-zA-Z0-9_]+)\)\s*REFERENCES\s*([a-zA-Z0-9_]+)\s*\(([a-zA-Z0-9_]+)\)", line, re.IGNORECASE)
                        if fk_m:
                            relations.append({"from": fk_m.group(2), "from_col": fk_m.group(3), "to": tname, "to_col": fk_m.group(1), "label": "1:N"})
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        cname, ctype = parts[0], parts[1]
                        is_pk = "PRIMARY KEY" in line.upper()
                        cols.append({"name": cname, "type": ctype, "pk": is_pk})
                tables.append({"id": tname, "name": tname, "columns": cols})
        elif src.endswith(".prisma"):
            scalars = {"String", "Boolean", "Int", "BigInt", "Float", "Decimal", "DateTime", "Json", "Bytes"}
            for mm in re.finditer(r"model\s+([a-zA-Z0-9_]+)\s*\{([^}]*)\}", code):
                tname, cols = mm.group(1).lower(), []
                for line in mm.group(2).split("\n"):
                    line = line.strip()
                    if not line or line.startswith(("@@", "//")):
                        continue
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    cname, ctype, rest = parts[0], parts[1].rstrip("?"), " ".join(parts[2:])
                    col = {"name": cname, "type": parts[1],
                           "pk": "@id" in rest, "unique": "@unique" in rest}
                    cols.append(col)
                    if ctype not in scalars:
                        # object-side relation field: Team @relation(fields:[fk], references:[pk])
                        fm = re.search(r"fields\s*:\s*\[([a-zA-Z0-9_]+)\]", rest)
                        pm = re.search(r"references\s*:\s*\[([a-zA-Z0-9_]+)\]", rest)
                        if fm and pm:
                            relations.append({"from": ctype.lower(), "from_col": pm.group(1),
                                              "to": tname, "to_col": fm.group(1), "label": "1:N"})
                if cols:
                    tables.append({"id": tname, "name": mm.group(1), "columns": cols[:12]})
        elif src.endswith(".py"):
            try:
                tree = ast.parse(code)

                def _call_name(call):
                    f = call.func
                    if isinstance(f, ast.Attribute):
                        return f.attr
                    return getattr(f, "id", "")

                def _kw_true(call, names):
                    return any(k.arg in names and isinstance(k.value, ast.Constant) and k.value.value is True
                               for k in call.keywords)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        tname = node.name.lower()
                        for _tn in node.body:  # SQLAlchemy reality: table name wins over class name
                            if isinstance(_tn, ast.Assign):
                                for _t in _tn.targets:
                                    if isinstance(_t, ast.Name) and _t.id == "__tablename__" \
                                            and isinstance(_tn.value, ast.Constant):
                                        tname = str(_tn.value.value)
                        is_django = any("Model" in ast.unparse(b) for b in node.bases) if hasattr(ast, "unparse") else False
                        cols = []
                        for item in node.body:
                            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                                cname = item.target.id
                                if cname.startswith("__"):
                                    continue
                                ctype = ast.unparse(item.annotation) if hasattr(ast, "unparse") else "any"
                                col = {"name": cname, "type": ctype, "pk": cname.lower() == "id"}
                                cols.append(col)
                                if isinstance(item.value, ast.Call):  # SQLModel: Field(foreign_key="t.c")
                                    for k in item.value.keywords:
                                        if k.arg == "foreign_key" and isinstance(k.value, ast.Constant) \
                                                and "." in str(k.value.value):
                                            ref = str(k.value.value).split(".")
                                            col["fk"] = True
                                            relations.append({"from": ref[0], "from_col": ref[1],
                                                              "to": tname, "to_col": cname, "label": "1:N"})
                            elif isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
                                call = item.value
                                fname = _call_name(call)
                                django_field = fname in ("CharField", "TextField", "IntegerField", "BigIntegerField",
                                                         "FloatField", "DecimalField", "BooleanField", "DateField",
                                                         "DateTimeField", "UUIDField", "EmailField", "ForeignKey",
                                                         "OneToOneField", "ManyToManyField", "AutoField", "BigAutoField")
                                if is_django or django_field:
                                    for tgt in item.targets:
                                        if not isinstance(tgt, ast.Name):
                                            continue
                                        cname = tgt.id
                                        if fname in ("ForeignKey", "OneToOneField"):
                                            arg0 = call.args[0] if call.args else None
                                            target = ""
                                            if isinstance(arg0, ast.Constant):
                                                target = str(arg0.value).split(".")[-1]
                                            elif isinstance(arg0, ast.Name):
                                                target = arg0.id
                                            cols.append({"name": cname, "type": fname, "pk": _kw_true(call, ("primary_key",))})
                                            if target and target.lower() != "self":
                                                relations.append({"from": target.lower(), "from_col": "id",
                                                                  "to": tname, "to_col": cname, "label": "1:N"})
                                        elif fname != "ManyToManyField":
                                            cols.append({"name": cname, "type": fname,
                                                         "pk": _kw_true(call, ("primary_key",)) or cname.lower() == "id"})
                                else:
                                    for tgt in item.targets:
                                        if not isinstance(tgt, ast.Name) or tgt.id.startswith("__"):
                                            continue
                                        cname = tgt.id
                                        ctype, fk_hit = "column", None
                                        for a in list(call.args) + [k.value for k in call.keywords]:
                                            if isinstance(a, ast.Call) and _call_name(a) == "ForeignKey" and a.args:
                                                ref = a.args[0]
                                                if isinstance(ref, ast.Constant) and "." in str(ref.value):
                                                    fk_hit = str(ref.value).split(".")
                                            elif isinstance(a, ast.Name):
                                                ctype = a.id
                                            elif isinstance(a, ast.Attribute):
                                                ctype = a.attr
                                        col = {"name": cname, "type": ctype,
                                               "pk": _kw_true(call, ("primary_key",)) or cname.lower() == "id"}
                                        cols.append(col)
                                        if fk_hit:
                                            col["fk"] = True
                                            relations.append({"from": fk_hit[0], "from_col": fk_hit[1],
                                                              "to": tname, "to_col": cname, "label": "1:N"})
                        if cols:
                            tables.append({"id": tname, "name": node.name, "columns": cols[:10]})
            except Exception as e:
                raise SpecError(f"AST parse failed: {e}")
        for rel in relations:  # back-mark FK columns so badges render
            for tbl in tables:
                if tbl["id"] == rel["to"]:
                    for col in tbl["columns"]:
                        if col["name"] == rel["to_col"]:
                            col["fk"] = True
        spec = {"title": f"Schema from {os.path.basename(src)}", "sub": "Auto-extracted database schema", "tables": tables, "relations": relations}
        if args.o:
            with open(args.o, "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=2)
            print(f"wrote extracted schema to {args.o} ({len(tables)} tables)")
        else:
            print(json.dumps(spec, indent=2))
    elif args.ext_type == "routes":
        nodes = [{"id": "client", "name": "Client", "tag": "USER", "layer": 0}]
        edges = []
        routes = re.findall(r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', code, re.IGNORECASE)
        for method, path in routes[:8]:
            rid = re.sub(r'[^a-zA-Z0-9_]', '_', path).strip('_') or "root"
            nodes.append({"id": rid, "name": path, "sub": method.upper(), "tag": "API", "layer": 1})
            edges.append({"from": "client", "to": rid, "label": method.upper(), "proto": "https"})
        spec = {"title": f"Routes from {os.path.basename(src)}", "sub": "Auto-extracted API routes", "nodes": nodes, "edges": edges}
        if args.o:
            with open(args.o, "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=2)
            print(f"wrote extracted routes to {args.o} ({len(nodes)} nodes)")
        else:
            print(json.dumps(spec, indent=2))


def _merge_specs(specs, kind):
    """Union per-file extractions (models/*.py is many files, one diagram)."""
    if kind == "schema":
        tables, rels, seen = {}, [], set()
        for s in specs:
            for t in s.get("tables", []):
                tables.setdefault(t["id"], t)
            for r in s.get("relations", []):
                k = (r.get("from"), r.get("from_col"), r.get("to"), r.get("to_col"))
                if k not in seen:
                    seen.add(k)
                    rels.append(r)
        return {"tables": list(tables.values()), "relations": rels}
    nodes, edges, nseen, eseen = [], [], set(), set()
    for s in specs:
        for n in s.get("nodes", []):
            if n.get("id") not in nseen:
                nseen.add(n["id"])
                nodes.append(n)
        for e in s.get("edges", []):
            k = (e.get("from"), e.get("to"), e.get("label"))
            if k not in eseen:
                eseen.add(k)
                edges.append(e)
    return {"nodes": nodes, "edges": edges}


def _spec_diff(existing, fresh, kind):
    """Semantic diff (layout-blind): '' = in sync, else human summary."""
    bits = []
    if kind == "schema":
        old = {t["id"]: {c["name"]: c.get("type", "") for c in t.get("columns", [])} for t in existing.get("tables", [])}
        new = {t["id"]: {c["name"]: c.get("type", "") for c in t.get("columns", [])} for t in fresh.get("tables", [])}
        for tid in sorted(set(new) - set(old)):
            bits.append(f"Added table '{tid}'")
        for tid in sorted(set(old) - set(new)):
            bits.append(f"Removed table '{tid}'")
        for tid in sorted(set(old) & set(new)):
            o, n = old[tid], new[tid]
            for c in sorted(set(n) - set(o)):
                bits.append(f"table '{tid}': +column '{c}'")
            for c in sorted(set(o) - set(n)):
                bits.append(f"table '{tid}': -column '{c}'")
            for c in sorted(set(o) & set(n)):
                if o[c] != n[c]:
                    bits.append(f"table '{tid}': ~column '{c}' ({o[c]}→{n[c]})")
    else:
        old_n = {n.get("id") for n in existing.get("nodes", [])}
        new_n = {n.get("id") for n in fresh.get("nodes", [])}
        old_e = {(e.get("from"), e.get("to")) for e in existing.get("edges", [])}
        new_e = {(e.get("from"), e.get("to")) for e in fresh.get("edges", [])}
        for i in sorted(new_n - old_n):
            bits.append(f"Added node '{i}'")
        for i in sorted(old_n - new_n):
            bits.append(f"Removed node '{i}'")
        for a, b in sorted(new_e - old_e):
            bits.append(f"Added edge {a}->{b}")
        for a, b in sorted(old_e - new_e):
            bits.append(f"Removed edge {a}->{b}")
    return "; ".join(bits[:12])

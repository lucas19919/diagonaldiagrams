"""doc: compile fenced graph blocks in Markdown into SVGs."""
import json, os, sys
from .errors import SpecError
from ._yaml import HAS_YAML, yaml
from ._lazy import lazy

render_arch = lazy("diagonaldiagrams.diagrams", "render_arch")
render_flow = lazy("diagonaldiagrams.diagrams", "render_flow")
render_schema = lazy("diagonaldiagrams.diagrams", "render_schema")
render_seq = lazy("diagonaldiagrams.diagrams", "render_seq")
_validate_spec_dict = lazy("diagonaldiagrams.validate", "_validate_spec_dict")


def _inject_links(content, items):
    """Idempotent figure-link injection after each fence. Re-run safe:
    an existing anchor+link pair for the id is replaced, never duplicated."""
    import re
    for end, diag_id, title, rel in sorted(items, reverse=True):
        safe = title.replace("[", "").replace("]", "")
        anchor = f"<!-- graph:{diag_id} -->\n![{safe}]({rel})"
        tail = content[end:]
        m2 = re.match(r"\n?<!-- graph:" + re.escape(diag_id) + r" -->\n!\[[^\]]*\]\([^)\s]*\)", tail)
        if m2:
            content = content[:end] + "\n" + anchor + tail[m2.end():]
        else:
            content = content[:end] + "\n" + anchor + tail
    return content


def do_doc(args):
    import re, hashlib
    target = args.target
    if not os.path.exists(target):
        raise SpecError(f"doc target not found: {target}")
    with open(target, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(r"```(?:graph|graph-spec):([a-zA-Z0-9_-]+)(?:[ \t]+([^\n]*))?\n([\s\S]*?)```")
    matches = list(pattern.finditer(content))
    if not matches:
        print(f"{target}: no ```graph:<type> blocks found")
        return
    base_dir = os.path.dirname(os.path.abspath(target))
    out_dir = args.out_dir or os.path.join(base_dir, "assets")
    if not args.check:  # --check is strictly read-only (CI)
        os.makedirs(out_dir, exist_ok=True)
    count, errs, injections = 0, 0, []
    for idx, m in enumerate(matches):
        kind = m.group(1).lower()
        meta = m.group(2) or ""
        body = m.group(3).strip()
        diag_id = f"diagram_{idx+1}"
        title = kind.capitalize()
        id_m = re.search(r'id="([^"]+)"', meta)
        if id_m:
            diag_id = id_m.group(1)
        t_m = re.search(r'title="([^"]+)"', meta)
        if t_m:
            title = t_m.group(1)
        ve, vw = [], []
        try:
            if kind in ("arch", "flow", "seq", "schema"):
                spec = json.loads(body) if body.startswith("{") else (yaml.safe_load(body) if HAS_YAML else json.loads(body))
                if "title" not in spec:
                    spec["title"] = title
                _validate_spec_dict(spec, ve, vw)  # validate BEFORE render
                if ve:
                    raise ValueError("validate: " + "; ".join(d["msg"] for d in ve))
                if kind == "flow":
                    svg, _, _ = render_flow(spec)
                elif kind == "arch":
                    svg, _, _ = render_arch(spec)
                elif kind == "seq":
                    svg, _, _ = render_seq(spec)
                elif kind == "schema":
                    svg, _, _ = render_schema(spec)
                out_svg = os.path.join(out_dir, f"{diag_id}.svg")
                digest = hashlib.sha1(svg.encode("utf-8")).hexdigest()
                if args.check:
                    if not os.path.exists(out_svg):
                        print(f"  [missing] {diag_id} ({kind}): run without --check first")
                        errs += 1
                    elif hashlib.sha1(open(out_svg, encoding="utf-8").read().encode("utf-8")).hexdigest() != digest:
                        print(f"  [stale] {diag_id} ({kind}): {out_svg} differs from spec")
                        errs += 1
                    else:
                        print(f"  [ok] {diag_id} ({kind})")
                        count += 1
                else:
                    with open(out_svg, "w", encoding="utf-8") as sf:
                        sf.write(svg)
                    count += 1
                    print(f"  [compiled] {kind} -> {out_svg}")
                    rel = os.path.relpath(out_svg, base_dir).replace(os.sep, "/")
                    injections.append((m.end(), diag_id, title, rel))
            else:
                errs += 1
                print(f"  [skip] {diag_id}: unknown kind '{kind}'", file=sys.stderr)
        except Exception as e:
            errs += 1
            print(f"  [error] {diag_id} ({kind}): {e}", file=sys.stderr)
    if injections and not args.check:
        with open(target, "w", encoding="utf-8") as f:
            f.write(_inject_links(content, injections))
        print(f"doc: figure links synced in {target}")
    print(f"doc: processed {count} diagrams ({errs} errors)")
    if errs > 0:
        return 1

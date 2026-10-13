"""The audit: reads a finished figure and reports what an agent cannot see in it.

svg_import turns any SVG into a display list; checks.CHECKS run over it in order.
"""
import json, os

from ..geom import affine as _affine, xbox as _xbox  # noqa: F401  (old names, kept for graph.<name>)
from .checks import CHECKS, WARNINGS, run_checks  # noqa: F401
from .svg_import import svg_import


def _svg_geometry(root, W, H, stats=None):
    """Collisions an agent cannot see in its own output: label on label, label off the
    canvas, label wider than its box, box on box. Returns error dicts with a fix."""
    return run_checks(svg_import(root, W, H), stats)


def do_audit(args):
    rep = _audit_file(args.target)
    print(json.dumps(rep, indent=2))
    return 0 if rep["ok"] else 1


def _audit_file(p):
    """Every check `audit` runs, as a report dict. Render calls it after drawing."""
    import re, xml.etree.ElementTree as ET
    errors, warnings = [], []
    if not os.path.isfile(p):
        return {"ok": False, "errors": [{"msg": f"no file {p}", "fix": "render first; audit takes the .svg or .html it wrote"}], "warnings": []}
    raw = open(p, encoding="utf-8", errors="replace").read()
    # the outermost <svg> first (D2 nests one svg in another), then the first whole one (an HTML page)
    a, b = raw.find("<svg"), raw.rfind("</svg>")
    m = re.search(r"<svg[\s\S]*?</svg>", raw)
    root, err = None, None
    for svg in ([raw[a:b + 6]] if a >= 0 and b > a else []) + ([m.group(0)] if m else [raw]):
        try:
            root = ET.fromstring(svg)
            break
        except ET.ParseError as e:
            err = err or e
    if root is None:
        return {"ok": False, "errors": [{"msg": f"malformed SVG: {err}"}], "warnings": []}
    W = H = 0
    vb = root.get("viewBox", "").split()
    if len(vb) == 4:
        W, H = float(vb[2]), float(vb[3])
    def _tagged(name):
        return [el for el in root.iter() if str(el.tag).split("}")[-1] == name]
    texts = _tagged("text")
    if not any(t.get("font-size") == "24" for t in texts) and not _tagged("title"):
        warnings.append({"msg": "no <title>: screen readers and docs see an unnamed figure", "fix": "add <title> as the first child of <svg>"})
    if not _tagged("desc"):
        warnings.append({"msg": "no <desc>: add one-sentence content summary"})
    if re.search(r"font-family='[^\"\]]", svg):
        errors.append({"msg": "unquoted font-family attribute", "fix": 'wrap families: font-family="\'Inter\',sans-serif"'})
    if sum(1 for t in texts if t.get("font-size") == "24") > 1:
        warnings.append({"msg": "2+ hero titles inside one figure", "fix": "title once (page XOR figure)"})
    neg = [t.text for t in texts if (t.text or "").strip().startswith("-") and re.fullmatch(r"-\d[\d.,k]*", (t.text or "").strip())]
    if neg:
        warnings.append({"msg": f"negative ticks {neg}", "fix": "verify intended; ratio data floors at 0"})
    circles = len(_tagged("circle"))
    if circles > 400:
        warnings.append({"msg": f"{circles} points over render budget", "fix": "aggregate/facet"})
    for t in texts:
        try:
            x = float(t.get("x", "0").split()[0])
            if (x < -4 or (W and x > W + 4)) and t.get("text-anchor") != "middle":
                warnings.append({"msg": f"text '{(t.text or '')[:20]}' near canvas edge x={x}", "fix": "check clipping"})
                break
        except ValueError:
            pass
    dup = [t.text for t in texts if t.text]
    from collections import Counter
    for txt, c in Counter(dup).items():
        if c > 3 and len(txt) > 8:
            warnings.append({"msg": f"'{txt[:30]}' repeated {c}x", "fix": "dedupe title/caption/source"})
            break
    for it in _svg_geometry(root, W, H):
        (warnings if it["code"] in WARNINGS else errors).append(it)
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "stats": {"texts": len(texts), "points": circles, "canvas": [W, H]}}

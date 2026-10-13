"""The engine from Python, in this process.

    import diagonaldiagrams as dd
    verdict = dd.render("flow", spec={"nodes": [...], "edges": [...]}, out="out/flow.html")
    code, stdout, stderr = dd.run(["describe", "flow"])

run() executes any command line exactly as the `diagonaldiagrams` command would and captures what
it prints, so a caller (the MCP server, a notebook, another agent's tool) gets the same text without
starting a process. tool_argv() turns an MCP-style tool call into that command line.
"""
import contextlib
import io
import json
import os
import sys
import tempfile

from ._issues import _SPEC_KEYS
from .charts.catalog import _CHART_BLURB
from ._lazy import lazy

_mermaid_kind = lazy("diagonaldiagrams.mermaid", "_mermaid_kind")

DIAGRAMS = set(_SPEC_KEYS)
OWN = {"bar", "line", "scatter", "geo"}  # data figures with their own command
ROLE_FLAGS = ("x", "y", "group", "facet", "size", "label", "parent", "val", "a", "b", "lo", "hi")


def run(argv):
    """Run one command in this process. Returns (exit code, stdout, stderr), as a subprocess would."""
    from .cli import cli
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    sys.argv = ["diagonaldiagrams", *[str(a) for a in argv]]
    code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            cli()
    except SystemExit as e:
        if isinstance(e.code, int):
            code = e.code
        elif e.code is not None:
            code = 1
            err.write(f"{e.code}\n")
    finally:
        sys.argv = saved
    return code, out.getvalue(), err.getvalue()


def flags(options):
    """CLI flags from an options dict: {"x": "month", "grid": False, "highlight": ["A", "B"]}."""
    out = []
    for k, v in (options or {}).items():
        flag = "--" + str(k).lstrip("-").replace("_", "-")
        if v is True:
            out.append(flag)
        elif v is False:
            if k in ("grid", "markers"):
                out.append("--no-" + k)
        elif isinstance(v, list):
            for item in v:
                out += [flag, str(item)]
        elif v is not None:
            out += [flag, str(v)]
    return out


def source(a, out_path=None):
    """The input as a file. Inline input is written beside the output, so export can redraw it."""
    if a.get("path") or a.get("target"):
        return a.get("path") or a.get("target")
    if a.get("scene") is not None:
        body, ext = json.dumps({"version": 2, **a["scene"]}, indent=1), ".json"
    elif a.get("spec") is not None:
        body, ext = json.dumps(a["spec"], indent=1), ".json"
    elif a.get("data") is not None:
        body = str(a["data"])
        if a.get("type") == "mermaid" or _mermaid_kind(body):
            ext = ".mmd"
        else:
            ext = ".geojson" if body.lstrip().startswith("{") else ".csv"
    else:
        raise ValueError("pass spec or scene (JSON object), data (CSV text), or path")
    if out_path:
        dest = os.path.splitext(out_path)[0] + ".input" + ext
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    else:
        fd, dest = tempfile.mkstemp(prefix="diagonaldiagrams-", suffix=ext)
        os.close(fd)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(body)
    return dest


def tool_argv(name, a):
    """The command line for an MCP tool call (describe, render, validate, audit, export, infer)."""
    kind = str(a.get("type") or "")
    if name == "describe":
        return ["describe"] + ([kind] if kind else [])
    if name == "audit":
        return ["audit", a.get("path") or a.get("target")]
    if name == "infer":
        return ["infer", source(a)]
    if name == "export":
        c = ["export", a.get("path") or a.get("target"), "--to", a.get("to") or "png"]
        if a.get("layout"):
            c += ["--layout", a["layout"]]
        return c + (["-o", a["out"]] if a.get("out") else [])
    if name == "validate":
        o = dict(a.get("options") or {})
        target = source(a)
        if kind in OWN or kind in _CHART_BLURB:
            # bar names its columns cat/val, which validate reads as --x/--y; chart types read --val themselves
            o.setdefault("x", o.pop("cat", None) or o.get("x"))
            if kind == "bar":
                o.setdefault("y", o.pop("val", None) or o.get("y"))
            o = {k: v for k, v in o.items() if k in ROLE_FLAGS and v}
            return ["validate", target, "--type", kind] + flags(o)
        return ["validate", target]
    if name == "render":
        if not kind:
            raise ValueError("render needs type")
        out = a.get("out") or ""
        if not out.endswith(".html"):
            out = os.path.splitext(out)[0] + ".html" if out else "diagonaldiagrams-out.html"
        target = source(a, out)
        head = [kind] if (kind in DIAGRAMS or kind in OWN or kind == "mermaid") else ["chart", kind]
        return head + [target, "-o", out] + flags(a.get("options"))
    raise ValueError(f"unknown tool {name}")


def render(kind, spec=None, data=None, path=None, out="diagonaldiagrams-out.html", scene=None, **options):
    """Validate, draw and audit one figure. Returns the verdict the command line prints, as a dict:
    ok, svg, html, receipt, layout, errors, warnings.

    kind: flow, arch, seq, schema, mermaid, bar, line, scatter, geo, or any `chart` kind.
    spec: a JSON-like dict; scene: a v2 scene dict (DESIGN 4) whose preset is kind; data: CSV,
    GeoJSON or Mermaid text; path: a file. Pass one.
    options: the command's flags without dashes, e.g. x="month", group="product", grid=False."""
    argv = tool_argv("render", {"type": kind, "spec": spec, "scene": scene, "data": data, "path": path, "out": out,
                                "options": options})
    code, stdout, stderr = run(argv)
    for line in reversed(stdout.strip().splitlines()):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    return {"ok": False, "errors": [{"msg": (stdout + stderr).strip()[-2000:] or f"exit {code}"}]}

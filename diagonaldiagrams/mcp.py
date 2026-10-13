"""The MCP server: the CLI as tools over stdio."""
import json, os, sys
from . import __version__
from ._issues import _SPEC_KEYS
from ._proc import _self_cmd
from .charts.catalog import _CHART_BLURB
from ._lazy import lazy

_mermaid_kind = lazy("diagonaldiagrams.mermaid", "_mermaid_kind")


def do_mcp(args):
    """MCP server over stdio: newline-delimited JSON-RPC, standard library only.
    `render` takes the spec or CSV inline, then validates, draws, and audits in one call.
    Tools return paths and a verdict, never pixels, so a call costs tens of tokens."""
    import subprocess
    import tempfile
    me, me_env = _self_cmd()
    src = {"spec": {"type": "object", "description": "JSON spec, inline"},
           "data": {"type": "string", "description": "CSV text, inline"},
           "path": {"type": "string", "description": "or a spec/CSV file on disk"}}
    opts = {"type": "object", "description": 'CLI flags without dashes, e.g. {"x": "month", "y": "signups", '
                                             '"group": "product", "title": "...", "highlight": ["Atlas"]}. describe lists them.'}
    TOOLS = [
        {"name": "describe", "description": "The spec shape, flags, and budgets for one figure type. No type: the list of types.",
         "inputSchema": {"type": "object", "properties": {"type": {"type": "string"}}}},
        {"name": "render", "description": "Validate, draw, and audit one figure. Writes OUT.svg, OUT.html, and a receipt. "
                                          "ok false: read errors, change the spec or options, call again.",
         "inputSchema": {"type": "object", "required": ["type"],
                         "properties": dict(type={"type": "string", "description": "mermaid (data = Mermaid text), flow, arch, seq, schema, bar, line, scatter, geo, or any describe type"},
                                            out={"type": "string", "description": "output path ending .html (default diagonaldiagrams-out.html)"},
                                            options=opts, **src)}},
        {"name": "validate", "description": "Check a spec or CSV without drawing.",
         "inputSchema": {"type": "object", "required": ["type"],
                         "properties": dict(type={"type": "string"}, options=opts, **src)}},
        {"name": "audit", "description": "Check any SVG for collisions, clipping, and arrows through boxes.",
         "inputSchema": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}}}},
        {"name": "export", "description": "Write png, pdf, or svg from a rendered figure's receipt.",
         "inputSchema": {"type": "object", "required": ["path"],
                         "properties": {"path": {"type": "string"}, "to": {"type": "string", "enum": ["png", "pdf", "svg", "drawio", "excalidraw"]},
                                        "layout": {"type": "string"}, "out": {"type": "string"}}}},
        {"name": "infer", "description": "Propose a scatter spec from a CSV.",
         "inputSchema": {"type": "object", "properties": {"data": {"type": "string"}, "path": {"type": "string"}}}},
    ]
    diagrams = set(_SPEC_KEYS)
    own = {"bar", "line", "scatter", "geo"}

    def flags(o):
        out = []
        for k, v in (o or {}).items():
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
        if a.get("spec") is not None:
            body, ext = json.dumps(a["spec"], indent=1), ".json"
        elif a.get("data") is not None:
            body = str(a["data"])
            if a.get("type") == "mermaid" or _mermaid_kind(body):
                ext = ".mmd"
            else:
                ext = ".geojson" if body.lstrip().startswith("{") else ".csv"
        else:
            raise ValueError("pass spec (JSON object), data (CSV text), or path")
        if out_path:
            dest = os.path.splitext(out_path)[0] + ".input" + ext
            os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        else:
            fd, dest = tempfile.mkstemp(prefix="diagonaldiagrams-", suffix=ext)
            os.close(fd)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(body)
        return dest

    def command(name, a):
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
            if kind in own or kind in _CHART_BLURB:
                # validate reads the CSV columns from --x/--y; map the bar names onto them
                o.setdefault("x", o.pop("cat", None) or o.get("x"))
                o.setdefault("y", o.pop("val", None) or o.get("y"))
                o = {k: v for k, v in o.items() if k in ("x", "y", "group", "facet") and v}
                return ["validate", target, "--type", kind] + flags(o)
            return ["validate", target]
        if name == "render":
            if not kind:
                raise ValueError("render needs type")
            out = a.get("out") or ""
            if not out.endswith(".html"):
                out = os.path.splitext(out)[0] + ".html" if out else "diagonaldiagrams-out.html"
            target = source(a, out)
            head = [kind] if (kind in diagrams or kind in own or kind == "mermaid") else ["chart", kind]
            return head + [target, "-o", out] + flags(a.get("options"))
        raise ValueError(f"unknown tool {name}")

    def call(name, a):
        try:
            argv = command(name, a or {})
        except (ValueError, KeyError, TypeError) as e:
            return {"isError": True, "content": [{"type": "text", "text": json.dumps({"ok": False, "errors": [{"msg": str(e)}]})}]}
        if any(x is None for x in argv):
            return {"isError": True, "content": [{"type": "text", "text": f"{name}: a required argument is missing"}]}
        try:
            p = subprocess.run(me + argv, capture_output=True, text=True, env=me_env,
                               encoding="utf-8", errors="replace", timeout=180)
        except subprocess.TimeoutExpired:
            return {"isError": True, "content": [{"type": "text", "text": f"{name} took over 180 s"}]}
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return {"content": [{"type": "text", "text": text[:12000]}], **({"isError": True} if p.returncode else {})}

    known = ("2025-06-18", "2025-03-26", "2024-11-05")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(m, dict) or "id" not in m:
            continue  # a notification: never answered
        mid, method, params = m.get("id"), m.get("method"), m.get("params") or {}
        reply = {"jsonrpc": "2.0", "id": mid}
        if method == "initialize":
            want = params.get("protocolVersion")
            reply["result"] = {"protocolVersion": want if want in known else known[0],
                               "capabilities": {"tools": {}},
                               "serverInfo": {"name": "diagonaldiagrams", "version": __version__}}
        elif method == "ping":
            reply["result"] = {}
        elif method == "tools/list":
            reply["result"] = {"tools": TOOLS}
        elif method == "tools/call":
            reply["result"] = call(params.get("name"), params.get("arguments"))
        else:
            reply["error"] = {"code": -32601, "message": f"method not found: {method}"}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()

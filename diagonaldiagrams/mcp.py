"""The MCP server: the CLI as tools over stdio."""
import json, sys
from . import __version__
from ._proc import _self_cmd
from .api import run, tool_argv


def do_mcp(args):
    """MCP server over stdio: newline-delimited JSON-RPC, standard library only.
    `render` takes the spec or CSV inline, then validates, draws, and audits in one call.
    Tools return paths and a verdict, never pixels, so a call costs tens of tokens.

    Each call runs in this process (diagonaldiagrams.api.run). --isolate runs each in its own
    process instead, with a 180 s limit."""
    isolate = getattr(args, "isolate", False)
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

    def call(name, a):
        try:
            argv = tool_argv(name, a or {})
        except (ValueError, KeyError, TypeError) as e:
            return {"isError": True, "content": [{"type": "text", "text": json.dumps({"ok": False, "errors": [{"msg": str(e)}]})}]}
        if any(x is None for x in argv):
            return {"isError": True, "content": [{"type": "text", "text": f"{name}: a required argument is missing"}]}
        if isolate:
            import subprocess
            me, me_env = _self_cmd()
            try:
                p = subprocess.run(me + argv, capture_output=True, text=True, env=me_env,
                                   encoding="utf-8", errors="replace", timeout=180)
            except subprocess.TimeoutExpired:
                return {"isError": True, "content": [{"type": "text", "text": f"{name} took over 180 s"}]}
            code, out, err = p.returncode, p.stdout or "", p.stderr or ""
        else:
            code, out, err = run(argv)
        text = (out + err).strip()
        return {"content": [{"type": "text", "text": text[:12000]}], **({"isError": True} if code else {})}

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

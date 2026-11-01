"""The MCP server: the CLI as tools over stdio."""
import json, sys
from . import __version__
from ._proc import _self_cmd
from .api import run, tool_argv


def tools():
    """The tool list the server advertises. Every tool has a title, annotations (what it reads and
    writes) and a description on every parameter; tests/unit/test_mcp_tools.py keeps it that way."""
    src = {"spec": {"type": "object", "description": "The figure as a JSON object, inline, in the shape `describe <type>` prints. "
                                                     "Give exactly one of spec, scene, data or path."},
           "scene": {"type": "object", "description": 'A v2 scene, inline: {"preset": "flow", "nodes": [...], '
                                                      '"edges": [...], "groups": [...]}; type names its preset. '
                                                      'Give exactly one of spec, scene, data or path.'},
           "data": {"type": "string", "description": "CSV, GeoJSON or Mermaid text, inline. "
                                                     "Give exactly one of spec, scene, data or path."},
           "path": {"type": "string", "description": "A spec, scene, CSV or Mermaid file on disk, instead of inline input."}}
    opts = {"type": "object", "description": 'CLI flags without dashes, e.g. {"x": "month", "y": "signups", '
                                             '"group": "product", "title": "...", "highlight": ["Atlas"]}. describe lists them. '
                                             'Diagrams also take "style": a stylesheet object (or a list of them), '
                                             '"font": "Inter", and "fit": where the figure goes, "slide" (default), '
                                             '"page" or "column" (a narrow docs or notes column); describe style lists '
                                             'properties and selectors.'}
    kind = "Figure type: mermaid (data is Mermaid text), flow, arch, seq, schema, iso (3D layer stack), bar, line, scatter, geo, or any chart type that describe lists."

    def ann(title, read_only, idempotent, destructive=False):
        # openWorldHint is false throughout: nothing here talks to the network.
        a = {"title": title, "readOnlyHint": read_only, "openWorldHint": False}
        if not read_only:
            a.update(destructiveHint=destructive, idempotentHint=idempotent)
        else:
            a["idempotentHint"] = True
        return a

    return [
        {"name": "describe", "title": "Describe a figure type",
         "description": "Look up how to write a spec. With a figure type it returns that type's spec shape, rules, "
                        "size budgets and an example; with no type it lists every type. Also takes style and story. "
                        "Read-only, writes nothing. Call it before render when you are unsure of the shape.",
         "annotations": ann("Describe a figure type", True, True),
         "inputSchema": {"type": "object",
                         "properties": {"type": {"type": "string", "description": "Figure type to describe, e.g. flow, arch, iso, bar, style or story. Omit to list all types."}}}},
        {"name": "render", "title": "Draw and audit a figure",
         "description": "Draw one figure and audit it in a single call. Validates the input, lays it out, writes OUT.svg, "
                        "OUT.html and a receipt (OUT.graph.json) side by side, then checks the drawing. Returns one JSON "
                        "line: ok, the file paths, a layout outline and any warnings. When ok is false, each error has a "
                        "fix: change the spec or options and call render again. Overwrites files at the same out path. "
                        "Use validate to check an input without drawing, and audit for an SVG this tool did not just draw.",
         "annotations": ann("Draw and audit a figure", False, True),
         "inputSchema": {"type": "object", "required": ["type"],
                         "properties": dict(type={"type": "string", "description": kind},
                                            out={"type": "string", "description": "Output path ending .html (default diagonaldiagrams-out.html). The .svg and the receipt are written beside it."},
                                            options=opts, **src)}},
        {"name": "validate", "title": "Validate a spec",
         "description": "Check an input without drawing anything: a spec, scene or CSV. Returns JSON with ok and, on "
                        "failure, errors that each carry a fix. Read-only, and cheaper than render while you are "
                        "still shaping the spec. For a finished drawing use audit.",
         "annotations": ann("Validate a spec", True, True),
         "inputSchema": {"type": "object", "required": ["type"],
                         "properties": dict(type={"type": "string", "description": kind}, options=opts, **src)}},
        {"name": "audit", "title": "Audit an SVG",
         "description": "Check a finished SVG or HTML figure for what you cannot see in your own output: text over text, "
                        "arrows through boxes, text that spills out of its shape, low contrast, tiny text, and in 3D "
                        "figures text hidden behind a nearer face. Works on any SVG on disk, not only ones this tool drew. "
                        "Returns JSON: ok, errors with a fix, and warnings. Read-only. render already audits its own "
                        "output, so use this after hand edits or on a figure from elsewhere.",
         "annotations": ann("Audit an SVG", True, True),
         "inputSchema": {"type": "object", "required": ["path"],
                         "properties": {"path": {"type": "string", "description": "Path of the .svg or .html figure to check."}}}},
        {"name": "export", "title": "Export a figure to another format",
         "description": "Redraw a rendered figure as png, pdf, svg, drawio or excalidraw. It reads the receipt "
                        "(OUT.graph.json) that render wrote beside the figure, so the figure must have been drawn by "
                        "this tool. Writes the new file next to it, or at out, and returns the path as a line of text. png and "
                        "pdf need cairosvg or headless Edge or Chrome. Overwrites an existing file at the same path.",
         "annotations": ann("Export a figure to another format", False, True),
         "inputSchema": {"type": "object", "required": ["path"],
                         "properties": {"path": {"type": "string", "description": "The figure's base path, or its .html or .svg. OUT.graph.json must sit beside it."},
                                        "to": {"type": "string", "enum": ["png", "pdf", "svg", "drawio", "excalidraw"], "description": "Output format. Default png."},
                                        "layout": {"type": "string", "enum": ["figure", "wide", "slide", "social"], "description": "Page preset for png and pdf: figure (760 px wide, default), wide (1120), slide (1280) or social (1080)."},
                                        "out": {"type": "string", "description": "Where to write the file. Default: beside the figure."}}}},
        {"name": "infer", "title": "Suggest a scatter spec from a CSV",
         "description": "Propose a starting spec for a scatter chart from a CSV. Returns the spec as JSON to edit and "
                        "pass to render. Read-only: it suggests and draws nothing. Only for scatter charts; for other "
                        "charts, describe the type and write the spec yourself.",
         "annotations": ann("Suggest a scatter spec from a CSV", True, True),
         "inputSchema": {"type": "object",
                         "properties": {"data": {"type": "string", "description": "CSV text, inline. Give this or path."},
                                        "path": {"type": "string", "description": "A CSV file on disk. Give this or data."}}}},
        {"name": "apply", "title": "Patch a spec file",
         "description": "Edit a spec file with a patch instead of rewriting it: move or reorder items, rename text, "
                        "change colors, add or remove things, or move them into a group, so a regenerated spec keeps "
                        "the change. Changes the spec file in place and writes the patch beside it (SPEC.patch.json). "
                        "Render the spec to the same out path again; changed in the result says what moved.",
         "annotations": ann("Patch a spec file", False, False, destructive=True),
         "inputSchema": {"type": "object", "required": ["spec", "patch"],
                         "properties": {"spec": {"type": "string", "description": "Path of the spec file to change. It is edited in place."},
                                        "patch": {"description": "A list of operations (place, order, style, text, add, "
                                                                 "remove, move-to-group), or the path of a patch file."}}}},
        {"name": "story", "title": "Build an animated story page",
         "description": "Present one figure as a story: a story file lists views that focus, dim, highlight and reveal "
                        "parts of it, and one HTML page animates between them. Writes OUT.html and returns JSON with "
                        "ok, the path and the views; overwrites an existing page. describe story shows the story file's shape. "
                        "For a plain figure use render.",
         "annotations": ann("Build an animated story page", False, True),
         "inputSchema": {"type": "object", "required": ["story", "out"],
                         "properties": {"story": {"type": "string", "description": "Path of the story file (JSON)."},
                                        "out": {"type": "string", "description": "The page to write, ending .html."}}}},
        {"name": "diff", "title": "Compare two drawings",
         "description": "Say what changed between two drawings of the same figure (.svg or .html): items added, "
                        "removed, renamed, moved, reordered or recolored, as JSON and plain sentences. Read-only. Use it after apply or an "
                        "edit to confirm the change did what you meant.",
         "annotations": ann("Compare two drawings", True, True),
         "inputSchema": {"type": "object", "required": ["old", "new"],
                         "properties": {"old": {"type": "string", "description": "The earlier drawing (.svg or .html)."},
                                        "new": {"type": "string", "description": "The later drawing (.svg or .html)."}}}},
    ]


def do_mcp(args):
    """MCP server over stdio: newline-delimited JSON-RPC, standard library only.
    `render` takes the spec or CSV inline, then validates, draws, and audits in one call.
    Tools return paths and a verdict, never pixels, so a call costs tens of tokens.

    Each call runs in this process (diagonaldiagrams.api.run). --isolate runs each in its own
    process instead, with a 180 s limit."""
    isolate = getattr(args, "isolate", False)
    TOOLS = tools()

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

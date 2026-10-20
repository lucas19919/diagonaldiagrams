#!/usr/bin/env python3
"""Static counts of the engine source, for scripts/metrics.py: truncation calls, inline fonts, side channels.

    py -3 scripts/counts.py            # JSON on stdout
    py -3 scripts/counts.py --md       # a Markdown table

Reads the engine's source with ast; runs nothing. Scans graph.py while it holds the engine,
and the diagonaldiagrams/ package once it exists (a graph.py that only re-exports is skipped).
"""
import argparse
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# What is counted, and why each one should reach zero (or shrink).
TRUNCATORS = {"_short", "_wrap"}          # cut text with an ellipsis instead of wrapping it
FONT_ATTRS = ("font-size=", "font-family=")  # inline font settings in drawing code
SIDE_CHANNEL_SKIP = {"__doc__", "__name__", "__wrapped__"}


def sources():
    """Engine source files: the package if present, else graph.py."""
    pkg = os.path.join(HERE, "diagonaldiagrams")
    files = []
    if os.path.isdir(pkg):
        for root, _, names in os.walk(pkg):
            files += [os.path.join(root, n) for n in sorted(names) if n.endswith(".py")]
    shim = os.path.join(HERE, "graph.py")
    if os.path.exists(shim) and os.path.getsize(shim) > 4000:  # the real engine, not a shim
        files.append(shim)
    return sorted(files)


def _strings(node):
    """Every literal string piece under node, including the fixed parts of f-strings."""
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value


def count_file(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    tree = ast.parse(text, filename=path)
    top_funcs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    out = {
        "lines": text.count("\n") + 1,
        "chart_renderers": sorted(n for n in top_funcs if n.startswith("_c_")),
        "truncation_calls": 0,
        "inline_font_settings": 0,
        "side_channels": set(),
        "system_exits": 0,
    }
    # a module's own `if __name__ == "__main__":` block is its script entry point, not engine code
    script = {id(x) for b in tree.body
              if isinstance(b, ast.If) and isinstance(b.test, ast.Compare)
              and getattr(b.test.left, "id", "") == "__name__" for x in ast.walk(b)}
    for n in ast.walk(tree):
        if id(n) in script:
            continue
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if name in TRUNCATORS:
                out["truncation_calls"] += 1
            if name == "exit" and isinstance(f, ast.Attribute) and getattr(f.value, "id", "") == "sys":
                out["system_exits"] += 1
        elif isinstance(n, ast.Raise) and n.exc is not None:
            exc = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            if isinstance(exc, ast.Name) and exc.id == "SystemExit":
                out["system_exits"] += 1
        elif isinstance(n, (ast.Assign, ast.AugAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in targets:
                # route_edge.last_pts = ... : state smuggled out of a function through an attribute
                if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                        and t.value.id in top_funcs and t.attr not in SIDE_CHANNEL_SKIP):
                    out["side_channels"].add(f"{t.value.id}.{t.attr}")
    for s in _strings(tree):
        out["inline_font_settings"] += sum(s.count(a) for a in FONT_ATTRS)
    return out


def count_all():
    files = sources()
    per = {os.path.relpath(p, HERE).replace(os.sep, "/"): count_file(p) for p in files}
    renderers = sorted({r for v in per.values() for r in v["chart_renderers"]})
    channels = sorted({c for v in per.values() for c in v["side_channels"]})
    biggest = max(per.items(), key=lambda kv: kv[1]["lines"]) if per else ("", {"lines": 0})
    return {
        "files": len(per),
        "total_lines": sum(v["lines"] for v in per.values()),
        "largest_module": {"path": biggest[0], "lines": biggest[1]["lines"]},
        "chart_renderers": len(renderers),
        "truncation_calls": sum(v["truncation_calls"] for v in per.values()),
        "inline_font_settings": sum(v["inline_font_settings"] for v in per.values()),
        "side_channels": len(channels),
        "side_channel_names": channels,
        # the command line may end the process; nothing else should. In the
        # single-file graph.py there was no separate CLI module, so every exit counted.
        "system_exits": sum(v["system_exits"] for k, v in per.items() if not k.endswith("diagonaldiagrams/cli.py")),
    }


def markdown(c):
    rows = [
        ("Engine files", c["files"]),
        ("Total lines", c["total_lines"]),
        ("Largest module", f'{c["largest_module"]["path"]} ({c["largest_module"]["lines"]} lines)'),
        ("`_c_*` chart renderers", c["chart_renderers"]),
        ("Truncation calls (`_short`, `_wrap`)", c["truncation_calls"]),
        ("Inline font settings", c["inline_font_settings"]),
        ("Function-attribute side channels", f'{c["side_channels"]} ({", ".join(c["side_channel_names"])})'),
        ("`SystemExit` / `sys.exit` outside the CLI", c["system_exits"]),
    ]
    return "| Count | Value |\n| --- | --- |\n" + "\n".join(f"| {k} | {v} |" for k, v in rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--md", action="store_true", help="print a Markdown table instead of JSON")
    a = ap.parse_args()
    c = count_all()
    print(markdown(c) if a.md else json.dumps(c, indent=2))


if __name__ == "__main__":
    sys.exit(main())

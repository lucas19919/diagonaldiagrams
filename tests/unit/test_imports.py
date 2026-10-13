"""Import rules (PLAN P2.13, DESIGN 15): the core never reaches the command line, the MCP server,
the API or the writers, not even through another module or an import inside a function.
Run: py -3 -m unittest discover tests/unit"""
import ast
import os
import unittest

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "diagonaldiagrams")

# today's names for DESIGN 15's layers: scene, style (_theme), text (_text), geom, and the display list
CORE = ["scene", "scene.model", "scene.normalize", "scene.ids", "scene.patch", "geom", "_text", "_theme",
        "displaylist", "errors", "sanitize", "style", "style.tokens", "style.parse", "style.select", "style.cascade"]
# emit (_output, export, apply write files), cli, mcp, api, and the process plumbing
FORBIDDEN = {"cli", "mcp", "api", "apply", "export", "_output", "_proc", "__main__"}


def modules():
    out = {}
    for root, _, files in os.walk(PKG):
        for f in files:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, f), PKG)[:-3].replace(os.sep, ".")
                out[rel[:-len(".__init__")] if rel.endswith(".__init__") else ("" if rel == "__init__" else rel)] = os.path.join(root, f)
    return out


def imports(name, path):
    """Package modules this module imports, anywhere in its body (relative or absolute)."""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    package = name if path.endswith("__init__.py") else name.rpartition(".")[0]
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".") if package else []
                base = base[:len(base) - (node.level - 1)] if node.level > 1 else base
                mod = ".".join(base + ([node.module] if node.module else []))
            elif node.module and node.module.startswith("diagonaldiagrams"):
                mod = node.module[len("diagonaldiagrams."):] if node.module != "diagonaldiagrams" else ""
            else:
                continue
            if node.module:
                found.add(mod)
            found.update(f"{mod}.{a.name}" if mod else a.name for a in node.names)  # `from . import paint`: paint
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("diagonaldiagrams."):
                    found.add(a.name[len("diagonaldiagrams."):])
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "lazy" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and str(arg.value).startswith("diagonaldiagrams."):
                found.add(arg.value[len("diagonaldiagrams."):])
    return found


class ImportRules(unittest.TestCase):
    def test_core_never_reaches_the_edges(self):
        mods = modules()
        graph = {m: {i for i in imports(m, p) if i in mods} for m, p in mods.items()}
        for start in CORE:
            self.assertIn(start, mods, f"{start} moved; update CORE")
            seen, todo, via = {start}, [start], {start: None}
            while todo:
                m = todo.pop()
                for n in graph[m]:
                    if n not in seen:
                        seen.add(n)
                        via[n] = m
                        todo.append(n)
            bad = sorted(seen & FORBIDDEN)
            if bad:
                chain, m = [], bad[0]
                while m is not None:
                    chain.append(m)
                    m = via[m]
                self.fail(f"{start} reaches {bad[0]}: {' <- '.join(chain)}")

    def test_the_checker_sees_imports(self):
        """The rule test itself: it finds relative, function-level and lazy() imports."""
        mods = modules()
        self.assertIn("errors", imports("scene.normalize", mods["scene.normalize"]))
        self.assertIn("inputs.v1", imports("apply", mods["apply"]))
        self.assertIn("diagrams", imports("cli", mods["cli"]))


if __name__ == "__main__":
    unittest.main()

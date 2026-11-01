"""The MCP tool list stays documented. Directories such as Glama score tool definitions on
annotations, parameter descriptions and usage guidance, so a tool that loses any of them is a bug.
Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams._output import LAYOUTS  # noqa: E402
from diagonaldiagrams.mcp import tools  # noqa: E402

NAMES = {"describe", "render", "validate", "audit", "export", "infer", "apply", "story", "diff"}


class McpToolDocs(unittest.TestCase):
    def setUp(self):
        self.tools = {t["name"]: t for t in tools()}

    def test_names_are_the_contract(self):
        self.assertEqual(set(self.tools), NAMES)

    def test_every_tool_says_what_it_does(self):
        for name, t in self.tools.items():
            with self.subTest(tool=name):
                self.assertTrue(t.get("title"))
                # long enough to say what comes back and when to use it, short enough to read
                self.assertTrue(120 <= len(t["description"]) <= 800, len(t["description"]))

    def test_every_tool_has_annotations(self):
        for name, t in self.tools.items():
            with self.subTest(tool=name):
                a = t["annotations"]
                self.assertIsInstance(a["readOnlyHint"], bool)
                self.assertIs(a["openWorldHint"], False)
                self.assertIsInstance(a["idempotentHint"], bool)
                if not a["readOnlyHint"]:
                    self.assertIsInstance(a["destructiveHint"], bool)

    def test_tools_that_only_read_say_so(self):
        for name in ("describe", "validate", "audit", "infer", "diff"):
            self.assertTrue(self.tools[name]["annotations"]["readOnlyHint"], name)
        for name in ("render", "export", "apply", "story"):
            self.assertFalse(self.tools[name]["annotations"]["readOnlyHint"], name)

    def test_apply_edits_in_place_so_it_is_destructive(self):
        self.assertTrue(self.tools["apply"]["annotations"]["destructiveHint"])

    def test_every_parameter_has_a_description(self):
        for name, t in self.tools.items():
            props = t["inputSchema"]["properties"]
            for p, spec in props.items():
                with self.subTest(tool=name, param=p):
                    self.assertTrue(spec.get("description"))
            for r in t["inputSchema"].get("required", []):
                self.assertIn(r, props, f"{name} requires {r}, which is not a property")

    def test_export_choices_match_the_command(self):
        props = self.tools["export"]["inputSchema"]["properties"]
        self.assertEqual(set(props["to"]["enum"]), {"png", "pdf", "svg", "drawio", "excalidraw"})
        self.assertEqual(set(props["layout"]["enum"]), set(LAYOUTS))
        for fmt in props["to"]["enum"]:
            self.assertIn(fmt, self.tools["export"]["description"])


if __name__ == "__main__":
    unittest.main()

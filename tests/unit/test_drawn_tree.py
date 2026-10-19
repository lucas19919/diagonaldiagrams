"""A drawing read in memory (paint.Drawing.tree) is what parsing its SVG gives, and the verdict's audit
of it is the file's (audit._audit_drawn against audit._audit_file).
Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.audit import _audit_drawn, _audit_file  # noqa: E402
from diagonaldiagrams.diagrams import render_arch, render_flow  # noqa: E402

ODD = ["tab\there", "line\nbreak", 'amp & <lt> "q" \'a\'', "font-family='x'", "<svg>inner</svg>", "unicode é ✓ 中文",
       "  spaces  ", "-12", " "]


def spec(label):
    return {"title": f"Odd {label}", "sub": label, "caption": label,
            "nodes": [{"id": "a", "name": label}, {"id": "b", "name": "B", "sub": label, "tag": label[:8]},
                      {"id": "c", "name": "C", "shape": "diamond"}],
            "edges": [{"from": "a", "to": "b", "label": label}, {"from": "b", "to": "c", "label": label[:10]}],
            "groups": [{"id": "g", "name": label, "members": ["a", "b"]}]}


def same(a, b, path="svg"):
    """None, or where the two trees first differ."""
    for what in ("tag", "text", "tail"):
        if getattr(a, what) != getattr(b, what):
            return f"{path}: {what} {getattr(a, what)!r} != {getattr(b, what)!r}"
    if dict(a.attrib) != dict(b.attrib):
        return f"{path}: {dict(a.attrib)} != {dict(b.attrib)}"
    if len(list(a)) != len(list(b)):
        return f"{path}: {len(list(a))} children != {len(list(b))}"
    for k, (x, y) in enumerate(zip(a, b)):
        d = same(x, y, f"{path}/{k}")
        if d:
            return d
    return None


class DrawnTree(unittest.TestCase):
    def drawn(self, render, label):
        info = {}
        render(spec(label), info=info)
        return info["drawing"]

    def test_the_tree_is_what_parsing_gives(self):
        for render in (render_flow, render_arch):
            for label in ODD:
                with self.subTest(render=render.__name__, label=label):
                    dr = self.drawn(render, label)
                    root = dr.tree()
                    self.assertIsNotNone(root)
                    self.assertIsNone(same(root, ET.fromstring(dr.written)))
                    self.assertEqual(list(root.itertext()), list(ET.fromstring(dr.written).itertext()))

    def test_the_audit_in_memory_is_the_files(self):
        with tempfile.TemporaryDirectory() as d:
            for k, label in enumerate(ODD):
                with self.subTest(label=label):
                    dr = self.drawn(render_flow, label)
                    path = os.path.join(d, f"f{k}.svg")
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(dr.written)
                    self.assertEqual(_audit_drawn(dr, dr.tree()), _audit_file(path))

    def test_text_a_parser_would_change_is_left_to_the_file(self):
        for label in ("carriage\rreturn", "crlf\r\nline", "bell\x07here"):
            with self.subTest(label=label):
                self.assertIsNone(self.drawn(render_flow, label).tree())


if __name__ == "__main__":
    unittest.main()

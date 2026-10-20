"""Internal registries: shapes, checks and export formats are looked up by name, so
a new one is added without editing the code that uses it. Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import paint  # noqa: E402
from diagonaldiagrams.audit.checks import CHECKS  # noqa: E402
from diagonaldiagrams.diagrams import render_flow  # noqa: E402
from diagonaldiagrams.export import OUTPUTS  # noqa: E402
from diagonaldiagrams.registry import Registry  # noqa: E402


class Registries(unittest.TestCase):
    def test_the_built_ins_are_registered(self):
        self.assertEqual(paint.SHAPES.names(), ["rect", "oval", "diamond", "dot"])
        self.assertEqual(OUTPUTS.names(), ["svg", "drawio", "excalidraw", "png", "pdf"])
        self.assertEqual(CHECKS.names()[0], "text lines")
        self.assertIn("through", CHECKS.meta("arrows through boxes and labels")["codes"])

    def test_a_name_registers_once(self):
        r = Registry("thing")
        r.add("a")(len)
        with self.assertRaises(ValueError):
            r.add("a")(len)

    def test_a_shape_added_from_outside_is_drawn_by_flow(self):
        @paint.SHAPES.add("hexagon")
        def hexagon(t, nid, n, cx, cy, w, h, corners="editorial", st=None):
            pts = [(cx - w / 2, cy), (cx - w / 4, cy - h / 2), (cx + w / 4, cy - h / 2), (cx + w / 2, cy),
                   (cx + w / 4, cy + h / 2), (cx - w / 4, cy + h / 2)]
            return [paint.el("polygon", owner=nid, role="node.shape", points=" ".join(f"{x},{y}" for x, y in pts),
                             fill=t["card"], stroke=t["ink"], data_node=nid, data_label=n["name"]),
                    paint.el("text", n["name"], owner=nid, role="node.label", x=cx, y=cy + 4, text_anchor="middle")]
        try:
            svg = render_flow({"nodes": [{"id": "a", "name": "Plan"}, {"id": "b", "name": "Hex", "shape": "hexagon"}],
                               "edges": [{"from": "a", "to": "b"}]})[0]
        finally:
            paint.SHAPES.remove("hexagon")
        self.assertEqual(svg.count('data-node="b"'), 1)
        self.assertIn("<polygon", svg)
        self.assertNotIn("hexagon", paint.SHAPES)


if __name__ == "__main__":
    unittest.main()

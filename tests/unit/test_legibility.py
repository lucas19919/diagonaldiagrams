"""Legibility checks (PLAN P3.9, DESIGN 9.3): contrast, min-size, colors.
Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.audit import _svg_geometry  # noqa: E402
from diagonaldiagrams.audit.checks import WARNINGS  # noqa: E402
from diagonaldiagrams.diagrams import render_flow  # noqa: E402


def audit(style=None, nodes=None):
    spec = {"nodes": nodes or [{"id": "a", "name": "Alpha", "sub": "first"}, {"id": "b", "name": "Beta"}],
            "edges": [] if nodes else [{"from": "a", "to": "b"}]}
    if style:
        spec["style"] = {"name": "brand", "rules": style}
    svg, w, h = render_flow(spec)
    return [i for i in _svg_geometry(ET.fromstring(svg), w, h) if i["code"] in ("contrast", "min-size", "colors")]


class Contrast(unittest.TestCase):
    def test_defaults_raise_nothing(self):
        self.assertEqual(audit(), [])

    def test_a_low_contrast_rule_is_caught_and_named(self):
        issues = audit({"#a::label": {"color": "#d1d5db"}})
        self.assertEqual([i["code"] for i in issues], ["contrast"])
        self.assertIn("stylesheet 'brand', rule '#a::label'", issues[0]["msg"])
        self.assertIn("1.5:1", issues[0]["msg"])

    def test_the_background_is_the_shape_under_the_text(self):
        self.assertEqual(audit({"#a": {"fill": "#1f2937"}, "#a::label": {"color": "#f9fafb"}}), [])
        self.assertEqual([i["code"] for i in audit({"#a": {"fill": "#1f2937"}, "#a::label": {"color": "#374151"}})],
                         ["contrast"])

    def test_large_text_needs_three_to_one(self):
        grey = "#8a8a8a"  # 3.4:1 on white: enough for large text, not for small
        self.assertEqual(audit({"#b::label": {"color": grey, "font-size": 20}}), [])
        self.assertEqual([i["code"] for i in audit({"#b::label": {"color": grey}})], ["contrast"])


class SizeAndColors(unittest.TestCase):
    def test_small_text_from_a_rule_warns(self):
        issues = audit({"node::sub": {"font-size": 7}})
        self.assertEqual([i["code"] for i in issues], ["min-size"])
        self.assertIn("min-size", WARNINGS)

    def test_more_than_eight_node_colors_warn(self):
        nodes = [{"id": f"n{k}", "name": f"N{k}", "data": {"team": f"t{k}"}} for k in range(10)]
        rules = {"node": {"fill": {"field": "team", "scale": {"type": "categorical",
                                                               "range": ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
                                                                         "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe"]}}}}
        self.assertEqual([i["code"] for i in audit(rules, nodes)], ["colors"])


if __name__ == "__main__":
    unittest.main()

"""Legibility checks (PLAN P3.9, DESIGN 9.3): contrast, min-size, colors.
Run: py -3 -m unittest discover tests/unit"""
import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.audit import _svg_geometry  # noqa: E402
from diagonaldiagrams.audit.checks import WARNINGS  # noqa: E402
from diagonaldiagrams._theme import get_theme  # noqa: E402
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


def judged(body, legibility=None):
    """The legibility issues of a hand-written 200 x 100 figure."""
    mark = f' data-legibility="{legibility}"' if legibility else ""
    svg = f'<svg xmlns="http://www.w3.org/2000/svg"{mark} viewBox="0 0 200 100">{body}</svg>'
    return [i for i in _svg_geometry(ET.fromstring(svg), 200, 100) if i["code"] in ("contrast", "min-size")]


class Translucent(unittest.TestCase):
    """A translucent fill is read over the paint beneath it, not over white (B25: the dark theme's
    focal box, accent-tint at 0.12 on dark paper, read 1.0:1 for its white text)."""
    def test_a_tint_over_dark_paper_is_dark(self):
        body = ('<rect width="200" height="100" fill="#16191d"/>'
                '<rect x="20" y="20" width="160" height="60" fill="rgba(94,166,255,0.12)"/>'
                '<text x="100" y="54" font-size="13" fill="#ffffff" text-anchor="middle" data-color-from="sheet">Risky?</text>')
        self.assertEqual(judged(body), [])

    def test_fill_opacity_counts_too(self):
        body = ('<rect width="200" height="100" fill="#16191d"/>'
                '<rect x="20" y="20" width="160" height="60" fill="#5ea6ff" fill-opacity="0.12"/>'
                '<text x="100" y="54" font-size="13" fill="#16191d" text-anchor="middle" data-color-from="sheet">Risky?</text>')
        issues = judged(body)
        self.assertEqual([i["code"] for i in issues], ["contrast"])
        self.assertIn("#5ea6ff at 0.12 over #16191d", issues[0]["msg"])

    def test_the_dark_theme_focal_box_passes(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "examples", "flow_decision.json")
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
        svg, w, h = render_flow(spec, theme=get_theme("ink"))
        self.assertIn('data-legibility="all"', svg)
        self.assertEqual([i for i in _svg_geometry(ET.fromstring(svg), w, h) if i["code"] in ("contrast", "min-size")], [])


class Defaults(unittest.TestCase):
    """flow, arch, seq and schema write data-legibility="all", so their default text is judged too.
    Elsewhere (the chart kinds) only text a stylesheet styled is (B25)."""
    BODY = '<text x="20" y="50" font-size="7" fill="#d1d5db">faint</text>'

    def test_unmarked_default_text_is_not_judged(self):
        self.assertEqual(judged(self.BODY), [])

    def test_marked_default_text_is_judged(self):
        issues = judged(self.BODY, "all")
        self.assertEqual([i["code"] for i in issues], ["contrast", "min-size"])
        self.assertIn("the theme's default", issues[0]["msg"])
        self.assertIn("the preset's default", issues[1]["msg"])

    def test_default_text_reads_on_a_mid_tone_fill(self):
        # neither ink nor paper reaches 4.5:1 on these; black or white does
        self.assertEqual(audit({"#a": {"fill": "#e6194b"}, "#b": {"fill": "#f032e6"}}), [])

    def test_the_four_presets_write_the_marker(self):
        svg, _, _ = render_flow({"nodes": [{"id": "a", "name": "Alpha"}]})
        self.assertEqual(ET.fromstring(svg).get("data-legibility"), "all")


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

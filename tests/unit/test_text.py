"""Text layout (PLAN P3.6, DESIGN 6.2): markup, wrapping, overflow, boxes that grow.
Run: py -3 -m unittest discover tests/unit"""
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams._text import _wrap_px  # noqa: E402
from diagonaldiagrams.audit import _svg_geometry  # noqa: E402
from diagonaldiagrams.diagrams import render_flow, render_seq  # noqa: E402
from diagonaldiagrams.text import markup, measure  # noqa: E402

LONG = "Reconcile the settlement batch with the bank statement and escalate any mismatch to finance"
NS = "{http://www.w3.org/2000/svg}"


class Markup(unittest.TestCase):
    def test_runs_and_plain(self):
        self.assertEqual(markup.runs("Ship **now** via `deploy`, then _verify_"),
                         [("Ship ", ""), ("now", "b"), (" via ", ""), ("deploy", "m"), (", then ", ""), ("verify", "i")])
        self.assertEqual(markup.plain("a **b** `c` _d_"), "a b c d")

    def test_underscores_inside_words_are_literal(self):
        for text in ("user_id", "created_at", "snake_case_name", "a_b_c"):
            self.assertEqual(markup.runs(text), [(text, "")], text)


class Wrapping(unittest.TestCase):
    def test_plain_text_wraps_as_it_always_has_but_is_never_cut(self):
        lines, size = measure.wrap(LONG, 144, 12, True)
        self.assertEqual(["".join(t for t, _ in ln) for ln in lines], _wrap_px(LONG, 144, 12, True, 99))
        self.assertGreater(len(lines), 3)
        self.assertEqual(size, 12)

    def test_shrink_and_ellipsis(self):
        lines, size = measure.wrap(LONG, 144, 12, True, max_lines=3, overflow="shrink")
        self.assertLess(size, 12)
        self.assertGreaterEqual(size, measure.MIN_SIZE)
        lines, _ = measure.wrap(LONG, 144, 12, True, max_lines=2, overflow="ellipsis")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1][-1][0].endswith("..."))


def box(svg, nid):
    return [ln for ln in svg.splitlines() if f'data-node="{nid}"' in ln][0]


class Boxes(unittest.TestCase):
    def test_a_long_name_grows_its_box(self):
        svg = render_flow({"nodes": [{"id": "a", "name": "Short"}, {"id": "b", "name": LONG}], "edges": [{"from": "a", "to": "b"}]})[0]
        h = lambda nid: float(re.search(r'height="([\d.]+)"', box(svg, nid)).group(1))  # noqa: E731
        self.assertEqual(h("a"), 56)
        self.assertGreater(h("b"), 56)
        self.assertNotIn("...", svg)

    def test_a_bigger_font_grows_the_box_and_the_lines_follow_it(self):
        spec = {"nodes": [{"id": "a", "name": "Payment provider integration"}], "edges": [],
                "style": {"rules": {"node::label": {"font-size": 18}}}}
        svg = render_flow(spec)[0]
        lines = [ln for ln in svg.splitlines() if 'role="node.label"' in ln or ('font-size="18"' in ln and "<text" in ln)]
        self.assertGreaterEqual(len(lines), 2)
        ys = [float(re.search(r' y="([\d.]+)"', ln).group(1)) for ln in lines]
        self.assertAlmostEqual(ys[1] - ys[0], 22.5, delta=0.11)  # 18 px at the 1.25 line height; y is rounded to 0.1

    def test_markup_draws_tspans_and_names_stay_plain(self):
        svg = render_flow({"nodes": [{"id": "a", "name": "Ship **now**"}], "edges": []})[0]
        self.assertIn('<tspan font-weight="700">now</tspan>', svg)
        self.assertIn('data-label="Ship now"', svg)
        self.assertIn('aria-label="Ship now"', svg)

    def test_an_ellipsis_warns(self):
        spec = {"nodes": [{"id": "a", "name": LONG}], "edges": [],
                "style": {"rules": {"node::label": {"overflow": "ellipsis", "max-lines": 2}}}}
        svg, w, h = render_flow(spec)
        codes = [i["code"] for i in _svg_geometry(ET.fromstring(svg), w, h)]
        self.assertIn("truncated", codes)

    def test_sequence_actors_grow_together(self):
        spec = {"actors": [{"id": "u", "name": "User"}, {"id": "api", "name": LONG}],
                "messages": [{"from": "u", "to": "api", "label": "call"}]}
        root = ET.fromstring(render_seq(spec)[0])
        heights = {float(e.get("height")) for e in root if e.get("data-node") is not None}
        self.assertEqual(len(heights), 1)
        self.assertGreater(heights.pop(), 52)


if __name__ == "__main__":
    unittest.main()

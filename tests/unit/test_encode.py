"""Encodings, scales and legends. Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import paint  # noqa: E402
from diagonaldiagrams.diagrams import render_arch, render_flow  # noqa: E402
from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.style.encode import Scale  # noqa: E402
from diagonaldiagrams.style.parse import color, contrast  # noqa: E402
from diagonaldiagrams.style.styler import Styler  # noqa: E402
from diagonaldiagrams.style.tokens import tokens  # noqa: E402

TOK = tokens("editorial")


class Scales(unittest.TestCase):
    def test_types_are_inferred(self):
        self.assertEqual(Scale("fill", {"field": "p"}, [1, 5, 9], TOK).type, "sequential")
        self.assertEqual(Scale("fill", {"field": "t"}, ["pay", "data"], TOK).type, "categorical")
        self.assertEqual(Scale("stroke-width", {"field": "r"}, [1, 9], TOK).type, "linear")

    def test_sequential_reads_the_data_extent_and_clamps(self):
        s = Scale("fill", {"field": "p", "scale": {"scheme": "greys"}}, [0, 100, None], TOK)
        self.assertEqual((s.domain, s(0).css, s(100).css, s(500).css), ([0.0, 100.0], "#f7f7f7", "#252525", "#252525"))
        self.assertEqual(s(None).css, "#e5e7eb")  # no value: the neutral grey

    def test_categorical_cycles_the_palette_in_first_seen_order(self):
        s = Scale("fill", {"field": "team"}, ["pay", "data", "pay"], TOK)
        self.assertEqual([s("pay").css, s("data").css], TOK["categorical"][:2])
        self.assertEqual(s.legend()[0][0], "pay")

    def test_linear_range(self):
        s = Scale("stroke-width", {"field": "rps", "scale": {"domain": [0, 100], "range": [1, 5]}}, [], TOK)
        self.assertEqual([s(0), s(50), s(100), s(None)], [1.0, 3.0, 5.0, 1.0])

    def test_an_unknown_scheme_lists_the_known_ones(self):
        with self.assertRaises(SpecError) as cm:
            Scale("fill", {"field": "p", "scale": {"scheme": "rainbow"}}, [1, 2], TOK)
        self.assertIn("heat", cm.exception.fix)


SPEC = {"nodes": [{"id": "a", "name": "A", "data": {"p99": 10, "team": "pay"}},
                  {"id": "b", "name": "B", "data": {"p99": 400}}, {"id": "c", "name": "C"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
        "style": {"rules": {"node": {"fill": {"field": "p99", "scale": {"scheme": "heat"}}},
                            "node[team=pay]": {"border-left": "4px solid #e11d48", "legend": "Payments team"}}}}


class InTheDrawing(unittest.TestCase):
    def test_each_node_reads_its_own_value(self):
        sty = Styler(SPEC, "flow")
        self.assertEqual([sty.node(n)["fill"] for n in "abc"], ["#fff5eb", "#7f2704", "#e5e7eb"])

    def test_the_legend_lists_the_scale_and_the_rule_once(self):
        entries = Styler(SPEC, "flow").legend_entries()
        self.assertEqual([e["type"] for e in entries], ["scale", "rule"])
        self.assertEqual((entries[0]["field"], len(entries[0]["steps"])), ("p99", 3))
        self.assertEqual((entries[1]["text"], entries[1]["look"]), ("Payments team", {"border": "#e11d48", "side": "left"}))

    def test_the_canvas_grows_for_the_legend_rows(self):
        plain = render_flow({k: v for k, v in SPEC.items() if k != "style"})
        styled = render_flow(SPEC)
        self.assertEqual(styled[2] - plain[2], paint.LEGEND_ROW)
        self.assertIn(">Payments team<", styled[0])

    def test_legend_rows_wrap(self):
        entries = [{"type": "rule", "text": f"Team number {k}", "kind": "node", "look": {"fill": "#ccc"}} for k in range(6)]
        _, wide = paint.legend_rows(TOK_V1, entries, 30, 0, 2000)
        _, narrow = paint.legend_rows(TOK_V1, entries, 30, 0, 300)
        self.assertEqual(wide, paint.LEGEND_ROW)
        self.assertGreater(narrow, paint.LEGEND_ROW)


TOK_V1 = {"muted": "#4f5d75", "soft": "#7a8399"}


class Readable(unittest.TestCase):
    def test_a_default_label_on_a_dark_fill_turns_light_and_a_chosen_color_stays(self):
        spec = dict(SPEC, style={"rules": {"node": {"fill": {"field": "p99", "scale": {"scheme": "heat"}}},
                                           "#c::label": {"color": "#eeeeee"}}})
        sty = Styler(spec, "flow")
        self.assertEqual(sty.node("a")["label"]["color"], "#2d3142")  # ink on a light fill
        self.assertEqual(sty.node("b")["label"]["color"], "#f5f5f5")  # paper on the dark one
        self.assertEqual(sty.node("c")["label"]["color"], "#eeeeee")  # the sheet's choice; the contrast check judges it

    def test_contrast(self):
        self.assertAlmostEqual(contrast(color("#000"), color("#fff")), 21.0)
        self.assertAlmostEqual(contrast(color("#777"), color("#777")), 1.0)
        tint = color("rgba(235,108,54,0.08)")  # laid over white before comparing
        self.assertGreater(contrast(color("#2d3142"), tint), 10)


class Sentences(unittest.TestCase):
    def test_a_legend_names_only_what_the_figure_has(self):
        svg = render_flow({"nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], "edges": [{"from": "a", "to": "b"}]})[0]
        self.assertIn(">box = step<", svg)
        self.assertNotIn("diamond = decision", svg)

    def test_colors_are_named_as_drawn(self):
        from diagonaldiagrams._theme import get_theme
        spec = {"nodes": [{"id": "a", "name": "A", "focal": True}, {"id": "b", "name": "B", "layer": 1}],
                "edges": [{"from": "a", "to": "b", "proto": "https"}]}
        self.assertIn("blue = HTTP call, coral = highlighted", render_arch(spec)[0])
        self.assertIn("dark grey = HTTP call, black = highlighted", render_arch(spec, theme=get_theme("print"))[0])
        branded = dict(spec, style={"tokens": {"accent": "#7c3aed", "link": "#0e7490"}})
        self.assertIn("teal = HTTP call, purple = highlighted", render_arch(branded)[0])


if __name__ == "__main__":
    unittest.main()

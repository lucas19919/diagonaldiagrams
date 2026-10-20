"""Style values. Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.style import parse  # noqa: E402
from diagonaldiagrams.style.tokens import tokens  # noqa: E402

TOK = tokens("editorial")


def rgba(c):
    return tuple(round(v, 3) for v in (c.r, c.g, c.b, c.a))


class Colors(unittest.TestCase):
    def test_every_form(self):
        cases = {"#2e5aa8": (46, 90, 168, 1), "#25a": (34, 85, 170, 1), "#2e5aa880": (46, 90, 168, 0.502),
                 "rgb(46, 90, 168)": (46, 90, 168, 1), "rgba(46,90,168,0.5)": (46, 90, 168, 0.5),
                 "rgb(46 90 168 / 50%)": (46, 90, 168, 0.5), "rgb(100%, 0%, 0%)": (255, 0, 0, 1),
                 "hsl(0, 100%, 50%)": (255, 0, 0, 1), "hsla(120deg, 100%, 25%, 0.5)": (0, 127.5, 0, 0.5),
                 "steelblue": (70, 130, 180, 1), "SteelBlue": (70, 130, 180, 1), "transparent": (0, 0, 0, 0)}
        for text, want in cases.items():
            self.assertEqual(rgba(parse.color(text)), tuple(round(v, 3) for v in want), text)

    def test_written_text_is_kept(self):
        self.assertEqual(parse.color("rgba(235,108,54,0.08)").css, "rgba(235,108,54,0.08)")
        self.assertEqual(parse.color("accent", TOK).css, "#eb6c36")  # a token writes its value
        self.assertEqual(parse.color("var(--accent-tint)", TOK).css, "rgba(235,108,54,0.08)")
        self.assertEqual(parse.color("accent_tint", TOK).css, "rgba(235,108,54,0.08)")

    def test_mix(self):
        c = parse.color("mix(#000000, white, 25%)")
        self.assertEqual((c.css, rgba(c)), ("#404040", (63.75, 63.75, 63.75, 1)))
        self.assertEqual(parse.color("mix(accent, paper, 50%)", TOK).css, "#f0b196")

    def test_errors_suggest(self):
        with self.assertRaises(SpecError) as cm:
            parse.color("steelblu", TOK)
        self.assertIn("did you mean 'steelblue'", cm.exception.msg)
        with self.assertRaises(SpecError) as cm:
            parse.color("acent", TOK)
        self.assertIn("did you mean 'accent'", cm.exception.msg)
        for bad in ("#12345", "rgb(1,2)", "mix(red, blue)", ""):
            with self.assertRaises(SpecError):
                parse.color(bad, TOK)

    def test_luminance(self):
        self.assertAlmostEqual(parse.color("white").luminance(), 1.0)
        self.assertAlmostEqual(parse.color("black").luminance(), 0.0)


class Lengths(unittest.TestCase):
    def test_px_and_em(self):
        self.assertEqual([parse.length(v, 10) for v in (3, 2.5, "4", "4px", "1.5em")], [3.0, 2.5, 4.0, 4.0, 15.0])
        with self.assertRaises(SpecError):
            parse.length("1.5em")
        with self.assertRaises(SpecError):
            parse.length("wide")

    def test_one_to_four_values(self):
        self.assertEqual(parse.box4("8"), (8, 8, 8, 8))
        self.assertEqual(parse.box4("8 12"), (8, 12, 8, 12))
        self.assertEqual(parse.box4("8 12 4"), (8, 12, 4, 12))
        self.assertEqual(parse.radius("1 2 3 4"), (1, 2, 3, 4))
        with self.assertRaises(SpecError):
            parse.radius("1 2 3 4 5")


class Shorthands(unittest.TestCase):
    def test_border_in_any_order(self):
        b = parse.border("3px solid accent", TOK)
        self.assertEqual((b["width"], b["style"], b["color"].css), (3.0, "solid", "#eb6c36"))
        b = parse.border("dashed #e11d48 2", TOK)
        self.assertEqual((b["width"], b["style"], b["color"].css), (2.0, "dashed", "#e11d48"))
        self.assertEqual(parse.border("none")["width"], 0.0)

    def test_shadows(self):
        s = parse.shadows("0 2px 6px rgba(0,0,0,0.15), inset 1 1 red")
        self.assertEqual([(x["x"], x["y"], x["blur"], x["inset"]) for x in s], [(0, 2, 6, False), (1, 1, 0, True)])
        self.assertEqual(parse.shadows("none"), [])
        with self.assertRaises(SpecError):
            parse.shadows("red")

    def test_font(self):
        self.assertEqual(parse.font("italic 600 13px/1.4 IBM Plex Sans"),
                         {"font-size": 13.0, "font-family": "IBM Plex Sans", "font-style": "italic", "font-weight": "600",
                          "line-height": 1.4})

    def test_gradient(self):
        g = parse.gradient("linear-gradient(to right, #fff, accent 80%)", TOK)
        self.assertEqual((g["angle"], [(a, c.css) for a, c in g["stops"]]), (90.0, [(0.0, "#fff"), (0.8, "#eb6c36")]))
        self.assertEqual(parse.paint("linear-gradient(#fff, #000)")["angle"], 180.0)


class Properties(unittest.TestCase):
    def test_known_properties_read_their_kind(self):
        self.assertEqual(parse.value("border-style", "Dashed"), "dashed")
        self.assertEqual(parse.value("stroke-width", "2px"), 2.0)
        self.assertEqual(parse.value("fill", "accent", TOK).css, "#eb6c36")
        self.assertEqual(parse.value("stroke-dasharray", "4 2"), [4.0, 2.0])
        enc = {"field": "p99", "scale": {"type": "linear"}}
        self.assertIs(parse.value("fill", enc), enc)  # encodings are read against data later

    def test_unknown_property_and_value_suggest(self):
        with self.assertRaises(SpecError) as cm:
            parse.value("border-tpo", "1px solid red")
        self.assertIn("did you mean 'border-top'", cm.exception.msg)
        with self.assertRaises(SpecError) as cm:
            parse.value("border-style", "dashd")
        self.assertIn("did you mean 'dashed'", cm.exception.msg)
        self.assertEqual(cm.exception.code, "bad-style")

    def test_design_property_table_is_covered(self):
        for prop in ("shape", "padding", "background", "border-left", "border-radius", "box-shadow", "glow", "pattern",
                     "sketch", "font-family", "max-lines", "overflow", "label-position", "marker-end", "router",
                     "corner-radius", "icon-color", "title-align", "legend-position"):
            self.assertIn(prop, parse.PROPERTIES, prop)


if __name__ == "__main__":
    unittest.main()

"""bar and line: tick labels, the percent axis, reference lines, the key, and series colors (plots.py).
Run: py -3 -m unittest discover tests/unit"""
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams._draw import tick_labels  # noqa: E402
from diagonaldiagrams._theme import OKABE_ITO, THEME, series_palette  # noqa: E402
from diagonaldiagrams.plots import render_bar, render_line  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"


def _texts(svg, role=None):
    root = ET.fromstring(svg)
    return [el.text for el in root.iter(SVG + "text") if role is None or el.get("data-role") == role]


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def csv(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path


class TickLabels(unittest.TestCase):
    def test_thousands_once_the_axis_reaches_ten_thousand(self):
        self.assertEqual(tick_labels([0, 5000, 10000, 15000, 20000]), ["0", "5k", "10k", "15k", "20k"])

    def test_commas_below_ten_thousand(self):
        self.assertEqual(tick_labels([0, 1000, 2500]), ["0", "1,000", "2,500"])

    def test_percent_on_each(self):
        self.assertEqual(tick_labels([0, 50, 100], "%"), ["0%", "50%", "100%"])


class Palette(unittest.TestCase):
    def test_reserve_leaves_out_colors_near_the_accent(self):
        pal = series_palette(THEME, reserve=True)
        self.assertNotIn("#E69F00", pal)  # the orange beside a coral accent
        self.assertNotIn("#D55E00", pal)
        self.assertEqual(pal[:2], ["#0072B2", "#009E73"])

    def test_without_a_highlight_or_reserve_the_palette_is_whole(self):
        self.assertEqual(series_palette(THEME), OKABE_ITO)


class Bar(Case):
    QUALITY = "figure,against,clearer\nSlide,vs Pele,85\nSlide,vs Mermaid,97\nArch,vs Pele,0\nArch,vs Mermaid,50\n"

    def test_percent_axis_ends_at_100(self):
        path = self.csv("q.csv", self.QUALITY)
        svg, *_ = render_bar(path, "figure", "clearer", "Q", groupcol="against", orientation="h", unit="%")
        texts = _texts(svg)
        self.assertIn("100%", texts)
        self.assertNotIn("120%", texts)
        self.assertIn("85%", texts)  # no space before a percent

    def test_reference_line_is_dashed_and_labelled(self):
        path = self.csv("q.csv", self.QUALITY)
        svg, *_ = render_bar(path, "figure", "clearer", "Q", groupcol="against", orientation="h", unit="%",
                             refs=[{"at": "50", "text": "even"}])
        root = ET.fromstring(svg)
        dashed = [el for el in root.iter(SVG + "line") if el.get("stroke-dasharray")]
        self.assertEqual(len(dashed), 1)
        self.assertEqual(dashed[0].get("x1"), dashed[0].get("x2"))  # across horizontal bars, a vertical line
        self.assertIn("even", _texts(svg))

    def test_key_follows_the_drawing_order(self):
        path = self.csv("q.csv", self.QUALITY)
        svg, *_ = render_bar(path, "figure", "clearer", "Q", groupcol="against", orientation="h", unit="%")
        self.assertEqual(_texts(svg, "series"), ["vs Pele", "vs Mermaid"])

    def test_no_key_when_it_only_repeats_the_categories(self):
        path = self.csv("s.csv", "tool,ms\nours,152\nPele,101\nMermaid CLI,2340\n")
        svg, *_ = render_bar(path, "tool", "ms", "S", groupcol="tool", orientation="h", unit="ms", highlights=["ours"])
        self.assertEqual(_texts(svg, "series"), [])
        self.assertIn("152 ms", _texts(svg))

    def test_value_title_sits_above_vertical_bars(self):
        path = self.csv("v.csv", "service,ms\na,10\nb,20\n")
        svg, *_ = render_bar(path, "service", "ms", "V", unit="ms")
        root = ET.fromstring(svg)
        title = next(el for el in root.iter(SVG + "text") if el.get("data-role") == "yaxis")
        self.assertIsNone(title.get("transform"))  # horizontal, not rotated
        rules = [float(el.get("y1")) for el in root.iter(SVG + "line") if el.get("y1") == el.get("y2")]
        self.assertLess(float(title.get("y")), min(rules))


class Line(Case):
    def test_a_few_x_values_each_get_a_tick(self):
        path = self.csv("t.csv", "steps,tokens\n5,4400\n11,6000\n20,5100\n40,6400\n")
        svg, *_ = render_line(path, "steps", "tokens", "T")
        for value in ("5", "11", "20", "40"):
            self.assertIn(value, _texts(svg))
        self.assertNotIn("30", _texts(svg))

    def test_reference_line(self):
        path = self.csv("t.csv", "x,y\n1,10\n2,30\n")
        svg, *_ = render_line(path, "x", "y", "T", refs=[{"at": 20, "text": "target"}])
        root = ET.fromstring(svg)
        dashed = [el for el in root.iter(SVG + "line") if el.get("stroke-dasharray")]
        self.assertEqual(len(dashed), 1)
        self.assertEqual(dashed[0].get("y1"), dashed[0].get("y2"))
        self.assertIn("target", _texts(svg))


if __name__ == "__main__":
    unittest.main()

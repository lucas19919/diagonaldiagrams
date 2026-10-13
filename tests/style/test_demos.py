"""The P3 exit suite (docs/PLAN.md, P3): seven style demos, each a stylesheet and nothing else, drawn on
flow, arch, seq and schema through the command line. Every demo passes the audit, except the low-
contrast one, which the contrast check must catch and name. Run: py -3 -m unittest discover tests/style
"""
import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests", "unit"))

from diagonaldiagrams import api  # noqa: E402
from test_fonts import make_font  # noqa: E402

NS = "{http://www.w3.org/2000/svg}"
EXAMPLES = {"flow": "flow_decision.json", "arch": "checkout_platform.json", "seq": "seq_checkout.json",
            "schema": "schema_ecommerce.json"}
NODES = {"flow": "nodes", "arch": "nodes", "seq": "actors", "schema": "tables"}
EDGES = {"flow": "edges", "arch": "edges", "seq": "messages", "schema": "relations"}
OUT = tempfile.mkdtemp(prefix="dd-style-demos-")


def spec_for(kind):
    """The example spec with data for the demos' selectors: the first two parts are the payments
    team, and every part has a p99. The first edge is critical. Generic: nothing per type."""
    with open(os.path.join(REPO, "examples", EXAMPLES[kind]), encoding="utf-8") as f:
        spec = json.load(f)
    for k, n in enumerate(spec[NODES[kind]]):
        n["data"] = dict(n.get("data") or {}, p99=40 + 90 * k, **({"team": "pay"} if k < 2 else {}))
    spec[EDGES[kind]][0]["class"] = "critical"
    return spec


def draw(kind, sheet, name, **options):
    spec = spec_for(kind)
    spec["style"] = sheet
    v = api.render(kind, spec=spec, out=os.path.join(OUT, f"{name}-{kind}.html"), **options)
    svg = ""
    if v.get("svg") and os.path.exists(v["svg"]):
        with open(v["svg"], encoding="utf-8") as f:
            svg = f.read()
    return v, svg


class Demos(unittest.TestCase):
    def each(self, sheet, name, check, **options):
        for kind in EXAMPLES:
            with self.subTest(kind=kind):
                v, svg = draw(kind, sheet, name, **options)
                self.assertTrue(v["ok"], (kind, v.get("errors")))
                check(kind, svg, v)

    def test_1_a_font_measured_from_its_file_wraps(self):
        path = os.path.join(OUT, "wide.ttf")
        with open(path, "wb") as f:  # a very wide face: the estimate would fit lines this font can't
            f.write(make_font({c: 760 for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 :-?._/"},
                              family="Wide Demo"))
        from diagonaldiagrams.text.fonts import load
        font = load(path)

        def check(kind, svg, v):
            root = ET.fromstring(svg)
            labels = [e for e in root.iter(NS + "text") if (e.get("font-family") or "").startswith("'Wide Demo'")]
            self.assertTrue(labels, kind)
            for e in labels:
                boxed = e.get("font-weight") == "600" and e.get("text-anchor") == "middle"  # a box's name, not the title
                if boxed and kind in ("flow", "arch"):  # inside the 144 px a box's text wraps to
                    self.assertLessEqual(font.width(e.text, float(e.get("font-size"))), 144.5, (kind, e.text))
        self.each({"name": "demo"}, "font", check, font=path)

    def test_2_a_brand_restyles_every_type_through_tokens(self):
        brand = {"name": "brand", "tokens": {"ink": "#0f172a", "accent": "#7c3aed", "link": "#0e7490", "card": "#f8fafc"}}
        self.each(brand, "brand", lambda kind, svg, v: self.assertTrue(
            'fill="#f8fafc"' in svg and 'stroke="#0f172a"' in svg, kind))

    def test_3_a_top_border_on_every_shape(self):
        def check(kind, svg, v):
            self.assertGreaterEqual(svg.count('stroke-width="3"'), 2, kind)
        self.each({"name": "tops", "rules": {"node": {"border-top": "3px solid accent"}}}, "tops", check)
        v, svg = draw("flow", {"name": "tops", "rules": {"node": {"border-top": "3px solid accent"}}}, "tops-shapes")
        shapes = re.findall(r'data-node="[^"]+" data-label="[^"]*"', svg)
        self.assertGreaterEqual(svg.count('stroke-width="3"'), len(shapes))  # rect, oval and diamond alike

    def test_4_a_team_gets_a_left_bar(self):
        sheet = {"name": "teams", "rules": {"node[team=pay]": {"border-left": "4px solid #e11d48", "legend": "Payments team"}}}
        self.each(sheet, "teams", lambda kind, svg, v: self.assertTrue(
            svg.count('stroke="#e11d48" stroke-width="4"') >= 2 and ">Payments team<" in svg, kind))

    def test_5_critical_and_from_edges_are_highlighted(self):
        def check(kind, svg, v):
            self.assertIn('stroke="#e11d48" stroke-width="3"', svg, kind)  # edge.critical
            spec = spec_for(kind)
            src = spec[EDGES[kind]][-1]["from"]
            self.assertTrue(re.search(rf'stroke="#7c3aed"[^>]*data-from="{re.escape(str(src))}"', svg) or kind == "seq", kind)
        for kind in EXAMPLES:
            spec = spec_for(kind)
            src = spec[EDGES[kind]][-1]["from"]
            sheet = {"name": "edges", "rules": {"edge.critical": {"stroke": "#e11d48", "stroke-width": 3},
                                                f"edge[from={src}]": {"stroke": "#7c3aed"}}}
            with self.subTest(kind=kind):
                v, svg = draw(kind, sheet, "edges")
                self.assertTrue(v["ok"], (kind, v.get("errors")))
                check(kind, svg, v)

    def test_6_a_data_driven_fill_with_its_legend(self):
        sheet = {"name": "heat", "rules": {"node": {"fill": {"field": "p99", "scale": {"scheme": "heat"}}}}}

        def check(kind, svg, v):
            fills = set(re.findall(r'fill="(#[0-9a-f]{6})"[^>]*data-node=', svg))
            self.assertGreaterEqual(len(fills), 3, kind)
            self.assertIn(">p99:<", svg, kind)
        self.each(sheet, "heat", check)

    def test_7_low_contrast_is_caught_and_named(self):
        sheet = {"name": "faint", "rules": {"node::label": {"color": "#d1d5db"}}}
        for kind in EXAMPLES:
            with self.subTest(kind=kind):
                v, _ = draw(kind, sheet, "faint")
                self.assertFalse(v["ok"], kind)
                contrast = [e for e in v.get("errors", []) if e.get("code") == "contrast"]
                self.assertTrue(contrast and "stylesheet 'faint', rule 'node::label'" in contrast[0]["msg"], (kind, v))


if __name__ == "__main__":
    unittest.main()

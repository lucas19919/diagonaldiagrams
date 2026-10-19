"""The four diagram types paint from the cascade: one stylesheet restyles them all.
Run: py -3 -m unittest discover tests/unit"""
import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from diagonaldiagrams.diagrams import render_arch, render_flow, render_schema, render_seq  # noqa: E402

NS = "{http://www.w3.org/2000/svg}"
BRAND = {"name": "brand", "tokens": {"accent": "#7c3aed", "link": "#0e7490"},
         "rules": {"node": {"fill": "#f8fafc", "stroke": "#334155", "stroke-width": 2},
                   "node::label": {"font-family": "Georgia, serif", "color": "#0f172a"},
                   "edge": {"stroke": "#64748b", "stroke-width": 2.5},
                   "edge::label": {"text-transform": "none"}}}
SPECS = {"flow": ("flow_decision.json", render_flow), "arch": ("checkout_platform.json", render_arch),
         "seq": ("seq_checkout.json", render_seq), "schema": ("schema_ecommerce.json", render_schema)}


def draw(kind, style=None):
    name, fn = SPECS[kind]
    with open(os.path.join(REPO, "examples", name), encoding="utf-8") as f:
        spec = json.load(f)
    if style:
        spec["style"] = style
    return ET.fromstring(fn(spec)[0])


class OneSheetEveryType(unittest.TestCase):
    def test_the_brand_reaches_every_type(self):
        for kind in SPECS:
            root = draw(kind, BRAND)
            shapes = [e for e in root if e.get("data-node") is not None]
            self.assertTrue(shapes and all(e.get("stroke") == "#334155" and e.get("stroke-width") == "2" for e in shapes
                                           if e.get("stroke") != "#7c3aed"), kind)  # focal parts keep the accent
            labels = [e for e in root.iter(NS + "text") if e.get("font-family") == "Georgia, serif"]
            self.assertTrue(labels, kind)
            arrows = [e for e in root if e.get("role") == "graphics-symbol" and e.get("aria-roledescription") in
                      ("arrow", "message", "relation")]
            self.assertTrue(arrows and all(e.get("stroke-width") == "2.5" for e in arrows), kind)

    def test_tokens_restyle_what_the_preset_ties_to_them(self):
        root = draw("arch", BRAND)
        http = [e for e in root if e.get("data-from") is not None and e.get("stroke") == "#0e7490"]
        self.assertFalse(http)  # the brand's edge rule is later than the preset's http rule, so it wins
        root = draw("arch", {"tokens": {"link": "#0e7490"}})
        self.assertTrue([e for e in root if e.get("data-from") is not None and e.get("stroke") == "#0e7490"])

    def test_a_new_stroke_color_gets_its_own_arrowhead(self):
        root = draw("flow", {"rules": {"edge": {"stroke": "#e11d48"}}})
        marker = [m for m in root.iter(NS + "marker") if m.get("id") == "m1"]
        self.assertEqual(marker[0][0].get("fill"), "#e11d48")
        self.assertTrue(all(e.get("marker-end") == "url(#m1)" for e in root if e.get("data-from") is not None))

    def test_a_bad_rule_is_an_error_before_drawing(self):
        from diagonaldiagrams.errors import SpecError
        with self.assertRaises(SpecError) as cm:
            draw("seq", {"rules": {"node": {"stroke": "acent"}}})
        self.assertIn("did you mean 'accent'", cm.exception.msg)



class FigureParts(unittest.TestCase):
    def test_title_legend_groups_notes_and_paper_follow_the_sheet(self):
        spec = {"title": "Checkout", "sub": "one line", "notes": [{"at": "b", "text": "rate limited"}],
                "nodes": [{"id": "a", "name": "A", "group": "core"}, {"id": "b", "name": "B", "group": "core"}],
                "edges": [{"from": "a", "to": "b"}],
                "style": {"tokens": {"font": "Georgia, serif"},
                          "rules": {"figure": {"fill": "#fffbeb"}, "figure::title": {"color": "#7c3aed"},
                                    "legend": {"color": "#0e7490"}, "group": {"stroke": "#e11d48", "border-radius": 2},
                                    "group::title": {"color": "#e11d48"}, "annotation": {"color": "#b45309"}}}}
        root = ET.fromstring(render_flow(spec)[0])
        texts = {e.text: e for e in root.iter(NS + "text")}
        self.assertEqual(texts["Checkout"].get("fill"), "#7c3aed")
        self.assertEqual(texts["Checkout"].get("font-family"), "Georgia, serif")  # the font token reaches the title
        self.assertEqual(texts["CORE"].get("fill"), "#e11d48")
        self.assertEqual(texts["rate limited"].get("fill"), "#b45309")
        self.assertEqual(texts["box = step"].get("fill"), "#0e7490")
        rects = list(root.iter(NS + "rect"))
        self.assertEqual(rects[0].get("fill"), "#fffbeb")  # the paper
        frame = [r for r in rects if r.get("data-group") == "core"][0]
        self.assertEqual((frame.get("stroke"), frame.get("rx")), ("#e11d48", "2"))



class CaptionAndFigure(unittest.TestCase):
    def test_every_type_draws_them_and_grows_only_for_them(self):
        for kind in SPECS:
            plain = draw(kind)
            name, fn = SPECS[kind]
            with open(os.path.join(REPO, "examples", name), encoding="utf-8") as f:
                spec = json.load(f)
            spec.update(figure="Fig. 2", caption="What the reader should take away, in one sentence.")
            svg = fn(spec)[0]
            root = ET.fromstring(svg)
            texts = [e.text for e in root.iter(NS + "text")]
            self.assertIn("FIG. 2", texts, kind)
            self.assertIn("What the reader should take away, in one sentence.", texts, kind)
            self.assertGreater(float(root.get("viewBox").split()[3]), float(plain.get("viewBox").split()[3]), kind)


if __name__ == "__main__":
    unittest.main()

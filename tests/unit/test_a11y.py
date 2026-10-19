"""Accessible structure and attachments. Run: py -3 -m unittest discover tests/unit"""
import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from diagonaldiagrams.audit.svg_import import svg_import  # noqa: E402
from diagonaldiagrams.diagrams import render_flow, render_schema, render_seq  # noqa: E402

NS = "{http://www.w3.org/2000/svg}"


def load(name):
    with open(os.path.join(REPO, "examples", name), encoding="utf-8") as f:
        return json.load(f)


def parts(svg):
    root = ET.fromstring(svg)
    return root, [e for e in root if e.tag not in (NS + "title", NS + "desc")]


class Flow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svg, cls.w, cls.h = render_flow(load("flow_decision.json"))
        cls.root, cls.els = parts(cls.svg)

    def test_the_figure_is_a_graphics_document(self):
        self.assertEqual((self.root.get("role"), self.root.get("aria-roledescription")), ("graphics-document", "flow diagram"))

    def test_every_node_and_arrow_is_named(self):
        nodes = [e for e in self.els if e.get("data-node") is not None]
        self.assertTrue(nodes and all(e.get("role") == "graphics-symbol" and e.get("aria-label") for e in nodes))
        self.assertEqual({e.get("aria-roledescription") for e in nodes}, {"start or end", "box", "decision"})
        arrows = [e for e in self.els if e.get("data-from") is not None]
        self.assertIn("CI tests to Fix: fail", [e.get("aria-label") for e in arrows])

    def test_text_inside_a_part_is_not_read_twice(self):
        labels = [e for e in self.els if e.tag == NS + "text" and e.text == "Fix"]
        self.assertTrue(labels and all(e.get("aria-hidden") == "true" for e in labels))
        heading = [e for e in self.els if e.tag == NS + "text" and e.text == "Deploy approval"]
        self.assertTrue(heading and heading[0].get("aria-hidden") is None)

    def test_arrows_say_where_they_attach_and_the_display_list_reads_it(self):
        arrows = [e for e in self.els if e.get("data-from") is not None]
        self.assertTrue(all(e.get("data-from-port") in ("n", "s", "e", "w") for e in arrows))
        dl = svg_import(self.root, self.w, self.h)
        attached = [a.attach for a in dl.arrows if a.attach]
        self.assertTrue(attached and all(set(x) == {"from", "to"} and x["from"]["port"] for x in attached))
        named = sorted((i.a11y for i in dl.items if i.a11y), key=lambda a: a["order"])
        self.assertEqual(named[0], {"name": "Push", "kind": "start or end", "order": 0})


class OtherDiagrams(unittest.TestCase):
    def test_sequence_messages_are_numbered_sentences(self):
        root, els = parts(render_seq(load("seq_checkout.json"))[0])
        msgs = [e.get("aria-label") for e in els if e.get("aria-roledescription") == "message"]
        self.assertTrue(msgs[0].startswith("1. Customer to "), msgs[:2])
        self.assertEqual(root.get("aria-roledescription"), "sequence diagram")

    def test_schema_tables_list_their_columns_and_relations_their_columns_as_ports(self):
        root, els = parts(render_schema(load("schema_ecommerce.json"))[0])
        tables = [e.get("aria-label") for e in els if e.get("aria-roledescription") == "table"]
        self.assertTrue(any("(primary key)" in t for t in tables), tables[:2])
        rels = [e for e in els if e.get("aria-roledescription") == "relation"]
        self.assertTrue(rels and all(e.get("data-from-port") and e.get("data-to-port") for e in rels))


class Charts(unittest.TestCase):
    def test_charts_stay_single_images_until_they_paint_through_the_drawing(self):
        from diagonaldiagrams.plots import render_bar
        svg = render_bar(os.path.join(REPO, "examples", "bar_latency.csv"), "service", "p99_latency_ms", "Latency")[0]
        self.assertEqual(ET.fromstring(svg).get("role"), "img")


if __name__ == "__main__":
    unittest.main()

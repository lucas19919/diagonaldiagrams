"""Selectors and the cascade. Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.scene import normalize  # noqa: E402
from diagonaldiagrams.style.cascade import Cascade, scene_views  # noqa: E402
from diagonaldiagrams.style.select import Selector  # noqa: E402

SCENE, _ = normalize({
    "version": 2, "preset": "arch",
    "nodes": [{"id": "web", "name": "Web", "class": "edge-tier"},
              {"id": "api", "name": "API", "group": "core", "focal": True, "data": {"team": "pay", "p99": 182}},
              {"id": "db", "name": "Orders DB", "class": "db store", "group": "core", "data": {"team": "data", "p99": 12}},
              {"id": "cache", "name": "Cache", "group": "inner", "style": {"stroke": "#123456"}}],
    "edges": [{"from": "web", "to": "api", "proto": "https", "class": "critical"}, {"from": "api", "to": "db", "async": True},
              {"from": "api", "to": "cache"}],
    "groups": [{"id": "core", "name": "Core"}, {"id": "inner", "name": "Inner", "parent": "core"}]})
V = scene_views(SCENE)


def pick(text):
    sel = Selector(text)
    every = [*V["nodes"].values(), *V["groups"].values(), *V["edges"].values(), V["figure"]]
    return sorted(v.id for v in every if sel.matches(v))


class Selectors(unittest.TestCase):
    def test_types_ids_classes(self):
        self.assertEqual(pick("node"), ["api", "cache", "db", "web"])
        self.assertEqual(pick("#api"), ["api"])
        self.assertEqual(pick("node.db.store"), ["db"])
        self.assertEqual(pick(".critical"), ["web->api"])
        self.assertEqual(pick("*.db"), ["db"])

    def test_attributes_read_fields_then_data(self):
        self.assertEqual(pick("node[team=pay]"), ["api"])
        self.assertEqual(pick("node[team!=pay]"), ["cache", "db", "web"])
        self.assertEqual(pick("edge[proto^=http]"), ["web->api"])
        self.assertEqual(pick("edge[async]"), ["api->db"])
        self.assertEqual(pick("edge[from=api]"), ["api->cache", "api->db"])
        self.assertEqual(pick("node[p99>100]"), ["api"])
        self.assertEqual(pick("node[p99<50]"), ["db"])
        self.assertEqual(pick('node[name="Orders DB"]'), ["db"])

    def test_combinators_follow_the_group_tree(self):
        self.assertEqual(pick("group#core node"), ["api", "cache", "db"])
        self.assertEqual(pick("group#core > node"), ["api", "db"])
        self.assertEqual(pick("group > group"), ["inner"])
        self.assertEqual(pick("figure > node"), ["web"])

    def test_pseudo_classes(self):
        self.assertEqual(pick("node:focal"), ["api"])
        self.assertEqual(pick("node:source"), ["web"])
        self.assertEqual(pick("node:sink"), ["cache", "db"])
        self.assertEqual(pick("group#core > node:first-child"), ["api"])
        self.assertEqual(pick("node:not(.db):not(:focal)"), ["cache", "web"])
        self.assertEqual(pick("edge:nth-child(2)"), ["api->db"])

    def test_specificity(self):
        self.assertEqual(Selector("node").specificity, (0, 0, 1))
        self.assertEqual(Selector("#api").specificity, (1, 0, 0))
        self.assertEqual(Selector("node.db[team=x]:focal").specificity, (0, 3, 1))
        self.assertEqual(Selector("node:not(#api)::label").specificity, (1, 0, 2))

    def test_errors_suggest(self):
        for text, near in (("nod", "node"), ("node:focl", ":focal"), ("node::lable", "::label")):
            with self.assertRaises(SpecError) as cm:
                Selector(text)
            self.assertIn(f"did you mean '{near}'", cm.exception.msg, text)
        for bad in ("", "node node::label node", "> node", "node[p99>high]", "node:nth-child(0)", "node{"):
            with self.assertRaises(SpecError, msg=bad):
                Selector(bad)


class Cascading(unittest.TestCase):
    def test_order_specificity_and_layers(self):
        c = Cascade(["editorial", {"name": "brand", "rules": {
            "node": {"fill": "card", "stroke": "ink", "stroke-width": 1},
            "node.db": {"fill": "#eeeeee"},
            "#api": {"stroke": "accent"},
            "node:focal": {"stroke": "link"}}},  # less specific than #api: loses on api
            {"name": "inline", "rules": {"node": {"stroke-width": 2}}}])
        api, db, cache = (c.computed(V["nodes"][k]) for k in ("api", "db", "cache"))
        self.assertEqual((api["fill"].css, api["stroke"].css, api["stroke-width"]), ("#ffffff", "#eb6c36", 2.0))
        self.assertEqual(db["fill"].css, "#eeeeee")
        self.assertEqual(cache["stroke"].css, "#123456")  # the element's own style beats every sheet

    def test_policy_beats_the_element(self):
        c = Cascade(["editorial", {"name": "brand", "policy": True, "rules": {"node": {"stroke": "#000000"}},
                                   "tokens": {"accent": "#ff0000"}},
                     {"name": "agent", "tokens": {"accent": "#00ff00"}, "rules": {"node": {"fill": "accent"}}}])
        cache = c.computed(V["nodes"]["cache"])
        self.assertEqual((cache["stroke"].css, cache["fill"].css), ("#000000", "#ff0000"))

    def test_shorthands_expand_and_longhands_win_later(self):
        c = Cascade(["editorial", {"rules": {"node": {"border": "1px solid ink", "border-left": "4px solid #e11d48"},
                                             "edge": {"background": "paper"}}}])
        api = c.computed(V["nodes"]["api"])
        self.assertEqual([api[f"border-{s}"]["width"] for s in ("top", "right", "bottom", "left")], [1.0, 1.0, 1.0, 4.0])
        self.assertEqual(c.computed(V["edges"]["web->api"])["fill"].css, "#f5f5f5")

    def test_text_inherits_and_em_reads_the_font_size(self):
        c = Cascade(["editorial", {"rules": {"figure": {"font-family": "Inter", "font-size": 12, "color": "ink"},
                                             "group#core": {"font-size": 20},
                                             "node": {"stroke": "accent", "letter-spacing": "0.1em"},
                                             "node::label": {"font-weight": 600}}}])
        db = c.computed(V["nodes"]["db"])
        web = c.computed(V["nodes"]["web"])
        self.assertEqual((db["font-family"], db["font-size"], db["letter-spacing"]), ("Inter", 20.0, 2.0))
        self.assertEqual(web["font-size"], 12.0)
        self.assertAlmostEqual(web["letter-spacing"], 1.2)
        label = c.computed(V["nodes"]["db"], "label")
        self.assertEqual((label["font-weight"], label["font-size"], label.get("stroke")), ("600", 20.0, None))

    def test_errors_name_the_sheet_and_rule(self):
        with self.assertRaises(SpecError) as cm:
            Cascade(["editorial", {"name": "brand", "rules": {"node": {"stroke": "acent"}}}])
        self.assertIn("stylesheet 'brand', rule 'node'", cm.exception.msg)
        self.assertIn("did you mean 'accent'", cm.exception.msg)
        with self.assertRaises(SpecError) as cm:
            Cascade([{"rules": {"nod": {"fill": "red"}}}])
        self.assertIn("did you mean 'node'", cm.exception.msg)
        with self.assertRaises(SpecError):
            Cascade([{"rules": {"node": {"colour": "red"}}}])

    def test_encodings_pass_through(self):
        enc = {"field": "p99", "scale": {"type": "sequential"}}
        c = Cascade(["editorial", {"rules": {"node": {"fill": enc}}}])
        self.assertEqual(c.computed(V["nodes"]["api"])["fill"], enc)


if __name__ == "__main__":
    unittest.main()

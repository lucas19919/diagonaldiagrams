"""Stable identity (PLAN P2.15, DESIGN D15): an edit keeps the ids of what it didn't touch, in the
outline, in the SVG and in the editable exports. Run: py -3 -m unittest discover tests/unit"""
import copy
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import api  # noqa: E402

FLOW = {"preset": "flow", "title": "Release",
        "nodes": [{"id": "a", "label": "Merge"}, {"id": "b", "label": "Tests pass?", "shape": "diamond"},
                  {"id": "c", "label": "Deploy"}, {"id": "d", "label": "Fix", "shape": "oval"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c", "label": "yes"},
                  {"from": "b", "to": "d", "label": "no"}, {"from": "c", "to": "d"}],
        "groups": [{"id": "ship", "label": "Ship", "members": ["b", "c"]}]}


def edited(scene):
    """A node and an edge added at the front, one label changed, one edge repeated."""
    s = copy.deepcopy(scene)
    s["nodes"].insert(0, {"id": "z", "label": "Plan"})
    s["edges"].insert(0, {"from": "z", "to": "a"})
    s["edges"][3]["label"] = "fail"  # b->d: its id follows its label
    s["edges"].append({"from": "a", "to": "b"})
    return s


class Identity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="dd-identity-")

    def draw(self, name, scene, kind="flow"):
        out = os.path.join(self.dir, name + ".html")
        v = api.render(kind, scene=scene, out=out, outline=True)
        self.assertTrue(v["ok"], v)
        return v

    def export(self, svg, to):
        dest = os.path.splitext(svg)[0] + "." + to
        code, out, err = api.run(["export", svg, "--to", to, "-o", dest])
        self.assertEqual(code, 0, out + err)
        with open(dest, encoding="utf-8") as f:
            return f.read()

    def test_outline_ids_survive_an_edit(self):
        before, after = self.draw("before", FLOW), self.draw("after", edited(FLOW))
        nodes = lambda v: [n["id"] for n in v["outline"]["nodes"]]  # noqa: E731
        edges = lambda v: [e["id"] for e in v["outline"]["edges"]]  # noqa: E731
        self.assertEqual(edges(before), ["a->b", "b->c:yes", "b->d:no", "c->d"])
        self.assertEqual(edges(after), ["z->a", "a->b", "b->c:yes", "b->d:fail", "c->d", "a->b#2"])
        self.assertTrue(set(nodes(before)) <= set(nodes(after)))

    def test_svg_and_exports_keep_unchanged_ids(self):
        before, after = self.draw("svg-before", FLOW), self.draw("svg-after", edited(FLOW))
        for v in (before, after):
            with open(v["svg"], encoding="utf-8") as f:
                self.assertIn('data-id="b-&gt;c:yes"', f.read())
        cells = [set(re.findall(r'<mxCell id="([^"]+)"', self.export(v["svg"], "drawio"))) for v in (before, after)]
        kept = {"node:a", "node:b", "node:c", "node:d", "edge:a-&gt;b", "edge:b-&gt;c:yes", "edge:c-&gt;d", "group:ship"}
        self.assertTrue(kept <= cells[0] and kept <= cells[1], cells)
        self.assertIn("edge:b-&gt;d:no", cells[0])
        self.assertNotIn("edge:b-&gt;d:no", cells[1])
        seeds = [{e["id"]: e["seed"] for e in json.loads(self.export(v["svg"], "excalidraw"))["elements"]}
                 for v in (before, after)]
        for eid in ("node:a", "node:b", "edge:b->c:yes", "group:ship"):
            self.assertEqual(seeds[0][eid], seeds[1][eid], eid)

    def test_sequence_messages_are_named_by_content_not_place(self):
        seq = {"preset": "seq", "nodes": [{"id": "u", "label": "User"}, {"id": "api", "label": "API"}],
               "edges": [{"from": "u", "to": "api", "label": "login"}, {"from": "api", "to": "u", "label": "token"}]}
        later = copy.deepcopy(seq)
        later["edges"].insert(0, {"from": "u", "to": "api", "label": "hello"})
        ids = [[m["id"] for m in self.draw(name, s, "seq")["outline"]["messages"]] for name, s in (("s1", seq), ("s2", later))]
        self.assertEqual(ids, [["u->api:login", "api->u:token"], ["u->api:hello", "u->api:login", "api->u:token"]])


if __name__ == "__main__":
    unittest.main()

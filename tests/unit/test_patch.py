"""Patches (PLAN P2.16, DESIGN 21.3). Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.inputs.v1 import from_v1, to_v1  # noqa: E402
from diagonaldiagrams.scene import normalize  # noqa: E402
from diagonaldiagrams.scene.patch import apply, compact  # noqa: E402

BASE = {"version": 2, "preset": "flow",
        "nodes": [{"id": "a", "name": "Merge"}, {"id": "b", "name": "Test"}, {"id": "c", "name": "Ship", "group": "out"},
                  {"id": "d", "name": "Fix"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c", "label": "pass"}, {"from": "b", "to": "d", "label": "fail"}],
        "groups": [{"id": "out", "name": "Release", "members": ["c"]}],
        "constraints": [{"order": ["c", "d"]}],
        "annotations": [{"type": "note", "target": "#d", "text": "rare"}]}


def run(ops, base=BASE):
    scene, _ = normalize(base)
    return apply(scene, ops)


class Operations(unittest.TestCase):
    def test_pin_text_and_style(self):
        s, n, c = run([{"op": "pin", "id": "a", "x": 40, "y": 60},
                       {"op": "text", "id": "b", "name": "Run tests", "sub": "CI"},
                       {"op": "style", "selector": "#c", "set": {"fill": "#fee2e2"}},
                       {"op": "style", "selector": "node.hot", "set": {"stroke": "accent"}}])
        self.assertEqual((n, c), (4, []))
        self.assertEqual(s.node("a").pin, {"x": 40, "y": 60})
        self.assertEqual((s.node("b").name, s.node("b").sub), ("Run tests", "CI"))
        self.assertEqual(s.node("c").style, {"fill": "#fee2e2"})
        self.assertEqual(s.style, {"rules": {"node.hot": {"stroke": "accent"}}})

    def test_style_null_removes_and_rules_join_an_existing_sheet(self):
        base = dict(BASE, style=["brand.json"])
        base["nodes"] = [dict(BASE["nodes"][0], style={"fill": "red", "stroke": "blue"})] + BASE["nodes"][1:]
        s, _, c = run([{"op": "style", "selector": "#a", "set": {"fill": None}},
                       {"op": "style", "selector": "edge", "set": {"stroke-width": 2}}], base)
        self.assertEqual((s.node("a").style, s.style, c), ({"stroke": "blue"}, ["brand.json", {"rules": {"edge": {"stroke-width": 2}}}], []))

    def test_retexting_an_edge_keeps_its_id(self):
        s, _, _ = run([{"op": "text", "id": "b->d:fail", "label": "red"}])
        e = s.edges[2]
        self.assertEqual((e.id, e.label), ("b->d:fail", "red"))
        self.assertEqual(compact(s.to_dict())["edges"][2]["id"], "b->d:fail")  # kept, since it no longer follows
        self.assertNotIn("id", compact(s.to_dict())["edges"][0])

    def test_order_rewrites_the_constraint_that_holds_its_ids(self):
        s, _, _ = run([{"op": "order", "ids": ["d", "c"]}])
        self.assertEqual(s.constraints, [{"order": ["d", "c"]}])
        s, _, _ = run([{"op": "order", "ids": ["b", "a"]}])
        self.assertEqual(s.constraints, [{"order": ["c", "d"]}, {"order": ["b", "a"]}])

    def test_add_then_connect(self):
        s, n, c = run([{"op": "add", "node": {"id": "e", "name": "Notify"}}, {"op": "add", "edge": {"from": "c", "to": "e"}}])
        self.assertEqual((n, c, s.edges[-1].id), (2, [], "c->e"))

    def test_remove_a_node_takes_what_points_at_it(self):
        s, _, c = run([{"op": "remove", "id": "d"}])
        self.assertEqual(c, [])
        self.assertEqual([e.id for e in s.edges], ["a->b", "b->c:pass"])
        self.assertEqual((s.constraints, s.annotations), ([], []))

    def test_remove_a_group_frees_its_members(self):
        s, _, _ = run([{"op": "remove", "id": "out"}])
        self.assertEqual((s.groups, s.node("c").group), ([], None))

    def test_move_to_group_and_out(self):
        s, _, c = run([{"op": "move-to-group", "id": "d", "group": "out"}])
        self.assertEqual((c, s.group("out").members, s.node("d").group), ([], ["c", "d"], "out"))
        s, _, _ = run([{"op": "move-to-group", "id": "c", "group": None}])
        self.assertEqual([(g.id, g.members) for g in s.groups], [("out", [])])  # declared, so it stays, empty
        self.assertIsNone(s.node("c").group)


class Conflicts(unittest.TestCase):
    def test_each_conflict_is_reported_and_the_rest_apply(self):
        s, n, c = run([{"op": "text", "id": "gone", "name": "x"},
                       {"op": "text", "id": "a", "name": "Merge it", "was": "Merged"},
                       {"op": "add", "node": {"id": "a"}},
                       {"op": "add", "edge": {"from": "a", "to": "nowhere"}},
                       {"op": "pin", "id": "a->b", "x": 1, "y": 2},
                       {"op": "move-to-group", "id": "a", "group": "b"},
                       {"op": "explode"},
                       {"op": "text", "id": "a", "name": "Merge it", "was": "Merge"}])
        self.assertEqual(n, 1)
        self.assertEqual([x["path"] for x in c], [f"patch[{k}]" for k in range(7)])
        self.assertTrue(all(x["code"] == "patch-conflict" and x["fix"] for x in c))
        self.assertEqual(s.node("a").name, "Merge it")

    def test_the_scene_passed_in_is_untouched(self):
        scene, _ = normalize(BASE)
        before = scene.to_dict()
        apply(scene, [{"op": "remove", "id": "b"}, {"op": "text", "id": "a", "name": "New"}])
        self.assertEqual(scene.to_dict(), before)

    def test_not_a_list(self):
        _, n, c = run({"op": "text"})
        self.assertEqual((n, c[0]["path"]), (0, "patch"))


class V1Files(unittest.TestCase):
    def test_a_patch_survives_the_v1_round_trip(self):
        v1 = {"nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], "edges": [{"from": "a", "to": "b"}]}
        scene, _ = normalize(from_v1(v1, "flow"))
        patched, _, _ = apply(scene, [{"op": "style", "selector": "#a", "set": {"fill": "red"}},
                                      {"op": "pin", "id": "b", "x": 1, "y": 2}])
        _, spec, warn = to_v1(patched)
        self.assertEqual(spec["nodes"], [{"id": "a", "name": "A", "style": {"fill": "red"}}, {"id": "b", "name": "B", "pin": {"x": 1, "y": 2}}])
        self.assertEqual([w["code"] for w in warn], ["not-drawn"])
        again, _ = normalize(from_v1(spec, "flow"))  # read back: the patch is still there
        self.assertEqual((again.node("a").style, again.node("b").pin), ({"fill": "red"}, {"x": 1, "y": 2}))


if __name__ == "__main__":
    unittest.main()

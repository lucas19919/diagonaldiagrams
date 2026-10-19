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
        self.assertEqual([w["code"] for w in warn], ["not-drawn"])  # the pin; the style is drawn
        again, _ = normalize(from_v1(spec, "flow"))  # read back: the patch is still there
        self.assertEqual((again.node("a").style, again.node("b").pin), ({"fill": "red"}, {"x": 1, "y": 2}))



def drawn(kind, spec):
    """(exit code, the verdict's layout lines) of a render of a v1 spec."""
    import json
    import tempfile
    from diagonaldiagrams import api
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "spec.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f)
        code, out, _ = api.run([kind, path, "-o", os.path.join(d, "out.svg")])
    return code, json.loads(out.strip().splitlines()[-1]).get("layout", [])


def drawn_rows(kind, spec):
    """The rows a render draws (its verdict's layout lines), for a v1 spec."""
    code, layout = drawn(kind, spec)
    return code, [line for line in layout if line.startswith("row ")]


def placed(v1, kind, ops):
    scene, _ = normalize(from_v1(v1, kind))
    patched, n, c = apply(scene, ops)
    _, spec, warn = to_v1(patched)
    return spec, n, c, warn


class Place(unittest.TestCase):
    """A drag in the page becomes a place: the node's new row, in order (DESIGN 21.3)."""
    FLOW = {"nodes": [{"id": "a", "name": "A", "rank": 0}, {"id": "b", "name": "B", "rank": 1, "lane": -1},
                      {"id": "c", "name": "C", "rank": 1, "lane": 1}, {"id": "d", "name": "D", "rank": 2}],
            "edges": [{"from": "a", "to": "b"}, {"from": "a", "to": "c"}, {"from": "b", "to": "d"}, {"from": "c", "to": "d"}]}

    def test_reorder_within_a_row_beats_its_lanes(self):
        spec, n, c, warn = placed(self.FLOW, "flow", [{"op": "place", "id": "b", "row": ["c", "b"]}])
        self.assertEqual((n, c, warn), (1, [], []))
        self.assertEqual(drawn_rows("flow", spec), (0, ["row 1: A", "row 2: C | B", "row 3: D"]))

    def test_into_another_ranked_row(self):
        spec, n, c, _ = placed(self.FLOW, "flow", [{"op": "place", "id": "d", "row": ["b", "d", "c"]}])
        self.assertEqual(next(x for x in spec["nodes"] if x["id"] == "d")["rank"], 1)
        self.assertNotIn("constraints", spec)
        self.assertEqual(drawn_rows("flow", spec), (0, ["row 1: A", "row 2: B | D | C"]))

    def test_unranked_rows_hold_by_a_same_rank_constraint(self):
        v1 = {"nodes": [{"id": x, "name": x.upper()} for x in "abcd"],
              "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "d"}]}
        spec, n, c, warn = placed(v1, "flow", [{"op": "place", "id": "d", "row": ["b", "d"]}])
        self.assertEqual((spec["constraints"], warn), ([{"same-rank": ["b", "d"]}], []))
        code, rows = drawn_rows("flow", spec)
        self.assertEqual((code, rows[1]), (0, "row 2: B | D"))
        spec, _, _, _ = placed(spec, "flow", [{"op": "place", "id": "d", "row": ["c", "d"]}])
        self.assertEqual(spec["constraints"], [{"same-rank": ["c", "d"]}])  # moving on drops the old row

    def test_arch_keeps_frames_whole(self):
        v1 = {"nodes": [{"id": "gw", "name": "Gateway", "layer": 0}, {"id": "auth", "name": "Auth", "layer": 0},
                        {"id": "mem", "name": "Memory", "layer": 1}, {"id": "agent", "name": "Agent", "layer": 1},
                        {"id": "llm", "name": "Model", "layer": 1}],
              "edges": [{"from": "gw", "to": "agent"}, {"from": "gw", "to": "auth"}, {"from": "agent", "to": "mem"},
                        {"from": "agent", "to": "llm"}],
              "groups": [{"id": "rt", "name": "Runtime", "nodes": ["mem", "agent"]}]}
        spec, _, c, _ = placed(v1, "arch", [{"op": "place", "id": "auth", "row": ["mem", "agent", "auth", "llm"]}])
        self.assertEqual((c, next(x for x in spec["nodes"] if x["id"] == "auth")["layer"]), ([], 1))
        self.assertEqual(drawn_rows("arch", spec), (0, ["row 1: Gateway", "row 2: Memory | Agent | Auth | Model"]))

    def test_what_a_place_cannot_be(self):
        for op in ({"op": "place", "id": "b", "row": ["c"]}, {"op": "place", "id": "b", "row": ["b"]},
                   {"op": "place", "id": "b", "row": ["b", "zz"]}, {"op": "place", "id": "a->b", "row": ["a->b", "c"]}):
            _, n, c, _ = placed(self.FLOW, "flow", [op])
            self.assertEqual((n, len(c)), (0, 1), op)


def outlined(kind, spec):
    """(exit code, verdict) of a render of a v1 spec, with its outline."""
    import json
    import tempfile
    from diagonaldiagrams import api
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "spec.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f)
        code, out, _ = api.run([kind, path, "-o", os.path.join(d, "out.svg"), "--outline"])
    return code, json.loads(out.strip().splitlines()[-1])


def middles(verdict):
    return {n["id"]: (n["x"], n["y"]) for n in verdict["outline"]["nodes"]}


class Pins(unittest.TestCase):
    """A pin in flow and arch is not drawn: the boxes stand in rows, and a place, a rank or an order
    says where one goes (DESIGN 4.6)."""

    def test_a_pin_is_not_drawn_and_names_what_to_use(self):
        spec, n, c, warn = placed(Place.FLOW, "flow", [{"op": "pin", "id": "c", "x": 600, "y": 300}])
        self.assertEqual((n, c, [w["code"] for w in warn]), (1, [], ["not-drawn"]))
        self.assertIn("place patch", warn[0]["fix"])
        code, after = outlined("flow", spec)
        self.assertEqual(code, 0)
        self.assertEqual([w["code"] for w in after.get("warnings", [])], ["not-drawn"])
        self.assertEqual(middles(after), middles(outlined("flow", Place.FLOW)[1]))

    def test_a_drag_drops_the_pin(self):
        spec, _, _, _ = placed(Place.FLOW, "flow", [{"op": "pin", "id": "b", "x": 600, "y": 300}])
        spec, n, c, _ = placed(spec, "flow", [{"op": "place", "id": "b", "row": ["c", "b"]}])
        self.assertEqual((n, c), (1, []))
        self.assertNotIn("pin", next(x for x in spec["nodes"] if x["id"] == "b"))
        self.assertEqual(drawn_rows("flow", spec), (0, ["row 1: A", "row 2: C | B", "row 3: D"]))


class Messages(unittest.TestCase):
    """A message dragged to another step in the page becomes an order over messages (DESIGN 21.3)."""
    SEQ = {"actors": [{"id": "u", "name": "User"}, {"id": "api", "name": "API"}, {"id": "db", "name": "DB"}],
           "messages": [{"from": "u", "to": "api", "label": "login"}, {"from": "api", "to": "db", "label": "look up"},
                        {"from": "db", "to": "api", "label": "row"}, {"from": "api", "to": "u", "label": "token"}]}
    IDS = ["u->api:login", "api->db:look up", "db->api:row", "api->u:token"]

    def test_an_order_takes_the_steps_its_messages_held(self):
        spec, n, c, warn = placed(self.SEQ, "seq", [{"op": "order", "ids": [self.IDS[2], self.IDS[1]]}])
        self.assertEqual((n, c, warn), (1, [], []))
        self.assertEqual([m["label"] for m in spec["messages"]], ["login", "row", "look up", "token"])
        again, n, c, _ = placed(spec, "seq", [{"op": "order", "ids": [self.IDS[2], self.IDS[1]]}])
        self.assertEqual((again, n, c), (spec, 1, []))  # a kept patch applied again changes nothing

    def test_a_relabeled_message_keeps_its_id_and_moves(self):
        spec, n, c, _ = placed(self.SEQ, "seq", [{"op": "text", "id": self.IDS[1], "label": "find the user", "was": "look up"},
                                                 {"op": "order", "ids": [self.IDS[1], self.IDS[0]]}])
        self.assertEqual((n, c), (2, []))
        self.assertEqual(spec["messages"][0], {"from": "api", "to": "db", "id": "api->db:look up", "label": "find the user"})
        code, layout = drawn("seq", spec)
        self.assertEqual((code, layout[1:3]), (0, ["1. API -> DB: find the user", "2. User -> API: login"]))

    def test_what_an_order_of_messages_cannot_be(self):
        _, n, c, _ = placed(self.SEQ, "seq", [{"op": "order", "ids": [self.IDS[0], "u"]}])
        self.assertEqual((n, c[0]["msg"]), (0, "order: an order names nodes or edges, not both"))
        _, n, c, _ = placed(Place.FLOW, "flow", [{"op": "order", "ids": ["a->b", "a->c"]}])
        self.assertEqual((n, c[0]["msg"]), (0, "order: only a sequence's messages have an order"))


if __name__ == "__main__":
    unittest.main()

"""The scene model and normalize (PLAN P2.3). Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.inputs.v1 import from_v1, to_v1  # noqa: E402
from diagonaldiagrams.scene import check, normalize  # noqa: E402


def codes(issues):
    return [i["code"] for i in issues]


class Aliases(unittest.TestCase):
    def test_v1_names_read_as_scene_fields(self):
        s, _ = normalize({"version": 2, "sub": "One line", "nodes": [{"id": "a", "label": "API", "subtitle": "Go", "layer": 2}],
                          "groups": [{"id": "g", "label": "Edge", "nodes": ["a"]}]})
        self.assertEqual(s.subtitle, "One line")
        n = s.node("a")
        self.assertEqual((n.name, n.sub, n.rank), ("API", "Go", 2))
        self.assertEqual((s.group("g").name, s.group("g").members), ("Edge", ["a"]))

    def test_alias_and_canonical_disagree(self):
        s, w = normalize({"nodes": [{"id": "a", "name": "One", "label": "Two"}]})
        self.assertEqual(s.node("a").name, "One")
        self.assertEqual(codes(w), ["alias-conflict"])

    def test_name_defaults_to_id_and_id_to_name(self):
        s, _ = normalize({"nodes": [{"id": "a"}, {"name": "Billing"}, {"id": 7}]})
        self.assertEqual([(n.id, n.name) for n in s.nodes], [("a", "a"), ("Billing", "Billing"), ("7", "7")])


class Groups(unittest.TestCase):
    def test_both_membership_forms_merge(self):
        s, _ = normalize({"nodes": [{"id": "a"}, {"id": "b", "group": "g"}, {"id": "c", "group": "h"}],
                          "groups": [{"id": "g", "members": ["a"]}]})
        self.assertEqual(s.group("g").members, ["a", "b"])
        self.assertEqual([g.id for g in s.groups], ["g", "h"])  # h exists only through its member
        self.assertEqual([n.group for n in s.nodes], ["g", "g", "h"])

    def test_a_node_in_two_groups_is_an_error(self):
        _, errors, _ = check({"nodes": [{"id": "a", "group": "h"}], "groups": [{"id": "g", "members": ["a"]}]})
        self.assertEqual(codes(errors), ["two-groups"])
        _, errors, _ = check({"nodes": [{"id": "a"}], "groups": [{"id": "g", "members": ["a"]}, {"id": "h", "members": ["a"]}]})
        self.assertEqual(codes(errors), ["two-groups"])

    def test_container_tree(self):
        s, _ = normalize({"nodes": [{"id": "a", "group": "inner"}, {"id": "b"}],
                          "groups": [{"id": "outer", "members": []}, {"id": "inner", "parent": "outer"}]})
        self.assertEqual([x.id for x in s.children()], ["outer", "b"])
        self.assertEqual([x.id for x in s.children("outer")], ["inner"])
        self.assertEqual([x.id for x in s.children("inner")], ["a"])

    def test_parent_cycle_and_unknown_parent(self):
        _, errors, _ = check({"groups": [{"id": "g", "parent": "h"}, {"id": "h", "parent": "g"}]})
        self.assertIn("group-cycle", codes(errors))
        _, errors, _ = check({"groups": [{"id": "g", "parent": "nope"}]})
        self.assertEqual(codes(errors), ["unknown-group"])

    def test_empty_group_warns(self):
        _, errors, warnings = check({"nodes": [{"id": "a"}], "groups": [{"id": "g"}]})
        self.assertEqual((errors, codes(warnings)), ([], ["empty-group"]))


class Ids(unittest.TestCase):
    def test_errors_carry_paths_and_all_are_reported(self):
        _, errors, _ = check({"nodes": [{"id": "a"}, {"id": "a"}, {"sub": "x"}],
                              "edges": [{"from": "a", "to": "ghost"}, {"to": "a"}]})
        self.assertEqual([(e["code"], e["path"]) for e in errors],
                         [("missing-id", "nodes[2].id"), ("duplicate-id", "nodes[1].id"),
                          ("unknown-node", "edges[0].to"), ("missing-end", "edges[1].from")])

    def test_normalize_raises_the_first_error(self):
        with self.assertRaises(SpecError) as cm:
            normalize({"nodes": [{"id": "a"}], "edges": [{"from": "a", "to": "x"}, {"from": "y", "to": "a"}]})
        self.assertEqual((cm.exception.code, cm.exception.at), ("unknown-node", "edges[0].to"))
        self.assertIn("(and 1 more)", cm.exception.msg)

    def test_bad_types(self):
        _, errors, _ = check({"nodes": [{"id": "a", "rank": "top", "focal": "yes"}], "budget": "no"})
        self.assertEqual(sorted(e["path"] for e in errors), ["nodes[0].focal", "nodes[0].rank", "scene.budget"])

    def test_edge_ids_come_from_content(self):
        s, _ = normalize({"nodes": [{"id": "a"}, {"id": "b"}],
                          "edges": [{"from": "a", "to": "b"}, {"from": "a", "to": "b", "label": "retry"},
                                    {"from": "a", "to": "b"}, {"id": "mine", "from": "b", "to": "a"}]})
        self.assertEqual([e.id for e in s.edges], ["a->b", "a->b:retry", "a->b#2", "mine"])

    def test_edge_ids_survive_an_insert(self):
        """D15: adding an edge elsewhere doesn't rename the others."""
        base = {"nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                "edges": [{"from": "a", "to": "b", "label": "go"}, {"from": "b", "to": "c"}]}
        before = [e.id for e in normalize(base)[0].edges]
        base["edges"].insert(0, {"from": "a", "to": "b", "label": "stop"})
        after = [e.id for e in normalize(base)[0].edges]
        self.assertEqual(after[1:], before)

    def test_typo_in_a_field_name_is_flagged(self):
        s, w = normalize({"nodes": [{"id": "a", "focla": True, "team": "pay"}]})
        self.assertEqual(s.node("a").extra, {"focla": True, "team": "pay"})
        self.assertEqual([(x["code"], x["fix"]) for x in w], [("unknown-field", "did you mean 'focal'?")])


class RoundTrip(unittest.TestCase):
    SCENE = {"version": 2, "title": "Checkout", "preset": "arch",
             "nodes": [{"id": "web", "name": "Web", "class": "edge hot", "rank": 0},
                       {"id": "api", "name": "API", "sub": "Go:8080", "rank": 1, "focal": True, "group": "core", "owner": "pay"}],
             "edges": [{"from": "web", "to": "api", "label": "calls", "proto": "https", "from-port": "s"}],
             "groups": [{"id": "core", "name": "Core"}],
             "annotations": [{"type": "note", "target": "#api", "text": "rate limited"}]}

    def test_to_dict_normalizes_to_the_same_scene(self):
        s, _ = normalize(self.SCENE)
        again, _ = normalize(s.to_dict())
        self.assertEqual(again, s)
        d = s.to_dict()
        self.assertEqual(d["nodes"][0]["class"], "edge hot")
        self.assertEqual(d["nodes"][1]["owner"], "pay")
        self.assertEqual(d["edges"][0]["from-port"], "s")
        self.assertEqual(d["edges"][0]["id"], "web->api:calls")  # written out, so a receipt or patch can name it

    def test_v1_specs_map_to_presets(self):
        seq = {"title": "Login", "actors": [{"id": "u"}, {"id": "api", "name": "API"}],
               "messages": [{"from": "u", "to": "api", "label": "login"}, {"from": "api", "to": "u", "reply": True}]}
        s, _ = normalize(from_v1(seq, "seq"))
        self.assertEqual((s.preset, s.layout, [e.order for e in s.edges]), ("seq", "sequence", [0, 1]))
        kind, back, warn = to_v1(s)
        self.assertEqual((kind, warn), ("seq", []))
        self.assertEqual(back["messages"], [{"from": "u", "to": "api", "label": "login"}, {"from": "api", "to": "u", "reply": True}])

        schema = {"tables": [{"id": "u", "name": "users", "x": 40, "y": 90, "columns": [{"name": "id", "pk": True}]}],
                  "relations": [{"from": "u", "to": "u", "from_col": "id", "to_col": "id"}]}
        s, _ = normalize(from_v1(schema, "schema"))
        t = s.node("u")
        self.assertEqual((t.shape, t.pin, t.ports), ("table", {"x": 40, "y": 90}, [{"id": "id"}]))
        self.assertEqual((s.edges[0].from_port, s.edges[0].to_port), ("id", "id"))
        self.assertEqual(to_v1(s)[1], {"tables": [{"id": "u", "name": "users", "x": 40, "y": 90,
                                                   "columns": [{"name": "id", "pk": True}]}],
                                       "relations": [{"from": "u", "to": "u", "from_col": "id", "to_col": "id"}]})

    def test_arch_rows_keep_spec_order_through_constraints(self):
        arch = {"nodes": [{"id": "a", "layer": 1}, {"id": "b", "layer": 1}, {"id": "c"}], "edges": []}
        s, _ = normalize(from_v1(arch, "arch"))
        self.assertEqual(s.constraints, [{"order": ["a", "b"]}])
        self.assertEqual([n.rank for n in s.nodes], [1, 1, 0])
        s.constraints = [{"order": ["b", "a"]}]  # what a patch that swaps them writes
        self.assertEqual([n["id"] for n in to_v1(s)[1]["nodes"]], ["b", "a", "c"])

    def test_what_v1_cannot_draw_is_named(self):
        s, _ = normalize({"version": 2, "preset": "flow", "nodes": [{"id": "a", "style": {"fill": "red"}}],
                          "annotations": [{"type": "callout", "target": "#a", "text": "!"}]})
        _, _, warn = to_v1(s)
        self.assertEqual([w["path"] for w in warn], ["annotations", "nodes.a"])

    def test_a_scene_without_a_drawable_preset_is_refused(self):
        s, _ = normalize({"version": 2, "nodes": [{"id": "a"}]})
        with self.assertRaises(SpecError):
            to_v1(s)


if __name__ == "__main__":
    unittest.main()

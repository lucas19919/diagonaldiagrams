"""The layered layout kernel (PLAN P4.2-P4.4, DESIGN 7-8). Run: py -3 -m unittest discover tests/unit"""
import itertools
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.layout import channels, layered  # noqa: E402
from diagonaldiagrams.layout.order import Layering, crossings  # noqa: E402
from diagonaldiagrams.layout.rank import back_edges, network_simplex, ranks  # noqa: E402


def box(n, res):
    x, y = res.pos[n["id"]]
    return (x - n["w"] / 2, y - n["h"] / 2, x + n["w"] / 2, y + n["h"] / 2)


def chain(n, back=()):
    nodes = [{"id": f"n{i}", "w": 160, "h": 56} for i in range(n)]
    edges = [{"id": f"e{i}", "from": f"n{i}", "to": f"n{i + 1}"} for i in range(n - 1)]
    edges += [{"id": f"b{k}", "from": f"n{a}", "to": f"n{b}"} for k, (a, b) in enumerate(back)]
    return nodes, edges


def random_graph(seed, n):
    rng = random.Random(seed)
    nodes = [{"id": f"n{i}", "w": rng.choice([160, 160, 8]), "h": rng.choice([56, 64, 8]),
              "shape": rng.choice(["rect", "rect", "diamond"])} for i in range(n)]
    for nd in nodes:
        if nd["w"] == 8 or nd["h"] == 8:
            nd.update(w=8, h=8, shape="dot")
    edges = []
    for i in range(1, n):
        for _ in range(rng.randint(1, 2)):
            j = rng.randrange(max(0, i - 6), i)
            edges.append({"id": f"e{len(edges)}", "from": f"n{j}", "to": f"n{i}"})
    for _ in range(n // 5):  # some arrows back up
        a, b = sorted(rng.sample(range(n), 2))
        edges.append({"id": f"e{len(edges)}", "from": f"n{b}", "to": f"n{a}"})
    return nodes, edges


class Ranking(unittest.TestCase):
    def test_a_loops_start_stays_on_top(self):
        self.assertEqual(back_edges(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")]), {2})

    def test_the_simplex_finds_the_shortest_arrows(self):
        rng = random.Random(7)
        for _ in range(60):
            ids = [f"n{i}" for i in range(rng.randint(3, 6))]
            E = [(ids[a], ids[b], 1, 1) for a, b in (sorted(rng.sample(range(len(ids)), 2)) for _ in range(6))]
            if len({x for e in E for x in e[:2]}) < len(ids):
                continue
            r = network_simplex(ids, E)
            self.assertTrue(all(r[v] - r[u] >= mn for u, v, mn, _ in E))
            cost = sum(r[v] - r[u] for u, v, _, _ in E)
            best = min(sum(c[ids.index(v)] - c[ids.index(u)] for u, v, _, _ in E)
                       for c in itertools.product(range(6), repeat=len(ids))
                       if all(c[ids.index(v)] - c[ids.index(u)] >= 1 for u, v, _, _ in E))
            self.assertEqual(cost, best)

    def test_pinned_ranks_are_kept_in_order(self):
        self.assertEqual(ranks(["a", "b", "c"], [], {"a": 0, "b": 5, "c": 2}), {"a": 0, "b": 2, "c": 1})


class Ordering(unittest.TestCase):
    def test_crossings_are_counted(self):
        L = Layering()
        for it in ("a", "b"):
            L.add(it, 0, "node")
        for it in ("c", "d"):
            L.add(it, 1, "node")
        L.link("a", "d")
        L.link("b", "c")
        self.assertEqual(crossings(L), 1)


class Tracks(unittest.TestCase):
    def test_a_run_coming_down_sits_above_one_leaving_at_its_x(self):
        a = channels.Run("a", [(100.0, "top"), (300.0, "bottom")])
        b = channels.Run("b", [(0.0, "top"), (100.0, "bottom")])
        channels.assign([b, a])
        self.assertLess(a.track, b.track)

    def test_runs_side_by_side_share_a_track(self):
        a = channels.Run("a", [(0.0, "top"), (50.0, "bottom")])
        b = channels.Run("b", [(200.0, "top"), (300.0, "bottom")])
        self.assertEqual(channels.assign([a, b]), 1)

    def test_three_runs_passing_columns_round_keep_the_rules_they_can(self):
        # a must sit above b, b above c and c above a: no order meets all three. The rule given up is
        # the loosest one (a's line and b's are 11 px apart, b's and c's 10); c leaves where a comes up
        a = channels.Run("a", [(100.0, "bottom"), (60.0, "top")])
        b = channels.Run("b", [(71.0, "bottom"), (160.0, "top")])
        c = channels.Run("c", [(150.0, "bottom"), (100.0, "top")])
        channels.assign([a, b, c])
        self.assertLess(c.track, a.track)
        self.assertLess(b.track, c.track)


class Layered(unittest.TestCase):
    def check(self, nodes, edges, groups=(), **options):
        res = layered.layout(nodes, edges, groups, options)
        boxes = {n["id"]: box(n, res) for n in nodes}
        ids = list(boxes)
        for a, b in itertools.combinations(ids, 2):  # no two boxes overlap
            p, q = boxes[a], boxes[b]
            self.assertFalse(p[0] < q[2] - 0.5 and q[0] < p[2] - 0.5 and p[1] < q[3] - 0.5 and q[1] < p[3] - 0.5, (a, b))
        for e in edges:
            r = res.routes[e["id"]]
            pts = r.points
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):  # every segment runs across or up and down
                self.assertTrue(abs(x0 - x1) < 0.01 or abs(y0 - y1) < 0.01, (e["id"], pts))
            for end, nid in ((pts[0], e["from"]), (pts[-1], e["to"])):  # and ends on its box
                b = boxes[nid]
                self.assertTrue(b[0] - 1 <= end[0] <= b[2] + 1 and b[1] - 1 <= end[1] <= b[3] + 1, (e["id"], end, b))
        for g in groups:  # a frame holds its members and no one else
            f = res.frames[g["id"]]
            for nid, b in boxes.items():
                inside = f[0] <= b[0] and b[2] <= f[2] and f[1] <= b[1] and b[3] <= f[3]
                apart = b[2] <= f[0] or f[2] <= b[0] or b[3] <= f[1] or f[3] <= b[1]
                self.assertTrue(inside if nid in g["members"] else apart, (g["id"], nid))
        return res

    def test_random_graphs_hold_the_invariants(self):
        for seed in range(12):
            nodes, edges = random_graph(seed, 8 + seed * 2)
            self.check(nodes, edges, trunk=bool(seed % 2))

    def test_groups_are_frames_with_only_their_members(self):
        nodes, edges = random_graph(3, 14)
        groups = [{"id": "g", "members": ["n2", "n3", "n4"]}, {"id": "h", "members": ["n8", "n9"]}]
        self.check(nodes, edges, groups)

    def test_back_edges_climb_beside_or_through_ports(self):
        nodes, edges = chain(5, back=[(4, 1)])
        side = self.check(nodes, edges)
        self.assertEqual(side.routes["b0"].sides[0] in ("w", "e"), True)
        ports = self.check(nodes, edges, back="ports")
        self.assertEqual(ports.routes["b0"].sides, ("n", "s"))

    def test_directions_turn_the_layout(self):
        nodes, edges = chain(4)
        tb = self.check(nodes, edges)
        lr = self.check(nodes, edges, direction="LR")
        self.assertGreater(tb.size[1], tb.size[0])
        self.assertGreater(lr.size[0], lr.size[1])

    def test_a_long_chain_wraps_near_the_aspect_and_a_short_one_does_not(self):
        nodes, edges = chain(30)
        res = self.check(nodes, edges, aspect=4 / 3)
        self.assertTrue(res.wrapped)
        w, h = res.size
        self.assertLess(abs(w / h - 4 / 3) / (4 / 3), 0.5)
        nodes, edges = chain(6)
        self.assertFalse(self.check(nodes, edges, aspect=4 / 3).wrapped)


class Pins(unittest.TestCase):
    """A pinned node in the layered layout (DESIGN 4.6): held at its x, what stands in its way pushed over."""

    def test_hold_pushes_what_stands_in_the_way(self):
        from diagonaldiagrams.layout import bk
        layers = [["a", "b", "c"], ["d"]]
        xs = {"a": 0.0, "b": 100.0, "c": 200.0, "d": 100.0}
        width = dict.fromkeys(xs, 60.0)

        def hold(targets, walls=None):
            return bk.hold(layers, xs, lambda u, v: 100.0, width, {}, targets, walls)
        out, blocked = hold([("a", 150.0)])
        self.assertEqual(([out[k] for k in "abcd"], blocked), ([150.0, 250.0, 350.0, 100.0], {}))
        out, blocked = hold([("a", 150.0), ("c", 150.0)])  # a held first: c can't come back past it
        self.assertEqual((out["c"], blocked), (350.0, {"c": "pin"}))
        out, blocked = hold([("b", 30.0)], walls=[0.0, None])  # a stands past the wall, so it moves first
        self.assertEqual(([out[k] for k in "abcd"], blocked), ([30.0, 130.0, 230.0, 100.0], {"b": "edge"}))

    def test_hold_moves_a_frames_borders_and_a_straight_arrow_whole(self):
        from diagonaldiagrams.layout import bk
        layers = [["a", "R1"], ["R2", "b"]]
        xs = {"a": 0.0, "R1": 50.0, "R2": 50.0, "b": 150.0}
        out, blocked = bk.hold(layers, xs, lambda u, v: 50.0, dict.fromkeys(xs, 0.0), {"R2": "R1"}, [("a", 100.0)])
        self.assertEqual(([out[k] for k in ("a", "R1", "R2", "b")], blocked), ([100.0, 150.0, 150.0, 200.0], {}))
        layers = [["a", "D1"], ["b", "D2"], ["D3"]]  # D1-D2 run straight, D2-D3 jog: only D2 follows D1
        xs = {"a": 0.0, "D1": 50.0, "b": 0.0, "D2": 50.0, "D3": 70.0}
        out, _ = bk.hold(layers, xs, lambda u, v: 50.0, dict.fromkeys(xs, 0.0), {}, [("a", 100.0)],
                         straight=[("D1", "D2"), ("D2", "D3")])
        self.assertEqual([out[k] for k in ("a", "D1", "b", "D2", "D3")], [100.0, 150.0, 0.0, 150.0, 70.0])

    def diamond(self):
        nodes = [{"id": i, "w": 160, "h": 56} for i in "abcd"]
        edges = [{"id": f"{u}{v}", "from": u, "to": v} for u, v in ("ab", "ac", "bd", "cd")]
        return nodes, edges

    def test_a_pin_holds_in_the_frame_of_the_places_before(self):
        nodes, edges = self.diamond()
        first = layered.layout(nodes, edges)
        prev = {i: x + 1000.0 for i, (x, _) in first.pos.items()}  # any frame: only differences count
        res = Layered.check(self, nodes, edges, prev=prev, pins={"c": prev["c"] + 300.0})
        shift = sum(prev[i] - res.pos[i][0] for i in "abd") / 3  # the result's frame, read off the other boxes
        self.assertAlmostEqual(res.pos["c"][0] + shift, prev["c"] + 300.0, places=6)
        self.assertEqual(res.blocked, {})

    def test_the_wall_keeps_a_pin_off_the_canvas_edge(self):
        nodes, edges = self.diamond()
        first = layered.layout(nodes, edges)
        prev = {i: x for i, (x, _) in first.pos.items()}
        res = Layered.check(self, nodes, edges, prev=prev, pins={"b": -500.0}, wall=30.0)
        shift = sum(prev[i] - res.pos[i][0] for i in "ad") / 2  # not c: the wall moved it along with b
        self.assertEqual(res.blocked, {"b": "edge"})
        self.assertAlmostEqual(res.pos["b"][0] + shift - 80, 30.0, places=6)  # its left edge, on the wall

    def test_rows_stay_where_they_stood_and_cuts_carry_over(self):
        nodes, edges = chain(4)
        first = layered.layout(nodes, edges)
        res = layered.layout(nodes, edges, (), {"row_y": {"n2": first.bands[2] + 100}})
        self.assertEqual([round(b - a, 6) for a, b in zip(first.bands, res.bands)], [0, 0, 100, 100])
        nodes, edges = chain(30)
        wrapped = layered.layout(nodes, edges, (), {"aspect": 4 / 3})
        self.assertTrue(wrapped.cuts)
        again = layered.layout(nodes, edges, (), {"aspect": 4 / 3, "cuts": wrapped.cuts})
        self.assertEqual(again.cuts, wrapped.cuts)
        self.assertFalse(layered.layout(nodes, edges, (), {"aspect": 4 / 3, "cuts": []}).wrapped)
        groups = [{"id": "g", "members": [f"n{wrapped.cuts[0]}", f"n{wrapped.cuts[0] + 1}"]}]  # a frame across the cut
        moved = layered.layout(nodes, edges, groups, {"aspect": 4 / 3, "cuts": wrapped.cuts})
        self.assertEqual(len(moved.cuts), len(wrapped.cuts))
        self.assertNotIn(wrapped.cuts[0], moved.cuts)


class Sequence(unittest.TestCase):
    def test_lifelines_make_room_for_the_widest_label_and_messages_step_down(self):
        from diagonaldiagrams.layout import sequence
        actors = [{"id": "a", "w": 140, "h": 52}, {"id": "b", "w": 140, "h": 70}, {"id": "c", "w": 140, "h": 52}]
        messages = [{"from": "a", "to": "b", "label_w": 300}, {"from": "b", "to": "b", "label_w": 900},
                    {"from": "b", "to": "c", "label_w": 20}]
        res = sequence.layout(actors, messages)
        self.assertEqual(res.x["b"] - res.x["a"], 336)  # 300 + 36: the self-call's label does not count
        self.assertEqual(res.x["c"] - res.x["b"], 336)
        self.assertEqual(res.box_h, 70)  # every box takes the tallest height
        self.assertEqual([res.y[1] - res.y[0], res.y[2] - res.y[1]], [52, 52])
        self.assertGreater(res.y[0], res.top + res.box_h)
        self.assertEqual(res.size[0], res.x["c"] + 70 + 70)
        self.assertGreater(res.size[1], res.y[-1])


class LabelsModule(unittest.TestCase):
    def test_longest_segment_and_place_label(self):
        from diagonaldiagrams.route import LabelPlacer, label_box, longest_segment, place_label
        pts = [(0, 0), (0, 100), (200, 100)]
        mx, my, vert = longest_segment(pts)
        self.assertEqual((mx, my, vert), (100.0, 100, False))
        lx, ly, v, flip = place_label(mx, my, vert, "status", pts, avoid=[])
        box = label_box(lx, ly, "status", v, flip)
        self.assertGreater(box[2], box[0])
        self.assertGreater(box[3], box[1])

        placer = LabelPlacer()
        lx2, ly2, v2, flip2 = placer.place("status", pts)
        self.assertEqual(len(placer.placed), 1)


class FuzzRegressions(unittest.TestCase):
    """Fuzz scenes that once failed the audit, drawn whole (tests/fuzz/gen.py makes the same spec
    from the same kind, seed and size)."""

    def check(self, kind, seed, n, pins=None):
        """pins: {node id: (x, y)}, pinned on the generated spec (DESIGN 4.6)."""
        import importlib.util
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location("fuzz_gen", os.path.join(here, "fuzz", "gen.py"))
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        made = gen.make(kind, seed, n)
        for node in made["nodes"]:
            if node["id"] in (pins or {}):
                node["pin"] = dict(zip("xy", pins[node["id"]]))
        self.draw(kind, made)

    def draw(self, kind, spec):
        import json
        import tempfile
        from diagonaldiagrams import api
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "spec.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(spec, f)
            code, out, _ = api.run([kind, path, "-o", os.path.join(d, "out.svg")])
        self.assertEqual(code, 0, out)

    def test_two_decisions_in_a_layer_branching_toward_each_other(self):
        self.check("flow", 20918, 43)  # their side runs met on the layer's middle line

    def test_a_crowded_decision_side_on_a_wide_figure(self):
        self.check("flow", 20246, 75)  # arrows stacked on one point of the side

    def test_three_back_edges_passing_columns_round_in_one_gap(self):
        self.check("flow", 402, 79)  # their tracks broke a rule, so two climbs shared a line

    def test_three_exits_on_a_decision_side_beside_a_box(self):
        self.check("flow", 40630, 51)  # the third turned down inside the box next to the decision

    def test_a_long_label_on_an_arrow_climbing_inside_a_frame(self):
        self.check("arch", 40349, 6)  # no room inside the frame, so the label sat on its border

    def test_a_label_beside_a_back_edge_climbing_past_a_column(self):
        self.check("flow", 40124, 37)  # boxes beside the climb and the canvas edge outside it

    def test_a_long_label_on_a_short_back_edge_at_the_canvas_edge(self):
        self.check("flow", 414, 67)  # another label inside the loop and the canvas edge outside it

    def test_lanes_inside_sibling_frames(self):
        self.check("flow", 330, 71)  # the frames took their members' lane hints and broke their own order

    def test_a_label_between_neighbors_with_a_back_edges_port_between(self):
        # the climb into the decision stood between it and Start, so the label got no room and sat on a box
        nodes = [("n0", "Start", "oval", 0), ("n1", "Load the account 1", "rect", 1), ("n2", "Parse the upload 2", "rect", 2),
                 ("n3", "Customer verified by the identity provider? (3)", "diamond", 0), ("n4", "End", "oval", 3)]
        edges = [("n0", "n1", ""), ("n1", "n2", ""), ("n2", "n3", ""), ("n3", "n4", "yes"), ("n0", "n3", "publishes"),
                 ("n2", "n0", "")]
        self.draw("flow", {"title": "Fuzz flow 5", "budget": False,
                           "nodes": [{"id": i, "name": t, "shape": s, "rank": r} for i, t, s, r in nodes],
                           "edges": [dict({"from": a, "to": b}, **({"label": t} if t else {})) for a, b, t in edges]})

    def test_a_decision_turning_down_beside_another_boxs_back_edge_port(self):
        # pins put a box's climb 1 px from where the decision's side exit turned down: one line for both
        self.check("flow", 11014, 27, pins={"n17": (965, 1279), "n13": (538, 980), "n16": (390, 1669)})

    def test_a_decision_turning_down_past_another_boxs_run_to_its_port(self):
        # kept off that box's port item, the turn went past it, onto the back edge's run at the same y
        self.check("flow", 70166, 175, pins={"n14": (7354, 1452)})


if __name__ == "__main__":
    unittest.main()


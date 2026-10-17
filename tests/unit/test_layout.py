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


class ContainerProtocol(unittest.TestCase):
    def test_measure_and_place_tree(self):
        from diagonaldiagrams.layout import Container, measure_tree, place_tree
        root = Container("root", layout="row")
        c1 = Container("c1", layout="column")
        c1.add({"id": "n1", "w": 100, "h": 50})
        c1.add({"id": "n2", "w": 100, "h": 50})
        c2 = {"id": "n3", "w": 120, "h": 80}
        root.add(c1)
        root.add(c2)
        size = measure_tree(None, root)
        self.assertGreater(size.w, 200)
        self.assertGreater(size.h, 80)
        p = place_tree(None, root)
        self.assertIn("n1", p.pos)
        self.assertIn("n2", p.pos)
        self.assertIn("n3", p.pos)
        # n1 should be above n2 in column c1
        self.assertLess(p.pos["n1"][1], p.pos["n2"][1])
        # c1 should be left of n3 in row root
        self.assertLess(p.pos["n1"][0], p.pos["n3"][0])

    def test_node_svg_content_resizes_node(self):
        from diagonaldiagrams.layout import Container, measure_tree
        node = {"id": "n1", "w": 40, "h": 40, "content": {"svg": "<g></g>", "viewBox": "0 0 100 80"}}
        root = Container("root", layout="stack")
        root.add(node)
        measure_tree(None, root)
        self.assertGreaterEqual(node["w"], 100)
        self.assertGreaterEqual(node["h"], 80)


class OtherKernels(unittest.TestCase):
    def test_grid_layout(self):
        from diagonaldiagrams.layout import Container, get_layout
        grid = get_layout("grid")
        c = Container("c", layout=grid)
        for i in range(6):
            c.add({"id": f"n{i}", "w": 100, "h": 50})
        s = grid.measure(None, c)
        p = grid.place(None, c, (0, 0, s.w, s.h))
        self.assertEqual(len(p.pos), 6)

    def test_tree_layout(self):
        from diagonaldiagrams.layout import Container, get_layout
        tree = get_layout("tree")
        c = Container("c", layout=tree, edges=[{"from": "root", "to": "c1"}, {"from": "root", "to": "c2"}])
        c.add({"id": "root", "w": 100, "h": 50})
        c.add({"id": "c1", "w": 80, "h": 40})
        c.add({"id": "c2", "w": 80, "h": 40})
        s = tree.measure(None, c)
        p = tree.place(None, c, (0, 0, s.w, s.h))
        self.assertLess(p.pos["root"][1], p.pos["c1"][1])
        self.assertLess(p.pos["c1"][0], p.pos["c2"][0])

    def test_radial_layout(self):
        from diagonaldiagrams.layout import Container, get_layout
        rad = get_layout("radial")
        c = Container("c", layout=rad)
        c.add({"id": "hub", "w": 60, "h": 60})
        for i in range(4):
            c.add({"id": f"s{i}", "w": 40, "h": 40})
        s = rad.measure(None, c)
        p = rad.place(None, c, (0, 0, s.w, s.h))
        self.assertEqual(len(p.pos), 5)
        # Hub should be at center
        hx, hy = p.pos["hub"]
        self.assertAlmostEqual(hx, s.w / 2.0, delta=1.0)
        self.assertAlmostEqual(hy, s.h / 2.0, delta=1.0)

    def test_force_layout(self):
        from diagonaldiagrams.layout import Container, get_layout
        force = get_layout("force")
        c = Container("c", layout=force, edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "c"}])
        c.add({"id": "a", "w": 80, "h": 40})
        c.add({"id": "b", "w": 80, "h": 40})
        c.add({"id": "c", "w": 80, "h": 40})
        s = force.measure(None, c)
        p = force.place(None, c, (0, 0, s.w, s.h))
        self.assertEqual(len(p.pos), 3)

    def test_manual_layout_detects_overlap(self):
        from diagonaldiagrams.layout import Container, get_layout
        man = get_layout("manual")
        c = Container("c", layout=man)
        c.add({"id": "a", "w": 100, "h": 50, "pin": {"x": 50, "y": 50}})
        c.add({"id": "b", "w": 100, "h": 50, "pin": {"x": 60, "y": 50}})
        s = man.measure(None, c)
        p = man.place(None, c, (0, 0, s.w, s.h))
        self.assertTrue(any(iss.get("code") == "overlap" for iss in p.issues))

    def test_sequence_layout(self):
        from diagonaldiagrams.layout import Container, get_layout
        seq = get_layout("sequence")
        c = Container("c", layout=seq, edges=[{"id": "m1", "from": "client", "to": "server"}])
        c.add({"id": "client", "name": "Client"})
        c.add({"id": "server", "name": "Server"})
        s = seq.measure(None, c)
        p = seq.place(None, c, (0, 0, s.w, s.h))
        self.assertIn("client", p.pos)
        self.assertIn("server", p.pos)
        self.assertIn("m1", p.routes)
        self.assertLess(p.pos["client"][0], p.pos["server"][0])

    def test_table_layout(self):
        from diagonaldiagrams.layout import Container, get_layout
        tbl = get_layout("table")
        c = Container("c", layout=tbl, edges=[{"id": "r1", "from": "users", "to": "orders"}])
        c.add({"id": "users", "columns": ["id", "email"]})
        c.add({"id": "orders", "columns": ["id", "user_id", "total"]})
        s = tbl.measure(None, c)
        p = tbl.place(None, c, (0, 0, s.w, s.h))
        self.assertIn("users.id:e", p.ports)
        self.assertIn("r1", p.routes)

    def test_timeaxis_layout(self):
        from diagonaldiagrams.layout import Container, get_layout
        ta = get_layout("timeaxis")
        c = Container("c", layout=ta)
        c.add({"id": "task1", "lane": 0, "data": {"start": 0, "end": 100}})
        c.add({"id": "task2", "lane": 1, "data": {"start": 50, "end": 150}})
        s = ta.measure(None, c)
        p = ta.place(None, c, (0, 0, s.w, s.h))
        self.assertLess(p.pos["task1"][1], p.pos["task2"][1])
        self.assertLess(p.pos["task1"][0], p.pos["task2"][0])


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

    def check(self, kind, seed, n):
        import importlib.util
        import json
        import tempfile
        from diagonaldiagrams import api
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location("fuzz_gen", os.path.join(here, "fuzz", "gen.py"))
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "spec.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(gen.make(kind, seed, n), f)
            code, out, _ = api.run([kind, path, "-o", os.path.join(d, "out.svg")])
        self.assertEqual(code, 0, out)

    def test_two_decisions_in_a_layer_branching_toward_each_other(self):
        self.check("flow", 20918, 43)  # their side runs met on the layer's middle line

    def test_a_crowded_decision_side_on_a_wide_figure(self):
        self.check("flow", 20246, 75)  # arrows stacked on one point of the side


if __name__ == "__main__":
    unittest.main()


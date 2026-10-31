"""The iso toolkit and the layer stack: the projection, how solids are ordered, the columns links
line up in, the spec checks, and the audit's depth checks firing on figures that break them.
Run: py -3 -m unittest discover tests/unit"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import iso, paint  # noqa: E402
from diagonaldiagrams.audit import _audit_drawn  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def stack(**over):
    spec = {"title": "t", "layers": [
        {"id": "a", "name": "Top", "items": [{"id": "p", "name": "P"}, {"id": "q", "name": "Q"}]},
        {"id": "b", "name": "Bottom", "items": [{"id": "r", "name": "R"}, {"id": "s", "name": "S"}, {"id": "u", "name": "U"}]}],
        "links": [{"from": "q", "to": "s"}]}
    spec.update(over)
    return spec


def audit(spec):
    info = {}
    iso.render(spec, info=info)
    d = info["drawing"]
    return _audit_drawn(d, d.tree())


def solid(dr, pr, key, box):
    pr.solids[key] = box
    dr.add(*iso.box_faces(box, key, ("#ffffff", "#eeeeee", "#dddddd"), "#333333", 1, owner=key))


class Toolkit(unittest.TestCase):
    def test_true_isometric(self):
        pr = iso.Iso(100, 100)
        x, y, d = pr(10, 0, 0)
        self.assertAlmostEqual(x, 100 + 10 * iso.COS)
        self.assertAlmostEqual(y, 105)
        self.assertEqual(pr(0, 0, 10)[:2], (100, 90))       # up is up the page
        self.assertGreater(pr(0, 0, 0)[2], pr(5, 5, 5)[2])  # the far corner is deeper

    def test_behind_reads_the_axis_that_keeps_two_boxes_apart(self):
        plate, block = (0, 0, 0, 100, 100, 10), (0, 0, 10, 20, 20, 30)
        self.assertEqual(iso.behind(plate, block), 1)
        self.assertEqual(iso.behind(block, plate), -1)
        self.assertEqual(iso.behind((0, 0, 0, 10, 10, 10), (5, 5, 5, 15, 15, 15)), 0)  # they cross

    def test_a_block_at_the_back_of_its_plate_is_drawn_after_the_plate(self):
        # mean depth gets this wrong: the block's faces are farther on average than the plate's top
        pr = iso.Iso(300, 50)
        dr = paint.Drawing(600, 400, "t", "d", projection=pr)
        solid(dr, pr, "block", (0, 0, 10, 20, 20, 30))
        solid(dr, pr, "plate", (0, 0, 0, 300, 300, 10))
        drawn = [e.attrs["data-solid"] for e in paint.project(dr.items, pr)]
        self.assertEqual(drawn, ["plate"] * 3 + ["block"] * 3)
        by_depth = [e.attrs["data-solid"] for e in paint.project(dr.items, lambda *p: pr(*p))]
        self.assertNotEqual(by_depth, drawn)  # what a plain mean-depth sort would draw

    def test_a_path_through_3d_points_is_projected_too(self):
        pr = iso.Iso(0, 0)
        e = paint.el("path", fill="none")
        e.pts3d = [(0, 0, 0), (0, 0, 10)]
        paint.project([e], pr)
        self.assertEqual(e.attrs["d"], "M0,0 L0,-10")

    def test_hull_and_clip(self):
        sq = iso.hull([(0, 0), (10, 0), (10, 10), (0, 10), (5, 5)])
        self.assertEqual(len(sq), 4)
        self.assertEqual(iso.clip((-5, 5), (15, 5), sq), (0.25, 0.75))
        self.assertIsNone(iso.clip((-5, -5), (-1, -1), sq))


class Columns(unittest.TestCase):
    def test_linked_items_stand_in_one_column(self):
        col, most = iso.columns(stack()["layers"], stack()["links"])
        self.assertEqual(most, 3)
        self.assertEqual(col["q"], col["s"])
        self.assertEqual(len({col[i] for i in "rsu"}), 3)

    def test_col_wins(self):
        spec = stack()
        spec["layers"][1]["items"][0]["col"] = 2
        col, _ = iso.columns(spec["layers"], spec["links"])
        self.assertEqual(col["r"], 2)


class Spec(unittest.TestCase):
    def errors(self, spec):
        return [e["msg"] for e in iso.check(spec)[0]]

    def test_the_example_is_clean(self):
        with open(os.path.join(HERE, "examples", "iso_platform.json"), encoding="utf-8") as f:
            self.assertEqual(iso.check(json.load(f)), ([], []))

    def test_mistakes(self):
        self.assertIn("iso needs a layers list", self.errors({}))
        self.assertTrue(any("used twice" in m for m in self.errors(stack(links=[], layers=[
            {"id": "a", "items": [{"id": "a"}]}]))))
        mid = {"id": "m", "items": [{"id": "v"}]}
        spec = stack(links=[{"from": "p", "to": "r"}])
        spec["layers"].insert(1, mid)
        self.assertTrue(any("skips a layer" in m for m in self.errors(spec)))
        self.assertTrue(any("same layer" in m for m in self.errors(stack(links=[{"from": "p", "to": "q"}]))))
        self.assertTrue(any("no item 'x'" in m for m in self.errors(stack(links=[{"from": "p", "to": "x"}]))))


class Audit(unittest.TestCase):
    def test_a_stack_passes_its_audit(self):
        rep = audit(stack())
        self.assertTrue(rep["ok"], rep["errors"])

    def test_the_showcase_passes_too(self):
        with open(os.path.join(HERE, "examples", "showcase", "ai_stack.json"), encoding="utf-8") as f:
            rep = audit(json.load(f))
        self.assertTrue(rep["ok"], rep["errors"])

    def test_a_link_label_behind_the_slab_in_front_is_hidden(self):
        spec = stack(links=[{"from": "q", "to": "r", "label": "far"}])
        spec["layers"][0]["items"][1]["col"] = 2
        spec["layers"][1]["items"][0]["col"] = 0
        codes = [(e["code"], e["msg"]) for e in audit(spec)["errors"]]
        self.assertIn(("hidden", "'far' is hidden behind 'a'"), codes)

    def test_labels_off_their_block_and_solids_that_cross(self):
        pr = iso.Iso(200, 300)
        dr = paint.Drawing(400, 400, "t", "d", projection=pr, kind="x", legible=True)
        solid(dr, pr, "back", (0, 0, 0, 60, 60, 20))
        solid(dr, pr, "cross", (40, 40, 0, 90, 90, 20))
        x, y = pr.flat(30, 30, 20)
        t = paint.el("text", "A very long label that spills", x=x, y=y, font_size=12, font_family="sans-serif",
                     fill="#333333", text_anchor="middle")
        t.attrs["data-face"] = "back"
        dr.add(t)
        dr.svg()
        codes = {e["code"] for e in _audit_drawn(dr, dr.tree())["errors"]}
        self.assertEqual({"spill", "overlap"}, codes)

    def test_a_label_behind_a_nearer_tower_is_hidden(self):
        pr = iso.Iso(200, 300)
        dr = paint.Drawing(400, 400, "t", "d", projection=pr, kind="x", legible=True)
        solid(dr, pr, "back", (0, 0, 0, 60, 60, 20))
        solid(dr, pr, "tower", (30, 61, 0, 90, 121, 100))  # in front of it (y), and tall
        x, y = pr.flat(30, 30, 20)
        t = paint.el("text", "Back", x=x, y=y, font_size=12, font_family="sans-serif", fill="#333333", text_anchor="middle")
        t.attrs["data-face"] = "back"
        dr.add(t)  # painted last, so it shows, but it stands where the tower is
        dr.svg()
        errors = _audit_drawn(dr, dr.tree())["errors"]
        self.assertEqual([(e["code"], e["msg"]) for e in errors], [("hidden", "'Back' is hidden behind 'tower'")])

    def test_an_arrow_drawn_over_a_block_it_does_not_join_crosses_it(self):
        pr = iso.Iso(200, 300)
        dr = paint.Drawing(400, 400, "t", "d", projection=pr, kind="x", legible=True)
        solid(dr, pr, "box", (0, 0, 0, 60, 60, 20))
        a, b = pr.flat(-40, 30, 10), pr.flat(100, 30, 10)
        dr.add(paint.el("path", d=f"M{a[0]},{a[1]} L{b[0]},{b[1]}", fill="none", stroke="#333333", marker_end="url(#a)"))
        dr.svg()
        codes = {e["code"] for e in _audit_drawn(dr, dr.tree())["errors"]}
        self.assertIn("through", codes)

    def test_the_same_verdict_from_the_file(self):
        from diagonaldiagrams.audit import _audit_file
        import tempfile
        svg, _, _ = iso.render(stack())
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.svg")
            with open(p, "w", encoding="utf-8") as f:
                f.write(svg)
            self.assertTrue(_audit_file(p)["ok"])


class Deterministic(unittest.TestCase):
    def test_same_bytes_twice(self):
        self.assertEqual(iso.render(stack())[0], iso.render(stack())[0])


if __name__ == "__main__":
    unittest.main()

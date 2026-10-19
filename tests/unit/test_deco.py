"""Named sides and borders. Run: py -3 -m unittest discover tests/unit"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import deco  # noqa: E402
from diagonaldiagrams.diagrams import render_flow  # noqa: E402
from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.style import parse  # noqa: E402


def ends(d):
    pts = [(float(a), float(b)) for a, b in re.findall(r"(-?[\d.]+),(-?[\d.]+)", d)]
    return pts[0], pts[-1]


class Geometry(unittest.TestCase):
    def test_square_sides_run_corner_to_corner(self):
        s = deco.rect_sides(0, 0, 100, 50, 0)
        self.assertEqual({k: ends(v) for k, v in s.items()},
                         {"top": ((0, 0), (100, 0)), "right": ((100, 0), (100, 50)), "bottom": ((100, 50), (0, 50)),
                          "left": ((0, 50), (0, 0))})

    def test_rounded_sides_meet_at_the_middle_of_each_corner_arc(self):
        s = deco.rect_sides(0, 0, 100, 50, (10, 20, 10, 20))
        k = deco.K
        top, right = ends(s["top"]), ends(s["right"])
        self.assertAlmostEqual(top[0][0], 10 * k, places=2)
        self.assertEqual(top[1], right[0])  # where one side stops, the next begins
        self.assertEqual(ends(s["left"])[1], top[0])
        self.assertIn("A20,20", s["top"])

    def test_a_radius_larger_than_the_box_is_clipped(self):
        s = deco.rect_sides(0, 0, 40, 20, 100)
        self.assertIn("A10,10", s["top"])

    def test_diamond_sides(self):
        s = deco.diamond_sides(50, 50, 100, 60)
        self.assertEqual(ends(s["top-left"]), ((0, 50), (50, 20)))
        self.assertEqual(ends(s["bottom-right"]), ((100, 50), (50, 80)))


class Declared(unittest.TestCase):
    def test_generic_sides_map_onto_a_diamond(self):
        b = parse.border("3px solid red")
        got = deco.declared({"border-top": b, "border-top-left": parse.border("1px dashed blue")}, "diamond")
        self.assertEqual((got["top-right"], got["top-left"]["style"]), (b, "dashed"))  # a named side wins

    def test_an_unknown_side_lists_the_real_ones(self):
        with self.assertRaises(SpecError) as cm:
            deco.declared({"border-top-left": parse.border("1px solid red")}, "oval")
        self.assertEqual((cm.exception.msg, cm.exception.fix, cm.exception.code),
                         ("an oval has no side 'top-left'", "its sides are: top, right, bottom, left", "unknown-side"))

    def test_border_styles(self):
        sides = {"top": parse.border("2px dashed red"), "right": parse.border("2px dotted red"),
                 "bottom": parse.border("3px double red"), "left": parse.border("none")}
        els = deco.borders(deco.rect_sides(0, 0, 10, 10, 0), sides, "#000", None, "#fff", "n")
        self.assertEqual([(e.attrs.get("stroke-dasharray"), e.attrs.get("stroke-linecap"), e.attrs["stroke"]) for e in els],
                         [("6,4", None, "red"), ("0,4", "round", "red"), (None, None, "red"), (None, None, "#fff")])


class Painted(unittest.TestCase):
    def test_no_border_keeps_one_outline_and_a_border_splits_it(self):
        flow = {"nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], "edges": [{"from": "a", "to": "b"}]}
        plain = render_flow(flow)[0]
        self.assertNotIn('stroke="none"', plain)
        styled = render_flow(dict(flow, style={"rules": {"#a": {"border-left": "4px solid #e11d48"}}}))[0]
        a_shape = [ln for ln in styled.splitlines() if 'data-node="a"' in ln][0]
        self.assertIn('stroke="none"', a_shape)
        self.assertEqual(styled.count('stroke="#e11d48" stroke-width="4"'), 1)
        self.assertEqual(len([ln for ln in styled.splitlines() if 'stroke="none"' in ln]), 1)  # b is untouched


if __name__ == "__main__":
    unittest.main()


class Decorations(unittest.TestCase):
    def draw(self, rules):
        flow = {"nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B", "shape": "diamond"}],
                "edges": [{"from": "a", "to": "b"}], "style": {"rules": rules}}
        return render_flow(flow)[0]

    def test_gradient_shadow_glow_pattern_and_opacity(self):
        svg = self.draw({"node": {"box-shadow": "0 2px 6px rgba(0,0,0,0.2)"},
                         "#a": {"fill": "linear-gradient(to bottom, #ffffff, rgba(79,70,229,0.5))", "opacity": 0.9},
                         "#b": {"glow": "accent", "pattern": "hatch"}})
        self.assertEqual(svg.count("<filter "), 2)  # one shadow (shared by both nodes) and one glow
        self.assertIn('flood-color="#000000" flood-opacity="0.2"', svg)  # the alpha counted once
        self.assertIn('stop-color="#4f46e5" stop-opacity="0.5"', svg)
        a = [ln for ln in svg.splitlines() if 'data-node="a"' in ln][0]
        self.assertTrue('fill="url(#gr-' in a and 'opacity="0.9"' in a)
        self.assertEqual(svg.count('role="deco.defs"'), 0)  # every definition moved into the figure's <defs>
        self.assertIn('<pattern id="pt-hatch-', svg)
        self.assertEqual(svg.count('fill="url(#pt-hatch-'), 1)

    def test_definitions_are_shared_and_ids_stable(self):
        rules = {"node": {"box-shadow": "0 2px 6px rgba(0,0,0,0.2)"}}
        one, two = self.draw(rules), self.draw(rules)
        self.assertEqual(one, two)
        self.assertEqual(one.count("<filter "), 1)

    def test_a_radius_per_corner_draws_a_path_that_still_outlines(self):
        from diagonaldiagrams.outline import outline, read_figure
        svg = self.draw({"#a": {"border-radius": "12 0 12 0"}})
        a = [ln for ln in svg.splitlines() if 'data-node="a"' in ln][0]
        self.assertTrue(a.startswith("<path"))
        nodes = {n["id"]: n for n in outline(read_figure(svg))["nodes"]}
        self.assertEqual(set(nodes), {"a", "b"})

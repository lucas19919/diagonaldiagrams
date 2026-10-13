"""The 3D hooks (PLAN P2.14, DESIGN 13): positions take a z, a shape may paint several faces,
items carry depth, and the projection stage is the identity in 2D. Everything 3D below is defined
in this file, as the 3D toolkit (P7) will define it, without touching the core.
Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import paint  # noqa: E402
from diagonaldiagrams.audit.svg_import import svg_import  # noqa: E402
from diagonaldiagrams.scene import check, normalize  # noqa: E402
from diagonaldiagrams.scene.patch import apply  # noqa: E402


def oblique(x, y, z):
    """A toy projection: up and right with height; depth grows away from the viewer (lower z)."""
    return x + 0.5 * z, y - 0.5 * z, -z


def slab(owner, x, y, w, h, z):
    """A toy solid's faces: a shape that returns several elements, each a polygon with 3D corners."""
    top = [(x, y, z), (x + w, y, z), (x + w, y + h, z), (x, y + h, z)]
    side = [(x + w, y, z), (x + w, y, z - 20), (x + w, y + h, z - 20), (x + w, y + h, z)]
    return [paint.Element("polygon", {"points": "0,0 1,0 1,1 0,1", "fill": "#ddd"}, owner=owner, role="solid.top", pts3d=top),
            paint.Element("polygon", {"points": "0,0 1,0 1,1 0,1", "fill": "#bbb"}, owner=owner, role="solid.side", pts3d=side)]


def drawing(projection=None):
    dr = paint.Drawing(400, 300, "slabs", "two slabs", projection=projection)
    dr.add(paint.el("rect", role="figure.paper", width=400, height=300, fill="#fff"))
    dr.add(*slab("near", 40, 40, 120, 80, 60))   # painted first, but nearer
    dr.add(*slab("far", 200, 120, 120, 80, 0))
    dr.add(paint.el("text", "label", role="figure.label", x=10, y=290))
    return dr


class Projection(unittest.TestCase):
    def test_identity_in_2d(self):
        svg = drawing().svg()
        self.assertNotIn("data-depth", svg)
        self.assertEqual(svg.count('points="0,0 1,0 1,1 0,1"'), 4)

    def test_faces_project_and_paint_back_to_front_in_their_own_places(self):
        root = ET.fromstring(drawing(oblique).svg())
        kids = [k for k in root if k.tag.split("}")[-1] not in ("title", "desc")]
        self.assertEqual(kids[0].get("fill"), "#fff")         # the paper stays first
        self.assertEqual(kids[-1].text, "label")              # the label stays last
        depths = [float(k.get("data-depth")) for k in kids[1:-1]]
        self.assertEqual(depths, sorted(depths, reverse=True))  # far faces before near ones
        self.assertEqual([k.get("data-depth") for k in kids[1:-1]], ["10", "0", "-50", "-60"])  # far side first
        self.assertEqual(kids[2].get("points"), "200,120 320,120 320,200 200,200")  # the far top, z = 0
        near_top = [k for k in kids[1:-1] if k.get("fill") == "#ddd" and k.get("data-depth") == "-60"][0]
        self.assertEqual(near_top.get("points"), "70,10 190,10 190,90 70,90")

    def test_the_display_list_carries_depth(self):
        svg = drawing(oblique).svg()
        dl = svg_import(ET.fromstring(svg), 400, 300)
        depths = sorted({i.depth for i in dl.items if i.kind == "shape" and i.tag == "polygon"})
        self.assertEqual(depths, [-60.0, -50.0, 0.0, 10.0])


class Positions(unittest.TestCase):
    def test_a_pin_may_carry_z(self):
        s, _ = normalize({"nodes": [{"id": "a", "pin": {"x": 1, "y": 2, "z": 3}}]})
        self.assertEqual(s.node("a").pin, {"x": 1, "y": 2, "z": 3})
        s, n, c = apply(s, [{"op": "pin", "id": "a", "x": 5, "y": 6, "z": 7}])
        self.assertEqual((n, c, s.node("a").pin), (1, [], {"x": 5, "y": 6, "z": 7}))

    def test_a_bad_pin_is_an_error(self):
        _, errors, _ = check({"nodes": [{"id": "a", "pin": {"x": "left", "y": 2}}, {"id": "b", "pin": {"y": 2}}]})
        self.assertEqual([e["path"] for e in errors], ["nodes[0].pin", "nodes[1].pin"])


if __name__ == "__main__":
    unittest.main()

"""What changed between two drawings (diff.py, DESIGN 21.4). Run: py -3 -m unittest discover tests/unit"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import api  # noqa: E402
from diagonaldiagrams.diff import diff, middles  # noqa: E402

FLOW = {"title": "Deploy", "nodes": [{"id": "a", "name": "Push", "rank": 0}, {"id": "b", "name": "Test", "rank": 1},
                                     {"id": "c", "name": "Fix", "rank": 2}, {"id": "d", "name": "Review", "rank": 2},
                                     {"id": "e", "name": "Ship", "rank": 3}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c", "label": "fail"}, {"from": "b", "to": "d"},
                  {"from": "d", "to": "e"}, {"from": "c", "to": "b", "label": "retry"}]}


def draw(spec, kind="flow"):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f)
        code, out, _ = api.run([kind, path, "-o", os.path.join(d, "o.svg")])
        assert code == 0, out
        with open(os.path.join(d, "o.svg"), encoding="utf-8") as f:
            return f.read()


def edited(**changes):
    spec = json.loads(json.dumps(FLOW))
    for nid, fields in changes.items():
        n = next(n for n in spec["nodes"] if n["id"] == nid)
        n.update(fields)
    return spec


class Diff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = draw(FLOW)

    def test_the_same_drawing_has_no_changes(self):
        d = diff(self.old, self.old)
        self.assertEqual((d["sentences"], d["shifted"]["count"]), ([], 0))

    def test_rename_and_recolor(self):
        d = diff(self.old, draw(edited(d={"name": "Peer review", "style": {"fill": "#fde2e2"}})))
        self.assertIn('Renamed "Review" to "Peer review"', d["sentences"])
        self.assertIn('Recolored "Peer review"', d["sentences"])
        self.assertEqual(d["nodes"]["renamed"], [{"id": "d", "was": "Review", "now": "Peer review"}])

    def test_a_move_to_another_row_names_the_rows(self):
        d = diff(self.old, draw(edited(c={"rank": 1})))
        self.assertIn('Moved "Fix" from row 3 to row 2', d["sentences"])
        self.assertEqual([m["id"] for m in d["nodes"]["moved"]], ["c"])

    def test_a_reorder_reads_the_row_and_does_not_count_as_a_shift(self):
        from diagonaldiagrams.outline import layout_rows, read_figure
        self.assertIn("row 3: Review | Fix", layout_rows(read_figure(self.old)))  # the layout's own order
        d = diff(self.old, draw(edited(c={"order": 0}, d={"order": 1})))
        self.assertIn("Row 3 now reads Fix | Review", d["sentences"])
        self.assertFalse({"c", "d"} & {s["id"] for s in d["shifted"]["boxes"]})

    def test_arrows_added_removed_and_relabeled(self):
        spec = edited()
        spec["edges"] = [e for e in spec["edges"] if e["to"] != "e"] + [{"from": "c", "to": "e"}]
        d = diff(self.old, draw(spec))
        self.assertIn('Added an arrow from "Fix" to "Ship"', d["sentences"])
        self.assertIn('Removed the arrow from "Review" to "Ship"', d["sentences"])

    def test_middles_read_an_html_page_too(self):
        m = middles("<html><body>" + self.old + "</body></html>")
        self.assertEqual(sorted(m), ["a", "b", "c", "d", "e"])


if __name__ == "__main__":
    unittest.main()

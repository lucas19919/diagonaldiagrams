"""Edits survive regeneration, or are reported.

A person edits a figure in its page, which hands over a patch; apply writes it into the spec. Then
the agent regenerates the spec from a changed brief, and the patch is applied again. Every
operation must either show in the new drawing or come back as a patch-conflict with a fix: none is
lost without a word. Run: py -3 -m unittest discover tests/unit
"""
import copy
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import api  # noqa: E402
from diagonaldiagrams.inputs.v1 import from_v1, to_v1  # noqa: E402
from diagonaldiagrams.scene import normalize  # noqa: E402
from diagonaldiagrams.scene.patch import apply  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(HERE, "examples", "flow_decision.json"), encoding="utf-8") as f:
    BRIEF = json.load(f)  # the agent's first spec, from the first brief

# what the person did in the page: Review before Fix, a new name, a color
PATCH = [{"op": "place", "id": "fix", "row": ["review", "fix"]},
         {"op": "text", "id": "review", "name": "Peer review", "was": "Review"},
         {"op": "style", "selector": "#fix", "set": {"fill": "#fde2e2"}}]


def patched(spec, ops=PATCH):
    scene, _ = normalize(from_v1(spec, "flow"))
    out, applied, conflicts = apply(scene, ops)
    _, v1, _ = to_v1(out)
    return v1, applied, conflicts


def drawn(spec):
    """(rows, the drawing's SVG) for a flow spec."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(spec, f)
        code, out, _ = api.run(["flow", path, "-o", os.path.join(d, "o.svg")])
        with open(os.path.join(d, "o.svg"), encoding="utf-8") as f:
            svg = f.read()
    assert code == 0, out
    return [r for r in json.loads(out)["layout"] if r.startswith("row ")], svg


def shows(spec):
    """Which of PATCH's operations the drawing of spec shows, by index."""
    rows, svg = drawn(spec)
    out = set()
    if any(re.fullmatch(r"row \d+: .*Peer review \| Fix.*", r) or re.fullmatch(r"row \d+: .*Review \| Fix.*", r) for r in rows):
        out.add(0)
    if 'data-node="review" data-label="Peer review"' in svg:
        out.add(1)
    if re.search(r'fill="#fde2e2"[^>]*data-node="fix"', svg):
        out.add(2)
    return out


def survived_or_reported(spec, ops=PATCH):
    """The regeneration check: each op shows or is a reported conflict."""
    v1, applied, conflicts = patched(spec, ops)
    seen = shows(v1)
    reported = {int(c["path"][6:-1]) for c in conflicts}
    return v1, applied, conflicts, all(k in seen or k in reported for k in range(len(ops))), seen


class Regeneration(unittest.TestCase):
    def test_the_edits_show_after_the_first_apply(self):
        v1, applied, conflicts, ok, seen = survived_or_reported(BRIEF)
        self.assertEqual((applied, conflicts, seen), (3, [], {0, 1, 2}))

    def test_applying_again_to_the_edited_spec_changes_nothing(self):
        once, _, _ = patched(BRIEF)
        twice, applied, conflicts = patched(once)
        self.assertEqual((twice, applied, conflicts), (once, 3, []))  # a patch can be kept and re-applied safely

    def test_a_brief_that_grows_keeps_every_edit(self):
        # the agent edits its own spec, which carries the person's edits, and adds a step
        v2 = copy.deepcopy(patched(BRIEF)[0])
        v2["nodes"].append({"id": "notify", "name": "Notify the team", "rank": 5})
        v2["edges"].append({"from": "ship", "to": "notify"})
        _, applied, conflicts, ok, seen = survived_or_reported(v2)
        self.assertTrue(ok)
        self.assertEqual((applied, conflicts, seen), (3, [], {0, 1, 2}))

    def test_a_spec_written_fresh_from_the_brief_takes_the_edits_again(self):
        # the agent regenerates from scratch: the edit fields are gone, the patch puts them back
        v3 = copy.deepcopy(BRIEF)
        v3["nodes"].append({"id": "notify", "name": "Notify the team", "rank": 5})
        v3["edges"].append({"from": "ship", "to": "notify"})
        self.assertEqual(shows(v3), set())
        _, applied, conflicts, ok, seen = survived_or_reported(v3)
        self.assertTrue(ok)
        self.assertEqual((applied, seen), (3, {0, 1, 2}))

    def test_edits_the_new_brief_contradicts_are_reported_with_a_fix(self):
        # the new brief drops Fix and renames Review: those edits can't hold, and say so
        v4 = copy.deepcopy(BRIEF)
        v4["nodes"] = [n for n in v4["nodes"] if n["id"] != "fix"]
        v4["edges"] = [e for e in v4["edges"] if "fix" not in (e["from"], e["to"])]
        next(n for n in v4["nodes"] if n["id"] == "review")["name"] = "Approval"
        _, applied, conflicts, ok, _ = survived_or_reported(v4)
        self.assertTrue(ok)
        self.assertEqual((applied, sorted(c["path"] for c in conflicts)), (0, ["patch[0]", "patch[1]", "patch[2]"]))
        self.assertTrue(all(c["code"] == "patch-conflict" and c["fix"] for c in conflicts))


if __name__ == "__main__":
    unittest.main()

"""Stories: views of one figure (story.py, DESIGN 21.2). Run: py -3 -m unittest discover tests/unit"""
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.diff import middles  # noqa: E402
from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.mermaid import load_spec  # noqa: E402
from diagonaldiagrams.story import DIM, build, camera, frames, read_story, split  # noqa: E402
from diagonaldiagrams.style.styler import Styler  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLATFORM = os.path.join(HERE, "examples", "agent_platform.json")


def plan(views):
    spec = load_spec(PLATFORM, "arch")
    return frames({"views": views}, spec, "arch", Styler(spec, "arch"))


class Selectors(unittest.TestCase):
    def test_a_list_splits_at_top_level_commas_only(self):
        self.assertEqual(split("#a, node:not(.x, .y), edge[label='a, b']"), ["#a", "node:not(.x, .y)", "edge[label='a, b']"])


class Frames(unittest.TestCase):
    def test_highlight_beats_dim_and_hide_beats_both(self):
        out, warn = plan([{"id": "v", "dim": "node", "highlight": "#agent, #llm", "hide": "#llm"}])
        looks = out[0]["looks"]
        self.assertEqual((looks[("nodes", "web")]["opacity"], looks[("nodes", "agent")]["opacity"]), (DIM, 1))
        self.assertEqual((looks[("nodes", "agent")]["stroke"], looks[("nodes", "llm")]["opacity"]), ("accent", 0))
        self.assertEqual(warn, [])

    def test_reveal_shows_one_selector_per_step_and_arrows_once_both_ends_show(self):
        out, _ = plan([{"id": "v", "dim": "node, edge", "reveal": ["#web", "#gw", "#agent"]}])
        self.assertEqual([f["steps"] for f in out], [3, 3, 3])
        first, last = out[0]["looks"], out[2]["looks"]
        self.assertEqual((first[("nodes", "web")]["opacity"], first[("nodes", "gw")]["opacity"]), (1, 0))
        self.assertEqual(first[("edges", "gw->agent:run")]["opacity"], 0)  # its ends are hidden
        self.assertEqual(last[("edges", "gw->agent:run")]["opacity"], 1)   # both ends revealed: full strength
        self.assertEqual(last[("nodes", "memory")]["opacity"], DIM)        # never revealed: dimmed as asked

    def test_a_selector_that_matches_nothing_is_a_warning_and_a_bad_one_an_error(self):
        _, warn = plan([{"id": "v", "focus": "#nope"}])
        self.assertIn("matches nothing", warn[0]["msg"])
        with self.assertRaises(SpecError) as e:
            plan([{"id": "v", "dim": "node:hover"}])
        self.assertIn("view 'v' dim", e.exception.msg)

    def test_the_camera_frames_its_elements_and_stays_on_the_canvas(self):
        spec = load_spec(PLATFORM, "arch")
        from diagonaldiagrams.diagrams import render_arch
        svg, W, H = render_arch(spec)
        box = camera(svg, {"nodes": ["agent"]})
        m = middles(svg)["agent"]
        self.assertTrue(box[0] < m[0] < box[0] + box[2] and box[1] < m[1] < box[1] + box[3])
        self.assertGreaterEqual(box[2], 280)
        self.assertTrue(box[0] >= 0 and box[1] >= 0 and box[0] + box[2] <= W and box[1] + box[3] <= H)
        self.assertIsNone(camera(svg, {}))


class Build(unittest.TestCase):
    def test_every_frame_shares_one_layout_and_one_structure(self):
        with tempfile.TemporaryDirectory() as d:
            out = build(os.path.join(HERE, "examples", "story_platform.json"), os.path.join(d, "story.html"))
            self.assertTrue(out["ok"], out)
            self.assertEqual(([v["steps"] for v in out["views"]], out["frames"]), ([1, 1, 4, 1], 7))
            with open(out["html"], encoding="utf-8") as f:
                page = f.read()
        data = json.loads(page.split('<script type="application/json" id="dd-story">', 1)[1].split("</script>", 1)[0])
        svgs = [f["svg"] for f in data["frames"]]
        shapes = [re.findall(r"<(\w+)[ />]", s) for s in svgs]
        self.assertTrue(all(s == shapes[0] for s in shapes))  # the page moves between frames element by element
        places = [middles(s) for s in svgs]
        self.assertTrue(all(p == places[0] for p in places))  # looks change, the layout does not
        self.assertEqual([bool(f["viewBox"]) for f in data["frames"]], [False, True, False, False, False, False, True])

    def test_story_errors_name_the_fix(self):
        with tempfile.TemporaryDirectory() as d:
            cases = [{"views": [{}]}, {"figure": {"type": "arch", "spec": "x.json"}, "views": []},
                     {"figure": {"type": "arch", "spec": "x.json"}, "views": [{"id": "a"}, {"id": "a"}]},
                     {"figure": {"type": "arch", "spec": "x.json"}, "views": [{"reveal": "#a"}]}]
            for k, story in enumerate(cases):
                path = os.path.join(d, f"s{k}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(story, f)
                with self.assertRaises(SpecError, msg=story) as e:
                    read_story(path)
                self.assertTrue(e.exception.fix)


if __name__ == "__main__":
    unittest.main()

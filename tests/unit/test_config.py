"""Project config and the brand policy (PLAN P3.12, DESIGN 22.4). Run: py -3 -m unittest discover tests/unit"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import config  # noqa: E402
from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.style.styler import Styler  # noqa: E402

SPEC = {"nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], "edges": [{"from": "a", "to": "b"}]}


def project(toml, files=None):
    root = tempfile.mkdtemp(prefix="dd-config-")
    with open(os.path.join(root, config.NAME), "w", encoding="utf-8") as f:
        f.write(toml)
    for name, body in (files or {}).items():
        os.makedirs(os.path.dirname(os.path.join(root, name)), exist_ok=True)
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            json.dump(body, f)
    os.makedirs(os.path.join(root, "specs", "deep"))
    return root


class Loading(unittest.TestCase):
    def setUp(self):
        self.env = os.environ.pop(config.ENV, None)

    def tearDown(self):
        if self.env is not None:
            os.environ[config.ENV] = self.env
        else:
            os.environ.pop(config.ENV, None)

    def test_found_by_walking_up_from_the_spec(self):
        root = project('[defaults]\ncorners = "sharp"\n')
        cfg = config.load(os.path.join(root, "specs", "deep"))
        self.assertEqual((cfg.paths, cfg.defaults), ([os.path.join(root, config.NAME)], {"corners": "sharp"}))

    def test_sheets_and_policy_are_read_beside_the_config(self):
        root = project('[style]\nsheets = ["brand/house.json"]\npolicy = "brand/policy.json"\n',
                       {"brand/house.json": {"rules": {"node": {"stroke-width": 2}}},
                        "brand/policy.json": {"name": "policy", "rules": {"node": {"stroke": "ink"}}}})
        cfg = config.load(root)
        self.assertEqual([s["name"] for s in cfg.all_sheets()], ["house.json", "policy"])
        self.assertTrue(cfg.all_sheets()[-1]["policy"])

    def test_mistakes_are_named(self):
        with self.assertRaises(SpecError) as cm:
            config.load(project("[stlye]\nsheets = []\n"))
        self.assertIn("did you mean [style]", cm.exception.msg)
        with self.assertRaises(SpecError):
            config.load(project("[style]\nsheet = []\n"))

    def test_an_organization_narrows_what_a_project_allows(self):
        root = project('[palette]\nallowed = ["ink", "#ff0000", "#00ff00"]\n')
        org = os.path.join(project('[palette]\nallowed = ["ink", "#00ff00"]\n'), config.NAME)
        os.environ[config.ENV] = org
        self.assertEqual(config.load(root).palette, {"ink", "#00ff00"})


class Policy(unittest.TestCase):
    def test_the_policy_wins_and_overriding_it_is_named(self):
        policy = {"name": "policy", "policy": True, "tokens": {"accent": "#7c3aed"}, "rules": {"node": {"stroke": "ink"}}}
        agent = {"name": "agent", "tokens": {"accent": "#ff0000"}, "rules": {"#a": {"stroke": "#e11d48"}}}
        sty = Styler(dict(SPEC, style=agent), "flow", sheets=[policy])
        self.assertEqual((sty.node("a")["stroke"], sty.token("accent")), ("#2d3142", "#7c3aed"))
        issues = sty.off_brand()
        self.assertEqual([i["msg"] for i in issues],
                         ["stylesheet 'agent', rule '#a' sets stroke, which stylesheet 'policy', rule 'node' locks"])

    def test_colors_and_fonts_outside_the_config(self):
        agent = {"name": "agent", "rules": {"#a": {"fill": "#ffedd5"}, "#b": {"fill": "accent-tint"},
                                            "node::label": {"font-family": "Comic Sans MS"}}}
        issues = Styler(dict(SPEC, style=agent), "flow").off_brand(palette=["ink", "card", "accent-tint"],
                                                                   fonts={"system-ui", "georgia"})
        msgs = sorted(i["msg"] for i in issues)
        self.assertEqual(len(msgs), 2)
        self.assertTrue(any("#ffedd5" in m for m in msgs))
        self.assertTrue(any("comic sans ms" in m for m in msgs))

    def test_the_defaults_are_not_judged(self):
        self.assertEqual(Styler(SPEC, "flow").off_brand(palette=["#000000"], fonts={"nothing"}), [])


if __name__ == "__main__":
    unittest.main()

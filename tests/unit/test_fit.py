"""Where a figure goes (size.fit, --fit, Mermaid's fit:): the wrap target and the widest it draws.
Run: py -3 -m unittest discover tests/unit"""
import itertools
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from diagonaldiagrams import api  # noqa: E402
from diagonaldiagrams.diagrams import ASPECT, _fit, render_arch, render_flow, render_schema  # noqa: E402
from diagonaldiagrams.layout import layered  # noqa: E402
from diagonaldiagrams.mermaid import _mermaid_spec  # noqa: E402


def flow(n, fit=None):
    spec = {"title": "A long flow", "budget": False,
            "nodes": [{"id": f"s{i}", "name": f"Step {i}"} for i in range(n)],
            "edges": [{"from": f"s{i}", "to": f"s{i + 1}"} for i in range(n - 1)]}
    if fit:
        spec["size"] = {"fit": fit}
    return spec


def fan_out(fit=None):
    """A gateway calling eight services in one layer, which then all write to one store."""
    names = ["Orders", "Payments", "Catalog", "Search", "Accounts", "Shipping", "Reviews", "Pricing"]
    spec = {"title": "Eight services", "budget": False,
            "nodes": [{"id": "gw", "name": "API gateway", "layer": 0}] +
                     [{"id": f"s{i}", "name": f"{n} service", "layer": 1} for i, n in enumerate(names)] +
                     [{"id": "db", "name": "Postgres", "layer": 2}],
            "edges": [{"from": "gw", "to": f"s{i}"} for i in range(8)] + [{"from": f"s{i}", "to": "db"} for i in range(8)]}
    if fit:
        spec["size"] = {"fit": fit}
    return spec


def schema(fit=None):
    cols = [{"name": "id", "type": "uuid", "pk": True}, {"name": "parent_id", "type": "uuid", "fk": True},
            {"name": "name", "type": "text"}]
    tables = [{"id": t, "name": t, "columns": cols} for t in ("users", "teams", "projects", "tasks")]
    rel = [("teams", "users"), ("projects", "teams"), ("tasks", "projects")]
    spec = {"title": "Work tracker", "tables": tables,
            "relations": [{"from": a, "from_col": "parent_id", "to": b, "to_col": "id", "label": "1:N"} for a, b in rel]}
    if fit:
        spec["size"] = {"fit": fit}
    return spec


class FitSize(unittest.TestCase):
    def test_each_fit_sets_a_wrap_target_and_a_widest(self):
        self.assertEqual(_fit({}), (ASPECT, None))  # slide, today's default
        self.assertEqual(_fit({"size": {"fit": "slide"}}), (ASPECT, None))
        self.assertEqual(_fit({"size": {"fit": "column"}}), (None, 640))
        aspect, most = _fit({"size": {"fit": "page"}})
        self.assertLess(aspect, 1.0)  # a portrait page
        self.assertEqual(most, 640)

    def test_size_aspect_and_width_win_over_the_fit(self):
        self.assertEqual(_fit({"size": {"fit": "column", "aspect": "16:9"}}), (16 / 9, 640))
        self.assertEqual(_fit({"size": {"fit": "column", "width": 800}}), (None, 800))
        self.assertEqual(_fit({"size": {"aspect": 2}}), (2.0, None))


class Kernel(unittest.TestCase):
    def test_a_layer_too_wide_for_max_width_spreads_over_rows(self):
        nodes = [{"id": "gw", "w": 160, "h": 56}] + [{"id": f"s{i}", "w": 160, "h": 56} for i in range(8)]
        edges = [{"id": f"e{i}", "from": "gw", "to": f"s{i}"} for i in range(8)]
        wide = layered.layout(nodes, edges, (), {})
        narrow = layered.layout(nodes, edges, (), {"max_width": 580.0})
        self.assertGreater(wide.size[0], 1400)
        self.assertLess(narrow.size[0], wide.size[0] / 2)
        self.assertLess(layered.room(narrow.size, {"max_width": 580.0}), layered.room(wide.size, {"max_width": 580.0}))
        self.assertGreater(len({narrow.rank[f"s{i}"] for i in range(8)}), 1)
        boxes = {n["id"]: (narrow.pos[n["id"]][0] - 80, narrow.pos[n["id"]][1] - 28,
                           narrow.pos[n["id"]][0] + 80, narrow.pos[n["id"]][1] + 28) for n in nodes}
        for a, b in itertools.combinations(boxes, 2):  # no two boxes overlap
            p, q = boxes[a], boxes[b]
            self.assertFalse(p[0] < q[2] - 0.5 and q[0] < p[2] - 0.5 and p[1] < q[3] - 0.5 and q[1] < p[3] - 0.5, (a, b))
        for r in narrow.routes.values():  # and every arrow still runs across or up and down
            for (x0, y0), (x1, y1) in zip(r.points, r.points[1:]):
                self.assertTrue(abs(x0 - x1) < 0.01 or abs(y0 - y1) < 0.01, r.points)

    def test_a_layer_that_rows_would_only_make_taller_stays_whole(self):
        # four boxes are a little too wide; two rows of two would add more height than the width they
        # save (layered.room), so the layer stays one row and the figure is shrunk instead
        nodes = [{"id": "gw", "w": 150, "h": 56}] + [{"id": f"s{i}", "w": 150, "h": 56} for i in range(4)]
        edges = [{"id": f"e{i}", "from": "gw", "to": f"s{i}"} for i in range(4)]
        res = layered.layout(nodes, edges, (), {"max_width": 580.0})
        self.assertGreater(res.size[0], 580)
        self.assertEqual({res.rank[f"s{i}"] for i in range(4)}, {1})

    def test_a_layer_that_fits_stays_one_row(self):
        nodes = [{"id": "gw", "w": 160, "h": 56}] + [{"id": f"s{i}", "w": 160, "h": 56} for i in range(3)]
        edges = [{"id": f"e{i}", "from": "gw", "to": f"s{i}"} for i in range(3)]
        res = layered.layout(nodes, edges, (), {"max_width": 580.0})
        self.assertEqual({res.rank[f"s{i}"] for i in range(3)}, {1})

    def test_over_runs_arrows_within_a_layer_over_the_top_neighbors_too(self):
        nodes = [{"id": i, "w": 120, "h": 60, "rank": 0} for i in "abc"]
        edges = [{"id": "ab", "from": "a", "to": "b", "from_at": -10.0, "to_at": 20.0},
                 {"id": "ac", "from": "a", "to": "c"}]
        plain = layered.layout(nodes, edges, (), {})
        over = layered.layout(nodes, edges, (), {"over": True})
        self.assertEqual(plain.routes["ab"].sides, ("e", "w"))  # neighbors: straight across
        self.assertEqual(over.routes["ab"].sides, ("n", "n"))
        ax, bx = over.pos["a"][0], over.pos["b"][0]
        self.assertAlmostEqual(over.routes["ab"].points[0][0], ax - 10.0, delta=0.01)  # its ends stay pinned
        self.assertAlmostEqual(over.routes["ab"].points[-1][0], bx + 20.0, delta=0.01)


class Renders(unittest.TestCase):
    def test_a_long_flow_wraps_on_a_slide_and_runs_one_strip_in_a_column(self):
        info = {}
        svg, w, h = render_flow(flow(30), info=info)
        self.assertIn("columns", info)  # wrapped
        info = {}
        svg, w, h = render_flow(flow(30, "column"), info=info)
        self.assertNotIn("columns", info)
        self.assertLessEqual(w, 640)
        self.assertGreater(h, 4 * w)
        info = {}
        svg, w, h = render_flow(flow(30, "page"), info=info)
        self.assertIn("columns", info)
        self.assertLess(w / h, 1.0)  # toward a portrait page

    def test_a_wide_architecture_layer_splits_into_rows_in_a_column(self):
        svg, w, h = render_arch(fan_out())
        self.assertGreater(w, 1000)
        info = {}
        svg, w, h = render_arch(fan_out("column"), info=info)
        self.assertLessEqual(w, 640)
        self.assertGreater(len(info["layers"]), 3)

    def test_grouped_architecture_keeps_its_layers_where_rows_take_more_of_the_column(self):
        # dealt into rows it ran three screens tall with arrows wrapping around them, and lost every
        # blind judgment in a column (bench-quality-fit); whole and shrunk, it takes less of the column
        with open(os.path.join(ROOT, "examples", "checkout_groups.json"), encoding="utf-8") as f:
            spec = json.load(f)
        slide, column = {}, {}
        render_arch(spec, info=slide)
        svg, w, h = render_arch(dict(spec, size={"fit": "column"}), info=column)
        self.assertEqual(column["layers"], slide["layers"])
        self.assertGreater(w, 640)
        self.assertLess(h, 1000)

    def test_a_schema_too_wide_for_a_column_stacks_its_tables(self):
        info = {}
        svg, w, h = render_schema(schema(), info=info)
        self.assertGreater(w, 640)
        self.assertGreater(len(info["layers"]), 1)  # side by side
        info = {}
        svg, w, h = render_schema(schema("column"), info=info)
        self.assertLessEqual(w, 640)
        self.assertEqual(len(info["layers"]), 1)  # one column of tables
        self.assertEqual(sorted(info["layers"][0]), ["projects", "tasks", "teams", "users"])

    def test_the_command_line_draws_and_audits_every_fit(self):
        with tempfile.TemporaryDirectory() as d:
            for kind, spec in (("flow", flow(24)), ("arch", fan_out()), ("schema", schema())):
                path = os.path.join(d, kind + ".json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(spec, f)
                for fit in ("slide", "page", "column"):
                    out = os.path.join(d, f"{kind}-{fit}.svg")
                    code, stdout, _ = api.run([kind, path, "-o", out, "--fit", fit])
                    self.assertEqual(code, 0, (kind, fit, stdout))
                    with open(os.path.splitext(out)[0] + ".graph.json", encoding="utf-8") as f:
                        self.assertEqual(json.load(f).get("fit"), fit)  # export draws it again the same way
            code, stdout, _ = api.run(["flow", path, "-o", os.path.join(d, "x.svg"), "--fit", "poster"])
            self.assertNotEqual(code, 0)


class Mermaid(unittest.TestCase):
    def test_front_matter_says_where_the_figure_goes(self):
        spec = _mermaid_spec("---\ntitle: Deploy\nfit: column\n---\nflowchart TD\n  A --> B\n")
        self.assertEqual(spec["size"], {"fit": "column"})
        self.assertEqual(spec["title"], "Deploy")
        self.assertNotIn("_errors", spec)
        spec = _mermaid_spec("erDiagram\n  A ||--o{ B : has\n")
        self.assertNotIn("size", spec)

    def test_a_fit_it_does_not_know_is_an_error_with_a_fix(self):
        spec = _mermaid_spec("---\nfit: poster\n---\nflowchart TD\n  A --> B\n")
        self.assertIn("poster", spec["_errors"][0]["msg"])
        self.assertIn("column", spec["_errors"][0]["fix"])

    def test_validate_checks_a_spec_size_fit(self):
        from diagonaldiagrams.validate import _validate_spec_dict
        errors, warnings = [], []
        _validate_spec_dict(flow(3, "poster"), errors, warnings, "flow")
        self.assertTrue(any("size.fit" in e["msg"] for e in errors), errors)
        errors = []
        _validate_spec_dict(flow(3, "column"), errors, warnings, "flow")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

"""The verdict's layout rows (outline.py): the layout's own layers when the renderer gives them.
Run: py -3 -m unittest discover tests/unit"""
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import api  # noqa: E402
from diagonaldiagrams.outline import layout_rows, read_figure  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verdict(kind, path, *flags):
    with tempfile.TemporaryDirectory() as d:
        out_svg = os.path.join(d, "o.svg")
        code, out, _ = api.run([kind, path, "-o", out_svg, *flags])
        with open(out_svg, encoding="utf-8") as f:
            svg = f.read()
    assert code == 0, out
    return json.loads(out), svg


class Rows(unittest.TestCase):
    def test_a_wrapped_flow_lists_its_layers_and_where_the_columns_break(self):
        v, svg = verdict("flow", os.path.join(HERE, "tests", "golden", "inputs", "flows", "flow-20.json"), "--outline")
        rows = [r for r in v["layout"] if r.startswith("row ")]
        by_height = [r for r in layout_rows(read_figure(svg)) if r.startswith("row ")]
        self.assertGreater(len(rows), len(by_height))  # heights mix the columns: fewer, wider rows
        wrapped = [r for r in v["layout"] if r.startswith("wrapped into ")]
        self.assertEqual(len(wrapped), 1)
        self.assertRegex(wrapped[0], r"^wrapped into (\d+) columns: rows 1-\d+(, rows \d+-\d+)+$")
        breaks = [tuple(map(int, m)) for m in re.findall(r"rows (\d+)-(\d+)", wrapped[0])]
        self.assertEqual((breaks[0][0], breaks[-1][1]), (1, len(rows)))
        names = [n for r in rows for n in r.split(": ", 1)[1].split(" | ")]
        self.assertEqual(len(names), len(read_figure(svg)["nodes"]))  # every box once
        self.assertEqual({n["row"] for n in v["outline"]["nodes"]}, set(range(1, len(rows) + 1)))

    def test_a_schema_lists_its_columns_of_tables(self):
        v, _ = verdict("schema", os.path.join(HERE, "examples", "schema_ecommerce.json"), "--outline")
        self.assertEqual(v["layout"], ["tables: users, orders, order_items", "column 1: users", "column 2: orders",
                                       "column 3: order_items"])
        self.assertEqual({n["column"] for n in v["outline"]["nodes"]}, {1, 2, 3})

    def test_an_unwrapped_flow_reads_as_before(self):
        v, svg = verdict("flow", os.path.join(HERE, "examples", "flow_decision.json"))
        self.assertEqual(v["layout"], layout_rows(read_figure(svg)))  # one layer, one height


if __name__ == "__main__":
    unittest.main()

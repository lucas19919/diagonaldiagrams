"""The render commands' quick argument reader (cli._quick) against argparse (cli._parse): the same
arguments for what it reads, and None (argparse decides) for everything else.
Run: py -3 -m unittest discover tests/unit"""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import cli  # noqa: E402

READ = [
    ["flow", "s.json", "-o", "o.html"],
    ["flow", "-o", "o.html", "s.json"],
    ["flow", "s.json", "-o", "o.html", "--auto", "--no-audit", "--outline", "--embed-fonts", "--style", "a.json",
     "--style=b.json", "--caption", "A caption", "--figure=Fig. 2", "--font", "Inter", "--corners", "sharp",
     "--theme", "ink", "--theme-file", "t.json"],
    ["mermaid", "-", "-o", "out/x.html"],
    ["mermaid", "-o", "-", "a.mmd"],
    ["arch", "-s", '{"nodes": []}', "-o", "o.svg"],
    ["seq", "--string=sequenceDiagram", "-o", "out"],
    ["schema", "s.json", "-o", "o.html", "-o", "p.html", "--corners=rounded", "--corners", "editorial"],
    ["flow", "--spec-text", "flowchart TD", "-o", ""],
    ["flow", "-o", "o.html"],
]
LEFT = [  # argparse's to read (or to refuse)
    [], ["--version"], ["-h"], ["flow", "-h"], ["flow", "--help"], ["bar", "x.csv", "-o", "o.html"],
    ["flow", "s.json"], ["flow", "a.json", "b.json", "-o", "o"], ["flow", "--cap", "x", "-o", "o"],
    ["flow", "--theme", "nope", "-o", "o"], ["arch", "--auto", "-o", "o"], ["flow", "-o", "-x"],
    ["flow", "-oout.html"], ["flow", "-o=out.html"], ["flow", "--no-audit=1", "-o", "o"], ["flow", "--caption=", "-o", "o"],
    ["flow", "--caption", "-o", "o"], ["flow", "s.json", "-o"], ["flow", "--", "s.json", "-o", "o"], ["flow", "-5", "-o", "o"],
    ["flow", "s.json", "--layout-engine", "v1", "-o", "o"],  # gone with the v1 engine: argparse refuses it
]


def parsed(argv):
    saved = sys.argv
    sys.argv = ["diagonaldiagrams", *argv]
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return vars(cli._parse())
    finally:
        sys.argv = saved


class QuickArgs(unittest.TestCase):
    def test_what_it_reads_argparse_reads_the_same(self):
        for argv in READ:
            with self.subTest(argv=argv):
                quick = cli._quick(argv)
                self.assertIsNotNone(quick)
                self.assertEqual(vars(quick), parsed(argv))

    def test_everything_else_is_left_to_argparse(self):
        for argv in LEFT:
            with self.subTest(argv=argv):
                self.assertIsNone(cli._quick(argv))

    def test_a_flow_loads_none_of_what_it_does_not_use(self):
        """A whole flow call: no argparse (and the help formatter's shutil and _colorize), no xml.etree
        (the verdict reads the drawing in memory), no describe or chart catalog."""
        import subprocess
        import tempfile
        here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        spec = os.path.join(here, "tests", "golden", "inputs", "flows", "flow-11.json")
        with tempfile.TemporaryDirectory() as d:
            code = ("import io, sys, contextlib\n"
                    "from diagonaldiagrams.cli import cli\n"
                    f"sys.argv = ['diagonaldiagrams', 'flow', {spec!r}, '-o', {os.path.join(d, 'o.html')!r}]\n"
                    "with contextlib.redirect_stdout(io.StringIO()) as out:\n"
                    "    try:\n        cli()\n    except SystemExit:\n        pass\n"
                    "print('ok' if '\"ok\": true' in out.getvalue() else out.getvalue())\n"
                    "print(sorted(m for m in ('argparse', 'shutil', '_colorize', 'xml.etree.ElementTree', "
                    "'diagonaldiagrams.describe', 'diagonaldiagrams.charts.catalog') if m in sys.modules))")
            out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=here)
        self.assertEqual(out.stdout.split(), ["ok", "[]"], out.stderr)


if __name__ == "__main__":
    unittest.main()

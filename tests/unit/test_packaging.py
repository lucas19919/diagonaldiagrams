"""The wheel ships what the source has: every package, and the stylesheets' JSON.
Run: py -3 -m unittest discover tests/unit"""
import ast
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Packaging(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPO, "pyproject.toml"), encoding="utf-8") as f:
            self.toml = f.read()

    def test_every_package_is_listed(self):
        listed = set(ast.literal_eval(self.toml.split("packages = ", 1)[1].split("]", 1)[0] + "]"))
        found = {os.path.relpath(r, REPO).replace(os.sep, ".") for r, _, files in os.walk(os.path.join(REPO, "diagonaldiagrams"))
                 if "__init__.py" in files and "__pycache__" not in r}
        self.assertEqual(found - listed, set(), "add these to [tool.setuptools] packages in pyproject.toml")

    def test_every_data_folder_is_listed(self):
        style = os.path.join(REPO, "diagonaldiagrams", "style")
        for folder in ("themes", "presets"):
            self.assertTrue(any(f.endswith(".json") for f in os.listdir(os.path.join(style, folder))))
            self.assertIn(f'"{folder}/*.json"', self.toml)
        self.assertTrue(os.path.isfile(os.path.join(REPO, "diagonaldiagrams", "web", "page.js")))
        self.assertIn('"diagonaldiagrams" = ["web/*.js"]', self.toml)  # a diagram page's edit mode


if __name__ == "__main__":
    unittest.main()

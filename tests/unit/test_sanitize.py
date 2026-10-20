"""Raw SVG content is reduced to an allowlist.
Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.errors import SpecError  # noqa: E402
from diagonaldiagrams.sanitize import MAX_CHARS, sanitize  # noqa: E402
from diagonaldiagrams.scene import check  # noqa: E402


def clean(markup):
    return sanitize(markup)[0]


class Removes(unittest.TestCase):
    def test_scripts_and_foreign_content(self):
        for bad in ('<script>alert(1)</script>', '<foreignObject><div>x</div></foreignObject>',
                    '<iframe src="https://evil.example"/>', '<image href="https://evil.example/a.png"/>',
                    '<style>@import url(https://evil.example/x.css);</style>', '<a href="https://evil.example"><rect/></a>',
                    '<SCRIPT>alert(1)</SCRIPT>', '<svg:script xmlns:svg="http://www.w3.org/2000/svg">alert(1)</svg:script>'):
            out, removed = sanitize(f'<g>{bad}<rect width="4" height="4"/></g>')
            self.assertEqual(out, '<g><rect width="4" height="4"/></g>', bad)
            self.assertTrue(removed, bad)

    def test_event_handlers(self):
        out, removed = sanitize('<rect width="4" height="4" onload="alert(1)" onMouseOver="x()"/>')
        self.assertEqual(out, '<rect width="4" height="4"/>')
        self.assertEqual(len(removed), 2)

    def test_references_outside_the_fragment(self):
        cases = ['<use href="https://evil.example/s.svg#x"/>', '<use xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="//evil.example/x"/>',
                 '<rect fill="url(https://evil.example/p.svg#g)"/>', '<rect style="fill: url(\'http://evil.example\')"/>',
                 '<use href="javascript:alert(1)"/>', '<rect style="behavior: expression(alert(1))"/>',
                 '<rect fill="url(data:image/svg+xml;base64,AAAA)"/>']
        for bad in cases:
            out, removed = sanitize(bad)
            self.assertNotIn("evil", out, bad)
            self.assertNotIn("javascript", out, bad)
            self.assertNotIn("data:", out, bad)
            self.assertTrue(removed, bad)

    def test_unknown_attributes_go(self):
        out, removed = sanitize('<rect width="4" height="4" formaction="x" data-anything="1"/>')
        self.assertEqual(out, '<rect width="4" height="4"/>')


class Keeps(unittest.TestCase):
    def test_a_plain_drawing_is_unchanged(self):
        art = ('<defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient></defs>'
               '<g transform="translate(2,2)"><path d="M0 0 L10 10" stroke="#333" stroke-width="2"/>'
               '<circle cx="5" cy="5" r="3" fill="url(#g)"/><use href="#g"/><text x="1" y="9">A &amp; B</text></g>')
        out, removed = sanitize(art)
        self.assertEqual((out, removed), (art, []))


class Refuses(unittest.TestCase):
    def test_entities_and_doctypes(self):
        for bad in ('<!DOCTYPE svg [<!ENTITY x "y">]><g>&x;</g>', '<!ENTITY lol "lol"><g/>'):
            with self.assertRaises(SpecError) as cm:
                sanitize(bad)
            self.assertEqual(cm.exception.code, "unsafe-svg")

    def test_malformed_and_too_large(self):
        with self.assertRaises(SpecError):
            sanitize("<g><rect></g>")
        with self.assertRaises(SpecError) as cm:
            sanitize("<g/>" * (MAX_CHARS // 4 + 1))
        self.assertEqual(cm.exception.code, "too-large")
        with self.assertRaises(SpecError):
            sanitize(["<g/>"])


class InTheScene(unittest.TestCase):
    def test_normalize_cleans_content_and_says_so(self):
        scene, errors, warnings = check({"nodes": [{"id": "a", "content": {"svg": '<rect width="4" height="4" onclick="x()"/>',
                                                                          "viewBox": "0 0 4 4"}}]})
        self.assertEqual(errors, [])
        self.assertEqual(scene.node("a").content, {"svg": '<rect width="4" height="4"/>', "viewBox": "0 0 4 4"})
        self.assertEqual([(w["code"], w["path"]) for w in warnings], [("svg-sanitized", "nodes[0].content.svg")])

    def test_unreadable_content_is_an_error_with_its_path(self):
        _, errors, _ = check({"nodes": [{"id": "a", "content": {"svg": "<g>"}}]})
        self.assertEqual([(e["code"], e["path"]) for e in errors], [("bad-value", "nodes[0].content.svg")])


if __name__ == "__main__":
    unittest.main()

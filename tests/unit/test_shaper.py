"""The shaper extension point (PLAN P3.11, DESIGN 6.1). Run: py -3 -m unittest discover tests/unit"""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.audit import _svg_geometry  # noqa: E402
from diagonaldiagrams.diagrams import render_flow  # noqa: E402
from diagonaldiagrams.text import shaper  # noqa: E402

ARABIC, HINDI, HEBREW, CHINESE = "الدفع", "भुगतान", "שלום", "支付"


class Basic(unittest.TestCase):
    def test_which_scripts_need_shaping(self):
        self.assertEqual(shaper.shape(ARABIC)["scripts"], ["Arabic"])
        self.assertEqual(shaper.shape(HINDI + " " + ARABIC)["scripts"], ["Indic", "Arabic"])
        for text in ("Payments", "Αθήνα", "Москва", CHINESE, HEBREW):
            self.assertTrue(shaper.shape(text)["exact"], text)

    def test_direction(self):
        self.assertTrue(shaper.shape(HEBREW)["rtl"])
        self.assertTrue(shaper.shape(ARABIC + " 2026")["rtl"])
        self.assertFalse(shaper.shape("API " + HEBREW)["rtl"])

    def test_a_registered_shaper_takes_over(self):
        @shaper.SHAPERS.add("exact-everything")
        def everything(text):
            return {"exact": True, "scripts": [], "rtl": shaper.is_rtl(text)}
        try:
            self.assertTrue(shaper.shape(ARABIC)["exact"])
        finally:
            shaper.SHAPERS.remove("exact-everything")
        self.assertFalse(shaper.shape(ARABIC)["exact"])


class InTheAudit(unittest.TestCase):
    def test_one_warning_per_script_needing_shaping(self):
        spec = {"nodes": [{"id": "a", "name": ARABIC}, {"id": "b", "name": HINDI}, {"id": "c", "name": HEBREW},
                          {"id": "d", "name": ARABIC + " 2"}],
                "edges": [{"from": "a", "to": "b", "label": ARABIC}, {"from": "b", "to": "c"}, {"from": "c", "to": "d"}]}
        svg, w, h = render_flow(spec)
        found = [i["msg"].split(" ")[0] for i in _svg_geometry(ET.fromstring(svg), w, h) if i["code"] == "shaping"]
        self.assertEqual(found, ["Arabic", "Indic"])


if __name__ == "__main__":
    unittest.main()

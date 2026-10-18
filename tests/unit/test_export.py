"""PNG and PDF export through a headless browser (export._raster_svg). Run: py -3 -m unittest discover tests/unit"""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams import export  # noqa: E402

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 30"><rect width="40" height="30"/></svg>'
REFUSED = ("FATAL:sandbox/linux/suid/client/setuid_sandbox_host.cc:172] The SUID sandbox helper binary was found, "
           "but is not configured correctly.")


def browser(calls, refuse=True):
    """A stand-in for subprocess.run: a browser that cannot start its sandbox unless told not to use one."""
    def run(cmd, **kw):
        calls.append(cmd)
        if refuse and "--no-sandbox" not in cmd:
            return subprocess.CompletedProcess(cmd, -6, "", REFUSED)
        shot = next(a.split("=", 1)[1] for a in cmd if a.startswith("--screenshot="))
        with open(shot, "wb") as f:
            f.write(b"\x89PNG" + b"\0" * 600)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return run


class Sandbox(unittest.TestCase):
    def raster(self, platform, refuse=True):
        calls, clock = [], [0.0]  # a clock of its own: the wait for a late file passes at once
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(sys.modules, {"cairosvg": None}), \
                mock.patch.object(export, "_browser", return_value="/usr/bin/microsoft-edge"), \
                mock.patch("subprocess.run", browser(calls, refuse)), mock.patch("sys.platform", platform), \
                mock.patch("time.time", lambda: clock[0]), mock.patch("time.sleep", lambda s: clock.__setitem__(0, clock[0] + s)):
            how, why = export._raster_svg(SVG, os.path.join(d, "a.png"), "png", 40)
        return how, why, calls

    def test_a_browser_that_cannot_start_its_sandbox_runs_once_more_without_it(self):
        how, why, calls = self.raster("linux")
        self.assertEqual((how, why), ("browser", ""))
        self.assertEqual(["--no-sandbox" in c for c in calls], [False, True])

    def test_a_browser_that_starts_keeps_its_sandbox(self):
        how, _, calls = self.raster("linux", refuse=False)
        self.assertEqual((how, len(calls), "--no-sandbox" in calls[0]), ("browser", 1, False))

    def test_windows_never_drops_the_sandbox(self):
        how, why, calls = self.raster("win32")
        self.assertEqual((how, len(calls)), (None, 1))
        self.assertIn("sandbox", why)


if __name__ == "__main__":
    unittest.main()

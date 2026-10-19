"""Font files and measuring. The fonts are built here, byte by byte, so the
test needs nothing installed. Run: py -3 -m unittest discover tests/unit"""
import os
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from diagonaldiagrams.text import fonts, measure  # noqa: E402


def _cmap4(chars):
    """A format 4 subtable mapping each char to glyph 1, 2, ... in order, one segment per char."""
    cps = sorted(ord(c) for c in chars) + [0xFFFF]
    seg = len(cps)
    ends, starts, deltas, ranges = [], [], [], []
    for k, cp in enumerate(cps):
        ends.append(cp)
        starts.append(cp)
        deltas.append(((k + 1) - cp) & 0xFFFF if cp != 0xFFFF else 1)
        ranges.append(0)
    body = struct.pack(f">{seg}H", *ends) + b"\0\0" + struct.pack(f">{seg}H", *starts) + \
        struct.pack(f">{seg}H", *deltas) + struct.pack(f">{seg}H", *ranges)
    head = struct.pack(">HHHHHHH", 4, 14 + len(body), 0, seg * 2, 0, 0, 0)
    return head + body


def make_font(advances, family="Test Sans", sub="Regular", weight=400, italic=False, upem=1000, fstype=0):
    """The bytes of a minimal TrueType font: glyph 0 (.notdef, 500 wide), then one glyph per char."""
    chars = sorted(advances)
    widths = [500] + [advances[c] for c in chars]
    tables = {
        "head": struct.pack(">IIIIHH16x4hHhhhh", 0x00010000, 0, 0, 0x5F0F3CF5, 0, upem, 0, 0, 1000, 1000,
                            2 if italic else 0, 8, 2, 0, 0),
        "hhea": struct.pack(">I3h", 0x00010000, 800, -200, 0) + b"\0" * 24 + struct.pack(">H", len(widths)),
        "hmtx": b"".join(struct.pack(">Hh", w, 0) for w in widths),
        "cmap": struct.pack(">HHHHI", 0, 1, 3, 1, 12) + _cmap4(chars),
        "OS/2": struct.pack(">HhHHH", 4, 500, weight, 5, fstype) + b"\0" * 52 + struct.pack(">H", 1 if italic else 0)
                + b"\0" * 24 + struct.pack(">h", 700) + b"\0" * 6,
    }
    strings = [(1, family), (2, sub)]
    data, recs = b"", b""
    for nid, text in strings:
        raw = text.encode("utf-16-be")
        recs += struct.pack(">6H", 3, 1, 0x409, nid, len(raw), len(data))
        data += raw
    tables["name"] = struct.pack(">HHH", 0, len(strings), 6 + 12 * len(strings)) + recs + data
    return _sfnt(tables)


def _sfnt(tables):
    tags = sorted(tables)
    out = struct.pack(">IHHHH", 0x00010000, len(tags), 0, 0, 0)
    offset = 12 + 16 * len(tags)
    body = b""
    for t in tags:
        data = tables[t] + b"\0" * (-len(tables[t]) % 4)
        out += struct.pack(">4sIII", t.encode("latin-1"), 0, offset + len(body), len(tables[t]))
        body += data
    return out + body


def write(tmp, name, data):
    path = os.path.join(tmp, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


class Reading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="dd-fonts-")
        cls.path = write(cls.tmp, "test.ttf", make_font({"a": 400, "b": 600, " ": 250}))

    def test_advances_and_widths(self):
        f = fonts.Font(self.path)
        self.assertEqual((f.family, f.weight, f.italic, f.upem), ("Test Sans", 400, False, 1000))
        self.assertEqual([f.advance(c) for c in "ab z"], [400, 600, 250, 500])  # z is missing: .notdef
        self.assertAlmostEqual(f.width("ab", 10), 10.0)
        self.assertEqual(f.missing("abz"), ["z"])
        self.assertTrue(f.embeddable())

    def test_restricted_fonts_say_so(self):
        f = fonts.Font(write(self.tmp, "locked.ttf", make_font({"a": 400}, fstype=2)))
        self.assertFalse(f.embeddable())

    def test_collections_and_woff(self):
        a, b = make_font({"a": 400}, family="One"), make_font({"a": 700}, family="Two", weight=700)
        head = struct.pack(">4sIIII", b"ttcf", 0x00010000, 2, 20, 20 + len(a))
        # each font's table offsets are relative to the file, so shift the second font's
        ttc = write(self.tmp, "pair.ttc", head + _shift(a, 20) + _shift(b, 20 + len(a)))
        self.assertEqual((fonts.Font(ttc, 0).family, fonts.Font(ttc, 1).advance("a")), ("One", 700))
        self.assertEqual(fonts.Font(write(self.tmp, "w.woff", _woff(make_font({"a": 321})))).advance("a"), 321)

    def test_not_a_font(self):
        with self.assertRaises(fonts.FontError):
            fonts.Font(write(self.tmp, "x.ttf", b"hello, world, not a font"))


class Finding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="dd-fonts-")
        cls.path = write(cls.tmp, "brand.ttf", make_font({c: 600 for c in "abcdefghijklmnopqrstuvwxyz "}, family="Brand Sans"))

    def test_named_files_come_first_and_generic_stacks_are_not_looked_up(self):
        font, missing = fonts.find("Brand Sans, sans-serif", files={"Brand Sans": self.path})
        self.assertEqual((font.family, missing), ("Brand Sans", None))
        self.assertEqual(fonts.find("system-ui, 'Segoe UI', sans-serif"), (None, None))
        self.assertEqual(fonts.find("Nowhere Grotesk 9000, sans-serif"), (None, "Nowhere Grotesk 9000"))

    def test_a_measured_font_wraps_by_its_own_widths(self):
        font = fonts.load(self.path)
        text = "abcd abcd abcd abcd"  # 4 x 4 x 600 + spaces: wide at 12 px
        est, _ = measure.wrap(text, 130, 12)
        real, _ = measure.wrap(text, 130, 12, font=font)
        self.assertEqual(len(est), 1)  # the estimate thinks it fits
        self.assertGreater(len(real), 1)  # the font says it doesn't
        self.assertTrue(all(font.width("".join(t for t, _ in ln), 12) <= 130 for ln in real))


def _shift(font_bytes, by):
    """A font's bytes with every table offset moved by `by` (for placing it later in a file)."""
    num = struct.unpack(">H", font_bytes[4:6])[0]
    out = bytearray(font_bytes)
    for k in range(num):
        at = 12 + 16 * k + 8
        struct.pack_into(">I", out, at, struct.unpack(">I", font_bytes[at:at + 4])[0] + by)
    return bytes(out)


def _woff(font_bytes):
    num = struct.unpack(">H", font_bytes[4:6])[0]
    entries, blobs = [], []
    offset = 44 + 20 * num
    for k in range(num):
        tag, _, off, length = struct.unpack(">4sIII", font_bytes[12 + 16 * k:28 + 16 * k])
        raw = font_bytes[off:off + length]
        comp = zlib.compress(raw)
        blob = comp if len(comp) < len(raw) else raw
        entries.append(struct.pack(">4sIIII", tag, offset, len(blob), length, 0))
        blobs.append(blob + b"\0" * (-len(blob) % 4))
        offset += len(blobs[-1])
    head = struct.pack(">4sIIHHIHHIIIII", b"wOFF", 0x00010000, offset, num, 0, 0, 1, 0, 0, 0, 0, 0, 0)
    return head + b"".join(entries) + b"".join(blobs)


if __name__ == "__main__":
    unittest.main()

"""Font files, read with struct: TrueType and OpenType (.ttf, .otf), collections
(.ttc) and zlib-compressed WOFF 1. WOFF2 needs Brotli and is not read.

A Font knows its family, weight and style, its units per em, its ascent, descent and cap height, its
embedding permission (OS/2 fsType), and each character's advance width (cmap formats 4 and 12, hmtx).
Kerning is not applied, which errs slightly wide.

find(families) resolves a CSS font-family list: a file the stylesheets named, then the installed fonts
(indexed by their name tables, the index cached in the user cache directory). Generic families
(system-ui, sans-serif, serif, monospace) are not looked up: the default stack keeps the engine's
built-in estimate, so default figures don't depend on the machine.
"""
import json
import os
import struct
import sys
import zlib

GENERIC = {"system-ui", "sans-serif", "serif", "monospace", "cursive", "fantasy", "ui-sans-serif", "ui-serif",
           "ui-monospace", "ui-rounded", "-apple-system", "blinkmacsystemfont", "math", "emoji"}
EXTENSIONS = (".ttf", ".otf", ".ttc", ".woff")


class FontError(Exception):
    pass


def _tables(data, index=0):
    """{tag: bytes} for one font in a file's bytes."""
    tag = data[:4]
    if tag == b"ttcf":
        count = struct.unpack(">I", data[8:12])[0]
        if index >= count:
            raise FontError(f"the collection has {count} fonts, not {index + 1}")
        start = struct.unpack(">I", data[12 + 4 * index:16 + 4 * index])[0]
        return _sfnt(data, start)
    if tag == b"wOFF":
        num = struct.unpack(">H", data[12:14])[0]
        out = {}
        for k in range(num):
            t, off, comp, orig, _ = struct.unpack(">4sIIII", data[44 + 20 * k:64 + 20 * k])
            raw = data[off:off + comp]
            out[t.decode("latin-1")] = zlib.decompress(raw) if comp < orig else raw
        return out
    if tag == b"wOF2":
        raise FontError("WOFF2 needs Brotli, which the standard library lacks; use the .ttf or .otf")
    if tag not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        raise FontError("not a font file this engine reads (TrueType, OpenType, TTC or WOFF 1)")
    return _sfnt(data, 0)


def _sfnt(data, start):
    num = struct.unpack(">H", data[start + 4:start + 6])[0]
    out = {}
    for k in range(num):
        t, _, off, length = struct.unpack(">4sIII", data[start + 12 + 16 * k:start + 28 + 16 * k])
        out[t.decode("latin-1")] = data[off:off + length]
    return out


def _names(name):
    """{nameID: text} from a name table, English Windows strings first."""
    count, store = struct.unpack(">2xHH", name[:6])
    found = {}
    for k in range(count):
        plat, enc, lang, nid, length, off = struct.unpack(">6H", name[6 + 12 * k:18 + 12 * k])
        raw = name[store + off:store + off + length]
        if plat == 3 and enc in (0, 1, 10):
            text, rank = raw.decode("utf-16-be", "replace"), 0 if lang == 0x409 else 1
        elif plat == 1 and enc == 0:
            text, rank = raw.decode("mac-roman", "replace"), 2
        else:
            continue
        if nid not in found or rank < found[nid][1]:
            found[nid] = (text, rank)
    return {nid: text for nid, (text, _) in found.items()}


def describe(path, index=0):
    """What the index keeps of a font: family, subfamily, weight, italic. Reads only small tables."""
    with open(path, "rb") as f:
        data = f.read()
    t = _tables(data, index)
    names = _names(t["name"]) if "name" in t else {}
    weight, italic = 400, False
    if "OS/2" in t and len(t["OS/2"]) >= 64:
        weight = struct.unpack(">H", t["OS/2"][4:6])[0]
        italic = bool(struct.unpack(">H", t["OS/2"][62:64])[0] & 1)
    family = names.get(16) or names.get(1) or os.path.splitext(os.path.basename(path))[0]
    return {"family": family, "subfamily": names.get(17) or names.get(2) or "", "weight": weight, "italic": italic,
            "path": path, "index": index}


class Font:
    def __init__(self, path, index=0):
        with open(path, "rb") as f:
            data = f.read()
        t = _tables(data, index)
        for need in ("head", "hhea", "hmtx", "cmap"):
            if need not in t:
                raise FontError(f"{os.path.basename(path)} has no {need} table")
        self.path, self.index = path, index
        self.upem = struct.unpack(">H", t["head"][18:20])[0]
        self.ascent, self.descent = struct.unpack(">hh", t["hhea"][4:8])
        n_metrics = struct.unpack(">H", t["hhea"][34:36])[0]
        hmtx = t["hmtx"]
        self._adv = [struct.unpack(">H", hmtx[4 * k:4 * k + 2])[0] for k in range(n_metrics)]
        self._cmap = _cmap(t["cmap"])
        info = describe(path, index)
        self.family, self.subfamily, self.weight, self.italic = info["family"], info["subfamily"], info["weight"], info["italic"]
        self.fstype = struct.unpack(">H", t["OS/2"][8:10])[0] if "OS/2" in t else 0
        self.cap_height = struct.unpack(">h", t["OS/2"][88:90])[0] if "OS/2" in t and len(t["OS/2"]) >= 90 else \
            round(self.ascent * 0.7)
        import hashlib
        self.sha1 = hashlib.sha1(data).hexdigest()

    def advance(self, ch):
        """A character's advance in font units; one the font lacks takes the .notdef glyph's."""
        gid = self._cmap.get(ord(ch), 0)
        return self._adv[min(gid, len(self._adv) - 1)]

    def width(self, text, size):
        return sum(self.advance(ch) for ch in str(text)) * size / self.upem

    def missing(self, text):
        """The characters this font has no glyph for."""
        return sorted({ch for ch in str(text) if ord(ch) not in self._cmap and not ch.isspace()})

    def embeddable(self):
        """OS/2 fsType: 0 installable, 4 preview, 8 editable; 2 alone forbids embedding."""
        return not (self.fstype & 0x000F) == 0x0002

    def __repr__(self):
        return f"Font({self.family!r}, weight={self.weight}, italic={self.italic})"


def _cmap(table):
    """{codepoint: glyph id} from the best Unicode subtable (format 12, else 4)."""
    num = struct.unpack(">H", table[2:4])[0]
    subs = {}
    for k in range(num):
        plat, enc, off = struct.unpack(">HHI", table[4 + 8 * k:12 + 8 * k])
        subs[(plat, enc)] = off
    for key in ((3, 10), (0, 6), (0, 4), (3, 1), (0, 3), (0, 2), (0, 1), (0, 0)):
        if key not in subs:
            continue
        off = subs[key]
        fmt = struct.unpack(">H", table[off:off + 2])[0]
        if fmt == 12:
            n = struct.unpack(">I", table[off + 12:off + 16])[0]
            out = {}
            for g in range(n):
                start, end, gid = struct.unpack(">III", table[off + 16 + 12 * g:off + 28 + 12 * g])
                for cp in range(start, min(end, start + 0x10000) + 1):
                    out[cp] = gid + cp - start
            return out
        if fmt == 4:
            seg2 = struct.unpack(">H", table[off + 6:off + 8])[0]
            ends = struct.unpack(f">{seg2 // 2}H", table[off + 14:off + 14 + seg2])
            starts = struct.unpack(f">{seg2 // 2}H", table[off + 16 + seg2:off + 16 + 2 * seg2])
            deltas = struct.unpack(f">{seg2 // 2}h", table[off + 16 + 2 * seg2:off + 16 + 3 * seg2])
            ro_at = off + 16 + 3 * seg2
            ranges = struct.unpack(f">{seg2 // 2}H", table[ro_at:ro_at + seg2])
            out = {}
            for k, (s, e, d, r) in enumerate(zip(starts, ends, deltas, ranges)):
                if s == 0xFFFF:
                    continue
                for cp in range(s, e + 1):
                    if r == 0:
                        gid = (cp + d) & 0xFFFF
                    else:
                        at = ro_at + 2 * k + r + 2 * (cp - s)
                        gid = struct.unpack(">H", table[at:at + 2])[0]
                        gid = (gid + d) & 0xFFFF if gid else 0
                    if gid:
                        out[cp] = gid
            return out
    return {}


# ---------- finding installed fonts ----------

def font_dirs():
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        return [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
                os.path.join(os.environ.get("LOCALAPPDATA", home), "Microsoft", "Windows", "Fonts")]
    if sys.platform == "darwin":
        return ["/System/Library/Fonts", "/Library/Fonts", os.path.join(home, "Library", "Fonts")]
    return ["/usr/share/fonts", "/usr/local/share/fonts", os.path.join(home, ".fonts"),
            os.path.join(home, ".local", "share", "fonts")]


def cache_dir():
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", home)
        return os.path.join(base, "diagonaldiagrams", "Cache")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Caches", "diagonaldiagrams")
    return os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(home, ".cache")), "diagonaldiagrams")


_INDEX = None


def index(dirs=None):
    """Every installed font's family, weight and style, from a cache that is rebuilt when a font
    folder changes."""
    global _INDEX
    dirs = dirs or font_dirs()
    stamp = {d: os.path.getmtime(d) for d in dirs if os.path.isdir(d)}
    path = os.path.join(cache_dir(), "fonts.json")
    if _INDEX is not None and _INDEX["stamp"] == stamp:
        return _INDEX["fonts"]
    try:
        with open(path, encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("stamp") == {k: v for k, v in stamp.items()} and cached.get("version") == 1:
            _INDEX = cached
            return cached["fonts"]
    except (OSError, ValueError):
        pass
    fonts = []
    for d in stamp:
        for root, _, files in os.walk(d):
            for name in files:
                if not name.lower().endswith(EXTENSIONS):
                    continue
                full = os.path.join(root, name)
                try:
                    count = 1
                    if name.lower().endswith(".ttc"):
                        with open(full, "rb") as f:
                            head = f.read(12)
                        count = struct.unpack(">I", head[8:12])[0]
                    for k in range(min(count, 16)):
                        fonts.append(describe(full, k))
                except (OSError, FontError, struct.error, KeyError, IndexError, UnicodeDecodeError):
                    continue
    _INDEX = {"version": 1, "stamp": stamp, "fonts": fonts}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_INDEX, f)
    except OSError:
        pass  # a read-only home: the index is rebuilt next time
    return fonts


def families(spec):
    """A CSS font-family value as a list of names, quotes removed."""
    return [p.strip().strip("'\"") for p in str(spec or "").split(",") if p.strip()]


_LOADED = {}


def load(path, index_=0):
    key = (os.path.abspath(path), index_)
    if key not in _LOADED:
        _LOADED[key] = Font(path, index_)
    return _LOADED[key]


def find(spec, weight=400, italic=False, files=None):
    """(Font or None, the first family asked for if none was found). files maps family names to font
    files a stylesheet named. A generic first family means the default stack: (None, None)."""
    names = families(spec)
    if not names or names[0].lower() in GENERIC:
        return None, None
    want = None
    for name in names:
        if name.lower() in GENERIC:
            break
        want = want or name
        path = (files or {}).get(name)
        if path:
            try:
                return load(path), None
            except (OSError, FontError) as e:
                raise FontError(f"font file {path} for '{name}' can't be read: {e}") from None
        matches = [f for f in index() if f["family"].lower() == name.lower()]
        if matches:
            best = min(matches, key=lambda f: (f["italic"] != italic, abs(int(f["weight"]) - int(weight))))
            try:
                return load(best["path"], best["index"]), None
            except (OSError, FontError):
                continue
    return None, want

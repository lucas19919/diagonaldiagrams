"""Shaping: an extension point between text and its measured width.

Latin, Greek, Cyrillic and CJK need no shaping: each character has its own width. Right-to-left
scripts (Hebrew, Arabic) are kept in logical order in SVG, where the viewer's browser applies the
bidi algorithm. Scripts whose letters change shape with their neighbours (Arabic joining, Indic
conjuncts, Thai, Khmer, Myanmar, Tibetan) need a real shaper for exact widths. The built-in one
recognizes them so the figure can say its widths are estimates (the `shaping` warning); a HarfBuzz-
backed shaper registers here later, and SHAPERS.get("active") is whichever was registered last.
"""
import unicodedata

from ..registry import Registry

SHAPERS = Registry("shaper")
# (first, last, script) for blocks whose letters join or reorder: widths need a shaper
CONTEXTUAL = ((0x0600, 0x06FF, "Arabic"), (0x0700, 0x074F, "Syriac"), (0x0750, 0x077F, "Arabic"),
              (0x0780, 0x07BF, "Thaana"), (0x0860, 0x08FF, "Arabic"), (0x0900, 0x0DFF, "Indic"),
              (0x0E00, 0x0E7F, "Thai"), (0x0E80, 0x0EFF, "Lao"), (0x0F00, 0x0FFF, "Tibetan"),
              (0x1000, 0x109F, "Myanmar"), (0x1780, 0x17FF, "Khmer"), (0x1800, 0x18AF, "Mongolian"),
              (0xFB50, 0xFDFF, "Arabic"), (0xFE70, 0xFEFF, "Arabic"))


def scripts_needing_shaping(text):
    """The scripts in text whose widths depend on shaping, in the order first met."""
    out = []
    for ch in str(text):
        cp = ord(ch)
        if cp < 0x0600:
            continue
        for lo, hi, name in CONTEXTUAL:
            if lo <= cp <= hi and name not in out:
                out.append(name)
    return out


def is_rtl(text):
    """True when the first strong character is right-to-left (bidi class R or AL)."""
    for ch in str(text):
        kind = unicodedata.bidirectional(ch)
        if kind in ("R", "AL"):
            return True
        if kind == "L":
            return False
    return False


@SHAPERS.add("basic")
def basic(text):
    """{"exact": widths need no shaping, "scripts": the ones that would, "rtl": direction}."""
    scripts = scripts_needing_shaping(text)
    return {"exact": not scripts, "scripts": scripts, "rtl": is_rtl(text)}


def shape(text):
    """The active shaper's reading of a text: the last one registered."""
    names = SHAPERS.names()
    return SHAPERS.get(names[-1])(text)

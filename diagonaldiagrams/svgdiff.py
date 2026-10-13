"""Are two SVGs the same drawing? Element by element, ignoring how the text is laid out.

    py -3 -m diagonaldiagrams.svgdiff A.svg B.svg [--tol 0.01]

Two SVGs match when they have the same elements in the same order (tag, attributes, text), with
numbers equal within a tolerance. Whitespace between elements, attribute order, quoting, and how a
number is written (120 vs 120.0, 0.5 vs .5) do not matter. Used to check that rewriting how a
figure is written out did not change what it draws (docs/PLAN.md, P2.6).
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET

NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _flatten(root):
    """(tag, attributes, text) for every element, in document order."""
    out = []
    for el in root.iter():
        tag = str(el.tag).split("}")[-1]
        attrs = {str(k).split("}")[-1]: v for k, v in el.attrib.items()}
        out.append((tag, attrs, (el.text or "").strip()))
    return out


def _same_value(a, b, tol):
    if a == b:
        return True
    na, nb = NUM.findall(a), NUM.findall(b)
    if not na or len(na) != len(nb):
        return False
    if NUM.sub("#", a).replace(" ", "") != NUM.sub("#", b).replace(" ", ""):
        return False  # the same numbers in a different frame ("translate(1 2)" vs "scale(1 2)")
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(na, nb))


def compare(a_text, b_text, tol=0.01, limit=10):
    """Differences between two SVG texts, as readable lines; empty when they draw the same."""
    a, b = _flatten(ET.fromstring(a_text)), _flatten(ET.fromstring(b_text))
    out = []
    if len(a) != len(b):
        out.append(f"{len(a)} elements vs {len(b)}")
    for i, ((ta, aa, xa), (tb, ab, xb)) in enumerate(zip(a, b)):
        if ta != tb:
            out.append(f"element {i}: <{ta}> vs <{tb}>")
            break  # everything after a missing or extra element is shifted
        if xa != xb:
            out.append(f"element {i} <{ta}> text: {xa[:40]!r} vs {xb[:40]!r}")
        for k in sorted(set(aa) | set(ab)):
            va, vb = aa.get(k), ab.get(k)
            if va is None or vb is None or not _same_value(va, vb, tol):
                out.append(f"element {i} <{ta}> {k}: {str(va)[:50]!r} vs {str(vb)[:50]!r}")
        if len(out) >= limit:
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Do two SVGs draw the same thing?")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--tol", type=float, default=0.01)
    a = ap.parse_args(argv)
    with open(a.a, encoding="utf-8") as fa, open(a.b, encoding="utf-8") as fb:
        diffs = compare(fa.read(), fb.read(), a.tol)
    print("\n".join(diffs) if diffs else "same drawing")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())

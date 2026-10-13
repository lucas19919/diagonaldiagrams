"""Text layout for boxes (DESIGN 6.2, PLAN P3.6): wrapping, overflow and line metrics.

wrap() breaks a label into lines that fit a width at its computed size. Its overflow mode decides
what happens when the lines run past max-lines:
- wrap (the default) keeps every line and the box grows: nothing is ever cut;
- shrink lowers the size in half-pixel steps, down to 9 px, until the lines fit;
- ellipsis cuts at max-lines and ends the last line in "...": only when asked for.

Plain text wraps exactly as the engine always has (_text._wrap_px), so default figures keep their
bytes. Text with markup (text.markup) wraps word by word, each word measured in its own style.
"""
from .._text import _text_w, _wrap_px
from . import markup

MIN_SIZE = 9.0
NO_LIMIT = 10 ** 6


def width(text, size, bold=False, kind="", font=None):
    """A run's width: from the font's own advances when one was found, else the built-in estimate
    (bold runs as bold, mono runs at a fixed 0.6 em per character). A bold run in a regular font is
    measured 6% wider, as the estimate does."""
    if font is not None and kind != "m":
        w = font.width(text, size)
        return w * 1.06 if kind == "b" and font.weight < 600 else w
    if kind == "m":
        return 0.6 * size * len(text)
    return _text_w(text, size, bold or kind == "b")


def _wrap_measured(text, max_w, size, font, limit):
    """Greedy wrapping by a font's advances, as _wrap_px does by the estimate: a word too wide for a
    line is split with a hyphen; past limit lines the last ends in "..."."""
    words, lines, cur = str(text or "").split(), [], ""
    for wd in words:
        while font.width(wd, size) > max_w and len(wd) > 1:
            cut = max(1, int(len(wd) * max_w / font.width(wd, size)) - 1)
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(wd[:cut] + "-")
            wd = wd[cut:]
        trial = (cur + " " + wd).strip()
        if cur and font.width(trial, size) > max_w:
            lines.append(cur)
            cur = wd
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if len(lines) > limit:
        lines = lines[:limit]
        last = lines[-1]
        while last and font.width(last + "...", size) > max_w:
            last = last[:-1]
        lines[-1] = last.rstrip() + "..."
    return lines or [""]


def _wrap_runs(text, max_w, size, bold, font=None):
    """Lines of (text, kind) runs, breaking between words; a word too wide for a line stays whole."""
    words = []  # (word, kind, whether a space comes before it)
    spaced = False
    for piece, kind in markup.runs(text):
        for k, wd in enumerate(piece.split(" ")):
            if wd:
                words.append((wd, kind, spaced or k > 0))
                spaced = False
            elif k > 0 or piece.startswith(" "):
                spaced = True
        spaced = spaced or piece.endswith(" ")
    lines, cur, cur_w = [], [], 0.0
    space = width(" ", size, bold, font=font)
    for wd, kind, before in words:
        w = width(wd, size, bold, kind, font)
        gap = space if (cur and before) else 0.0
        if cur and cur_w + gap + w > max_w:
            lines.append(cur)
            cur, cur_w, gap = [], 0.0, 0.0
        if gap:
            cur.append((" ", ""))
            cur_w += gap
        cur.append((wd, kind))
        cur_w += w
    if cur:
        lines.append(cur)
    return [_merge(line) for line in lines] or [[("", "")]]


def _merge(line):
    out = []
    for text, kind in line:
        if out and out[-1][1] == kind:
            out[-1] = (out[-1][0] + text, kind)
        else:
            out.append((text, kind))
    return out


def wrap(text, max_w, size, bold=False, max_lines=None, overflow="wrap", font=None):
    """(lines, size): each line a list of (text, kind) runs, and the size the text ends up at. With a
    font, widths are its own advances; without, the built-in estimate."""
    def lay(sz, limit):
        if markup.has_markup(text):
            lines = _wrap_runs(text, max_w, sz, bold, font)
            if len(lines) > limit:
                lines = lines[:limit]
                last = lines[-1]
                lines[-1] = last[:-1] + [(last[-1][0].rstrip() + "...", last[-1][1])]
            return lines
        if font is not None:
            return [[(line, "")] for line in _wrap_measured(text, max_w, sz, font, limit)]
        return [[(line, "")] for line in _wrap_px(text, max_w, sz, bold, limit)]

    if overflow == "ellipsis":
        return lay(size, max_lines or 3), size
    if overflow == "shrink" and max_lines:
        sz = size
        while sz > MIN_SIZE and len(lay(sz, NO_LIMIT)) > max_lines:
            sz = max(MIN_SIZE, sz - 0.5)
        return lay(sz, NO_LIMIT), sz
    return lay(size, NO_LIMIT), size


def line_height(st, default_ratio):
    """A line's pitch in px: the style's line-height (a multiple of the size), or the preset's."""
    ratio = st.get("line-height") or default_ratio
    return round(st["font-size"] * ratio, 2)

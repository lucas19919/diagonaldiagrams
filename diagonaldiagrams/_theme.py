"""Themes, palettes and the font stack."""
from .style.tokens import THEME_NAMES, read_theme_file, v1_theme


# The flat theme dicts the renderers read, built from the theme stylesheets (style/themes/*.json).
THEMES = {name: v1_theme(name) for name in THEME_NAMES}
THEME = THEMES["editorial"]  # named, like every theme


OKABE_ITO_DARK = ["#56B4E9", "#E69F00", "#2dd4a7", "#CC79A7", "#7cc7ff", "#f08a59", "#F0E442", "#e8e8e8"]


def get_theme(name=None, path=None):
    """Resolve a theme dict: a builtin name, plus the keys a --theme-file overrides (its flat v1 keys,
    or a stylesheet's tokens; accent_tint and accent-tint both work)."""
    t = dict(THEMES.get(name or "editorial", THEMES["editorial"]))
    if path:
        t.update(read_theme_file(path))
        if not name:
            name = "custom"
    t["_name"] = name or "editorial"
    return t


def _assign_colors(groups, pal, highlights=None):
    """Palette colors in order, skipping highlighted groups: they draw in the accent, so they
    should not use up a color the next series needs."""
    out, k = {}, 0
    for g in groups:
        if highlights and _hit(highlights, g):
            out[g] = pal[0]
            continue
        out[g] = pal[k % len(pal)]
        k += 1
    return out


def series_palette(t, highlights=None, reserve=False):
    """Colorblind-safe series colors fitting the theme (dark gets brightened set). With a highlight, or
    reserve (bar and line, where --highlight can give the accent to any series), colors close to the
    accent are left out, so only a highlighted series reads as coral, and a series keeps its color
    across figures whether or not one is highlighted."""
    pal = OKABE_ITO_DARK if t.get("_name") == "ink" else OKABE_ITO
    if not highlights and not reserve:
        return pal

    def rgb(c):
        c = str(c).lstrip("#")
        return tuple(int(c[k:k + 2], 16) for k in (0, 2, 4)) if len(c) == 6 else (0, 0, 0)
    acc = rgb(t.get("accent", "#eb6c36"))
    # 90 drops vermillion and the Okabe-Ito orange beside a coral accent; both read as the accent
    far = [c for c in pal if sum((a - b) ** 2 for a, b in zip(rgb(c), acc)) ** 0.5 > 90]
    return far or pal


OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]


FONT = "system-ui, 'Segoe UI', sans-serif"


SANS = MONO = SERIF = FONT


def _hit(highlights, *vals):
    want = {str(h) for h in (highlights or [])}
    return any(str(v) in want for v in vals if v is not None)

"""Themes, palettes and the font stack."""
import json, sys


THEME = {
    "paper": "#f5f5f5", "ink": "#2d3142", "muted": "#4f5d75",
    "soft": "#7a8399", "rule": "rgba(45,49,66,0.12)",
    "accent": "#eb6c36", "accent_tint": "rgba(235,108,54,0.08)",
    "link": "#2e5aa8", "card": "#ffffff",
}


THEMES = {
    "editorial": dict(THEME),
    "ink": {"paper": "#2d3142", "ink": "#f5f5f5", "muted": "#bfc0c0",
            "soft": "#8e98ac", "rule": "rgba(245,245,245,0.14)",
            "accent": "#f08a59", "accent_tint": "rgba(240,138,89,0.12)",
            "link": "#6a95d8", "card": "#393e53"},
    "print": {"paper": "#ffffff", "ink": "#111111", "muted": "#444444",
              "soft": "#777777", "rule": "rgba(0,0,0,0.18)",
              "accent": "#000000", "accent_tint": "rgba(0,0,0,0.06)",
              "link": "#333333", "card": "#ffffff"},
}


OKABE_ITO_DARK = ["#56B4E9", "#E69F00", "#2dd4a7", "#CC79A7", "#7cc7ff", "#f08a59", "#F0E442", "#e8e8e8"]


def get_theme(name=None, path=None):
    """Resolve a theme dict: builtin name + optional JSON overrides file."""
    t = dict(THEMES.get(name or "editorial", THEMES["editorial"]))
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                custom = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            sys.exit(f"bad --theme-file: {e}")
        unknown = sorted(set(custom) - set(t))
        if unknown:
            sys.exit(f"--theme-file unknown keys {unknown}; known: {sorted(t)}")
        t.update(custom)
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


def series_palette(t, highlights=None):
    """Colorblind-safe series colors fitting the theme (dark gets brightened set). With a highlight,
    colors close to the accent are left out, so only the highlighted series reads as coral."""
    pal = OKABE_ITO_DARK if t.get("_name") == "ink" else OKABE_ITO
    if not highlights:
        return pal

    def rgb(c):
        c = str(c).lstrip("#")
        return tuple(int(c[k:k + 2], 16) for k in (0, 2, 4)) if len(c) == 6 else (0, 0, 0)
    acc = rgb(t.get("accent", "#eb6c36"))
    far = [c for c in pal if sum((a - b) ** 2 for a, b in zip(rgb(c), acc)) ** 0.5 > 70]
    return far or pal


OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]


FONT = "system-ui, 'Segoe UI', sans-serif"


SANS = MONO = SERIF = FONT


def _hit(highlights, *vals):
    want = {str(h) for h in (highlights or [])}
    return any(str(v) in want for v in vals if v is not None)

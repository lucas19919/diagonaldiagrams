"""Style values (DESIGN 5.3, 5.4): what a stylesheet may say, read into values the painters use.

- Colors: #rgb, #rgba, #rrggbb, #rrggbbaa, rgb()/rgba() (commas or spaces, / alpha), hsl()/hsla(),
  CSS named colors, transparent, currentColor, tokens (accent, var(--accent)), and mix(a, b, 30%)
  (30% of b into a).
- Lengths: plain numbers and px; em is relative to the element's font size.
- Shorthands: border and border-<side> (width, style, color in any order), border-radius (1 to 4
  values, CSS corner order), padding (1 to 4 values), box-shadow (one or more, or none), font
  ([style] [weight] size[/line-height] family), and linear-gradient().

A color keeps the text it was written as (`.css`), unless it was computed (mix), so restyling
with the default stylesheet draws the same bytes. Every error is a SpecError with code "bad-style"
and a did-you-mean fix where one is close.
"""
import colorsys
import re

from ..errors import SpecError

NAMED = {
    "aliceblue": "#f0f8ff", "antiquewhite": "#faebd7", "aqua": "#00ffff", "aquamarine": "#7fffd4", "azure": "#f0ffff",
    "beige": "#f5f5dc", "bisque": "#ffe4c4", "black": "#000000", "blanchedalmond": "#ffebcd", "blue": "#0000ff",
    "blueviolet": "#8a2be2", "brown": "#a52a2a", "burlywood": "#deb887", "cadetblue": "#5f9ea0", "chartreuse": "#7fff00",
    "chocolate": "#d2691e", "coral": "#ff7f50", "cornflowerblue": "#6495ed", "cornsilk": "#fff8dc", "crimson": "#dc143c",
    "cyan": "#00ffff", "darkblue": "#00008b", "darkcyan": "#008b8b", "darkgoldenrod": "#b8860b", "darkgray": "#a9a9a9",
    "darkgreen": "#006400", "darkgrey": "#a9a9a9", "darkkhaki": "#bdb76b", "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f", "darkorange": "#ff8c00", "darkorchid": "#9932cc", "darkred": "#8b0000",
    "darksalmon": "#e9967a", "darkseagreen": "#8fbc8f", "darkslateblue": "#483d8b", "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f", "darkturquoise": "#00ced1", "darkviolet": "#9400d3", "deeppink": "#ff1493",
    "deepskyblue": "#00bfff", "dimgray": "#696969", "dimgrey": "#696969", "dodgerblue": "#1e90ff",
    "firebrick": "#b22222", "floralwhite": "#fffaf0", "forestgreen": "#228b22", "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc", "ghostwhite": "#f8f8ff", "gold": "#ffd700", "goldenrod": "#daa520", "gray": "#808080",
    "green": "#008000", "greenyellow": "#adff2f", "grey": "#808080", "honeydew": "#f0fff0", "hotpink": "#ff69b4",
    "indianred": "#cd5c5c", "indigo": "#4b0082", "ivory": "#fffff0", "khaki": "#f0e68c", "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5", "lawngreen": "#7cfc00", "lemonchiffon": "#fffacd", "lightblue": "#add8e6",
    "lightcoral": "#f08080", "lightcyan": "#e0ffff", "lightgoldenrodyellow": "#fafad2", "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90", "lightgrey": "#d3d3d3", "lightpink": "#ffb6c1", "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa", "lightskyblue": "#87cefa", "lightslategray": "#778899", "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de", "lightyellow": "#ffffe0", "lime": "#00ff00", "limegreen": "#32cd32",
    "linen": "#faf0e6", "magenta": "#ff00ff", "maroon": "#800000", "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd", "mediumorchid": "#ba55d3", "mediumpurple": "#9370db", "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee", "mediumspringgreen": "#00fa9a", "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585", "midnightblue": "#191970", "mintcream": "#f5fffa", "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5", "navajowhite": "#ffdead", "navy": "#000080", "oldlace": "#fdf5e6", "olive": "#808000",
    "olivedrab": "#6b8e23", "orange": "#ffa500", "orangered": "#ff4500", "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa", "palegreen": "#98fb98", "paleturquoise": "#afeeee", "palevioletred": "#db7093",
    "papayawhip": "#ffefd5", "peachpuff": "#ffdab9", "peru": "#cd853f", "pink": "#ffc0cb", "plum": "#dda0dd",
    "powderblue": "#b0e0e6", "purple": "#800080", "rebeccapurple": "#663399", "red": "#ff0000",
    "rosybrown": "#bc8f8f", "royalblue": "#4169e1", "saddlebrown": "#8b4513", "salmon": "#fa8072",
    "sandybrown": "#f4a460", "seagreen": "#2e8b57", "seashell": "#fff5ee", "sienna": "#a0522d", "silver": "#c0c0c0",
    "skyblue": "#87ceeb", "slateblue": "#6a5acd", "slategray": "#708090", "slategrey": "#708090", "snow": "#fffafa",
    "springgreen": "#00ff7f", "steelblue": "#4682b4", "tan": "#d2b48c", "teal": "#008080", "thistle": "#d8bfd8",
    "tomato": "#ff6347", "turquoise": "#40e0d0", "violet": "#ee82ee", "wheat": "#f5deb3", "white": "#ffffff",
    "whitesmoke": "#f5f5f5", "yellow": "#ffff00", "yellowgreen": "#9acd32",
}
BORDER_STYLES = ("solid", "dashed", "dotted", "double", "none")
SIDES = ("top", "right", "bottom", "left")

# DESIGN 5.4: every property a stylesheet may set, and what kind of value it takes
_BOX = {"shape": "word", "width": "length", "height": "length", "min-width": "length", "max-width": "length",
        "padding": "padding", "fill": "paint", "background": "paint", "stroke": "paint", "stroke-width": "length",
        "border": "border", "border-top": "border", "border-right": "border", "border-bottom": "border",
        "border-left": "border", "border-top-left": "border", "border-top-right": "border",
        "border-bottom-right": "border", "border-bottom-left": "border",  # a diamond's sides (DESIGN 5.5)
        "border-style": ("solid", "dashed", "dotted", "double", "none"),
        "border-radius": "radius", "box-shadow": "shadow", "opacity": "number", "glow": "glow",
        "pattern": ("hatch", "dots", "grid", "none"), "sketch": "bool"}
_TEXT = {"font": "font", "font-family": "family", "font-size": "length", "font-weight": "weight",
         "font-style": ("normal", "italic", "oblique"), "color": "color",
         "text-align": ("start", "middle", "end", "left", "center", "right"),
         "text-transform": ("none", "uppercase", "lowercase", "capitalize"), "letter-spacing": "length",
         "line-height": "number", "max-lines": "int", "overflow": ("wrap", "shrink", "ellipsis"),
         "label-position": ("inside", "top-left", "top-right", "top", "bottom", "left", "right", "center")}
_EDGE = {"stroke-dasharray": "dasharray",
         "marker-start": ("arrow", "open", "diamond", "circle", "crow-many", "crow-one", "none"),
         "marker-end": ("arrow", "open", "diamond", "circle", "crow-many", "crow-one", "none"),
         "router": "word", "corner-radius": "length", "bundle": "bool"}
_ICON = {"icon": "word", "icon-position": ("left", "right", "top", "bottom", "top-left", "top-right"),
         "icon-color": "color", "icon-size": "length"}
_FIGURE = {"font-embed": "bool",  # embed the named fonts the figure uses (P3.5b)
           "title-align": ("start", "middle", "end", "left", "center", "right"),
           "legend-position": ("bottom", "top", "right", "left", "none")}
PROPERTIES = {**_BOX, **_TEXT, **_EDGE, **_ICON, **_FIGURE, "legend": "text"}


def error(msg, fix, near=None):
    return SpecError(msg + (f" (did you mean '{near}'?)" if near else ""), fix, "bad-style")


def _near(word, words):
    import difflib
    hit = difflib.get_close_matches(str(word).lower(), list(words), n=1, cutoff=0.75)
    return hit[0] if hit else None


class Color:
    """r, g, b in 0-255 and a in 0-1, plus the text to write (the text it came from, if any)."""
    __slots__ = ("r", "g", "b", "a", "css")

    def __init__(self, r, g, b, a=1.0, css=None):
        self.r, self.g, self.b, self.a = r, g, b, a
        self.css = css if css is not None else self.computed()

    def computed(self):
        r, g, b = (int(c + 0.5) for c in (self.r, self.g, self.b))  # half up, as color tools round
        if self.a >= 1:
            return f"#{r:02x}{g:02x}{b:02x}"
        return f"rgba({r},{g},{b},{round(self.a, 3):g})"

    def luminance(self):
        """WCAG relative luminance (for the contrast check, P3.9)."""
        def lin(c):
            c /= 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * lin(self.r) + 0.7152 * lin(self.g) + 0.0722 * lin(self.b)

    def __eq__(self, other):
        return isinstance(other, Color) and (self.r, self.g, self.b, self.a) == (other.r, other.g, other.b, other.a)

    def __repr__(self):
        return f"Color({self.css!r})"


def contrast(fg, bg, paper=None):
    """The WCAG contrast ratio of two colors (1 to 21). Translucent colors are first laid over the
    one beneath them: bg over paper (white if not given), fg over bg."""
    under = paper or Color(255, 255, 255)
    bg = _over(bg, under)
    fg = _over(fg, bg)
    a, b = sorted((fg.luminance(), bg.luminance()), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _over(c, under):
    if c.a >= 1:
        return c
    return Color(c.r * c.a + under.r * (1 - c.a), c.g * c.a + under.g * (1 - c.a), c.b * c.a + under.b * (1 - c.a), 1.0)


def _split_args(s):
    return [p for p in re.split(r"[\s,/]+", s.strip()) if p]


def _channel(v, scale=255):
    v = v.strip()
    return float(v[:-1]) * scale / 100 if v.endswith("%") else float(v)


def color(value, tokens=None, _depth=0):
    """A Color from CSS color text, a token name, var(--token) or mix(a, b, p%)."""
    tokens = tokens or {}
    if isinstance(value, Color):
        return value
    if not isinstance(value, str) or not value.strip():
        raise error(f"{value!r} is not a color", "write a color such as #2e5aa8, rgb(46,90,168), steelblue or accent")
    text = value.strip()
    low = text.lower()
    if _depth > 8:
        raise error(f"the token '{text}' refers to itself", "point the token at a color")
    m = re.fullmatch(r"var\(\s*--([\w-]+)\s*\)", low)
    if m:
        low = text = m.group(1)
    if text in tokens or text.replace("_", "-") in tokens:
        val = tokens.get(text, tokens.get(text.replace("_", "-")))
        return color(val, tokens, _depth + 1)
    if low in ("transparent", "none"):
        return Color(0, 0, 0, 0.0, text)
    if low == "currentcolor":
        return Color(0, 0, 0, 1.0, "currentColor")
    if low in NAMED:
        h = NAMED[low]
        return Color(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 1.0, text)
    m = re.fullmatch(r"#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})", low)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a, text)
    m = re.fullmatch(r"(rgba?|hsla?)\((.*)\)", low)
    if m:
        args = _split_args(m.group(2))
        try:
            if len(args) not in (3, 4):
                raise ValueError
            a = _channel(args[3], 1) if len(args) == 4 else 1.0
            if m.group(1).startswith("rgb"):
                r, g, b = (_channel(x) for x in args[:3])
            else:
                hue = float(args[0].replace("deg", "")) % 360 / 360
                s, li = (float(x.rstrip("%")) / 100 for x in args[1:3])  # 50% or 50: half
                r, g, b = (c * 255 for c in colorsys.hls_to_rgb(hue, li, s))
        except ValueError:
            raise error(f"'{text}' is not a valid {m.group(1)}() color", f"write {m.group(1)}(46, 90, 168)") from None
        return Color(r, g, b, max(0.0, min(1.0, a)), text)
    m = re.fullmatch(r"mix\((.*)\)", low)
    if m:
        parts = [p.strip() for p in re.split(r",(?![^(]*\))", text[text.index("(") + 1:-1])]
        if len(parts) != 3 or not parts[2].endswith("%"):
            raise error(f"'{text}' is not mix(a, b, p%)", "write mix(accent, white, 30%): 30% of the second color")
        a, b = color(parts[0], tokens, _depth + 1), color(parts[1], tokens, _depth + 1)
        p = float(parts[2][:-1]) / 100
        return Color(a.r + (b.r - a.r) * p, a.g + (b.g - a.g) * p, a.b + (b.b - a.b) * p, a.a + (b.a - a.a) * p)
    near = _near(low, list(NAMED) + list(tokens))
    raise error(f"'{text}' is not a color or a token", "write a hex color, rgb(), hsl(), a CSS color name, or a token "
                f"({', '.join(sorted(k for k in tokens if isinstance(tokens[k], str) and not k.startswith('font'))[:8])})",
                near)


def length(value, font_size=None):
    """A length in px: a number, "12px", or "1.5em" (needs the font size)."""
    if isinstance(value, bool):
        raise error(f"{value!r} is not a length", "write a number of pixels, e.g. 2 or 2px")
    if isinstance(value, (int, float)):
        return float(value)
    m = re.fullmatch(r"\s*(-?\d*\.?\d+)\s*(px|em)?\s*", str(value))
    if not m:
        raise error(f"'{value}' is not a length", "write pixels (2 or 2px) or em (1.5em)")
    n = float(m.group(1))
    if m.group(2) == "em":
        if font_size is None:
            raise error(f"'{value}' needs a font size to mean anything here", "write it in pixels")
        return n * font_size
    return n


def _four(value, font_size=None):
    """1 to 4 lengths spread over four places, as CSS does: a; a b; a b c; a b c d."""
    parts = value.split() if isinstance(value, str) else [value]
    if not 1 <= len(parts) <= 4:
        raise error(f"'{value}' should have 1 to 4 lengths", "write 8, or 8 12, or 8 12 8 12")
    v = [length(p, font_size) for p in parts]
    if len(v) == 1:
        return (v[0],) * 4
    if len(v) == 2:
        return (v[0], v[1], v[0], v[1])
    if len(v) == 3:
        return (v[0], v[1], v[2], v[1])
    return tuple(v)


def box4(value, font_size=None):
    """padding: (top, right, bottom, left)."""
    return _four(value, font_size)


def radius(value, font_size=None):
    """border-radius: (top-left, top-right, bottom-right, bottom-left)."""
    return _four(value, font_size)


def border(value, tokens=None):
    """border, border-<side>: {"width", "style", "color"}; "none" or 0 width draws nothing."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {"width": float(value), "style": "solid", "color": None}
    text = str(value).strip()
    if text.lower() == "none":
        return {"width": 0.0, "style": "none", "color": None}
    out = {"width": None, "style": None, "color": None}
    for part in re.findall(r"\w+\([^)]*\)|\S+", text):
        low = part.lower()
        if low in BORDER_STYLES and out["style"] is None:
            out["style"] = low
            continue
        if out["width"] is None:
            try:
                out["width"] = length(part)
                continue
            except SpecError:
                pass
        out["color"] = color(part, tokens)
    out["width"] = 1.0 if out["width"] is None else out["width"]
    out["style"] = out["style"] or "solid"
    if out["style"] == "none":
        out["width"] = 0.0
    return out


def shadows(value, tokens=None):
    """box-shadow: a list of {"x", "y", "blur", "spread", "color", "inset"}; "none" is []."""
    text = str(value).strip()
    if text.lower() == "none":
        return []
    out = []
    for one in re.split(r",(?![^(]*\))", text):
        nums, col, inset = [], None, False
        for part in re.findall(r"\w+\([^)]*\)|\S+", one):
            if part.lower() == "inset":
                inset = True
                continue
            try:
                nums.append(length(part))
            except SpecError:
                col = color(part, tokens)
        if len(nums) < 2 or len(nums) > 4:
            raise error(f"'{one.strip()}' is not a shadow", "write x y [blur [spread]] color, e.g. 0 2px 6px rgba(0,0,0,0.15)")
        nums += [0.0] * (4 - len(nums))
        out.append({"x": nums[0], "y": nums[1], "blur": nums[2], "spread": nums[3],
                    "color": col or Color(0, 0, 0, 0.25), "inset": inset})
    return out


def font(value):
    """font shorthand: {"font-style", "font-weight", "font-size", "line-height", "font-family"}."""
    m = re.fullmatch(r"\s*((?:(?:italic|oblique|normal|bold|bolder|lighter|[1-9]00)\s+)*)"
                     r"(\d*\.?\d+(?:px|em)?)(?:\s*/\s*(\d*\.?\d+))?\s+(.+)", str(value))
    if not m:
        raise error(f"'{value}' is not a font shorthand", "write [style] [weight] size[/line-height] family, e.g. 600 13px Inter")
    out = {"font-size": length(m.group(2), 13), "font-family": m.group(4).strip()}
    for word in m.group(1).split():
        out["font-style" if word in ("italic", "oblique", "normal") else "font-weight"] = word
    if m.group(3):
        out["line-height"] = float(m.group(3))
    return out


def weight(value):
    text = str(value).strip().lower()
    if text in ("normal", "bold", "bolder", "lighter") or re.fullmatch(r"[1-9]00", text):
        return text
    raise error(f"'{value}' is not a font weight", "write normal, bold, or 100 to 900")


def gradient(value, tokens=None):
    """linear-gradient(angle or `to side`, color [stop%], ...): {"type", "angle", "stops"}."""
    m = re.fullmatch(r"\s*linear-gradient\((.*)\)\s*", str(value), re.S)
    if not m:
        raise error(f"'{value}' is not a linear-gradient()", "write linear-gradient(180deg, #fff, #eee)")
    parts = [p.strip() for p in re.split(r",(?![^(]*\))", m.group(1))]
    angle = 180.0
    sides = {"to top": 0.0, "to right": 90.0, "to bottom": 180.0, "to left": 270.0}
    if parts and (parts[0].lower() in sides or re.fullmatch(r"-?\d*\.?\d+deg", parts[0].lower())):
        first = parts.pop(0).lower()
        angle = sides.get(first, float(first[:-3]) if first.endswith("deg") else 180.0)
    if len(parts) < 2:
        raise error(f"'{value}' needs two colors or more", "write linear-gradient(180deg, #fff, #eee)")
    stops = []
    for k, p in enumerate(parts):
        mm = re.fullmatch(r"(.*?)\s+(\d*\.?\d+)%", p)
        col, at = (mm.group(1), float(mm.group(2)) / 100) if mm else (p, k / (len(parts) - 1))
        stops.append((at, color(col, tokens)))
    return {"type": "linear", "angle": angle, "stops": stops}


def paint(value, tokens=None):
    """fill, background, stroke: a color, none, or a linear-gradient()."""
    if isinstance(value, str) and value.strip().lower().startswith("linear-gradient("):
        return gradient(value, tokens)
    return color(value, tokens)


def value(prop, raw, tokens=None, font_size=None):
    """One property's value, checked and read. Unknown properties and values are errors."""
    kind = PROPERTIES.get(prop)
    if kind is None:
        raise error(f"'{prop}' is not a style property", "see `describe style` for the list", _near(prop, PROPERTIES))
    if isinstance(raw, dict) and "field" in raw:
        return raw  # an encoding: read later, against the data (P3.7)
    if isinstance(kind, tuple):
        word = str(raw).strip().lower()
        if word not in kind:
            raise error(f"{prop}: '{raw}' is not one of {', '.join(kind)}", f"use one of: {', '.join(kind)}", _near(word, kind))
        return word
    if kind in ("color",):
        return color(raw, tokens)
    if kind == "paint":
        return paint(raw, tokens)
    if kind == "length":
        if isinstance(raw, str) and tokens and raw.strip() in tokens:  # size-s, radius, stroke ...
            raw = tokens[raw.strip()]
        return length(raw, font_size)
    if kind == "number":
        try:
            return float(raw)
        except (TypeError, ValueError):
            raise error(f"{prop}: '{raw}' is not a number", "write a number, e.g. 0.8") from None
    if kind == "int":
        if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
            return raw
        raise error(f"{prop}: '{raw}' is not a whole number above 0", "write e.g. 2")
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        raise error(f"{prop}: '{raw}' is not true or false", "write true or false")
    if kind == "padding":
        return box4(raw, font_size)
    if kind == "radius":
        return radius(raw, font_size)
    if kind == "border":
        return border(raw, tokens)
    if kind == "shadow":
        return shadows(raw, tokens)
    if kind == "glow":
        return None if str(raw).lower() == "none" else color(raw, tokens)
    if kind == "font":
        return font(raw)
    if kind == "weight":
        return weight(raw)
    if kind == "dasharray":
        text = str(raw).strip()
        if text.lower() == "none":
            return None
        return [length(p) for p in re.split(r"[\s,]+", text) if p]
    if kind == "family" and isinstance(raw, str) and tokens and raw.strip() in tokens:
        return tokens[raw.strip()]  # font, font-mono
    return raw  # word, family, text: taken as written

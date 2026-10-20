"""Encodings and scales: style values that come from data.

    "node": {"fill": {"field": "p99", "scale": {"type": "sequential", "scheme": "heat", "domain": [0, 500]}}}
    "edge": {"stroke-width": {"field": "rps", "scale": {"type": "linear", "range": [1, 6]}}}

A scale reads every element's value for its field, so a domain left out is the data's own extent.
Its type is inferred when not given: numbers on a color property are sequential, words are
categorical, and numbers on a numeric property are linear. Color ranges come from a named scheme,
a palette token (sequential, diverging, categorical) or a list of colors. An element without the
field gets the scale's neutral value: a light grey, or the low end of a numeric range.

Charts share this code.
"""
from ..errors import SpecError
from .parse import Color, color

SCHEMES = {
    "heat": ["#fff5eb", "#fdd0a2", "#fd8d3c", "#d94801", "#7f2704"],
    "blues": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
    "greens": ["#f7fcf5", "#c7e9c0", "#74c476", "#238b45", "#00441b"],
    "greys": ["#f7f7f7", "#cccccc", "#969696", "#525252", "#252525"],
}
COLOR_PROPS = {"fill", "stroke", "color", "background", "icon-color", "glow"}


def _number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class Scale:
    def __init__(self, prop, enc, values, tokens):
        self.prop, self.field = prop, enc.get("field")
        spec = enc.get("scale") or {}
        if not isinstance(spec, dict):
            raise SpecError(f"{prop}: the scale should be an object", 'write "scale": {"type": "sequential"}', "bad-style")
        present = [v for v in values if v is not None]
        numeric = bool(present) and all(_number(v) is not None for v in present)
        is_color = prop in COLOR_PROPS
        if spec.get("type"):
            self.type = spec["type"]
        elif is_color:
            self.type = "sequential" if numeric else "categorical"
        else:
            self.type = "linear"
        if self.type not in ("linear", "sequential", "categorical"):
            raise SpecError(f"{prop}: '{self.type}' is not a scale type", "use linear, sequential or categorical", "bad-style")
        if self.type == "categorical":
            self.domain = list(spec.get("domain") or dict.fromkeys(str(v) for v in present))
        else:
            nums = [_number(v) for v in present if _number(v) is not None]
            dom = spec.get("domain") or ([min(nums), max(nums)] if nums else [0, 1])
            self.domain = [float(dom[0]), float(dom[-1])]
        rng = spec.get("range") or spec.get("scheme")
        if is_color:
            if isinstance(rng, str):
                rng = SCHEMES.get(rng) or tokens.get(rng)
                if rng is None:
                    raise SpecError(f"{prop}: no color scheme '{spec.get('scheme') or spec.get('range')}'",
                                    f"use one of: {', '.join(sorted(SCHEMES))}, or a palette token (sequential, "
                                    "diverging, categorical), or a list of colors", "bad-style")
            rng = rng or tokens.get("categorical" if self.type == "categorical" else "sequential")
            self.range = [color(c, tokens) for c in rng]
            self.neutral = Color(229, 231, 235, 1.0)  # an element without the field
        else:
            rng = rng or [1, 6]
            self.range = [float(rng[0]), float(rng[-1])]
            self.neutral = self.range[0]

    def __call__(self, value):
        if value is None:
            return self.neutral
        if self.type == "categorical":
            key = str(value)
            if key not in self.domain:
                self.domain.append(key)
            return self.range[self.domain.index(key) % len(self.range)]
        x = _number(value)
        if x is None:
            return self.neutral
        lo, hi = self.domain
        t = 0.0 if hi == lo else max(0.0, min(1.0, (x - lo) / (hi - lo)))
        if isinstance(self.range[0], Color):
            return _ramp(self.range, t)
        return self.range[0] + (self.range[1] - self.range[0]) * t

    def legend(self, steps=3):
        """[(label, value)] for a legend: each category, or the domain's low, middle and high."""
        if self.type == "categorical":
            return [(k, self(k)) for k in self.domain[:8]]
        lo, hi = self.domain
        marks = [lo + (hi - lo) * k / (steps - 1) for k in range(steps)]
        return [(_fmt(v), self(v)) for v in marks]


def _ramp(colors, t):
    """A color t of the way along stops spread evenly."""
    if len(colors) == 1:
        return colors[0]
    pos = t * (len(colors) - 1)
    k = min(int(pos), len(colors) - 2)
    f = pos - k
    a, b = colors[k], colors[k + 1]
    return Color(a.r + (b.r - a.r) * f, a.g + (b.g - a.g) * f, a.b + (b.b - a.b) * f, a.a + (b.a - a.a) * f)


def _fmt(v):
    return f"{v:,.0f}" if abs(v) >= 100 or v == int(v) else f"{v:.2g}"


def is_encoding(value):
    return isinstance(value, dict) and "field" in value

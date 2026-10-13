"""Tokens and themes (DESIGN 5.6).

Tokens are named values: colors (paper, ink, accent, ...), type sizes, spacing, strokes and
palettes. A theme is a stylesheet whose tokens set the colors; it extends `core`, which holds the
type, space and palette tokens every theme shares. editorial, ink and print ship as JSON in
themes/, so a brand stylesheet is a copy with other values.

v1_theme() gives the flat theme dict the renderers have always read (accent_tint with an
underscore, plus _name), built from the same tokens.
"""
import json
import os

from ..errors import SpecError

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
PRESETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")  # each preset's look, as rules
THEME_NAMES = ("editorial", "ink", "print")
V1_KEYS = ("paper", "ink", "muted", "soft", "rule", "accent", "accent_tint", "link", "card")
_SHEETS = {}


def sheet(name):
    """A bundled stylesheet by name, as written (extends not resolved)."""
    if name not in _SHEETS:
        path = os.path.join(HERE, f"{name}.json")
        if not os.path.isfile(path):
            path = os.path.join(PRESETS, f"{name}.json")
        if not os.path.isfile(path):
            raise SpecError(f"no stylesheet named '{name}'", f"use one of: {', '.join(THEME_NAMES)}", "unknown-theme")
        with open(path, encoding="utf-8") as f:
            _SHEETS[name] = json.load(f)
    return _SHEETS[name]


def tokens(name, _seen=()):
    """Every token a bundled stylesheet sets, the sheets it extends first."""
    if name in _seen:
        raise SpecError(f"stylesheet '{name}' extends itself", "remove the loop from its extends list", "style-cycle")
    s = sheet(name)
    out = {}
    for base in s.get("extends", []):
        out.update(tokens(base, _seen + (name,)))
    out.update(s.get("tokens", {}))
    return out


def token_name(key):
    """accent_tint and accent-tint are the same token (v1 theme files write the underscore)."""
    return key.replace("_", "-")


def v1_theme(name, overrides=None):
    """The flat theme dict the renderers read: the nine color keys, with _name."""
    t = tokens(name)
    out = {k: t[token_name(k)] for k in V1_KEYS}
    for k, v in (overrides or {}).items():
        out[k.replace("-", "_")] = v
    out["_name"] = name
    return out


def read_theme_file(path):
    """--theme-file: either v1's flat keys ({"accent": ..., "accent_tint": ...}) or a stylesheet with
    "tokens". Returns the overrides with v1 key names; unknown keys are an error with the known ones."""
    try:
        with open(path, encoding="utf-8") as f:
            custom = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise SpecError(f"bad --theme-file: {e}", "pass a JSON file of theme keys, e.g. {\"accent\": \"#7c3aed\"}",
                        "bad-theme") from None
    if not isinstance(custom, dict):
        raise SpecError("bad --theme-file: it is not a JSON object", 'write {"accent": "#7c3aed"}', "bad-theme")
    if isinstance(custom.get("tokens"), dict):
        custom = custom["tokens"]
    known = {token_name(k) for k in V1_KEYS}
    unknown = sorted(k for k in custom if token_name(k) not in known)
    if unknown:
        raise SpecError(f"--theme-file unknown keys {unknown}; known: {sorted(V1_KEYS)}",
                        "use the theme's color keys (accent_tint and accent-tint both work)", "bad-theme")
    return {token_name(k).replace("-", "_"): v for k, v in custom.items()}

"""Raw SVG from a spec, made safe to draw.

A node's `content: {"svg": "<g>...</g>"}` is the lowest level of control. Specs
arrive from agents, MCP clients and documents, so the markup is reduced to an allowlist of drawing
elements and attributes before anything else sees it:

- no scripts, event handlers (on*), foreignObject, links, images, iframes or style blocks;
- references only within the fragment: href="#id" and url(#id), never another file or site;
- no DOCTYPE or entity declarations at all (they are refused, not cleaned);
- bounded: at most MAX_CHARS characters and MAX_ELEMENTS elements.

sanitize() returns (clean markup, what was removed). It raises SpecError when the markup can't be
read or is over the limits.
"""
import re
import xml.etree.ElementTree as ET

from .errors import SpecError

MAX_CHARS = 200_000
MAX_ELEMENTS = 5_000
ELEMENTS = {
    "svg", "g", "defs", "symbol", "use", "title", "desc", "path", "rect", "circle", "ellipse", "line",
    "polyline", "polygon", "text", "tspan", "textPath", "linearGradient", "radialGradient", "stop",
    "clipPath", "mask", "pattern", "marker",
}
ATTRS = {
    "id", "class", "d", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height",
    "points", "transform", "viewBox", "preserveAspectRatio", "fill", "fill-opacity", "fill-rule",
    "stroke", "stroke-width", "stroke-opacity", "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
    "stroke-dashoffset", "stroke-miterlimit", "opacity", "color", "font-family", "font-size", "font-weight",
    "font-style", "text-anchor", "dominant-baseline", "letter-spacing", "dx", "dy", "rotate", "offset",
    "stop-color", "stop-opacity", "gradientUnits", "gradientTransform", "spreadMethod", "fx", "fy",
    "clip-path", "clip-rule", "mask", "patternUnits", "patternContentUnits", "patternTransform",
    "markerWidth", "markerHeight", "refX", "refY", "orient", "markerUnits", "marker-start", "marker-mid",
    "marker-end", "href", "visibility", "display", "vector-effect", "paint-order", "style",
}
_URL = re.compile(r"url\(\s*['\"]?\s*([^)'\"\s]*)", re.I)
_BAD_VALUE = re.compile(r"javascript:|vbscript:|data:|expression\s*\(|@import", re.I)


def _local(name):
    return name.rsplit("}", 1)[-1]


def _safe_value(name, value):
    """Why an attribute value is unsafe, or None."""
    if _BAD_VALUE.search(value):
        return "a script or data URL"
    if name == "href" and not value.startswith("#"):
        return "a reference outside the content"
    for ref in _URL.findall(value):
        if not ref.startswith("#"):
            return "a reference outside the content"
    return None


def sanitize(markup):
    """(clean SVG markup, list of what was removed)."""
    if not isinstance(markup, str):
        raise SpecError("content.svg should be SVG markup as a string", 'write "content": {"svg": "<g>...</g>"}', "bad-value")
    if len(markup) > MAX_CHARS:
        raise SpecError(f"content.svg is {len(markup):,} characters; the limit is {MAX_CHARS:,}",
                        "simplify the drawing, or draw it as nodes and edges", "too-large")
    if re.search(r"<!DOCTYPE|<!ENTITY", markup, re.I):
        raise SpecError("content.svg declares a DOCTYPE or entities, which are not allowed",
                        "remove the <!DOCTYPE ...> and <!ENTITY ...> declarations", "unsafe-svg")
    try:
        root = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">{markup}</svg>')
    except ET.ParseError as e:
        raise SpecError(f"content.svg is not well-formed SVG: {e}", "check the markup: every tag closed, attributes quoted",
                        "bad-value") from None
    if sum(1 for _ in root.iter()) > MAX_ELEMENTS:
        raise SpecError(f"content.svg has more than {MAX_ELEMENTS:,} elements", "simplify the drawing", "too-large")
    removed = []

    def clean(el):
        for child in list(el):
            tag = _local(child.tag) if isinstance(child.tag, str) else None
            if tag not in ELEMENTS:
                removed.append(f"<{tag}>" if tag else "a comment or instruction")
                el.remove(child)
                continue
            for name in list(child.attrib):
                local = _local(name)
                why = "an event handler" if local.lower().startswith("on") else (
                    None if local in ATTRS else "an attribute outside the allowlist")
                why = why or _safe_value(local, child.attrib[name])
                if why:
                    removed.append(f"{local}= on <{tag}> ({why})")
                    del child.attrib[name]
            clean(child)

    clean(root)
    return "".join(_write(c) for c in root) + (_escape(root.text) if root.text and root.text.strip() else ""), removed


def _escape(s, quote=False):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace('"', "&quot;") if quote else s


def _write(el):
    tag = _local(el.tag)
    attrs = "".join(f' {_local(k)}="{_escape(v, True)}"' for k, v in el.attrib.items())
    inner = _escape(el.text or "") + "".join(_write(c) + _escape(c.tail or "") for c in el)
    return f"<{tag}{attrs}>{inner}</{tag}>" if inner else f"<{tag}{attrs}/>"

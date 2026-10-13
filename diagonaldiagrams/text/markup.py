"""Inline markup in labels (DESIGN 4.2): **bold**, _italic_ and `mono`. Everything else is literal.

An underscore counts only at a word's edges, so snake_case and user_id stay as written. runs()
splits a text into (text, kind) pieces, kind being "", "b", "i" or "m"; plain() is the text without
its markers, for names, accessible labels and outlines.
"""
import re

_TOKEN = re.compile(r"\*\*(?P<b>.+?)\*\*|(?<![\w])_(?P<i>[^_\s](?:[^_]*?[^_\s])?)_(?![\w])|`(?P<m>[^`]+)`")


def has_markup(text):
    return bool(_TOKEN.search(str(text)))


def runs(text):
    """[(text, kind)] in order, adjacent plain text kept together."""
    text = str(text)
    out, pos = [], 0
    for m in _TOKEN.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], ""))
        kind = m.lastgroup
        out.append((m.group(kind), kind))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], ""))
    return out or [("", "")]


def plain(text):
    """The text as read aloud: markers removed."""
    return "".join(t for t, _ in runs(text))

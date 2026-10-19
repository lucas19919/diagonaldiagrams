"""Validation basics: one error or warning with its fix, and the list each diagram spec must have."""


def _vissue(errors, warnings, code, msg, fix=""):
    (errors if code == "E" else warnings).append({"msg": msg, "fix": fix} if fix else {"msg": msg})


_SPEC_KEYS = {"flow": "nodes", "arch": "nodes", "seq": "actors", "schema": "tables"}
_FITS = ("slide", "page", "column")  # where a figure goes: size.fit, --fit, Mermaid's fit: (diagrams.FITS sizes each)

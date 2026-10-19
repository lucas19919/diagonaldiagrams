"""Project and organization config.

A project's diagonaldiagrams.toml is found by walking up from the spec's folder (or the working
directory). An organization's file is named by the DIAGONALDIAGRAMS_ORG_CONFIG environment variable
and applies on top of it: its policy and limits can only be added to, never lifted.

    [style]
    sheets = ["brand/house.json"]   # every figure, below --style
    policy = "brand/policy.json"    # locked: the top of the cascade (5.1, layer 8)
    [palette]
    allowed = ["#0f172a", "#7c3aed", "accent"]   # colors and tokens a figure may use
    [fonts]
    allowed = ["Inter", "IBM Plex Sans"]
    files = { Inter = "fonts/Inter.ttf" }
    [defaults]
    theme = "ink"
    corners = "rounded"
    [toolkits]
    enabled = []                    # read from P5 on
    [icons]
    dirs = []                       # read from P8 on

Paths are relative to the file that names them.
"""
import json
import os

from .errors import SpecError

NAME = "diagonaldiagrams.toml"
ENV = "DIAGONALDIAGRAMS_ORG_CONFIG"
KNOWN = {"style": {"sheets", "policy"}, "palette": {"allowed"}, "fonts": {"allowed", "files", "dirs"},
         "defaults": {"theme", "corners"}, "toolkits": {"enabled"}, "icons": {"dirs"}}


class Config:
    def __init__(self):
        self.paths = []            # the config files read, organization last
        self.sheets = []           # stylesheets every figure gets
        self.policies = []         # locked stylesheets
        self.palette = None        # allowed colors (lowercase text), None when unlimited
        self.fonts = None          # allowed families (lowercase), None when unlimited
        self.font_files = {}       # family -> font file
        self.defaults = {}

    def all_sheets(self):
        return self.sheets + [dict(p, policy=True) for p in self.policies]


def find(start=None):
    """The project config file above start (a folder or a file), or None."""
    here = os.path.abspath(start or os.getcwd())
    if os.path.isfile(here):
        here = os.path.dirname(here)
    while True:
        path = os.path.join(here, NAME)
        if os.path.isfile(path):
            return path
        up = os.path.dirname(here)
        if up == here:
            return None
        here = up


def _read_toml(path):
    import tomllib
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise SpecError(f"{path} can't be read: {e}", "fix the TOML; see `describe style` for the keys", "bad-config") from None


def _sheet(path, base, what):
    full = path if os.path.isabs(path) else os.path.join(base, path)
    try:
        with open(full, encoding="utf-8") as f:
            sheet = json.load(f)
    except (OSError, ValueError) as e:
        raise SpecError(f"{what} {full} can't be read: {e}", "point it at a JSON stylesheet", "bad-config") from None
    if not isinstance(sheet, dict):
        raise SpecError(f"{what} {full} is not a stylesheet object", 'write {"tokens": {...}, "rules": {...}}', "bad-config")
    here = os.path.dirname(full)
    fonts = {fam: f if os.path.isabs(f) else os.path.join(here, f) for fam, f in (sheet.get("fonts") or {}).items()}
    return dict(sheet, name=sheet.get("name") or os.path.basename(full), fonts=fonts)


def load(start=None):
    """The config that applies to a spec at start: the project's, then the organization's on top."""
    cfg = Config()
    for path in (find(start), os.environ.get(ENV) or None):
        if not path:
            continue
        if not os.path.isfile(path):
            raise SpecError(f"{ENV} names {path}, which doesn't exist", f"fix or unset {ENV}", "bad-config")
        _apply(cfg, path, _read_toml(path))
    return cfg


def _apply(cfg, path, data):
    import difflib
    base = os.path.dirname(os.path.abspath(path))
    cfg.paths.append(path)
    for section, keys in data.items():
        if section not in KNOWN:
            near = difflib.get_close_matches(section, list(KNOWN), n=1)
            raise SpecError(f"{path}: no section [{section}]" + (f" (did you mean [{near[0]}]?)" if near else ""),
                            f"use: {', '.join(f'[{k}]' for k in KNOWN)}", "bad-config")
        for key in keys if isinstance(keys, dict) else []:
            if key not in KNOWN[section]:
                raise SpecError(f"{path}: [{section}] has no key '{key}'", f"use: {', '.join(sorted(KNOWN[section]))}",
                                "bad-config")
    style = data.get("style", {})
    cfg.sheets += [_sheet(p, base, "a [style] sheet") for p in style.get("sheets", [])]
    if style.get("policy"):
        cfg.policies.append(_sheet(style["policy"], base, "the [style] policy"))
    allowed = data.get("palette", {}).get("allowed")
    if allowed is not None:
        mine = {str(c).strip().lower() for c in allowed}
        cfg.palette = mine if cfg.palette is None else cfg.palette & mine  # a later file narrows, never widens
    fonts = data.get("fonts", {})
    if fonts.get("allowed") is not None:
        mine = {str(f).strip().lower() for f in fonts["allowed"]}
        cfg.fonts = mine if cfg.fonts is None else cfg.fonts & mine
    for fam, f in (fonts.get("files") or {}).items():
        cfg.font_files[fam] = f if os.path.isabs(f) else os.path.join(base, f)
    cfg.defaults.update(data.get("defaults", {}))

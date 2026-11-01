"""diagonaldiagrams: diagrams and charts an agent can draw, and check before it shows you.

The command line is diagonaldiagrams.cli.cli(); `python -m diagonaldiagrams` runs it.
"""

__version__ = "0.9.1"


def __getattr__(name):
    """dd.render() and dd.run() load the API on first use, so importing the package stays cheap."""
    if name in ("render", "run"):
        from . import api
        return getattr(api, name)
    raise AttributeError(f"module 'diagonaldiagrams' has no attribute {name!r}")

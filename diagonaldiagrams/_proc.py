"""Running this same engine in a new process, installed or from a checkout."""
import os, sys


def _self_cmd():
    """The argv prefix and environment that run this same engine in a new process.

    `python -m diagonaldiagrams` with this package's folder first on PYTHONPATH, so a checkout
    runs its own code even when another copy is installed. -P keeps the working directory off
    sys.path, so a diagonaldiagrams/ folder there cannot stand in for this one."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ)
    env["PYTHONPATH"] = root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    flags = ["-P"] if sys.version_info >= (3, 11) else []
    return [sys.executable, *flags, "-m", "diagonaldiagrams"], env

"""Typed errors. The engine raises them; only the command line decides how a process ends."""


class SpecError(Exception):
    """The input cannot be drawn as given: msg says why, fix says what to change.

    The command line prints msg and exits 1, as the engine's sys.exit(msg) calls used to; the
    Python API and an in-process MCP server can catch it and answer with a structured error."""

    def __init__(self, msg, fix="", code="spec", at=None):
        super().__init__(msg)
        self.msg, self.fix, self.code, self.at = msg, fix, code, at

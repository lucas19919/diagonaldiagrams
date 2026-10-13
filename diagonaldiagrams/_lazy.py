"""Functions from modules that are imported on first use.

A module that needs a function from a feature module it does not import at its top (charts,
math, maps, export, the MCP server, ...) holds a proxy made here. The proxy imports the module
on its first call, so each command compiles and loads only the code it runs.
"""
import importlib


def lazy(module, name):
    """A callable that imports `module` on first use and calls its `name`."""
    def call(*args, **kwargs):
        return getattr(importlib.import_module(module), name)(*args, **kwargs)
    call.__name__ = call.__qualname__ = name
    call.lazy_target = (module, name)
    return call

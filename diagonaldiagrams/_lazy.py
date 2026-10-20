"""Functions from modules that are imported on first use.

A module that needs a function from a feature module it does not import at its top (charts,
math, maps, export, the MCP server, ...) holds a proxy made here. The proxy imports the module
on its first call, so each command compiles and loads only the code it runs.
"""
import sys


def lazy(module, name):
    """A callable that imports `module` on first use and calls its `name`. (__import__, not
    importlib.import_module: importlib is one more module to load on every command.)"""
    def call(*args, **kwargs):
        mod = sys.modules.get(module)
        if mod is None:
            __import__(module)
            mod = sys.modules[module]
        return getattr(mod, name)(*args, **kwargs)
    call.__name__ = call.__qualname__ = name
    call.lazy_target = (module, name)
    return call

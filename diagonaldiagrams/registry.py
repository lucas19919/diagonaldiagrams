"""Private registries (PLAN P2.12): name -> function tables for shapes, audit checks and export
formats, filled by the built-in parts with a decorator. P5 opens the same tables to toolkits
(DESIGN 11.1), so a toolkit adds a shape the way the core adds "diamond".
"""


class Registry:
    """Entries in registration order, each a function and its metadata."""

    def __init__(self, kind):
        self.kind, self._items = kind, {}

    def add(self, name, **meta):
        """A decorator that registers the function under name."""
        def register(fn):
            if name in self._items:
                raise ValueError(f"{self.kind} {name!r} is registered twice")
            self._items[name] = (fn, meta)
            return fn
        return register

    def remove(self, name):
        """Take an entry out again (a toolkit unloading, a test cleaning up)."""
        self._items.pop(name, None)

    def get(self, name, default=None):
        """The function registered as name, or default."""
        entry = self._items.get(name)
        return entry[0] if entry else default

    def meta(self, name):
        return self._items[name][1]

    def names(self):
        return list(self._items)

    def items(self):
        """(name, function, metadata) in registration order."""
        return [(name, fn, meta) for name, (fn, meta) in self._items.items()]

    def __contains__(self, name):
        return name in self._items

    def __len__(self):
        return len(self._items)

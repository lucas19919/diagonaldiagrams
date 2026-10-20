"""The scene: what a figure shows. model.py holds the types, normalize.py builds and
checks them from JSON, ids.py names edges. All three import only the standard library's core, so a
renderer that needs ids.py pays a few milliseconds at most."""
from .model import Edge, Group, Node, Scene
from .normalize import check, normalize

__all__ = ["Edge", "Group", "Node", "Scene", "check", "normalize"]

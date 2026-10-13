"""The scene: what a figure shows (DESIGN 4). model.py holds the types; normalize.py builds and
checks them from JSON."""
from .model import Edge, Group, Node, Scene
from .normalize import check, normalize

__all__ = ["Edge", "Group", "Node", "Scene", "check", "normalize"]

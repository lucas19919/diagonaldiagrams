"""Container protocol and layout extension point (DESIGN 7.1, PLAN P4.1).

Every figure is a container tree: the scene is the root container, groups are containers that
draw frames, and a node with `content` holds a nested container or raw SVG.

The protocol:
- measure(ctx, container) -> Size: bottom-up; child items and nested containers are already measured.
- place(ctx, container, box) -> Placement: top-down; places direct children in container-local coordinates.

A Placement holds positions (x, y, optional z for 3D), container-local ports, frames, routes,
and any constraint issues. A layout never paints.
"""


class Size:
    __slots__ = ("w", "h")

    def __init__(self, w=0.0, h=0.0):
        self.w, self.h = float(w), float(h)

    def __iter__(self):
        yield self.w
        yield self.h

    def __getitem__(self, idx):
        return (self.w, self.h)[idx]

    def __len__(self):
        return 2

    def __eq__(self, other):
        if isinstance(other, (tuple, list)) and len(other) == 2:
            return (self.w, self.h) == (float(other[0]), float(other[1]))
        return isinstance(other, Size) and self.w == other.w and self.h == other.h

    def __repr__(self):
        return f"Size({self.w}, {self.h})"


class Placement:
    __slots__ = ("pos", "size", "routes", "frames", "ports", "issues", "extra")

    def __init__(self, pos=None, size=(0.0, 0.0), routes=None, frames=None, ports=None, issues=None, extra=None):
        self.pos = dict(pos) if pos is not None else {}
        self.size = size if isinstance(size, Size) else Size(size[0], size[1])
        self.routes = dict(routes) if routes is not None else {}
        self.frames = dict(frames) if frames is not None else {}
        self.ports = dict(ports) if ports is not None else {}
        self.issues = list(issues) if issues is not None else []
        self.extra = dict(extra) if extra is not None else {}

    def to_dict(self):
        return {
            "pos": {k: [round(x, 2) for x in v] for k, v in self.pos.items()},
            "size": [round(self.size.w, 2), round(self.size.h, 2)],
            "frames": {k: [round(x, 2) for x in v] for k, v in self.frames.items()},
            "routes": {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in self.routes.items()},
            "ports": {k: [round(x, 2) for x in v] for k, v in self.ports.items()},
        }


class Container:
    """A container in the layout tree: the root figure, a group frame, or a node's content."""
    __slots__ = ("id", "layout", "children", "options", "size", "parent", "content", "edges", "extra")

    def __init__(self, id, layout=None, children=None, options=None, size=None, parent=None, content=None,
                 edges=None, extra=None):
        self.id = str(id)
        self.layout = layout
        self.children = list(children or [])
        self.options = dict(options or {})
        self.size = size or Size(0.0, 0.0)
        self.parent = parent
        self.content = content
        self.edges = list(edges or [])
        self.extra = dict(extra or {})

    def add(self, child):
        self.children.append(child)
        if isinstance(child, Container):
            child.parent = self.id


class Layout:
    """Base class and protocol for layout kernels (DESIGN 7.1)."""
    name = ""
    options = {}

    def measure(self, ctx, container) -> Size:
        """Calculates container size after its children have been measured."""
        raise NotImplementedError

    def place(self, ctx, container, box) -> Placement:
        """Places direct children within box (x, y, w, h). Returns a Placement."""
        raise NotImplementedError


LAYOUTS = {}


def register(name, layout_cls):
    """Registers a layout kernel by name."""
    LAYOUTS[name] = layout_cls


def get_layout(spec_or_name):
    """Resolves a layout instance from a name string or options dict."""
    if isinstance(spec_or_name, Layout):
        return spec_or_name
    if isinstance(spec_or_name, dict):
        t = spec_or_name.get("type") or spec_or_name.get("name")
        cls = LAYOUTS.get(t)
        if cls:
            return cls(spec_or_name)
    elif isinstance(spec_or_name, str):
        cls = LAYOUTS.get(spec_or_name)
        if cls:
            return cls()
    return None


def _measure_svg_content(content):
    """Extracts intrinsic width/height from sanitized SVG content or viewBox."""
    if not isinstance(content, dict):
        return 0.0, 0.0
    vb = content.get("viewBox") or content.get("viewbox")
    if vb and isinstance(vb, str):
        parts = vb.replace(",", " ").split()
        if len(parts) == 4:
            try:
                return float(parts[2]), float(parts[3])
            except (ValueError, TypeError):
                pass
    w = content.get("width") or content.get("w")
    h = content.get("height") or content.get("h")
    try:
        if w is not None and h is not None:
            return float(w), float(h)
    except (ValueError, TypeError):
        pass
    return 32.0, 32.0


def measure_node_content(ctx, node):
    """Updates node dimensions if it holds nested container or SVG content."""
    content = getattr(node, "content", None) or (node.get("content") if isinstance(node, dict) else None)
    if not content:
        return
    if isinstance(content, dict) and "svg" in content:
        cw, ch = _measure_svg_content(content)
        pad = 16.0
        if isinstance(node, dict):
            node["w"] = max(float(node.get("w", 0)), cw + pad * 2)
            node["h"] = max(float(node.get("h", 0)), ch + pad * 2)
        else:
            node.w = max(float(getattr(node, "w", 0)), cw + pad * 2)
            node.h = max(float(getattr(node, "h", 0)), ch + pad * 2)
    elif isinstance(content, Container):
        csize = measure_tree(ctx, content)
        pad = 20.0
        if isinstance(node, dict):
            node["w"] = max(float(node.get("w", 0)), csize.w + pad * 2)
            node["h"] = max(float(node.get("h", 0)), csize.h + pad * 2)
        else:
            node.w = max(float(getattr(node, "w", 0)), csize.w + pad * 2)
            node.h = max(float(getattr(node, "h", 0)), csize.h + pad * 2)


def measure_tree(ctx, container):
    """Bottom-up measurement over container tree."""
    for child in container.children:
        if isinstance(child, Container):
            measure_tree(ctx, child)
        else:
            measure_node_content(ctx, child)
    lay = get_layout(container.layout)
    if lay:
        container.size = lay.measure(ctx, container)
    return container.size


def place_tree(ctx, container, box=None):
    """Top-down placement over container tree."""
    if box is None:
        box = (0.0, 0.0, container.size.w, container.size.h)
    bx, by, bw, bh = box
    lay = get_layout(container.layout)
    if lay:
        placement = lay.place(ctx, container, box)
    else:
        placement = Placement(size=(bw, bh))

    for child in container.children:
        if isinstance(child, Container) and child.id in placement.pos:
            cx, cy = placement.pos[child.id]
            cbox = (cx, cy, child.size.w, child.size.h)
            sub = place_tree(ctx, child, cbox)
            for k, pt in sub.pos.items():
                placement.pos[k] = (pt[0] + cx, pt[1] + cy)
            for k, fr in sub.frames.items():
                placement.frames[k] = (fr[0] + cx, fr[1] + cy, fr[2] + cx, fr[3] + cy)
            for k, rt in sub.routes.items():
                placement.routes[k] = rt
            for k, pt in sub.ports.items():
                placement.ports[k] = (pt[0] + cx, pt[1] + cy, *pt[2:])
            placement.issues.extend(sub.issues)
    return placement

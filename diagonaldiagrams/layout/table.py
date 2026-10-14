"""Table / schema layout kernel (DESIGN 7.2, PLAN P4.5): database schemas, ER diagrams, UML classes.

Places tables in rows with row pitch based on the tallest table (fixing B6), with column rows
acting as port anchors for orthogonal relationship routing.
"""
from .base import Layout, Placement, Size, register


class TableLayout(Layout):
    name = "table"
    options = {
        "columns": 3,
        "gap_x": 48.0,
        "gap_y": 64.0,
        "pad": 32.0,
        "table_w": 200.0,
        "header_h": 32.0,
        "row_h": 22.0,
    }

    def __init__(self, options=None):
        self.opts = dict(self.options, **(options or {}))

    def _tables_relations(self, container):
        tables = []
        for c in container.children:
            cid = getattr(c, "id", c.get("id") if isinstance(c, dict) else str(c))
            name = getattr(c, "name", c.get("name", cid) if isinstance(c, dict) else cid)
            cols = getattr(c, "columns", c.get("columns", []) if isinstance(c, dict) else [])
            tw = float(getattr(c, "w", 0) or getattr(getattr(c, "size", None), "w", 0) or (c.get("w", self.opts["table_w"]) if isinstance(c, dict) else self.opts["table_w"]))
            th = float(getattr(c, "h", 0) or getattr(getattr(c, "size", None), "h", 0) or (c.get("h", self.opts["header_h"] + len(cols) * self.opts["row_h"] + 10) if isinstance(c, dict) else 100.0))
            tables.append((cid, name, cols, tw, th))
        relations = getattr(container, "edges", []) or container.extra.get("relations", [])
        return tables, relations

    def measure(self, ctx, container) -> Size:
        tables, _ = self._tables_relations(container)
        if not tables:
            return Size(0.0, 0.0)
        n = len(tables)
        cols_count = max(1, min(int(self.opts.get("columns", 3)), n))
        gx = float(self.opts.get("gap_x", 48.0))
        gy = float(self.opts.get("gap_y", 64.0))
        pad = float(self.opts.get("pad", 32.0))

        col_w = [0.0] * cols_count
        row_count = (n + cols_count - 1) // cols_count
        row_h = [0.0] * row_count

        for i, (tid, name, cols, tw, th) in enumerate(tables):
            c = i % cols_count
            r = i // cols_count
            col_w[c] = max(col_w[c], tw)
            row_h[r] = max(row_h[r], th)  # B6: row pitch = tallest table in the row + gap

        total_w = sum(col_w) + gx * max(0, cols_count - 1) + 2 * pad
        total_h = sum(row_h) + gy * max(0, row_count - 1) + 2 * pad
        return Size(total_w, total_h)

    def place(self, ctx, container, box) -> Placement:
        tables, relations = self._tables_relations(container)
        pos = {}
        ports = {}
        routes = {}
        if not tables:
            return Placement(pos=pos, size=Size(box[2], box[3]))
        n = len(tables)
        cols_count = max(1, min(int(self.opts.get("columns", 3)), n))
        gx = float(self.opts.get("gap_x", 48.0))
        gy = float(self.opts.get("gap_y", 64.0))
        pad = float(self.opts.get("pad", 32.0))
        header_h = float(self.opts.get("header_h", 32.0))
        row_h = float(self.opts.get("row_h", 22.0))

        row_count = (n + cols_count - 1) // cols_count
        col_w = [0.0] * cols_count
        row_h_list = [0.0] * row_count
        for i, (tid, name, cols, tw, th) in enumerate(tables):
            c = i % cols_count
            r = i // cols_count
            col_w[c] = max(col_w[c], tw)
            row_h_list[r] = max(row_h_list[r], th)

        bx, by = box[0] + pad, box[1] + pad
        col_x = [bx]
        for c in range(cols_count - 1):
            col_x.append(col_x[-1] + col_w[c] + gx)
        row_y = [by]
        for r in range(row_count - 1):
            row_y.append(row_y[-1] + row_h_list[r] + gy)

        for i, (tid, name, cols, tw, th) in enumerate(tables):
            c = i % cols_count
            r = i // cols_count
            tx = col_x[c]
            ty = row_y[r]
            cx = tx + tw / 2.0
            cy = ty + th / 2.0
            pos[tid] = (cx, cy)
            # Row ports on left and right borders of each column row
            for idx, col in enumerate(cols):
                col_name = col.get("name") if isinstance(col, dict) else str(col)
                port_y = ty + header_h + idx * row_h + row_h / 2.0
                ports[f"{tid}.{col_name}:w"] = (tx, port_y, -1.0, 0.0)
                ports[f"{tid}.{col_name}:e"] = (tx + tw, port_y, 1.0, 0.0)

        # Route relations between tables
        for i, rel in enumerate(relations):
            rid = rel.get("id") if isinstance(rel, dict) else getattr(rel, "id", f"rel_{i}")
            f_table = rel.get("from") if isinstance(rel, dict) else getattr(rel, "from_", None)
            t_table = rel.get("to") if isinstance(rel, dict) else getattr(rel, "to", None)
            if f_table in pos and t_table in pos:
                fx, fy = pos[f_table]
                tx, ty = pos[t_table]
                routes[rid] = {"id": rid, "points": [(fx, fy), ((fx + tx) / 2.0, fy),
                                                     ((fx + tx) / 2.0, ty), (tx, ty)]}

        return Placement(pos=pos, size=Size(box[2], box[3]), ports=ports, routes=routes)


register("table", TableLayout)
register("schema", TableLayout)

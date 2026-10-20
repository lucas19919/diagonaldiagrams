"""chart math: the equation language, sampling and plotting."""
from ..errors import SpecError
from .._draw import fmt_tick, nice_ticks
from .._text import _text_w, esc
from .._theme import FONT, _hit, series_palette
from ..charts._base import _begin, _cap, _done, _dot, _legend, _short


def _math_prep(src):
    """Turn a small slice of calculator and LaTeX spelling into plain tokens."""
    s = str(src).strip().replace("π", "pi").replace("τ", "tau")
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\,", "").replace("\\;", "").replace("\\!", "").replace("\\ ", "")
    s = s.replace("\\cdot", "*").replace("\\times", "*").replace("\\pi", "pi").replace("\\tau", "tau")
    while True:
        i, j = s.find("\\frac"), s.find("\\sqrt")
        if i < 0 and j < 0:
            break
        if i >= 0 and (j < 0 or i < j):
            k = i + 5
            num, k = _math_braced(s, k)
            den, k = _math_braced(s, k)
            s = s[:i] + "((" + num + ")/(" + den + "))" + s[k:]
        else:
            k = j + 5
            body, k = _math_braced(s, k)
            s = s[:j] + "(sqrt(" + body + "))" + s[k:]
    import re
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)
    return s


def _math_braced(s, i):
    if i >= len(s) or s[i] != "{":
        raise ValueError("expected { }")
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    raise ValueError("unbalanced braces")


def _math_lex(s):
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            j = i + 1
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            if j < n and s[j] in "eE":
                k = j + 1
                if k < n and s[k] in "+-":
                    k += 1
                if k < n and s[k].isdigit():
                    k += 1
                    while k < n and s[k].isdigit():
                        k += 1
                    j = k
            try:
                toks.append(("num", float(s[i:j])))
            except ValueError as exc:
                raise ValueError(f"bad number {s[i:j]}") from exc
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            toks.append(("id", s[i:j]))
            i = j
            continue
        if c in "<>" and i + 1 < n and s[i + 1] == "=":
            toks.append(("op", c + "="))
            i += 2
            continue
        if c == "*" and i + 1 < n and s[i + 1] == "*":
            toks.append(("op", "^"))
            i += 2
            continue
        if c in "+-*/^=<>(),|":
            toks.append(("op", c))
            i += 1
            continue
        raise ValueError(f"unexpected {c!r}")
    return toks


_MATH_CONST = None


_MATH_FUNCS = None


def _math_tables():
    import math
    global _MATH_CONST, _MATH_FUNCS
    if _MATH_FUNCS:
        return _MATH_CONST, _MATH_FUNCS

    def cbrt(v):
        return math.copysign(abs(v) ** (1.0 / 3.0), v)

    def sign(v):
        return float((v > 0) - (v < 0))

    _MATH_CONST = {"pi": math.pi, "e": math.e, "tau": math.tau}
    _MATH_FUNCS = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
        "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "sqrt": math.sqrt, "cbrt": cbrt, "abs": abs, "fabs": abs,
        "floor": math.floor, "ceil": math.ceil, "round": lambda v: float(round(v)),
        "sign": sign, "ln": math.log, "log10": math.log10, "log2": math.log2,
        "exp": math.exp, "min": min, "max": max, "hypot": math.hypot,
    }
    return _MATH_CONST, _MATH_FUNCS


class _MathParse:
    def __init__(self, toks):
        self.toks, self.k = toks, 0

    def peek(self):
        return self.toks[self.k] if self.k < len(self.toks) else None

    def pop(self):
        tok = self.peek()
        if tok is None:
            raise ValueError("unexpected end")
        self.k += 1
        return tok

    def parse(self):
        node = self.comparison()
        if self.peek() is not None:
            raise ValueError(f"unexpected {self.peek()[1]!r}")
        return node

    def comparison(self):
        left = self.add()
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] in ("=", "<", ">", "<=", ">="):
            op = self.pop()[1]
            return ("rel", op, left, self.add())
        return left

    def add(self):
        left = self.mul()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.pop()[1]
            left = ("bin", op, left, self.mul())
        return left

    def mul(self):
        # Juxtaposition binds tighter than * and /, so 1/2x is 1/(2x).
        left = self.jux()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.pop()[1]
            left = ("bin", op, left, self.jux())
        return left

    def jux(self):
        left = self.unary()
        while self._jux():
            left = ("bin", "*", left, self.unary())
        return left

    def _jux(self):
        tok = self.peek()
        if tok is None or tok[0] == "num":
            return False
        if tok[0] == "id":
            return True
        return tok in (("op", "("), ("op", "|"))

    def unary(self):
        if self.peek() in (("op", "+"), ("op", "-")):
            op = self.pop()[1]
            node = self.unary()
            return node if op == "+" else ("neg", node)
        consts, funcs = _math_tables()
        tok = self.peek()
        if tok and tok[0] == "id" and tok[1] in funcs:
            name = self.pop()[1]
            if self.peek() == ("op", "^") and self.k + 1 < len(self.toks) and self.toks[self.k + 1][0] == "num":
                self.pop()
                exp = self.pop()[1]
                return ("bin", "^", ("call", name, [self.unary()]), ("num", exp))
            return ("call", name, [self.unary()] if self.peek() != ("op", "(") else self.args())
        return self.power()

    def args(self):
        self.pop()
        out = [self.add()]
        while self.peek() == ("op", ","):
            self.pop()
            out.append(self.add())
        if self.pop() != ("op", ")"):
            raise ValueError("expected )")
        return out

    def power(self):
        base = self.primary()
        if self.peek() == ("op", "^"):
            self.pop()
            return ("bin", "^", base, self.unary())
        return base

    def primary(self):
        tok = self.pop()
        consts, funcs = _math_tables()
        if tok[0] == "num":
            return ("num", tok[1])
        if tok[0] == "id":
            if tok[1] in consts:
                return ("num", consts[tok[1]])
            if tok[1] in ("x", "y", "t", "u"):
                return ("var", tok[1])
            if tok[1] in funcs:
                raise ValueError(f"{tok[1]} needs an argument")
            raise ValueError(f"unknown name {tok[1]}")
        if tok == ("op", "("):
            node = self.comparison()
            if self.pop() != ("op", ")"):
                raise ValueError("expected )")
            return node
        if tok == ("op", "|"):
            node = self.add()
            if self.pop() != ("op", "|"):
                raise ValueError("expected |")
            return ("abs", node)
        raise ValueError(f"unexpected {tok[1]!r}")


def _math_parse(src):
    return _MathParse(_math_lex(_math_prep(src))).parse()


def _math_vars(node, acc=None):
    acc = set() if acc is None else acc
    kind = node[0]
    if kind == "var":
        acc.add(node[1])
    elif kind in ("neg", "abs"):
        _math_vars(node[1], acc)
    elif kind in ("bin", "rel"):
        _math_vars(node[2], acc)
        _math_vars(node[3], acc)
    elif kind == "call":
        for arg in node[2]:
            _math_vars(arg, acc)
    return acc


def _math_value(node, env, depth=0):
    if depth > 64:
        return None
    try:
        return _math_eval(node, env, depth)
    except (ValueError, ZeroDivisionError, OverflowError, ArithmeticError):
        return None


def _math_eval(node, env, depth):
    import math
    kind = node[0]
    if kind == "num":
        return float(node[1])
    if kind == "var":
        return float(env[node[1]])
    if kind == "neg":
        return -_math_eval(node[1], env, depth + 1)
    if kind == "abs":
        return abs(_math_eval(node[1], env, depth + 1))
    if kind == "bin":
        a = _math_eval(node[2], env, depth + 1)
        b = _math_eval(node[3], env, depth + 1)
        op = node[1]
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                return None
            return a / b
        if a < 0 and abs(b - round(b)) > 1e-9:
            return None
        return math.pow(a, b) if abs(a) > 1e-12 or b >= 0 else None
    if kind == "call":
        args = [_math_eval(a, env, depth + 1) for a in node[2]]
        name = node[1]
        if name == "log":
            if len(args) == 1:
                return math.log10(args[0])
            if len(args) == 2 and args[1] not in (0, 1, -1) and args[0] > 0 and args[1] > 0:
                return math.log(args[0]) / math.log(args[1])
            return None
        fn = _math_tables()[1][name]
        return float(fn(*args))
    return None


def _math_const(node):
    if _math_vars(node):
        raise ValueError("bounds must be numbers")
    value = _math_value(node, {})
    if value is None:
        raise ValueError("bounds must be numbers")
    return value


def _math_peel_for(src):
    import re
    match = re.search(r"^(.*?)\s+\bfor\s+([A-Za-z])\s+in\s*\[\s*([^,\]]+?)\s*,\s*([^\]]+?)\s*\]\s*$", src.strip())
    if not match:
        return src.strip(), None, None, None
    return match.group(1).strip(), match.group(2), match.group(3).strip(), match.group(4).strip()


def _math_pair(src):
    if not src.startswith("("):
        return None
    depth, comma = 0, None
    for i, ch in enumerate(src):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                if i != len(src) - 1:
                    return None
                break
        elif ch == "," and depth == 1 and comma is None:
            comma = i
    if depth != 0 or comma is None:
        return None
    return src[1:comma].strip(), src[comma + 1:-1].strip()


def _math_compile_item(item):
    if isinstance(item, str):
        item = {"expr": item}
    if not isinstance(item, dict) or not str(item.get("expr") or "").strip():
        raise ValueError("an equation needs expr")
    original = str(item["expr"]).strip()
    try:
        body, param, lo_s, hi_s = _math_peel_for(original)
        pair = _math_pair(_math_prep(body))
        if pair:
            left, right = _math_parse(pair[0]), _math_parse(pair[1])
            if param:
                names = {param}
                t0, t1 = _math_const(_math_parse(lo_s)), _math_const(_math_parse(hi_s))
            else:
                used = _math_vars(left) | _math_vars(right)
                names = used & {"t", "u", "x"}
                t0 = float(item["tmin"]) if "tmin" in item else 0.0
                t1 = float(item["tmax"]) if "tmax" in item else (2 * _math_tables()[0]["pi"])
            if len(names) > 1:
                raise ValueError("a parametric curve uses one parameter")
            name = item.get("name") or original
            if not names:
                return {"kind": "point", "x": _math_const(left), "y": _math_const(right),
                        "name": name, "expr": original, "focal": bool(item.get("focal"))}
            return {"kind": "parametric", "x": left, "y": right, "param": names.pop(),
                    "tmin": t0, "tmax": t1, "name": name, "expr": original, "focal": bool(item.get("focal"))}
        node = _math_parse(body)
    except ValueError as exc:
        raise ValueError(f"cannot read {original}: {exc}") from None
    name = item.get("name") or original
    focal = bool(item.get("focal"))
    if node[0] == "rel":
        op, lhs, rhs = node[1], node[2], node[3]
        diff = ("bin", "-", lhs, rhs)
        if lhs == ("var", "y") and "y" not in _math_vars(rhs):
            kind = "explicit" if op == "=" else "ineq"
            return {"kind": kind, "var": "x", "fn": rhs, "op": op, "diff": diff,
                    "name": name, "expr": original, "focal": focal}
        if lhs == ("var", "x") and "x" not in _math_vars(rhs):
            if op != "=":
                raise ValueError(f"cannot read {original}: inequality in x is not drawn")
            return {"kind": "explicit", "var": "y", "fn": rhs, "op": op, "diff": diff,
                    "name": name, "expr": original, "focal": focal}
        if op == "=":
            return {"kind": "implicit", "diff": diff, "name": name, "expr": original, "focal": focal}
        return {"kind": "region", "diff": diff, "op": op, "name": name, "expr": original, "focal": focal}
    used = _math_vars(node)
    if "y" not in used:
        return {"kind": "explicit", "var": "x", "fn": node, "op": "=", "name": name, "expr": original, "focal": focal}
    if "x" not in used:
        return {"kind": "explicit", "var": "y", "fn": node, "op": "=", "name": name, "expr": original, "focal": focal}
    return {"kind": "implicit", "diff": node, "name": name, "expr": original, "focal": focal}


def _math_items(spec):
    if not isinstance(spec, dict):
        raise ValueError("math spec must be a JSON object")
    raw = spec.get("equations", spec.get("expr"))
    if isinstance(raw, str):
        raw = [raw]
    raw = list(raw or [])
    if not raw and not spec.get("points"):
        raise ValueError("math needs an equation")
    return raw


def _math_from_text(path):
    spec = {"equations": []}
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, val = line.partition("=")
            if sep and key.strip() in ("xmin", "xmax", "ymin", "ymax", "samples", "title", "sub", "equal"):
                key, val = key.strip(), val.strip()
                if key == "equal":
                    spec[key] = val.lower() in ("1", "true", "yes")
                elif key in ("title", "sub"):
                    spec[key] = val
                else:
                    spec[key] = float(val)
                continue
            spec["equations"].append(line)
    if not spec["equations"]:
        raise ValueError("math needs an equation")
    return spec


def _math_call(fn_node, var, value):
    env = {"x": 0.0, "y": 0.0, "t": 0.0, "u": 0.0, var: value}
    value = _math_value(fn_node, env)
    if value is None or value != value or abs(value) > 1e6:
        return None
    return value


def _math_field(node, x, y):
    value = _math_value(node, {"x": x, "y": y, "t": 0.0, "u": 0.0})
    if value is None or value != value or abs(value) > 1e6:
        return None
    return value


def _math_sample(fn_node, var, lo, hi, n):
    n = max(48, min(int(n or 360), 1600))
    xs = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    ys = [_math_call(fn_node, var, x) for x in xs]
    rx, ry = [xs[0]], [ys[0]]
    for i in range(n - 1):
        y1, y2 = ys[i], ys[i + 1]
        mid = _math_call(fn_node, var, (xs[i] + xs[i + 1]) / 2)
        if y1 is not None and y2 is not None and mid is not None:
            chord = abs(mid - (y1 + y2) / 2)
            if chord > 0.015 * max(1.0, abs(y1), abs(y2), abs(mid)):
                rx.append((xs[i] + xs[i + 1]) / 2)
                ry.append(mid)
        rx.append(xs[i + 1])
        ry.append(ys[i + 1])
    lines, cur = [], []
    for x, y in zip(rx, ry):
        if y is None:
            if len(cur) > 1:
                lines.append(cur)
            cur = []
            continue
        if cur:
            y0 = cur[-1][1]
            if y0 * y < 0 and abs(y0) > 8 and abs(y) > 8:
                mid = _math_call(fn_node, var, (cur[-1][0] + x) / 2)
                if mid is None or abs(mid) > max(abs(y0), abs(y)):
                    if len(cur) > 1:
                        lines.append(cur)
                    cur = [(x, y)]
                    continue
        cur.append((x, y))
    if len(cur) > 1:
        lines.append(cur)
    if var == "y":
        lines = [[(y, x) for x, y in line] for line in lines]
    return lines


def _math_clip_seg(x1, y1, x2, y2, xmin, xmax, ymin, ymax):
    dx, dy = x2 - x1, y2 - y1
    u1, u2 = 0.0, 1.0
    for pi, qi in ((-dx, x1 - xmin), (dx, xmax - x1), (-dy, y1 - ymin), (dy, ymax - y1)):
        if abs(pi) < 1e-15:
            if qi < 0:
                return None
            continue
        t = qi / pi
        if pi < 0:
            if t > u2:
                return None
            u1 = max(u1, t)
        else:
            if t < u1:
                return None
            u2 = min(u2, t)
    if u1 > u2:
        return None
    return (x1 + u1 * dx, y1 + u1 * dy, x1 + u2 * dx, y1 + u2 * dy)


def _math_clip_chain(pts, box):
    xmin, xmax, ymin, ymax = box
    out, cur = [], []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        hit = _math_clip_seg(x1, y1, x2, y2, xmin, xmax, ymin, ymax)
        if not hit:
            if len(cur) > 1:
                out.append(cur)
            cur = []
            continue
        a, b = (hit[0], hit[1]), (hit[2], hit[3])
        if not cur or abs(a[0] - cur[-1][0]) > 1e-7 or abs(a[1] - cur[-1][1]) > 1e-7:
            if len(cur) > 1:
                out.append(cur)
            cur = [a, b]
        else:
            cur.append(b)
    if len(cur) > 1:
        out.append(cur)
    return out


def _math_march(diff, xmin, xmax, ymin, ymax, n=72):
    xs = [xmin + (xmax - xmin) * i / n for i in range(n + 1)]
    ys = [ymin + (ymax - ymin) * j / n for j in range(n + 1)]
    grid = [[_math_field(diff, xs[i], ys[j]) for i in range(n + 1)] for j in range(n + 1)]
    segs = []

    def cross(p, q, vp, vq):
        if vp is None or vq is None or vp == vq:
            t = 0.5
        else:
            t = vp / (vp - vq)
        t = max(0.0, min(1.0, t))
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)

    for j in range(n):
        for i in range(n):
            corners = (grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i])
            if any(v is None for v in corners):
                continue
            bit = (1 if corners[0] < 0 else 0) | (2 if corners[1] < 0 else 0)
            bit |= (4 if corners[2] < 0 else 0) | (8 if corners[3] < 0 else 0)
            if bit in (0, 15):
                continue
            sw, se = (xs[i], ys[j]), (xs[i + 1], ys[j])
            ne, nw = (xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1])
            edge = {
                "B": cross(sw, se, corners[0], corners[1]),
                "R": cross(se, ne, corners[1], corners[2]),
                "T": cross(ne, nw, corners[2], corners[3]),
                "L": cross(nw, sw, corners[3], corners[0]),
            }
            pairs = {
                1: [("L", "B")], 2: [("B", "R")], 3: [("L", "R")], 4: [("R", "T")],
                6: [("B", "T")], 7: [("L", "T")], 8: [("T", "L")], 9: [("B", "T")],
                11: [("R", "T")], 12: [("R", "L")], 13: [("B", "R")], 14: [("L", "B")],
            }.get(bit)
            if bit in (5, 10):
                center = _math_field(diff, (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2)
                neg = center is not None and center < 0
                pairs = [("L", "B"), ("R", "T")] if (bit == 5) == neg else [("B", "R"), ("T", "L")]
                if bit == 10:
                    pairs = [("B", "L"), ("T", "R")] if neg else [("L", "T"), ("R", "B")]
            for a, b in pairs or []:
                segs.append((edge[a], edge[b]))
    return _math_stitch(segs)


def _math_stitch(segs):
    def key(pt):
        return (round(pt[0], 5), round(pt[1], 5))

    adj, edges = {}, {}
    for a, b in segs:
        edges[(key(a), key(b)) if key(a) <= key(b) else (key(b), key(a))] = (a, b)
        adj.setdefault(key(a), []).append(b)
        adj.setdefault(key(b), []).append(a)
    unused = set(edges)
    lines = []
    while unused:
        start = unused.pop()
        a, b = edges[start]
        chain = [a, b]
        for end in (0, -1):
            while True:
                tip = chain[end]
                nxt = None
                for nb in adj.get(key(tip), []):
                    mark = (key(tip), key(nb)) if key(tip) <= key(nb) else (key(nb), key(tip))
                    if mark in unused:
                        unused.remove(mark)
                        nxt = nb
                        break
                if nxt is None:
                    break
                if end == 0:
                    chain.insert(0, nxt)
                else:
                    chain.append(nxt)
        if len(chain) > 1:
            lines.append(chain)
    return lines


def _math_runs(pred, xmin, xmax, ymin, ymax, n=64):
    strips = []
    for j in range(n):
        y0 = ymin + (ymax - ymin) * j / n
        y1 = ymin + (ymax - ymin) * (j + 1) / n
        yc = (y0 + y1) / 2
        run = None
        for i in range(n + 1):
            inside = False
            if i < n:
                xc = xmin + (xmax - xmin) * (i + 0.5) / n
                inside = bool(pred(xc, yc))
            if inside and run is None:
                run = i
            if not inside and run is not None:
                strips.append((xmin + (xmax - xmin) * run / n, y0,
                               xmin + (xmax - xmin) * i / n, y1))
                run = None
    return strips


def _math_pct(vals, p):
    if not vals:
        return None
    ordered = sorted(vals)
    idx = (len(ordered) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def _math_trace(curve, xmin, xmax, ymin, ymax, samples):
    """Sample a curve on the final window. Returns y values used to autoscale."""
    curve.pop("lines", None)
    if curve["kind"] in ("explicit", "ineq"):
        if curve["var"] == "x":
            lines = _math_sample(curve["fn"], "x", xmin, xmax, samples)
        else:
            lines = _math_sample(curve["fn"], "y", ymin, ymax, samples)
        curve["lines"] = lines
        return [pt[1] for line in lines for pt in line]
    if curve["kind"] != "parametric":
        return []
    t0, t1 = float(curve["tmin"]), float(curve["tmax"])
    if t1 < t0:
        t0, t1 = t1, t0
    count = max(48, min(int(samples or 360), 1600))
    pts, lines = [], []
    for i in range(count):
        t = t0 + (t1 - t0) * i / (count - 1)
        x = _math_call(curve["x"], curve["param"], t)
        y = _math_call(curve["y"], curve["param"], t)
        if x is None or y is None:
            if len(pts) > 1:
                lines.append(pts)
            pts = []
            continue
        pts.append((x, y))
    if len(pts) > 1:
        lines.append(pts)
    curve["lines"] = lines
    return [pt[1] for line in lines for pt in line]


def _c_math(spec, rows, opt):
    spec = spec if isinstance(spec, dict) else {}
    opt = dict(opt, spec=spec)
    try:
        curves = [_math_compile_item(item) for item in _math_items(spec)]
    except ValueError as exc:
        raise SpecError(str(exc))
    _cap(spec, len(curves), 8, "equations", opt["unbounded"])
    if sum(1 for c in curves if c.get("focal")) > 2:
        raise SpecError("focal on >2 equations. Keep one or two.")
    samples = int(spec.get("samples") or 360)
    xmin = spec.get("xmin", -10)
    xmax = spec.get("xmax", 10)
    try:
        xmin, xmax = float(xmin), float(xmax)
    except (TypeError, ValueError):
        raise SpecError("xmin and xmax must be numbers")
    if xmax <= xmin:
        raise SpecError("xmax must be greater than xmin")
    probe = []
    y_probe_lo = float(spec["ymin"]) if spec.get("ymin") is not None else xmin
    y_probe_hi = float(spec["ymax"]) if spec.get("ymax") is not None else xmax
    for curve in curves:
        probe.extend(_math_trace(curve, xmin, xmax, y_probe_lo, y_probe_hi, min(samples, 180)))
    finite = [v for v in probe if v is not None]
    if spec.get("ymin") is None or spec.get("ymax") is None:
        if finite:
            ymin, ymax = _math_pct(finite, 0.02), _math_pct(finite, 0.98)
            span = (ymax - ymin) or 1
            ymin, ymax = ymin - span * 0.08, ymax + span * 0.08
        else:
            ymin, ymax = xmin, xmax
    else:
        ymin, ymax = float(spec["ymin"]), float(spec["ymax"])
    if ymax <= ymin:
        raise SpecError("ymax must be greater than ymin")
    auto_equal = any(c["kind"] in ("implicit", "region", "parametric", "point") for c in curves)
    equal = spec["equal"] if "equal" in spec else auto_equal
    legend = len(curves) > 1
    parts, t, W, H, ox, oy, pw, ph = _begin(opt, 340, ox=72, right=28, W=780, bottom=86 if legend else 58)
    if equal:
        xmin, xmax, ymin, ymax = _math_equal(xmin, xmax, ymin, ymax, pw, ph)
    for curve in curves:
        _math_trace(curve, xmin, xmax, ymin, ymax, samples)
    xt = [v for v in nice_ticks(xmin, xmax, 8) if xmin - 1e-9 <= v <= xmax + 1e-9] or [xmin, xmax]
    yt = [v for v in nice_ticks(ymin, ymax, 8) if ymin - 1e-9 <= v <= ymax + 1e-9] or [ymin, ymax]
    spanx, spany = (xmax - xmin) or 1, (ymax - ymin) or 1

    def X(v):
        return ox + (v - xmin) / spanx * pw

    def Y(v):
        return oy + ph - (v - ymin) / spany * ph

    parts.append(f'<clipPath id="plotclip"><rect x="{ox}" y="{oy}" width="{pw}" height="{ph}"/></clipPath>')
    if opt["grid"]:
        for v in xt:
            parts.append(f'<line x1="{X(v):.1f}" y1="{oy}" x2="{X(v):.1f}" y2="{oy + ph}" stroke="{t["rule"]}" stroke-width="1"/>')
        for v in yt:
            parts.append(f'<line x1="{ox}" y1="{Y(v):.1f}" x2="{ox + pw}" y2="{Y(v):.1f}" stroke="{t["rule"]}" stroke-width="1"/>')
    parts.append(f'<rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" fill="none" stroke="{t["ink"]}" stroke-width="1"/>')
    x_axis = 0 if xmin < 0 < xmax else xmin
    y_axis = 0 if ymin < 0 < ymax else ymin
    parts.append(f'<line x1="{ox}" y1="{Y(y_axis):.1f}" x2="{ox + pw}" y2="{Y(y_axis):.1f}" stroke="{t["ink"]}" stroke-width="1.3"/>')
    parts.append(f'<line x1="{X(x_axis):.1f}" y1="{oy}" x2="{X(x_axis):.1f}" y2="{oy + ph}" stroke="{t["ink"]}" stroke-width="1.3"/>')
    for v in xt:
        if abs(v) < 1e-9 and xmin < 0 < xmax and ymin < 0 < ymax:
            continue
        parts.append(
            f'<text x="{X(v):.1f}" y="{Y(y_axis) + 14:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="middle">{fmt_tick(v)}</text>')
    for v in yt:
        if abs(v) < 1e-9:
            continue
        parts.append(
            f'<text x="{X(x_axis) - 6:.1f}" y="{Y(v) + 3:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">{fmt_tick(v)}</text>')
    if xmin < 0 < xmax and ymin < 0 < ymax:
        parts.append(
            f'<text x="{X(0) - 6:.1f}" y="{Y(0) + 14:.1f}" font-size="10" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">0</text>')
    parts.append(
        f'<text x="{ox + pw - 8:.1f}" y="{Y(y_axis) - 6:.1f}" font-size="11" font-family="{FONT}" fill="{t["muted"]}" text-anchor="end">x</text>')
    parts.append(
        f'<text x="{X(x_axis) + 8:.1f}" y="{oy + 14:.1f}" font-size="11" font-family="{FONT}" fill="{t["muted"]}">y</text>')
    taken = [(ox + pw - 18, Y(y_axis) - 16, ox + pw - 6, Y(y_axis) - 3),
             (X(x_axis) + 6, oy + 4, X(x_axis) + 18, oy + 17)]
    for v in xt:
        tw = _text_w(fmt_tick(v), 10)
        taken.append((X(v) - tw / 2, Y(y_axis) + 6, X(v) + tw / 2, Y(y_axis) + 16))
    for v in yt:
        tw = _text_w(fmt_tick(v), 10)
        taken.append((X(x_axis) - 6 - tw, Y(v) - 5, X(x_axis) - 6, Y(v) + 5))
    box = (xmin, xmax, ymin, ymax)
    pal = series_palette(t)
    parts.append('<g clip-path="url(#plotclip)">')
    legend_items = []
    for i, curve in enumerate(curves):
        col = t["accent"] if curve.get("focal") or _hit(opt["highlights"], curve["name"], curve["expr"]) else pal[i % len(pal)]
        legend_items.append((col, _short(_math_label(curve), 22)))
        if curve["kind"] == "ineq":
            for line in curve.get("lines", []):
                for piece in _math_clip_chain(line, box):
                    floor = ymin if curve["op"] in ("<", "<=") else ymax
                    poly = piece + [(piece[-1][0], floor), (piece[0][0], floor)]
                    d = " ".join(
                        [("M" if n == 0 else "L") + f"{X(p[0]):.1f},{Y(p[1]):.1f}" for n, p in enumerate(poly)]) + " Z"
                    parts.append(f'<path d="{d}" fill="{col}" fill-opacity="0.16" stroke="none"/>')
        if curve["kind"] == "region":
            op = curve["op"]

            def pred(x, y, node=curve["diff"], op=op):
                value = _math_field(node, x, y)
                if value is None:
                    return False
                if op == "<":
                    return value < 0
                if op == "<=":
                    return value <= 0
                if op == ">":
                    return value > 0
                return value >= 0

            for x0, y0, x1, y1 in _math_runs(pred, xmin, xmax, ymin, ymax):
                parts.append(
                    f'<rect x="{X(x0):.1f}" y="{Y(y1):.1f}" width="{max(0.6, X(x1) - X(x0)):.1f}" height="{max(0.6, Y(y0) - Y(y1)):.1f}" fill="{col}" fill-opacity="0.2" stroke="none"/>')
            for line in _math_march(curve["diff"], xmin, xmax, ymin, ymax):
                _math_stroke(parts, line, X, Y, col, 1.4)
        if curve["kind"] == "implicit":
            for line in _math_march(curve["diff"], xmin, xmax, ymin, ymax):
                _math_stroke(parts, line, X, Y, col, 1.8)
        if curve["kind"] in ("explicit", "ineq", "parametric"):
            longest = []
            for line in curve.get("lines", []):
                for piece in _math_clip_chain(line, box):
                    _math_stroke(parts, piece, X, Y, col, 1.8)
                    if len(piece) > len(longest):
                        longest = piece
            if opt["markers"] and longest:
                _math_tag(parts, t, longest, X, Y, ox, oy, pw, ph, _math_label(curve), col, taken)
        if curve["kind"] == "point":
            _dot(parts, t, X(curve["x"]), Y(curve["y"]), 3.4, col, True, curve.get("focal"))
            _math_tag(parts, t, [(curve["x"], curve["y"])], X, Y, ox, oy, pw, ph, _math_label(curve), col, taken)
    for pt in spec.get("points") or []:
        try:
            px, py = float(pt["x"]), float(pt["y"])
        except (TypeError, ValueError, KeyError):
            continue
        if not (xmin <= px <= xmax and ymin <= py <= ymax):
            continue
        _dot(parts, t, X(px), Y(py), 3.4, t["ink"], True, _hit(opt["highlights"], pt.get("name")))
        if pt.get("name"):
            _math_tag(parts, t, [(px, py)], X, Y, ox, oy, pw, ph, str(pt["name"]), t["ink"], taken)
    parts.append("</g>")
    if legend:
        _legend(parts, t, legend_items, ox, oy + ph + 34, ox + pw)
    return _done(parts, opt, W, H, len(curves), "equal scale" if equal else "")


def _math_equal(xmin, xmax, ymin, ymax, pw, ph):
    dx, dy = xmax - xmin, ymax - ymin
    if dx <= 0 or dy <= 0 or pw <= 0 or ph <= 0:
        return xmin, xmax, ymin, ymax
    data, pix = dx / dy, pw / ph
    if abs(data - pix) <= 0.02 * pix:
        return xmin, xmax, ymin, ymax
    if data > pix:
        need = dx / pix
        mid = (ymin + ymax) / 2
        return xmin, xmax, mid - need / 2, mid + need / 2
    need = dy * pix
    mid = (xmin + xmax) / 2
    return mid - need / 2, mid + need / 2, ymin, ymax


def _math_label(curve):
    return str(curve.get("name") or curve.get("expr") or "f").replace("{", "(").replace("}", ")")


def _math_stroke(parts, pts, X, Y, col, width):
    if len(pts) < 2:
        return
    d = " ".join((("M" if i == 0 else "L") + f"{X(p[0]):.1f},{Y(p[1]):.1f}") for i, p in enumerate(pts))
    parts.append(
        f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')


def _math_tag(parts, t, pts, X, Y, ox, oy, pw, ph, label, col, taken=None):
    """Label a curve near its end. Walk back along the curve until the label sits clear
    of the axis names and the labels already placed."""
    shown = _short(label, 18)
    w = _text_w(shown, 11)
    taken = [] if taken is None else taken
    step = max(1, len(pts) // 12)
    first = None
    for k in range(len(pts) - 1, -1, -step):
        x, y = X(pts[k][0]), Y(pts[k][1])
        if not (ox - 2 <= x <= ox + pw + 2 and oy - 2 <= y <= oy + ph + 2):
            continue
        anchor = "end" if x > ox + pw - 72 else "start"
        tx = x - 6 if anchor == "end" else x + 6
        for ty in (y - 6, y + 16):
            x0 = tx - w if anchor == "end" else tx
            box = (x0, ty - 9, x0 + w, ty + 3)
            if first is None:
                first = (tx, ty, anchor, box)
            if oy <= box[1] and box[3] <= oy + ph and not any(
                    box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in taken):
                first = (tx, ty, anchor, box)
                break
        else:
            continue
        break
    if first is None:
        return
    tx, ty, anchor, box = first
    taken.append(box)
    parts.append(
        f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="11" font-family="{FONT}" fill="{col}" text-anchor="{anchor}">{esc(shown)}</text>')

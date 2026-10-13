"""Text: escaping, labels, wrapping, and the width estimate that layout and audit share."""
import html


def _humanize(col):
    """p99_latency_ms -> p99 latency ms. Acronyms uppercased, units kept short."""
    out = []
    for w in str(col).replace("_", " ").split():
        low = w.lower()
        if low in ("p50", "p90", "p95", "p99", "ms", "rps", "pct"):
            out.append(low)
        elif len(w) <= 3 and w.isalpha() and low not in ("per", "avg", "max", "min"):
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _with_unit(label, unit):
    """Append (unit) unless the label already carries it: 'p99 ms'+'ms' -> 'p99 (ms) x1."""
    label, unit = (label or "").strip(), (unit or "").strip()
    if not unit:
        return label
    low = label.lower()
    if low.endswith(f"({unit.lower()})") or low.endswith(f" {unit.lower()}") or low.endswith(f"_{unit.lower()}"):
        label = label[: -len(unit) - 1].rstrip(" (_-") if not low.endswith(f"({unit.lower()})") else label
        if low.endswith(f"({unit.lower()})"):
            return label
    return f"{label} ({unit})" if label else f"({unit})"


def _wrap(text, width=24, max_lines=3):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, width - 1)] + "…"
    return lines


def esc(s):
    return html.escape(str(s))


def _wrap_px(text, max_w, fs, bold=False, max_lines=3):
    """Greedy word wrap by estimated pixel width. A word wider than a line is split.
    Past max_lines the last line ends in an ellipsis; validate warns before that happens."""
    words, lines, cur = str(text or "").split(), [], ""
    for wd in words:
        while _text_w(wd, fs, bold) > max_w and len(wd) > 1:
            cut = max(1, int(len(wd) * max_w / _text_w(wd, fs, bold)) - 1)
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(wd[:cut] + "-")
            wd = wd[cut:]
        trial = (cur + " " + wd).strip()
        if cur and _text_w(trial, fs, bold) > max_w:
            lines.append(cur)
            cur = wd
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and _text_w(last + "...", fs, bold) > max_w:
            last = last[:-1]
        lines[-1] = last.rstrip() + "..."
    return lines or [""]


_NARROW = set("iljI.,:;'|!()[]{}`ftr ")


_WIDE = set("mwMW@%")


_WIDTHS = {}  # (text, size, bold) -> width: the repair loops measure the same labels hundreds of times


def _text_w(s, fs, bold=False):
    """Width estimate for a system sans. No font metrics in the stdlib, so it errs a little wide."""
    key = (s, fs, bold)
    w = _WIDTHS.get(key)
    if w is None:
        if len(_WIDTHS) > 50000:
            _WIDTHS.clear()
        w = _WIDTHS[key] = _measure(s, fs, bold)
    return w


def _measure(s, fs, bold):
    w = 0.0
    for ch in s:
        if ch in _NARROW:
            w += 0.30
        elif ch in _WIDE:
            w += 0.85
        elif ch.isupper():
            w += 0.62
        elif ch.isdigit():
            w += 0.56
        elif ord(ch) > 0x2E80:
            w += 1.0
        else:
            w += 0.52
    return w * fs * (1.06 if bold else 1.0)

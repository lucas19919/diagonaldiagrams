"""Animated GIF in pure Python (DESIGN 21.2.1): PNG frames in, one looping GIF out.

read_png() decodes what the raster path writes: 8-bit RGB or RGBA, not interlaced, one frame or
a sheet of frames stacked top to bottom. The frames of one loop share most of their rows, so each
is decoded against the one before it. A row whose filtered bytes match, under a row that matched,
is the same row, and is not unfiltered again. Rows that match are the same bytes object, so
comparing frames is mostly an identity check.

write() makes one palette for the whole loop: the colors that cover the most pixels exactly, the
rest by median cut, and index 255 kept for "unchanged". Each frame after the first holds only the
rectangle whose palette indices changed, the other pixels transparent, and is drawn over the one
before (disposal 1). Comparing indices, not colors, keeps raster noise that a viewer cannot see out
of the file. A frame that changes nothing adds its delay to the one before. NETSCAPE2.0 loops it.
"""
import collections
import struct
import zlib

CLEAR = 255  # the palette index of a pixel that did not change


class Frame:
    """w, h, rows (RGB bytes, one per row); px and filtered (the rows as unfiltered and as stored)
    are what the next frame's decode compares against, and can be dropped after it."""
    __slots__ = ("w", "h", "rows", "px", "filtered")

    def __init__(self, w, h, rows, px, filtered):
        self.w, self.h, self.rows, self.px, self.filtered = w, h, rows, px, filtered


_MASKS = {}


def _masks(n):
    if n not in _MASKS:
        _MASKS[n] = (int.from_bytes(b"\x7f" * n, "big"), int.from_bytes(b"\x80" * n, "big"))
    return _MASKS[n]


def _add(a, b, lo, hi):
    """Bytewise (a + b) mod 256 of two rows held as big integers: no carry crosses a byte."""
    return ((a & lo) + (b & lo)) ^ ((a ^ b) & hi)


def _unfilter(ft, f, prior, bpp):
    n = len(f)
    if ft == 0:
        return bytes(f)
    lo, hi = _masks(n)
    if ft == 1:  # Sub: a running sum per channel, in log2(width) whole-row additions
        x, k = int.from_bytes(f, "big"), bpp
        while k < n:
            x = _add(x, x >> (8 * k), lo, hi)
            k *= 2
        return x.to_bytes(n, "big")
    if ft == 2:  # Up
        return _add(int.from_bytes(f, "big"), int.from_bytes(prior, "big"), lo, hi).to_bytes(n, "big")
    out = bytearray(f)
    if ft == 3:  # Average
        for i in range(bpp):
            out[i] = (out[i] + (prior[i] >> 1)) & 255
        for i in range(bpp, n):
            out[i] = (out[i] + ((out[i - bpp] + prior[i]) >> 1)) & 255
        return bytes(out)
    if ft == 4:  # Paeth
        for i in range(bpp):
            out[i] = (out[i] + prior[i]) & 255
        for i in range(bpp, n):
            a, b, c = out[i - bpp], prior[i], prior[i - bpp]
            pa, pb = b - c, a - c
            pc = pa + pb
            pa, pb, pc = abs(pa), abs(pb), abs(pc)
            out[i] = (out[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        return bytes(out)
    raise ValueError(f"PNG filter type {ft}")


def read_png(path, like=None, period=None):
    """A Frame of RGB rows, from a PNG file or its bytes. The PNG may be a sheet of frames stacked
    top to bottom, each `period` rows high; each frame is then decoded against the one above it,
    and the first against the last frame of `like` (the sheet or frame before). Rows that match
    are reused, not unfiltered."""
    if isinstance(path, (bytes, bytearray)):
        data, path = path, "the image"
    else:
        with open(path, "rb") as f:
            data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    pos, idat, ihdr = 8, [], None
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    w, h, depth, ctype, _, _, interlace = ihdr
    if depth != 8 or ctype not in (2, 6) or interlace:
        raise ValueError(f"{path}: only 8-bit RGB or RGBA PNGs, not interlaced (depth {depth}, type {ctype})")
    bpp = 3 if ctype == 2 else 4
    raw = zlib.decompress(b"".join(idat))
    stride, period = w * bpp + 1, period or h
    if like is not None and (like.w != w or like.h < period or like.filtered is None):
        like = None
    # the rows each row is compared with: the frame before's, then this sheet's own
    rows, pxs, filtered = ([], [], []) if like is None else (like.rows[-period:], like.px[-period:], like.filtered[-period:])
    back = len(rows) - period  # row r's reference is at r + back in the lists above
    prior, prior_same = bytes(w * bpp), True
    for r in range(h):
        line = raw[r * stride:(r + 1) * stride]
        ft, k = line[0], r + back
        if k >= 0 and line == filtered[k] and (ft <= 1 or prior_same):
            px, rgb, same = pxs[k], rows[k], True  # None and Sub read only their own row
        else:
            px = _unfilter(ft, line[1:], prior, bpp)
            same = k >= 0 and px == pxs[k]
            if same:
                px, rgb = pxs[k], rows[k]
            elif bpp == 4:
                rgb3 = bytearray(w * 3)
                rgb3[0::3], rgb3[1::3], rgb3[2::3] = px[0::4], px[1::4], px[2::4]
                rgb = bytes(rgb3)
            else:
                rgb = px
        rows.append(rgb)
        pxs.append(px)
        filtered.append(line)
        prior, prior_same = px, same
    cut = len(rows) - h
    return Frame(w, h, rows[cut:], pxs[cut:], filtered[cut:])


def split(sheet, period):
    """The frames of a sheet, top to bottom (they share the sheet's row objects)."""
    return [Frame(sheet.w, period, sheet.rows[y:y + period], None, None) for y in range(0, sheet.h - period + 1, period)]


def write_png(path, f):
    """A plain PNG of a Frame (filter None), for tools that want one file per frame."""
    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body))
    raw = b"".join(b"\x00" + row for row in f.rows)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", f.w, f.h, 8, 2, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw, 3)) + chunk(b"IEND", b""))


# ---- palette ---------------------------------------------------------------------------------

def _pixels(row):
    return [row[i:i + 3] for i in range(0, len(row), 3)]


def _spans(a, b):
    """{row: (x0, x1)}: where frame b differs from frame a, row by row (pixels, x1 inclusive)."""
    out = {}
    for r, (ra, rb) in enumerate(zip(a.rows, b.rows)):
        if ra is rb or ra == rb:
            continue
        x = int.from_bytes(ra, "big") ^ int.from_bytes(rb, "big")
        n = len(ra)
        hi = n - 1 - ((x & -x).bit_length() - 1) // 8  # the last byte that differs
        lo = n - 1 - (x.bit_length() - 1) // 8          # the first
        out[r] = (lo // 3, hi // 3)
    return out


def _median_cut(colors, slots):
    """colors: [(rgb tuple, count)]. Up to `slots` boxes; returns {rgb: the mean of its box}."""
    def scored(box):
        rng = [max(c[0][ch] for c in box) - min(c[0][ch] for c in box) for ch in range(3)]
        weight = sum(c[1] for c in box)
        return [max(rng) * weight ** 0.5 if len(box) > 1 else -1, rng.index(max(rng)), box]
    boxes = [scored(colors)]
    while len(boxes) < slots:
        k = max(range(len(boxes)), key=lambda i: boxes[i][0])
        if boxes[k][0] <= 0:
            break
        _, ch, box = boxes.pop(k)
        box.sort(key=lambda c: c[0][ch])
        total, run, cut = sum(c[1] for c in box), 0, 1
        for i, c in enumerate(box):
            run += c[1]
            if run * 2 >= total:
                cut = min(max(1, i + 1), len(box) - 1)
                break
        boxes += [scored(box[:cut]), scored(box[cut:])]
    out = {}
    for _, _, box in boxes:
        total = sum(c[1] for c in box) or 1
        mean = tuple(int(round(sum(c[0][ch] * c[1] for c in box) / total)) for ch in range(3))
        for c in box:
            out[c[0]] = mean
    return out


def palette(frames, spans):
    """(256 * 3 palette bytes, {rgb bytes: index}) for the whole loop."""
    count = collections.Counter()
    for row, k in collections.Counter(frames[0].rows).items():
        for px, m in collections.Counter(_pixels(row)).items():
            count[px] += m * k
    for f, sp in zip(frames[1:], spans[1:]):
        for r, (x0, x1) in sp.items():
            count.update(_pixels(f.rows[r][3 * x0:3 * x1 + 3]))
    total = sum(count.values())
    ranked = count.most_common()
    exact = [c for c, m in ranked[:96] if m * 2000 >= total]
    chosen = set(exact)
    rest = [(tuple(c), m) for c, m in ranked if c not in chosen]
    near = _median_cut(rest, 255 - len(exact)) if rest else {}
    colors = [tuple(c) for c in exact] + sorted(set(near.values()) - {tuple(c) for c in exact})
    colors = colors[:255]
    index = {c: i for i, c in enumerate(colors)}
    lookup = {bytes(c): index[c] for c in colors}
    for c, mean in near.items():
        lookup[bytes(c)] = index[mean] if mean in index else _nearest(mean, colors)
    pal = b"".join(bytes(c) for c in colors) + bytes(3 * (256 - len(colors)))
    return pal, lookup, colors


def _nearest(c, colors):
    return min(range(len(colors)), key=lambda i: sum((a - b) ** 2 for a, b in zip(c, colors[i])))


# ---- LZW and the file --------------------------------------------------------------------------

def lzw(data, min_size=8):
    """GIF's LZW: variable-width codes, least significant bit first, a clear code when full."""
    clear, eoi = 1 << min_size, (1 << min_size) + 1
    out = bytearray()
    acc, nbits, size, nxt, table = clear, min_size + 1, min_size + 1, eoi + 1, {}
    it = iter(data)
    prefix = next(it)
    for k in it:
        key = (prefix << 8) | k
        c = table.get(key)
        if c is not None:
            prefix = c
            continue
        acc |= prefix << nbits
        nbits += size
        if nxt < 4096:
            table[key] = nxt
            nxt += 1
            if nxt > (1 << size) and size < 12:
                size += 1
        else:
            acc |= clear << nbits
            nbits += size
            table, nxt, size = {}, eoi + 1, min_size + 1
        while nbits >= 8:
            out.append(acc & 255)
            acc >>= 8
            nbits -= 8
        prefix = k
    acc |= prefix << nbits
    nbits += size
    if nxt < 4096 and nxt + 1 > (1 << size) and size < 12:  # the decoder adds one more entry first
        size += 1
    acc |= eoi << nbits
    nbits += size
    while nbits > 0:
        out.append(acc & 255)
        acc >>= 8
        nbits -= 8
    return bytes(out)


def _blocks(data):
    return b"".join(bytes([len(data[i:i + 255])]) + data[i:i + 255] for i in range(0, len(data), 255)) + b"\x00"


def encode(frames, delays, loop=0):
    """(GIF bytes, frames written). frames: Frames of one size; delays in hundredths of a second."""
    w, h = frames[0].w, frames[0].h
    spans = [None] + [_spans(a, b) for a, b in zip(frames, frames[1:])]
    pal, lookup, colors = palette(frames, spans)

    def index(px):
        i = lookup.get(px)
        if i is None:
            i = lookup[px] = _nearest(tuple(px), colors)
        return i
    images = []  # [delay, x, y, w, h, indices, transparent]
    canvas, coded = bytearray(), {}  # canvas: the palette index each pixel shows so far
    for row in frames[0].rows:
        if row not in coded:
            coded[row] = bytes(index(px) for px in _pixels(row))
        canvas.extend(coded[row])
    images.append([delays[0], 0, 0, w, h, bytes(canvas), False])
    for k in range(1, len(frames)):
        rb = frames[k].rows
        changed = {}  # row: [(x, index)], only where the shown index changes
        for r, (a, b) in spans[k].items():
            row, at, out = rb[r], r * w, []
            for x in range(a, b + 1):
                i = index(row[3 * x:3 * x + 3])
                if canvas[at + x] != i:
                    canvas[at + x] = i
                    out.append((x, i))
            if out:
                changed[r] = out
        if not changed:  # nothing a viewer could see: the frame before stays up longer
            images[-1][0] += delays[k]
            continue
        y0, y1 = min(changed), max(changed)
        x0 = min(c[0][0] for c in changed.values())
        x1 = max(c[-1][0] for c in changed.values())
        bw = x1 - x0 + 1
        sub = bytearray(bytes([CLEAR]) * (bw * (y1 - y0 + 1)))
        for r, cs in changed.items():
            base = (r - y0) * bw - x0
            for x, i in cs:
                sub[base + x] = i
        images.append([delays[k], x0, y0, bw, y1 - y0 + 1, bytes(sub), True])
    parts = [b"GIF89a", struct.pack("<HHBBB", w, h, 0xF7, 0, 0), pal,
             b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00"]
    for delay, x, y, iw, ih, px, transparent in images:
        parts.append(b"\x21\xf9\x04" + bytes([(1 << 2) | (1 if transparent else 0)]) + struct.pack("<H", delay)
                     + bytes([CLEAR]) + b"\x00")
        parts.append(b"\x2c" + struct.pack("<HHHHB", x, y, iw, ih, 0))
        parts.append(b"\x08" + _blocks(lzw(px)))
    parts.append(b"\x3b")
    return b"".join(parts), len(images)


def write(path, frames, delays, loop=0):
    """Writes the GIF; returns (bytes written, frames in the file)."""
    data, n = encode(frames, delays, loop)
    with open(path, "wb") as f:
        f.write(data)
    return len(data), n

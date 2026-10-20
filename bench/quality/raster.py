"""Rasterize the benchmark's SVGs the way a reader meets them: python bench/quality/raster.py

Two placements, each drawn by headless Edge or Chrome straight from the SVG (no raster rescaling):
  slide   a 16:9 slide, 1600 x 900 px: the figure is fitted inside 1520 x 820 and centered, up to 2x.
  column  a 700 px notes or docs column, read by scrolling: the figure is shown at its own size, or
          shrunk to the column's width; drawn at 1.5 device pixels per CSS pixel (1050 px wide).

Every SVG is placed by its viewBox, whatever its origin. export._raster_svg only reads a
viewBox that starts at "0 0", which Mermaid's (4 4 ..., -50 -50 ...) do not, so it guessed a 4:3 page and
cropped them; dd's own SVGs always start at 0 0, so the export command is not affected.

Also writes svg/sizes.json: each figure's viewBox size, its scale in each placement, and its text sizes.

    py -3 bench/quality/raster.py [NAME ...] [--run RUN] [--context slide|column]

NAME keeps the figures whose names contain it; --run reads and writes runs/RUN instead (render.py --run);
--context draws one placement only."""
import argparse, concurrent.futures, glob, json, os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from diagonaldiagrams.export import _browser  # noqa: E402

SLIDE_W, SLIDE_H, SLIDE_FIT_W, SLIDE_FIT_H, SLIDE_MAX = 1600, 900, 1520, 820, 2.0
COL_W, COL_PAD, COL_DPR = 700, 16, 1.5


def viewbox(svg):
    m = re.search(r'<svg\b[^>]*?\bviewBox="\s*([-\d.eE]+)[\s,]+([-\d.eE]+)[\s,]+([\d.eE]+)[\s,]+([\d.eE]+)\s*"', svg)
    if not m:
        raise ValueError("no viewBox on the root svg")
    return tuple(float(v) for v in m.groups())


def font_sizes(svg):
    """The text sizes the SVG asks for, in viewBox units (attributes and inline or <style> CSS)."""
    sizes = [float(v) for v in re.findall(r'font-size[=:]\s*"?\s*([\d.]+)(?:px)?', svg)]
    sizes += [float(v) for v in re.findall(r'\bfont:\s*(?:[a-z]+\s+)*([\d.]+)px', svg)]
    return sorted(s for s in sizes if 4 <= s <= 60)


def page(svg, page_w, page_h, left, top, w, h):
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;padding:0;width:{page_w}px;height:{page_h}px;overflow:hidden;background:#fff}}"
            f"#fig{{position:absolute;left:{left}px;top:{top}px;width:{w}px;height:{h}px}}"
            f"#fig>svg{{display:block;width:{w}px!important;height:{h}px!important;max-width:none!important}}"
            "</style></head><body><div id='fig'>" + svg + "</div></body></html>")


def shoot(html, dest, w, h, dpr):
    browser = _browser()
    folder = tempfile.mkdtemp(prefix="ddq-raster-")
    try:
        path = os.path.join(folder, "fig.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        if os.path.exists(dest):
            os.remove(dest)
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--force-device-scale-factor={dpr}",
               f"--user-data-dir={os.path.join(folder, 'profile')}", f"--window-size={w},{h}",
               f"--screenshot={os.path.abspath(dest)}", "file:///" + path.replace("\\", "/")]
        subprocess.run(cmd, timeout=120, capture_output=True)
        last, deadline = -1, time.time() + 30  # Edge may hand the job on and exit before the file lands
        while time.time() < deadline:
            size = os.path.getsize(dest) if os.path.isfile(dest) else -1
            if size > 400 and size == last:
                break
            last = size
            time.sleep(0.4)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return os.path.isfile(dest)


def one(svg_path, root=HERE, contexts=("slide", "column")):
    name = os.path.splitext(os.path.basename(svg_path))[0]
    with open(svg_path, encoding="utf-8") as f:
        svg = f.read()
    x, y, w, h = viewbox(svg)
    s_slide = min(SLIDE_FIT_W / w, SLIDE_FIT_H / h, SLIDE_MAX)
    sw, sh = w * s_slide, h * s_slide
    ok1 = "slide" not in contexts or shoot(
        page(svg, SLIDE_W, SLIDE_H, round((SLIDE_W - sw) / 2, 2), round((SLIDE_H - sh) / 2, 2), sw, sh),
        os.path.join(root, "png", "slide", name + ".png"), SLIDE_W, SLIDE_H, 1)
    s_col = min(1.0, (COL_W - 2 * COL_PAD) / w)
    cw, ch = w * s_col, h * s_col
    page_h = int(ch + 2 * COL_PAD + 0.999)
    ok2 = "column" not in contexts or shoot(page(svg, COL_W, page_h, round((COL_W - cw) / 2, 2), COL_PAD, cw, ch),
                                            os.path.join(root, "png", "column", name + ".png"), COL_W, page_h, COL_DPR)
    fs = font_sizes(svg)
    return name, {"w": round(w, 1), "h": round(h, 1), "slide_scale": round(s_slide, 3), "column_scale": round(s_col, 3),
                  "font_min": fs[0] if fs else None, "font_median": fs[len(fs) // 2] if fs else None,
                  "ok": ok1 and ok2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="*")
    ap.add_argument("--run")
    ap.add_argument("--context", choices=["slide", "column"])
    a = ap.parse_args()
    root = os.path.join(HERE, "runs", a.run) if a.run else HERE
    contexts = (a.context,) if a.context else ("slide", "column")
    for ctx in contexts:
        os.makedirs(os.path.join(root, "png", ctx), exist_ok=True)
    only = a.only
    svgs = sorted(glob.glob(os.path.join(root, "svg", "*.svg")))
    if only:
        svgs = [p for p in svgs if any(o in os.path.basename(p) for o in only)]
    out = {}
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        for name, info in pool.map(lambda p: one(p, root, contexts), svgs):
            out[name] = info
            if not info["ok"]:
                print("failed:", name)
    sizes_path = os.path.join(root, "svg", "sizes.json")
    old = {}
    if only and os.path.isfile(sizes_path):
        with open(sizes_path, encoding="utf-8") as f:
            old = json.load(f)
    old.update(out)
    with open(sizes_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(old, f, indent=1, sort_keys=True)
    print(f"rasterized {len(out)} figures")


if __name__ == "__main__":
    main()

"""Measure what text size each figure reaches in each placement: python bench/quality/measure.py

Headless Edge or Chrome draws each SVG at its own size and reports every text run's font size
(SVG text and HTML labels in foreignObject alike, through the transforms above it). The sizes are
then multiplied by the figure's scale in each placement:
  slide   fitted into 1520 x 820 on a 1600 x 900 slide, up to 2x (as raster.py)
  page    an A4 portrait page at 96 dpi (794 x 1123) with 72 px margins: fitted into 650 x 980,
          never enlarged; a figure has to fit on its page
  column  a 700 px column, read by scrolling: shrunk to 668 px wide if wider (as raster.py)
Writes measure.json: per figure, the text sizes in each placement (10th percentile and median, by
characters), and the share of characters under 9 px."""
import concurrent.futures, glob, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from diagonaldiagrams.export import _browser  # noqa: E402
from raster import viewbox, SLIDE_FIT_W, SLIDE_FIT_H, SLIDE_MAX, COL_W, COL_PAD  # noqa: E402

PAGE_FIT_W, PAGE_FIT_H = 650, 980

SCRIPT = """<script>
const out = [];
const root = document.querySelector('#fig > svg');
for (const el of root.querySelectorAll('*')) {
  if (el.closest('style, script, title, desc, metadata, defs, marker')) continue;
  let chars = 0;
  for (const n of el.childNodes) if (n.nodeType === 3) chars += n.textContent.trim().length;
  if (!chars) continue;
  const cs = getComputedStyle(el);
  if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
  let g = el;
  while (g && !(g instanceof SVGGraphicsElement)) g = g.parentElement;
  const m = g && g.getScreenCTM ? g.getScreenCTM() : null;
  const s = m ? Math.hypot(m.a, m.b) : 1;
  out.push([+(parseFloat(cs.fontSize) * s).toFixed(2), chars]);
}
const pre = document.createElement('pre');
pre.id = 'out';
pre.textContent = JSON.stringify(out);
document.body.appendChild(pre);
</script>"""


def runs(svg_path):
    with open(svg_path, encoding="utf-8") as f:
        svg = f.read()
    x, y, w, h = viewbox(svg)
    html = ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>html,body{margin:0}"
            f"#fig>svg{{display:block;width:{w}px!important;height:{h}px!important;max-width:none!important}}"
            "</style></head><body><div id='fig'>" + svg + "</div>" + SCRIPT + "</body></html>")
    folder = tempfile.mkdtemp(prefix="ddq-measure-")
    try:
        page = os.path.join(folder, "fig.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(html)
        p = subprocess.run([_browser(), "--headless=new", "--disable-gpu", f"--user-data-dir={os.path.join(folder, 'p')}",
                            "--dump-dom", "file:///" + page.replace("\\", "/")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    m = re.search(r'<pre id="out">(.*?)</pre>', p.stdout, re.S)
    return (w, h), json.loads(m.group(1)) if m else []


def pct(rs, q):
    """The size below which a share q of the characters sit."""
    total = sum(c for _, c in rs)
    acc = 0
    for size, c in sorted(rs):
        acc += c
        if acc >= q * total:
            return size
    return None


def one(path):
    name = os.path.splitext(os.path.basename(path))[0]
    (w, h), rs = runs(path)
    scales = {"slide": min(SLIDE_FIT_W / w, SLIDE_FIT_H / h, SLIDE_MAX),
              "page": min(PAGE_FIT_W / w, PAGE_FIT_H / h, 1.0),
              "column": min(1.0, (COL_W - 2 * COL_PAD) / w)}
    total = sum(c for _, c in rs) or 1
    res = {"w": round(w), "h": round(h), "chars": total, "own": {"p10": pct(rs, 0.1), "median": pct(rs, 0.5)}}
    for k, s in scales.items():
        res[k] = {"scale": round(s, 3), "p10": round(pct(rs, 0.1) * s, 1) if rs else None,
                  "median": round(pct(rs, 0.5) * s, 1) if rs else None,
                  "under9": round(sum(c for size, c in rs if size * s < 9) / total, 2)}
    return name, res


def main():
    svgs = sorted(glob.glob(os.path.join(HERE, "svg", "*.svg")))
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        out = dict(pool.map(one, svgs))
    with open(os.path.join(HERE, "measure.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"measured {len(out)} figures")


if __name__ == "__main__":
    main()

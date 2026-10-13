"""Writing a figure: the HTML page, the SVG file, and the receipt that export redraws from."""
import json, os
from ._text import esc
from ._theme import FONT, THEME


HTML_SHELL = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{margin:0;background:{paper};color:{ink};font-family:{font}}}
.gbar{{display:flex;gap:.4rem;align-items:center;padding:.4rem .7rem;background:{paper};border-bottom:1px solid {rule}}}
.gbar button{{font:13px {font};color:{ink};background:{card};border:1px solid {rule};padding:.28rem .6rem;cursor:pointer}}
svg{{display:block;max-width:100%;height:auto;margin:0 auto}}
@media print{{.gbar{{display:none}} body{{background:#fff}}}}
</style></head><body>
<div class="gbar" id="gbar">
  <button type="button" id="copy">Copy SVG</button>
  <button type="button" id="save">Export SVG</button>
  <button type="button" id="png">Export PNG</button>
</div>
{svg}
<script>
(function(){{
  var svg = document.querySelector("svg");
  if (!svg) return;
  function svgText(){{ return new XMLSerializer().serializeToString(svg); }}
  document.getElementById("copy").addEventListener("click", function(){{
    var btn = this;
    navigator.clipboard.writeText(svgText()).then(function(){{
      btn.textContent = "Copied"; setTimeout(function(){{ btn.textContent = "Copy SVG"; }}, 900);
    }});
  }});
  document.getElementById("save").addEventListener("click", function(){{
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([svgText()], {{type: "image/svg+xml"}}));
    a.download = "graph.svg"; a.click();
  }});
  document.getElementById("png").addEventListener("click", function(){{
    var btn = this;
    var vb = svg.viewBox.baseVal;
    var w = (vb && vb.width) ? vb.width : svg.getBoundingClientRect().width;
    var h = (vb && vb.height) ? vb.height : svg.getBoundingClientRect().height;
    var url = URL.createObjectURL(new Blob([svgText()], {{type: "image/svg+xml;charset=utf-8"}}));
    var img = new Image();
    img.onload = function(){{
      var c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(w * 2));
      c.height = Math.max(1, Math.round(h * 2));
      var g = c.getContext("2d");
      g.fillStyle = getComputedStyle(document.body).backgroundColor || "#ffffff";
      g.fillRect(0, 0, c.width, c.height);
      g.drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      c.toBlob(function(b){{
        var a = document.createElement("a");
        a.href = URL.createObjectURL(b);
        a.download = "graph.png";
        a.click();
        btn.textContent = "Saved";
        setTimeout(function(){{ btn.textContent = "Export PNG"; }}, 900);
      }}, "image/png");
    }};
    img.onerror = function(){{
      URL.revokeObjectURL(url);
      btn.textContent = "PNG failed";
      setTimeout(function(){{ btn.textContent = "Export PNG"; }}, 1200);
    }};
    img.src = url;
  }});
}})();
</script>
</body></html>"""


def write_out(svg, kind, title, sub, eyebrow, out, caption="", cap_title="", source="", corners="editorial", theme=None):
    t = theme or THEME
    # -o NAME.html, NAME.svg, or NAME all give NAME.html + NAME.svg side by side
    base, ext = os.path.splitext(out)
    if ext.lower() not in (".html", ".htm", ".svg"):
        base = out
    out = base + ".html"
    h = HTML_SHELL.format(paper=t["paper"], ink=t["ink"], rule=t["rule"], card=t["card"],
                          font=FONT, title=esc(title), svg=svg)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(h)
    svg_path = base + ".svg"
    # extract inner svg for embed use
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return out, svg_path


LAYOUTS = {
    # name -> (width, facet_dir, chrome): doc presets for export
    "figure": {"width": 760, "facet_dir": "row", "chrome": True},
    "wide": {"width": 1120, "facet_dir": "row", "chrome": True},
    "slide": {"width": 1280, "facet_dir": "row", "chrome": True},
    "social": {"width": 1080, "facet_dir": "col", "chrome": True},
}


_RECEIPT_PATHS = ("spec", "csv", "src")


def save_receipt(out, payload):
    """Input paths are stored relative to the receipt, so export works from any directory."""
    base, _ = os.path.splitext(out)
    home = os.path.dirname(os.path.abspath(base))
    for k in _RECEIPT_PATHS:
        if isinstance(payload.get(k), str) and os.path.exists(payload[k]):
            try:
                payload[k] = os.path.relpath(os.path.abspath(payload[k]), home).replace(os.sep, "/")
            except ValueError:  # another drive on Windows
                payload[k] = os.path.abspath(payload[k])
    with open(base + ".graph.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _receipt_inputs(r, rcpt):
    """Resolve receipt input paths: beside the receipt first, then the working directory."""
    home = os.path.dirname(os.path.abspath(rcpt))
    for k in _RECEIPT_PATHS:
        v = r.get(k)
        if isinstance(v, str) and not os.path.isabs(v):
            near = os.path.join(home, v)
            if os.path.exists(near) or not os.path.exists(v):
                r[k] = near
    return r

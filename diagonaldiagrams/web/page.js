/* diagonaldiagrams: a diagram page's edit mode and change animation (DESIGN 21.2, 21.3).
 *
 * Settings come from <script id="dd-page" type="application/json">: the figure's kind, its spec
 * and output paths, the drawing before the last edit (or null), and what changed.
 *
 * Edit mode never edits the figure's source. A rename, a color or a drag shows in place and is
 * collected as a patch operation; the engine writes the patch into the spec (apply) and draws the
 * figure again, and the new page animates from the old drawing to the new one.
 */
(function () {
  "use strict";
  var cfgEl = document.getElementById("dd-page");
  var svg = document.querySelector("body > svg");
  if (!cfgEl || !svg) return;
  var cfg = JSON.parse(cfgEl.textContent);
  var NS = "http://www.w3.org/2000/svg";
  var reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var ROW = 30; // outline.layout_rows' row tolerance: a drop lands in the row the verdict names
  var SWATCHES = ["#fde2e2", "#fff1d6", "#e3f4e1", "#dfeefc", "#ece5fb", null];

  // ---- the boxes: each data-node shape, and the parts drawn inside its box ---------------------

  function middle(el, b) {
    var cx = parseFloat(el.getAttribute("data-cx")), cy = parseFloat(el.getAttribute("data-cy"));
    return {x: isNaN(cx) ? b.x + b.width / 2 : cx, y: isNaN(cy) ? b.y + b.height / 2 : cy};
  }

  function readBoxes(root) {
    var list = [];
    root.querySelectorAll("[data-node][data-label]").forEach(function (el) {
      var b = el.getBBox(), m = middle(el, b);
      list.push({id: el.getAttribute("data-node"), label: el.getAttribute("data-label"), shape: el, box: b,
                 x: m.x, y: m.y, parts: []});
    });
    Array.prototype.forEach.call(root.children, function (el) {
      var tag = el.tagName.toLowerCase();
      if (tag === "defs" || tag === "title" || tag === "desc" || tag === "style") return;
      if (el.hasAttribute("data-from") || el.hasAttribute("data-group") || el.hasAttribute("data-msg")) return;
      var b;
      try { b = el.getBBox(); } catch (e) { return; }
      if (!b || (b.width === 0 && b.height === 0)) return;
      var mx = b.x + b.width / 2, my = b.y + b.height / 2;
      for (var i = 0; i < list.length; i++) {
        var nb = list[i].box;
        if (mx >= nb.x - 1 && mx <= nb.x + nb.width + 1 && my >= nb.y - 1 && my <= nb.y + nb.height + 1 &&
            b.width <= nb.width + 2 && b.height <= nb.height + 2) {
          list[i].parts.push(el);
          return;
        }
      }
    });
    var out = {};
    list.forEach(function (n) { out[n.id] = n; });
    return out;
  }

  // a box's parts go into one group, so the box moves as one piece (painters draw them together)
  function group(nodes) {
    Object.keys(nodes).forEach(function (id) {
      var n = nodes[id];
      if (!n.parts.length) return;
      var g = document.createElementNS(NS, "g");
      g.setAttribute("class", "dd-node");
      g.setAttribute("data-of", id);
      n.parts[0].parentNode.insertBefore(g, n.parts[0]);
      n.parts.forEach(function (p) { g.appendChild(p); });
      n.g = g;
    });
    return nodes;
  }

  var nodes = group(readBoxes(svg));

  function rowsOf(skip) {
    var list = Object.keys(nodes).map(function (k) { return nodes[k]; })
      .filter(function (n) { return n.id !== skip; })
      .sort(function (a, b) { return a.y - b.y || a.x - b.x; });
    var rows = [];
    list.forEach(function (n) {
      var last = rows[rows.length - 1];
      if (last && Math.abs(last.y - n.y) < ROW) last.items.push(n);
      else rows.push({y: n.y, items: [n]});
    });
    rows.forEach(function (r) { r.items.sort(function (a, b) { return a.x - b.x; }); });
    return rows;
  }

  // ---- page chrome --------------------------------------------------------------------------------

  var bar = document.getElementById("gbar");
  var css = document.createElement("style");
  css.textContent = [
    ".dd-on .dd-node{cursor:grab}",
    ".dd-on .dd-node:hover{filter:drop-shadow(0 0 2px rgba(45,49,66,.45))}",
    ".dd-sel{outline:none}",
    ".dd-ring{fill:none;stroke:#eb6c36;stroke-width:2;stroke-dasharray:5 3;pointer-events:none}",
    ".dd-pending{opacity:.75}",
    "#dd-panel{position:fixed;right:12px;top:52px;width:330px;max-width:calc(100vw - 24px);max-height:calc(100vh - 64px);overflow:auto;",
    "background:#fff;border:1px solid rgba(45,49,66,.2);box-shadow:0 6px 24px rgba(0,0,0,.12);padding:10px 12px;font:13px system-ui,sans-serif;display:none}",
    ".dd-on #dd-panel{display:block}",
    "body.dd-on{padding-right:356px}",
    "@media (max-width:700px){body.dd-on{padding-right:0;padding-bottom:60vh}#dd-panel{left:12px;right:12px;width:auto;max-height:55vh}}",
    "#dd-panel h4{margin:.2rem 0 .4rem;font-size:13px}",
    "#dd-panel input{font:13px system-ui,sans-serif;width:100%;box-sizing:border-box;padding:.25rem .35rem}",
    "#dd-panel pre{background:rgba(45,49,66,.05);padding:.4rem;white-space:pre-wrap;word-break:break-all;font:11px ui-monospace,monospace;max-height:160px;overflow:auto}",
    "#dd-panel button{font:12px system-ui,sans-serif;margin:.15rem .2rem .15rem 0;padding:.2rem .5rem;cursor:pointer}",
    ".dd-sw{display:inline-block;width:20px;height:20px;border:1px solid rgba(45,49,66,.35);margin-right:4px;cursor:pointer;vertical-align:middle}",
    ".dd-note{color:#4f5d75;font-size:12px;margin:.3rem 0}",
    "#dd-changed{font-size:12px;color:#4f5d75;margin-left:.6rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
  ].join("\n");
  document.head.appendChild(css);

  function button(label, title) {
    var b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    if (title) b.title = title;
    return b;
  }

  // ---- edit mode ------------------------------------------------------------------------------------

  var ops = []; // {op, revert}
  var editing = false, selected = null, ring = null;
  var canDrag = cfg.kind === "flow" || cfg.kind === "arch";
  var canColor = cfg.kind === "flow" || cfg.kind === "arch";

  var panel = document.createElement("div");
  panel.id = "dd-panel";
  panel.innerHTML =
    '<h4>Edit</h4>' +
    '<div class="dd-note" id="dd-hint">' + (canDrag ? "Click a box to rename or recolor it. Drag it to another place in its row, or into another row." :
                                            "Click a box to rename it.") + '</div>' +
    '<div id="dd-box" style="display:none">' +
    '  <label class="dd-note" for="dd-name">Name</label><input id="dd-name" autocomplete="off">' +
    (canColor ? '  <div class="dd-note">Color</div><div id="dd-swatches"></div>' : '') +
    '</div>' +
    '<h4>Patch <span id="dd-count"></span></h4><pre id="dd-ops">[]</pre>' +
    '<div><span id="dd-actions"></span></div>' +
    '<div class="dd-note">Then write it into the spec and draw again:</div><pre id="dd-cmd"></pre>';
  document.body.appendChild(panel);

  function q(s) { return /[\s"'&|<>]/.test(s) ? '"' + s.replace(/"/g, '\\"') + '"' : s; }
  document.getElementById("dd-cmd").textContent =
    "diagonaldiagrams apply " + q(cfg.spec) + " patch.json\n" + "diagonaldiagrams " + cfg.kind + " " + q(cfg.spec) + " -o " + q(cfg.out);

  function patchJSON() { // one operation per line
    return ops.length ? "[\n" + ops.map(function (o) { return " " + JSON.stringify(o.op); }).join(",\n") + "\n]" : "[]";
  }
  function refresh() {
    document.getElementById("dd-ops").textContent = patchJSON();
    document.getElementById("dd-count").textContent = ops.length ? "(" + ops.length + ")" : "";
  }
  function record(op, revert) {
    ops.push({op: op, revert: revert});
    refresh();
  }

  var actions = document.getElementById("dd-actions");
  var copyBtn = button("Copy patch"), saveBtn = button("Save patch.json"), undoBtn = button("Undo"), cmdBtn = button("Copy commands");
  [copyBtn, saveBtn, undoBtn, cmdBtn].forEach(function (b) { actions.appendChild(b); });
  function flash(b, text) {
    var was = b.textContent;
    b.textContent = text;
    setTimeout(function () { b.textContent = was; }, 900);
  }
  copyBtn.addEventListener("click", function () {
    navigator.clipboard.writeText(patchJSON()).then(function () { flash(copyBtn, "Copied"); });
  });
  saveBtn.addEventListener("click", function () {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([patchJSON() + "\n"], {type: "application/json"}));
    a.download = "patch.json";
    a.click();
  });
  undoBtn.addEventListener("click", function () {
    var o = ops.pop();
    if (o) o.revert();
    refresh();
    if (selected) select(selected);
  });
  cmdBtn.addEventListener("click", function () {
    navigator.clipboard.writeText(document.getElementById("dd-cmd").textContent).then(function () { flash(cmdBtn, "Copied"); });
  });

  var editBtn = button("Edit", "Rename, recolor and move boxes; the changes become a patch");
  bar.appendChild(editBtn);
  editBtn.addEventListener("click", function () {
    editing = !editing;
    document.body.classList.toggle("dd-on", editing);
    editBtn.textContent = editing ? "Done editing" : "Edit";
    if (!editing) select(null);
  });

  function select(n) {
    selected = n;
    if (ring) { ring.remove(); ring = null; }
    var box = document.getElementById("dd-box");
    if (!n) { box.style.display = "none"; return; }
    var b = n.g.getBBox();
    ring = document.createElementNS(NS, "rect");
    ring.setAttribute("class", "dd-ring");
    ring.setAttribute("x", b.x - 4); ring.setAttribute("y", b.y - 4);
    ring.setAttribute("width", b.width + 8); ring.setAttribute("height", b.height + 8);
    ring.setAttribute("rx", 6);
    n.g.appendChild(ring);
    box.style.display = "block";
    var input = document.getElementById("dd-name");
    input.value = n.label;
    if (canColor) swatches(n);
  }

  // the text a box shows its name in: its largest text (a wrapped name is several lines)
  function nameTexts(n) {
    var texts = Array.prototype.filter.call(n.g.querySelectorAll("text"), function (t) { return t.textContent.trim(); });
    var size = Math.max.apply(null, texts.map(function (t) { return parseFloat(t.getAttribute("font-size")) || 0; }).concat([0]));
    return texts.filter(function (t) { return (parseFloat(t.getAttribute("font-size")) || 0) === size; });
  }

  document.getElementById("dd-name").addEventListener("change", function () {
    var n = selected, name = this.value.trim();
    if (!n || !name || name === n.label) return;
    var was = n.label, texts = nameTexts(n), old = texts.map(function (t) { return [t.textContent, t.style.display]; });
    texts.forEach(function (t, i) { if (i) t.style.display = "none"; else t.textContent = name; });
    n.label = name;
    record({op: "text", id: n.id, name: name, was: was}, function () {
      texts.forEach(function (t, i) { t.textContent = old[i][0]; t.style.display = old[i][1]; });
      n.label = was;
    });
  });

  function swatches(n) {
    var host = document.getElementById("dd-swatches");
    host.innerHTML = "";
    SWATCHES.forEach(function (c) {
      var s = document.createElement("span");
      s.className = "dd-sw";
      s.title = c ? c : "back to the style's color";
      s.style.background = c || "linear-gradient(135deg,#fff 45%,#eb6c36 46%,#eb6c36 54%,#fff 55%)";
      s.addEventListener("click", function () {
        var was = n.shape.getAttribute("fill");
        if (c) n.shape.setAttribute("fill", c);
        record({op: "style", selector: "#" + n.id, set: {fill: c}}, function () { n.shape.setAttribute("fill", was); });
      });
      host.appendChild(s);
    });
  }

  // a drag: the box follows the pointer; the drop picks a row and a place in it
  function toSvg(evt) {
    var p = svg.createSVGPoint();
    p.x = evt.clientX; p.y = evt.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }
  var drag = null;
  svg.addEventListener("pointerdown", function (evt) {
    if (!editing) return;
    var g = evt.target.closest && evt.target.closest(".dd-node");
    if (!g) { select(null); return; }
    var n = nodes[g.getAttribute("data-of")];
    select(n);
    if (!canDrag) return;
    var p = toSvg(evt);
    drag = {n: n, x0: p.x, y0: p.y, dx: n.dx || 0, dy: n.dy || 0, moved: false};
    g.setPointerCapture && g.setPointerCapture(evt.pointerId);
    evt.preventDefault();
  });
  svg.addEventListener("pointermove", function (evt) {
    if (!drag) return;
    var p = toSvg(evt), dx = drag.dx + p.x - drag.x0, dy = drag.dy + p.y - drag.y0;
    if (Math.abs(p.x - drag.x0) + Math.abs(p.y - drag.y0) > 3) drag.moved = true;
    drag.n.g.setAttribute("transform", "translate(" + dx + " " + dy + ")");
  });
  svg.addEventListener("pointerup", function (evt) {
    if (!drag) return;
    var d = drag;
    drag = null;
    if (!d.moved) return;
    var p = toSvg(evt), dx = d.dx + p.x - d.x0, dy = d.dy + p.y - d.y0;
    var n = d.n, x = n.x + dx, y = n.y + dy;
    var rows = rowsOf(n.id), best = null;
    rows.forEach(function (r) { if (!best || Math.abs(r.y - y) < Math.abs(best.y - y)) best = r; });
    var gap = rows.length > 1 ? Math.min.apply(null, rows.slice(1).map(function (r, i) { return r.y - rows[i].y; })) : 120;
    function back() { n.g.setAttribute("transform", d.dx || d.dy ? "translate(" + d.dx + " " + d.dy + ")" : ""); }
    if (!best || Math.abs(best.y - y) > Math.max(ROW, gap * 0.6)) { back(); return; }
    var row = best.items.filter(function (m) { return m.x < x; }).map(function (m) { return m.id; });
    row.push(n.id);
    row = row.concat(best.items.filter(function (m) { return m.x >= x; }).map(function (m) { return m.id; }));
    var mine = rowsOf(null).filter(function (r) { return r.items.some(function (m) { return m.id === n.id; }); })[0];
    var same = mine && mine.items.map(function (m) { return m.id; }).join("\u0000") === row.join("\u0000");
    if (same) { back(); return; }
    var was = {dx: d.dx, dy: d.dy};
    n.dx = dx; n.dy = dy;
    n.g.classList.add("dd-pending");
    record({op: "place", id: n.id, row: row}, function () {
      n.dx = was.dx; n.dy = was.dy;
      n.g.setAttribute("transform", was.dx || was.dy ? "translate(" + was.dx + " " + was.dy + ")" : "");
      if (!was.dx && !was.dy) n.g.classList.remove("dd-pending");
    });
  });

  // ---- the change animation: from the drawing before the edit to this one ------------------------

  var changed = cfg.changed || [];
  if (changed.length) {
    var note = document.createElement("span");
    note.id = "dd-changed";
    note.textContent = "Changed: " + changed.slice(0, 3).join(" · ") + (changed.length > 3 ? " · and " + (changed.length - 3) + " more" : "");
    note.title = changed.join("\n");
    bar.appendChild(note);
  }

  function signature(el) {
    var keys = ["d", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "points", "width", "height", "fill", "stroke"];
    return el.tagName + "|" + keys.map(function (k) { return el.getAttribute(k) || ""; }).join("|") + "|" + (el.textContent || "");
  }

  var overlay = null;
  function animate() {
    if (!cfg.previous || reduced) return;
    var holder = document.createElement("div");
    holder.style.cssText = "position:absolute;left:-100000px;top:0;visibility:hidden";
    holder.innerHTML = cfg.previous;
    document.body.appendChild(holder);
    var oldSvg = holder.querySelector("svg");
    if (!oldSvg) { holder.remove(); return; }
    var before = readBoxes(oldSvg);
    var same = {};
    Array.prototype.forEach.call(oldSvg.children, function (el) { same[signature(el)] = true; });
    if (overlay) overlay.remove();
    overlay = document.createElementNS(NS, "g");
    overlay.setAttribute("class", "dd-overlay");
    svg.appendChild(overlay);
    var slide = "transform 650ms cubic-bezier(.2,.7,.2,1)";
    Object.keys(nodes).forEach(function (id) {
      var n = nodes[id], o = before[id];
      if (!n.g) return;
      n.g.style.transition = "none";
      if (o) {
        n.g.style.transform = "translate(" + (o.x - n.x) + "px," + (o.y - n.y) + "px)";
        n.g.style.opacity = "";
      } else {
        n.g.style.transform = "";
        n.g.style.opacity = "0";
      }
    });
    Object.keys(before).forEach(function (id) { // boxes the edit removed: shown where they were, fading
      if (nodes[id]) return;
      before[id].parts.forEach(function (p) {
        var c = p.cloneNode(true);
        c.style.transition = "opacity 300ms ease";
        overlay.appendChild(c);
      });
    });
    var fresh = Array.prototype.filter.call(svg.children, function (el) {
      var tag = el.tagName.toLowerCase();
      return el !== overlay && tag !== "defs" && tag !== "title" && tag !== "desc" && tag !== "style" &&
        !(el.classList && el.classList.contains("dd-node")) && !same[signature(el)];
    });
    fresh.forEach(function (el) { el.style.transition = "none"; el.style.opacity = "0"; });
    holder.remove();
    svg.getBoundingClientRect(); // the start positions take effect before the transitions begin
    requestAnimationFrame(function () {
      Object.keys(nodes).forEach(function (id) {
        var n = nodes[id];
        if (!n.g) return;
        n.g.style.transition = before[id] ? slide : "opacity 400ms ease 300ms";
        n.g.style.transform = "";
        n.g.style.opacity = "";
      });
      Array.prototype.forEach.call(overlay.children, function (c) { c.style.opacity = "0"; });
      fresh.forEach(function (el) { el.style.transition = "opacity 400ms ease 450ms"; el.style.opacity = ""; });
      setTimeout(function () { if (overlay) { overlay.remove(); overlay = null; } }, 1000);
    });
  }

  if (cfg.previous) {
    var replay = button("Replay change", "Animate from the drawing before the last edit to this one");
    replay.addEventListener("click", animate);
    bar.appendChild(replay);
    if (document.readyState === "complete") animate();
    else window.addEventListener("load", animate);
  }

  window.ddPage = {nodes: nodes, rows: rowsOf, ops: function () { return ops.map(function (o) { return o.op; }); }, animate: animate};
})();

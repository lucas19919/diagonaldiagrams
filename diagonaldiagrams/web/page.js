/* diagonaldiagrams: a diagram page's edit mode and change animation (DESIGN 21.2, 21.3).
 *
 * Settings come from <script id="dd-page" type="application/json">: the figure's kind, its spec
 * and output paths, the layout's layers (rows top to bottom, or columns left to right when
 * "across"), the drawing before the last edit (or null), and what changed.
 *
 * Edit mode never edits the figure's source. A rename, a color or a move shows in place and is
 * collected as a patch operation; the engine writes the patch into the spec (apply) and draws the
 * figure again, and the new page animates from the old drawing to the new one. Moves work with the
 * mouse and the keyboard alike: a box goes into a layer at a place, which is a place patch (an
 * order patch for a sequence's actors). A sequence's messages move between steps, an order patch
 * over the messages, and take a new label, a text patch.
 */
(function () {
  "use strict";
  var cfgEl = document.getElementById("dd-page");
  var svg = document.querySelector("body > svg");
  if (!cfgEl || !svg) return;
  var cfg = JSON.parse(cfgEl.textContent);
  var NS = "http://www.w3.org/2000/svg";
  var reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var ROW = 30; // outline.layout_rows' row tolerance, for a figure that gives no layers
  var SWATCHES = ["#fde2e2", "#fff1d6", "#e3f4e1", "#dfeefc", "#ece5fb", null];
  var across = !!cfg.across; // layers run left to right (schema columns); a layer's boxes go down

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
      g.setAttribute("aria-label", n.shape.getAttribute("aria-label") || n.label);
      n.parts[0].parentNode.insertBefore(g, n.parts[0]);
      n.parts.forEach(function (p) { g.appendChild(p); });
      n.g = g;
      n.dx = 0; n.dy = 0;
    });
    return nodes;
  }

  var nodes = group(readBoxes(svg));

  // ---- a sequence's messages: each line (or self-call loop) and its label, as one piece --------------

  function msgY(el) { // the step a message stands at: its line's y, or the top of a self-call's loop
    var y = parseFloat(el.getAttribute("y1"));
    return isNaN(y) ? el.getBBox().y : y;
  }

  function readMessages(root) {
    var out = {}, kids = Array.prototype.slice.call(root.children);
    kids.forEach(function (el, k) {
      if (!el.hasAttribute("data-msg")) return;
      var y = msgY(el), b = el.getBBox();
      var m = {id: el.getAttribute("data-id"), label: el.getAttribute("data-msg"), line: el, parts: [el], y: y, msg: true,
               x0: b.x, x1: b.x + b.width, start: isNaN(parseFloat(el.getAttribute("x1"))) ? b.x : parseFloat(el.getAttribute("x1"))};
      for (var j = k + 1; j < kids.length; j++) { // its label comes next: a pill and its text, beside the line
        var s = kids[j], sb;
        if (s.hasAttribute("data-msg") || s.hasAttribute("data-node") || s.tagName.toLowerCase() === "g") break;
        try { sb = s.getBBox(); } catch (e) { break; }
        var mid = sb.y + sb.height / 2;
        if (mid < y - 30 || mid > y + 34) break;
        m.parts.push(s);
      }
      out[m.id] = m;
    });
    return out;
  }

  function groupMessages(msgs) {
    Object.keys(msgs).forEach(function (id) {
      var m = msgs[id], g = document.createElementNS(NS, "g"), line = m.line;
      g.setAttribute("class", "dd-msg");
      g.setAttribute("data-of", id);
      g.setAttribute("aria-label", line.getAttribute("aria-label") || m.label);
      line.parentNode.insertBefore(g, line);
      var hit = document.createElementNS(NS, line.tagName.toLowerCase() === "line" ? "line" : "path"); // the drawn line is a hairline
      ["x1", "y1", "x2", "y2", "d"].forEach(function (k) { if (line.hasAttribute(k)) hit.setAttribute(k, line.getAttribute(k)); });
      hit.setAttribute("class", "dd-hit");
      hit.setAttribute("aria-hidden", "true");
      g.appendChild(hit);
      m.parts.forEach(function (p) { g.appendChild(p); });
      m.g = g;
      m.dx = 0; m.dy = 0;
    });
    return msgs;
  }

  var msgs = cfg.kind === "seq" ? groupMessages(readMessages(svg)) : {};
  var steps = Object.keys(msgs).sort(function (a, b) { return msgs[a].y - msgs[b].y; }); // message ids, in the order shown
  var stepY = steps.map(function (id) { return msgs[id].y; });
  var PIECE = ".dd-node, .dd-msg";
  function itemOf(g) {
    var id = g.getAttribute("data-of");
    return g.classList.contains("dd-msg") ? msgs[id] : nodes[id];
  }

  // ---- layers: which boxes share a row (or a column), in order --------------------------------------

  function along(n) { return across ? n.y + n.dy : n.x + n.dx; } // the position within a layer
  function cross(n) { return across ? n.x + n.dx : n.y + n.dy; } // the layer's position

  var model = (cfg.layers || []).map(function (layer) {
    return layer.filter(function (id) { return nodes[id]; });
  }).filter(function (layer) { return layer.length; });
  if (!model.length) { // a figure that gave no layers: rows by height, as the verdict counts them
    Object.keys(nodes).map(function (k) { return nodes[k]; }).sort(function (a, b) { return a.y - b.y || a.x - b.x; })
      .forEach(function (n) {
        var last = model[model.length - 1];
        if (last && Math.abs(nodes[last[0]].y - n.y) < ROW) last.push(n.id);
        else model.push([n.id]);
      });
  }
  function layerOf(id) {
    for (var i = 0; i < model.length; i++) if (model[i].indexOf(id) >= 0) return i;
    return -1;
  }
  function sorted(layer) { return layer.slice().sort(function (a, b) { return along(nodes[a]) - along(nodes[b]); }); }

  // ---- page chrome --------------------------------------------------------------------------------

  var bar = document.getElementById("gbar");
  var css = document.createElement("style");
  css.textContent = [
    ".dd-on .dd-node,.dd-on .dd-msg{cursor:grab}",
    ".dd-on .dd-node:hover,.dd-on .dd-msg:hover{filter:drop-shadow(0 0 2px rgba(45,49,66,.45))}",
    ".dd-node:focus,.dd-msg:focus{outline:none}",
    ".dd-hit{stroke:transparent;stroke-width:14;fill:none;pointer-events:none}",
    ".dd-on .dd-hit{pointer-events:stroke}",
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
    "#dd-panel kbd{font:11px ui-monospace,monospace;border:1px solid rgba(45,49,66,.3);border-radius:3px;padding:0 3px}",
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
  var canMove = ["flow", "arch", "schema", "seq"].indexOf(cfg.kind) >= 0;
  var canColor = canMove; // every diagram's boxes take a fill: steps, services, tables, actors
  var seq = cfg.kind === "seq";
  var keysAlong = across ? ["ArrowUp", "ArrowDown"] : ["ArrowLeft", "ArrowRight"];
  var keysCross = across ? ["ArrowLeft", "ArrowRight"] : ["ArrowUp", "ArrowDown"];
  var layerWord = across ? "column" : "row";

  var panel = document.createElement("div");
  panel.id = "dd-panel";
  panel.innerHTML =
    '<h4>Edit</h4>' +
    '<div class="dd-note">Click a box, or <kbd>Tab</kbd> to one, to rename' + (canColor ? ' or recolor' : '') + ' it' +
    (seq ? '; click a message to change its label' : '') + '.' +
    (canMove ? (seq ? ' Drag an actor along the actors, or a message to another step; <kbd>Shift</kbd>+arrows move them too.'
                    : ' Drag it to another place, or press <kbd>Shift</kbd>+arrows to move it within its ' + layerWord + ' or into the next.') : '') +
    '</div>' +
    '<div class="dd-note">Arrows go to the next box' + (seq ? ' (<kbd>Down</kbd> from an actor goes to its first message)' : '') +
    '; <kbd>Enter</kbd> renames' + (canColor ? '; <kbd>1</kbd>-<kbd>6</kbd> color' : '') +
    '; <kbd>Ctrl</kbd>+<kbd>Z</kbd> undoes; <kbd>Esc</kbd> lets go.</div>' +
    '<div id="dd-box" style="display:none">' +
    '  <label class="dd-note" for="dd-name" id="dd-name-label">Name</label><input id="dd-name" autocomplete="off">' +
    (canColor ? '  <div id="dd-color"><div class="dd-note">Color</div><div id="dd-swatches"></div></div>' : '') +
    '</div>' +
    '<h4>Patch <span id="dd-count"></span></h4><pre id="dd-ops">[]</pre>' +
    '<div><span id="dd-actions"></span></div>' +
    '<div class="dd-note">Then write it into the spec and draw again:</div><pre id="dd-cmd"></pre>' +
    '<div class="dd-note">Keep the patch: after the spec is regenerated, apply it again, and edits that no longer fit are reported.</div>';
  document.body.appendChild(panel);
  var live = document.createElement("div"); // what moved, for screen readers
  live.setAttribute("aria-live", "polite");
  live.style.cssText = "position:absolute;left:-10000px";
  document.body.appendChild(live);

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
  function record(op, revert, said) {
    ops.push({op: op, revert: revert});
    refresh();
    if (said) live.textContent = said;
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
  function undo() {
    var o = ops.pop();
    if (o) o.revert();
    refresh();
    if (selected) select(selected);
  }
  undoBtn.addEventListener("click", undo);
  cmdBtn.addEventListener("click", function () {
    navigator.clipboard.writeText(document.getElementById("dd-cmd").textContent).then(function () { flash(cmdBtn, "Copied"); });
  });

  var editBtn = button("Edit", "Rename, recolor and move boxes; the changes become a patch");
  bar.appendChild(editBtn);
  function setEditing(on) {
    editing = on;
    document.body.classList.toggle("dd-on", editing);
    editBtn.textContent = editing ? "Done editing" : "Edit";
    // boxes take focus only while editing; messages from the arrow keys, so Tab goes from box to box
    Object.keys(nodes).map(function (id) { return nodes[id]; }).concat(steps.map(function (id) { return msgs[id]; }))
      .forEach(function (n) {
        var g = n.g;
        if (!g) return;
        if (editing) { g.setAttribute("tabindex", n.msg ? "-1" : "0"); g.setAttribute("role", "button"); }
        else { g.removeAttribute("tabindex"); g.removeAttribute("role"); }
      });
    if (!editing) select(null);
  }
  editBtn.addEventListener("click", function () { setEditing(!editing); });

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
    document.getElementById("dd-name").value = n.label;
    document.getElementById("dd-name-label").textContent = n.msg ? "Label" : "Name";
    if (canColor) {
      document.getElementById("dd-color").style.display = n.msg ? "none" : "";
      if (!n.msg) swatches(n);
    }
  }

  // the text a box shows its name in: its largest text (a wrapped name is several lines)
  function nameTexts(n) {
    var texts = Array.prototype.filter.call(n.g.querySelectorAll("text"), function (t) { return t.textContent.trim(); });
    var size = Math.max.apply(null, texts.map(function (t) { return parseFloat(t.getAttribute("font-size")) || 0; }).concat([0]));
    return texts.filter(function (t) { return (parseFloat(t.getAttribute("font-size")) || 0) === size; });
  }

  function rename(n, name) {
    if (!n || !name || name === n.label) return;
    var was = n.label, texts = nameTexts(n), old = texts.map(function (t) { return [t.textContent, t.style.display]; });
    texts.forEach(function (t, i) {
      if (i) t.style.display = "none";
      else t.textContent = n.msg && was && t.textContent.indexOf(was) >= 0 ? t.textContent.replace(was, name) : name; // keeps [HTTPS]
    });
    n.label = name;
    var op = n.msg ? {op: "text", id: n.id, label: name, was: was} : {op: "text", id: n.id, name: name, was: was};
    record(op, function () {
      texts.forEach(function (t, i) { t.textContent = old[i][0]; t.style.display = old[i][1]; });
      n.label = was;
    }, (n.msg ? "Relabeled the message " : "Renamed ") + (was || "with no label") + " to " + name);
  }
  var nameInput = document.getElementById("dd-name");
  nameInput.addEventListener("change", function () { rename(selected, this.value.trim()); });
  nameInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { rename(selected, this.value.trim()); if (selected) selected.g.focus(); e.preventDefault(); }
    else if (e.key === "Escape") { this.value = selected ? selected.label : ""; if (selected) selected.g.focus(); e.preventDefault(); }
    e.stopPropagation();
  });

  function recolor(n, c) {
    var was = n.shape.getAttribute("fill");
    if (c) n.shape.setAttribute("fill", c);
    record({op: "style", selector: "#" + n.id, set: {fill: c}}, function () { n.shape.setAttribute("fill", was); },
           c ? "Recolored " + n.label : "Back to the style's color: " + n.label);
  }
  function swatches(n) {
    var host = document.getElementById("dd-swatches");
    host.innerHTML = "";
    SWATCHES.forEach(function (c, k) {
      var s = document.createElement("span");
      s.className = "dd-sw";
      s.title = (k + 1) + ": " + (c ? c : "back to the style's color");
      s.style.background = c || "linear-gradient(135deg,#fff 45%,#eb6c36 46%,#eb6c36 54%,#fff 55%)";
      s.addEventListener("click", function () { recolor(n, c); });
      host.appendChild(s);
    });
  }

  function place(n, dx, dy) {
    n.dx = dx; n.dy = dy;
    n.g.setAttribute("transform", dx || dy ? "translate(" + dx + " " + dy + ")" : "");
    n.g.classList.toggle("dd-pending", !!(dx || dy));
  }

  // a move: n into layer li at index k among the layer's other boxes. The patch says the layer's
  // new order; the box is shown at the spot it takes (or where it was dropped). False: no change.
  function move(n, li, k, at) {
    var from = layerOf(n.id);
    var rest = sorted(model[li]).filter(function (id) { return id !== n.id; });
    k = Math.max(0, Math.min(rest.length, k));
    var row = rest.slice(0, k).concat([n.id], rest.slice(k));
    if (from === li && sorted(model[li]).join("\u0000") === row.join("\u0000")) return false;
    if (cfg.kind !== "seq" && !rest.length) return false; // a place needs another box in its layer
    var before = model.map(function (l) { return l.slice(); }), was = {dx: n.dx, dy: n.dy};
    if (from >= 0) model[from] = model[from].filter(function (id) { return id !== n.id; });
    model[li] = row;
    if (!at) { // the spot it takes: between its new neighbors, at the layer's line
      var a = row[k - 1] && nodes[row[k - 1]], b = row[k + 1] && nodes[row[k + 1]];
      var size = across ? n.box.height : n.box.width, gap = 24;
      var spot = a && b ? (along(a) + along(b)) / 2 : a ? along(a) + size + gap : along(b) - size - gap;
      var line = rest.reduce(function (s, id) { return s + cross(nodes[id]); }, 0) / rest.length;
      at = across ? {x: line, y: spot} : {x: spot, y: line};
    }
    place(n, at.x - n.x, at.y - n.y);
    var op = cfg.kind === "seq" ? {op: "order", ids: row} : {op: "place", id: n.id, row: row};
    record(op, function () { model = before; place(n, was.dx, was.dy); },
           "Moved " + n.label + (from === li ? " to place " + (k + 1) + " of " + row.length : " to " + layerWord + " " + (li + 1)));
    return true;
  }

  // a message moved to step k: the messages from its old step to its new one shift by one. The
  // patch orders that stretch of messages; they take the steps they held.
  function showSteps() {
    steps.forEach(function (id, k) { place(msgs[id], 0, stepY[k] - msgs[id].y); });
  }
  function moveMsg(m, k) {
    var from = steps.indexOf(m.id);
    k = Math.max(0, Math.min(steps.length - 1, k));
    if (k === from) return false;
    var before = steps.slice();
    steps.splice(from, 1);
    steps.splice(k, 0, m.id);
    showSteps();
    record({op: "order", ids: steps.slice(Math.min(from, k), Math.max(from, k) + 1)},
           function () { steps = before; showSteps(); },
           "Moved the message " + (m.label || "") + " to step " + (k + 1) + " of " + steps.length);
    return true;
  }

  // the mouse: the box follows the pointer; the drop goes into the layer of the nearest box
  function toSvg(evt) {
    var p = svg.createSVGPoint();
    p.x = evt.clientX; p.y = evt.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }
  var drag = null;
  svg.addEventListener("pointerdown", function (evt) {
    if (!editing) return;
    var g = evt.target.closest && evt.target.closest(PIECE);
    if (!g) { select(null); return; }
    var n = itemOf(g);
    select(n);
    if (!canMove) return;
    var p = toSvg(evt);
    drag = {n: n, x0: p.x, y0: p.y, dx: n.dx, dy: n.dy, moved: false};
    try { g.setPointerCapture(evt.pointerId); } catch (e) { /* a pointer the page can't capture still drags */ }
    evt.preventDefault();
  });
  svg.addEventListener("pointermove", function (evt) {
    if (!drag) return;
    var p = toSvg(evt), dx = drag.n.msg ? 0 : drag.dx + p.x - drag.x0, dy = drag.dy + p.y - drag.y0; // a message moves in time only
    if (Math.abs(p.x - drag.x0) + Math.abs(p.y - drag.y0) > 3) drag.moved = true;
    drag.n.g.setAttribute("transform", "translate(" + dx + " " + dy + ")");
  });
  svg.addEventListener("pointerup", function (evt) {
    if (!drag) return;
    var d = drag, n = d.n;
    drag = null;
    n.g.focus({preventScroll: true});
    if (!d.moved) return;
    var p = toSvg(evt), dx = d.dx + p.x - d.x0, dy = d.dy + p.y - d.y0, x = n.x + dx, y = n.y + dy;
    if (n.msg) { // the step it was dropped at: after every other message drawn above it
      var at = n.y + dy;
      var k = steps.filter(function (id) { return id !== n.id && msgs[id].y + msgs[id].dy < at; }).length;
      if (!moveMsg(n, k)) place(n, d.dx, d.dy);
      return;
    }
    var near = null, best = Infinity;
    Object.keys(nodes).forEach(function (id) {
      var m = nodes[id];
      if (id === n.id) return;
      var dist = Math.hypot(m.x + m.dx - x, m.y + m.dy - y);
      if (dist < best) { best = dist; near = m; }
    });
    var reach = 1.5 * Math.max(n.box.width, n.box.height, 120);
    var li = near ? layerOf(near.id) : -1;
    if (li < 0 || best > reach) { place(n, d.dx, d.dy); return; }
    var pos = across ? y : x;
    var k = sorted(model[li]).filter(function (id) { return id !== n.id && along(nodes[id]) < pos; }).length;
    if (!move(n, li, k, {x: x, y: y})) place(n, d.dx, d.dy);
  });

  // the keyboard: arrows go to the next box, Shift+arrows move the box, as the mouse does
  function nearestActor(x) {
    return Object.keys(nodes).map(function (id) { return nodes[id]; })
      .sort(function (a, b) { return Math.abs(a.x - x) - Math.abs(b.x - x); })[0] || null;
  }
  function neighbor(n, key) {
    if (n.msg) { // up and down the steps; up from the first goes to its sender
      var s = steps.indexOf(n.id);
      if (key === "ArrowDown") return msgs[steps[s + 1]] || null;
      if (key === "ArrowUp") return s > 0 ? msgs[steps[s - 1]] : nearestActor(n.start);
      return null;
    }
    if (seq && key === "ArrowDown") { // the first message to or from this actor
      var first = steps.filter(function (id) { return msgs[id].x0 - 12 <= n.x && n.x <= msgs[id].x1 + 12; })[0];
      return first ? msgs[first] : null;
    }
    var li = layerOf(n.id), layer = sorted(model[li]), k = layer.indexOf(n.id);
    if (keysAlong.indexOf(key) >= 0) return nodes[layer[k + (key === keysAlong[1] ? 1 : -1)]] || null;
    var step = key === keysCross[1] ? 1 : -1;
    for (var j = li + step; j >= 0 && j < model.length; j += step) {
      if (!model[j].length) continue;
      return model[j].map(function (id) { return nodes[id]; })
        .sort(function (a, b) { return Math.abs(along(a) - along(n)) - Math.abs(along(b) - along(n)); })[0];
    }
    return null;
  }
  function keyMove(n, key) {
    if (n.msg) {
      if (key !== "ArrowUp" && key !== "ArrowDown") return false;
      return moveMsg(n, steps.indexOf(n.id) + (key === "ArrowDown" ? 1 : -1));
    }
    var li = layerOf(n.id), layer = sorted(model[li]), k = layer.indexOf(n.id);
    if (keysAlong.indexOf(key) >= 0) return move(n, li, k + (key === keysAlong[1] ? 1 : -1));
    if (cfg.kind === "seq") return false; // a sequence's actors stand in one row
    var step = key === keysCross[1] ? 1 : -1, j = li + step;
    while (j >= 0 && j < model.length && !model[j].length) j += step;
    if (j < 0 || j >= model.length) return false;
    var at = sorted(model[j]).filter(function (id) { return along(nodes[id]) < along(n); }).length;
    return move(n, j, at);
  }
  svg.addEventListener("focusin", function (evt) {
    var g = evt.target.closest && evt.target.closest(PIECE);
    if (editing && g && (!selected || selected.g !== g)) select(itemOf(g));
  });
  document.addEventListener("keydown", function (e) {
    if (!editing) return;
    if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")) { undo(); e.preventDefault(); return; }
    if (e.target === nameInput) return;
    var focused = document.activeElement && document.activeElement.closest && document.activeElement.closest(PIECE);
    if (focused && (!selected || selected.g !== focused)) select(itemOf(focused));
    if (!selected) return;
    var n = selected;
    if (e.key.indexOf("Arrow") === 0) {
      if (e.shiftKey) { if (canMove) keyMove(n, e.key); }
      else { var m = neighbor(n, e.key); if (m) m.g.focus(); }
      e.preventDefault();
    } else if (e.key === "Enter" || e.key === "F2") {
      nameInput.focus(); nameInput.select(); e.preventDefault();
    } else if (canColor && !n.msg && /^[1-6]$/.test(e.key)) {
      recolor(n, SWATCHES[+e.key - 1]); e.preventDefault();
    } else if (e.key === "Escape") {
      n.g.blur(); select(null); e.preventDefault();
    }
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
    var before = readBoxes(oldSvg), beforeMsgs = seq ? readMessages(oldSvg) : {};
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
    steps.forEach(function (id) { // messages too: each starts at the step it held
      var m = msgs[id], o = beforeMsgs[id];
      m.g.style.transition = "none";
      m.g.style.transform = o ? "translate(0px," + (o.y - m.y) + "px)" : "";
      m.g.style.opacity = o ? "" : "0";
    });
    [[before, nodes], [beforeMsgs, msgs]].forEach(function (pair) { // what the edit removed: shown where it was, fading
      Object.keys(pair[0]).forEach(function (id) {
        if (pair[1][id]) return;
        pair[0][id].parts.forEach(function (p) {
          var c = p.cloneNode(true);
          c.style.transition = "opacity 300ms ease";
          overlay.appendChild(c);
        });
      });
    });
    var fresh = Array.prototype.filter.call(svg.children, function (el) {
      var tag = el.tagName.toLowerCase();
      return el !== overlay && tag !== "defs" && tag !== "title" && tag !== "desc" && tag !== "style" &&
        !(el.classList && (el.classList.contains("dd-node") || el.classList.contains("dd-msg"))) && !same[signature(el)];
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
      steps.forEach(function (id) {
        var m = msgs[id];
        m.g.style.transition = beforeMsgs[id] ? slide : "opacity 400ms ease 300ms";
        m.g.style.transform = "";
        m.g.style.opacity = "";
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

  window.ddPage = {nodes: nodes, layers: function () { return model.map(function (l) { return sorted(l); }); },
                   messages: function () { return steps.slice(); },
                   ops: function () { return ops.map(function (o) { return o.op; }); }, animate: animate,
                   edit: setEditing, select: function (id) { select(nodes[id] || msgs[id] || null); }};
})();

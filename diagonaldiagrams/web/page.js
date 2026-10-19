/* diagonaldiagrams: a diagram page's change animation (DESIGN 21.4).
 *
 * Settings come from <script id="dd-page" type="application/json">: the figure's kind, the layout's
 * layers (which `diff` reads back from an old page), the drawing before the last edit (or null), and
 * what changed. When the figure was drawn again at the same path, the page animates from the old
 * drawing to the new one: each box, and each message of a sequence, slides from where it was.
 */
(function () {
  "use strict";
  var cfgEl = document.getElementById("dd-page");
  var svg = document.querySelector("body > svg");
  if (!cfgEl || !svg) return;
  var cfg = JSON.parse(cfgEl.textContent);
  var NS = "http://www.w3.org/2000/svg";
  var reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var seq = cfg.kind === "seq";

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
      var y = msgY(el);
      var m = {id: el.getAttribute("data-id"), label: el.getAttribute("data-msg"), line: el, parts: [el], y: y};
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
      m.parts.forEach(function (p) { g.appendChild(p); });
      m.g = g;
    });
    return msgs;
  }

  var msgs = seq ? groupMessages(readMessages(svg)) : {};
  var steps = Object.keys(msgs).sort(function (a, b) { return msgs[a].y - msgs[b].y; }); // message ids, in the order shown

  // ---- page chrome --------------------------------------------------------------------------------

  var bar = document.getElementById("gbar");
  var css = document.createElement("style");
  css.textContent = "#dd-changed{font-size:12px;color:#4f5d75;margin-left:.6rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}";
  document.head.appendChild(css);

  function button(label, title) {
    var b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    if (title) b.title = title;
    return b;
  }

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

  window.ddPage = {nodes: nodes, messages: function () { return steps.slice(); }, animate: animate};
})();

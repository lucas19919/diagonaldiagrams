/* diagonaldiagrams: a story's presenter (DESIGN 21.2, 21.5).
 *
 * The page holds every frame the engine drew: one per view, or one per reveal step. All frames have
 * the same layout, so moving between them changes only looks (opacity, stroke, fill, line width)
 * and the camera (the viewBox). Those are animated; anything else is set at once. Keys: arrows,
 * Space, Page Up/Down, Home, End; N shows the speaker notes. The address bar keeps the view and
 * step (#view or #view/2), so a link opens the story where it was.
 */
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("dd-story").textContent);
  var frames = data.frames, views = data.views;
  var stage = document.getElementById("stage");
  var reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var LOOKS = ["opacity", "stroke", "fill", "stroke-width"];
  var BLANK = {opacity: "1"};
  var full = [0, 0, data.size[0], data.size[1]];
  var at = -1, box = full.slice(), tween = null;

  function parse(markup) {
    var holder = document.createElement("div");
    holder.innerHTML = markup;
    return holder.querySelector("svg");
  }
  var live = parse(frames[0].svg);
  live.removeAttribute("width");
  live.setAttribute("preserveAspectRatio", "xMidYMid meet");
  stage.appendChild(live);
  var parsed = frames.map(function () { return null; });
  function frameSvg(k) {
    if (!parsed[k]) parsed[k] = parse(frames[k].svg);
    return parsed[k];
  }

  function setBox(b) {
    box = b;
    live.setAttribute("viewBox", b.map(function (v) { return Math.round(v * 10) / 10; }).join(" "));
  }
  function moveCamera(to) {
    if (tween) cancelAnimationFrame(tween);
    var from = box.slice(), t0 = null, ms = reduced ? 0 : 650;
    if (!ms) { setBox(to); return; }
    function step(t) {
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / ms), e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      setBox(from.map(function (v, i) { return v + (to[i] - v) * e; }));
      if (p < 1) tween = requestAnimationFrame(step);
    }
    tween = requestAnimationFrame(step);
  }

  function apply(k) {
    var target = frameSvg(k), a = live.children, b = target.children;
    var same = a.length === b.length && Array.prototype.every.call(a, function (el, i) { return el.tagName === b[i].tagName; });
    if (!same) { // a frame drawn differently: take it whole, without a transition
      var fresh = parse(frames[k].svg);
      fresh.removeAttribute("width");
      fresh.setAttribute("preserveAspectRatio", "xMidYMid meet");
      stage.replaceChild(fresh, live);
      live = fresh;
      setBox(box);
      return;
    }
    Array.prototype.forEach.call(a, function (el, i) {
      var to = b[i], tag = el.tagName.toLowerCase();
      if (tag === "defs") { el.innerHTML = to.innerHTML; return; }
      if (tag === "title" || tag === "desc") return;
      LOOKS.forEach(function (name) {
        var v = to.getAttribute(name);
        el.style.setProperty(name, v !== null ? v : (BLANK[name] || ""));
      });
      Array.prototype.forEach.call(to.attributes, function (attr) {
        if (LOOKS.indexOf(attr.name) < 0 && el.getAttribute(attr.name) !== attr.value) el.setAttribute(attr.name, attr.value);
      });
      if (!el.children.length && el.textContent !== to.textContent) el.textContent = to.textContent;
    });
  }

  var titleEl = document.getElementById("view-title"), textEl = document.getElementById("view-text");
  var notesEl = document.getElementById("notes"), countEl = document.getElementById("count");
  var dotsEl = document.getElementById("dots");
  views.forEach(function (v, i) {
    var d = document.createElement("button");
    d.type = "button";
    d.className = "dot";
    d.title = v.title || v.id;
    d.setAttribute("aria-label", "View " + (i + 1) + ": " + (v.title || v.id));
    d.addEventListener("click", function () { go(frames.findIndex(function (f) { return f.view === i; })); });
    dotsEl.appendChild(d);
  });

  function go(k) {
    k = Math.max(0, Math.min(frames.length - 1, k));
    if (k === at) return;
    var f = frames[k], v = views[f.view], first = at < 0;
    if (!first) apply(k);
    at = k;
    if (first) setBox(f.viewBox || full);
    else moveCamera(f.viewBox || full);
    titleEl.textContent = v.title || "";
    textEl.textContent = v.text || "";
    textEl.style.display = v.text ? "" : "none";
    notesEl.textContent = v.notes || "No notes for this view.";
    countEl.textContent = (f.view + 1) + " / " + views.length + (f.steps > 1 ? "  ·  step " + (f.step + 1) + " of " + f.steps : "");
    Array.prototype.forEach.call(dotsEl.children, function (d, i) { d.classList.toggle("on", i === f.view); });
    document.getElementById("prev").disabled = k === 0;
    document.getElementById("next").disabled = k === frames.length - 1;
    var hash = "#" + encodeURIComponent(v.id) + (f.steps > 1 ? "/" + (f.step + 1) : "");
    if (location.hash !== hash) history.replaceState(null, "", hash);
  }

  function fromHash() {
    var h = decodeURIComponent(location.hash.slice(1)).split("/");
    var vi = views.findIndex(function (v) { return v.id === h[0]; });
    if (vi < 0) return 0;
    var step = Math.max(0, (parseInt(h[1], 10) || 1) - 1);
    var k = frames.findIndex(function (f) { return f.view === vi && f.step === step; });
    return k < 0 ? frames.findIndex(function (f) { return f.view === vi; }) : k;
  }

  document.getElementById("prev").addEventListener("click", function () { go(at - 1); });
  document.getElementById("next").addEventListener("click", function () { go(at + 1); });
  document.addEventListener("keydown", function (e) {
    if (e.target && /input|textarea/i.test(e.target.tagName)) return;
    if (["ArrowRight", "PageDown", " "].indexOf(e.key) >= 0) { go(at + 1); e.preventDefault(); }
    else if (["ArrowLeft", "PageUp", "Backspace"].indexOf(e.key) >= 0) { go(at - 1); e.preventDefault(); }
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(frames.length - 1);
    else if (e.key === "n" || e.key === "N") document.body.classList.toggle("notes-on");
  });
  window.addEventListener("hashchange", function () { go(fromHash()); });

  // printing: one page per frame, each with its camera
  var print = document.getElementById("print");
  frames.forEach(function (f) {
    var v = views[f.view], page = document.createElement("section");
    page.className = "page";
    var h = document.createElement("h2");
    h.textContent = (v.title || v.id) + (f.steps > 1 ? " (" + (f.step + 1) + "/" + f.steps + ")" : "");
    page.appendChild(h);
    var s = parse(f.svg);
    s.removeAttribute("width");
    if (f.viewBox) s.setAttribute("viewBox", f.viewBox.join(" "));
    page.appendChild(s);
    if (v.text) { var p = document.createElement("p"); p.textContent = v.text; page.appendChild(p); }
    print.appendChild(page);
  });

  setBox(full);
  var first = fromHash();
  if (first > 0) apply(first); // the live drawing starts as frame 0
  go(first); // at is -1, so this draws the page for the first frame without a transition
  window.ddStory = {go: go, at: function () { return at; }, frames: frames.length};
})();

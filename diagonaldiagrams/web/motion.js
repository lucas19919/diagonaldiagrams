/* diagonaldiagrams: motion from meaning.
 *
 * The engine resolves a view's motion block into a schedule (motion.py): each arrow's route as a
 * polyline with its lengths, and each event's start and end. at(schedule, t) is the motion layer
 * at time t, the same arithmetic as motion.at() in Python, so the page and the exported frames
 * agree (a test holds them equal). draw(group, shapes) puts that layer into an SVG group.
 */
(function (root) {
  "use strict";
  var FADE = 0.5, PULSE = 0.7, TIP = 12, RAMP = 10;
  var DOT_R = 2.6, HALO_R = 10, PACKET_R = 4.6, DASH = 22, LIT_W = 2.8, GLOW_W = 9, GLOW = 0.16;

  function clamp(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
  function ease(p) { return p * p * (3 - 2 * p); }
  function n(v) {
    var s = (Math.round(v * 100) / 100).toString();
    return s === "-0" ? "0" : s;
  }
  function point(pts, cum, s) {
    if (s <= 0) return [pts[0][0], pts[0][1]];
    for (var i = 1; i < pts.length; i++) {
      if (cum[i] >= s) {
        var seg = cum[i] - cum[i - 1], f = seg > 0 ? (s - cum[i - 1]) / seg : 1;
        return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f];
      }
    }
    return [pts[pts.length - 1][0], pts[pts.length - 1][1]];
  }
  function between(pts, cum, s0, s1) {
    var out = [point(pts, cum, s0)];
    for (var i = 1; i < pts.length; i++) if (s0 < cum[i] && cum[i] < s1) out.push([pts[i][0], pts[i][1]]);
    out.push(point(pts, cum, s1));
    return out;
  }
  function d(line) {
    return "M" + line.map(function (p) { return n(p[0]) + "," + n(p[1]); }).join(" L");
  }
  function head(pts) {
    var x1 = pts[pts.length - 1][0], y1 = pts[pts.length - 1][1], dx = 0, dy = 0, L = 0;
    for (var i = pts.length - 2; i >= 0; i--) {
      dx = x1 - pts[i][0]; dy = y1 - pts[i][1]; L = Math.sqrt(dx * dx + dy * dy);
      if (L > 0.5) break;
    }
    if (!(L > 0.5)) return null;
    var ux = dx / L, uy = dy / L, bx = x1 - ux * 11.5, by = y1 - uy * 11.5;
    return [[x1 + ux * 1.4, y1 + uy * 1.4], [bx - uy * 5, by + ux * 5], [bx + uy * 5, by - ux * 5]]
      .map(function (p) { return n(p[0]) + "," + n(p[1]); }).join(" ");
  }
  function extend(a, b) { var o = {}, k; for (k in a) o[k] = a[k]; for (k in b) o[k] = b[k]; return o; }

  function at(s, t) {
    var loop = s.loop;
    t = ((t % loop) + loop) % loop;
    var dots = [], glows = [], cores = [], heads = [], rings = [], packets = [];
    s.flows.forEach(function (f) {
      var end = f.cum[f.cum.length - 1] - TIP, x = (f.v * t) % f.gap;
      for (; x <= end; x += f.gap) {
        var op = Math.min(1, x / RAMP, (end - x) / RAMP);
        if (op > 0.01) {
          var p = point(f.pts, f.cum, x);
          dots.push(["circle", {cx: p[0], cy: p[1], r: DOT_R, fill: f.color, opacity: op}]);
        }
      }
    });
    s.traces.forEach(function (tr) {
      var u = t - tr.t0;
      if (u < 0 || u >= tr.dur) return;
      var c = tr.color, fade = 1 - clamp((u - tr.end - tr.hold) / FADE);
      for (var k = 0; k < tr.hops.length; k++) {
        var h = tr.hops[k];
        if (u < h.a || fade <= 0) break;
        var L = h.cum[h.cum.length - 1], moving = u < h.b;
        var pos = moving ? L * ease((u - h.a) / (h.b - h.a)) : L;
        var line = {d: d(between(h.pts, h.cum, 0, pos)), fill: "none", stroke: c, "stroke-linecap": "round", "stroke-linejoin": "round"};
        glows.push(["path", extend(line, {"stroke-width": GLOW_W, opacity: GLOW * fade})]);
        cores.push(["path", extend(line, {"stroke-width": LIT_W, opacity: fade})]);
        if (!moving && h.head) {
          var hd = head(h.pts);
          if (hd) heads.push(["polygon", {points: hd, fill: c, opacity: fade}]);
        }
        if (moving) {
          var p = point(h.pts, h.cum, pos);
          if (tr.packet === "dash") {
            var tail = d(between(h.pts, h.cum, Math.max(0, pos - DASH), pos));
            packets.push(["path", {d: tail, fill: "none", stroke: c, "stroke-linecap": "round", "stroke-width": 12, opacity: 0.22}]);
            packets.push(["path", {d: tail, fill: "none", stroke: c, "stroke-linecap": "round", "stroke-width": 5}]);
          } else {
            packets.push(["circle", {cx: p[0], cy: p[1], r: HALO_R, fill: c, opacity: 0.22}]);
            packets.push(["circle", {cx: p[0], cy: p[1], r: PACKET_R, fill: c, stroke: s.paper, "stroke-width": 1.6}]);
          }
        }
      }
      tr.pulses.forEach(function (p) {
        var w = (u - p.t) / PULSE;
        if (w < 0 || w >= 1) return;
        var op = w < 0.15 ? w / 0.15 : (1 - w) / 0.85, g = 3 + 6 * w;
        var x = p.box[0], y = p.box[1], bw = p.box[2], bh = p.box[3];
        if (p.shape === "diamond") {
          var cx = x + bw / 2, cy = y + bh / 2;
          var pts = [[cx, y - g], [x + bw + g, cy], [cx, y + bh + g], [x - g, cy]];
          rings.push(["polygon", {points: pts.map(function (q) { return n(q[0]) + "," + n(q[1]); }).join(" "), fill: "none", stroke: c,
                                  "stroke-width": 2, opacity: op}]);
        } else {
          rings.push(["rect", {x: x - g, y: y - g, width: bw + 2 * g, height: bh + 2 * g, rx: 8 + g, fill: "none", stroke: c,
                               "stroke-width": 2, opacity: op}]);
        }
      });
    });
    return dots.concat(glows, cores, heads, rings, packets);
  }

  var NS = "http://www.w3.org/2000/svg";
  function draw(g, shapes) { // reuses the group's elements, so a frame of the loop costs no new nodes
    var kids = g.childNodes;
    shapes.forEach(function (sh, i) {
      var el = kids[i];
      if (!el || el.tagName !== sh[0]) {
        var fresh = g.ownerDocument.createElementNS(NS, sh[0]);
        if (el) g.replaceChild(fresh, el); else g.appendChild(fresh);
        el = fresh;
      }
      var attrs = sh[1], seen = {};
      for (var k in attrs) {
        var v = attrs[k];
        el.setAttribute(k, typeof v === "number" ? n(v) : v);
        seen[k] = true;
      }
      for (var j = el.attributes.length - 1; j >= 0; j--) if (!seen[el.attributes[j].name]) el.removeAttribute(el.attributes[j].name);
    });
    while (kids.length > shapes.length) g.removeChild(g.lastChild);
  }

  root.ddMotion = {at: at, draw: draw, fmt: n};
})(typeof window !== "undefined" ? window : globalThis);

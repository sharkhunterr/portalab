// Manga — the toolkit the four scenes share, to draw anime effects in EffectCraft frame by frame for video:
// comps built in slices of frames side by side (FROM..TO: only their layers are made) and at a scale (S: every
// shape drawn in the scenes' own coordinates, the comp S times as large); each frame four layers, made in this
// order — haze and glow (blurred and added: light), main, top — so what is drawn on each is laid in a fixed
// order. Within a layer, groups added later go below. Times in frames (24 a second), y downwards.
var F = 1 / 24;
if (typeof FROM === "undefined") var FROM = 0;
if (typeof TO === "undefined") var TO = 100000;
if (typeof S === "undefined") var S = 1;
var BLACK = [0.04, 0.03, 0.06], WHITE = [1, 1, 1];

var _seed = 1;
function seed(s) { _seed = Math.floor(Math.abs(s)) % 2147483646 + 1; }
function rnd() { _seed = (_seed * 16807) % 2147483647; return (_seed - 1) / 2147483646; }
function between(a, b) { return a + (b - a) * rnd(); }
function pick(list) { return list[Math.floor(rnd() * list.length)]; }
function clamp01(x) { return Math.max(0, Math.min(1, x)); }
function ease(x) { x = clamp01(x); return 1 - Math.pow(1 - x, 3); }
function inOut(x) { x = clamp01(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
function back(x) { x = clamp01(x); var c = 1.70158; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); }
function fade(f, a, b) { return f < a ? 1 : Math.max(0, 1 - (f - a) / (b - a)); }   // 1 until a, 0 at b

function newComp(name, w, h, count) { return app.project.items.addComp(name, Math.round(w * S), Math.round(h * S), 1, count * F, 24); }
function tr(L, name) { return L.property("ADBE Transform Group").property(name); }
function layerAt(comp, name, f, blur) {
  var L = comp.layers.addShape(); L.name = name;
  tr(L, "ADBE Anchor Point").setValue([0, 0]); tr(L, "ADBE Position").setValue([0, 0]); tr(L, "ADBE Scale").setValue([S * 100, S * 100]);
  var op = tr(L, "ADBE Opacity");
  if (f > 0) { op.setValueAtTime(0, 0); op.setValueAtTime(f * F, 100); } else { op.setValueAtTime(0, 100); }
  op.setValueAtTime((f + 1) * F, 0);
  for (var i = 1; i <= op.numKeys; i++) op.setInterpolationTypeAtKey(i, KeyframeInterpolationType.HOLD);
  if (blur) {
    // in the layer's own pixels: scaled with it
    L.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2").property("ADBE Gaussian Blur 2-0001").setValue(blur);
    L.blendingMode = BlendingMode.ADD;
  }
  return L;
}
// the four layers of frame f (null outside the slice being built): haze (wide light), glow, main, top
function frameOf(comp, f) {
  if (f < FROM || f >= TO) return { haze: null, glow: null, main: null, top: null };
  return { haze: layerAt(comp, "haze-" + f, f, 40), glow: layerAt(comp, "glow-" + f, f, 12), main: layerAt(comp, "main-" + f, f, 0), top: layerAt(comp, "top-" + f, f, 0) };
}
function group(L) { return L.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group"); }
function pathInto(g, verts, closed) {
  var p = g.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Group");
  var s = new Shape(); s.vertices = verts; s.closed = closed; p.property("ADBE Vector Shape").setValue(s);
}
// closed paths sharing a fill (its opacity in %; even-odd: a path inside another cuts it)
function polys(L, list, color, opacity, evenodd) {
  if (!L || !list || !list.length || opacity === 0) return;
  var g = group(L);
  for (var i = 0; i < list.length; i++) if (list[i].length > 2) pathInto(g, list[i], true);
  var fl = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
  fl.property("ADBE Vector Fill Color").setValue(color);
  if (opacity !== undefined && opacity < 100) fl.property("ADBE Vector Fill Opacity").setValue(Math.max(0, opacity));
  if (evenodd) fl.property("ADBE Vector Fill Rule").setValue(2);
}
// paths sharing a stroke; dash: [dash, gap] (a dash of 0.1: round dots)
function lines(L, list, color, width, opacity, closed, dash) {
  if (!L || !list || !list.length || opacity === 0 || width <= 0) return;
  var g = group(L);
  for (var i = 0; i < list.length; i++) if (list[i].length > 1) pathInto(g, list[i], !!closed);
  var st = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Stroke");
  st.property("ADBE Vector Stroke Color").setValue(color);
  st.property("ADBE Vector Stroke Width").setValue(width);
  st.property("ADBE Vector Stroke Line Join").setValue(2);
  st.property("ADBE Vector Stroke Line Cap").setValue(2);
  if (opacity !== undefined && opacity < 100) st.property("ADBE Vector Stroke Opacity").setValue(Math.max(0, opacity));
  if (dash) {
    var d = st.property("ADBE Vector Stroke Dashes");
    d.property("ADBE Vector Stroke Dash 1").setValue(dash[0]); d.property("ADBE Vector Stroke Gap 1").setValue(dash[1]);
  }
}
// the same shapes, inked: an ink line under them (only its outer half shows)
function inked(L, list, color, ink, opacity) { polys(L, list, color, opacity); lines(L, list, BLACK, ink, opacity, true); }

// --- geometry --------------------------------------------------------------------------------------------
function circle(cx, cy, r, k, n) {
  var v = [], m = n || 40;
  for (var q = 0; q < m; q++) v.push([cx + Math.cos(q / m * Math.PI * 2) * r, cy + Math.sin(q / m * Math.PI * 2) * r * (k || 1)]);
  return v;
}
function ring(cx, cy, r, k, from, to) {   // an open arc (a whole circle by default)
  var v = [], a0 = from === undefined ? 0 : from, a1 = to === undefined ? Math.PI * 2 : to, m = Math.max(8, Math.round(64 * (a1 - a0) / (Math.PI * 2)));
  for (var q = 0; q <= m; q++) { var a = a0 + (a1 - a0) * q / m; v.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r * (k || 1)]); }
  return v;
}
function toEdge(a, hw, hh) {
  var c = Math.abs(Math.cos(a)), s = Math.abs(Math.sin(a));
  return Math.min(c > 1e-4 ? hw / c : 1e9, s > 1e-4 ? hh / s : 1e9);
}
function place(list, x, y, ang, sx, sy) {
  var c = Math.cos(ang), s = Math.sin(ang), out = [];
  for (var i = 0; i < list.length; i++) { var px = list[i][0] * (sx === undefined ? 1 : sx), py = list[i][1] * (sy === undefined ? 1 : sy); out.push([x + px * c - py * s, y + px * s + py * c]); }
  return out;
}
function partOf(list, p) {
  var out = [];
  if (p <= 0) return out;
  for (var i = 0; i < list.length; i++) out.push(list[i].slice(0, Math.max(2, Math.round(list[i].length * clamp01(p)))));
  return out;
}

// --- manga effects ---------------------------------------------------------------------------------------
// an impact star: spikes of uneven length round (cx, cy)
function burst(cx, cy, n, rOut, rIn, spread, turn, k) {
  var v = [];
  for (var i = 0; i < n * 2; i++) {
    var a = (turn || 0) + i / (n * 2) * Math.PI * 2 + between(-0.12, 0.12) / n, r = i % 2 === 0 ? rOut * between(1 - (spread || 0.3), 1) : rIn * between(0.85, 1.1);
    v.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r * (k || 1)]);
  }
  return v;
}
// rays out of a centre (or a rectangle's edge, half sizes hw, hh): wedges
function rays(n, cx, cy, hw, hh, reach, width, turn) {
  var out = [];
  for (var i = 0; i < n; i++) {
    var a = (i + between(-0.3, 0.3)) / n * Math.PI * 2 + (turn || 0), w = width * between(0.5, 1.2), r0 = hw ? toEdge(a, hw, hh) * 0.92 : 0, tip = r0 + reach * between(0.5, 1);
    out.push([[cx + Math.cos(a - w) * r0, cy + Math.sin(a - w) * r0], [cx + Math.cos(a) * tip, cy + Math.sin(a) * tip], [cx + Math.cos(a + w) * r0, cy + Math.sin(a + w) * r0]]);
  }
  return out;
}
// concentration lines (shūchūsen): needles from far out towards a centre, stopping short of it
function concentration(cx, cy, n, r0, r1, width) {
  var out = [];
  for (var i = 0; i < n; i++) {
    var a = (i + between(-0.45, 0.45)) / n * Math.PI * 2, tip = r0 * between(0.85, 1.4), w = width * between(0.4, 1.3) / r1;
    out.push([[cx + Math.cos(a - w) * r1, cy + Math.sin(a - w) * r1], [cx + Math.cos(a) * tip, cy + Math.sin(a) * tip], [cx + Math.cos(a + w) * r1, cy + Math.sin(a + w) * r1]]);
  }
  return out;
}
// speed lines streaking one way (angle ang) across a box: thin needles
function streaks(cx, cy, w, h, n, ang, len, width) {
  var out = [], c = Math.cos(ang), s = Math.sin(ang);
  for (var i = 0; i < n; i++) {
    var x = cx + between(-w, w), y = cy + between(-h, h), l = len * between(0.4, 1), t = width * between(0.4, 1);
    out.push([[x - c * l / 2 - s * t, y - s * l / 2 + c * t], [x + c * l / 2, y + s * l / 2], [x - c * l / 2 + s * t, y - s * l / 2 - c * t]]);
  }
  return out;
}
// halftone: rows of dots (stroke dashes of nothing, round caps) filling a ring between r0 and r1
function halftoneRows(cx, cy, r0, r1, gap) {
  var out = [];
  for (var y = -r1; y <= r1; y += gap) {
    var half = Math.sqrt(Math.max(0, r1 * r1 - y * y)), inner = Math.abs(y) < r0 ? Math.sqrt(r0 * r0 - y * y) : 0;
    if (inner > 0) { out.push([[cx - half, cy + y], [cx - inner, cy + y]]); out.push([[cx + inner, cy + y], [cx + half, cy + y]]); }
    else out.push([[cx - half, cy + y], [cx + half, cy + y]]);
  }
  return out;
}
// an aura of flames round a rectangle (half sizes hw, hh): an oval envelope a little larger, licked by pointed
// tongues all round — longest on top, the side ones leaning upwards too —, their heights changing every other
// frame (`phase`: the frame); `tones` envelopes, each smaller (the outer first)
function aura(cx, cy, hw, hh, amp, phase, tones, spikes) {
  var out = [], N = spikes || 18, heights = [];
  seed(7000 + Math.floor(phase / 2));
  for (var k = 0; k < N; k++) heights.push(between(0.35, 1));
  var rx = hw * 1.16, ry = hh * 1.08, turn = phase * 0.012;
  for (var t = 0; t < tones; t++) {
    var v = [], n = N * 8, scale = 1 - t * 0.3;
    for (var i = 0; i < n; i++) {
      var a = i / n * Math.PI * 2, c = Math.cos(a), s = Math.sin(a), r = rx * ry / Math.sqrt(Math.pow(ry * c, 2) + Math.pow(rx * s, 2));
      var sp = ((a + turn) / (Math.PI * 2) * N) % N, k2 = Math.floor(sp), u = sp - k2;
      var tongue = Math.pow(1 - Math.abs(2 * u - 1), 2.6) * heights[(k2 + N) % N];
      var up = Math.max(0, -s), reach = amp * scale * (0.18 + 0.82 * tongue) * (0.45 + 1.55 * up * up + 0.3 * Math.abs(c));
      v.push([cx + c * (r * (0.92 + 0.08 * scale) + reach * 0.45), cy + s * (r * (0.92 + 0.08 * scale) + reach * 0.45) - reach * (0.35 + 0.9 * up)]);
    }
    out.push(v);
  }
  return out;
}
// lightning: a jagged bolt from (x0, y0) to (x1, y1), forking now and then — polylines
function bolt(x0, y0, x1, y1, jag, forks) {
  var out = [], pts = [[x0, y0]], n = 9, dx = x1 - x0, dy = y1 - y0, l = Math.sqrt(dx * dx + dy * dy) || 1;
  for (var i = 1; i < n; i++) {
    var u = i / n, off = between(-jag, jag);
    var p = [x0 + dx * u - dy / l * off, y0 + dy * u + dx / l * off];
    pts.push(p);
    if (forks && rnd() < 0.3) { var fa = Math.atan2(dy, dx) + between(-0.9, 0.9), fl = l * between(0.12, 0.25); out.push([p, [p[0] + Math.cos(fa) * fl * 0.5 + between(-8, 8), p[1] + Math.sin(fa) * fl * 0.5 + between(-8, 8)], [p[0] + Math.cos(fa) * fl, p[1] + Math.sin(fa) * fl]]); }
  }
  pts.push([x1, y1]);
  out.unshift(pts);
  return out;
}
function star5(cx, cy, r, turn, inner) {
  var v = [];
  for (var i = 0; i < 10; i++) { var a = (turn || 0) - Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * (inner || 0.45) : r; v.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]); }
  return v;
}
function heart(cx, cy, r, turn) {
  var v = [];
  for (var i = 0; i < 40; i++) {
    var t = i / 40 * Math.PI * 2, x = 16 * Math.pow(Math.sin(t), 3), y = -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t));
    v.push([x / 17 * r, y / 17 * r]);
  }
  return place(v, cx, cy, turn || 0);
}
// four-pointed glints, each [x, y, r]
function glintPolys(list) {
  var all = [];
  for (var j = 0; j < list.length; j++) {
    var cx = list[j][0], cy = list[j][1], r = list[j][2], v = [];
    if (r < 0.5) continue;
    for (var i = 0; i < 36; i++) {
      var a = i / 36 * Math.PI * 2, c = Math.cos(a), s = Math.sin(a), k = Math.pow(Math.pow(Math.abs(c), 0.5) + Math.pow(Math.abs(s), 0.5), -2);
      v.push([cx + c * r * k, cy + s * r * k]);
    }
    all.push(v);
  }
  return all;
}
// glints flaring now and then at given points
function twinkle(points, f, phase, size) {
  var out = [];
  for (var i = 0; i < points.length; i++) {
    var ph = Math.sin(f * 0.55 + i * 2.3 + phase);
    if (ph > 0.5) out.push([points[i][0], points[i][1], size * (ph - 0.5) / 0.5]);
  }
  return out;
}
// a ribbon: a band along a centre line, `w` wide, turning over (its face and its back, two tones) — each stretch
// showing one side drawn as one band, so no seam shows; returns [face bands, back bands]; `keep(i)`: only the
// segments it keeps
function ribbon(pts, w, twist, phase, keep) {
  var front = [], backs = [], n = pts.length, left = [], right = [], side = null;
  var close = function () { if (left.length > 1) (side ? front : backs).push(left.concat(right.reverse())); left = []; right = []; };
  for (var i = 0; i < n; i++) {
    var a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)], tx = b[0] - a[0], ty = b[1] - a[1], l = Math.sqrt(tx * tx + ty * ty) || 1, nx = -ty / l, ny = tx / l;
    var c = Math.cos(phase + twist * i / n), half = w * Math.max(0.12, Math.abs(c)) / 2, here = c > 0;
    if ((keep && !keep(Math.min(i, n - 2))) || (side !== null && here !== side)) {
      if (left.length) { left.push([pts[i][0] + nx * half, pts[i][1] + ny * half]); right.push([pts[i][0] - nx * half, pts[i][1] - ny * half]); }
      close();
      if (keep && !keep(Math.min(i, n - 2))) { side = null; continue; }
    }
    side = here;
    left.push([pts[i][0] + nx * half, pts[i][1] + ny * half]); right.push([pts[i][0] - nx * half, pts[i][1] - ny * half]);
  }
  close();
  return [front, backs];
}
// a spiral round (cx, cy): `turns` turns from radius r0 to r1, a tilt (y squeezed), drawn up to `upto`
function spiral(cx, cy, r0, r1, turns, k, a0, upto, rise) {
  var v = [], n = 90;
  for (var i = 0; i <= n * clamp01(upto === undefined ? 1 : upto); i++) {
    var u = i / n, a = a0 + u * turns * Math.PI * 2, r = r0 + (r1 - r0) * u;
    v.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r * k - (rise || 0) * (u - 0.5)]);
  }
  return v;
}
// a magic circle: rings, a star of lines, runes as dots and ticks — {rings, star, ticks, dots} for (cx, cy), r,
// squeezed by k, turned by rot
function magicCircle(cx, cy, r, k, rot, points) {
  var rings = [ring(cx, cy, r, k), ring(cx, cy, r * 0.86, k), ring(cx, cy, r * 0.5, k)], star = [], ticks = [], dots = [], n = points || 6;
  var pts = [];
  for (var i = 0; i < n; i++) { var a = rot + i / n * Math.PI * 2; pts.push([cx + Math.cos(a) * r * 0.86, cy + Math.sin(a) * r * 0.86 * k]); }
  var step = n % 2 ? 2 : (n === 6 ? 2 : 3);
  for (var j = 0; j < n; j++) star.push([pts[j], pts[(j + step) % n]]);
  for (var t = 0; t < 48; t++) { var ta = -rot * 0.7 + t / 48 * Math.PI * 2, r1 = r * (t % 4 ? 0.9 : 0.94); ticks.push([[cx + Math.cos(ta) * r * 0.87, cy + Math.sin(ta) * r * 0.87 * k], [cx + Math.cos(ta) * r1, cy + Math.sin(ta) * r1 * k]]); }
  for (var d = 0; d < n; d++) { var da = rot + (d + 0.5) / n * Math.PI * 2; dots.push(circle(cx + Math.cos(da) * r * 0.68, cy + Math.sin(da) * r * 0.68 * k, r * 0.035, k, 12)); }
  return { rings: rings, star: star, ticks: ticks, dots: dots };
}
// a shuriken: four blades round a hole (even-odd), turned
function shuriken(cx, cy, r, turn) {
  var v = [];
  for (var i = 0; i < 4; i++) {
    var a = turn + i * Math.PI / 2;
    v.push([cx + Math.cos(a - 0.62) * r * 0.32, cy + Math.sin(a - 0.62) * r * 0.32], [cx + Math.cos(a) * r, cy + Math.sin(a) * r], [cx + Math.cos(a + 0.35) * r * 0.36, cy + Math.sin(a + 0.35) * r * 0.36]);
  }
  return [v, circle(cx, cy, r * 0.12, 1, 12)];
}
function kunai(x, y, len, ang) {
  return place([[len, 0], [len * 0.55, -len * 0.13], [len * 0.42, -len * 0.05], [0, -len * 0.04], [0, len * 0.04], [len * 0.42, len * 0.05], [len * 0.55, len * 0.13]], x, y, ang);
}
// a puff of smoke: a cluster of round billows — [their light, their shadow]
function puff(cx, cy, r, n) {
  var light = [], shade = [];
  for (var i = 0; i < (n || 7); i++) {
    var a = between(0, Math.PI * 2), d = r * between(0, 0.55), rr = r * between(0.35, 0.6), x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d * 0.8;
    shade.push(circle(x + rr * 0.12, y + rr * 0.18, rr, 1, 20)); light.push(circle(x - rr * 0.08, y - rr * 0.1, rr * 0.86, 1, 20));
  }
  return [light, shade];
}
function rockPoly(x, y, size, turn) {
  var v = [];
  for (var i = 0; i < 7; i++) { var a = i / 7 * Math.PI * 2 + between(-0.3, 0.3); v.push([Math.cos(a) * size * between(0.65, 1.1), Math.sin(a) * size * between(0.6, 1)]); }
  return { body: place(v, x, y, turn), lit: place([v[4], v[5], v[6], [0, -size * 0.1]], x, y, turn) };
}
// a feather blade of an energy wing: long, pointed, from (x, y) along ang
function blade(x, y, len, wid, ang) {
  return place([[0, -wid * 0.5], [len * 0.7, -wid * 0.42], [len, 0], [len * 0.7, wid * 0.18], [0, wid * 0.5]], x, y, ang);
}
// a capsule missile along ang, and its exhaust flame
function missile(x, y, len, ang) {
  return { body: place([[len, 0], [len * 0.8, -len * 0.11], [0, -len * 0.11], [-len * 0.12, -len * 0.2], [-len * 0.12, len * 0.2], [0, len * 0.11], [len * 0.8, len * 0.11]], x, y, ang),
           flame: place([[-len * 0.1, -len * 0.08], [-len * 0.6, 0], [-len * 0.1, len * 0.08]], x, y, ang) };
}
// a helix round a card: points {x, y, d, u} from its tail (u 0) to its head (u 1) — d > 0: on the near side (over
// the card); R its radius, H its height, `turns` turns, starting at angle spin, tilted
function helix(cx, cy, R, H, turns, spin, tilt, n) {
  var pts = [], m = n || 80;
  for (var i = 0; i <= m; i++) { var u = i / m, th = spin + u * turns * Math.PI * 2; pts.push({ x: cx + R * Math.cos(th), y: cy + (0.5 - u) * H + tilt * R * Math.sin(th), d: Math.sin(th), u: u }); }
  return pts;
}
// a band along a helix's points, its width w(u), split into runs on the near or the far side — polygons
function band(pts, width, front) {
  var runs = [], run = [], out = [];
  for (var j = 0; j < pts.length; j++) { if ((pts[j].d > 0) === front) run.push(j); else if (run.length) { runs.push(run); run = []; } }
  if (run.length) runs.push(run);
  for (var r = 0; r < runs.length; r++) {
    var idx = runs[r]; if (idx.length < 2) continue;
    var left = [], right = [];
    for (var q = 0; q < idx.length; q++) {
      var i = idx[q], a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)], tx = b.x - a.x, ty = b.y - a.y, l = Math.sqrt(tx * tx + ty * ty) || 1, w = width(pts[i].u) / 2;
      left.push([pts[i].x - ty / l * w, pts[i].y + tx / l * w]); right.push([pts[i].x + ty / l * w, pts[i].y - tx / l * w]);
    }
    out.push(left.concat(right.reverse()));
  }
  return out;
}

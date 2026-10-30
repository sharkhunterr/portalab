// Sumi — helpers to draw ink and gold in EffectCraft: the palette, a seeded random, layers shown for a few frames,
// and brushed, splashed, flaked and cracked shapes. Coordinates are the comp's own pixels, y downwards.
var INK = [0.055, 0.04, 0.035], GOLD = [0.86, 0.64, 0.2], GOLD_L = [1, 0.87, 0.5], GOLD_D = [0.52, 0.33, 0.07];
var WHITE = [0.98, 0.95, 0.88], SHU = [0.86, 0.19, 0.11], SHU_D = [0.5, 0.07, 0.04];
var SAKURA = [0.99, 0.75, 0.81], SAKURA_D = [0.9, 0.45, 0.58], AI = [0.15, 0.29, 0.56], AI_L = [0.62, 0.77, 0.95];
var F = 1 / 24;   // every time is counted in frames, 24 a second

var _seed = 1;
function seed(s) { _seed = Math.floor(s) % 2147483646 + 1; }
function rnd() { _seed = (_seed * 16807) % 2147483647; return (_seed - 1) / 2147483646; }
function between(a, b) { return a + (b - a) * rnd(); }
function clamp01(x) { return Math.max(0, Math.min(1, x)); }
function ease(x) { x = clamp01(x); return 1 - Math.pow(1 - x, 3); }

function shapeLayer(comp, name) { var L = comp.layers.addShape(); L.name = name; return L; }
function contents(L) { return L.property("ADBE Root Vectors Group"); }
function tr(L, name) { return L.property("ADBE Transform Group").property(name); }
function group(L, name) { var g = contents(L).addProperty("ADBE Vector Group"); g.name = name; return g; }
function pathInto(g, verts, closed) {
  var p = g.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Group");
  var s = new Shape(); s.vertices = verts; s.closed = closed; p.property("ADBE Vector Shape").setValue(s);
}
function strokeInto(g, color, width, opacity) {
  var st = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Stroke");
  st.property("ADBE Vector Stroke Color").setValue(color);
  st.property("ADBE Vector Stroke Width").setValue(width);
  st.property("ADBE Vector Stroke Line Join").setValue(2);
  st.property("ADBE Vector Stroke Line Cap").setValue(2);
  if (opacity !== undefined) st.property("ADBE Vector Stroke Opacity").setValue(opacity);
}
// one group: several closed paths sharing one fill (its opacity in %) — groups added later go below
function polys(L, list, color, opacity) {
  if (!list.length) return null;
  var g = group(L, "polys");
  for (var i = 0; i < list.length; i++) pathInto(g, list[i], true);
  var fl = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
  fl.property("ADBE Vector Fill Color").setValue(color);
  if (opacity !== undefined) fl.property("ADBE Vector Fill Opacity").setValue(opacity);
  return g;
}
// open paths sharing strokes, the first listed on top
function lines(L, list, strokes) {
  if (!list.length) return;
  var g = group(L, "lines");
  for (var i = 0; i < list.length; i++) pathInto(g, list[i], false);
  for (var k = 0; k < strokes.length; k++) strokeInto(g, strokes[k][0], strokes[k][1], strokes[k][2]);
}
function shifted(list, dx, dy) {
  var out = [];
  for (var i = 0; i < list.length; i++) { var p = []; for (var j = 0; j < list[i].length; j++) p.push([list[i][j][0] + dx, list[i][j][1] + dy]); out.push(p); }
  return out;
}
// ink with a gilded edge: the shapes in ink, the same shapes in gold a little lower right, under them
function gilded(L, list, color, edge, dx, dy) {
  polys(L, list, color || INK);
  polys(L, shifted(list, dx === undefined ? 5 : dx, dy === undefined ? 7 : dy), edge || GOLD);
}
// a layer shown from frame a to frame b (exclusive), at an opacity (%)
function frames(comp, name, a, b, opacity) {
  var L = shapeLayer(comp, name);
  tr(L, "ADBE Position").setValue([0, 0]);
  var op = tr(L, "ADBE Opacity"), on = opacity === undefined ? 100 : opacity;
  if (a > 0) { op.setValueAtTime(0, 0); op.setValueAtTime(a * F, on); } else { op.setValueAtTime(0, on); }
  op.setValueAtTime(b * F, 0);
  for (var i = 1; i <= op.numKeys; i++) op.setInterpolationTypeAtKey(i, KeyframeInterpolationType.HOLD);
  return L;
}
function circle(cx, cy, r, k, n) {
  var v = [], m = n || 48;
  for (var q = 0; q < m; q++) v.push([cx + Math.cos(q / m * Math.PI * 2) * r, cy + Math.sin(q / m * Math.PI * 2) * r * (k || 1)]);
  return v;
}
// distance from the middle to a rectangle's edge (half sizes hw, hh) along angle a
function toEdge(a, hw, hh) {
  var c = Math.abs(Math.cos(a)), s = Math.abs(Math.sin(a));
  return Math.min(c > 1e-4 ? hw / c : 1e9, s > 1e-4 ? hh / s : 1e9);
}
function rotated(list, cx, cy, ang, sx, sy) {
  var c = Math.cos(ang), s = Math.sin(ang), out = [];
  for (var i = 0; i < list.length; i++) { var x = list[i][0] * (sx || 1), y = list[i][1] * (sy || 1); out.push([cx + x * c - y * s, cy + x * s + y * c]); }
  return out;
}

// --- a brush stroke ------------------------------------------------------------------------------------
// along a centre line (points), W wide: a heavy, rounded press where the brush lands, its weight swelling and
// easing as it moves, thinning to a point; drawn as bristles side by side, each wavering a little — solid where
// the brush is loaded, the outer ones running dry first, breaking into streaks (kasure) towards its end. Drawn up
// to `upto` (0..1) of its length, the brush still moving; `erode` (0..1) dries it away. Returns the outlines.
function resample(pts, m) {
  var len = [0];
  for (var i = 1; i < pts.length; i++) { var dx = pts[i][0] - pts[i - 1][0], dy = pts[i][1] - pts[i - 1][1]; len.push(len[i - 1] + Math.sqrt(dx * dx + dy * dy)); }
  var out = [], total = len[len.length - 1] || 1, j = 1;
  for (var k = 0; k <= m; k++) {
    var at = total * k / m;
    while (j < pts.length - 1 && len[j] < at) j++;
    var t = (at - len[j - 1]) / ((len[j] - len[j - 1]) || 1);
    out.push([pts[j - 1][0] + (pts[j][0] - pts[j - 1][0]) * t, pts[j - 1][1] + (pts[j][1] - pts[j - 1][1]) * t]);
  }
  return out;
}
function brushPolys(pts, W, upto, dry, bristles, erode) {
  var line = resample(pts, 140), n = line.length, B = bristles || 9, out = [], end = upto === undefined ? 1 : upto;
  var d = dry === undefined ? 0.55 : dry, e = erode || 0, nx = [], ny = [], press = [];
  var ph = between(0, 6), ph2 = between(0, 6);
  for (var i = 0; i < n; i++) {
    var a = line[Math.max(0, i - 1)], b = line[Math.min(n - 1, i + 1)], tx = b[0] - a[0], ty = b[1] - a[1], l = Math.sqrt(tx * tx + ty * ty) || 1;
    nx.push(-ty / l); ny.push(tx / l);
    var u = i / (n - 1);
    // landing: a round, heavy press; then the weight swelling and easing; then thinning to the tip
    var land = Math.sqrt(Math.min(1, u / 0.03)) * (1 + 0.38 * Math.exp(-u * 22));
    press.push(W * 0.5 * land * (1 + 0.13 * Math.sin(u * 7.5 + ph) + 0.06 * Math.sin(u * 19 + ph2)) * Math.pow(1 - u, 0.42));
  }
  for (var k = 0; k < B; k++) {
    var o = (k + 0.5) / B * 2 - 1, h = 1.55 / B * between(0.7, 1.2), outer = Math.abs(o);
    var stop = d + (1 - d) * (1 - Math.pow(outer, 1.2) * between(0.35, 1)) * between(0.7, 1), start = between(0, 0.02) * outer;
    var wph = between(0, 6), wamp = between(0.02, 0.06), gone = rnd() < e * (0.6 + outer);
    if (gone) continue;
    h *= 1 - 0.55 * e; stop = d + (stop - d) * (1 - e * 0.7);
    var pieces = [[start, stop]];
    for (var g = 0; g < 2; g++) {   // a dry bristle skips over the paper here and there
      if (rnd() < 0.55) { var at = d + (stop - d) * rnd(), gap = between(0.02, 0.07), last = pieces.pop(); if (at > last[0] && at + gap < last[1]) { pieces.push([last[0], at], [at + gap, last[1]]); } else pieces.push(last); }
    }
    for (var p = 0; p < pieces.length; p++) {
      var u0 = pieces[p][0], u1 = Math.min(pieces[p][1], end);
      if (u1 - u0 < 0.015) continue;
      var left = [], right = [];
      for (var j = 0; j < n; j++) {
        var uu = j / (n - 1);
        if (uu < u0 || uu > u1) continue;
        var c = o + wamp * Math.sin(uu * 13 + wph), w = press[j];
        left.push([line[j][0] + nx[j] * (c + h) * w, line[j][1] + ny[j] * (c + h) * w]);
        right.push([line[j][0] + nx[j] * (c - h) * w, line[j][1] + ny[j] * (c - h) * w]);
      }
      if (left.length > 1) out.push(left.concat(right.reverse()));
    }
  }
  return out;
}
// a centre line: a gentle arc from (x0, y0) to (x1, y1), bowed by `bow` pixels
function arcLine(x0, y0, x1, y1, bow, n) {
  var pts = [], m = n || 40, dx = x1 - x0, dy = y1 - y0, l = Math.sqrt(dx * dx + dy * dy) || 1;
  for (var i = 0; i <= m; i++) { var u = i / m, s = Math.sin(Math.PI * u) * bow; pts.push([x0 + dx * u - dy / l * s, y0 + dy * u + dx / l * s]); }
  return pts;
}
// the ensō: a circle drawn in one breath, from angle a0 round most of the way
function ensoLine(cx, cy, r, k, a0, sweep, n) {
  var pts = [], m = n || 72;
  for (var i = 0; i <= m; i++) {
    var u = i / m, a = a0 + u * sweep, rr = r * (1 + 0.035 * Math.sin(u * 7.0 + a0) - 0.05 * u);
    pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr * k]);
  }
  return pts;
}

// --- splashes, droplets, flakes, petals, cracks -------------------------------------------------------
// ink flung out: heavy brush strokes radiating from a centre — from its rectangle's edge (half sizes hw, hh) —
// thrown in a few frames, a drop beyond each, then drying away; `age` in frames, the same strokes every frame
function inkBurst(cx, cy, n, hw, hh, reach, width, ky, age, base) {
  seed(base);
  var strokes = [];
  for (var i = 0; i < n; i++) {
    var a = (i + between(-0.35, 0.35)) / n * Math.PI * 2, r0 = (hw ? toEdge(a, hw, hh) * 0.92 : 0) + between(30, 70), len = reach * between(0.45, 1);
    var x0 = cx + Math.cos(a) * r0, y0 = cy + Math.sin(a) * r0 * ky, x1 = cx + Math.cos(a) * (r0 + len), y1 = cy + Math.sin(a) * (r0 + len) * ky;
    strokes.push({ line: arcLine(x0, y0, x1, y1, between(-0.12, 0.12) * len, 30), w: width * between(0.55, 1.1), drop: [cx + Math.cos(a) * (r0 + len + between(25, 70)), cy + Math.sin(a) * (r0 + len + between(25, 70)) * ky, between(6, 15)] });
  }
  seed(base + 1000 + Math.floor(age / 2));
  var out = [], p = ease((age + 1) / 4), dry = age < 7 ? 0 : (age - 6) / 14;
  for (var k = 0; k < strokes.length; k++) {
    out = out.concat(brushPolys(strokes[k].line, strokes[k].w, p, 0.4, 8, dry));
    if (p > 0.8 && dry < 0.85) { var d = strokes[k].drop; out.push(circle(d[0], d[1], d[2] * (1 - dry), 1, 14)); }
  }
  return out;
}
// gold leaf flakes: torn little sheets turning over as they fly — each [x, y, size, turn, flip]
function flakes(L, list) {
  var leaf = [], shine = [];
  for (var i = 0; i < list.length; i++) {
    var f = list[i], v = [], n = 5, sx = Math.max(0.12, Math.abs(Math.cos(f[4])));
    for (var j = 0; j < n; j++) { var a = j / n * Math.PI * 2 + f[0] * 0.01, r = f[2] * (0.6 + 0.4 * Math.abs(Math.sin(f[1] * 0.07 + j * 1.9))); v.push([Math.cos(a) * r, Math.sin(a) * r]); }
    leaf.push(rotated(v, f[0], f[1], f[3], sx, 1));
    var hv = []; for (var q = 0; q < v.length; q++) hv.push([v[q][0] * 0.5 - f[2] * 0.15, v[q][1] * 0.5 - f[2] * 0.15]);
    shine.push(rotated(hv, f[0], f[1], f[3], sx, 1));
  }
  polys(L, shine, GOLD_L); polys(L, leaf, GOLD);
}
// a cherry petal: wide towards its notched tip — length l, width w, at (x, y), turned, flipped
function petal(x, y, l, w, turn, flip) {
  var v = [], n = 10;
  for (var i = 0; i <= n; i++) { var t = i / n; v.push([l * 0.9 * t, -w * 0.5 * Math.pow(Math.sin(Math.PI * (0.08 + t * 0.7)), 0.8)]); }
  v.push([l * 0.97, -w * 0.28], [l * 0.82, 0], [l * 0.97, w * 0.28]);
  for (var j = n; j >= 0; j--) { var s = j / n; v.push([l * 0.9 * s, w * 0.5 * Math.pow(Math.sin(Math.PI * (0.08 + s * 0.7)), 0.8)]); }
  return rotated(v, x, y, turn, 1, Math.max(0.15, Math.abs(Math.cos(flip))));
}
function petals(L, list) {   // each [x, y, size, turn, flip]
  var body = [], heart = [];
  for (var i = 0; i < list.length; i++) {
    var p = list[i];
    body.push(petal(p[0], p[1], p[2], p[2] * 0.72, p[3], p[4]));
    heart.push(petal(p[0], p[1], p[2] * 0.42, p[2] * 0.3, p[3], p[4]));
  }
  polys(L, heart, SAKURA_D); polys(L, body, SAKURA);
}
// a whole blossom: five petals round a golden heart
function blossom(L, x, y, r, turn, fill) {
  var list = [];
  for (var k = 0; k < 5; k++) list.push(petal(x, y, r, r * 0.8, turn + k * Math.PI * 2 / 5, 0));
  polys(L, [circle(x, y, r * 0.18, 1, 16)], GOLD_L);
  polys(L, list, fill || SAKURA);
}
// gold cracks (kintsugi): a branching jagged walk from (x, y) heading `a`, `len` pixels long — a list of polylines
function crackLines(x, y, a, len, branchy) {
  var out = [], todo = [[x, y, a, len]];
  while (todo.length && out.length < 14) {
    var c = todo.shift(), pts = [[c[0], c[1]]], px = c[0], py = c[1], ang = c[2], left = c[3];
    while (left > 0) {
      var step = between(9, 22); ang += between(-0.55, 0.55);
      px += Math.cos(ang) * step; py += Math.sin(ang) * step; left -= step; pts.push([px, py]);
      if (rnd() < (branchy || 0.08) && left > 40) todo.push([px, py, ang + (rnd() < 0.5 ? -1 : 1) * between(0.5, 1.1), left * between(0.3, 0.6)]);
    }
    out.push(pts);
  }
  return out;
}
// the first part (0..1) of each polyline
function partOf(list, p) {
  var out = [];
  for (var i = 0; i < list.length; i++) { var n = Math.max(2, Math.round(list[i].length * clamp01(p))); if (p > 0) out.push(list[i].slice(0, n)); }
  return out;
}
function gold(L, list, w) { lines(L, list, [[GOLD_L, w * 0.35], [GOLD, w * 0.7], [GOLD_D, w]]); }
// four-pointed glints, each [x, y, r]
function glints(L, list, color) {
  var all = [];
  for (var j = 0; j < list.length; j++) {
    var cx = list[j][0], cy = list[j][1], r = list[j][2], v = [], n = 40;
    for (var i = 0; i < n; i++) {
      var a = i / n * Math.PI * 2, c = Math.cos(a), s = Math.sin(a), k = Math.pow(Math.pow(Math.abs(c), 0.5) + Math.pow(Math.abs(s), 0.5), -2);
      v.push([cx + c * r * k, cy + s * r * k]);
    }
    all.push(v);
  }
  polys(L, all, color || GOLD_L);
}

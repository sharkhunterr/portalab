// Géode — helpers to draw stone, crystal and light in EffectCraft: gem palettes, a seeded random, layers shown
// for a few frames (only those of the slice being built: FROM..TO, so a comp is built in slices side by side),
// faceted crystals, shards, rock shell fragments, glowing cracks, rays, rings and glints. Light is drawn twice:
// sharp, then blurred and added (a glow). Coordinates are the comp's own pixels, y downwards; times in frames.
var F = 1 / 24;
if (typeof FROM === "undefined") var FROM = 0;
if (typeof TO === "undefined") var TO = 100000;
// each gem: its three faces (shadow, body, light), its edge's shine and its glow
var GEMS = {
  amethyst: { faces: [[0.27, 0.08, 0.47], [0.52, 0.22, 0.82], [0.78, 0.58, 1.0]], shine: [0.97, 0.9, 1.0], glow: [0.68, 0.42, 1.0] },
  quartz: { faces: [[0.05, 0.2, 0.48], [0.22, 0.52, 0.93], [0.62, 0.86, 1.0]], shine: [0.92, 0.98, 1.0], glow: [0.4, 0.7, 1.0] },
  citrine: { faces: [[0.52, 0.27, 0.02], [0.93, 0.64, 0.13], [1.0, 0.88, 0.48]], shine: [1.0, 0.98, 0.85], glow: [1.0, 0.75, 0.3] },
  emerald: { faces: [[0.02, 0.32, 0.2], [0.08, 0.66, 0.42], [0.55, 0.98, 0.78]], shine: [0.9, 1.0, 0.95], glow: [0.3, 0.95, 0.65] },
  rose: { faces: [[0.5, 0.08, 0.27], [0.92, 0.4, 0.62], [1.0, 0.78, 0.88]], shine: [1.0, 0.95, 0.97], glow: [1.0, 0.5, 0.75] },
  clear: { faces: [[0.55, 0.6, 0.72], [0.82, 0.86, 0.95], [0.97, 0.98, 1.0]], shine: [1, 1, 1], glow: [0.85, 0.9, 1.0] }
};
var ROCK = [[0.13, 0.1, 0.12], [0.27, 0.22, 0.24], [0.44, 0.38, 0.38]], WHITE = [1, 1, 1], LIGHT = [0.86, 0.74, 1.0];

var _seed = 1;
function seed(s) { _seed = Math.floor(s) % 2147483646 + 1; }
function rnd() { _seed = (_seed * 16807) % 2147483647; return (_seed - 1) / 2147483646; }
function between(a, b) { return a + (b - a) * rnd(); }
function clamp01(x) { return Math.max(0, Math.min(1, x)); }
function ease(x) { x = clamp01(x); return 1 - Math.pow(1 - x, 3); }
function back(x) { x = clamp01(x); var c = 1.70158; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); }  // a little past, then back

function tr(L, name) { return L.property("ADBE Transform Group").property(name); }
function group(L, name) { if (!L) return null; var g = L.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group"); g.name = name; return g; }
function pathInto(g, verts, closed) {
  var p = g.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Group");
  var s = new Shape(); s.vertices = verts; s.closed = closed; p.property("ADBE Vector Shape").setValue(s);
}
// closed paths sharing one fill — groups added later go below; nothing on a layer outside the slice
function polys(L, list, color, opacity) {
  if (!L || !list.length) return;
  var g = group(L, "polys");
  for (var i = 0; i < list.length; i++) pathInto(g, list[i], true);
  var fl = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
  fl.property("ADBE Vector Fill Color").setValue(color);
  if (opacity !== undefined) fl.property("ADBE Vector Fill Opacity").setValue(opacity);
}
function lines(L, list, color, width, closed) {
  if (!L || !list.length) return;
  var g = group(L, "lines");
  for (var i = 0; i < list.length; i++) pathInto(g, list[i], !!closed);
  var st = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Stroke");
  st.property("ADBE Vector Stroke Color").setValue(color);
  st.property("ADBE Vector Stroke Width").setValue(width);
  st.property("ADBE Vector Stroke Line Join").setValue(2);
  st.property("ADBE Vector Stroke Line Cap").setValue(2);
}
// a layer shown from frame a to frame b (exclusive) — none at all outside the slice being built; a glow: blurred
// by `blur` pixels and added to what is under it
function frames(comp, name, a, b, opacity, blur) {
  if (b <= FROM || a >= TO) return null;
  var L = comp.layers.addShape(); L.name = name;
  tr(L, "ADBE Position").setValue([0, 0]);
  var op = tr(L, "ADBE Opacity"), on = opacity === undefined ? 100 : opacity;
  if (a > 0) { op.setValueAtTime(0, 0); op.setValueAtTime(a * F, on); } else { op.setValueAtTime(0, on); }
  op.setValueAtTime(b * F, 0);
  for (var i = 1; i <= op.numKeys; i++) op.setInterpolationTypeAtKey(i, KeyframeInterpolationType.HOLD);
  if (blur) {
    L.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2").property("ADBE Gaussian Blur 2-0001").setValue(blur);
    L.blendingMode = BlendingMode.ADD;
  }
  return L;
}
function circle(cx, cy, r, k, n) {
  var v = [], m = n || 48;
  for (var q = 0; q < m; q++) v.push([cx + Math.cos(q / m * Math.PI * 2) * r, cy + Math.sin(q / m * Math.PI * 2) * r * (k || 1)]);
  return v;
}
function ring(cx, cy, r, k) { var v = circle(cx, cy, r, k, 72); v.push(v[0]); return v; }
function toEdge(a, hw, hh) {
  var c = Math.abs(Math.cos(a)), s = Math.abs(Math.sin(a));
  return Math.min(c > 1e-4 ? hw / c : 1e9, s > 1e-4 ? hh / s : 1e9);
}
function place(list, x, y, ang, sx, sy) {
  var c = Math.cos(ang), s = Math.sin(ang), out = [];
  for (var i = 0; i < list.length; i++) { var px = list[i][0] * (sx || 1), py = list[i][1] * (sy || 1); out.push([x + px * c - py * s, y + px * s + py * c]); }
  return out;
}

// --- crystals ------------------------------------------------------------------------------------------
// a crystal: a hexagonal column ending in a point, seen from its side — three faces (shadow, body, light) meeting
// at its tip, a bright edge down its lit side. From its base (x, y) along `ang`, `len` long, `wid` wide.
// Collected per gem and face, drawn together (one group per colour): crystals(L, list) with each
// {x, y, ang, len, wid, gem}
function crystalFaces(c) {
  var L = c.len, W = c.wid, body = L * 0.7, mid = body + (L - body) * 0.45;
  var faces = [
    [[0, -W / 2], [body, -W / 2], [L, 0], [mid, -W / 6], [0, -W / 6]],
    [[0, -W / 6], [mid, -W / 6], [L, 0], [mid, W / 6], [0, W / 6]],
    [[0, W / 6], [mid, W / 6], [L, 0], [body, W / 2], [0, W / 2]]
  ];
  var out = [];
  for (var i = 0; i < 3; i++) out.push(place(faces[i], c.x, c.y, c.ang));
  out.push(place([[W * 0.1, W / 6], [mid, W / 6], [L, 0]], c.x, c.y, c.ang));  // the edge catching the light
  return out;
}
function crystals(L, list) {
  if (!L || !list.length) return;
  var byGem = {}, order = [];
  for (var i = 0; i < list.length; i++) {
    var c = list[i]; if (c.len < 2) continue;
    if (!byGem[c.gem]) { byGem[c.gem] = [[], [], [], []]; order.push(c.gem); }
    var f = crystalFaces(c);
    for (var k = 0; k < 4; k++) byGem[c.gem][k].push(f[k]);
  }
  for (var g = 0; g < order.length; g++) {
    var gem = GEMS[order[g]], set = byGem[order[g]];
    lines(L, set[3], gem.shine, 2.2);
    polys(L, set[2], gem.faces[2]); polys(L, set[1], gem.faces[1]); polys(L, set[0], gem.faces[0]);
  }
}
// their glow: the same crystals as plain light, for a blurred, added layer
function crystalGlow(L, list, opacity) {
  if (!L || !list.length) return;
  var byGem = {}, order = [];
  for (var i = 0; i < list.length; i++) {
    var c = list[i]; if (c.len < 2) continue;
    if (!byGem[c.gem]) { byGem[c.gem] = []; order.push(c.gem); }
    var f = crystalFaces(c); byGem[c.gem].push(f[0], f[1], f[2]);
  }
  for (var g = 0; g < order.length; g++) polys(L, byGem[order[g]], GEMS[order[g]].glow, opacity);
}
// shards: little faceted splinters turning as they fly — each {x, y, size, turn, gem}; two faces, light and dark
function shards(L, list) {
  if (!L || !list.length) return;
  var byGem = {}, order = [];
  for (var i = 0; i < list.length; i++) {
    var s = list[i]; if (s.size < 1) continue;
    if (!byGem[s.gem]) { byGem[s.gem] = [[], []]; order.push(s.gem); }
    var k = s.size, a = [[-k, -k * 0.35], [k * 1.2, 0], [-k * 0.3, k * 0.5]];
    byGem[s.gem][0].push(place([a[0], a[1], [0, 0]], s.x, s.y, s.turn, 1, Math.max(0.2, Math.abs(Math.cos(s.turn * 1.7)))));
    byGem[s.gem][1].push(place([[0, 0], a[1], a[2]], s.x, s.y, s.turn, 1, Math.max(0.2, Math.abs(Math.cos(s.turn * 1.7)))));
  }
  for (var g = 0; g < order.length; g++) { polys(L, byGem[order[g]][0], GEMS[order[g]].faces[2]); polys(L, byGem[order[g]][1], GEMS[order[g]].faces[0]); }
}
// a crown of crystals growing out of a centre (or a rectangle's edge, half sizes hw, hh): `n` of them, every
// way or within a fan, each starting when its turn comes — `age` in frames; their shapes the same every frame
function crown(n, cx, cy, hw, hh, reach, width, gems, age, base, opts) {
  seed(base);
  var o = opts || {}, out = [];
  for (var i = 0; i < n; i++) {
    var a = o.fan ? o.fan[0] + (o.fan[1] - o.fan[0]) * (i + between(0.2, 0.8)) / n : (i + between(-0.3, 0.3)) / n * Math.PI * 2;
    var r0 = (hw ? toEdge(a, hw, hh) : 0) * between(0.7, 0.95) + (o.inset || 0), start = (o.stagger || 0) * rnd() + (o.order ? i * o.order : 0);
    var len = reach * between(0.45, 1), wid = width * between(0.6, 1.15), gem = gems[Math.floor(rnd() * gems.length)];
    var grow = o.shrink !== undefined && age > o.shrink ? Math.max(0, 1 - (age - o.shrink) / 12) : back((age - start) / (o.speed || 7));
    if (age < start) grow = 0;
    var main = { x: cx + Math.cos(a) * r0, y: cy + Math.sin(a) * r0, ang: a + between(-0.12, 0.12), len: len * grow, wid: wid * Math.min(1, grow * 1.6), gem: gem, a: a, r0: r0, full: len, w: wid };
    // a druse: smaller crystals growing at its foot, leaning away from it (drawn under it)
    for (var m = 0; m < (o.cluster === undefined ? 2 : o.cluster); m++) {
      var side = m % 2 ? 1 : -1, lean = side * between(0.18, 0.4), k = between(0.35, 0.65), shift = side * between(0.4, 0.9) * wid;
      out.push({ x: main.x - Math.sin(a) * shift, y: main.y + Math.cos(a) * shift, ang: main.ang + lean, len: main.len * k, wid: main.wid * between(0.5, 0.75), gem: rnd() < 0.7 ? gem : gems[Math.floor(rnd() * gems.length)], a: a + lean, r0: r0, full: len * k, w: wid * 0.6 });
    }
    out.push(main);
  }
  return out;
}
// the crystals shattering: each breaks into shards flying on from where it stood
function shatter(list, age, count, base) {
  seed(base);
  var out = [];
  for (var i = 0; i < list.length; i++) {
    var c = list[i];
    for (var k = 0; k < count; k++) {
      var along = between(0.1, 1) * c.full, spread = between(-0.6, 0.6), speed = between(6, 16), d = along + speed * age;
      out.push({ x: c.x + Math.cos(c.a + spread * 0.3) * d, y: c.y + Math.sin(c.a + spread * 0.3) * d + age * age * 0.25, size: between(9, 22) * c.w / 40 * (1 - age / 28), turn: between(0, 6) + age * between(-0.4, 0.4), gem: c.gem });
    }
  }
  return out;
}

// --- light ---------------------------------------------------------------------------------------------
// glowing cracks: a branching jagged walk from (x, y), a list of polylines (drawn up to a part, 0..1)
function crackLines(x, y, a, len, branchy) {
  var out = [], todo = [[x, y, a, len]];
  while (todo.length && out.length < 12) {
    var c = todo.shift(), pts = [[c[0], c[1]]], px = c[0], py = c[1], ang = c[2], left = c[3];
    while (left > 0) {
      var step = between(7, 16); ang += between(-0.6, 0.6);
      px += Math.cos(ang) * step; py += Math.sin(ang) * step; left -= step; pts.push([px, py]);
      if (rnd() < (branchy || 0.1) && left > 25) todo.push([px, py, ang + (rnd() < 0.5 ? -1 : 1) * between(0.5, 1.1), left * between(0.3, 0.6)]);
    }
    out.push(pts);
  }
  return out;
}
function partOf(list, p) {
  var out = [];
  if (p <= 0) return out;
  for (var i = 0; i < list.length; i++) out.push(list[i].slice(0, Math.max(2, Math.round(list[i].length * clamp01(p)))));
  return out;
}
// rays from a centre (or a rectangle's edge), turning slowly: wedges of light
function rays(n, cx, cy, hw, hh, reach, width, turn, base) {
  seed(base);
  var out = [];
  for (var i = 0; i < n; i++) {
    var a = (i + between(-0.3, 0.3)) / n * Math.PI * 2 + turn, w = width * between(0.5, 1.2), r0 = hw ? toEdge(a, hw, hh) * 0.9 : 0, tip = r0 + reach * between(0.5, 1);
    out.push([[cx + Math.cos(a - w) * r0, cy + Math.sin(a - w) * r0], [cx + Math.cos(a) * tip, cy + Math.sin(a) * tip], [cx + Math.cos(a + w) * r0, cy + Math.sin(a + w) * r0]]);
  }
  return out;
}
// four-pointed glints, each [x, y, r]
function glints(L, list, color) {
  if (!L) return;
  var all = [];
  for (var j = 0; j < list.length; j++) {
    var cx = list[j][0], cy = list[j][1], r = list[j][2], v = [], n = 40;
    if (r < 0.5) continue;
    for (var i = 0; i < n; i++) {
      var a = i / n * Math.PI * 2, c = Math.cos(a), s = Math.sin(a), k = Math.pow(Math.pow(Math.abs(c), 0.5) + Math.pow(Math.abs(s), 0.5), -2);
      v.push([cx + c * r * k, cy + s * r * k]);
    }
    all.push(v);
  }
  polys(L, all, color || WHITE);
}
// rock: the geode's shell in pieces — each piece its outer stone and, along one edge, its crust of crystal
function rockPiece(x, y, size, turn) {
  var v = [], n = 6;
  for (var i = 0; i < n; i++) { var a = i / n * Math.PI * 2 + between(-0.3, 0.3); v.push([Math.cos(a) * size * between(0.6, 1.1), Math.sin(a) * size * between(0.6, 1.1)]); }
  return { stone: place(v, x, y, turn), top: place([v[0], v[1], v[2], [0, 0]], x, y, turn), crust: place([v[3], v[4], [v[4][0] * 0.6, v[4][1] * 0.6], [v[3][0] * 0.6, v[3][1] * 0.6]], x, y, turn) };
}

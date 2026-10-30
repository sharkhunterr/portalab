// Impact — the booster scene's animations, drawn as anime impact frames on twos (12 fps): every shape flat,
// inked, regenerated each frame or two. Builds four comps: opening, reveal-rare, reveal-epic, reveal-legendary.
var F = 1 / 12;

function group(L, name) { var g = contents(L).addProperty("ADBE Vector Group"); g.name = name; return g; }
function pathInto(g, verts, closed) {
  var p = g.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Group");
  var s = new Shape(); s.vertices = verts; s.closed = closed; p.property("ADBE Vector Shape").setValue(s);
}
function fillInto(g, color) { g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill").property("ADBE Vector Fill Color").setValue(color); }
function strokeInto(g, color, width, taper) {
  var st = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Stroke");
  st.property("ADBE Vector Stroke Color").setValue(color);
  st.property("ADBE Vector Stroke Width").setValue(width);
  st.property("ADBE Vector Stroke Line Join").setValue(2);
  st.property("ADBE Vector Stroke Line Cap").setValue(2);
  if (taper) {
    var tp = st.property("ADBE Vector Stroke Taper");
    tp.property("startWidth").setValue(taper[0]); tp.property("endWidth").setValue(taper[1]);
    tp.property("startLength").setValue(taper[2]); tp.property("endLength").setValue(taper[3]);
  }
}
// a flat shape inked (the ink drawn below the fill: only its outer half shows) — groups added later go below
function blob(L, verts, color, ink) {
  var g = group(L, "blob"); pathInto(g, verts, true); fillInto(g, color); if (ink) strokeInto(g, INK, ink); return g;
}
// one frame's layer: visible from frame a to frame b (exclusive), on twos
function frames(comp, name, a, b) {
  var L = shapeLayer(comp, name);
  tr(L, "ADBE Position").setValue([0, 0]);   // the paths are drawn in the comp's own coordinates
  var op = tr(L, "ADBE Opacity");
  if (a > 0) { op.setValueAtTime(0, 0); op.setValueAtTime(a * F, 100); } else { op.setValueAtTime(0, 100); }
  op.setValueAtTime(b * F, 0);
  for (var i = 1; i <= op.numKeys; i++) op.setInterpolationTypeAtKey(i, KeyframeInterpolationType.HOLD);
  return L;
}

// --- shapes -------------------------------------------------------------------------------------------
// one group: several paths sharing one fill (even-odd: a path inside another cuts a hole) and one ink line
function polys(L, list, color, ink, evenodd) {
  var g = group(L, "polys");
  for (var i = 0; i < list.length; i++) pathInto(g, list[i], true);
  var fl = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
  fl.property("ADBE Vector Fill Color").setValue(color);
  if (evenodd) fl.property("ADBE Vector Fill Rule").setValue(2);
  if (ink) strokeInto(g, INK, ink);
  return g;
}
// distance from the middle to a rectangle's edge (half sizes hw, hh) along angle a
function toEdge(a, hw, hh) {
  var c = Math.abs(Math.cos(a)), s = Math.abs(Math.sin(a));
  return Math.min(c > 1e-4 ? hw / c : 1e9, s > 1e-4 ? hh / s : 1e9);
}
// a ring of spikes shooting out of a rectangle: one polygon, its base along the rectangle's edge
function spikes(L, cx, cy, hw, hh, n, reach, width, color, ink, turn) {
  var v = [], hole = [];
  for (var i = 0; i < n; i++) {
    var a = (turn || 0) + (i + between(-0.25, 0.25)) / n * Math.PI * 2;
    var w = Math.PI / n * between(0.5, 0.9) * width / 80;
    var b1 = toEdge(a - w, hw, hh), b2 = toEdge(a + w, hw, hh), tip = toEdge(a, hw, hh) + reach * between(0.45, 1);
    var p1 = [cx + Math.cos(a - w) * b1, cy + Math.sin(a - w) * b1], p2 = [cx + Math.cos(a + w) * b2, cy + Math.sin(a + w) * b2];
    v.push(p1, [cx + Math.cos(a) * tip, cy + Math.sin(a) * tip], p2);
    hole.push(p1, p2);
  }
  // the middle cut out (even-odd): the pack or the card shows through, inked round
  return polys(L, [v, hole], color, ink, true);
}
// speed lines: needles outwards from radius r0 to r1 — one polygon, its inside cut out (even-odd)
function speedLines(L, cx, cy, n, r0, r1, width, color, oval) {
  var v = [], hole = [], k = oval || 1;
  for (var i = 0; i < n; i++) {
    var a = (i + between(-0.4, 0.4)) / n * Math.PI * 2, s = r0 * between(0.95, 1.15), e = rnd() < 0.4 ? s + 2 : s + (r1 - r0) * between(0.4, 1);
    var w = width / s / 2;
    var p1 = [cx + Math.cos(a - w) * s, cy + Math.sin(a - w) * s * k], p2 = [cx + Math.cos(a + w) * s, cy + Math.sin(a + w) * s * k];
    v.push(p1, [cx + Math.cos(a) * e, cy + Math.sin(a) * e * k], p2);
    hole.push(p1, p2);
  }
  return polys(L, [v, hole], color, 0, true);
}
// lightning round a rectangle: jagged strokes on its sides — white core, pink, ink, in one group
function zaps(L, cx, cy, hw, hh, count, out) {
  var g = group(L, "zaps");
  for (var k = 0; k < count; k++) {
    var side = Math.floor(rnd() * 4), n = 6, pts = [], start = between(0, 0.45), span = between(0.35, 0.6);
    for (var i = 0; i <= n; i++) {
      var t = start + span * i / n, off = out + (i % 2 ? between(10, 30) : between(-4, 8)), x, y;
      if (side === 0) { x = cx - hw + 2 * hw * t; y = cy - hh - off; }
      else if (side === 1) { x = cx + hw + off; y = cy - hh + 2 * hh * t; }
      else if (side === 2) { x = cx + hw - 2 * hw * t; y = cy + hh + off; }
      else { x = cx - hw - off; y = cy + hh - 2 * hh * t; }
      pts.push([x, y]);
    }
    pathInto(g, pts, false);
  }
  strokeInto(g, WHITE, 3.5); strokeInto(g, PINK, 11); strokeInto(g, INK, 19);
}
// a brush slash: fat early, tapering to a point, its trailing edge torn into teeth; a pink rim, inked
function slashVerts(cx, cy, len, thick, ang, bend) {
  var top = [], bot = [], n = 40;
  for (var i = 0; i <= n; i++) {
    var x = i / n, w = Math.pow(Math.sin(Math.PI * Math.pow(x, 0.55)), 0.7) * thick;
    var y = bend * (Math.sin(Math.PI * x) - 0.5) * thick * 0.9, px = (x - 0.5) * len;
    top.push([px, y - w * between(0.92, 1)]);
    bot.push([px, y + (x < 0.72 && i % 2 ? w * between(0.35, 1) : w)]);
  }
  var v = top.concat(bot.reverse()), out = [], c = Math.cos(ang), s = Math.sin(ang);
  for (var k = 0; k < v.length; k++) out.push([cx + v[k][0] * c - v[k][1] * s, cy + v[k][0] * s + v[k][1] * c]);
  return out;
}
function slash(L, cx, cy, len, thick, ang, bend) {
  var v = slashVerts(cx, cy, len, thick, ang, bend), rim = [];
  for (var i = 0; i < v.length; i++) rim.push([v[i][0] + 9, v[i][1] + 13]);
  polys(L, [v], WHITE, 9, false);
  polys(L, [rim], PINK, 0, false);
}
// four-pointed glints, inked, in one group
function glints(L, list, color) {
  var all = [];
  for (var j = 0; j < list.length; j++) {
    var cx = list[j][0], cy = list[j][1], r = list[j][2], v = [], n = 40;
    for (var i = 0; i < n; i++) {
      var a = i / n * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
      var k = Math.pow(Math.pow(Math.abs(c), 0.5) + Math.pow(Math.abs(s), 0.5), -2);
      v.push([cx + c * r * k, cy + s * r * k]);
    }
    all.push(v);
  }
  return polys(L, all, color, list.length ? Math.max(4, list[0][2] * 0.06) : 4, false);
}
// dots: round-capped dashes of zero length along paths — a ring, or rows
function dotted(L, paths, d, gap, color, closed) {
  var g = group(L, "dots");
  for (var i = 0; i < paths.length; i++) pathInto(g, paths[i], closed);
  var st = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Stroke");
  st.property("ADBE Vector Stroke Color").setValue(color);
  st.property("ADBE Vector Stroke Width").setValue(d);
  st.property("ADBE Vector Stroke Line Cap").setValue(2);
  var dashes = st.property("ADBE Vector Stroke Dashes");
  dashes.property("ADBE Vector Stroke Dash 1").setValue(0.1);
  dashes.property("ADBE Vector Stroke Gap 1").setValue(gap);
}
function circle(cx, cy, r, k) { var v = []; for (var q = 0; q < 64; q++) v.push([cx + Math.cos(q / 64 * Math.PI * 2) * r, cy + Math.sin(q / 64 * Math.PI * 2) * r * (k || 1)]); return v; }
// flames round a rectangle: tongues rising, longest on its top, three tones, inked
function flames(L, cx, cy, hw, hh, amp, phase) {
  var tones = [[GREEN_L, 0.3, 0], [GREEN, 0.62, 0], [GREEN_D, 1.0, 6]];
  for (var t = 0; t < tones.length; t++) {
    var v = [], n = 140, scale = tones[t][1];
    for (var i = 0; i < n; i++) {
      var u = i / n, per = 2 * (2 * hw + 2 * hh), s = u * per, x, y, nx, ny;
      if (s < 2 * hw) { x = cx - hw + s; y = cy - hh; nx = 0; ny = -1; }
      else if (s < 2 * hw + 2 * hh) { x = cx + hw; y = cy - hh + (s - 2 * hw); nx = 1; ny = 0; }
      else if (s < 4 * hw + 2 * hh) { x = cx + hw - (s - 2 * hw - 2 * hh); y = cy + hh; nx = 0; ny = 1; }
      else { x = cx - hw; y = cy + hh - (s - 4 * hw - 2 * hh); nx = -1; ny = 0; }
      var tongue = Math.pow(Math.max(0, Math.sin(u * 58 + phase) * 0.6 + Math.sin(u * 23 - phase * 1.7) * 0.4), 3.0);
      var rise = ny < 0 ? 1.5 : ny > 0 ? 0.5 : 1.0;
      var off = (6 + amp * tongue * rise) * scale;
      v.push([x + nx * off, y + ny * off - (ny === 0 ? amp * tongue * 0.35 * scale : 0)]);
    }
    polys(L, [v], tones[t][0], tones[t][2], false);
  }
}

// --- the comps ----------------------------------------------------------------------------------------
// the opening: 768 x 720, the pack at (384, 337), 240 x 355 — 32 frames (2.6 s), the last one empty
if (ONLY === "opening") (function () {
  var comp = app.project.items.addComp("opening", 768, 720, 1, 32 * F, 12);
  var cx = 384, cy = 337, hw = 120, hh = 177;
  for (var f = 0; f < 23; f++) {
    seed(100 + f);
    var grow = Math.min(1, (f + 2) / 12), L = frames(comp, "rays-" + f, f, f + 1);
    speedLines(L, cx, cy, 70, 300 + f * 6, 520 + f * 8, 7, WHITE);
    spikes(L, cx, cy, hw, hh, 16, 220 * grow, 70, WHITE, 6, 0.1);
    spikes(L, cx, cy, hw, hh, 22, 330 * grow, 90, PINK, 8, 0);
  }
  for (var z = 1; z < 23; z++) { seed(300 + z); var Z = frames(comp, "zap-" + z, z, z + 1); var k = 1 + 0.2 * Math.min(1, z / 20); zaps(Z, cx, cy, hw * k, hh * k, 7, 14); }
  // two slashes crossing the box at frames 14 and 16, drawn in two frames, held, then gone
  seed(500);
  var s1 = [[14, 0.35], [15, 0.85], [16, 1.0], [17, 1.0]], s2 = [[16, 0.4], [17, 0.9], [18, 1.0], [19, 1.0]];
  for (var i = 0; i < s1.length; i++) { var A = frames(comp, "slashA-" + i, s1[i][0], s1[i][0] + 1); slash(A, cx - 380 * (1 - s1[i][1]) / 2, cy + 20, 760 * s1[i][1], 95, -0.32, 1); }
  for (var j = 0; j < s2.length; j++) { var B = frames(comp, "slashB-" + j, s2[j][0], s2[j][0] + 1); slash(B, cx + 380 * (1 - s2[j][1]) / 2, cy - 10, 760 * s2[j][1], 85, 0.28, -1); }
  // the comic explosion swelling over everything, then dissolving into halftone dots
  var sizes = { 23: 260, 24: 520, 25: 900 };
  for (var p = 23; p < 26; p++) { seed(700 + p); var P = frames(comp, "pow-" + p, p, p + 1); polys(P, [starVerts(cx, cy, 14, sizes[p], sizes[p] * 0.62, 0.25, 0)], WHITE, 12, false); }
  for (var d = 26; d < 31; d++) {
    var D = frames(comp, "dots-" + d, d, d + 1), rad = 30 * (1 - (d - 26) / 5), even = [], odd = [];
    for (var gy = -9; gy <= 9; gy++) { var row = [[cx - 420 + (gy % 2 ? 21 : 0), cy + gy * 40], [cx + 420, cy + gy * 40]]; (gy % 2 ? odd : even).push(row); }
    dotted(D, even.concat(odd), rad, 42, WHITE, false);
  }
})();

// the reveals: 576 x 800, the card at the middle, 320 x 444
function revealComp(name, count) { return app.project.items.addComp(name, 576, 800, 1, count * F, 12); }
var RX = 288, RY = 400, RW = 160, RH = 222;

if (ONLY === "reveal-rare") (function () {  // rare, 1.8 s: 22 frames
  var comp = revealComp("reveal-rare", 22);
  for (var f = 0; f < 12; f++) {
    seed(1000 + f);
    var g = f < 3 ? (f + 1) / 3 : 1 - Math.max(0, f - 7) / 5, L = frames(comp, "burst-" + f, f, f + 1);
    if (f < 8) speedLines(L, RX, RY, 48, 230 + f * 14, 380 + f * 14, 7, WHITE);
    spikes(L, RX, RY, RW * 0.6, RH * 0.6, 14, 170 * g, 60, WHITE, 6, 0.12);
    spikes(L, RX, RY, RW * 0.6, RH * 0.6, 18, 240 * g, 80, PINK, 8, 0);
  }
  for (var r = 2; r < 14; r++) { var R = frames(comp, "ring-" + r, r, r + 1), rad = 170 + (r - 2) * 22, dd = 22 * (1 - (r - 2) / 13);
    dotted(R, [circle(RX, RY, rad + 12, 1.15)], dd, Math.PI * 2 * rad / 40, CYAN, true);
    dotted(R, [circle(RX, RY, rad + 12, 1.15)], dd + 6, Math.PI * 2 * rad / 40, INK, true); }
  for (var s = 3; s < 16; s++) { seed(1200 + s); var S = frames(comp, "spark-" + s, s, s + 1), list = [];
    for (var i = 0; i < 6; i++) { var a = between(0, Math.PI * 2), d = 230 + (s - 3) * 9 + between(0, 60); list.push([RX + Math.cos(a) * d, RY + Math.sin(a) * d * 1.2, between(8, 16) * (1 - (s - 3) / 14)]); }
    glints(S, list, WHITE); }
})();

if (ONLY === "reveal-epic") (function () {  // epic, 2.4 s: 29 frames
  var comp = revealComp("reveal-epic", 29);
  for (var f = 0; f < 16; f++) {
    seed(2000 + f);
    var g = f < 3 ? (f + 1) / 3 : 1 - Math.max(0, f - 10) / 6, L = frames(comp, "burst-" + f, f, f + 1);
    speedLines(L, RX, RY, 56, 260 + f * 10, 400 + f * 10, 8, WHITE);
    spikes(L, RX, RY, RW * 0.7, RH * 0.7, 16, 200 * g, 64, WHITE, 6, 0.1);
    spikes(L, RX, RY, RW * 0.7, RH * 0.7, 22, 290 * g, 90, PINK, 9, 0);
  }
  for (var z = 0; z < 15; z++) { seed(2200 + z); zaps(frames(comp, "zap-" + z, z, z + 1), RX, RY, RW, RH, 7, 12); }
  for (var s = 2; s < 22; s++) { seed(2400); var S = frames(comp, "sparks-" + s, s, s + 1), wl = [], pl = [];
    for (var i = 0; i < 10; i++) { var a = between(0, Math.PI * 2), sp = between(10, 20), d = 200 + (s - 2) * sp; (i % 2 ? wl : pl).push([RX + Math.cos(a) * d, RY + Math.sin(a) * d, between(10, 20) * (1 - (s - 2) / 22)]); }
    glints(S, wl, WHITE); glints(S, pl, PINK_L); }
  for (var c = 6; c < 24; c++) { var C = frames(comp, "cross-" + c, c, c + 1), k = c < 8 ? 1.4 - (c - 6) * 0.2 : 1;
    var cx = 470, cy = 150, r = 42 * k, ring = [];
    for (var q = 0; q <= 40; q++) ring.push([cx + Math.cos(q / 40 * Math.PI * 2) * r, cy + Math.sin(q / 40 * Math.PI * 2) * r]);
    var gr = group(C, "ring"); pathInto(gr, ring, true); strokeInto(gr, PINK, 5);
    var h1 = group(C, "h"); pathInto(h1, [[cx - r * 1.7, cy], [cx - r * 0.45, cy]], false); strokeInto(h1, PINK, 5);
    var h2 = group(C, "h"); pathInto(h2, [[cx + r * 0.45, cy], [cx + r * 1.7, cy]], false); strokeInto(h2, PINK, 5);
    var v1 = group(C, "v"); pathInto(v1, [[cx, cy - r * 1.7], [cx, cy - r * 0.45]], false); strokeInto(v1, PINK, 5);
    var v2 = group(C, "v"); pathInto(v2, [[cx, cy + r * 0.45], [cx, cy + r * 1.7]], false); strokeInto(v2, PINK, 5);
    glints(C, [[cx, cy, 10]], WHITE); }
})();

if (ONLY === "reveal-legendary") (function () {  // legendary, 3.0 s: 36 frames
  var comp = revealComp("reveal-legendary", 36);
  for (var f = 1; f < 31; f++) {
    var amp = 120 * Math.min(1, f / 4) * (1 - Math.max(0, f - 24) / 7);
    flames(frames(comp, "flames-" + f, f, f + 1), RX, RY, RW + 18, RH + 18, amp, f * 1.3);
  }
  for (var r = 0; r < 14; r++) { var R = frames(comp, "rings-" + r, r, r + 1);
    for (var k = 0; k < 2; k++) { var rad = 230 + (r - k * 4) * 18; if (r - k * 4 < 0) continue; var ring = [];
      for (var q = 0; q <= 60; q++) ring.push([RX + Math.cos(q / 60 * Math.PI * 2) * rad, RY + Math.sin(q / 60 * Math.PI * 2) * rad * 1.15]);
      var gi = group(R, "lime"); pathInto(gi, ring, true); strokeInto(gi, LIME, 7);
      var go = group(R, "ink"); pathInto(go, ring, true); strokeInto(go, INK, 15); } }
  for (var s = 2; s < 16; s++) { seed(3300); var S = frames(comp, "drops-" + s, s, s + 1), drops = [];
    for (var i = 0; i < 12; i++) { var a = between(0, Math.PI * 2), d = 240 + (s - 2) * between(12, 22), rr = between(8, 15) * (1 - (s - 2) / 16);
      drops.push(circle(RX + Math.cos(a) * d, RY + Math.sin(a) * d * 1.1, rr, 1)); }
    polys(S, drops, GREEN, 4, false); }
  var big = [[4, 0.5], [5, 1], [6, 0.85], [7, 0.6], [8, 0.4], [9, 0.2]], small = [[17, 0.5], [18, 1], [19, 0.7], [20, 0.4], [21, 0.2]];
  for (var b = 0; b < big.length; b++) glints(frames(comp, "glintA-" + b, big[b][0], big[b][0] + 1), [[470, 150, 120 * big[b][1]]], WHITE);
  for (var m = 0; m < small.length; m++) glints(frames(comp, "glintB-" + m, small[m][0], small[m][0] + 1), [[110, 650, 80 * small[m][1]]], WHITE);
})();

writeLn("comps " + app.project.numItems);

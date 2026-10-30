// Impact — the booster scene's animations, drawn as anime impact frames at 24 fps: every shape flat,
// inked. Times are counted in twelfths of a second (F); the comps run at 24 frames a second: every loop steps by
// half a twelfth (an in-between), its shapes redrawn each twelfth (their seed), their motion moving on each frame.
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
// one frame's layer: visible from frame a to frame b (exclusive), in twelfths
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
  var comp = app.project.items.addComp("opening", 1152, 1080, 1, 32 * F, 24);
  var cx = 576, cy = 505, hw = 120, hh = 177;   // the pack at its real size, room all round
  for (var f = 0; f < 23; f += 0.5) {
    seed(100 + Math.floor(f));
    var grow = Math.min(1, (f + 2) / 12), L = frames(comp, "rays-" + f, f, f + 0.5);
    speedLines(L, cx, cy, 80, 380 + f * 10, 760 + f * 12, 7, WHITE);
    spikes(L, cx, cy, hw, hh, 16, 320 * grow, 70, WHITE, 6, 0.1);
    spikes(L, cx, cy, hw, hh, 22, 480 * grow, 90, PINK, 8, 0);
  }
  for (var z = 1; z < 23; z += 0.5) { seed(300 + z * 2); var Z = frames(comp, "zap-" + z, z, z + 0.5); var k = 1 + 0.2 * Math.min(1, z / 20); zaps(Z, cx, cy, hw * k, hh * k, 7, 14); }
  // two slashes crossing the box at frames 14 and 16, drawn in two frames, held, then gone
  seed(500);
  var s1 = [[14, 0.35], [15, 0.85], [16, 1.0], [17, 1.0]], s2 = [[16, 0.4], [17, 0.9], [18, 1.0], [19, 1.0]];
  for (var i = 0; i < s1.length; i++) { var A = frames(comp, "slashA-" + i, s1[i][0], s1[i][0] + 1); slash(A, cx - 500 * (1 - s1[i][1]) / 2, cy + 20, 1000 * s1[i][1], 105, -0.32, 1); }
  for (var j = 0; j < s2.length; j++) { var B = frames(comp, "slashB-" + j, s2[j][0], s2[j][0] + 1); slash(B, cx + 500 * (1 - s2[j][1]) / 2, cy - 10, 1000 * s2[j][1], 95, 0.28, -1); }
  // the comic explosion swelling over everything, then dissolving into halftone dots
  var sizes = { 23: 360, 24: 720, 25: 1300 };
  for (var p = 23; p < 26; p++) { seed(700 + p); var P = frames(comp, "pow-" + p, p, p + 1); polys(P, [starVerts(cx, cy, 14, sizes[p], sizes[p] * 0.62, 0.25, 0)], WHITE, 12, false); }
  for (var d = 26; d < 31; d += 0.5) {
    var D = frames(comp, "dots-" + d, d, d + 0.5), rad = 30 * (1 - (d - 26) / 5), even = [], odd = [];
    for (var gy = -14; gy <= 14; gy++) { var row = [[cx - 640 + (gy % 2 ? 21 : 0), cy + gy * 40], [cx + 640, cy + gy * 40]]; (gy % 2 ? odd : even).push(row); }
    dotted(D, even.concat(odd), rad, 42, WHITE, false);
  }
})();

// the reveals: 576 x 800, the card at the middle, 320 x 444
// the card at its real size in the middle of a stage 2.6 times as large: room for the effects to spread
function revealComp(name, count) { return app.project.items.addComp(name, 832, 1154, 1, count * F, 24); }
var RX = 416, RY = 577, RW = 160, RH = 222;

if (ONLY === "reveal-rare") (function () {  // rare, 1.8 s: 22 frames
  var comp = revealComp("reveal-rare", 22);
  for (var f = 0; f < 12; f += 0.5) {
    seed(1000 + Math.floor(f));
    var g = f < 3 ? (f + 1) / 3 : 1 - Math.max(0, f - 7) / 5, L = frames(comp, "burst-" + f, f, f + 0.5);
    if (f < 8) speedLines(L, RX, RY, 56, 300 + f * 22, 560 + f * 24, 7, WHITE);
    spikes(L, RX, RY, RW * 0.6, RH * 0.6, 14, 250 * g, 60, WHITE, 6, 0.12);
    spikes(L, RX, RY, RW * 0.6, RH * 0.6, 18, 360 * g, 80, PINK, 8, 0);
  }
  for (var r = 2; r < 14; r += 0.5) { var R = frames(comp, "ring-" + r, r, r + 0.5), rad = 200 + (r - 2) * 32, dd = 22 * (1 - (r - 2) / 13);
    dotted(R, [circle(RX, RY, rad + 12, 1.15)], dd, Math.PI * 2 * rad / 40, CYAN, true);
    dotted(R, [circle(RX, RY, rad + 12, 1.15)], dd + 6, Math.PI * 2 * rad / 40, INK, true); }
  for (var s = 3; s < 16; s += 0.5) { seed(1200 + Math.floor(s)); var S = frames(comp, "spark-" + s, s, s + 0.5), list = [];
    for (var i = 0; i < 6; i++) { var a = between(0, Math.PI * 2), d = 260 + (s - 3) * 16 + between(0, 80); list.push([RX + Math.cos(a) * d, RY + Math.sin(a) * d * 1.2, between(8, 16) * (1 - (s - 3) / 14)]); }
    glints(S, list, WHITE); }
})();

if (ONLY === "reveal-epic") (function () {  // epic, 2.4 s: 29 frames
  var comp = revealComp("reveal-epic", 29);
  for (var f = 0; f < 16; f += 0.5) {
    seed(2000 + Math.floor(f));
    var g = f < 3 ? (f + 1) / 3 : 1 - Math.max(0, f - 10) / 6, L = frames(comp, "burst-" + f, f, f + 0.5);
    speedLines(L, RX, RY, 64, 320 + f * 16, 600 + f * 18, 8, WHITE);
    spikes(L, RX, RY, RW * 0.7, RH * 0.7, 16, 300 * g, 64, WHITE, 6, 0.1);
    spikes(L, RX, RY, RW * 0.7, RH * 0.7, 22, 420 * g, 90, PINK, 9, 0);
  }
  for (var z = 0; z < 15; z += 0.5) { seed(2200 + z * 2); zaps(frames(comp, "zap-" + z, z, z + 0.5), RX, RY, RW, RH, 7, 12); }
  for (var s = 2; s < 22; s += 0.5) { seed(2400); var S = frames(comp, "sparks-" + s, s, s + 0.5), wl = [], pl = [];
    for (var i = 0; i < 10; i++) { var a = between(0, Math.PI * 2), sp = between(10, 20), d = 230 + (s - 2) * sp * 1.5; (i % 2 ? wl : pl).push([RX + Math.cos(a) * d, RY + Math.sin(a) * d, between(10, 20) * (1 - (s - 2) / 22)]); }
    glints(S, wl, WHITE); glints(S, pl, PINK_L); }
  for (var c = 6; c < 24; c += 0.5) { var C = frames(comp, "cross-" + c, c, c + 0.5), k = c < 8 ? 1.4 - (c - 6) * 0.2 : 1;
    var cx = RX + 182, cy = RY - 250, r = 42 * k, ring = [];
    for (var q = 0; q <= 40; q++) ring.push([cx + Math.cos(q / 40 * Math.PI * 2) * r, cy + Math.sin(q / 40 * Math.PI * 2) * r]);
    var gr = group(C, "ring"); pathInto(gr, ring, true); strokeInto(gr, PINK, 5);
    var h1 = group(C, "h"); pathInto(h1, [[cx - r * 1.7, cy], [cx - r * 0.45, cy]], false); strokeInto(h1, PINK, 5);
    var h2 = group(C, "h"); pathInto(h2, [[cx + r * 0.45, cy], [cx + r * 1.7, cy]], false); strokeInto(h2, PINK, 5);
    var v1 = group(C, "v"); pathInto(v1, [[cx, cy - r * 1.7], [cx, cy - r * 0.45]], false); strokeInto(v1, PINK, 5);
    var v2 = group(C, "v"); pathInto(v2, [[cx, cy + r * 0.45], [cx, cy + r * 1.7]], false); strokeInto(v2, PINK, 5);
    glints(C, [[cx, cy, 10]], WHITE); }
})();

// the legendary's power vortex, played while the card turns (0.8 s) and just after: three energy ribbons — white,
// rimmed in pink, inked — spiralling round the card, tightening, then blasting outwards as it lands; pink
// lightning crackling round its edges. Its front half goes over the card, its back half under it.
function ribbonRuns(f, k, front) {
  var spin = f * 0.75, tight = f < 9 ? 1 - f / 9 : 0, blast = f < 9 ? 0 : (f - 9) / 6;
  // each ribbon its own pitch, reach and tilt: they cross, a whirlwind rather than a barber's pole
  var turns = [1.0, 1.45, 1.8][k], reach = [1.0, 1.12, 0.92][k], tilt = [0.24, -0.3, 0.12][k], dir = k === 1 ? -1 : 1;
  var R = (185 + 120 * tight + 380 * blast) * reach, H = 2 * RH + 150, thin = Math.max(0.15, 1 - blast);
  var pts = [], n = 64;
  for (var i = 0; i <= n; i++) {
    var u = i / n, th = dir * (spin + u * turns * Math.PI * 2) + k * Math.PI * 2 / 3;
    pts.push({ x: RX + R * Math.cos(th), y: RY + (0.5 - u) * H + tilt * R * Math.sin(th) + (u - 0.5) * 40 * k, d: Math.sin(th), w: [30, 24, 34][k] * Math.pow(Math.sin(Math.PI * u), 0.7) * thin });
  }
  var runs = [], run = [];
  for (var j = 0; j < pts.length; j++) {
    if ((pts[j].d > 0) === front) run.push(pts[j]);
    else if (run.length) { runs.push(run); run = []; }
  }
  if (run.length) runs.push(run);
  var polysOut = [];
  for (var r = 0; r < runs.length; r++) {
    var rr = runs[r]; if (rr.length < 3) continue;
    var left = [], right = [];
    for (var q = 0; q < rr.length; q++) {
      var a = rr[Math.max(0, q - 1)], b = rr[Math.min(rr.length - 1, q + 1)], tx = b.x - a.x, ty = b.y - a.y, l = Math.sqrt(tx * tx + ty * ty) || 1;
      var nx = -ty / l, ny = tx / l, w = rr[q].w * (q === 0 || q === rr.length - 1 ? 0.35 : 1);
      left.push([rr[q].x + nx * w, rr[q].y + ny * w]); right.push([rr[q].x - nx * w * 0.7, rr[q].y - ny * w * 0.7]);
    }
    polysOut.push(left.concat(right.reverse()));
  }
  return polysOut;
}
function ribbons(L, f, front) {
  var white = [], pink = [];
  for (var k = 0; k < 3; k++) {
    var list = ribbonRuns(f, k, front);
    for (var i = 0; i < list.length; i++) {
      white.push(list[i]);
      var rim = []; for (var v = 0; v < list[i].length; v++) rim.push([list[i][v][0] + 7, list[i][v][1] + 10]);
      pink.push(rim);
    }
  }
  if (white.length) { polys(L, white, WHITE, 7, false); polys(L, pink, PINK, 0, false); }
}
if (ONLY === "legendary-front") (function () {  // over the card, 1.5 s: 18 frames
  var comp = revealComp("legendary-front", 18);
  for (var f = 0; f < 16; f += 0.5) {
    var L = frames(comp, "front-" + f, f, f + 0.5);
    if (f < 11) { seed(4100 + f * 2); zaps(L, RX, RY, RW * 1.04, RH * 1.04, 5, 8); }
    ribbons(L, f, true);
  }
})();
if (ONLY === "legendary-back") (function () {  // under the card, 1.5 s: 18 frames
  var comp = revealComp("legendary-back", 18);
  for (var f = 0; f < 16; f += 0.5) {
    seed(4300 + Math.floor(f));
    var L = frames(comp, "back-" + f, f, f + 0.5), g = Math.min(1, (f + 2) / 8);
    ribbons(L, f, false);
    speedLines(L, RX, RY, 64, 360 + f * 14, 640 + f * 16, 8, WHITE);
    spikes(L, RX, RY, RW, RH, 18, 240 * g, 70, WHITE, 6, 0.1);
    spikes(L, RX, RY, RW, RH, 24, 360 * g, 90, PINK, 8, 0);
  }
})();
// the legendary's reveal, once it has landed, 2.5 s: 30 frames — the biggest burst, rings, great glints
if (ONLY === "reveal-legendary") (function () {
  var comp = revealComp("reveal-legendary", 30);
  for (var f = 0; f < 16; f += 0.5) {
    seed(4500 + Math.floor(f));
    var g = f < 3 ? (f + 1) / 3 : 1 - Math.max(0, f - 10) / 6, L = frames(comp, "burst-" + f, f, f + 0.5);
    speedLines(L, RX, RY, 72, 340 + f * 18, 640 + f * 20, 9, WHITE);
    spikes(L, RX, RY, RW, RH, 18, 260 * g, 70, WHITE, 6, 0.12);
    spikes(L, RX, RY, RW, RH, 26, 400 * g, 95, PINK, 9, 0);
    spikes(L, RX, RY, RW, RH, 12, 500 * g, 60, YELLOW, 7, 0.27);
  }
  for (var r = 0; r < 14; r += 0.5) { var R = frames(comp, "rings-" + r, r, r + 0.5);
    for (var k = 0; k < 2; k++) { var s = r - k * 4; if (s < 0) continue; var rad = 260 + s * 30, ring = circle(RX, RY, rad, 1.2);
      var gi = group(R, "white"); pathInto(gi, ring, true); strokeInto(gi, k ? PINK : WHITE, 7);
      var go = group(R, "ink"); pathInto(go, ring, true); strokeInto(go, INK, 15); } }
  for (var s2 = 2; s2 < 22; s2 += 0.5) { seed(4700); var S = frames(comp, "sparks-" + s2, s2, s2 + 0.5), wl = [], yl = [];
    for (var i = 0; i < 12; i++) { var a = between(0, Math.PI * 2), d = 250 + (s2 - 2) * between(14, 28); (i % 2 ? wl : yl).push([RX + Math.cos(a) * d, RY + Math.sin(a) * d * 1.15, between(10, 20) * (1 - (s2 - 2) / 21)]); }
    glints(S, wl, WHITE); glints(S, yl, YELLOW); }
  var big = [[1, 0.5], [2, 1], [3, 0.85], [4, 0.6], [5, 0.4], [6, 0.2]], small = [[14, 0.5], [15, 1], [16, 0.7], [17, 0.4], [18, 0.2]];
  for (var b = 0; b < big.length; b++) glints(frames(comp, "glintA-" + b, big[b][0], big[b][0] + 1), [[RX + 182, RY - 250, 130 * big[b][1]]], WHITE);
  for (var m = 0; m < small.length; m++) glints(frames(comp, "glintB-" + m, small[m][0], small[m][0] + 1), [[RX - 178, RY + 250, 90 * small[m][1]]], YELLOW);
})();

writeLn("comps " + app.project.numItems);

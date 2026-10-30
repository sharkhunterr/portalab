// Sumi — the booster scene's animations, ink and gold drawn frame by frame at 24 frames a second: brushed ink
// edged with gold leaf, white gofun, vermillion and cherry pink. Every shape is redrawn each frame; its brush
// grain changes every other frame (its seed), like ink still wet. Layers made later are drawn on top.

// --- the opening: 1152 x 1080, the pack at (576, 505), 240 x 355 — 64 frames (2.67 s) ------------------------
// Ink gathers round the pack in curling strokes, gold dust drawn in with it, a thin gold circle closing; gold
// cracks run over the pack (kintsugi); one huge dry-brush stroke cuts it through, a white hairline at its heart,
// a flash; ink bursts out in heavy gilded strokes, gold leaf flying; a great gold ensō is drawn and fades away.
if (ONLY === "opening") (function () {
  var comp = app.project.items.addComp("opening", 1152, 1080, 1, 64 * F, 24);
  var cx = 576, cy = 505, hw = 120, hh = 177;
  // the strokes gathering: seven tendrils spiralling in, drawn, then drawn in towards the pack
  seed(10);
  var tendrils = [];
  for (var k = 0; k < 7; k++) {
    var a0 = k / 7 * Math.PI * 2 + between(-0.25, 0.25), pts = [], r0 = between(520, 600), r1 = Math.max(hw, hh) * 1.2, curl = between(1.0, 1.5);
    for (var i = 0; i <= 44; i++) { var u = i / 44, r = r0 + (r1 - r0) * Math.pow(u, 0.8), a = a0 + curl * u; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r * 0.92]); }
    tendrils.push({ pts: pts, w: between(30, 46) });
  }
  for (var f = 0; f < 27; f++) {
    var L = frames(comp, "tendrils-" + f, f, f + 1), list = [];
    seed(100 + Math.floor(f / 2));
    for (var t = 0; t < tendrils.length; t++) {
      var tp = tendrils[t].pts, sucked = f > 15 ? ease((f - 15) / 11) : 0, from = Math.floor(sucked * (tp.length - 3));
      var part = tp.slice(from), grow = f > 15 ? 1 : ease((f + 1) / 14);
      list = list.concat(brushPolys(part, tendrils[t].w * (1 - 0.6 * sucked), grow, 0.45, 8));
    }
    gilded(L, list, INK, GOLD, 4, 6);
  }
  // gold dust drawn in with the ink
  for (var g = 0; g < 26; g++) {
    seed(200); var G = frames(comp, "dust-" + g, g, g + 1), motes = [];
    for (var m = 0; m < 34; m++) {
      var ma = between(0, Math.PI * 2) + g * 0.06, md = between(380, 620) * (1 - ease(g / 25) * 0.78), size = between(3, 7) * (0.6 + 0.4 * Math.sin(g * 0.9 + m));
      motes.push([cx + Math.cos(ma) * md, cy + Math.sin(ma) * md * 0.9, Math.max(1.5, size)]);
    }
    glints(G, motes, GOLD_L);
  }
  // a thin gold circle closing round the pack
  for (var e = 6; e < 30; e++) {
    seed(300 + Math.floor(e / 2));
    var E = frames(comp, "ring-" + e, e, e + 1, e < 24 ? 100 : 100 - (e - 24) * 16);
    polys(E, brushPolys(ensoLine(cx, cy, 250, 1.05, -2.0, Math.PI * 1.85), 12, ease((e - 5) / 14), 0.6, 4), GOLD);
  }
  // gold cracks running over the pack
  seed(400);
  var cracks = [];
  for (var c = 0; c < 6; c++) cracks = cracks.concat(crackLines(cx + between(-30, 30), cy + between(-50, 10), c / 6 * Math.PI * 2 + between(-0.3, 0.3), between(90, 150), 0.12));
  for (var q = 18; q < 31; q++) gold(frames(comp, "cracks-" + q, q, q + 1), partOf(cracks, ease((q - 17) / 9)), 7);
  // the flash under the cut
  var flash = { 30: [420, 90], 31: [760, 70], 32: [1000, 40] };
  for (var fl = 30; fl < 33; fl++) {
    seed(500 + fl); var FL = frames(comp, "flash-" + fl, fl, fl + 1, flash[fl][1]), star = [];
    for (var s = 0; s < 36; s++) { var sa = s / 36 * Math.PI * 2, sr = s % 2 ? flash[fl][0] * 0.35 : flash[fl][0] * between(0.7, 1); star.push([cx + Math.cos(sa) * sr, cy + Math.sin(sa) * sr]); }
    polys(FL, [star], GOLD_L);
  }
  // the ink bursting out of it: heavy strokes flung outwards, gilded, a drop beyond each, drying away
  for (var bb = 32; bb < 54; bb++) gilded(frames(comp, "burst-" + bb, bb, bb + 1), inkBurst(cx, cy, 17, 0, 0, 470, 74, 0.92, bb - 32, 600), INK, GOLD, 5, 7);
  // the cut: one huge dry-brush stroke across everything, a white hairline at its heart
  seed(700);
  var cut = arcLine(cx - 560, cy + 340, cx + 560, cy - 330, 70, 60), cutAt = { 28: 0.3, 29: 0.7 };
  for (var x = 28; x < 40; x++) {
    seed(710 + Math.floor(x / 2));
    var X = frames(comp, "cut-" + x, x, x + 1);
    gilded(X, brushPolys(cut, 150, cutAt[x] || 1, 0.5, 13, x < 34 ? 0 : (x - 33) / 6), INK, GOLD, 6, 9);
    if (x >= 30 && x < 34) lines(X, [cut.slice(6, 54)], [[WHITE, 6 - (x - 30)]]);
  }
  // gold leaf flying out, turning over, falling
  for (var l = 33; l < 64; l++) {
    seed(800); var LL = frames(comp, "leaf-" + l, l, l + 1, l < 52 ? 100 : Math.max(0, 100 - (l - 52) * 9)), leaf = [], age = l - 33;
    for (var j = 0; j < 38; j++) {
      var la = between(0, Math.PI * 2), ld = 90 + between(300, 640) * ease(age / 18), fall = age * age * 0.18 * between(0.6, 1.2);
      leaf.push([cx + Math.cos(la) * ld, cy + Math.sin(la) * ld * 0.85 + fall, between(9, 20), between(0, 6) + age * between(-0.25, 0.25), between(0, 6) + age * between(0.2, 0.5)]);
    }
    flakes(LL, leaf);
  }
  // the great ensō, drawn in one breath, held, fading
  for (var n = 42; n < 64; n++) {
    seed(900 + Math.floor(n / 2));
    var N = frames(comp, "enso-" + n, n, n + 1, n < 60 ? 100 : 100 - (n - 59) * 22);
    gilded(N, brushPolys(ensoLine(cx, cy, 330, 1.0, -2.3, Math.PI * 1.82), 52, ease((n - 41) / 8), 0.5, 10, n < 52 ? 0 : (n - 51) / 12), GOLD, GOLD_D, 4, 6);
  }
})();

// --- the reveals: 832 x 1154, the card in the middle, 320 x 444 — drawn behind the card -------------------
// the legendary's comps take more room: 4.4 times the card (its layer as much), the others 2.6 times
var BIG = ONLY === "reveal-legendary" || ONLY === "legendary-front" || ONLY === "legendary-back", K = BIG ? 1.5 : 1;
var CW = BIG ? 1408 : 832, CH = BIG ? 1954 : 1154;
function revealComp(name, count) { return app.project.items.addComp(name, CW, CH, 1, count * F, 24); }
var RX = CW / 2, RY = CH / 2, RW = 160, RH = 222;
function ringLines(cx, cy, r, k) { var v = circle(cx, cy, r, k, 64); v.push(v[0]); return v; }

// rare, 1.8 s: 44 frames — a white ensō brushed round the card, edged in indigo, ripples spreading as on a pond,
// silver drops and glints
if (ONLY === "reveal-rare") (function () {
  var comp = revealComp("reveal-rare", 44);
  for (var w = 2; w < 42; w++) {
    var W = frames(comp, "ripples-" + w, w, w + 1), list = [], thin = [];
    for (var k = 0; k < 3; k++) { var age = w - 2 - k * 7; if (age < 0 || age > 30) continue; var r = 230 + age * 13; list.push(ringLines(RX, RY, r, 1.18)); thin.push(ringLines(RX, RY, r + 14, 1.18)); }
    lines(W, list, [[AI_L, 7 * (1 - (w - 2) / 44), 80]]);
    lines(W, thin, [[WHITE, 2.5, 50]]);
  }
  for (var e = 0; e < 32; e++) {
    seed(1000 + Math.floor(e / 2));
    var E = frames(comp, "enso-" + e, e, e + 1, e < 28 ? 100 : 100 - (e - 27) * 22);
    gilded(E, brushPolys(ensoLine(RX, RY, 300, 1.18, -1.9, Math.PI * 1.78), 58, ease((e + 1) / 9), 0.5, 10, e < 18 ? 0 : (e - 17) / 14), WHITE, AI, 5, 7);
  }
  for (var d = 3; d < 32; d++) {
    seed(1100); var D = frames(comp, "drops-" + d, d, d + 1, d < 24 ? 100 : 100 - (d - 24) * 12), drops = [], sp = [], age2 = d - 3;
    for (var i = 0; i < 18; i++) {
      var a = between(0, Math.PI * 2), dist = 250 + between(60, 260) * ease(age2 / 12), y = age2 * age2 * 0.25;
      drops.push(circle(RX + Math.cos(a) * dist, RY + Math.sin(a) * dist * 1.2 + y, between(4, 9) * (1 - age2 / 40), 1, 12));
      if (i % 3 === 0) sp.push([RX + Math.cos(a + 0.3) * dist * 1.1, RY + Math.sin(a + 0.3) * dist * 1.25, between(8, 16) * Math.sin(Math.PI * Math.min(1, age2 / 20))]);
    }
    polys(D, drops, WHITE);
    glints(D, sp, AI_L);
  }
})();

// epic, 2.4 s: 58 frames — two vermillion brush strokes crossing behind the card, edged in ink; a storm of cherry
// petals and blossoms; gold leaf; a vermillion seal stamped by its corner
if (ONLY === "reveal-epic") (function () {
  var comp = revealComp("reveal-epic", 58);
  var cutA = arcLine(RX - 360, RY + 300, RX + 360, RY - 290, 50, 50), cutB = arcLine(RX + 350, RY + 280, RX - 350, RY - 300, -40, 50);
  var at = { 2: 0.35, 3: 0.75, 6: 0.35, 7: 0.75 };
  for (var s = 2; s < 24; s++) {
    seed(2000 + Math.floor(s / 2));
    var dryA = s < 13 ? 0 : (s - 12) / 12, S = frames(comp, "strokes-" + s, s, s + 1, s < 21 ? 100 : 100 - (s - 20) * 30), list = brushPolys(cutA, 96, at[s] || 1, 0.5, 11, dryA);
    if (s >= 6) list = list.concat(brushPolys(cutB, 84, at[s] || 1, 0.5, 11, dryA));
    gilded(S, list, SHU, INK, 6, 8);
  }
  for (var g = 4; g < 50; g++) {
    seed(2100); var G = frames(comp, "leaf-" + g, g, g + 1, g < 40 ? 100 : 100 - (g - 40) * 10), leaf = [], age = g - 4;
    for (var j = 0; j < 18; j++) { var la = between(0, Math.PI * 2), ld = 240 + between(120, 300) * ease(age / 16); leaf.push([RX + Math.cos(la) * ld, RY + Math.sin(la) * ld * 1.15 + age * age * 0.12, between(8, 16), age * between(-0.2, 0.2), age * between(0.25, 0.5)]); }
    flakes(G, leaf);
  }
  for (var p = 3; p < 58; p++) {
    seed(2200); var P = frames(comp, "petals-" + p, p, p + 1, p < 46 ? 100 : 100 - (p - 46) * 8), list2 = [], age2 = p - 3;
    for (var i = 0; i < 46; i++) {
      var a = between(0, Math.PI * 2), base = toEdge(a, RW, RH) * 0.9, out = base + between(120, 420) * ease(age2 / 22), sway = Math.sin(age2 * 0.18 + i) * 22;
      list2.push([RX + Math.cos(a) * out + sway, RY + Math.sin(a) * out + age2 * between(0.8, 2.4), between(16, 30), between(0, 6) + age2 * between(-0.12, 0.12), between(0, 6) + age2 * between(0.12, 0.3)]);
    }
    petals(P, list2);
    if (p > 4) {
      seed(2300);
      for (var b = 0; b < 5; b++) { var ba = between(0, Math.PI * 2), bd = toEdge(ba, RW, RH) + between(90, 220) * ease((p - 4) / 14); blossom(P, RX + Math.cos(ba) * bd, RY + Math.sin(ba) * bd + age2 * 0.9, between(26, 38) * ease((p - 4) / 5), age2 * 0.05 + b); }
    }
  }
  var stamp = { 10: 1.7, 11: 1.3, 12: 1.0 };
  for (var h = 10; h < 52; h++) {
    var H = frames(comp, "seal-" + h, h, h + 1, h < 44 ? 100 : 100 - (h - 44) * 12), k = stamp[h] || 1, hx = RX + 222, hy = RY - 272;
    blossom(H, hx, hy, 30 * k, 0.3, WHITE);
    polys(H, [circle(hx, hy, 52 * k, 1, 40)], SHU);
    if (h >= 12 && h < 18) { seed(2400); var dots = []; for (var q = 0; q < 9; q++) { var qa = between(0, Math.PI * 2), qd = 62 + (h - 12) * 9 + between(0, 20); dots.push(circle(hx + Math.cos(qa) * qd, hy + Math.sin(qa) * qd, between(3, 7), 1, 10)); } polys(H, dots, SHU); }
  }
})();

// the legendary's ink dragon, while the card turns (1.5 s: 36 frames) — a black dragon edged in gold, scaled
// in gold, its belly gilded, its mane vermillion, coiling twice round the card and tightening, then soaring
// away upwards, flinging its ink, as the card lands. Its front half goes over the card, its back half under it.
function dragonPoints(f) {
  var spin = 0.9 + f * 0.21, coil = f < 22 ? 1 - ease(f / 22) : 0, out = f < 22 ? 0 : ease((f - 22) / 11);
  var R = (225 + 105 * coil) * (1 + (K - 1) * 0.8) + 260 * out * K, H = (2 * RH + 170 * K * K) * (1 + 0.6 * out), turns = 1.55, rise = 820 * K * out, pts = [];
  for (var i = 0; i <= 96; i++) {
    var u = i / 96, th = spin + u * turns * Math.PI * 2;
    pts.push({ x: RX + R * Math.cos(th), y: RY + (0.5 - u) * H + 0.22 * R * Math.sin(th) - rise, d: Math.sin(th), u: u });
  }
  return { pts: pts, thin: out < 0.75 ? 1 : Math.max(0.05, 1 - (out - 0.75) * 4) };
}
function bodyWidth(u) { return (9 + 36 * Math.pow(u, 0.55) * (u > 0.93 ? 0.86 : 1)) * (1 + (K - 1) * 0.7); }
// the head, in its own frame (x forwards, y across), about twice the body's width
var SKULL = [[-40, -34], [-5, -42], [30, -32], [62, -22], [90, -13], [100, -4], [86, 2], [52, 4], [22, 9], [-10, 15], [-42, 20]];
var JAW = [[-30, 16], [10, 14], [48, 13], [82, 26], [72, 34], [40, 33], [4, 34], [-30, 32]];
var HORNS = [[[-12, -38], [-74, -96], [-98, -102], [-58, -62], [-30, -32]], [[-28, -30], [-100, -62], [-122, -54], [-52, -18]]];
var TEETH = [[[48, 4], [53, 13], [58, 4]], [[64, 3], [69, 12], [74, 3]], [[78, 2], [82, 9], [86, 2]], [[38, 14], [43, 6], [48, 14]], [[56, 17], [61, 9], [66, 19]]];
function headPolys(list, x, y, ang, s) { var out = []; for (var i = 0; i < list.length; i++) out.push(rotated(list[i], x, y, ang, s, s)); return out; }
function dragon(L, f, front) {
  var D = dragonPoints(f), pts = D.pts, runs = [], run = [];
  for (var j = 0; j < pts.length; j++) {
    if ((pts[j].d > 0) === front) run.push(j);
    else if (run.length) { runs.push(run); run = []; }
  }
  if (run.length) runs.push(run);
  var body = [], scales = [], fins = [], belly = [], plates = [];
  for (var r = 0; r < runs.length; r++) {
    var idx = runs[r]; if (idx.length < 2) continue;
    var left = [], right = [], inner = [];
    for (var q = 0; q < idx.length; q++) {
      var i = idx[q], a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)], tx = b.x - a.x, ty = b.y - a.y, l = Math.sqrt(tx * tx + ty * ty) || 1;
      var nx = -ty / l, ny = tx / l, w = bodyWidth(pts[i].u) * D.thin, ux = tx / l, uy = ty / l;
      left.push([pts[i].x + nx * w, pts[i].y + ny * w]); right.push([pts[i].x - nx * w, pts[i].y - ny * w]);
      inner.push([pts[i].x - nx * w * 0.42, pts[i].y - ny * w * 0.42]);
      if (i % 2 === 0) plates.push([[pts[i].x - nx * w * 0.44, pts[i].y - ny * w * 0.44], [pts[i].x - nx * w * 0.96 - ux * w * 0.15, pts[i].y - ny * w * 0.96 - uy * w * 0.15]]);
      if (i % 4 === 0 && i > 4 && i < 90) fins.push([[pts[i].x + nx * w * 0.9 - ux * w * 0.3, pts[i].y + ny * w * 0.9 - uy * w * 0.3], [pts[i].x + nx * w * 1.8 - ux * w, pts[i].y + ny * w * 1.8 - uy * w], [pts[i].x + nx * w * 0.9 + ux * w * 0.5, pts[i].y + ny * w * 0.9 + uy * w * 0.5]]);
      if (i % 3 === 0 && i > 3 && i < 93) scales.push([[pts[i].x + nx * w * 0.75, pts[i].y + ny * w * 0.75], [pts[i].x + nx * w * 0.1 - ux * w * 0.6, pts[i].y + ny * w * 0.1 - uy * w * 0.6], [pts[i].x - nx * w * 0.38, pts[i].y - ny * w * 0.38]]);
    }
    body.push(left.concat(right.slice().reverse()));
    belly.push(inner.concat(right.slice().reverse()));
  }
  var whiskers = [], eyes = [], pupils = [], teeth = [], mane = [], head = [];
  var hi = pts.length - 1, hp = pts[hi];
  if ((hp.d > 0) === front && D.thin > 0.3) {
    var p2 = pts[hi - 3], ang = Math.atan2(hp.y - p2.y, hp.x - p2.x), s = 1.25 * (1 + (K - 1) * 0.7) * D.thin;
    head = headPolys([SKULL, JAW].concat(HORNS), hp.x, hp.y, ang, s);
    teeth = headPolys(TEETH, hp.x, hp.y, ang, s);
    for (var m = 0; m < 7; m++) { var mx = -34 - m * 15, flick = Math.sin(f * 0.7 + m) * 8; mane.push(rotated([[mx + 6, -30 + m * 3], [mx - 44 + flick, -74 + m * 7], [mx - 14, -24 + m * 3]], hp.x, hp.y, ang, s, s)); mane.push(rotated([[mx + 4, 24], [mx - 40 + flick, 56 + m * 2], [mx - 12, 22]], hp.x, hp.y, ang, s, s)); }
    for (var side = -1; side <= 1; side += 2) {
      var wl = [];
      for (var k = 0; k <= 18; k++) { var t = k / 18; wl.push([92 - t * 300, side * (6 + t * 54) + Math.sin(t * 6 + f * 0.5 + side) * 26 * t]); }
      whiskers.push(rotated(wl, hp.x, hp.y, ang, s, s));
    }
    var eye = rotated([[34, -20]], hp.x, hp.y, ang, s, s)[0];
    eyes.push(rotated(circle(0, 0, 11, 0.55, 18), eye[0], eye[1], ang, s, s)); pupils.push(circle(eye[0], eye[1], 4 * s, 1, 12));
    lines(L, [rotated([[6, -36], [30, -30], [52, -24]], hp.x, hp.y, ang, s, s)], [[GOLD_L, 3]]);
  }
  // top to bottom: whiskers, eye, teeth, scales, belly plates, belly, the ink body edged in gold, the mane
  lines(L, whiskers, [[GOLD_L, 3.5], [GOLD_D, 7]]);
  polys(L, pupils, SHU); polys(L, eyes, GOLD_L); polys(L, teeth, WHITE);
  lines(L, scales, [[GOLD, 3.5]]);
  lines(L, plates, [[INK, 3]]);
  polys(L, belly, [0.66, 0.44, 0.13]);
  gilded(L, body.concat(fins, head), INK, GOLD, 4, 6);
  gilded(L, mane, SHU, INK, 3, 4);
  // the ink it flings away as it soars off
  if (f >= 22) {
    seed(3000 + (front ? 1 : 2));
    var drops = [], age = f - 22;
    for (var i2 = 0; i2 < 30; i2++) {
      var pi = pts[Math.floor(between(6, 80))];
      if ((pi.d > 0) !== front) continue;
      var da = Math.atan2(pi.y - RY, pi.x - RX) + between(-0.5, 0.5), dd = age * between(8, 20);
      drops.push(circle(pi.x + Math.cos(da) * dd, pi.y + Math.sin(da) * dd + age * 30, between(4, 12) * (1 - age / 16), 1, 12));
    }
    gilded(L, drops, INK, GOLD, 3, 4);
  }
}
if (ONLY === "legendary-front") (function () {
  var comp = revealComp("legendary-front", 36);
  for (var f = 0; f < 34; f++) {
    var L = frames(comp, "front-" + f, f, f + 1);
    dragon(L, f, true);
    if (f % 3 === 0 && f < 26) { seed(3100 + f); var sp = []; for (var i = 0; i < 5; i++) { var p = dragonPoints(f).pts[Math.floor(between(8, 90))]; if (p.d > 0) sp.push([p.x + between(-30, 30), p.y + between(-30, 30), between(8, 16)]); } glints(frames(comp, "spark-" + f, f, f + 3), sp, GOLD_L); }
  }
})();
if (ONLY === "legendary-back") (function () {
  var comp = revealComp("legendary-back", 36);
  for (var r = 8; r < 36; r++) {
    seed(3200); var Y = frames(comp, "rays-" + r, r, r + 1, Math.min(28, (r - 7) * 4) * (r < 30 ? 1 : (36 - r) / 6)), rays = [];
    for (var i = 0; i < 26; i++) {
      var a = i / 26 * Math.PI * 2 + r * 0.012, w = between(0.04, 0.09), reach = between(260, 520) * ease((r - 7) / 12);
      var b1 = toEdge(a - w, RW, RH), b2 = toEdge(a + w, RW, RH), tip = toEdge(a, RW, RH) + reach;
      rays.push([[RX + Math.cos(a - w) * b1, RY + Math.sin(a - w) * b1], [RX + Math.cos(a) * tip, RY + Math.sin(a) * tip], [RX + Math.cos(a + w) * b2, RY + Math.sin(a + w) * b2]]);
    }
    polys(Y, rays, GOLD_L);
  }
  for (var f = 0; f < 34; f++) dragon(frames(comp, "back-" + f, f, f + 1), f, false);
})();

// the legendary's reveal, once it has landed, 2.5 s: 60 frames — gold cracks running out from the card across
// everything, soft gold rays, ink flung out from behind it, a great gold ensō, a storm of gold leaf, two great glints
// gold clouds (zuiun): a band of scalloped lobes over a flat foot, a curl in each lobe — w wide, at (x, y), facing
// left or right (dir)
function cloud(x, y, w, lobes, dir) {
  var top = [], curls = [], r = w / lobes / 2;
  for (var i = 0; i < lobes; i++) {
    var cx = x + dir * (r + i * 2 * r), rr = r * (1 - 0.18 * Math.abs(i - lobes / 2) / lobes), cy = y - rr * 0.35;
    for (var q = 0; q <= 10; q++) { var a = Math.PI + q / 10 * Math.PI; top.push([cx + Math.cos(a) * rr * dir, cy + Math.sin(a) * rr]); }
    var c = []; for (var k = 0; k <= 18; k++) { var t = k / 18, ca = Math.PI * 1.1 + t * Math.PI * 1.6, cr = rr * 0.6 * (1 - t * 0.7); c.push([cx + Math.cos(ca) * cr * dir, cy + Math.sin(ca) * cr]); }
    curls.push(c);
  }
  var foot = [[x + dir * w, y + r * 0.35], [x + dir * w * 1.08, y + r * 0.6], [x - dir * w * 0.06, y + r * 0.6], [x, y + r * 0.35]];
  return { shape: top.concat(foot), curls: curls };
}
// the legendary's reveal, once it has landed, 2.5 s: 60 frames — a great vermillion sun rising behind the card,
// ringed in gold; gold clouds drifting in from both sides; gold cracks running out from the card across
// everything; soft gold rays; ink flung out; a great gold ensō; a storm of gold leaf; two great glints
if (ONLY === "reveal-legendary") (function () {
  var comp = revealComp("reveal-legendary", 60);
  for (var u = 0; u < 60; u++) {   // the sun: rising, swelling, fading
    var su = frames(comp, "sun-" + u, u, u + 1, (u < 46 ? 100 : 100 - (u - 46) * 7) * 0.92), sr = 380 * ease((u + 1) / 10) + u * 1.2, sy = RY - 120 - 60 * ease(u / 30);
    polys(su, [circle(RX, sy, sr * 0.97, 1, 72)], SHU);
    lines(su, [circle(RX, sy, sr * 1.04, 1, 72).concat([[RX + sr * 1.04, sy]])], [[GOLD, 10]]);
    lines(su, [circle(RX, sy, sr * 1.13, 1, 72).concat([[RX + sr * 1.13, sy]])], [[GOLD, 4, 70]]);
  }
  for (var y = 0; y < 36; y++) {
    seed(4000); var Y = frames(comp, "rays-" + y, y, y + 1, y < 20 ? 40 : 40 - (y - 20) * 2.5), rays = [];
    for (var i = 0; i < 36; i++) {
      var a = i / 36 * Math.PI * 2 + y * 0.01, w = between(0.03, 0.08), reach = between(450, 900) * ease((y + 1) / 7);
      var b1 = toEdge(a - w, RW, RH), b2 = toEdge(a + w, RW, RH), tip = toEdge(a, RW, RH) + reach;
      rays.push([[RX + Math.cos(a - w) * b1, RY + Math.sin(a - w) * b1], [RX + Math.cos(a) * tip, RY + Math.sin(a) * tip], [RX + Math.cos(a + w) * b2, RY + Math.sin(a + w) * b2]]);
    }
    polys(Y, rays, GOLD_L);
  }
  for (var cl = 0; cl < 60; cl++) {   // the clouds, drifting in from both sides, then on
    var CL = frames(comp, "clouds-" + cl, cl, cl + 1, cl < 46 ? 100 : 100 - (cl - 46) * 7), inn = ease((cl + 1) / 14), dx = (1 - inn) * 700 + cl * 1.5;
    var set = [cloud(RX - 360 - dx, RY + 330, 420, 5, -1), cloud(RX + 360 + dx, RY - 380, 380, 4, 1), cloud(RX - 330 - dx * 1.2, RY - 620, 300, 3, -1), cloud(RX + 330 + dx * 1.2, RY + 640, 340, 4, 1)];
    var shapes = [], curls = [];
    for (var cs = 0; cs < set.length; cs++) { shapes.push(set[cs].shape); curls = curls.concat(set[cs].curls); }
    lines(CL, curls, [[GOLD_D, 5]]);
    gilded(CL, shapes, GOLD, GOLD_D, 4, 6);
  }
  for (var s = 0; s < 22; s++) gilded(frames(comp, "burst-" + s, s, s + 1), inkBurst(RX, RY, 22, RW, RH, 520, 80, 1, s, 4100), INK, GOLD, 5, 7);
  seed(4200);
  var cracks = [];
  for (var c = 0; c < 10; c++) { var ca = c / 10 * Math.PI * 2 + between(-0.2, 0.2), ce = toEdge(ca, RW, RH); cracks = cracks.concat(crackLines(RX + Math.cos(ca) * ce, RY + Math.sin(ca) * ce, ca, between(320, 560), 0.04)); }
  for (var k = 1; k < 48; k++) gold(frames(comp, "cracks-" + k, k, k + 1, k < 38 ? 100 : 100 - (k - 38) * 10), partOf(cracks, ease(k / 14)), 8);
  for (var e = 6; e < 46; e++) {
    seed(4300 + Math.floor(e / 2));
    var E = frames(comp, "enso-" + e, e, e + 1, e < 42 ? 100 : 100 - (e - 41) * 24);
    gilded(E, brushPolys(ensoLine(RX, RY, 560, 1.12, -2.0, Math.PI * 1.8), 90, ease((e - 5) / 9), 0.5, 13, e < 30 ? 0 : (e - 29) / 15), GOLD, GOLD_D, 6, 8);
  }
  for (var l = 2; l < 60; l++) {
    seed(4400); var LL = frames(comp, "leaf-" + l, l, l + 1, l < 46 ? 100 : 100 - (l - 46) * 7), leaf = [], age = l - 2;
    for (var j = 0; j < 64; j++) { var la = between(0, Math.PI * 2), ld = toEdge(la, RW, RH) + between(80, 720) * ease(age / 20); leaf.push([RX + Math.cos(la) * ld, RY + Math.sin(la) * ld + age * age * 0.14 * between(0.5, 1.2), between(10, 24), age * between(-0.2, 0.2), between(0, 6) + age * between(0.2, 0.45)]); }
    flakes(LL, leaf);
  }
  var big = { 2: 0.5, 3: 1, 4: 0.85, 5: 0.6, 6: 0.4, 7: 0.2 }, small = { 28: 0.5, 29: 1, 30: 0.7, 31: 0.4, 32: 0.2 };
  for (var bg in big) glints(frames(comp, "glintA-" + bg, +bg, +bg + 1), [[RX + 200, RY - 270, 170 * big[bg]]], GOLD_L);
  for (var sm in small) glints(frames(comp, "glintB-" + sm, +sm, +sm + 1), [[RX - 195, RY + 270, 120 * small[sm]]], WHITE);
})();

writeLn("comps " + app.project.numItems);

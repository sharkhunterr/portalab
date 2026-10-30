// Magical girl — a transformation in pastel light: magic circles drawing themselves, ribbons spiralling and
// unwinding, hearts, five-pointed stars, cherry petals, iridescent bubbles, sparkles and star flashes.
var PINK = [1, 0.5, 0.78], PINK_L = [1, 0.8, 0.93], LAV = [0.72, 0.56, 1], LAV_L = [0.9, 0.84, 1], CYAN = [0.55, 0.9, 1];
var GOLD = [1, 0.86, 0.42], MINT = [0.6, 1, 0.85], PETAL = [1, 0.74, 0.86], PETAL_D = [0.95, 0.5, 0.7];

function circleOf(fr, cx, cy, r, k, rot, drawn, opacity, color) {   // a magic circle, drawn up to `drawn` (0..1)
  var m = magicCircle(cx, cy, r, k, rot, 6), o = opacity === undefined ? 100 : opacity, c = color || PINK;
  var rings = [], d = clamp01(drawn);
  for (var i = 0; i < m.rings.length; i++) rings.push(m.rings[i].slice(0, Math.max(2, Math.round(m.rings[i].length * d))));
  lines(fr.glow, rings.concat(d > 0.5 ? m.star : []), c, 12, o);
  lines(fr.main, rings, WHITE, 3, o); if (d > 0.5) lines(fr.main, m.star, PINK_L, 2.4, o * (d - 0.5) * 2);
  if (d > 0.8) { lines(fr.main, m.ticks, PINK_L, 2, o); polys(fr.main, m.dots, WHITE, o); }
}
// ribbons wrapped round a box on a helix: two-tone (their face, their back), the near half or the far half
function ribbons(L, glowL, cx, cy, R, H, f, count, front, colors, unwind) {
  for (var k = 0; k < count; k++) {
    var pts = helix(cx, cy, R * (1 + (unwind || 0) * (1.2 + k * 0.3)), H, 1.3 + k * 0.25, f * 0.2 + k * 2.1, 0.22, 70);
    var up = [];
    for (var i = 0; i < pts.length; i++) up.push([pts[i].x, pts[i].y + (unwind || 0) * 200 * (pts[i].u - 0.5)]);
    var both = ribbon(up, 34, 6, f * 0.3 + k, function (i) { return (pts[i].d > 0) === front; }), faceQ = both[0], backQ = both[1];
    polys(glowL, faceQ.concat(backQ), colors[0], 50);
    polys(L, faceQ, colors[0]); polys(L, backQ, colors[1]);
  }
}
function confetti(L, cx, cy, spread, f, start, count, base) {   // hearts, stars and petals falling, turning
  seed(base);
  var hearts = [], stars = [], petals = [], age = f - start;
  if (age < 0) return;
  for (var i = 0; i < count; i++) {
    var a = between(0, Math.PI * 2), sp = between(8, 22), x = cx + Math.cos(a) * sp * age * (1 - age / 90), y = cy + Math.sin(a) * sp * age * (1 - age / 90) + age * age * 0.12 * between(0.5, 1.2);
    var size = between(10, 22), turn = between(0, 6) + age * between(-0.15, 0.15), kind = i % 3;
    if (kind === 0) hearts.push(heart(x, y, size, turn)); else if (kind === 1) stars.push(star5(x, y, size, turn)); else petals.push(place([[0, 0], [size * 0.9, -size * 0.45], [size * 1.4, 0], [size * 0.9, size * 0.45]], x, y, turn, 1, Math.max(0.2, Math.abs(Math.cos(age * 0.2 + i)))));
  }
  polys(L, hearts, PINK); polys(L, stars, GOLD); polys(L, petals, PETAL);
}
function bubbles(fr, cx, cy, spread, f, count, base, opacity) {   // iridescent bubbles drifting up
  seed(base);
  var rims = [], shine = [], tint = [];
  for (var i = 0; i < count; i++) {
    var r = between(10, 34), x = cx + between(-spread, spread) + Math.sin(f * 0.1 + i) * 14, y = cy + spread - ((f * between(3, 7) + between(0, spread * 2)) % (spread * 2));
    rims.push(ring(x, y, r, 1)); shine.push(ring(x, y, r * 0.72, 1, -2.6, -1.6)); tint.push(circle(x, y, r, 1, 24));
  }
  var o = opacity === undefined ? 100 : opacity;
  polys(fr.main, tint, i % 2 ? CYAN : LAV_L, 14 * o / 100);
  lines(fr.glow, rims, CYAN, 6, o * 0.6); lines(fr.main, rims, WHITE, 2, o * 0.8); lines(fr.top, shine, WHITE, 3, o);
}
function sparkles(L, cx, cy, spread, f, count, base, size) {
  seed(base);
  var pts = [];
  for (var i = 0; i < count; i++) pts.push([cx + between(-spread, spread), cy + between(-spread, spread) * 1.2]);
  polys(L, glintPolys(twinkle(pts, f, base, size || 22)), WHITE);
}

// --- the opening: 1152 x 1080, the pack at (576, 505), 240 x 355 — 64 frames ------------------------------
// A magic circle draws itself round the pack; ribbons spiral round it, hearts and sparkles rising; a star flash —
// the pack gone —, a ring of light, the ribbons unwinding away, a shower of hearts, stars, petals and bubbles.
if (ONLY === "opening") (function () {
  var comp = newComp("opening", 1152, 1080, 64), cx = 576, cy = 505;
  for (var f = 0; f < 64; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var co = fade(f, 40, 60) * 100;
    circleOf(fr, cx, cy, 360, 1, f * 0.03, ease(f / 14), co);
    if (f < 50) {
      var unwind = f < 26 ? 0 : ease((f - 26) / 20), ro = fade(f, 40, 50) * 100;
      // their far half shows once the pack is gone (this layer is over the pack)
      if (f >= 26) ribbons(fr.main, fr.glow, cx, cy, 175 - 25 * ease(f / 26), 470, f, 3, false, [PINK, PINK_L], unwind);
      ribbons(fr.top, fr.glow, cx, cy, 175 - 25 * ease(f / 26), 470, f, 3, true, [LAV, LAV_L], unwind);
    }
    if (f > 4 && f < 30) { seed(100); var hs = []; for (var i = 0; i < 10; i++) hs.push(heart(cx + between(-240, 240), cy + 220 - ((f - 4) * between(8, 16)) % 480, between(10, 18), Math.sin(f * 0.2 + i) * 0.3)); polys(fr.top, hs, PINK); polys(fr.glow, hs, PINK_L, 60); }
    sparkles(fr.top, cx, cy, 330, f, 24, 200, 20);
    if (f >= 25 && f < 34) {
      var t = f - 25, k = t < 3 ? (t + 1) / 3 : 1 - (t - 2) / 7;
      polys(fr.haze, [circle(cx, cy, 260 * k, 1, 40)], PINK_L, 90);
      polys(fr.glow, glintPolys([[cx, cy, 420 * k]]), WHITE); polys(fr.main, [star5(cx, cy, 170 * k, t * 0.1)], GOLD, 90); polys(fr.top, glintPolys([[cx, cy, 260 * k]]), WHITE);
    }
    if (f >= 26 && f < 44) { var rr = 120 + (f - 26) * 30, ro2 = fade(f, 34, 44) * 100; lines(fr.glow, [ring(cx, cy, rr, 1)], PINK, 16, ro2); lines(fr.main, [ring(cx, cy, rr, 1)], WHITE, 6, ro2, false, [0.1, 18]); }
    if (f >= 26) { confetti(fr.main, cx, cy, 0, f, 26, 46, 300); bubbles(fr, cx, cy, 380, f, 14, 400, fade(f, 52, 63) * 100); }
  }
})();

// --- the reveals: 832 x 1154, the card in the middle, 320 x 444 — behind the card --------------------------
var RX = 416, RY = 577, RW = 160, RH = 222;
function revealComp(name, count) { return newComp(name, 832, 1154, count); }

// rare, 1.8 s: 44 frames — a ring of light, iridescent bubbles drifting up round the card, sparkles
if (ONLY === "reveal-rare") (function () {
  var comp = revealComp("reveal-rare", 44);
  for (var f = 0; f < 44; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f < 14) { var rr = 230 + f * 26, ro = fade(f, 6, 14) * 100; lines(fr.glow, [ring(RX, RY, rr, 1.2)], CYAN, 16, ro); lines(fr.main, [ring(RX, RY, rr, 1.2)], WHITE, 5, ro, false, [0.1, 16]); }
    if (f < 10) polys(fr.haze, [circle(RX, RY, 300, 1.3, 40)], LAV_L, 70 - f * 7);
    bubbles(fr, RX, RY, 330, f, 22, 1000, fade(f, 32, 43) * 100);
    sparkles(fr.top, RX, RY, 300, f, 18, 1100, 22);
  }
})();

// epic, 2.4 s: 58 frames — two ribbons whirling round the card, a burst of hearts and petals, sparkles
if (ONLY === "reveal-epic") (function () {
  var comp = revealComp("reveal-epic", 58);
  for (var f = 0; f < 58; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f < 8) polys(fr.haze, [circle(RX, RY, 320, 1.3, 40)], PINK_L, 80 - f * 10);
    if (f < 46) ribbons(fr.main, fr.glow, RX, RY, 230 + 40 * ease(f / 12), 560, f, 2, false, [PINK, PINK_L], f > 30 ? ease((f - 30) / 14) : 0);
    confetti(fr.main, RX, RY, 0, f, 2, 40, 2000);
    sparkles(fr.top, RX, RY, 320, f, 22, 2100, 24);
  }
})();

// the legendary, 3 s: 72 frames — a giant magic circle turning behind the card, pastel rays, ribbons wrapping it
// (over the card in ``legendary-over``), a rain of stars, great star glints
if (ONLY === "legendary") (function () {
  var comp = revealComp("legendary", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, 52, 70) * 100;
    if (f < 60) { seed(3000); polys(fr.haze, rays(16, RX, RY, RW, RH, 480, 0.08, f * 0.01), PINK_L, Math.min(60, f * 10) * fade(f, 44, 60)); }
    circleOf(fr, RX, RY, 390, 1, f * 0.025, ease(f / 12), o, PINK);
    circleOf(fr, RX, RY, 300, 1, -f * 0.04 + 0.5, ease((f - 4) / 12), o, LAV);
    if (f < 58) ribbons(fr.main, fr.glow, RX, RY, 230, 600, f, 3, false, [PINK, PINK_L], f > 42 ? ease((f - 42) / 14) : 0);
    seed(3100); var st = [];
    for (var i = 0; i < 26; i++) { var x = RX + between(-400, 400), y = -60 + ((f * between(10, 20) + between(0, 1300)) % 1300); st.push(star5(x, y, between(8, 18), f * 0.1 + i)); }
    polys(fr.glow, st, GOLD, 70 * o / 100); polys(fr.main, st, GOLD, o);
    sparkles(fr.top, RX, RY, 340, f, 24, 3200, 26);
  }
})();
if (ONLY === "legendary-over") (function () {
  var comp = revealComp("legendary-over", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f < 58) ribbons(fr.main, fr.glow, RX, RY, 230, 600, f, 3, true, [LAV, LAV_L], f > 42 ? ease((f - 42) / 14) : 0);
    if (f > 6 && f < 50) { seed(3300); var hs = []; for (var i = 0; i < 8; i++) hs.push(heart(RX + between(-RW, RW), RY + RH - ((f - 6) * between(9, 16)) % (RH * 2.4), between(10, 20), Math.sin(f * 0.2 + i) * 0.3)); polys(fr.glow, hs, PINK_L, 60); polys(fr.top, hs, PINK); }
    var big = { 3: 0.5, 4: 1, 5: 0.85, 6: 0.6, 7: 0.35 }[f], small = { 30: 0.5, 31: 1, 32: 0.7, 33: 0.4 }[f];
    if (big) { polys(fr.glow, glintPolys([[RX + 170, RY - 235, 170 * big]]), PINK_L); polys(fr.top, glintPolys([[RX + 170, RY - 235, 120 * big]]), WHITE); }
    if (small) { polys(fr.glow, [star5(RX - 165, RY + 240, 90 * small, 0)], GOLD); polys(fr.top, glintPolys([[RX - 165, RY + 240, 80 * small]]), WHITE); }
  }
})();

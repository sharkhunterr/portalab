// Shōnen — a fighting aura: power flaring round the pack or the card in flat flames (outer, inner, white-hot
// core), rocks torn from the ground and levitating, ki lightning crackling, concentration lines, a pillar of
// light, shockwaves, dust and embers.
var AURA = {
  orange: [[1, 0.42, 0.06], [1, 0.72, 0.18], [1, 0.96, 0.78]],
  blue: [[0.15, 0.45, 1], [0.45, 0.8, 1], [0.9, 0.98, 1]],
  violet: [[0.55, 0.18, 1], [0.8, 0.5, 1], [0.97, 0.9, 1]],
  gold: [[1, 0.62, 0.05], [1, 0.86, 0.3], [1, 0.99, 0.85]]
};
var ROCK = [[0.2, 0.17, 0.19], [0.42, 0.37, 0.38]], DUST = [[0.56, 0.48, 0.42], [0.36, 0.3, 0.27]];

// the aura round a box, three tones, its glow under it
// `hole`: the box itself left clear (the opening's aura is drawn over the pack)
function flare(fr, cx, cy, hw, hh, amp, phase, tones, opacity, hole) {
  var a = aura(cx, cy, hw, hh, amp, phase, 3), o = opacity === undefined ? 100 : opacity;
  var box = hole ? [[cx - hw, cy - hh], [cx + hw, cy - hh], [cx + hw, cy + hh], [cx - hw, cy + hh]] : null;
  var cut = function (p) { return box ? [p, box] : [p]; };
  polys(fr.haze, cut(a[0]), tones[0], o * 0.9, !!box);
  polys(fr.glow, cut(a[0]), tones[1], o * 0.6, !!box);
  polys(fr.main, cut(a[2]), tones[2], o * 0.85, !!box); polys(fr.main, cut(a[1]), tones[1], o * 0.7, !!box); polys(fr.main, cut(a[0]), tones[0], o * 0.55, !!box);
}
// ki lightning round a box: a few bolts from its edge outwards, white cores in a coloured glow
function crackle(fr, cx, cy, hw, hh, count, reach, color, f) {
  seed(900 + f * 7);
  var all = [];
  for (var i = 0; i < count; i++) {
    var a = between(0, Math.PI * 2), r0 = toEdge(a, hw, hh) * 0.95, r1 = r0 + reach * between(0.5, 1);
    all = all.concat(bolt(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0, cx + Math.cos(a + between(-0.3, 0.3)) * r1, cy + Math.sin(a + between(-0.3, 0.3)) * r1, 16, true));
  }
  lines(fr.glow, all, color, 12);
  lines(fr.top, all, WHITE, 2.6);
}
// rocks: each {x, y, size, turn}, inked, lit on top
function rocks(L, list) {
  var bodies = [], lit = [];
  for (var i = 0; i < list.length; i++) { var r = rockPoly(list[i].x, list[i].y, list[i].size, list[i].turn); bodies.push(r.body); lit.push(r.lit); }
  polys(L, lit, ROCK[1]); inked(L, bodies, ROCK[0], 4);
}
function embers(L, cx, cy, spread, f, count, color, base) {
  seed(base);
  var list = [];
  for (var i = 0; i < count; i++) {
    var x = cx + between(-spread, spread), speed = between(3, 9), y = cy + spread * 0.6 - ((f * speed + between(0, 400)) % (spread * 1.6));
    list.push(circle(x + Math.sin(f * 0.2 + i) * 8, y, between(2, 5), 1, 10));
  }
  polys(L, list, color);
}

// --- the opening: 1152 x 1080, the pack at (576, 505), 240 x 355 — 64 frames ------------------------------
// Power gathers round the pack: its aura flares higher and higher, rocks tear off the ground and float up, ki
// lightning crackles, concentration lines close in; at 1.1 s a pillar of light shoots up out of it — the pack
// gone — a white impact, shockwaves cracking the ground in dust, rocks flung away, embers rising.
if (ONLY === "opening") (function () {
  var comp = newComp("opening", 1152, 1080, 64), cx = 576, cy = 505, hw = 120, hh = 177, ground = cy + hh + 30;
  seed(10);
  var stones = [];
  for (var i = 0; i < 12; i++) stones.push({ x: cx + (i % 2 ? 1 : -1) * between(hw + 40, 440), y: ground + between(-20, 60), size: between(14, 34), turn: between(0, 6), lift: between(80, 260), delay: between(0, 10), spin: between(-0.06, 0.06) });
  for (var f = 0; f < 64; f++) {
    var fr = frameOf(comp, f);
    if (!fr.main) continue;
    var charge = ease(f / 26), on = f < 27;
    if (on) {
      flare(fr, cx, cy, hw, hh, 40 + 170 * charge, f, AURA.orange, 100, true);
      if (f > 8) crackle(fr, cx, cy, hw, hh, 2 + Math.floor(charge * 4), 90 + 80 * charge, AURA.orange[1], f);
      if (f > 10) { seed(300 + f); polys(fr.main, concentration(cx, cy, 70, 330 - 60 * charge, 900, 9), WHITE, 22 + 20 * charge); }
    }
    // the rocks: lifting while it charges, flung away when it bursts
    var list = [];
    for (var k = 0; k < stones.length; k++) {
      var s = stones[k], up = ease((f - s.delay) / 22) * s.lift, x = s.x, y = s.y - up + Math.sin(f * 0.3 + k) * 4;
      if (f >= 27) { var t = f - 27, dx = x - cx, dy = y - cy, d = Math.sqrt(dx * dx + dy * dy) || 1; x += dx / d * t * 22; y += dy / d * t * 22 - t * 6 + t * t * 0.6; }
      if (f < 50) list.push({ x: x, y: y, size: s.size, turn: s.turn + f * s.spin });
    }
    rocks(f < 27 ? fr.main : fr.top, list);
    // the pillar of light, then the impact
    if (f >= 25 && f < 52) {
      var p = f < 28 ? (f - 24) / 4 : 1, w = (f < 30 ? 60 + (f - 25) * 40 : 260 - (f - 30) * 9) * p, o = fade(f, 40, 52) * 100;
      var beam = [[cx - w / 2, -60], [cx + w / 2, -60], [cx + w * 0.62, ground], [cx - w * 0.62, ground]];
      polys(fr.haze, [beam], AURA.orange[1], o); polys(fr.glow, [beam], AURA.gold[2], o);
      polys(fr.main, [[[cx - w * 0.18, -60], [cx + w * 0.18, -60], [cx + w * 0.24, ground], [cx - w * 0.24, ground]]], WHITE, o);
    }
    if (f >= 26 && f < 32) { seed(400); var b = 1 + (f - 26) * 0.5; polys(fr.glow, [burst(cx, cy + 40, 16, 330 * b, 150 * b, 0.4, 0.1)], AURA.orange[1], 90); inked(fr.main, [burst(cx, cy + 40, 16, 260 * b, 120 * b, 0.4, 0.1)], WHITE, 6, fade(f, 29, 32) * 100); }
    if (f >= 27 && f < 50) {
      for (var w2 = 0; w2 < 3; w2++) {
        var age = f - 27 - w2 * 5; if (age < 0) continue;
        var rr = 90 + age * 40, oo = fade(age, 6, 16) * 100;
        lines(fr.glow, [ring(cx, ground, rr, 0.28)], AURA.gold[1], 16, oo); lines(fr.main, [ring(cx, ground, rr, 0.28)], WHITE, 3, oo);
      }
      seed(500); var dust = [], shadow = [];
      for (var d2 = 0; d2 < 9; d2++) { var da = between(-0.3, Math.PI + 0.3), dd = 60 + (f - 27) * between(10, 22), pf = puff(cx + Math.cos(da) * dd * 1.6, ground - Math.abs(Math.sin(da)) * dd * 0.5, 40 + (f - 27) * 3, 5); dust = dust.concat(pf[0]); shadow = shadow.concat(pf[1]); }
      polys(fr.main, dust, DUST[0], fade(f, 38, 50) * 80); polys(fr.main, shadow, DUST[1], fade(f, 38, 50) * 80);
    }
    if (f >= 27) embers(fr.glow, cx, cy, 380, f, 40, AURA.orange[1], 600);
    if (f >= 27) embers(fr.top, cx, cy, 380, f, 40, AURA.gold[2], 600);
  }
})();

// --- the reveals: 832 x 1154, the card in the middle, 320 x 444 — behind the card --------------------------
var RX = 416, RY = 577, RW = 160, RH = 222;
function revealComp(name, count) { return newComp(name, 832, 1154, count); }

// rare, 1.8 s: 44 frames — a blue aura flaring round the card, ki lightning, a shockwave, blue embers rising
if (ONLY === "reveal-rare") (function () {
  var comp = revealComp("reveal-rare", 44);
  for (var f = 0; f < 44; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var grow = ease((f + 1) / 6), o = fade(f, 28, 42) * 100;
    flare(fr, RX, RY, RW, RH, 48 + 118 * grow, f, AURA.blue, o);
    if (f > 2 && f < 34) crackle(fr, RX, RY, RW, RH, 3, 120, AURA.blue[1], f);
    if (f < 14) { var rr = 230 + f * 26; lines(fr.glow, [ring(RX, RY, rr, 1.2)], AURA.blue[1], 18, fade(f, 4, 14) * 100); lines(fr.main, [ring(RX, RY, rr, 1.2)], WHITE, 3, fade(f, 4, 14) * 100); }
    embers(fr.glow, RX, RY, 330, f, 30, AURA.blue[1], 1100);
    embers(fr.main, RX, RY, 330, f, 30, AURA.blue[2], 1100);
  }
})();

// epic, 2.4 s: 58 frames — a violet aura, rocks torn off and levitating round the card, lightning, concentration
// lines, an impact
if (ONLY === "reveal-epic") (function () {
  var comp = revealComp("reveal-epic", 58);
  seed(2000);
  var stones = [];
  for (var i = 0; i < 9; i++) { var a = i / 9 * Math.PI * 2 + between(-0.2, 0.2); stones.push({ a: a, d: between(250, 330), size: between(18, 38), turn: between(0, 6), spin: between(-0.05, 0.05) }); }
  for (var f = 0; f < 58; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var grow = ease((f + 1) / 6), o = fade(f, 40, 56) * 100;
    flare(fr, RX, RY, RW, RH, 56 + 150 * grow, f, AURA.violet, o);
    if (f < 44) crackle(fr, RX, RY, RW, RH, 4, 150, AURA.violet[1], f);
    if (f < 30) { seed(2100 + f); polys(fr.main, concentration(RX, RY, 60, 300, 760, 8), WHITE, fade(f, 16, 30) * 30); }
    if (f < 6) { seed(2200); polys(fr.glow, [burst(RX, RY, 14, 360 + f * 30, 200, 0.4, 0)], AURA.violet[1], 80 - f * 12); }
    var list = [];
    for (var k = 0; k < stones.length; k++) { var s = stones[k], rise = ease(f / 14) * 40, a2 = s.a + f * 0.012; list.push({ x: RX + Math.cos(a2) * s.d * 1.05, y: RY + Math.sin(a2) * s.d * 1.25 - rise + Math.sin(f * 0.25 + k) * 6, size: s.size * Math.min(1, ease(f / 6) * 1.1), turn: s.turn + f * s.spin }); }
    if (f < 50) rocks(fr.main, list);
    embers(fr.glow, RX, RY, 340, f, 30, AURA.violet[1], 2300);
  }
})();

// the legendary, 3 s: 72 frames — a golden aura exploding round the card, a pillar of light behind it,
// shockwaves, rocks, embers; over the card (``legendary-over``): lightning crossing it, embers, great glints
function legendaryRocks(f, front) {
  seed(3000);
  var out = [];
  for (var i = 0; i < 12; i++) {
    var a = i / 12 * Math.PI * 2 + between(-0.2, 0.2) + f * 0.02, near = Math.sin(a) > 0.2, d = between(300, 380);
    if (near !== front) continue;
    out.push({ x: RX + Math.cos(a) * d, y: RY + Math.sin(a) * d * 0.45 + 120 - ease(f / 20) * 160 + Math.sin(f * 0.2 + i) * 6, size: between(18, 36) * (near ? 1.2 : 0.9), turn: i + f * 0.04 });
  }
  return out;
}
if (ONLY === "legendary") (function () {
  var comp = revealComp("legendary", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var grow = ease((f + 1) / 5), o = fade(f, 50, 70) * 100;
    if (f >= 2 && f < 56) {
      var p = ease((f - 2) / 5), w = (170 + 40 * Math.sin(f * 0.6)) * p, po = fade(f, 40, 56) * 100;
      var beam = [[RX - w / 2, -80], [RX + w / 2, -80], [RX + w * 0.7, 1234], [RX - w * 0.7, 1234]];
      polys(fr.haze, [beam], AURA.gold[1], po); polys(fr.glow, [beam], AURA.gold[2], po * 0.8);
    }
    flare(fr, RX, RY, RW, RH, 70 + 200 * grow, f, AURA.gold, o);
    if (f < 8) { seed(3100); polys(fr.glow, [burst(RX, RY, 18, 420 + f * 40, 220, 0.4, 0)], AURA.gold[1], 90 - f * 11); }
    for (var w2 = 0; w2 < 3; w2++) { var age = f - w2 * 6; if (age < 0 || age > 18) continue; var rr = 240 + age * 30; lines(fr.glow, [ring(RX, RY, rr, 1.2)], AURA.gold[1], 20, fade(age, 8, 18) * 100); lines(fr.main, [ring(RX, RY, rr, 1.2)], WHITE, 3.5, fade(age, 8, 18) * 100); }
    if (f < 60) rocks(fr.main, legendaryRocks(f, false));
    embers(fr.glow, RX, RY, 360, f, 40, AURA.gold[1], 3200);
    embers(fr.main, RX, RY, 360, f, 30, AURA.gold[2], 3300);
  }
})();
if (ONLY === "legendary-over") (function () {
  var comp = revealComp("legendary-over", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f > 4 && f < 48 && f % 3 !== 2) {
      seed(3400 + f);
      var x0 = RX + between(-RW, RW), all = bolt(x0, RY - RH - 60, x0 + between(-120, 120), RY + RH + 60, 22, true);
      lines(fr.glow, all, AURA.gold[1], 14, 90); lines(fr.top, all, WHITE, 3);
    }
    if (f < 60) rocks(fr.main, legendaryRocks(f, true));
    embers(fr.glow, RX, RY + 100, 300, f, 18, AURA.gold[1], 3500);
    embers(fr.top, RX, RY + 100, 300, f, 18, AURA.gold[2], 3500);
    var big = { 3: 0.5, 4: 1, 5: 0.85, 6: 0.6, 7: 0.35 }[f], small = { 30: 0.5, 31: 1, 32: 0.7, 33: 0.4 }[f];
    if (big) { polys(fr.glow, glintPolys([[RX + 170, RY - 235, 160 * big]]), AURA.gold[1]); polys(fr.top, glintPolys([[RX + 170, RY - 235, 120 * big]]), WHITE); }
    if (small) polys(fr.top, glintPolys([[RX - 165, RY + 240, 90 * small]]), WHITE);
  }
})();

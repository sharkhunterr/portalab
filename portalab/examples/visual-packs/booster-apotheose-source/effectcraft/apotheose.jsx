// Apothéose — every rarity staged over the whole screen (``place: screen``), like an animated trading card
// game's reveals: square comps (1080, played cropped to cover any screen) drawn round the middle, where Portalab
// brings the card, big — behind it (``reveal-*``) and over it (``over-*``). Built on the manga toolkit
// (../booster-manga-source/effectcraft/core.jsx). The rarity's name is Portalab's, written over them.
var PINK = [1, 0.18, 0.47], PINK_L = [1, 0.62, 0.78], CYAN = [0.2, 0.86, 1], CYAN_L = [0.72, 0.96, 1], NAVY = [0.03, 0.06, 0.16];
var ORANGE = [1, 0.45, 0.06], GOLD = [1, 0.8, 0.22], GOLD_L = [1, 0.95, 0.7], VIOLET = [0.42, 0.12, 0.85], INK = [0.05, 0.02, 0.08];
var C = 540;   // the middle of the square comps

function square(name, count) { return newComp(name, 1080, 1080, count); }
function full() { return [[-60, -60], [1140, -60], [1140, 1140], [-60, 1140]]; }
// wedges from the middle reaching past the corners, in turns of colours, turning
function spikes(L, n, turn, colors, base, reach) {
  for (var c = 0; c < colors.length; c++) {
    seed(base + c);
    var list = [];
    for (var i = 0; i < n; i++) {
      var a = (i + c / colors.length + between(-0.12, 0.12)) / n * Math.PI * 2 + turn, w = Math.PI / n / colors.length * between(0.7, 1.3), r = (reach || 1100) * between(0.7, 1);
      list.push([[C, C], [C + Math.cos(a - w) * r, C + Math.sin(a - w) * r], [C + Math.cos(a + w) * r * 1.05, C + Math.sin(a + w) * r * 1.05]]);
    }
    polys(L, list, colors[c][0], colors[c][1]);
  }
}
// a brush slash across the screen: fat early, tapering to a point, its trailing edge torn — along (x0,y0)→(x1,y1)
function slash(x0, y0, x1, y1, thick, upto, bend) {
  var top = [], bot = [], n = 36, dx = x1 - x0, dy = y1 - y0, l = Math.sqrt(dx * dx + dy * dy), nx = -dy / l, ny = dx / l;
  for (var i = 0; i <= n * clamp01(upto); i++) {
    var u = i / n, w = Math.pow(Math.sin(Math.PI * Math.pow(u, 0.55)), 0.7) * thick, off = (bend || 0) * Math.sin(Math.PI * u) * l * 0.08;
    var x = x0 + dx * u + nx * off, y = y0 + dy * u + ny * off;
    top.push([x + nx * w, y + ny * w]);
    bot.push([x - nx * w * (u < 0.7 && i % 2 ? between(0.3, 1) : 1), y - ny * w * (u < 0.7 && i % 2 ? between(0.3, 1) : 1)]);
  }
  return top.length > 1 ? [top.concat(bot.reverse())] : [];
}
// sparks thrown out of the card's edges: short streaks flying away, fading — the middle left clear
function sparks(L, glowL, f, count, color, base, speed) {
  seed(base);
  var list = [];
  for (var i = 0; i < count; i++) {
    var a = between(0, Math.PI * 2), start = between(0, 14), age = f - start;
    if (age < 0) continue;
    var r0 = toEdge(a, 150, 210) + age * (speed || 22) * between(0.7, 1.3), len = between(20, 60);
    if (r0 > 760) continue;
    list.push([[C + Math.cos(a) * r0, C + Math.sin(a) * r0], [C + Math.cos(a) * (r0 + len), C + Math.sin(a) * (r0 + len)]]);
  }
  lines(glowL, list, color, 10); lines(L, list, WHITE, 3);
}
// speed streaks sweeping in from the screen's edges towards the middle
function inrush(L, f, count, base, opacity) {
  seed(base + Math.floor(f / 2));
  polys(L, concentration(C, C, count, 330 + 40 * Math.sin(f * 0.7), 900, 10), WHITE, opacity);
}

// --- the opening: 1152 x 1080, the pack at (576, 505), 240 x 355 — 64 frames ---------------------------------
// The pack lifts, light leaking from its seams; a beam of light strikes down through it and slices it in two,
// pink flames licking up its cut; a white flash, then a burst of pink, white and violet spikes over everything,
// glints flying, as the cards come out.
if (ONLY === "opening") (function () {
  var comp = newComp("opening", 1152, 1080, 64), cx = 576, cy = 505, hw = 120, hh = 177;
  for (var f = 0; f < 64; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f < 22) { seed(10); polys(fr.glow, rays(16, cx, cy, hw, hh, 80 + f * 12, 0.05, f * 0.01), PINK_L, 40 + f * 2); }
    if (f >= 10 && f < 34) {   // the beam: a vertical blade of light, widening then narrowing
      var w = f < 18 ? (f - 9) * 7 : Math.max(0, 70 - (f - 18) * 4.5), beam = [[cx - w / 2, -40], [cx + w / 2, -40], [cx + w / 2, 1120], [cx - w / 2, 1120]];
      polys(fr.haze, [beam], PINK, 100); polys(fr.glow, [beam], PINK_L, 90); polys(fr.main, [[[cx - w * 0.15, -40], [cx + w * 0.15, -40], [cx + w * 0.15, 1120], [cx - w * 0.15, 1120]]], WHITE);
      if (f >= 14) {   // pink flames licking up the cut
        seed(20 + Math.floor(f / 2)); var tongues = [];
        for (var k = 0; k < 9; k++) { var y = cy + hh - k * 42 + between(-10, 10), h = between(30, 70); tongues.push([[cx - 16, y], [cx + between(-30, 30), y - h], [cx + 16, y]]); }
        polys(fr.glow, tongues, PINK, 90); polys(fr.main, tongues, PINK_L);
      }
    }
    if (f >= 24 && f < 29) { var k2 = f - 24; polys(fr.haze, [circle(cx, cy, 300 + k2 * 120, 1, 40)], WHITE, 100 - k2 * 18); polys(fr.main, [full()], WHITE, 70 - k2 * 16); }
    if (f >= 25 && f < 58) {
      var g = ease((f - 24) / 6), o = fade(f, 44, 58) * 100;
      seed(30); spikes(fr.main, 18, (f - 25) * 0.012, [[PINK, o], [WHITE, o * 0.9], [VIOLET, o]], 31, 260 + 760 * g);
      inrush(fr.top, f, 60, 40, o * 0.35);
      sparks(fr.top, fr.glow, f - 25, 40, PINK_L, 50, 26);
    }
  }
})();

// --- the reveals, behind the card ----------------------------------------------------------------------------
// rare, 1.8 s: a cyan flash, cyan and white spikes turning over a deep blue, a ring of light, glints
if (ONLY === "reveal-rare") (function () {
  var comp = square("reveal-rare", 44);
  for (var f = 0; f < 44; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, 30, 43) * 100, g = ease((f + 1) / 5);
    spikes(fr.main, 16, f * 0.01, [[CYAN, o * 0.85], [WHITE, o * 0.5], [[0.1, 0.35, 0.8], o]], 100, 300 + 800 * g);
    polys(fr.main, [full()], NAVY, o * 0.88);
    if (f < 5) polys(fr.top, [full()], WHITE, 90 - f * 18);
    if (f < 18) { var rr = 220 + f * 34; lines(fr.glow, [ring(C, C, rr, 1)], CYAN, 22, fade(f, 8, 18) * 100); lines(fr.main, [ring(C, C, rr, 1)], WHITE, 4, fade(f, 8, 18) * 100); }
    polys(fr.glow, [circle(C, C, 300, 1.3, 40)], CYAN, o * 0.6);
  }
})();
// epic, 2.4 s: the screen explodes in pink, white and black spikes, two slashes crossing, shards, a pink glow
if (ONLY === "reveal-epic") (function () {
  var comp = square("reveal-epic", 58);
  for (var f = 0; f < 58; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, 42, 57) * 100, g = ease((f + 1) / 4);
    spikes(fr.main, 20, f * 0.014 + Math.sin(f * 0.3) * 0.02, [[PINK, o], [WHITE, o * 0.95], [[0.55, 0.05, 0.25], o]], 200, 250 + 900 * g);
    polys(fr.main, [full()], INK, o * 0.9);
    polys(fr.haze, [circle(C, C, 340, 1.3, 40)], PINK, o * 0.8);
    if (f < 4) polys(fr.top, [full()], WHITE, 100 - f * 25);
    if (f >= 2 && f < 22) {
      var u = ease((f - 1) / 4), so = fade(f, 12, 22) * 100;
      polys(fr.top, slash(-80, 860, 1160, 180, 70, u, 1), WHITE, so);
      if (f >= 5) polys(fr.top, slash(1160, 900, -80, 220, 56, ease((f - 4) / 4), -1), PINK_L, so);
    }
  }
})();
// legendary, 3 s: orange bands slashing across the screen, cracked with white lightning; a flash; then black with
// orange and gold spikes turning, gold rays, rings of light, halftone, a golden glow
if (ONLY === "reveal-legendary") (function () {
  var comp = square("reveal-legendary", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, 56, 71) * 100;
    if (f < 16) {   // the orange bands, slanted, sliding in
      var slide = ease((f + 1) / 6) * 1;
      for (var b = 0; b < 4; b++) {
        var y0 = -200 + b * 360, x = -1400 + slide * 1400 + b * 60;
        polys(fr.main, [[[x, y0 + 260], [x + 1400, y0 - 260], [x + 1400 + 300, y0 - 260], [x + 300, y0 + 260]]], b % 2 ? GOLD : ORANGE, 100);
      }
      polys(fr.main, [full()], [0.12, 0.03, 0.02], 100);
      if (f > 4) { seed(300 + f); var cracks = []; for (var k = 0; k < 4; k++) cracks = cracks.concat(bolt(between(100, 980), -20, between(100, 980), 1100, 50, true)); lines(fr.glow, cracks, GOLD_L, 14); lines(fr.top, cracks, WHITE, 3.5); }
    }
    if (f >= 14 && f < 19) polys(fr.top, [full()], WHITE, 100 - (f - 14) * 20);
    if (f >= 14) {
      var g = ease((f - 13) / 5);
      spikes(fr.main, 22, (f - 14) * 0.012, [[ORANGE, o], [GOLD, o * 0.9], [[0.45, 0.12, 0.02], o]], 400, 260 + 900 * g);
      seed(410); polys(fr.glow, rays(14, C, C, 0, 0, 900, 0.04, (f - 14) * -0.008), GOLD_L, o * 0.5);
      for (var w = 0; w < 3; w++) { var age = f - 14 - w * 7; if (age < 0 || age > 22) continue; var rr = 240 + age * 30; lines(fr.glow, [ring(C, C, rr, 1)], GOLD, 24, fade(age, 10, 22) * o); lines(fr.main, [ring(C, C, rr, 1)], WHITE, 4, fade(age, 10, 22) * o); }
      lines(fr.main, halftoneRows(C, C, 420, 760, 28), GOLD, 9 * (1 - (f - 14) / 70), o * 0.35, false, [0.1, 28]);
      polys(fr.main, [full()], INK, o * 0.92);
      polys(fr.haze, [circle(C, C, 360, 1.3, 40)], ORANGE, o * 0.9);
    }
  }
})();

// --- over the card ---------------------------------------------------------------------------------------------
// rare: a white streak crossing it, sparks and glints thrown off its edges
if (ONLY === "over-rare") (function () {
  var comp = square("over-rare", 44);
  for (var f = 0; f < 44; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f >= 1 && f < 9) polys(fr.top, slash(80, 760, 1000, 320, 34, ease(f / 4), 0.6), WHITE, fade(f, 4, 9) * 100);
    sparks(fr.main, fr.glow, f, 36, CYAN, 1200, 20);
    seed(1300); var pts = []; for (var i = 0; i < 14; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 160, 220) + between(10, 120); pts.push([C + Math.cos(a) * r, C + Math.sin(a) * r]); }
    polys(fr.top, glintPolys(twinkle(pts, f, 1, 26)), WHITE);
  }
})();
// epic: a great white slash across it, pink speed lines rushing in, sparks, glints
if (ONLY === "over-epic") (function () {
  var comp = square("over-epic", 58);
  for (var f = 0; f < 58; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f >= 1 && f < 12) { var so = fade(f, 6, 12) * 100; polys(fr.glow, slash(-40, 820, 1120, 260, 70, ease(f / 3), 1), PINK, so); polys(fr.top, slash(-40, 820, 1120, 260, 50, ease(f / 3), 1), WHITE, so); }
    if (f < 34) inrush(fr.main, f, 70, 1400, fade(f, 20, 34) * 40);
    sparks(fr.main, fr.glow, f, 50, PINK, 1500, 24);
    var big = { 8: 0.5, 9: 1, 10: 0.8, 11: 0.5, 12: 0.25 }[f];
    if (big) { polys(fr.glow, glintPolys([[C + 150, C - 210, 170 * big]]), PINK_L); polys(fr.top, glintPolys([[C + 150, C - 210, 120 * big]]), WHITE); }
  }
})();
// legendary: a slash of light cutting across it, gold lightning crawling its edges, embers, two great glints
if (ONLY === "over-legendary") (function () {
  var comp = square("over-legendary", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f >= 14 && f < 24) { var so = fade(f, 19, 24) * 100, u = ease((f - 13) / 3); polys(fr.glow, slash(1120, 780, -40, 300, 80, u, -1), GOLD, so); polys(fr.top, slash(1120, 780, -40, 300, 58, u, -1), WHITE, so); }
    if (f >= 16 && f < 56) {
      seed(1600 + f); var arcs = [];
      for (var k = 0; k < 3; k++) { var a = between(0, Math.PI * 2), a2 = a + between(0.4, 0.9), r = toEdge(a, 160, 222), r2 = toEdge(a2, 160, 222); arcs = arcs.concat(bolt(C + Math.cos(a) * r, C + Math.sin(a) * r, C + Math.cos(a2) * r2, C + Math.sin(a2) * r2, 24, true)); }
      lines(fr.glow, arcs, GOLD, 14, fade(f, 46, 56) * 100); lines(fr.top, arcs, WHITE, 3, fade(f, 46, 56) * 100);
    }
    if (f >= 14) sparks(fr.main, fr.glow, f - 14, 60, ORANGE, 1700, 22);
    var big = { 18: 0.5, 19: 1, 20: 0.85, 21: 0.6, 22: 0.3 }[f], small = { 40: 0.5, 41: 1, 42: 0.7, 43: 0.35 }[f];
    if (big) { polys(fr.glow, glintPolys([[C + 150, C - 215, 190 * big]]), GOLD); polys(fr.top, glintPolys([[C + 150, C - 215, 130 * big]]), WHITE); }
    if (small) polys(fr.top, glintPolys([[C - 150, C + 215, 100 * small]]), WHITE);
  }
})();

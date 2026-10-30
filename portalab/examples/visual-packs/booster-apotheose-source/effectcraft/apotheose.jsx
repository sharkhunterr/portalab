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

// --- the reveals over the whole screen ---------------------------------------------------------------------
// Timed on Portalab's takeover: the rarity's name across the screen until --card-at (0.9 s, frame 22), the card
// flung in face down, turning at --flip-at (1.45 s) — its face showing from frame 42.
var CARD_AT = 22, FACE_AT = 42;
var PALETTE = {
  rare: { main: CYAN, light: CYAN_L, deep: [0.03, 0.2, 0.55], dark: [0.02, 0.05, 0.14], length: 76 },
  epic: { main: PINK, light: PINK_L, deep: [0.55, 0.05, 0.25], dark: [0.07, 0.01, 0.05], length: 92 },
  legendary: { main: ORANGE, light: GOLD_L, deep: [0.45, 0.12, 0.02], dark: [0.08, 0.02, 0.01], length: 110 }
};
// thick ink slashes sweeping across the screen on a slant — the title screen's strokes
function inkSlashes(L, f, count, base, color) {
  seed(base);
  for (var k = 0; k < count; k++) {
    var y = between(-200, 1280), speed = between(60, 110), x = -900 + ((f + between(0, 20)) * speed) % 2900, len = between(700, 1300), thick = between(40, 120);
    polys(L, slash(x, y + 300, x + len, y - 300, thick, 1, between(-0.6, 0.6)), color, 100);
  }
}
// the comic crown round the card: a white ring, its outside a star burst, its inside torn into teeth, the card
// showing through — r: its inner size (0..1.4)
function crown(L, r, turn, color, base) {
  seed(base);
  var outer = burst(C, C, 26, 1150 * r, 760 * r, 0.25, turn, 1), inner = [], n = 34;
  for (var i = 0; i < n * 2; i++) {
    var a = turn + i / (n * 2) * Math.PI * 2, d = (i % 2 ? 300 : between(360, 470)) * r;
    inner.push([C + Math.cos(a) * d * 0.82, C + Math.sin(a) * d * 1.08]);
  }
  polys(L, [outer, inner], color, 100, true);
}
function stagedBehind(rarity) {
  var P = PALETTE[rarity], comp = square("reveal-" + rarity, P.length), N = P.length;
  for (var f = 0; f < N; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, N - 12, N - 1) * 100;
    if (f < CARD_AT + 2) {   // the title screen: the rarity's colour, ink slashes, lightning
      if (f < 2) polys(fr.top, [full()], WHITE, 90 - f * 40);
      inkSlashes(fr.main, f, 7, 100 + Math.floor(f / 2), INK);
      seed(150 + f); var bolts = [];
      for (var k = 0; k < 3; k++) bolts = bolts.concat(bolt(between(100, 980), between(-40, 300), between(100, 980), between(780, 1120), 60, true));
      lines(fr.glow, bolts, P.light, 18); lines(fr.top, bolts, WHITE, 4);
      polys(fr.main, streaks(C, C, 600, 600, 30, -0.9, 500, 6), P.light, 60);
      polys(fr.main, [full()], P.main, 100);
      continue;
    }
    // the card's stage: black, the rarity's spikes and white bursting from the middle, speed lines rushing in
    var g = ease((f - CARD_AT) / 5), at = f - FACE_AT, spin = (f - CARD_AT) * 0.01;
    if (at >= 0 && at < 4) polys(fr.top, [full()], WHITE, 100 - at * 25);
    if (at >= 0) {
      var cr = 0.55 + 0.55 * back(at / 6) + 0.004 * at;
      crown(fr.main, cr, spin * 2, WHITE, 300);
      crown(fr.main, cr * 1.04 + 0.03, spin * 2 + 0.05, P.main, 300);
      for (var w = 0; w < 2; w++) { var age = at - w * 6; if (age < 0 || age > 18) continue; var rr = 300 + age * 36; lines(fr.glow, [ring(C, C, rr, 1.15)], P.light, 26, fade(age, 8, 18) * o); lines(fr.main, [ring(C, C, rr, 1.15)], WHITE, 5, fade(age, 8, 18) * o); }
    } else {
      polys(fr.top, concentration(C, C, 70, 360, 900, 14), WHITE, 45);
    }
    spikes(fr.main, 22, spin, [[P.main, o], [WHITE, o * (at >= 0 ? 0.95 : 0.8)], [P.deep, o]], 400 + (at >= 0 ? 1 : 0), 240 + 900 * g);
    polys(fr.haze, [circle(C, C, 330, 1.35, 40)], P.main, o * 0.9);
    polys(fr.main, [full()], P.dark, o);
  }
}
if (ONLY === "reveal-rare") stagedBehind("rare");
if (ONLY === "reveal-epic") stagedBehind("epic");
if (ONLY === "reveal-legendary") stagedBehind("legendary");

// over the card: as it turns, a slash of light across it; then sparks off its edges, lightning for a legendary,
// great glints
function stagedOver(rarity) {
  var P = PALETTE[rarity], comp = square("over-" + rarity, P.length), N = P.length;
  for (var f = 0; f < N; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var at = f - FACE_AT + 3;
    if (at >= 0 && at < 9) {
      var so = fade(at, 4, 9) * 100, u = ease(at / 3);
      polys(fr.glow, slash(-60, 830, 1140, 250, 74, u, 1), P.main, so);
      polys(fr.top, slash(-60, 830, 1140, 250, 52, u, 1), WHITE, so);
    }
    if (at >= 3) sparks(fr.main, fr.glow, at - 3, rarity === "legendary" ? 70 : 46, P.main, 1500, 24);
    if (rarity === "legendary" && at >= 4 && at < N - FACE_AT - 8) {
      seed(1600 + f); var arcs = [];
      for (var k = 0; k < 3; k++) { var a = between(0, Math.PI * 2), a2 = a + between(0.4, 0.9), r = toEdge(a, 160, 222), r2 = toEdge(a2, 160, 222); arcs = arcs.concat(bolt(C + Math.cos(a) * r, C + Math.sin(a) * r, C + Math.cos(a2) * r2, C + Math.sin(a2) * r2, 24, true)); }
      lines(fr.glow, arcs, GOLD, 14); lines(fr.top, arcs, WHITE, 3);
    }
    var big = { 6: 0.5, 7: 1, 8: 0.85, 9: 0.6, 10: 0.3 }[at], small = { 24: 0.5, 25: 1, 26: 0.7, 27: 0.35 }[at];
    if (big) { polys(fr.glow, glintPolys([[C + 150, C - 215, 190 * big]]), P.light); polys(fr.top, glintPolys([[C + 150, C - 215, 130 * big]]), WHITE); }
    if (small) polys(fr.top, glintPolys([[C - 150, C + 215, 100 * small]]), WHITE);
  }
}
if (ONLY === "over-rare") stagedOver("rare");
if (ONLY === "over-epic") stagedOver("epic");
if (ONLY === "over-legendary") stagedOver("legendary");

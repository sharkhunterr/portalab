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
  legendary: { main: ORANGE, light: GOLD_L, deep: [0.45, 0.12, 0.02], dark: [0.15, 0.03, 0.02], length: 110 }
};
// the title screen: few, big, flat shapes — the rarity's colour filling the screen, two great dark wedges cutting
// its corners and drifting, a thin line of colour, two white brush flicks (u: 0..1 over the title)
function titleScreen(fr, P, u, f) {
  var drift = u * 60;
  polys(fr.main, [[[-80, -80], [700 - drift, -80], [-80, 520 - drift]]], P.dark, 100);
  polys(fr.main, [[[1160, 1160], [380 + drift, 1160], [1160, 560 + drift]]], P.dark, 100);
  lines(fr.main, [[[-80, 600 - drift], [820 - drift, -80]]], P.main, 10);
  lines(fr.main, [[[1160, 470 + drift], [260 + drift, 1160]]], P.main, 6);
  var flick = function (x, y, r, a0, sweep, w) { return [ring(x, y, r, 1, a0, a0 + sweep)]; };
  if (f >= 3 && f < 14) lines(fr.top, flick(240, 300, 110, 3.6, 1.1 * ease((f - 2) / 4)), WHITE, 9 * fade(f, 9, 14));
  if (f >= 7 && f < 19) lines(fr.top, flick(820, 760, 140, 0.4, 1.0 * ease((f - 6) / 4)), WHITE, 11 * fade(f, 13, 19));
  polys(fr.main, [full()], P.main, 100);
}
// the wipe out of it: dark bands, edged in the rarity's colour, sweeping across on a slant (v: 0..1)
function wipe(fr, P, v) {
  var bands = [];
  for (var k = 0; k < 6; k++) {
    var x = -1600 + v * 2600 + k * 230, w = 150;
    bands.push([[x, 1160], [x + w, 1160], [x + w + 1240, -80], [x + 1240, -80]]);
  }
  lines(fr.top, bands, P.main, 5);
  polys(fr.top, bands, P.dark, 100);
}
// the comic crown round the card: a white ring, its outside a star burst, its inside torn into teeth, the card
// showing through — r: its inner size (0..1.4)
function crown(L, r, turn, color, base) {
  seed(base);
  var outer = burst(C, C, 18, 1100 * r, 760 * r, 0.22, turn, 1), inner = [], n = 22;
  for (var i = 0; i < n * 2; i++) {
    var a = turn + i / (n * 2) * Math.PI * 2, d = (i % 2 ? 310 : between(380, 470)) * r;
    inner.push([C + Math.cos(a) * d * 0.82, C + Math.sin(a) * d * 1.08]);
  }
  polys(L, [outer, inner], color, 100, true);
}
// a clean burst: n great wedges from the middle, the rarity's colour and white in turn, dark between
function cleanBurst(L, n, turn, reach, P, o) {
  var mains = [], whites = [];
  for (var i = 0; i < n * 2; i++) {
    var a = turn + i / (n * 2) * Math.PI * 2, w = Math.PI / (n * 2) * 0.62;
    (i % 2 ? whites : mains).push([[C, C], [C + Math.cos(a - w) * reach, C + Math.sin(a - w) * reach], [C + Math.cos(a + w) * reach, C + Math.sin(a + w) * reach]]);
  }
  polys(L, whites, WHITE, o * 0.92); polys(L, mains, P.main, o);
}
function stagedBehind(rarity) {
  var P = PALETTE[rarity], comp = square("reveal-" + rarity, P.length), N = P.length;
  for (var f = 0; f < N; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, N - 12, N - 1) * 100;
    if (f < CARD_AT) titleScreen(fr, P, f / CARD_AT, f);
    if (f >= CARD_AT - 4 && f < CARD_AT + 4) wipe(fr, P, (f - CARD_AT + 4) / 8);
    if (f < CARD_AT - 1) continue;
    // the card's stage: a clean burst turning slowly on dark; as it turns over, a flash, then the white crown
    var g = ease((f - CARD_AT) / 6), at = f - FACE_AT, spin = (f - CARD_AT) * 0.008;
    if (at >= 0 && at < 3) polys(fr.top, [full()], WHITE, 100 - at * 33);
    if (at >= 0) {
      var cr = 0.55 + 0.5 * back(at / 6);
      crown(fr.main, cr, spin * 1.5, WHITE, 300);
      crown(fr.main, cr * 1.05 + 0.03, spin * 1.5 + 0.06, P.main, 300);
    }
    cleanBurst(fr.main, 12, spin, (300 + 900 * g) * (at >= 0 ? 1.1 : 1), P, o);
    polys(fr.haze, [circle(C, C, 330, 1.35, 40)], P.main, o * 0.7);
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
    if (at >= 0 && at < 8) {
      var so = fade(at, 4, 8) * 100, u = ease(at / 3);
      polys(fr.glow, slash(-60, 830, 1140, 250, 70, u, 1), P.main, so);
      polys(fr.top, slash(-60, 830, 1140, 250, 50, u, 1), WHITE, so);
    }
    if (at >= 3) sparks(fr.main, fr.glow, at - 3, 18, P.main, 1500, 22);
    var big = { 6: 0.5, 7: 1, 8: 0.85, 9: 0.6, 10: 0.3 }[at];
    if (big) { polys(fr.glow, glintPolys([[C + 150, C - 215, 190 * big]]), P.light); polys(fr.top, glintPolys([[C + 150, C - 215, 130 * big]]), WHITE); }
  }
}
if (ONLY === "over-rare") stagedOver("rare");
if (ONLY === "over-epic") stagedOver("epic");
if (ONLY === "over-legendary") stagedOver("legendary");

// Géode — the booster scene's animations, crystal and light drawn frame by frame at 24 frames a second and
// played as videos: faceted crystals (three faces and a lit edge), shards, the geode's shell of stone, cracks
// of light, rays, rings and glints — every light drawn sharp, then blurred and added (its glow). Layers made
// later are drawn on top.

function twinkle(points, f, base, size) {   // glints at given points, each flaring now and then
  var out = [];
  for (var i = 0; i < points.length; i++) {
    var ph = Math.sin(f * 0.5 + i * 2.3 + base);
    if (ph > 0.55) out.push([points[i][0], points[i][1], size * (ph - 0.55) / 0.45]);
  }
  return out;
}
function tips(list) { var out = []; for (var i = 0; i < list.length; i++) { var c = list[i]; out.push([c.x + Math.cos(c.ang) * c.len, c.y + Math.sin(c.ang) * c.len]); } return out; }
function lit(comp, name, f, list, glowOpacity, blur) {   // crystals with their glow under them
  crystalGlow(frames(comp, name + "-glow-" + f, f, f + 1, glowOpacity, blur), list, 100);
  crystals(frames(comp, name + "-" + f, f, f + 1), list);
}

// --- the opening: 1152 x 1080, the pack at (576, 505), 240 x 355 — 64 frames (2.67 s) -----------------------
// Cracks of light spread over the stone as it trembles, light leaking through; it bursts — a flash, a shockwave,
// its shell flying in pieces —, the geode open: a heart of small crystals and a crown of amethysts shooting out,
// glinting, then shattering into shards that sparkle away. The cards come out of it.
if (ONLY === "opening") (function () {
  var comp = app.project.items.addComp("opening", 1152, 1080, 1, 64 * F, 24);
  var cx = 576, cy = 505, hw = 120, hh = 177, gems = ["amethyst", "amethyst", "amethyst", "quartz", "citrine"];
  seed(10);
  var cracks = [];
  for (var c = 0; c < 7; c++) cracks = cracks.concat(crackLines(cx + between(-25, 25), cy + between(-40, 40), c / 7 * Math.PI * 2 + between(-0.3, 0.3), between(80, 160), 0.14));
  for (var f = 2; f < 21; f++) {
    var p = ease((f - 1) / 14);
    lines(frames(comp, "crack-glow-" + f, f, f + 1, 90, 12), partOf(cracks, p), LIGHT, 16);
    lines(frames(comp, "crack-" + f, f, f + 1), partOf(cracks, p), WHITE, 3);
  }
  // light leaking through the cracks: beams out of the stone, swelling (the flash has the frame within it)
  for (var k = 8; k < 22; k++) {
    var beams = rays(14, cx, cy, hw, hh, 220 + (k - 8) * 26, 0.1, k * 0.012, 20);
    polys(frames(comp, "leak-glow-" + k, k, k + 1, 45 + (k - 8) * 4, 12), beams, LIGHT);
    polys(frames(comp, "leak-" + k, k, k + 1, 30 + (k - 8) * 3), beams, WHITE);
  }
  var flash = { 20: [240, 100], 21: [400, 80], 22: [470, 45], 23: [500, 20] };
  for (var h in flash) {
    var n = +h, FL = frames(comp, "flash-" + n, n, n + 1, flash[h][1], 40);
    polys(FL, [circle(cx, cy, flash[h][0] * 0.45, 1, 48)], WHITE);
    polys(FL, [circle(cx, cy, flash[h][0], 1, 64)], LIGHT);
  }
  for (var w = 20; w < 35; w++) {
    var wr = 120 + (w - 20) * 38, wo = 100 - (w - 20) * 7;
    lines(frames(comp, "wave-glow-" + w, w, w + 1, wo, 10), [ring(cx, cy, wr, 0.9)], LIGHT, 22 * (1 - (w - 20) / 15));
    lines(frames(comp, "wave-" + w, w, w + 1, wo), [ring(cx, cy, wr, 0.9)], WHITE, 3);
  }
  // the shell in pieces, flying out and falling, fading
  for (var r = 20; r < 46; r++) {
    seed(40); var R = frames(comp, "shell-" + r, r, r + 1, r < 38 ? 100 : 100 - (r - 38) * 12), age = r - 20, stone = [], top = [], crust = [];
    for (var i = 0; i < 16; i++) {
      var sx = cx + between(-hw, hw), sy = cy + between(-hh, hh), a = Math.atan2(sy - cy, sx - cx), sp = between(14, 30), d = sp * age * (1 - age / 60);
      var piece = rockPiece(sx + Math.cos(a) * d, sy + Math.sin(a) * d + age * age * 0.45, between(28, 56), between(0, 6) + age * between(-0.25, 0.25));
      stone.push(piece.stone); top.push(piece.top); crust.push(piece.crust);
    }
    polys(R, crust, GEMS.amethyst.faces[1]); polys(R, top, ROCK[2]); polys(R, stone, ROCK[1]);
  }
  // the geode open: its heart, then its crown, glinting, shattering
  for (var g = 20; g < 50; g++) {
    var age2 = g - 20, heart = crown(20, cx, cy, 0, 0, 90, 34, ["amethyst"], age2 + 3, 520, { inset: 18, speed: 5, shrink: 22 });
    var big = crown(26, cx, cy, 0, 0, 380, 72, gems, age2, 500, { inset: 50, stagger: 5, speed: 7, shrink: 22 });
    lit(comp, "crown", g, big.concat(heart), 45, 18);
    glints(frames(comp, "tips-" + g, g, g + 1), twinkle(tips(big), g, 1, 26), WHITE);
  }
  var full = crown(26, cx, cy, 0, 0, 380, 72, gems, 30, 500, { inset: 50, stagger: 5, speed: 7 });
  for (var s = 42; s < 64; s++) {
    var age3 = s - 42, list = shatter(full, age3, 4, 600), so = s < 56 ? 100 : 100 - (s - 56) * 13;
    shards(frames(comp, "shards-glow-" + s, s, s + 1, so * 0.6, 8), list);
    shards(frames(comp, "shards-" + s, s, s + 1, so), list);
    seed(700); var sp2 = [];
    for (var q = 0; q < 30; q++) { var qa = between(0, Math.PI * 2), qd = between(120, 520); sp2.push([cx + Math.cos(qa) * qd, cy + Math.sin(qa) * qd + age3 * 2, between(6, 16)]); }
    glints(frames(comp, "spark-" + s, s, s + 1, s < 56 ? 100 : 100 - (s - 56) * 13), twinkle(sp2, s, 2, 18), WHITE);
  }
})();

// --- the reveals: 832 x 1154, the card in the middle, 320 x 444 — behind the card (a legendary's second video
// over it) ------------------------------------------------------------------------------------------------
function revealComp(name, count) { return app.project.items.addComp(name, 832, 1154, 1, count * F, 24); }
var RX = 416, RY = 577, RW = 160, RH = 222;

// rare, 1.8 s: 44 frames — blue quartz sprouting from behind the card's edges, a ring of light, glints, then
// shattering into glitter
if (ONLY === "reveal-rare") (function () {
  var comp = revealComp("reveal-rare", 44), gems = ["quartz", "quartz", "clear"];
  for (var b = 0; b < 22; b++) polys(frames(comp, "light-" + b, b, b + 1, b < 6 ? b * 14 : 84 - (b - 6) * 5, 40), [circle(RX, RY, 250, 1.3, 48)], GEMS.quartz.glow);
  for (var w = 1; w < 20; w++) lines(frames(comp, "wave-" + w, w, w + 1, 100 - w * 5, 8), [ring(RX, RY, 250 + w * 20, 1.15)], GEMS.quartz.glow, 14 * (1 - w / 20));
  for (var f = 0; f < 32; f++) {
    var list = crown(12, RX, RY, RW, RH, 230, 56, gems, f, 1000, { stagger: 6, speed: 6, shrink: 24 });
    lit(comp, "quartz", f, list, 40, 14);
    glints(frames(comp, "tips-" + f, f, f + 1), twinkle(tips(list), f, 3, 22), WHITE);
  }
  var full = crown(12, RX, RY, RW, RH, 230, 56, gems, 20, 1000, { stagger: 6, speed: 6 });
  for (var s = 24; s < 44; s++) {
    var bits = shatter(full, s - 24, 4, 1100), so = s < 36 ? 100 : 100 - (s - 36) * 12;
    shards(frames(comp, "shards-glow-" + s, s, s + 1, so * 0.6, 8), bits);
    shards(frames(comp, "shards-" + s, s, s + 1, so), bits);
  }
})();

// epic, 2.4 s: 58 frames — violet rays turning, a fan of amethysts and rose quartz shooting out one after another
// round the card, shards orbiting it, then all shattering
if (ONLY === "reveal-epic") (function () {
  var comp = revealComp("reveal-epic", 58), gems = ["amethyst", "amethyst", "rose"];
  for (var b = 0; b < 30; b++) polys(frames(comp, "light-" + b, b, b + 1, b < 6 ? b * 15 : 90 - (b - 6) * 3.7, 44), [circle(RX, RY, 270, 1.3, 48)], GEMS.amethyst.glow);
  for (var y = 0; y < 40; y++) polys(frames(comp, "rays-" + y, y, y + 1, Math.min(40, y * 8) * (y < 30 ? 1 : (40 - y) / 10), 12), rays(22, RX, RY, RW, RH, 440, 0.06, y * 0.015, 2050), GEMS.amethyst.glow);
  for (var f = 0; f < 40; f++) {
    var list = crown(18, RX, RY, RW, RH, 330, 64, gems, f, 2000, { order: 0.5, speed: 6, shrink: 32 });
    lit(comp, "fan", f, list, 40, 16);
    glints(frames(comp, "tips-" + f, f, f + 1), twinkle(tips(list), f, 4, 24), WHITE);
  }
  for (var o = 4; o < 50; o++) {
    seed(2100); var orbit = [];
    for (var i = 0; i < 16; i++) { var a = i / 16 * Math.PI * 2 + o * 0.09; orbit.push({ x: RX + Math.cos(a) * 300, y: RY + Math.sin(a) * 380, size: between(8, 14), turn: a * 2 + o * 0.3, gem: i % 3 ? "amethyst" : "rose" }); }
    shards(frames(comp, "orbit-" + o, o, o + 1, o < 42 ? 100 : 100 - (o - 42) * 12), orbit);
  }
  var full = crown(18, RX, RY, RW, RH, 330, 64, gems, 30, 2000, { order: 0.5, speed: 6 });
  for (var s = 32; s < 58; s++) {
    var bits = shatter(full, s - 32, 4, 2200), so = s < 48 ? 100 : 100 - (s - 48) * 10;
    shards(frames(comp, "shards-glow-" + s, s, s + 1, so * 0.6, 8), bits);
    shards(frames(comp, "shards-" + s, s, s + 1, so), bits);
  }
})();

// the legendary, 3 s: 72 frames — prismatic rays turning; a crown of giant crystals of every gem erupting round
// the card one after another; a belt of shards orbiting it, behind the card and over it; great glints; then all
// shattering into rainbow shards. Its back half and what passes behind: ``reveal``; what passes over the card:
// ``over``.
var PRISM = [[1, 0.35, 0.4], [1, 0.7, 0.3], [1, 0.95, 0.4], [0.4, 1, 0.6], [0.35, 0.75, 1], [0.6, 0.45, 1], [1, 0.45, 0.9]];
var ALL = ["amethyst", "citrine", "emerald", "rose", "quartz", "amethyst"];
function belt(o, front) {   // the shards orbiting the card, tilted: the near half over it, the far half behind
  seed(3100); var out = [];
  for (var i = 0; i < 30; i++) {
    var a = i / 30 * Math.PI * 2 + o * 0.08, near = Math.sin(a) > 0;
    var item = { x: RX + Math.cos(a) * 340, y: RY + 40 + Math.sin(a) * 150 + Math.cos(a) * 60, size: between(16, 28) * (near ? 1.25 : 0.8), turn: a * 2 + o * 0.35, gem: ALL[i % ALL.length] };
    if (near === front) out.push(item);
  }
  return out;
}
if (ONLY === "legendary") (function () {
  var comp = revealComp("legendary", 72);
  for (var b = 0; b < 44; b++) polys(frames(comp, "light-" + b, b, b + 1, b < 6 ? b * 16 : 96 - (b - 6) * 2.5, 50), [circle(RX, RY, 300, 1.3, 48)], [1, 0.88, 0.7]);
  for (var y = 0; y < 62; y++) {
    var op = Math.min(32, y * 6) * (y < 50 ? 1 : (62 - y) / 12);
    for (var c = 0; c < PRISM.length; c++) polys(frames(comp, "prism-" + y + "-" + c, y, y + 1, op, 14), rays(5, RX, RY, RW, RH, 520, 0.05, y * 0.012 + c * 0.13, 3000 + c), PRISM[c]);
  }
  for (var hl = 2; hl < 30; hl++) lines(frames(comp, "halo-" + hl, hl, hl + 1, 90 - hl * 3, 12), [ring(RX, RY, 300 + hl * 6, 1.18)], [1, 0.9, 0.7], 18);
  for (var f = 0; f < 50; f++) {
    var list = crown(22, RX, RY, RW, RH, 420, 84, ALL, f, 3200, { order: 0.35, speed: 7, shrink: 44 });
    lit(comp, "crown", f, list, 45, 20);
    glints(frames(comp, "tips-" + f, f, f + 1), twinkle(tips(list), f, 5, 30), WHITE);
  }
  for (var o = 6; o < 60; o++) shards(frames(comp, "belt-" + o, o, o + 1, o < 52 ? 100 : 100 - (o - 52) * 12), belt(o, false));
  var full = crown(22, RX, RY, RW, RH, 420, 84, ALL, 40, 3200, { order: 0.35, speed: 7 });
  for (var s = 44; s < 72; s++) {
    var bits = shatter(full, s - 44, 4, 3300), so = s < 60 ? 100 : 100 - (s - 60) * 8;
    shards(frames(comp, "shards-glow-" + s, s, s + 1, so * 0.6, 8), bits);
    shards(frames(comp, "shards-" + s, s, s + 1, so), bits);
  }
})();
if (ONLY === "legendary-over") (function () {
  var comp = revealComp("legendary-over", 72);
  for (var o = 6; o < 60; o++) {
    var near = belt(o, true), bo = o < 52 ? 100 : 100 - (o - 52) * 12;
    shards(frames(comp, "belt-glow-" + o, o, o + 1, bo * 0.7, 10), near);
    shards(frames(comp, "belt-" + o, o, o + 1, bo), near);
    seed(3400); var sp = [];
    for (var i = 0; i < 18; i++) sp.push([RX + between(-RW * 1.3, RW * 1.3), RY + between(-RH * 1.2, RH * 1.2), between(8, 18)]);
    glints(frames(comp, "spark-" + o, o, o + 1, o < 52 ? 100 : 100 - (o - 52) * 12), twinkle(sp, o, 6, 20), WHITE);
  }
  var big = { 3: 0.5, 4: 1, 5: 0.85, 6: 0.6, 7: 0.35 }, small = { 30: 0.5, 31: 1, 32: 0.7, 33: 0.4 };
  for (var b in big) { glints(frames(comp, "glintA-glow-" + b, +b, +b + 1, 80, 10), [[RX + 175, RY - 240, 150 * big[b]]], [1, 0.9, 0.7]); glints(frames(comp, "glintA-" + b, +b, +b + 1), [[RX + 175, RY - 240, 120 * big[b]]], WHITE); }
  for (var m in small) glints(frames(comp, "glintB-" + m, +m, +m + 1), [[RX - 170, RY + 245, 90 * small[m]]], WHITE);
})();

writeLn("comps " + app.project.numItems);

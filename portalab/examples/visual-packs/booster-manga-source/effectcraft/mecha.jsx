// Mecha — a giant robot's hangar: a pilot's HUD locking on (rings, ticks, brackets, data bars), bolts releasing,
// steam jets, armour plates flying off, a reactor's cyan flash, electric arcs, a missile salvo with its trails
// and blasts, thrusters, and wings of energy unfolding.
var CYAN = [0.2, 0.9, 1], CYAN_L = [0.75, 1, 1], ORANGE = [1, 0.55, 0.1], YELLOW = [1, 0.88, 0.35], MAGENTA = [1, 0.3, 0.65];
var METAL = [[0.82, 0.86, 0.92], [0.52, 0.57, 0.65], [0.28, 0.31, 0.38]], STEAM = [[0.95, 0.97, 1], [0.7, 0.75, 0.82]];

function hud(fr, cx, cy, r, f, opacity, color) {   // a lock-on reticle: broken rings turning, ticks, a cross
  var o = opacity === undefined ? 100 : opacity, c = color || CYAN, arcs = [], ticks = [];
  for (var k = 0; k < 4; k++) arcs.push(ring(cx, cy, r, 1, f * 0.06 + k * Math.PI / 2 + 0.2, f * 0.06 + k * Math.PI / 2 + 1.25));
  for (var k2 = 0; k2 < 3; k2++) arcs.push(ring(cx, cy, r * 0.8, 1, -f * 0.09 + k2 * 2.09, -f * 0.09 + k2 * 2.09 + 1.5));
  for (var t = 0; t < 36; t++) { var a = t / 36 * Math.PI * 2, r1 = r * (t % 3 ? 1.06 : 1.12); ticks.push([[cx + Math.cos(a) * r * 1.02, cy + Math.sin(a) * r * 1.02], [cx + Math.cos(a) * r1, cy + Math.sin(a) * r1]]); }
  var cross = [[[cx - r * 1.3, cy], [cx - r * 0.55, cy]], [[cx + r * 0.55, cy], [cx + r * 1.3, cy]], [[cx, cy - r * 1.3], [cx, cy - r * 0.55]], [[cx, cy + r * 0.55], [cx, cy + r * 1.3]]];
  lines(fr.glow, arcs.concat(cross), c, 10, o); lines(fr.main, arcs, c, 4, o); lines(fr.main, ticks.concat(cross), CYAN_L, 2, o);
}
function brackets(L, glowL, cx, cy, hw, hh, len, opacity, color) {   // the corners of a frame
  var c = [];
  for (var sx = -1; sx <= 1; sx += 2) for (var sy = -1; sy <= 1; sy += 2) c.push([[cx + sx * hw, cy + sy * (hh - len)], [cx + sx * hw, cy + sy * hh], [cx + sx * (hw - len), cy + sy * hh]]);
  lines(glowL, c, color || CYAN, 12, opacity); lines(L, c, CYAN_L, 4, opacity);
}
function dataBars(L, x, y, f, count, opacity) {   // rows of data flickering
  seed(500 + Math.floor(f / 2));
  var bars = [];
  for (var i = 0; i < count; i++) { var w = between(20, 120); bars.push([[x, y + i * 14], [x + w, y + i * 14], [x + w, y + i * 14 + 6], [x, y + i * 14 + 6]]); }
  polys(L, bars, CYAN, opacity);
}
function sparks(L, glowL, cx, cy, f, count, spread, base, opacity) {   // sparks flying, falling
  seed(base);
  var list = [];
  for (var i = 0; i < count; i++) {
    var a = between(-Math.PI, 0) + between(-0.4, 0.4), sp = between(8, 20), age = (f + between(0, 30)) % 30, x = cx + between(-spread, spread) * 0.3 + Math.cos(a) * sp * age, y = cy + Math.sin(a) * sp * age + age * age * 0.5;
    list.push([[x, y], [x - Math.cos(a) * 14, y - Math.sin(a) * 14 - age]]);
  }
  lines(glowL, list, ORANGE, 8, opacity); lines(L, list, YELLOW, 2.4, opacity);
}
function steam(L, x, y, dir, f, start, opacity) {   // a jet of steam from (x, y) along dir
  var age = f - start; if (age < 0) return;
  seed(600 + Math.floor(x));
  var light = [], shade = [];
  for (var i = 0; i < 6; i++) { var d = (age * 22 + i * 30) * between(0.8, 1.1), r = 8 + d * 0.12, px = x + Math.cos(dir) * d, py = y + Math.sin(dir) * d - d * 0.15; var p = puff(px, py, r, 4); light = light.concat(p[0]); shade = shade.concat(p[1]); }
  polys(L, light, STEAM[0], opacity * 0.7); polys(L, shade, STEAM[1], opacity * 0.7);
}
function blast(fr, x, y, r, opacity) {   // an explosion: an orange star, a yellow core, white heat
  polys(fr.haze, [circle(x, y, r * 1.3, 1, 24)], ORANGE, opacity);
  polys(fr.main, [burst(x, y, 10, r * 0.45, r * 0.25, 0.3, 0)], [1, 1, 0.9], opacity); polys(fr.main, [burst(x, y, 12, r * 0.75, r * 0.45, 0.35, 0.2)], YELLOW, opacity); inked(fr.main, [burst(x, y, 14, r, r * 0.6, 0.35, 0.1)], ORANGE, 4, opacity);
}

// --- the opening: 1152 x 1080, the pack at (576, 505), 240 x 355 — 64 frames ------------------------------
// A pilot's HUD locks on the pack; its four bolts release; steam jets burst from its sides; its armour plates
// fly off in a cyan flash of its reactor — the pack gone —, arcs crackling, a hexagonal shockwave, sparks.
if (ONLY === "opening") (function () {
  var comp = newComp("opening", 1152, 1080, 64), cx = 576, cy = 505, hw = 120, hh = 177;
  seed(10);
  var plates = [];
  for (var i = 0; i < 10; i++) plates.push({ x: cx + between(-hw, hw) * 0.8, y: cy + between(-hh, hh) * 0.8, w: between(50, 90), h: between(30, 60), turn: between(0, 6), spin: between(-0.25, 0.25), speed: between(16, 30) });
  for (var f = 0; f < 64; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f < 22) { var lock = ease(f / 12), r = 420 - 200 * lock; hud(fr, cx, cy, r, f, 100, f > 12 && f % 2 ? MAGENTA : CYAN); brackets(fr.main, fr.glow, cx, cy, hw + 30 + (1 - lock) * 120, hh + 30 + (1 - lock) * 120, 40, 100); dataBars(fr.main, cx + hw + 60, cy - hh, f, 8, 70); }
    if (f >= 10 && f < 18) {   // the bolts at its corners turning loose
      var bolts = [];
      for (var sx = -1; sx <= 1; sx += 2) for (var sy = -1; sy <= 1; sy += 2) { var bx = cx + sx * (hw - 18), by = cy + sy * (hh - 18) - (f - 10) * 2 * (f > 14 ? 3 : 0); bolts.push(burst(bx, by, 6, 14, 11, 0, (f - 10) * 0.5)); }
      inked(fr.top, bolts, METAL[1], 2);
    }
    if (f >= 14 && f < 40) { var so = fade(f, 28, 40) * 100; steam(fr.top, cx - hw, cy, Math.PI, f, 14, so); steam(fr.top, cx + hw, cy, 0, f, 14, so); steam(fr.top, cx - hw + 20, cy - hh, -2.3, f, 16, so); steam(fr.top, cx + hw - 20, cy - hh, -0.8, f, 16, so); }
    if (f >= 20 && f < 26) { var k = f < 22 ? (f - 19) / 2 : 1 - (f - 22) / 4; polys(fr.haze, [circle(cx, cy, 380 * k, 1, 40)], CYAN, 90); polys(fr.glow, [circle(cx, cy, 220 * k, 1, 40)], CYAN_L, 90); polys(fr.main, [circle(cx, cy, 120 * k, 1, 40)], WHITE, 90); }
    if (f >= 20 && f < 48) {
      var bodies = [], lit = [], age = f - 20;
      for (var p = 0; p < plates.length; p++) {
        var pl = plates[p], dx = pl.x - cx, dy = pl.y - cy, dd = Math.sqrt(dx * dx + dy * dy) || 1, x = pl.x + dx / dd * age * pl.speed, y = pl.y + dy / dd * age * pl.speed + age * age * 0.6;
        bodies.push(place([[-pl.w / 2, -pl.h / 2], [pl.w / 2, -pl.h / 2], [pl.w / 2, pl.h / 2], [-pl.w / 2 + 12, pl.h / 2], [-pl.w / 2, pl.h / 2 - 12]], x, y, pl.turn + age * pl.spin));
        lit.push(place([[-pl.w / 2, -pl.h / 2], [pl.w / 2, -pl.h / 2], [pl.w / 2 - 8, -pl.h / 2 + 8], [-pl.w / 2 + 8, -pl.h / 2 + 8]], x, y, pl.turn + age * pl.spin));
      }
      polys(fr.top, lit, METAL[0], fade(f, 40, 48) * 100); inked(fr.top, bodies, METAL[1], 3, fade(f, 40, 48) * 100);
    }
    if (f >= 21 && f < 40) {
      seed(700 + f); var arcs = [];
      for (var a = 0; a < 5; a++) { var an = between(0, Math.PI * 2), r0 = between(40, 100), r1 = r0 + between(120, 260); arcs = arcs.concat(bolt(cx + Math.cos(an) * r0, cy + Math.sin(an) * r0, cx + Math.cos(an + 0.3) * r1, cy + Math.sin(an + 0.3) * r1, 20, true)); }
      lines(fr.glow, arcs, CYAN, 12, fade(f, 32, 40) * 100); lines(fr.top, arcs, WHITE, 2.4, fade(f, 32, 40) * 100);
    }
    if (f >= 22 && f < 40) { var hr = 100 + (f - 22) * 34, ho = fade(f, 30, 40) * 100; lines(fr.glow, [circle(cx, cy, hr, 1, 6).concat([[cx + hr, cy]])], CYAN, 18, ho); lines(fr.main, [circle(cx, cy, hr, 1, 6).concat([[cx + hr, cy]])], CYAN_L, 3, ho); }
    if (f >= 22) sparks(fr.top, fr.glow, cx, cy + 40, f, 40, 300, 800, fade(f, 52, 63) * 100);
  }
})();

// --- the reveals: 832 x 1154, the card in the middle, 320 x 444 — behind the card --------------------------
var RX = 416, RY = 577, RW = 160, RH = 222;
function revealComp(name, count) { return newComp(name, 832, 1154, count); }

// rare, 1.8 s: 44 frames — a HUD scanning the card: rings locking on, a scan line, data bars, sparks
if (ONLY === "reveal-rare") (function () {
  var comp = revealComp("reveal-rare", 44);
  for (var f = 0; f < 44; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, 32, 43) * 100;
    hud(fr, RX, RY, 330 - 40 * ease(f / 10), f, o);
    brackets(fr.main, fr.glow, RX, RY, RW + 40, RH + 40, 50, o);
    if (f < 30) { var sy = RY - RH - 40 + (f / 30) * (RH * 2 + 80); polys(fr.glow, [[[RX - RW - 90, sy - 3], [RX + RW + 90, sy - 3], [RX + RW + 90, sy + 3], [RX - RW - 90, sy + 3]]], CYAN, 100); polys(fr.haze, [[[RX - RW - 90, sy - 30], [RX + RW + 90, sy - 30], [RX + RW + 90, sy + 30], [RX - RW - 90, sy + 30]]], CYAN, 60); }
    dataBars(fr.main, RX + RW + 50, RY - 120, f, 10, o * 0.7); dataBars(fr.main, RX - RW - 170, RY + 20, f + 7, 8, o * 0.7);
    sparks(fr.main, fr.glow, RX, RY + RH, f, 18, 300, 1100, o);
  }
})();

// epic, 2.4 s: 58 frames — a missile salvo launched from behind the card, fanning out on trails of smoke, blasting
// high and wide, sparks
if (ONLY === "reveal-epic") (function () {
  var comp = revealComp("reveal-epic", 58);
  seed(2000);
  var salvo = [];
  for (var i = 0; i < 10; i++) salvo.push({ a: -Math.PI / 2 + (i - 4.5) * 0.28 + between(-0.06, 0.06), delay: i * 1.2, reach: between(380, 520), bend: between(-0.4, 0.4) });
  for (var f = 0; f < 58; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var bodies = [], flames = [], light = [], shade = [];
    for (var k = 0; k < salvo.length; k++) {
      var m = salvo[k], t = (f - m.delay) / 16;
      if (t < 0) continue;
      var u = Math.min(1, t), d = 60 + m.reach * ease(u), a = m.a + m.bend * u, x = RX + Math.cos(a) * d, y = RY - RH * 0.4 + Math.sin(a) * d;
      for (var s = 0; s < 8; s++) { var sd = d * s / 8; seed(2100 + k * 10 + s); var p = puff(RX + Math.cos(m.a + m.bend * u * s / 8) * sd, RY - RH * 0.4 + Math.sin(m.a + m.bend * u * s / 8) * sd, 10 + s * 2 + Math.max(0, f - m.delay - 16) * 1.5, 3); light = light.concat(p[0]); shade = shade.concat(p[1]); }
      if (t < 1) { var ms = missile(x, y, 46, a); bodies.push(ms.body); flames.push(ms.flame); }
      else if (t < 1.6) blast(fr, x, y, 50 + (t - 1) * 120, (1 - (t - 1) / 0.6) * 100);
    }
    var so = fade(f, 42, 56) * 100;
    polys(fr.main, light, STEAM[0], so * 0.7); polys(fr.main, shade, STEAM[1], so * 0.7);
    polys(fr.glow, flames, ORANGE); polys(fr.top, flames, YELLOW); inked(fr.top, bodies, METAL[0], 3);
    sparks(fr.main, fr.glow, RX, RY - RH, f, 20, 300, 2200, so);
  }
})();

// the legendary, 3 s: 72 frames — wings of energy unfolding from behind the card (twelve blades, cyan and gold),
// its thrusters flaring under it, a reticle; over the card (``legendary-over``): the HUD's frame, sparks, glints
function wings(fr, f) {
  var open = back((f - 4) / 16), o = fade(f, 54, 70) * 100, blades = [], cores = [];
  for (var side = -1; side <= 1; side += 2) for (var k = 0; k < 6; k++) {
    // folded up along the card, they fan out from upright to outwards, like a bird's
    var root = [RX + side * RW * 0.55, RY - RH * 0.5], right = -1.5 + (0.3 + k * 0.27) * open, ang = side > 0 ? right : Math.PI - right;
    var len = (420 - k * 34) * Math.min(1, open * 1.2), wid = 54 - k * 4;
    blades.push(blade(root[0], root[1], len, wid, ang)); cores.push(blade(root[0], root[1], len * 0.92, wid * 0.35, ang));
  }
  polys(fr.haze, blades, CYAN, o); polys(fr.glow, blades, CYAN_L, o * 0.7);
  polys(fr.main, cores, WHITE, o); polys(fr.main, blades, CYAN, o * 0.8);
}
if (ONLY === "legendary") (function () {
  var comp = revealComp("legendary", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f < 8) polys(fr.haze, [circle(RX, RY, 340, 1.3, 40)], CYAN, 90 - f * 11);
    wings(fr, f);
    if (f > 2 && f < 64) {   // the thrusters under the card
      var th = [], tc = [], flick = 1 + 0.15 * Math.sin(f * 1.7);
      for (var s = -1; s <= 1; s += 2) { th.push([[RX + s * 70 - 30, RY + RH], [RX + s * 70 + 30, RY + RH], [RX + s * 70, RY + RH + 260 * flick]]); tc.push([[RX + s * 70 - 12, RY + RH], [RX + s * 70 + 12, RY + RH], [RX + s * 70, RY + RH + 150 * flick]]); }
      var to = fade(f, 50, 64) * 100;
      polys(fr.haze, th, ORANGE, to); polys(fr.glow, th, YELLOW, to); polys(fr.main, tc, WHITE, to); polys(fr.main, th, ORANGE, to);
    }
    hud(fr, RX, RY, 420, f, fade(f, 40, 60) * 35, CYAN);
    sparks(fr.main, fr.glow, RX, RY + RH + 60, f, 26, 300, 3200, fade(f, 56, 70) * 100);
  }
})();
if (ONLY === "legendary-over") (function () {
  var comp = revealComp("legendary-over", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, 50, 66) * 100, close = ease(f / 10);
    brackets(fr.top, fr.glow, RX, RY, RW + 20 + (1 - close) * 120, RH + 20 + (1 - close) * 120, 46, o, f % 6 < 3 ? CYAN : MAGENTA);
    if (f > 4 && f < 44) { var sy = RY - RH + ((f - 4) / 40) * RH * 2; polys(fr.glow, [[[RX - RW, sy - 2], [RX + RW, sy - 2], [RX + RW, sy + 2], [RX - RW, sy + 2]]], CYAN, 70); }
    sparks(fr.top, fr.glow, RX, RY + RH, f, 14, 260, 3400, o);
    var big = { 3: 0.5, 4: 1, 5: 0.85, 6: 0.6, 7: 0.35 }[f], small = { 30: 0.5, 31: 1, 32: 0.7, 33: 0.4 }[f];
    if (big) { polys(fr.glow, glintPolys([[RX + 170, RY - 235, 160 * big]]), CYAN); polys(fr.top, glintPolys([[RX + 170, RY - 235, 120 * big]]), WHITE); }
    if (small) polys(fr.top, glintPolys([[RX - 165, RY + 240, 90 * small]]), WHITE);
  }
})();

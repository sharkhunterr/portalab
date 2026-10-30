// Ninja — night techniques: a seal catching fire, smoke bombs, shuriken and kunai, a blade's flash, blue
// lightning, falling maple leaves, a summoning circle and a dragon of fire.
var SMOKE = [[0.86, 0.85, 0.9], [0.55, 0.54, 0.62]], STEEL = [[0.78, 0.82, 0.88], [0.4, 0.44, 0.5]], FIRE = [[1, 0.35, 0.05], [1, 0.62, 0.12], [1, 0.92, 0.5]];
var RED = [0.92, 0.14, 0.12], LEAF = [[0.92, 0.25, 0.1], [0.75, 0.12, 0.06]], CHIDORI = [0.5, 0.82, 1];

function smoke(L, list, opacity) {   // puffs: each [x, y, r]
  var light = [], shade = [];
  for (var i = 0; i < list.length; i++) { seed(4000 + i * 13); var p = puff(list[i][0], list[i][1], list[i][2], 6); light = light.concat(p[0]); shade = shade.concat(p[1]); }
  polys(L, light, SMOKE[0], opacity); polys(L, shade, SMOKE[1], opacity);
}
function stars(L, glowL, list) {   // shuriken, each [x, y, r, turn], steel with a glint on one blade
  var bodies = [], holes = [], shines = [];
  for (var i = 0; i < list.length; i++) { var s = shuriken(list[i][0], list[i][1], list[i][2], list[i][3]); bodies.push(s[0]); holes.push(s[1]); shines.push(place([[0, 0], [list[i][2], 0], [list[i][2] * 0.3, list[i][2] * 0.12]], list[i][0], list[i][1], list[i][3])); }
  polys(L, holes, [0.08, 0.08, 0.12]); polys(L, shines, STEEL[0]); inked(L, bodies, STEEL[1], 3);
  if (glowL) polys(glowL, bodies, [0.6, 0.75, 1], 35);
}
function leaves(L, cx, cy, spread, f, count, base) {   // maple leaves swirling down
  seed(base);
  var lit = [], dark = [];
  for (var i = 0; i < count; i++) {
    var x = cx + between(-spread, spread) + Math.sin(f * 0.12 + i) * 60, y = cy - spread + ((f * between(4, 9) + between(0, spread * 2)) % (spread * 2.2)), r = between(10, 18), turn = f * between(-0.12, 0.12) + i;
    var v = [];
    for (var k = 0; k < 10; k++) { var a = k / 10 * Math.PI * 2, rr = k % 2 ? r * 0.45 : r * (k === 0 || k === 8 ? 0.7 : 1); v.push([Math.cos(a - Math.PI / 2) * rr, Math.sin(a - Math.PI / 2) * rr]); }
    var leaf = place(v, x, y, turn, 1, Math.max(0.25, Math.abs(Math.cos(f * 0.15 + i))));
    (i % 2 ? lit : dark).push(leaf);
  }
  polys(L, lit, LEAF[0]); polys(L, dark, LEAF[1]);
}
// the fire dragon on a helix round a box: a band of flame (three tones) thinning to its tail, its head leading
function fireDragon(fr, cx, cy, R, H, f, front) {
  var pts = helix(cx, cy, R, H, 1.6, 0.6 + f * 0.19, 0.2, 90), w = function (u) { return 10 + 58 * Math.pow(u, 0.6); };
  var outer = band(pts, w, front), mid = band(pts, function (u) { return w(u) * 0.62; }, front), core = band(pts, function (u) { return w(u) * 0.28; }, front);
  polys(fr.haze, outer, FIRE[0], 90); polys(fr.glow, outer, FIRE[1], 70);
  polys(fr.main, core, FIRE[2]); polys(fr.main, mid, FIRE[1]); polys(fr.main, outer, FIRE[0]);
  var h = pts[pts.length - 1];
  if ((h.d > 0) === front) {
    var p2 = pts[pts.length - 4], ang = Math.atan2(h.y - p2.y, h.x - p2.x), flick = Math.sin(f * 0.8) * 6;
    var head = place([[-30, -34], [20, -36], [70, -18], [92, -4], [70, 10], [40, 16], [58, 30], [20, 34], [-30, 32]], h.x, h.y, ang);
    var horns = [place([[-10, -32], [-66, -88 + flick], [-40, -40]], h.x, h.y, ang), place([[-24, -24], [-92, -50 - flick], [-50, -14]], h.x, h.y, ang)];
    var eye = place([[34, -16]], h.x, h.y, ang)[0];
    polys(fr.top, [circle(eye[0], eye[1], 5, 1, 10)], [1, 1, 0.85]);
    polys(fr.glow, [head].concat(horns), FIRE[1]);
    polys(fr.main, [head], FIRE[1]); polys(fr.main, horns, FIRE[2]);
  }
}

// --- the opening: 1152 x 1080, the pack at (576, 505), 240 x 355 — 64 frames ------------------------------
// The seal on the pack catches fire, flames licking round it; a smoke bomb bursts — the pack gone in the smoke —
// a blade's flash crosses it, shuriken shoot out of the cloud every way, spinning, maple leaves swirling.
if (ONLY === "opening") (function () {
  var comp = newComp("opening", 1152, 1080, 64), cx = 576, cy = 505, hw = 120, hh = 177;
  for (var f = 0; f < 64; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f < 18) {
      var a = aura(cx, cy, hw, hh, 20 + f * 4, f, 3, 14), box = [[cx - hw, cy - hh], [cx + hw, cy - hh], [cx + hw, cy + hh], [cx - hw, cy + hh]];
      polys(fr.haze, [a[0], box], FIRE[0], 80, true); polys(fr.main, [a[2], box], FIRE[2], 80, true); polys(fr.main, [a[1], box], FIRE[1], 75, true); polys(fr.main, [a[0], box], FIRE[0], 70, true);
    }
    if (f >= 15 && f < 50) {
      seed(100); var cloud = [], age = f - 15;
      for (var i = 0; i < 16; i++) { var pa = between(0, Math.PI * 2), pd = between(0, 1) * (60 + age * 18) * (1 - age / 80); cloud.push([cx + Math.cos(pa) * pd * 1.3, cy + Math.sin(pa) * pd - age * 2, (70 + age * 9) * between(0.6, 1)]); }
      smoke(fr.main, cloud, fade(f, 32, 50) * 100);
    }
    if (f >= 15 && f < 19) polys(fr.haze, [circle(cx, cy, 260 + (f - 15) * 70, 1, 40)], [1, 0.95, 0.85], 80 - (f - 15) * 18);
    if (f >= 20 && f < 24) { var k = (f - 19) / 4, slash = ring(cx + 520, cy + 620, 900, 1, -2.2, -2.2 + 0.9 * k); lines(fr.glow, [slash], [0.7, 0.85, 1], 24); lines(fr.top, [slash], WHITE, 7 * (1 - (f - 20) / 5)); }
    if (f >= 18 && f < 56) {
      seed(300); var list = [], age2 = f - 18;
      for (var j = 0; j < 14; j++) { var sa = j / 14 * Math.PI * 2 + between(-0.2, 0.2), sd = 60 + age2 * between(18, 32); list.push([cx + Math.cos(sa) * sd, cy + Math.sin(sa) * sd * 0.85, between(22, 34) * fade(age2, 26, 38), age2 * 0.7 + j]); }
      seed(301); var trail = [];
      for (var t = 0; t < list.length; t++) { var ta = Math.atan2(list[t][1] - cy, list[t][0] - cx); trail.push(place([[0, -3], [-120, 0], [0, 3]], list[t][0], list[t][1], ta)); }
      polys(fr.main, trail, [0.75, 0.85, 1], 40 * fade(age2, 20, 38));
      stars(fr.top, fr.glow, list);
    }
    if (f >= 18) leaves(fr.top, cx, cy, 420, f, 22, 500);
  }
})();

// --- the reveals: 832 x 1154, the card in the middle, 320 x 444 — behind the card --------------------------
var RX = 416, RY = 577, RW = 160, RH = 222;
function revealComp(name, count) { return newComp(name, 832, 1154, count); }

// rare, 1.8 s: 44 frames — a puff of smoke, then a whirlwind of shuriken round the card, streaking, flung away
if (ONLY === "reveal-rare") (function () {
  var comp = revealComp("reveal-rare", 44);
  for (var f = 0; f < 44; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f < 16) { seed(1000); var cloud = []; for (var i = 0; i < 10; i++) { var a = between(0, Math.PI * 2), d = toEdge(a, RW, RH) * 0.8 + f * 10; cloud.push([RX + Math.cos(a) * d, RY + Math.sin(a) * d, 60 + f * 5]); } smoke(fr.main, cloud, fade(f, 6, 16) * 100); }
    var list = [], trails = [], fling = f > 30 ? (f - 30) * 24 : 0;
    for (var k = 0; k < 8; k++) {
      var a2 = k / 8 * Math.PI * 2 + f * 0.22, d2 = 290 + fling, x = RX + Math.cos(a2) * d2, y = RY + Math.sin(a2) * d2 * 1.25;
      list.push([x, y, 30 * Math.min(1, ease(f / 5)), f * 0.9 + k]);
      trails.push(ring(RX, RY, d2, 1.25, a2 - 0.6, a2));
    }
    lines(fr.main, trails, [0.75, 0.85, 1], 10, 30 * fade(f, 34, 42)); lines(fr.glow, trails, [0.6, 0.75, 1], 14, 30 * fade(f, 34, 42));
    stars(fr.main, fr.glow, list);
  }
})();

// epic, 2.4 s: 58 frames — kunai flying in and striking round the card, blue lightning crackling between them,
// smoke, leaves
if (ONLY === "reveal-epic") (function () {
  var comp = revealComp("reveal-epic", 58);
  seed(2000);
  var blades = [];
  for (var i = 0; i < 10; i++) { var a = i / 10 * Math.PI * 2 + between(-0.15, 0.15); blades.push({ a: a, d: toEdge(a, RW, RH) + between(30, 70), delay: i * 0.8 }); }
  for (var f = 0; f < 58; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var bodies = [], o = fade(f, 44, 56) * 100, tips = [];
    for (var k = 0; k < blades.length; k++) {
      var b = blades[k], t = ease((f - b.delay) / 5), d = b.d + (1 - t) * 520;
      if (f < b.delay) continue;
      var x = RX + Math.cos(b.a) * d, y = RY + Math.sin(b.a) * d;
      bodies.push(kunai(x, y, -110, b.a)); tips.push([x, y]);
    }
    inked(fr.main, bodies, STEEL[1], 3, o); polys(fr.glow, bodies, [0.6, 0.75, 1], 30 * o / 100);
    if (f > 8 && f < 46) {
      seed(2100 + f); var arcs = [];
      for (var j = 0; j < 4; j++) { var p = pick(tips), q = pick(tips); if (p && q && p !== q) arcs = arcs.concat(bolt(p[0], p[1], q[0], q[1], 26, true)); }
      lines(fr.glow, arcs, CHIDORI, 14); lines(fr.top, arcs, WHITE, 2.6);
    }
    if (f < 12) { seed(2200); var cloud = []; for (var c = 0; c < 8; c++) { var ca = between(0, Math.PI * 2); cloud.push([RX + Math.cos(ca) * 260, RY + Math.sin(ca) * 320, 50 + f * 6]); } smoke(fr.main, cloud, fade(f, 4, 12) * 90); }
    leaves(fr.main, RX, RY, 380, f, 14, 2300);
  }
})();

// the legendary, 3 s: 72 frames — a summoning: a circle of seals glowing under the card, smoke bursting, a dragon
// of fire rising out of it and coiling round the card (its near half over it in ``legendary-over``), embers
function seals(fr, f) {
  var m = magicCircle(RX, RY + RH + 40, 360, 0.32, f * 0.02, 8), o = fade(f, 50, 66) * 100, d = ease(f / 10);
  var rings = [];
  for (var i = 0; i < m.rings.length; i++) rings.push(m.rings[i].slice(0, Math.max(2, Math.round(m.rings[i].length * d))));
  lines(fr.haze, rings, RED, 20, o); lines(fr.glow, rings.concat(m.star), RED, 10, o);
  lines(fr.main, rings, [1, 0.6, 0.5], 3, o); if (d > 0.6) { lines(fr.main, m.star, [1, 0.55, 0.45], 2.4, o); lines(fr.main, m.ticks, [1, 0.5, 0.4], 2, o); }
}
if (ONLY === "legendary") (function () {
  var comp = revealComp("legendary", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    seals(fr, f);
    if (f > 6 && f < 34) { seed(3000); var cloud = []; for (var i = 0; i < 12; i++) { var a = between(-Math.PI, 0); cloud.push([RX + Math.cos(a) * (200 + (f - 6) * 6), RY + RH + Math.sin(a) * 120 - (f - 6) * 5, 70 + (f - 6) * 4]); } smoke(fr.main, cloud, fade(f, 20, 34) * 90); }
    if (f >= 8 && f < 62) fireDragon(fr, RX, RY - ease((f - 8) / 20) * 40, 250, 600, f - 8, false);
    seed(3100); var em = [];
    for (var e = 0; e < 30; e++) { var ex = RX + between(-340, 340), ey = RY + RH + 60 - ((f * between(6, 14) + between(0, 900)) % 900); em.push(circle(ex, ey, between(2, 5), 1, 10)); }
    polys(fr.glow, em, FIRE[1], fade(f, 56, 70) * 100); polys(fr.main, em, FIRE[2], fade(f, 56, 70) * 100);
  }
})();
if (ONLY === "legendary-over") (function () {
  var comp = revealComp("legendary-over", 72);
  for (var f = 0; f < 72; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    if (f >= 8 && f < 62) fireDragon(fr, RX, RY - ease((f - 8) / 20) * 40, 250, 600, f - 8, true);
    leaves(fr.top, RX, RY, 360, f, 10, 3300);
    var big = { 3: 0.5, 4: 1, 5: 0.85, 6: 0.6, 7: 0.35 }[f], small = { 34: 0.5, 35: 1, 36: 0.7, 37: 0.4 }[f];
    if (big) { polys(fr.glow, glintPolys([[RX + 170, RY - 235, 160 * big]]), FIRE[1]); polys(fr.top, glintPolys([[RX + 170, RY - 235, 120 * big]]), WHITE); }
    if (small) polys(fr.top, glintPolys([[RX - 165, RY + 240, 90 * small]]), WHITE);
  }
})();

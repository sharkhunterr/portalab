// The edition scenes — the fourteen media card editions' boosters, each staged in its frame's own era (Portalab's
// portalab-editions frames): every rarity over the whole screen (``place: screen``) on Portalab's takeover — the
// edition's screen until the card comes (frame 22; the rarity's name over it, in some editions), the card coming
// in face down (each its own way: the packs' stylesheets), turning over — its face (its edition's frame,
// Portalab's) showing from frame 42. Square comps (1080, cropped to cover any
// screen), drawn round the middle; few, big, flat shapes. Built on the manga toolkit
// (../booster-manga-source/effectcraft/core.jsx). EDITION and ONLY say which comp to build.
var C = 540, CARD_AT = 22, FACE_AT = 42, LENGTH = { rare: 76, epic: 92, legendary: 110 };
var OX = 576, OY = 505;   // the opening's pack, in its comp (1152 × 1080): 240 × 400
function square(name, count) { return newComp(name, 1080, 1080, count); }
function full() { return [[-60, -60], [1140, -60], [1140, 1140], [-60, 1140]]; }
function rect(x0, y0, x1, y1) { return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]; }
function lerp(a, b, t) { return a + (b - a) * t; }
// a rounded rectangle centred on (x, y), turned by ang
function rounded(x, y, w, h, r, ang) {
  var v = [], cs = [[w / 2 - r, -h / 2 + r, -Math.PI / 2], [w / 2 - r, h / 2 - r, 0], [-w / 2 + r, h / 2 - r, Math.PI / 2], [-w / 2 + r, -h / 2 + r, Math.PI]];
  for (var k = 0; k < 4; k++) for (var i = 0; i <= 6; i++) { var a = cs[k][2] + i / 6 * Math.PI / 2; v.push([cs[k][0] + Math.cos(a) * r, cs[k][1] + Math.sin(a) * r]); }
  return place(v, x, y, ang || 0);
}
// a circle whose radius ripples: amp, freq waves round it, phase
function wobble(cx, cy, r, amp, freq, phase, n) {
  var v = [], m = n || 72;
  for (var i = 0; i < m; i++) { var a = i / m * Math.PI * 2, rr = r + amp * Math.sin(a * freq + phase); v.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]); }
  return v;
}
// a tapered slash: fat early, to a point — along (x0,y0)→(x1,y1), drawn up to u
function slash(x0, y0, x1, y1, thick, u, bend) {
  var top = [], bot = [], n = 30, dx = x1 - x0, dy = y1 - y0, l = Math.sqrt(dx * dx + dy * dy), nx = -dy / l, ny = dx / l;
  for (var i = 0; i <= n * clamp01(u); i++) {
    var t = i / n, w = Math.pow(Math.sin(Math.PI * Math.pow(t, 0.55)), 0.7) * thick, off = (bend || 0) * Math.sin(Math.PI * t) * l * 0.06;
    top.push([x0 + dx * t + nx * (off + w), y0 + dy * t + ny * (off + w)]); bot.push([x0 + dx * t + nx * (off - w), y0 + dy * t + ny * (off - w)]);
  }
  return top.length > 1 ? [top.concat(bot.reverse())] : [];
}
// wedges from (cx, cy): n of colour a, n of colour b between them
function fan(L, cx, cy, n, turn, reach, a, b, oa, ob, width, from, to) {
  var A = [], B = [], a0 = from === undefined ? 0 : from, a1 = to === undefined ? Math.PI * 2 : to;
  for (var i = 0; i < n * 2; i++) {
    var ang = turn + a0 + i / (n * 2) * (a1 - a0), w = (a1 - a0) / (n * 4) * (width || 1);
    (i % 2 ? B : A).push([[cx, cy], [cx + Math.cos(ang - w) * reach, cy + Math.sin(ang - w) * reach], [cx + Math.cos(ang + w) * reach, cy + Math.sin(ang + w) * reach]]);
  }
  if (b) polys(L, B, b, ob === undefined ? 100 : ob);
  polys(L, A, a, oa === undefined ? 100 : oa);
}
function flash(fr, at, color) { if (at >= 0 && at < 3) polys(fr.top, [full()], color || WHITE, 100 - at * 33); }
function bigGlint(fr, at, color) {
  var big = { 6: 0.5, 7: 1, 8: 0.85, 9: 0.6, 10: 0.3 }[at];
  if (big) { polys(fr.glow, glintPolys([[C + 150, C - 215, 190 * big]]), color); polys(fr.top, glintPolys([[C + 150, C - 215, 130 * big]]), WHITE); }
}
// things flung from round the card (or a point), turning: a list of shapes built by make(x, y, size, turn, i)
function flung(age, n, base, make, speed, from, cx, cy) {
  seed(base); var out = [], all = [];
  if (age < 0) return out;
  for (var i = 0; i < n; i++) {
    var a = between(0, Math.PI * 2), r0 = (from === undefined ? toEdge(a, 150, 210) : from) + age * (speed || 20) * between(0.6, 1.4), s = between(0.6, 1.3), turn = between(0, 6) + age * between(-0.25, 0.25);
    all.push([(cx === undefined ? C : cx) + Math.cos(a) * r0, (cy === undefined ? C : cy) + Math.sin(a) * r0 + age * age * 0.25, s, turn]);
  }
  // made once every one is placed: a maker drawing its own random numbers moves nothing
  for (var j = 0; j < n; j++) out = out.concat(make(all[j][0], all[j][1], all[j][2], all[j][3], j));
  return out;
}
function sq(s) { return [[-s, -s], [s, -s], [s, s], [-s, s]]; }
// a closed jagged outline round (cx, cy) (torn paper, burnt film)
function jagged(cx, cy, r, jag, n, base, k) {
  seed(base); var v = [];
  for (var i = 0; i < n; i++) { var a = i / n * Math.PI * 2; v.push([cx + Math.cos(a) * r * between(1 - jag, 1 + jag), cy + Math.sin(a) * r * between(1 - jag, 1 + jag) * (k || 1)]); }
  return v;
}

// ===== Nitrate — a silent film's intertitle: black lacquer, silver, sepia, Art Deco, the projector's flicker ====
var NIT = { lac: [0.05, 0.04, 0.035], silver: [0.86, 0.84, 0.8], silver_d: [0.5, 0.48, 0.44], sepia: [0.36, 0.25, 0.15], sepia_l: [0.66, 0.5, 0.32], cream: [0.97, 0.92, 0.8], fire: [1, 0.5, 0.12], fire_l: [1, 0.84, 0.45] };
function scratches(L, f, n, base, color, o) {   // the print's scratches and dust, new every frame
  seed(base + f); var cuts = [], dust = [];
  for (var i = 0; i < n; i++) { var x = between(-20, 1100), y0 = between(-60, 600), w = between(-12, 12); cuts.push([[x, y0], [x + w * 0.5, y0 + between(200, 700)], [x + w, 1140]]); }
  for (var j = 0; j < n * 2; j++) dust.push(circle(between(0, 1080), between(0, 1080), between(1.5, 5), between(0.4, 1), 8));
  lines(L, cuts, color, 1.6, o); polys(L, dust, color, o);
}
function decoFrame(L, inset, color, o) {   // double silver hairlines, cut corners, a diamond in each
  var out = [], gems = [];
  for (var k = 0; k < 2; k++) {
    var d = inset + k * 16, s = 46 + k * 10;
    out.push([[d + s, d], [1080 - d - s, d], [1080 - d, d + s], [1080 - d, 1080 - d - s], [1080 - d - s, 1080 - d], [d + s, 1080 - d], [d, 1080 - d - s], [d, d + s]]);
  }
  var cs = [[inset + 40, inset + 40], [1040 - inset, inset + 40], [1040 - inset, 1040 - inset], [inset + 40, 1040 - inset]];
  for (var c = 0; c < 4; c++) gems.push(place([[0, -14], [14, 0], [0, 14], [-14, 0]], cs[c][0], cs[c][1], 0));
  polys(L, gems, color, o); lines(L, out, color, 3, o, true);
}
function iris(L, r, color, o) { polys(L, [full(), circle(C, C, Math.max(1, r), 1, 72)], color, o, true); }
var ED_NITRATE = {
  title: function (fr, f, u) {
    seed(900 + f); polys(fr.top, [full()], NIT.cream, between(0, 9));
    scratches(fr.top, f, 6, 910, NIT.cream, 45);
    iris(fr.main, 640 - u * 40, NIT.lac, 100);
    decoFrame(fr.main, 150, NIT.silver, 100);
    lines(fr.main, [ring(C, 1180, 520, 1, Math.PI, Math.PI * 2), ring(C, 1180, 600, 1, Math.PI, Math.PI * 2), ring(C, 1180, 680, 1, Math.PI, Math.PI * 2)], NIT.silver_d, 4, 100);
    fan(fr.main, C, 1180, 14, f * 0.004, 1500, NIT.sepia_l, NIT.sepia, 100, 100, 1, Math.PI, Math.PI * 2);
    polys(fr.bg, [full()], NIT.lac, 100);
  },
  wipe: function (fr, v) {   // the iris closes on the screen, and opens again
    var r = v < 0.5 ? 900 * (1 - v * 2) : 900 * (v * 2 - 1);
    lines(fr.top, [ring(C, C, Math.max(2, r), 1)], NIT.silver, 6, 100);
    iris(fr.top, r, NIT.lac, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // the projector's light flares out: silver Deco rays and rings
      var ro = fade(at, 8, 20) * o;
      fan(fr.glow, C, C, 18, at * 0.01, 300 + at * 48, NIT.silver, null, ro * 0.7, 0, 0.5);
      fan(fr.main, C, C, 18, at * 0.01, 260 + at * 40, NIT.silver, null, ro, 0, 0.35);
      lines(fr.main, [ring(C, C, 240 + at * 30, 1.3), ring(C, C, 270 + at * 30, 1.3)], NIT.silver, 3, fade(at, 6, 14) * o);
    }
    seed(930); var specks = [];
    for (var i = 0; i < 30; i++) specks.push([between(0, 1080), between(0, 1080) - f * 1.5, between(2, 5)]);
    polys(fr.top, glintPolys(twinkle(specks, f, 1, 9)), NIT.cream);
    iris(fr.main, 470 + 90 * g, NIT.lac, o);
    lines(fr.main, [ring(C, C, 420, 1.15), ring(C, C, 445, 1.15)], NIT.silver, 3, o);
    var arcs = [];
    for (var k = 0; k < 5; k++) arcs.push(ring(C, C + 300, 330 + k * 38, 1, Math.PI * 1.08, Math.PI * 1.92));
    lines(fr.main, arcs, NIT.silver_d, 5, o);
    fan(fr.main, C, C, 24, -(f - CARD_AT) * 0.004, 900 * g + 200, NIT.sepia_l, NIT.sepia, o, o);
    polys(fr.bg, [full()], NIT.lac, o);
  },
  over: function (fr, f, at) {
    if (at >= -6) scratches(fr.main, f, 3, 960, NIT.cream, 32);
    bigGlint(fr, at, NIT.silver);
  },
  opening: function (comp) {   // the projector flickers; the nitrate print catches fire — a hole burns through the pack
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 26) { seed(970 + f); scratches(fr.top, f, 4, 980, NIT.cream, 50); polys(fr.top, [rect(OX - 120, OY - 200, OX + 120, OY + 200)], NIT.cream, between(0, 14)); }
      if (f >= 10 && f < 60) {
        var r = 14 + 330 * ease((f - 10) / 22), o = fade(f, 44, 60) * 100, n = 40 + Math.round(r / 10);
        polys(fr.main, [jagged(OX + 20, OY - 30, r, 0.07, n, 990 + f)], NIT.lac, o);
        polys(fr.main, [jagged(OX + 20, OY - 30, r * 1.05 + 4, 0.08, n, 995 + f)], NIT.fire_l, o);
        polys(fr.main, [jagged(OX + 20, OY - 30, r * 1.12 + 10, 0.1, n, 999 + f)], NIT.fire, o);
        polys(fr.glow, [circle(OX + 20, OY - 30, r * 1.15 + 20, 1, 40)], NIT.fire, o * 0.8);
        seed(1010); var em = [];
        for (var i = 0; i < 30; i++) { var a = between(0, Math.PI * 2), d = r * between(0.9, 1.2) + (f - 10) * between(0, 6); em.push([OX + 20 + Math.cos(a) * d, OY - 30 + Math.sin(a) * d - (f - 10) * between(3, 9), between(3, 8) * fade(f, 40, 60)]); }
        polys(fr.top, glintPolys(em), NIT.fire_l);
      }
    }
  }
};

// ===== Noir — a detective's case file: night, venetian blinds, rain, a red string between the clues ==========
var NOI = { night: [0.03, 0.03, 0.045], ink: [0.01, 0.01, 0.015], light: [0.96, 0.9, 0.76], gray: [0.42, 0.42, 0.44], kraft: [0.76, 0.62, 0.42], kraft_d: [0.56, 0.43, 0.27], red: [0.8, 0.06, 0.07], white: [0.97, 0.97, 0.95] };
function blinds(L, f, o, color) {
  var bars = [];
  for (var k = -6; k < 16; k++) { var y = k * 96 + (f * 1.2) % 96; bars.push([[-60, y], [1140, y - 360], [1140, y - 360 + 46], [-60, y + 46]]); }
  polys(L, bars, color, o);
}
function rain(L, f, n, base, color, o) {
  seed(base); var list = [];
  for (var i = 0; i < n; i++) { var x = between(-200, 1180), y = ((f * between(46, 70) + between(0, 1300)) % 1300) - 120, l = between(50, 110); list.push([[x, y], [x - l * 0.22, y + l]]); }
  lines(L, list, color, 2.2, o);
}
function sleuth(x, y, s) {   // a man in a fedora and a trench coat, from behind a shoulder
  return [place([[-1.3, 1.4], [-1.1, 0.55], [-0.55, 0.3], [-0.2, 0.36], [0.2, 0.36], [0.55, 0.3], [1.1, 0.55], [1.3, 1.4]], x, y, 0, s, s),
          circle(x, y - 0.05 * s, 0.3 * s, 1.15, 24),
          place([[-0.72, -0.32], [0.72, -0.32], [0.58, -0.2], [-0.58, -0.2]], x, y, 0, s, s),
          place([[-0.36, -0.28], [-0.32, -0.6], [-0.12, -0.68], [0.12, -0.68], [0.32, -0.6], [0.36, -0.28]], x, y, 0, s, s)];
}
function evidence(x, y, s, ang) {   // a print pinned to the board: its white border, the grey picture
  return { frame: place(sq(1), x, y, ang, s, s * 1.2), pic: place(sq(1), x, y - s * 0.12, ang, s * 0.82, s * 0.9) };
}
function stampRing(cx, cy, r) {
  seed(77); var a = [], b = [];
  for (var i = 0; i <= 48; i++) { var t = i / 48 * Math.PI * 2, j = between(0.97, 1.03); a.push([cx + Math.cos(t) * r * j, cy + Math.sin(t) * r * j]); b.push([cx + Math.cos(t) * r * 0.8 * j, cy + Math.sin(t) * r * 0.8 * j]); }
  return [a, b];
}
var NOIR_PINS = [[C - 360, C - 330], [C + 340, C - 380], [C + 400, C + 120], [C + 260, C + 400], [C - 300, C + 360], [C - 420, C + 20]];
var ED_NOIR = {
  title: function (fr, f, u) {
    rain(fr.top, f, 70, 1100, NOI.light, 30);
    polys(fr.main, sleuth(C + 250 - u * 30, 800, 300), NOI.ink, 100);
    polys(fr.haze, [circle(880, 160, 300, 1, 40)], NOI.light, 22);
    blinds(fr.main, f, 22, NOI.light);
    polys(fr.bg, [full()], NOI.night, 100);
  },
  wipe: function (fr, v) {   // the case file slides over the screen and on
    var x0 = v < 0.5 ? 1140 - 1320 * (v / 0.5) : -180 - 1400 * ((v - 0.5) / 0.5);
    lines(fr.top, [[[x0 + 60, 200], [x0 + 1200, 200]], [[x0 + 60, 260], [x0 + 900, 260]]], NOI.kraft_d, 6, 100);
    polys(fr.top, [rect(x0, -60, x0 + 1320, 1140)], NOI.kraft, 100);
    polys(fr.top, [[[x0 + 80, -60], [x0 + 420, -60], [x0 + 400, 40], [x0 + 100, 40]]], NOI.kraft_d, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // the flashbulb; the evidence thrown on the desk; the stamp
      if (at < 14) { var sr = 120 * (1 + 0.5 * fade(at, 0, 3)); lines(fr.top, stampRing(C - 290, C - 300, sr), NOI.red, 10, fade(at, 8, 14) * 100, true); }
      var prints = flung(at, 12, 1120, function (x, y, s, t) { var e = evidence(x, y, 46 * s, t); return [e.frame]; }, 20);
      var pics = flung(at, 12, 1120, function (x, y, s, t) { var e = evidence(x, y, 46 * s, t); return [e.pic]; }, 20);
      polys(fr.main, pics, NOI.gray, fade(at, 40, 60) * o); polys(fr.main, prints, NOI.white, fade(at, 40, 60) * o);
    }
    var pins = [], strings = [], boards = [], boardPics = [];
    for (var i = 0; i < NOIR_PINS.length; i++) {
      var p = NOIR_PINS[i], e = evidence(p[0], p[1] + 30, 70, (i % 2 ? 0.12 : -0.1));
      pins.push(circle(p[0], p[1] - 40, 9, 1, 12)); boards.push(e.frame); boardPics.push(e.pic);
      var q = NOIR_PINS[(i + 1) % NOIR_PINS.length]; strings.push([[p[0], p[1] - 40], [q[0], q[1] - 40]]);
    }
    polys(fr.main, pins, NOI.red, o);
    lines(fr.main, partOf(strings, g), NOI.red, 4, o);
    polys(fr.main, boardPics, NOI.gray, o * g); polys(fr.main, boards, NOI.white, o * g);
    polys(fr.glow, [[[C + 120, -60], [C + 260, -60], [C + 520, 1140], [C - 380, 1140]]], NOI.light, o * 0.2);
    rain(fr.main, f, 40, 1150, NOI.light, 14);
    blinds(fr.main, f, 16, NOI.light);
    polys(fr.bg, [full()], NOI.night, o);
  },
  over: function (fr, f, at) {
    rain(fr.main, f, 24, 1170, NOI.light, 22);
    bigGlint(fr, at, NOI.light);
  },
  opening: function (comp) {   // a red stamp slams on the pack — CLOSED; it goes through the shredder, in strips
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 6 && f < 30) { var s = 1 + 0.6 * fade(f - 6, 0, 3); lines(fr.top, stampRing(OX + 40, OY - 40, 110 * s), NOI.red, 12, fade(f, 24, 30) * 100, true); }
      if (f >= 6 && f < 9) polys(fr.top, [full()], NOI.white, 50 - (f - 6) * 16);
      if (f >= 26) {
        var t = f - 26, strips = [], dark = [];
        for (var k = 0; k < 12; k++) {
          var x = OX - 120 + k * 20, y = OY + 200 + t * (10 + k % 3 * 2) + t * t * 0.6, sway = Math.sin(t * 0.3 + k) * 10, len = Math.min(400, 40 + t * 22);
          (k % 2 ? dark : strips).push(place([[0, -len], [16, -len], [16, 0], [0, 0]], x + sway, y, Math.sin(t * 0.2 + k) * 0.12));
        }
        polys(fr.main, strips, NOI.kraft, fade(f, 50, 63) * 100); polys(fr.main, dark, NOI.kraft_d, fade(f, 50, 63) * 100);
      }
    }
  }
};

// ===== Drive-in — atomic Googie: a night sky, turquoise and cherry, chrome, bulbs chasing round a sign =========
var DRV = { night: [0.03, 0.05, 0.15], sky: [0.06, 0.13, 0.32], turq: [0.25, 0.84, 0.8], cherry: [0.9, 0.1, 0.22], cream: [1, 0.95, 0.84], chrome: [0.8, 0.86, 0.92], bulb: [1, 0.86, 0.45], car: [0.015, 0.02, 0.06] };
function sparkle8(cx, cy, r, turn) {   // a Googie starburst: four long points, four short
  var v = [];
  for (var i = 0; i < 16; i++) { var a = (turn || 0) + i * Math.PI / 8, rr = i % 2 ? r * 0.1 : (i % 4 ? r * 0.55 : r); v.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]); }
  return v;
}
function boomerang(x, y, s, ang) { return place([[-1, 0.2], [-0.2, -0.5], [1, -0.1], [0.9, 0.15], [-0.15, -0.2], [-0.7, 0.35]], x, y, ang, s, s); }
function atom(fr, cx, cy, r, f, o) {   // three orbits round a cherry nucleus, their electrons running
  var orbits = [], el = [];
  for (var k = 0; k < 3; k++) {
    var rot = k * Math.PI / 3 + f * 0.01, a = f * 0.16 + k * 2.1, px = Math.cos(a) * r, py = Math.sin(a) * r * 0.3;
    orbits.push(place(circle(0, 0, r, 0.3, 72), cx, cy, rot));
    el.push(circle(cx + px * Math.cos(rot) - py * Math.sin(rot), cy + px * Math.sin(rot) + py * Math.cos(rot), r * 0.06, 1, 16));
  }
  polys(fr.main, el, DRV.cream, o); polys(fr.glow, el, DRV.turq, o);
  polys(fr.main, [circle(cx, cy, r * 0.13, 1, 24)], DRV.cherry, o);
  lines(fr.glow, orbits, DRV.turq, 16, o * 0.8, true); lines(fr.main, orbits, DRV.turq, 6, o, true);
}
function car(x, y, s, dir) {   // a finned car seen from behind and aside: its body, and its taillights
  return { body: place([[-1.3, 0], [-1.25, -0.3], [-0.7, -0.38], [-0.45, -0.72], [0.35, -0.72], [0.62, -0.38], [1.05, -0.36], [1.32, -0.62], [1.38, -0.25], [1.34, 0]], x, y, 0, s * dir, s),
           lights: [circle(x + 1.28 * s * dir, y - 0.3 * s, 0.07 * s, 1, 12)] };
}
function marquee(fr, pts, f, o, step) {   // bulbs along a path, chasing
  var lit = [], dim = [];
  for (var i = 0; i < pts.length - 1; i++) {
    var a = pts[i], b = pts[i + 1], d = Math.sqrt((b[0] - a[0]) * (b[0] - a[0]) + (b[1] - a[1]) * (b[1] - a[1])), n = Math.max(1, Math.round(d / (step || 34)));
    for (var j = 0; j < n; j++) { var t = j / n, k = lit.length + dim.length; ((k + f) % 3 === 0 ? lit : dim).push(circle(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, 7, 1, 10)); }
  }
  polys(fr.glow, lit, DRV.bulb, o); polys(fr.main, lit, DRV.cream, o); polys(fr.main, dim, DRV.bulb, o * 0.35);
}
var DRV_ARROW = [[120, 860], [640, 780], [620, 720], [900, 840], [600, 960], [620, 900], [100, 950], [120, 860]];
var ED_DRIVEIN = {
  title: function (fr, f, u) {
    seed(1200); var stars = [];
    for (var i = 0; i < 14; i++) stars.push(sparkle8(between(40, 1040), between(40, 700), between(16, 44) * (0.6 + 0.4 * Math.sin(f * 0.4 + i)), f * 0.03 + i));
    polys(fr.top, stars, DRV.cream, 100);
    marquee(fr, DRV_ARROW, f, 100);
    polys(fr.main, [DRV_ARROW], DRV.cherry, 100);
    seed(1210); var boom = [];
    for (var j = 0; j < 5; j++) boom.push(boomerang(between(100, 980), between(120, 680) + Math.sin(f * 0.2 + j) * 12, between(40, 70), f * 0.05 + j));
    polys(fr.main, boom, DRV.turq, 70);
    atom(fr, C, C - 60, 380 + u * 20, f, 100);
    polys(fr.haze, [circle(C, C - 60, 360, 1, 40)], DRV.turq, 40);
    polys(fr.bg, [rect(-60, 700, 1140, 1140)], DRV.sky, 100);
    polys(fr.bg, [full()], DRV.night, 100);
  },
  wipe: function (fr, v) {   // the projector's beam opens over everything
    var w = 1500 * Math.sin(v * Math.PI);
    polys(fr.top, [[[C - 30, 1140], [C + 30, 1140], [C + w, -60], [C - w, -60]]], DRV.cream, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // an atomic burst of starbursts and boomerangs
      polys(fr.main, flung(at, 18, 1230, function (x, y, s, t) { return [sparkle8(x, y, 36 * s, t)]; }, 22), DRV.cream, fade(at, 30, 50) * o);
      polys(fr.main, flung(at, 10, 1240, function (x, y, s, t) { return [boomerang(x, y, 44 * s, t)]; }, 18), DRV.cherry, fade(at, 30, 50) * o);
      lines(fr.glow, [place(circle(0, 0, 300 + at * 40, 0.3, 64), C, C, 0.4), place(circle(0, 0, 300 + at * 40, 0.3, 64), C, C, -0.4)], DRV.turq, 18, fade(at, 6, 16) * o, true);
    }
    var cars = [], lights = [];
    for (var c = 0; c < 4; c++) { var cr = car(80 + c * 300, 1100, 120, c % 2 ? -1 : 1); cars.push(cr.body); lights = lights.concat(cr.lights); }
    polys(fr.glow, lights, DRV.cherry, o); polys(fr.main, lights, DRV.cherry, o); polys(fr.main, cars, DRV.car, o);
    seed(1250); var stars = [];
    for (var i = 0; i < 40; i++) stars.push([between(0, 1080), between(0, 520), between(3, 7)]);
    polys(fr.top, glintPolys(twinkle(stars, f, 2, 9)), DRV.cream);
    var shoot = (f % 40) - 10;
    if (shoot >= 0 && shoot < 10) lines(fr.glow, [[[900 - shoot * 60, 80 + shoot * 20], [980 - shoot * 60, 50 + shoot * 20]]], DRV.cream, 6, 100);
    polys(fr.glow, [[[C - 20, 1140], [C + 20, 1140], [C + 420, C - 420], [C - 420, C - 420]]], DRV.cream, o * 0.14);
    // the big screen the card plays on, chrome-rimmed, on its posts
    polys(fr.main, [rect(C - 360 * g, C - 400 * g, C + 360 * g, C + 360 * g)], [0.82, 0.86, 0.9], o * 0.25);
    lines(fr.main, [rect(C - 370 * g, C - 410 * g, C + 370 * g, C + 370 * g)], DRV.chrome, 8, o * g, true);
    polys(fr.main, [rect(C - 300, C + 360, C - 270, 1140), rect(C + 270, C + 360, C + 300, 1140)], DRV.car, o);
    polys(fr.bg, [rect(-60, 820, 1140, 1140)], [0.05, 0.08, 0.16], o);
    polys(fr.haze, [circle(C, C - 100, 520, 1, 40)], DRV.sky, o * 0.6);
    polys(fr.bg, [full()], DRV.night, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 30) {   // popcorn popping up from below
      var light = [], shade = [];
      for (var i = 0; i < 16; i++) {
        seed(1270 + i * 13); var t = at - between(0, 10); if (t < 0) continue;
        var x = between(80, 1000), y = 1140 - t * between(40, 60) + t * t * 2.2, p = puff(x, y, between(18, 28), 5);
        light = light.concat(p[0]); shade = shade.concat(p[1]);
      }
      polys(fr.main, light, DRV.cream, 100); polys(fr.main, shade, DRV.bulb, 100);
    }
    bigGlint(fr, at, DRV.bulb);
  },
  opening: function (comp) {   // the bulbs chase round the pack like a marquee; it pops — popcorn and starbursts
    var box = [[OX - 140, OY - 220], [OX + 140, OY - 220], [OX + 140, OY + 220], [OX - 140, OY + 220], [OX - 140, OY - 220]];
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 26) marquee(fr, box, f, fade(f, 22, 26) * 100, 30);
      if (f >= 24) {
        var t = f - 24, o = fade(f, 50, 63) * 100;
        seed(1290); var light = [], shade = [], stars = [];
        for (var i = 0; i < 26; i++) { var a = between(0, Math.PI * 2), d = 40 + t * between(10, 22), p = puff(OX + Math.cos(a) * d, OY + Math.sin(a) * d + t * t * 0.5, between(16, 26), 5); light = light.concat(p[0]); shade = shade.concat(p[1]); }
        for (var j = 0; j < 12; j++) { var a2 = between(0, Math.PI * 2), d2 = 60 + t * between(14, 26); stars.push(sparkle8(OX + Math.cos(a2) * d2, OY + Math.sin(a2) * d2, between(20, 40), t * 0.1 + j)); }
        polys(fr.top, stars, DRV.cream, o); polys(fr.main, light, DRV.cream, o); polys(fr.main, shade, DRV.bulb, o);
      }
      if (f >= 24 && f < 27) polys(fr.top, [circle(OX, OY, 500, 1, 40)], DRV.cream, 60 - (f - 24) * 20);
    }
  }
};

// ===== Super 8 — a psychedelic concert poster: op-art rings, a radiating sun, melting bands, flowers ===========
var PSY = { purple: [0.22, 0.04, 0.36], violet: [0.45, 0.12, 0.62], orange: [1, 0.46, 0.08], pink: [1, 0.27, 0.6], yellow: [1, 0.86, 0.2], green: [0.32, 0.84, 0.45], cream: [1, 0.95, 0.85] };
var PSY_RINGS = [PSY.orange, PSY.purple, PSY.pink, PSY.violet, PSY.yellow, PSY.purple, PSY.green, PSY.violet];
function opArt(L, cx, cy, f, r0, r1, step, amp, o) {   // rippling rings, the smallest drawn first (so on top)
  for (var r = r0, k = 0; r <= r1; r += step, k++) polys(L, [wobble(cx, cy, r, amp, 7, f * 0.25 - k * 0.6, 96)], PSY_RINGS[k % PSY_RINGS.length], o);
}
function daisy(cx, cy, r, turn) {
  var petals = [];
  for (var i = 0; i < 8; i++) petals.push(place(circle(r * 0.55, 0, r * 0.46, 0.4, 20), cx, cy, turn + i * Math.PI / 4));
  return { petals: petals, heart: circle(cx, cy, r * 0.28, 1, 20) };
}
function meltBand(top, f, color, depth) {   // a band along the top (or the foot) whose edge melts in drips
  var v = top ? [[-60, -60], [1140, -60]] : [[-60, 1140], [1140, 1140]];
  for (var i = 0; i <= 40; i++) {
    var x = 1140 - i * 30, d = depth + 30 * Math.sin(i * 0.9 + f * 0.15) + (i % 5 === 0 ? 50 + 30 * Math.sin(f * 0.1 + i) : 0);
    v.push([x, top ? d : 1080 - d]);
  }
  return v;
}
var ED_SUPER8 = {
  title: function (fr, f, u) {
    polys(fr.main, [meltBand(true, f, PSY.pink, 70)], PSY.pink, 100);
    polys(fr.main, [meltBand(false, f, PSY.green, 70)], PSY.green, 100);
    polys(fr.main, [circle(C, C, 130 + 10 * Math.sin(f * 0.4), 1, 48)], PSY.yellow, 100);
    fan(fr.main, C, C, 14, f * 0.03, 360, PSY.orange, PSY.cream, 100, 100, 0.9);
    opArt(fr.main, C, C, f, 380, 1000, 52, 16 + u * 10, 100);
  },
  wipe: function (fr, v) {   // a lava-lamp blob swells over everything
    var r = 30 + Math.sin(v * Math.PI) * 950;
    polys(fr.top, [wobble(C, C, r * 0.7, r * 0.06, 5, v * 8, 72)], PSY.orange, 100);
    polys(fr.top, [wobble(C, C, r, r * 0.08, 4, -v * 6, 72)], PSY.pink, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6), amp = 14 + (at >= 0 ? 30 * fade(at, 4, 16) : 0);
    if (at >= 0) {   // flowers thrown out of the card
      var pet = flung(at, 14, 1320, function (x, y, s, t) { return daisy(x, y, 40 * s, t).petals; }, 20), hearts = flung(at, 14, 1320, function (x, y, s, t) { return [daisy(x, y, 40 * s, t).heart]; }, 20);
      polys(fr.main, hearts, PSY.orange, fade(at, 34, 50) * o); polys(fr.main, pet, PSY.cream, fade(at, 34, 50) * o);
    }
    seed(1330); var pet2 = [], hearts2 = [];
    for (var i = 0; i < 8; i++) { var a = i / 8 * Math.PI * 2 + f * 0.01, d = 420 + 30 * Math.sin(f * 0.1 + i), dz = daisy(C + Math.cos(a) * d, C + Math.sin(a) * d * 1.1, 46, f * 0.04 + i); pet2 = pet2.concat(dz.petals); hearts2.push(dz.heart); }
    polys(fr.main, hearts2, PSY.yellow, o * g); polys(fr.main, pet2, PSY.pink, o * g);
    polys(fr.main, [meltBand(true, f, PSY.pink, 50)], PSY.pink, o);
    polys(fr.main, [meltBand(false, f, PSY.green, 50)], PSY.green, o);
    fan(fr.main, C, C, 16, -(f - CARD_AT) * 0.02, 330 + 60 * g, PSY.yellow, PSY.orange, o, o, 0.9);
    opArt(fr.main, C, C, f, 360, 1000, 56, amp, o);
  },
  over: function (fr, f, at) {
    seed(1350); var blobs = [];
    for (var i = 0; i < 6; i++) { var x = i % 2 ? between(40, 220) : between(860, 1040), y = 1200 - ((f * between(5, 9) + between(0, 1300)) % 1400), r = between(30, 60); blobs.push(wobble(x, y, r, r * 0.15, 3, f * 0.2 + i, 32)); }
    polys(fr.main, blobs, PSY.pink, 85);
    bigGlint(fr, at, PSY.yellow);
  },
  opening: function (comp) {   // the pack melts: its colours turn, drips run down, rings ripple out
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 8 && f < 50) {
        var t = f - 8, o = fade(f, 40, 50) * 100;
        for (var k = 0; k < 4; k++) { var rr = 140 + ((t * 14 + k * 90) % 420); lines(fr.main, [wobble(OX, OY, rr, 12, 6, t * 0.3 + k, 64)], PSY_RINGS[k], 14, o * fade(rr, 380, 560), true); }
      }
      if (f >= 14 && f < 64) {
        var t2 = f - 14, drips = [];
        for (var i = 0; i < 9; i++) { var x = OX - 120 + i * 30, len = Math.min(700, t2 * (8 + (i * 7) % 11) + t2 * t2 * 0.3), w = 14 + (i % 3) * 4; drips.push([[x - w, OY + 150], [x + w, OY + 150], [x + w * 0.8, OY + 150 + len], [x, OY + 150 + len + w], [x - w * 0.8, OY + 150 + len]]); }
        polys(fr.main, drips.slice(0, 3), PSY.pink, fade(f, 52, 63) * 100); polys(fr.main, drips.slice(3, 6), PSY.orange, fade(f, 52, 63) * 100); polys(fr.main, drips.slice(6), PSY.violet, fade(f, 52, 63) * 100);
      }
    }
  }
};

// ===== Pellicule — a 1970s poster: the countdown leader, a striped sunset in halftone, the film running ========
var FLM = { paper: [0.93, 0.86, 0.72], paper_d: [0.78, 0.68, 0.5], ink: [0.14, 0.1, 0.08], s1: [1, 0.8, 0.3], s2: [1, 0.58, 0.18], s3: [0.92, 0.33, 0.18], s4: [0.6, 0.16, 0.24], teal: [0.12, 0.42, 0.42], gray: [0.6, 0.57, 0.52] };
function leader(fr, f, r, o) {   // the countdown leader: crosshairs, two rings, the sweep going round
  var sweep = (f % 12) / 12 * Math.PI * 2, w = [[C, C]];
  for (var i = 0; i <= 40; i++) { var a = -Math.PI / 2 + sweep * i / 40; w.push([C + Math.cos(a) * r * 2.2, C + Math.sin(a) * r * 2.2]); }
  lines(fr.main, [[[C - r * 2.4, C], [C + r * 2.4, C]], [[C, C - r * 2.4], [C, C + r * 2.4]]], FLM.ink, 5, o);
  lines(fr.main, [ring(C, C, r, 1), ring(C, C, r * 0.82, 1)], FLM.ink, 10, o);
  polys(fr.main, [w], FLM.gray, o * 0.55);
}
function stripedSun(L, cx, cy, r, f, o) {   // a sun in bands, the gaps between them growing and sinking towards its foot
  var cols = [FLM.s1, FLM.s1, FLM.s2, FLM.s2, FLM.s3, FLM.s3, FLM.s4, FLM.s4], n = cols.length, edges = [];
  for (var k = 0; k < n; k++) {
    var y0 = cy - r + k * 2 * r / n, y1 = y0 + 2 * r / n, gap = k < 3 ? 0 : (k - 2) * 7 + 4 * Math.sin(f * 0.2 + k);
    if (k >= 3) y0 += gap;
    var left = [], right = [];
    for (var s = 0; s <= 6; s++) { var y = y0 + (y1 - y0) * s / 6, h = Math.sqrt(Math.max(0, r * r - (y - cy) * (y - cy))); right.push([cx + h, y]); left.push([cx - h, y]); }
    polys(L, [right.concat(left.reverse())], cols[k], o);
  }
}
function sprockets(L, f, y, o) {   // a strip of film running across, its holes
  var holes = [], x0 = -60 - (f * 18) % 60;
  for (var x = x0; x < 1160; x += 60) holes.push(rounded(x, y, 26, 22, 4, 0));
  polys(L, [rect(-60, y - 34, 1140, y + 34)].concat(holes), FLM.ink, o, true);
}
var ED_FILM = {
  title: function (fr, f, u) {
    scratches(fr.top, f, 4, 1400, FLM.paper, 40);
    leader(fr, f, 240 + u * 10, 100);
    lines(fr.main, halftoneRows(C, C, 0, 760, 26), FLM.paper_d, 9, 100, false, [0.1, 26]);
    polys(fr.bg, [full()], FLM.paper, 100);
  },
  wipe: function (fr, v) {   // the sweep inks the screen, then wipes it clean
    var w = [[C, C]], from = v < 0.5 ? 0 : (v - 0.5) * 2, to = v < 0.5 ? v * 2 : 1;
    for (var i = 0; i <= 48; i++) { var a = -Math.PI / 2 + (from + (to - from) * i / 48) * Math.PI * 2; w.push([C + Math.cos(a) * 1000, C + Math.sin(a) * 1000]); }
    polys(fr.top, [w], FLM.ink, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // rays of the sunset out of the card, scraps of poster
      fan(fr.main, C, C, 14, at * 0.01, 300 + at * 50, FLM.s1, null, fade(at, 10, 22) * o, 0, 0.5);
      polys(fr.main, flung(at, 16, 1420, function (x, y, s, t, i) { return [place(jagged(0, 0, 22 * s, 0.35, 7, 1430 + i), x, y, t)]; }, 20), FLM.paper, fade(at, 30, 50) * o);
    }
    sprockets(fr.main, f, 50, o); sprockets(fr.main, -f, 1030, o);
    stripedSun(fr.main, C, C - 20 + 60 * (1 - g), 420, f, o);
    lines(fr.main, halftoneRows(C, C - 20, 440, 900, 30), FLM.s3, 10, o * 0.5, false, [0.1, 30]);
    var bands = [FLM.s4, FLM.s3, FLM.s2];
    for (var b = 0; b < 3; b++) polys(fr.main, [rect(-60, 720 + b * 50, 1140, 760 + b * 50)], bands[b], o * 0.8);
    polys(fr.bg, [full()], FLM.paper, o);
  },
  over: function (fr, f, at) {
    if (at >= -4) scratches(fr.main, f, 2, 1450, FLM.paper, 30);
    bigGlint(fr, at, FLM.s1);
  },
  opening: function (comp) {   // a tear runs across the poster; it is ripped off, scraps of paper flying
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 14 && f < 30) { var tear = []; seed(1470); for (var i = 0; i <= 12; i++) tear.push([OX - 160 + i * 27, OY + 60 - i * 18 + between(-14, 14)]); lines(fr.top, partOf([tear], ease((f - 14) / 6)), FLM.paper, 9, fade(f, 26, 30) * 100); }
      if (f >= 24) {
        var t = f - 24, o = fade(f, 50, 63) * 100;
        seed(1480); var scraps = [], dark = [];
        for (var j = 0; j < 22; j++) { var a = between(0, Math.PI * 2), d = 40 + t * between(10, 24), s = between(16, 34); (j % 4 ? scraps : dark).push(jagged(OX + Math.cos(a) * d, OY + Math.sin(a) * d + t * t * 0.45, s, 0.4, 7, 1490 + j)); }
        polys(fr.main, dark, FLM.s3, o); polys(fr.main, scraps, FLM.paper, o);
      }
    }
  }
};

// ===== LaserDisc — Memphis: pastel shapes ringed in black on graph paper, solid offset shadows, a rainbow disc ==
var MEM = { mint: [0.55, 0.9, 0.8], pink: [1, 0.6, 0.74], yellow: [1, 0.84, 0.2], blue: [0.25, 0.45, 1], purple: [0.62, 0.48, 0.96], cream: [1, 0.97, 0.9], black: [0.06, 0.06, 0.08], coral: [1, 0.42, 0.38], grid: [0.62, 0.78, 0.95] };
var MEM_COLS = [MEM.pink, MEM.yellow, MEM.blue, MEM.mint, MEM.purple, MEM.coral];
function squiggle(x, y, len, amp, ang, phase) { var v = []; for (var i = 0; i <= 28; i++) { var t = i / 28; v.push([t * len - len / 2, Math.sin(t * Math.PI * 4 + phase) * amp]); } return place(v, x, y, ang); }
function memphis(L, list, color, o, shadow) {   // flat shapes ringed in black over a solid black shadow
  lines(L, list, MEM.black, 5, o, true); polys(L, list, color, o);
  if (shadow) { var sh = []; for (var i = 0; i < list.length; i++) sh.push(place(list[i], shadow, shadow, 0)); polys(L, sh, MEM.black, o); }
}
function memShape(k, x, y, s, t) {
  if (k % 3 === 0) return place([[0, -1], [0.95, 0.75], [-0.95, 0.75]], x, y, t, s, s);
  if (k % 3 === 1) return circle(x, y, s * 0.8, 1, 24);
  return place([[-1, -0.35], [1, -0.35], [1, 0.35], [-1, 0.35]], x, y, t, s, s);
}
function confetti(fr, list, o) {   // [k, x, y, s, t] → in six colours, ringed, shadowed
  for (var c = 0; c < MEM_COLS.length; c++) {
    var shapes = [];
    for (var i = 0; i < list.length; i++) if (list[i][0] % MEM_COLS.length === c) shapes.push(memShape(list[i][0], list[i][1], list[i][2], list[i][3], list[i][4]));
    if (shapes.length) memphis(fr.main, shapes, MEM_COLS[c], o, 6);
  }
}
function graph(L, o) { var g = []; for (var x = -60; x < 1140; x += 45) g.push([[x, -60], [x, 1140]]); for (var y = -60; y < 1140; y += 45) g.push([[-60, y], [1140, y]]); lines(L, g, MEM.grid, 1.5, o); }
function rainbowDisc(fr, cx, cy, r, f, o) {   // a LaserDisc catching the light: rings of colour turning, a gloss, its hole
  polys(fr.main, [circle(cx, cy, r * 0.12, 1, 32)], MEM.black, o);
  polys(fr.main, [[[cx, cy], [cx + Math.cos(f * 0.05) * r, cy + Math.sin(f * 0.05) * r], [cx + Math.cos(f * 0.05 + 0.5) * r, cy + Math.sin(f * 0.05 + 0.5) * r]]], WHITE, o * 0.45);
  for (var k = 0; k < 7; k++) polys(fr.main, [circle(cx, cy, r * (0.25 + k * 0.125), 1, 64)], MEM_COLS[(k + Math.floor(f / 3)) % MEM_COLS.length], o);
  lines(fr.main, [ring(cx, cy, r, 1)], MEM.black, 8, o);
  polys(fr.main, [circle(cx + 16, cy + 16, r, 1, 64)], MEM.black, o);
}
var ED_LASERDISC = {
  title: function (fr, f, u) {
    lines(fr.top, [squiggle(300, 250 + f * 2, 420, 30, -0.3, f * 0.3), squiggle(820, 820 - f * 2, 380, 26, 0.4, -f * 0.3)], MEM.black, 12, 100);
    seed(1500); var list = [];
    for (var i = 0; i < 26; i++) list.push([i, between(0, 1080), between(0, 1080), between(18, 40), between(0, 6) + f * between(-0.06, 0.06)]);
    confetti(fr, list, 100);
    memphis(fr.main, [circle(260 - f * 2, 260, 190, 1, 48)], MEM.yellow, 100, 18);
    memphis(fr.main, [place([[0, -1], [0.95, 0.75], [-0.95, 0.75]], 830 + f * 1.5, 760, 0.3 + f * 0.01, 260, 260)], MEM.pink, 100, 18);
    memphis(fr.main, [rect(560, 120 - f, 1000, 330 - f)], MEM.mint, 100, 18);
    graph(fr.main, 100);
    polys(fr.bg, [full()], MEM.cream, 100);
  },
  wipe: function (fr, v) {   // a giant coral disc rolls across
    var x = -1100 + v * 3300;
    memphis(fr.top, [circle(x, C, 1150, 1, 72)], MEM.coral, 100, 30);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // confetti thrown out of the card
      seed(1520); var burst = [];
      for (var i = 0; i < 30; i++) { var a = between(0, Math.PI * 2), d = toEdge(a, 150, 210) + at * between(14, 30); burst.push([i, C + Math.cos(a) * d, C + Math.sin(a) * d + at * at * 0.3, between(14, 30), between(0, 6) + at * 0.2]); }
      confetti(fr, burst, fade(at, 34, 50) * o);
    }
    seed(1530); var orbit = [];
    for (var j = 0; j < 12; j++) { var b = j / 12 * Math.PI * 2 + f * 0.02; orbit.push([j, C + Math.cos(b) * 470, C + Math.sin(b) * 520, 26, f * 0.05 + j]); }
    confetti(fr, orbit, o * g);
    rainbowDisc(fr, C, C, 470 * g + 1, f, o);
    memphis(fr.main, [rect(-60, 880, 330, 1140), circle(980, 120, 90, 1, 32)], MEM.blue, o, 12);
    graph(fr.main, o);
    polys(fr.bg, [full()], MEM.cream, o);
  },
  over: function (fr, f, at) {
    if (at >= 0) {
      var travel = at * 40;
      lines(fr.main, [squiggle(-200 + travel, 260, 360, 28, 0, at * 0.5), squiggle(1280 - travel, 840, 360, 28, 0, -at * 0.5)], MEM.black, 12, fade(at, 30, 40) * 100);
    }
    bigGlint(fr, at, MEM.yellow);
  },
  opening: function (comp) {   // the pack is cut into Memphis shapes, flung everywhere
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 12 && f < 24) lines(fr.top, [squiggle(OX, OY - 200 + (f - 12) * 34, 280, 16, 0, f * 0.8)], MEM.black, 8, 100);
      if (f >= 24) {
        var t = f - 24, list = [];
        seed(1550);
        for (var i = 0; i < 34; i++) { var a = between(0, Math.PI * 2), d = between(0, 120) + t * between(10, 26); list.push([i, OX + Math.cos(a) * d, OY + Math.sin(a) * d * 1.3 + t * t * 0.4, between(16, 34), between(0, 6) + t * 0.15]); }
        confetti(fr, list, fade(f, 50, 63) * 100);
      }
    }
  }
};

// ===== VHS — the arcade: a dusk sky in pixel bands, a pixel city, a striped sun, scanlines, the tape's tracking ==
var ARC = { b1: [0.1, 0.08, 0.27], b2: [0.18, 0.11, 0.39], b3: [0.35, 0.14, 0.47], b4: [0.63, 0.2, 0.49], b5: [0.88, 0.31, 0.48], b6: [1, 0.55, 0.4], sun: [1, 0.82, 0.42], city: [0.04, 0.035, 0.09], cyan: [0.3, 1, 0.95], magenta: [1, 0.25, 0.8], yellow: [1, 0.86, 0.2], white: [1, 1, 1] };
var PX = 20;
function snap(v) { return Math.round(v / PX) * PX; }
function pixelSky(L, o) { var b = [ARC.b6, ARC.b5, ARC.b4, ARC.b3, ARC.b2, ARC.b1], h = [800, 700, 600, 480, 340, -60]; for (var i = 0; i < 6; i++) polys(L, [rect(-60, h[i], 1140, 1140)], b[i], o); }
function pixelSun(L, cx, cy, r, f, o) {   // a stepped disc, its lower half striped
  var rows = [];
  for (var y = -r; y < r; y += PX) {
    var k = (y + r) / (2 * r); if (k > 0.5 && Math.floor((y + r + f * 2) / PX) % 3 === 0) continue;
    var h = snap(Math.sqrt(Math.max(0, r * r - (y + PX / 2) * (y + PX / 2))));
    rows.push(rect(cx - h, cy + y, cx + h, cy + y + PX));
  }
  polys(L, rows, ARC.sun, o);
}
function skyline(fr, f, o) {
  seed(1600); var blocks = [], wins = [];
  for (var x = -60; x < 1140; x += 80) {
    var h = snap(between(100, 300)); blocks.push(rect(x, 1080 - h, x + 80, 1140));
    for (var wy = 1080 - h + 20; wy < 1060; wy += 40) for (var wx = x + 20; wx < x + 70; wx += 30) if (rnd() > 0.45 + 0.3 * Math.sin(f * 0.2 + wx)) wins.push(rect(wx, wy, wx + 10, wy + 14));
  }
  polys(fr.main, wins, ARC.yellow, o); polys(fr.main, blocks, ARC.city, o);
}
function scanlines(L, o) { var s = []; for (var y = -60; y < 1140; y += 8) s.push([[-60, y], [1140, y]]); lines(L, s, ARC.city, 3, o); }
function tracking(L, f, o) {
  var y0 = ((f * 30) % 1400) - 160; seed(1610 + f); var bits = [];
  for (var i = 0; i < 70; i++) { var x = between(-60, 1140), y = y0 + between(0, 70); bits.push([[x, y], [x + between(10, 80), y]]); }
  lines(L, bits, ARC.white, 3, o);
}
function pixelStar(x, y, s) { x = snap(x); y = snap(y); return [rect(x - s, y - PX / 2, x + s + PX, y + PX / 2), rect(x, y - s - PX / 2, x + PX, y + s + PX / 2)]; }
var ED_VHS = {
  title: function (fr, f, u) {
    scanlines(fr.top, 30);
    if (f % 9 < 4) tracking(fr.top, f, 50);
    seed(1620); var stars = [];
    for (var i = 0; i < 18; i++) { var x = between(0, 1080), y = between(0, 420); if ((f + i) % 6 < 3) stars = stars.concat(pixelStar(x, y, (i % 3) * PX)); }
    polys(fr.main, stars, ARC.white, 100);
    skyline(fr, f, 100);
    pixelSun(fr.main, C, 720, 300, f, 100);
    pixelSky(fr.bg, 100);
  },
  wipe: function (fr, v) {   // the screen dissolves into big pixels, and back
    seed(1630); var cells = [];
    for (var j = 0; j < 12; j++) for (var i = 0; i < 12; i++) { var r1 = between(0, 0.5), r2 = between(0.5, 1); if (v > r1 && v < r2) cells.push(rect(-60 + i * 100, -60 + j * 100, 40 + i * 100, 40 + j * 100)); }
    polys(fr.top, cells, ARC.b1, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // an 8-bit explosion: squares flung in steps, a square ring growing
      var cols = [ARC.cyan, ARC.magenta, ARC.yellow, ARC.white];
      for (var c = 0; c < 4; c++) polys(fr.main, flung(Math.floor(at / 2) * 2, 12, 1640 + c, function (x, y, s) { return [rect(snap(x), snap(y), snap(x) + PX * Math.round(s * 1.5), snap(y) + PX * Math.round(s * 1.5))]; }, 24), cols[c], fade(at, 24, 40) * o);
      var q = snap(240 + Math.floor(at / 2) * 60); lines(fr.glow, [rect(C - q, C - q * 1.3, C + q, C + q * 1.3)], ARC.cyan, PX, fade(at, 8, 16) * o, true);
    }
    seed(1650); var coins = [];
    for (var k = 0; k < 8; k++) { var a = k / 8 * Math.PI * 2 + f * 0.03, w = Math.max(4, Math.abs(Math.cos(f * 0.3 + k)) * 24); coins.push(rect(snap(C + Math.cos(a) * 420) - w, snap(C + Math.sin(a) * 480) - 24, snap(C + Math.cos(a) * 420) + w, snap(C + Math.sin(a) * 480) + 24)); }
    polys(fr.main, coins, ARC.yellow, o * g);
    skyline(fr, f, o);
    pixelSun(fr.main, C, C + 120, 260 + 200 * g, f, o);
    pixelSky(fr.bg, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) tracking(fr.main, f * 3, 60);
    if (at >= 2) { seed(1660); var stars = []; for (var i = 0; i < 10; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 160, 222) + between(20, 120); if ((f + i) % 4 < 2) stars = stars.concat(pixelStar(C + Math.cos(a) * r, C + Math.sin(a) * r, PX)); } polys(fr.top, stars, ARC.white, 100); }
    bigGlint(fr, at, ARC.cyan);
  },
  opening: function (comp) {   // the pack glitches and bursts into pixels
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 10 && f < 24) { tracking(fr.top, f * 2, 60); if (f % 3 === 0) polys(fr.top, [rect(OX - 140, OY - 60 + (f % 7) * 20, OX + 160, OY - 30 + (f % 7) * 20)], ARC.magenta, 70); }
      if (f >= 24) {
        var t = Math.floor((f - 24) / 2) * 2, o = fade(f, 50, 63) * 100, cols = [ARC.cyan, ARC.magenta, ARC.yellow, ARC.white, ARC.b4];
        for (var c = 0; c < cols.length; c++) {
          seed(1670 + c); var bits = [];
          for (var i = 0; i < 14; i++) { var x = OX + between(-120, 120), y = OY + between(-200, 200), a = Math.atan2(y - OY, x - OX), d = t * between(8, 20); bits.push(rect(snap(x + Math.cos(a) * d), snap(y + Math.sin(a) * d + t * t * 0.3), snap(x + Math.cos(a) * d) + PX * 2, snap(y + Math.sin(a) * d + t * t * 0.3) + PX * 2)); }
          polys(fr.main, bits, cols[c], o);
        }
      }
    }
  }
};

// ===== Fanzine — a photocopy: torn scraps on black toner, tape, a highlighter, a pink marker, the copier's light =
var ZIN = { paper: [0.95, 0.94, 0.9], gray: [0.6, 0.6, 0.58], toner: [0.07, 0.07, 0.07], hi: [1, 0.95, 0.15], pink: [1, 0.2, 0.55], tape: [0.92, 0.88, 0.72], light: [0.85, 1, 0.9] };
function scrap(x, y, w, h, ang, base) {   // a torn piece of page
  seed(base); var v = [], n = 7;
  for (var i = 0; i <= n; i++) v.push([-w + 2 * w * i / n, -h + between(-6, 6)]);
  for (var j = 0; j <= n; j++) v.push([w + between(-6, 6), -h + 2 * h * j / n]);
  for (var k = 0; k <= n; k++) v.push([w - 2 * w * k / n, h + between(-6, 6)]);
  for (var m = 0; m <= n; m++) v.push([-w + between(-6, 6), h - 2 * h * m / n]);
  return place(v, x, y, ang);
}
function tapeStrip(x, y, len, ang) { return place([[-len, -18], [-len + 8, -10], [-len, -2], [-len + 8, 6], [-len, 18], [len, 18], [len - 8, 10], [len, 2], [len - 8, -6], [len, -18]], x, y, ang); }
function loop(cx, cy, rx, ry, u, turn) {   // a marker's loop, twice round, not quite closing
  var v = [];
  for (var i = 0; i <= 90 * clamp01(u); i++) { var a = turn + i / 90 * Math.PI * 4.1, w = 1 + 0.06 * Math.sin(i * 0.3); v.push([cx + Math.cos(a) * rx * w, cy + Math.sin(a) * ry * w]); }
  return v;
}
function grain(L, f, n, base, color, o) { seed(base + f); var g = []; for (var i = 0; i < n; i++) { var x = between(0, 1080), y = between(0, 1080), s = between(1, 3); g.push(place(sq(s), x, y, 0)); } polys(L, g, color, o); }
var ZIN_SCRAPS = [[200, 220, 170, 120, -0.2], [820, 180, 160, 140, 0.15], [880, 760, 190, 130, -0.1], [190, 820, 150, 160, 0.2], [540, 120, 120, 70, 0.05], [540, 980, 140, 70, -0.08]];
function collage(fr, f, o, out) {
  var j = Math.floor(f / 3), papers = [], grays = [], tapes = [], hl = [];
  for (var i = 0; i < ZIN_SCRAPS.length; i++) {
    var s = ZIN_SCRAPS[i], dx = (s[0] - C) * out, dy = (s[1] - C) * out;
    seed(1700 + i * 7 + j); var jx = between(-3, 3), jy = between(-3, 3);
    (i % 2 ? grays : papers).push(scrap(s[0] + dx + jx, s[1] + dy + jy, s[2], s[3], s[4], 1710 + i));
    tapes.push(tapeStrip(s[0] + dx - s[2] * 0.6, s[1] + dy - s[3], 60, s[4] - 0.5));
    if (i % 3 === 0) hl.push(place(rect(-s[2] * 0.7, -10, s[2] * 0.5, 22), s[0] + dx, s[1] + dy + s[3] * 0.3, s[4]));
  }
  polys(fr.main, tapes, ZIN.tape, o * 0.8);
  polys(fr.main, hl, ZIN.hi, o * 0.7);
  var lines1 = [];
  for (var p = 0; p < papers.length; p++) { var c = papers[p][0]; lines1.push([[c[0] + 30, c[1] + 50], [c[0] + 200, c[1] + 50]], [[c[0] + 30, c[1] + 80], [c[0] + 160, c[1] + 80]]); }
  lines(fr.main, lines1, ZIN.toner, 7, o);
  polys(fr.main, papers, ZIN.paper, o); polys(fr.main, grays, ZIN.gray, o);
}
var ED_ZINE = {
  title: function (fr, f, u) {
    grain(fr.top, f, 120, 1730, ZIN.paper, 50);
    var bar = ((f * 60) % 1500) - 200; polys(fr.glow, [rect(bar - 40, -60, bar + 40, 1140)], ZIN.light, 70);
    lines(fr.main, [loop(C, C, 360 + u * 20, 200, ease(f / 14), -0.4)], ZIN.pink, 14, 100);
    lines(fr.main, [star5(820, 470, 70, f * 0.05, 0.42), star5(250, 520, 50, -f * 0.05, 0.42)], ZIN.hi, 8, 100, true);
    collage(fr, f, 100, 0);
    polys(fr.bg, [full()], ZIN.toner, 100);
  },
  wipe: function (fr, v) {   // the copier's light passes: a white page behind it, then the page goes
    var x = -60 + v * 1300;
    polys(fr.top, [rect(x - 30, -60, x + 30, 1140)], ZIN.light, 100);
    polys(fr.top, [v < 0.5 ? rect(-60, -60, x, 1140) : rect(x, -60, 1140, 1140)], ZIN.paper, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // scraps and tape thrown out; the marker rings the card
      polys(fr.main, flung(at, 14, 1750, function (x, y, s, t, i) { return [scrap(x, y, 30 * s, 22 * s, t, 1760 + i)]; }, 20), ZIN.paper, fade(at, 30, 50) * o);
      polys(fr.main, flung(at, 8, 1770, function (x, y, s, t) { return [tapeStrip(x, y, 40 * s, t)]; }, 16), ZIN.tape, fade(at, 30, 50) * o);
    }
    lines(fr.main, [loop(C, C, 330, 420, ease((f - CARD_AT) / 14), -0.6)], ZIN.pink, 12, o);
    var arrows = [[[150, 300], [300, 380]], [[300, 380], [270, 330]], [[300, 380], [250, 395]], [[930, 760], [790, 690]], [[790, 690], [835, 680]], [[790, 690], [815, 730]]];
    lines(fr.main, arrows, ZIN.hi, 9, o * g);
    collage(fr, f, o, 0.2 + 0.25 * g);
    grain(fr.main, f, 80, 1780, ZIN.paper, 35);
    polys(fr.bg, [full()], ZIN.toner, o);
  },
  over: function (fr, f, at) {
    if (at >= 0) {   // tape slapped over the card's top corners
      var s = at < 2 ? 1.3 - at * 0.15 : 1;
      polys(fr.main, [tapeStrip(C - 150, C - 205, 70 * s, -0.7), tapeStrip(C + 150, C - 205, 70 * s, 0.7)], ZIN.tape, 70);
      seed(1790); var stars = []; for (var i = 0; i < 8; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 170, 230) + between(30, 110); if ((f + i * 3) % 8 < 5) stars.push(star5(C + Math.cos(a) * r, C + Math.sin(a) * r, 26, i, 0.42)); }
      lines(fr.main, stars, ZIN.pink, 6, 100, true);
    }
    bigGlint(fr, at, ZIN.hi);
  },
  opening: function (comp) {   // crossed out in pink marker, then torn to scraps
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 6 && f < 30) lines(fr.top, partOf([[[OX - 150, OY - 220], [OX + 150, OY + 220]]], ease((f - 6) / 4)).concat(partOf([[[OX + 150, OY - 220], [OX - 150, OY + 220]]], ease((f - 12) / 4))), ZIN.pink, 26, fade(f, 26, 30) * 100);
      if (f >= 26) {
        var t = f - 26, o = fade(f, 50, 63) * 100, pieces = [], dark = [];
        seed(1800);
        for (var i = 0; i < 22; i++) { var a = between(0, Math.PI * 2), d = 30 + t * between(10, 24); (i % 3 ? pieces : dark).push(scrap(OX + Math.cos(a) * d, OY + Math.sin(a) * d * 1.2 + t * t * 0.5, between(18, 36), between(14, 28), t * 0.12 + i, 1810 + i)); }
        polys(fr.main, dark, ZIN.gray, o); polys(fr.main, pieces, ZIN.paper, o);
      }
    }
  }
};

// ===== Bulle — translucent Y2K: candy-blue plastic, bubbles rising, a rain of green code ======================
var BUB = { deep: [0.02, 0.07, 0.2], aqua: [0.2, 0.68, 1], candy: [0.5, 0.86, 1], code: [0.3, 1, 0.55], pink: [1, 0.55, 0.88], lime: [0.7, 1, 0.3] };
function bubbles(L, list, o, tint) {   // [x, y, r]: a faint fill, a rim, a gloss, a glint
  var fills = [], rims = [], gloss = [], arcs = [];
  for (var i = 0; i < list.length; i++) {
    var x = list[i][0], y = list[i][1], r = list[i][2];
    fills.push(circle(x, y, r, 1, 28)); rims.push(ring(x, y, r, 1));
    gloss.push(place(circle(0, 0, r * 0.2, 0.55, 14), x - r * 0.42, y - r * 0.46, -0.75)); arcs.push(ring(x, y, r * 0.78, 1, Math.PI * 0.15, Math.PI * 0.45));
  }
  polys(L, gloss, WHITE, o * 0.9); lines(L, arcs, WHITE, 3, o * 0.6);
  lines(L, rims, tint || BUB.candy, 3.5, o * 0.9); polys(L, fills, tint || BUB.candy, o * 0.16);
}
function codeRain(L, glowL, f, o) {
  var heads = [], tails = [];
  for (var x = 10; x < 1080; x += 36) {
    seed(1900 + x); var sp = between(14, 30), y = ((f * sp + between(0, 1400)) % 1500) - 200, n = Math.round(between(6, 14));
    for (var k = 0; k < n; k++) { var yy = y - k * 26, l = between(6, 16); (k === 0 ? heads : tails).push([[x, yy], [x, yy + l]]); }
  }
  lines(glowL, heads, BUB.code, 10, o); lines(L, heads, WHITE, 5, o); lines(L, tails, BUB.code, 5, o * 0.55);
}
function rising(f, n, base, x0, x1, rMin, rMax, speed) {
  seed(base); var list = [];
  for (var i = 0; i < n; i++) { var x = between(x0, x1), sp = between(0.6, 1.4) * speed, r = between(rMin, rMax); list.push([x + Math.sin(f * 0.1 + i) * 16, 1180 - ((f * sp + between(0, 1400)) % 1400), r]); }
  return list;
}
var ED_BUBBLE = {
  title: function (fr, f, u) {
    bubbles(fr.top, rising(f, 22, 1910, 0, 1080, 16, 70, 14), 100);
    var stripes = []; for (var y = -60; y < 1140; y += 14) stripes.push([[-60, y], [1140, y]]);
    lines(fr.main, stripes, WHITE, 2, 5);
    codeRain(fr.main, fr.glow, f, 70);
    polys(fr.haze, [circle(C, C, 420 + u * 40, 1, 40)], BUB.aqua, 28);
    polys(fr.bg, [full()], BUB.deep, 100);
  },
  wipe: function (fr, v) {   // a huge bubble swells over the screen, then pops
    if (v < 0.6) { var r = 60 + (v / 0.6) * 950; bubbles(fr.top, [[C, C, r]], 100); polys(fr.top, [circle(C, C, r, 1, 64)], BUB.candy, 85); }
    else { var t = (v - 0.6) / 0.4, drops = []; for (var i = 0; i < 24; i++) { var a = i / 24 * Math.PI * 2; drops.push(circle(C + Math.cos(a) * (900 + t * 300), C + Math.sin(a) * (900 + t * 300), 26 * (1 - t), 1, 12)); } polys(fr.top, drops, BUB.candy, 100); }
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // bubbles burst out of the card and pop: rings and droplets
      var popped = flung(at, 14, 1930, function (x, y, s) { return [[x, y, 30 * s + 6]]; }, 18), list = [];
      for (var i = 0; i < popped.length; i++) list.push(popped[i]);
      if (at < 16) bubbles(fr.main, list, fade(at, 8, 16) * o);
      if (at >= 6) { var rings = []; for (var j = 0; j < list.length; j++) rings.push(ring(list[j][0], list[j][1], list[j][2] * (1 + (at - 6) * 0.25), 1)); lines(fr.main, rings, WHITE, 3, fade(at, 12, 22) * o); }
      lines(fr.glow, [ring(C, C, 260 + at * 36, 1.25)], BUB.candy, 18, fade(at, 6, 14) * o);
    }
    bubbles(fr.main, rising(f, 26, 1940, 0, 1080, 14, 64, 12), o);
    // the glossy orb behind the card
    polys(fr.main, [place(circle(0, 0, 130 * g, 0.45, 32), C - 160, C - 260, -0.5)], WHITE, o * 0.35);
    polys(fr.main, [circle(C, C, 420 * g + 1, 1, 64)], BUB.aqua, o * 0.35);
    lines(fr.main, [ring(C, C, 420 * g + 1, 1)], BUB.candy, 6, o);
    codeRain(fr.main, fr.glow, f, o * 0.5);
    polys(fr.haze, [circle(C, C, 460 * g + 60, 1, 40)], BUB.aqua, o * 0.32);
    polys(fr.bg, [full()], BUB.deep, o);
  },
  over: function (fr, f, at) {
    if (at >= 0) bubbles(fr.main, rising(f, 12, 1960, 260, 820, 8, 26, 16), 90);
    bigGlint(fr, at, BUB.candy);
  },
  opening: function (comp) {   // a bubble closes round the pack, carries it up a little, and pops
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      var lift = 32 * ease(f / 26), cy = OY - lift;
      if (f >= 2 && f < 27) { var r = 280 * ease((f - 2) / 8) + 1; bubbles(fr.main, [[OX, cy, r]], 100); }
      if (f >= 26 && f < 46) {
        var t = f - 26, drops = [], o = fade(t, 10, 20) * 100;
        for (var i = 0; i < 28; i++) { var a = i / 28 * Math.PI * 2; drops.push(circle(OX + Math.cos(a) * (280 + t * 22), cy + Math.sin(a) * (280 + t * 22) + t * t * 0.4, 12 * (1 - t / 20), 1, 10)); }
        polys(fr.main, drops, BUB.candy, o); lines(fr.glow, [ring(OX, cy, 280 + t * 30, 1)], BUB.candy, 14, o);
        if (t < 3) polys(fr.top, [circle(OX, cy, 320, 1, 40)], WHITE, 60 - t * 20);
      }
      if (f >= 28) bubbles(fr.top, rising(f, 10, 1980, OX - 250, OX + 250, 8, 22, 18), fade(f, 52, 63) * 100);
    }
  }
};

// ===== DVD — the filigree showcase: a rose window of stained glass, gold leading, a damask, light and embers ====
var DVD = { night: [0.06, 0.02, 0.05], wine: [0.24, 0.035, 0.08], wine_l: [0.36, 0.07, 0.12], gold: [0.88, 0.68, 0.28], gold_l: [1, 0.9, 0.58], ruby: [0.85, 0.1, 0.18], sapph: [0.15, 0.3, 0.85], emer: [0.1, 0.62, 0.35], amber: [1, 0.62, 0.12], violet: [0.5, 0.2, 0.75], light: [1, 0.95, 0.82] };
var DVD_GLASS = [DVD.ruby, DVD.sapph, DVD.emer, DVD.amber, DVD.violet];
function pane(cx, cy, r0, r1, a0, a1) { var v = [], n = 6; for (var i = 0; i <= n; i++) { var a = a0 + (a1 - a0) * i / n; v.push([cx + Math.cos(a) * r1, cy + Math.sin(a) * r1]); } for (var j = n; j >= 0; j--) { var b = a0 + (a1 - a0) * j / n; v.push([cx + Math.cos(b) * r0, cy + Math.sin(b) * r0]); } return v; }
function roseWindow(fr, cx, cy, r, rot, o) {
  var radii = [0.2, 0.48, 0.76, 1], counts = [1, 8, 16, 24], byColour = [[], [], [], [], []], lead = [];
  for (var k = 0; k < radii.length; k++) {
    var r0 = k ? radii[k - 1] * r : 0, r1 = radii[k] * r, n = counts[k], turn = rot * (k % 2 ? 1 : -1);
    lead.push(ring(cx, cy, r1, 1));
    for (var i = 0; i < n; i++) {
      var a0 = turn + i / n * Math.PI * 2, a1 = turn + (i + 1) / n * Math.PI * 2;
      byColour[(i + k * 2) % 5].push(k ? pane(cx, cy, r0, r1, a0, a1) : circle(cx, cy, r1, 1, 24));
      if (k) lead.push([[cx + Math.cos(a0) * r0, cy + Math.sin(a0) * r0], [cx + Math.cos(a0) * r1, cy + Math.sin(a0) * r1]]);
    }
  }
  lines(fr.main, lead, DVD.gold, Math.max(3, r * 0.018), o);
  for (var c = 0; c < 5; c++) { polys(fr.glow, byColour[c], DVD_GLASS[c], o * 0.5); polys(fr.main, byColour[c], DVD_GLASS[c], o); }
  polys(fr.main, [circle(cx, cy, r * 1.06, 1, 72)], DVD.gold, o);
}
function damask(L, o) {   // a lattice of diamonds and little lilies, darker on the wine
  var d = [];
  for (var y = -60; y < 1140; y += 120) for (var x = -60 + (y / 120 % 2) * 60; x < 1140; x += 120) d.push(place([[0, -34], [18, 0], [0, 34], [-18, 0]], x, y, 0));
  polys(L, d, DVD.wine_l, o);
}
function filigree(L, x, y, s, flip, o) { lines(L, [spiral(x, y, 4, s, 1.6, 1, flip ? Math.PI : 0, 1, 0), spiral(x + (flip ? -1 : 1) * s * 0.9, y + s * 0.4, 3, s * 0.6, 1.4, 1, flip ? 0 : Math.PI, 1, 0)], DVD.gold, 5, o); }
function embers(f, n, base, x0, x1) { seed(base); var list = []; for (var i = 0; i < n; i++) list.push([between(x0, x1) + Math.sin(f * 0.15 + i) * 18, 1160 - ((f * between(6, 12) + between(0, 1200)) % 1250), between(3, 7)]); return list; }
var ED_DISC = {
  title: function (fr, f, u) {
    polys(fr.top, glintPolys(embers(f, 26, 2000, 0, 1080)), DVD.amber);
    fan(fr.glow, C, -200, 8, f * 0.003, 1500, DVD.light, null, 30, 0, 0.35, Math.PI * 0.3, Math.PI * 0.7);
    roseWindow(fr, C, C - 40, 470 + u * 20, f * 0.006, 100);
    filigree(fr.main, 90, 90, 80, false, 100); filigree(fr.main, 990, 90, 80, true, 100); filigree(fr.main, 90, 990, 80, false, 100); filigree(fr.main, 990, 990, 80, true, 100);
    damask(fr.main, 100);
    polys(fr.bg, [full()], DVD.wine, 100);
  },
  wipe: function (fr, v) {   // the window flares white
    var r = 1100 * Math.sin(v * Math.PI);
    polys(fr.top, [circle(C, C - 40, Math.max(1, r), 1, 64)], DVD.light, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // the glass bursts: shards of every colour flung out, gold sparks
      for (var c = 0; c < 5; c++) polys(fr.main, flung(at, 6, 2010 + c, function (x, y, s, t) { return [place([[0, -1], [0.7, 0.6], [-0.5, 0.8]], x, y, t, 30 * s, 30 * s)]; }, 22), DVD_GLASS[c], fade(at, 30, 46) * o);
      polys(fr.top, glintPolys(flung(at, 16, 2020, function (x, y, s) { return [[x, y, 10 * s]]; }, 26)), DVD.gold_l);
      fan(fr.glow, C, C, 16, at * 0.01, 300 + at * 50, DVD.light, null, fade(at, 8, 20) * o * 0.8, 0, 0.4);
    }
    polys(fr.top, glintPolys(embers(f, 20, 2030, 80, 1000)), DVD.amber);
    fan(fr.glow, C, C, 12, -(f - CARD_AT) * 0.004, 900, DVD.light, null, o * 0.25, 0, 0.3);
    filigree(fr.main, 110, 110, 90, false, o); filigree(fr.main, 970, 110, 90, true, o); filigree(fr.main, 110, 970, 90, false, o); filigree(fr.main, 970, 970, 90, true, o);
    roseWindow(fr, C, C, 300 + 200 * g, (f - CARD_AT) * 0.006, o);
    damask(fr.main, o);
    polys(fr.bg, [full()], DVD.wine, o);
  },
  over: function (fr, f, at) {
    if (at >= 0) polys(fr.top, glintPolys(embers(f, 14, 2050, 200, 880)), DVD.gold_l);
    bigGlint(fr, at, DVD.gold);
  },
  opening: function (comp) {   // light floods the pack like a window; it shatters into stained glass
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 6 && f < 26) fan(fr.glow, OX, OY, 10, f * 0.02, 200 + (f - 6) * 22, DVD.light, null, 70, 0, 0.4);
      if (f >= 24) {
        var t = f - 24, o = fade(f, 50, 63) * 100;
        for (var c = 0; c < 5; c++) {
          seed(2060 + c); var shards = [];
          for (var i = 0; i < 8; i++) { var x = OX + between(-120, 120), y = OY + between(-200, 200), a = Math.atan2(y - OY, x - OX), d = t * between(8, 22), s = between(20, 40); shards.push(place([[0, -1], [0.8, 0.5], [-0.6, 0.9]], x + Math.cos(a) * d, y + Math.sin(a) * d + t * t * 0.4, t * between(-0.2, 0.2) + i, s, s)); }
          polys(fr.main, shards, DVD_GLASS[c], o); lines(fr.main, shards, DVD.gold, 3, o, true);
        }
        if (t < 3) polys(fr.top, [circle(OX, OY, 420, 1, 40)], DVD.light, 70 - t * 23);
      }
    }
  }
};

// ===== Cuir & lin — skeuomorphic: stitched leather, brass, a watercolour sky, clouds drifting, balloons rising ===
var LEA = { leather: [0.45, 0.26, 0.14], leather_d: [0.27, 0.14, 0.07], stitch: [0.96, 0.86, 0.62], brass: [0.88, 0.7, 0.32], brass_l: [1, 0.9, 0.6], sky: [0.56, 0.76, 0.93], sky_l: [0.84, 0.92, 0.98], cloud: [1, 1, 1], cloud_d: [0.85, 0.9, 0.96], basket: [0.5, 0.32, 0.16], ribbon: [0.82, 0.14, 0.2], ribbon_d: [0.55, 0.06, 0.12] };
var LEA_BALLOONS = [[0.92, 0.3, 0.28], [0.98, 0.76, 0.25], [0.3, 0.6, 0.86], [0.45, 0.76, 0.4], [0.7, 0.42, 0.85]];
function balloon(x, y, s) {   // an envelope (a teardrop), its light gores, its basket on two ropes
  var env = [], gore = [];
  for (var i = 0; i < 32; i++) { var a = i / 32 * Math.PI * 2, r = 1 - 0.35 * Math.max(0, Math.sin(a)); env.push([x + Math.cos(a) * s * r * (1 - 0.25 * Math.max(0, Math.sin(a))), y + Math.sin(a) * s * (Math.sin(a) > 0 ? 1.25 : 1)]); }
  gore.push(place([[-0.12, -1], [0.12, -1], [0.1, 1.1], [-0.1, 1.1]], x, y, 0, s, s));
  return { env: env, gore: gore, basket: rect(x - s * 0.18, y + s * 1.5, x + s * 0.18, y + s * 1.78), ropes: [[[x - s * 0.3, y + s * 1.05], [x - s * 0.16, y + s * 1.5]], [[x + s * 0.3, y + s * 1.05], [x + s * 0.16, y + s * 1.5]]] };
}
function balloons(fr, list, o) {   // [x, y, s, colour index]
  var baskets = [], ropes = [], gores = [], envs = [[], [], [], [], []];
  for (var i = 0; i < list.length; i++) { var b = balloon(list[i][0], list[i][1], list[i][2]); baskets.push(b.basket); ropes = ropes.concat(b.ropes); gores = gores.concat(b.gore); envs[list[i][3] % 5].push(b.env); }
  polys(fr.main, baskets, LEA.basket, o); lines(fr.main, ropes, LEA.basket, 2, o);
  polys(fr.main, gores, WHITE, o * 0.3);
  for (var c = 0; c < 5; c++) polys(fr.main, envs[c], LEA_BALLOONS[c], o);
}
function clouds(fr, f, n, base, y0, y1, o) {
  seed(base); var light = [], shade = [];
  for (var i = 0; i < n; i++) { var x = ((between(0, 1400) + f * between(1, 3)) % 1500) - 200, y = between(y0, y1), p = puff(x, y, between(70, 140), 6); light = light.concat(p[0]); shade = shade.concat(p[1]); }
  polys(fr.main, light, LEA.cloud, o); polys(fr.main, shade, LEA.cloud_d, o);
}
function leatherFrame(fr, inset, o) {   // a stitched leather rim round the screen, brass rivets at its corners
  var d = inset, riv = [[d * 0.5, d * 0.5], [1080 - d * 0.5, d * 0.5], [1080 - d * 0.5, 1080 - d * 0.5], [d * 0.5, 1080 - d * 0.5]], rivets = [], shine = [];
  for (var i = 0; i < 4; i++) { rivets.push(circle(riv[i][0], riv[i][1], 16, 1, 16)); shine.push(circle(riv[i][0] - 5, riv[i][1] - 5, 5, 1, 8)); }
  polys(fr.main, shine, LEA.brass_l, o); polys(fr.main, rivets, LEA.brass, o);
  lines(fr.main, [rect(d - 18, d - 18, 1098 - d, 1098 - d)], LEA.stitch, 4, o, true, [16, 10]);
  polys(fr.main, [rect(-60, -60, 1140, 1140), rect(d, d, 1080 - d, 1080 - d)], LEA.leather, o, true);
}
function sky(fr, o) { polys(fr.bg, [rect(-60, 560, 1140, 1140)], LEA.sky_l, o * 0.7); polys(fr.bg, [full()], LEA.sky, o); }
var ED_LEATHER = {
  title: function (fr, f, u) {
    leatherFrame(fr, 70, 100);
    seed(2100); var list = [];
    for (var i = 0; i < 9; i++) list.push([between(120, 960), 1180 - ((f * between(3, 6) + between(0, 1300)) % 1400), between(30, 70), i]);
    balloons(fr, list, 100);
    clouds(fr, f, 7, 2110, 100, 900, 100);
    sky(fr, 100);
  },
  wipe: function (fr, v) {   // the leather cover swings shut over the screen, and open again
    var w = 1240 * Math.sin(v * Math.PI);
    lines(fr.top, [rect(-60 + 30, 30, -60 + w - 30, 1050)], LEA.stitch, 5, 100, true, [18, 12]);
    polys(fr.top, [rect(-60 + w - 160, 480, -60 + w - 40, 600)], LEA.brass, 100);
    polys(fr.top, [rect(-60, -60, -60 + w, 1140)], LEA.leather_d, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // a flock of balloons let go from below, brass glints
      seed(2130); var rise = [];
      for (var i = 0; i < 14; i++) { var t = at - between(0, 8), x = between(60, 1020), sp = between(28, 46), s = between(30, 60); if (t >= 0) rise.push([x, 1200 - t * sp, s, i]); }
      balloons(fr, rise, o);
      polys(fr.top, glintPolys(flung(at, 12, 2140, function (x, y, s) { return [[x, y, 12 * s]]; }, 22)), LEA.brass_l);
    }
    seed(2150); var list = [];
    for (var j = 0; j < 7; j++) { var a = j / 7 * Math.PI * 2 + 0.4, d = 430 + 40 * Math.sin(f * 0.08 + j); list.push([C + Math.cos(a) * d, C + Math.sin(a) * d * 1.05 - (f - CARD_AT) * 1.5, 46 + (j % 3) * 10, j]); }
    balloons(fr, list, o * g);
    leatherFrame(fr, 40 + 30 * (1 - g), o);
    clouds(fr, f, 6, 2160, 120, 960, o);
    sky(fr, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 40) {   // a satin ribbon drifting across, turning
      var pts = []; for (var i = 0; i <= 40; i++) pts.push([-120 + i * 34 + at * 10, 900 + Math.sin(i * 0.3 + at * 0.25) * 40 - at * 4]);
      var rb = ribbon(pts, 34, 6, at * 0.3);
      polys(fr.main, rb[0], LEA.ribbon, fade(at, 28, 40) * 100); polys(fr.main, rb[1], LEA.ribbon_d, fade(at, 28, 40) * 100);
    }
    bigGlint(fr, at, LEA.brass);
  },
  opening: function (comp) {   // balloons tied to the pack fill, and lift it away into the sky
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      var lift = f < 24 ? 0 : (f - 24) / 14 * 536 + Math.max(0, f - 38) * 20, top = OY - 200 - lift, o = fade(f, 50, 63) * 100;
      if (f >= 4) {
        var s = 60 * ease((f - 4) / 12), spots = [[OX - 110, top - 230], [OX, top - 280], [OX + 110, top - 230]], list = [], ropes = [];
        for (var i = 0; i < 3; i++) { list.push([spots[i][0], spots[i][1], s, i * 2]); ropes.push([[spots[i][0], spots[i][1] + s * 1.2], [OX - 40 + i * 40, top]]); }
        lines(fr.main, ropes, LEA.basket, 3, o); balloons(fr, list, o);
      }
    }
  }
};

// ===== Tuiles — flat design: a mosaic of flat tiles turning over in a wave, a flat sun, long shadows =========
var TIL = { dark: [0.1, 0.1, 0.12], white: [1, 1, 1] };
var TCOL = [[0, 0.67, 0.66], [0.97, 0.58, 0.1], [0.88, 0.3, 0.24], [0.13, 0.5, 0.78], [0.55, 0.76, 0.2], [0.6, 0.33, 0.72], [0.9, 0.2, 0.55]];
function tiles(L, f, cell, gap, speed, o, hole) {   // each tile turns over as the wave passes, a new colour behind
  var byColour = [[], [], [], [], [], [], []];
  for (var j = -1; j * cell < 1140; j++) for (var i = -1; i * cell < 1140; i++) {
    var x = i * cell, y = j * cell; if (hole && Math.abs(x + cell / 2 - C) < hole[0] && Math.abs(y + cell / 2 - C) < hole[1]) continue;
    var s = f * speed - (i + j) * 0.09, k = Math.floor(s), fr = s - k, w = 1;
    if (fr < 0.16) w = Math.abs(Math.cos(fr / 0.16 * Math.PI));
    var col = ((i * 7 + j * 3 + 70) % 7 + k + (fr > 0.08 && fr < 0.16 ? 1 : 0)) % 7;
    if (col < 0) col += 7;
    var half = (cell - gap) / 2 * w;
    byColour[col].push(rect(x + cell / 2 - half, y + gap / 2, x + cell / 2 + half, y + cell - gap / 2));
  }
  for (var c = 0; c < 7; c++) polys(L, byColour[c], TCOL[c], o);
}
function longShadow(cx, cy, hw, hh, len) { return [[cx + hw, cy - hh], [cx + hw + len, cy - hh + len], [cx - hw + len, cy + hh + len], [cx - hw, cy + hh]]; }
var ED_TILES = {
  title: function (fr, f, u) {
    var r = 170 + 14 * Math.sin(f * 0.35);
    polys(fr.main, [circle(C, C, r, 1, 64)], TCOL[1], 100);
    polys(fr.main, [[[C - r * 0.707, C - r * 0.707], [C + r * 0.707, C + r * 0.707], [C + r * 0.707 + 900, C + r * 0.707 + 900], [C - r * 0.707 + 900, C - r * 0.707 + 900]], circle(C + 450, C + 450, r, 1, 64)], [0, 0, 0], 22);
    tiles(fr.main, f, 135, 10, 0.06, 100);
    polys(fr.bg, [full()], TIL.dark, 100);
  },
  wipe: function (fr, v) {   // tiles turn over to the dark in a wave, and back
    var cells = [];
    for (var j = 0; j < 9; j++) for (var i = 0; i < 9; i++) { var p = clamp01(v * 2.2 - (i + j) * 0.06), q = clamp01((v - 0.5) * 2.2 - (i + j) * 0.06), w = v < 0.5 ? p : 1 - q, x = -60 + i * 135; cells.push(rect(x + 67 - 68 * w, -60 + j * 135, x + 67 + 68 * w, 75 + j * 135)); }
    polys(fr.top, cells, TIL.dark, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // flat squares flung out (no turning: flat), a flat ring growing
      for (var c = 0; c < 7; c++) polys(fr.main, flung(at, 4, 2200 + c, function (x, y, s) { return [rect(x - 18 * s, y - 18 * s, x + 18 * s, y + 18 * s)]; }, 22), TCOL[c], fade(at, 30, 46) * o);
      lines(fr.main, [ring(C, C, 260 + at * 36, 1.3)], TIL.white, 10, fade(at, 6, 14) * o);
    }
    lines(fr.main, [ring(C, C, 330 * g + 1, 1.3)], TIL.white, 4, o);
    polys(fr.main, [longShadow(C, C, 150, 210, 900 * g)], [0, 0, 0], o * 0.28);
    tiles(fr.main, f, 120, 10, 0.05, o);
    polys(fr.bg, [full()], TIL.dark, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 14) {   // the foil as flat stripes sweeping over
      var x = -300 + at * 110, st = [];
      for (var k = 0; k < 3; k++) st.push([[x + k * 70, -60], [x + k * 70 + 36, -60], [x + k * 70 + 36 - 400, 1140], [x + k * 70 - 400, 1140]]);
      polys(fr.main, st, TIL.white, 35);
    }
    bigGlint(fr, at, TCOL[0]);
  },
  opening: function (comp) {   // the pack breaks into a grid of tiles turning over and away, in a wave
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 18) {
        var byColour = [[], [], [], [], [], [], []], t = f - 18;
        for (var j = 0; j < 7; j++) for (var i = 0; i < 4; i++) {
          var x = OX - 120 + i * 60 + 30, y = OY - 200 + j * 57 + 28, d = t - (i + j) * 1.4, w = d < 0 ? 1 : Math.abs(Math.cos(Math.min(d, 8) * 0.4)), out = Math.max(0, d) * 14, a = Math.atan2(y - OY, x - OX);
          if (d > 10) continue;
          byColour[(i * 3 + j * 5) % 7].push(rect(x + Math.cos(a) * out - 26 * w, y + Math.sin(a) * out - 25, x + Math.cos(a) * out + 26 * w, y + Math.sin(a) * out + 25));
        }
        for (var c = 0; c < 7; c++) polys(fr.main, byColour[c], TCOL[c], 100);
      }
    }
  }
};

// ===== Streaming — holo-tech: a neon grid floor, a haze on the horizon, corner brackets, a scan, a glitch =======
var HOL = { dark: [0.015, 0.015, 0.06], cyan: [0.2, 0.95, 1], magenta: [1, 0.15, 0.6], violet: [0.45, 0.22, 1], white: [1, 1, 1] };
function gridFloor(fr, f, horizon, o) {
  var v = [], h = [];
  for (var k = -14; k <= 14; k++) v.push([[C + k * 20, horizon], [C + k * 160, 1140]]);
  for (var q = 0; q < 12; q++) { var z = ((q + f * 0.12) % 12) / 12, y = horizon + (1140 - horizon) * z * z; h.push([[-60, y], [1140, y]]); }
  lines(fr.glow, v.concat(h), HOL.violet, 8, o); lines(fr.main, v.concat(h), HOL.cyan, 2.5, o);
}
function brackets(cx, cy, hw, hh, len) {
  return [[[cx - hw, cy - hh + len], [cx - hw, cy - hh], [cx - hw + len, cy - hh]], [[cx + hw - len, cy - hh], [cx + hw, cy - hh], [cx + hw, cy - hh + len]],
          [[cx + hw, cy + hh - len], [cx + hw, cy + hh], [cx + hw - len, cy + hh]], [[cx - hw + len, cy + hh], [cx - hw, cy + hh], [cx - hw, cy + hh - len]]];
}
function buffering(fr, cx, cy, r, f, o) {   // the stream's loading ring: dots chasing round
  var hot = [], warm = [], cold = [];
  for (var i = 0; i < 12; i++) { var a = i / 12 * Math.PI * 2 - Math.PI / 2, d = (i - f + 1200) % 12, dot = circle(cx + Math.cos(a) * r, cy + Math.sin(a) * r, r * 0.09, 1, 14); (d === 0 ? hot : d < 4 ? warm : cold).push(dot); }
  polys(fr.glow, hot.concat(warm), HOL.cyan, o); polys(fr.main, hot, HOL.white, o); polys(fr.main, warm, HOL.cyan, o * 0.7); polys(fr.main, cold, HOL.violet, o * 0.35);
}
function glitch(L, f, base, o) { seed(base + f); var bars = [], cols = [HOL.cyan, HOL.magenta]; for (var c = 0; c < 2; c++) { bars = []; for (var i = 0; i < 4; i++) { var y = between(0, 1080), x = between(-100, 600); bars.push(rect(x, y, x + between(200, 700), y + between(6, 26))); } polys(L, bars, cols[c], o); } }
function motes(f, n, base, x0, x1) { seed(base); var list = []; for (var i = 0; i < n; i++) { var x = between(x0, x1), y = 1140 - ((f * between(4, 10) + between(0, 1200)) % 1250), s = between(2, 5); list.push(rect(x - s, y - s, x + s, y + s)); } return list; }
var ED_STREAM = {
  title: function (fr, f, u) {
    if (f % 7 === 3 || f % 11 === 5) glitch(fr.top, f, 2300, 80);
    lines(fr.main, brackets(C, C, 470, 470, 90), HOL.cyan, 8, 100);
    buffering(fr, C, C - 120, 170, f, 100);
    polys(fr.main, motes(f, 30, 2310, 0, 1080), HOL.cyan, 80);
    gridFloor(fr, f, 640, 100);
    polys(fr.haze, [rect(-60, 560, 1140, 700)], HOL.magenta, 90);
    polys(fr.bg, [full()], HOL.dark, 100);
  },
  wipe: function (fr, v) {   // a scan line falls: the dark behind it, then it lifts
    var y = -60 + v * 1200;
    polys(fr.glow, [rect(-60, y - 30, 1140, y + 30)], HOL.cyan, 100); polys(fr.top, [rect(-60, y - 4, 1140, y + 4)], HOL.white, 100);
    polys(fr.top, [v < 0.5 ? rect(-60, -60, 1140, y) : rect(-60, y, 1140, 1140)], HOL.dark, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // the hologram locks: rings rising off the platform, the loading dots flung out, a glitch
      for (var k = 0; k < 3; k++) { var t = at - k * 4; if (t >= 0 && t < 16) lines(fr.glow, [ring(C, C + 300 - t * 30, 260 + t * 8, 0.25)], HOL.cyan, 12, fade(t, 8, 16) * o); }
      polys(fr.main, flung(at, 12, 2320, function (x, y, s) { return [circle(x, y, 14 * s, 1, 12)]; }, 24), HOL.cyan, fade(at, 24, 40) * o);
      if (at < 6) glitch(fr.top, f, 2330, 70);
    }
    var sx = ((f * 22) % 1400) - 160; polys(fr.glow, [rect(sx - 20, -60, sx + 20, 1140)], HOL.cyan, o * 0.35);
    lines(fr.main, brackets(C, C, 230 + 200 * (1 - g), 290 + 200 * (1 - g), 70), HOL.cyan, 7, o);
    polys(fr.main, motes(f, 24, 2340, 100, 980), HOL.cyan, o * 0.8);
    var plat = [ring(C, C + 300, 260, 0.25), ring(C, C + 300, 320, 0.25)];
    lines(fr.glow, plat, HOL.magenta, 14, o * g); lines(fr.main, plat, HOL.cyan, 4, o * g, false, [30, 18]);
    gridFloor(fr, f, 600, o);
    polys(fr.haze, [rect(-60, 520, 1140, 660)], HOL.magenta, o * 0.9);
    polys(fr.haze, [circle(C, C, 380 * g + 40, 1.2, 40)], HOL.violet, o * 0.35);
    polys(fr.bg, [full()], HOL.dark, o);
  },
  over: function (fr, f, at) {
    if (at >= 0) {
      var close = ease(at / 5);
      lines(fr.main, brackets(C, C, 175 + 80 * (1 - close), 235 + 80 * (1 - close), 50), HOL.cyan, 6, fade(at, 30, 44) * 100);
      if (at < 12) { var y = C - 240 + at * 40; polys(fr.main, [rect(C - 200, y, C + 200, y + 4)], HOL.cyan, 80); polys(fr.glow, [rect(C - 200, y - 16, C + 200, y + 20)], HOL.cyan, 50); }
    }
    bigGlint(fr, at, HOL.cyan);
  },
  opening: function (comp) {   // the pack glitches, its picture torn in bars; it is uploaded — voxels rising away
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 8 && f < 26 && f % 2 === 0) { seed(2350 + f); var bars = []; for (var i = 0; i < 5; i++) { var y = OY + between(-200, 200), x = OX + between(-160, 40); bars.push(rect(x, y, x + between(80, 240), y + between(8, 30))); } polys(fr.top, bars, f % 4 ? HOL.cyan : HOL.magenta, 80); }
      if (f >= 24) {
        var t = f - 24, o = fade(f, 50, 63) * 100; seed(2370); var vox = [];
        for (var j = 0; j < 60; j++) { var x2 = OX + between(-120, 120), y2 = OY + between(-200, 200) - t * between(8, 26), s = between(4, 10) * (1 - t / 44); vox.push(rect(x2 - s, y2 - s, x2 + s, y2 + s)); }
        polys(fr.glow, vox, HOL.cyan, o); polys(fr.main, vox, HOL.white, o);
        if (t < 10) lines(fr.glow, [[[OX - 300 + t * 30, OY], [OX + 300 - t * 30, OY]]], HOL.cyan, 16, 100 - t * 10);
      }
    }
  }
};

// ===== Verre liquide — an aurora under plates of frosted glass, their light edges, lenses, ripples, a glint ======
var GLS = { deep: [0.015, 0.025, 0.08], green: [0.25, 1, 0.65], teal: [0.15, 0.75, 0.95], violet: [0.6, 0.4, 1], pink: [1, 0.45, 0.8], frost: [0.86, 0.93, 1] };
function veil(f, y0, amp, thick, phase) {   // a band of aurora waving across
  var top = [], bot = [];
  for (var i = 0; i <= 30; i++) { var x = -60 + i * 40, y = y0 + amp * Math.sin(x * 0.006 + f * 0.05 + phase); top.push([x, y]); bot.push([x, y + thick * (0.6 + 0.4 * Math.sin(x * 0.01 + f * 0.07 + phase * 2))]); }
  return top.concat(bot.reverse());
}
function aurora(fr, f, o) {
  var cols = [GLS.green, GLS.teal, GLS.violet, GLS.pink], ys = [260, 420, 580, 720];
  for (var k = 0; k < 4; k++) { var v = veil(f, ys[k], 90, 150, k * 1.7); polys(fr.haze, [v], cols[k], o); polys(fr.glow, [veil(f, ys[k] + 30, 90, 40, k * 1.7)], cols[k], o * 0.6); }
}
function plates(fr, list, o) {   // [x, y, w, h, ang]: frosted glass, a highlight along its top, a light rim
  var bodies = [], rims = [], tops = [];
  for (var i = 0; i < list.length; i++) {
    var p = list[i]; bodies.push(rounded(p[0], p[1], p[2], p[3], 30, p[4])); rims.push(rounded(p[0], p[1], p[2], p[3], 30, p[4]));
    tops.push(place([[-p[2] / 2 + 34, -p[3] / 2 + 6], [p[2] / 2 - 34, -p[3] / 2 + 6]], p[0], p[1], p[4]));
  }
  lines(fr.main, tops, WHITE, 5, o * 0.8); lines(fr.main, rims, GLS.frost, 2.5, o * 0.55, true); polys(fr.main, bodies, GLS.frost, o * 0.12);
}
function lenses(fr, list, o) {   // [x, y, r]: droplets of glass
  var b = [], hl = [], rim = [];
  for (var i = 0; i < list.length; i++) { var x = list[i][0], y = list[i][1], r = list[i][2]; b.push(circle(x, y, r, 1, 28)); rim.push(ring(x, y, r, 1, Math.PI * 0.9, Math.PI * 1.7)); hl.push(place(circle(0, 0, r * 0.22, 0.5, 12), x - r * 0.35, y - r * 0.5, -0.6)); }
  polys(fr.main, hl, WHITE, o * 0.85); lines(fr.main, rim, WHITE, 3, o * 0.7); polys(fr.main, b, GLS.frost, o * 0.15);
}
var ED_GLASS = {
  title: function (fr, f, u) {
    plates(fr, [[260 + f * 2, 300, 360, 220, -0.08], [820 - f * 1.5, 520, 300, 360, 0.06], [420 + f, 820, 420, 200, 0.04]], 100);
    lenses(fr, [[700 + f * 2, 220, 60], [180, 640 - f * 2, 44], [900, 900 - f, 36]], 100);
    aurora(fr, f, 100);
    polys(fr.bg, [full()], GLS.deep, 100);
  },
  wipe: function (fr, v) {   // a drop of liquid glass spreads over the screen and clears
    var r = 40 + v * 1100, o = 100 * Math.sin(v * Math.PI);
    lines(fr.top, [ring(C, C, r, 1), ring(C, C, r * 0.8, 1)], WHITE, 10, o);
    polys(fr.top, [circle(C, C, r, 1, 64)], GLS.frost, o);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // ripples running out of the card; droplets splashing
      var rp = []; for (var k = 0; k < 4; k++) { var t = at - k * 3; if (t > 0 && t < 24) rp.push(ring(C, C, 240 + t * 26, 1.3)); }
      lines(fr.main, rp, WHITE, 4, fade(at, 14, 30) * o); lines(fr.glow, rp, GLS.teal, 14, fade(at, 14, 30) * o);
      lenses(fr, flung(at, 14, 2400, function (x, y, s) { return [[x, y, 18 * s]]; }, 20), fade(at, 30, 46) * o);
    }
    var list = [];
    for (var i = 0; i < 6; i++) { var a = i / 6 * Math.PI * 2 + f * 0.012, d = 440; list.push([C + Math.cos(a) * d, C + Math.sin(a) * d * 1.08, 170, 110, a * 0.2]); }
    plates(fr, list, o * g);
    lenses(fr, [[C - 300, C - 380, 50], [C + 340, C + 360, 64], [C + 360, C - 300, 34]], o);
    polys(fr.main, [circle(C, C, 380 * g + 1, 1.25, 72)], GLS.frost, o * 0.1);
    lines(fr.main, [ring(C, C, 380 * g + 1, 1.25, Math.PI * 1.1, Math.PI * 1.6)], WHITE, 6, o * 0.8);
    aurora(fr, f, o);
    polys(fr.bg, [full()], GLS.deep, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 14) {   // a glint crossing the glass, corner to corner
      var x = -300 + at * 110;
      polys(fr.main, [[[x, -60], [x + 120, -60], [x + 120 - 600, 1140], [x - 600, 1140]]], WHITE, 18);
      polys(fr.main, [[[x + 40, -60], [x + 70, -60], [x + 70 - 600, 1140], [x + 40 - 600, 1140]]], WHITE, 30);
    }
    if (at >= 0) lenses(fr, [[C - 190, C + 160 + Math.min(at, 20) * 6, 14], [C + 200, C - 120 + Math.min(at, 20) * 4, 10]], fade(at, 30, 44) * 100);
    bigGlint(fr, at, GLS.teal);
  },
  opening: function (comp) {   // the pack melts into liquid glass: ripples, drops falling and gathering
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 10 && f < 50) { var rp = []; for (var k = 0; k < 4; k++) { var t = f - 10 - k * 6; if (t > 0 && t < 30) rp.push(ring(OX, OY + 120, 100 + t * 14, 0.35)); } lines(fr.main, rp, WHITE, 4, fade(f, 40, 50) * 70); lines(fr.glow, rp, GLS.teal, 12, fade(f, 40, 50) * 70); }
      if (f >= 16) {
        var t2 = f - 16, drops = []; seed(2450);
        for (var i = 0; i < 14; i++) { var x = OX + between(-110, 110), d = Math.max(0, t2 - between(0, 14)), y = OY + 190 + d * d * 0.9, r = between(10, 24); if (d > 0) drops.push([x, y, r]); }
        lenses(fr, drops, fade(f, 52, 63) * 100);
      }
    }
  }
};

var EDITION = { nitrate: ED_NITRATE, noir: ED_NOIR, drivein: ED_DRIVEIN, super8: ED_SUPER8, film: ED_FILM, laserdisc: ED_LASERDISC, vhs: ED_VHS, zine: ED_ZINE,
                bubble: ED_BUBBLE, disc: ED_DISC, leather: ED_LEATHER, tiles: ED_TILES, stream: ED_STREAM, glass: ED_GLASS }[EDITION_KEY];

// --- the comps --------------------------------------------------------------------------------------------
// a frame's layers with a background under them all, so the light (haze, glow) shows over it
function framed(comp, f) { var bg = f >= FROM && f < TO ? layerAt(comp, "bg-" + f, f, 0) : null, fr = frameOf(comp, f); fr.bg = bg; return fr; }
function behind(rarity) {
  var N = LENGTH[rarity], comp = square("reveal-" + rarity, N);
  for (var f = 0; f < N; f++) {
    var fr = framed(comp, f); if (!fr.main) continue;
    var o = fade(f, N - 12, N - 1) * 100, at = f - FACE_AT;
    if (f < CARD_AT) EDITION.title(fr, f, f / CARD_AT);
    if (f >= CARD_AT - 4 && f < CARD_AT + 4) EDITION.wipe(fr, (f - CARD_AT + 4) / 8);
    if (f < CARD_AT - 1) continue;
    flash(fr, at);
    EDITION.stage(fr, f, at, o);
  }
}
function overCard(rarity) {
  var N = LENGTH[rarity], comp = square("over-" + rarity, N);
  for (var f = 0; f < N; f++) { var fr = frameOf(comp, f); if (!fr.main) continue; EDITION.over(fr, f, f - FACE_AT + 3); }
}
if (ONLY === "opening") EDITION.opening(newComp("opening", 1152, 1080, 64));
if (ONLY.indexOf("reveal-") === 0) behind(ONLY.slice(7));
if (ONLY.indexOf("over-") === 0) overCard(ONLY.slice(5));

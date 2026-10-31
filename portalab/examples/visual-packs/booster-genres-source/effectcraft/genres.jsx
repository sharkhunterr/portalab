// The genre scenes — Action, Sombre (dark), Drame, Fantastique, Science-fiction — every rarity staged over the
// whole screen (``place: screen``) on Portalab's takeover: the rarity's name across the screen until the card
// comes (frame 22), the card flung in face down, turning over — its face showing from frame 42. Square comps
// (1080, cropped to cover any screen), drawn round the middle; few, big, flat shapes. Built on the manga toolkit
// (../booster-manga-source/effectcraft/core.jsx). GENRE and ONLY say which comp to build.
var C = 540, CARD_AT = 22, FACE_AT = 42, LENGTH = { rare: 76, epic: 92, legendary: 110 };
function square(name, count) { return newComp(name, 1080, 1080, count); }
function full() { return [[-60, -60], [1140, -60], [1140, 1140], [-60, 1140]]; }
function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
// a tapered slash: fat early, to a point — along (x0,y0)→(x1,y1), drawn up to u
function slash(x0, y0, x1, y1, thick, u, bend) {
  var top = [], bot = [], n = 30, dx = x1 - x0, dy = y1 - y0, l = Math.sqrt(dx * dx + dy * dy), nx = -dy / l, ny = dx / l;
  for (var i = 0; i <= n * clamp01(u); i++) {
    var t = i / n, w = Math.pow(Math.sin(Math.PI * Math.pow(t, 0.55)), 0.7) * thick, off = (bend || 0) * Math.sin(Math.PI * t) * l * 0.06;
    top.push([x0 + dx * t + nx * (off + w), y0 + dy * t + ny * (off + w)]); bot.push([x0 + dx * t + nx * (off - w), y0 + dy * t + ny * (off - w)]);
  }
  return top.length > 1 ? [top.concat(bot.reverse())] : [];
}
// wedges from the middle: n of colour a, n of colour b between them
function wedges(L, n, turn, reach, a, b, oa, ob, width) {
  var A = [], B = [];
  for (var i = 0; i < n * 2; i++) {
    var ang = turn + i / (n * 2) * Math.PI * 2, w = Math.PI / (n * 2) * (width || 0.62);
    (i % 2 ? B : A).push([[C, C], [C + Math.cos(ang - w) * reach, C + Math.sin(ang - w) * reach], [C + Math.cos(ang + w) * reach, C + Math.sin(ang + w) * reach]]);
  }
  if (b) polys(L, B, b, ob === undefined ? 100 : ob);
  polys(L, A, a, oa === undefined ? 100 : oa);
}
function flash(fr, at, color) { if (at >= 0 && at < 3) polys(fr.top, [full()], color || WHITE, 100 - at * 33); }
function bigGlint(fr, at, color) {
  var big = { 6: 0.5, 7: 1, 8: 0.85, 9: 0.6, 10: 0.3 }[at];
  if (big) { polys(fr.glow, glintPolys([[C + 150, C - 215, 190 * big]]), color); polys(fr.top, glintPolys([[C + 150, C - 215, 130 * big]]), WHITE); }
}
function sparksOut(L, glowL, age, count, color, base, speed) {
  seed(base);
  var list = [];
  for (var i = 0; i < count; i++) {
    var a = between(0, Math.PI * 2), r0 = toEdge(a, 150, 210) + age * (speed || 20) * between(0.7, 1.3), len = between(20, 60);
    if (r0 > 760 || age < 0) continue;
    list.push([[C + Math.cos(a) * r0, C + Math.sin(a) * r0], [C + Math.cos(a) * (r0 + len), C + Math.sin(a) * (r0 + len)]]);
  }
  lines(glowL, list, color, 10); lines(L, list, WHITE, 3);
}

// ===== Action — a blockbuster: steel and fire ===========================================================
var ACT = { fire: [1, 0.42, 0.02], flame: [1, 0.7, 0.1], core: [1, 0.95, 0.7], steel: [0.16, 0.19, 0.24], steel_l: [0.42, 0.47, 0.55], night: [0.04, 0.05, 0.08] };
function fireball(L, glowL, hazeL, r, f, base, o) {   // layered flat fire: smoky rim, orange, yellow, white core
  seed(base + Math.floor(f / 2));
  var rings = [[1.0, ACT.fire], [0.78, ACT.flame], [0.5, ACT.core]];
  if (hazeL) polys(hazeL, [circle(C, C, r * 1.15, 1, 40)], ACT.fire, o * 0.9);
  for (var k = rings.length - 1; k >= 0; k--) polys(L, [burst(C, C, 16, r * rings[k][0], r * rings[k][0] * 0.82, 0.18, f * 0.03 + k)], rings[k][1], o);
}
// a fighter jet's silhouette along ang (its nose at x, y), and its two contrails behind it
function jet(x, y, s, ang) {
  var half = [[1, 0], [0.55, -0.07], [0.1, -0.1], [-0.25, -0.62], [-0.4, -0.62], [-0.3, -0.12], [-0.7, -0.12], [-0.85, -0.34], [-0.97, -0.34], [-0.92, 0]];
  var shape = [], i;   // the upper half, then the lower one mirrored (ExtendScript has no Array.map)
  for (i = 0; i < half.length; i++) shape.push([half[i][0] * s, half[i][1] * s]);
  for (i = half.length - 2; i > 0; i--) shape.push([half[i][0] * s, -half[i][1] * s]);
  return place(shape, x, y, ang);
}
function contrails(x, y, s, ang, len) {
  var c = Math.cos(ang), sn = Math.sin(ang), out = [];
  for (var k = -1; k <= 1; k += 2) { var bx = x - c * s * 0.9 - sn * k * s * 0.25, by = y - sn * s * 0.9 + c * k * s * 0.25; out.push([[bx, by], [bx - c * len, by - sn * len]]); }
  return out;
}
function explosionAt(fr, x, y, r, f, base, o) {   // a flat fireball anywhere: smoky rim, orange, yellow, a white core
  seed(base + Math.floor(f / 2));
  polys(fr.haze, [circle(x, y, r * 1.25, 1, 32)], ACT.fire, o * 0.8);
  polys(fr.main, [burst(x, y, 14, r * 0.45, r * 0.36, 0.2, f * 0.05)], ACT.core, o);
  polys(fr.main, [burst(x, y, 14, r * 0.75, r * 0.6, 0.2, f * 0.05 + 1)], ACT.flame, o);
  polys(fr.main, [burst(x, y, 14, r, r * 0.8, 0.22, f * 0.05 + 2)], ACT.fire, o * 0.95);
}
function embers(L, glowL, f, n, base, o) {   // embers rising and swaying, everywhere
  seed(base); var list = [];
  for (var i = 0; i < n; i++) { var x = between(-40, 1120) + Math.sin(f * 0.15 + i) * 20, y = 1120 - ((f * between(8, 18) + between(0, 1200)) % 1250), r = between(2.5, 6); list.push(circle(x, y, r, 1, 8)); }
  polys(glowL, list, ACT.fire, o); polys(L, list, ACT.core, o);
}
// every rarity its own moment: a rare a car chase, an epic an explosion, a legendary the finale
var ACTION_RARE = {
  title: function (fr, f, u) {   // a night road rushing at the screen, headlights, speed lines
    seed(90); polys(fr.top, streaks(C, C, 600, 600, 26, 1.5708, 420, 3), WHITE, 45);
    var dashes = [];
    for (var k = 0; k < 7; k++) { var t = (f * 0.09 + k / 7) % 1, d = t * t, y = 200 + d * 940, w = 3 + d * 34, l = 8 + d * 150; dashes.push([[C - w, y], [C + w, y], [C + w * 1.15, y + l], [C - w * 1.15, y + l]]); }
    polys(fr.main, dashes, ACT.flame, 100);
    for (var side = -1; side <= 1; side += 2) { polys(fr.haze, [circle(C + side * 230, 1010, 150, 0.6, 32)], ACT.core, 70); polys(fr.main, [circle(C + side * 230, 1010, 40, 0.6, 24)], WHITE, 100); }
    polys(fr.main, [[[C - 24, 200], [C + 24, 200], [1140, 1140], [-60, 1140]]], ACT.steel, 100);
    polys(fr.glow, [[[-60, 150], [1140, 150], [1140, 230], [-60, 230]]], ACT.fire, 50);
    polys(fr.main, [full()], ACT.night, 100);
  },
  wipe: function (fr, v) {   // two black skid marks swerving across
    polys(fr.top, slash(-60, 980, 1140, 120, 170, ease(v * 1.4), 0.8), ACT.night, 100);
    polys(fr.top, slash(-60, 1240, 1140, 380, 170, ease(v * 1.4 - 0.15), 0.8), ACT.night, 100);
  },
  stage: function (fr, f, at, o) {
    seed(95 + (f % 3)); polys(fr.main, concentration(C, C, 70, 900, 300, 7), WHITE, o * 0.22);
    if (at >= 0) { var sw = 240 + at * 38; lines(fr.glow, [ring(C, C, sw, 1.2)], ACT.flame, 22, fade(at, 5, 12) * o); lines(fr.main, [ring(C, C, sw, 1.2)], WHITE, 5, fade(at, 5, 12) * o); }
    sparksOut(fr.main, fr.glow, f - CARD_AT, 18, ACT.flame, 1400, 16);
    polys(fr.haze, [circle(C, C + 380, 420, 0.4, 40)], ACT.fire, o * 0.6);
    polys(fr.main, [full()], ACT.night, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 6) polys(fr.top, slash(-60, 700, 1140, 380, 34, ease(at / 3), 0.4), WHITE, fade(at, 3, 6) * 100);
    sparksOut(fr.main, fr.glow, at - 2, 12, ACT.flame, 1520, 22);
  }
};
var ACTION_EPIC = {
  title: function (fr, f, u) {
    var drift = u * 50;
    // three white speed bars rushing past, a shockwave, the screen cut in two — steel above, fire below
    for (var b = 0; b < 3; b++) { var x = -400 + ((f * 90 + b * 520) % 1900); polys(fr.top, [[[x, 1140], [x + 70, 1140], [x + 470, -60], [x + 400, -60]]], WHITE, 85); }
    if (f < 12) { var rr = 80 + f * 70; lines(fr.glow, [ring(C, C, rr, 1)], ACT.flame, 26, fade(f, 6, 12) * 100); lines(fr.main, [ring(C, C, rr, 1)], WHITE, 6, fade(f, 6, 12) * 100); }
    polys(fr.main, [[[-60, 760 - drift], [1140, 220 - drift], [1140, 1140], [-60, 1140]]], ACT.fire, 100);
    polys(fr.main, [full()], ACT.steel, 100);
  },
  wipe: function (fr, v) {   // a fireball swelling over everything
    fireball(fr.top, null, null, 120 + v * 1100, Math.round(v * 8), 40, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // the shockwave and the anamorphic flare
      var sw = 260 + at * 42; lines(fr.glow, [ring(C, C, sw, 1)], ACT.flame, 30, fade(at, 6, 16) * o); lines(fr.main, [ring(C, C, sw, 1)], WHITE, 7, fade(at, 6, 16) * o);
      var fl = fade(at, 8, 20) * o; polys(fr.top, [[[-60, C - 5], [C, C - 14], [1140, C - 5], [1140, C + 5], [C, C + 14], [-60, C + 5]]], [0.75, 0.9, 1], fl);
      polys(fr.glow, [[[-60, C - 30], [1140, C - 30], [1140, C + 30], [-60, C + 30]]], [0.4, 0.6, 1], fl * 0.6);
    }
    seed(60); var chunks = [];   // debris flung out, turning
    for (var i = 0; i < 18; i++) { var a = between(0, Math.PI * 2), d = 200 + (f - CARD_AT) * between(10, 22), s = between(10, 26); chunks.push(place([[-s, -s * 0.6], [s, -s * 0.4], [s * 0.7, s * 0.7], [-s * 0.8, s * 0.5]], C + Math.cos(a) * d, C + Math.sin(a) * d, f * 0.2 + i)); }
    polys(fr.main, chunks, ACT.steel_l, o);
    wedges(fr.main, 12, (f - CARD_AT) * 0.006, 300 + 900 * g, ACT.fire, ACT.flame, o * 0.9, o * 0.55, 0.5);
    fireball(fr.main, fr.glow, fr.haze, 260 * g + (at >= 0 ? 70 * back(at / 5) : 0), f, 50, o);
    polys(fr.main, [full()], ACT.night, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 7) polys(fr.top, slash(-60, 760, 1140, 300, 48, ease(at / 3), 0.6), WHITE, fade(at, 3, 7) * 100);
    sparksOut(fr.main, fr.glow, at - 2, 26, ACT.flame, 1500, 26);
    bigGlint(fr, at, ACT.flame);
  }
};
function skyline(base, top, seedBase) {   // a city's towers side by side, standing on base, their roofs from top down
  seed(seedBase); var town = [[-60, 1140], [-60, base]], x = -60;
  while (x < 1140) { var w = between(40, 95), h = top + between(0, (base - top) * 0.45); town.push([x, h]); town.push([x + w, h]); x += w; }
  town.push([1140, base]); town.push([1140, 1140]);
  return town;
}
function searchlights(L, f, o) {   // two beams sweeping a smoky sky from the city
  var out = [];
  for (var k = 0; k < 3; k++) { var ang = -1.5708 + 0.55 * Math.sin(f * 0.07 + k * 2.1), x = 180 + k * 360, y = 1000, c = Math.cos(ang), sn = Math.sin(ang); out.push([[x - 14, y], [x + 14, y], [x + c * 1300 + sn * 160, y + sn * 1300 - c * 160], [x + c * 1300 - sn * 160, y + sn * 1300 + c * 160]]); }
  polys(L, out, [0.8, 0.85, 1], o);
}
var BOOMS = [[C - 330, C - 270, 150], [C + 350, C - 190, 170], [C - 300, C + 310, 160], [C + 320, C + 330, 150], [C - 20, C - 440, 190], [C + 20, C + 470, 170]];
var ACTION_LEGENDARY = {
  title: function (fr, f, u) {   // the finale: a city burning at the horizon, two fighters screaming past, letterboxed
    polys(fr.top, [[[-60, -60], [1140, -60], [1140, 110], [-60, 110]], [[-60, 970], [1140, 970], [1140, 1140], [-60, 1140]]], ACT.night, 100);
    for (var j = 0; j < 2; j++) { var t = f - j * 6; if (t < 0) continue; var x = -260 + t * 95, y = 330 + j * 150 - t * 6; polys(fr.main, [jet(x, y, 70 - j * 14, -0.06)], ACT.night, 100); lines(fr.glow, contrails(x, y, 70 - j * 14, -0.06, 700), WHITE, 10, 70); lines(fr.main, contrails(x, y, 70 - j * 14, -0.06, 700), WHITE, 3, 80); }
    embers(fr.main, fr.glow, f, 40, 120, 100);
    polys(fr.main, [skyline(780, 600, 130)], ACT.night, 100);
    polys(fr.haze, [[[-60, 560], [1140, 560], [1140, 860], [-60, 860]]], ACT.fire, 100);
    polys(fr.main, [[[-60, 600], [1140, 600], [1140, 800], [-60, 800]]], ACT.fire, 100);
    polys(fr.main, [[[-60, 430], [1140, 430], [1140, 640], [-60, 640]]], [0.45, 0.1, 0.04], 100);
    polys(fr.main, [full()], [0.1, 0.03, 0.03], 100);
  },
  wipe: function (fr, v) {   // a nuclear-white flash rolling out, ringed in fire
    var r = 40 + ease(v) * 1000;
    polys(fr.top, [circle(C, C, r, 1, 48)], ACT.core, 100);
    lines(fr.top, [ring(C, C, r, 1)], ACT.fire, 60, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // a double shockwave, a long blue flare
      for (var q = 0; q < 2; q++) { var sw = 260 + (at - q * 4) * 46; if (at < q * 4) continue; lines(fr.glow, [ring(C, C, sw, 1)], ACT.flame, 34, fade(at - q * 4, 6, 18) * o); lines(fr.main, [ring(C, C, sw, 1)], WHITE, 8, fade(at - q * 4, 6, 18) * o); }
      var fl = fade(at, 14, 28) * o; polys(fr.top, [[[-60, C - 7], [C, C - 20], [1140, C - 7], [1140, C + 7], [C, C + 20], [-60, C + 7]]], [0.75, 0.9, 1], fl);
      polys(fr.glow, [[[-60, C - 44], [1140, C - 44], [1140, C + 44], [-60, C + 44]]], [0.35, 0.55, 1], fl * 0.7);
    }
    for (var i = 0; i < BOOMS.length; i++) {   // explosions going off round the card, one after the other
      var t = f - CARD_AT - 2 - i * 5; if (t < 0) continue;
      explosionAt(fr, BOOMS[i][0], BOOMS[i][1], BOOMS[i][2] * ease(t / 5) * (1 + t * 0.01), f, 200 + i * 10, fade(t, 16, 30) * o);
    }
    if (at >= -6 && at < 18) { var tj = at + 6; var x = 1300 - tj * 70, y = 220 + tj * 9; polys(fr.top, [jet(x, y, 80, Math.PI + 0.12)], ACT.night, o); lines(fr.glow, contrails(x, y, 80, Math.PI + 0.12, 900), WHITE, 12, o * 0.7); lines(fr.main, contrails(x, y, 80, Math.PI + 0.12, 900), WHITE, 3, o); }
    embers(fr.top, fr.glow, f, 60, 140, o);
    // the city burning below, searchlights sweeping a blood-red sky — no wedges: the finale is a place
    polys(fr.main, [skyline(1140, 700, 131)], ACT.night, o);
    polys(fr.haze, [[[-60, 760], [1140, 760], [1140, 1000], [-60, 1000]]], ACT.fire, o);
    searchlights(fr.glow, f, o * 0.35);
    fireball(fr.main, fr.glow, fr.haze, 200 * g + (at >= 0 ? 60 * back(at / 5) : 0), f, 50, o * 0.9);
    polys(fr.main, [[[-60, 640], [1140, 640], [1140, 1140], [-60, 1140]]], [0.55, 0.14, 0.04], o);
    polys(fr.main, [[[-60, 300], [1140, 300], [1140, 700], [-60, 700]]], [0.3, 0.06, 0.04], o);
    polys(fr.main, [full()], [0.09, 0.02, 0.03], o);
  },
  over: function (fr, f, at) {   // two slashes crossing, a hail of sparks
    if (at >= 0 && at < 8) { polys(fr.top, slash(-60, 860, 1140, 220, 34, ease(at / 3), 0.6), WHITE, fade(at, 3, 7) * 70); polys(fr.top, slash(-60, 220, 1140, 860, 34, ease((at - 2) / 3), -0.6), ACT.core, fade(at, 4, 8) * 70); }
    sparksOut(fr.main, fr.glow, at - 2, 40, ACT.flame, 1600, 30);
    embers(fr.main, fr.glow, f, 30, 170, at >= 0 ? 100 : 0);
    bigGlint(fr, at, ACT.flame);
  }
};
var GENRE_ACTION = {
  rarities: { rare: ACTION_RARE, epic: ACTION_EPIC, legendary: ACTION_LEGENDARY },
  opening: function (comp) {   // a countdown's rings closing on the pack, then it blows up: fireball, debris
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 24) { for (var k = 0; k < 3; k++) { var t = (f - k * 7) / 10; if (t < 0 || t > 1) continue; var rr = 520 * (1 - t) + 150; lines(fr.glow, [ring(cx, cy, rr, 1)], ACT.flame, 18, 100 * (1 - t)); lines(fr.main, [ring(cx, cy, rr, 1)], WHITE, 5, 100 * (1 - t)); } }
      if (f >= 24 && f < 56) {
        var t2 = f - 24, r = 160 + 520 * ease(t2 / 8), o = fade(t2, 18, 32) * 100;
        seed(70 + Math.floor(f / 2));
        polys(fr.haze, [circle(cx, cy, r * 1.2, 1, 40)], ACT.fire, o);
        polys(fr.main, [burst(cx, cy, 16, r * 0.5, r * 0.4, 0.2, f * 0.04)], ACT.core, o); polys(fr.main, [burst(cx, cy, 16, r * 0.78, r * 0.62, 0.2, f * 0.04 + 1)], ACT.flame, o); polys(fr.main, [burst(cx, cy, 16, r, r * 0.8, 0.2, f * 0.04 + 2)], ACT.fire, o * 0.95);
        seed(80); var chunks = [];
        for (var i = 0; i < 22; i++) { var a = between(0, Math.PI * 2), d = 120 + t2 * between(14, 30), s = between(10, 28); chunks.push(place([[-s, -s * 0.6], [s, -s * 0.4], [s * 0.7, s * 0.7], [-s * 0.8, s * 0.5]], cx + Math.cos(a) * d, cy + Math.sin(a) * d + t2 * t2 * 0.4, t2 * 0.25 + i)); }
        polys(fr.top, chunks, ACT.steel_l, o);
      }
      if (f >= 24 && f < 27) polys(fr.top, [circle(cx, cy, 600, 1, 40)], WHITE, 100 - (f - 24) * 33);
    }
  }
};

// ===== Sombre — horror, crime, thrillers: black and blood ==================================================
var DARK = { blood: [0.72, 0.03, 0.06], blood_l: [0.95, 0.15, 0.15], black: [0.03, 0.02, 0.025], bone: [0.93, 0.9, 0.84], mist: [0.35, 0.05, 0.08] };
function crow(x, y, s, flap, turn) {   // a crow's silhouette: body, head, tail, two wings at the flap
  var wing = 0.6 * Math.sin(flap), body = [[-0.9, 0], [-0.3, -0.18], [0.5, -0.12], [0.85, -0.05], [1.05, 0.02], [0.8, 0.08], [0.3, 0.16], [-0.4, 0.14], [-1.1, 0.22], [-1.2, 0.05]];
  var w1 = [[-0.1, -0.1], [0.1, -0.8 - wing], [0.35, -0.95 - wing], [0.25, -0.5 - wing * 0.5], [0.3, -0.1]], w2 = [[-0.25, -0.08], [-0.7, -0.6 - wing * 0.8], [-0.55, -0.62 - wing * 0.8], [0.0, -0.1]];
  return [place(body, x, y, turn, s, s), place(w1, x, y, turn, s, s), place(w2, x, y, turn, s, s)];
}
function claws(u, x, y, ang, len, thick) {   // three parallel claw marks
  var out = [], nx = -Math.sin(ang), ny = Math.cos(ang);
  for (var k = -1; k <= 1; k++) out = out.concat(slash(x + nx * k * thick * 2.6 - Math.cos(ang) * len / 2, y + ny * k * thick * 2.6 - Math.sin(ang) * len / 2, x + nx * k * thick * 2.6 + Math.cos(ang) * len / 2, y + ny * k * thick * 2.6 + Math.sin(ang) * len / 2, thick * (k ? 0.8 : 1), u, 0.3));
  return out;
}
function drips(f, n, base, maxLen) {   // blood drips running down from the top edge
  seed(base); var out = [];
  for (var i = 0; i < n; i++) { var x = between(-20, 1100), w = between(10, 34), len = Math.min(maxLen, (f + between(0, 6)) * between(20, 45)); out.push([[x - w, -60], [x + w, -60], [x + w * 0.6, len - w], [x, len + w * 0.6], [x - w * 0.6, len - w]]); }
  return out;
}
var GENRE_DARK = {
  title: function (fr, f, u) {
    var cu = ease((f - 2) / 5);
    if (f >= 2) polys(fr.main, claws(cu, C, C + 20, -0.75, 1500, 46), DARK.blood, 100);
    polys(fr.main, drips(f, 9, 300, 520), DARK.blood, 100);
    if (f >= 2 && f < 6) polys(fr.top, [full()], DARK.blood_l, 40 - (f - 2) * 10);
    polys(fr.main, [full()], DARK.black, 100);
  },
  wipe: function (fr, v) {   // blinds closing — a thriller's venetian shadows
    var bars = [];
    for (var k = 0; k < 12; k++) { var y = -60 + k * 100, h = 100 * clamp01(v * 1.4 - k * 0.03); bars.push([[-60, y], [1140, y], [1140, y + h], [-60, y + h]]); }
    polys(fr.top, bars, DARK.black, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // lightning strikes, the screen cracks like glass round the card
      seed(320); var cracks = [];
      for (var k = 0; k < 14; k++) { var a = k / 14 * Math.PI * 2 + between(-0.15, 0.15), pts = [[C + Math.cos(a) * 240, C + Math.sin(a) * 300]], px = pts[0][0], py = pts[0][1]; for (var j = 0; j < 7; j++) { a += between(-0.25, 0.25); px += Math.cos(a) * 60; py += Math.sin(a) * 60; pts.push([px, py]); } cracks.push(partOf([pts], ease((at + 1) / 4))[0]); }
      var rings = []; for (var q = 0; q < 2; q++) { var rv = []; for (var k2 = 0; k2 <= 14; k2++) { var a2 = k2 / 14 * Math.PI * 2; rv.push([C + Math.cos(a2) * (330 + q * 160) * between(0.92, 1.08), C + Math.sin(a2) * (400 + q * 180) * between(0.92, 1.08)]); } rings.push(rv); }
      lines(fr.top, cracks.concat(at > 2 ? rings : []), DARK.bone, 3.5, fade(at, 30, 40) * 100);
      lines(fr.glow, cracks, DARK.blood_l, 12, fade(at, 30, 40) * 100);
    }
    if (at >= -6 && at < 6) { seed(330 + f); var b = bolt(between(200, 880), -40, C + between(-80, 80), C - 200, 50, true); lines(fr.glow, b, [0.9, 0.85, 1], 18, at < 0 ? 40 : 100); lines(fr.top, b, WHITE, 4, at < 0 ? 40 : 100); }
    seed(340); var birds = [];   // crows bursting away from the card
    for (var i = 0; i < 14; i++) { var a3 = between(0, Math.PI * 2), d = 200 + (f - CARD_AT) * between(9, 18), s = between(34, 70); birds = birds.concat(crow(C + Math.cos(a3) * d, C + Math.sin(a3) * d * 0.8, s, f * 0.9 + i, Math.cos(a3) > 0 ? -0.3 : Math.PI + 0.3)); }
    polys(fr.main, birds, DARK.black, o);
    polys(fr.haze, [circle(C, C, 420 * g + 60, 1.3, 40)], DARK.blood, o);
    wedges(fr.main, 10, (f - CARD_AT) * 0.004, 300 + 900 * g, DARK.mist, null, o * 0.8, 0, 0.4);
    polys(fr.main, [full()], DARK.black, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) polys(fr.top, claws(ease(at / 3), C, C, 2.3, 760, 18), DARK.blood_l, fade(at, 4, 8) * 100);
    seed(360); var birds = [];
    for (var i = 0; i < 4; i++) { var t = f - FACE_AT - 2 - i * 5; if (t < 0) continue; birds = birds.concat(crow(-120 + t * 45 + i * 60, 900 - t * 22 - i * 140, 70 + i * 10, f * 0.9 + i, -0.4)); }
    polys(fr.top, birds, DARK.black, 100);
    bigGlint(fr, at, DARK.blood_l);
  },
  opening: function (comp) {   // three claws rip the pack; blood spatters; crows burst out of the dark
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      for (var k = 0; k < 2; k++) { var st = 12 + k * 9; if (f >= st && f < st + 20) polys(fr.main, claws(ease((f - st) / 3), cx, cy, k ? 0.8 : -0.8, 620, 26), DARK.blood, fade(f - st, 10, 20) * 100); }
      if (f >= 26 && f < 56) {
        seed(400); var spat = [];
        for (var i = 0; i < 26; i++) { var a = between(0, Math.PI * 2), d = 80 + (f - 26) * between(14, 34), r = between(6, 22) * (1 - (f - 26) / 40); spat.push(circle(cx + Math.cos(a) * d, cy + Math.sin(a) * d + (f - 26) * (f - 26) * 0.5, r, 1, 12)); }
        polys(fr.main, spat, DARK.blood, fade(f, 46, 56) * 100);
        seed(410); var birds = [];
        for (var j = 0; j < 12; j++) { var a2 = between(0, Math.PI * 2), d2 = 60 + (f - 26) * between(12, 24); birds = birds.concat(crow(cx + Math.cos(a2) * d2, cy + Math.sin(a2) * d2 * 0.8, between(40, 80), f + j, Math.cos(a2) > 0 ? -0.3 : Math.PI + 0.3)); }
        polys(fr.top, birds, DARK.black, fade(f, 48, 60) * 100);
      }
      if (f >= 26 && f < 29) polys(fr.top, [circle(cx, cy, 700, 1, 40)], DARK.blood_l, 60 - (f - 26) * 20);
    }
  }
};

// ===== Drame — a stage: red velvet, gold, a spotlight ======================================================
var DRA = { velvet: [0.55, 0.03, 0.08], velvet_d: [0.3, 0.01, 0.04], velvet_l: [0.78, 0.12, 0.16], gold: [0.95, 0.75, 0.3], gold_l: [1, 0.92, 0.65], light: [1, 0.95, 0.82], dark: [0.05, 0.02, 0.03], rose: [0.8, 0.05, 0.12] };
function curtain(L, x0, x1, folds, sway, open) {   // velvet folds: light and dark stripes, a scalloped hem
  var lit = [], deep = [], w = (x1 - x0) / folds;
  for (var i = 0; i < folds; i++) {
    var a = x0 + i * w + sway * Math.sin(i), b = a + w * 0.5, hem = 1140 - 30 * Math.sin(i * 1.7 + open * 3);
    lit.push([[a, -60], [b, -60], [b + 8, hem], [a - 6, hem - 20]]);
    deep.push([[b, -60], [a + w, -60], [a + w + 6, hem - 10], [b + 8, hem]]);
  }
  polys(L, lit, DRA.velvet_l, 100); polys(L, deep, DRA.velvet_d, 100);
  polys(L, [[[x0, -60], [x1, -60], [x1, 1140], [x0, 1140]]], DRA.velvet, 100);
}
function petalsFall(L, f, n, base, color, spread) {
  seed(base); var list = [];
  for (var i = 0; i < n; i++) { var x = C + between(-1, 1) * (spread || 560) + Math.sin(f * 0.12 + i) * 40, y = -60 + ((f * between(6, 12) + between(0, 1200)) % 1260), s = between(14, 26); list.push(place([[0, 0], [s * 0.6, -s * 0.5], [s * 1.2, -s * 0.2], [s * 1.3, s * 0.2], [s * 0.6, s * 0.45]], x, y, f * 0.1 + i, 1, Math.max(0.25, Math.abs(Math.cos(f * 0.15 + i))))); }
  polys(L, list, color || DRA.rose, 100);
}
var GENRE_DRAMA = {
  title: function (fr, f, u) {   // the curtain, closed, swaying; gold dust in a soft light
    seed(500); var dust = []; for (var i = 0; i < 40; i++) dust.push([between(0, 1080), between(0, 1080) - f * 2, between(2, 5)]);
    polys(fr.top, glintPolys(twinkle(dust, f, 1, 10)), DRA.gold_l);
    polys(fr.glow, [[[C - 200, -60], [C + 200, -60], [C + 520, 1140], [C - 520, 1140]]], DRA.light, 20);
    curtain(fr.main, -60, 1140, 12, 10 * Math.sin(f * 0.3), 0);
  },
  wipe: function (fr, v) {   // the curtain parts
    var gap = ease(v) * 640;
    curtain(fr.top, -60, C - gap, 6, 0, v); curtain(fr.top, C + gap, 1140, 6, 0, v);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // gold confetti and roses thrown towards the card
      seed(520); var conf = [], roses = [];
      for (var i = 0; i < 40; i++) { var a = between(0, Math.PI * 2), d = 200 + at * between(12, 28), s = between(6, 12); conf.push(place([[-s, -s * 0.4], [s, -s * 0.4], [s, s * 0.4], [-s, s * 0.4]], C + Math.cos(a) * d, C + Math.sin(a) * d + at * at * 0.4, at * 0.3 + i, 1, Math.max(0.2, Math.abs(Math.cos(at * 0.3 + i))))); }
      polys(fr.main, conf, DRA.gold, fade(at, 40, 60) * o);
      for (var r = 0; r < 6; r++) { var ra = r / 6 * Math.PI * 2 + 0.3, rd = 700 - 380 * ease(at / 10); if (rd < 260) rd = 260; roses.push(circle(C + Math.cos(ra) * rd, C + Math.sin(ra) * rd * 1.2, 26, 1, 16)); roses.push(circle(C + Math.cos(ra) * rd, C + Math.sin(ra) * rd * 1.2, 14, 1, 12)); }
      polys(fr.main, roses, DRA.rose, o);
      lines(fr.glow, [ring(C, C, 280 + at * 30, 1.2)], DRA.gold, 22, fade(at, 6, 16) * o);
    }
    petalsFall(fr.main, f, 18, 530, DRA.rose, 520);
    // the spotlight: a cone from above on the card, dust in it
    var sp = 120 + 160 * g;
    polys(fr.glow, [[[C - 60, -60], [C + 60, -60], [C + sp * 1.6, 1140], [C - sp * 1.6, 1140]]], DRA.light, o * 0.5);
    polys(fr.main, [[[C - 50, -60], [C + 50, -60], [C + sp * 1.4, 1140], [C - sp * 1.4, 1140]]], DRA.light, o * 0.18);
    polys(fr.main, [circle(C, C + 330, sp * 1.5, 0.25, 40)], DRA.light, o * 0.3);
    curtain(fr.main, -60, 160, 3, 0, 1); curtain(fr.main, 920, 1140, 3, 0, 1);
    polys(fr.main, [full()], DRA.dark, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) polys(fr.top, slash(-60, 300, 1140, 760, 40, ease(at / 3), -0.5), DRA.gold_l, fade(at, 4, 8) * 100);
    if (at >= 2) { seed(560); var pts = []; for (var i = 0; i < 16; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 160, 222) + between(10, 120); pts.push([C + Math.cos(a) * r, C + Math.sin(a) * r]); } polys(fr.top, glintPolys(twinkle(pts, f, 2, 22)), DRA.gold_l); }
    bigGlint(fr, at, DRA.gold);
  },
  opening: function (comp) {   // a spotlight finds the pack, petals fall; the curtain sweeps over it and it is gone
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 40) { var sp = 100 + 80 * ease(f / 10); polys(fr.glow, [[[cx - 50, -60], [cx + 50, -60], [cx + sp * 1.6, 1140], [cx - sp * 1.6, 1140]]], DRA.light, 50 * fade(f, 30, 40)); }
      if (f >= 8) petalsFall(fr.main, f, 26, 600, DRA.rose, 500);
      if (f >= 18 && f < 44) { var g = f < 30 ? ease((f - 18) / 10) : 1 - ease((f - 32) / 10); curtain(fr.top, cx - 700, cx - 700 + 700 * g, 6, 0, g); curtain(fr.top, cx + 700 - 700 * g, cx + 700, 6, 0, g); }
      if (f >= 30) { seed(600); var conf = []; for (var i = 0; i < 40; i++) { var a = between(0, Math.PI * 2), d = 60 + (f - 30) * between(10, 24), s = between(6, 12); conf.push(place([[-s, -s * 0.4], [s, -s * 0.4], [s, s * 0.4], [-s, s * 0.4]], cx + Math.cos(a) * d, cy + Math.sin(a) * d + (f - 30) * (f - 30) * 0.35, f * 0.3 + i)); } polys(fr.main, conf, DRA.gold, fade(f, 52, 63) * 100); }
    }
  }
};

// ===== Fantastique — runes, a portal, wings of light ======================================================
var FAN = { night: [0.04, 0.03, 0.12], indigo: [0.12, 0.08, 0.35], teal: [0.15, 0.85, 0.8], violet: [0.6, 0.35, 1], gold: [1, 0.82, 0.38], gold_l: [1, 0.95, 0.75] };
function runeRing(fr, r, rot, o, color) {   // a great rune circle: rings, a hexagram, runes as little strokes
  var m = magicCircle(C, C, r, 1, rot, 6), glyphs = [];
  seed(700);
  for (var i = 0; i < 24; i++) {
    var a = -rot * 0.6 + i / 24 * Math.PI * 2, gx = C + Math.cos(a) * r * 0.93, gy = C + Math.sin(a) * r * 0.93, s = r * 0.035, g = [];
    for (var k = 0; k < 3; k++) g.push([gx + between(-s, s), gy + between(-s, s)]);
    glyphs.push(g);
  }
  lines(fr.glow, m.rings.concat(m.star), color || FAN.gold, 12, o * 0.8);
  lines(fr.main, m.rings, color || FAN.gold, 4, o); lines(fr.main, m.star, FAN.gold_l, 3, o); lines(fr.main, m.ticks.concat(glyphs), FAN.gold_l, 2.5, o);
}
function vortex(L, f, r, o) {   // a swirling portal: spiral arms in violet and teal
  var arms = [];
  for (var k = 0; k < 6; k++) arms.push(spiral(C, C, r * 0.08, r, 1.3, 1.15, k / 6 * Math.PI * 2 + f * 0.12, 1, 0));
  lines(L, arms.slice(0, 3), FAN.violet, 26, o); lines(L, arms.slice(3), FAN.teal, 18, o);
}
var GENRE_FANTASY = {
  title: function (fr, f, u) {
    seed(710); var motes = []; for (var i = 0; i < 46; i++) motes.push([between(0, 1080), between(0, 1080) - f * 3, between(3, 7)]);
    polys(fr.top, glintPolys(twinkle(motes, f, 3, 12)), FAN.gold_l);
    runeRing(fr, 470 + u * 30, f * 0.02, 100);
    runeRing(fr, 290, -f * 0.035 + 0.5, 70, FAN.teal);
    polys(fr.haze, [circle(C, C, 420, 1, 40)], FAN.violet, 60);
    polys(fr.main, [full()], FAN.indigo, 100);
  },
  wipe: function (fr, v) {   // the circle flares into a portal swallowing the screen
    polys(fr.top, [circle(C, C, 40 + v * 900, 1, 48)], FAN.night, 100);
    lines(fr.top, [ring(C, C, 40 + v * 900, 1)], FAN.gold_l, 14, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) {   // great wings of light unfolding behind the card
      var open = back(at / 10), blades = [], cores = [];
      for (var side = -1; side <= 1; side += 2) for (var k = 0; k < 7; k++) {
        var right = -1.45 + (0.25 + k * 0.24) * open, ang = side > 0 ? right : Math.PI - right, len = (520 - k * 40) * Math.min(1, open * 1.2), wid = 64 - k * 5, root = [C + side * 120, C - 160];
        blades.push(blade(root[0], root[1], len, wid, ang)); cores.push(blade(root[0], root[1], len * 0.9, wid * 0.32, ang));
      }
      polys(fr.haze, blades, FAN.gold, o); polys(fr.glow, blades, FAN.gold_l, o * 0.7);
      polys(fr.main, cores, WHITE, o); polys(fr.main, blades, FAN.gold, o * 0.85);
    }
    seed(720); var squares = [];   // rune stones orbiting
    for (var i = 0; i < 10; i++) { var a = i / 10 * Math.PI * 2 + f * 0.05, s = 22; squares.push(place([[-s, -s], [s, -s], [s, s], [-s, s]], C + Math.cos(a) * 380, C + Math.sin(a) * 440, a)); }
    polys(fr.main, squares, FAN.teal, o * 0.9);
    vortex(fr.main, f, (300 + 500 * g), o * 0.9);
    polys(fr.haze, [circle(C, C, 360 * g + 60, 1.25, 40)], FAN.violet, o);
    polys(fr.main, [full()], FAN.night, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) polys(fr.top, slash(1140, 820, -60, 260, 44, ease(at / 3), -0.5), FAN.gold_l, fade(at, 4, 8) * 100);
    seed(740); var motes = [];
    for (var i = 0; i < 26; i++) { var x = C + between(-420, 420), y = 1100 - ((f * between(6, 14) + between(0, 1100)) % 1150); motes.push([x, y, between(4, 9)]); }
    if (at >= 0) polys(fr.top, glintPolys(twinkle(motes, f, 4, 14)), FAN.gold_l);
    bigGlint(fr, at, FAN.teal);
  },
  opening: function (comp) {   // runes seal the pack, a circle of gold closing; it dissolves into motes
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 36) {
        var m = magicCircle(cx, cy, 460 - 160 * ease(f / 24), 1, f * 0.04, 6), d = ease((f + 1) / 10), o = fade(f, 26, 36) * 100, rings = [];
        for (var i = 0; i < m.rings.length; i++) rings.push(m.rings[i].slice(0, Math.max(2, Math.round(m.rings[i].length * d))));
        lines(fr.glow, rings, FAN.gold, 14, o); lines(fr.main, rings, FAN.gold_l, 4, o); if (d > 0.7) lines(fr.main, m.star, FAN.gold_l, 3, o);
      }
      if (f >= 24) {
        seed(760); var motes = [];
        for (var j = 0; j < 70; j++) { var a = between(0, Math.PI * 2), dd = between(0, 160) + (f - 24) * between(6, 16); motes.push([cx + Math.cos(a) * dd, cy + Math.sin(a) * dd - (f - 24) * between(2, 8), between(4, 10) * (1 - (f - 24) / 44)]); }
        polys(fr.top, glintPolys(motes), FAN.gold_l); polys(fr.glow, glintPolys(motes), FAN.teal);
      }
    }
  }
};

// ===== Science-fiction — hyperspace, a ringed planet ======================================================
var SF = { space: [0.01, 0.02, 0.07], blue: [0.1, 0.3, 0.9], cyan: [0.3, 0.9, 1], magenta: [1, 0.3, 0.8], white: [0.95, 0.98, 1], planet: [0.2, 0.25, 0.55], planet_l: [0.45, 0.55, 0.95] };
function hyperspace(L, glowL, f, n, base, k) {   // star streaks rushing out of the middle
  seed(base); var list = [];
  for (var i = 0; i < n; i++) { var a = between(0, Math.PI * 2), sp = between(0.6, 1.4), d = ((f * 30 * sp * k + between(0, 900)) % 900) + 40, len = 40 + d * 0.5 * k; list.push([[C + Math.cos(a) * d, C + Math.sin(a) * d], [C + Math.cos(a) * (d + len), C + Math.sin(a) * (d + len)]]); }
  lines(glowL, list, SF.cyan, 8); lines(L, list, SF.white, 2.5);
}
var GENRE_SF = {
  title: function (fr, f, u) {
    hyperspace(fr.main, fr.glow, f, 120, 800, 1 + u * 1.5);
    lines(fr.glow, [ring(C, C, 200 + u * 80, 1)], SF.blue, 60, 50);
    polys(fr.haze, [circle(C, C, 520, 1, 40)], SF.blue, 70);
    polys(fr.main, [full()], SF.space, 100);
  },
  wipe: function (fr, v) {   // the jump: a white flash shrinking to a point, then gone
    polys(fr.top, [circle(C, C, 1000 * (1 - Math.abs(v * 2 - 1)) + 10, 1, 48)], SF.white, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6), tilt = -0.25;
    if (at >= 0) {   // the jump's shockwave, a hologram's scan line sweeping
      var sw = 250 + at * 45; lines(fr.glow, [ring(C, C, sw, 0.4)], SF.cyan, 26, fade(at, 8, 18) * o); lines(fr.main, [ring(C, C, sw, 0.4)], SF.white, 5, fade(at, 8, 18) * o);
      var fl = fade(at, 8, 20) * o; polys(fr.top, [[[-60, C - 4], [C, C - 10], [1140, C - 4], [1140, C + 4], [C, C + 10], [-60, C + 4]]], SF.cyan, fl);
    }
    // the ringed planet behind the card: the ring's far half, the planet, the ring's near half
    var pr = 330 * g, near = [], far = [];
    var ring1 = place(circle(0, 0, pr * 1.75, 0.28, 72), C, C + 40, tilt), ring2 = place(circle(0, 0, pr * 1.45, 0.22, 72), C, C + 40, tilt);
    polys(fr.main, [ring1, ring2], SF.cyan, o * 0.55, true);
    polys(fr.main, [place([[-pr * 0.6, -pr * 0.6], [pr * 0.2, -pr * 0.9], [pr * 0.9, -pr * 0.3], [0, 0]], C, C + 40, 0)], SF.planet_l, o * 0.5);
    polys(fr.main, [circle(C, C + 40, pr, 1, 64)], SF.planet, o);
    seed(820); var stars = []; for (var i = 0; i < 80; i++) stars.push([between(0, 1080), between(0, 1080), between(1.5, 4)]);
    polys(fr.main, glintPolys(twinkle(stars, f, 5, 6)), SF.white);
    polys(fr.haze, [circle(C - 200, C - 260, 380, 0.7, 40)], SF.magenta, o * 0.35);
    polys(fr.haze, [circle(C + 220, C + 240, 420, 0.8, 40)], SF.blue, o * 0.5);
    polys(fr.main, [full()], SF.space, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 12) { var y = C - 260 + at * 50; polys(fr.top, [[[C - 230, y], [C + 230, y], [C + 230, y + 6], [C - 230, y + 6]]], SF.cyan, 80); polys(fr.glow, [[[C - 230, y - 20], [C + 230, y - 20], [C + 230, y + 26], [C - 230, y + 26]]], SF.cyan, 40); }
    sparksOut(fr.main, fr.glow, at - 2, 22, SF.cyan, 1800, 24);
    bigGlint(fr, at, SF.cyan);
  },
  opening: function (comp) {   // a teleport beam locks on the pack; it is beamed away in rising rings
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 6 && f < 40) { var w = 120 + 120 * ease((f - 6) / 8), o = fade(f, 32, 40) * 100; polys(fr.glow, [[[cx - w, -60], [cx + w, -60], [cx + w, 1140], [cx - w, 1140]]], SF.cyan, o * 0.6); polys(fr.main, [[[cx - w * 0.3, -60], [cx + w * 0.3, -60], [cx + w * 0.3, 1140], [cx - w * 0.3, 1140]]], SF.white, o * 0.5); }
      if (f >= 10 && f < 44) { for (var k = 0; k < 4; k++) { var t = ((f - 10) + k * 6) % 24, y = cy + 260 - t * 22; lines(fr.glow, [ring(cx, y, 200, 0.22)], SF.cyan, 16, fade(f, 36, 44) * 100); lines(fr.main, [ring(cx, y, 200, 0.22)], SF.white, 4, fade(f, 36, 44) * 100); } }
      if (f >= 26) { seed(860); var bits = []; for (var i = 0; i < 50; i++) { var x = cx + between(-120, 120), y2 = cy + between(-180, 180) - (f - 26) * between(10, 30), s = between(3, 8) * (1 - (f - 26) / 38); bits.push([[x - s, y2 - s], [x + s, y2 - s], [x + s, y2 + s], [x - s, y2 + s]]); } polys(fr.top, bits, SF.cyan, fade(f, 50, 63) * 100); }
    }
  }
};

// ===== every rarity its own moment, for the four other genres (the epic is each genre's first moment) ========
function iris(fr, r) {   // the screen black but a round hole
  polys(fr.top, [full(), circle(C, C, Math.max(1, r), 1, 48)], BLACK, 100, true);
}
function cone(L, x, ang, len, w0, w1, color, o) {   // a light's cone from (x, -60) along ang
  var c = Math.cos(ang), sn = Math.sin(ang);
  polys(L, [[[x - w0, -60], [x + w0, -60], [x + c * len - sn * w1, -60 + sn * len + c * w1], [x + c * len + sn * w1, -60 + sn * len - c * w1]]], color, o);
}
// --- Ténèbres -------------------------------------------------------------------------------------------------
function bulb(fr, x, y, on, o) {   // a bare bulb on its wire, its light cone when on
  lines(fr.main, [[[x, -60], [x, y - 30]]], DARK.bone, 3, o);
  polys(fr.main, [circle(x, y, 22, 1.25, 20)], on ? [1, 0.93, 0.7] : [0.25, 0.22, 0.2], o);
  if (on) {
    polys(fr.glow, [circle(x, y, 90, 1, 24)], [1, 0.85, 0.5], o * on);
    cone(fr.haze, x, 1.5708, 1200, 30, 460, [1, 0.85, 0.55], o * on * 0.8);
    cone(fr.main, x, 1.5708, 1200, 24, 380, [1, 0.88, 0.62], o * on * 0.34);
    polys(fr.main, [circle(x, 960, 380, 0.22, 40)], [1, 0.88, 0.62], o * on * 0.45);
  }
}
function flicker(f) { seed(990 + f); return rnd() < 0.18 ? 0 : rnd() < 0.3 ? 0.45 : 1; }
function eyes(x, y, s, o) {   // two red eyes in the dark
  return [place(circle(-s, 0, s * 0.45, 0.55, 12), x, y, 0), place(circle(s, 0, s * 0.45, 0.55, 12), x, y, 0)];
}
function figure(x, y, s) {   // someone standing at the back, in silhouette
  return place([[-0.5 * s, 0], [-0.42 * s, -1.6 * s], [-0.25 * s, -1.9 * s], [0, -2.05 * s], [0.25 * s, -1.9 * s], [0.42 * s, -1.6 * s], [0.5 * s, 0], [0.7 * s, 2.6 * s], [-0.7 * s, 2.6 * s]], x, y, 0);
}
var DARK_RARE = {
  title: function (fr, f, u) {   // a bare bulb flickering in the dark; each time it dies, someone has come closer
    var on = flicker(f), near = 0.6 + u * 0.8;
    bulb(fr, C - 120, 380, on, 100);
    polys(fr.main, [figure(C + 230, 600 - near * 40, 70 * near)], [0.015, 0.01, 0.012], 100);
    if (!on) { polys(fr.glow, eyes(C + 230, 600 - near * 40 - 125 * near, 14 * near), DARK.blood_l, 100); polys(fr.main, eyes(C + 230, 600 - near * 40 - 125 * near, 9 * near), [1, 0.3, 0.25], 100); }
    if (on) polys(fr.main, [circle(C - 120, 1000, 420, 0.25, 40)], [0.28, 0.24, 0.2], 60);
    polys(fr.main, [full()], DARK.black, 100);
  },
  wipe: function (fr, v) {   // the bulb bursts: dark closing in
    iris(fr, 900 * (1 - ease(v)) + 40);
  },
  stage: function (fr, f, at, o) {   // the bulb over the card now; at the edge of its light, eyes, a figure
    var on = f > CARD_AT + 2 ? flicker(f) * 0.9 + 0.1 : 0;
    bulb(fr, C, 300, on, o);
    for (var k = 0; k < 3; k++) { var x = [C - 380, C + 390, C + 300][k], y = [500, 420, 760][k], bl = (f + k * 7) % 23 < 2; if (!bl) { polys(fr.glow, eyes(x, y, 20), DARK.blood_l, o); polys(fr.main, eyes(x, y, 13), [1, 0.35, 0.3], o); } }
    polys(fr.main, [figure(C - 360, 660, 75)], [0.015, 0.01, 0.012], o);
    seed(345); var dust = []; for (var i = 0; i < 30; i++) dust.push([C + between(-380, 380), (between(0, 1080) + f * 3) % 1080, between(1.5, 3.5)]);
    polys(fr.main, glintPolys(dust), DARK.bone, o * 0.5 * (on ? 1 : 0.2));
    polys(fr.main, [full()], DARK.black, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 7) polys(fr.top, claws(ease(at / 3), C + 200, C - 120, 2.4, 380, 10), DARK.blood_l, fade(at, 4, 7) * 100);
  }
};
function swarm(f, n, base, cx, cy, r0, spin) {   // crows wheeling round a centre
  seed(base); var birds = [];
  for (var i = 0; i < n; i++) { var a = between(0, Math.PI * 2) + f * spin * between(0.6, 1.2), d = r0 * between(0.7, 1.5); birds = birds.concat(crow(cx + Math.cos(a) * d, cy + Math.sin(a) * d * 0.75, between(26, 58), f * 0.9 + i, a + 1.5708)); }
  return birds;
}
function branches(base) {   // a dead tree's branches reaching in from the sides
  seed(base); var out = [];
  for (var side = -1; side <= 1; side += 2) for (var k = 0; k < 4; k++) { var y = 120 + k * 230 + between(-40, 40), x0 = side < 0 ? -60 : 1140, len = between(260, 460); out = out.concat(slash(x0, y, x0 - side * len, y + between(-160, 60), between(16, 28), 1, side * 0.6)); }
  return out;
}
var DARK_LEGENDARY = {
  title: function (fr, f, u) {   // a blood moon, dead branches, a swarm of crows
    polys(fr.main, branches(380), DARK.black, 100);
    polys(fr.main, swarm(f, 22, 381, C, C - 40, 420, 0.04), DARK.black, 100);
    polys(fr.haze, [circle(C, C - 40, 420, 1, 48)], DARK.blood, 100);
    polys(fr.main, [circle(C, C - 40, 330, 1, 64)], [0.62, 0.05, 0.06], 100);
    polys(fr.main, [circle(C - 60, C - 90, 330, 1, 64)], [0.75, 0.12, 0.1], 100);
    polys(fr.main, [full()], [0.06, 0.01, 0.02], 100);
  },
  wipe: function (fr, v) {   // the crows fill the screen
    seed(385); var birds = [];
    for (var i = 0; i < 70; i++) { var x = between(-100, 1180), y = between(-100, 1180), s = between(60, 140) * ease(v * 1.3 - between(0, 0.4)); if (s > 4) birds = birds.concat(crow(x, y, s, i, between(-0.5, 0.5))); }
    polys(fr.top, birds, BLACK, 100);
  },
  stage: function (fr, f, at, o) {
    var g = ease((f - CARD_AT) / 6);
    if (at >= -6 && at < 6) { seed(386 + f); var b = bolt(between(150, 930), -40, C + between(-80, 80), C - 220, 50, true); lines(fr.glow, b, [1, 0.6, 0.6], 18, at < 0 ? 40 : 100); lines(fr.top, b, WHITE, 4, at < 0 ? 40 : 100); }
    if (at >= 0 && at < 12) polys(fr.top, claws(ease(at / 3), C, C, -0.7, 1100, 30), DARK.blood_l, fade(at, 6, 12) * 70);
    polys(fr.main, swarm(f, 30, 387, C, C, 420 + 120 * g, 0.05), DARK.black, o);
    polys(fr.main, branches(388), DARK.black, o);
    polys(fr.haze, [circle(C, C, 520 * g + 80, 1, 48)], DARK.blood, o);
    polys(fr.main, [circle(C, C, 420 * g + 40, 1, 64)], [0.62, 0.05, 0.06], o);
    polys(fr.main, drips(f - CARD_AT, 12, 389, 380), DARK.blood, o);
    polys(fr.main, [full()], [0.06, 0.01, 0.02], o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) polys(fr.top, claws(ease(at / 3), C, C, 2.3, 900, 22), DARK.blood_l, fade(at, 4, 8) * 100);
    var birds = [];
    for (var i = 0; i < 6; i++) { var t = f - FACE_AT - 1 - i * 3; if (t < 0) continue; birds = birds.concat(crow(C + (i % 2 ? 1 : -1) * (120 + t * 40), C + 140 - t * 30 - i * 30, 60 + i * 8, f * 0.9 + i, (i % 2 ? -0.4 : Math.PI + 0.4))); }
    polys(fr.top, birds, BLACK, 100);
    bigGlint(fr, at, DARK.blood_l);
  }
};
GENRE_DARK.rarities = { rare: DARK_RARE, epic: GENRE_DARK, legendary: DARK_LEGENDARY };

// --- Rideau ---------------------------------------------------------------------------------------------------
var DRAMA_RARE = {
  title: function (fr, f, u) {   // a dark stage: one spotlight looking for someone, dust in it
    var x = C + 360 * Math.sin(f * 0.16), ang = 1.5708 + (x - C) / 2600;
    cone(fr.glow, x, ang, 1300, 40, 260, DRA.light, 60); cone(fr.main, x, ang, 1300, 30, 200, DRA.light, 22);
    polys(fr.main, [circle(x, 960, 230, 0.22, 40)], DRA.light, 35);
    polys(fr.main, [[[-60, 940], [1140, 940], [1140, 1140], [-60, 1140]]], [0.12, 0.05, 0.04], 100);
    polys(fr.main, [full()], DRA.dark, 100);
  },
  wipe: function (fr, v) {   // the light closes to a point, then opens on the card
    iris(fr, v < 0.5 ? 900 * (1 - ease(v * 2)) + 30 : 30 + 900 * ease(v * 2 - 1));
  },
  stage: function (fr, f, at, o) {
    var sp = 140 + 60 * ease((f - CARD_AT) / 6);
    cone(fr.glow, C, 1.5708, 1300, 50, sp * 1.6, DRA.light, o * 0.55); cone(fr.main, C, 1.5708, 1300, 40, sp * 1.3, DRA.light, o * 0.18);
    seed(510); var dust = []; for (var i = 0; i < 30; i++) dust.push([C + between(-sp, sp), (between(0, 1080) + f * 2) % 1080, between(2, 4)]);
    polys(fr.top, glintPolys(twinkle(dust, f, 1, 8)), DRA.gold_l);
    polys(fr.main, [full()], DRA.dark, o);
  },
  over: function (fr, f, at) {
    if (at >= 2) { seed(511); var pts = []; for (var i = 0; i < 8; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 160, 222) + between(10, 80); pts.push([C + Math.cos(a) * r, C + Math.sin(a) * r]); } polys(fr.top, glintPolys(twinkle(pts, f, 2, 18)), DRA.gold_l); }
  }
};
function audience(f, cheer) {   // a row of heads and raised arms at the foot of the screen
  var out = []; seed(570);
  for (var i = 0; i < 22; i++) { var x = -40 + i * 54 + between(-10, 10), y = 880 + between(-20, 20), r = between(30, 40); out.push(circle(x, y - r * 1.4, r * 0.7, 1.15, 14)); out.push([[x - r, 1140], [x - r * 0.9, y], [x + r * 0.9, y], [x + r, 1140]]); if (cheer && (i % 3 === 0)) { var lift = 60 + 30 * Math.sin(f * 0.6 + i); out.push([[x - 8, y], [x - 30, y - lift - 60], [x - 18, y - lift - 64], [x + 4, y]]); } }
  return out;
}
var DRAMA_LEGENDARY = {
  title: function (fr, f, u) {   // the theatre itself: tiers of gilded balconies, a chandelier, a full house
    polys(fr.top, audience(f, false), DRA.dark, 100);
    seed(560); var lamps = []; for (var t = 0; t < 3; t++) for (var i = 0; i < 16; i++) { var a = Math.PI * (0.08 + i / 15 * 0.84); lamps.push([C - Math.cos(a) * (360 + t * 150), 520 + t * 90 - Math.sin(a) * (120 + t * 40), 5 + t]); }
    polys(fr.glow, glintPolys(twinkle(lamps, f, 1, 10)), DRA.gold_l);
    for (var t2 = 0; t2 < 3; t2++) lines(fr.main, [ring(C, 520 + t2 * 90, 360 + t2 * 150, 0.33, Math.PI * 1.05, Math.PI * 1.95)], DRA.gold, 10, 100);
    polys(fr.glow, glintPolys([[C, 300, 80]]), DRA.gold_l); polys(fr.main, [circle(C, 300, 46, 1.4, 20)], DRA.gold, 100); lines(fr.main, [[[C, -60], [C, 250]]], DRA.gold, 4, 100);
    polys(fr.main, [full()], DRA.velvet_d, 100);
  },
  wipe: function (fr, v) {   // the great curtain comes down
    var y = -1140 + ease(v) * 1200;
    var folds = []; for (var i = 0; i < 12; i++) { var a = -60 + i * 100; folds.push([[a, -60], [a + 50, -60], [a + 55, y + 1140], [a - 5, y + 1120]]); }
    polys(fr.top, folds, DRA.velvet_l, 100); polys(fr.top, [[[-60, -60], [1140, -60], [1140, y + 1140], [-60, y + 1140]]], DRA.velvet, 100);
  },
  stage: function (fr, f, at, o) {   // a standing ovation: the curtain up, spotlights crossing, roses raining
    polys(fr.top, audience(f, true), DRA.dark, o);
    if (at >= 0) { seed(580); var conf = []; for (var i = 0; i < 60; i++) { var a = between(-Math.PI, 0), d = 200 + at * between(14, 30), s = between(6, 13); conf.push(place([[-s, -s * 0.4], [s, -s * 0.4], [s, s * 0.4], [-s, s * 0.4]], C + Math.cos(a) * d, C + 200 + Math.sin(a) * d + at * at * 0.5, at * 0.3 + i, 1, Math.max(0.2, Math.abs(Math.cos(at * 0.3 + i))))); } polys(fr.main, conf, DRA.gold, fade(at, 50, 68) * o); }
    petalsFall(fr.main, f, 40, 581, DRA.rose, 560);
    for (var k = 0; k < 3; k++) { var ang = 1.5708 + 0.35 * Math.sin(f * 0.08 + k * 2.2); cone(fr.glow, 180 + k * 360, ang, 1400, 30, 220, DRA.light, o * 0.4); }
    curtain(fr.main, -60, 200, 4, 0, 1); curtain(fr.main, 880, 1140, 4, 0, 1);
    var folds = []; for (var i2 = 0; i2 < 12; i2++) folds.push(circle(-60 + i2 * 100 + 50, 230, 60, 0.6, 16));
    polys(fr.main, folds, DRA.velvet_l, o); polys(fr.main, [[[-60, -60], [1140, -60], [1140, 250], [-60, 250]]], DRA.velvet, o);
    polys(fr.main, [[[-60, 250], [1140, 250], [1140, 262], [-60, 262]]], DRA.gold, o);
    polys(fr.main, [full()], DRA.dark, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) { polys(fr.top, slash(-60, 300, 1140, 760, 36, ease(at / 3), -0.5), DRA.gold_l, fade(at, 4, 8) * 90); polys(fr.top, slash(1140, 300, -60, 760, 36, ease((at - 2) / 3), 0.5), DRA.gold_l, fade(at, 5, 9) * 90); }
    petalsFall(fr.top, f, 14, 590, DRA.rose, 600);
    bigGlint(fr, at, DRA.gold);
  }
};
GENRE_DRAMA.rarities = { rare: DRAMA_RARE, epic: GENRE_DRAMA, legendary: DRAMA_LEGENDARY };

// --- Arcanes --------------------------------------------------------------------------------------------------
var FANTASY_RARE = {
  title: function (fr, f, u) {   // one rune circle drawing itself on the night, motes rising
    var m = magicCircle(C, C, 400, 1, f * 0.02, 5), d = ease(f / 16), rings = [];
    for (var i = 0; i < m.rings.length; i++) rings.push(m.rings[i].slice(0, Math.max(2, Math.round(m.rings[i].length * d))));
    lines(fr.glow, rings, FAN.teal, 12, 90); lines(fr.main, rings, FAN.gold_l, 4, 100); if (d > 0.8) lines(fr.main, m.star, FAN.gold_l, 3, 100);
    seed(711); var motes = []; for (var j = 0; j < 30; j++) motes.push([between(0, 1080), 1080 - ((f * between(4, 9) + between(0, 1080)) % 1080), between(3, 6)]);
    polys(fr.top, glintPolys(motes), FAN.gold_l);
    polys(fr.main, [full()], FAN.night, 100);
  },
  wipe: function (fr, v) {   // the circle flares out in a ring of light
    var r = 60 + ease(v) * 900; lines(fr.top, [ring(C, C, r, 1)], FAN.gold_l, 40 * (1 - v) + 6, 100); polys(fr.top, [circle(C, C, r * 0.98, 1, 48)], FAN.night, 100 * (1 - v));
  },
  stage: function (fr, f, at, o) {
    runeRing(fr, 320, f * 0.03, o * 0.8, FAN.teal);
    polys(fr.haze, [circle(C, C, 380, 1, 40)], FAN.violet, o * 0.6);
    polys(fr.main, [full()], FAN.night, o);
  },
  over: function (fr, f, at) {
    seed(712); var motes = []; for (var i = 0; i < 12; i++) motes.push([C + between(-300, 300), 1000 - ((f * between(5, 10) + between(0, 1000)) % 1050), between(4, 8)]);
    if (at >= 0) polys(fr.top, glintPolys(twinkle(motes, f, 4, 12)), FAN.gold_l);
  }
};
function dragon(cx, cy, s, flap, ang) {   // a dragon's silhouette: a long body, a horned head, two great wings
  var wing = Math.sin(flap) * 0.5, body = [], head;
  for (var i = 0; i <= 12; i++) { var t = i / 12, w = (0.16 - t * 0.13) * s; body.push([(-1.4 + t * 2.4) * s, Math.sin(t * 4 + flap * 0.5) * 0.12 * s - w]); }
  for (var j = 12; j >= 0; j--) { var t2 = j / 12, w2 = (0.16 - t2 * 0.13) * s; body.push([(-1.4 + t2 * 2.4) * s, Math.sin(t2 * 4 + flap * 0.5) * 0.12 * s + w2]); }
  head = [[1.0 * s, -0.1 * s], [1.35 * s, -0.04 * s], [1.45 * s, 0.05 * s], [1.0 * s, 0.1 * s], [1.15 * s, -0.25 * s]];
  var w1 = [[-0.2 * s, -0.05 * s], [-0.6 * s, (-0.9 - wing) * s], [-0.35 * s, (-0.62 - wing) * s], [-0.1 * s, (-1.0 - wing) * s], [0.05 * s, (-0.6 - wing) * s], [0.3 * s, (-0.85 - wing) * s], [0.3 * s, -0.1 * s]];
  var w2 = [[-0.1 * s, 0.05 * s], [-0.45 * s, (0.5 + wing * 0.6) * s], [-0.15 * s, (0.4 + wing * 0.6) * s], [0.1 * s, (0.6 + wing * 0.6) * s], [0.25 * s, 0.1 * s]];
  return [place(body, cx, cy, ang), place(head, cx, cy, ang), place(w1, cx, cy, ang), place(w2, cx, cy, ang)];
}
var FANTASY_LEGENDARY = {
  title: function (fr, f, u) {   // a dragon crossing a great moon over mountains
    polys(fr.main, dragon(-200 + f * 60, 420 - f * 6, 150, f * 0.7, -0.08), FAN.night, 100);
    seed(770); var peaks = [[-60, 1140], [-60, 860]]; for (var x = -60; x < 1140; x += 90) peaks.push([x + 45, 860 - between(80, 260)], [x + 90, 860 - between(0, 60)]); peaks.push([1140, 1140]);
    polys(fr.main, [peaks], [0.03, 0.02, 0.08], 100);
    polys(fr.haze, [circle(C + 120, 420, 380, 1, 48)], FAN.teal, 70);
    polys(fr.main, [circle(C + 120, 420, 300, 1, 64)], [0.85, 0.95, 1], 100);
    polys(fr.main, [full()], FAN.indigo, 100);
  },
  wipe: function (fr, v) {   // a breath of golden fire sweeping the screen
    var w = ease(v) * 1500; polys(fr.top, [[[-60, C - 60], [-60 + w, C - 60 - w * 0.6], [-60 + w * 1.1, C], [-60 + w, C + 60 + w * 0.6], [-60, C + 60]]], FAN.gold, 100);
    polys(fr.top, [[[-60, C - 30], [-60 + w * 0.9, C - 30 - w * 0.35], [-60 + w, C], [-60 + w * 0.9, C + 30 + w * 0.35], [-60, C + 30]]], FAN.gold_l, 100);
  },
  stage: function (fr, f, at, o) {   // a dragon of light coiled round the card, its wings spread, runes turning
    var g = ease((f - CARD_AT) / 6);
    var coil = spiral(C, C, 260, 470 * g + 40, 1.6, 1.15, f * 0.05, 1, 0);
    lines(fr.glow, [coil], FAN.teal, 70, o); lines(fr.main, [coil], FAN.gold, 30, o); lines(fr.main, [coil], FAN.gold_l, 10, o);
    var tip = coil[coil.length - 1]; polys(fr.main, [circle(tip[0], tip[1], 34, 1, 16)], FAN.gold_l, o);
    if (at >= 0) {
      var open = back(at / 10), blades = [];
      for (var side = -1; side <= 1; side += 2) for (var k = 0; k < 9; k++) { var right = -1.5 + (0.2 + k * 0.22) * open, ang = side > 0 ? right : Math.PI - right; blades.push(blade(C + side * 140, C - 200, (640 - k * 45) * Math.min(1, open * 1.2), 70 - k * 5, ang)); }
      polys(fr.haze, blades, FAN.teal, o); polys(fr.main, blades, FAN.gold, o * 0.75);
    }
    runeRing(fr, 500, f * 0.02, o * 0.7); runeRing(fr, 380, -f * 0.03, o * 0.6, FAN.teal);
    polys(fr.haze, [circle(C, C, 480 * g + 60, 1.2, 40)], FAN.violet, o);
    polys(fr.main, [full()], FAN.night, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) { polys(fr.top, slash(1140, 820, -60, 260, 40, ease(at / 3), -0.5), FAN.gold_l, fade(at, 4, 8) * 90); polys(fr.top, slash(-60, 820, 1140, 260, 40, ease((at - 2) / 3), 0.5), FAN.teal, fade(at, 5, 9) * 80); }
    seed(780); var motes = []; for (var i = 0; i < 40; i++) motes.push([C + between(-500, 500), 1100 - ((f * between(6, 14) + between(0, 1100)) % 1150), between(4, 10)]);
    if (at >= 0) polys(fr.top, glintPolys(twinkle(motes, f, 4, 14)), FAN.gold_l);
    bigGlint(fr, at, FAN.teal);
  }
};
GENRE_FANTASY.rarities = { rare: FANTASY_RARE, epic: GENRE_FANTASY, legendary: FANTASY_LEGENDARY };

// --- Hyperespace ----------------------------------------------------------------------------------------------
function radar(fr, cx, cy, r, f, o) {   // a scope: rings, cross hairs, a sweeping beam, blips
  var rings = []; for (var k = 1; k <= 4; k++) rings.push(ring(cx, cy, r * k / 4, 1));
  lines(fr.main, rings.concat([[[cx - r, cy], [cx + r, cy]], [[cx, cy - r], [cx, cy + r]]]), SF.cyan, 2.5, o * 0.6);
  var a = f * 0.18; polys(fr.glow, [[[cx, cy], [cx + Math.cos(a) * r, cy + Math.sin(a) * r], [cx + Math.cos(a - 0.5) * r, cy + Math.sin(a - 0.5) * r]]], SF.cyan, o * 0.7);
  lines(fr.main, [[[cx, cy], [cx + Math.cos(a) * r, cy + Math.sin(a) * r]]], SF.white, 4, o);
  seed(880); var blips = []; for (var i = 0; i < 7; i++) { var ba = between(0, Math.PI * 2), bd = between(0.2, 0.95) * r, lag = ((a - ba) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2); if (lag < 2.5) blips.push(circle(cx + Math.cos(ba) * bd, cy + Math.sin(ba) * bd, 9, 1, 10)); }
  polys(fr.glow, blips, SF.cyan, o); polys(fr.main, blips, SF.white, o);
}
var SF_RARE = {
  title: function (fr, f, u) {   // a ship's scope looking for something
    radar(fr, C, C, 440, f, 100);
    polys(fr.main, [full()], SF.space, 100);
  },
  wipe: function (fr, v) {   // a scan line sweeping down
    var y = -60 + ease(v) * 1200; polys(fr.top, [[[-60, -60], [1140, -60], [1140, y], [-60, y]]], SF.space, 100); polys(fr.top, [[[-60, y - 8], [1140, y - 8], [1140, y + 8], [-60, y + 8]]], SF.cyan, 100);
  },
  stage: function (fr, f, at, o) {
    var lines2 = []; for (var k = 0; k < 12; k++) { var y = 760 + k * k * 6; lines2.push([[-60, y], [1140, y]]); } for (var j = -8; j <= 8; j++) lines2.push([[C + j * 40, 760], [C + j * 260, 1140]]);
    lines(fr.main, lines2, SF.cyan, 2, o * 0.5);
    radar(fr, C, C, 330, f, o * 0.35);
    polys(fr.main, [full()], SF.space, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 12) { var y = C - 260 + at * 50; polys(fr.top, [[[C - 230, y], [C + 230, y], [C + 230, y + 5], [C - 230, y + 5]]], SF.cyan, 70); }
  }
};
function ship(x, y, s, ang) {   // a capital ship's wedge, its bridge, its engines' glow
  return { hull: place([[s, 0], [-s * 0.6, -s * 0.42], [-s * 0.7, -s * 0.34], [-s * 0.7, s * 0.34], [-s * 0.6, s * 0.42]], x, y, ang), bridge: place([[-s * 0.35, -s * 0.06], [-s * 0.55, -s * 0.1], [-s * 0.55, s * 0.1], [-s * 0.35, s * 0.06]], x, y, ang), engines: [place(circle(-s * 0.72, -s * 0.18, s * 0.07, 1, 10), x, y, ang), place(circle(-s * 0.72, s * 0.18, s * 0.07, 1, 10), x, y, ang)] };
}
var FLEET = [[C - 360, C - 300, 150, 0.3], [C + 380, C - 260, 120, 2.6], [C - 400, C + 280, 110, -0.4], [C + 360, C + 320, 170, -2.7], [C, C - 470, 90, 1.6]];
var SF_LEGENDARY = {
  title: function (fr, f, u) {   // hyperspace, then a great ship tearing out of it
    hyperspace(fr.main, fr.glow, f, 140, 890, 1 + u * 2);
    var s = 60 + f * f * 1.4, sh = ship(C, C, s, 0.0);
    if (f > 6) { polys(fr.main, [sh.hull], [0.55, 0.6, 0.7], 100); polys(fr.main, [sh.bridge], [0.3, 0.33, 0.4], 100); polys(fr.glow, sh.engines, SF.cyan, 100); }
    polys(fr.main, [full()], SF.space, 100);
  },
  wipe: function (fr, v) { polys(fr.top, [circle(C, C, 1000 * (1 - Math.abs(v * 2 - 1)) + 10, 1, 48)], SF.white, 100); },
  stage: function (fr, f, at, o) {   // a fleet dropping out of hyperspace round the card, lasers crossing, the planet behind
    var g = ease((f - CARD_AT) / 6);
    for (var i = 0; i < FLEET.length; i++) {
      var t = f - CARD_AT - 1 - i * 4; if (t < 0) continue;
      var arrive = ease(t / 4), sx = FLEET[i][0] - Math.cos(FLEET[i][3]) * 700 * (1 - arrive), sy = FLEET[i][1] - Math.sin(FLEET[i][3]) * 700 * (1 - arrive), sh = ship(sx, sy, FLEET[i][2], FLEET[i][3]);
      if (arrive < 1) lines(fr.glow, [[[sx, sy], [sx - Math.cos(FLEET[i][3]) * 600, sy - Math.sin(FLEET[i][3]) * 600]]], SF.white, 30 * (1 - arrive), o);
      polys(fr.main, [sh.bridge], [0.3, 0.33, 0.4], o); polys(fr.main, [sh.hull], [0.55, 0.6, 0.72], o); polys(fr.glow, sh.engines, SF.cyan, o);
    }
    if (at >= 0) { seed(895 + Math.floor(at / 3)); var beams = []; for (var k = 0; k < 4; k++) { var a = FLEET[k], b = FLEET[(k + 2) % 5]; beams.push([[a[0], a[1]], [b[0], b[1]]]); } lines(fr.glow, beams, (at % 6 < 3) ? SF.magenta : SF.cyan, 14, fade(at, 30, 50) * o); lines(fr.top, beams, SF.white, 3, fade(at, 30, 50) * o); }
    if (at >= 0) { var sw = 250 + at * 45; lines(fr.glow, [ring(C, C, sw, 0.4)], SF.cyan, 26, fade(at, 8, 18) * o); lines(fr.main, [ring(C, C, sw, 0.4)], SF.white, 5, fade(at, 8, 18) * o); }
    var pr = 400 * g; polys(fr.main, [place(circle(0, 0, pr * 1.75, 0.28, 72), C, C + 40, -0.25)], SF.cyan, o * 0.5);
    polys(fr.main, [circle(C, C + 40, pr, 1, 64)], SF.planet, o);
    seed(820); var stars = []; for (var j = 0; j < 90; j++) stars.push([between(0, 1080), between(0, 1080), between(1.5, 4)]);
    polys(fr.main, glintPolys(twinkle(stars, f, 5, 6)), SF.white);
    polys(fr.haze, [circle(C - 200, C - 260, 420, 0.7, 40)], SF.magenta, o * 0.45);
    polys(fr.main, [full()], SF.space, o);
  },
  over: function (fr, f, at) {
    sparksOut(fr.main, fr.glow, at - 2, 34, SF.cyan, 1850, 30);
    if (at >= 0 && at < 8) polys(fr.top, slash(-60, 760, 1140, 300, 34, ease(at / 3), 0.5), SF.cyan, fade(at, 4, 8) * 80);
    bigGlint(fr, at, SF.cyan);
  }
};
GENRE_SF.rarities = { rare: SF_RARE, epic: GENRE_SF, legendary: SF_LEGENDARY };

// ===== Trésor — adventure: a treasure map, a sunken chest, an island ======================================
var ADV = { sea: [0.05, 0.22, 0.25], sea_l: [0.12, 0.42, 0.46], deep: [0.02, 0.09, 0.12], foam: [0.88, 0.95, 0.92], parch: [0.92, 0.84, 0.64], parch_d: [0.7, 0.55, 0.32], ink: [0.2, 0.11, 0.04], gold: [0.96, 0.72, 0.18], gold_l: [1, 0.9, 0.55], sun: [1, 0.78, 0.4], dusk: [0.62, 0.22, 0.3], sky: [0.98, 0.55, 0.32], wood: [0.36, 0.21, 0.1] };
function compassRose(cx, cy, r, turn) {   // eight points, the four long ones split light and dark
  var light = [], dark = [];
  for (var i = 0; i < 8; i++) { var a = turn + i * Math.PI / 4, l = i % 2 ? r * 0.55 : r, w = r * 0.13; var tip = [cx + Math.cos(a) * l, cy + Math.sin(a) * l], s1 = [cx + Math.cos(a + Math.PI / 2) * w, cy + Math.sin(a + Math.PI / 2) * w], s2 = [cx + Math.cos(a - Math.PI / 2) * w, cy + Math.sin(a - Math.PI / 2) * w]; light.push([[cx, cy], tip, s1]); dark.push([[cx, cy], tip, s2]); }
  return { light: light, dark: dark };
}
function trail(points, upto) {   // a dotted path drawn up to a share
  var out = [], n = Math.max(2, Math.round(points.length * clamp01(upto)));
  return [points.slice(0, n)];
}
function mapPath() { var pts = []; for (var i = 0; i <= 40; i++) { var t = i / 40; pts.push([120 + t * 840, 900 - t * 520 + Math.sin(t * 9) * 90]); } return pts; }
function coins(f, n, base, cx, cy, speed, o) {   // gold coins thrown up and falling, turning (thin when edge-on)
  seed(base); var out = [], lit = [];
  for (var i = 0; i < n; i++) { var a = between(-Math.PI * 0.95, -Math.PI * 0.05), v = between(14, 30) * speed, t = f, x = cx + Math.cos(a) * v * t, y = cy + Math.sin(a) * v * t + 0.9 * t * t, r = between(14, 24), k = Math.max(0.12, Math.abs(Math.cos(t * 0.3 + i))); out.push(circle(x, y, r, k, 14)); lit.push(circle(x - r * 0.2, y - r * 0.2 * k, r * 0.45, k, 10)); }
  return { coins: out, lit: lit };
}
function waves(f, y0, amp, n, phase) {   // a band of sea: its crest a running wave
  var pts = [[-60, 1140]];
  for (var x = -60; x <= 1140; x += 30) pts.push([x, y0 + Math.sin(x * 0.012 + f * 0.25 + phase) * amp + Math.sin(x * 0.031 - f * 0.4) * amp * 0.35]);
  pts.push([1140, 1140]);
  return [pts];
}
function galleon(x, y, s, roll) {   // a sailing ship in silhouette: hull, three masts, sails
  var hull = place([[-1.2 * s, 0], [1.25 * s, 0], [0.95 * s, 0.35 * s], [-0.9 * s, 0.35 * s], [-1.3 * s, -0.25 * s]], x, y, roll), sails = [];
  for (var m = -1; m <= 1; m++) { var mx = m * 0.6 * s, h = (m ? 1.1 : 1.45) * s; sails.push(place([[mx - 0.03 * s, 0], [mx + 0.03 * s, 0], [mx + 0.03 * s, -h], [mx - 0.03 * s, -h]], x, y, roll)); sails.push(place([[mx - 0.32 * s, -h * 0.25], [mx + 0.32 * s, -h * 0.3], [mx + 0.36 * s, -h * 0.85], [mx - 0.3 * s, -h * 0.8]], x, y, roll)); }
  return [hull].concat(sails);
}
function palm(x, y, s, sway) {   // a palm tree: a leaning trunk, a crown of fronds
  var out = [slash(x, y, x + 0.3 * s + sway * 20, y - 1.6 * s, 0.09 * s, 1, 0.4)[0]], top = [x + 0.3 * s + sway * 20, y - 1.6 * s];
  for (var k = 0; k < 6; k++) { var a = -Math.PI / 2 + (k - 2.5) * 0.55 + sway * 0.1; out = out.concat(slash(top[0], top[1], top[0] + Math.cos(a) * 0.9 * s, top[1] + Math.sin(a) * 0.9 * s + 0.4 * s, 0.12 * s, 1, k < 3 ? 0.5 : -0.5)); }
  return out;
}
var ADV_RARE = {
  title: function (fr, f, u) {   // a treasure map: a dotted path finding its way to an X
    var path = mapPath();
    lines(fr.main, trail(path, f / 20), ADV.ink, 7, 100, false, [0.1, 22]);
    if (f > 16) { var x = path[40][0], y = path[40][1], k = ease((f - 16) / 3); lines(fr.main, [[[x - 40 * k, y - 40 * k], [x + 40 * k, y + 40 * k]], [[x + 40 * k, y - 40 * k], [x - 40 * k, y + 40 * k]]], [0.7, 0.1, 0.06], 12, 100); }
    var rose = compassRose(230, 260, 150, f * 0.02); polys(fr.main, rose.light, ADV.parch, 100); polys(fr.main, rose.dark, ADV.ink, 100);
    lines(fr.main, [ring(230, 260, 160, 1), ring(230, 260, 172, 1)], ADV.ink, 3, 100);
    var grid = []; for (var g = 0; g < 9; g++) { grid.push([[-60, g * 140], [1140, g * 140]]); grid.push([[g * 140, -60], [g * 140, 1140]]); }
    lines(fr.main, grid, ADV.parch_d, 2, 45);
    polys(fr.haze, [circle(C, C, 700, 1, 40)], ADV.parch_d, 60);
    polys(fr.main, [full()], ADV.parch, 100);
  },
  wipe: function (fr, v) {   // the map rolls up
    var y = 1140 - ease(v) * 1260; polys(fr.top, [[[-60, y], [1140, y], [1140, 1140], [-60, 1140]]], ADV.parch, 100); polys(fr.top, [[[-60, y - 30], [1140, y - 30], [1140, y + 10], [-60, y + 10]]], ADV.parch_d, 100);
  },
  stage: function (fr, f, at, o) {
    var rose = compassRose(C, C, 520, f * 0.01); polys(fr.main, rose.light, ADV.parch, o * 0.5); polys(fr.main, rose.dark, ADV.parch_d, o * 0.5);
    lines(fr.main, [ring(C, C, 530, 1), ring(C, C, 548, 1)], ADV.ink, 3, o * 0.6);
    polys(fr.haze, [circle(C, C, 700, 1, 40)], ADV.parch_d, o * 0.7);
    polys(fr.main, [full()], ADV.parch, o);
  },
  over: function (fr, f, at) {
    if (at >= 2) { seed(1012); var pts = []; for (var i = 0; i < 10; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 160, 222) + between(10, 90); pts.push([C + Math.cos(a) * r, C + Math.sin(a) * r]); } polys(fr.top, glintPolys(twinkle(pts, f, 2, 18)), ADV.gold_l); }
  }
};
var ADV_EPIC = {
  title: function (fr, f, u) {   // under the sea: light falling in shafts, bubbles rising, a chest on the seabed
    seed(1020); var bub = []; for (var i = 0; i < 30; i++) { var x = between(0, 1080) + Math.sin(f * 0.2 + i) * 12, y = 1100 - ((f * between(10, 22) + between(0, 1100)) % 1180); bub.push(circle(x, y, between(5, 16), 1, 12)); }
    lines(fr.main, bub, ADV.foam, 3, 70);
    var shafts = []; for (var k = 0; k < 5; k++) { var x0 = 120 + k * 210 + Math.sin(f * 0.05 + k) * 30; shafts.push([[x0 - 30, -60], [x0 + 30, -60], [x0 + 180, 1140], [x0 + 60, 1140]]); }
    polys(fr.glow, shafts, ADV.sea_l, 60);
    polys(fr.main, [place([[-150, 0], [150, 0], [140, -110], [-140, -110]], C, 930, 0), place([[-160, -100], [160, -100], [120, -190], [-120, -190]], C, 930, 0)], ADV.wood, 100);
    lines(fr.main, [[[C - 150, 860], [C + 150, 860]], [[C, 740], [C, 930]]], ADV.gold, 8, 100);
    polys(fr.main, [[[-60, 920], [1140, 960], [1140, 1140], [-60, 1140]]], [0.6, 0.52, 0.36], 100);
    polys(fr.main, [full()], ADV.deep, 100);
  },
  wipe: function (fr, v) {   // a burst of bubbles fills the screen
    seed(1025); var bub = []; for (var i = 0; i < 90; i++) { var x = between(-60, 1140), y = between(-60, 1140), r = between(20, 70) * ease(v * 1.4 - between(0, 0.4)); if (r > 2) bub.push(circle(x, y, r, 1, 16)); }
    polys(fr.top, bub, ADV.foam, 100);
  },
  stage: function (fr, f, at, o) {   // the chest open behind the card: golden light, coins thrown out, bubbles
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) { var c = coins(at, 30, 1030, C, C + 260, 1, o); polys(fr.main, c.lit, ADV.gold_l, fade(at, 40, 60) * o); polys(fr.main, c.coins, ADV.gold, fade(at, 40, 60) * o); }
    wedges(fr.main, 14, (f - CARD_AT) * 0.004, 300 + 900 * g, ADV.gold, null, o * 0.5, 0, 0.45);
    polys(fr.haze, [circle(C, C + 100, 420 * g + 60, 1, 40)], ADV.gold, o);
    seed(1031); var bub = []; for (var i = 0; i < 26; i++) { var x = between(0, 1080), y = 1100 - ((f * between(10, 22) + between(0, 1100)) % 1180); bub.push(circle(x, y, between(5, 14), 1, 12)); }
    lines(fr.main, bub, ADV.foam, 3, o * 0.6);
    polys(fr.main, [full()], ADV.deep, o);
  },
  over: function (fr, f, at) {
    if (at >= 0) { var c = coins(at + 4, 12, 1040, C, C + 140, 0.8, 100); polys(fr.top, c.lit, ADV.gold_l, fade(at, 30, 44) * 100); polys(fr.top, c.coins, ADV.gold, fade(at, 30, 44) * 100); }
    bigGlint(fr, at, ADV.gold);
  }
};
var ADV_LEGENDARY = {
  title: function (fr, f, u) {   // a galleon riding the waves under a setting sun
    polys(fr.main, waves(f, 760, 26, 0, 0), ADV.sea, 100);
    polys(fr.main, waves(f, 720, 30, 0, 2), ADV.sea_l, 100);
    polys(fr.main, galleon(C - 80 + f * 4, 700 + Math.sin(f * 0.25) * 14, 150, Math.sin(f * 0.2) * 0.06), ADV.ink, 100);
    polys(fr.glow, [circle(C + 220, 620, 260, 1, 48)], ADV.sun, 80);
    polys(fr.main, [circle(C + 220, 650, 190, 1, 64)], ADV.sun, 100);
    polys(fr.main, [[[-60, 300], [1140, 300], [1140, 760], [-60, 760]]], ADV.sky, 100);
    polys(fr.main, [full()], ADV.dusk, 100);
  },
  wipe: function (fr, v) {   // a great wave crashing over the screen
    var x = 1200 - ease(v) * 1500, pts = [[1140, -60], [1140, 1140], [x, 1140]];
    for (var k = 0; k <= 12; k++) { var t = k / 12; pts.push([x - 200 * Math.sin(t * Math.PI) + t * 300, 1140 - t * 1200]); }
    polys(fr.top, [pts], ADV.sea_l, 100); lines(fr.top, [pts.slice(3)], ADV.foam, 40, 100);
  },
  stage: function (fr, f, at, o) {   // the treasure island at sunset: palms, a pillar of gold light, coins raining, the ship far off
    var g = ease((f - CARD_AT) / 6);
    if (at >= 0) { seed(1050); var rain = [], lit = []; for (var i = 0; i < 40; i++) { var x = between(0, 1080), y = -60 + ((at * between(14, 26) + between(0, 1200)) % 1250), r = between(12, 22), k = Math.max(0.15, Math.abs(Math.cos(at * 0.3 + i))); rain.push(circle(x, y, r, k, 12)); lit.push(circle(x - r * 0.2, y - r * 0.2 * k, r * 0.45, k, 8)); } polys(fr.top, lit, ADV.gold_l, fade(at, 50, 68) * o); polys(fr.main, rain, ADV.gold, fade(at, 50, 68) * o); }
    polys(fr.main, palm(130, 900, 230, Math.sin(f * 0.1)).concat(palm(960, 920, 200, Math.sin(f * 0.1 + 1))), ADV.ink, o);
    polys(fr.main, [[[-60, 880], [300, 820], [780, 830], [1140, 880], [1140, 1140], [-60, 1140]]], [0.45, 0.3, 0.12], o);
    polys(fr.main, galleon(250 + f * 2, 740, 50, 0), ADV.ink, o * 0.8);
    polys(fr.main, waves(f, 780, 10, 0, 1), ADV.sea, o);
    polys(fr.haze, [[[C - 160 * g, -60], [C + 160 * g, -60], [C + 260 * g, 1140], [C - 260 * g, 1140]]], ADV.gold_l, o);
    polys(fr.main, [[[C - 70 * g, -60], [C + 70 * g, -60], [C + 120 * g, 820], [C - 120 * g, 820]]], ADV.gold_l, o * 0.5);
    polys(fr.glow, [circle(C, 700, 300 * g + 40, 1, 48)], ADV.sun, o);
    polys(fr.main, [[[-60, 280], [1140, 280], [1140, 780], [-60, 780]]], ADV.sky, o);
    polys(fr.main, [full()], ADV.dusk, o);
  },
  over: function (fr, f, at) {   // the X that marks the spot, drawn in gold over the card; coins and glints
    if (at >= 0 && at < 9) { polys(fr.top, slash(C - 380, C - 420, C + 380, C + 420, 40, ease(at / 3), 0.2), ADV.gold_l, fade(at, 5, 9) * 90); polys(fr.top, slash(C + 380, C - 420, C - 380, C + 420, 40, ease((at - 2) / 3), -0.2), ADV.gold_l, fade(at, 6, 10) * 90); }
    if (at >= 0) { var c = coins(at + 3, 16, 1060, C, C + 180, 1, 100); polys(fr.top, c.lit, ADV.gold_l, fade(at, 30, 44) * 100); polys(fr.top, c.coins, ADV.gold, fade(at, 30, 44) * 100); }
    bigGlint(fr, at, ADV.gold);
  }
};
var GENRE_ADVENTURE = {
  rarities: { rare: ADV_RARE, epic: ADV_EPIC, legendary: ADV_LEGENDARY },
  opening: function (comp) {   // the map unrolls round the pack, a dotted path finds it, an X — it bursts into gold
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 30) { var w = ease(f / 8) * 520; polys(fr.main, [[[cx - w, cy - 380], [cx + w, cy - 380], [cx + w, cy + 380], [cx - w, cy + 380]]], ADV.parch, 80 * fade(f, 24, 30)); polys(fr.main, [[[cx - w - 20, cy - 380], [cx - w + 20, cy - 380], [cx - w + 20, cy + 380], [cx - w - 20, cy + 380]], [[cx + w - 20, cy - 380], [cx + w + 20, cy - 380], [cx + w + 20, cy + 380], [cx + w - 20, cy + 380]]], ADV.parch_d, 100 * fade(f, 24, 30)); }
      if (f >= 6 && f < 30) { var pts = []; for (var i = 0; i <= 30; i++) { var t = i / 30; pts.push([cx - 460 + t * 460, cy + 300 - t * 300 + Math.sin(t * 8) * 60]); } lines(fr.top, trail(pts, (f - 6) / 14), ADV.ink, 7, 100 * fade(f, 26, 30), false, [0.1, 20]); }
      if (f >= 18 && f < 32) { var k = ease((f - 18) / 4); lines(fr.top, [[[cx - 60 * k, cy - 60 * k], [cx + 60 * k, cy + 60 * k]], [[cx + 60 * k, cy - 60 * k], [cx - 60 * k, cy + 60 * k]]], [0.7, 0.1, 0.06], 16, 100 * fade(f, 28, 32)); }
      if (f >= 30) { var c = coins(f - 30, 40, 1070, cx, cy, 1.2, 100); polys(fr.top, c.lit, ADV.gold_l, fade(f, 52, 63) * 100); polys(fr.top, c.coins, ADV.gold, fade(f, 52, 63) * 100); }
      if (f >= 30 && f < 33) polys(fr.top, [circle(cx, cy, 600, 1, 40)], ADV.gold_l, 100 - (f - 30) * 33);
    }
  }
};

// ===== Reportage — documentary: a viewfinder, a clapperboard, the film's archive =========================
var DOC = { black: [0.04, 0.05, 0.06], grey: [0.5, 0.55, 0.58], dim: [0.16, 0.18, 0.2], white: [0.95, 0.96, 0.97], yellow: [1, 0.84, 0.04], red: [1, 0.23, 0.19], sepia: [0.82, 0.7, 0.5] };
function brackets(cx, cy, hw, hh, len) {   // a viewfinder's four corner marks
  var out = [];
  for (var sx = -1; sx <= 1; sx += 2) for (var sy = -1; sy <= 1; sy += 2) out.push([[cx + sx * hw, cy + sy * (hh - len)], [cx + sx * hw, cy + sy * hh], [cx + sx * (hw - len), cy + sy * hh]]);
  return out;
}
function sprockets(x, f, speed) {   // a strip of film running down: its holes
  var out = []; for (var k = -1; k < 14; k++) { var y = -60 + ((k * 90 + f * speed) % 1260); out.push([[x - 18, y], [x + 18, y], [x + 18, y + 50], [x - 18, y + 50]]); } return out;
}
function reel(cx, cy, r, turn) {   // a film reel: rim, hub, five round windows
  var holes = []; for (var k = 0; k < 5; k++) { var a = turn + k * Math.PI * 2 / 5; holes.push(circle(cx + Math.cos(a) * r * 0.55, cy + Math.sin(a) * r * 0.55, r * 0.24, 1, 20)); }
  return [circle(cx, cy, r, 1, 48)].concat(holes, [circle(cx, cy, r * 0.12, 1, 16)]);
}
function filmBand(pts, w, f) {   // a ribbon of film along a path, its frames marked
  var band = ribbon(pts, w, 0, 0, 1), frames = [];
  for (var i = 2; i < pts.length - 2; i += 3) { var p = pts[i]; frames.push(circle(p[0], p[1], w * 0.3, 1, 4)); }
  return { band: band, frames: frames };
}
var DOC_RARE = {
  title: function (fr, f, u) {   // through a camera's viewfinder: corner marks, a blinking REC, the focus breathing
    lines(fr.main, brackets(C, C, 470, 310, 90), DOC.white, 8, 100);
    var thirds = [[[C - 157, C - 300], [C - 157, C + 300]], [[C + 157, C - 300], [C + 157, C + 300]], [[C - 470, C - 103], [C + 470, C - 103]], [[C - 470, C + 103], [C + 470, C + 103]]];
    lines(fr.main, thirds, DOC.white, 2, 30);
    if (f % 12 < 8) polys(fr.main, [circle(140, 280, 22, 1, 20)], DOC.red, 100);
    polys(fr.main, [[[190, 266], [330, 266], [330, 294], [190, 294]]], DOC.white, 100);
    var bars = []; for (var k = 0; k < 8; k++) { var h = 20 + 40 * Math.abs(Math.sin(f * 0.5 + k)); bars.push([[760 + k * 26, 300], [776 + k * 26, 300], [776 + k * 26, 300 - h], [760 + k * 26, 300 - h]]); }
    polys(fr.main, bars, DOC.yellow, 100);
    lines(fr.main, [ring(C, C, 140 + 20 * Math.sin(f * 0.4), 1), [[C - 30, C], [C + 30, C]], [[C, C - 30], [C, C + 30]]], DOC.white, 4, 80);
    polys(fr.main, [full()], DOC.dim, 100);
  },
  wipe: function (fr, v) {   // the shutter closing and opening
    var h = (v < 0.5 ? ease(v * 2) : 1 - ease(v * 2 - 1)) * 620;
    polys(fr.top, [[[-60, -60], [1140, -60], [1140, h - 60], [-60, h - 60]], [[-60, 1140 - h], [1140, 1140 - h], [1140, 1140], [-60, 1140]]], DOC.black, 100);
  },
  stage: function (fr, f, at, o) {
    var k = at >= 0 ? 1 + 0.3 * fade(at, 0, 6) : 1.3;
    lines(fr.main, brackets(C, C, 230 * k, 300 * k, 60), at >= 0 ? DOC.yellow : DOC.white, 7, o);
    if (f % 12 < 8) polys(fr.main, [circle(140, 280, 20, 1, 20)], DOC.red, o);
    lines(fr.main, [ring(C, C, 120 + 30 * Math.sin(f * 0.3), 1)], DOC.white, 3, o * 0.4);
    lines(fr.main, brackets(C, C, 470, 310, 60), DOC.white, 4, o * 0.5);
    polys(fr.main, [full()], DOC.dim, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 6) lines(fr.top, brackets(C, C, 200, 270, 50), DOC.yellow, 6, fade(at, 3, 6) * 100);
  }
};
var DOC_EPIC = {
  title: function (fr, f, u) {   // a clapperboard, its stick slamming shut
    var shut = f < 10 ? 0.5 - 0.5 * ease(f / 10) : 0, cx = C, cy = C + 120;
    var board = [[cx - 380, cy - 60], [cx + 380, cy - 60], [cx + 380, cy + 330], [cx - 380, cy + 330]];
    var stick = place([[0, -10], [760, -10], [760, 70], [0, 70]], cx - 380, cy - 140, -shut);
    var stripes = []; for (var k = 0; k < 8; k++) stripes.push(place([[k * 100, -10], [k * 100 + 50, -10], [k * 100 + 20, 70], [k * 100 - 30, 70]], cx - 380, cy - 140, -shut));
    polys(fr.main, stripes, DOC.white, 100); polys(fr.main, [stick], DOC.black, 100);
    lines(fr.main, [[[cx - 340, cy + 60], [cx + 340, cy + 60]], [[cx - 340, cy + 170], [cx + 340, cy + 170]], [[cx, cy + 60], [cx, cy + 330]]], DOC.white, 4, 100);
    polys(fr.main, [board], DOC.black, 100);
    if (f >= 10 && f < 13) polys(fr.top, [full()], WHITE, 60 - (f - 10) * 20);
    polys(fr.main, [full()], DOC.grey, 100);
  },
  wipe: function (fr, v) { polys(fr.top, [full()], WHITE, 100 * (1 - Math.abs(v * 2 - 1))); },
  stage: function (fr, f, at, o) {   // a film leader's countdown behind the card, the film running at the sides
    var a = (f - CARD_AT) * 0.35;
    polys(fr.main, [[[C, C], [C + Math.cos(-1.5708) * 900, C + Math.sin(-1.5708) * 900], [C + Math.cos(a - 1.5708) * 900, C + Math.sin(a - 1.5708) * 900]]], DOC.sepia, o * 0.35);
    lines(fr.main, [ring(C, C, 330, 1), ring(C, C, 420, 1), [[-60, C], [1140, C]], [[C, -60], [C, 1140]]], DOC.white, 5, o * 0.8);
    polys(fr.main, sprockets(60, f, 40).concat(sprockets(1020, f, 40)), DOC.dim, o);
    polys(fr.main, [[[0, -60], [120, -60], [120, 1140], [0, 1140]], [[960, -60], [1080, -60], [1080, 1140], [960, 1140]]], DOC.black, o);
    seed(1100 + f); var specks = []; for (var i = 0; i < 14; i++) specks.push(circle(between(0, 1080), between(0, 1080), between(2, 6), 1, 8)); polys(fr.main, specks, DOC.black, o * 0.6);
    polys(fr.main, [full()], [0.36, 0.32, 0.26], o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 3) polys(fr.top, [full()], WHITE, 50 - at * 16);
    seed(1110 + f); var scratches = []; for (var i = 0; i < 3; i++) { var x = between(100, 980); scratches.push([[x, -60], [x + between(-20, 20), 1140]]); } if (at >= 0) lines(fr.top, scratches, DOC.white, 2, 40);
  }
};
var DOC_LEGENDARY = {
  title: function (fr, f, u) {   // two reels turning, the film running between them
    polys(fr.main, reel(300, 360, 230, f * 0.2), DOC.dim, 100, true);
    polys(fr.main, reel(800, 330, 190, f * 0.24), DOC.dim, 100, true);
    var pts = []; for (var i = 0; i <= 30; i++) { var t = i / 30; pts.push([300 + t * 500 + Math.sin(t * 3) * 40, 590 + t * 120 + Math.sin(t * 6 + f * 0.3) * 30]); }
    lines(fr.main, [pts], DOC.black, 70, 100); lines(fr.main, [pts], DOC.sepia, 3, 100, false, [10, 18]);
    polys(fr.glow, [circle(C, 900, 300, 0.5, 40)], DOC.sepia, 50);
    polys(fr.main, [full()], [0.24, 0.21, 0.17], 100);
  },
  wipe: function (fr, v) {   // the projector's light coming on
    polys(fr.top, [[[C - 20, -60], [C + 20, -60], [C + 900 * ease(v), 1140], [C - 900 * ease(v), 1140]]], [1, 0.95, 0.8], 100 * (1 - Math.abs(v * 2 - 1)) + 20);
  },
  stage: function (fr, f, at, o) {   // the projector's beam on the card, film ribbons swirling round it, frames flying
    var g = ease((f - CARD_AT) / 6);
    for (var k = 0; k < 3; k++) { var pts = []; for (var i = 0; i <= 40; i++) { var t = i / 40, a = t * Math.PI * 2.2 + f * 0.06 + k * 2.1, r = (330 + k * 90) * g + 40; pts.push([C + Math.cos(a) * r, C + Math.sin(a) * r * 0.75]); } lines(fr.main, [pts], DOC.black, 60, o); lines(fr.main, [pts], DOC.sepia, 3, o, false, [10, 18]); }
    if (at >= 0) { seed(1130); var fl = []; for (var j = 0; j < 14; j++) { var a2 = between(0, Math.PI * 2), d = 260 + at * between(14, 28), s = 44; fl.push(place([[-s, -s * 0.75], [s, -s * 0.75], [s, s * 0.75], [-s, s * 0.75]], C + Math.cos(a2) * d, C + Math.sin(a2) * d, at * 0.1 + j)); } polys(fr.main, fl, DOC.sepia, fade(at, 30, 50) * o); }
    polys(fr.glow, [[[C - 30, 1140], [C + 30, 1140], [C + 420, -60], [C - 420, -60]]], [1, 0.92, 0.75], o * 0.8);
    polys(fr.main, [[[C - 20, 1140], [C + 20, 1140], [C + 360, -60], [C - 360, -60]]], [1, 0.92, 0.75], o * 0.14);
    seed(1131); var dust = []; for (var d2 = 0; d2 < 40; d2++) dust.push([C + between(-300, 300), (between(0, 1080) - f * 2 + 1080) % 1080, between(2, 4)]);
    polys(fr.top, glintPolys(twinkle(dust, f, 1, 6)), [1, 0.95, 0.8]);
    polys(fr.main, reel(160, 160, 120, f * 0.2).concat(reel(920, 160, 120, f * 0.2)), DOC.dim, o, true);
    polys(fr.main, [full()], [0.2, 0.17, 0.14], o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) polys(fr.top, slash(-60, 760, 1140, 300, 34, ease(at / 3), 0.4), [1, 0.95, 0.8], fade(at, 4, 8) * 80);
    seed(1140 + f); var scratches = []; for (var i = 0; i < 4; i++) { var x = between(100, 980); scratches.push([[x, -60], [x + between(-20, 20), 1140]]); } if (at >= 0) lines(fr.top, scratches, DOC.white, 2, 35);
    bigGlint(fr, at, DOC.sepia);
  }
};
var GENRE_DOC = {
  rarities: { rare: DOC_RARE, epic: DOC_EPIC, legendary: DOC_LEGENDARY },
  opening: function (comp) {   // a camera's iris closing on the pack, a flash — it is gone, the iris opens
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 6 && f < 44) {
        var close = f < 26 ? ease((f - 6) / 18) : 1 - ease((f - 30) / 12), r = 560 - 520 * close, blades = [];
        for (var k = 0; k < 7; k++) { var a = k / 7 * Math.PI * 2 + close * 0.8; blades.push([[cx + Math.cos(a) * r, cy + Math.sin(a) * r], [cx + Math.cos(a) * 900, cy + Math.sin(a) * 900], [cx + Math.cos(a + 1.1) * 900, cy + Math.sin(a + 1.1) * 900], [cx + Math.cos(a + 0.9) * r, cy + Math.sin(a + 0.9) * r]]); }
        polys(fr.top, blades, DOC.dim, 100 * fade(f, 40, 44)); lines(fr.top, blades, DOC.grey, 3, 100 * fade(f, 40, 44), true);
      }
      if (f >= 26 && f < 30) polys(fr.top, [circle(cx, cy, 700, 1, 40)], WHITE, 100 - (f - 26) * 25);
      if (f < 26 && f % 10 < 6) polys(fr.main, [circle(cx - 400, cy - 330, 20, 1, 16)], DOC.red, 100);
    }
  }
};

// ===== Insomnie — thriller: a rainy night, a countdown, the hunt ==========================================
var THR = { night: [0.04, 0.04, 0.06], street: [0.09, 0.09, 0.12], rain: [0.62, 0.68, 0.8], red: [0.88, 0.03, 0.02], red_l: [1, 0.3, 0.25], white: [0.95, 0.95, 0.95], blue: [0.2, 0.42, 1], lamp: [1, 0.85, 0.55] };
function rain(L, f, n, base, o, slant) {
  seed(base); var out = [];
  for (var i = 0; i < n; i++) { var x = between(-100, 1180), y = -60 + ((f * between(50, 80) + between(0, 1200)) % 1260), l = between(40, 90); out.push([[x, y], [x + (slant || -0.2) * l, y + l]]); }
  lines(L, out, THR.rain, 2, o);
}
function blinds(L, f, o, ang) {   // a venetian blind's shadow over the screen
  var out = []; for (var k = -6; k < 14; k++) { var y = k * 90 + (f * 2) % 90; out.push(place([[-800, 0], [1800, 0], [1800, 38], [-800, 38]], C, y, ang || -0.18)); }
  polys(L, out, BLACK, o);
}
function pulse(x0, f, y, amp) {   // a heart monitor's trace scrolling
  var pts = [];
  for (var x = -60; x <= 1140; x += 12) { var u = ((x - x0 + f * 24) % 360 + 360) % 360, h = u > 150 && u < 165 ? -amp : u > 165 && u < 180 ? amp * 0.6 : u > 180 && u < 190 ? -amp * 0.3 : 0; pts.push([x, y + h]); }
  return pts;
}
function hatman(x, y, s) {   // a man in a hat and a long coat, in silhouette
  return [place([[-0.45 * s, 0], [-0.32 * s, -1.5 * s], [-0.18 * s, -1.65 * s], [0.18 * s, -1.65 * s], [0.32 * s, -1.5 * s], [0.45 * s, 0], [0.55 * s, 1.6 * s], [-0.55 * s, 1.6 * s]], x, y, 0), place(circle(0, -1.85 * s, 0.22 * s, 1.1, 14), x, y, 0), place([[-0.4 * s, -2.0 * s], [0.4 * s, -2.0 * s], [0.25 * s, -2.08 * s], [0.22 * s, -2.3 * s], [-0.22 * s, -2.3 * s], [-0.25 * s, -2.08 * s]], x, y, 0)];
}
function reticle(cx, cy, r, turn) {
  var out = [ring(cx, cy, r, 1), ring(cx, cy, r * 0.62, 1, 0.3, Math.PI - 0.3), ring(cx, cy, r * 0.62, 1, Math.PI + 0.3, Math.PI * 2 - 0.3)];
  for (var k = 0; k < 4; k++) { var a = turn + k * Math.PI / 2; out.push([[cx + Math.cos(a) * r * 0.75, cy + Math.sin(a) * r * 0.75], [cx + Math.cos(a) * r * 1.25, cy + Math.sin(a) * r * 1.25]]); }
  return out;
}
var THR_RARE = {
  title: function (fr, f, u) {   // a rainy street at night, a lamp, a man in a hat following someone
    rain(fr.top, f, 90, 1200, 70);
    polys(fr.main, hatman(260 + f * 9, 720, 95), BLACK, 100);
    lines(fr.main, [[[C + 260, 1140], [C + 260, 300]], [[C + 260, 300], [C + 200, 290]]], [0.15, 0.15, 0.18], 14, 100);
    cone(fr.glow, C + 200, 1.62, 900, 20, 260, THR.lamp, 50); polys(fr.main, [circle(C + 200, 300, 18, 1, 14)], THR.lamp, 100);
    polys(fr.main, [circle(C + 200, 1000, 300, 0.2, 40)], THR.lamp, 25);
    polys(fr.main, [[[-60, 940], [1140, 940], [1140, 1140], [-60, 1140]]], THR.street, 100);
    polys(fr.main, [full()], THR.night, 100);
  },
  wipe: function (fr, v) { blinds(fr.top, 0, 100 * (1 - Math.abs(v * 2 - 1)) + 10); },
  stage: function (fr, f, at, o) {
    rain(fr.top, f, 60, 1210, o * 0.5);
    blinds(fr.main, f, o * 0.55);
    polys(fr.haze, [circle(C, C, 420, 1, 40)], THR.red, o * 0.5);
    polys(fr.main, [full()], THR.street, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 6) polys(fr.top, slash(-60, 600, 1140, 480, 22, ease(at / 3), 0.2), THR.red_l, fade(at, 3, 6) * 90);
  }
};
var THR_EPIC = {
  title: function (fr, f, u) {   // a clock's hands racing, a pulse on a monitor
    var p = pulse(0, f, 860, 120); lines(fr.glow, [p], THR.red, 16, 90); lines(fr.main, [p], THR.red_l, 5, 100);
    var ticks = []; for (var k = 0; k < 60; k++) { var a = k / 60 * Math.PI * 2, l = k % 5 ? 20 : 50; ticks.push([[C + Math.cos(a) * 330, 420 + Math.sin(a) * 330], [C + Math.cos(a) * (330 - l), 420 + Math.sin(a) * (330 - l)]]); }
    lines(fr.main, ticks.concat([ring(C, 420, 350, 1)]), THR.white, 5, 100);
    var ha = f * 0.6 - 1.5708, ma = f * 0.08 - 1.5708; lines(fr.main, [[[C, 420], [C + Math.cos(ha) * 280, 420 + Math.sin(ha) * 280]]], THR.red_l, 8, 100); lines(fr.main, [[[C, 420], [C + Math.cos(ma) * 190, 420 + Math.sin(ma) * 190]]], THR.white, 14, 100);
    polys(fr.main, [full()], THR.night, 100);
  },
  wipe: function (fr, v) { polys(fr.top, [full()], THR.red, 100 * (1 - Math.abs(v * 2 - 1))); },
  stage: function (fr, f, at, o) {
    var p = pulse(200, f, C + 330, 160); lines(fr.glow, [p], THR.red, 18, o); lines(fr.main, [p], THR.red_l, 6, o);
    if (at >= 0) for (var q = 0; q < 3; q++) { var t = at - q * 6; if (t < 0) continue; lines(fr.glow, [ring(C, C, 260 + t * 30, 1.2)], THR.red, 24, fade(t, 6, 14) * o); }
    var ticks = []; for (var k = 0; k < 60; k++) { var a = k / 60 * Math.PI * 2 + f * 0.01, l = k % 5 ? 14 : 34; ticks.push([[C + Math.cos(a) * 470, C + Math.sin(a) * 470], [C + Math.cos(a) * (470 - l), C + Math.sin(a) * (470 - l)]]); }
    lines(fr.main, ticks, THR.white, 4, o * 0.8);
    polys(fr.main, [full()], THR.night, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 4) polys(fr.top, [full()], THR.red, 35 - at * 9);
    bigGlint(fr, at, THR.red_l);
  }
};
// the shots: when (after the card turned), where the bullet strikes the card, where it came from
var SHOTS = [[8, C - 60, C - 110, -0.3], [11, C + 70, C - 30, 3.5], [13, C - 30, C + 90, 2.6], [17, C + 55, C + 150, -0.9], [20, C - 85, C + 20, 3.0]];
function bulletHole(x, y, base) {   // a hole: its dark core, a pale chipped rim, cracks running out like a star
  seed(base); var cracks = [], ring2 = [];
  for (var k = 0; k < 8; k++) { var a = k / 8 * Math.PI * 2 + between(-0.2, 0.2), len = between(36, 92), pts = [[x + Math.cos(a) * 9, y + Math.sin(a) * 9]], px = pts[0][0], py = pts[0][1]; for (var j = 0; j < 4; j++) { a += between(-0.35, 0.35); px += Math.cos(a) * len / 4; py += Math.sin(a) * len / 4; pts.push([px, py]); } cracks.push(pts); }
  for (var q = 0; q <= 10; q++) { var a2 = q / 10 * Math.PI * 2; ring2.push([x + Math.cos(a2) * between(24, 34), y + Math.sin(a2) * between(24, 34)]); }
  return { cracks: cracks, ring: [ring2.slice(0, 6), ring2.slice(7, 11)], rim: circle(x, y, 13, 1, 14), core: circle(x, y, 8, 1, 12) };
}
function gunshot(fr, t, x, y, from, base) {   // a tracer from off screen, a flash and sparks on impact, the hole that stays
  if (t < 0) return;
  if (t < 2) { var sx = x + Math.cos(from) * 900, sy = y + Math.sin(from) * 900; lines(fr.glow, [[[sx, sy], [x, y]]], [1, 0.8, 0.4], 14, 100 - t * 40); lines(fr.top, [[[x + Math.cos(from) * (60 + t * 200), y + Math.sin(from) * (60 + t * 200)], [x + Math.cos(from) * (300 + t * 200), y + Math.sin(from) * (300 + t * 200)]]], [1, 0.95, 0.8], 5, 100 - t * 40); }
  if (t < 3) { polys(fr.glow, [circle(x, y, 70 - t * 15, 1, 20)], [1, 0.75, 0.35], 100 - t * 30); polys(fr.top, [burst(x, y, 9, 46 - t * 10, 14, 0.3, base)], [1, 0.95, 0.75], 100 - t * 33); }
  if (t < 6) { seed(base * 7); var sp = []; for (var k = 0; k < 10; k++) { var a = between(0, Math.PI * 2), d = 14 + t * between(12, 26); sp.push([[x + Math.cos(a) * d, y + Math.sin(a) * d], [x + Math.cos(a) * (d + 14), y + Math.sin(a) * (d + 14)]]); } lines(fr.top, sp, [1, 0.85, 0.5], 3, fade(t, 2, 6) * 100); }
  var h = bulletHole(x, y, base), grow = ease((t + 1) / 3);
  lines(fr.top, partOf(h.cracks, grow), [0.92, 0.94, 1], 2.4, 85);
  if (t >= 1) lines(fr.top, h.ring, [0.92, 0.94, 1], 1.8, 60);
  polys(fr.top, [h.core], [0.03, 0.03, 0.04], 100); polys(fr.top, [h.rim], [0.75, 0.75, 0.78], 100);   // the first drawn lies on top
}
var THR_LEGENDARY = {
  title: function (fr, f, u) {   // the hunt: rooftops in the rain, a helicopter's searchlight, police lights
    rain(fr.top, f, 120, 1220, 80, -0.35);
    var sx = C + 380 * Math.sin(f * 0.1); polys(fr.glow, [[[C + 300, -60], [C + 340, -60], [sx + 180, 1140], [sx - 180, 1140]]], [0.85, 0.9, 1], 60);
    polys(fr.main, [skyline(1140, 560, 1230)], BLACK, 100);
    polys(fr.haze, [[[-60, 520], [1140, 520], [1140, 1140], [-60, 1140]]], (f % 8 < 4) ? THR.red : THR.blue, 100);
    polys(fr.main, [[[-60, 300], [1140, 300], [1140, 900], [-60, 900]]], [0.12, 0.12, 0.2], 100);
    polys(fr.main, [full()], THR.night, 100);
  },
  wipe: function (fr, v) { polys(fr.top, [full()], v < 0.5 ? THR.red : THR.blue, 100 * (1 - Math.abs(v * 2 - 1)) + 15); },
  stage: function (fr, f, at, o) {   // the searchlight on the card, strobes, a reticle locking on it, glass flying
    rain(fr.top, f, 100, 1240, o * 0.6, -0.35);
    var lock = at >= 0 ? 1 : ease((f - CARD_AT) / 20), r = 700 - 420 * lock;
    lines(fr.top, reticle(C, C, r, f * 0.05 * (1 - lock)), at >= 0 ? THR.red_l : THR.white, 5, o);
    if (at >= 0) { seed(1250); var shards = []; for (var i = 0; i < 26; i++) { var a = between(0, Math.PI * 2), d = 220 + at * between(14, 34), s = between(14, 40); shards.push(place([[0, -s], [s * 0.5, s * 0.3], [-s * 0.4, s * 0.6]], C + Math.cos(a) * d, C + Math.sin(a) * d, at * 0.25 + i)); } polys(fr.top, shards, [0.8, 0.88, 1], fade(at, 30, 50) * o); lines(fr.top, shards, WHITE, 2, fade(at, 30, 50) * o, true); }
    polys(fr.glow, [[[C - 40, -60], [C + 40, -60], [C + 330, 1140], [C - 330, 1140]]], [0.85, 0.9, 1], o * 0.45);
    polys(fr.haze, [circle(f % 8 < 4 ? 150 : 930, C, 520, 1.2, 40)], (f % 8 < 4) ? THR.red : THR.blue, o);
    polys(fr.main, [skyline(1140, 700, 1251)], BLACK, o);
    polys(fr.main, [[[-60, 400], [1140, 400], [1140, 1000], [-60, 1000]]], [0.1, 0.1, 0.17], o);
    polys(fr.main, [full()], THR.night, o);
  },
  over: function (fr, f, at) {   // locked on — then shots: tracers, sparks, and bullet holes left in the card
    if (at >= 0 && at < 8) lines(fr.top, reticle(C, C, 300 - at * 10, 0), THR.red_l, 6, fade(at, 4, 8) * 100);
    for (var i = 0; i < SHOTS.length; i++) gunshot(fr, at - SHOTS[i][0], SHOTS[i][1], SHOTS[i][2], SHOTS[i][3], 1290 + i);
    bigGlint(fr, at, THR.red_l);
  }
};
var GENRE_THRILLER = {
  rarities: { rare: THR_RARE, epic: THR_EPIC, legendary: THR_LEGENDARY },
  opening: function (comp) {   // a sniper's reticle finds the pack and locks; a shot — it shatters like glass
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 30) { var lock = ease(f / 22), x = cx + (1 - lock) * 260 * Math.sin(f * 0.4), y = cy + (1 - lock) * 160 * Math.cos(f * 0.3); lines(fr.top, reticle(x, y, 380 - 160 * lock, 0), f > 22 ? THR.red_l : THR.white, 5, 100); }
      if (f >= 28 && f < 31) polys(fr.top, [circle(cx, cy, 650, 1, 40)], WHITE, 100 - (f - 28) * 33);
      if (f >= 30) { seed(1270); var shards = []; for (var i = 0; i < 40; i++) { var a = between(0, Math.PI * 2), d = 40 + (f - 30) * between(10, 30), s = between(16, 46); shards.push(place([[0, -s], [s * 0.5, s * 0.3], [-s * 0.4, s * 0.6]], cx + Math.cos(a) * d, cy + Math.sin(a) * d + (f - 30) * (f - 30) * 0.5, (f - 30) * 0.3 + i)); } polys(fr.top, shards, [0.8, 0.88, 1], fade(f, 50, 63) * 100); lines(fr.top, shards, WHITE, 2, fade(f, 50, 63) * 100, true); }
    }
  }
};

// ===== Fou rire — comedy: a party popper, a cream pie, the big show ======================================
var COM = { yellow: [1, 0.82, 0.25], sun: [1, 0.7, 0.1], pink: [1, 0.31, 0.55], cyan: [0.24, 0.78, 1], green: [0.3, 0.85, 0.45], violet: [0.6, 0.4, 1], ink: [0.1, 0.08, 0.19], cream: [1, 0.98, 0.92], white: [1, 1, 1] };
var PARTY = [COM.pink, COM.cyan, COM.yellow, COM.green, COM.violet];
function dots(L, f, o, color, gap) {   // a field of polka dots drifting
  var out = [], g = gap || 90;
  for (var y = -60; y < 1180; y += g) for (var x = -60; x < 1180; x += g) { var off = (Math.floor((y + 60) / g) % 2) * g / 2; out.push(circle(x + off + (f * 2) % g, y, g * 0.18, 1, 12)); }
  polys(L, out, color, o);
}
function confetti(L, f, n, base, cx, cy, spread, o, burst) {   // confetti thrown out (burst) or raining, in the party colours
  seed(base); var groups = [[], [], [], [], []];
  for (var i = 0; i < n; i++) {
    var x, y, s = between(8, 16);
    if (burst) { var a = between(-Math.PI, 0) * spread - Math.PI * (1 - spread) / 2, v = between(16, 34); x = cx + Math.cos(a) * v * f; y = cy + Math.sin(a) * v * f + 0.8 * f * f; }
    else { x = between(-40, 1120) + Math.sin(f * 0.15 + i) * 30; y = -60 + ((f * between(8, 16) + between(0, 1200)) % 1260); }
    groups[i % 5].push(place([[-s, -s * 0.4], [s, -s * 0.4], [s, s * 0.4], [-s, s * 0.4]], x, y, f * 0.3 + i, 1, Math.max(0.2, Math.abs(Math.cos(f * 0.3 + i)))));
  }
  for (var k = 0; k < 5; k++) polys(L, groups[k], PARTY[k], o);
}
function popper(cx, cy, s, ang) {   // a party popper's cone, striped
  return { cone: place([[0, -0.25 * s], [1.0 * s, -0.04 * s], [1.0 * s, 0.04 * s], [0, 0.25 * s]], cx, cy, ang), band: place([[0.3 * s, -0.19 * s], [0.45 * s, -0.16 * s], [0.45 * s, 0.16 * s], [0.3 * s, 0.19 * s]], cx, cy, ang) };
}
function pie(cx, cy, r, tilt) {   // a cream pie seen from the side: the tin, the cream piled on it
  return { tin: place([[-r, 0], [r, 0], [r * 0.85, r * 0.3], [-r * 0.85, r * 0.3]], cx, cy, tilt), cream: place(burst(0, -r * 0.1, 10, r * 1.05, r * 0.85, 0.1, 0, 0.45), cx, cy, tilt) };
}
function splat(cx, cy, r, base) {   // a splat of cream: a lumpy blob and drops round it
  seed(base); var drops = []; for (var i = 0; i < 10; i++) { var a = between(0, Math.PI * 2), d = r * between(1.1, 1.6); drops.push(circle(cx + Math.cos(a) * d, cy + Math.sin(a) * d, r * between(0.08, 0.18), 1, 10)); }
  return [burst(cx, cy, 14, r, r * 0.75, 0.25, base)].concat(drops);
}
function dizzy(cx, cy, r, f, n) {   // stars wheeling round a head
  var out = []; for (var i = 0; i < n; i++) { var a = f * 0.2 + i * Math.PI * 2 / n; out.push(star5(cx + Math.cos(a) * r, cy + Math.sin(a) * r * 0.35, 26, f * 0.2 + i)); } return out;
}
function balloon(x, y, r) { return { body: circle(x, y, r, 1.2, 24), knot: [[x - 8, y + r * 1.2 + 10], [x + 8, y + r * 1.2 + 10], [x, y + r * 1.2 - 4]] }; }
var COM_RARE = {
  title: function (fr, f, u) {   // a party popper going off
    var pp = popper(150, 900, 260, -0.8); polys(fr.main, [pp.band], COM.pink, 100); polys(fr.main, [pp.cone], COM.yellow, 100); lines(fr.main, [pp.cone], COM.ink, 6, 100, true);
    if (f > 4) confetti(fr.top, f - 4, 70, 1400, 330, 700, 0.5, 100, true);
    if (f > 4) { var streamers = []; for (var k = 0; k < 5; k++) { var pts = []; for (var i = 0; i <= 14; i++) { var t = i / 14 * Math.min(1, (f - 4) / 8); pts.push([330 + t * (300 + k * 120), 700 - t * (500 + k * 60) + Math.sin(t * 10 + k) * 40]); } streamers.push(pts); } for (var k2 = 0; k2 < 5; k2++) lines(fr.main, [streamers[k2]], PARTY[k2], 10, 100); }
    dots(fr.main, f, 100, [1, 0.9, 0.45], 110);
    polys(fr.main, [full()], COM.yellow, 100);
  },
  wipe: function (fr, v) { iris(fr, v < 0.5 ? 900 * (1 - ease(v * 2)) + 30 : 30 + 900 * ease(v * 2 - 1)); },
  stage: function (fr, f, at, o) {
    confetti(fr.main, f, 50, 1410, 0, 0, 0, o, false);
    polys(fr.haze, [circle(C, C, 420, 1, 40)], COM.white, o * 0.6);
    dots(fr.main, f, o, [1, 0.9, 0.45], 110);
    polys(fr.main, [full()], COM.yellow, o);
  },
  over: function (fr, f, at) { if (at >= 0) confetti(fr.top, at, 30, 1420, C, C + 100, 0.7, fade(at, 24, 40) * 100, true); }
};
var COM_EPIC = {
  title: function (fr, f, u) {   // a cream pie flying in an arc, whooshing
    var t = f / 20, x = -200 + t * 1500, y = 700 - Math.sin(t * Math.PI) * 420, p = pie(x, y, 130, f * 0.25);
    lines(fr.main, [[[x - 260, y + 30], [x - 140, y + 20]], [[x - 300, y - 30], [x - 160, y - 30]], [[x - 250, y - 80], [x - 150, y - 70]]], COM.ink, 8, 100);
    polys(fr.main, [p.cream], COM.cream, 100); lines(fr.main, [p.cream], COM.ink, 5, 100, true); polys(fr.main, [p.tin], [0.75, 0.55, 0.3], 100);
    dots(fr.main, f, 100, [1, 0.55, 0.7], 100);
    polys(fr.main, [full()], COM.pink, 100);
  },
  wipe: function (fr, v) { polys(fr.top, splat(C, C, 100 + ease(v) * 900, 1430), COM.cream, 100); },
  stage: function (fr, f, at, o) {   // cream dripping from the top, stars wheeling round the card, a spotlight
    seed(1440); var pts = [[-60, -60], [1140, -60], [1140, 80]]; for (var x = 1140; x >= -60; x -= 60) { var len = 60 + between(0, 260) * ease((f - CARD_AT) / 20); pts.push([x, 80], [x - 15, 80 + len], [x - 30, 80 + len + 20], [x - 45, 80 + len], [x - 60, 80]); }
    polys(fr.main, [pts], COM.cream, o);
    polys(fr.top, dizzy(C, C - 270, 220, f, 5), COM.yellow, o); lines(fr.top, dizzy(C, C - 270, 220, f, 5), COM.ink, 4, o, true);
    polys(fr.haze, [circle(C, C, 380, 1, 40)], COM.white, o * 0.7);
    dots(fr.main, f, o, [1, 0.55, 0.7], 100);
    polys(fr.main, [full()], COM.pink, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) polys(fr.top, splat(C + 140, C - 180, 30 + at * 6, 1450), COM.cream, fade(at, 4, 8) * 100);
    bigGlint(fr, at, COM.yellow);
  }
};
var COM_LEGENDARY = {
  title: function (fr, f, u) {   // the big show: a spotlight, a brick wall, a microphone — and the crowd laughing (rays)
    var bricks = []; for (var y = 0; y < 1140; y += 60) for (var x = -60; x < 1140; x += 120) bricks.push([[x + (y / 60 % 2) * 60, y], [x + 112 + (y / 60 % 2) * 60, y], [x + 112 + (y / 60 % 2) * 60, y + 52], [x + (y / 60 % 2) * 60, y + 52]]);
    lines(fr.main, [[[C, 1140], [C, 520]]], COM.ink, 14, 100); polys(fr.main, [circle(C, 480, 50, 1.3, 20)], [0.3, 0.3, 0.35], 100);
    polys(fr.glow, [[[C - 40, -60], [C + 40, -60], [C + 420, 1140], [C - 420, 1140]]], [1, 0.95, 0.8], 70);
    polys(fr.main, bricks, [0.55, 0.2, 0.15], 100); polys(fr.main, [full()], [0.3, 0.1, 0.08], 100);
  },
  wipe: function (fr, v) { confetti(fr.top, v * 12, 160, 1460, C, 1140, 0.9, 100, true); polys(fr.top, [full()], COM.white, 100 * (1 - Math.abs(v * 2 - 1)) * 0.6); },
  stage: function (fr, f, at, o) {   // confetti cannons, balloons rising, a rainbow sunburst turning
    if (at >= 0) { confetti(fr.top, at, 70, 1470, 60, 1100, 0.35, fade(at, 40, 60) * o, true); confetti(fr.top, at, 70, 1471, 1020, 1100, 0.35, fade(at, 40, 60) * o, true); }
    seed(1480); for (var i = 0; i < 12; i++) { var x = between(40, 1040), y = 1300 - (f - CARD_AT) * between(14, 24), r = between(40, 60), b = balloon(x, y, r); lines(fr.main, [[[x, y + r * 1.2 + 10], [x + Math.sin(f * 0.2 + i) * 20, y + r * 1.2 + 140]]], COM.ink, 2, o); polys(fr.main, [b.body, b.knot], PARTY[i % 5], o); polys(fr.main, [circle(x - r * 0.35, y - r * 0.5, r * 0.18, 1.3, 10)], COM.white, o * 0.7); }
    confetti(fr.main, f, 60, 1490, 0, 0, 0, o, false);
    var rays = []; for (var k = 0; k < 20; k++) { var a = (f - CARD_AT) * 0.015 + k * Math.PI / 10, w = 0.12; rays.push([[C, C], [C + Math.cos(a - w) * 1100, C + Math.sin(a - w) * 1100], [C + Math.cos(a + w) * 1100, C + Math.sin(a + w) * 1100]]); }
    for (var k2 = 0; k2 < 5; k2++) { var some = []; for (var j = k2; j < rays.length; j += 5) some.push(rays[j]); polys(fr.main, some, PARTY[k2], o); }
    polys(fr.main, [full()], COM.yellow, o);
  },
  over: function (fr, f, at) {
    if (at >= 0) confetti(fr.top, at, 50, 1495, C, C + 60, 0.8, fade(at, 24, 44) * 100, true);
    if (at >= 2) polys(fr.top, dizzy(C, C - 280, 240, f, 6), COM.yellow, 100);
    bigGlint(fr, at, COM.yellow);
  }
};
var GENRE_COMEDY = {
  rarities: { rare: COM_RARE, epic: COM_EPIC, legendary: COM_LEGENDARY },
  opening: function (comp) {   // a cream pie flies in and splats the pack — confetti
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 24) { var t = f / 24, x = -150 + t * (cx + 150), y = cy + 200 - Math.sin(t * Math.PI) * 260 + t * -200, p = pie(x, y, 120, f * 0.3); polys(fr.top, [p.cream], COM.cream, 100); lines(fr.top, [p.cream], COM.ink, 5, 100, true); polys(fr.top, [p.tin], [0.75, 0.55, 0.3], 100); }
      if (f >= 24 && f < 50) polys(fr.top, splat(cx, cy, 150 + ease((f - 24) / 5) * 260, 1500), COM.cream, fade(f, 40, 50) * 100);
      if (f >= 26) confetti(fr.top, f - 26, 90, 1510, cx, cy, 0.9, fade(f, 52, 63) * 100, true);
    }
  }
};

// ===== Crayonné — animation: a sketch, a flip book, the grand finale =====================================
var ANI = { paper: [1, 0.97, 0.92], grid: [0.75, 0.84, 1], blue: [0.23, 0.42, 1], graphite: [0.36, 0.37, 0.42], violet: [0.48, 0.36, 1], mint: [0.18, 0.88, 0.7], orange: [1, 0.62, 0.11], red: [1, 0.3, 0.35], yellow: [1, 0.85, 0.2], sky: [0.55, 0.82, 1] };
var RAINBOW = [ANI.red, ANI.orange, ANI.yellow, ANI.mint, ANI.blue, ANI.violet];
function boil(pts, f, amp, base) {   // a drawn line boiling: redrawn a little off each frame
  seed(base + Math.floor(f / 2)); var out = []; for (var i = 0; i < pts.length; i++) out.push([pts[i][0] + between(-amp, amp), pts[i][1] + between(-amp, amp)]); return out;
}
function sketchCircle(cx, cy, r, f, base) { var pts = []; for (var i = 0; i <= 36; i++) { var a = i / 36 * Math.PI * 2.1; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return boil(pts, f, 6, base); }
function paperGrid(L, o) { var g = []; for (var k = 0; k < 14; k++) { g.push([[-60, k * 90], [1140, k * 90]]); g.push([[k * 90, -60], [k * 90, 1140]]); } lines(L, g, ANI.grid, 2, o); }
function bounceBall(f, x0, base) {   // a ball bouncing across, squashed on the ground: its positions this frame and the last ones
  var out = [];
  for (var k = 0; k < 5; k++) { var t = (f - k * 1.5) * 0.09, x = x0 + t * 260, ph = (t * 1.6) % 1, y = 900 - Math.abs(Math.sin(ph * Math.PI)) * 520 * Math.pow(0.85, Math.floor(t * 1.6)), sq = ph < 0.08 || ph > 0.92 ? 0.65 : 1.1; out.push({ x: x, y: y, sx: 1 / sq, sy: sq, a: k }); }
  return out;
}
var ANI_RARE = {
  title: function (fr, f, u) {   // an animator's sheet: construction circles in blue pencil, a figure sketched, boiling
    lines(fr.main, [sketchCircle(C, 460, 150, f, 1600), sketchCircle(C, 700, 210, f, 1601), boil([[C - 300, 960], [C + 300, 960]], f, 4, 1602), boil([[C, 300], [C, 920]], f, 4, 1603)], ANI.blue, 5, 90);
    lines(fr.main, [boil([[C - 120, 400], [C - 60, 360], [C + 60, 360], [C + 120, 420], [C + 100, 560], [C, 610], [C - 100, 560], [C - 120, 400]], f, 5, 1604)], ANI.graphite, 7, 100);
    paperGrid(fr.main, 50);
    polys(fr.main, [full()], ANI.paper, 100);
  },
  wipe: function (fr, v) {   // the next sheet laid over
    var x = 1200 - ease(v) * 1300; polys(fr.top, [[[x, -60], [x + 1300, -60], [x + 1300, 1140], [x, 1140]]], ANI.paper, 100); lines(fr.top, [[[x, -60], [x, 1140]]], ANI.graphite, 4, 100);
  },
  stage: function (fr, f, at, o) {
    lines(fr.main, [sketchCircle(C, C, 360, f, 1610), sketchCircle(C, C, 470, f, 1611)], ANI.blue, 4, o * 0.8);
    paperGrid(fr.main, o * 0.5);
    polys(fr.main, [full()], ANI.paper, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 10) lines(fr.top, [sketchCircle(C, C, 260 + at * 12, f, 1620)], ANI.orange, 6, fade(at, 6, 10) * 100); }
};
var ANI_EPIC = {
  title: function (fr, f, u) {   // a flip book: a ball bouncing, its in-betweens trailing
    var bb = bounceBall(f, 80, 1630);
    for (var k = bb.length - 1; k >= 0; k--) { var b = bb[k]; polys(fr.main, [place(circle(0, 0, 70, 1, 24), b.x, b.y, 0, b.sx, b.sy)], k ? ANI.grid : ANI.red, k ? 60 : 100); }
    lines(fr.main, [[[-60, 975], [1140, 975]]], ANI.graphite, 5, 100);
    var pages = []; for (var p = 0; p < 5; p++) { var t = ((f * 0.4 + p) % 5) / 5; pages.push([[1140, 1140], [1140 - 400 * t, 1140], [1140 - 300 * t, 1140 - 500 * t], [1140, 1140 - 400 * t]]); }
    lines(fr.main, pages, ANI.graphite, 3, 50, true);
    polys(fr.main, [full()], ANI.paper, 100);
  },
  wipe: function (fr, v) { var pages = []; for (var p = 0; p < 6; p++) { var t = clamp01(v * 1.6 - p * 0.1); pages.push([[1140, 1140], [1140 - 1600 * t, 1140], [1140 - 1300 * t, 1140 - 1700 * t], [1140, 1140 - 1600 * t]]); } polys(fr.top, pages, ANI.paper, 100); lines(fr.top, pages, ANI.graphite, 3, 100, true); },
  stage: function (fr, f, at, o) {   // balls bouncing round the card in colour, their trails
    for (var i = 0; i < 4; i++) { var bb = bounceBall(f - CARD_AT + i * 9, -100 + i * 40, 1640 + i); for (var k = bb.length - 1; k >= 0; k--) { var b = bb[k]; polys(fr.main, [place(circle(0, 0, 46, 1, 20), (b.x + i * 300) % 1300 - 100, b.y - i * 120, 0, b.sx, b.sy)], RAINBOW[(i * 2) % 6], k ? o * 0.35 : o); } }
    paperGrid(fr.main, o * 0.4);
    polys(fr.haze, [circle(C, C, 400, 1, 40)], ANI.sky, o * 0.5);
    polys(fr.main, [full()], ANI.paper, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 8) { var pops = []; for (var k = 0; k < 8; k++) { var a = k * Math.PI / 4; pops.push([[C + Math.cos(a) * (240 + at * 14), C + Math.sin(a) * (300 + at * 14)], [C + Math.cos(a) * (290 + at * 18), C + Math.sin(a) * (350 + at * 18)]]); } lines(fr.top, pops, ANI.graphite, 8, fade(at, 4, 8) * 100); } bigGlint(fr, at, ANI.orange); }
};
var ANI_LEGENDARY = {
  title: function (fr, f, u) {   // cels sliding over each other in colour, a cartoon sky opening
    for (var k = 0; k < 4; k++) { var x = -400 + ((f * (14 + k * 8) + k * 300) % 1600); polys(fr.main, [[[x, 180 + k * 200], [x + 700, 160 + k * 200], [x + 760, 330 + k * 200], [x + 40, 350 + k * 200]]], RAINBOW[k + 1], 85); }
    polys(fr.main, [place(circle(0, 0, 140, 0.5, 30), 260 + f * 6, 220, 0), place(circle(0, 0, 100, 0.5, 30), 360 + f * 6, 200, 0)], [1, 1, 1], 100);
    polys(fr.main, [full()], ANI.sky, 100);
  },
  wipe: function (fr, v) { iris(fr, 30 + ease(v) * 1000); },
  stage: function (fr, f, at, o) {   // a rainbow behind the card, a cartoon sun turning, paint splashing, stars
    var g = ease((f - CARD_AT) / 8);
    for (var k = 0; k < 6; k++) lines(fr.main, [ring(C, C + 380, (620 - k * 50) * g + 40, 1, Math.PI, Math.PI * 2)], RAINBOW[k], 52, o);
    var rays = []; for (var r = 0; r < 16; r++) { var a = f * 0.03 + r * Math.PI / 8, w = 0.09; rays.push([[C, C], [C + Math.cos(a - w) * 1100, C + Math.sin(a - w) * 1100], [C + Math.cos(a + w) * 1100, C + Math.sin(a + w) * 1100]]); }
    polys(fr.main, rays, [1, 0.95, 0.6], o * 0.55);
    if (at >= 0) { seed(1660); var splats = []; for (var i = 0; i < 8; i++) { var a2 = between(0, Math.PI * 2), d = 380 + between(0, 160); splats.push({ s: splat(C + Math.cos(a2) * d, C + Math.sin(a2) * d, 50 * ease(at / 4), 1661 + i), c: RAINBOW[i % 6] }); } for (var j = 0; j < splats.length; j++) polys(fr.main, splats[j].s, splats[j].c, o); }
    seed(1670); var stars = []; for (var q = 0; q < 14; q++) { var a3 = between(0, Math.PI * 2), d3 = between(320, 520); stars.push(star5(C + Math.cos(a3 + f * 0.02) * d3, C + Math.sin(a3 + f * 0.02) * d3, between(16, 30), f * 0.1 + q)); }
    polys(fr.top, stars, ANI.yellow, o); lines(fr.top, stars, ANI.graphite, 3, o, true);
    polys(fr.main, [full()], ANI.sky, o);
  },
  over: function (fr, f, at) {
    if (at >= 0 && at < 8) for (var k = 0; k < 3; k++) polys(fr.top, slash(-60, 760 - k * 40, 1140, 300 - k * 40, 18, ease((at - k) / 3), 0.4), RAINBOW[k * 2], fade(at, 4, 8) * 90);
    bigGlint(fr, at, ANI.yellow);
  }
};
var GENRE_ANIMATION = {
  rarities: { rare: ANI_RARE, epic: ANI_EPIC, legendary: ANI_LEGENDARY },
  opening: function (comp) {   // the pack scribbled over in pencil, coloured in a flash, rubbed out by an eraser
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 30) { seed(1680 + Math.floor(f / 2)); var sc = []; for (var i = 0; i < Math.min(14, f); i++) { var y = cy - 220 + i * 32; sc.push([[cx - 160 + between(-20, 20), y], [cx + 160 + between(-20, 20), y + between(-14, 14)]]); } lines(fr.top, sc, ANI.graphite, 8, 100); }
      if (f >= 24 && f < 30) polys(fr.top, [[[cx - 200, cy - 260], [cx + 200, cy - 260], [cx + 200, cy + 260], [cx - 200, cy + 260]]], RAINBOW[f % 6], 80);
      if (f >= 30 && f < 50) { var x = cx - 300 + (f - 30) * 40; polys(fr.top, [place([[-70, -40], [70, -40], [70, 40], [-70, 40]], x, cy + Math.sin(f) * 40, 0.3)], [1, 0.6, 0.65], 100); polys(fr.top, [[[cx - 300, cy - 300], [x - 60, cy - 300], [x - 60, cy + 300], [cx - 300, cy + 300]]], ANI.paper, 100 * fade(f, 44, 50)); }
    }
  }
};

// ===== Scellés — crime: a clue, the board, the crime scene ===============================================
var CRI = { night: [0.05, 0.06, 0.09], asphalt: [0.13, 0.13, 0.15], tape: [0.96, 0.77, 0], ink: [0.11, 0.1, 0.09], chalk: [0.92, 0.92, 0.9], cork: [0.66, 0.47, 0.28], manila: [0.85, 0.71, 0.42], red: [0.8, 0.1, 0.08], blue: [0.2, 0.42, 1], white: [1, 1, 1] };
function tapeBand(y0, y1, offset) {   // a band of police tape across the screen: yellow, its black chevrons
  var band = [[-200, y0 - 40], [1300, y1 - 40], [1300, y1 + 40], [-200, y0 + 40]], ang = Math.atan2(y1 - y0, 1500), marks = [];
  for (var k = -4; k < 22; k++) { var x = -200 + k * 90 + (offset % 90), y = y0 + (y1 - y0) * (x + 200) / 1500; marks.push(place([[-20, -40], [10, -40], [40, 40], [10, 40]], x, y, ang)); }
  return { band: band, marks: marks };
}
function fingerprint(cx, cy, r) { var out = []; for (var k = 1; k <= 9; k++) out.push(ring(cx, cy, r * k / 9, 1.35, -0.3 + k * 0.05, Math.PI * 2 - 0.6 + k * 0.03)); return out; }
function chalkOutline(cx, cy, s) {   // a body's chalk outline on the ground
  return [[cx - 0.2 * s, cy - 1.0 * s], [cx + 0.2 * s, cy - 1.0 * s], [cx + 0.25 * s, cy - 0.7 * s], [cx + 0.75 * s, cy - 0.9 * s], [cx + 0.8 * s, cy - 0.75 * s], [cx + 0.3 * s, cy - 0.45 * s], [cx + 0.35 * s, cy + 0.2 * s], [cx + 0.7 * s, cy + 1.0 * s], [cx + 0.5 * s, cy + 1.05 * s], [cx + 0.05 * s, cy + 0.35 * s], [cx - 0.35 * s, cy + 1.0 * s], [cx - 0.55 * s, cy + 0.95 * s], [cx - 0.3 * s, cy + 0.2 * s], [cx - 0.3 * s, cy - 0.4 * s], [cx - 0.85 * s, cy - 0.2 * s], [cx - 0.9 * s, cy - 0.35 * s], [cx - 0.25 * s, cy - 0.7 * s], [cx - 0.2 * s, cy - 1.0 * s]];
}
function marker(x, y, s) { return place([[-0.5 * s, 0], [0.5 * s, 0], [0.3 * s, -0.8 * s], [-0.3 * s, -0.8 * s]], x, y, 0); }
var CRI_RARE = {
  title: function (fr, f, u) {   // a fingerprint on a dark floor, a magnifying glass sweeping over it
    var mx = C + 260 * Math.sin(f * 0.12), my = C + 80 * Math.cos(f * 0.1);
    lines(fr.main, fingerprint(C, C, 300), [0.4, 0.42, 0.48], 7, 100);
    polys(fr.main, [circle(mx, my, 170, 1, 40)], [0.9, 0.92, 1], 12); lines(fr.main, [ring(mx, my, 170, 1)], [0.7, 0.55, 0.3], 22, 100);
    lines(fr.main, [[[mx + 120, my + 120], [mx + 300, my + 300]]], CRI.ink, 40, 100);
    polys(fr.main, [full()], CRI.night, 100);
  },
  wipe: function (fr, v) { iris(fr, v < 0.5 ? 900 * (1 - ease(v * 2)) + 30 : 30 + 900 * ease(v * 2 - 1)); },
  stage: function (fr, f, at, o) {
    lines(fr.main, fingerprint(C, C, 520), [0.25, 0.27, 0.32], 9, o);
    cone(fr.glow, C, 1.5708, 1300, 40, 380, [1, 0.95, 0.8], o * 0.4);
    polys(fr.main, [full()], CRI.night, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 5) polys(fr.top, [full()], CRI.white, 40 - at * 9); }
};
var CRI_EPIC = {
  title: function (fr, f, u) {   // the investigation board: photos pinned, red strings joining them
    seed(1720); var photos = [], pins = [], strings = [];
    for (var i = 0; i < 7; i++) { var x = between(120, 960), y = between(180, 900), r = between(-0.2, 0.2); photos.push({ p: place([[-90, -70], [90, -70], [90, 70], [-90, 70]], x, y, r), x: x, y: y }); pins.push(circle(x, y - 60, 10, 1, 10)); }
    for (var k = 0; k < 6; k++) strings.push(partOf([[[photos[k].x, photos[k].y - 60], [photos[k + 1].x, photos[k + 1].y - 60]]], ease((f - k * 2) / 4))[0] || [[0, 0], [0, 0]]);
    lines(fr.top, strings, CRI.red, 5, 100);
    for (var j = 0; j < photos.length; j++) { polys(fr.main, [photos[j].p], CRI.white, 100); }
    polys(fr.top, pins, CRI.red, 100);
    polys(fr.main, [full()], CRI.cork, 100);
  },
  wipe: function (fr, v) { lines(fr.top, [[[-60, -60 + v * 600], [1140, 1140 - v * 600]], [[-60, 1140 - v * 400], [1140, v * 400]]], CRI.red, 40 * (1 - Math.abs(v * 2 - 1)) + 4, 100); },
  stage: function (fr, f, at, o) {   // the board round the card, every string now leading to it
    seed(1730); var photos = [], strings = [], pins = [];
    for (var i = 0; i < 10; i++) { var a = i / 10 * Math.PI * 2 + 0.3, x = C + Math.cos(a) * 430, y = C + Math.sin(a) * 430, r = between(-0.2, 0.2); photos.push(place([[-80, -62], [80, -62], [80, 62], [-80, 62]], x, y, r)); pins.push(circle(x, y - 54, 9, 1, 10)); strings.push(partOf([[[x, y - 54], [C, C]]], ease((f - CARD_AT - i) / 5))[0] || [[C, C], [C, C]]); }
    lines(fr.main, strings, CRI.red, 5, o); polys(fr.main, pins, CRI.red, o); polys(fr.main, photos, CRI.white, o);
    polys(fr.main, [full()], CRI.cork, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 6) lines(fr.top, [ring(C, C, 240 + at * 20, 1.3)], CRI.red, 10, fade(at, 3, 6) * 100); bigGlint(fr, at, CRI.tape); }
};
var CRI_LEGENDARY = {
  title: function (fr, f, u) {   // the crime scene: a chalk outline on wet asphalt, police lights, the tape
    var tb = tapeBand(260, 160, f * 8); polys(fr.top, tb.marks, CRI.ink, 100); polys(fr.top, [tb.band], CRI.tape, 100);
    lines(fr.main, [chalkOutline(C, 700, 260)], CRI.chalk, 9, 100);
    polys(fr.haze, [circle(f % 8 < 4 ? 120 : 960, 300, 520, 1, 40)], (f % 8 < 4) ? CRI.red : CRI.blue, 100);
    polys(fr.main, [full()], CRI.asphalt, 100);
  },
  wipe: function (fr, v) { var tb = tapeBand(-200 + v * 1500, -400 + v * 1500, 0); polys(fr.top, tb.marks, CRI.ink, 100); polys(fr.top, [tb.band], CRI.tape, 100); var t2 = tapeBand(1300 - v * 1500, 1100 - v * 1500, 40); polys(fr.top, t2.marks, CRI.ink, 100); polys(fr.top, [t2.band], CRI.tape, 100); },
  stage: function (fr, f, at, o) {   // the tape crossing the screen, numbered markers, camera flashes, the lights
    var t1 = tapeBand(220, 120, f * 6), t2 = tapeBand(980, 860, -f * 6);
    polys(fr.top, t1.marks.concat(t2.marks), CRI.ink, o); polys(fr.top, [t1.band, t2.band], CRI.tape, o);
    var ms = [[C - 380, 760], [C + 360, 700], [C - 300, 420], [C + 400, 380]]; var mk = []; for (var i = 0; i < ms.length; i++) mk.push(marker(ms[i][0], ms[i][1], 70));
    polys(fr.main, mk, CRI.tape, o); lines(fr.main, mk, CRI.ink, 4, o, true);
    if (at >= 0) { var flashes = [[C - 420, C - 250, 0], [C + 430, C + 160, 5], [C - 200, C + 380, 9], [C + 300, C - 330, 13]]; for (var j = 0; j < flashes.length; j++) { var t = at - flashes[j][2]; if (t >= 0 && t < 4) { polys(fr.glow, [circle(flashes[j][0], flashes[j][1], 160 - t * 30, 1, 24)], CRI.white, 100 - t * 25); polys(fr.top, glintPolys([[flashes[j][0], flashes[j][1], 60 - t * 12]]), CRI.white); } } }
    lines(fr.main, [chalkOutline(C, C + 40, 330)], CRI.chalk, 10, o * 0.7);
    polys(fr.haze, [circle(f % 8 < 4 ? 120 : 960, C, 560, 1.2, 40)], (f % 8 < 4) ? CRI.red : CRI.blue, o);
    polys(fr.main, [full()], CRI.asphalt, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 4) polys(fr.top, [full()], CRI.white, 60 - at * 15); bigGlint(fr, at, CRI.tape); }
};
var GENRE_CRIME = {
  rarities: { rare: CRI_RARE, epic: CRI_EPIC, legendary: CRI_LEGENDARY },
  opening: function (comp) {   // police tape wraps round the pack; an evidence photo's flash — it is taken away
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 4 && f < 40) { for (var k = 0; k < 3; k++) { var t = clamp01((f - 4 - k * 5) / 8); if (t <= 0) continue; var y = cy - 160 + k * 160, w = t * 1500, tb = tapeBand(y + 60, y - 60, f * 6); polys(fr.top, tb.marks, CRI.ink, 100 * fade(f, 34, 40)); polys(fr.top, [tb.band], CRI.tape, 100 * fade(f, 34, 40)); } }
      if (f >= 28 && f < 32) polys(fr.top, [circle(cx, cy, 700, 1, 40)], CRI.white, 100 - (f - 28) * 25);
      if (f >= 6 && f < 28 && f % 8 < 4) polys(fr.glow, [circle(cx - 420, cy - 300, 120, 1, 20)], CRI.red, 100);
      if (f >= 6 && f < 28 && f % 8 >= 4) polys(fr.glow, [circle(cx + 420, cy - 300, 120, 1, 20)], CRI.blue, 100);
    }
  }
};

// ===== Idylle — romance: a love letter, the ball, love at first sight =====================================
var ROM = { blush: [1, 0.85, 0.88], rose: [0.91, 0.26, 0.42], rose_l: [1, 0.55, 0.65], wine: [0.48, 0.06, 0.2], gold: [0.85, 0.64, 0.25], gold_l: [1, 0.88, 0.6], dusk: [0.36, 0.12, 0.3], sun: [1, 0.72, 0.5], white: [1, 1, 1] };
function hearts(f, n, base, rise, size) {   // little hearts floating up and swaying
  seed(base); var out = [];
  for (var i = 0; i < n; i++) { var x = between(-40, 1120) + Math.sin(f * 0.12 + i) * 30, y = 1140 - ((f * between(4, 9) * (rise || 1) + between(0, 1200)) % 1260); out.push(heart(x, y, between(14, 30) * (size || 1), Math.sin(f * 0.1 + i) * 0.3)); }
  return out;
}
function envelope(cx, cy, s, open) {   // a letter: its body, its flap (open from 0 to 1), a heart seal
  return { body: [[cx - s, cy - s * 0.6], [cx + s, cy - s * 0.6], [cx + s, cy + s * 0.6], [cx - s, cy + s * 0.6]], flap: [[cx - s, cy - s * 0.6], [cx + s, cy - s * 0.6], [cx, cy - s * 0.6 + s * 0.7 * (1 - 2 * open)]], seal: heart(cx, cy - s * 0.05 - s * 0.6 * open, s * 0.22, 0) };
}
function dancers(cx, cy, s, turn) {   // a couple waltzing, in silhouette: two figures close, a gown flaring
  var sw = Math.sin(turn) * 0.3 * s;
  return [place([[-0.15 * s, -1.6 * s], [0.05 * s, -1.6 * s], [0.12 * s, -0.7 * s], [0.75 * s + sw, 0.4 * s], [-0.65 * s + sw, 0.4 * s], [-0.2 * s, -0.7 * s]], cx - 0.2 * s, cy, 0), place(circle(0, -1.8 * s, 0.17 * s, 1.1, 12), cx - 0.25 * s, cy, 0),
          place([[0.1 * s, -1.75 * s], [0.4 * s, -1.75 * s], [0.45 * s, 0.4 * s], [0.05 * s, 0.4 * s]], cx + 0.15 * s, cy, 0), place(circle(0, -1.95 * s, 0.17 * s, 1.1, 12), cx + 0.4 * s, cy, 0)];
}
function arrow(x0, y0, x1, y1, u) {   // Cupid's arrow flying from (x0, y0) to (x1, y1): shaft, head, fletching
  var x = x0 + (x1 - x0) * u, y = y0 + (y1 - y0) * u, a = Math.atan2(y1 - y0, x1 - x0);
  return { shaft: [[x - Math.cos(a) * 320, y - Math.sin(a) * 320], [x, y]], head: place([[0, 0], [-40, -18], [-40, 18]], x, y, a), fletch: [place([[-300, 0], [-340, -26], [-320, 0]], x, y, a), place([[-300, 0], [-340, 26], [-320, 0]], x, y, a)] };
}
var ROM_RARE = {
  title: function (fr, f, u) {   // a love letter floating, opening, hearts rising out of it
    var env = envelope(C, 560 + Math.sin(f * 0.2) * 20, 220, ease((f - 6) / 10));
    polys(fr.top, hearts(f, 14, 1800, 1.4, 0.9), ROM.rose, 100);
    polys(fr.main, [env.seal], ROM.rose, 100); polys(fr.main, [env.flap], [0.98, 0.9, 0.86], 100); lines(fr.main, [env.flap, env.body], ROM.wine, 4, 100, true); polys(fr.main, [env.body], [1, 0.96, 0.92], 100);
    polys(fr.main, [full()], ROM.blush, 100);
  },
  wipe: function (fr, v) { polys(fr.top, [heart(C, C + 80, 30 + ease(v) * 1400, 0)], ROM.rose_l, 100 * (1 - Math.abs(v * 2 - 1)) + 10); },
  stage: function (fr, f, at, o) {
    polys(fr.main, hearts(f, 20, 1810, 1, 1), ROM.rose_l, o * 0.7);
    polys(fr.haze, [circle(C, C, 420, 1, 40)], ROM.white, o * 0.7);
    polys(fr.main, [full()], ROM.blush, o);
  },
  over: function (fr, f, at) { if (at >= 0) polys(fr.top, hearts(at, 8, 1820, 2, 0.8), ROM.rose, fade(at, 20, 34) * 100); }
};
var ROM_EPIC = {
  title: function (fr, f, u) {   // the ball: a chandelier, a couple waltzing
    polys(fr.main, dancers(C, 900, 210, f * 0.3), ROM.wine, 100);
    seed(1830); var lamps = []; for (var i = 0; i < 16; i++) { var a = i / 16 * Math.PI; lamps.push([C + Math.cos(a) * 200, 180 + Math.sin(a) * 70, 8]); }
    polys(fr.glow, glintPolys(twinkle(lamps, f, 1, 14)), ROM.gold_l); lines(fr.main, [ring(C, 180, 200, 0.35, 0, Math.PI), [[C, -60], [C, 120]]], ROM.gold, 6, 100);
    polys(fr.glow, [circle(C, 800, 380, 0.6, 40)], ROM.gold_l, 50);
    polys(fr.main, [full()], ROM.dusk, 100);
  },
  wipe: function (fr, v) { seed(1835); var pts = []; for (var i = 0; i < 90; i++) { var a = between(0, Math.PI * 2), d = ease(v) * 900 * between(0.4, 1.2); pts.push(place([[0, 0], [16, -10], [30, 0], [16, 10]], C + Math.cos(a) * d, C + Math.sin(a) * d, a + v * 6)); } polys(fr.top, pts, ROM.rose, 100); },
  stage: function (fr, f, at, o) {   // petals whirling round the card, a ring of roses, sparkles
    seed(1840); var petals = []; for (var i = 0; i < 50; i++) { var a = between(0, Math.PI * 2) + f * 0.04 * between(0.6, 1.4), d = between(280, 560); petals.push(place([[0, 0], [16, -10], [32, 0], [16, 10]], C + Math.cos(a) * d, C + Math.sin(a) * d * 0.8, a * 2 + f * 0.1)); }
    polys(fr.main, petals, ROM.rose, o);
    var roses = []; for (var r = 0; r < 14; r++) { var a2 = r / 14 * Math.PI * 2, x = C + Math.cos(a2) * 420, y = C + Math.sin(a2) * 480; roses.push(circle(x, y, 30, 1, 16)); roses.push(circle(x, y, 16, 1, 12)); }
    polys(fr.main, roses, ROM.wine, o);
    polys(fr.haze, [circle(C, C, 420, 1, 40)], ROM.gold_l, o * 0.6);
    polys(fr.main, [full()], ROM.dusk, o);
  },
  over: function (fr, f, at) { if (at >= 2) { seed(1850); var pts = []; for (var i = 0; i < 14; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 160, 222) + between(10, 100); pts.push([C + Math.cos(a) * r, C + Math.sin(a) * r]); } polys(fr.top, glintPolys(twinkle(pts, f, 2, 20)), ROM.gold_l); } bigGlint(fr, at, ROM.gold_l); }
};
var ROM_LEGENDARY = {
  title: function (fr, f, u) {   // love at first sight: a couple on a bridge at dusk, fireworks bursting into hearts
    for (var k = 0; k < 3; k++) { var t = f - k * 6; if (t < 0) continue; var x = 260 + k * 280, y = 300 - k * 30, r = Math.min(1, t / 6) * 160; var sp = []; for (var j = 0; j < 14; j++) { var a = j / 14 * Math.PI * 2; sp.push(heart(x + Math.cos(a) * r, y + Math.sin(a) * r, 12, 0)); } polys(fr.glow, sp, k % 2 ? ROM.gold_l : ROM.rose_l, 100 * fade(t, 10, 16)); polys(fr.main, sp, k % 2 ? ROM.gold_l : ROM.rose_l, 100 * fade(t, 10, 16)); }
    polys(fr.main, dancers(C + 120, 790, 120, 0).concat([[[-60, 800], [1140, 800], [1140, 1140], [-60, 1140]]]), [0.18, 0.04, 0.12], 100);
    lines(fr.main, [ring(C, 1100, 520, 0.6, Math.PI, Math.PI * 2)], [0.18, 0.04, 0.12], 30, 100);
    polys(fr.glow, [circle(C - 300, 780, 60, 1, 20)], ROM.gold_l, 100); lines(fr.main, [[[C - 300, 800], [C - 300, 680]]], [0.18, 0.04, 0.12], 10, 100);
    polys(fr.main, [[[-60, 500], [1140, 500], [1140, 820], [-60, 820]]], ROM.sun, 100);
    polys(fr.main, [full()], ROM.dusk, 100);
  },
  wipe: function (fr, v) { var s = ease(v); polys(fr.top, [heart(C - 300 * (1 - s), C, 900 * s + 40, -0.3 * (1 - s)), heart(C + 300 * (1 - s), C, 900 * s + 40, 0.3 * (1 - s))], ROM.rose, 100); },
  stage: function (fr, f, at, o) {   // a golden heart behind the card, fireworks of hearts, a storm of petals
    var g = ease((f - CARD_AT) / 6);
    for (var k = 0; k < 6; k++) { var t = f - CARD_AT - k * 6; if (t < 0) continue; seed(1860 + k); var x = between(120, 960), y = between(160, 920), r = Math.min(1, t / 6) * 180; var sp = []; for (var j = 0; j < 16; j++) { var a = j / 16 * Math.PI * 2; sp.push(heart(x + Math.cos(a) * r, y + Math.sin(a) * r + t * 1.5, 13, 0)); } polys(fr.glow, sp, k % 2 ? ROM.gold_l : ROM.rose_l, o * fade(t, 10, 18)); polys(fr.main, sp, k % 2 ? ROM.gold_l : ROM.white, o * fade(t, 10, 18)); }
    seed(1870); var petals = []; for (var i = 0; i < 70; i++) { var a2 = between(0, Math.PI * 2) + f * 0.05, d = between(250, 700); petals.push(place([[0, 0], [16, -10], [32, 0], [16, 10]], C + Math.cos(a2) * d, C + Math.sin(a2) * d * 0.8, a2 * 2 + f * 0.15)); }
    polys(fr.main, petals, ROM.rose, o);
    polys(fr.glow, [heart(C, C + 60, 520 * g + 40, 0)], ROM.gold, o); polys(fr.main, [heart(C, C + 60, 470 * g + 30, 0)], ROM.gold_l, o * 0.5);
    polys(fr.main, [full()], ROM.dusk, o);
  },
  over: function (fr, f, at) {   // Cupid's arrow going through the card, a burst of hearts
    if (at >= 0 && at < 14) { var ar = arrow(-200, C + 260, 1300, C - 260, ease(at / 6)); lines(fr.top, [ar.shaft], ROM.gold, 9, fade(at, 9, 14) * 100); polys(fr.top, [ar.head], ROM.gold_l, fade(at, 9, 14) * 100); polys(fr.top, ar.fletch, ROM.rose, fade(at, 9, 14) * 100); }
    if (at >= 3) polys(fr.top, hearts(at - 3, 16, 1880, 2.2, 1.1), ROM.rose, fade(at, 24, 40) * 100);
    bigGlint(fr, at, ROM.gold_l);
  }
};
var GENRE_ROMANCE = {
  rarities: { rare: ROM_RARE, epic: ROM_EPIC, legendary: ROM_LEGENDARY },
  opening: function (comp) {   // hearts whirl round the pack, a great heart closes on it and bursts into petals
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 30) { var hs = []; for (var i = 0; i < 12; i++) { var a = i / 12 * Math.PI * 2 + f * 0.15, d = 420 - f * 9; hs.push(heart(cx + Math.cos(a) * d, cy + Math.sin(a) * d * 0.8, 26, a)); } polys(fr.top, hs, ROM.rose, 100); }
      if (f >= 18 && f < 32) polys(fr.top, [heart(cx, cy + 40, 700 - ease((f - 18) / 10) * 560, 0)], ROM.rose_l, 70);
      if (f >= 30) { seed(1890); var petals = []; for (var j = 0; j < 60; j++) { var a2 = between(0, Math.PI * 2), d2 = 40 + (f - 30) * between(10, 26); petals.push(place([[0, 0], [16, -10], [32, 0], [16, 10]], cx + Math.cos(a2) * d2, cy + Math.sin(a2) * d2 + (f - 30) * (f - 30) * 0.3, a2 + f * 0.2)); } polys(fr.top, petals, ROM.rose, fade(f, 52, 63) * 100); }
      if (f >= 30 && f < 33) polys(fr.top, [heart(cx, cy + 40, 260, 0)], ROM.white, 100 - (f - 30) * 33);
    }
  }
};

// ===== Brume — mystery: a lantern in the fog, the keyhole, the riddle =====================================
var MYS = { fog: [0.66, 0.76, 0.74], night: [0.04, 0.1, 0.12], teal: [0.09, 0.21, 0.23], brass: [0.78, 0.63, 0.29], brass_l: [1, 0.86, 0.5], lamp: [1, 0.85, 0.5], ink: [0.02, 0.05, 0.06] };
function fogBands(L, f, o, base) {   // drifting bands of fog
  seed(base); var out = []; for (var i = 0; i < 7; i++) { var y = between(100, 1000), x = -400 + ((f * between(3, 7) + between(0, 1600)) % 1900), w = between(400, 800); out.push(circle(x, y, w, 0.12, 30)); } polys(L, out, MYS.fog, o);
}
function keyhole(cx, cy, s) { return [circle(cx, cy - 0.35 * s, 0.38 * s, 1, 30), [[cx - 0.2 * s, cy - 0.2 * s], [cx + 0.2 * s, cy - 0.2 * s], [cx + 0.34 * s, cy + 0.75 * s], [cx - 0.34 * s, cy + 0.75 * s]]]; }
function gear(cx, cy, r, teeth, turn) {   // a cog: its toothed rim, a hub cut out
  var v = []; for (var i = 0; i < teeth * 4; i++) { var a = turn + i / (teeth * 4) * Math.PI * 2, rr = (i % 4 < 2) ? r : r * 0.84; v.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]); }
  return [v, circle(cx, cy, r * 0.32, 1, 20)];
}
function question(cx, cy, s, turn) {   // a question mark: its hook over the top (screen y down), its stem, its dot
  var hook = []; for (var i = 0; i <= 18; i++) { var a = Math.PI + i / 18 * Math.PI * 1.45; hook.push([Math.cos(a) * 0.36 * s, -0.55 * s + Math.sin(a) * 0.36 * s]); } hook.push([0, -0.1 * s]); hook.push([0, 0.1 * s]);
  return { hook: [place(hook, cx, cy, turn)], dot: place(circle(0, 0.36 * s, 0.09 * s, 1, 10), cx, cy, turn) };
}
var MYS_RARE = {
  title: function (fr, f, u) {   // a lantern swaying in the fog
    var sw = Math.sin(f * 0.18) * 0.5, lx = C + 260 + Math.sin(sw) * 300, ly = 60 + Math.cos(sw) * 300;
    lines(fr.main, [[[C, -60], [lx, ly]]], MYS.ink, 4, 100);
    polys(fr.glow, [circle(lx, ly + 40, 160, 1, 30)], MYS.lamp, 90); polys(fr.main, [[[lx - 34, ly], [lx + 34, ly], [lx + 28, ly + 90], [lx - 28, ly + 90]]], MYS.lamp, 100); lines(fr.main, [[[lx - 34, ly], [lx + 34, ly], [lx + 28, ly + 90], [lx - 28, ly + 90], [lx - 34, ly]]], MYS.ink, 6, 100);
    fogBands(fr.main, f, 30, 1900); fogBands(fr.haze, f, 90, 1901);
    polys(fr.main, [full()], MYS.night, 100);
  },
  wipe: function (fr, v) { polys(fr.top, [full()], MYS.fog, 100 * (1 - Math.abs(v * 2 - 1))); },
  stage: function (fr, f, at, o) {   // the lantern hanging over the card, its light in the fog, the fog drifting past
    var lx = C + Math.sin(f * 0.15) * 40, ly = 250;
    lines(fr.main, [[[C, -60], [lx, ly]]], MYS.ink, 4, o);
    polys(fr.glow, [circle(lx, ly + 40, 220, 1, 30)], MYS.lamp, o); polys(fr.main, [[[lx - 30, ly], [lx + 30, ly], [lx + 24, ly + 80], [lx - 24, ly + 80]]], MYS.lamp, o); lines(fr.main, [[[lx - 30, ly], [lx + 30, ly], [lx + 24, ly + 80], [lx - 24, ly + 80], [lx - 30, ly]]], MYS.ink, 6, o);
    cone(fr.haze, lx, 1.5708, 1200, 40, 420, MYS.lamp, o * 0.5);
    fogBands(fr.main, f, o * 0.35, 1910); fogBands(fr.haze, f + 40, o, 1911);
    polys(fr.main, [full()], MYS.teal, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 6) lines(fr.top, [ring(C, C, 240 + at * 16, 1.3)], MYS.brass_l, 6, fade(at, 3, 6) * 100); }
};
var MYS_EPIC = {
  title: function (fr, f, u) {   // an ornate keyhole, a light moving behind it
    polys(fr.main, keyhole(C, 600, 420), [1, 0.9, 0.6], 100);
    polys(fr.glow, [circle(C + Math.sin(f * 0.2) * 60, 560, 160, 1, 30)], MYS.lamp, 100);
    lines(fr.main, [ring(C, 450, 300, 1), ring(C, 450, 330, 1)], MYS.brass, 10, 100);
    polys(fr.main, [full()], MYS.brass, 100);
  },
  wipe: function (fr, v) { var a = ease(v) * Math.PI / 2; polys(fr.top, [place([[-60, -24], [300, -24], [300, -60], [360, -60], [360, 60], [300, 60], [300, 24], [-60, 24]], C, C, a), circle(C - 120 * Math.cos(a), C - 120 * Math.sin(a), 110, 1, 24)], MYS.brass_l, 100 * (1 - Math.abs(v * 2 - 1)) + 10); },
  stage: function (fr, f, at, o) {   // brass gears turning round the card, the lock opening
    var gs = [[C - 360, C - 330, 160, 14, 1], [C + 380, C - 260, 200, 18, -1], [C - 330, C + 330, 190, 16, -1], [C + 360, C + 360, 150, 12, 1]];
    for (var i = 0; i < gs.length; i++) { var g2 = gear(gs[i][0], gs[i][1], gs[i][2], gs[i][3], f * 0.04 * gs[i][4]); polys(fr.main, g2, MYS.brass, o, true); lines(fr.main, [g2[0]], MYS.ink, 4, o, true); }
    fogBands(fr.haze, f, o * 0.6, 1920);
    polys(fr.main, [full()], MYS.teal, o);
  },
  over: function (fr, f, at) { bigGlint(fr, at, MYS.brass_l); }
};
var MYS_LEGENDARY = {
  title: function (fr, f, u) {   // a Victorian street at night: gas lamps, a figure in a cape fleeing, question marks drifting
    seed(1930); for (var i = 0; i < 6; i++) { var q = question(between(80, 1000), 1100 - ((f * between(6, 12) + between(0, 1100)) % 1200), between(60, 110), between(-0.3, 0.3)); lines(fr.main, q.hook, MYS.brass_l, 12, 70); polys(fr.main, [q.dot], MYS.brass_l, 70); }
    var x = 900 - f * 22; polys(fr.main, [place([[0, -150], [30, -150], [40, -100], [120, 60], [-80, 60], [-10, -100]], x, 820, 0), place(circle(0, -175, 26, 1, 12), x + 15, 820, 0), place([[-30, -200], [60, -200], [50, -210], [42, -250], [-12, -250], [-20, -210]], x, 820, 0)], MYS.ink, 100);
    for (var k = 0; k < 3; k++) { var lx = 160 + k * 380; lines(fr.main, [[[lx, 1140], [lx, 420]]], MYS.ink, 12, 100); polys(fr.glow, [circle(lx, 400, 120, 1, 24)], MYS.lamp, 90); polys(fr.main, [[[lx - 28, 380], [lx + 28, 380], [lx + 22, 430], [lx - 22, 430]]], MYS.lamp, 100); }
    fogBands(fr.haze, f, 90, 1931);
    polys(fr.main, [full()], MYS.night, 100);
  },
  wipe: function (fr, v) { iris(fr, v < 0.5 ? 900 * (1 - ease(v * 2)) + 30 : 30 + 900 * ease(v * 2 - 1)); },
  stage: function (fr, f, at, o) {   // the riddle solved: great gears, a magnifier sweeping, question marks whirling
    var gs = [[C - 420, C - 380, 230, 18, 1], [C + 440, C - 300, 260, 22, -1], [C - 400, C + 380, 250, 20, -1], [C + 420, C + 420, 210, 16, 1], [C, C - 560, 180, 14, 1]];
    for (var i = 0; i < gs.length; i++) { var g2 = gear(gs[i][0], gs[i][1], gs[i][2], gs[i][3], f * 0.05 * gs[i][4]); polys(fr.main, g2, MYS.brass, o, true); lines(fr.main, [g2[0]], MYS.ink, 4, o, true); }
    seed(1940); for (var j = 0; j < 10; j++) { var a = between(0, Math.PI * 2) + f * 0.03, d = between(300, 480), q = question(C + Math.cos(a) * d, C + Math.sin(a) * d, between(50, 80), a); lines(fr.top, q.hook, MYS.brass_l, 9, o * 0.85); polys(fr.top, [q.dot], MYS.brass_l, o * 0.85); }
    var mx = C + 300 * Math.cos(f * 0.08), my = C + 200 * Math.sin(f * 0.11); lines(fr.top, [ring(mx, my, 120, 1)], MYS.brass, 18, o); lines(fr.top, [[[mx + 85, my + 85], [mx + 210, my + 210]]], MYS.ink, 26, o); polys(fr.top, [circle(mx, my, 110, 1, 30)], [0.9, 1, 1], o * 0.12);
    fogBands(fr.haze, f, o * 0.7, 1941);
    polys(fr.main, [full()], MYS.teal, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 8) lines(fr.top, [ring(C, C, 260, 1.3)], MYS.brass_l, 14, fade(at, 4, 8) * 100); bigGlint(fr, at, MYS.brass_l); }
};
var GENRE_MYSTERY = {
  rarities: { rare: MYS_RARE, epic: MYS_EPIC, legendary: MYS_LEGENDARY },
  opening: function (comp) {   // the pack seen through a keyhole closing on it; the fog takes it
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f >= 6 && f < 36) { var s = 2400 - ease((f - 6) / 22) * 2200; polys(fr.top, [[[-60, -60], [1212, -60], [1212, 1140], [-60, 1140]]].concat(keyhole(cx, cy + 0.1 * s, s)), MYS.ink, 100 * fade(f, 32, 36), true); }
      if (f >= 28) fogBands(fr.top, f, 100 * fade(f, 52, 63), 1950);
    }
  }
};

// ===== Concert — music: a note, the record, the stadium ===================================================
var MUS = { black: [0.08, 0.04, 0.12], magenta: [1, 0.18, 0.66], cyan: [0.16, 0.89, 1], purple: [0.48, 0.17, 1], gold: [1, 0.8, 0.3], white: [1, 1, 1] };
function note(x, y, s, two) {   // a note (or two beamed): heads, stems, a flag
  var out = { heads: [place(circle(0, 0, 0.3 * s, 0.7, 14), x, y, -0.4)], stems: [[[x + 0.27 * s, y - 0.05 * s], [x + 0.27 * s, y - 1.3 * s]]] };
  if (two) { out.heads.push(place(circle(0, 0, 0.3 * s, 0.7, 14), x + s, y - 0.2 * s, -0.4)); out.stems.push([[x + 1.27 * s, y - 0.25 * s], [x + 1.27 * s, y - 1.5 * s]]); out.beam = [[x + 0.27 * s, y - 1.3 * s], [x + 1.27 * s, y - 1.5 * s], [x + 1.27 * s, y - 1.3 * s], [x + 0.27 * s, y - 1.1 * s]]; }
  else out.beam = [[x + 0.27 * s, y - 1.3 * s], [x + 0.65 * s, y - 0.9 * s], [x + 0.6 * s, y - 0.8 * s], [x + 0.27 * s, y - 1.05 * s]];
  return out;
}
function drawNote(L, n, color, o) { polys(L, n.heads.concat([n.beam]), color, o); lines(L, n.stems, color, 0.1 * 60, o); }
function vinyl(cx, cy, r, turn) {   // a record: its disc, grooves, label, a glint turning
  return { disc: circle(cx, cy, r, 1, 60), grooves: [ring(cx, cy, r * 0.9, 1), ring(cx, cy, r * 0.78, 1), ring(cx, cy, r * 0.66, 1), ring(cx, cy, r * 0.54, 1)], label: circle(cx, cy, r * 0.32, 1, 30), hole: circle(cx, cy, r * 0.04, 1, 10), shine: [[cx, cy], [cx + Math.cos(turn) * r, cy + Math.sin(turn) * r], [cx + Math.cos(turn + 0.3) * r, cy + Math.sin(turn + 0.3) * r]] };
}
function eqBars(cx, cy, r, f, n) {   // an equaliser's bars round a circle, pulsing
  var out = []; for (var i = 0; i < n; i++) { var a = i / n * Math.PI * 2, h = 40 + 120 * Math.abs(Math.sin(f * 0.5 + i * 0.7) * Math.sin(f * 0.23 + i * 0.3)), w = 0.035; out.push([[cx + Math.cos(a - w) * r, cy + Math.sin(a - w) * r], [cx + Math.cos(a - w) * (r + h), cy + Math.sin(a - w) * (r + h)], [cx + Math.cos(a + w) * (r + h), cy + Math.sin(a + w) * (r + h)], [cx + Math.cos(a + w) * r, cy + Math.sin(a + w) * r]]); } return out;
}
function crowd(f, y0) {   // heads and raised hands at the foot of the screen
  var out = []; seed(2050);
  for (var i = 0; i < 26; i++) { var x = -40 + i * 46 + between(-8, 8), y = y0 + between(-12, 12), up = Math.sin(f * 0.4 + i) * 20; out.push(circle(x, y, 24, 1.1, 12)); out.push([[x - 30, 1140], [x - 26, y + 20], [x + 26, y + 20], [x + 30, 1140]]); if (i % 2) out.push([[x + 10, y + 10], [x + 24, y - 90 - up], [x + 34, y - 88 - up], [x + 22, y + 10]]); }
  return out;
}
var MUS_RARE = {
  title: function (fr, f, u) {   // notes floating along a staff that waves
    var staff = []; for (var k = 0; k < 5; k++) { var pts = []; for (var x = -60; x <= 1140; x += 30) pts.push([x, 420 + k * 40 + Math.sin(x * 0.006 + f * 0.2) * 60]); staff.push(pts); }
    lines(fr.main, staff, MUS.white, 3, 70);
    seed(2000); for (var i = 0; i < 6; i++) { var x2 = -100 + ((f * 18 + i * 220) % 1300), y2 = 520 + Math.sin(x2 * 0.006 + f * 0.2) * 60 - i % 3 * 40; drawNote(fr.main, note(x2, y2, 70, i % 2), [MUS.magenta, MUS.cyan, MUS.gold][i % 3], 100); }
    polys(fr.main, [full()], MUS.black, 100);
  },
  wipe: function (fr, v) { lines(fr.top, [ring(C, C, 40 + ease(v) * 900, 1), ring(C, C, 20 + ease(v) * 700, 1)], MUS.cyan, 30, 100 * (1 - v) + 20); },
  stage: function (fr, f, at, o) {
    seed(2010); for (var i = 0; i < 10; i++) { var a = between(0, Math.PI * 2) + f * 0.02, d = between(300, 500); drawNote(fr.main, note(C + Math.cos(a) * d, C + Math.sin(a) * d, 50, i % 2), [MUS.magenta, MUS.cyan, MUS.gold][i % 3], o * 0.85); }
    polys(fr.haze, [circle(C, C, 400, 1, 40)], MUS.purple, o * 0.6);
    polys(fr.main, [full()], MUS.black, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 8) lines(fr.top, [ring(C, C, 240 + at * 24, 1.3)], MUS.cyan, 8, fade(at, 4, 8) * 100); }
};
var MUS_EPIC = {
  title: function (fr, f, u) {   // a record spinning, its glint turning
    var v = vinyl(C, 560, 400, f * 0.25);
    polys(fr.main, [v.hole], MUS.black, 100); polys(fr.main, [v.label], MUS.magenta, 100); polys(fr.main, [v.shine], MUS.white, 18); lines(fr.main, v.grooves, [0.2, 0.2, 0.24], 3, 100); polys(fr.main, [v.disc], [0.06, 0.06, 0.08], 100);
    lines(fr.main, [[[1000, 140], [900, 360], [760, 420]]], [0.75, 0.75, 0.8], 14, 100);
    polys(fr.main, [full()], MUS.purple, 100);
  },
  wipe: function (fr, v) { lines(fr.top, [ring(C, C, 40 + ease(v) * 900, 1)], MUS.magenta, 60 * (1 - v) + 10, 100); },
  stage: function (fr, f, at, o) {   // an equaliser pulsing round the card, sound rings going out
    polys(fr.main, eqBars(C, C, 330, f, 48), MUS.cyan, o);
    if (at >= 0) for (var q = 0; q < 3; q++) { var t = (at - q * 4); if (t < 0) continue; lines(fr.glow, [ring(C, C, 320 + t * 30, 1.2)], MUS.magenta, 20, fade(t, 6, 14) * o); }
    var v = vinyl(C, C, 330, f * 0.2); lines(fr.main, v.grooves, [0.2, 0.2, 0.26], 3, o); polys(fr.main, [v.disc], [0.06, 0.06, 0.08], o);
    polys(fr.main, [full()], MUS.black, o);
  },
  over: function (fr, f, at) { bigGlint(fr, at, MUS.cyan); }
};
var MUS_LEGENDARY = {
  title: function (fr, f, u) {   // a stadium: the crowd's lights, beams sweeping the smoke
    polys(fr.main, crowd(f, 900), MUS.black, 100);
    seed(2060); var lights = []; for (var i = 0; i < 80; i++) lights.push([between(0, 1080), between(760, 1000), between(2, 4)]); polys(fr.main, glintPolys(twinkle(lights, f, 1, 5)), MUS.gold);
    for (var k = 0; k < 5; k++) cone(fr.glow, 120 + k * 210, 1.5708 + 0.5 * Math.sin(f * 0.12 + k), 1400, 20, 220, [MUS.magenta, MUS.cyan, MUS.purple][k % 3], 60);
    polys(fr.main, [full()], [0.12, 0.06, 0.2], 100);
  },
  wipe: function (fr, v) { polys(fr.top, [full()], MUS.white, 100 * (1 - Math.abs(v * 2 - 1))); },
  stage: function (fr, f, at, o) {   // lasers crossing over the card, fountains of sparks at the sides, the crowd
    polys(fr.top, crowd(f, 840), MUS.black, o);
    var lasers = []; for (var k = 0; k < 8; k++) { var a = -1.5708 + Math.sin(f * 0.1 + k) * 0.9; lasers.push([[k < 4 ? 80 : 1000, 1000], [(k < 4 ? 80 : 1000) + Math.cos(a) * 1600, 1000 + Math.sin(a) * 1600]]); }
    lines(fr.glow, lasers, MUS.cyan, 16, o * 0.8); lines(fr.main, lasers, MUS.white, 3, o);
    if (at >= -4) for (var side = 0; side < 2; side++) { seed(2070 + side + f); var sparks = []; for (var i = 0; i < 30; i++) { var x = (side ? 960 : 120) + between(-40, 40), h = between(100, 700); sparks.push(circle(x + between(-60, 60) * (h / 700), 1000 - h, between(3, 7), 1, 8)); } polys(fr.glow, sparks, MUS.gold, o); polys(fr.main, sparks, MUS.white, o); }
    polys(fr.main, eqBars(C, C, 360, f, 40), MUS.magenta, o * 0.8);
    polys(fr.haze, [circle(C, C, 500, 1, 40)], MUS.purple, o);
    polys(fr.main, [full()], [0.1, 0.05, 0.16], o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 8) { polys(fr.top, slash(-60, 300, 1140, 760, 24, ease(at / 3), -0.3), MUS.magenta, fade(at, 4, 8) * 90); polys(fr.top, slash(1140, 300, -60, 760, 24, ease((at - 1) / 3), 0.3), MUS.cyan, fade(at, 5, 9) * 90); } sparksOut(fr.main, fr.glow, at - 2, 30, MUS.gold, 2080, 26); bigGlint(fr, at, MUS.cyan); }
};
var GENRE_MUSIC = {
  rarities: { rare: MUS_RARE, epic: MUS_EPIC, legendary: MUS_LEGENDARY },
  opening: function (comp) {   // a record spins under the pack, the needle drops — the pack bursts in sound waves
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 30) { var v = vinyl(cx, cy, 380, f * 0.3); polys(fr.main, [v.shine], MUS.white, 15); lines(fr.main, v.grooves, [0.25, 0.25, 0.3], 3, 100); polys(fr.main, [v.disc], [0.06, 0.06, 0.08], 100 * fade(f, 26, 30)); var arm = f < 16 ? 0.4 * (1 - ease(f / 14)) : 0; lines(fr.top, [place([[0, 0], [-160, 260], [-260, 300]], cx + 420, cy - 360, arm)], [0.75, 0.75, 0.8], 14, 100 * fade(f, 26, 30)); }
      if (f >= 24) for (var q = 0; q < 5; q++) { var t = f - 24 - q * 4; if (t < 0) continue; lines(fr.glow, [ring(cx, cy, 120 + t * 40, 1)], q % 2 ? MUS.cyan : MUS.magenta, 22, fade(t, 10, 20) * 100); lines(fr.top, [ring(cx, cy, 120 + t * 40, 1)], MUS.white, 4, fade(t, 10, 20) * 100); }
      if (f >= 26) { seed(2090); for (var i = 0; i < 10; i++) { var a = between(0, Math.PI * 2), d = 60 + (f - 26) * between(10, 20); drawNote(fr.top, note(cx + Math.cos(a) * d, cy + Math.sin(a) * d, 46, i % 2), [MUS.magenta, MUS.cyan, MUS.gold][i % 3], fade(f, 52, 63) * 100); } }
    }
  }
};

// ===== Chronique — history: a seal, a mosaic, the triumph ==================================================
function glowOn(fr, list, color, o) { polys(fr.glow, list, color, o); polys(fr.main, list, color, o * 0.35); }   // a glow seen over the main layer's own background
function beamOn(fr, x, ang, len, w0, w1, color, o) { beam(fr.glow, x, ang, len, w0, w1, color, o); beam(fr.main, x, ang, len, w0 * 0.7, w1 * 0.7, color, o * 0.3); }
function coneOn(fr, x, ang, len, w0, w1, color, o) { cone(fr.haze, x, ang, len, w0, w1, color, o); cone(fr.main, x, ang, len, w0 * 0.7, w1 * 0.7, color, o * 0.3); }
var HIS = { parch: [0.92, 0.85, 0.68], parch_d: [0.72, 0.6, 0.4], marble: [0.9, 0.87, 0.8], stone: [0.55, 0.52, 0.46], bronze: [0.66, 0.45, 0.17], gold: [1, 0.81, 0.35], wax: [0.62, 0.1, 0.12], crimson: [0.56, 0.11, 0.13], ink: [0.17, 0.14, 0.1], sky: [0.95, 0.75, 0.45] };
function laurel(cx, cy, rx, ry, upto, leaf) {   // a laurel wreath: two branches of leaves meeting at the top
  var out = [];
  for (var side = -1; side <= 1; side += 2) for (var i = 0; i < 14 * clamp01(upto); i++) { var t = i / 14, a = Math.PI / 2 + side * (0.25 + t * 2.6), x = cx + Math.cos(a) * rx, y = cy + Math.sin(a) * ry; var dir = a + side * Math.PI / 2; for (var k = -1; k <= 1; k += 2) out.push(place([[0, 0], [leaf * 0.5, -leaf * 0.22], [leaf, 0], [leaf * 0.5, leaf * 0.22]], x, y, dir + k * 0.7)); }
  return out;
}
function column(x, y0, y1, w) { var out = [[[x - w * 0.6, y0], [x + w * 0.6, y0], [x + w * 0.6, y0 + 30], [x - w * 0.6, y0 + 30]], [[x - w * 0.5, y0 + 30], [x + w * 0.5, y0 + 30], [x + w * 0.5, y1 - 30], [x - w * 0.5, y1 - 30]], [[x - w * 0.6, y1 - 30], [x + w * 0.6, y1 - 30], [x + w * 0.6, y1], [x - w * 0.6, y1]]]; return out; }
function flutes(x, y0, y1, w) { var out = []; for (var k = -2; k <= 2; k++) out.push([[x + k * w * 0.18, y0 + 34], [x + k * w * 0.18, y1 - 34]]); return out; }
function banner(x, y, w, h, f, k) {   // a long banner hanging and rippling
  var pts = [[x - w / 2, y], [x + w / 2, y]]; for (var i = 0; i <= 10; i++) { var t = i / 10; pts.push([x + w / 2 + Math.sin(f * 0.2 + t * 4 + k) * 12 * t, y + t * h]); } pts.push([x, y + h - 50]); for (var j = 10; j >= 0; j--) { var t2 = j / 10; pts.push([x - w / 2 + Math.sin(f * 0.2 + t2 * 4 + k) * 12 * t2, y + t2 * h]); }
  return pts;
}
function eagle(cx, cy, s, flap) {   // an eagle with spread wings, in silhouette: feathered tips, a fanned tail, a hooked beak
  var w = Math.sin(flap) * 0.3, L = [[0, -0.1], [-0.3, -0.35], [-0.7, -0.5], [-1.15, -0.45], [-1.1, -0.3], [-1.0, -0.32], [-0.98, -0.18], [-0.85, -0.22], [-0.82, -0.08], [-0.68, -0.12], [-0.62, 0.0], [-0.45, -0.02], [-0.2, 0.12]];
  var wl = [], wr = [];
  for (var i = 0; i < L.length; i++) { var x = L[i][0] * s, y = (L[i][1] - w * Math.abs(L[i][0])) * s; wl.push([cx + x, cy + y]); wr.push([cx - x, cy + y]); }
  return [wl, wr, place([[-0.14, -0.3], [0.14, -0.3], [0.17, 0.3], [-0.17, 0.3]], cx, cy, 0, s, s), place([[-0.12, 0.25], [0.12, 0.25], [0.26, 0.62], [0.08, 0.55], [0, 0.64], [-0.08, 0.55], [-0.26, 0.62]], cx, cy, 0, s, s),
          place(circle(0, -0.38, 0.13, 1, 12), cx, cy, 0, s, s), place([[0.06, -0.44], [0.27, -0.38], [0.2, -0.3], [0.06, -0.32]], cx, cy, 0, s, s)];
}
var HIS_RARE = {
  title: function (fr, f, u) {   // a parchment, a quill's lines, a wax seal pressed onto it
    var lines2 = []; for (var k = 0; k < 9; k++) { var u2 = ease((f - k) / 4); if (u2 > 0) lines2.push([[160, 220 + k * 80], [160 + (760 - (k % 3) * 120) * u2, 220 + k * 80]]); }
    lines(fr.main, lines2, HIS.ink, 4, 70);
    var press = f < 14 ? 1 - ease(f / 14) : 0; polys(fr.main, [burst(780, 860, 18, 110 + press * 30, 96 + press * 26, 0.08, 0.2)], HIS.wax, 100); polys(fr.main, [circle(780, 860, 70, 1, 30)], [0.48, 0.06, 0.08], 100);
    polys(fr.haze, [circle(C, C, 700, 1, 40)], HIS.parch_d, 70);
    polys(fr.main, [full()], HIS.parch, 100);
  },
  wipe: function (fr, v) { var y = -60 + ease(v) * 1260; polys(fr.top, [[[-60, -60], [1140, -60], [1140, y], [-60, y]]], HIS.parch, 100); polys(fr.top, [[[-60, y - 20], [1140, y - 20], [1140, y + 30], [-60, y + 30]]], HIS.parch_d, 100); },
  stage: function (fr, f, at, o) {
    var open2 = ease((f - CARD_AT + 6) / 10), top2 = C - 60 - 260 * open2, bot2 = C + 60 + 260 * open2;
    var rolls = [[[110, top2 - 26], [970, top2 - 26], [970, top2 + 26], [110, top2 + 26]], [[110, bot2 - 26], [970, bot2 - 26], [970, bot2 + 26], [110, bot2 + 26]]];
    polys(fr.main, [burst(840, bot2 - 60, 16, 70, 60, 0.08, 0.3), circle(840, bot2 - 60, 44, 1, 24)], HIS.wax, o); polys(fr.main, rolls, HIS.parch_d, o); lines(fr.main, rolls, HIS.bronze, 4, o, true);
    var writing = []; for (var k = 0; k < 9; k++) { var y = top2 + 70 + k * 56; if (y > bot2 - 50) break; writing.push([[150, y], [330 - (k % 3) * 30, y]]); writing.push([[750 + (k % 2) * 30, y], [930, y]]); } lines(fr.main, writing, HIS.ink, 4, o * 0.7);
    polys(fr.main, [[[130, top2], [950, top2], [950, bot2], [130, bot2]]], HIS.parch, o);
    polys(fr.main, [burst(C, C, 20, 430, 380, 0.06, 0.2)], HIS.wax, o * 0.25);
    polys(fr.haze, [circle(C, C, 700, 1, 40)], HIS.parch_d, o * 0.7);
    polys(fr.main, [full()], HIS.parch, o);
  },
  over: function (fr, f, at) { if (at >= 2) { seed(2112); var pts = []; for (var i = 0; i < 8; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 160, 222) + between(10, 80); pts.push([C + Math.cos(a) * r, C + Math.sin(a) * r]); } polys(fr.top, glintPolys(twinkle(pts, f, 2, 16)), HIS.gold); } }
};
var HIS_EPIC = {
  title: function (fr, f, u) {   // a mosaic laying itself out tile by tile round a sun
    var tiles = [[], [], [], []], cols = [HIS.crimson, HIS.gold, [0.18, 0.35, 0.45], HIS.marble];
    for (var y = 0; y < 18; y++) for (var x = 0; x < 18; x++) { var cx2 = -30 + x * 64, cy2 = -30 + y * 64, d = Math.sqrt((cx2 - C) * (cx2 - C) + (cy2 - C) * (cy2 - C)); if (d / 40 > f * 1.2) continue; var ring2 = Math.floor(d / 120) % 4; tiles[ring2].push([[cx2 + 2, cy2 + 2], [cx2 + 60, cy2 + 2], [cx2 + 60, cy2 + 60], [cx2 + 2, cy2 + 60]]); }
    for (var k = 0; k < 4; k++) polys(fr.main, tiles[k], cols[k], 100);
    polys(fr.main, [full()], HIS.stone, 100);
  },
  wipe: function (fr, v) { var tiles = []; for (var y = 0; y < 18; y++) for (var x = 0; x < 18; x++) { var t = clamp01(v * 2.2 - (x + y) / 34); var cx2 = -30 + x * 64, cy2 = -30 + y * 64; tiles.push(place([[-32, -32 * t], [32, -32 * t], [32, 32 * t], [-32, 32 * t]], cx2 + 32, cy2 + 32, 0)); } polys(fr.top, tiles, HIS.marble, 100); },
  stage: function (fr, f, at, o) {   // a laurel wreath growing round the card, marble columns at the sides
    var lw = laurel(C, C + 20, 380, 470, ease((f - CARD_AT) / 14), 64); polys(fr.main, lw, [0.4, 0.5, 0.2], o); lines(fr.main, lw, [0.25, 0.32, 0.1], 2, o, true);
    var cols2 = column(120, 60, 1100, 120).concat(column(960, 60, 1100, 120)); polys(fr.main, cols2, HIS.marble, o); lines(fr.main, flutes(120, 60, 1100, 120).concat(flutes(960, 60, 1100, 120)), HIS.stone, 3, o);
    polys(fr.haze, [circle(C, C, 420, 1, 40)], HIS.gold, o * 0.6);
    polys(fr.main, [full()], [0.36, 0.32, 0.27], o);
  },
  over: function (fr, f, at) { bigGlint(fr, at, HIS.gold); }
};
var HIS_LEGENDARY = {
  title: function (fr, f, u) {   // the triumph: a temple's columns, crimson banners, an eagle rising at sunrise
    polys(fr.top, eagle(C, 330 - f * 4, 200, f * 0.4), HIS.ink, 100);
    for (var k = 0; k < 4; k++) { var x = 140 + k * 266; polys(fr.main, column(x, 380, 1100, 110), HIS.marble, 100); lines(fr.main, flutes(x, 380, 1100, 110), HIS.stone, 3, 100); }
    polys(fr.main, [[[40, 380], [1040, 380], [C, 230]]], HIS.marble, 100);
    var rays = []; for (var r = 0; r < 16; r++) { var a = -Math.PI + r * Math.PI / 15; rays.push([[C, 760], [C + Math.cos(a - 0.05) * 1200, 760 + Math.sin(a - 0.05) * 1200], [C + Math.cos(a + 0.05) * 1200, 760 + Math.sin(a + 0.05) * 1200]]); }
    polys(fr.main, rays, HIS.gold, 30);
    polys(fr.main, [full()], HIS.sky, 100);
  },
  wipe: function (fr, v) { polys(fr.top, [full()], HIS.gold, 100 * (1 - Math.abs(v * 2 - 1))); },
  stage: function (fr, f, at, o) {   // a golden laurel, rays of glory, crimson banners, petals falling
    var lw = laurel(C, C + 20, 420, 500, ease((f - CARD_AT) / 10), 74); polys(fr.main, lw, HIS.gold, o); lines(fr.main, lw, HIS.bronze, 3, o, true);
    var bn = [banner(120, -60, 150, 900, f, 0), banner(960, -60, 150, 900, f, 2), banner(320, -60, 110, 560, f, 1), banner(760, -60, 110, 560, f, 3)]; polys(fr.main, bn, HIS.crimson, o); lines(fr.main, bn, HIS.gold, 5, o, true);
    seed(2140); var petals = []; for (var i = 0; i < 40; i++) { var x = between(0, 1080) + Math.sin(f * 0.1 + i) * 30, y = -60 + ((f * between(6, 12) + between(0, 1200)) % 1260); petals.push(place([[0, 0], [14, -8], [28, 0], [14, 8]], x, y, f * 0.1 + i)); } polys(fr.top, petals, [0.8, 0.12, 0.15], o);
    var rays = []; for (var r = 0; r < 24; r++) { var a = r * Math.PI / 12 + f * 0.01; rays.push([[C, C], [C + Math.cos(a - 0.06) * 1200, C + Math.sin(a - 0.06) * 1200], [C + Math.cos(a + 0.06) * 1200, C + Math.sin(a + 0.06) * 1200]]); }
    polys(fr.main, rays, HIS.gold, o * 0.35);
    polys(fr.main, [full()], [0.5, 0.25, 0.12], o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 8) polys(fr.top, slash(-60, 760, 1140, 300, 36, ease(at / 3), 0.4), HIS.gold, fade(at, 4, 8) * 90); bigGlint(fr, at, HIS.gold); }
};
var GENRE_HISTORY = {
  rarities: { rare: HIS_RARE, epic: HIS_EPIC, legendary: HIS_LEGENDARY },
  opening: function (comp) {   // a wax seal stamped on the pack, then a parchment rolling over it
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 30) { var down = f < 14 ? ease(f / 14) : 1, r = 140 + (1 - down) * 120; polys(fr.top, [burst(cx, cy, 18, r, r * 0.88, 0.08, 0.2)], HIS.wax, 100 * fade(f, 26, 30)); polys(fr.top, [circle(cx, cy, r * 0.62, 1, 30)], [0.48, 0.06, 0.08], 100 * fade(f, 26, 30)); }
      if (f >= 14 && f < 18) polys(fr.top, [circle(cx, cy, 500, 1, 30)], HIS.gold, 60 - (f - 14) * 15);
      if (f >= 26 && f < 56) { var x = -60 + ease((f - 26) / 14) * 1300; polys(fr.top, [[[-60, cy - 400], [x, cy - 400], [x, cy + 400], [-60, cy + 400]]], HIS.parch, 100 * fade(f, 48, 56)); polys(fr.top, [[[x - 30, cy - 420], [x + 30, cy - 420], [x + 30, cy + 420], [x - 30, cy + 420]]], HIS.parch_d, 100 * fade(f, 48, 56)); }
    }
  }
};

// ===== Front — war: flares over a trench, the bombing, victory =============================================
var WAR = { olive: [0.29, 0.33, 0.13], khaki: [0.76, 0.7, 0.5], dark: [0.12, 0.13, 0.07], smoke: [0.35, 0.35, 0.33], flare: [1, 0.85, 0.5], fire: [1, 0.5, 0.15], sky: [0.2, 0.22, 0.25], dawn: [0.98, 0.65, 0.35], red: [0.7, 0.12, 0.1], white: [0.95, 0.95, 0.92] };
function wire(y, f) {   // barbed wire along the trench: a coil and its barbs
  var coil = [], barbs = []; for (var x = -60; x <= 1140; x += 8) coil.push([x, y + Math.sin(x * 0.08) * 26]); for (var x2 = -60; x2 <= 1140; x2 += 40) { var yy = y + Math.sin(x2 * 0.08) * 26; barbs.push([[x2 - 8, yy - 8], [x2 + 8, yy + 8]]); barbs.push([[x2 - 8, yy + 8], [x2 + 8, yy - 8]]); }
  return coil.length ? [coil].concat(barbs) : barbs;
}
function smokeCloud(L, cx, cy, r, base, color, o) { seed(base); var pf = puff(cx, cy, r, 8); polys(L, pf[0], color, o); polys(L, pf[1], [color[0] * 0.75, color[1] * 0.75, color[2] * 0.75], o); }
function beam(L, x, ang, len, w0, w1, color, o) {   // a searchlight's beam from (x, 1140) along ang, up the screen
  var c = Math.cos(ang), sn = Math.sin(ang);
  polys(L, [[[x - w0, 1140], [x + w0, 1140], [x + c * len + sn * w1, 1140 + sn * len - c * w1], [x + c * len - sn * w1, 1140 + sn * len + c * w1]]], color, o);
}
function bomber(x, y, s) { return [place([[-1.0 * s, -0.08 * s], [1.0 * s, -0.06 * s], [1.1 * s, 0], [1.0 * s, 0.06 * s], [-1.0 * s, 0.08 * s]], x, y, 0), place([[0.1 * s, 0], [-0.25 * s, -0.95 * s], [-0.45 * s, -0.95 * s], [-0.25 * s, 0], [-0.45 * s, 0.95 * s], [-0.25 * s, 0.95 * s]], x, y, 0), place([[-0.85 * s, 0], [-1.0 * s, -0.35 * s], [-1.08 * s, -0.35 * s], [-1.0 * s, 0], [-1.08 * s, 0.35 * s], [-1.0 * s, 0.35 * s]], x, y, 0)]; }
function flag(x, y, w, h, f) {   // a flag on its pole, waving: two bands
  var top = [], mid = []; for (var i = 0; i <= 16; i++) { var t = i / 16, dy = Math.sin(f * 0.3 - t * 5) * 18 * t; top.push([x + t * w, y + dy]); mid.push([x + t * w, y + h / 2 + dy]); }
  var bot = []; for (var j = 16; j >= 0; j--) { var t2 = j / 16; bot.push([x + t2 * w, y + h + Math.sin(f * 0.3 - t2 * 5) * 18 * t2]); }
  var upper = top.concat(mid.slice().reverse()), lower = mid.concat(bot);
  return { upper: upper, lower: lower, pole: [[x - 8, y - 20], [x + 4, y - 20], [x + 4, y + h * 3.2], [x - 8, y + h * 3.2]] };
}
var WAR_RARE = {
  title: function (fr, f, u) {   // night over the trench: flares drifting down, their light swinging, barbed wire
    for (var k = 0; k < 2; k++) { var t = f + k * 10, x = 300 + k * 480 + Math.sin(t * 0.2) * 40, y = 240 + t * 6; glowOn(fr, [circle(x, y, 140, 1, 24)], WAR.flare, 90); polys(fr.main, [circle(x, y, 14, 1, 12)], WAR.white, 100); lines(fr.main, [[[x, y], [x, y - 260]]], WAR.smoke, 6, 60); coneOn(fr, x, 1.5708, 1000, 60, 500, WAR.flare, 40); polys(fr.main, [circle(x, y, 260, 1, 30)], [0.3, 0.26, 0.18], 60); }
    lines(fr.main, wire(740, f), [0.3, 0.3, 0.26], 4, 100);
    polys(fr.main, [[[-60, 770], [200, 730], [500, 780], [800, 740], [1140, 770], [1140, 1140], [-60, 1140]]], WAR.dark, 100);
    polys(fr.main, [full()], [0.08, 0.09, 0.1], 100);
  },
  wipe: function (fr, v) { smokeCloud(fr.top, C, C, 100 + ease(v) * 900, 2200, WAR.smoke, 100 * (1 - Math.abs(v * 2 - 1)) + 10); },
  stage: function (fr, f, at, o) {
    var fx = C + 300 * Math.sin(f * 0.05), fy = 260 + ((f - CARD_AT) * 3) % 120;
    polys(fr.main, [circle(fx, fy, 12, 1, 12)], WAR.white, o); glowOn(fr, [circle(fx, fy, 200, 1, 24)], WAR.flare, o * 0.8);
    smokeCloud(fr.main, 160, 780, 220, 2210, WAR.smoke, o * 0.7); smokeCloud(fr.main, 930, 800, 240, 2211, WAR.smoke, o * 0.7);
    lines(fr.main, wire(830, f), [0.3, 0.3, 0.26], 4, o);
    polys(fr.main, [[[-60, 850], [300, 820], [700, 860], [1140, 830], [1140, 1140], [-60, 1140]]], WAR.dark, o);
    polys(fr.main, [circle(fx, fy, 700, 1, 40)], [0.24, 0.21, 0.15], o * 0.6);
    polys(fr.main, [full()], [0.1, 0.11, 0.1], o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 5) polys(fr.top, [full()], WAR.flare, 30 - at * 6); }
};
var WAR_EPIC = {
  title: function (fr, f, u) {   // bombers in formation, searchlights crossing, flak bursting
    for (var i = 0; i < 5; i++) { var x = -300 + f * 40 + (i % 2) * 120 + i * 150, y = 260 + Math.abs(i - 2) * 70; polys(fr.main, bomber(x, y, 110), WAR.dark, 100); }
    for (var k = 0; k < 3; k++) beamOn(fr, 200 + k * 340, -1.5708 + 0.4 * Math.sin(f * 0.1 + k * 2), 1400, 20, 160, WAR.white, 50);
    seed(2220); for (var j = 0; j < 6; j++) { var t = (f + j * 4) % 16, x2 = between(100, 980), y2 = between(150, 600); if (t < 10) smokeCloud(fr.main, x2, y2, 30 + t * 6, 2221 + j, [0.15, 0.15, 0.15], 100 * fade(t, 6, 10)); }
    polys(fr.main, [full()], WAR.sky, 100);
  },
  wipe: function (fr, v) { smokeCloud(fr.top, C, C, 100 + ease(v) * 1000, 2230, [0.4, 0.38, 0.33], 100 * (1 - Math.abs(v * 2 - 1)) + 10); },
  stage: function (fr, f, at, o) {   // flak bursting round the card, searchlights sweeping
    seed(2240); for (var j = 0; j < 10; j++) { var t = (f - CARD_AT + j * 3) % 20, a = between(0, Math.PI * 2), d = between(320, 520); if (t < 12) { if (t < 3) polys(fr.main, [burst(C + Math.cos(a) * d, C + Math.sin(a) * d, 10, 70, 30, 0.4, j)], WAR.flare, o); smokeCloud(fr.main, C + Math.cos(a) * d, C + Math.sin(a) * d, 40 + t * 7, 2241 + j, [0.18, 0.18, 0.18], o * fade(t, 6, 12)); if (t < 2) glowOn(fr, [circle(C + Math.cos(a) * d, C + Math.sin(a) * d, 90, 1, 20)], WAR.fire, o); } }
    for (var k = 0; k < 3; k++) beamOn(fr, 200 + k * 340, -1.5708 + 0.5 * Math.sin(f * 0.09 + k * 2), 1300, 20, 180, WAR.white, o * 0.5);
    seed(2245); var city = [[-60, 1140]]; for (var x = -60; x <= 1140; x += 40) { var h = between(40, 140); city.push([x, 860 - h]); city.push([x + 40, 860 - h]); } city.push([1140, 1140]); polys(fr.main, [city], [0.07, 0.07, 0.08], o);
    glowOn(fr, [[[-60, 700], [1140, 700], [1140, 900], [-60, 900]]], WAR.fire, o * 0.7);
    polys(fr.main, [[[-60, 640], [1140, 640], [1140, 900], [-60, 900]]], [0.45, 0.22, 0.12], o * 0.8);
    polys(fr.main, [full()], WAR.sky, o);
  },
  over: function (fr, f, at) { sparksOut(fr.main, fr.glow, at - 2, 20, WAR.fire, 2250, 24); bigGlint(fr, at, WAR.flare); }
};
var WAR_LEGENDARY = {
  title: function (fr, f, u) {   // victory at dawn: soldiers raising a flag on a hill
    var fl = flag(C + 60, 260, 300, 160, f); polys(fr.main, [fl.upper], WAR.red, 100); polys(fr.main, [fl.lower], WAR.white, 100); polys(fr.main, [fl.pole], WAR.dark, 100);
    for (var k = 0; k < 3; k++) polys(fr.main, [place([[-30, 0], [30, 0], [40, 180], [-40, 180]], C - 20 - k * 70, 780 + k * 30, -0.4), place(circle(0, -24, 24, 1, 12), C - 20 - k * 70, 780 + k * 30, 0)], WAR.dark, 100);
    polys(fr.main, [[[-60, 1000], [300, 900], [C + 100, 800], [800, 880], [1140, 960], [1140, 1140], [-60, 1140]]], WAR.dark, 100);
    glowOn(fr, [circle(C + 300, 820, 300, 1, 40)], WAR.dawn, 100);
    polys(fr.main, [full()], [0.95, 0.6, 0.4], 100);
  },
  wipe: function (fr, v) { polys(fr.top, [full()], WAR.white, 100 * (1 - Math.abs(v * 2 - 1))); },
  stage: function (fr, f, at, o) {   // the flag great behind the card, planes trailing coloured smoke, the sun rising
    var fl = flag(140, 140, 820, 420, f); polys(fr.main, [fl.upper], WAR.red, o); polys(fr.main, [fl.lower], WAR.white, o); polys(fr.main, [fl.pole], WAR.dark, o);
    for (var p = 0; p < 3; p++) { var t = f - CARD_AT - p * 3; if (t < 0) continue; var x = -200 + t * 60, y = 900 - p * 60 - t * 20; polys(fr.top, bomber(x, y, 60), WAR.dark, o); var trail = []; for (var i = 0; i < 20; i++) trail.push(circle(x - i * 40, y + i * 13, 14 + i * 1.5, 1, 10)); polys(fr.main, trail, [WAR.red, WAR.white, [0.2, 0.3, 0.7]][p], o * 0.8); }
    var rays = []; for (var r = 0; r < 18; r++) { var a = -Math.PI + r * Math.PI / 17; rays.push([[C, 1100], [C + Math.cos(a - 0.05) * 1400, 1100 + Math.sin(a - 0.05) * 1400], [C + Math.cos(a + 0.05) * 1400, 1100 + Math.sin(a + 0.05) * 1400]]); }
    polys(fr.main, rays, WAR.dawn, o * 0.4);
    polys(fr.main, [full()], [0.92, 0.55, 0.35], o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 8) polys(fr.top, slash(-60, 760, 1140, 300, 36, ease(at / 3), 0.4), WAR.white, fade(at, 4, 8) * 90); bigGlint(fr, at, WAR.flare); }
};
var GENRE_WAR = {
  rarities: { rare: WAR_RARE, epic: WAR_EPIC, legendary: WAR_LEGENDARY },
  opening: function (comp) {   // searchlights find the pack, a flare — it blows up in a cloud of dust
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      if (f < 26) for (var k = 0; k < 3; k++) { var x0 = 180 + k * 400, a = Math.atan2(cy - 1100, cx - x0) * ease(f / 16) + (-1.5708) * (1 - ease(f / 16)); polys(fr.glow, [[[x0 - 14, 1100], [x0 + 14, 1100], [x0 + Math.cos(a) * 1300 + 120, 1100 + Math.sin(a) * 1300], [x0 + Math.cos(a) * 1300 - 120, 1100 + Math.sin(a) * 1300]]], WAR.white, 60); }
      if (f >= 24 && f < 27) polys(fr.top, [circle(cx, cy, 700, 1, 40)], WAR.flare, 100 - (f - 24) * 33);
      if (f >= 24) { smokeCloud(fr.top, cx, cy, 120 + ease((f - 24) / 10) * 380, 2260, [0.55, 0.5, 0.4], fade(f, 46, 63) * 100); seed(2261); var debris = []; for (var i = 0; i < 20; i++) { var a2 = between(-Math.PI, 0), d = 60 + (f - 24) * between(14, 28); debris.push(place([[-12, -8], [12, -6], [8, 10], [-10, 8]], cx + Math.cos(a2) * d, cy + Math.sin(a2) * d + (f - 24) * (f - 24) * 0.6, f * 0.3 + i)); } polys(fr.top, debris, WAR.dark, fade(f, 50, 63) * 100); }
    }
  }
};

// ===== Saloon — western: a wanted poster, the duel, riding into the sunset ================================
var WES = { sand: [0.91, 0.78, 0.55], desert: [0.9, 0.6, 0.32], sun: [1, 0.78, 0.35], dusk: [0.75, 0.28, 0.18], wood: [0.42, 0.26, 0.14], wood_d: [0.28, 0.16, 0.08], paper: [0.93, 0.84, 0.64], ink: [0.23, 0.14, 0.08], gold: [1, 0.8, 0.3], sky: [0.98, 0.76, 0.42] };
function planks(L, o) { var out = []; for (var k = 0; k < 10; k++) out.push([[-60, k * 124 - 60], [1140, k * 124 - 60], [1140, k * 124 + 58], [-60, k * 124 + 58]]); polys(L, out, WES.wood, o); }
function plankLines(L, o) { var out = []; for (var k = 0; k < 10; k++) out.push([[-60, k * 124 + 60], [1140, k * 124 + 60]]); lines(L, out, WES.wood_d, 6, o); }
function wanted(cx, cy, w, h, sway) { return { paper: place([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]], cx, cy, sway), frame: place([[-w * 0.36, -h * 0.2], [w * 0.36, -h * 0.2], [w * 0.36, h * 0.25], [-w * 0.36, h * 0.25]], cx, cy, sway), bars: [place([[-w * 0.4, -h * 0.4], [w * 0.4, -h * 0.4], [w * 0.4, -h * 0.3], [-w * 0.4, -h * 0.3]], cx, cy, sway), place([[-w * 0.3, h * 0.32], [w * 0.3, h * 0.32], [w * 0.3, h * 0.4], [-w * 0.3, h * 0.4]], cx, cy, sway)], nail: place(circle(0, -h * 0.47, 8, 1, 10), cx, cy, sway) }; }
function cowboy(x, y, s, face) { return [place([[-0.35 * s, 0], [-0.3 * s, -1.4 * s], [0.3 * s, -1.4 * s], [0.35 * s, 0], [0.45 * s, 1.5 * s], [-0.45 * s, 1.5 * s]], x, y, 0), place(circle(0, -1.6 * s, 0.2 * s, 1.1, 12), x, y, 0), place([[-0.55 * s, -1.75 * s], [0.55 * s, -1.75 * s], [0.25 * s, -1.85 * s], [0.2 * s, -2.1 * s], [-0.2 * s, -2.1 * s], [-0.25 * s, -1.85 * s]], x, y, 0), place([[0.3 * face * s, -0.9 * s], [0.85 * face * s, -0.7 * s], [0.85 * face * s, -0.6 * s], [0.3 * face * s, -0.75 * s]], x, y, 0)]; }
function cactus(x, y, s) { return [[[x - 0.15 * s, y], [x - 0.15 * s, y - 1.6 * s], [x + 0.15 * s, y - 1.6 * s], [x + 0.15 * s, y]], [[x - 0.15 * s, y - 0.8 * s], [x - 0.55 * s, y - 0.8 * s], [x - 0.55 * s, y - 1.3 * s], [x - 0.35 * s, y - 1.3 * s], [x - 0.35 * s, y - 1.0 * s], [x - 0.15 * s, y - 1.0 * s]], [[x + 0.15 * s, y - 0.6 * s], [x + 0.5 * s, y - 0.6 * s], [x + 0.5 * s, y - 1.1 * s], [x + 0.3 * s, y - 1.1 * s], [x + 0.3 * s, y - 0.8 * s], [x + 0.15 * s, y - 0.8 * s]]]; }
function rider(x, y, s, f) {   // a horse at the gallop and its rider, in silhouette, facing right
  var out = [place([[-0.8, -0.3], [0.45, -0.35], [0.8, -0.85], [1.0, -0.95], [1.3, -0.7], [1.2, -0.6], [0.95, -0.62], [0.75, -0.25], [0.65, 0.05], [-0.6, 0.1], [-0.85, -0.05]], x, y, 0, s, s),
             place([[-0.8, -0.25], [-1.25, 0.1 + 0.08 * Math.sin(f * 0.8)], [-1.15, 0.2], [-0.78, -0.1]], x, y, 0, s, s),
             place([[0.85, -0.9], [0.9, -1.08], [0.97, -0.92]], x, y, 0, s, s)];
  var legs = [[0.5, 0], [0.35, 1.6], [-0.55, 3.1], [-0.7, 4.6]];
  for (var i = 0; i < legs.length; i++) out.push(place([[-0.06, 0], [0.06, 0], [0.05, 0.7], [-0.05, 0.7]], x + legs[i][0] * s, y + 0.02 * s, 0.55 * Math.sin(f * 0.8 + legs[i][1]), s, s));
  out.push(place([[-0.05, -0.35], [0.17, -0.35], [0.22, -1.0], [0.0, -1.0]], x, y, 0, s, s), place([[0.0, -0.35], [0.16, -0.35], [0.22, 0.02], [0.08, 0.02]], x, y, 0, s, s),
           place(circle(0.11, -1.12, 0.12, 1, 12), x, y, 0, s, s), place([[-0.14, -1.2], [0.36, -1.2], [0.36, -1.24], [0.24, -1.26], [0.2, -1.42], [0.0, -1.42], [-0.04, -1.26], [-0.14, -1.24]], x, y, 0, s, s));
  return out;
}
var WES_RARE = {
  title: function (fr, f, u) {   // a wanted poster nailed to the wall, fluttering
    var w = wanted(C, 540, 520, 700, Math.sin(f * 0.25) * 0.04);
    polys(fr.main, [w.nail], [0.3, 0.3, 0.3], 100); polys(fr.main, w.bars, WES.ink, 100); polys(fr.main, [w.frame], [0.75, 0.62, 0.42], 100); polys(fr.main, [w.paper], WES.paper, 100);
    plankLines(fr.main, 100); planks(fr.main, 100);
    polys(fr.main, [full()], WES.wood, 100);
  },
  wipe: function (fr, v) { iris(fr, v < 0.5 ? 900 * (1 - ease(v * 2)) + 30 : 30 + 900 * ease(v * 2 - 1)); },
  stage: function (fr, f, at, o) {
    var w = wanted(C, C + 10, 480, 640, 0); polys(fr.main, [w.nail], [0.3, 0.3, 0.3], o); polys(fr.main, w.bars, WES.ink, o); polys(fr.main, [w.paper], WES.paper, o * 0.9);
    plankLines(fr.main, o); planks(fr.main, o);
    polys(fr.main, [full()], WES.wood, o);
  },
  over: function (fr, f, at) { if (at >= 2) { seed(2312); var pts = []; for (var i = 0; i < 6; i++) { var a = between(0, Math.PI * 2), r = toEdge(a, 160, 222) + between(10, 80); pts.push([C + Math.cos(a) * r, C + Math.sin(a) * r]); } polys(fr.top, glintPolys(twinkle(pts, f, 2, 16)), WES.gold); } }
};
var WES_EPIC = {
  title: function (fr, f, u) {   // high noon: two gunmen facing each other down the street, a tumbleweed rolling
    polys(fr.main, cowboy(230, 720, 130, 1).concat(cowboy(850, 720, 130, -1)), WES.ink, 100);
    var tx = -100 + f * 50; polys(fr.main, [burst(tx, 900, 16, 70, 50, 0.4, f * 0.3)], [0.55, 0.42, 0.22], 100);
    polys(fr.main, [[[-60, 860], [1140, 860], [1140, 1140], [-60, 1140]]], WES.desert, 100);
    glowOn(fr, [circle(C, 160, 160, 1, 30)], WES.sun, 100); polys(fr.main, [circle(C, 160, 80, 1, 30)], [1, 0.95, 0.8], 100);
    polys(fr.main, [full()], WES.sky, 100);
  },
  wipe: function (fr, v) { polys(fr.top, [burst(C + 200, C - 100, 12, 60 + ease(v) * 900, 30 + ease(v) * 500, 0.4, 0.3)], [1, 0.9, 0.6], 100 * (1 - Math.abs(v * 2 - 1)) + 20); },
  stage: function (fr, f, at, o) {   // dust swirling, the wall behind riddled with bullet holes, sheriff's stars spinning
    if (at >= -4) { var holes = [[C - 380, C - 300, -4], [C + 400, C - 200, -1], [C - 330, C + 260, 2], [C + 360, C + 320, 5], [C + 20, C - 480, 8], [C - 440, C + 20, 11]]; for (var i = 0; i < holes.length; i++) { var t = at - holes[i][2]; if (t < 0) continue; var h = bulletHole(holes[i][0], holes[i][1], 2320 + i); lines(fr.main, h.cracks, WES.wood_d, 3, o); polys(fr.main, [h.core], [0.06, 0.03, 0.02], o); polys(fr.main, [h.rim], [0.7, 0.5, 0.3], o); if (t < 3) glowOn(fr, [circle(holes[i][0], holes[i][1], 60, 1, 16)], WES.sun, o); } }
    var stars = []; for (var k = 0; k < 4; k++) { var a = f * 0.04 + k * Math.PI / 2; stars.push(star5(C + Math.cos(a) * 470, C + Math.sin(a) * 470, 50, f * 0.15 + k, 0.5)); } polys(fr.main, stars, WES.gold, o); lines(fr.main, stars, WES.ink, 3, o, true);
    plankLines(fr.main, o); planks(fr.main, o);
    polys(fr.main, [full()], WES.wood, o);
  },
  over: function (fr, f, at) { bigGlint(fr, at, WES.gold); }
};
var WES_LEGENDARY = {
  title: function (fr, f, u) {   // a rider crossing a huge setting sun among mesas and cacti
    polys(fr.main, rider(-150 + f * 40, 760, 130, f), WES.ink, 100);
    polys(fr.main, cactus(150, 900, 160).concat(cactus(920, 920, 130)), WES.ink, 100);
    polys(fr.main, [[[-60, 860], [1140, 860], [1140, 1140], [-60, 1140]], [[620, 860], [660, 700], [880, 690], [920, 860]]], [0.45, 0.2, 0.12], 100);
    glowOn(fr, [circle(C, 760, 380, 1, 48)], WES.sun, 80); polys(fr.main, [circle(C, 760, 300, 1, 64)], WES.sun, 100);
    polys(fr.main, [[[-60, 300], [1140, 300], [1140, 860], [-60, 860]]], [0.95, 0.5, 0.25], 100);
    polys(fr.main, [full()], WES.dusk, 100);
  },
  wipe: function (fr, v) { smokeCloud(fr.top, C, C + 200, 120 + ease(v) * 900, 2330, WES.sand, 100 * (1 - Math.abs(v * 2 - 1)) + 10); },
  stage: function (fr, f, at, o) {   // the great sun behind the card, its rays, the desert in silhouette, an eagle circling
    var rays = []; for (var r = 0; r < 20; r++) { var a = r * Math.PI / 10 + f * 0.01; rays.push([[C, C], [C + Math.cos(a - 0.07) * 1300, C + Math.sin(a - 0.07) * 1300], [C + Math.cos(a + 0.07) * 1300, C + Math.sin(a + 0.07) * 1300]]); }
    polys(fr.main, cactus(140, 1100, 200).concat(cactus(960, 1080, 170)), WES.ink, o);
    polys(fr.main, [[[-60, 980], [1140, 980], [1140, 1140], [-60, 1140]], [[-60, 980], [-60, 760], [220, 750], [260, 980]], [[800, 980], [840, 720], [1140, 730], [1140, 980]]], [0.3, 0.13, 0.08], o);
    polys(fr.main, eagle(C + Math.cos(f * 0.05) * 420, 220 + Math.sin(f * 0.05) * 60, 70, f * 0.3), WES.ink, o);
    glowOn(fr, [circle(C, C, 420 * ease((f - CARD_AT) / 6) + 60, 1, 48)], WES.sun, o); polys(fr.main, [circle(C, C, 360 * ease((f - CARD_AT) / 6) + 40, 1, 64)], WES.sun, o);
    polys(fr.main, rays, [1, 0.6, 0.3], o * 0.4);
    polys(fr.main, [full()], WES.dusk, o);
  },
  over: function (fr, f, at) { if (at >= 0 && at < 8) polys(fr.top, slash(-60, 760, 1140, 300, 34, ease(at / 3), 0.4), WES.gold, fade(at, 4, 8) * 90); sparksOut(fr.main, fr.glow, at - 2, 18, WES.gold, 2340, 22); bigGlint(fr, at, WES.gold); }
};
var GENRE_WESTERN = {
  rarities: { rare: WES_RARE, epic: WES_EPIC, legendary: WES_LEGENDARY },
  opening: function (comp) {   // a saloon's swinging doors close in front of the pack — they swing open: it is gone
    var cx = 576, cy = 505;
    for (var f = 0; f < 64; f++) {
      var fr = frameOf(comp, f); if (!fr.main) continue;
      var sw = f < 16 ? ease(f / 14) : f < 34 ? 1 : 1 - ease((f - 34) / 6) + Math.sin((f - 34) * 0.9) * 0.15 * fade(f, 40, 56);
      if (f < 56) for (var side = -1; side <= 1; side += 2) { var w = 300 * clamp01(sw), x0 = cx + side * 320; var door = [[x0, cy - 280], [x0 - side * w, cy - 260], [x0 - side * w, cy + 220], [x0, cy + 240]]; polys(fr.top, [door], WES.wood, 100 * fade(f, 50, 56)); lines(fr.top, [door, [[x0, cy - 100], [x0 - side * w, cy - 90]], [[x0, cy + 60], [x0 - side * w, cy + 60]]], WES.wood_d, 8, 100 * fade(f, 50, 56)); }
      if (f >= 34) smokeCloud(fr.main, cx, cy + 260, 60 + (f - 34) * 10, 2350, WES.sand, fade(f, 50, 63) * 80);
    }
  }
};

var GENRE = { action: GENRE_ACTION, dark: GENRE_DARK, drama: GENRE_DRAMA, fantasy: GENRE_FANTASY, sf: GENRE_SF, adventure: GENRE_ADVENTURE, documentary: GENRE_DOC, thriller: GENRE_THRILLER, comedy: GENRE_COMEDY, animation: GENRE_ANIMATION, crime: GENRE_CRIME, romance: GENRE_ROMANCE, mystery: GENRE_MYSTERY, music: GENRE_MUSIC, history: GENRE_HISTORY, war: GENRE_WAR, western: GENRE_WESTERN }[GENRE_KEY];

// --- the comps --------------------------------------------------------------------------------------------
// a genre with a moment of its own per rarity gives it (``rarities``), else the same one for every rarity
function moment(rarity) { return GENRE.rarities ? GENRE.rarities[rarity] : GENRE; }
function behind(rarity) {
  var N = LENGTH[rarity], comp = square("reveal-" + rarity, N), G = moment(rarity);
  for (var f = 0; f < N; f++) {
    var fr = frameOf(comp, f); if (!fr.main) continue;
    var o = fade(f, N - 12, N - 1) * 100, at = f - FACE_AT;
    if (f < CARD_AT) G.title(fr, f, f / CARD_AT);
    if (f >= CARD_AT - 4 && f < CARD_AT + 4) G.wipe(fr, (f - CARD_AT + 4) / 8);
    if (f < CARD_AT - 1) continue;
    flash(fr, at);
    G.stage(fr, f, at, o);
  }
}
function overCard(rarity) {
  var N = LENGTH[rarity], comp = square("over-" + rarity, N);
  var G = moment(rarity);
  for (var f = 0; f < N; f++) { var fr = frameOf(comp, f); if (!fr.main) continue; G.over(fr, f, f - FACE_AT + 3); }
}
if (ONLY === "opening") GENRE.opening(newComp("opening", 1152, 1080, 64));
if (ONLY.indexOf("reveal-") === 0) behind(ONLY.slice(7));
if (ONLY.indexOf("over-") === 0) overCard(ONLY.slice(5));

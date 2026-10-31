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

var GENRE = { action: GENRE_ACTION, dark: GENRE_DARK, drama: GENRE_DRAMA, fantasy: GENRE_FANTASY, sf: GENRE_SF }[GENRE_KEY];

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

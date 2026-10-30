// Impact — helpers to draw comic shapes in EffectCraft: inked flat paths, stars, tapered lines, held keys.
var INK = [0.07, 0.02, 0.11], PINK = [1, 0.18, 0.56], PINK_L = [1, 0.55, 0.8], WHITE = [1, 1, 1];
var VIOLET = [0.42, 0.13, 0.79], LIME = [0.83, 0.96, 0.24], GREEN = [0.17, 1, 0.43], GREEN_D = [0.04, 0.6, 0.25];
var GREEN_L = [0.75, 1, 0.65], CYAN = [0.13, 0.75, 0.94], YELLOW = [1, 0.82, 0.12];

// a seeded random, so a render is the same every time
var _seed = 1;
function seed(s) { _seed = s; }
function rnd() { _seed = (_seed * 16807) % 2147483647; return (_seed - 1) / 2147483646; }
function between(a, b) { return a + (b - a) * rnd(); }

function shapeLayer(comp, name) { var L = comp.layers.addShape(); L.name = name; return L; }
function contents(L) { return L.property("ADBE Root Vectors Group"); }
function at(L, x, y) { L.property("ADBE Transform Group").property("ADBE Position").setValue([x, y]); }

// a closed (or open) path, filled and inked: the ink line drawn under the fill (only its outer half shows)
function inked(L, verts, o) {
  var g = contents(L).addProperty("ADBE Vector Group");
  if (o.name) g.name = o.name;
  var c = g.property("ADBE Vectors Group");
  var p = c.addProperty("ADBE Vector Shape - Group");
  var s = new Shape(); s.vertices = verts; s.closed = o.closed !== false;
  p.property("ADBE Vector Shape").setValue(s);
  if (o.fill) { var f = c.addProperty("ADBE Vector Graphic - Fill"); f.property("ADBE Vector Fill Color").setValue(o.fill); }
  if (o.ink) {
    var st = c.addProperty("ADBE Vector Graphic - Stroke");
    st.property("ADBE Vector Stroke Color").setValue(o.inkColor || INK);
    st.property("ADBE Vector Stroke Width").setValue(o.ink);
    st.property("ADBE Vector Stroke Line Join").setValue(2);
    st.property("ADBE Vector Stroke Line Cap").setValue(2);
    if (o.taper) {
      var tp = st.property("ADBE Vector Stroke Taper");
      tp.property("startWidth").setValue(o.taper[0]); tp.property("endWidth").setValue(o.taper[1]);
      tp.property("startLength").setValue(o.taper[2] || 50); tp.property("endLength").setValue(o.taper[3] || 50);
    }
  }
  return g;
}

// a star's points around (cx, cy): spikes of uneven length
function starVerts(cx, cy, n, rOut, rIn, spread, turn) {
  var v = [];
  for (var i = 0; i < n * 2; i++) {
    var a = (turn || 0) + i / (n * 2) * Math.PI * 2 + between(-0.12, 0.12) / n;
    var r = i % 2 === 0 ? rOut * between(1 - spread, 1) : rIn * between(0.85, 1.1);
    v.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return v;
}
// a four-pointed glint: pinched curves between its four tips
function glintVerts(r, k) {
  var v = [], pts = 32;
  for (var i = 0; i < pts; i++) {
    var a = i / pts * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
    var rr = r * Math.pow(Math.abs(c), 1 / k) + r * Math.pow(Math.abs(s), 1 / k);
    var m = Math.pow(Math.pow(Math.abs(c), 2 / 3) + Math.pow(Math.abs(s), 2 / 3), -1.5);
    v.push([c * r * m * 0 + c * Math.pow(Math.abs(c), 2) * r, s * Math.pow(Math.abs(s), 2) * r]);
  }
  return v;
}

// keys on a property, eased, held between frames for the anime cadence (the comps run at 24 fps)
function keys(prop, pairs) { for (var i = 0; i < pairs.length; i++) prop.setValueAtTime(pairs[i][0], pairs[i][1]); }
function tr(L, name) { return L.property("ADBE Transform Group").property(name); }
// visible only between two times (hold keys on opacity)
function window_(L, from, to) {
  var op = tr(L, "ADBE Opacity");
  op.setValueAtTime(0, from <= 0 ? 100 : 0);
  if (from > 0) op.setValueAtTime(from, 100);
  op.setValueAtTime(to, 0);
  for (var i = 1; i <= op.numKeys; i++) { op.setInterpolationTypeAtKey(i, KeyframeInterpolationType.HOLD); }
}

// Portalab — ambient/pixelbeach: the « pixelbeach » ambience (spec 028, B2)
float bayer2(vec2 a) {
  a = floor(a);
  return fract(dot(a, vec2(0.5, a.y * 0.75)));
}
float bayer4(vec2 a) {
  return bayer2(0.5 * a) * 0.25 + bayer2(a);
}
// a two-colour gradient the old way: v from 0 to 1 picks a or b, the dither mixing them in between
vec3 dither(vec3 a, vec3 b, float v, vec2 px) {
  return step(bayer4(px), clamp(v, 0.0, 1.0)) > 0.5 ? b : a;
}

void main() {
  float rows = 180.0;
  vec2 px = floor(gl_FragCoord.xy / u_res.y * rows);
  float W = floor(u_res.x / u_res.y * rows);
  float t = u_time;
  float tf = floor(t * 6.0) / 6.0;
  vec4 o = vec4(0.0);
  float hz = 70.0;
  // the sky: five bands, dithered between them
  float v = clamp((px.y - hz) / (rows - hz), 0.0, 1.0) * 4.0;
  float band = floor(v);
  vec3 c0 = band < 1.0 ? vec3(1.0, 0.85, 0.5) : band < 2.0 ? vec3(1.0, 0.62, 0.3) : band < 3.0 ? vec3(0.95, 0.4, 0.38) : vec3(0.55, 0.22, 0.45);
  vec3 c1 = band < 1.0 ? vec3(1.0, 0.62, 0.3) : band < 2.0 ? vec3(0.95, 0.4, 0.38) : band < 3.0 ? vec3(0.55, 0.22, 0.45) : vec3(0.22, 0.12, 0.35);
  o = over(o, dither(c0, c1, smoothstep(0.55, 1.0, fract(v)), px), step(hz, px.y) * 0.5);
  // the sun, striped as it sinks
  vec2 sun = vec2(floor(W * 0.62), hz + 12.0);
  float ds = length(px - sun);
  float below = sun.y + 4.0 - px.y;
  float gaps = step(0.0, below) * step(mod(px.y, 5.0), clamp(below / 6.0, 0.0, 3.0));
  float disc = step(ds, 22.0) * (1.0 - gaps) * step(hz, px.y);
  o = over(o, dither(vec3(1.0, 0.5, 0.25), vec3(1.0, 0.92, 0.45), (px.y - sun.y + 22.0) / 44.0, px), disc);
  // flat clouds lit pink from below
  float cn = noise(vec2(px.x * 0.025 + t * 0.03, floor(px.y / 3.0) * 0.4));
  float cloud = step(0.62, cn) * step(115.0, px.y) * step(px.y, 160.0);
  float lit = step(0.62, noise(vec2(px.x * 0.025 + t * 0.03, floor((px.y - 3.0) / 3.0) * 0.4)));
  o = over(o, lit < 0.5 ? vec3(1.0, 0.65, 0.6) : vec3(0.6, 0.3, 0.5), cloud);
  // the sea, the sun's reflection glittering on it
  float sea = step(px.y, hz - 1.0) * step(26.0, px.y);
  float deep = (hz - px.y) / 44.0;
  o = over(o, dither(vec3(0.5, 0.25, 0.45), vec3(0.15, 0.12, 0.32), deep, px), sea * 0.8);
  float wv = step(0.86, fract((px.y + tf * 4.0) / 7.0)) * step(0.55, noise(vec2(px.x * 0.08 + tf, px.y)));
  o = over(o, vec3(0.75, 0.45, 0.6), wv * sea);
  float spread = 24.0 - deep * 6.0;
  float glitter = step(abs(px.x - sun.x), spread) * step(0.45, hash(vec2(floor((px.x + px.y * 3.0) / 4.0), px.y + floor(t * 4.0))));
  o = over(o, mix(vec3(1.0, 0.65, 0.3), vec3(1.0, 0.9, 0.5), step(0.8, hash(px + tf))), glitter * sea * step(mod(px.y, 2.0), 0.5));
  // the sailboat on the horizon
  float bx = mod(W * 0.2 + t * 2.0, W + 40.0) - 20.0;
  vec2 bq = px - vec2(floor(bx), hz);
  float hull = step(abs(bq.x), 6.0 - max(0.0, -bq.y) ) * step(-2.0, bq.y) * step(bq.y, 0.0);
  float sail = step(1.0, bq.y) * step(bq.y, 13.0) * step(0.0, bq.x + 1.0) * step(bq.x, (13.0 - bq.y) * 0.5);
  o = over(o, vec3(0.2, 0.08, 0.2), clamp(hull + sail, 0.0, 1.0));
  // the waves running up the sand, foam at their edge
  float reach = 26.0 + floor(4.0 * (0.5 + 0.5 * sin(t * 0.6)) + 2.0 * sin(px.x * 0.06 + t * 0.4));
  float sand = step(px.y, reach);
  o = over(o, dither(vec3(0.95, 0.68, 0.45), vec3(0.85, 0.52, 0.38), (reach - px.y) / 26.0 + hash(px) * 0.2, px), sand * 0.9);
  float wet = step(px.y, reach) * step(reach - 4.0, px.y);
  o = over(o, vec3(0.7, 0.45, 0.4), wet * 0.6);
  float foam = step(abs(px.y - reach - 1.0), 1.0) * step(0.35, hash(vec2(floor(px.x / 2.0), floor(t * 5.0))));
  o = over(o, vec3(1.0, 0.92, 0.88), foam);
  // the palm tree against the light
  float px0 = floor(W * 0.14);
  float sway = sin(t * 1.1) * 0.08 + sin(t * 2.3) * 0.03;
  float ty = px.y - 20.0;
  float cx = px0 + 0.0022 * ty * ty + sway * ty * 0.1;
  float trunk = step(0.0, ty) * step(ty, 95.0) * step(abs(px.x - cx), 2.5 - ty * 0.008) * (0.7 + 0.3 * step(1.0, mod(ty, 5.0)));
  vec2 top = vec2(px0 + 0.0022 * 95.0 * 95.0 + sway * 9.5, 115.0);
  float fronds = 0.0;
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    float a = -2.6 + fi * 0.86 + sway * 2.0 + sin(t * 1.7 + fi) * 0.05;
    vec2 dir = vec2(cos(a), sin(a) * 0.6 + 0.35);
    vec2 rel = px - top;
    float L = 30.0 + 6.0 * hash(vec2(fi, 1.0));
    float s = clamp(dot(rel, dir) / L, 0.0, 1.0);
    vec2 on = dir * s * L - vec2(0.0, s * s * L * 0.55);
    float thick = (1.0 - s) * 3.5 + 0.8 + step(0.5, fract(s * 9.0)) * (1.0 - s) * 2.0;
    fronds += step(length(rel - on), thick) * step(0.02, s);
  }
  o = over(o, vec3(0.15, 0.07, 0.15), clamp(trunk + fronds + step(length(px - top), 3.5), 0.0, 1.0));
  // gulls flapping by
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float gx = mod(t * (8.0 + fi * 3.0) + fi * 90.0, W + 30.0) - 15.0;
    vec2 g = px - vec2(floor(gx), floor(130.0 + fi * 12.0 + sin(t + fi) * 4.0));
    float flap = step(0.5, fract(t * 2.5 + fi * 0.3));
    float wing = step(abs(g.x), 4.0) * step(abs(g.y - floor(abs(g.x) * (flap > 0.5 ? 0.6 : -0.3))), 0.5);
    o = over(o, vec3(0.2, 0.1, 0.22), wing);
  }
  gl_FragColor = o;
}
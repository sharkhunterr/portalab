// Portalab — ambient/constellations: the « constellations » ambience (spec 028, B2)
float fbm4(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = turn * p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}
// thin bright filaments: the creases of a noise, sharpened octave after octave
float ridged(vec2 p) {
  float v = 0.0;
  float a = 0.55;
  float prev = 1.0;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 5; i++) {
    float n = 1.0 - abs(2.0 * noise(p) - 1.0);
    n = n * n;
    v += n * a * prev;
    prev = n;
    p = turn * p * 2.1 + vec2(3.1, 7.7);
    a *= 0.5;
  }
  return v;
}
float starfield(vec2 p, float scale, float t, float density) {
  vec2 sg = p * scale;
  vec2 id = floor(sg);
  float h = hash(id);
  vec2 at = vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5;
  float s = step(1.0 - density, h) * smoothstep(0.12 + 0.1 * hash(id + 1.3), 0.0, length(fract(sg) - 0.5 - at * 0.6));
  return s * (0.55 + 0.45 * sin(t * (1.0 + 2.0 * hash(id + 5.0)) + h * 40.0));
}
// a star seen by a great telescope: a bright core, a halo and six diffraction spikes (two short ones across)
float spiked(vec2 d, float size) {
  float r = length(d);
  float core = exp(-r / size * 3.2) + exp(-r / size * 0.9) * 0.18;
  float spikes = 0.0;
  for (int i = 0; i < 3; i++) {
    float a = float(i) * 1.0472 + 1.5708;
    vec2 dir = vec2(cos(a), sin(a));
    float along = abs(dot(d, dir));
    float across = abs(dot(d, vec2(-dir.y, dir.x)));
    spikes += exp(-across / size * 9.0) * exp(-along / size * 0.55);
  }
  spikes += 0.5 * exp(-abs(d.y) / size * 9.0) * exp(-abs(d.x) / size * 1.1);
  return core + spikes * 0.55;
}
// a few big stars with their spikes, slowly twinkling, coloured blue-white to gold
vec4 brightStars(vec4 o, vec2 p, float aspect, float t, float seed, float count) {
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    if (fi >= count) break;
    vec2 at = vec2(hash(vec2(fi, seed)) * aspect, 0.08 + hash(vec2(fi, seed + 1.0)) * 0.86);
    float size = 0.006 + 0.008 * hash(vec2(fi, seed + 2.0));
    float tw = 0.75 + 0.25 * sin(t * (0.7 + hash(vec2(fi, seed + 3.0))) + fi * 2.0);
    vec3 col = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.88, 0.7), hash(vec2(fi, seed + 4.0)));
    o = over(o, col, clamp(spiked(p - at, size) * tw, 0.0, 1.0));
  }
  return o;
}

vec2 cstar(float k, float i) {
  if (k < 0.5) { // Orion
    if (i < 0.5) return vec2(-0.35, 0.45); if (i < 1.5) return vec2(0.3, 0.4); if (i < 2.5) return vec2(-0.08, 0.0);
    if (i < 3.5) return vec2(0.0, 0.03); if (i < 4.5) return vec2(0.08, 0.06); if (i < 5.5) return vec2(-0.28, -0.45);
    if (i < 6.5) return vec2(0.35, -0.42); return vec2(0.0, 0.62);
  }
  if (k < 1.5) { // Cassiopeia
    if (i < 0.5) return vec2(-0.55, 0.1); if (i < 1.5) return vec2(-0.27, -0.15); if (i < 2.5) return vec2(0.0, 0.06);
    if (i < 3.5) return vec2(0.27, -0.2); if (i < 4.5) return vec2(0.55, 0.15); return vec2(9.0);
  }
  if (k < 2.5) { // the Plough
    if (i < 0.5) return vec2(-0.6, 0.25); if (i < 1.5) return vec2(-0.33, 0.3); if (i < 2.5) return vec2(-0.12, 0.2);
    if (i < 3.5) return vec2(0.08, 0.08); if (i < 4.5) return vec2(0.12, -0.2); if (i < 5.5) return vec2(0.52, -0.15);
    if (i < 6.5) return vec2(0.5, 0.12); return vec2(9.0);
  }
  if (k < 3.5) { // the Swan
    if (i < 0.5) return vec2(0.0, 0.52); if (i < 1.5) return vec2(0.0, 0.12); if (i < 2.5) return vec2(0.02, -0.5);
    if (i < 3.5) return vec2(-0.45, 0.18); if (i < 4.5) return vec2(0.45, 0.04); if (i < 5.5) return vec2(-0.22, 0.14);
    if (i < 6.5) return vec2(0.22, 0.08); return vec2(9.0);
  }
  if (k < 4.5) { // the Lion
    if (i < 0.5) return vec2(-0.35, -0.15); if (i < 1.5) return vec2(-0.4, 0.1); if (i < 2.5) return vec2(-0.3, 0.3);
    if (i < 3.5) return vec2(-0.12, 0.36); if (i < 4.5) return vec2(-0.05, 0.16); if (i < 5.5) return vec2(0.22, 0.12);
    if (i < 6.5) return vec2(0.52, -0.05); return vec2(0.22, -0.14);
  }
  // the Scorpion
  if (i < 0.5) return vec2(-0.5, 0.42); if (i < 1.5) return vec2(-0.36, 0.26); if (i < 2.5) return vec2(-0.14, 0.12);
  if (i < 3.5) return vec2(0.02, -0.06); if (i < 4.5) return vec2(0.12, -0.28); if (i < 5.5) return vec2(0.3, -0.4);
  if (i < 6.5) return vec2(0.48, -0.3); return vec2(0.45, -0.08);
}
// the lines: pairs of stars (« 9 »: none)
vec2 cline(float k, float j) {
  if (k < 0.5) {
    if (j < 0.5) return vec2(0, 2); if (j < 1.5) return vec2(1, 4); if (j < 2.5) return vec2(2, 3); if (j < 3.5) return vec2(3, 4);
    if (j < 4.5) return vec2(2, 5); if (j < 5.5) return vec2(4, 6); if (j < 6.5) return vec2(0, 7); return vec2(1, 7);
  }
  if (k < 1.5) { if (j < 3.5) return vec2(j, j + 1.0); return vec2(9.0); }
  if (k < 2.5) { if (j < 5.5) return vec2(j, j + 1.0); if (j < 6.5) return vec2(6, 3); return vec2(9.0); }
  if (k < 3.5) {
    if (j < 0.5) return vec2(0, 1); if (j < 1.5) return vec2(1, 2); if (j < 2.5) return vec2(3, 5); if (j < 3.5) return vec2(5, 1);
    if (j < 4.5) return vec2(1, 6); if (j < 5.5) return vec2(6, 4); return vec2(9.0);
  }
  if (k < 4.5) {
    if (j < 4.5) return vec2(j, j + 1.0); if (j < 5.5) return vec2(5, 6); if (j < 6.5) return vec2(6, 7); return vec2(7, 0);
  }
  if (j < 6.5) return vec2(j, j + 1.0); return vec2(9.0);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float turn = t * 0.004;
  vec2 rp = mat2(cos(turn), -sin(turn), sin(turn), cos(turn)) * (p - vec2(0.5 * aspect, 0.5));
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(rp, 80.0, t, 0.03));
  o = over(o, vec3(0.8, 0.85, 1.0), starfield(rp + 4.0, 150.0, t, 0.025) * 0.5);
  float period = 9.0;
  float k = mod(floor(t / period), 6.0);
  float cyc = mod(t, period);
  float fade = smoothstep(0.0, 0.6, cyc) * smoothstep(period, period - 1.4, cyc);
  vec2 centre = vec2((0.3 + 0.4 * hash(vec2(k, floor(t / 54.0)))) * aspect, 0.35 + 0.3 * hash(vec2(k + 3.0, floor(t / 54.0))));
  float scale = 0.55;
  vec2 q = (p - centre) / scale;
  float stars = 0.0;
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    vec2 s = cstar(k, fi);
    float born = 0.4 + fi * 0.35;
    float tw = 0.85 + 0.15 * sin(t * 3.0 + fi);
    stars += exp(-length(q - s) * 55.0) * smoothstep(born, born + 0.3, cyc) * tw;
    stars += exp(-length(q - s) * 14.0) * 0.12 * smoothstep(born, born + 0.3, cyc);
  }
  float lines = 0.0;
  for (int j = 0; j < 8; j++) {
    float fj = float(j);
    vec2 pair = cline(k, fj);
    if (pair.x > 8.5) continue;
    vec2 a = cstar(k, pair.x);
    vec2 b = cstar(k, pair.y);
    vec2 ab = b - a;
    float h = clamp(dot(q - a, ab) / dot(ab, ab), 0.0, 1.0);
    float drawn = clamp((cyc - 3.2 - fj * 0.35) / 0.4, 0.0, 1.0);
    lines += smoothstep(0.012, 0.0, length(q - a - ab * h)) * step(h, drawn);
  }
  float shine = 1.0 + 0.6 * exp(-abs(cyc - 6.5) * 2.0);
  o = over(o, vec3(0.5, 0.75, 1.0), clamp(lines, 0.0, 1.0) * 0.55 * fade * shine);
  o = over(o, vec3(1.0, 0.95, 0.85), clamp(stars, 0.0, 1.0) * fade);
  gl_FragColor = o;
}
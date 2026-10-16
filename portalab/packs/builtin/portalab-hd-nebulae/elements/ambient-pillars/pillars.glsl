// Portalab — ambient/pillars: the « pillars » ambience (spec 028, B2)
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

// a column of dust, leaning, lumpy, wide at its foot, its head swollen — a signed distance (< 0 inside)
float column(vec2 p, vec2 base, float top, float wid, float lean, float seed) {
  float h = max(top - base.y, 0.01);
  float y = clamp((p.y - base.y) / h, 0.0, 1.2);
  float x = p.x - base.x - lean * (p.y - base.y) - 0.04 * sin(y * 4.0 + seed);
  float w = wid * (1.6 - 0.9 * smoothstep(0.0, 1.0, y)) * (1.0 + 0.55 * (fbm4(vec2(p.y * 4.5, seed)) - 0.5));
  w += wid * 0.5 * smoothstep(0.08, 0.0, abs(y - 0.35 - 0.2 * hash(vec2(seed, 2.0)))) * step(0.0, x * sign(hash(vec2(seed, 3.0)) - 0.5));
  float side = abs(x) - w;
  vec2 hp = vec2(p.x - base.x - lean * h - 0.04 * sin(4.0 + seed), p.y - top);
  float head = length(hp * vec2(1.0, 1.15)) - wid * 0.95;
  float d = min(max(side, p.y - top), head);
  return d + (fbm(p * 12.0 + seed) - 0.5) * 0.05 + (fbm4(p * 5.0 + seed) - 0.5) * 0.06 + (noise(p * 40.0) - 0.5) * 0.012;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec2 w = vec2(fbm4(p * 1.6 + vec2(t * 0.008, 0.0)), fbm4(p * 1.6 + vec2(3.0, t * 0.006)));
  float field = fbm(p * 1.3 + w * 1.4);
  vec3 sky = mix(vec3(0.03, 0.07, 0.26), vec3(0.14, 0.32, 0.68), smoothstep(0.35, 0.85, field));
  sky = mix(sky, vec3(0.28, 0.55, 0.75), smoothstep(0.7, 0.95, field) * 0.4);
  float a = 0.32 + 0.25 * field;
  vec4 o = vec4(sky * a, a);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 85.0, t, 0.045));
  o = over(o, vec3(0.8, 0.88, 1.0), starfield(p + 9.0, 170.0, t, 0.04) * 0.7);
  float x0 = 0.16 * aspect;
  float d1 = column(p, vec2(x0, -0.12), 0.8, 0.075, 0.32, 1.0);
  float d2 = column(p, vec2(x0 + 0.3 * aspect, -0.12), 0.58, 0.06, 0.28, 4.0);
  float d3 = column(p, vec2(x0 + 0.56 * aspect, -0.12), 0.36, 0.05, 0.2, 7.0);
  float d = min(d1, min(d2, d3));
  float body = smoothstep(0.012, -0.012, d);
  float depth = clamp(-d * 7.0, 0.0, 1.0);
  float fluff = fbm(p * 7.0 + w * 2.0);
  float grain = fbm(p * 20.0 + w * 2.0);
  vec3 dust = mix(vec3(0.58, 0.34, 0.13), vec3(0.2, 0.09, 0.04), depth);
  dust = mix(dust, vec3(0.86, 0.62, 0.3), smoothstep(0.55, 0.85, fluff) * (1.0 - depth) * 0.6);
  dust *= 0.6 + 0.5 * grain * fluff + 0.15;
  // lit from above right: the edges facing the light glow gold, the others stay dark
  vec2 eps = vec2(0.01, 0.0);
  vec2 normal = normalize(vec2(min(column(p + eps.xy, vec2(x0, -0.12), 0.8, 0.075, 0.32, 1.0), d) - d + 1e-4, 0.01));
  float facing = smoothstep(-0.2, 0.8, dot(normalize(vec2(0.6, 0.8)), vec2(1.0, 0.6) * sign(p.x - x0 - 0.32 * (p.y + 0.12))));
  float rim = smoothstep(0.035, 0.0, abs(d)) * (0.35 + 0.65 * facing);
  o = over(o, dust, body * 0.96);
  o = over(o, vec3(1.0, 0.8, 0.48), rim * 0.6);
  vec2 tip1 = vec2(x0 + 0.32 * 0.92 + 0.04 * sin(5.0), 0.8);
  vec2 tip2 = vec2(x0 + 0.3 * aspect + 0.28 * 0.7 + 0.04 * sin(8.0), 0.58);
  float tops = exp(-length((p - tip1) * vec2(1.0, 1.6)) * 16.0) + exp(-length((p - tip2) * vec2(1.0, 1.6)) * 20.0);
  o = over(o, vec3(1.0, 0.32, 0.28), tops * (0.5 + 0.15 * sin(t * 0.7)));
  for (int i = 0; i < 2; i++) {
    vec2 tip = i == 0 ? tip1 : tip2;
    vec2 v = p - tip;
    float plume = fbm4(vec2(v.x * 8.0 - t * 0.03, v.y * 5.0 - t * 0.12)) * smoothstep(0.26, 0.0, length(v * vec2(1.2, 0.75))) * step(-0.03, v.y);
    o = over(o, vec3(0.9, 0.78, 0.6), smoothstep(0.35, 0.7, plume) * 0.5);
  }
  o = brightStars(o, p, aspect, t, 41.0, 6.0);
  gl_FragColor = o;
}